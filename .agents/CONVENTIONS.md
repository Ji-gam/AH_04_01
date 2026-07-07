# CONVENTIONS.md — 코드/API/DB 통일 규칙

이 문서는 **"누가 어디를 작업하는가"(AGENTS.md/CLAUDE.md)가 아니라, "같은 종류의 코드를 짤 때 모양을 어떻게 통일하는가"**를 정합니다.
에이전트는 새 파일/함수/엔드포인트/테이블을 만들 때 항상 이 문서를 기준으로 삼고, 예시가 없는 경우에도 여기 있는 패턴을 그대로 따라 확장합니다.

---

## 0. 우선순위

같은 항목에 대해 다른 문서와 내용이 다르면 **이 문서(CONVENTIONS.md) > TRD/PRD > 각자 판단** 순으로 따릅니다.
단, 폴더 소유권/작업 범위는 `AGENTS.md`가 우선합니다. 이 문서는 "스타일"만 다룹니다.

**적용 범위**: 프론트엔드(React)는 `frontend/`로 백엔드(`app/`, `ai_worker/`)와 같은 레포(모노레포)
안에 있습니다. 이 문서의 1~4장(코드 스타일, 폴더 구조, API 명세, DB 네이밍)은 백엔드 기준이며,
프론트 세부 스타일은 팀의 `CODING_RULES.md` 3번(프론트엔드 규칙)을 따르되, **3장(API 명세)의
요청/응답 포맷·에러코드 규칙만은 계약이므로 프론트도 동일하게 따른다.**

---

## 1. 코드 스타일

### 1-1. 공통 네이밍
| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 변수/함수 | snake_case | `get_user_by_id` |
| 클래스(Pydantic DTO, SQLAlchemy Model) | PascalCase | `MedicationScheduleDTO`, `MedicationSchedule` |
| 상수/Enum 값 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| 파일명 | snake_case | `medication_service.py` |
| Boolean 변수/필드 | is/has/can 접두사 | `is_active`, `has_consent` |

### 1-2. 포맷터/린터/패키지 관리 (질문 없이 고정)
- 패키지 매니저: `uv` (`pyproject.toml` + `uv.lock`) — pip 직접 설치 금지
- 포맷/린트: `ruff format` + `ruff check` (line-length 100)
- 타입체크: `mypy` 필수 통과 (모든 함수 시그니처에 타입 힌트 명시)
- 커밋 전 `uv run ruff check . && uv run mypy .` 통과 확인. 실패한 코드는 PR 올리지 않음.

### 1-3. 에러/예외 처리
- 백엔드는 반드시 `HTTPException` (혹은 공용 `AppException`)으로 던지고, 문자열 그대로 노출 금지.
- 에러 메시지는 사용자용(한국어, 간결)과 로그용(영어, 상세)을 분리.
- 절대 `except: pass`로 조용히 삼키지 않음 — 최소 `logger.warning`/`logger.error` 남길 것.

### 1-4. 주석/TODO
- 스텁/미완성 코드는 반드시 `# TODO(T-ID): 설명` 형태로 표시 (예: `# TODO(T-MED-1): OCR 후보 매칭률 로직 미구현`).
- Task ID 없는 TODO는 남기지 않음 (누가 언제 할지 추적 불가해짐).

### 1-5. 테스트 (TDD)
- 테스트를 먼저 작성하고 구현한다. 완료 정의(Task Contract의 체크리스트)를 그대로 테스트 케이스명으로 옮긴다.
- 위치: `app/tests/{도메인}_apis/test_*.py` (예: `app/tests/medication_apis/test_schedule.py`).
- `uv run pytest -v` 통과가 완료 보고의 전제 조건이다.

---

## 2. 폴더/파일 구조 상세 (레이어별 표준 배치)

`AGENTS.md`의 구조는 도메인별 폴더가 아니라 **레이어별 폴더**(`apis/`, `dtos/`, `services/`, `repositories/`, `models/`)입니다.
도메인 구분은 폴더가 아니라 **파일명**으로 합니다. 새 도메인을 추가할 때도 아래 레이어에
같은 이름 규칙으로 파일을 하나씩 만들어 시작합니다.

