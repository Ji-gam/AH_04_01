import csv
from collections.abc import Iterable
from typing import Any

from langchain_chroma import Chroma

from ai_worker.core import observability
from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger
from ai_worker.ingest.embeddings import get_embeddings
from ai_worker.ingest.pipeline import build_vector_store
from ai_worker.ingest.sources import SOURCE_DIR, STRUCTURED
from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.services.drug_name_resolver import (
    DrugNameIndex,
    build_index,
    build_ingredient_index,
    build_product_ingredient_map,
)

# 제품명 -> 성분명 조회 사전(RAG 문서 아님, `ai_worker/scripts/export_source_from_mysql.py`가
# 빌드 시점에 만든다). `source/` 안에 있지만 밑줄 접두어라 ingest 색인에서는 제외된다
# (`ai_worker/ingest/sources.py`의 `_is_source_file`) — RAG와 같은 배포 산출물 취급만 받는다.
PRODUCT_INGREDIENT_MAP_PATH = SOURCE_DIR / "_item_ingredient_map.csv"

logger = setup_logger("ai_worker.retrieve_service")

# DUR 규칙은 CSV라 structured 컬렉션에 있다. 이름 문자열을 여기 또 적지 않는다 —
# 예전엔 "dur_rules"가 매니페스트 + 파이썬 3곳에 흩어져 있었고, 그 파일들엔 하나같이
# "매니페스트의 collection: 값과 일치해야 한다"는 주석이 붙어 있었다. 손으로 맞춰야 하는
# 것을 주석으로 경고하는 대신, 맞출 필요가 없게 한 곳에서 가져온다.
#
# 이 컬렉션엔 DUR 규칙(성분 단위)과 e약은요(제품 단위)가 함께 있다. 둘은 필터 키가 달라
# 서로 섞이지 않는다 — DUR 문서엔 ingr_name만, e약은요 문서엔 item_name만 있다.
COLLECTION_NAME = STRUCTURED

# 싱글톤 데이터베이스 인스턴스 및 이름 캐시 홀더.
# 값 타입을 Any로 둔 이유: 테스트에서 이 딕셔너리에 실제 Chroma 대신 duck-typed
# fake 객체를 직접 대입해 모킹하므로(ai_worker/tests/test_main.py 참고), Chroma로
# 좁히면 오히려 모킹이 막힌다.
db_holder: dict[str, Any] = {
    "db": None,
    "ingr_names": DrugNameIndex(),
    "drug_names": DrugNameIndex(),
    "product_ingredients": {},
}


def _load_product_ingredient_map() -> dict[str, tuple[str, ...]]:
    """빌드 시점에 만들어진 제품명->성분명 조회 사전을 읽는다. 파일이 없으면(아직
    `export_source_from_mysql`을 안 돌린 로컬/테스트 환경) 빈 사전 — 브릿지 없이도
    기존 성분명/약 이름 검색은 그대로 동작해야 하므로 예외를 던지지 않는다."""
    if not PRODUCT_INGREDIENT_MAP_PATH.exists():
        logger.warning(f"{PRODUCT_INGREDIENT_MAP_PATH.name} 없음 — 제품명->성분명 브릿지 비활성화")
        return {}
    with PRODUCT_INGREDIENT_MAP_PATH.open(encoding="utf-8", newline="") as f:
        mapping = build_product_ingredient_map(csv.DictReader(f))
    logger.info(f"Cached product-ingredient bridge: {len(mapping)}개 제품")
    return mapping


