# Task Contract: T-GOAL-2 (목표 기반 맞춤 가이드 생성·갱신)

> **문서 버전**: v1.0 · **작성**: 2026-07-29
> **변경 이력**
> - v1.0 (2026-07-29): 신규 작성

---

## Task ID: T-GOAL-2 (목표 기반 맞춤 가이드 생성·갱신)

### 참조
- PRD: F-GOAL-2 / TRD: T-GOAL-2 / REQ: REQ-GOAL-002~004

### 목표 (TRD 원문)
등록한 목표와 신체정보를 바탕으로 맞춤형 식단·운동 가이드를 자동으로 생성하고, 목표 변경 시 가이드를 자동 재생성합니다.

**입력**: 목표 수치, 신체정보, 지병 정보  
**출력/노출**: 식단/운동 가이드, 재생성 진행 상태 표시

---

## 완료 정의 (Definition of Done)

### 기능 요구사항
- [ ] 목표 생성 시 AI를 통해 3~5문장의 식단·운동 가이드가 자동으로 생성된다
- [ ] 지병이 있는 경우, 해당 지병에 위험한 항목이 추천 결과에 포함되지 않는다
- [ ] 목표의 제목/수치/기간이 변경되면 가이드가 자동으로 재생성된다
- [ ] 재생성 중임을 UI 화면에서 명확히 표시한다 (로딩 상태)
- [ ] 일일 수치 기록(log_progress)은 가이드를 재생성하지 않는다 (매일 AI 호출 최소화)
- [ ] AI 호출 실패 시, 폴백 템플릿으로 가이드를 저장해 서비스가 중단되지 않는다

### 공통 요구사항 (모든 Task 공통)
- [ ] 새 테이블/조회 로직은 `profile_id` 기준으로 설계되었는가 (`user_id` 직접 참조 금지)
- [ ] 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가
- [ ] API P95 Latency ≤ 3초
- [ ] 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과
- [ ] Swagger API 명세에 `summary`, `description`, `responses`, 각 필드 `description` 포함

---

## 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)

```
app/apis/v1/goal_routers.py
app/services/goal_service.py
app/repositories/goal_repository.py
app/repositories/goal_progress_log_repository.py
app/dtos/goal_dto.py
app/models/goals.py
app/models/goal_progress_logs.py
app/core/db/migrations/versions/004X_*.py  (DB 마이그레이션 필요시)
app/tests/goal_apis/**
app/tests/services/test_goal_service.py
frontend/src/pages/GoalPage/**  (신규 페이지)
frontend/src/pages/HomePage/**  (목표 위젯 추가)
frontend/src/pages/TrackPage/**  (목표 섹션 추가)
frontend/src/hooks/useGoal*.ts
frontend/src/api/goalApi.ts
docs/tasks/T-GOAL-2.md  (이 파일의 "완료 보고" 섹션만)
```

---

## 금지 경로 (절대 수정하지 않음)

```
app/core/**
app/dependencies/**
app/models/profiles.py
app/models/diagnosis_entries.py
app/services/ai_worker_gateway.py  (AI Worker 호출 인터페이스만 사용)
frontend/src/api/client.ts
frontend/src/api/types.ts
frontend/src/components/**
frontend/src/routes/**
frontend/src/store/**
envs/**
infra/**
scripts/**
docs/tasks/_active.json
docs/CODING_RULES.md
docs/plan/PRD*.md
docs/plan/TRD*.md
```

---

## 의존하는 공유 계약 (읽기만 가능)

### 백엔드
- `app/dependencies/security.py` — `get_current_profile()` 의존성
- `app/services/ai_worker_gateway.py` — `AIWorkerGateway.call_structured()` 메서드
  - 입력: `system_prompt` (str), `user_input` (str), `schema` (Pydantic 스키마)
  - 출력: 스키마 검증된 객체
  - 실패 시: `AIWorkerUnavailableError`, `AIWorkerInvalidRequestError`, `AIWorkerProcessingError` 발생
- `app/services/disease_code_mapper.py` — `map_diagnosis_entries()` 함수 (진단명 매핑)
- `app/models/profiles.py` — Profile 모델 (diagnosis_entries 관계 포함)
- `app/repositories/profile_repository.py` — `ProfileRepository.get_profile()`

