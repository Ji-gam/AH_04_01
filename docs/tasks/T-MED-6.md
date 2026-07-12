# Task ID: T-MED-6 (OCR confidence 기반 매칭률 계산)

### 배경

`docs/tasks/T-MED-1-clova-ocr-benchmark.md` §3-1에서 "바로 구현 가능"으로 명시했던 항목 중
"OCR confidence → 매칭률(%) UI 노출"이 실제로는 반영되지 않은 채, `_execute_ocr_logic`
(`app/services/medication_service.py`)의 `match_rate`가 완전히 하드코딩되어 있었음:

```python
if med.id in auto_created_ids:
    match_rate = 0.5
else:
    match_rate = 1.0 if "타이레놀" in med.medication_name else 0.85
```

즉 "타이레놀"이 이름에 포함되면 무조건 100%, 그 외 매칭은 무조건 85% — CLOVA OCR이 그 텍스트를
실제로 얼마나 확신했는지와 전혀 무관했다. CLOVA General OCR 응답의 `fields[].inferConfidence`는
`_call_clova_ocr`이 `inferText`만 뽑고 버려온 값으로, T-MED-5(에러 핸들링 개선) 완료 후 이어서
이 값을 실제로 활용하도록 하는 것이 이번 태스크의 목표.

### 참조

- 설계 문서: `docs/tasks/T-MED-1-clova-ocr-benchmark.md` §2-1("필드별 confidence score"), §3-1
- 관련 코드: `app/services/medication_service.py` (`_call_clova_ocr`, `_parse_clova_ocr_response`,
  `_match_existing_by_word`, `_resolve_or_create_drug_like_names`, `_match_or_create_medications`,
  `_execute_ocr_logic`)
- 선행 작업: `docs/tasks/T-MED-5.md` (CLOVA OCR 에러 핸들링/재시도)

### 범위

- **포함**: CLOVA OCR 응답에서 `inferConfidence`를 함께 파싱, 매칭 파이프라인 전체에 confidence를
  실어 날라 실제 `match_rate` 계산에 반영, 마스터 DB에 없어 즉석 생성된(AUTO_) 약품은 상한을 둠.
- **제외**: 회전/기울기 보정(`enableRotate`), 표 구조 인식, 용법 텍스트 실제 파싱(용량/횟수/기간),
  confidence 임계값 미만일 때 자동으로 수동 검색 화면 전환 — 전부 벤치마크 문서의 별도 액션
  아이템으로 남아 있으며 후속 태스크 대상.

### 완료 정의 (Definition of Done)

- [x] CLOVA OCR 응답의 `inferConfidence`를 `inferText`와 함께 파싱한다 (없거나 숫자가 아니면 0.0)
- [x] 마스터 DB에 이미 있는 약의 `match_rate`는 하드코딩된 값이 아니라, 그 약을 인식한 OCR 필드의
      실제 confidence를 그대로 사용한다
- [x] 마스터 DB/공공 API에 없어 즉석 생성된(AUTO_) 약품은 OCR confidence가 아무리 높아도
      `match_rate`에 상한(0.5)이 적용된다 — "검증되지 않은 신규 등록"이라는 리스크가 남기 때문
- [x] OCR 텍스트가 약품명처럼 전혀 안 보여 마스터 DB 상위 몇 개를 참고용으로만 보여주는 경우
      (기존 폴백), 실제 OCR 근거가 없으므로 낮은 `match_rate`(0.3)를 부여해 수동 확인을 유도한다
- [x] dummy_mode(T-MED-3) 폴백은 confidence=1.0인 결정적 텍스트로 취급되어 기존 흐름과 동일하게
      동작한다 (더미 후보의 `match_rate`가 여전히 유효한 값)
- [x] T-MED-1/T-MED-3/T-MED-5 기존 동작(후보 여러 개/신뢰도 낮으면 사용자 확인 필수, 등록 자체는
      막히지 않음, 에러 핸들링/재시도) 회귀 없음
- [x] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다
- [x] (공통) 모든 신규 코드에 대해 Ruff 통과, Mypy 통과

---

### 허용 경로

```
app/services/medication_service.py
app/tests/services/**
app/tests/medication_apis/test_medication_apis.py
docs/tasks/T-MED-6.md (이 파일)
```

### 금지 경로

