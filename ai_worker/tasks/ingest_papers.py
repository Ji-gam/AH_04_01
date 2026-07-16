"""
T-LLM-7-3(개정): PubMed 논문 RAG 인제스천. 오프라인/배치로 실행하며 두 단계로 나뉜다.

1단계(fetch_and_append_category_papers): PubMed에서 질환×카테고리
(`app/services/content_service.py`의 CATEGORIES: LIFESTYLE/FOOD/MEDICAL_NEWS) 조합별로
원본 논문(제목+초록+PMID)을 수집해 ai_worker/mock_data_for_papers_raw/{질환}.json에
그대로 저장한다. 가공(청킹/임베딩) 없이 원문만 남겨, 사람이 직접 열어 품질/건수를
검토할 수 있게 한다.

카테고리 구분 없이 질환만으로 넓게 수집하는 방식은 초기에 시도했다가 폐기했다 —
"약물/치료" 위주로 쏠려서 라이프스타일/식단/최신동향 같은 실제 사용자 질문 각도를
반영하지 못했기 때문. 항상 카테고리 단위로 수집한다.

2단계(ingest_papers): 1단계 원본 JSON을 읽어(PubMed 재호출 없음) 청킹+임베딩 후
Chroma 컬렉션(pubmed_papers)에 저장한다. 제목+초록 결합이 1000자 이하면 그대로 문서
1개로, 넘으면 RecursiveCharacterTextSplitter로 분할한다. PMID 기준 증분 인제스천이라
이미 색인된 논문은 다시 임베딩하지 않는다(원본이 계속 늘어나도 신규분만 과금됨).
DUR 인제스천(ingest.py)의 임베딩/Chroma 인프라를 그대로 재사용.

run_daily_pipeline: 1단계+2단계를 순서대로 잇는 완결된 배치. 매일 이 함수(또는
`--pipeline` CLI) 하나만 실행하면 "신규 논문 수집 -> 색인"까지 사람 개입 없이 끝까지
돈다. 다만 "이 명령을 매일 자동으로 실행시키는" 스케줄러(cron/Celery beat) 자체는
아직 안 붙였다 — 스테이징 환경이 없는 지금은 배치 로직만 수동 트리거로 완성해두고,
실제 자동 스케줄링은 스테이징이 생긴 뒤 별도로 붙이기로 결정했다(T-LLM-3와 동일 원칙).
그때까지는 아래 명령을 사람이 매일 한 번 수동 실행한다:

    uv run python -m ai_worker.tasks.ingest_papers --pipeline

실행(개별 단계 디버깅용):
    uv run python -m ai_worker.tasks.ingest_papers                        # 1단계만(원본 수집)
    uv run python -m ai_worker.tasks.ingest_papers --index-only           # 2단계만(색인)
    uv run python -m ai_worker.tasks.ingest_papers --index-only --force   # 컬렉션 삭제 후 전체 재색인
"""

import argparse
import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ai_worker.core.config import settings
from ai_worker.tasks.ingest import CHROMA_DIR, active_embedding_model, get_embeddings

logger = logging.getLogger("ai_worker.ingest_papers")
logging.basicConfig(level=logging.INFO)

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_EFETCH_BATCH_SIZE = 50

RAW_DATA_DIR = Path(__file__).parent.parent / "mock_data_for_papers_raw"

# DUR과 도메인이 섞이지 않도록 별도 컬렉션(같은 CHROMA_DIR 아래).
PAPER_COLLECTION_NAME = "pubmed_papers"
# 제목+초록 결합이 이 길이를 넘을 때만 분할한다(대부분의 초록은 안 넘음).
_MAX_CHARS_BEFORE_SPLIT = 1000
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 100

# 원래 실시간 검색 도구(ai_worker/tools/paper_search.py)에 있던 값을 그대로 이식.
# 답변 프롬프트가 "구체적 수치 인용"을 요구하므로, Review(종합 논문) 대신 원 연구
# (RCT/Clinical Trial, 실제 실험 수치를 보고하는 논문)로 한정한다(카테고리별로 예외 있음,
# _CATEGORIES_REQUIRING_TRIAL_FILTER 참고).
SUPPORTED_DISEASES = ["암", "심장질환", "뇌혈관질환", "당뇨", "간질환"]
_TRIAL_FILTER = "(Clinical Trial[Publication Type] OR Randomized Controlled Trial[Publication Type])"