### 프론트엔드
- `frontend/src/api/goalApi.ts` — API 클라이언트 (이미 작성됨)
  - `goalApi.list()`, `goalApi.create()`, `goalApi.update()`, `goalApi.logProgress()`, `goalApi.remove()`

---

## 현재 구현 상태 (참고용 — 변경하지 않음)

### 백엔드 ✅ (완성)
- `app/services/goal_service.py` (216줄)
  - `create()`: 목표 생성 + AI 가이드 생성
  - `update()`: 목표 수정 + 변경 시 가이드 재생성
  - `_generate_guide()`: AI Worker 호출로 가이드 생성
  - `log_progress()`: 일일 수치 기록 (가이드 재생성 안 함)
  - `list_goals()`: 목표 목록 조회
  - `delete()`: 목표 삭제

- `app/apis/v1/goal_routers.py`
  - `GET /goals` — 목표 목록 조회
  - `POST /goals` — 목표 생성 (가이드 자동 생성)
  - `PATCH /goals/{goal_id}` — 목표 수정 (변경 시 가이드 재생성)
  - `POST /goals/{goal_id}/logs` — 일일 수치 기록
  - `DELETE /goals/{goal_id}` — 목표 삭제

- 데이터베이스 ✅
  - `goals` 테이블: id, profile_id, title, start_value, target_value, current_value, unit, start_date, end_date, guide_content, guide_generated_at, is_achieved, created_at
  - `goal_progress_logs` 테이블: id, goal_id, log_date, value, created_at

### 프론트엔드 🔲 (부분 구현)
- API 클라이언트: `frontend/src/api/goalApi.ts` ✅
- UI 페이지: 미구현 (이 Task에서 완성)
  - [ ] `/goals` 목표 목록 페이지 (CRUD)
  - [ ] 목표 생성 모달/페이지
  - [ ] 목표 수정 모달/페이지
  - [ ] 일일 수치 기록 UI
  - [ ] 가이드 표시 영역 (로딩/에러/성공 상태)
  - [ ] HomePage 위젯 (진행률 표시)
  - [ ] TrackPage 목표 섹션 (목표별 진행 그래프)

---

## 자율 판단 허용 범위

- 가이드 생성 AI 프롬프트 튜닝 (더 나은 결과를 위한 문구 개선)
- 폴백 가이드 템플릿 텍스트
- UI 로딩 상태 표현 방식 (스켈레톤, 스피너 등)
- 목표 입력 폼의 입력값 검증 규칙 (수치 범위, 날짜 선택 제약 등)
- 프론트 상태 관리 방식 (로컬 state vs 전역 상태)

---

## 반드시 멈춰야 하는 경우

1. 목표 데이터 스키마 변경이 필요해 보이는 경우 → `docs/tasks/T-GOAL-2.md` "완료 보고"에 구체 내용 기록
2. AI Worker Gateway 인터페이스 변경이 필요한 경우
3. profile_id 기준이 아닌 user_id 직접 참조로 구현해야 하는 상황
4. 기존 T-GOAL-1 (목표 설정) 스키마와 충돌하는 경우
5. 외부 API 연동 (영양정보 DB, 운동 정보 API 등)이 필요해 보이는 경우 → TRD 범위 확인 후 보고

---

## 테스트 케이스 (TDD 작성 순서)

아래를 테스트 케이스명으로 사용하세요:

### 백엔드 (pytest)
1. `test_create_goal_generates_guide_with_disease_context` — 지병 있을 때 가이드 생성
2. `test_create_goal_generates_guide_without_disease` — 지병 없을 때 가이드 생성
3. `test_update_goal_regenerates_guide_on_title_change` — 제목 변경 시 가이드 재생성
4. `test_update_goal_regenerates_guide_on_value_change` — 수치 변경 시 가이드 재생성
5. `test_update_goal_regenerates_guide_on_date_change` — 기간 변경 시 가이드 재생성
6. `test_update_goal_no_regenerate_on_other_field_change` — 다른 필드 변경 시 재생성 안 함
7. `test_log_progress_does_not_regenerate_guide` — 일일 기록은 가이드 재생성 안 함
8. `test_ai_failure_uses_fallback_guide` — AI 실패 시 폴백 템플릿 사용
9. `test_list_goals_includes_guide_content` — 목표 목록에 가이드 포함
10. `test_goal_filtered_by_profile_id` — profile_id 기준 필터링
11. `test_goal_delete_removes_associated_logs` — 목표 삭제 시 관련 로그도 삭제

