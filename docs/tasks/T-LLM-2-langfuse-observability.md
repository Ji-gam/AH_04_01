## Task ID: T-LLM-2-langfuse-observability (T-LLM-2 "AI 챗봇 상담" 하위 작업 — LLM/RAG 관측성(Langfuse) 도입)

> 작성자: 박지은(D스쿼드, `chat_*`/`ai_worker/` 소유). **이 문서는 착수 전 계획(plan)이다** — 구현은 이 PR에
> 이어서 커밋한다. 신규 최상위 TRD 요구사항이 아니라, 기존 `ai_worker/`의 LLM 호출을 관측 가능하게 만드는
> 횡단 인프라 작업이라 T-LLM-2 하위 슬러그로 둔다.

### 참조
- PRD: F-LLM-2 / TRD: T-LLM-2 / REQ: REQ-BOT-001~005 (관측 대상이 챗봇 상담 파이프라인)
- 관련: `ai_worker/tasks/chat_agent.py`(스트리밍 RAG 채팅, T-LLM-2), `ai_worker/tasks/generate_structured.py`
  (구조화 생성, T-LLM-3) — LLM 호출이 이 둘뿐이라 두 경로를 함께 계측한다.
- 배경: 현재 `ai_worker/`에는 트레이싱/관측 계층이 전혀 없다. 평범한 `logging`(`ai_worker/core/logger.py`)과
  검색 서비스의 `DEBUG_SCORE:` 로그만 있어, "왜 이런 답이 나왔는지"(어떤 문서를 검색해왔는지·프롬프트·
  토큰·지연)를 사후에 추적할 수 없다.

### 목표
- 입력: 기존 챗봇/구조화 생성 요청 (변경 없음 — 사용자 대면 동작·응답 스키마 무변경)
- 출력/노출: 각 LLM 호출이 **Langfuse 클라우드**(무료 플랜, `cloud.langfuse.com`)에 trace로 기록된다 —
  프롬프트, 응답, 모델명, 토큰 사용량, 지연시간.
- 방식: LangChain 콜백 핸들러를 통한 계측. `ChatOpenAI.astream`/`chain.ainvoke` 호출에
  `config={"callbacks": [handler]}`를 주입한다. 두 호출부가 공유하는 핸들러 팩토리를
  `ai_worker/core/`에 신설한다(현재는 각 task 모듈이 각자 `_build_llm()`을 갖고 있어 공유 지점이 없다 —
  워크어라운드로 두 군데 복붙하지 않고, 관측 설정을 한 곳으로 모은다).

### 단계 구분 (이번 PR = 1단계만)
- **1단계 (이번 PR, 우선 범위)**: LLM 호출 2곳에 Langfuse 콜백 연결. 프롬프트/응답/토큰/지연이 trace로 잡힌다.
  키가 없으면(로컬·CI) **자동으로 no-op** — 관측이 꺼져도 챗봇은 정상 동작한다.
- **2단계 (별도 PR, 나중)**: RAG 검색 단계(`retrieve_service.search_documents`,
  `paper_retrieve_service.search_papers`)를 trace의 하위 span으로 계측(`@observe`). "어떤 문서를 왜
  가져왔는지"가 trace에 단계로 보인다. RAG 품질 디버깅에 가장 값진 부분이지만, 수동 계측이라 분리한다.
- POC 제출용 범위임을 감안해 1단계로 관측의 80%를 확보하고, 2단계는 필요 시 착수한다.

### 완료 정의 (Definition of Done — 1단계)
- [ ] `langfuse` 의존성이 `[dependency-groups].ai`에 추가되고 `uv.lock`이 갱신된다
- [ ] `ai_worker/core/config.py`에 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST`
      설정이 추가된다(기본값은 빈 문자열 — 미설정 시 관측 비활성)
- [ ] `ai_worker/core/`에 콜백 핸들러 팩토리 신설 — 키가 모두 설정된 경우에만 `CallbackHandler`를
      반환하고, 아니면 `None`(no-op)을 반환한다
- [ ] `chat_agent.py`의 `llm.astream(...)`과 `generate_structured.py`의 `chain.ainvoke(...)`가
      핸들러가 있을 때 `config={"callbacks": [handler]}`로 호출된다
- [ ] 키 미설정 시(로컬/CI) 예외·경고 없이 챗봇/구조화 생성이 종전과 동일하게 동작한다(무회귀)
- [ ] 실제 키 설정 후 챗봇 1회 호출 시 Langfuse 대시보드에 trace 1건(프롬프트·응답·토큰)이 뜬다 — 스크린샷으로 확인
- [ ] `.env.example`(및 `envs/`)에 3개 키의 자리표시자와 주석이 추가된다
- [ ] (공통) 테스트 함수명 영문, ruff/mypy 통과 (CI 게이트: `ruff check` + `ruff format --check` + `mypy`; 이 레포 CI는 pytest 미실행)

### 허용 경로 (이 안에서만 자유롭게 작업)
```
ai_worker/tasks/chat_agent.py
ai_worker/tasks/generate_structured.py
ai_worker/core/config.py
ai_worker/core/observability.py        (신규 — 콜백 핸들러 팩토리)
ai_worker/tests/**                      (관측 no-op/활성 분기 테스트)
pyproject.toml                          ([dependency-groups].ai 에 langfuse 추가만)
uv.lock                                 (uv add 결과)
envs/.example.env 등 자리표시자          (키 3개 추가)
docs/tasks/T-LLM-2-langfuse-observability.md  (이 파일)
```

### 금지 경로 (수정하지 않음 — 필요하면 "공유 계약 변경 필요"로 보고만)
```
app/**                                  (앱 서비스는 ai_worker를 HTTP로만 호출 — 계측 대상 아님)
ai_worker/core/logger.py                (기존 로깅 계약 유지)
docker-compose.yml / infra/**           (셀프호스팅 아님 — 클라우드 무료 플랜 결정)
frontend/**
docs/tasks/_active.json                 (등록/해제 외 수정 금지)
```

### 자율 판단 허용 범위
- 핸들러 팩토리의 함수 시그니처/파일명, trace 이름·메타데이터 태깅 방식, no-op 판정 로직,
  테스트 분리 방식 — 전부 자율 결정.

### 반드시 멈춰야 하는 경우
- Langfuse 계측을 위해 사용자 대면 응답 스키마나 스트리밍 이벤트 포맷(`{"type": ...}`)을 바꿔야 하는 상황이
  생기면 — 진행하지 말고 보고. (관측은 부수효과여야 하고 계약을 건드리면 안 된다.)
- 셀프호스팅(docker-compose)이 필요하다는 판단이 들면 — compose는 리더 승인 대상이므로 멈추고 보고.

### 미결/확인 필요
- Langfuse 클라우드 프로젝트 생성 및 3개 키 발급은 사람(박지은)이 한다 — 코드는 키를 환경변수로만 읽는다.
- 프롬프트/응답에 환자 관련 텍스트가 포함될 수 있으므로, 외부(Langfuse 클라우드)로 전송되는 데이터 범위를
  구현 전 한 번 더 확인한다(POC 데모 데이터 기준). 필요 시 마스킹/비활성 스위치를 기본값으로 둔다.

### 완료 보고 (구현 후 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/T-LLM-2-langfuse-observability`
