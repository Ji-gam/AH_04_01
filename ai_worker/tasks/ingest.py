import csv
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from ai_worker.core.config import settings

logger = logging.getLogger("ai_worker.ingest")
logging.basicConfig(level=logging.INFO)

# 데이터 및 크로마 디렉토리 경로
BASE_DIR = Path(__file__).parent.parent
# T-RAG-SOURCE-MIGRATION: 예전엔 mock_data_for_rag/(실험용 스냅샷)를 봤으나, 이제
# ai_worker/source/(RAG+구조화 데이터가 함께 모이는 단일 원천)를 본다. source/의 25개
# CSV 중 RAG 대상은 _DUR_RAG_REGISTRY에 명시적으로 등록된 것만이다(아래 참고) — 나머지는
# ITEM_SEQ 기반 정확 조회용 구조화 데이터라 이 파이프라인이 건드리지 않는다.
DATA_DIR = BASE_DIR / "source"
CHROMA_DIR = BASE_DIR / "chroma_data"

COLLECTION_NAME = "dur_rules"

# 임베딩 모델 식별자(컬렉션 메타데이터에 저장되는 값).
_EMBEDDING_MODEL_NAME = "openai:text-embedding-3-small"


class EmbeddingMismatchError(Exception):
    """저장된 벡터의 임베딩 모델과 현재 백엔드가 달라 검색이 무의미할 때 발생.
    (레거시: HF 폴백이 있던 시절에 임베딩된 컬렉션을 감지하기 위한 안전망으로 유지한다.)"""


class EmbeddingUnavailableError(Exception):
    """OpenAI 프로바이더에 필요한 API 키가 없어 임베딩을 생성할 수 없을 때 발생.
    과거엔 키가 없으면 로컬 HuggingFace로 조용히 폴백했으나, 검색 정확도가 실서비스와
    달라져 무음 성능저하를 낳았다. 팀이 `.env`를 공유해 키 부재가 일어날 일이 없으므로,
    조용히 저하되는 대신 설정 오류로 간주해 즉시 실패한다(결정 2026-07-13)."""


# 프로세스당 1회만 로드되도록 모델 인스턴스를 캐싱한다(모델 로딩엔 초기 다운로드+수 초의
# 메모리 적재 시간이 들어, get_embeddings()가 여러 번 호출돼도 매번 다시 로드하면 안 된다).
_LOCAL_MODEL_CACHE: dict[str, object] = {}


def _get_local_model(model_name: str):
    if model_name not in _LOCAL_MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading local HF model into memory: {model_name} (최초 1회, 다운로드 시 시간이 걸릴 수 있음)")
        _LOCAL_MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _LOCAL_MODEL_CACHE[model_name]


class _HFHybridEmbeddings(Embeddings):
    """문서 임베딩(`embed_documents`, 대량 인제스트)은 로컬에 내려받은 HF 모델
    (sentence-transformers)로 배치 인코딩하고, 질의 임베딩(`embed_query`, 실시간 챗
    검색)은 HF Inference API(호스팅)로 단건 호출한다.

    - 인제스트는 한 번에 수천 건을 처리해야 해서(source/ 7개 DUR 파일 합쳐 5,700여
      건) 로컬 배치가 압도적으로 빠르다 — HF Inference API로 텍스트당 개별 HTTP
      요청을 보내면 비현실적으로 느리다(수십 분 이상, 2026-07-17 실측).
    - 반대로 실시간 챗 질의는 요청당 1건뿐이라 호스팅 API 호출 지연(0.3~1초)이
      체감되지 않고, 대신 ai_worker 프로세스마다 ~2GB 모델을 상시 메모리에 올려둘
      필요가 없어진다(워커 프로세스가 여럿이면 그만큼 메모리를 아낌).
    - 같은 모델 가중치를 두 경로 다 쓰므로(로컬 실행 vs HF 서버 실행) 결과 벡터는
      동일한 공간에 있다 — 다만 실행 환경이 달라 부동소수점 오차가 아주 미세하게
      있을 수 있고, 이는 임계값 실측 시 감안했다(config.py 주석 참고).
    - e5 계열 모델 공식 권장대로 문서엔 'passage: ', 질의엔 'query: ' 프리픽스를
      붙이고, 두 경로 모두 단위벡터로 정규화한다(OpenAI 임베딩도 단위벡터라
      `RAG_SIMILARITY_THRESHOLD`/`PAPER_SIMILARITY_THRESHOLD`가 그 스케일 기준)."""

    def __init__(self, model: str, hf_api_key: str, retries: int = 3) -> None:
        self._model_name = model
        self._hf_api_key = hf_api_key
        self._retries = retries

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = _get_local_model(self._model_name)
        vectors = model.encode([f"passage: {t}" for t in texts], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors).tolist()

    def embed_query(self, text: str) -> list[float]:
        import time

        from huggingface_hub import InferenceClient

        client = InferenceClient(token=self._hf_api_key)
        last_error: Exception | None = None
        for attempt in range(self._retries):
            try:
                vec = client.feature_extraction(f"query: {text}", model=self._model_name, normalize=True)
                return np.asarray(vec).reshape(-1).tolist()
            except Exception as e:
                last_error = e
                time.sleep(2 * (attempt + 1))
        assert last_error is not None
        raise last_error


