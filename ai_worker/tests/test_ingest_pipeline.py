"""파이프라인이 '순환'하는지 — 이 재설계의 존재 이유.

예전 파이프라인은 `_needs_reingest()`가 문서 **개수**만 비교해서, 행 수가 그대로면
내용을 아무리 고쳐도 반영되지 않았다(원래 docstring도 그 한계를 자인했다). 그래서 오픈할
때 넣은 데이터로 계속 살아야 했다. 여기서 지키는 계약:

  1. 안 바뀌면 재임베딩하지 않는다      (비용)
  2. **내용이 바뀌면 반영된다**          (예전에 안 되던 것)
  3. 원천에서 사라지면 컬렉션에서도 지운다 (예전에 없던 것)

실제 임베딩/Chroma 대신 LangChain이 제공하는 테스트 더블(`InMemoryVectorStore` +
`DeterministicFakeEmbedding`)을 쓴다 — 우리가 fake를 발명하지 않는다. RecordManager는
실물(SQLite)을 그대로 쓴다. 검증 대상이 바로 그 판단이기 때문이다.
"""

from langchain_core.embeddings.fake import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

from ai_worker.ingest import pipeline as pipeline_module
from ai_worker.ingest.manifest import SourceSpec


def _setup(monkeypatch, tmp_path, rows: str):
    """source/ 파일 하나짜리 임시 환경."""
    import ai_worker.ingest.manifest as manifest_module

    monkeypatch.setattr(manifest_module, "SOURCE_DIR", tmp_path)
    (tmp_path / "a.csv").write_text(rows, encoding="utf-8")

    store = InMemoryVectorStore(DeterministicFakeEmbedding(size=8))
    monkeypatch.setattr(pipeline_module, "build_vector_store", lambda collection: store)
    monkeypatch.setattr(pipeline_module, "CHROMA_DIR", tmp_path)
    monkeypatch.setattr(pipeline_module, "RECORD_DB_PATH", tmp_path / "rm.sqlite")

    spec = SourceSpec(
        file="a.csv", rag=True, loader="csv", collection="dur_rules", content_columns=("INGR_NAME", "PROHBT_CONTENT")
    )
    return spec, store


def test_unchanged_source_is_not_reembedded(tmp_path, monkeypatch):
    spec, _ = _setup(monkeypatch, tmp_path, "INGR_NAME,PROHBT_CONTENT\n와파린,병용금기\n")

    first = pipeline_module.ingest_source(spec)
    second = pipeline_module.ingest_source(spec)

    assert first["num_added"] == 1
    assert second["num_added"] == 0
    assert second["num_skipped"] == 1  # 콘텐츠 해시가 같아 재임베딩하지 않는다


def test_changed_content_is_reindexed(tmp_path, monkeypatch):
    """예전 `_needs_reingest()`가 못 잡던 바로 그 경우 — 행 수는 그대로, 내용만 바뀜."""
    spec, store = _setup(monkeypatch, tmp_path, "INGR_NAME,PROHBT_CONTENT\n와파린,병용금기\n")
    pipeline_module.ingest_source(spec)

    (tmp_path / "a.csv").write_text("INGR_NAME,PROHBT_CONTENT\n와파린,병용금기 (2026 개정)\n", encoding="utf-8")
    result = pipeline_module.ingest_source(spec)

    assert result["num_added"] == 1
    assert result["num_deleted"] == 1  # 옛 버전은 지워진다
    stored = list(store.store.values())
    assert len(stored) == 1
    assert "2026 개정" in stored[0]["text"]


def test_row_removed_from_source_is_deleted_from_collection(tmp_path, monkeypatch):
    """원천에서 사라진 행이 컬렉션에 유령으로 남으면 안 된다 — 예전엔 정리 로직이 없었다."""
    spec, store = _setup(monkeypatch, tmp_path, "INGR_NAME,PROHBT_CONTENT\n와파린,병용금기\n아스피린,노인주의\n")
    pipeline_module.ingest_source(spec)
    assert len(store.store) == 2

    (tmp_path / "a.csv").write_text("INGR_NAME,PROHBT_CONTENT\n와파린,병용금기\n", encoding="utf-8")
    result = pipeline_module.ingest_source(spec)

    assert result["num_deleted"] == 1
    assert len(store.store) == 1


def test_force_reembeds_unchanged_content(tmp_path, monkeypatch):
    """임베딩 모델을 바꾸면 내용이 같아도 벡터를 다시 만들어야 한다."""
    spec, _ = _setup(monkeypatch, tmp_path, "INGR_NAME,PROHBT_CONTENT\n와파린,병용금기\n")
    pipeline_module.ingest_source(spec)

    result = pipeline_module.ingest_source(spec, force=True)

    assert result["num_skipped"] == 0
    assert result["num_updated"] == 1
