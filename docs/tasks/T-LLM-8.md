## Task ID: T-LLM-8 (LangSmith 연결 + 미니 평가셋 — II단계: 보고 재는 습관 들이기)

### 참조
- 배경: "ai_worker · RAG 원정기 v2" 로드맵 II단계. T-LLM-7(질환 논문 검색 에이전트, PR #53)이
  선행 완료됨.

### 목표
- LangSmith로 에이전트의 사고 과정(도구 호출 여부/입력/출력)이 눈에 보이게 한다.
- "좋아졌다"를 감이 아니라 눈으로 확인할 수 있도록, T-LLM-7의 `/agent/paper-search`에 대한
  미니 평가셋(질환 5개 × 2문항 = 10개)을 만든다.

### 완료 정의 (Definition of Done)
- [ ] `LANGCHAIN_TRACING_V2`/`LANGCHAIN_API_KEY`/`LANGCHAIN_PROJECT`가 개인 로컬 env 파일에
      설정되어 있다(git에 커밋되지 않음 — `envs/.local.env`는 추적 대상 아님)
- [ ] `ai_worker/scripts/eval_paper_agent.py`가 존재하며, 질환 5개(암/심장질환/뇌혈관질환/당뇨/
      간질환) 각각 정확 표현 1개 + 변형 표현 1개(예: "당뇨병")로 총 10개 질문을 `ask_paper_agent()`에
      통과시켜 질문/답변을 출력한다
- [ ] 스크립트를 1회 로컬 실행해 LangSmith 프로젝트(`ai-health-ai-worker`)에 10건의 트레이스가
      찍히는 것을 육안으로 확인한다
- [ ] (공통) 새 코드에 대해 ruff/mypy 통과 (pytest 스위트에는 포함하지 않음 — 수동 실행 스크립트)

### 허용 경로
```
ai_worker/scripts/**
envs/.local.env  (LANGCHAIN_* 키만 추가, git 비추적 파일)
docs/tasks/T-LLM-8.md  (이 파일의 "완료 보고" 섹션만)
```

### 금지 경로
```
ai_worker/tasks/paper_agent.py, ai_worker/tools/**  (T-LLM-7 로직 변경 금지, 평가 스크립트는 이를 그대로 호출만 함)
ai_worker/core/**
docker-compose.yml
```

### 의존하는 공유 계약 (읽기만 가능)
- `ai_worker/tasks/paper_agent.py`의 `ask_paper_agent()` — 평가 대상 함수, 시그니처 변경 없이 그대로 호출

### 자율 판단 허용 범위
- 평가 질문 문구, 스크립트 출력 포맷, LangSmith 프로젝트명 — 전부 자율 결정.

### 반드시 멈춰야 하는 경우
- LangSmith Dataset/Evaluation API로 확장이 필요해 보이는 경우(이번 스코프 아님, 로컬 스크립트로
  한정하기로 확정됨)

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/59-langsmith-eval-set`