_DISEASE_MESH_TERMS: dict[str, str] = {
    "암": '"Neoplasms"[MeSH Terms]',
    "심장질환": '"Heart Diseases"[MeSH Terms]',
    "뇌혈관질환": '"Cerebrovascular Disorders"[MeSH Terms]',
    "당뇨": '"Diabetes Mellitus"[MeSH Terms]',
    "간질환": '"Liver Diseases"[MeSH Terms]',
}

# app/services/content_service.py의 CATEGORIES/CATEGORY_TOPICS와 동일한 3분류를
# PubMed MeSH 용어로 옮긴 것. 콘텐츠 파이프라인(T-LLM-3)이 이미 쓰는 분류 체계를
# 그대로 재사용해 두 파이프라인의 "카테고리" 개념이 어긋나지 않게 한다.
CATEGORIES = ["LIFESTYLE", "FOOD", "MEDICAL_NEWS"]
_CATEGORY_SEARCH_TERMS: dict[str, str] = {
    "LIFESTYLE": '("Exercise"[MeSH Terms] OR "Sleep Hygiene"[MeSH Terms] OR "Stress, Psychological"[MeSH Terms])',
    "FOOD": '("Diet, Food, and Nutrition"[MeSH Terms] OR "Diet Therapy"[MeSH Terms] OR "Nutritional Physiological Phenomena"[MeSH Terms])',
    # "신규 발견/치료법/신약" 소식 — RCT로 확정되기 전 단계의 연구도 걸려야 하므로
    # 이 카테고리만 _TRIAL_FILTER를 강제하지 않는다(아래 _category_search_term 참고).
    "MEDICAL_NEWS": (
        '("Drug Discovery"[MeSH Terms] OR "Molecular Targeted Therapy"[MeSH Terms] '
        'OR "Biomarkers, Pharmacological"[MeSH Terms] OR "Drug Therapy"[MeSH Subheading])'
    ),
}
_CATEGORY_RETMAX = 50
# MEDICAL_NEWS는 신약/신규 치료법이 아직 RCT로 확정되기 전 단계도 다뤄야 해서 제외.
_CATEGORIES_REQUIRING_TRIAL_FILTER = {"LIFESTYLE", "FOOD"}


def _category_search_term(disease: str, category: str) -> str:
    base = f"{_DISEASE_MESH_TERMS[disease]} AND {_CATEGORY_SEARCH_TERMS[category]}"
    if category in _CATEGORIES_REQUIRING_TRIAL_FILTER:
        return f"{base} AND {_TRIAL_FILTER}"
    return base


async def _esearch_bulk(client: httpx.AsyncClient, term: str, retmax: int) -> list[str]:
    params: dict[str, str] = {"db": "pubmed", "term": term, "retmax": str(retmax), "sort": "date", "retmode": "json"}
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    response = await client.get(f"{_EUTILS_BASE}/esearch.fcgi", params=params)
    response.raise_for_status()
    result: list[str] = response.json().get("esearchresult", {}).get("idlist", [])
    return result


