"""
T-LLM-7-3(개정): PubMed 논문 RAG 인제스천. 오프라인/배치로 실행하며 두 단계로 나뉜다.

1단계(fetch_and_append_category_papers): PubMed에서 질환×카테고리
(`app/services/content_service.py`의 CATEGORIES: LIFESTYLE/FOOD/MEDICAL_NEWS) 조합별로
원본 논문(제목+초록+PMID)을 수집해 ai_worker/source/{질환}.json에 그대로 저장한다
(T-RAG-SOURCE-MIGRATION: 예전 mock_data_for_papers_raw/에서 이전). 가공(청킹/임베딩)
없이 원문만 남겨, 사람이 직접 열어 품질/건수를 검토할 수 있게 한다.

카테고리 구분 없이 질환만으로 넓게 수집하는 방식은 초기에 시도했다가 폐기했다 —
"약물/치료" 위주로 쏠려서 라이프스타일/식단/최신동향 같은 실제 사용자 질문 각도를
반영하지 못했기 때문. 항상 카테고리 단위로 수집한다.

2단계(ensure_paper_summaries): 논문마다 한국어 요약을 LLM으로 1회 생성해
source/paper_summaries_ko.json에 캐시한다. 사용자 질의는 한국어인데 논문은 영어라,
이 요약이 없으면 정답 논문과 무관 논문의 거리 차가 노이즈 수준으로 좁아진다
(_paper_page_content의 실측치 참고). 비용은 인제스트 시점 1회뿐이라 채팅 응답은 안 느려진다.

3단계(ingest_papers): 원본 JSON+요약 캐시를 읽어(PubMed 재호출 없음) 임베딩 후 Chroma
컬렉션(pubmed_papers)에 저장한다. 초록 1편 = 청크 1개이며, 임베딩되는 본문 앞에
"[질환 / 카테고리] 한국어요약 / 원문제목"을 접두한다(build_documents 참고 — 고정 크기
분할을 쓰던 과거 방식이 컬렉션의 70%를 맥락 없는 조각으로 만들었다). PMID 기준 증분
인제스천이라 이미 색인된 논문은 다시 임베딩하지 않는다(원본이 늘어나도 신규분만 과금됨).
DUR 인제스천(ingest.py)의 임베딩/Chroma 인프라를 그대로 재사용.

run_daily_pipeline: 1단계+2단계를 순서대로 잇는 완결된 배치. 매일 이 함수(또는
`--pipeline` CLI) 하나만 실행하면 "신규 논문 수집 -> 색인"까지 사람 개입 없이 끝까지
돈다. 다만 "이 명령을 매일 자동으로 실행시키는" 스케줄러(cron/Celery beat) 자체는
아직 안 붙였다 — 스테이징 환경이 없는 지금은 배치 로직만 수동 트리거로 완성해두고,
실제 자동 스케줄링은 스테이징이 생긴 뒤 별도로 붙이기로 결정했다(T-LLM-3와 동일 원칙).
그때까지는 아래 명령을 사람이 매일 한 번 수동 실행한다:

    uv run python -m ai_worker.tasks.ingest_papers --pipeline

실행(개별 단계 디버깅용):
    uv run python -m ai_worker.tasks.ingest_papers                        # 1단계만(원본 수집)
    uv run python -m ai_worker.tasks.ingest_papers --summarize-only       # 2단계만(한국어 요약 캐시)
    uv run python -m ai_worker.tasks.ingest_papers --index-only           # 2+3단계(요약 미스분+색인)
    uv run python -m ai_worker.tasks.ingest_papers --index-only --force   # 컬렉션 삭제 후 전체 재색인
                                                                          # (요약 캐시는 재사용 = 재과금 없음)
"""

import argparse
import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ai_worker.core.config import settings
from ai_worker.tasks.ingest import CHROMA_DIR, active_embedding_model, get_embeddings

logger = logging.getLogger("ai_worker.ingest_papers")
logging.basicConfig(level=logging.INFO)

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_EFETCH_BATCH_SIZE = 50

# T-RAG-SOURCE-MIGRATION: mock_data_for_papers_raw/(실험용 스냅샷, 폐기)에서
# ai_worker/source/(RAG+구조화 데이터가 함께 모이는 단일 원천)로 이전.
RAW_DATA_DIR = Path(__file__).parent.parent / "source"

