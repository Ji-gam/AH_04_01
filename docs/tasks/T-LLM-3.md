# Task ID: T-LLM-3 (건강 콘텐츠 생성 파이프라인)

### 참조
- PRD: F-LLM-3 / TRD: T-LLM-3 / REQ: REQ-CONT-001~004
- 관련 결정: `docs/decision_log.md` "RAG 개발 기간 동안의 화면별 대응 전략(Tier 구조)" — Tier 1(생성만 필요 → 배치 생성 → 캐시 테이블 저장 → 화면은 캐시만 읽음)

### 목표 (TRD 원문 그대로)
- 입력: 질환 태그, 생활 패턴 데이터
- 출력/노출: 규격화된 팁 카드(JSON 기반)

### 이번 라운드 범위
백엔드(모델/서비스/API) + 수동 배치 트리거까지. 프론트 "정보" 탭 UI, 가족 프로필 스위처(T-AUTH-5/6 의존), 챗봇의 콘텐츠 추천 기능은 이번 PR 범위 밖 — 별도 후속 작업.

### 완료 정의 (Definition of Done — TRD 성공요건 = 자동 검증 대상)
- [ ] 동일 질환+카테고리 콘텐츠가 당일 이미 존재하면 재생성 없이 캐시가 재사용된다
- [ ] 5대 질환(암/심장질환/뇌혈관질환/당뇨/간질환)은 수동 배치 스크립트 실행으로 사용자 접속 이전에 미리 생성 가능하다
- [ ] 배치 대상이 아닌 질환에 사용자가 접속하면 온디맨드로 생성되고 이후 캐시로 재사용된다
- [ ] 콘텐츠는 카테고리(LIFESTYLE/FOOD/MEDICAL_NEWS)로 구분되어 저장되고, 과거 날짜 카드는 삭제/교체되지 않고 누적된다
- [ ] `GET /contents/me`가 로그인한 프로필의 `conditions` 각각에 대해 카테고리별 카드를 반환하며, 응답 시점에 `safety_service`의 면책문구가 동적으로 부착된다(콘텐츠에 문구를 박아 저장하지 않음)
- [ ] (공통) 새 테이블/조회 로직은 `profile_id` 기준으로 설계되었는가 (`user_id` 직접 참조 금지)
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

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
app/dependencies/**
app/services/chat_service.py  (챗봇 연동은 후속 작업)
app/services/safety_service.py  (읽기만, 수정 금지)
app/services/user_health_context_service.py  (읽기만, 수정 금지)
app/services/retriever_stub.py, app/services/llm_stub.py  (읽기/재사용만, 수정 금지)
ai_worker/**
frontend/**
envs/**
infra/**
docker-compose.yml
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 의존하는 공유 계약 (읽기만 가능, 이미 고정됨)
- `app/dependencies/security.py` — `get_current_profile`
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
_(작업 완료 후 채움)_
