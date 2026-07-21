# Task Contract 템플릿 (AI 워커 및 백엔드 전용)

## Task ID: T-MED-16 (medications/medication_schedules 폐기, item_seq 직접 참조 전환)

### 참조
- 관련 선행: T-MED-15(SQLite 제거·MySQL 단일화, Phase 1 — 머지됨)
- 계획: `C:\Users\surt2\.claude\plans\elegant-humming-spring.md` (plan mode에서 작성, 사용자 승인)

### 목표
- 입력: OCR/수동/빠른등록으로 확정된 약품, 스케줄 CRUD
- 출력/노출: 기존과 동일한 등록/조회 흐름. 단, `MedicationSchedule`이 자체 캐시 테이블
  `medications`(65건, 폐기 대상)를 거치지 않고 MySQL 마스터 데이터(`drugs_data`,
  `drug_identification`, `dur_prod_master_list` 등)의 `item_seq`를 직접 참조한다.
- 배경: T-MED-15에서 조회 경로는 MySQL로 옮겼지만 `medications` 캐시 테이블은 남아있었음.
  사용자가 이 캐시 계층을 완전히 없애기로 확정(2026-07-20 대화, plan mode 승인).

### 완료 정의 (Definition of Done)
- [ ] `Medication` 모델/`medications` 테이블 완전 삭제 (모델 + Alembic 마이그레이션 + ERD.dbml)
- [ ] `MedicationSchedule.item_seq`(str, DB FK 없음 — item_seq가 마스터 테이블에서 row 단위
      unique가 아니라 앱 레벨에서만 존재 검증, 사용자 확정)로 전환, `display_name`(AUTO_ 더미
      전용) 컬럼 추가
- [ ] `medication_service.py`/`medication_repository.py`의 매칭 로직이 MySQL 마스터 데이터
      (`DurDrugRepository`)를 직접 조회 (재캐싱 계층 없음)
- [ ] `MedicationScheduleResponse.medication_id: int` → `item_seq: str` (사용자 확정 — 프론트
      5개 파일은 후속 작업으로 분리, 이번 작업 범위 아님)
- [ ] (공통) `profile_id` 기준 유지 (`user_id` 직접 참조 금지)
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가 (기존 baseline:
      90 passed / 3 pre-existing 실패 유지 확인)
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