async def _efetch_batch(client: httpx.AsyncClient, pmids: list[str]) -> str:
    params: dict[str, str] = {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    response = await client.get(f"{_EUTILS_BASE}/efetch.fcgi", params=params)
    response.raise_for_status()
    return response.text


def _flatten_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def _parse_articles(xml_text: str) -> list[dict[str, str | None]]:
    """efetch XML을 파싱해 초록이 있는 논문만 전부(순서 그대로) 반환한다."""
    root = ET.fromstring(xml_text)
    articles: list[dict[str, str | None]] = []
    for article_el in root.findall(".//PubmedArticle"):
        pmid_el = article_el.find(".//PMID")
        title_el = article_el.find(".//ArticleTitle")
        if pmid_el is None or title_el is None or pmid_el.text is None:
            continue
        abstract = " ".join(
            text for el in article_el.findall(".//Abstract/AbstractText") if (text := _flatten_text(el))
        )
        if not abstract:
            continue
        articles.append({"pmid": pmid_el.text.strip(), "title": _flatten_text(title_el), "abstract": abstract})
    return articles


async def _fetch_papers_for_term(client: httpx.AsyncClient, term: str, retmax: int) -> list[dict[str, str | None]]:
    """검색어 하나로 PubMed에서 최대 retmax건의 원본(제목+초록+PMID)을 수집한다."""
    pmids = await _esearch_bulk(client, term, retmax)
    if not pmids:
        return []

    articles: list[dict[str, str | None]] = []
    for i in range(0, len(pmids), _EFETCH_BATCH_SIZE):
        batch = pmids[i : i + _EFETCH_BATCH_SIZE]
        xml_text = await _efetch_batch(client, batch)
        articles.extend(_parse_articles(xml_text))
        await asyncio.sleep(0.4)  # 키 없는 3req/sec 제한 준수
    return articles


async def fetch_and_append_category_papers(
    retmax_per_category: int = _CATEGORY_RETMAX, categories: list[str] | None = None
) -> dict[str, dict[str, int]]:
    """기존 질환별 raw 파일은 그대로 두고, 카테고리별 검색어로 새로 찾은 논문만
    (PMID 중복 없는 것만) category 태그를 붙여 증분 추가한다.
    categories를 넘기면 그 카테고리들만 재시도(예: 검색어 수정 후 MEDICAL_NEWS만 재수집)."""
    target_categories = categories if categories is not None else CATEGORIES
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict[str, int]] = {}
    async with httpx.AsyncClient(timeout=settings.PUBMED_TIMEOUT) as client:
        for disease in SUPPORTED_DISEASES:
            out_path = RAW_DATA_DIR / f"{disease}.json"
            existing: list[dict] = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
            existing_pmids = {p["pmid"] for p in existing}

            report[disease] = {}
            for category in target_categories:
                term = _category_search_term(disease, category)
                papers = await _fetch_papers_for_term(client, term, retmax_per_category)
                added = 0
                for paper in papers:
                    if paper["pmid"] in existing_pmids:
                        continue
                    paper["category"] = category
                    existing.append(paper)
                    existing_pmids.add(paper["pmid"])
                    added += 1
                report[disease][category] = added
                await asyncio.sleep(0.4)

            out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{disease}: 총 {len(existing)}건 (카테고리별 신규 추가: {report[disease]})")
    return report


def load_raw_papers() -> dict[str, list[dict]]:
    """mock_data_for_papers_raw/*.json을 읽는다(PubMed 재호출 없음). 질환 파일이 없거나
    비어 있으면 에러 로그만 남기고 건너뛴다 — 다른 질환 인제스천은 계속 진행한다."""
    result: dict[str, list[dict]] = {}
    for disease in SUPPORTED_DISEASES:
        path = RAW_DATA_DIR / f"{disease}.json"
        if not path.exists():
            logger.error(f"원본 파일 없음, 건너뜀: {path}")
            continue
        papers = json.loads(path.read_text(encoding="utf-8"))
        if not papers:
            logger.error(f"원본 파일이 비어 있음, 건너뜀: {path}")
            continue
        result[disease] = papers
    return result


