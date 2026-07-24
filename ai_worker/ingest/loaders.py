"""확장자 -> LangChain `Document`.

**왜 로더를 직접 구현하나:** `langchain_community`가 이 프로젝트에 설치돼 있지 않다.
`CSVLoader` / `JSONLoader` / `PyPDFLoader` / `TextLoader`를 전부 못 쓴다 —
`langchain_classic`도 community를 요구하며 ImportError를 낸다. LangChain은 그 대신
`langchain_core`에 `BaseLoader`를 확장 지점으로 남겼고 "애플리케이션 코드에서 직접
구현하라"고 안내한다. 그러니 아래는 우리 발명이 아니라 **LangChain이 시킨 방식**이다.

자르는 원칙: **자연스러운 금이 있으면 그걸 따르고, 없으면 글자 수로 자른다.**
  CSV 행 / JSON 원소  -> 그 자체로 완결. 안 자른다.
  마크다운            -> 헤더가 금이다. MarkdownHeaderTextSplitter.
  PDF                 -> 금이 없다. RecursiveCharacterTextSplitter.
"""

import csv
import json
import logging
from collections.abc import Iterator
from typing import Any

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from ai_worker.ingest.sources import Source

logger = logging.getLogger("ai_worker.ingest.loaders")

# 일부 원천 CSV는 한 셀에 긴 안내문이 통째로 들어있어 기본 한도(131,072자)를 넘긴다.
csv.field_size_limit(10**9)

_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 200


def _render(record: dict[str, Any], exclude: frozenset[str]) -> str:
    """본문 텍스트. LangChain CSVLoader의 관례("컬럼: 값" 줄바꿈 나열)를 따른다 —
    우리만의 한국어 문장 템플릿을 발명하지 않는다.

    **기본은 전 컬럼이고, 빼는 것만 지정한다.** 빈 값은 검색에 기여하지 않고 노이즈만
    되므로 건너뛴다."""
    lines = []
    for key, raw in record.items():
        if key in exclude:
            continue
        value = str(raw if raw is not None else "").strip()
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _base_metadata(source: Source) -> dict[str, Any]:
    # `source`는 index()의 source_id_key다 — cleanup이 이 키로 "이 파일에서 온 문서"를 묶는다.
    return {"source": source.name, "collection": source.collection, **source.metadata}


def _record_metadata(record: dict[str, Any], columns: dict[str, str]) -> dict[str, str]:
    """레코드의 컬럼을 메타데이터로 옮긴다. `columns`는 {원본 컬럼: 메타데이터 키}.

    없는 컬럼은 건너뛴다 — 이 설정은 전역이라 파일마다 있는 컬럼이 다르다. 그래서
    `INGR_NAME`과 `INGR_KOR_NAME`을 둘 다 `ingr_name`으로 보내도, 각 파일엔 둘 중
    하나만 있으므로 충돌하지 않는다(병용금기만 KOR을 쓴다)."""
    out = {}
    for column, key in columns.items():
        value = str(record.get(column) or "").strip()
        if value:
            out[key] = value
    return out


class CsvLoader(BaseLoader):
    """CSV 한 파일 = 문서 여러 개. 행이 곧 완결된 레코드라 자르지 않는다.

    단 `explode_columns`가 선언되면 행 1개를 필드마다 문서 1개로 쪼갠다."""

    def __init__(self, source: Source) -> None:
        self.source = source

    def _explode(self, row: dict[str, Any], metadata: dict[str, Any]) -> Iterator[Document]:
        """행 하나를 필드마다 별개 문서로 쪼갠다. 필드가 곧 질문 유형인 파일용(e약은요).

        머리말을 따로 선언하지 않는다 — **쪼갠 필드와 제외 컬럼을 빼고 남은 게 곧 머리말**이다
        (e약은요면 itemName·entpName). 조각마다 "어느 약인지"가 있어야 "타이레놀 부작용"이
        약 이름으로도 걸리고, 뽑혔을 때 무슨 약 얘긴지 알 수 있다."""
        header = _render(row, self.source.exclude_columns | frozenset(self.source.explode_columns))
        for column, label in self.source.explode_columns.items():
            text = str(row.get(column) or "").strip()
            if not text:
                continue
            content = f"{header}\n{label}: {text}" if header else f"{label}: {text}"
            yield Document(page_content=content, metadata={**metadata, "field": label})

    def lazy_load(self) -> Iterator[Document]:
        with self.source.path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                metadata = _base_metadata(self.source)
                metadata.update(_record_metadata(row, self.source.metadata_columns))

                if self.source.explode_columns:
                    yield from self._explode(row, metadata)
                    continue

                content = _render(row, self.source.exclude_columns)
                if not content:
                    # 본문이 통째로 비면 임베딩할 게 없다. index()가 콘텐츠 해시로 중복을
                    # 잡으므로 빈 문서를 넣으면 서로 같은 문서로 뭉친다.
                    continue
                yield Document(page_content=content, metadata=metadata)