# DUR과 도메인이 섞이지 않도록 별도 컬렉션(같은 CHROMA_DIR 아래).
PAPER_COLLECTION_NAME = "pubmed_papers"

# 원래 실시간 검색 도구(ai_worker/tools/paper_search.py)에 있던 값을 그대로 이식.
# 답변 프롬프트가 "구체적 수치 인용"을 요구하므로, Review(종합 논문) 대신 원 연구
# (RCT/Clinical Trial, 실제 실험 수치를 보고하는 논문)로 한정한다(카테고리별로 예외 있음,
# _CATEGORIES_REQUIRING_TRIAL_FILTER 참고).
SUPPORTED_DISEASES = ["암", "심장질환", "뇌혈관질환", "당뇨", "간질환"]
_TRIAL_FILTER = "(Clinical Trial[Publication Type] OR Randomized Controlled Trial[Publication Type])"

_DISEASE_MESH_TERMS: dict[str, str] = {
    "암": '"Neoplasms"[MeSH Terms]',
    "심장질환": '"Heart Diseases"[MeSH Terms]',
    "뇌혈관질환": '"Cerebrovascular Disorders"[MeSH Terms]',
    "당뇨": '"Diabetes Mellitus"[MeSH Terms]',
    "간질환": '"Liver Diseases"[MeSH Terms]',
}

# app/services/content_service.py의 CATEGORIES/CATEGORY_TOPICS와 동일한 3분류를
# PubMed MeSH 용어로 옮긴 것. 콘텐츠 파이프라인(T-LLM-3)이 이미 쓰는 분류 체계를
# 그대로 재사용해 두 파이프라인의 "카테고리" 개념이 어긋나지 않게 한다.
CATEGORIES = ["LIFESTYLE", "FOOD", "MEDICAL_NEWS"]
_CATEGORY_SEARCH_TERMS: dict[str, str] = {
    "LIFESTYLE": '("Exercise"[MeSH Terms] OR "Sleep Hygiene"[MeSH Terms] OR "Stress, Psychological"[MeSH Terms])',
    "FOOD": '("Diet, Food, and Nutrition"[MeSH Terms] OR "Diet Therapy"[MeSH Terms] OR "Nutritional Physiological Phenomena"[MeSH Terms])',
    # "신규 발견/치료법/신약" 소식 — RCT로 확정되기 전 단계의 연구도 걸려야 하므로
    # 이 카테고리만 _TRIAL_FILTER를 강제하지 않는다(아래 _category_search_term 참고).
    "MEDICAL_NEWS": (
        '("Drug Discovery"[MeSH Terms] OR "Molecular Targeted Therapy"[MeSH Terms] '
        'OR "Biomarkers, Pharmacological"[MeSH Terms] OR "Drug Therapy"[MeSH Subheading])'
    ),
}
_CATEGORY_RETMAX = 50
# MEDICAL_NEWS는 신약/신규 치료법이 아직 RCT로 확정되기 전 단계도 다뤄야 해서 제외.
_CATEGORIES_REQUIRING_TRIAL_FILTER = {"LIFESTYLE", "FOOD"}


def _category_search_term(disease: str, category: str) -> str:
    base = f"{_DISEASE_MESH_TERMS[disease]} AND {_CATEGORY_SEARCH_TERMS[category]}"
    if category in _CATEGORIES_REQUIRING_TRIAL_FILTER:
        return f"{base} AND {_TRIAL_FILTER}"
    return base


async def _esearch_bulk(client: httpx.AsyncClient, term: str, retmax: int) -> list[str]:
    params: dict[str, str] = {"db": "pubmed", "term": term, "retmax": str(retmax), "sort": "date", "retmode": "json"}
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    response = await client.get(f"{_EUTILS_BASE}/esearch.fcgi", params=params)
    response.raise_for_status()
    result: list[str] = response.json().get("esearchresult", {}).get("idlist", [])
    return result


