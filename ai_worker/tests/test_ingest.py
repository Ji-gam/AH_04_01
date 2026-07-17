"""
T-RAG-SOURCE-MIGRATION: `source/`의 RAG 대상 CSV를 명시적 레지스트리(`_DUR_RAG_REGISTRY`)로만
처리하는지, 파일 단위 upsert(재업로드=자동 갱신, 컬렉션 전체 스킵 버그 없음)가 되는지 검증한다.

T-LLM-7-embedding-guard: 저장된 벡터의 임베딩 모델과 현재 백엔드가 불일치하면 무음
오필터 대신 명시적으로 거부하는지 검증한다.

T-LLM-7-embedding-fail-fast: 로컬 HuggingFace 폴백을 제거하고, API 키가 없으면
조용히 성능이 떨어지는 대신 즉시 실패하는지 검증한다(팀은 .env를 공유하므로 키 부재는
설정 오류로 간주 — 결정 2026-07-13).
"""

import numpy as np
import pytest

from ai_worker.tasks import ingest as ingest_module
from ai_worker.tasks.ingest import (
    _DUR_RAG_REGISTRY,
    EmbeddingMismatchError,
    EmbeddingUnavailableError,
    _load_docs_from_csv,
    _read_collection_metadata,
    active_embedding_model,
    assert_embedding_compatible,
    get_embeddings,
    ingest_csv_data,
    ingest_single_csv_file,
    reset_dur_collection,
)

_PWNM_HEADER = "DUR_SEQ,TYPE_NAME,INGR_NAME,INGR_ENG_NAME,PROHBT_CONTENT,GRADE,CLASS_NAME\n"
_PWNM_ROW = "{seq},임부금기,테스트성분,test_ingr,임부에 대한 안전성 미확립,1등급,테스트분류\n"


def _write_pwnm_csv(path, rows: list[str]) -> None:
    path.write_text(_PWNM_HEADER + "".join(rows), encoding="utf-8")


def test_load_docs_from_csv_assigns_deterministic_id_from_id_fields(tmp_path):
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    _write_pwnm_csv(csv_file, [_PWNM_ROW.format(seq=1)])
    spec = _DUR_RAG_REGISTRY["dur_pwnm_taboo.csv"]

    docs, warnings = _load_docs_from_csv(csv_file, spec)

    assert len(docs) == 1
    assert docs[0].id == "dur_pwnm_taboo.csv:1"
    assert docs[0].metadata["display_name"] == "임부금기의약품"
    assert docs[0].metadata["publisher"] == "식약처"
    assert docs[0].metadata["source_id"] == "dur_pwnm_taboo.csv"
    assert warnings == []


def test_load_docs_from_csv_falls_back_to_row_index_when_id_field_missing(tmp_path):
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    # DUR_SEQ를 비워서 id 필드 누락 케이스를 만든다.
    _write_pwnm_csv(csv_file, [_PWNM_ROW.format(seq="")])
    spec = _DUR_RAG_REGISTRY["dur_pwnm_taboo.csv"]

    docs, warnings = _load_docs_from_csv(csv_file, spec)

    assert len(docs) == 1
    assert docs[0].id == "dur_pwnm_taboo.csv:row0"
    assert len(warnings) == 1
    assert "id 필드" in warnings[0]


_USJNT_HEADER = (
    "INGR_CODE,INGR_ENG_NAME,INGR_KOR_NAME,MIX_TYPE,MIX,CLASS,"
    "MIXTURE_INGR_CODE,MIXTURE_INGR_ENG_NAME,MIXTURE_INGR_KOR_NAME,MIXTURE_MIX_TYPE,"
    "MIXTURE_MIX,MIXTURE_CLASS,NOTIFICATION_DATE,PROHBT_CONTENT,DEL_YN,TYPE_NAME\n"
)


def _usjnt_row(mix: str = "") -> str:
    return f"A001,ingr_a,성분A,단일,{mix},class_a,B002,ingr_b,성분B,단일,,class_b,20200101,병용 시 위험,정상,병용금기\n"


