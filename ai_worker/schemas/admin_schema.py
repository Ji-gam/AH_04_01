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
    """드롭 폴더(source/)에 뭐가 있는지.

    예전엔 `excluded`/`unregistered`/`missing`이 더 있었다. 전부 폴더와 별개로 "선언"이
    존재해서 생기던 어긋남이었다 — 폴더가 곧 진실이면 어긋날 대상이 없다. 남는 건
    "이 확장자는 읽을 줄 모른다" 하나뿐이다."""

    indexed: list[str]
    unsupported: list[str]


class IngestStatusResponse(BaseModel):
    structured_count: int
    unstructured_count: int
    papers_raw_counts: dict[str, int]
    sources: SourceScanResult