```
app/
├─ apis/v1/{도메인}.py             # 예: apis/v1/medication.py — 엔드포인트 정의만, 로직 없음
├─ dtos/{도메인}_dto.py             # 예: dtos/medication_dto.py — Pydantic 요청/응답 모델
├─ services/{도메인}_service.py     # 예: services/medication_service.py — 비즈니스 로직
├─ repositories/{도메인}_repository.py # 예: repositories/medication_repository.py — DB 쿼리(SQLAlchemy AsyncSession)
├─ models/{도메인}_model.py         # 예: models/medication_model.py — SQLAlchemy ORM 모델
├─ dependencies/                    # [공유 구역] get_current_user, get_current_profile — 수정 금지 대상
├─ tests/{도메인}_apis/test_*.py    # TDD로 구현보다 먼저 작성 — 예: tests/medication_apis/test_schedule.py
└─ core/                            # [공유 구역] DB Engine/Session 설정, JWT, 공통 유틸/검증기 — 수정 금지 대상
```

```
ai_worker/                          # ※ 아직 내부 로직 미구현 상태 (AGENTS.md 참조)
├─ tasks/{도메인}_task.py           # 예: tasks/ocr_task.py — OCR/LLM 비동기 큐 작업
├─ schemas/{도메인}_schema.py       # 큐 payload용 Pydantic 스키마
└─ core/                            # [공유 구역] 워커 설정, 로거 — 수정 금지 대상
```

```
frontend/src/pages/{도메인}/       # Page 컴포넌트. Page → Hook(src/hooks) → api(src/api) 순서로 호출한다.
```

**규칙**:
- 레이어를 건너뛰지 않는다 (`apis` → `services` → `repositories` → `models` 순서만).
  `services`가 `models`를 직접 조회하지 않고 `repositories`를 거친다. `apis`가 `repositories`/`models`를 직접 호출하지 않는다.
- SQLAlchemy는 `AsyncSession` 기반이므로 모든 DB 접근 함수는 `async def` + `await` 필수이며,
  세션은 `Depends(get_db_session)` 등으로 주입받는다(직접 `Session()` 생성 금지).
- 한 도메인의 파일이 여러 레이어에 걸쳐 있으므로, 도메인 이름(`medication`, `auth` 등)은
  전 레이어에서 **철자까지 동일하게** 맞춘다 (예: `medication` vs `medications` 혼용 금지).
- `dtos/`는 API 요청/응답 스키마 전용 폴더 하나만 사용한다. 비슷한 이름의 폴더를 새로 만들지 않는다.

---

## 3. API 명세 규칙

### 3-1. 엔드포인트 네이밍
- 경로: `/api/v1/{도메인}/{리소스}` (복수형, kebab-case) — 예: `/api/v1/medication/schedules`
  (`apis/v1/` 폴더 버전과 경로 버전을 항상 일치시킨다)
- 동사를 경로에 쓰지 않음. HTTP 메서드로 표현: `GET`(조회) `POST`(생성) `PATCH`(부분수정) `PUT`(전체수정) `DELETE`(삭제)
- 예외적으로 상태 변경 트리거만 동사 허용: `/api/v1/medication/schedules/{id}/complete`

### 3-2. 요청/응답 공통 포맷 (고정, 새 엔드포인트도 반드시 준수)
성공 응답:
```json
{ "success": true, "data": { ... }, "message": null }
```
에러 응답:
```json
{ "success": false, "data": null, "message": "사용자에게 보여줄 메시지", "error_code": "MED_001" }
```
- 리스트 응답은 `data`에 `{ "items": [...], "total": N, "page": N }` 형태(페이지네이션 필요 시)
- `error_code`는 `{도메인 3글자}_{3자리 숫자}` (예: `AUTH_001`, `MED_002`) — `docs/error-codes.md`에 누적 기록.

### 3-3. 상태 코드
| 상황 | 코드 |
| --- | --- |
| 조회/수정 성공 | 200 |
| 생성 성공 | 201 |
| 입력값 오류 | 400 |
| 인증 실패/토큰 없음 | 401 |
| 권한 없음 | 403 |
| 리소스 없음 | 404 |
| 서버 내부 오류 | 500 |

