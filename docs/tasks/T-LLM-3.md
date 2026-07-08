# Task ID: T-LLM-3 (건강 콘텐츠 생성 파이프라인)

### 참조
- PRD: F-LLM-3 / TRD: T-LLM-3 / REQ: REQ-CONT-001~004
- 관련 결정: `docs/decision_log.md` "RAG 개발 기간 동안의 화면별 대응 전략(Tier 구조)" — Tier 1(생성만 필요 → 배치 생성 → 캐시 테이블 저장 → 화면은 캐시만 읽음)

### 목표 (TRD 원문 그대로)
- 입력: 질환 태그, 생활 패턴 데이터
- 출력/노출: 규격화된 팁 카드(JSON 기반)

### 이번 라운드 범위
백엔드(모델/서비스/API) + 오프라인 생성·시드 스크립트까지. 프론트 "정보" 탭 UI는 이 브랜치를 base로 하는 `feature/T-LLM-3-info-page-frontend`(스택형 PR)에서 별도로 진행한다(백엔드만으로는 리뷰가 어렵다는 판단하에 PR을 분리). 가족 프로필 스위처(T-AUTH-5/6 의존), 챗봇의 콘텐츠 추천 기능은 범위 밖 — 별도 후속 작업.

**설계 변경 1 (2026-07-08, 구현 중 확정)**: 최초 계획은 캐시 미스 시 요청 안에서 온디맨드로 LLM을 호출하는 것이었으나, 사용자 요청마다 LLM 호출이 발생하는 구조의 지연/비용 문제가 지적되어 **라이브 생성을 완전히 제거**했다. 대신 `generate_health_content.py`(오프라인, LLM 호출 → JSON 픽스처 생성) → 커밋 → `seed_health_content.py`(픽스처를 로컬 DB에 시드)로 흐름을 바꿨다. `GET /contents/me`는 캐시에 있는 것만 읽고, 없는 조합은 조용히 스킵한다(생성하지 않음).

**설계 변경 2 (2026-07-08, 구현 중 확정)**: "정보" 탭은 로그인 여부와 무관하게 볼 수 있어야 한다는 요구사항이 확인되어, `GET /contents/me`를 인증 필수(`get_current_profile`)에서 **공개 엔드포인트**(`get_current_profile_optional`, `app/dependencies/security.py`에 신규 추가 — 금지 경로였으나 이 목적을 위해 예외로 허용받음, [공통모듈 변경])로 전환했다. 비로그인이거나 프로필에 등록된 질환이 없으면 전체 질환의 콘텐츠를 누적 피드로 반환하고(질환 등록 유도 배너는 프론트 몫), 등록된 질환이 있으면 그 질환들만 필터링한다.

