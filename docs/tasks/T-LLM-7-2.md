## Task ID: T-LLM-7-2 (판단 결정론화 — Router 분리 + 강제 도구 호출)

### 참조
- 배경: T-LLM-7-1(Query Rewriting, PR #62)에서도 "지방간", "심장마비" 같은 변형 표현이
  확률적으로만 개선되는 문제가 남아있었음.
- 웹 리서치로 확인한 근거: agentic RAG의 "Router" 컴포넌트 분리 패턴, forced tool
  calling(`tool_choice`)이 결정론적 파이프라인에 적합하다는 사례.
  - [Agentic RAG Series - Query Routing/Rewriting](https://sajalsharma.com/posts/comprehensive-agentic-rag/)
  - [Build a custom RAG agent with LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
  - [Reliable Tool Calling and Structured Outputs](https://changegamer.ai/resources/reliable-tool-calling)

### 목표
- "질환 인식"과 "도구 호출 여부 판단"을 하나의 LLM 판단으로 뭉뚱그리지 않고,
  구조화 출력(`disease`, `is_information_request`) 2축으로 분리한다.
- 두 조건이 모두 참일 때만 코드에서 결정론적으로 `search_disease_paper`를 호출한다
  (LLM이 다시 "부를지 말지" 재판단하지 않음).
- 신체 장기를 빗댄 한국어 관용구("심장이 쫄리다", "간이 크다" 등)를 실제 질환 언급과
  구분한다.

### 완료 정의 (Definition of Done)
- [ ] `QueryClassification`(disease: str|None, is_information_request: bool) 구조화 출력
      분류기가 존재한다
- [ ] 분류 결과가 (유효한 disease 존재 AND is_information_request=True)일 때만
      `search_disease_paper`가 호출된다 — 그 외엔 도구 호출 없이 정중한 안내
- [ ] `create_agent`(LangGraph) 기반 에이전트 루프는 제거되고, "분류 → (결정론적 검색) →
      답변 생성"의 단순 파이프라인으로 대체된다
- [ ] 관용구 4종 이상이 회귀 테스트(mock)로 고정되고, 실제 API 키로 육안 검증됨
- [ ] T-LLM-7-1에서 실패했던 "지방간"/"심장마비" 케이스가 실제 API 키 실행에서 해결됨을 확인
- [ ] `docs/tasks/_active.json`에서 이미 merge된 `T-LLM-7-1` 클레임을 이번 PR에서 함께 해제
- [ ] (공통) ruff/mypy 통과, `ai_worker/tests` 전부 통과(PR 직전 1회만 실행)

### 허용 경로
```
ai_worker/tasks/paper_agent.py
ai_worker/tests/test_paper_agent.py
ai_worker/scripts/eval_paper_agent.py
docs/tasks/T-LLM-7-2.md  (이 파일의 "완료 보고" 섹션만)
docs/tasks/_active.json  (T-LLM-7-1 해제 + T-LLM-7-2 등록/해제)
```

### 금지 경로
```
ai_worker/tools/paper_search.py  (참조만, 수정 안 함)
ai_worker/core/**
ai_worker/main.py  (엔드포인트 계약 변경 없음)
```

### 자율 판단 허용 범위
- 분류 프롬프트 문구, 답변 생성 프롬프트 문구, 관용구 예시 목록 — 자율 결정.

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/64-router-classification`
