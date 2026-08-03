# T-LLM-2-langfuse-user-feedback — 챗봇 답변 사용자 피드백 수집 → 저장 → 개선 루프

> **작성 목적**: 이 문서만 읽고 다른 세션에서 바로 착수할 수 있게 쓴 작업지시서다.
> 코드 사실관계는 2026-08-03 기준 실제 파일을 읽고 확인했다(경로·함수명·리비전 번호 모두 실측).

---

## 1. 배경 — 왜 지금 이걸 하는가

대회 평가기준 **3-4번 항목**이 다음과 같다:

| 점수 | 기준 |
|---|---|
| **5** | 사용자 피드백 수집 → 저장 → **개선 또는 재학습 구조까지** 구현하였다 |
| 4 | 피드백 수집 기능을 구현하였다 |
| 3 | 단순 의견 입력 기능만 존재한다 |
| 0 | 피드백 구조가 없다 |

현재 상태: **0점.** `feedback` 전수 검색 결과 나오는 것은 정다이님의 주간 순응도 알림(`adherence_feedback_day_of_week`)뿐이고, **챗봇 답변 품질에 대한 피드백 기능은 존재하지 않는다.**

반면 유리한 조건이 이미 갖춰져 있다:
- `T-LLM-2-langfuse-observability`(1단계)와 `T-LLM-2-langfuse-retrieval-span`(2단계)로 **Langfuse 계측이 이미 붙어 있다.**
- Langfuse는 trace에 점수를 붙이는 `create_score()` API를 제공한다 → 피드백을 trace와 함께 저장하면 "수집 → 저장"이 자연스럽게 완성된다.
- 지난 작업에서 "trace 기반 정량 개선은 다음 과제로 남김"이라고 한계로 적어둔 부분이 **바로 이 항목의 5점 조건**이다.

**목표는 4점이 아니라 5점이다.** 즉 버튼만 붙이고 끝내면 안 되고, **낮은 점수를 받은 trace를 실제로 검토해 프롬프트/임계값을 고친 사례를 최소 1건 만들어 문서에 남겨야 한다**(8단계).

---

## 2. 확인된 현재 구조 (실측)

### 요청 경로
```
frontend/src/pages/ChatPage/ChatPage.tsx
  → frontend/src/hooks/useChatStream.ts
  → frontend/src/api/chatApi.ts
  → POST /api/v1/chat/sessions/{session_id}/messages   (app/apis/v1/chat_routers.py:50)
  → ChatService.stream_reply                            (app/services/chat_service.py:114)
  → _run_detached → _generate                           (chat_service.py:143, 158)
  → AIWorkerGateway.stream_chat                         (app/services/ai_worker_gateway.py:46)
  → POST {ai_worker}/agent/chat                         (ai_worker/main.py)
  → stream_chat_answer                                  (ai_worker/tasks/chat_agent.py:116)
      └ observe_span("chat_turn")  ← ★ Langfuse trace가 여기서 생성된다
```

### 핵심 사실 4개

1. **Langfuse trace는 `ai_worker` 안에서 생성된다.** `chat_agent.py:129`의 `observability.observe_span("chat_turn", ...)` 루트 span이 그것이고, 검색 span과 LLM generation이 모두 그 하위로 묶인다. 즉 **trace_id를 알고 있는 곳은 ai_worker뿐**이고, 피드백을 받는 곳은 `app`이다 → 이 간극을 잇는 것이 이 작업의 유일한 난점이다.

2. **`AIWorkerGateway.stream_chat`은 청크를 필터링하지 않는다.** `ai_worker_gateway.py:75-81`이 `yield json.loads(line)`로 전부 그대로 통과시킨다 → **새 청크 타입을 추가해도 게이트웨이는 수정 불필요.**

3. **`ChatService._generate`는 화이트리스트로 걸러낸다.** `chat_service.py:187-202`가 `if chunk["type"] == "token" / elif "sources" / elif "error"` 구조라 **모르는 타입은 조용히 버려진다** → 여기는 반드시 수정해야 한다.

