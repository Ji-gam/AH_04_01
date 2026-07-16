import zoneinfo
from dataclasses import field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))

    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    # 분류·구조화 추출·논문 답변은 결정적이어야 하므로 기본 0. 창의성이 필요한
    # 용도가 생기면 호출부에서 개별적으로 올린다(기본값은 결정성 우선).
    OPENAI_TEMPERATURE: float = 0.0

    # RAG 검색 유사도 임계값(Chroma L2 거리, score < threshold만 통과). 임베딩 백엔드가
    # 바뀌면 거리 스케일도 달라지므로 값이 코드에 박히지 않도록 config로 뺀다.
    RAG_SIMILARITY_THRESHOLD: float = 1.4
    # DUR 검색 시 반환할 최대 청크 수. 기존 /retrieve 요청의 기본값(limit=3)을 그대로
    # 고정값으로 옮긴 것 — 통합 스트리밍 엔드포인트는 요청마다 limit을 안 받는다.
    RAG_RETRIEVAL_LIMIT: int = 3

    # PubMed E-utilities (T-LLM-7-3). 키 없이도 동작(3req/sec 제한), 무료 키 등록 시
    # 10req/sec로 완화된다(https://www.ncbi.nlm.nih.gov/account/settings/).
    PUBMED_API_KEY: str | None = None
    # esearch/efetch 각각에 적용되는 타임아웃(순차 2회 호출이라 총 지연은 최대 2배).
    PUBMED_TIMEOUT: float = 8.0

    # 논문 RAG 검색 유사도 임계값. RAG_SIMILARITY_THRESHOLD(1.4)는 DUR의 짧고 균일한
    # 템플릿 문장 기준으로 튜닝된 값이라 그대로 재사용하면 안 맞을 가능성이 높아 별도로 둔다.
    # 1.6은 실제 질문으로 재보니 "안녕"/"고마워" 같은 잡담까지 통과시켜(점수 1.57~1.60)
    # 1.5로 낮춤 — 관련 질문(점수 1.06~1.44)과 잡담(1.57~1.75) 사이 간격이 뚜렷해 1.5가
    # 안전하게 그 사이를 가른다(2026-07-16 실측, ingest_papers 색인 데이터 기준).
    PAPER_SIMILARITY_THRESHOLD: float = 1.5
    # 논문 검색 시 반환할 최대 청크 수(멀티 논문 인용).
    PAPER_RETRIEVAL_LIMIT: int = 5


# 글로벌 싱글톤 인스턴스 생성
settings = Config()
