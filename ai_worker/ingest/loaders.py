"""매니페스트가 지목하는 LangChain 로더들.

`langchain_community`의 `CSVLoader`/`JSONLoader`를 쓰지 않는 이유: 그 패키지는
2026-05-22 sunset, 06-19 아카이브(읽기 전용)됐고 이 로더들은 전용 패키지로 이관되지
않았다. LangChain의 공식 안내가 "implement tools directly in application code"이고,
그 확장 지점으로 `langchain_core.document_loaders.BaseLoader`를 core에 남겨뒀다.
그래서 BaseLoader를 구현한다 — 이게 LangChain 방식이지 우리 발명이 아니다.

핵심은 **로더가 파일 종류당 하나**라는 것이다. 예전엔 파일 하나당 전용 함수 하나였다
(CSV 7개 = 함수 7개). 이제 CSV가 몇 개가 되든 이 로더 하나가 처리하고, 파일별 차이는
매니페스트에 있다.
"""

import csv
import json
from collections.abc import Iterator
from typing import Any

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from ai_worker.ingest.manifest import SourceSpec

# 일부 원천 CSV는 한 셀에 긴 안내문이 통째로 들어있어 기본 한도(131,072자)를 넘긴다.
csv.field_size_limit(10**9)


def _render(row: dict[str, Any], columns: tuple[str, ...]) -> str:
    """본문 텍스트. LangChain CSVLoader의 관례("컬럼: 값" 줄바꿈 나열)를 따른다 —
    우리만의 문장 템플릿을 발명하지 않는다. 빈 값은 검색에 기여하지 않고 노이즈만
    되므로 뺀다."""
    cols = columns or tuple(row.keys())
    lines = [f"{c}: {v}" for c in cols if (v := (row.get(c) or "").strip())]
    return "\n".join(lines)


def _base_metadata(spec: SourceSpec) -> dict[str, Any]:
    # `source`는 index()의 source_id_key로 쓰인다 — 이 키를 기준으로 cleanup이
    # "이 파일에서 온 문서들"을 묶어 정리한다.
    return {"source": spec.file, "collection": spec.collection, **spec.metadata}


def _column_metadata(record: dict[str, Any], columns: dict[str, str]) -> dict[str, str]:
    """레코드의 컬럼 값을 메타데이터로 옮긴다. `columns`는 {원본 컬럼: 메타데이터 키}.

    키 이름을 바꿀 수 있어야 하는 이유: 검색 층이 기대하는 키와 CSV 컬럼명이 다르다
    (`retrieve_service`는 `ingr_name`으로 필터하는데 CSV 컬럼은 `INGR_NAME`이고,
    병용금기 파일만 `INGR_KOR_NAME`이다). 이런 차이를 코드가 아니라 매니페스트가 흡수한다."""
    return {key: (str(record.get(col) or "")).strip() for col, key in columns.items()}


class CsvRecordLoader(BaseLoader):
    """CSV 한 파일 = 문서 여러 개(행 1개 = 문서 1개).

    행이 곧 완결된 레코드라 청킹하지 않는다. 어떤 컬럼을 본문에 넣을지는 매니페스트의
    `content_columns`가 정한다."""

    def __init__(self, spec: SourceSpec) -> None:
        self.spec = spec

    def lazy_load(self) -> Iterator[Document]:
        with self.spec.path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                content = _render(row, self.spec.content_columns)
                if not content:
                    # 본문 컬럼이 전부 비어있으면 임베딩할 게 없다. index()가 콘텐츠
                    # 해시로 중복을 잡으므로, 빈 문서를 넣으면 서로 같은 문서로 뭉친다.
                    continue
                metadata = _base_metadata(self.spec)
                metadata.update(_column_metadata(row, self.spec.metadata_columns))
                yield Document(page_content=content, metadata=metadata)


class JsonRecordLoader(BaseLoader):
    """JSON 배열 한 파일 = 문서 여러 개(원소 1개 = 문서 1개).

    논문 JSON(`source/당뇨.json` 등)이 이 형태다. `args.content_columns`가 없으면
    원소의 모든 키를 쓴다."""

    def __init__(self, spec: SourceSpec) -> None:
        self.spec = spec

    def lazy_load(self) -> Iterator[Document]:
        records = json.loads(self.spec.path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError(f"{self.spec.file}: 최상위가 JSON 배열이 아닙니다.")

        for record in records:
            content = _render(record, self.spec.content_columns)
            if not content:
                continue
            metadata = _base_metadata(self.spec)
            metadata.update(_column_metadata(record, self.spec.metadata_columns))
            yield Document(page_content=content, metadata=metadata)


# 매니페스트의 `loader:` 값 -> 구현. 새 포맷 지원 = 여기 한 줄 + 매니페스트 한 줄.
# PDF(`docling`)는 langchain-docling 도입 시 추가한다.
LOADERS: dict[str, type[BaseLoader]] = {
    "csv": CsvRecordLoader,
    "json": JsonRecordLoader,
}


def build_loader(spec: SourceSpec) -> BaseLoader:
    loader_cls = LOADERS.get(spec.loader)
    if loader_cls is None:
        raise ValueError(f"{spec.file}: 알 수 없는 loader '{spec.loader}'. 가능한 값: {sorted(LOADERS)}")
    return loader_cls(spec)  # type: ignore[call-arg]
