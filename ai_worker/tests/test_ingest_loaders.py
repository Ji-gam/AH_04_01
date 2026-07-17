"""로더 회귀 테스트: 확장자 -> Document.

핵심은 두 가지다.
  1) **블랙리스트**여야 한다. 예전 화이트리스트는 7개 DUR 파일 전부에서 FORM_NAME(제형명)과
     REMARK(비고)를 소리 없이 버리고 있었다.
  2) 검색 층이 쓰는 메타데이터 키(`ingr_name`)가 붙어야 한다. 없으면 DUR 검색이 통째로
     0건이 된다(search_documents가 항상 그 키로 필터하므로).
"""

import json
from pathlib import Path

import pytest

from ai_worker.ingest.loaders import CsvLoader, JsonLoader, MarkdownLoader, build_loader
from ai_worker.ingest.sources import Source


def _source(tmp_path: Path, name: str, body: str, **kwargs) -> Source:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return Source(path=path, **kwargs)


def test_csv_puts_every_column_in_content_by_default(tmp_path):
    """기본은 전 컬럼이다. 예전 화이트리스트가 FORM_NAME/REMARK를 버리던 사고의 재발 방지."""
    source = _source(tmp_path, "a.csv", "INGR_NAME,FORM_NAME,REMARK\n와파린,정제,경구\n")

    doc = next(CsvLoader(source).lazy_load())

    assert "INGR_NAME: 와파린" in doc.page_content
    assert "FORM_NAME: 정제" in doc.page_content
    assert "REMARK: 경구" in doc.page_content


def test_csv_drops_only_excluded_columns(tmp_path):
    source = _source(
        tmp_path,
        "a.csv",
        "DUR_SEQ,INGR_NAME,PROHBT_CONTENT\n123,와파린,병용금기\n",
        exclude_columns=frozenset({"DUR_SEQ"}),
    )

    doc = next(CsvLoader(source).lazy_load())

    assert "DUR_SEQ" not in doc.page_content
    assert "INGR_NAME: 와파린" in doc.page_content
    assert "PROHBT_CONTENT: 병용금기" in doc.page_content


def test_csv_skips_empty_values(tmp_path):
    """빈 값은 검색에 기여하지 않고 노이즈만 된다."""
    source = _source(tmp_path, "a.csv", "INGR_NAME,REMARK\n와파린,\n")

    doc = next(CsvLoader(source).lazy_load())

    assert "REMARK" not in doc.page_content


def test_csv_skips_rows_whose_content_is_entirely_empty(tmp_path):
    """본문이 통째로 비면 임베딩할 게 없다. index()가 콘텐츠 해시로 중복을 잡으므로 빈
    문서를 넣으면 서로 같은 문서로 뭉친다."""
    source = _source(tmp_path, "a.csv", "INGR_NAME,REMARK\n와파린,경구\n,\n")

    assert len(list(CsvLoader(source).lazy_load())) == 1


def test_csv_renames_columns_into_metadata_keys_the_search_layer_expects(tmp_path):
    """대부분 INGR_NAME인데 병용금기만 INGR_KOR_NAME이다. 전역 설정에 둘 다 두면 파일에
    있는 쪽만 붙는다 — 그 차이를 코드가 아니라 설정이 흡수한다."""
    tuning = {"INGR_NAME": "ingr_name", "INGR_KOR_NAME": "ingr_name"}
    usual = _source(tmp_path, "a.csv", "INGR_NAME,X\n와파린,1\n", metadata_columns=tuning)
    combo = _source(tmp_path, "b.csv", "INGR_KOR_NAME,X\n아스피린,1\n", metadata_columns=tuning)

    assert next(CsvLoader(usual).lazy_load()).metadata["ingr_name"] == "와파린"
    assert next(CsvLoader(combo).lazy_load()).metadata["ingr_name"] == "아스피린"


def test_loaders_stamp_source_and_collection_and_labels(tmp_path):
    """`source`는 index()의 source_id_key다 — cleanup이 이 키로 파일별 문서를 묶는다."""
    source = _source(tmp_path, "a.csv", "X\n1\n", metadata={"display_name": "임부금기의약품"})

    doc = next(CsvLoader(source).lazy_load())

    assert doc.metadata["source"] == "a.csv"
    assert doc.metadata["collection"] == "structured"
    assert doc.metadata["display_name"] == "임부금기의약품"


def test_json_makes_one_document_per_element(tmp_path):
    """초록을 고정 크기로 자르지 않는다 — 740편 중 729편이 쪼개져 제목 없는 조각이
    컬렉션의 70%가 됐고, 그게 "고혈압 질문에 당뇨 논문"의 원인이었다."""
    body = json.dumps([{"title": "A", "abstract": "a"}, {"title": "B", "abstract": "b"}])
    source = _source(tmp_path, "p.json", body)

    docs = list(JsonLoader(source).lazy_load())

    assert len(docs) == 2
    assert "title: A" in docs[0].page_content


def test_json_keeps_korean_summary_ahead_of_the_english_abstract(tmp_path):
    """질의는 한국어인데 초록은 영어다. 요약이 뒤에 있으면 긴 초록에 밀려 잘릴 수 있다."""
    body = json.dumps([{"summary_ko": "한국어 요약", "title": "T", "abstract": "long english"}])
    source = _source(tmp_path, "p.json", body)

    assert next(JsonLoader(source).lazy_load()).page_content.startswith("summary_ko: 한국어 요약")


def test_json_rejects_non_array_top_level(tmp_path):
    source = _source(tmp_path, "p.json", json.dumps({"not": "an array"}))

    with pytest.raises(ValueError, match="JSON 배열이 아닙니다"):
        list(JsonLoader(source).lazy_load())


def test_markdown_splits_on_headings_and_keeps_them_as_metadata(tmp_path):
    """헤더가 곧 금이다. 조각이 어느 절에서 왔는지 메타데이터로 남는다."""
    source = _source(tmp_path, "d.md", "# 안내서\n\n앞말\n\n## 기관지 확장제\n\n본문입니다\n")

    docs = list(MarkdownLoader(source).lazy_load())

    assert any(d.metadata.get("subsection") == "기관지 확장제" for d in docs)
    assert all(d.metadata["source"] == "d.md" for d in docs)


def test_build_loader_routes_by_extension(tmp_path):
    """매니페스트에 `loader: csv`를 적게 하지 않는다 — 파일이 이미 아는 걸 또 묻는 셈이다."""
    assert isinstance(build_loader(_source(tmp_path, "a.csv", "X\n1\n")), CsvLoader)
    assert isinstance(build_loader(_source(tmp_path, "a.json", "[]")), JsonLoader)
    assert isinstance(build_loader(_source(tmp_path, "a.md", "# t")), MarkdownLoader)


def test_build_loader_rejects_unknown_extension(tmp_path):
    with pytest.raises(ValueError, match="지원하지 않는 확장자"):
        build_loader(_source(tmp_path, "a.xyz", "junk"))
