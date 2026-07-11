"""
T-LLM-2-rag-source-label: `_load_docs_from_csv`가 Chroma 메타데이터 `source`에
원본 CSV 파일명 대신 사람이 읽기 좋은 한글 라벨을 넣는지 검증한다.

T-LLM-7-embedding-guard: 런타임에 교체되는 임베딩 백엔드(OpenAI 1536차원 ↔ HF 384차원)와
저장된 벡터의 임베딩 모델이 불일치하면 무음 오필터 대신 명시적으로 거부하는지 검증한다.
"""

import pytest

from ai_worker.tasks import ingest as ingest_module
from ai_worker.tasks.ingest import (
    EmbeddingMismatchError,
    _display_source_label,
    _load_docs_from_csv,
    active_embedding_model,
    assert_embedding_compatible,
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


def test_active_embedding_model_switches_with_api_key(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", "sk-key")
    assert "text-embedding-3-small" in active_embedding_model()

    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", None)
    assert "MiniLM" in active_embedding_model()


class _FakeCollection:
    def __init__(self, metadata: dict | None) -> None:
        self.metadata = metadata


class _FakeDb:
    def __init__(self, metadata: dict | None) -> None:
        self._collection = _FakeCollection(metadata)


def test_assert_embedding_compatible_raises_on_mismatch(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", None)  # 현재 HF
    db = _FakeDb({"embedding_model": "openai:text-embedding-3-small"})  # 저장은 OpenAI

    with pytest.raises(EmbeddingMismatchError):
        assert_embedding_compatible(db)


def test_assert_embedding_compatible_passes_on_match(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", None)
    db = _FakeDb({"embedding_model": active_embedding_model()})

    assert_embedding_compatible(db)  # 예외 없음


def test_assert_embedding_compatible_skips_when_metadata_absent():
    """임베딩 모델명이 저장되지 않은 기존 컬렉션은 검증할 수 없으므로 통과시킨다(무음 차단 방지)."""
    assert_embedding_compatible(_FakeDb(None))
    assert_embedding_compatible(_FakeDb({}))