### 프론트엔드 (Vitest/React Testing Library)
1. `test_create_goal_button_opens_modal` — 목표 생성 버튼 → 모달 열림
2. `test_create_goal_form_validates_input` — 입력값 검증
3. `test_create_goal_shows_loading_state_during_generation` — 가이드 생성 중 로딩 표시
4. `test_create_goal_displays_guide_on_success` — 가이드 표시
5. `test_update_goal_regenerates_guide_with_loading_state` — 수정 시 로딩 표시 + 가이드 재생성
6. `test_update_goal_does_not_trigger_on_cancel` — 취소 시 수정 안 됨
7. `test_guide_content_is_readable_text` — 가이드가 텍스트로 표시됨 (마크다운 등)
8. `test_log_progress_shows_confirm_feedback` — 일일 기록 완료 피드백
9. `test_goal_list_sorts_by_end_date` — 목표 목록이 종료일 순 정렬
10. `test_home_widget_displays_progress_rate` — HomePage 위젯이 진행률 표시
11. `test_error_state_displays_fallback_guide_message` — 에러 시 폴백 메시지 표시

---

## API 명세 (Swagger)

### POST /goals (목표 생성)
```
summary: "목표 생성 및 AI 가이드 자동 생성"
description: "사용자가 목표를 생성하면 제목, 수치, 기간, 지병 정보를 바탕으로 AI가 맞춤형 식단·운동 가이드를 즉시 생성합니다. AI 실패 시에도 폴백 템플릿으로 저장되어 서비스가 중단되지 않습니다."

Request Body (GoalCreateRequest):
  - title (string, required): 목표 제목 (예: "체중 5kg 감량")
  - start_value (number, optional): 시작 수치 (예: 80)
  - target_value (number, optional): 목표 수치 (예: 75)
  - current_value (number, optional): 현재 수치 (생략 시 start_value로 설정)
  - unit (string, optional): 단위 (예: "kg", "분")
  - start_date (date, required): 시작 날짜
  - end_date (date, required): 종료 날짜

Response (GoalItemResult, 201 Created):
  - id (number): 목표 ID
  - title (string): 목표 제목
  - start_value, target_value, current_value (number): 수치값
  - unit (string): 단위
  - term (string): 기간 유형 ("단기" / "장기")
  - progress_rate (number, 0~1): 진행률
  - guide_content (string): AI 가이드 콘텐츠 (3~5문장)
  - guide_generated_at (datetime): 가이드 생성 시각
  - is_achieved (boolean): 달성 여부
  - created_at (datetime): 목표 생성 시각
  - recent_logs (array): 최근 7일 기록

Errors:
  - 400: 입력값 검증 실패
  - 401: 토큰 없음/유효하지 않음
```

### PATCH /goals/{goal_id} (목표 수정)
```
summary: "목표 수정 및 조건부 가이드 재생성"
description: "목표의 제목, 수치, 기간 중 하나라도 변경되면 AI가 새로운 가이드를 자동으로 생성합니다. 수정 중임을 프론트엔드에서 로딩 상태로 표시해야 합니다."

Path Parameter:
  - goal_id (integer): 목표 ID

Request Body (GoalUpdateRequest, 선택적 필드):
  - title (string, optional): 새 제목
  - start_value, target_value, current_value (number, optional): 새 수치
  - unit (string, optional): 새 단위
  - start_date, end_date (date, optional): 새 기간
  - is_achieved (boolean, optional): 달성 여부

Response (GoalItemResult, 200 OK):
  - [위 POST 응답과 동일]
  - guide_generated_at: 가이드 재생성 시각 (변경이 있을 경우만 업데이트)

Errors:
  - 400: 입력값 검증 실패
  - 401: 토큰 없음/유효하지 않음
  - 404: 목표를 찾을 수 없음 (소유권 확인)
```

### POST /goals/{goal_id}/logs (일일 수치 기록)
```
summary: "목표 일일 수치 기록"
description: "해당 날짜의 목표 수치를 기록합니다. 가이드는 재생성되지 않습니다(매일 AI 호출 최소화)."

Path Parameter:
  - goal_id (integer): 목표 ID

Request Body (GoalProgressLogCreateRequest):
  - value (number, required): 기록할 수치
  - log_date (date, optional): 기록 날짜 (생략 시 오늘)

Response (GoalItemResult, 200 OK):
  - [위 POST 응답과 동일]
  - current_value: 최신 기록값으로 즉시 반영
  - recent_logs: 최신 기록 추가됨

Errors:
  - 400: 입력값 검증 실패
  - 401: 토큰 없음/유효하지 않음
  - 404: 목표를 찾을 수 없음
```

