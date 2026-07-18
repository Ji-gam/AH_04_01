"""파이프라인 회귀 테스트.

여기서 지키는 건 "조용히 데이터를 잃지 않는다"이다. 이 시스템이 실제로 당한 사고들:
  - 부팅마다 전체 동기화가 돌면서 cleanup="full"이 안 보이는 파일의 문서를 지웠다.
  - 로더가 0건을 내도 "처리했다"고 보고했다(한국어를 못 읽는 OCR로 44페이지가 통째로 0건).
  - 소스 하나가 실패해도 나머지를 cleanup="full"로 밀어, 못 읽은 파일의 멀쩡한 문서를
    "원천에서 사라졌다"고 오해해 날렸다.
"""

import pytest

from ai_worker.ingest import pipeline as pipeline_module
from ai_worker.ingest.pipeline import IngestError, _load_docs
from ai_worker.ingest.sources import Source


def _drop(tmp_path, name, body="INGR_NAME,PROHBT_CONTENT\n와파린,병용금기\n"):
    (tmp_path / name).write_text(body, encoding="utf-8")
    return Source(path=tmp_path / name)


def test_scan_reports_what_would_be_indexed(tmp_path, monkeypatch):
    """폴더가 곧 진실이라 `unregistered`/`missing`/`excluded`가 없다 — 전부 폴더와 별개의
    "선언"이 있어서 생기던 어긋남이었다. 남는 건 "읽을 줄 모르는 확장자"뿐이다."""
    monkeypatch.setattr(pipeline_module, "discover", lambda: [_drop(tmp_path, "a.csv"), _drop(tmp_path, "b.xyz", "?")])

    assert pipeline_module.scan() == {"indexed": ["a.csv"], "unsupported": ["b.xyz"]}


def test_load_docs_treats_zero_documents_as_a_failure(tmp_path):
    """0건은 성공이 아니라 고장이다. 조용히 넘어가면 "처리했다"고 보고하면서 컬렉션은 빈다."""
    source = _drop(tmp_path, "empty.csv", "INGR_NAME\n")  # 헤더만, 행 없음

    with pytest.raises(IngestError, match="문서를 하나도 만들지 못했습니다"):
        _load_docs(source)


def test_ingest_all_skips_unsupported_extensions_instead_of_blocking_everything(tmp_path, monkeypatch):
    """엉뚱한 파일 하나가 컬렉션 전체 동기화를 막으면 안 된다."""
    indexed: dict = {}
    monkeypatch.setattr(pipeline_module, "discover", lambda: [_drop(tmp_path, "a.csv"), _drop(tmp_path, "b.xyz", "?")])
    monkeypatch.setattr(
        pipeline_module, "_index", lambda c, docs, cleanup, force: indexed.update(collection=c, n=len(docs)) or {}
    )

    results = pipeline_module.ingest_all()

    assert indexed == {"collection": "structured", "n": 1}
    assert results[0]["files"] == {"a.csv": 1}


def test_ingest_all_preserves_existing_documents_when_a_source_fails(tmp_path, monkeypatch):
    """이게 이 파일에서 제일 중요한 테스트다.

    cleanup="full"은 이번 배치에 없는 문서를 전부 지운다. 소스 하나가 깨졌을 뿐인데 그대로
    밀면, 못 읽은 파일의 멀쩡한 문서가 "원천에서 사라졌다"고 오해받아 삭제된다. 로더가
    잠깐 깨진 것과 사람이 파일을 뺀 것은 다른 사건이다."""
    called: list = []
    monkeypatch.setattr(
        pipeline_module,
        "discover",
        lambda: [_drop(tmp_path, "ok.csv"), _drop(tmp_path, "broken.csv", "INGR_NAME\n")],  # 행 0개
    )
    monkeypatch.setattr(pipeline_module, "_index", lambda *a, **k: called.append(a) or {})

    results = pipeline_module.ingest_all()

    assert called == []  # 색인 자체를 안 돌렸다 = 기존 문서 보존
    assert "broken.csv" in results[0]["errors"][0]
    assert results[0]["files"] == {"ok.csv": 1}  # 뭐가 읽혔는지는 보고한다


def test_ingest_all_groups_sources_by_collection(tmp_path, monkeypatch):
    """컬렉션 단위로 묶어 한 번에 넣어야 cleanup="full"이 올바른 범위를 본다.
    ingest_source()를 파일마다 반복하면 폴더에서 사라진 파일의 문서가 영원히 남는다."""
    seen: list[tuple[str, int]] = []
    monkeypatch.setattr(
        pipeline_module,
        "discover",
        lambda: [_drop(tmp_path, "a.csv"), _drop(tmp_path, "b.csv"), _drop(tmp_path, "p.json", '[{"t": "x"}]')],
    )
    monkeypatch.setattr(pipeline_module, "_index", lambda c, docs, *a: seen.append((c, len(docs))) or {})

    pipeline_module.ingest_all()

    assert sorted(seen) == [("structured", 2), ("unstructured", 1)]


def test_ingest_all_uses_full_cleanup_and_ingest_source_uses_scoped(tmp_path, monkeypatch):
    """섞으면 조용히 망가진다. "incremental"은 한 소스가 여러 배치에 걸치면 뒤 배치가 앞
    배치를 지운다(실측: 112건 파일이 매번 added 12 / deleted 12)."""
    modes: list[str] = []
    monkeypatch.setattr(pipeline_module, "discover", lambda: [_drop(tmp_path, "a.csv")])
    monkeypatch.setattr(pipeline_module, "_index", lambda c, docs, cleanup, force: modes.append(cleanup) or {})

    pipeline_module.ingest_all()
    pipeline_module.ingest_source(_drop(tmp_path, "a.csv"))

    assert modes == ["full", "scoped_full"]