class JsonLoader(BaseLoader):
    """JSON 배열 한 파일 = 문서 여러 개(원소 1개 = 문서 1개).

    논문 초록을 고정 크기로 자르지 않는 이유: 740편 중 729편(99%)이 쪼개져 제목 없는
    조각이 컬렉션의 70%가 됐고, 그게 "고혈압 질문에 당뇨 논문"의 원인이었다."""

    def __init__(self, source: Source) -> None:
        self.source = source

    def lazy_load(self) -> Iterator[Document]:
        records = json.loads(self.source.path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError(f"{self.source.name}: 최상위가 JSON 배열이 아닙니다.")

        for record in records:
            content = _render(record, self.source.exclude_columns)
            if not content:
                continue
            metadata = _base_metadata(self.source)
            metadata.update(_record_metadata(record, self.source.metadata_columns))
            yield Document(page_content=content, metadata=metadata)


class MarkdownLoader(BaseLoader):
    """마크다운 = 헤더가 곧 금이다.

    LangChain이 문서로 안내하는 2단 조합을 그대로 쓴다: 헤더로 의미 단위를 가른 뒤
    (`MarkdownHeaderTextSplitter`), 그래도 긴 덩어리는 글자 수로 한 번 더 자른다
    (`RecursiveCharacterTextSplitter`). 헤더 텍스트는 메타데이터로 따라붙어 조각이
    어느 절에서 왔는지 남는다.

    페이지 번호는 남기지 않는다. OCR 산출물에 `## N쪽` 마커를 넣어봤지만, LLM이 정리하며
    만든 헤딩이 `#`/`##`/`###` 전부를 이미 쓰고 있어 페이지 마커만 가려낼 레벨이 없었다.
    무엇보다 `metadata["page"]`를 읽는 코드가 어디에도 없었다 — 아무도 안 쓰는 값을 위해
    커스텀 파서를 두지 않는다. 인용에 페이지가 필요해지면 그때 다시 만든다."""

    def __init__(self, source: Source) -> None:
        self.source = source

    def lazy_load(self) -> Iterator[Document]:
        header_splitter = MarkdownHeaderTextSplitter([("#", "section"), ("##", "subsection")])
        size_splitter = RecursiveCharacterTextSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)
        sections = header_splitter.split_text(self.source.path.read_text(encoding="utf-8"))
        for doc in size_splitter.split_documents(sections):
            content = doc.page_content.strip()
            if not content:
                continue
            yield Document(page_content=content, metadata={**_base_metadata(self.source), **doc.metadata})


class PdfLoader(BaseLoader):
    """PDF 한 파일 = 페이지마다 잘린 문서 여러 개.

    pymupdf로 읽고 LangChain 기본 splitter로 자른다. Docling을 쓰지 않는 이유: Apple
    Silicon에서 가속기가 MPS를 잡으면 레이아웃 모델이 float64를 써서 전 페이지가 터지고
    ("Cannot convert a MPS Tensor to float64"), CPU 강제가 필요하며, 청크 메타데이터가
    중첩 dict라 Chroma가 거부해 풀어줘야 한다. PDF 몇 개에 그 무게는 과하다.

    글자가 안 나오면(스캔본) 0건이 되고 파이프라인이 그걸 고장으로 잡는다. 그건 이
    로더가 고칠 문제가 아니다 — `ai_worker/scripts/ocr_pdf.py`로 미리 `.md`를 만들어
    넣는다(사서는 요리를 안 한다)."""

    def __init__(self, source: Source) -> None:
        self.source = source

    def lazy_load(self) -> Iterator[Document]:
        import pymupdf

        splitter = RecursiveCharacterTextSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)
        doc = pymupdf.open(self.source.path)
        try:
            # pymupdf Document는 런타임엔 iterable이지만 타입 스텁이 그렇게 선언하지 않아
            # `enumerate(doc)`가 mypy에서 걸린다. 인덱스로 도는 게 스텁과 맞는다.
            for index in range(doc.page_count):
                page_no = index + 1
                text = doc[index].get_text().strip()
                if not text:
                    continue
                for chunk in splitter.split_text(text):
                    yield Document(page_content=chunk, metadata={**_base_metadata(self.source), "page": page_no})
        finally:
            doc.close()


# 확장자 -> 구현. **새 포맷 지원 = 여기 한 줄 + BaseLoader 구현 하나.**
#
# 매니페스트에 `loader: csv`를 적게 하지 않는다. 파일이 이미 아는 걸 사람에게 또 물으면
# 두 벌이 되고, 두 벌은 어긋날 수 있으며, 어긋나도 아무도 안 알려준다. 실제로 예전
# 선언 18개는 **전부** 확장자와 일치했다 — 애초에 물어볼 필요가 없는 질문이었다.
LOADERS: dict[str, type[BaseLoader]] = {
    ".csv": CsvLoader,
    ".json": JsonLoader,
    ".md": MarkdownLoader,
    ".pdf": PdfLoader,
}


def build_loader(source: Source) -> BaseLoader:
    loader_cls = LOADERS.get(source.path.suffix.lower())
    if loader_cls is None:
        raise ValueError(f"{source.name}: 지원하지 않는 확장자입니다. 가능한 값: {sorted(LOADERS)}")
    return loader_cls(source)  # type: ignore[call-arg]