def cache_searchable_names(db: Chroma, extra_item_names: Iterable[str] = ()) -> None:
    """적재된 문서에서 질의에 쓸 이름을 뽑아 캐싱한다 — 성분명과 약 이름 **둘 다**.

    약 이름을 같이 담는 이유: 사람은 "아세트아미노펜 부작용"이 아니라 "타이레놀 부작용"이라고
    묻는다. 성분명만 보던 시절엔 그런 질문이 전부 0건이었다(`drug_name_resolver` 참고).

    `extra_item_names`(T-LLM-2-rag-brand-name-bridge): Chroma에 적재된 문서는 e약은요
    부분집합뿐이라(~4,758건), "인데놀"처럼 e약은요엔 없지만 전체 허가목록(43K)엔 있는
    브랜드는 이 스캔만으로는 절대 안 걸린다. 호출부가 브랜드->성분 브릿지
    (`_load_product_ingredient_map`의 키, 즉 전체 허가목록 유래 제품명)를 여기 같이
    넘겨 `drug_names` 인덱스 자체를 넓힌다 — 문서가 없어도 "이 이름은 아는 약이다"까지는
    알아보게 한다."""
    try:
        logger.info("Extracting searchable names (ingredients + drug names) from ChromaDB...")
        # metadatas만 조회 (langchain-chroma의 공개 API — 사설 `_collection` 미사용)
        data = db.get(include=["metadatas"])
        metadatas = (data.get("metadatas") or []) if data else []
        ingr_names: set[str] = set()
        item_names: set[str] = set(extra_item_names)
        for meta in metadatas:
            if not meta:
                continue
            ingr_name = meta.get("ingr_name")
            if isinstance(ingr_name, str) and ingr_name.strip():
                ingr_names.add(ingr_name.strip())
            item_name = meta.get("item_name")
            if isinstance(item_name, str) and item_name.strip():
                item_names.add(item_name.strip())
        db_holder["ingr_names"] = build_ingredient_index(ingr_names)
        db_holder["drug_names"] = build_index(item_names)
        logger.info(f"Cached {len(ingr_names)} ingredients and {len(item_names)} drug names")
    except Exception as e:
        logger.error(f"Failed to cache searchable names: {e}")


def initialize_rag() -> None:
    """서비스 기동 시 벡터스토어 핸들과 성분명 인덱스를 캐싱한다. **색인은 하지 않는다.**

    예전엔 여기서 `ingest_all()`을 돌렸고, 그게 이 시스템 최악의 버그였다. cleanup="full"
    이라 `source/`에 파일이 하나 안 보이면(다른 컴퓨터, git에 없는 큰 파일, 볼륨 미마운트)
    그 문서들이 **부팅과 동시에 삭제**됐다. 아래 except가 그걸 로그로만 삼켜서 아무도 몰랐다.

    색인은 사건이지 감시 루프가 아니다. 사람이 `python -m ai_worker.ingest`를 치거나
    관리자 화면에서 누를 때만 돈다.

    임베딩 모델은 여기서 미리 올린다(약 10초). 안 그러면 그 10초를 **첫 질문한 사용자가**
    낸다 — 기동은 아무도 안 보지만 첫 질문은 사람이 기다린다."""
    logger.info("Initializing RAG...")
    try:
        db = build_vector_store(COLLECTION_NAME)
        db_holder["db"] = db
        # 브릿지를 먼저 로드해야 그 제품명 전체를 drug_names 인덱스에 병합할 수 있다
        # (cache_searchable_names의 extra_item_names 참고) — 순서를 바꾸면 안 된다.
        db_holder["product_ingredients"] = _load_product_ingredient_map()
        cache_searchable_names(db, extra_item_names=db_holder["product_ingredients"].keys())
        warm_up_embeddings()
        logger.info("RAG Initialization completed.")
    except Exception as e:
        logger.error(f"Failed to initialize RAG on startup: {e}")


def warm_up_embeddings() -> None:
    """임베딩 모델을 미리 메모리에 올린다. 실패해도 기동을 막지 않는다 — 그땐 첫 질의가
    느릴 뿐이고, 진짜 문제라면 그 질의에서 제대로 된 예외가 난다."""
    try:
        get_embeddings().embed_query("워밍업")
        logger.info("Embedding model warmed up.")
    except Exception as e:
        logger.warning(f"임베딩 예열 실패(첫 질의가 느려질 뿐 동작엔 문제없음): {e}")


def ensure_db() -> Chroma:
    """벡터스토어가 아직 초기화되지 않았으면 lazy하게 만든다.
    실패 시(`EmbeddingUnavailableError` 등) 도메인 예외를 그대로 전파한다 — HTTP 매핑은 라우터 몫."""
    db = db_holder["db"]
    if db is None:
        db = build_vector_store(COLLECTION_NAME)
        db_holder["db"] = db
        db_holder["product_ingredients"] = _load_product_ingredient_map()
        cache_searchable_names(db, extra_item_names=db_holder["product_ingredients"].keys())
    return db


