import zoneinfo
from dataclasses import field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))

    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # 공유 MySQL(app/core/config.py와 동일 필드명 — 같은 .env를 두 서비스가 나눠 쓴다).
    # ai_worker 자체는 요청 처리 중엔 MySQL을 안 읽는다(retrieve_service는 Chroma만 연다) —
    # 오직 scripts/export_source_from_mysql.py(빌드 시점, 드롭 폴더 CSV 생성용)만 쓴다.
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "pw1234"
    DB_NAME: str = "ai_health"

    # **RAG엔 필요 없다.** 임베딩은 모델을 로컬에 내려받아 돌리므로 네트워크도 키도 안 쓴다
    # (ingest/embeddings.py의 _LocalHFEmbeddings). 이 키가 필요한 건 아직 안 받은 후보
    # 모델을 API로 비교하는 1회성 도구뿐이다(scripts/benchmark_embeddings.py).
    # 발급: huggingface.co/settings/tokens (Inference Providers 호출 권한 포함)
    HUGGINGFACE_API_KEY: str | None = None
    # Phase 0 임베딩 벤치마크 결과(40문항 골든셋, recall@3: OpenAI 0.85 vs
    # intfloat/multilingual-e5-large 1.0) 채택 — 한국어 도메인 검색 품질이 유의미하게
    # 앞서 기본 프로바이더를 HF로 전환했다(2026-07-17). "openai"로 되돌리면 코드 변경
    # 없이 원복 가능 — `assert_embedding_compatible`이 프로바이더 전환을 자동 감지해
    # 재인제스트를 요구한다.
    EMBEDDING_PROVIDER: str = "huggingface"  # "openai" | "huggingface"
    HF_EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
    # 분류·구조화 추출·논문 답변은 결정적이어야 하므로 기본 0. 창의성이 필요한
    # 용도가 생기면 호출부에서 개별적으로 올린다(기본값은 결정성 우선).
    OPENAI_TEMPERATURE: float = 0.0

    # RAG 검색 유사도 임계값(Chroma L2 거리, score < threshold만 통과). 임베딩 백엔드가
    # 바뀌면 거리 스케일도 달라지므로 값이 코드에 박히지 않도록 config로 뺀다.
    # HF multilingual-e5-large 전환(2026-07-17) 직후 실측: 관련 질문 점수 0.23~0.31,
    # 무관 질문(인사/잡담/성분 미상 일반 건강질문) 점수 0.38~0.51로 간격이 뚜렷해 0.35로
    # 재설정(과거 OpenAI 기준값 1.4는 정규화 단위벡터라도 모델별 거리 분포가 달라 그대로
    # 못 씀 — 이래서 프로바이더 전환 시 반드시 재실측해야 한다).
    RAG_SIMILARITY_THRESHOLD: float = 0.35
    # DUR 검색 시 반환할 최대 청크 수. 기존 /retrieve 요청의 기본값(limit=3)을 그대로
    # 고정값으로 옮긴 것 — 통합 스트리밍 엔드포인트는 요청마다 limit을 안 받는다.
    RAG_RETRIEVAL_LIMIT: int = 3

    # PubMed E-utilities (T-LLM-7-3). 키 없이도 동작(3req/sec 제한), 무료 키 등록 시
    # 10req/sec로 완화된다(https://www.ncbi.nlm.nih.gov/account/settings/).
    PUBMED_API_KEY: str | None = None
    # esearch/efetch 각각에 적용되는 타임아웃(순차 2회 호출이라 총 지연은 최대 2배).
    PUBMED_TIMEOUT: float = 8.0

    # 논문 RAG 검색 유사도 임계값. RAG_SIMILARITY_THRESHOLD는 DUR의 짧고 균일한 템플릿
    # 문장 기준으로 튜닝된 값이라 그대로 재사용하면 안 맞을 가능성이 높아 별도로 둔다.
    # HF multilingual-e5-large 전환(2026-07-17) 직후 실측: 관련 질문 점수 0.31~0.33,
    # 무관 질문(인사/감사/잡담) 점수 0.47~0.54로 간격이 뚜렷해 0.40으로 재설정
    # (과거 OpenAI 기준값 1.5 — 임계값·거리 스케일이 프로바이더마다 달라 전환 시마다
    # 재실측 필요, RAG_SIMILARITY_THRESHOLD 주석 참고).
    PAPER_SIMILARITY_THRESHOLD: float = 0.40
    # 논문 검색 시 반환할 최대 청크 수(멀티 논문 인용).
    PAPER_RETRIEVAL_LIMIT: int = 5


# 글로벌 싱글톤 인스턴스 생성
settings = Config()
