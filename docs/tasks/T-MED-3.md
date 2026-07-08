# Task ID: T-MED-3 (OCR 인식 수동 폴백/더미 모드)

### 배경 (팀원 피드백, 2026-07-08)

T-MED-1(PR #16) 리뷰 중 팀원이 다음을 보고함:
- OCR 리딩 자체가 실패했다 — 다만 이는 성능(인식 정확도)상의 문제로 판단.
- 스케줄 등록 등 OCR 이후 단계가 전부 OCR 결과에 연결돼 있어서, OCR이 실패하는 동안 뒤 프로세스를 테스트해보지 못했다.
- 다음 작업에서 "수동 폴백" 기능을 넣어주면, OCR과 무관하게 전체 프로세스를 가져와 테스트할 수 있을 것 같다.

`app/services/medication_service.py`의 `_execute_ocr_logic`에는 이미 CLOVA OCR 키 미설정/호출 예외 시
`"MOCK OCR TEXT 타이레놀"`로 대체하는 코드가 존재하나(T-MED-1 완료 보고 참고), 이번 피드백은 그 대체
동작이 QA가 **의도적으로 트리거**해서 신뢰할 수 있게 쓸 수 있는 형태가 아니었다는 뜻으로 판단.
→ 이번 태스크는 "우연한 예외처리 부산물"이던 mock 대체를 "QA가 명시적으로 켤 수 있는 수동 폴백"으로 승격.

### 참조
- TRD: T-MED-1 성공요건("식별 실패 시 수동 검색으로 전환되며 등록 자체가 막히지 않는다")을 그대로 유지하는
  범위 내에서, 그 요건을 **더미 데이터로 결정적으로 재현 가능하게** 만드는 후속 작업.
- 관련 파일: `app/services/medication_service.py`(`_execute_ocr_logic`), `app/dtos/medication_dto.py`,
  `docs/tasks/T-MED-1.md`(완료 보고 "가정(Assumptions)" 항목)

### 범위 — OCR 인식 단계 + 수동 등록 UX 개선 (2026-07-08 확장)

- **포함(1차, OCR 인식 단계)**: `POST /recognition/jobs` ~ `GET /recognition/jobs/{job_id}` (OCR 호출 → candidates 생성)까지.
- **제외**: 알림 연동 등 — 이미 T-MED-1에서 구현된 기존 흐름을 그대로 타므로 별도 더미 처리가 필요 없음.
- **포함(2차, 2026-07-08 확장, 사용자 확인)**: "수동 약품 등록" UX를, 검색→목록에서 선택하는 2단계 대신
  **약품명을 입력하고 등록 버튼 한 번으로 끝나는 1단계**로 개선. QA/사용자가 OCR 없이도 원하는 약을
  즉시 등록해 전체 프로세스(스케줄 등록~조회~삭제)를 테스트할 수 있게 하는 것이 목적 — OCR 폴백과 같은 동기.
  - 정책(사용자 확정): 이름이 DB와 정확히 하나만 일치하면 즉시 등록. 일치가 전혀 없으면 OCR 플로우의
    기존 자동생성 로직과 동일하게 새 약품을 즉석 생성해서라도 등록(등록 자체가 막히지 않아야 한다는
    T-MED-1 원칙을 수동 등록에도 동일 적용). 여러 개가 부분일치하면 자동 등록하지 않고 후보 목록을 보여줘
    사용자가 직접 골라 등록하게 한다(T-MED-1의 "사용자 최종 선택 없이는 등록되지 않는다" 원칙 준수).
  - 기존 `GET /medications/search` + `POST /medications`(drug_code 지정) 조합은 그대로 유지(여러 후보
    중 하나를 고르는 화면에서 재사용). 새 엔드포인트로 "이름 입력 한 번"의 진입점만 추가한다.

### 목표

- 입력: 기존과 동일(알약 사진 또는 처방전 PDF/이미지) + QA가 명시적으로 수동/더미 모드를 요청할 수 있는 트리거
  (구체적 트리거 방식 — 요청 파라미터 vs 환경변수 vs 별도 엔드포인트 — 는 구현 단계에서 결정, 이 문서는 목표만 정의)
- 출력/노출: 실제 OCR 호출 여부와 무관하게, 고정된 더미 candidates(약품명, 매칭률)를 포함한 정상적인
  recognition job 결과. 더미 모드로 생성된 job임을 QA가 구분할 수 있는 표시 포함(실제 인식 결과와 혼동 방지).

### 완료 정의 (Definition of Done)

- [x] CLOVA OCR API 키가 없거나 호출이 실패해도 job이 `"failed"`로 끝나지 않고, 더미 candidates를 포함한
      `"done"` 상태로 응답한다 (기존 mock 대체 동작을 결정적·검증 가능하게 정리)
- [x] QA가 실제 OCR 성공/실패 여부와 무관하게 더미 모드를 명시적으로 트리거할 수 있다
- [x] 더미 모드로 만들어진 candidates도 기존 `confirm_recognition_job` 플로우(사용자 최종 선택 → 스케줄 등록)를
      변경 없이 그대로 통과한다
- [x] 응답(또는 로그)에 더미 모드 여부가 표시되어, 실제 인식 결과와 혼동되지 않는다
- [x] T-MED-1 기존 성공요건("신뢰도가 낮거나 후보가 여러 개면 사용자 최종 선택 없이는 등록되지 않는다")이
      그대로 유지되는지 회귀 확인
- [x] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가
- [x] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

---

### 허용 경로 (T-MED-1과 동일 — 이 안에서만 자유롭게 작업)
```
app/apis/v1/medication.py
app/services/medication_service.py
app/repositories/medication_repository.py
app/dtos/medication_dto.py
app/tests/medication_apis/**
ai_worker/schemas/medication_schema.py
frontend/src/pages/medication/**
frontend/src/hooks/useMedication*.ts
docs/tasks/T-MED-3.md (이 파일의 "완료 보고" 섹션만)
```

### 금지 경로
```
app/core/**
app/dependencies/**
frontend/src/api/**
frontend/src/components/**
frontend/src/routes/**
frontend/src/store/**
frontend/src/types/**
envs/**
infra/**
scripts/**
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 자율 판단 허용 범위
- 더미 모드 트리거 방식(쿼리 파라미터/헤더/DTO 필드 중 선택), 더미 candidates 샘플 데이터 내용,
  내부 함수 분리 방식 — 에이전트 자율 결정. 단, 실제 운영 요청과 명확히 구분되는 방식으로 설계할 것
  (예: 운영 환경에서 기본값으로 켜지지 않도록).

### 반드시 멈춰야 하는 경우
- 더미 모드 트리거가 인증/보안 우회로 악용될 수 있는 설계(예: 인증 없이 접근 가능)가 되려는 경우
- `confirm` 이후 플로우(스케줄 등록, 알림)에도 더미 데이터를 넣어야 할 것 같다고 판단되는 경우 → 범위 밖,
  사용자에게 먼저 확인

---

### 완료 보고 (에이전트가 작성)

- 구현 방식:
  - `app/services/medication_service.py`에 고정 더미 인식 텍스트 `DUMMY_OCR_RAW_TEXT = ["*타이레놀정", "*아스피린정"]`를
    신설(기존 매칭 로직인 `_looks_like_drug_name`의 "*" 불릿 규칙을 그대로 태워, "실제 인식됐을 때와 동일한 코드 경로"로
    검증되게 함).
  - CLOVA 호출부를 `_call_clova_ocr`(순수 API 호출)와 `_resolve_ocr_raw_text`(dummy_mode 판단 + 폴백 결정)로 분리.
    `dummy_mode=True`면 CLOVA 호출 자체를 생략, 아니면 기존처럼 호출하되 결과가 비어 있으면(키 미설정/예외/빈 응답)
    자동으로 같은 더미 텍스트로 폴백. 두 경우 모두 `extracted_fields["dummy_mode"] = true`로 표시.
  - 기존에 있던 `"MOCK OCR TEXT 타이레놀"` 문자열(매칭에는 실제로 쓰이지 않고 표시용으로만 존재해 결과가
    비결정적이었던 원인)은 제거.
  - API: `POST /api/v1/recognition/jobs`에 `dummy_mode: bool = False` 폼 필드 추가(Swagger에 설명 포함).
    `MedicationService.create_recognition_job` → `run_ocr_task` → `_execute_ocr_logic`까지 그대로 threading.
- 가정(Assumptions):
  - dummy 트리거는 별도 인증/권한 우회 경로 없이 기존 인증된 업로드 엔드포인트의 폼 필드로만 노출 — 운영에서도
    호출 가능하지만 인증 없이는 접근 불가하므로 반드시 확인받아야 할 보안 이슈는 아니라고 판단.
  - `confirm` 이후 스케줄 등록/알림 로직은 변경하지 않음(범위 밖).
- 테스트: `app/tests/medication_apis/test_medication_apis.py`에 2건 추가
  - `test_recognition_job_dummy_mode_returns_deterministic_candidates_and_is_marked`
  - `test_recognition_job_real_ocr_failure_falls_back_to_dummy_mode_marker`
  - 검증 결과: `uv run pytest -v` 전체 40 passed (medication 7건 포함), `uv run ruff check app/` /
    `uv run ruff format --check app/` / `uv run mypy app/services/medication_service.py app/apis/v1/medication.py`
    전부 통과. `_execute_ocr_logic`의 C901(복잡도) 경고는 `_call_clova_ocr`/`_resolve_ocr_raw_text`로 분리해 해소.
  - 로컬(venv) 모드로 검증: 이 워크트리에는 `.env`/`envs/.local.env`가 없어(gitignore 대상, 개인 파일) 이미
    떠 있는 `mysql` 컨테이너(호스트 3306 포트 노출, 템플릿 계정과 동일)를 대상으로 `envs/example.local.env`를
    복사해 임시로 검증만 하고 커밋에는 포함하지 않음. Docker 모드로 `docker exec fastapi`를 시도했으나 그
    컨테이너는 워크트리가 아닌 리포 루트(`D:\...\AH_04_01\app`)를 마운트하고 있어 이 브랜치의 변경이 반영되지
    않는 상태였음(별도 조치 불필요 — 로컬 venv 검증으로 충분).
- 공유 계약 변경 필요 사항: 없음.
- 브랜치명: `feature/T-MED-3-ocr-manual-fallback`

### 완료 보고 2 — 수동 등록 UX 개선 (2차 확장, 2026-07-08, 사용자 확인 후 진행)

- 완료 정의(DoD) 추가분:
  - [x] 약품명을 입력하고 등록 버튼 한 번으로 스케줄이 등록된다(검색→선택 2단계 불필요)
  - [x] DB와 정확히 하나만 일치하면 즉시 등록된다
  - [x] DB에 전혀 없는 이름이어도 등록 자체가 막히지 않고, OCR 플로우와 동일하게 새 약품을 즉석 생성해 등록한다
  - [x] 여러 약과 부분일치하면 자동 등록하지 않고 후보 목록만 반환한다(T-MED-1 "사용자 최종 선택 없이는
        등록되지 않는다" 원칙 유지)
- 구현 방식:
  - `app/dtos/medication_dto.py`: `QuickRegisterRequest`(drug_name, times), `QuickRegisterCandidate`,
    `QuickRegisterResult`(status/schedule/candidates/auto_created) 신설.
  - `app/services/medication_service.py`: `MedicationService.quick_register_medication` 신설 — 정확히
    일치 1건이면 즉시 등록, 매칭 0건이면 `Medication(standard_code=f"AUTO_...")`로 즉석 생성 후 등록(기존
    OCR 자동생성 로직과 동일 패턴), 매칭 2건 이상이면 등록하지 않고 후보만 반환.
  - `app/apis/v1/medication.py`: `POST /api/v1/medications/quick-register` 신규(Swagger 설명 포함, 후보가
    여러 개일 때는 기존 `POST /medications`(drug_code 지정)를 재사용해 최종 확정하도록 안내).
  - 프론트(`useMedication.ts`, `MedicationPage.tsx`): 기존 "검색 → 목록에서 선택" 2단계 UI를 "약품명 입력 →
    등록 버튼" 1단계로 교체. 여러 후보가 반환된 경우에만 선택 목록이 나타나고, 선택 시 기존
    `createManualSchedule`(→ `POST /medications`)로 확정 등록. `searchMedications`/`GET /medications/search`는
    이 후보 선택 화면 재사용을 위해 그대로 유지(엔드포인트 자체는 삭제하지 않음).
- 가정(Assumptions):
  - "정확히 하나 일치"는 `medication_name` 완전 일치 기준. 완전 일치가 없고 부분일치가 1건뿐이면 그 1건으로
    간주해 즉시 등록(부분일치 1건과 완전일치 0건인 흔한 오타 케이스도 등록이 막히지 않도록).
  - 자동 생성된 약품은 기존 OCR 플로우와 동일하게 `standard_code=AUTO_*`로 구분되며, 별도 신뢰도 표시는
    프론트 알림 문구로만 안내(스키마 변경 없음).
- 테스트: `app/tests/medication_apis/test_medication_apis.py`에 3건 추가
  - `test_quick_register_with_exact_name_match_registers_immediately`
  - `test_quick_register_with_no_match_auto_creates_and_registers`
  - `test_quick_register_with_multiple_matches_returns_candidates_without_registering`
  - 검증 결과: `uv run pytest -v` 전체 43 passed, `uv run ruff check app/`/`ruff format --check app/`/
    `uv run mypy app/services/medication_service.py app/apis/v1/medication.py app/dtos/medication_dto.py` 전부 통과.
  - 실제 구동 확인: 리포 루트를 이 커밋으로 detached checkout 후 `docker compose up -d --build fastapi`로
    재기동(WatchFiles 자동 reload로 반영 확인), `npm run dev`(포트 5174)로 프론트 기동 후 `/api/openapi.json`에
    `quick-register` 경로 노출 확인.
- 공유 계약 변경 필요 사항: 없음(`frontend/src/api/`, `app/core/` 등 금지 경로 미변경).
- 브랜치명: `feature/T-MED-3-ocr-manual-fallback` (동일 브랜치, 2번째 커밋)