def _require_api_key() -> str | None:
    """OpenAI 프로바이더는 API 키가 반드시 있어야 한다. HF 프로바이더는 인제스트(로컬
    추론)엔 키가 필요 없지만, 실시간 질의(HF Inference API)엔 필요해 어차피 있어야
    한다 — 상황별로 필요 여부가 갈리면 헷갈리므로 항상 요구한다(fail-fast 원칙,
    2026-07-13 결정과 동일한 방향)."""
    if settings.EMBEDDING_PROVIDER == "huggingface":
        api_key = settings.HUGGINGFACE_API_KEY
        if not api_key:
            raise EmbeddingUnavailableError(
                "HUGGINGFACE_API_KEY가 설정되지 않아 임베딩을 생성할 수 없습니다"
                "(실시간 질의는 HF Inference API를 쓰므로 필요합니다)."
            )
        return api_key

    api_key = settings.OPENAI_EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        raise EmbeddingUnavailableError(
            "OPENAI_API_KEY/OPENAI_EMBEDDING_API_KEY가 설정되지 않아 임베딩을 생성할 수 없습니다."
        )
    return api_key


def active_embedding_model() -> str:
    """현재 사용 중인 임베딩 모델 식별자(컬렉션 메타데이터에 저장되는 값). 프로바이더가
    바뀌면 이 식별자도 바뀌어 `assert_embedding_compatible`이 자동으로 재인제스트를
    요구한다."""
    _require_api_key()
    if settings.EMBEDDING_PROVIDER == "huggingface":
        return f"huggingface:{settings.HF_EMBEDDING_MODEL}"
    return _EMBEDDING_MODEL_NAME


def get_embeddings():
    """`settings.EMBEDDING_PROVIDER`에 따라 HF(로컬 인제스트+호스팅 질의 하이브리드)
    또는 OpenAI로 임베딩을 생성한다. 키가 없으면 즉시 실패한다(로컬 폴백 없음 —
    `EmbeddingUnavailableError` 참고)."""
    api_key = _require_api_key()
    if settings.EMBEDDING_PROVIDER == "huggingface":
        logger.info(f"Using HF hybrid embeddings ({settings.HF_EMBEDDING_MODEL}: local ingest + API query)")
        assert api_key is not None
        return _HFHybridEmbeddings(model=settings.HF_EMBEDDING_MODEL, hf_api_key=api_key)
    logger.info("Using OpenAIEmbeddings (text-embedding-3-small) for RAG Ingestion")
    return OpenAIEmbeddings(openai_api_key=api_key, model="text-embedding-3-small")