async def _efetch_batch(client: httpx.AsyncClient, pmids: list[str]) -> str:
    params: dict[str, str] = {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    response = await client.get(f"{_EUTILS_BASE}/efetch.fcgi", params=params)
    response.raise_for_status()
    return response.text


def _flatten_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def _parse_articles(xml_text: str) -> list[dict[str, str | None]]:
    """efetch XML을 파싱해 초록이 있는 논문만 전부(순서 그대로) 반환한다."""
    root = ET.fromstring(xml_text)
    articles: list[dict[str, str | None]] = []
    for article_el in root.findall(".//PubmedArticle"):
        pmid_el = article_el.find(".//PMID")
        title_el = article_el.find(".//ArticleTitle")
        if pmid_el is None or title_el is None or pmid_el.text is None:
            continue
        abstract = " ".join(
            text for el in article_el.findall(".//Abstract/AbstractText") if (text := _flatten_text(el))
        )
        if not abstract:
            continue
        articles.append({"pmid": pmid_el.text.strip(), "title": _flatten_text(title_el), "abstract": abstract})
    return articles


async def _fetch_papers_for_term(client: httpx.AsyncClient, term: str, retmax: int) -> list[dict[str, str | None]]:
    """검색어 하나로 PubMed에서 최대 retmax건의 원본(제목+초록+PMID)을 수집한다."""
    pmids = await _esearch_bulk(client, term, retmax)
    if not pmids:
        return []

    articles: list[dict[str, str | None]] = []
    for i in range(0, len(pmids), _EFETCH_BATCH_SIZE):
        batch = pmids[i : i + _EFETCH_BATCH_SIZE]
        xml_text = await _efetch_batch(client, batch)
        articles.extend(_parse_articles(xml_text))
        await asyncio.sleep(0.4)  # 키 없는 3req/sec 제한 준수
    return articles


async def fetch_and_append_category_papers(
    retmax_per_category: int = _CATEGORY_RETMAX, categories: list[str] | None = None
) -> dict[str, dict[str, int]]:
    """기존 질환별 raw 파일은 그대로 두고, 카테고리별 검색어로 새로 찾은 논문만
    (PMID 중복 없는 것만) category 태그를 붙여 증분 추가한다.
    categories를 넘기면 그 카테고리들만 재시도(예: 검색어 수정 후 MEDICAL_NEWS만 재수집)."""
    target_categories = categories if categories is not None else CATEGORIES
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict[str, int]] = {}
    async with httpx.AsyncClient(timeout=settings.PUBMED_TIMEOUT) as client:
        for disease in SUPPORTED_DISEASES:
            out_path = RAW_DATA_DIR / f"{disease}.json"
            existing: list[dict] = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
            existing_pmids = {p["pmid"] for p in existing}

            report[disease] = {}
            for category in target_categories:
                term = _category_search_term(disease, category)
                papers = await _fetch_papers_for_term(client, term, retmax_per_category)
                added = 0
                for paper in papers:
                    if paper["pmid"] in existing_pmids:
                        continue
                    paper["category"] = category
                    existing.append(paper)
                    existing_pmids.add(paper["pmid"])
                    added += 1
                report[disease][category] = added
                await asyncio.sleep(0.4)

            out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{disease}: 총 {len(existing)}건 (카테고리별 신규 추가: {report[disease]})")
    return report


def load_raw_papers() -> dict[str, list[dict]]:
    """source/*.json을 읽는다(PubMed 재호출 없음). 질환 파일이 없거나
    비어 있으면 에러 로그만 남기고 건너뛴다 — 다른 질환 인제스천은 계속 진행한다."""
    result: dict[str, list[dict]] = {}
    for disease in SUPPORTED_DISEASES:
        path = RAW_DATA_DIR / f"{disease}.json"
        if not path.exists():
            logger.error(f"원본 파일 없음, 건너뜀: {path}")
            continue
        papers = json.loads(path.read_text(encoding="utf-8"))
        if not papers:
            logger.error(f"원본 파일이 비어 있음, 건너뜀: {path}")
            continue
        result[disease] = papers
    return result


