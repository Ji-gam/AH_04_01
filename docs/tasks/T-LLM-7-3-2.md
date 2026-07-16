## Task ID: T-LLM-7-3-2 (DUR+논문 통합 RAG 스트리밍 재설계) — 인수인계 문서 (작업 중, 미커밋)

**이 문서는 세션 인수인계용입니다.** 새 세션은 이 문서를 먼저 읽고, `git status`로 아래
"브랜치/커밋 상태"가 맞는지 확인한 뒤 "다음 할 일"부터 이어가면 됩니다.

### 배경 — 왜 이 작업이 시작됐는지

T-LLM-7-3(PR #176, PubMed 논문 RAG)과 T-LLM-7-3-1(PR #178, 채팅 출처 칩 UI)이 이미
`dev`에 머지된 상태에서, 사용자가 그 설계를 재검토하며 지적했다:

> "dur_rag스트리밍이라는게 따로 있는게 이상해. 사용자가 질문을 하면 그 질문에 대한
> 답변을 위해서 rag검색을 하고 해당 청크들을 함께 llm으로 보내는거 아니야? 거기에는
> 당연히 dur, 논문, pdf등 많은 재료들이 다 포함된 검색결과일거고."

기존 구조는 DUR 전용(`/retrieve`, 청크만 반환하고 `app/`가 자체 LLM(`llm_stub.py`)으로
생성)과 논문 전용(`/agent/paper-search`, `ai_worker`가 질환 분류→검색→**자체 답변까지
완결**)이 완전히 분리된 두 파이프라인이었다. 질문 하나가 DUR도 논문도 관련될 수 있는데,
지금 구조는 둘 중 하나만 골라 답하고 나머지를 버렸다 — "진짜 RAG"가 아니라는 지적이
정확했다. 사용자 요청: "중복되는 기능이 남는 것은 싫다. 큰 변화가 있어도 상관없다."

### 최종 합의된 아키텍처

```
사용자 질문 → app/chat_service.py (응급 판정[키워드 전용] + 개인 DUR 경고[SQL 조회]만 처리)
           → ai_worker의 /agent/chat (신규, 스트리밍 단일 엔드포인트)
               1. DUR(dur_rules) + 논문(pubmed_papers) 컬렉션을 "질문 그대로" 벡터 검색
               2. 임계값 통과한 청크가 하나도 없으면 → RAG 컨텍스트 없이 그냥 LLM 답변
               3. 있으면 → 그 청크들 다 합쳐서 LLM에 같이 넣어 답변 생성
               4. 토큰이 나오는 대로 스트리밍 + 출처 목록(sources)
           → app/chat_service.py는 그 스트림을 그대로 중계 + 메시지 저장 + 면책문구 부착
```

**"RAG 필요 여부" 판단에 별도 LLM 분류 없음** — 임계값 통과 청크가 0건이면 자연히
"RAG 없이 그냥 답변"이 된다(DUR이 원래 이렇게 동작했고, 논문도 이번에 질환 사전
분류(`classify_query`)를 없애고 동일하게 맞췄다).

### 브랜치/커밋 상태 — 반드시 먼저 확인할 것

- 브랜치: `feat/T-LLM-7-3-2-unified-rag-streaming` (`origin/dev`에서 분기, `dev`에는
  아직 없음)
- **아직 커밋 0개 — 전부 워킹트리 변경사항(uncommitted).** 새 세션에서 `git status`로
  아래 파일 목록과 일치하는지 먼저 확인.
- `git stash list`에 6개가 쌓여 있음. **`stash@{0}`("unrelated parallel work:
  auto_ingest/raw_data (not mine, do not touch)")은 이 세션 도중 다른 세션/사람의
  작업물을 안전하게 치워둔 것 — 절대 만지지 말 것.** 나머지(`stash@{1}`~`{5}`)는 이
  작업 이전부터 있던 것들로 이번 작업과 무관.

### 삭제된 것 (의도적, 복구 금지)

- `ai_worker/routers/retrieve_router.py` (`/retrieve` 엔드포인트)
- `ai_worker/routers/paper_agent_router.py` (`/agent/paper-search` 엔드포인트)
- `ai_worker/tasks/paper_agent.py` (`classify_query` 기반 질환 분류 전체)
- `ai_worker/scripts/eval_paper_agent.py`, `ai_worker/tests/test_paper_agent.py`
- `app/services/llm_stub.py` (`app/`가 직접 OpenAI를 호출하던 것 — 이제 LLM 호출은
  전부 `ai_worker` 안에서만 일어남)
- `chat_service.py`의 `EmergencyClassification`/`_check_emergency_via_llm`(응급 판정
  LLM 분류 — 아래 "이번 세션에서 고친 것" 3번 참고, 키워드 전용으로 되돌림)
- `AIWorkerGateway`의 `search()`/`ask_paper_agent()`/`retrieve_timeout` 파라미터,
  `config.AI_WORKER_RETRIEVE_TIMEOUT`

### 새로 생긴 것

- `ai_worker/tasks/chat_agent.py` — 핵심 로직. `_search_all()`(DUR+논문 통합 검색),
  `stream_chat_answer()`(프롬프트 조립 + LLM 스트리밍, `{"type":"sources"|"token"}` yield)
- `ai_worker/routers/chat_agent_router.py` — `POST /agent/chat`(`StreamingResponse`).
  키/임베딩 불일치 등 스트림 시작 **전** 확인 가능한 실패만 503으로, 스트림 도중 실패는
  인밴드 `{"type":"error",...}` 청크로(상태 코드 변경 불가하므로)
- `ai_worker/routers/health_router.py` — `/health`만 분리
- `ai_worker/schemas/retrieval_schema.py` — `ChatCompletionRequest`, `SourceRef` 추가.
  `RetrieveRequest`/`RetrieveResponse`/`PaperAgentRequest`/`PaperAgentResponse`/
  `PaperSourceRef` 삭제
- `app/services/ai_worker_gateway.py`의 `stream_chat()` — httpx 스트리밍 클라이언트로
  `/agent/chat` 호출, 한 줄씩 파싱해 그대로 yield
- 프론트: `types.ts`의 `ChatMessageChunk.type`에 `"sources"` 추가(`"paper_answer"`
  삭제), `useChatStream.ts`가 `sources` 청크로 새 어시스턴트 메시지를 열고 `token`이
  이어붙는 방식으로 재작성(`ChatPage.tsx`의 칩 렌더링 자체는 안 바뀜, `m.sources` 그대로 소비)

### 이번 세션에서 실사용 중 발견하고 고친 버그/트레이드오프 (시간 순)

1. **역할 대소문자 버그(치명적)**: `MessageRole.USER`="USER"(대문자)를 그대로 OpenAI
   메시지 role로 보내서, 대화 이력이 있는 **두 번째 턴부터 OpenAI가 400 거부** →
   "[응답이 중단되었습니다]"가 대부분 질문에서 떴던 원인. `chat_service.py`에서
   `m.role.value.lower()`로 수정 완료 + 회귀 테스트 추가(`test_stream_reply_lowercases_history_roles_for_openai_compatibility`).
2. **논문 유사도 임계값 너무 헐거움**: `PAPER_SIMILARITY_THRESHOLD` 1.6→**1.5**.
   실측: 관련 질문 1.06~1.44 vs 잡담("안녕" 등) 1.57~1.75 — 1.5가 안전하게 가른다.
3. **응급 판정 LLM 분류 제거(사용자 결정)**: 오늘 오전 별도 세션이 추가했던 LLM 기반
   응급 분류(매 턴 ~1.3초 직렬 대기, `_check_emergency_via_llm`)를 **키워드 전용으로
   되돌림**. 사용자 판단: "키워드 1000개 붙여도 1.3초 안 걸린다, 속도가 더 중요하다."
   트레이드오프: 키워드 목록에 없는 파라프레이즈 표현으로 응급이 누락될 위험은 이제
   순수 `safety_service._EMERGENCY_KEYWORDS`에만 의존 — 필요시 이 키워드 목록을
   보강하는 쪽으로 대응(LLM 재도입이 아니라).
4. **의료관련성 분류 조건부화**: `sources`(DUR/논문 출처)나 `injected_context`(개인
   DUR 경고)가 하나도 없으면 LLM 호출(~1초) 없이 `_is_medical_related_fallback`
   키워드 폴백만 사용. 있으면 정밀도를 위해 `_check_if_medical_related_via_llm` 사용.
   **주의**: `safety_service._MEDICAL_KEYWORDS`에 "약"/"병"/"먹어"/"먹는" 같은 아주
   흔한 단어가 있어 출처 없는 대화에서 오탐 가능성이 있음 — 사용자가 트레이드오프로
   명시 수용(정밀도보다 속도 우선, 오늘 오전 커밋이 고치려던 문제가 일부 되살아날 수
   있음을 인지한 상태).
5. **DUR이 완전히 무관한 성분과 매칭되는 문제(구조적)**: DUR 문서가 전부 "의약품
   성분 [X]는 Y 약물입니다..." 형태의 짧은 템플릿 문장이라, 성분명이 쿼리에 없으면
   임계값과 무관하게 노이즈 매칭 발생. 실측: "당뇨병 진단받았는데 어떡하죠"(무관)가
   1.271점, "타이레놀 먹어도 되나요"(진짜 약물질문, 브랜드명)가 1.533점 — **무관한
   질문이 더 좋은 점수**를 받아 임계값으로는 절대 못 거름. **해결**:
   `retrieve_service.search_documents()`가 이제 쿼리에서 성분명이 식별 안 되면 검색
   자체를 생략(빈 리스트, Chroma 호출도 안 함). **받아들인 트레이드오프(사용자 승인)**:
   브랜드명("타이레놀")이나 부분매칭 실패("졸피뎀"+다른 단어) 케이스는 DUR 결과 0건이
   됨 — 성분명 매칭 로직 자체(브랜드명 매핑 등) 개선은 후속 작업으로 명시적으로 미룸
   (메모리 `project_dur_ingredient_matching_gap.md` 참고).
6. **응급 fallback 문구 교체**: 사용자가 제공한 위기상담 문구(자살예방상담전화 109,
   정신건강상담전화 1577-0199, 생명의 전화 1588-9191)로
   `safety_service.EMERGENCY_FALLBACK_MESSAGE` 전체 교체.

### 검증 상태

- `uv run pytest ai_worker/tests` — **48 passed**
- `uv run pytest app/tests/services/test_chat_service.py app/tests/services/test_ai_worker_gateway.py app/tests/services/test_safety_service.py` — 개별 실행 전부 통과(14+개)
- 실제 로컬 uvicorn(`ai_worker`, 임시 포트 8099)으로 `/agent/chat` 직접 호출해 검증:
  "안녕"(0출처, 무관 청크 없음, 1.5초대), "당뇨병 혈당관리"(6출처, 정상 답변,
  6초대) — 둘 다 실제 Chroma+OpenAI로 확인함
- `ruff check`/`ruff format --check`/`mypy`는 매 파일 수정 직후마다 통과 확인했으나,
  **최종적으로 전체 대상(`ai_worker/ app/`)으로 한 번에 다시 확인 안 함**
- **아직 안 한 것**:
  1. `uv run pytest`(app 전체, 이번 최종 상태 기준) — 직전 세션 유사 상태에서 한 번
     돌렸을 때 무관한 OCR 테스트 3건(`test_medication_apis.py`, CLOVA 키 없음/타이밍
     이슈)만 실패했었음(이번 변경과 무관). 이번 최종 상태로 다시 실행 필요.
  2. 프론트 `npx tsc -b`/`eslint`/`prettier --check` 최종 재확인(마지막 확인 이후
     `chat_service.py` 등을 여러 번 더 고쳤음)
  3. 프론트+백엔드+ai_worker 전부 띄운 상태에서 브라우저로 실제 클릭 확인(1회는
     필요 — 기능 동작 확인 목적이지 비주얼 리뷰 목적 아님)

### 다음 할 일 (우선순위 순)

1. `git status`로 브랜치 상태가 이 문서와 일치하는지 확인
2. `uv run pytest`(전체) + `uv run pytest ai_worker/tests` 재실행 → 회귀 없는지 최종 확인
3. `uv run ruff check .`/`ruff format --check .`/`mypy app/ ai_worker/` 전체 최종 확인
4. 프론트 `tsc -b`/`eslint`/`prettier --check` 최종 확인
5. 실제 서버 띄워서 브라우저로 최소 1회 수동 확인(응급 메시지, 출처 칩, 일반 대화 전부)
6. 커밋 + PR(`dev` 기준). **PR 본문에 반드시 포함**:
   - 삭제 목록(`/retrieve`, `/agent/paper-search`, `llm_stub.py`, 응급 LLM 분류 등)과
     "왜 삭제했는지"
   - 받아들인 트레이드오프 3가지(위 3, 4, 5번) — 팀이 나중에 "왜 이렇게 됐지?" 하지
     않도록 명시
7. PR 본문/코멘트에 "[구현완료, merge 요청]" 표기(팀 컨벤션)

### 알아두면 좋은 것

- **전체 테스트는 기능이 로컬에서 실제로 완전히 동작한다고 확신되기 전까지 제안하지
  말 것** — 이번 세션 사용자 피드백. 목(mock) 기반 단위테스트가 전부 통과해도 실제
  RAG 품질/지연시간 문제는 못 잡는다(이번에 5개 버그를 전부 실제 서버 호출로 잡음).
- 사용자는 genie0320/박지은, D스쿼드(ai_worker/RAG/챗봇 담당), 병행 세션 습관 있음
  (다른 세션 작업물이 워킹트리에 섞여 있을 수 있으니 항상 `git status`부터 확인).
- `ai_worker/services/retrieve_service.py`의 `db_holder` 구조는 절대 변경 금지(다른
  곳에서 이름으로 재노출 + 테스트가 직접 조작).
