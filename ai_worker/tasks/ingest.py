import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

from ai_worker.core.config import settings

logger = logging.getLogger("ai_worker.ingest")
logging.basicConfig(level=logging.INFO)

# 데이터 및 크로마 디렉토리 경로
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "mock_data_for_rag"
CHROMA_DIR = BASE_DIR / "chroma_data"

# T-LLM-2-rag-source-label: 원본 CSV 파일명이 챗봇 답변의 [출처: ...]에 그대로 노출되지
# 않도록, Chroma 메타데이터 source에는 이 한글 라벨을 대신 넣는다. 매핑에 없는 파일은
# raw 파일명으로 폴백한다(조용히 사라지는 대신, 매핑 추가가 필요하다는 신호로 남긴다).
_SOURCE_LABELS = {
    "dur_pwnm_taboo.csv": "식약처 DUR 임부금기 정보",
    "dur_odsn_atent.csv": "식약처 DUR 노인주의 정보",
    "dur_mdctn_pd_atent.csv": "식약처 DUR 투여기간주의 정보",
    "dur_efcy_dplct.csv": "식약처 DUR 효능군중복 정보",
}


def _display_source_label(file_name: str) -> str:
    return _SOURCE_LABELS.get(file_name, file_name)


COLLECTION_NAME = "dur_rules"

# 임베딩 백엔드 식별자 → 실제 모델명. OpenAI(1536차원)와 HF(384차원)는 거리 스케일이
# 달라, 저장 시점과 검색 시점의 백엔드가 다르면 검색 결과가 무의미해진다.
_EMBEDDING_MODELS = {
    "openai": "openai:text-embedding-3-small",
    "hf": "hf:sentence-transformers/all-MiniLM-L6-v2",
}


class EmbeddingMismatchError(Exception):
    """저장된 벡터의 임베딩 모델과 현재 백엔드가 달라 검색이 무의미할 때 발생."""


def _embedding_backend() -> str:
    """현재 사용 가능한 임베딩 백엔드('openai' 또는 'hf')를 결정한다."""
    api_key = settings.OPENAI_EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    return "openai" if api_key else "hf"


def active_embedding_model() -> str:
    """현재 백엔드가 사용하는 임베딩 모델 식별자(컬렉션 메타데이터에 저장되는 값)."""
    return _EMBEDDING_MODELS[_embedding_backend()]