def _build_filters(query: str) -> list[tuple[dict[str, Any], str]]:
    """질의에서 성분명이나 약 이름을 찾아 (메타데이터 필터, 검색 문구) 쌍의 목록을 만든다.
    못 찾으면 빈 리스트. 필터마다 검색 문구를 따로 두는 이유는 아래 브릿지 설명 참고.

    성분명을 먼저 본다 — DUR 금기/주의 규칙이 성분 단위라 더 구체적인 답이기 때문이다.
    성분명이 없으면 약 이름으로 e약은요(효능/용법/부작용 산문)를 찾는다. 둘 다 같은 접두사
    인덱스(`drug_name_resolver.DrugNameIndex`)로 찾는다 — 사용자는 "졸피뎀타르타르산염"이
    아니라 "졸피뎀"까지만 치기 때문이다.

    DUR 문서엔 ingr_name만, e약은요 문서엔 item_name만 있어 원래는 서로 배타적이었다.
    "타이레놀 같이 먹어도 돼?"처럼 제품명으로 물으면 DUR 병용금기(성분 단위, 아세트아미노펜)를
    못 뽑던 문제는 `db_holder["product_ingredients"]`(제품명->성분명 조회 사전,
    `drug_name_resolver.build_product_ingredient_map` 참고)로 다리를 놓아 해결한다 — 제품명이
    매칭되면 그 제품의 성분 필터도 목록에 함께 넣는다.

    필터를 하나의 `$or`로 합치지 않고 목록으로 따로 반환하는 이유: Chroma의
    similarity_search는 필터(그리고 `$or`로 묶은 필터 전체)에서 상위 k개를 고른다. e약은요는
    산문이라 쿼리와 임베딩 거리가 더 가깝게 나와, 하나의 `$or`로 합치면 DUR 규칙(짧은 템플릿
    문장)이 top-k에서 통째로 밀려난다(실측 2026-07-20: "타이레놀 같이 먹어도 돼?"가 e약은요
    5건만 반환하고 병용금기 규칙은 후보에도 못 낌). `search_documents()`가 필터마다 따로
    top-k를 뽑아야 두 종류 다 안전하게 살아남는다."""
    matched_ingr = db_holder["ingr_names"].resolve(query)
    if matched_ingr is not None:
        key, ingredients = matched_ingr
        logger.info(f"Dynamic metadata filter applied: ingr '{key}' -> {len(ingredients)}개 성분")
        return [({"ingr_name": ingredients[0] if len(ingredients) == 1 else {"$in": ingredients}}, query)]

    matched_drug = db_holder["drug_names"].resolve(query)
    if matched_drug is not None:
        key, products = matched_drug
        logger.info(f"Dynamic metadata filter applied: drug '{key}' -> {len(products)}개 제품")
        # 브랜드 하나에 제품이 여럿이다("타이레놀" -> 정/서방정/현탁액...). 하나만 고르면
        # 엉뚱한 제형이 잡히므로 전부 넘기고 유사도가 고르게 한다. e약은요 문서는 본문에
        # 브랜드명을 그대로 쓰므로(예: "itemName: 인데놀정10mg...") 원본 질의 그대로 비교해도 된다.
        filters: list[tuple[dict[str, Any], str]] = [
            ({"item_name": products[0] if len(products) == 1 else {"$in": products}}, query)
        ]

        # 브릿지가 주는 성분명 표기는 MySQL item_ingredient_map 원문이라 염(鹽) 형태
        # ("프로프라놀롤염산염")일 수 있고, DUR 문서엔 염을 뗀 원형("프로프라놀롤")으로
        # 저장돼 있다(T-LLM-2-rag-brand-name-bridge 실측). 원문을 그대로 필터 값으로 쓰면
        # Chroma 정확매치가 항상 0건이 되므로, 사용자 질의를 정규화할 때와 같은 인덱스
        # (`ingr_names`)로 한 번 더 정규화해 실제 문서에 저장된 표기를 찾는다. 정규화가
        # 실패하면(그 성분에 대한 DUR 문서가 애초에 없음) 조용히 건너뛴다 — 억지로 걸어도
        # 어차피 0건이라 다름없다.
        bridged_ingredients: set[str] = set()
        for product in products:
            for raw_ingr_name in db_holder["product_ingredients"].get(product, ()):
                resolved = db_holder["ingr_names"].resolve(raw_ingr_name)
                if resolved is not None:
                    bridged_ingredients.update(resolved[1])

        if bridged_ingredients:
            ingr_list = sorted(bridged_ingredients)
            logger.info(f"Dynamic metadata filter applied: drug '{key}' -> 성분 브릿지 {len(ingr_list)}개")
            ingr_filter = {"ingr_name": ingr_list[0] if len(ingr_list) == 1 else {"$in": ingr_list}}
            # DUR 문서는 브랜드명("인데놀")을 절대 쓰지 않고 성분명("프로프라놀롤")만 쓴다.
            # 원본 질의 그대로 임베딩 비교하면 브랜드명이 문서 어휘와 안 겹쳐 유사도 점수가
            # 나쁘게 나와, 실제로 관련 있는 문서가 임계값(RAG_SIMILARITY_THRESHOLD)에 걸려
            # 탈락한다(T-LLM-2-rag-brand-name-bridge 실측: "인데놀 노인이 먹어도 돼?" -> DUR
            # 문서 점수 0.42, 임계값 0.35 미달 — 기존 브랜드 "타이레놀"도 같은 문제였으나
            # e약은요 문서가 늘 함께 걸려 가려져 있었다). 임계값 자체는 건드리지 않는다(그
            # 값은 무관 질문을 걸러내는 별개의 방어선 — config.py 참고) — 이 필터에 한해서만
            # 검색 문구에 정규화된 성분명을 덧붙여 문서 어휘와 겹치게 한다. 원본 질의는
            # 그대로 뒤에 남겨 "노인이 먹어도 돼?" 같은 질문 의도는 보존한다.
            search_text = f"{' '.join(ingr_list)} {query}"
            filters.append((ingr_filter, search_text))

        return filters

    return []


