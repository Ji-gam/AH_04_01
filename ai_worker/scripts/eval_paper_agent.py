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
]


async def run_eval() -> None:
    for item in EVAL_QUESTIONS:
        answer = await ask_paper_agent(item["question"])
        print(f"[{item['disease']}] Q: {item['question']}\nA: {answer}\n")


if __name__ == "__main__":
    asyncio.run(run_eval())
