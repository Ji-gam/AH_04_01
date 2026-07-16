"""
T-LLM-8: `/agent/paper-search`(T-LLM-7) 미니 평가셋.

pytest 스위트에는 포함하지 않는다 — 사람이 답변 품질을 눈으로 비교하기 위한
수동 실행 스크립트다. `load_dotenv()`로 로컬 env 파일의 LANGCHAIN_* 값을
프로세스 환경변수로 끌어와야 LangSmith 트레이싱이 켜진다(pydantic-settings는
os.environ을 건드리지 않는다).

실행: `uv run python -m ai_worker.scripts.eval_paper_agent`
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from ai_worker.services.paper_retrieve_service import ensure_paper_db  # noqa: E402
from ai_worker.tasks.paper_agent import ask_paper_agent  # noqa: E402

# 질환 5개 × (정확 표현 1 + 변형 표현 1) = 10문항.
EVAL_QUESTIONS = [
    {"disease": "암", "question": "암 검진과 조기진단의 관계가 어떻게 돼?"},
    {"disease": "암", "question": "암 검진율이 높아지면 생존율도 올라가?"},
    {"disease": "심장질환", "question": "심장질환 재발 예방에 대한 논문 알려줘"},
    {"disease": "심장질환", "question": "아스피린과 스타틴을 같이 먹으면 심근경색 재발률이 줄어?"},
    {"disease": "뇌혈관질환", "question": "뇌혈관질환 관련 최신 연구 있어?"},
    {"disease": "뇌혈관질환", "question": "뇌졸중 치료는 빠를수록 좋다는 게 사실이야?"},
    {"disease": "당뇨", "question": "당뇨 논문 알려줘"},
    {"disease": "당뇨", "question": "당뇨병 혈당 관리에 대한 연구 결과 있어?"},
    {"disease": "간질환", "question": "간질환 진단 관련 논문 알려줘"},
    {"disease": "간질환", "question": "지방간 진행 여부를 검사 없이도 알 수 있어?"},
    # T-LLM-7-1: Query Rewriting 도입 후 변형 표현 정규화 개선 확인용 추가 케이스.
    {"disease": "심장질환", "question": "심장마비 재발을 줄이는 약물 조합이 있어?"},
    {"disease": "미지원(ADHD)", "question": "ADHD 관련 논문 있어?"},
    # T-LLM-7-2: 신체 장기를 빗댄 관용구 — 질환 단어가 있어도 도구를 부르면 안 되는 케이스.
    {"disease": "관용구(오탐 방지 확인용)", "question": "나 심장이 너무 쫄려..."},
    {"disease": "관용구(오탐 방지 확인용)", "question": "요즘 너무 간이 콩알만해지는 일이 많아"},
    {"disease": "관용구(오탐 방지 확인용)", "question": "시험 때문에 심장 떨려 죽겠어"},
    {"disease": "관용구(오탐 방지 확인용)", "question": "아 진짜 간 떨어질 뻔했네"},
]


async def run_eval() -> None:
    db = ensure_paper_db()
    for item in EVAL_QUESTIONS:
        answer, sources = await ask_paper_agent(item["question"], db)
        source_lines = "\n".join(f"  - {s.name} ({s.url})" for s in sources)
        print(f"[{item['disease']}] Q: {item['question']}\nA: {answer}\n출처:\n{source_lines}\n")


if __name__ == "__main__":
    asyncio.run(run_eval())