def build_documents(disease: str, papers: list[dict]) -> list[Document]:
    """질환 하나의 원본 논문 목록을 Document로 변환한다. 제목+초록 결합이
    _MAX_CHARS_BEFORE_SPLIT 이하면 문서 1개, 넘으면 RecursiveCharacterTextSplitter로
    분할한다(분할된 청크는 모두 같은 pmid/title 메타데이터를 공유)."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)
    documents: list[Document] = []
    for paper in papers:
        pmid = paper.get("pmid")
        abstract = paper.get("abstract")
        if not pmid or not abstract:
            logger.error(f"pmid/abstract 누락, 건너뜀: disease={disease}, paper={paper}")
            continue
        title = paper.get("title") or ""
        page_content = f"{title}\n\n{abstract}"
        metadata = {
            "disease": disease,
            "pmid": pmid,
            "title": title,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source": "PubMed",
            "category": paper.get("category") or "",
        }
        if len(page_content) <= _MAX_CHARS_BEFORE_SPLIT:
            documents.append(Document(page_content=page_content, metadata=metadata))
        else:
            documents.extend(
                Document(page_content=chunk, metadata=metadata) for chunk in splitter.split_text(page_content)
            )
    return documents


def build_paper_vector_store() -> Chroma:
    """ingest_papers·search_papers가 공유하는 Chroma 스토어 팩토리. DUR과 동일한
    CHROMA_DIR 아래, 별도 컬렉션(PAPER_COLLECTION_NAME)에 저장한다."""
    return Chroma(
        collection_name=PAPER_COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"embedding_model": active_embedding_model()},
    )


def _indexed_pmids(db: Chroma) -> set[str]:
    """이미 색인된 논문의 pmid 집합(청크 단위 저장이라 같은 pmid가 여러 청크에 걸쳐
    중복 등장하지만 set이라 자연히 1개로 합쳐진다). 증분 인제스천의 스킵 기준이 된다."""
    try:
        data = db.get(include=["metadatas"])
    except Exception as e:
        logger.warning(f"기존 색인 pmid 조회 실패: {e}. 전체를 신규로 간주하고 진행.")
        return set()
    metadatas = data.get("metadatas") or []
    return {m["pmid"] for m in metadatas if m and m.get("pmid")}


def ingest_papers() -> Chroma:
    """원본 JSON(load_raw_papers) -> 청킹(build_documents) -> Chroma 저장.
    PMID 기준 증분 인제스천이다: 이미 색인된 논문은 건너뛰고 신규 논문만 임베딩한다.
    (전체를 매번 다시 임베딩하면 원본이 늘어날 때마다 이미 낸 OpenAI 임베딩 비용을
    계속 반복 청구하게 되므로, 컬렉션 통째 스킵/재생성 대신 pmid 단위로 차이만 채운다.)"""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    db = build_paper_vector_store()
    already_indexed = _indexed_pmids(db)

    raw_by_disease = load_raw_papers()
    all_docs: list[Document] = []
    for disease, papers in raw_by_disease.items():
        new_papers = [p for p in papers if p.get("pmid") not in already_indexed]
        docs = build_documents(disease, new_papers)
        all_docs.extend(docs)
        logger.info(
            f"{disease}: 원본 {len(papers)}건 중 신규 {len(new_papers)}건 "
            f"(기존 색인 {len(papers) - len(new_papers)}건 스킵) -> 청크 {len(docs)}건"
        )

    if not all_docs:
        logger.info("신규 인제스천할 문서가 없습니다(모두 이미 색인됨).")
        return db

    batch_size = 500
    for i in range(0, len(all_docs), batch_size):
        batch = all_docs[i : i + batch_size]
        db.add_documents(batch)
        logger.info(f"배치 {i // batch_size + 1} 적재 완료 ({len(batch)}건)")
    logger.info(f"총 {len(all_docs)}건 신규 인제스천 완료.")
    return db


def reset_paper_collection() -> None:
    """--force 재색인용: 기존 pubmed_papers 컬렉션을 통째로 삭제한다."""
    db = build_paper_vector_store()
    db.delete_collection()
    logger.info(f"{PAPER_COLLECTION_NAME} 컬렉션 삭제 완료.")


async def run_daily_pipeline(
    retmax_per_category: int = _CATEGORY_RETMAX, categories: list[str] | None = None
) -> Chroma:
    """1단계(신규 논문 수집)+2단계(청킹+임베딩+색인)를 순서대로 잇는 완결된 배치.
    사람은 이 함수(또는 CLI `--pipeline`)를 실행 버튼처럼 누르기만 하면 되고, 그 안에서
    수집→중복 제거→색인까지 전부 자동으로 끝난다. "매일 자동으로 이 명령 자체를 실행시키는"
    스케줄러(cron/Celery beat)는 아직 붙이지 않았다 — 그건 별도 단계다(모듈 docstring 참고)."""
    await fetch_and_append_category_papers(retmax_per_category=retmax_per_category, categories=categories)
    return ingest_papers()


async def _main(args: argparse.Namespace) -> None:
    if args.pipeline:
        db = await run_daily_pipeline(retmax_per_category=args.retmax_per_category, categories=args.categories)
        count = len(db.get(include=[])["ids"])
        print(f"{PAPER_COLLECTION_NAME} 컬렉션 문서 수: {count}")
        return
    if args.index_only:
        if args.force:
            reset_paper_collection()
        db = ingest_papers()
        count = len(db.get(include=[])["ids"])
        print(f"{PAPER_COLLECTION_NAME} 컬렉션 문서 수: {count}")
        return
    await fetch_and_append_category_papers(retmax_per_category=args.retmax_per_category, categories=args.categories)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--retmax-per-category",
        type=int,
        default=_CATEGORY_RETMAX,
        help=f"조합(질환×카테고리)당 수집 건수(기본 {_CATEGORY_RETMAX})",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=CATEGORIES,
        default=None,
        help="재수집할 카테고리만 지정(예: --categories MEDICAL_NEWS). 생략 시 전체 카테고리.",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="2단계(청킹+임베딩+Chroma 저장)만 실행. PubMed를 호출하지 않고 원본 JSON만 읽는다.",
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="1단계+2단계를 순서대로 모두 실행하는 완결된 배치(매일 수동 실행용).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="(--index-only 전용) 기존 pubmed_papers 컬렉션을 삭제하고 재색인한다.",
    )
    parsed_args = parser.parse_args()
    asyncio.run(_main(parsed_args))