```
app/core/**
app/dependencies/**
app/apis/v1/medication.py (API 계약 변경 없음 — 내부 구현만 수정)
frontend/**
envs/**
infra/**
scripts/**
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 자율 판단 허용 범위

- confidence 파싱 실패 시 기본값(0.0), AUTO_ 생성 약품의 match_rate 상한값(0.5),
  OCR 근거가 전혀 없을 때의 기본 match_rate(0.3) — 전부 매칭률 임계값 성격의 내부 파라미터로
  에이전트 자율 결정.

### 반드시 멈춰야 하는 경우

- confidence 임계값 미만 시 자동 수동 검색 전환처럼 API 응답 스키마(`RecognitionResult` 등)나
  프론트 계약 변경이 필요해지는 경우 → 범위 밖, 사용자에게 먼저 확인.

---

### 완료 보고 (에이전트가 작성)

- 구현 방식:
  - `app/services/medication_service.py`에 `OcrField(NamedTuple)` 추가 — `text`/`confidence` 한 쌍.
  - `_parse_clova_ocr_response`가 `list[str]` 대신 `list[OcrField]`를 반환하도록 변경.
    `inferConfidence`가 없거나 `float()` 변환에 실패하면 0.0으로 취급.
  - `_call_clova_ocr` / `_resolve_ocr_fields`(구 `_resolve_ocr_raw_text`)도 동일하게 `list[OcrField]`
    반환으로 변경. 더미 모드 텍스트(`DUMMY_OCR_RAW_TEXT`)는 confidence 개념이 없는 결정적 데이터라
    `_dummy_ocr_fields()`에서 고정 confidence=1.0을 부여해 실제 인식과 동일한 코드 경로를 태움.
  - `_match_existing_by_word`/`_resolve_or_create_drug_like_names`/`_match_or_create_medications`가
    각각 "약품 id → 그 약을 인식한 OCR 필드의 최대 confidence" 맵(`match_confidence`)을 추가로
    반환하도록 시그니처 확장(각각 2-tuple/3-tuple → 튜플에 confidence 맵 추가).
  - `_compute_match_rate(confidence, *, is_auto_created)` 순수 함수 신설 — 신규 생성(AUTO_) 약품은
    `min(confidence, 0.5)`로 상한을 두고, 그 외는 confidence를 그대로 사용. 기존 "타이레놀=1.0,
    그 외=0.85, 신규=0.5" 하드코딩 로직 완전히 제거.
  - `_execute_ocr_logic`에서 OCR 근거가 없는 약(참고용 상위 3개 폴백)은 `match_confidence`에
    항목이 없으므로 기본값 `_NO_OCR_EVIDENCE_MATCH_RATE = 0.3`을 적용.
- 가정(Assumptions):
  - AUTO_ 생성 약품의 match_rate 상한은 0.5로 유지(기존 하드코딩 값과 동일선상) — OCR이 아무리
    확신해도 마스터 DB 검증이 안 된 신규 등록이라는 리스크는 별개라고 판단.
  - OCR 텍스트가 전혀 약품명처럼 안 보여 "참고용 상위 3개"만 보여주는 기존 폴백 케이스는 사용자가
    반드시 수동 검색으로 전환하도록 유도해야 해서 낮은 고정값(0.3)을 부여. 별도 프론트 변경(자동
    수동 검색 전환 UI)은 범위 밖으로 남김.
  - 더미 텍스트(예: `*타이레놀정`)가 마스터 DB의 정식명(`타이레놀정 500mg`)과 공백/용량 차이로
    정확히 일치하지 않아 별도 AUTO_ 더미가 함께 생성되는 기존 동작(T-MED-3 때부터 있던 현상)은
    이번 태스크 범위 밖이라 손대지 않음 — 관련 테스트 어서션은 시드된 약품(`drug_code` 기준)만
    확인하도록 좁힘.
- 테스트:
  - `app/tests/services/test_medication_service_clova_ocr.py`: 기존 5건을 confidence 포함 응답으로
    갱신하고, confidence 누락/비정상 값 기본 처리 검증 1건 추가.
  - `app/tests/services/test_medication_service_public_api_fallback.py`: `_match_or_create_medications`
    반환 튜플이 3-tuple(confidence 맵 포함)로 바뀐 것에 맞춰 3건 갱신.
  - `app/tests/services/test_medication_service_ocr_confidence.py` 신규(5건):
    - `_compute_match_rate`가 confidence를 그대로 쓰는지 / AUTO_ 생성 시 상한을 두는지
    - `_match_or_create_medications`가 기존 매칭/신규 생성 약품 각각에 대해 올바른 confidence를
      맵에 담는지, OCR 근거가 없는 폴백 약품은 맵에서 빠지는지
  - `app/tests/medication_apis/test_medication_apis.py`: dummy_mode 테스트에 "시드된 두 약(코드
    기준)의 match_rate가 1.0"이라는 어서션 추가(하드코딩된 "타이레놀만 1.0" 로직이 아님을 확인).
  - 검증 결과: `uv run pytest app/tests/medication_apis/ app/tests/services/` 123 passed, 1 failed
    (`test_enqueue_registers_celery_task_and_returns_id` — `celery` 패키지 미설치로 인한 기존
    무관 실패). `uv run ruff check .` / `uv run ruff format --check .` / `uv run mypy
    app/services/medication_service.py` 전부 통과.
  - 로컬(venv) 검증: 이 워크트리에는 `.env`가 없어(gitignore 대상) `envs/.local.env`를 임시로
    `.env`로 복사해 이미 떠 있는 `mysql` 컨테이너를 대상으로 검증만 하고, 검증 후 `.env`는 삭제해
    커밋에 포함하지 않음.
- 공유 계약 변경 필요 사항: 없음(API 응답/DTO 스키마 변경 없음 — `match_rate` 필드 타입은 그대로
  `float`, 값 계산 로직만 개선).
- 브랜치명: `feature/T-MED-6-ocr-confidence-matching`
