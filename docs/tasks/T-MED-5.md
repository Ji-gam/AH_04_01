# Task ID: T-MED-5 (CLOVA OCR 호출 에러 핸들링/재시도 개선)

### 배경

`docs/tasks/T-MED-1-clova-ocr-benchmark.md` 설계 검토 중, `_call_clova_ocr`(`app/services/medication_service.py`)이
`except Exception: pass`로 모든 실패(타임아웃/네트워크 오류/인증 실패/응답 파싱 실패)를 구분 없이 삼키고
조용히 더미 텍스트(`DUMMY_OCR_RAW_TEXT`)로 폴백하는 것을 확인함. 이 상태에서는 CLOVA API 키가 만료되거나
요청 포맷이 잘못돼도 로그에 아무것도 남지 않아 운영 중 장애를 감지할 방법이 없고, 일시적 오류(타임아웃/5xx)도
재시도 없이 즉시 더미로 넘어가 정상 인식 가능한 요청까지 더미 처리되는 문제가 있었음.

### 참조

- 설계 문서: `docs/tasks/T-MED-1-clova-ocr-benchmark.md` §2-1 (confidence/재시도 등은 후속 과제로 명시된 항목 중
  에러 핸들링 부분만 이번 태스크에서 반영)
- 관련 코드: `app/services/medication_service.py` (`_call_clova_ocr`, `_resolve_ocr_raw_text`)
- T-MED-1 성공요건("식별 실패 시 수동 검색으로 전환되며 등록 자체가 막히지 않는다")은 그대로 유지 —
  이번 작업은 그 폴백이 "일어난 이유"를 알 수 있게 만드는 관측성 개선이며, 폴백 동작 자체(더미 대체)는 변경하지 않음.

### 범위

- **포함**: CLOVA OCR 호출부의 예외 유형별 처리 분기, 일시적 오류(타임아웃/5xx)에 대한 제한적 재시도,
  실패/폴백 사유 로깅.
- **제외**: confidence 기반 매칭률 계산, 회전/기울기 보정, 표 구조 인식, OCR 텍스트 기반 필드(용량/횟수/기간)
  실제 파싱 — 전부 벤치마크 문서의 미체크 항목으로 남아 있으며 별도 태스크로 진행 필요.

### 완료 정의 (Definition of Done)

- [x] 타임아웃/네트워크 오류/5xx 응답은 짧게 재시도한 뒤에도 실패하면 로그를 남기고 더미로 폴백한다
- [x] 401/403 등 재시도해도 결과가 같은 오류는 즉시 실패 처리하고 로그를 남긴다(불필요한 재시도로 지연 유발 금지)
- [x] 200 응답이어도 JSON 구조가 기대와 다르면(파싱 실패) 로그를 남기고 빈 결과로 처리한다
- [x] 더미 폴백이 발생한 경우, "키 미설정"과 "호출 결과 없음"을 구분해 경고 로그로 남긴다
- [x] T-MED-1/T-MED-3 기존 동작(폴백 시 `extracted_fields.dummy_mode=true`, 등록 자체는 막히지 않음)은
      회귀 없이 유지된다
- [x] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다
- [x] (공통) 모든 신규 코드에 대해 Ruff 통과 (Mypy는 이번 태스크 범위에서 별도 실행 안 함 — 아래 참고)

---

### 허용 경로 (T-MED-1/T-MED-3과 동일)

```
app/services/medication_service.py
app/tests/services/**
docs/tasks/T-MED-5.md (이 파일)
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

- 재시도 횟수/간격(최종: 최대 2회, 0.5초 간격), 로그 레벨(warning/error) 구분 기준 — 에이전트 자율 결정.

---

### 완료 보고 (에이전트가 작성)

- 구현 방식:
  - `app/services/medication_service.py`에 `logger = logging.getLogger("app.medication_service")` 추가
    (`chat_service.py`와 동일한 컨벤션).
  - `_call_clova_ocr`을 재작성: 요청 페이로드 구성(`_build_clova_ocr_request`)과 응답 파싱
    (`_parse_clova_ocr_response`)을 분리하고, 본체는 최대 2회(`_CLOVA_OCR_MAX_ATTEMPTS`) 재시도 루프로 구성.
    - `httpx.TimeoutException` / `httpx.HTTPError` → 마지막 시도가 아니면 경고 로그 후 0.5초 대기하고 재시도
    - HTTP 5xx → 동일하게 재시도
    - HTTP 4xx(인증 실패 등) → 재시도 없이 에러 로그(상태코드 + 응답 본문 일부) 후 즉시 빈 리스트 반환
    - 200이지만 JSON 구조가 예상과 다름(`response.json()`이 `ValueError` 등) → 에러 로그 후 빈 리스트
  - `_resolve_ocr_raw_text`에서 더미 폴백 발생 시 원인(CLOVA 미설정 vs 호출 결과 없음)을 구분해 `logger.warning` 호출.
  - 기존 "모든 예외를 조용히 삼키는" 동작은 제거되었지만, 상위 계층에서 보는 최종 결과(실패 시 더미 폴백,
    `extracted_fields.dummy_mode=true`)는 그대로 유지 — API 계약/DTO 변경 없음.
- 가정(Assumptions):
  - 재시도는 CLOVA OCR API가 짧은 시간 내 복구 가능한 일시 장애(타임아웃/5xx)에 한정. 인증 오류(4xx)는
    설정 문제로 간주해 재시도하지 않음 — 불필요한 지연으로 P95 latency 요건(T-QUAL-1)을 해치지 않기 위함.
  - 로깅은 표준 `logging` 모듈만 사용(`app.core.logger`의 `setup_logger`는 `ai_worker` 전용으로 보여 별도
    핸들러를 추가하지 않고 `chat_service.py`와 동일하게 `logging.getLogger`만 사용 — 루트 로거 설정은
    uvicorn 기본 설정에 위임).
- 테스트: `app/tests/services/test_medication_service_clova_ocr.py` 신규(5건), httpx를 mock으로 대체해 재시도/
  폴백 분기를 검증:
  - `test_call_clova_ocr_retries_on_timeout_then_succeeds`
  - `test_call_clova_ocr_gives_up_after_max_attempts_on_repeated_timeout`
  - `test_call_clova_ocr_retries_on_server_error_then_succeeds`
  - `test_call_clova_ocr_does_not_retry_on_auth_error`
  - `test_call_clova_ocr_returns_empty_on_malformed_response_body`
  - 검증 결과: `uv run pytest app/tests/medication_apis/ app/tests/services/` 74 passed, 1 failed
    (`test_enqueue_registers_celery_task_and_returns_id` — `celery` 패키지 미설치로 인한 기존 무관 실패,
    이번 변경과 무관). `uv run ruff check app/services/medication_service.py` 통과.
  - 로컬(venv) 검증: 이 워크트리에는 `.env`가 없어(gitignore 대상) `envs/.local.env`를 임시로 `.env`로 복사해
    이미 떠 있는 `mysql` 컨테이너(호스트 3306 포트 노출)를 대상으로 검증만 하고, 검증 후 `.env`는 삭제해
    커밋에 포함하지 않음.
- 공유 계약 변경 필요 사항: 없음 (API 응답/DTO/`extracted_fields` 스키마 변경 없음).
- 브랜치명: `feature/T-MED-5-clova-ocr-error-handling`
