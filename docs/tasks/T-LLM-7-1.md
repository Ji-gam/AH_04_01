## Task ID: T-LLM-7-1 (Query Rewriting + 프롬프트 다듬기 — III단계: 질문을 다듬어보기)

### 참조
- 배경: "ai_worker · RAG 원정기 v2" 로드맵 III단계. T-LLM-7(I단계, PR #53)·T-LLM-8(II단계, PR #60)
  이 선행 완료됨. 앞으로 로드맵 단계는 `T-LLM-7-N` 하위번호로 통일(T-LLM-8은 이미 별도
  번호로 merge된 예외).
- T-LLM-8 미니 평가셋에서 발견: "뇌졸중 치료는 빠를수록 좋다는 게 사실이야?"(뇌혈관질환
  변형 표현), "지방간 진행 여부를 검사 없이도 알 수 있어?"(간질환 변형 표현) 두 질문이
  도구 호출 없이 "범위 밖"으로 거부됨.

### 목표
- 도구를 부르기 전에 질문을 정규화하는 별도 LLM 전처리 단계(Query Rewriting)를 추가해
  변형 표현 인식 일관성을 개선한다.
- 이 단계는 "지금 5개 질환 중 하나로 강제 매핑"이 아니라 "질문에 언급된 질환/증상의
  표준 명칭이 뭐야?"를 여는 방식으로 설계한다 — 나중에 질환이 늘어나도(ADHD, 비만 등)
  이 프롬프트 자체는 안 건드려도 되게 하기 위함(질환 목록은 `SUPPORTED_DISEASES`에서
  동적으로 interpolation).

### 완료 정의 (Definition of Done)
- [ ] `rewrite_disease_query(question: str) -> str | None`이 `ai_worker/tasks/paper_agent.py`에
      존재하고, 언급된 질환/증상이 없으면 `None`을 반환한다
- [ ] `ask_paper_agent()`가 이 결과를 힌트로 붙여 기존 에이전트에 전달한다(정규화 결과가
      현재 지원 5개 밖이어도 그대로 통과 — 화이트리스트 필터링을 이 단계에서 하지 않음)
- [ ] `OPENAI_API_KEY` 미설정 시 기존 관례(`GenerationUnavailableError`)를 그대로 따른다
- [ ] `ai_worker/scripts/eval_paper_agent.py`에 변형 표현 케이스를 추가하고 재실행해,
      "뇌졸중"/"지방간" 케이스가 개선되는지(또는 여전히 실패하면 그 결과를) 육안 확인한다
- [ ] (공통) 새 코드에 대해 ruff/mypy 통과, 기존 `ai_worker/tests` 전부 통과

### 허용 경로
```
ai_worker/tasks/paper_agent.py
ai_worker/tests/test_paper_agent.py
ai_worker/scripts/eval_paper_agent.py
docs/tasks/T-LLM-7-1.md  (이 파일의 "완료 보고" 섹션만)
```

### 금지 경로
```
ai_worker/tools/paper_search.py  (SUPPORTED_DISEASES/도구 자체는 참조만, 수정 안 함)
ai_worker/core/**
ai_worker/main.py  (엔드포인트 계약 변경 없음 — /agent/paper-search 그대로)
```

### 의존하는 공유 계약 (읽기만 가능)
- `ai_worker/tools/paper_search.py`의 `SUPPORTED_DISEASES`

### 자율 판단 허용 범위
- rewrite 프롬프트 문구, 힌트를 원본 질문에 붙이는 정확한 포맷 — 자율 결정.

### 반드시 멈춰야 하는 경우
- 화이트리스트 밖 질환(ADHD 등)에 대한 실제 스텁 데이터 추가가 필요해 보이는 경우
  (이번 스코프 아님 — 카탈로그 확장은 별도 작업)

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/61-query-rewriting`