def build_vector_store() -> Chroma:
    """ingest·query가 공유하는 Chroma 스토어 팩토리. 컬렉션 메타데이터에 임베딩 모델명을
    함께 기록해, 나중에 백엔드가 바뀌면 불일치를 감지할 수 있게 한다."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"embedding_model": active_embedding_model()},
    )


def _read_collection_metadata(db) -> dict:
    """컬렉션 메타데이터(임베딩 모델명 등)를 읽는다. langchain-chroma 1.1.0엔 이를 읽는
    공개 접근자가 없어, 사설 속성 `_collection.metadata` 접근을 이 함수 하나로 격리한다 —
    나중에 langchain이 공개 접근자를 열면 이 함수만 교체하면 된다."""
    collection = getattr(db, "_collection", None)
    metadata = getattr(collection, "metadata", None) if collection is not None else None
    return metadata or {}


def assert_embedding_compatible(db) -> None:
    """컬렉션에 저장된 임베딩 모델명과 현재 백엔드가 다르면 예외로 명시적 거부한다.
    모델명이 저장되지 않은 (라벨 도입 이전) 컬렉션은 검증할 수 없어 통과시킨다 —
    무음 오필터를 막는 게 목적이지, 검증 불가를 차단으로 오인하지 않기 위함."""
    stored = _read_collection_metadata(db).get("embedding_model")
    if stored is not None and stored != active_embedding_model():
        raise EmbeddingMismatchError(
            f"컬렉션은 '{stored}'로 임베딩됐는데 현재 백엔드는 '{active_embedding_model()}'입니다. "
            "벡터공간이 달라 검색 결과가 무의미하므로 재인제스트가 필요합니다."
        )


def _collection_count(db) -> int:
    return len(db.get(include=[])["ids"])


def _clean(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


# ---------- 파일별 문장 템플릿 (_DUR_RAG_REGISTRY의 build_content로 쓰인다) ----------


def _pwnm_content(row: dict) -> str:
    ingr_name = _clean(row, "INGR_NAME")
    ingr_eng_name = _clean(row, "INGR_ENG_NAME")
    prohbt_content = _clean(row, "PROHBT_CONTENT")
    type_name = _clean(row, "TYPE_NAME")
    grade = _clean(row, "GRADE")
    grade_str = f" ({grade})" if grade else ""
    class_name = _clean(row, "CLASS_NAME")
    class_str = f" 약효 분류: {class_name}." if class_name else ""
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
        f"{type_name}{grade_str} 약물입니다. 임부 금기 사유: {prohbt_content or '임부에 대한 안전성 미확립.'}{class_str}"
    )


def _odsn_content(row: dict) -> str:
    ingr_name = _clean(row, "INGR_NAME")
    ingr_eng_name = _clean(row, "INGR_ENG_NAME")
    prohbt_content = _clean(row, "PROHBT_CONTENT")
    type_name = _clean(row, "TYPE_NAME")
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
        f"{type_name} 약물입니다. 상세 안내: {prohbt_content or '주의 및 안내 사항 확인 필요.'}"
    )


def _mdctn_content(row: dict) -> str:
    ingr_name = _clean(row, "INGR_NAME")
    ingr_eng_name = _clean(row, "INGR_ENG_NAME")
    prohbt_content = _clean(row, "PROHBT_CONTENT")
    type_name = _clean(row, "TYPE_NAME")
    max_dosage_term = _clean(row, "MAX_DOSAGE_TERM")
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
        f"{type_name} 약물이며, 최대 처방(투여) 기간은 [{max_dosage_term}]입니다. "
        f"상세 내용: {prohbt_content or '투여기간 주의 필요.'}"
    )


def _efcy_content(row: dict) -> str:
    ingr_name = _clean(row, "INGR_NAME")
    ingr_eng_name = _clean(row, "INGR_ENG_NAME")
    type_name = _clean(row, "TYPE_NAME")
    sers_name = _clean(row, "SERS_NAME")
    class_name = _clean(row, "CLASS_NAME")
    sers_str = f" [{sers_name}] 계열" if sers_name else ""
    class_str = f"({class_name})" if class_name else ""
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
        f"{type_name} 주의 약물입니다. 해당 성분은{sers_str}{class_str}에 속하며, "
        f"동일 효능군 약물과의 중복 처방을 주의해야 합니다."
    )


def _cpcty_content(row: dict) -> str:
    ingr_name = _clean(row, "INGR_NAME")
    ingr_eng_name = _clean(row, "INGR_ENG_NAME")
    prohbt_content = _clean(row, "PROHBT_CONTENT")
    type_name = _clean(row, "TYPE_NAME")
    max_qty = _clean(row, "MAX_QTY")
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
        f"{type_name} 약물이며, 최대 처방(투여) 용량은 [{max_qty}]입니다. "
        f"상세 내용: {prohbt_content or '용량 주의 필요.'}"
    )


def _spcify_agrde_content(row: dict) -> str:
    ingr_name = _clean(row, "INGR_NAME")
    ingr_eng_name = _clean(row, "INGR_ENG_NAME")
    prohbt_content = _clean(row, "PROHBT_CONTENT")
    type_name = _clean(row, "TYPE_NAME")
    age_base = _clean(row, "AGE_BASE")
    age_str = f"{age_base} 연령대에서" if age_base else "특정 연령대에서"
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
        f"{type_name} 약물입니다. {age_str} 금기 사유: {prohbt_content or '특정 연령에 대한 안전성 미확립.'}"
    )


def _usjnt_content(row: dict) -> str:
    """병용금기: DUR_SEQ가 없고 성분 조합(INGR/MIXTURE_INGR) 단위 데이터."""
    ingr_name = _clean(row, "INGR_KOR_NAME")
    ingr_eng_name = _clean(row, "INGR_ENG_NAME")
    mixture_name = _clean(row, "MIXTURE_INGR_KOR_NAME")
    mixture_eng_name = _clean(row, "MIXTURE_INGR_ENG_NAME")
    prohbt_content = _clean(row, "PROHBT_CONTENT")
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})과(와) "
        f"[{mixture_name}] (영문명: {mixture_eng_name})은/는 병용금기 조합입니다. "
        f"사유: {prohbt_content or '병용 시 안전성 미확립.'}"
    )


@dataclass(frozen=True)
class DurFileSpec:
    """RAG 대상 CSV 1개의 처리 스펙. `_DUR_RAG_REGISTRY`에 명시적으로 등록된 파일만
    이 파이프라인이 처리한다 — `source/`엔 구조화 전용 CSV가 훨씬 많이 섞여 있어,
    화이트리스트 없이 전부 훑으면 언젠가 표 데이터가 실수로 임베딩된다."""

    source_id: str  # 내부 식별자(=파일명). delete-필터/upsert 키로만 쓰고 사용자에게 노출 안 함.
    display_name: str  # 사용자 노출용 자료명, 예: "임부금기의약품"
    build_content: Callable[[dict], str]
    publisher: str = "식약처"
    id_fields: tuple[str, ...] = ("DUR_SEQ",)  # 복합키 지원(usjnt_taboo는 두 성분 코드 조합)


_DUR_RAG_REGISTRY: dict[str, DurFileSpec] = {
    "dur_pwnm_taboo.csv": DurFileSpec("dur_pwnm_taboo.csv", "임부금기의약품", _pwnm_content),
    "dur_odsn_atent.csv": DurFileSpec("dur_odsn_atent.csv", "노인주의의약품", _odsn_content),
    "dur_mdctn_pd_atent.csv": DurFileSpec("dur_mdctn_pd_atent.csv", "투여기간주의의약품", _mdctn_content),
    "dur_efcy_dplct.csv": DurFileSpec("dur_efcy_dplct.csv", "효능군중복의약품", _efcy_content),
    "dur_cpcty_atent.csv": DurFileSpec("dur_cpcty_atent.csv", "용량주의의약품", _cpcty_content),
    "dur_spcify_agrde_taboo.csv": DurFileSpec(
        "dur_spcify_agrde_taboo.csv", "특정연령금기의약품", _spcify_agrde_content
    ),
    "dur_usjnt_taboo.csv": DurFileSpec(
        "dur_usjnt_taboo.csv",
        "병용금기의약품",
        _usjnt_content,
        # 성분 코드 조합(INGR_CODE+MIXTURE_INGR_CODE)만으론 유일하지 않다 — 같은 성분이
        # 여러 "복합제" 조합(MIX)으로 반복 등장한다(예: 메트포르민+아이오다이즈드오일
        # 병용금기가 글리벤클라미드/글리클라지드/로시글리타존 등 복합제별로 별도 행).
        # app/database/drugs_full.db의 dur_usjnt_taboo 테이블에 이미 이 데이터의
        # UNIQUE 제약이 정의돼 있어(팀이 먼저 검증해둔 설계) 그대로 재사용한다.
        id_fields=(
            "INGR_CODE",
            "MIXTURE_INGR_CODE",
            "MIX_TYPE",
            "MIXTURE_MIX_TYPE",
            "NOTIFICATION_DATE",
            "MIX",
            "MIXTURE_MIX",
            "CLASS",
            "MIXTURE_CLASS",
            "DEL_YN",
            "PROHBT_CONTENT",
        ),
    ),
}


def _load_docs_from_csv(csv_file: Path, spec: DurFileSpec) -> tuple[list[Document], list[str]]:
    """CSV 한 파일을 읽어 Document 리스트로 변환한다. id 필드가 전부 비어있는 행은 행
    인덱스로 id를 폴백하고(조용히 사라지지 않게 warning에 남김), 폴백 후에도 같은
    id가 이미 나왔으면(복합키가 실제로는 유일하지 않았던 경우) 다시 행 인덱스로
    떨어뜨려 절대 중복 id가 나가지 않게 한다 — id_fields 설계가 데이터 실측과
    어긋나도(예: dur_usjnt_taboo 최초 설계 실수) 안전망이 항상 작동한다."""
    docs: list[Document] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    with open(csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            ingr_name = _clean(row, "INGR_NAME") or _clean(row, "INGR_KOR_NAME")
            if not ingr_name:
                continue

            id_values = [_clean(row, field) for field in spec.id_fields]
            if any(id_values):
                doc_id = f"{spec.source_id}:{'-'.join(id_values)}"
            else:
                doc_id = f"{spec.source_id}:row{i}"
                warnings.append(f"{spec.source_id} 행 {i}: id 필드{spec.id_fields} 전부 비어있음, row 인덱스로 폴백")

            if doc_id in seen_ids:
                warnings.append(f"{spec.source_id} 행 {i}: id 중복({doc_id}), row 인덱스로 재폴백")
                doc_id = f"{spec.source_id}:row{i}"
            seen_ids.add(doc_id)

            try:
                page_content = spec.build_content(row)
            except Exception as e:
                warnings.append(f"{spec.source_id} 행 {i} 문장 생성 실패: {e}")
                continue

            metadata = {
                "source_id": spec.source_id,
                "display_name": spec.display_name,
                "publisher": spec.publisher,
                "ingr_name": ingr_name,
                "type_name": _clean(row, "TYPE_NAME"),
            }
            docs.append(Document(page_content=page_content, metadata=metadata, id=doc_id))
    return docs, warnings


def _upsert_file_docs(db: Chroma, spec: DurFileSpec, docs: list[Document]) -> int:
    """`spec.source_id`로 태그된 기존 문서를 지우고 새 문서를 upsert한다(파일 단위
    갱신). `Document.id`가 채워져 있으면 langchain_chroma가 upsert로 처리하므로
    (add_documents 내부가 항상 collection.upsert를 호출), 같은 id로 다시 넣으면
    자동으로 덮어써진다 — 다만 CSV에서 빠진 행(삭제된 규칙)은 upsert만으론 안 지워지므로
    먼저 이 파일 소스의 기존 문서를 전부 지우고 다시 채운다."""
    try:
        existing = db.get(where={"source_id": spec.source_id}, include=[])
        deleted = len(existing["ids"])
        if deleted:
            db.delete(where={"source_id": spec.source_id})
    except Exception as e:
        logger.warning(f"{spec.source_id} 기존 문서 삭제 확인 실패: {e}. 계속 진행.")
        deleted = 0

    batch_size = 500
    for i in range(0, len(docs), batch_size):
        db.add_documents(docs[i : i + batch_size])
    return deleted


def _needs_reingest(db: Chroma, spec: DurFileSpec, doc_count: int) -> bool:
    """startup/bulk 경로(`ingest_csv_data`) 전용 스킵 판단. 이 파일 소스로 이미 적재된
    문서 수가 방금 파싱한 문서 수와 같으면 "바뀐 게 없다"고 보고 재임베딩을 생략한다
    (매 앱 재시작마다 전체를 다시 임베딩하는 낭비를 막기 위함). 행 수가 같은데 내용만
    바뀐 경우는 못 잡아내는 한계가 있다 — 그런 갱신은 admin 업로드(`ingest_single_csv_file`,
    항상 무조건 재적재)로 하면 된다."""
    try:
        existing = db.get(where={"source_id": spec.source_id}, include=[])
        return len(existing["ids"]) != doc_count
    except Exception as e:
        logger.warning(f"{spec.source_id} 기존 문서 수 확인 실패: {e}. 재인제스트 진행.")
        return True


def ingest_single_csv_file(csv_file: Path) -> dict:
    """관리자 업로드 1건을 처리한다: 항상 무조건 그 파일 소스를 지우고 새로 upsert한다
    (재업로드 = 최신 스냅샷이라는 뜻이므로 스킵 판단 없이 매번 반영). `source/`가 아닌
    임의 경로로 호출해도 되게 파일명만으로 레지스트리를 조회한다."""
    spec = _DUR_RAG_REGISTRY.get(csv_file.name)
    if spec is None:
        return {
            "filename": csv_file.name,
            "deleted": 0,
            "ingested": 0,
            "collection_count": 0,
            "errors": [f"{csv_file.name}은(는) RAG 대상으로 등록되지 않은 파일입니다."],
        }

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    db = build_vector_store()

    try:
        docs, warnings = _load_docs_from_csv(csv_file, spec)
    except Exception as e:
        logger.error(f"CSV 파싱 실패: {csv_file.name}: {e}")
        return {
            "filename": csv_file.name,
            "deleted": 0,
            "ingested": 0,
            "collection_count": _collection_count(db),
            "errors": [f"{csv_file.name} 파싱 실패: {e}"],
        }

    deleted = _upsert_file_docs(db, spec, docs)
    return {
        "filename": csv_file.name,
        "deleted": deleted,
        "ingested": len(docs),
        "collection_count": _collection_count(db),
        "errors": warnings,
    }


def reset_dur_collection() -> None:
    """`dur_rules` 컬렉션을 통째로 삭제한다(제로 그라운드 리셋용).
    ingest_papers.py의 `reset_paper_collection()`과 동일 패턴."""
    db = build_vector_store()
    db.delete_collection()
    logger.info(f"{COLLECTION_NAME} 컬렉션 삭제 완료.")


def ingest_csv_data(force: bool = False) -> list[dict]:
    """`source/`의 RAG 대상 CSV(레지스트리에 등록된 것만)를 전부 훑어 적재한다.
    startup(`initialize_rag`)과 CLI 진입점으로 쓰인다. `force=True`면 컬렉션을 통째로
    삭제하고 전체 재적재한다(제로 그라운드 CLI 경로). `force=False`(기본)는 파일별로
    이미 최신인지 확인해(`_needs_reingest`) 바뀐 파일만 재임베딩한다 — 매 재시작마다
    전체를 다시 임베딩하던 과거 방식(및 그걸 막으려 컬렉션이 비었을 때만 인제스트하던
    버그)을 둘 다 피한다."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    db = build_vector_store()

    if force:
        db.delete_collection()
        db = build_vector_store()

    if not DATA_DIR.exists():
        logger.error(f"Data directory {DATA_DIR} does not exist. Cannot ingest.")
        return []

    results: list[dict] = []
    for file_name, spec in _DUR_RAG_REGISTRY.items():
        csv_file = DATA_DIR / file_name
        if not csv_file.exists():
            logger.warning(f"레지스트리에 등록된 파일이 source/에 없음, 건너뜀: {file_name}")
            continue

        try:
            docs, warnings = _load_docs_from_csv(csv_file, spec)
        except Exception as e:
            logger.error(f"CSV 파싱 실패: {file_name}: {e}")
            results.append({"filename": file_name, "deleted": 0, "ingested": 0, "errors": [str(e)]})
            continue

        if not force and not _needs_reingest(db, spec, len(docs)):
            logger.info(f"{file_name}: 변경 없음({len(docs)}건), 재임베딩 생략.")
            results.append({"filename": file_name, "deleted": 0, "ingested": 0, "errors": warnings, "skipped": True})
            continue

        deleted = _upsert_file_docs(db, spec, docs)
        logger.info(f"{file_name}: 기존 {deleted}건 삭제 후 {len(docs)}건 적재.")
        results.append({"filename": file_name, "deleted": deleted, "ingested": len(docs), "errors": warnings})

    return results


if __name__ == "__main__":
    import sys

    force_flag = "--force" in sys.argv
    summary = ingest_csv_data(force=force_flag)
    for r in summary:
        print(r)
