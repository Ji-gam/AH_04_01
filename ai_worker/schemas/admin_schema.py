from pydantic import BaseModel


class IngestCsvResponse(BaseModel):
    filename: str
    deleted: int
    ingested: int
    collection_count: int
    errors: list[str] = []


class IngestPapersRequest(BaseModel):
    categories: list[str] | None = None
    retmax_per_category: int | None = None


class IngestPapersStartedResponse(BaseModel):
    status: str = "started"


class SourceScanResult(BaseModel):
    """source/(드롭 폴더)와 _manifest.yaml의 대조 결과.

    `unregistered`가 이 스키마의 존재 이유다 — 예전엔 매니페스트(당시엔 하드코딩
    레지스트리)에 없는 파일을 **조용히 무시**해서, 데이터를 넣어도 아무 일도 아무 말도
    없었다. 드롭 폴더로 쓰려면 "이건 아직 등록 안 됐다"고 말해줘야 한다."""

    indexed: list[str]
    excluded: list[str]
    unregistered: list[str]
    missing: list[str]


class IngestStatusResponse(BaseModel):
    dur_rules_count: int
    pubmed_papers_count: int
    papers_raw_counts: dict[str, int]
    sources: SourceScanResult
