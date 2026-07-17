"""
Phase 0 임베딩 벤치마크(1회성 분석 도구, 프로덕션 코드 아님 — 어디서도 import되지 않는다).

현재 쓰는 OpenAI `text-embedding-3-small`과 한국어 후보 HF 모델(HF Inference API, 호스팅
호출 — 로컬 torch/sentence-transformers 불필요)을 `embedding_golden_set.json`으로 recall@k
비교한다. 전체 코퍼스(DUR 7개 파일 + 논문 5개 질환, 약 3,400건)를 매번 다 임베딩하면 API
호출이 커지므로, 골든셋 정답 문서는 반드시 포함하고 나머지는 무작위 표본으로 채운
`CORPUS_SAMPLE_SIZE`건만 비교 대상으로 쓴다.

실행:
    uv run python -m ai_worker.scripts.benchmark_embeddings

사전 준비: .env에 OPENAI_API_KEY, HUGGINGFACE_API_KEY(Inference Providers 호출 권한 포함)가
설정돼 있어야 한다.
"""

import json
import random
import time
from pathlib import Path

import numpy as np
from huggingface_hub import InferenceClient

from ai_worker.core.config import settings
from ai_worker.tasks.ingest import _DUR_RAG_REGISTRY, _load_docs_from_csv, get_embeddings
from ai_worker.tasks.ingest import DATA_DIR as DUR_DATA_DIR
from ai_worker.tasks.ingest_papers import build_documents, load_raw_papers, load_summary_cache

GOLDEN_SET_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "embedding_golden_set.json"
CORPUS_SAMPLE_SIZE = 250
TOP_K = (3, 5)
# 한국어 검색 벤치마크에서 자주 상위권으로 언급되는 다국어 모델 후보. HF Inference API
# 서버리스 호스팅 가용성은 실행 시점에 달라질 수 있어, 실패하면 다른 후보로 교체한다.
HF_CANDIDATES = ["intfloat/multilingual-e5-large", "BAAI/bge-m3"]

random.seed(42)


def _load_corpus() -> list[dict]:
    """DUR 7개 파일 + 논문 5개 질환의 전체 문서를 (text, doc_id|None, pmid|None) 형태로 모은다."""
    corpus: list[dict] = []
    for file_name, spec in _DUR_RAG_REGISTRY.items():
        csv_file = DUR_DATA_DIR / file_name
        if not csv_file.exists():
            print(f"경고: {file_name}이 source/에 없어 코퍼스에서 제외됨")
            continue
        docs, _ = _load_docs_from_csv(csv_file, spec)
        corpus.extend({"text": d.page_content, "doc_id": d.id, "pmid": None} for d in docs)

    # 한국어 요약 캐시를 함께 넘겨, 실제 색인되는 본문과 같은 형태로 벤치마크한다
    # (요약 접두 여부가 한국어 질의 매칭에 크게 영향을 준다 — ingest_papers 참고).
    raw_by_disease = load_raw_papers()
    summaries = load_summary_cache()
    for disease, papers in raw_by_disease.items():
        docs = build_documents(disease, papers, summaries)
        corpus.extend({"text": d.page_content, "doc_id": None, "pmid": d.metadata.get("pmid")} for d in docs)
    return corpus


def _sample_corpus(corpus: list[dict], golden_set: list[dict]) -> list[dict]:
    """골든셋 정답 문서는 반드시 포함하고, 나머지는 무작위 표본으로 CORPUS_SAMPLE_SIZE까지 채운다."""
    required_doc_ids = {g["expected_doc_id"] for g in golden_set if "expected_doc_id" in g}
    required_pmids = {g["expected_pmid"] for g in golden_set if "expected_pmid" in g}

    required, rest = [], []
    for c in corpus:
        if c["doc_id"] in required_doc_ids or c["pmid"] in required_pmids:
            required.append(c)
        else:
            rest.append(c)

    missing = required_doc_ids - {c["doc_id"] for c in required}
    missing |= required_pmids - {c["pmid"] for c in required}
    if missing:
        print(f"경고: 골든셋 정답 문서를 코퍼스에서 못 찾음(무시하고 진행): {missing}")

    random.shuffle(rest)
    fill = max(CORPUS_SAMPLE_SIZE - len(required), 0)
    return required + rest[:fill]


def _cosine_sim(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def _embed_openai(texts: list[str]) -> list[list[float]]:
    return get_embeddings().embed_documents(texts)


def _embed_hf(texts: list[str], model: str, retries: int = 3) -> list[np.ndarray]:
    """HF 서버리스 Inference는 콜드스타트/부하로 간헐적 500이 흔해, 텍스트당 재시도를 둔다."""
    client = InferenceClient(token=settings.HUGGINGFACE_API_KEY)
    vectors = []
    for i, t in enumerate(texts):
        last_error = None
        for attempt in range(retries):
            try:
                vectors.append(np.asarray(client.feature_extraction(t, model=model)).reshape(-1))
                last_error = None
                break
            except Exception as e:
                last_error = e
                time.sleep(2 * (attempt + 1))
        if last_error is not None:
            raise last_error
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{len(texts)} embedded ({model})")
    return vectors


def _recall_at_k(golden_set: list[dict], corpus: list[dict], corpus_vecs, query_vecs, k: int) -> float:
    hits = 0
    for g, qvec in zip(golden_set, query_vecs, strict=True):
        sims = sorted(
            ((_cosine_sim(qvec, cvec), c) for cvec, c in zip(corpus_vecs, corpus, strict=True)),
            key=lambda x: x[0],
            reverse=True,
        )[:k]
        expected_doc_id = g.get("expected_doc_id")
        expected_pmid = g.get("expected_pmid")
        found = any(
            (expected_doc_id is not None and c["doc_id"] == expected_doc_id)
            or (expected_pmid is not None and c["pmid"] == expected_pmid)
            for _, c in sims
        )
        hits += int(found)
    return hits / len(golden_set)


def run_benchmark() -> dict:
    golden_set = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    full_corpus = _load_corpus()
    corpus = _sample_corpus(full_corpus, golden_set)
    print(f"코퍼스 표본: {len(corpus)}건 (전체 {len(full_corpus)}건 중), 골든셋 {len(golden_set)}문항\n")

    questions = [g["question"] for g in golden_set]
    corpus_texts = [c["text"] for c in corpus]
    results: dict[str, dict] = {}

    print("[OpenAI text-embedding-3-small] 임베딩 중...")
    openai_corpus_vecs = _embed_openai(corpus_texts)
    openai_query_vecs = _embed_openai(questions)
    results["openai:text-embedding-3-small"] = {
        f"recall@{k}": _recall_at_k(golden_set, corpus, openai_corpus_vecs, openai_query_vecs, k) for k in TOP_K
    }

    for model in HF_CANDIDATES:
        print(f"\n[HF {model}] 임베딩 중...")
        try:
            hf_corpus_vecs = _embed_hf(corpus_texts, model)
            hf_query_vecs = _embed_hf(questions, model)
        except Exception as e:
            print(f"  실패: {e}")
            results[f"hf:{model}"] = {"error": str(e)}
            continue
        results[f"hf:{model}"] = {
            f"recall@{k}": _recall_at_k(golden_set, corpus, hf_corpus_vecs, hf_query_vecs, k) for k in TOP_K
        }

    print("\n=== 결과 ===")
    for provider, metrics in results.items():
        print(f"{provider}: {metrics}")
    return results


if __name__ == "__main__":
    run_benchmark()
