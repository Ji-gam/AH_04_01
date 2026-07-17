"""임베딩 프로바이더와 컬렉션 호환성 검증.

예전엔 `ai_worker/tasks/ingest.py` 안에 DUR 전용 인제스트 로직과 뒤섞여 있었다. 그
파일이 매니페스트 파이프라인(`ai_worker/ingest/`)으로 대체되면서, 프로바이더 선택과
모델 식별자만 여기로 분리한다 — 인제스트든 검색이든 같은 임베딩을 써야 하므로 어느
한쪽에 얹혀 있으면 안 된다.
"""

import logging
from pathlib import Path

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from ai_worker.core.config import settings

logger = logging.getLogger("ai_worker.ingest.embeddings")

CHROMA_DIR = Path(__file__).parent.parent / "chroma_data"

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
