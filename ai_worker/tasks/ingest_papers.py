"""
T-LLM-7-3(개정): PubMed 논문 RAG 인제스천. 오프라인/배치로 실행하며 두 단계로 나뉜다.

1단계(fetch_and_append_category_papers): PubMed에서 질환×카테고리
(`app/services/content_service.py`의 CATEGORIES: LIFESTYLE/FOOD/MEDICAL_NEWS) 조합별로
원본 논문(제목+초록+PMID)을 수집해 ai_worker/source/{질환}.json에 그대로 저장한다
(T-RAG-SOURCE-MIGRATION: 예전 mock_data_for_papers_raw/에서 이전). 가공(청킹/임베딩)
없이 원문만 남겨, 사람이 직접 열어 품질/건수를 검토할 수 있게 한다.

카테고리 구분 없이 질환만으로 넓게 수집하는 방식은 초기에 시도했다가 폐기했다 —
"약물/치료" 위주로 쏠려서 라이프스타일/식단/최신동향 같은 실제 사용자 질문 각도를
반영하지 못했기 때문. 항상 카테고리 단위로 수집한다.

2단계(ensure_paper_summaries): 논문마다 한국어 요약을 LLM으로 1회 생성해 **원본 JSON의
`summary_ko` 필드에 직접 써 넣는다.** 사용자 질의는 한국어인데 논문은 영어라, 이 요약이
없으면 정답 논문과 무관 논문의 거리 차가 노이즈 수준으로 좁아진다.

곁다리 캐시 파일(pmid -> 요약)을 두지 않는 이유: 그러면 색인할 때 로더가 그 파일을 읽어
본문 앞에 붙여야 하고, 그건 **사서가 요리를 하는 것**이다. 색인은 여러 번 돌리므로 요리는
미리 끝내두고 결과를 원본의 필드로 합친다 — 로더는 그냥 컬럼 하나로 읽는다. 재과금 방지는
"레코드에 summary_ko가 있나"가 대신하므로 신규 논문에만 비용이 난다.

3단계(색인): 이 모듈이 하지 않는다. `source/`에 있는 논문 JSON을 드롭 폴더 파이프라인
(`ai_worker/ingest/`)이 처리한다. 초록 1편 = 문서 1개다 — 고정 크기 분할을 쓰던 과거 방식이
740편 중 729편을 쪼개 제목 없는 조각으로 컬렉션의 70%를 채웠고, 그게 "고혈압 질문에 당뇨
논문"의 원인이었다.

run_daily_pipeline: 1단계+2단계를 순서대로 잇는 완결된 배치. 매일 이 함수(또는
`--pipeline` CLI) 하나만 실행하면 "신규 논문 수집 -> 색인"까지 사람 개입 없이 끝까지
돈다. 다만 "이 명령을 매일 자동으로 실행시키는" 스케줄러(cron/Celery beat) 자체는
아직 안 붙였다 — 스테이징 환경이 없는 지금은 배치 로직만 수동 트리거로 완성해두고,
실제 자동 스케줄링은 스테이징이 생긴 뒤 별도로 붙이기로 결정했다(T-LLM-3와 동일 원칙).
그때까지는 아래 명령을 사람이 매일 한 번 수동 실행한다:

    uv run python -m ai_worker.tasks.ingest_papers --pipeline

실행(개별 단계 디버깅용):
    uv run python -m ai_worker.tasks.ingest_papers                        # 1단계만(원본 수집)
    uv run python -m ai_worker.tasks.ingest_papers --summarize-only       # 2단계만(한국어 요약)
    uv run python -m ai_worker.ingest                                      # 3단계(색인) — 드롭 폴더 파이프라인 소관
"""

import argparse
import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ai_worker.core.config import settings
from ai_worker.ingest.pipeline import ingest_source
from ai_worker.ingest.sources import discover

logger = logging.getLogger("ai_worker.ingest_papers")
logging.basicConfig(level=logging.INFO)

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_EFETCH_BATCH_SIZE = 50

# T-RAG-SOURCE-MIGRATION: mock_data_for_papers_raw/(실험용 스냅샷, 폐기)에서
# ai_worker/source/(RAG+구조화 데이터가 함께 모이는 단일 원천)로 이전.
RAW_DATA_DIR = Path(__file__).parent.parent / "source"

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


# LLM 동시 호출 수. 논문 740건을 순차로 돌리면 오래 걸리고, 너무 올리면 레이트리밋에 걸린다.
_SUMMARY_CONCURRENCY = 8
_SUMMARY_PROMPT = (
    "당신은 의학 논문을 한국어로 요약하는 전문가입니다. 주어진 논문 제목과 초록을 읽고, "
    "한국어 한두 문장으로 요약하세요. 반드시 포함할 것: 어떤 질환/대상자인지, 무엇을 했는지(중재/방법), "
    "무엇을 알아냈는지(결과). 이 요약은 한국어 검색 질의와 매칭되는 데 쓰이므로, 한국인이 실제로 "
    "검색할 법한 일상적인 의학 용어를 쓰세요. 요약문만 출력하고 다른 말은 하지 마세요."
)