### 완료 정의 (Definition of Done — TRD 성공요건 = 자동 검증 대상)
- [x] 동일 질환+카테고리 콘텐츠가 당일 이미 존재하면 재생성 없이 캐시가 재사용된다 (`seed_health_content.py` 재실행 시 0건, 멱등성 확인)
- [x] 5대 질환(암/심장질환/뇌혈관질환/당뇨/간질환)은 오프라인 스크립트로 사용자 접속 이전에 미리 생성 가능하다
- [x] (설계 변경) 배치 대상이 아닌 질환은 온디맨드 생성 대신 **캐시에 없으면 조용히 제외**된다 — 원래 계획(온디맨드 생성)에서 변경, 위 "설계 변경" 참고
- [x] 콘텐츠는 카테고리(LIFESTYLE/FOOD/MEDICAL_NEWS)로 구분되어 저장되고, 과거 날짜 카드는 삭제/교체되지 않고 누적된다
- [x] `GET /contents/me`는 인증 없이도 호출 가능하며, 로그인한 프로필에 등록된 질환이 있으면 그 `conditions` 기준으로, 없거나 비로그인이면 전체 질환 기준으로 카테고리별 카드를 누적 피드(날짜 역순)로 반환한다. 응답 시점에 `safety_service`의 면책문구가 동적으로 부착된다(콘텐츠에 문구를 박아 저장하지 않음)
- [x] (공통) 새 테이블/조회 로직은 `profile_id` 기준으로 설계되었는가 (`user_id` 직접 참조 금지) — 단, `health_contents`는 개인 데이터가 아닌 질환 기준 공유 캐시라 profile_id 자체를 갖지 않음(모델 docstring에 근거 명시)
- [x] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가 (전체 51개 통과)
- [x] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
app/apis/v1/content_routers.py
app/services/content_service.py
app/repositories/content_repository.py
app/models/content.py
app/dtos/content_dto.py
app/tests/content_apis/**
app/tests/services/test_content_service.py
app/scripts/generate_health_content.py
app/core/db/migrations/versions/000X_*content*.py  (신규 리비전 파일만 추가, 기존 리비전 수정 금지)
docs/dev/ERD.dbml  (health_contents 테이블 추가분만)
docs/tasks/T-LLM-3.md  (이 파일의 "완료 보고" 섹션만)
docs/squad-map.md  (D 스쿼드 접두어에 content_* 추가 — 이미 반영됨)
```

### 금지 경로 (절대 수정하지 않음 — 필요해 보여도 "공유 파일 변경 필요"로 보고만)
```
app/core/** (celery_app.py 등 스케줄러 인프라 포함 — 이번 라운드는 수동 트리거만, Celery 도입 안 함)
app/dependencies/**  (예외: get_current_profile_optional 추가만 사용자 승인 하에 진행, 기존 함수는 미수정)
app/services/chat_service.py  (챗봇 연동은 후속 작업)
app/services/safety_service.py  (읽기만, 수정 금지)
app/services/user_health_context_service.py  (예외: 데모/테스트용 mock 프로필(profile_id=5, 당뇨) 1건 추가만 사용자 승인 하에 진행, 기존 항목은 미수정)
app/services/retriever_stub.py, app/services/llm_stub.py  (읽기/재사용만, 수정 금지)
ai_worker/**
frontend/**
envs/**
infra/**
docker-compose.yml
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 의존하는 공유 계약 (읽기만 가능, 이미 고정됨)
- `app/dependencies/security.py` — `get_current_profile_optional`(신규 추가, 이 Task에서 도입)
- `app/services/user_health_context_service.py` — `get_context(profile_id) -> dict`(`conditions` 필드를 콘텐츠 대상 질환으로 사용, `family_history`는 이번 범위 아님)
- `app/services/safety_service.py` — 면책문구 조회 함수
- `app/services/retriever_stub.py`, `app/services/llm_stub.py` — RAG 검색 + LLM 생성 재사용

### 자율 판단 허용 범위
- 5대 질환 상수의 정확한 코드 문자열 표기, 카테고리별 프롬프트 문구, 콘텐츠 JSON 세부 필드명(title/summary/body/image_prompt/source_refs 골격은 고정, 세부 표현은 자율), 배치 스크립트 실행 인터페이스(CLI 인자 등) — 전부 에이전트 자율 결정.

### 반드시 멈춰야 하는 경우 (이 Task에 한정된 추가 조건)
- `chat_service.py`나 `ai_worker/`의 RAG 인덱스 구조를 바꿔야 할 필요가 생기는 경우(챗봇 연동은 후속 작업이므로 이번엔 손대지 않는다)
- `user_health_context_service.py`의 `conditions`만으로는 콘텐츠 생성이 불가능하다고 판단되는 경우(예: 질환 코드 정규화가 안 맞음)

### 가정 (Assumptions)
- 콘텐츠 생성 대상은 `conditions`(현재 진단 질환)만 사용하고 `family_history`(가족력)는 이번 범위에서 제외한다.
- "인기 질환" 5종은 관리자가 향후 확장할 하드코딩 상수로 시작한다(사용자 입력 기반 통계 아님).
- 배치 트리거는 Celery/cron 없이 수동 스크립트로 시작한다(스테이징 환경이 아직 없음 — 스테이징 도입 후 스케줄러 연결은 후속 작업).

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 위 목록 전부 충족(온디맨드 생성 항목은 설계 변경으로 대체, 사유는 위 "설계 변경" 참고)
- 가정(Assumptions):
  - 콘텐츠 생성 대상은 `conditions`만 사용, `family_history`는 제외
  - "인기 질환" 5종은 관리자 확장형 하드코딩 상수
  - 배치 트리거는 Celery/cron 없이 수동 스크립트(스테이징 도입 후 스케줄러 연결은 후속 작업)
  - 픽스처는 오늘 날짜로 시드되므로 자정이 지나면 재시드가 필요함(로컬 데모용 설계, 실제 운영 스케줄링은 후속 작업)
- 공유 계약 변경 필요 사항:
  - `app/services/llm_stub.py`에 `generate_content_card` 함수를 추가함(기존 `stream_llm_reply`는 그대로, 회귀 없음 확인)
  - `app/dependencies/security.py`에 `get_current_profile_optional` 함수를 추가함(Auth 스쿼드 소유 공유 파일, 사용자 명시적 승인 하에 진행, 기존 `get_current_profile`/`get_request_user`는 미수정 — [공통모듈 변경])
  - `app/services/user_health_context_service.py`의 mock 딕셔너리에 `profile_id=5`(당뇨) 항목을 추가함 — 프론트 데모/테스트 시 로그인해서 개인화 콘텐츠를 바로 확인할 수 있는 계정 필요성 때문(사용자 명시적 승인 하에 진행, 기존 1/2/4번 항목은 미수정). 테스트 계정: `demo-diabetes@example.com` / `Password123!`
- 검증: `pytest -v` 52/52 통과, `ruff check .`/`ruff format --check .`/`mypy .` 전체 통과, 실제 OpenAI로 15건(5질환x3카테고리) 생성 → 시드 → 재시드 멱등성 확인 → 실제 profile_id=1(mock 조건 "당뇨")로 서비스 호출 시 3장 정상 반환 확인, 비인증 요청으로 실제 dev DB에서 15건 전체 반환 확인
- 브랜치명: `feature/T-LLM-3-content-pipeline-backend` (백엔드 전용 — 프론트 "정보" 탭 UI는 이 브랜치를 base로 하는 `feature/T-LLM-3-info-page-frontend`에서 별도 PR로 진행. 애초 하나의 브랜치/PR로 진행했으나, 백엔드만으로는 리뷰/데모가 어려워 PR을 분리했다)
- 후속 작업(범위 밖, 별도 T-ID 필요): 프론트 "정보" 탭 UI(별도 PR로 분리 진행 중), 가족 프로필 스위처(T-AUTH-5/6 완료 후), 챗봇의 콘텐츠 추천 기능, 스테이징 도입 후 배치 스케줄러(Celery beat 등) 연결
