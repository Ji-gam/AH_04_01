"""
T-LLM-7: 질환 논문 검색 도구(스텁). 실제 논문 API 연동 전까지, 질환별로 미리
저장해 둔 논문 1개(제목+초록)를 돌려주는 자리표시자다. 에이전트가 "부를 수 있는
것"인지를 검증하는 데 목적이 있으며, 실제 검색 로직(PubMed/Semantic Scholar)은
팀 승인 후 이 함수 내부만 교체한다.
"""

import json
from pathlib import Path

from langchain_core.tools import tool

DATA_DIR = Path(__file__).parent.parent / "mock_data_for_papers"

# 에이전트가 넘겨야 하는 정확한 질환 키. 도구 설명(docstring)에도 그대로 노출해
# LLM이 "당뇨병" 같은 변형 표현을 이 중 하나로 정규화하도록 유도한다.
SUPPORTED_DISEASES = ["암", "심장질환", "뇌혈관질환", "당뇨", "간질환"]


@tool
def search_disease_paper(disease: str) -> str:
    """5대 질환 관련 논문 제목과 초록을 검색한다.

    disease 인자는 반드시 다음 5개 중 하나로 정확히 정규화해서 호출한다:
    암, 심장질환, 뇌혈관질환, 당뇨, 간질환.
    예: 사용자가 "당뇨병"이라고 물어도 "당뇨"로, "뇌졸중"이라고 물어도
    "뇌혈관질환"으로 바꿔서 호출한다.
    의학 논문과 무관한 질문(날씨, 잡담 등)에는 이 도구를 호출하지 않는다.
    """
    # disease는 LLM이 산출한 값이라 파일 경로에 그대로 삽입하면 path traversal 위험이 있다.
    # 파일 경로를 조립하기 전에 화이트리스트로 먼저 검증한다.
    if disease not in SUPPORTED_DISEASES:
        return f"'{disease}'에 대한 논문 자료를 찾지 못했습니다. 지원 질환: {', '.join(SUPPORTED_DISEASES)}"

    stub_path = DATA_DIR / f"{disease}.json"
    if not stub_path.exists():
        return f"'{disease}'에 대한 논문 자료를 찾지 못했습니다. 지원 질환: {', '.join(SUPPORTED_DISEASES)}"

    paper = json.loads(stub_path.read_text(encoding="utf-8"))
    return f"제목: {paper['title']}\n초록: {paper['abstract']}"