4. **`ChatMessage`에 id는 있지만 API로 안 나간다.** `app/models/chat.py`의 `ChatMessage.id`는 존재하는데, `ChatMessageResponse`(`app/dtos/chat.py`)에는 `id` 필드가 없다(`role/content/sources/disclaimer/created_at`만). 스트리밍 응답도 message id를 주지 않는다 → **피드백을 어느 메시지에 붙일지 지정할 방법이 현재 없다.** 이것도 만들어야 한다.

### 검증된 Langfuse API (langfuse 4.14.1 설치 확인)
```python
Langfuse.get_current_trace_id() -> str | None      # 활성 span 안에서 현재 trace id
Langfuse.create_score(*, name, value, trace_id=None, data_type=None, comment=None, ...) -> None
```

### 마이그레이션 현재 최신
```
0061_add_marketing_consent_revoked_at.py   ← 최신
```
→ 이번 작업은 **0062**. ⚠️ **아래 4단계의 경고를 반드시 읽어라.**

---

## 3. 설계 결정 (이대로 구현, 임의 변경 시 사유를 문서에 남길 것)

### 결정 1 — trace_id는 프론트에 노출하지 않는다
ai_worker → app 까지만 내려보내 **`chat_messages.trace_id` 컬럼에 저장**하고, 프론트는 `message_id`만 다룬다. 피드백 요청이 오면 서버가 message_id → trace_id를 조회해 Langfuse에 점수를 보낸다.

*이유*: 관측 인프라의 내부 식별자를 클라이언트에 내보낼 이유가 없고(수정·위조 가능), 프론트는 "이 답변이 좋았다"만 알면 된다. 계층 경계를 지키는 쪽.

### 결정 2 — 피드백은 별도 테이블에 저장한다
`chat_messages`에 컬럼을 더하지 않고 **`chat_message_feedbacks` 테이블 신설.**

*이유*: (a) `chat_messages`는 "대화 기록"이라는 단일 책임을 유지, (b) comment(자유 서술) 필드와 재평가 시각을 담기 좋다, (c) 평가 심사에서 "피드백 저장 구조"가 스키마로 명확히 보인다.

`message_id`에 **unique 제약**을 걸어 한 답변당 피드백 1건으로 두고, 다시 누르면 upsert(값 갱신)한다.

### 결정 3 — Langfuse 점수 전송은 ai_worker를 경유한다
`app`이 Langfuse 클라이언트를 직접 만들지 않고, **ai_worker에 `POST /observability/score` 엔드포인트를 신설**해 게이트웨이로 호출한다.

*이유*: Langfuse 키 설정은 `ai_worker/core/config.py`가 단일 소유하고 있다. `app`에 키를 중복 배치하면 설정 이중화가 되고, `_bridge_env()` 같은 SDK 우회 로직도 두 곳에 생긴다. 홉이 하나 늘지만 fire-and-forget이라 지연은 무의미하다.

### 결정 4 — 관측 실패는 절대 사용자 요청을 실패시키지 않는다
기존 `observability.py`의 원칙(“관측은 부수효과일 뿐”)을 그대로 따른다. **DB 저장이 성공하면 API는 200을 반환**하고, Langfuse 전송 실패는 `logger.exception` 후 삼킨다. Langfuse 미설정(로컬/CI)이면 trace_id가 `None`이고 점수 전송은 그냥 생략 — 기능은 정상 동작해야 한다.

---

## 4. 작업 단계

> **브랜치**: `feat/chat-answer-feedback`
> **PR 워크플로**: 계획 PR을 먼저 열고(이 문서 커밋), 단계별로 촘촘히 커밋, 끝나면 `[구현완료, merge 요청]` 코멘트.

### 1단계 — ai_worker: trace_id를 스트림에 실어 보내기
**파일**: `ai_worker/core/observability.py`, `ai_worker/tasks/chat_agent.py`

- `observability.py`에 헬퍼 추가:
  ```python
  def get_current_trace_id() -> str | None:
      """활성 span 안에서 현재 trace id를 반환. 미설정/오류 시 None (no-op)."""
  ```
  `get_langfuse_client()`가 `None`이면 `None` 반환, 예외는 잡아서 `None` 반환(기존 함수들과 동일한 방어 패턴).