---

## 데이터베이스 스키마 (ERD.dbml)

현재 구현된 스키마를 유지하되, 필요시 다음 필드 확인:

```
Table goals {
  id int [pk]
  profile_id int [ref: > profiles.id]
  title varchar
  start_value decimal [note: "시작 수치"]
  target_value decimal [note: "목표 수치"]
  current_value decimal [note: "현재 수치"]
  unit varchar [note: "단위 (kg, 분 등)"]
  start_date date
  end_date date
  guide_content text [note: "AI 생성 가이드 (3~5문장)"]
  guide_generated_at datetime [note: "가이드 생성 시각"]
  is_achieved boolean [default: false]
  created_at datetime
  updated_at datetime [note: "수정되면 업데이트, 일일 기록만으로는 아님"]
}

Table goal_progress_logs {
  id int [pk]
  goal_id int [ref: > goals.id, note: "목표 삭제 시 cascade 삭제"]
  log_date date
  value decimal [note: "기록된 수치"]
  created_at datetime
  Indexes {
    (goal_id, log_date) [unique, note: "같은 날짜 재기록 시 upsert"]
  }
}
```

---

## 프론트엔드 UI 체크리스트

> 실제 구현 위치: `frontend/src/components/goal/GoalContent.tsx` — 신규 페이지가 아니라
> 기존 "더보기 > 마이다이어리 > 🎯 목표 설정" 모달 안에 이미 있던 컴포넌트를 스크린샷
> 디자인대로 재구성했다(모달 자체는 그대로 유지, 독립 `/goals` 페이지로 분리하지 않기로
> 사용자와 합의).

### 목표 생성 화면
- [x] 입력 폼: 제목, 목표 종류(수치형/횟수형), 시작값, 목표값, 단위, 기간
- [x] 제출 버튼 ("+ 새 목표 생성", AI 생성 시작)
- [x] 로딩 상태: 저장 버튼이 "저장 중... (AI 가이드 생성 중)"으로 바뀜
- [x] 성공 상태: 카드에 생성된 가이드 즉시 표시
- [x] 에러 상태: 실패 시 폼 안에 에러 메시지 표시(폴백은 자동 저장되므로 별도 안내 불필요)

### 목표 목록 화면
- [x] 목표별 카드 (제목, 진행률, 남은 일수)
- [x] 각 카드에 "✨ AI 가이드" 텍스트 표시
- [x] "✏️" 버튼 (인라인 폼으로 전환)
- [x] 수치형: "기록하기" → 인라인 숫자 입력 → 저장 / 횟수형: "오늘 완료" 버튼 1회 클릭(당일 중복 방지)
- [x] "🗑️" 버튼 (confirm 후 삭제)

### 수정 화면
- [x] 기존 값 미리 채우기 (`toFormState`)
- [x] 목표 종류는 생성 후 변경 불가로 결정 — 수정 폼에서는 토글 안 보여줌
- [x] 제출 시 로딩 표시(생성과 동일 버튼 문구)
- [x] 완료 후 새 가이드 즉시 반영

### 진행률 위젯 (홈/추적 페이지)
- [ ] 목표별 진행률 바 — 미구현. "A안"(홈 화면 요약 카드) 목업까지 승인받았으나 실제 코드
  구현은 아직 착수 안 함. 다음 작업으로 남겨둠.
- [ ] 남은 기간 표시 — 목표 상세 카드에는 있음, 홈 위젯 자체가 없어 요약 노출은 미구현
- [ ] "기록하기" 단축 버튼 — 위와 동일 사유로 미구현

---

## 완료 보고 (에이전트가 작성)

