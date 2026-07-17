"""드롭 폴더 스캔 회귀 테스트.

여기서 지키려는 건 하나다: **폴더가 곧 진실이고, 설정은 선택적이다.** 예전엔 매니페스트에
등록해야만 색인됐고(파일을 넣어도 아무 일이 없었다), 그 매니페스트가 사실상 DB가 되면서
파일명·로더·컬렉션이 전부 두 벌씩 존재하게 됐다.
"""

import unicodedata
from pathlib import Path

import pytest

from ai_worker.ingest.sources import STRUCTURED, UNSTRUCTURED, collection_for, discover, nfc


def _drop(dir_path: Path, name: str, body: str = "a,b\n1,2\n") -> Path:
    path = dir_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_discover_picks_up_every_file_in_the_folder(tmp_path):
    """등록 절차가 없다는 것. 넣으면 들어간다."""
    _drop(tmp_path, "a.csv")
    _drop(tmp_path, "b.json", "[]")

    assert [s.name for s in discover(tmp_path, tuning={})] == ["a.csv", "b.json"]


def test_discover_works_without_any_tuning(tmp_path):
    """설정 파일이 없어도 돈다. 설정은 기본보다 잘하고 싶을 때 쓰는 덮어쓰기지 필수가 아니다."""
    _drop(tmp_path, "a.csv")

    source = discover(tmp_path, tuning={})[0]

    assert source.exclude_columns == frozenset()
    assert source.metadata_columns == {}
    assert source.metadata == {}


def test_discover_ignores_underscore_and_dot_prefixed_entries(tmp_path):
    """`_`로 시작하는 건 설정이나 파생물이지 원천 데이터가 아니다. `_not_rag/`도 이 규칙으로 빠진다."""
    _drop(tmp_path, "real.csv")
    _drop(tmp_path, "_tuning.yaml", "sources: []")
    _drop(tmp_path, ".DS_Store", "junk")
    (tmp_path / "_not_rag").mkdir()
    _drop(tmp_path / "_not_rag", "sql_table.csv")

    assert [s.name for s in discover(tmp_path, tuning={})] == ["real.csv"]


def test_tuning_applies_globally_not_per_file(tmp_path):
    """컬럼명이 파일끼리 겹치지 않으므로 전역 목록 하나로 모든 파일을 커버한다 —
    파일마다 같은 블랙리스트를 반복하지 않는다."""
    _drop(tmp_path, "a.csv")
    _drop(tmp_path, "b.csv")
    tuning = {"exclude_columns": ["DUR_SEQ"], "metadata_columns": {"INGR_NAME": "ingr_name"}}

    sources = discover(tmp_path, tuning=tuning)

    assert all(s.exclude_columns == frozenset({"DUR_SEQ"}) for s in sources)
    assert all(s.metadata_columns == {"INGR_NAME": "ingr_name"} for s in sources)


def test_file_labels_attach_only_to_their_own_file(tmp_path):
    _drop(tmp_path, "a.csv")
    _drop(tmp_path, "b.csv")
    tuning = {"metadata": {"a.csv": {"display_name": "가"}}}

    sources = {s.name: s for s in discover(tmp_path, tuning=tuning)}

    assert sources["a.csv"].metadata == {"display_name": "가"}
    assert sources["b.csv"].metadata == {}


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("a.csv", STRUCTURED),
        ("A.CSV", STRUCTURED),
        ("a.json", UNSTRUCTURED),
        ("a.md", UNSTRUCTURED),
        ("a.pdf", UNSTRUCTURED),
    ],
)
def test_collection_is_decided_by_extension(filename, expected):
    """컬렉션 이름을 사람이 선언하지 않는다. 예전엔 이 문자열이 매니페스트 + 파이썬 4곳에
    흩어져 있었고, 세 파일에 "매니페스트와 일치해야 한다"는 주석이 붙어 있었다."""
    assert collection_for(Path(filename)) == expected


def test_label_lookup_survives_macos_filename_normalization(tmp_path):
    """Finder로 이름을 바꾼 한글 파일은 NFD로 저장된다. 설정에 적힌 NFC 문자열과 바이트가
    달라(52자 vs 24자) 이름표가 안 붙는 사고가 실제로 났다."""
    nfd_name = unicodedata.normalize("NFD", "약과음식.csv")
    _drop(tmp_path, nfd_name)
    tuning = {"metadata": {"약과음식.csv": {"display_name": "복약안내서"}}}  # NFC로 적힌 설정

    source = discover(tmp_path, tuning=tuning)[0]

    assert source.name == "약과음식.csv"  # 정규화돼서 나온다
    assert source.metadata == {"display_name": "복약안내서"}


def test_nfc_makes_visually_identical_names_compare_equal():
    assert nfc(unicodedata.normalize("NFD", "간질환.json")) == "간질환.json"