def _paper_page_content(disease: str, title: str, category: str, abstract: str, summary_ko: str = "") -> str:
    """임베딩될 본문. 질환/카테고리 헤더 + 한국어 요약 + 원문 제목 + 초록 순으로 조립한다.

    이 정보는 metadata에도 담기지만, Chroma는 page_content만 임베딩하고 metadata는
    벡터에 반영하지 않는다 — 검색 결과에 영향을 주려면 본문 안에 있어야 한다.

    한국어 요약이 핵심이다. 사용자 질의는 한국어인데 논문 제목·초록은 영어라, 한국어
    토큰 몇 개를 헤더에 접두하는 것만으로는 1,500자 영어 문서의 평균 풀링에서 희석돼
    버린다. 실측(2026-07-17, 골든셋 paper-09): 같은 질의에 대해 정답 논문까지의 거리가
    영어 제목만일 때 0.1583, 한국어 요약을 붙이면 0.0801로 절반이 된다. 더 중요한 건
    무관 논문(0.1749)과의 마진이 0.0166 -> 0.0948로 약 6배 벌어진다는 점이다 — 마진이
    노이즈 수준이라 정답 논문이 4위로 밀려나던 문제가 여기서 온다.

    요약 생성 비용(논문당 LLM 1회)은 인제스트 시점에 1회만 내고 캐시하므로, 질의마다
    번역/확장 LLM을 태우는 방식과 달리 채팅 응답 지연이 0이다."""
    header = f"[{disease} / {category}]" if category else f"[{disease}]"
    lead = f"{header} {summary_ko}\n{title}" if summary_ko else f"{header} {title}"
    return f"{lead}\n\n{abstract}"


# 한국어 요약 캐시(pmid -> 요약). 원본 JSON은 "가공 없이 원문만" 원칙이라 건드리지 않고,
# 파생물인 요약은 이 파일에 따로 모은다. 캐시가 있으면 리셋 후 전체 재색인을 해도 LLM
# 비용을 다시 내지 않는다(임베딩만 다시 함).
SUMMARY_CACHE_PATH = RAW_DATA_DIR / "paper_summaries_ko.json"
# LLM 동시 호출 수. 논문 740건을 순차로 돌리면 오래 걸리고, 너무 올리면 레이트리밋에 걸린다.
_SUMMARY_CONCURRENCY = 8
_SUMMARY_PROMPT = (
    "당신은 의학 논문을 한국어로 요약하는 전문가입니다. 주어진 논문 제목과 초록을 읽고, "
    "한국어 한두 문장으로 요약하세요. 반드시 포함할 것: 어떤 질환/대상자인지, 무엇을 했는지(중재/방법), "
    "무엇을 알아냈는지(결과). 이 요약은 한국어 검색 질의와 매칭되는 데 쓰이므로, 한국인이 실제로 "
    "검색할 법한 일상적인 의학 용어를 쓰세요. 요약문만 출력하고 다른 말은 하지 마세요."
)


def load_summary_cache() -> dict[str, str]:
    """pmid -> 한국어 요약 캐시를 읽는다. 파일이 없으면 빈 dict(요약 없이 색인은 계속 진행)."""
    if not SUMMARY_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(SUMMARY_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"요약 캐시 읽기 실패, 요약 없이 진행: {e}")
        return {}


async def _summarize_one(llm, paper: dict) -> tuple[str, str] | None:
    pmid = paper.get("pmid")
    abstract = paper.get("abstract")
    if not pmid or not abstract:
        return None
    user_input = f"제목: {paper.get('title') or ''}\n\n초록: {abstract}"
    try:
        response = await llm.ainvoke(
            [{"role": "system", "content": _SUMMARY_PROMPT}, {"role": "user", "content": user_input}]
        )
    except Exception as e:
        # 한 건 실패가 전체 배치를 죽이면 안 된다 — 요약 없는 논문은 헤더+영어 원문으로
        # 색인되고(검색은 되지만 한국어 매칭이 약함), 다음 실행 때 캐시 미스로 재시도된다.
        logger.error(f"요약 생성 실패(pmid={pmid}), 건너뜀: {e}")
        return None
    return pmid, str(response.content).strip()