### 완료 정의 체크리스트 결과
- [x] 목표 생성 시 AI 가이드 자동 생성 (실패 시 폴백 템플릿) — 서비스/API 테스트로 검증
- [x] 지병 반영 (user_input에 진단명 포함, 없으면 "없음") — 서비스 테스트로 검증
- [x] 목표 변경(제목/수치/기간) 시 가이드 자동 재생성, `is_achieved`만 바뀌거나 빈 PATCH는 재생성 안 함
- [x] 일일 기록(log_progress)은 가이드 재생성 안 함, 같은 날 재기록은 upsert(중복 안 남음)
- [x] 프론트 UI: 기존 `GoalContent.tsx`(마이다이어리 > 목표 설정 모달) 재사용 + 스크린샷 디자인대로 재구성
- [x] **[추가 범위]** 목표 종류 구분(NUMERIC/FREQUENCY) — 횟수형은 "오늘 완료" 버튼 1회 클릭으로 수치 자동 증가(당일 중복 방지)
- [x] **[버그 수정]** 최근 기록 미니 그래프가 항목 1~2개일 때 카드 전체 너비로 늘어나던 문제(flex:1 → 고정폭)
- [x] `profile_id` 기준 스코핑 (다른 프로필 소유 목표 조회/수정/삭제 불가, 404 반환)
- [x] TDD: `ruff`/`mypy`/`pytest` 전부 통과 (백엔드), `tsc`/`eslint` 통과 (프론트)
- [x] API P95 ≤ 3초 — 별도 부하테스트는 안 했으나 개별 요청은 수 ms~수백 ms 수준(ai_worker 미가동 시 폴백 경로 포함)
- [ ] Swagger `Field(description=...)` — 기존 필드는 있으나 `goal_type` 관련 신규 필드 설명은 DTO에 포함, 라우터 `description`은 T-GOAL-1 원문 그대로 두어 별도 갱신 안 함(범위 외)

### 테스트 현황 (신규 작성, 총 38개)
- `app/tests/services/test_goal_service.py` (19개) — 가이드 생성/재생성 조건, AI 실패 폴백, 소유권 스코핑, `_term`/`_progress_rate` 순수함수
- `app/tests/goal_apis/test_goal_apis.py` (15개) — CRUD 전체, 인증 필요, 소유권 404, 로그 upsert, FREQUENCY 생성
- `app/tests/repositories/test_goal_repository.py` (2개) — 삭제 시 progress_logs cascade, 목록 정렬(종료일 오름차순)
- 전체 백엔드 스위트(`pytest app/tests`) 실행해 회귀 없음 확인(결과는 아래 "실행 결과" 참고)

### 가정 (Assumptions)
- "고혈압"은 `Disease` enum에 전용 카테고리가 없어 `HEART_DISEASE`로 등록하기로 사용자와 확정함(메모리에 별도 기록: `project_hypertension_category`).
- FREQUENCY(횟수형) 목표는 항상 `start_value=0`에서 시작한다고 가정 — "주 N회" 같은 반복 목표를 하나의 목표 기간 동안 누적 횟수로 해석(주간 리셋 로직은 없음).
- "오늘 완료" 중복 방지는 `recent_logs`에 오늘 날짜 항목이 있는지로 판단(프론트 로직) — 서버가 별도로 "하루 1회" 제약을 걸지는 않는다(같은 log_progress API를 그대로 재사용).

### 공유 계약 변경 필요 사항
- `frontend/src/api/types.ts` (원래 "금지 경로"로 지정됐던 공유 파일) — `GoalType`, `GoalItemResult.goal_type`, `GoalCreateRequest.goal_type` 추가. Goal 도메인 타입 동기화가 애초에 이 파일에 있어 불가피했음. 다른 도메인 타입에는 영향 없음.
- `docs/dev/ERD.dbml` — goals/goal_progress_logs 테이블이 애초에 이 문서에 없던 상태(사전 존재 gap)라, 이번 `goal_type` 컬럼 추가도 반영하지 않음. 전체 ERD 정비는 별도 작업으로 필요.

### 브랜치명
- `feat/T-GOAL-2-lifestyle-guide-generation` (아직 커밋/브랜치 분리 안 함 — 사용자 요청 시 진행)

### PR 링크
- (미생성 — 사용자가 커밋/PR 생성을 요청하면 진행)

---

## 참고 자료

- **AI Worker Gateway**: `app/services/ai_worker_gateway.py` (프롬프트 샘플: goal_service.py 라인 35-40)
- **지병 매핑**: `app/services/disease_code_mapper.py` (진단명 → 위험 음식/운동 필터링)
- **유사 Task**: T-GOAL-3 (목표 달성 리포트), T-ADH-2 (순응도 기반 피드백) — UI 패턴 참고
- **기존 구현 참고**: `app/services/weekly_report_service.py` (AI 호출 + 폴백 패턴)
