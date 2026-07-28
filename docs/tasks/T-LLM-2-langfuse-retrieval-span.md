## Task ID: T-LLM-2-langfuse-retrieval-span (T-LLM-2 "AI 챗봇 상담" 하위 작업 — Langfuse 관측 2단계: RAG 검색 span)

> 작성자: 박지은(D스쿼드, `chat_*`/`ai_worker/` 소유). **이 문서는 착수 전 계획(plan)이다.**
> `T-LLM-2-langfuse-observability`(1단계, 병합됨)의 "미결/후속" 항목 중 (c)를 이어서 처리한다.
> 리더 승인 불필요 — 전부 `ai_worker/` 내부 파일, Chroma 재적재·docker-compose 변경 없음.

### 참조
- PRD: F-LLM-2 / TRD: T-LLM-2 / REQ: REQ-BOT-001~005
- 선행 작업: `docs/tasks/T-LLM-2-langfuse-observability.md`(1단계, 병합됨) — LLM 호출 2곳(`chat_agent.py`,
  `generate_structured.py`)에 콜백 핸들러만 연결했고, RAG 검색 단계는 trace에 안 보였다(2단계로 분리 예고).
- 관련: `ai_worker/services/retrieve_service.py`(`search_documents`), `ai_worker/services/paper_retrieve_service.py`
  (`search_papers`), `ai_worker/tasks/chat_agent.py`(`stream_chat_answer`), `ai_worker/core/observability.py`

### 배경
1단계 이후 챗봇 답변(LLM 호출)은 trace로 잡히지만, 그 답변이 **어떤 문서를 왜 가져와서** 나왔는지는
안 보인다 — DUR 필터 매칭 결과, 후보 문서 점수, 임계값 통과/탈락 여부가 전부 `logger.info`
(`DEBUG_SCORE:` 등)로만 남아 Langfuse 밖에 있다. RAG 품질 디버깅(예: T-LLM-2-rag-brand-name-bridge류
버그의 재발 확인)에 가장 값진 부분이 빠져 있는 상태다.

### 목표
- `search_documents`/`search_papers` 호출을 현재 활성 trace의 **하위 span**으로 기록한다
  (Langfuse v4 `as_type="retriever"` — 검색 전용 관측 타입, UI에서 별도로 구분돼 보인다).
- span에 입력(질의, 매칭된 필터/질환)과 출력(반환 청크 수, 후보 수, 임계값)을 남긴다.
- 검색 span과 기존 1단계 LLM generation이 **같은 trace**로 묶이게 한다 — 따로 떨어진 trace 두 개가
  아니라, 한 번의 챗봇 응답이 trace 하나 안에 "검색 → 생성" 순서로 보여야 실사용 가치가 있다.
- 키 미설정 시(로컬/CI) 기존과 동일하게 완전 no-op — 1단계와 같은 원칙.

### 방식 (SDK API 실측 확인됨)
Langfuse v4는 `from langfuse import get_client`가 **1단계 `CallbackHandler`와 같은 전역 싱글톤**을
돌려준다(`inspect.signature`로 확인). 즉 `client.start_as_current_observation(name=..., as_type="retriever")`로
연 span과, 그 안에서 실행되는 `llm.astream(config={"callbacks": [handler]})`가 만드는 generation이
자동으로 같은 trace에 묶인다 — 별도의 trace_id 수동 전달이 필요 없다.

(`start_as_current_span`은 존재하지 않는다 — 1단계 검증 스크립트에서 이미 한 번 틀렸던 이름이라
다시 실수하지 않도록 여기 기록한다. 실제 메서드는 `start_as_current_observation`.)

- `ai_worker/core/observability.py`에 추가:
  - `get_langfuse_client()`: 키 미설정 시 `None`. 설정돼 있으면 env 브릿지 후 `get_client()` 반환.
    (env 브릿지 로직은 `get_langfuse_handler()`와 공유 — 어느 쪽이 먼저 불려도 안전하게 중복 실행)
  - `observe_span(name, as_type="span", **input_kwargs)`: 컨텍스트 매니저. 클라이언트가 없으면
    `None`을 yield하는 no-op, 있으면 `client.start_as_current_observation(...)`을 그대로 감싼다.
    호출부는 `with observability.observe_span(...) as span:` 하나만 쓰고, `span`이 `None`일 수 있다는
    것만 알면 된다(1단계의 `if handler:` 패턴과 동일한 선택적 계측 원칙).
- `chat_agent.stream_chat_answer()`: 검색(`_search_all`)과 LLM 스트리밍을 감싸는 루트 span
  (`as_type="span"`, name="chat_turn")을 추가해 그 하위로 검색 span과 generation이 함께 묶이게 한다.
- `retrieve_service.search_documents()` / `paper_retrieve_service.search_papers()`: 각자
  `observe_span(..., as_type="retriever")`로 자기 검색 로직을 감싸고, 끝에 `span.update(output=...,
  metadata=...)`로 결과를 남긴다(span이 `None`이면 건너뜀).

### 환자 텍스트 마스킹 (미결 항목 처리 결과)
1단계 계획 문서의 "미결/확인 필요" 항목 — 사용자 확인 결과: **지금은 마스킹 없이 그대로 전송**
(POC 학원 제출용 범위, [[project_poc_academy_submission_nature]] 참고). 실사용자 데이터가 붙는
시점에 재검토한다. 이번 작업 범위에 마스킹 구현은 포함하지 않는다.

### 완료 정의 (Definition of Done)
- [ ] `observability.py`에 `get_langfuse_client()`/`observe_span()` 추가, 키 미설정 시 no-op 확인
- [ ] `search_documents()`가 `as_type="retriever"` span으로 계측되고, 필터/후보수/반환수/임계값이
      output·metadata로 남는다
- [ ] `search_papers()`도 동일하게 계측된다(질환 매칭 결과 포함)
- [ ] `stream_chat_answer()`에 루트 span 추가 — 실 키로 수동 확인 시 대시보드에서 검색 span과
      LLM generation이 **하나의 trace** 아래 부모-자식으로 보인다
- [ ] 키 미설정 시(로컬/CI) 챗봇 동작 무회귀 — conftest의 `_disable_langfuse`가 `get_langfuse_client`도
      막도록 확장
- [ ] (공통) 테스트 함수명 영문, ruff/mypy 통과(CI 게이트: `ruff check` + `ruff format --check` + `mypy`)

### 허용 경로
```
ai_worker/core/observability.py
ai_worker/tasks/chat_agent.py
ai_worker/services/retrieve_service.py
ai_worker/services/paper_retrieve_service.py
ai_worker/tests/**
docs/tasks/T-LLM-2-langfuse-retrieval-span.md  (이 파일)
```

### 금지 경로
```
docker-compose.yml / infra/**
app/**
frontend/**
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 자율 판단 허용 범위
- span에 남길 정확한 input/output/metadata 필드 구성, 루트 span의 이름/as_type, 헬퍼 함수 시그니처 — 자율 결정.

### 반드시 멈춰야 하는 경우
- 검색 span과 LLM generation을 같은 trace로 묶으려면 사용자 대면 응답 스키마나 스트리밍 이벤트
  포맷을 바꿔야 한다는 결론이 나면 — 진행하지 말고 보고.

### 완료 보고 (구현 후 작성)
_구현 후 채움._