def search_documents(db: Chroma, query: str, limit: int) -> list[DocumentChunk]:
    """질의에서 찾아낸 성분명 또는 약 이름으로 문서를 검색한다. 둘 다 없으면 검색 자체를
    생략하고 빈 목록을 반환한다.

    필터 없이 전체를 유사도 검색하지 않는 이유: DUR 문서는 짧은 템플릿 문장이라 무관한
    성분이 임계값을 통과해버린다(실측: "혈당 관리 운동"이 항고혈압제/항히스타민제와 매칭됨,
    2026-07-16). 이건 "이 약이 안전한가"를 위한 자료이지 일반 건강 지식 베이스가 아니므로,
    약이 식별 안 되면 애초에 관련 문서가 없다고 보는 게 맞다.

    임베딩 호환성 검증(`assert_embedding_compatible`)은 호출자(라우터) 책임이다."""
    logger.info(f"Retrieving documents for query: '{query}' (limit: {limit})")

    with observability.observe_span("search_documents", as_type="retriever", query=query, limit=limit) as span:
        filters = _build_filters(query)

        if not filters:
            logger.info("쿼리에서 성분명·약 이름을 식별하지 못해 검색을 생략합니다.")
            if span is not None:
                span.update(output=[], metadata={"filters_matched": 0, "reason": "no_name_matched"})
            return []

        # 필터마다 따로 top-k를 뽑아 합친다(단일 $or로 합치지 않는 이유는 _build_filters
        # 참고) — 제품명 브릿지가 걸리면 필터가 2개(item_name, ingr_name)라 최대 limit*2건이
        # 후보로 모일 수 있다. 필터마다 검색 문구(search_text)도 다를 수 있다 — 성분 브릿지
        # 필터는 원본 질의 대신 정규화된 성분명을 덧붙인 문구로 비교한다(_build_filters 참고).
        docs_with_scores: list[tuple[Any, float]] = []
        for filter_dict, search_text in filters:
            docs_with_scores.extend(db.similarity_search_with_score(search_text, k=limit, filter=filter_dict))

        # 디버깅 로그 출력 (유사도 거리 분석용)
        for doc, score in docs_with_scores:
            logger.info(
                f"DEBUG_SCORE: INGR={doc.metadata.get('ingr_name')}, score={score}, "
                f"source_id={doc.metadata.get('source_id')}"
            )

        # 임계값(score < threshold)을 만족하는 유효한 문서만 반환합니다. 값은 config에서
        # 가져와 임베딩 백엔드별로 튜닝할 수 있게 한다(거리 스케일이 백엔드마다 다름).
        threshold = settings.RAG_SIMILARITY_THRESHOLD
        valid_docs_with_scores = [(doc, score) for doc, score in docs_with_scores if score < threshold]
        # 필터별로 따로 뽑아 합쳤으니(위 주석 참고) 점수 오름차순(더 유사할수록 앞)으로
        # 다시 정렬해야 어느 필터에서 나왔든 더 관련 있는 문서가 앞에 온다.
        valid_docs_with_scores.sort(key=lambda pair: pair[1])

        # 문서의 내용과 메타데이터를 함께 추출
        chunks = [
            DocumentChunk(content=doc.page_content, metadata=doc.metadata, score=score)
            for doc, score in valid_docs_with_scores
        ]
        logger.info(
            f"Found {len(chunks)} relevant chunks after filter and threshold (candidates: {len(docs_with_scores)})"
        )
        if span is not None:
            span.update(
                output=[{"source_id": c.metadata.get("source_id"), "score": c.score} for c in chunks],
                metadata={
                    "filters_matched": len(filters),
                    "candidate_count": len(docs_with_scores),
                    "threshold": threshold,
                },
            )
        return chunks
