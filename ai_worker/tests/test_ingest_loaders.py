"""로더가 매니페스트 선언만으로 Document를 만드는지.

예전엔 파일 하나당 전용 함수 하나(`_pwnm_content` 등 7개)가 문장을 조립했다. 여기서
지키려는 계약은 **CSV가 몇 개가 되든 로더는 하나**이고, 파일별 차이는 전부 spec에서
온다는 것이다.
"""

import json

from ai_worker.ingest.loaders import CsvRecordLoader, JsonRecordLoader, build_loader
from ai_worker.ingest.manifest import SourceSpec


def test_csv_loader_renders_only_declared_content_columns(tmp_path, monkeypatch):
    import ai_worker.ingest.manifest as manifest_module

    monkeypatch.setattr(manifest_module, "SOURCE_DIR", tmp_path)
    (tmp_path / "a.csv").write_text(
        "INGR_NAME,PROHBT_CONTENT,NOISE\n프로게스테론,안전성 미확립,버릴값\n", encoding="utf-8"
    )
    spec = SourceSpec(
        file="a.csv",
        rag=True,
        loader="csv",
        collection="dur_rules",
        content_columns=("INGR_NAME", "PROHBT_CONTENT"),
        metadata_columns={"INGR_NAME": "ingr_name"},
        metadata={"display_name": "임부금기의약품"},
    )

    (doc,) = list(CsvRecordLoader(spec).lazy_load())

    # 선언 안 한 컬럼은 본문에 안 들어간다 — 이 선택이 코드가 아니라 매니페스트에 있다.
    assert doc.page_content == "INGR_NAME: 프로게스테론\nPROHBT_CONTENT: 안전성 미확립"
    assert "버릴값" not in doc.page_content
    # source는 index()의 source_id_key라 cleanup 범위를 정한다.
    assert doc.metadata["source"] == "a.csv"
    assert doc.metadata["ingr_name"] == "프로게스테론"
    assert doc.metadata["display_name"] == "임부금기의약품"


def test_csv_loader_renames_column_to_metadata_key(tmp_path, monkeypatch):
    """병용금기 파일만 성분 컬럼이 INGR_KOR_NAME이다. 검색 층은 ingr_name으로 필터하므로
    그 차이를 매니페스트가 흡수해야 한다(코드 분기가 아니라)."""
    import ai_worker.ingest.manifest as manifest_module

    monkeypatch.setattr(manifest_module, "SOURCE_DIR", tmp_path)
    (tmp_path / "u.csv").write_text("INGR_KOR_NAME,PROHBT_CONTENT\n와파린,병용금기\n", encoding="utf-8")
    spec = SourceSpec(
        file="u.csv",
        rag=True,
        loader="csv",
        collection="dur_rules",
        content_columns=("INGR_KOR_NAME",),
        metadata_columns={"INGR_KOR_NAME": "ingr_name"},
    )

    (doc,) = list(CsvRecordLoader(spec).lazy_load())

    assert doc.metadata["ingr_name"] == "와파린"


def test_csv_loader_skips_rows_with_empty_content(tmp_path, monkeypatch):
    """본문이 비면 임베딩할 게 없다. index()가 콘텐츠 해시로 키를 만들므로 빈 문서를
    넣으면 서로 같은 문서로 뭉쳐 조용히 사라진다."""
    import ai_worker.ingest.manifest as manifest_module

    monkeypatch.setattr(manifest_module, "SOURCE_DIR", tmp_path)
    (tmp_path / "a.csv").write_text("INGR_NAME,X\n,버림\n프로게스테론,값\n", encoding="utf-8")
    spec = SourceSpec(file="a.csv", rag=True, loader="csv", collection="c", content_columns=("INGR_NAME",))

    docs = list(CsvRecordLoader(spec).lazy_load())

    assert len(docs) == 1
    assert docs[0].page_content == "INGR_NAME: 프로게스테론"


def test_json_loader_reads_array_records(tmp_path, monkeypatch):
    import ai_worker.ingest.manifest as manifest_module

    monkeypatch.setattr(manifest_module, "SOURCE_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text(
        json.dumps([{"pmid": "1", "title": "T", "abstract": "A"}], ensure_ascii=False), encoding="utf-8"
    )
    spec = SourceSpec(
        file="당뇨.json",
        rag=True,
        loader="json",
        collection="pubmed_papers",
        content_columns=("title", "abstract"),
        metadata_columns={"pmid": "pmid"},
        metadata={"disease": "당뇨"},
    )

    (doc,) = list(JsonRecordLoader(spec).lazy_load())

    assert doc.page_content == "title: T\nabstract: A"
    assert doc.metadata["pmid"] == "1"
    assert doc.metadata["disease"] == "당뇨"


def test_build_loader_rejects_unknown_loader_name():
    spec = SourceSpec(file="a.xyz", rag=True, loader="없는로더", collection="c")

    try:
        build_loader(spec)
    except ValueError as e:
        assert "없는로더" in str(e)
    else:
        raise AssertionError("알 수 없는 로더는 즉시 실패해야 한다")
