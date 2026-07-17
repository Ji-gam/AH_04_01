from datetime import datetime

from pydantic import BaseModel, Field


class AdminChatSessionListItem(BaseModel):
    id: int = Field(description="채팅 세션 ID")
    profile_id: int = Field(description="세션 소유 프로필 ID")
    profile_name: str = Field(description="세션 소유 프로필 이름(닉네임)")
    created_at: datetime = Field(description="세션 생성 시각")


class IngestPapersRequest(BaseModel):
    categories: list[str] | None = Field(default=None, description="재수집할 카테고리만 지정. 생략 시 전체")
    retmax_per_category: int | None = Field(default=None, description="조합(질환×카테고리)당 수집 건수")


class IngestCsvResult(BaseModel):
    filename: str = Field(description="업로드된 CSV 파일명")
    deleted: int = Field(description="재업로드 전 이 파일 소스로 있던 기존 문서 수(삭제됨)")
    ingested: int = Field(description="이번 호출로 새로 적재된 문서 수")
    collection_count: int = Field(description="처리 후 dur_rules 컬렉션의 전체 문서 수")
    errors: list[str] = Field(default_factory=list, description="파싱 실패/행 단위 경고/미등록 파일 안내")


class IngestPapersResult(BaseModel):
    status: str = Field(description="'started' 고정 - 백그라운드로 실행되어 즉시 반환한다")


class SourceScanResult(BaseModel):
    """source/(드롭 폴더)와 _manifest.yaml 대조 결과. ai_worker의 같은 이름 스키마를 미러링한다."""

    indexed: list[str] = Field(description="매니페스트에 등록되어 색인되는 파일")
    excluded: list[str] = Field(description="일부러 RAG에서 뺀 파일(rag: false)")
    unregistered: list[str] = Field(description="source/에 있으나 매니페스트에 없는 파일 — 색인되지 않는다")
    missing: list[str] = Field(description="매니페스트엔 있으나 source/에 없는 파일")


class IngestStatusResult(BaseModel):
    dur_rules_count: int = Field(description="dur_rules 컬렉션 문서 수")
    pubmed_papers_count: int = Field(description="pubmed_papers 컬렉션 문서 수")
    papers_raw_counts: dict[str, int] = Field(description="질환별 원본 PubMed JSON 파일 수")
    sources: SourceScanResult = Field(description="드롭 폴더 대조 결과")
