"""
T-LLM-7-3: 질환 논문 검색 도구. PubMed E-utilities(esearch → efetch)로 5대 질환
관련 최신 임상연구 논문을 검색해 제목/초록/출처(PMID)를 반환한다.
"""

import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

from ai_worker.core.config import settings

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# 에이전트가 넘겨야 하는 정확한 질환 키. 도구 설명(docstring)에도 그대로 노출해
# LLM이 "당뇨병" 같은 변형 표현을 이 중 하나로 정규화하도록 유도한다.
SUPPORTED_DISEASES = ["암", "심장질환", "뇌혈관질환", "당뇨", "간질환"]

# 질환별 PubMed 검색어(MeSH). 답변 프롬프트가 "단일 연구 결과임을 밝히세요"라고
# 지시하므로 Clinical Trial/RCT로 한정하고 Review(합성 결론이라 수치 인용에 안 맞음)는
# 제외한다.
_TRIAL_FILTER = "(Clinical Trial[Publication Type] OR Randomized Controlled Trial[Publication Type])"
_DISEASE_SEARCH_TERMS: dict[str, str] = {
    "암": f'"Neoplasms"[MeSH Terms] AND {_TRIAL_FILTER}',
    "심장질환": f'"Heart Diseases"[MeSH Terms] AND {_TRIAL_FILTER}',
    "뇌혈관질환": f'"Cerebrovascular Disorders"[MeSH Terms] AND {_TRIAL_FILTER}',
    "당뇨": f'"Diabetes Mellitus"[MeSH Terms] AND {_TRIAL_FILTER}',
    "간질환": f'"Liver Diseases"[MeSH Terms] AND {_TRIAL_FILTER}',
}


class PaperSearchUnavailableError(Exception):
    """PubMed 요청 실패(네트워크·타임아웃·비정상 응답·응답 파싱 오류) 시 발생."""


def _not_found_message(disease: str) -> str:
    return f"'{disease}'에 대한 논문 자료를 찾지 못했습니다. 지원 질환: {', '.join(SUPPORTED_DISEASES)}"


async def _esearch(client: httpx.AsyncClient, term: str) -> list[str]:
    params: dict[str, str] = {"db": "pubmed", "term": term, "retmax": "5", "sort": "date", "retmode": "json"}
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    response = await client.get(f"{_EUTILS_BASE}/esearch.fcgi", params=params)
    if response.status_code != 200:
        raise PaperSearchUnavailableError(f"PubMed esearch 실패(status={response.status_code})")
    result: list[str] = response.json().get("esearchresult", {}).get("idlist", [])
    return result


async def _efetch(client: httpx.AsyncClient, pmids: list[str]) -> str:
    params: dict[str, str] = {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
    if settings.PUBMED_API_KEY:
        params["api_key"] = settings.PUBMED_API_KEY
    response = await client.get(f"{_EUTILS_BASE}/efetch.fcgi", params=params)
    if response.status_code != 200:
        raise PaperSearchUnavailableError(f"PubMed efetch 실패(status={response.status_code})")
    return response.text


def _flatten_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def _parse_articles(xml_text: str) -> list[dict[str, str]]:
    """efetch XML을 파싱해 초록이 있는 논문만 최신순 그대로 반환한다."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise PaperSearchUnavailableError("PubMed 응답(XML) 파싱에 실패했습니다.") from e

    articles = []
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


@tool
async def search_disease_paper(disease: str) -> str:
    """5대 질환 관련 최신 임상연구 논문 제목과 초록을 PubMed에서 검색한다.

    disease 인자는 반드시 다음 5개 중 하나로 정확히 정규화해서 호출한다:
    암, 심장질환, 뇌혈관질환, 당뇨, 간질환.
    예: 사용자가 "당뇨병"이라고 물어도 "당뇨"로, "뇌졸중"이라고 물어도
    "뇌혈관질환"으로 바꿔서 호출한다.
    의학 논문과 무관한 질문(날씨, 잡담 등)에는 이 도구를 호출하지 않는다.
    """
    # disease는 LLM이 산출한 값이라, 화이트리스트 밖 값은 PubMed에 질의하지 않고
    # 여기서 바로 걸러낸다(불필요한 외부 호출·쿼터 소모 방지).
    search_term = _DISEASE_SEARCH_TERMS.get(disease)
    if search_term is None:
        return _not_found_message(disease)

    try:
        async with httpx.AsyncClient(timeout=settings.PUBMED_TIMEOUT) as client:
            pmids = await _esearch(client, search_term)
            if not pmids:
                return _not_found_message(disease)
            xml_text = await _efetch(client, pmids)
    except httpx.HTTPError as e:
        raise PaperSearchUnavailableError("PubMed 요청 중 네트워크 오류가 발생했습니다.") from e

    articles = _parse_articles(xml_text)
    if not articles:
        return _not_found_message(disease)

    paper = articles[0]
    return (
        f"제목: {paper['title']}\n"
        f"초록: {paper['abstract']}\n"
        f"출처: https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/ (PMID: {paper['pmid']})"
    )
