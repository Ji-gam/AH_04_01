"""매니페스트 로드/검증과 source/ 대조 스캔.

이 파일이 지키는 계약: **새 파일 추가는 YAML만 고치면 된다.** 파이썬을 고쳐야 하는
상황이 생기면 설계가 무너진 것이다.
"""

import pytest
import yaml

from ai_worker.ingest.manifest import ManifestError, load_manifest, scan_source_dir


def _write(tmp_path, data):
    path = tmp_path / "_manifest.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_load_parses_rag_source(tmp_path):
    path = _write(
        tmp_path,
        {
            "sources": [
                {
                    "file": "a.csv",
                    "loader": "csv",
                    "collection": "dur_rules",
                    "content_columns": ["INGR_NAME", "PROHBT_CONTENT"],
                    "metadata_columns": {"INGR_NAME": "ingr_name"},
                    "metadata": {"display_name": "임부금기의약품"},
                }
            ]
        },
    )

    (spec,) = load_manifest(path)

    assert spec.file == "a.csv"
    assert spec.rag is True
    assert spec.content_columns == ("INGR_NAME", "PROHBT_CONTENT")
    assert spec.metadata_columns == {"INGR_NAME": "ingr_name"}
    assert spec.metadata == {"display_name": "임부금기의약품"}


def test_load_parses_excluded_source_without_requiring_loader(tmp_path):
    """rag=false는 '봤고 일부러 뺐다'는 선언이라 loader/collection이 필요 없다."""
    path = _write(tmp_path, {"sources": [{"file": "big.csv", "rag": False, "reason": "구조화 조회 데이터"}]})

    (spec,) = load_manifest(path)

    assert spec.rag is False
    assert spec.reason == "구조화 조회 데이터"


def test_load_rejects_rag_source_missing_collection(tmp_path):
    """조용히 넘어가면 데이터가 소리 없이 누락된다 — 설정 오류로 즉시 실패해야 한다."""
    path = _write(tmp_path, {"sources": [{"file": "a.csv", "loader": "csv"}]})

    with pytest.raises(ManifestError, match="collection"):
        load_manifest(path)


def test_load_rejects_duplicate_files(tmp_path):
    path = _write(
        tmp_path,
        {
            "sources": [
                {"file": "a.csv", "loader": "csv", "collection": "c"},
                {"file": "a.csv", "loader": "csv", "collection": "c"},
            ]
        },
    )

    with pytest.raises(ManifestError, match="중복"):
        load_manifest(path)


def test_load_rejects_missing_manifest(tmp_path):
    with pytest.raises(ManifestError, match="매니페스트가 없습니다"):
        load_manifest(tmp_path / "없음.yaml")


def test_scan_surfaces_unregistered_files(tmp_path):
    """드롭 폴더의 핵심: 등록 안 된 파일이 **조용히 무시되지 않고** 드러나야 한다.
    예전 파이프라인은 레지스트리에 없는 파일을 아무 말 없이 건너뛰었다."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for name in ("registered.csv", "excluded.csv", "그냥던져넣은거.csv"):
        (source_dir / name).write_text("x", encoding="utf-8")
    # 언더스코어로 시작하는 건 매니페스트 자신이나 파생 캐시라 원천 데이터가 아니다.
    (source_dir / "_manifest.yaml").write_text("x", encoding="utf-8")

    specs = load_manifest(
        _write(
            tmp_path,
            {
                "sources": [
                    {"file": "registered.csv", "loader": "csv", "collection": "c"},
                    {"file": "excluded.csv", "rag": False, "reason": "표 데이터"},
                    {"file": "지워진파일.csv", "loader": "csv", "collection": "c"},
                ]
            },
        )
    )

    scan = scan_source_dir(specs, source_dir=source_dir)

    assert scan["indexed"] == ["registered.csv"]
    assert scan["excluded"] == ["excluded.csv"]
    assert scan["unregistered"] == ["그냥던져넣은거.csv"]
    assert scan["missing"] == ["지워진파일.csv"]  # 매니페스트엔 있는데 폴더에 없음