### 3-4. 필수 사항
- 모든 신규 엔드포인트는 FastAPI docstring/`summary`/`description`으로 설명, 에러 응답, 필드 설명을 남길 것 (Swagger `/api/docs` 자동화).
- 인증 필요 엔드포인트는 `Depends(get_current_user)` 또는 `Depends(get_current_profile)`을 명시한다(임의 우회 금지).
  개인 데이터(건강정보 등)를 다루는 엔드포인트는 `user_id`가 아니라 `profile_id` 기준으로 조회/기록한다.
- 로그인/회원가입/토큰 재발급 응답: 바디에는 `access_token`과 `profile_id`만 포함하고, `refresh_token`은
  바디에 노출하지 않는다(HttpOnly 쿠키 등으로 전달).
- 날짜/시간은 항상 ISO 8601 UTC 문자열로 응답 (`2026-07-04T10:00:00Z`), `frontend/`에서 로컬 변환.

---

## 4. DB/ERD 네이밍 규칙

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 테이블명 | snake_case, 복수형 | `medication_schedules` |
| 컬럼명 | snake_case | `created_at`, `profile_id` |
| PK | 항상 `id` (`mapped_column(primary_key=True)`) | `id` |
| FK | `{참조테이블 단수}_id` (SQLAlchemy `ForeignKey`) | `profile_id`, `medication_id` |
| 생성/수정 시각 | 모든 모델에 필수 (`server_default=func.now()` / `onupdate=func.now()`) | `created_at`, `updated_at` |
| 삭제 | 하드 삭제 대신 소프트 삭제 우선 | `deleted_at` (nullable) |
| Boolean 컬럼 | is/has 접두사 | `is_active`, `has_consent` |
| Enum 값 | DB에는 문자열로 저장, UPPER_SNAKE_CASE | `"COMPLETED"`, `"PENDING"` |

- 새 테이블 추가 시 **반드시** `app/models/{도메인}_model.py` 변경 + `docs/dev/ERD.dbml`(dbdiagram.io) 동시 갱신.
  DB에 CRUD가 생기는 모든 변경에 대해 ERD도 같이 갱신한다 — 둘 중 하나만 바뀌면 안 됨.
- PII(개인식별정보)와 건강정보 테이블은 물리적으로 분리하고, FK로만 연결 (AGENTS.md 3장 T-ARCH-1 참조).
  구체적으로 `User`(계정/인증)와 `Profile`(개인정보)을 분리하고, **신규 도메인 테이블은 `profile_id`를
  FK 기준으로 삼는다**(서포터그룹처럼 한 계정이 여러 프로필을 가지는 확장을 대비).
- 마이그레이션은 반드시 **Alembic**으로 생성한다 (`uv run alembic revision --autogenerate -m "{설명}"` 후
  `uv run alembic upgrade head`). DB에 수동 ALTER 금지.

---

## 5. 공용 타입/상수 관리

- 백엔드 전체에서 쓰는 값(에러코드, enum, 상태값 등)은 **`app/core/constants.py` 한 곳에서만** 정의한다.
- 같은 의미의 상수를 도메인마다 각자 다시 정의하지 않는다 (예: 복약 상태값을 medication에서 또 만들고 tracking에서 또 만드는 것 금지).
- 새 Enum/상수 추가 시 `docs/shared-glossary.md`에 한 줄 등록 (이름, 의미, 사용 도메인).
- 프론트(`frontend/`)와 코드 레벨로 값을 공유하는 패키지가 없으므로(예: `packages/shared` 없음),
  `error_code`/enum 값이 바뀌면 PR 설명에 `[API 계약 변경]` 태그를 달고 프론트 담당자에게 별도로 공지한다.

---

## 6. 새 도메인/기능 시작 전 5초 체크리스트

- [ ] 폴더 구조가 2장의 표준 레이아웃과 같은가 (repositories 레이어 포함)
- [ ] 응답 포맷이 3-2 형식을 따르는가
- [ ] 새 테이블/컬럼 네이밍이 4장 규칙과 같은가, FK가 `profile_id` 기준인가
- [ ] `docs/dev/ERD.dbml`을 같이 갱신했는가
- [ ] 테스트를 구현보다 먼저 작성했는가(TDD)
- [ ] 공용으로 쓸 값을 도메인 로컬에 새로 만들지 않았는가
- [ ] lint/format/mypy/pytest 통과했는가