- `chat_agent.py::stream_chat_answer`에서 `observe_span("chat_turn")` 블록 **안**, `sources` 청크를 yield한 직후에:
  ```python
  trace_id = observability.get_current_trace_id()
  if trace_id:
      yield {"type": "trace", "trace_id": trace_id}
  ```
  ⚠️ span 블록 **바깥에서 부르면 None이 나온다** — 반드시 `with` 안에서.

### 2단계 — ai_worker: 점수 수신 엔드포인트
**파일**: `ai_worker/core/observability.py`, `ai_worker/main.py`

- `observability.py`:
  ```python
  def create_score(trace_id: str, name: str, value: float, comment: str | None = None) -> None:
      """Langfuse trace에 점수를 붙인다. 미설정/오류 시 조용히 무시(no-op)."""
  ```
  내부에서 `get_langfuse_client()` → `client.create_score(name=..., value=..., trace_id=..., data_type="NUMERIC", comment=...)`.
  전송 보장을 위해 `client.flush()`를 호출할지 검토 — ai_worker가 장수 프로세스라 배치 전송이 지연될 수 있다. **실측으로 Langfuse UI에 점수가 뜨는지 확인하고, 안 뜨면 flush 추가.**
- `main.py`: `POST /observability/score`, body `{trace_id, name, value, comment?}`. 항상 200/204로 응답(관측 실패를 상위로 전파하지 않음).

### 3단계 — app: 게이트웨이 메서드
**파일**: `app/services/ai_worker_gateway.py`

- `async def submit_score(self, trace_id: str, name: str, value: float, comment: str | None = None) -> None`
- 기존 메서드들과 달리 **예외를 밖으로 던지지 않는다**(로그만). 호출부가 try/except로 감싸지 않아도 안전하게.

### 4단계 — app: 마이그레이션 + 모델
**파일**: `app/models/chat.py`, `app/core/db/migrations/versions/0062_*.py`

> ⚠️ **리비전 번호 충돌 경고 — 이 프로젝트에서 실제로 배포 장애를 낸 원인이다.**
> 브랜치를 만드는 시점에 반드시:
> ```bash
> git fetch origin dev && git log origin/dev --oneline -5
> ls app/core/db/migrations/versions/ | sort | tail -3
> ```
> 확인해 **dev에 0062가 이미 들어왔으면 0063으로 밀어라.** `down_revision`이 실제 최신 리비전을 가리키는지도 확인.
> (현재 확인값: 최신 = `0061_add_marketing_consent_revoked_at`)

- `chat_messages`에 컬럼 추가: `trace_id VARCHAR(64) NULL`
  - 어시스턴트 메시지에만 채워지고, Langfuse 미설정 환경에서는 항상 NULL이다. **nullable 필수.**
- 신규 테이블 `chat_message_feedbacks`:

  | 컬럼 | 타입 | 비고 |
  |---|---|---|
  | `id` | BigInteger PK | autoincrement |
  | `message_id` | BigInteger FK → `chat_messages.id` ondelete=CASCADE | **UNIQUE** |
  | `value` | Enum(`UP`,`DOWN`) native_enum=False | 기존 `MessageRole` 패턴과 동일하게 |
  | `comment` | Text NULL | 선택 입력 |
  | `created_at` / `updated_at` | DateTime(timezone=True) | server_default=func.now(), updated_at은 onupdate |

  `value`는 `StrEnum`으로 정의하되 **파이썬 클래스명·멤버명 모두 영문**(ruff N802/N815 회피).

### 5단계 — app: trace_id 저장 + message_id 노출
**파일**: `app/services/chat_service.py`, `app/repositories/chat_repository.py`, `app/dtos/chat.py`, `app/apis/v1/chat_routers.py`

- `_generate`의 청크 분기(`chat_service.py:187`)에 **`elif chunk["type"] == "trace":`** 추가 → 로컬 변수에 보관. (앞서 확인한 대로 지금은 조용히 버려진다.)
  - ⚠️ 이 청크는 프론트로 **relay하지 말 것**(결정 1).
- `ChatRepository.save_message`에 `trace_id: str | None = None` 파라미터 추가, 어시스턴트 메시지 저장 시 전달. **저장된 ChatMessage 객체(또는 최소한 id)를 반환하도록 변경** — 지금은 반환값을 안 쓰고 있을 가능성이 높으니 확인 후 반환 추가.
- `done` 청크에 `message_id` 추가:
  ```python
  yield {"type": "done", "content": "", "disclaimer": disclaimer, "message_id": assistant_msg.id}
  ```