async def ensure_paper_summaries(papers_by_disease: dict[str, list[dict]]) -> dict[str, str]:
    """캐시에 없는 논문만 골라 한국어 요약을 생성하고 캐시에 병합·저장한다.
    이미 요약된 논문은 건너뛰므로 원본이 늘어나도 신규분만 과금된다."""
    cache = load_summary_cache()
    todo = [p for papers in papers_by_disease.values() for p in papers if p.get("pmid") not in cache]
    if not todo:
        logger.info(f"한국어 요약 캐시 최신({len(cache)}건). 신규 생성 없음.")
        return cache

    if settings.OPENAI_API_KEY is None:
        logger.error("OPENAI_API_KEY가 없어 한국어 요약을 생성하지 못합니다. 요약 없이 색인을 진행합니다.")
        return cache

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=settings.OPENAI_TEMPERATURE,
    )
    logger.info(f"한국어 요약 생성 시작: {len(todo)}건 (동시 {_SUMMARY_CONCURRENCY})")
    semaphore = asyncio.Semaphore(_SUMMARY_CONCURRENCY)

    async def _bounded(paper: dict):
        async with semaphore:
            return await _summarize_one(llm, paper)

    results = await asyncio.gather(*(_bounded(p) for p in todo))
    new = {pmid: summary for r in results if r for pmid, summary in [r] if summary}
    cache.update(new)
    SUMMARY_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"한국어 요약 {len(new)}건 생성 완료(실패 {len(todo) - len(new)}건). 캐시 총 {len(cache)}건.")
    return cache


def build_documents(disease: str, papers: list[dict], summaries: dict[str, str] | None = None) -> list[Document]:
    """질환 하나의 원본 논문 목록을 Document로 변환한다. 초록 1편 = 청크 1개.

    예전엔 제목+초록이 1000자를 넘으면 RecursiveCharacterTextSplitter로 쪼갰고, 주석엔
    "대부분의 초록은 안 넘음"이라 적혀 있었다. 실측 결과는 정반대였다 — 740편 중 729편
    (99%)이 분할돼 논문당 평균 3.45청크가 나왔고, 제목 없이 잘려나간 뒷청크가 컬렉션의
    약 70%를 차지했다. 그 조각들은 어느 논문의 무슨 맥락인지 알 수 없어 무관한 질환
    질문에 딸려 나왔다. PubMed 초록은 그 자체가 완결된 의미 단위라 쪼갤 이득이 없으므로
    분할하지 않는다(2026-07-17).

    `summaries`(pmid -> 한국어 요약)가 주어지면 본문에 접두한다 — 없으면 요약 없이
    색인한다(검색은 되지만 한국어 질의 매칭이 약해진다. `_paper_page_content` 참고)."""
    summaries = summaries or {}
    documents: list[Document] = []
    for paper in papers:
        pmid = paper.get("pmid")
        abstract = paper.get("abstract")
        if not pmid or not abstract:
            logger.error(f"pmid/abstract 누락, 건너뜀: disease={disease}, paper={paper}")
            continue
        title = paper.get("title") or ""
        category = paper.get("category") or ""
        summary_ko = summaries.get(pmid, "")
        metadata = {
            "disease": disease,
            "pmid": pmid,
            "title": title,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source": "PubMed",
            "category": category,
            "summary_ko": summary_ko,
        }
        documents.append(
            Document(
                page_content=_paper_page_content(disease, title, category, abstract, summary_ko), metadata=metadata
            )
        )
    return documents


def build_paper_vector_store() -> Chroma:
    """ingest_papers·search_papers가 공유하는 Chroma 스토어 팩토리. DUR과 동일한
    CHROMA_DIR 아래, 별도 컬렉션(PAPER_COLLECTION_NAME)에 저장한다."""
    return Chroma(
        collection_name=PAPER_COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"embedding_model": active_embedding_model()},
    )


def _indexed_pmids(db: Chroma) -> set[str]:
    """이미 색인된 논문의 pmid 집합(청크 단위 저장이라 같은 pmid가 여러 청크에 걸쳐
    중복 등장하지만 set이라 자연히 1개로 합쳐진다). 증분 인제스천의 스킵 기준이 된다."""
    try:
        data = db.get(include=["metadatas"])
    except Exception as e:
        logger.warning(f"기존 색인 pmid 조회 실패: {e}. 전체를 신규로 간주하고 진행.")
        return set()
    metadatas = data.get("metadatas") or []
    return {m["pmid"] for m in metadatas if m and m.get("pmid")}