def test_load_docs_from_csv_usjnt_taboo_uses_composite_id(tmp_path):
    csv_file = tmp_path / "dur_usjnt_taboo.csv"
    csv_file.write_text(_USJNT_HEADER + _usjnt_row(), encoding="utf-8")
    spec = _DUR_RAG_REGISTRY["dur_usjnt_taboo.csv"]

    docs, warnings = _load_docs_from_csv(csv_file, spec)

    assert len(docs) == 1
    expected_values = ["A001", "B002", "단일", "단일", "20200101", "", "", "class_a", "class_b", "정상", "병용 시 위험"]
    assert docs[0].id == "dur_usjnt_taboo.csv:" + "-".join(expected_values)
    assert "성분A" in docs[0].page_content and "성분B" in docs[0].page_content
    assert warnings == []


def test_load_docs_from_csv_usjnt_taboo_same_ingredient_pair_different_mix_gets_distinct_ids(tmp_path):
    """실측된 실제 문제: 같은 성분 조합(INGR_CODE+MIXTURE_INGR_CODE)이 여러 복합제(MIX)로
    반복 등장한다 — MIX가 id에 포함되어 있어야 서로 다른 id로 구분된다."""
    csv_file = tmp_path / "dur_usjnt_taboo.csv"
    csv_file.write_text(
        _USJNT_HEADER + _usjnt_row(mix="[D000690]Glibenclamide") + _usjnt_row(mix="[D000600]Gliclazide"),
        encoding="utf-8",
    )
    spec = _DUR_RAG_REGISTRY["dur_usjnt_taboo.csv"]

    docs, warnings = _load_docs_from_csv(csv_file, spec)

    assert len(docs) == 2
    assert docs[0].id != docs[1].id
    assert warnings == []


def test_load_docs_from_csv_falls_back_to_row_index_on_id_collision(tmp_path):
    """id_fields 조합으로도 실제 중복이 나오면(설계 실수 등) row 인덱스로 재폴백해
    ChromaDB의 DuplicateIDError로 인제스트 전체가 죽는 걸 막는다."""
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    # 완전히 동일한 DUR_SEQ가 두 번 나오는 이상 데이터를 흉내낸다.
    _write_pwnm_csv(csv_file, [_PWNM_ROW.format(seq=1), _PWNM_ROW.format(seq=1)])
    spec = _DUR_RAG_REGISTRY["dur_pwnm_taboo.csv"]

    docs, warnings = _load_docs_from_csv(csv_file, spec)

    assert len(docs) == 2
    assert docs[0].id != docs[1].id
    assert docs[1].id == "dur_pwnm_taboo.csv:row1"
    assert any("중복" in w for w in warnings)