- `ChatMessageResponse`에 `id: int` 추가 + `chat_routers.py:103`의 생성부에 `id=m.id` 추가 → **대화이력을 다시 불러온 과거 답변에도 피드백을 달 수 있다.**
  - ⚠️ 프론트 타입(`frontend/src/api/types.ts`)도 같이 고쳐야 tsc가 통과한다.

### 6단계 — app: 피드백 엔드포인트
**파일**: `app/apis/v1/chat_routers.py`, `app/services/chat_service.py`(또는 신규 `chat_feedback_service.py`), `app/repositories/chat_repository.py`

- `POST /chat/messages/{message_id}/feedback`, body `{"value": "up"|"down", "comment": str|None}`
- **소유권 검증 필수**: `message_id` → `chat_messages.session_id` → `chat_sessions.profile_id` 가 현재 프로필과 같은지. 아니면 404(403이 아니라 404 — 남의 메시지 존재 여부를 노출하지 않는다. 기존 `chat_routers.py:57`이 이미 이 패턴).
- 어시스턴트 메시지가 아니면 400 또는 404 (사용자 자기 질문에 별점 매기는 건 의미 없음).
- 처리 순서: **① DB upsert → ② 200 응답 확정 → ③ trace_id 있으면 `submit_score` fire-and-forget.**
  - 점수 매핑: `up → 1.0`, `down → 0.0`, `name="user_feedback"`, `comment`는 그대로 전달.
- 스코프 주의: **응급 fallback 메시지는 DB에 저장되지 않는다**(`chat_service.py` 주석 참고) → 피드백 대상이 아니다. 프론트에서도 버튼을 노출하지 않는다.

### 7단계 — 프론트: 👍/👎 버튼
**파일**: `frontend/src/api/chatApi.ts`, `frontend/src/hooks/useChatStream.ts`, `frontend/src/pages/ChatPage/ChatPage.tsx`, `frontend/src/api/types.ts`

- `useChatStream.ts:118`의 `done` 처리에서 `message_id`를 받아 해당 메시지 객체에 보관(`ChatMessage` 인터페이스는 `useChatStream.ts:9`).
- 어시스턴트 메시지 하단(출처 칩 근처)에 👍/👎. **낙관적 업데이트 후 실패 시 롤백.**
- 이미 누른 상태는 시각적으로 구분, 다시 누르면 값 변경(upsert).
- 폭·모달 등 기존 컨벤션 유지 — 챗 화면은 `maxWidth: 480`으로 통일돼 있다.
- 시각 디자인 판단은 하지 말고 기능만 맞춰라. 최종 모양은 사용자(박지은)가 본다.

### 8단계 — ★ 개선 루프 1건 실행 (이게 5점의 조건)
**이 단계를 빼면 4점이다. 반드시 한다.**

1. 로컬에서 실제 질문 10~15개를 던지고 👍/👎를 눌러 **의도적으로 낮은 점수를 몇 건 만든다**(답변이 실제로 부실한 케이스를 고를 것 — 억지로 만든 데이터는 개선 근거가 안 된다).
2. Langfuse UI에서 `user_feedback` score로 필터링 → 낮은 점수 trace를 열어 **검색된 문서와 유사도 점수를 확인**한다(2단계 retrieval span 덕분에 보인다).
3. 원인을 하나 특정한다. 예상되는 유형:
   - 관련 문서가 임계값에 걸려 잘렸다 → `PAPER_SIMILARITY_THRESHOLD` / `RAG_SIMILARITY_THRESHOLD` 조정 검토
   - 무관한 문서가 들어와 답변을 오염시켰다 → 임계값을 반대로 조정
   - 검색은 맞았는데 프롬프트가 문서를 안 썼다 → 시스템 프롬프트 보강
4. 고치고, **같은 질문을 다시 던져 개선을 확인**한다.
5. 이 문서 하단 "개선 사례" 절에 **before / after를 수치와 함께 기록**한다. 이게 발표 슬라이드에 그대로 들어간다.

