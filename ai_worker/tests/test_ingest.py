"""
T-LLM-2-rag-source-label: `_load_docs_from_csv`가 Chroma 메타데이터 `source`에
원본 CSV 파일명 대신 사람이 읽기 좋은 한글 라벨을 넣는지 검증한다.

T-LLM-7-embedding-guard: 저장된 벡터의 임베딩 모델과 현재 백엔드가 불일치하면 무음
오필터 대신 명시적으로 거부하는지 검증한다.

T-LLM-7-embedding-fail-fast: 로컬 HuggingFace 폴백을 제거하고, API 키가 없으면
조용히 성능이 떨어지는 대신 즉시 실패하는지 검증한다(팀은 .env를 공유하므로 키 부재는
설정 오류로 간주 — 결정 2026-07-13).
"""

import pytest

from ai_worker.tasks import ingest as ingest_module
from ai_worker.tasks.ingest import (
    EmbeddingMismatchError,
    EmbeddingUnavailableError,
    _display_source_label,
    _load_docs_from_csv,
    _read_collection_metadata,
    active_embedding_model,
    assert_embedding_compatible,
    get_embeddings,
    ingest_csv_data,
)


@pytest.mark.parametrize(
    "file_name,expected_label",
    [
        ("dur_pwnm_taboo.csv", "식약처 DUR 임부금기 정보"),
        ("dur_odsn_atent.csv", "식약처 DUR 노인주의 정보"),
        ("dur_mdctn_pd_atent.csv", "식약처 DUR 투여기간주의 정보"),
        ("dur_efcy_dplct.csv", "식약처 DUR 효능군중복 정보"),
    ],
)
def test_display_source_label_maps_known_files_to_korean_label(file_name, expected_label):
    assert _display_source_label(file_name) == expected_label


def test_display_source_label_falls_back_to_raw_file_name_for_unknown_files():
    assert _display_source_label("unknown_future_file.csv") == "unknown_future_file.csv"


def test_load_docs_from_csv_uses_display_label_in_metadata_source(tmp_path):
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    csv_file.write_text(
        "DUR_SEQ,TYPE_NAME,INGR_NAME,INGR_ENG_NAME,PROHBT_CONTENT,GRADE,CLASS_NAME\n"
        "1,임부금기,테스트성분,test_ingr,임부에 대한 안전성 미확립,1등급,테스트분류\n",
        encoding="utf-8",
    )

    docs = _load_docs_from_csv(csv_file)

    assert len(docs) == 1
    assert docs[0].metadata["source"] == "식약처 DUR 임부금기 정보"


def test_active_embedding_model_returns_openai_when_key_present(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", "sk-key")

    assert "text-embedding-3-small" in active_embedding_model()


def test_active_embedding_model_raises_when_no_key(monkeypatch):
    """로컬 HF 폴백 없이, 키가 전혀 없으면 즉시 실패한다(무음 성능저하 대신 fail-fast)."""
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", None)

    with pytest.raises(EmbeddingUnavailableError):
        active_embedding_model()


def test_get_embeddings_raises_when_no_key(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", None)

    with pytest.raises(EmbeddingUnavailableError):
        get_embeddings()


class _FakeCollection:
    def __init__(self, metadata: dict | None) -> None:
        self.metadata = metadata


class _FakeDb:
    def __init__(self, metadata: dict | None) -> None:
        self._collection = _FakeCollection(metadata)


def test_assert_embedding_compatible_raises_on_mismatch(monkeypatch):
    """HF 폴백 제거 이전에 만들어진 레거시 컬렉션(hf:...로 태깅됨)을 지금 다시 열면 거부돼야 한다."""
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", "sk-key")  # 현재는 OpenAI만 존재
    db = _FakeDb({"embedding_model": "hf:sentence-transformers/all-MiniLM-L6-v2"})  # 저장은 레거시 HF

    with pytest.raises(EmbeddingMismatchError):
        assert_embedding_compatible(db)


def test_assert_embedding_compatible_passes_on_match(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", "sk-key")
    db = _FakeDb({"embedding_model": active_embedding_model()})

    assert_embedding_compatible(db)  # 예외 없음


def test_assert_embedding_compatible_skips_when_metadata_absent():
    """임베딩 모델명이 저장되지 않은 기존 컬렉션은 검증할 수 없으므로 통과시킨다(무음 차단 방지)."""
    assert_embedding_compatible(_FakeDb(None))
    assert_embedding_compatible(_FakeDb({}))


class _FakeDbWithPublicGet:
    """langchain-chroma의 공개 API(`get`)만 흉내낸다. `_collection`은 일부러 두지 않는다 —
    프로덕션 코드가 사설 접근을 시도하면 AttributeError로 곧장 드러나야 한다."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self.add_documents_called = False

    def get(self, include: list[str]):
        return {"ids": self._ids}

    def add_documents(self, docs):
        self.add_documents_called = True


def test_read_collection_metadata_returns_stored_metadata():
    """langchain-chroma 1.1.0엔 컬렉션 메타데이터 공개 접근자가 없어, 사설 `_collection`
    접근이 이 헬퍼 한 곳에만 격리돼 있는지 검증한다."""
    db = _FakeDb({"embedding_model": "openai:text-embedding-3-small"})

    assert _read_collection_metadata(db) == {"embedding_model": "openai:text-embedding-3-small"}


def test_read_collection_metadata_returns_empty_dict_when_absent():
    assert _read_collection_metadata(_FakeDb(None)) == {}
    assert _read_collection_metadata(_FakeDbWithPublicGet(ids=[])) == {}


def test_ingest_csv_data_skips_when_documents_already_exist(monkeypatch):
    """이미 적재된 컬렉션은 공개 get()으로 개수를 확인해 재인제스트를 건너뛴다."""
    fake_db = _FakeDbWithPublicGet(ids=["1", "2", "3"])
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    result = ingest_csv_data()

    assert result is fake_db
    assert fake_db.add_documents_called is False