def ingest_papers() -> Chroma:
    """원본 JSON(load_raw_papers) -> 청킹(build_documents) -> Chroma 저장.
    PMID 기준 증분 인제스천이다: 이미 색인된 논문은 건너뛰고 신규 논문만 임베딩한다.
    (전체를 매번 다시 임베딩하면 원본이 늘어날 때마다 이미 낸 OpenAI 임베딩 비용을
    계속 반복 청구하게 되므로, 컬렉션 통째 스킵/재생성 대신 pmid 단위로 차이만 채운다.)"""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    db = build_paper_vector_store()
    already_indexed = _indexed_pmids(db)

    raw_by_disease = load_raw_papers()
    summaries = load_summary_cache()
    all_docs: list[Document] = []
    for disease, papers in raw_by_disease.items():
        new_papers = [p for p in papers if p.get("pmid") not in already_indexed]
        docs = build_documents(disease, new_papers, summaries)
        all_docs.extend(docs)
        logger.info(
            f"{disease}: 원본 {len(papers)}건 중 신규 {len(new_papers)}건 "
            f"(기존 색인 {len(papers) - len(new_papers)}건 스킵) -> 청크 {len(docs)}건"
        )

    if not all_docs:
        logger.info("신규 인제스천할 문서가 없습니다(모두 이미 색인됨).")
        return db

    batch_size = 500
    for i in range(0, len(all_docs), batch_size):
        batch = all_docs[i : i + batch_size]
        db.add_documents(batch)
        logger.info(f"배치 {i // batch_size + 1} 적재 완료 ({len(batch)}건)")
    logger.info(f"총 {len(all_docs)}건 신규 인제스천 완료.")
    return db


def reset_paper_collection() -> None:
    """--force 재색인용: 기존 pubmed_papers 컬렉션을 통째로 삭제한다."""
    db = build_paper_vector_store()
    db.delete_collection()
    logger.info(f"{PAPER_COLLECTION_NAME} 컬렉션 삭제 완료.")


async def run_daily_pipeline(
    retmax_per_category: int = _CATEGORY_RETMAX, categories: list[str] | None = None
) -> Chroma:
    """1단계(신규 논문 수집)+2단계(한국어 요약)+3단계(임베딩+색인)를 순서대로 잇는 완결된
    배치. 사람은 이 함수(또는 CLI `--pipeline`)를 실행 버튼처럼 누르기만 하면 되고, 그 안에서
    수집→중복 제거→요약→색인까지 전부 자동으로 끝난다. "매일 자동으로 이 명령 자체를 실행시키는"
    스케줄러(cron/Celery beat)는 아직 붙이지 않았다 — 그건 별도 단계다(모듈 docstring 참고)."""
    await fetch_and_append_category_papers(retmax_per_category=retmax_per_category, categories=categories)
    await ensure_paper_summaries(load_raw_papers())
    return ingest_papers()


async def _main(args: argparse.Namespace) -> None:
    if args.pipeline:
        db = await run_daily_pipeline(retmax_per_category=args.retmax_per_category, categories=args.categories)
        count = len(db.get(include=[])["ids"])
        print(f"{PAPER_COLLECTION_NAME} 컬렉션 문서 수: {count}")
        return
    if args.summarize_only:
        cache = await ensure_paper_summaries(load_raw_papers())
        print(f"한국어 요약 캐시: 총 {len(cache)}건 ({SUMMARY_CACHE_PATH})")
        return
    if args.index_only:
        if args.force:
            reset_paper_collection()
        await ensure_paper_summaries(load_raw_papers())
        db = ingest_papers()
        count = len(db.get(include=[])["ids"])
        print(f"{PAPER_COLLECTION_NAME} 컬렉션 문서 수: {count}")
        return
    await fetch_and_append_category_papers(retmax_per_category=args.retmax_per_category, categories=args.categories)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--retmax-per-category",
        type=int,
        default=_CATEGORY_RETMAX,
        help=f"조합(질환×카테고리)당 수집 건수(기본 {_CATEGORY_RETMAX})",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=CATEGORIES,
        default=None,
        help="재수집할 카테고리만 지정(예: --categories MEDICAL_NEWS). 생략 시 전체 카테고리.",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="요약(캐시 미스분)+임베딩+Chroma 저장만 실행. PubMed를 호출하지 않고 원본 JSON만 읽는다.",
    )
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="한국어 요약 캐시만 채우고 끝낸다(색인 없음). 요약 결과를 먼저 눈으로 검토할 때.",
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="1단계+2단계를 순서대로 모두 실행하는 완결된 배치(매일 수동 실행용).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="(--index-only 전용) 기존 pubmed_papers 컬렉션을 삭제하고 재색인한다.",
    )
    parsed_args = parser.parse_args()
    asyncio.run(_main(parsed_args))