⚠️ 임계값을 바꾸면 기존 실측 근거(DUR 0.35 / 논문 0.40, 관련·무관 거리 분포)와 어긋날 수 있다. **바꿀 경우 발표자료의 해당 수치도 같이 갱신해야 한다** — 지은님에게 알릴 것.

---

## 5. 검증 (CI 게이트 기준)

이 리포의 CI는 **pytest를 돌리지 않는다.** `.github/workflows/ci.yml`이 실제로 도는 것만 맞춰라:

```bash
ruff check . && ruff format --check .
mypy app ai_worker
cd frontend && npx tsc --noEmit && npx eslint . && npx prettier --check .
```

테스트는 **좁게** 쓴다(전체 스위트 실행 금지):
```bash
pytest app/tests/... -q -k "feedback or trace"
pytest ai_worker/tests/... -q -k "score or trace"
```

최소 테스트 항목:
- 남의 세션 메시지에 피드백 → 404
- 같은 메시지에 두 번 피드백 → 행이 1개이고 값이 갱신됨(upsert)
- Langfuse 미설정(trace_id=None)이어도 피드백 저장은 200
- `submit_score` 실패해도 엔드포인트는 200
- `trace` 청크가 프론트로 relay되지 않음
- 사용자(USER) 메시지에 피드백 시도 → 거부

⚠️ **테스트 함수명은 영문으로.** 한글 함수명은 ruff N802에 걸린다(이 리포에서 반복 발생한 이슈).

수동 확인:
- `docker compose build` 후 기동 → 챗 답변에 👍 → **Langfuse UI에 score가 실제로 붙는지 눈으로 확인**(1·2단계와 달리 이번엔 전송 경로가 하나 더 있어서 반드시 실측 필요).
- Langfuse 키를 비운 상태로도 챗봇과 피드백이 정상 동작하는지(무회귀).

---

## 6. 완료 정의 (DoD)

- [ ] ai_worker가 `{"type":"trace","trace_id":...}` 청크를 내보낸다 (Langfuse 미설정 시 생략)
- [ ] `chat_messages.trace_id` 저장됨
- [ ] `chat_message_feedbacks` 테이블 생성, message_id UNIQUE
- [ ] `POST /chat/messages/{id}/feedback` 동작 + 소유권 검증
- [ ] `ChatMessageResponse.id` 노출 → 과거 대화에도 피드백 가능
- [ ] 프론트 👍/👎 동작, 낙관적 업데이트 + 롤백
- [ ] Langfuse UI에서 `user_feedback` score 실측 확인
- [ ] **낮은 점수 trace 기반 개선 1건 실행 + before/after 기록** ← 5점 조건
- [ ] Langfuse 키 없는 환경에서 무회귀 확인
- [ ] ruff / mypy / tsc / eslint / prettier 통과
- [ ] `[구현완료, merge 요청]` 코멘트

---

## 7. 스코프 밖 (하지 말 것)

- **재학습 파이프라인** — RAG 구조라 fine-tuning이 없다. 평가기준의 "개선 **또는** 재학습"에서 개선 쪽으로 충족한다.
- **피드백 통계 관리자 화면** — 있으면 좋지만 이번 범위 아님. Langfuse UI가 대시보드 역할을 한다.
- **자동 실패 탐지 / 프롬프트 A/B 테스트** — 다음 과제. 이번엔 사람이 trace를 보고 고치는 루프까지.
- **Celery 등 스케줄러 도입** — 이 프로젝트 원칙상 수동 트리거 우선.
- **UI 시각 디자인 다듬기** — 기능만. 최종 판단은 사용자가 한다.

---

## 8. 개선 사례 (8단계 수행 후 여기에 기록)

> 형식 예시:
> - **질문**: "…"
> - **낮은 점수 원인**: trace `abc123`에서 관련 논문이 유사도 0.42로 임계값(0.40)에 걸려 제외됨
> - **조치**: 논문 임계값 0.40 → 0.45
> - **결과**: 같은 질문 재시도 시 해당 논문이 출처에 포함, 답변에 구체적 근거 등장
> - **부작용 확인**: 골든셋 40문항 recall@3 재측정 → 변화 없음 / 있음(수치)