async def _summarize_one(llm, paper: dict) -> bool:
    """논문 하나에 `summary_ko`를 채운다(제자리 수정). 성공하면 True."""
    abstract = paper.get("abstract")
    if not abstract:
        return False
    user_input = f"제목: {paper.get('title') or ''}\n\n초록: {abstract}"
    try:
        response = await llm.ainvoke(
            [{"role": "system", "content": _SUMMARY_PROMPT}, {"role": "user", "content": user_input}]
        )
    except Exception as e:
        # 한 건 실패가 전체 배치를 죽이면 안 된다 — 요약 없는 논문은 영어 원문만으로
        # 색인되고(검색은 되지만 한국어 매칭이 약함), 다음 실행 때 다시 시도된다.
        logger.error(f"요약 생성 실패(pmid={paper.get('pmid')}), 건너뜀: {e}")
        return False

    summary = str(response.content).strip()
    if not summary:
        return False
    paper["summary_ko"] = summary
    return True


async def ensure_paper_summaries() -> int:
    """요약이 없는 논문만 골라 한국어 요약을 만들어 **원본 JSON에 직접 써 넣는다.**

    곁다리 캐시 파일(pmid -> 요약)을 두지 않는 이유: 그러면 색인할 때 로더가 그 파일을 읽어
    본문 앞에 붙여야 하고, 그건 **사서가 요리를 하는 것**이다. 색인은 여러 번 돌리므로
    요리는 미리 끝내두고 결과를 원본의 필드로 합쳐둔다 — 로더는 그냥 컬럼 하나로 읽는다.

    재과금 방지(캐시의 원래 목적)는 "레코드에 summary_ko가 있나"가 대신한다. 이미 요약된
    논문은 건너뛰므로 원본이 늘어나도 신규분만 과금된다."""
    by_path: dict[Path, list[dict]] = {}
    todo: list[dict] = []
    for disease in SUPPORTED_DISEASES:
        path = RAW_DATA_DIR / f"{disease}.json"
        if not path.exists():
            logger.error(f"원본 파일 없음, 건너뜀: {path}")
            continue
        papers = json.loads(path.read_text(encoding="utf-8"))
        by_path[path] = papers
        # 아래 _summarize_one이 이 dict를 제자리에서 고치므로, papers를 그대로 다시 쓰면 된다.
        todo.extend(p for p in papers if not p.get("summary_ko"))

    if not todo:
        logger.info("한국어 요약 최신. 신규 생성 없음.")
        return 0

    if settings.OPENAI_API_KEY is None:
        logger.error("OPENAI_API_KEY가 없어 한국어 요약을 생성하지 못합니다. 요약 없이 진행합니다.")
        return 0

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=settings.OPENAI_TEMPERATURE,
    )
    logger.info(f"한국어 요약 생성 시작: {len(todo)}건 (동시 {_SUMMARY_CONCURRENCY})")
    semaphore = asyncio.Semaphore(_SUMMARY_CONCURRENCY)

    async def _bounded(paper: dict) -> bool:
        async with semaphore:
            return await _summarize_one(llm, paper)

    created = sum(await asyncio.gather(*(_bounded(p) for p in todo)))
    for path, papers in by_path.items():
        path.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"한국어 요약 {created}건 생성 완료(실패 {len(todo) - created}건).")
    return created


async def run_daily_pipeline(
    retmax_per_category: int = _CATEGORY_RETMAX, categories: list[str] | None = None
) -> list[dict]:
    """수집 -> 한국어 요약 -> 색인을 순서대로 잇는 완결된 배치. 사람은 이 함수(또는 CLI
    `--pipeline`)를 실행 버튼처럼 누르기만 하면 된다. "매일 자동으로 이 명령 자체를
    실행시키는" 스케줄러(cron/Celery beat)는 아직 붙이지 않았다 — 별도 단계다.

    색인은 이 모듈이 하지 않는다. `source/_manifest.yaml`에 선언된 논문 JSON을 매니페스트
    파이프라인이 처리한다 — 예전엔 이 파일에 전용 색인 코드(build_documents/ingest_papers/
    _indexed_pmids)가 따로 있었고, 그게 매니페스트 경로와 **양쪽에서 같은 컬렉션에 써서
    논문이 두 번 들어갔다**(실측: 740편이 1,480건). 색인 경로는 하나뿐이어야 한다."""
    await fetch_and_append_category_papers(retmax_per_category=retmax_per_category, categories=categories)
    await ensure_paper_summaries()
    # 이 배치가 방금 받아온 논문 파일만 골라 색인한다. 컬렉션으로 고르지 않는 이유: 컬렉션은
    # 확장자가 정하므로(sources.collection_for) 논문 JSON과 복약안내서 마크다운이 같은
    # unstructured에 있다 — 컬렉션으로 거르면 논문 배치마다 안내서까지 딸려온다.
    paper_files = {f"{disease}.json" for disease in SUPPORTED_DISEASES}
    return [ingest_source(source) for source in discover() if source.name in paper_files]


async def _main(args: argparse.Namespace) -> None:
    if args.pipeline:
        for result in await run_daily_pipeline(
            retmax_per_category=args.retmax_per_category, categories=args.categories
        ):
            print(result)
        return
    if args.summarize_only:
        created = await ensure_paper_summaries()
        print(f"한국어 요약 {created}건 생성(원본 JSON의 summary_ko 필드에 기록).")
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
        "--summarize-only",
        action="store_true",
        help="한국어 요약 캐시만 채우고 끝낸다(색인 없음). 요약 결과를 먼저 눈으로 검토할 때.",
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="1단계+2단계를 순서대로 모두 실행하는 완결된 배치(매일 수동 실행용).",
    )
    parsed_args = parser.parse_args()
    asyncio.run(_main(parsed_args))
