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
    collection_count: int = Field(description="처리 후 해당 컬렉션의 전체 문서 수")
    errors: list[str] = Field(default_factory=list, description="파싱 실패/행 단위 경고/미등록 파일 안내")


class IngestPapersResult(BaseModel):
    status: str = Field(description="'started' 고정 - 백그라운드로 실행되어 즉시 반환한다")


class SourceScanResult(BaseModel):
    """드롭 폴더(source/) 현황. ai_worker의 같은 이름 스키마를 미러링한다."""

    indexed: list[str] = Field(description="색인되는 파일 — 드롭 폴더에 있으면 전부 여기 든다")
    unsupported: list[str] = Field(description="확장자를 읽을 줄 몰라 건너뛰는 파일")


class IngestStatusResult(BaseModel):
    structured_count: int = Field(description="structured 컬렉션(CSV — DUR 규칙 + e약은요) 문서 수")
    unstructured_count: int = Field(description="unstructured 컬렉션(논문 + 복약안내서) 문서 수")
    papers_raw_counts: dict[str, int] = Field(description="질환별 원본 PubMed JSON 파일 수")
    sources: SourceScanResult = Field(description="드롭 폴더 현황")
