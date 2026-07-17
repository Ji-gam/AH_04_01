"""`source/_manifest.yaml` 로드·검증.

매니페스트는 이 시스템에서 LangChain이 대신해주지 않는 유일한 조각이다. LangChain은
"이 CSV가 RAG 재료인지"를 알 수 없고 알아서도 안 된다 — `source/`엔 `ITEM_SEQ` 기반
구조화 조회 데이터가 훨씬 많이 섞여 있어, 자동 감지가 "텍스트 컬럼이 있네" 하고 집어넣으면
컬렉션이 오염된다(그 판단은 도메인 지식이다).

다만 그 선언이 파이썬 코드일 이유는 없다. 예전엔 파일 하나당 전용 함수 하나
(`_pwnm_content` 등 7개)를 `_DUR_RAG_REGISTRY` 딕셔너리에 박아뒀고, 그래서 파일 추가가
코드 수정이었다 — 시스템이 성장하지 못한 원인. 이제 파일별로 다른 것(어떤 컬럼을 본문으로,
어떤 컬럼을 메타데이터로)은 전부 이 YAML에 있고, 코드는 로더 종류당 하나뿐이다.

**새 파일 추가 = 이 YAML에 블록 하나. 파이썬 0줄.**
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SOURCE_DIR = Path(__file__).parent.parent / "source"
MANIFEST_PATH = SOURCE_DIR / "_manifest.yaml"


class ManifestError(Exception):
    """매니페스트가 깨졌거나 필수 항목이 빠졌을 때. 조용히 넘어가면 데이터가 소리 없이
    누락되므로(예전 파이프라인의 고질병) 설정 오류로 간주해 즉시 실패한다."""


@dataclass(frozen=True)
class SourceSpec:
    """매니페스트의 `sources:` 블록 하나 = `source/`의 파일 하나에 대한 처리 선언."""

    file: str
    rag: bool
    # rag=False일 때만 의미 있음. "왜 RAG에서 뺐는지"를 사람이 읽으라고 남긴다.
    reason: str = ""
    loader: str = ""
    collection: str = ""
    # 임베딩될 본문에 넣을 컬럼(순서 유지). 비우면 로더가 전체 컬럼을 쓴다.
    content_columns: tuple[str, ...] = ()
    # 본문엔 안 넣고 필터·표시에만 쓸 컬럼. {원본 컬럼: 메타데이터 키} — 키를 바꿀 수
    # 있어야 검색 층이 기대하는 이름(`ingr_name`)과 CSV 컬럼명(`INGR_NAME`,
    # 병용금기만 `INGR_KOR_NAME`)의 차이를 코드 없이 흡수한다.
    metadata_columns: dict[str, str] = field(default_factory=dict)
    # 파일 단위 고정 메타데이터(예: display_name, publisher). 모든 문서에 그대로 붙는다.
    metadata: dict[str, Any] = field(default_factory=dict)
    # 로더별 추가 인자(예: JSON의 content_key).
    args: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return SOURCE_DIR / self.file


def _parse_source(raw: dict, idx: int) -> SourceSpec:
    file = raw.get("file")
    if not file:
        raise ManifestError(f"sources[{idx}]: 'file'이 없습니다.")

    rag = raw.get("rag", True)
    if not rag:
        return SourceSpec(file=file, rag=False, reason=raw.get("reason", ""))

    for required in ("loader", "collection"):
        if not raw.get(required):
            raise ManifestError(f"{file}: rag=true인 소스엔 '{required}'가 필요합니다.")

    return SourceSpec(
        file=file,
        rag=True,
        loader=raw["loader"],
        collection=raw["collection"],
        content_columns=tuple(raw.get("content_columns") or ()),
        metadata_columns=dict(raw.get("metadata_columns") or {}),
        metadata=dict(raw.get("metadata") or {}),
        args=dict(raw.get("args") or {}),
    )


def load_manifest(path: Path | None = None) -> list[SourceSpec]:
    """매니페스트를 읽어 SourceSpec 목록으로 돌려준다. 파일이 없거나 형식이 틀리면
    ManifestError로 즉시 실패한다."""
    path = path or MANIFEST_PATH
    if not path.exists():
        raise ManifestError(f"매니페스트가 없습니다: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources")
    if not isinstance(sources, list):
        raise ManifestError(f"{path}: 최상위에 'sources' 목록이 필요합니다.")

    specs = [_parse_source(s, i) for i, s in enumerate(sources)]

    duplicates = {s.file for s in specs if [x.file for x in specs].count(s.file) > 1}
    if duplicates:
        raise ManifestError(f"매니페스트에 중복된 file 항목: {sorted(duplicates)}")
    return specs


def scan_source_dir(specs: list[SourceSpec] | None = None, source_dir: Path | None = None) -> dict[str, list[str]]:
    """`source/`의 실제 파일과 매니페스트를 대조한다.

    예전엔 레지스트리에 없는 파일을 **조용히 무시**했다 — 사용자가 데이터를 던져 넣어도
    아무 일도 안 일어나고 아무 말도 없었다. 드롭 폴더로 쓰려면 최소한 "이 파일은 아직
    등록 안 됐다"고 말해줘야 한다. 관리자 화면(`/admin/ingest/status`)이 이걸 노출한다."""
    specs = specs if specs is not None else load_manifest()
    source_dir = source_dir or SOURCE_DIR
    declared = {s.file for s in specs}

    present = {
        p.name
        for p in source_dir.iterdir()
        # `_`로 시작하는 건 매니페스트 자신이나 파생 캐시(예: paper_summaries_ko.json)라
        # 원천 데이터가 아니다.
        if p.is_file() and not p.name.startswith("_") and not p.name.startswith(".")
    }

    return {
        "indexed": sorted(f for f in present if f in {s.file for s in specs if s.rag}),
        "excluded": sorted(f for f in present if f in {s.file for s in specs if not s.rag}),
        "unregistered": sorted(present - declared),
        "missing": sorted(declared - present),
    }
