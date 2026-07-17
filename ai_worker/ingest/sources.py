"""드롭 폴더 스캔. **폴더에 있는 파일이 곧 색인 대상이다.**

등록 절차는 없다. `source/`에 넣으면 들어간다. **여기엔 RAG 재료만 넣는다** — 그러면
"이 파일이 RAG인가"를 선언할 필요가 자체가 없다. 한때 SQL 조회용 표가 섞여 있었고, 그래서
파일마다 `rag: false`를 적어줘야 했다. 그게 매니페스트가 생긴 이유였다.

`_tuning.yaml`은 **선택적**이다. 없어도 돈다. 기계가 알 수 없는 것만 적는다:
어떤 컬럼이 본문에 안 어울리는지, 어떤 컬럼을 무슨 이름의 메타데이터로 챙길지, 이름표.

기계가 아는 건 적지 않는다 — 두 벌이 되면 반드시 어긋나고, 어긋나도 아무도 안 알려주므로
사람이 매번 눈으로 확인하게 된다:

    로더 종류  ->  확장자
    컬렉션     ->  확장자
    RAG 여부   ->  폴더
"""

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SOURCE_DIR = Path(__file__).parent.parent / "source"
TUNING_PATH = SOURCE_DIR / "_tuning.yaml"

# 컬렉션은 둘뿐이다. 도메인이 달라서가 아니라 **다루는 방식이 달라서** 나눈다.
# 검색 층은 어차피 메타데이터로 필터하므로(DUR은 ingr_name, 논문은 disease) 도메인별로
# 쪼갤 이유가 없다.
STRUCTURED = "structured"  # CSV — 행 하나가 곧 완결된 레코드. 자르지 않는다.
UNSTRUCTURED = "unstructured"  # JSON/MD/PDF — 산문. 필요하면 자른다.


def nfc(name: str) -> str:
    """파일명을 NFC로 맞춘다.

    macOS는 Finder로 이름을 바꾸면 파일명을 NFD(자모 분리)로 저장하는데, 파이썬이
    `write_text`로 만든 파일과 사람이 편집기로 쓴 설정 문자열은 NFC(완성형)다. 눈으로
    똑같은 "약과음식.md"가 바이트로는 다르다(NFD 52자 vs NFC 24자).

    APFS는 파일을 **열** 때만 정규화를 무시해준다 — `path.exists()`는 True인데 문자열
    비교는 False다. 그래서 파일명을 키로 쓰는 모든 지점에서 이걸 통과시킨다.
    실측(2026-07-17): 안 맞춰서 같은 파일이 `unregistered`와 `missing`에 동시에 떴다."""
    return unicodedata.normalize("NFC", name)


def collection_for(path: Path) -> str:
    """어느 컬렉션에 갈지는 확장자가 안다. 사람이 선언하지 않는다."""
    return STRUCTURED if path.suffix.lower() == ".csv" else UNSTRUCTURED


@dataclass(frozen=True)
class Source:
    """드롭 폴더의 파일 하나 + 그 파일에 대한 선택적 튜닝."""

    path: Path
    # 본문에서 뺄 컬럼. **화이트리스트가 아니라 블랙리스트다.**
    # 화이트리스트는 실수하면 데이터가 소리 없이 사라지고(실제로 7개 DUR 파일 전부에서
    # FORM_NAME·REMARK가 유실되고 있었다), 블랙리스트는 실수해도 노이즈가 조금 늘 뿐이다.
    exclude_columns: frozenset[str] = frozenset()
    # 본문과 별개로 챙길 메타데이터. {원본 컬럼: 메타데이터 키} — 검색 층이 기대하는 이름과
    # 원본 컬럼명의 차이를 코드 없이 흡수한다(대부분 INGR_NAME인데 병용금기만 INGR_KOR_NAME).
    metadata_columns: dict[str, str] = field(default_factory=dict)
    # 이 파일의 모든 문서에 붙는 이름표(display_name, disease 등).
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return nfc(self.path.name)

    @property
    def collection(self) -> str:
        return collection_for(self.path)


def _is_source_file(p: Path) -> bool:
    # `_`로 시작하는 건 설정이나 파생물(_tuning.yaml 등)이지 원천 데이터가 아니다.
    return p.is_file() and not p.name.startswith((".", "_"))


def load_tuning(path: Path | None = None) -> dict[str, Any]:
    """`_tuning.yaml`을 읽는다. **없으면 빈 설정을 준다 — 에러가 아니다.**
    설정은 기본보다 잘하고 싶을 때만 쓰는 덮어쓰기지 필수 선언이 아니다."""
    path = path or TUNING_PATH
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def discover(source_dir: Path | None = None, tuning: dict[str, Any] | None = None) -> list[Source]:
    """드롭 폴더를 훑어 Source 목록을 만든다. 폴더가 곧 진실이다."""
    source_dir = source_dir or SOURCE_DIR
    tuning = load_tuning() if tuning is None else tuning

    # 컬럼명은 파일끼리 겹치지 않는다(DUR_SEQ는 drugs_data에 없고 itemSeq는 DUR에 없다).
    # 그래서 이 둘은 전역 하나로 14개 파일을 전부 커버한다 — 파일마다 반복할 이유가 없다.
    exclude = frozenset(tuning.get("exclude_columns") or ())
    metadata_columns = dict(tuning.get("metadata_columns") or {})
    labels = {nfc(k): v for k, v in (tuning.get("metadata") or {}).items()}

    return sorted(
        (
            Source(
                path=p,
                exclude_columns=exclude,
                metadata_columns=metadata_columns,
                metadata=dict(labels.get(nfc(p.name)) or {}),
            )
            for p in source_dir.iterdir()
            if _is_source_file(p)
        ),
        key=lambda s: s.name,
    )