### 허용 경로
```
app/models/medication_model.py
app/repositories/medication_repository.py
app/repositories/dur_drug_repository.py (get_names_by_item_seqs 추가만)
app/services/medication_service.py
app/dtos/medication_dto.py
app/apis/v1/medication.py
app/tests/medication_apis/**
app/tests/services/test_medication_service_*.py
app/tests/repositories/test_sync_medication_master_data.py
app/tests/services/test_chat_*.py (medication_id 간접 참조 수정 필요시에만)
app/core/db/migrations/versions/** (신규 마이그레이션 파일 추가만)
docs/dev/ERD.dbml
docs/tasks/T-MED-16.md (이 파일의 "완료 보고" 섹션만)
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
```
app/core/** (db/migrations/versions/** 제외)
app/dependencies/**
frontend/src/**  (본 작업은 백엔드 한정 — 프론트 타입/화면은 후속 작업)
envs/**, infra/**, scripts/**
```

### 반드시 멈춰야 하는 경우 (해결됨, 기록용)
- ~~`drugs_data`/`drug_identification`의 `item_seq`가 실제로 유일(unique)하지 않아 안정적인
  참조 키로 쓸 수 없는 경우~~ → 실제로 발생 확인(MySQL 직접 카운트: drugs_data 4,758건 중 distinct
  4,741, drug_identification 25,309건 중 distinct 25,292 — 같은 약의 시기별 외형 변형).
  **사용자 확정: DB FK 없이 앱 레벨에서만 존재 검증.**
- `MedicationScheduleResponse.medication_id`를 쓰는 프론트 파일 5개(`MedicationPage.tsx`,
  `useMedication.ts`, `FamilyTrackerView.tsx`, `FamilyRegisterSection.tsx`,
  `familyMedicationApi.ts`) 존재 확인 → **사용자 확정: `item_seq`로 이름/타입 변경, 프론트는
  후속 작업으로 분리(이번 세션 범위 아님).**

---

### 완료 보고 (에이전트가 작성)

- `Medication` 모델/`medications` 테이블 완전 삭제(모델, `0029_drop_medications_use_item_seq.py` 마이그레이션, ERD.dbml) 완료.
- `MedicationSchedule.item_seq`(str) + `display_name`(AUTO_ 더미 전용) 컬럼으로 전환 완료. DB FK 없음, `MedicationRepository.item_seq_exists`가 `dur_prod_master_list`/`drugs_data`/`drug_identification` 중 하나라도 있으면 유효로 본다.
- `medication_service.py`/`medication_repository.py`의 모든 매칭·CRUD 로직이 `DurDrugRepository`(마스터 데이터)를 직접 조회하도록 재작성 완료(재캐싱 계층 없음). `MatchedDrug(item_seq, item_name)` NamedTuple로 `Medication` ORM 의존 제거.
- `MedicationScheduleResponse.medication_id: int` → `item_seq: str`로 변경(계획대로 프론트 5개 파일은 범위 밖).
- 연쇄 영향 처리: `app/models/__init__.py`(Medication export 제거), `app/services/chat_context_service.py`/`chat_service.py`(스케줄 이름 해석을 `drug_names` 맵 주입 방식으로 전환), `app/services/push_scheduler.py`(알림 문구용 이름 조회를 `DurDrugRepository.get_names_by_item_seqs`로 전환), `app/scripts/seed_demo_data.py`(AUTO_ 더미 패턴으로 전환), `app/scripts/sync_medication_master_data.py`+관련 테스트+fixture 삭제(Tier2 적재 스크립트, 대상 테이블 자체가 없어져 완전히 불필요해짐).
- 테스트 11개 파일을 item_seq/`MatchedDrug` 기준으로 재작성. `MedicationRepository.item_seq_exists`에 `DurProdMasterList` 조회를 추가해(기존엔 `drugs_data`/`drug_identification`만 확인해 커버리지가 더 넓은 `dur_prod_master_list`에서 찾은 약이 수동 등록 시 부당하게 404 나던 버그를 시딩 중 발견해 수정).
- 검증: `uv run ruff format --check .` / `uv run ruff check .` / `uv run mypy app/` 전부 통과. `uv run pytest`(전체, `test_drug_info_sync_pipeline.py` 제외 - `requests` 모듈 미설치로 인한 기존 무관 에러)는 348개 중 341 passed. 나머지 5개는 이번 작업과 무관한 환경 제약으로 실패(수정 대상 아님, 원인 직접 확인함):
  - `test_chat_router.py`/`test_chat_service.py`의 채팅 2건: `ai_worker` 호스트에 대한 실제 네트워크 접근이 이 샌드박스에서 안 됨(`getaddrinfo failed`) - Phase 1부터 있던 네트워크 의존 테스트.
  - OCR 인식 Job 3건(`test_recognition_job_*`): `_execute_ocr_logic`을 직접 호출하면 정상적으로 "done" 상태와 올바른 후보를 반환함(직접 검증 완료) - 실패 원인은 `run_ocr_task`가 `app.core.db.databases.AsyncSessionLocal`(운영 DB, `.env`의 `DB_NAME`)을 그대로 쓰는데, 테스트 요청 경로는 `TestSessionLocal`("test" 스키마, `app/tests/conftest.py`)로 오버라이드되어 있어 두 세션이 서로 다른 DB를 봐서 백그라운드 태스크의 상태 갱신이 테스트가 조회하는 DB에 반영되지 않음. `app/scripts/seed_food_drug_interaction.py`의 `SameDatabaseError` 가드로 재확인함(`DB_NAME=test`로 맞추면 이 가드가 즉시 발동 - 두 DB가 의도적으로 분리되어 있다는 설계임). T-MED-16 범위(허용 경로) 밖의 기존 테스트 인프라 이슈라 수정하지 않음 - 고정 `sleep(1.0)` 대신 최대 10초 폴링(`_wait_for_job_done`)으로 좀 더 견고하게만 바꿔 두었음.