def test_active_embedding_model_returns_openai_when_provider_openai(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", "sk-key")

    assert "text-embedding-3-small" in active_embedding_model()


def test_active_embedding_model_raises_when_no_key(monkeypatch):
    """로컬 HF 폴백 없이, 키가 전혀 없으면 즉시 실패한다(무음 성능저하 대신 fail-fast)."""
    monkeypatch.setattr(ingest_module.settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", None)

    with pytest.raises(EmbeddingUnavailableError):
        active_embedding_model()


def test_get_embeddings_raises_when_no_key(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(ingest_module.settings, "OPENAI_EMBEDDING_API_KEY", None)
    monkeypatch.setattr(ingest_module.settings, "OPENAI_API_KEY", None)

    with pytest.raises(EmbeddingUnavailableError):
        get_embeddings()


def test_active_embedding_model_returns_hf_when_provider_huggingface(monkeypatch):
    """Phase 0 벤치마크(recall@3: OpenAI 0.85 vs HF multilingual-e5-large 1.0) 결과로
    기본 프로바이더가 huggingface(하이브리드: 로컬 인제스트+API 질의)로 바뀌었다."""
    monkeypatch.setattr(ingest_module.settings, "EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setattr(ingest_module.settings, "HUGGINGFACE_API_KEY", "hf-key")
    monkeypatch.setattr(ingest_module.settings, "HF_EMBEDDING_MODEL", "intfloat/multilingual-e5-large")

    assert active_embedding_model() == "huggingface:intfloat/multilingual-e5-large"


def test_active_embedding_model_raises_when_huggingface_key_missing(monkeypatch):
    """인제스트(로컬)엔 키가 필요 없지만 실시간 질의(HF Inference API)엔 필요해,
    상황별로 갈리면 헷갈리므로 프로바이더가 huggingface면 항상 키를 요구한다."""
    monkeypatch.setattr(ingest_module.settings, "EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setattr(ingest_module.settings, "HUGGINGFACE_API_KEY", None)

    with pytest.raises(EmbeddingUnavailableError):
        active_embedding_model()


def test_get_embeddings_returns_hf_wrapper_when_provider_huggingface(monkeypatch):
    monkeypatch.setattr(ingest_module.settings, "EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setattr(ingest_module.settings, "HUGGINGFACE_API_KEY", "hf-key")

    embeddings = get_embeddings()

    assert isinstance(embeddings, ingest_module._HFHybridEmbeddings)


class _FakeSentenceTransformer:
    """`sentence_transformers.SentenceTransformer`를 흉내낸다(로컬 배치 인코딩 경로)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts, normalize_embeddings: bool = False, show_progress_bar: bool = False):
        self.calls.append(texts)
        return np.array([[1.0, 2.0, 3.0] for _ in texts])


class _FakeHFQueryClient:
    """`huggingface_hub.InferenceClient`를 흉내낸다(호스팅 질의 경로).
    `fail_times`만큼 연속 실패 후 성공한다."""

    def __init__(self, calls: list[str], fail_times: int = 0, token: str | None = None) -> None:
        self.calls = calls
        self.fail_times = fail_times
        self._call_count = 0

    def feature_extraction(self, text: str, model: str | None = None, normalize: bool | None = None):
        self.calls.append(text)
        self._call_count += 1
        if self._call_count <= self.fail_times:
            raise RuntimeError("일시적 500 에러")
        return np.array([4.0, 5.0, 6.0])


def test_hf_hybrid_embeddings_documents_use_local_batch_with_passage_prefix(monkeypatch):
    """대량 인제스트(embed_documents)는 로컬 sentence-transformers로 배치 인코딩한다."""
    fake_model = _FakeSentenceTransformer()
    monkeypatch.setattr(ingest_module, "_get_local_model", lambda name: fake_model)

    embedder = ingest_module._HFHybridEmbeddings(model="m", hf_api_key="key")
    doc_vecs = embedder.embed_documents(["문서1", "문서2"])

    assert fake_model.calls == [["passage: 문서1", "passage: 문서2"]]
    assert doc_vecs == [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]


def test_hf_hybrid_embeddings_query_uses_hf_api_with_query_prefix(monkeypatch):
    """실시간 챗 질의(embed_query)는 HF Inference API(호스팅)로 단건 호출한다."""
    calls: list[str] = []
    monkeypatch.setattr("huggingface_hub.InferenceClient", lambda token=None: _FakeHFQueryClient(calls))

    embedder = ingest_module._HFHybridEmbeddings(model="m", hf_api_key="key")
    query_vec = embedder.embed_query("질문 내용")

    assert calls == ["query: 질문 내용"]
    assert query_vec == [4.0, 5.0, 6.0]


def test_hf_hybrid_embeddings_query_retries_then_succeeds(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("huggingface_hub.InferenceClient", lambda token=None: _FakeHFQueryClient(calls, fail_times=2))
    monkeypatch.setattr("time.sleep", lambda s: None)

    embedder = ingest_module._HFHybridEmbeddings(model="m", hf_api_key="key", retries=3)
    vec = embedder.embed_query("질문")

    assert vec == [4.0, 5.0, 6.0]


def test_hf_hybrid_embeddings_query_raises_after_exhausting_retries(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("huggingface_hub.InferenceClient", lambda token=None: _FakeHFQueryClient(calls, fail_times=99))
    monkeypatch.setattr("time.sleep", lambda s: None)

    embedder = ingest_module._HFHybridEmbeddings(model="m", hf_api_key="key", retries=2)
    with pytest.raises(RuntimeError):
        embedder.embed_query("질문")


def test_hf_local_embeddings_caches_model_instance(monkeypatch):
    """모델은 프로세스당 1회만 로드되도록 캐싱된다(재호출 시 재다운로드/재로딩 없음)."""
    load_count = 0

    class _FakeSentenceTransformerClass:
        def __init__(self, name):
            nonlocal load_count
            load_count += 1

        def encode(self, texts, normalize_embeddings=False, show_progress_bar=False):
            return np.array([1.0, 2.0, 3.0])

    monkeypatch.setattr(ingest_module, "_LOCAL_MODEL_CACHE", {})
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", _FakeSentenceTransformerClass)

    ingest_module._get_local_model("m")
    ingest_module._get_local_model("m")

    assert load_count == 1


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


class _FakeVectorDb:
    """langchain-chroma의 공개 API(get/delete/add_documents/delete_collection)만
    흉내낸다. `_collection` 사설 접근은 일부러 두지 않는다 — 프로덕션 코드가 사설
    접근을 시도하면 AttributeError로 곧장 드러나야 한다."""

    def __init__(self, ids: list[str] | None = None, metadatas: list[dict] | None = None) -> None:
        self._ids = list(ids or [])
        self._metadatas = list(metadatas or [])
        self.call_order: list[str] = []
        self.delete_collection_called = False

    def get(self, where: dict | None = None, include: list[str] | None = None):
        if not where:
            return {"ids": list(self._ids)}
        key, value = next(iter(where.items()))
        matched = [i for i, m in zip(self._ids, self._metadatas, strict=True) if m.get(key) == value]
        return {"ids": matched}

    def delete(self, where: dict | None = None):
        self.call_order.append("delete")
        if not where:
            return
        key, value = next(iter(where.items()))
        kept = [(i, m) for i, m in zip(self._ids, self._metadatas, strict=True) if m.get(key) != value]
        self._ids = [i for i, _ in kept]
        self._metadatas = [m for _, m in kept]

    def add_documents(self, docs):
        self.call_order.append("add_documents")
        for d in docs:
            if d.id in self._ids:
                self._metadatas[self._ids.index(d.id)] = d.metadata
            else:
                self._ids.append(d.id)
                self._metadatas.append(d.metadata)

    def delete_collection(self):
        self.delete_collection_called = True
        self._ids = []
        self._metadatas = []


def test_read_collection_metadata_returns_stored_metadata():
    """langchain-chroma 1.1.0엔 컬렉션 메타데이터 공개 접근자가 없어, 사설 `_collection`
    접근이 이 헬퍼 한 곳에만 격리돼 있는지 검증한다."""
    db = _FakeDb({"embedding_model": "openai:text-embedding-3-small"})

    assert _read_collection_metadata(db) == {"embedding_model": "openai:text-embedding-3-small"}


def test_read_collection_metadata_returns_empty_dict_when_absent():
    assert _read_collection_metadata(_FakeDb(None)) == {}
    assert _read_collection_metadata(_FakeVectorDb()) == {}


def test_ingest_single_csv_file_deletes_before_upserting(tmp_path, monkeypatch):
    """재업로드 시 delete가 add_documents보다 먼저 호출되는지(순서) 검증한다 —
    그래야 CSV에서 빠진 행(삭제된 규칙)이 남지 않는다."""
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    _write_pwnm_csv(csv_file, [_PWNM_ROW.format(seq=1)])
    fake_db = _FakeVectorDb(ids=["dur_pwnm_taboo.csv:99"], metadatas=[{"source_id": "dur_pwnm_taboo.csv"}])
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    result = ingest_single_csv_file(csv_file)

    assert fake_db.call_order == ["delete", "add_documents"]
    assert result["deleted"] == 1
    assert result["ingested"] == 1
    assert result["errors"] == []
    assert fake_db._ids == ["dur_pwnm_taboo.csv:1"]


def test_ingest_single_csv_file_is_idempotent_on_repeated_upload(tmp_path, monkeypatch):
    """같은 파일을 두 번 업로드해도(같은 fake db 상태 유지) 문서 수가 늘어나지 않는다."""
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    _write_pwnm_csv(csv_file, [_PWNM_ROW.format(seq=1), _PWNM_ROW.format(seq=2)])
    fake_db = _FakeVectorDb()
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    ingest_single_csv_file(csv_file)
    result = ingest_single_csv_file(csv_file)

    assert result["collection_count"] == 2
    assert len(fake_db._ids) == 2


def test_ingest_single_csv_file_returns_error_for_unregistered_filename(tmp_path, monkeypatch):
    csv_file = tmp_path / "drug_identification.csv"  # 구조화 대상, 레지스트리에 없음
    csv_file.write_text("ITEM_SEQ,ITEM_NAME\n1,테스트약\n", encoding="utf-8")
    fake_db = _FakeVectorDb()
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    result = ingest_single_csv_file(csv_file)

    assert result["ingested"] == 0
    assert "RAG 대상으로 등록되지" in result["errors"][0]
    assert fake_db.call_order == []  # db를 아예 건드리지 않음


def test_ingest_single_csv_file_reports_parse_errors_without_raising(tmp_path, monkeypatch):
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    csv_file.write_bytes(b"\xff\xfe\x00\x01broken")  # utf-8-sig로도 못 읽는 깨진 바이트
    fake_db = _FakeVectorDb()
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    result = ingest_single_csv_file(csv_file)

    assert result["ingested"] == 0
    assert result["errors"]  # 예외 없이 errors에 담김


def test_reset_dur_collection_calls_delete_collection(monkeypatch):
    fake_db = _FakeVectorDb(ids=["a"], metadatas=[{}])
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    reset_dur_collection()

    assert fake_db.delete_collection_called is True


def test_ingest_csv_data_processes_all_registered_files_even_when_collection_nonempty(tmp_path, monkeypatch):
    """옛 버그(컬렉션에 문서가 하나라도 있으면 전체 스킵) 대체 테스트: 컬렉션이 이미
    비어있지 않아도, 레지스트리의 각 파일을 훑어(문서 수가 달라진 파일만) 처리한다."""
    monkeypatch.setattr(ingest_module, "DATA_DIR", tmp_path)
    _write_pwnm_csv(tmp_path / "dur_pwnm_taboo.csv", [_PWNM_ROW.format(seq=1)])
    # 나머지 등록 파일은 source/에 없다고 가정 -> "파일 없음"으로 건너뜀(에러 아님).

    fake_db = _FakeVectorDb(ids=["some-other-doc"], metadatas=[{"source_id": "other.csv"}])
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    results = ingest_csv_data()

    pwnm_result = next(r for r in results if r["filename"] == "dur_pwnm_taboo.csv")
    assert pwnm_result["ingested"] == 1
    assert "dur_pwnm_taboo.csv:1" in fake_db._ids


def test_ingest_csv_data_skips_unchanged_file_on_second_run(tmp_path, monkeypatch):
    """행 수가 그대로면(=바뀐 게 없다고 판단) 재임베딩(add_documents)을 생략한다 —
    매 앱 재시작마다 전체를 다시 임베딩하는 낭비를 막기 위함."""
    monkeypatch.setattr(ingest_module, "DATA_DIR", tmp_path)
    _write_pwnm_csv(tmp_path / "dur_pwnm_taboo.csv", [_PWNM_ROW.format(seq=1)])
    fake_db = _FakeVectorDb()
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    ingest_csv_data()  # 1차: 신규 적재
    fake_db.call_order.clear()
    results = ingest_csv_data()  # 2차: 변경 없음

    pwnm_result = next(r for r in results if r["filename"] == "dur_pwnm_taboo.csv")
    assert pwnm_result.get("skipped") is True
    assert "add_documents" not in fake_db.call_order


def test_ingest_csv_data_force_deletes_collection_before_reingesting(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_module, "DATA_DIR", tmp_path)
    _write_pwnm_csv(tmp_path / "dur_pwnm_taboo.csv", [_PWNM_ROW.format(seq=1)])
    fake_db = _FakeVectorDb(ids=["stale"], metadatas=[{}])
    monkeypatch.setattr(ingest_module, "build_vector_store", lambda: fake_db)

    ingest_csv_data(force=True)

    assert fake_db.delete_collection_called is True
    assert "dur_pwnm_taboo.csv:1" in fake_db._ids
    assert "stale" not in fake_db._ids
