import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from langchain_chroma import Chroma
from pydantic import BaseModel

from ai_worker.tasks.ingest import get_embeddings, ingest_csv_data

# 로거 설정
logger = logging.getLogger("ai_worker.main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="ReMedi AI Worker Service",
    description="RAG 파이프라인 및 Vector DB 검색 서비스를 제공하는 백그라운드 워커 API",
    version="0.1.0",
)

# 싱글톤 데이터베이스 인스턴스 및 성분명 캐시 홀더.
# 값 타입을 Any로 둔 이유: 테스트에서 이 딕셔너리에 실제 Chroma 대신 duck-typed
# fake 객체를 직접 대입해 모킹하므로(ai_worker/tests/test_main.py 참고), Chroma로
# 좁히면 오히려 모킹이 막힌다.
CHROMA_DIR = Path(__file__).parent / "chroma_data"

db_holder: dict[str, Any] = {
    "db": None,
    "ingr_names": set(),
}


class RetrieveRequest(BaseModel):
    query: str
    limit: int = 3


class DocumentChunk(BaseModel):
    content: str
    metadata: dict


class RetrieveResponse(BaseModel):
    chunks: list[DocumentChunk]


def cache_ingr_names(db: Chroma):
    """ChromaDB 적재 문서로부터 모든 성분명을 추출하여 캐싱합니다."""
    try:
        logger.info("Extracting and caching unique drug ingredients from ChromaDB...")
        collection = db._collection
        # metadatas만 조회
        data = collection.get(include=["metadatas"])
        metadatas = (data.get("metadatas") or []) if data else []
        names = set()
        for meta in metadatas:
            if not meta:
                continue
            ingr_name = meta.get("ingr_name")
            if isinstance(ingr_name, str) and ingr_name:
                names.add(ingr_name.strip())
        db_holder["ingr_names"] = names
        logger.info(f"Cached {len(names)} unique ingredients (e.g., {list(names)[:5]})")
    except Exception as e:
        logger.error(f"Failed to cache ingredient names: {e}")


@app.on_event("startup")
async def startup_event():
    """
    서비스 기동 시 데이터 인덱싱(Ingestion)을 자동 수행하고,
    크로마 DB 연결 객체와 성분명 인덱스를 캐싱합니다.
    """
    logger.info("Initializing RAG Ingestion on startup...")
    try:
        # 동기 Ingestion 함수 실행
        db = ingest_csv_data()
        db_holder["db"] = db
        cache_ingr_names(db)
        logger.info("RAG Initialization completed.")
    except Exception as e:
        logger.error(f"Failed to initialize RAG on startup: {e}")


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_documents(payload: RetrieveRequest) -> RetrieveResponse:
    """
    입력된 쿼리에 대해 ChromaDB에서 가장 유사한 의약 안전 정보 문서(chunk)들을 검색합니다.
    쿼리 내에 성분명이 식별될 경우 메타데이터 필터링을 우선 적용합니다.
    """
    db = db_holder["db"]
    if db is None:
        try:
            embeddings = get_embeddings()
            db = Chroma(collection_name="dur_rules", embedding_function=embeddings, persist_directory=str(CHROMA_DIR))
            db_holder["db"] = db
            cache_ingr_names(db)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Vector DB is not initialized. Error: {e}") from e

    try:
        logger.info(f"Retrieving documents for query: '{payload.query}' (limit: {payload.limit})")

        # 쿼리 내 성분명 매칭 기반 동적 메타데이터 필터링
        filter_dict = None
        query_text = payload.query.replace(" ", "")
        ingr_names = db_holder["ingr_names"]

        # 가장 긴 성분명부터 매칭을 시도하여 정확도를 높입니다.
        sorted_ingrs = sorted(list(ingr_names), key=len, reverse=True)
        for ingr in sorted_ingrs:
            # 양방향 부분 매칭 검사:
            # 1. 쿼리 텍스트가 성분명의 일부인 경우 (예: "졸피뎀" -> "졸피뎀타르타르산염")
            # 2. 성분명이 쿼리 텍스트의 일부인 경우 (예: "졸피뎀타르타르산염에 대해" -> "졸피뎀타르타르산염")
            if (ingr in query_text) or (len(query_text) >= 2 and query_text in ingr):
                filter_dict = {"ingr_name": ingr}
                logger.info(f"Dynamic metadata filter applied: ingr_name='{ingr}'")
                break

        # 유사도 점수(Score)를 포함한 검색 수행
        docs_with_scores = db.similarity_search_with_score(payload.query, k=payload.limit, filter=filter_dict)

        # 디버깅 로그 출력 (유사도 거리 분석용)
        for doc, score in docs_with_scores:
            logger.info(
                f"DEBUG_SCORE: INGR={doc.metadata.get('ingr_name')}, score={score}, source={doc.metadata.get('source')}"
            )

        # 임계값(score < 1.4)을 만족하는 유효한 문서만 반환합니다.
        threshold = 1.4
        valid_docs = [doc for doc, score in docs_with_scores if score < threshold]

        # 문서의 내용과 메타데이터를 함께 추출
        chunks = [DocumentChunk(content=doc.page_content, metadata=doc.metadata) for doc in valid_docs]
        logger.info(
            f"Found {len(chunks)} relevant chunks after filter and threshold (candidates: {len(docs_with_scores)})"
        )
        return RetrieveResponse(chunks=chunks)
    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        raise HTTPException(status_code=500, detail=f"Error occurred during vector retrieval: {e}") from e


@app.get("/health")
async def health_check():
    """
    컨테이너 헬스체크용 엔드포인트
    """
    return {"status": "healthy", "db_loaded": db_holder["db"] is not None}