def get_embeddings():
    """
    OpenAI text-embedding-3-small 모델을 기본 임베딩으로 사용하며,
    설정된 API Key 유무에 따라 적절한 객체를 반환합니다.
    API Key가 모두 없을 경우 로컬 HuggingFace Embeddings로 폴백합니다.
    """
    # 1. 임베딩 전용 API Key 확인
    api_key = settings.OPENAI_EMBEDDING_API_KEY or settings.OPENAI_API_KEY

    if api_key:
        logger.info("Using OpenAIEmbeddings (text-embedding-3-small) for RAG Ingestion")
        return OpenAIEmbeddings(openai_api_key=api_key, model="text-embedding-3-small")
    else:
        logger.warning("No OpenAI API Key found. Falling back to local HuggingFaceEmbeddings (all-MiniLM-L6-v2)")
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def build_vector_store() -> Chroma:
    """ingest·query가 공유하는 Chroma 스토어 팩토리. 컬렉션 메타데이터에 임베딩 모델명을
    함께 기록해, 나중에 백엔드가 바뀌면 불일치를 감지할 수 있게 한다."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"embedding_model": active_embedding_model()},
    )


def assert_embedding_compatible(db) -> None:
    """컬렉션에 저장된 임베딩 모델명과 현재 백엔드가 다르면 예외로 명시적 거부한다.
    모델명이 저장되지 않은 (라벨 도입 이전) 컬렉션은 검증할 수 없어 통과시킨다 —
    무음 오필터를 막는 게 목적이지, 검증 불가를 차단으로 오인하지 않기 위함."""
    collection = getattr(db, "_collection", None)
    metadata = getattr(collection, "metadata", None) if collection is not None else None
    stored = (metadata or {}).get("embedding_model")
    if stored is not None and stored != active_embedding_model():
        raise EmbeddingMismatchError(
            f"컬렉션은 '{stored}'로 임베딩됐는데 현재 백엔드는 '{active_embedding_model()}'입니다. "
            "벡터공간이 달라 검색 결과가 무의미하므로 재인제스트가 필요합니다."
        )


def _build_page_content(file_name: str, row: dict, ingr_name: str, ingr_eng_name: str, prohbt_content: str) -> str:
    """CSV 파일 종류별로 맞춤형 한글 자연어 설명(page_content)을 생성합니다."""
    type_name = (row.get("TYPE_NAME") or "").strip()

    if "pwnm" in file_name or "taboo" in file_name:
        grade = (row.get("GRADE") or "").strip()
        grade_str = f" ({grade})" if grade else ""
        class_name = (row.get("CLASS_NAME") or "").strip()
        class_str = f" 약효 분류: {class_name}." if class_name else ""
        return (
            f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
            f"{type_name}{grade_str} 약물입니다. 임부 금기 사유: {prohbt_content or '임부에 대한 안전성 미확립.'}{class_str}"
        )
    if ("mdctn_pd" in file_name or "atent" in file_name) and "MAX_DOSAGE_TERM" in row:
        max_dosage_term = (row.get("MAX_DOSAGE_TERM") or "").strip()
        return (
            f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
            f"{type_name} 약물이며, 최대 처방(투여) 기간은 [{max_dosage_term}]입니다. "
            f"상세 내용: {prohbt_content or '투여기간 주의 필요.'}"
        )
    if "efcy" in file_name or "dplct" in file_name:
        sers_name = (row.get("SERS_NAME") or "").strip()
        class_name = (row.get("CLASS_NAME") or "").strip()
        sers_str = f" [{sers_name}] 계열" if sers_name else ""
        class_str = f"({class_name})" if class_name else ""
        return (
            f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
            f"{type_name} 주의 약물입니다. 해당 성분은{sers_str}{class_str}에 속하며, "
            f"동일 효능군 약물과의 중복 처방을 주의해야 합니다."
        )
    return (
        f"의약품 성분 [{ingr_name}] (영문명: {ingr_eng_name})은/는 "
        f"{type_name} 약물입니다. 상세 안내: {prohbt_content or '주의 및 안내 사항 확인 필요.'}"
    )


def _load_docs_from_csv(csv_file: Path):
    """CSV 한 파일을 읽어 Document 리스트로 변환합니다."""
    import csv

    from langchain_core.documents import Document

    file_name = csv_file.name.lower()
    file_docs = []
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ingr_name = (row.get("INGR_NAME") or "").strip()
            if not ingr_name:
                continue

            ingr_eng_name = (row.get("INGR_ENG_NAME") or "").strip()
            prohbt_content = (row.get("PROHBT_CONTENT") or "").strip()
            dur_seq = (row.get("DUR_SEQ") or "").strip()
            type_name = (row.get("TYPE_NAME") or "").strip()

            page_content = _build_page_content(file_name, row, ingr_name, ingr_eng_name, prohbt_content)
            # 크로마 메타데이터에는 문자열, 정수, 실수, 부울만 허용되므로 모두 문자열 형태로 바인딩
            metadata = {
                "source": _display_source_label(csv_file.name),
                "ingr_name": ingr_name,
                "type_name": type_name,
                "dur_seq": dur_seq,
            }
            file_docs.append(Document(page_content=page_content, metadata=metadata))
    return file_docs


def ingest_csv_data():
    """
    mock_data_for_rag 디렉토리의 CSV 파일들을 읽어 ChromaDB에 적재합니다.
    이미 데이터가 적재되어 있다면 인덱싱을 생략합니다.
    """
    # 크로마 데이터 디렉토리 생성
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # Chroma 스토어 연결 (PERSIST_DIRECTORY 옵션 역할). 컬렉션 메타데이터에 임베딩 모델명을
    # 함께 기록하기 위해 공용 팩토리를 거친다.
    db = build_vector_store()

    # 이미 데이터가 적재되어 있는지 확인 (컬렉션 카운트)
    try:
        existing_count = db._collection.count()
        if existing_count > 0:
            logger.info(f"ChromaDB already has {existing_count} documents. Skipping ingestion.")
            return db
    except Exception as e:
        logger.warning(f"Failed to check existing collection count: {e}. Proceeding with ingestion.")

    # CSV 데이터 로드 및 파싱
    if not DATA_DIR.exists():
        logger.error(f"Data directory {DATA_DIR} does not exist. Cannot ingest.")
        return db

    csv_files = list(DATA_DIR.glob("*.csv"))
    if not csv_files:
        logger.warning(f"No CSV files found in {DATA_DIR}")
        return db

    all_docs = []
    for csv_file in csv_files:
        logger.info(f"Loading and processing CSV: {csv_file.name}")
        try:
            file_docs = _load_docs_from_csv(csv_file)
            all_docs.extend(file_docs)
            logger.info(f"Processed {len(file_docs)} documents from {csv_file.name}")
        except Exception as e:
            logger.error(f"Error processing {csv_file.name}: {e}")

    if all_docs:
        logger.info(f"Ingesting {len(all_docs)} total documents into ChromaDB...")
        # 대량 데이터 분할 적재
        batch_size = 500
        for i in range(0, len(all_docs), batch_size):
            batch = all_docs[i : i + batch_size]
            db.add_documents(batch)
            logger.info(f"Ingested batch {i // batch_size + 1} ({len(batch)} docs)")
        logger.info("ChromaDB ingestion completed successfully.")
    else:
        logger.warning("No documents to ingest.")

    return db


if __name__ == "__main__":
    ingest_csv_data()
