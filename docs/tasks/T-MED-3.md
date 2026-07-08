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

### 범위 — OCR 인식 단계만 (사용자 확정, 2026-07-08)

- **포함**: `POST /recognition/jobs` ~ `GET /recognition/jobs/{job_id}` (OCR 호출 → candidates 생성)까지.
- **제외**: 스케줄 등록(`confirm`) 이후, 알림 연동 등 — 이미 T-MED-1에서 구현된 기존 흐름을 그대로 타므로
  이번 태스크에서 별도 더미 처리가 필요 없음. (OCR 단계에서 유효한 candidates를 만들어주면 이후 단계는
  실제 OCR 결과를 받았을 때와 동일하게 동작해야 함 — 이것이 이 태스크의 검증 기준이 된다.)

### 목표

- 입력: 기존과 동일(알약 사진 또는 처방전 PDF/이미지) + QA가 명시적으로 수동/더미 모드를 요청할 수 있는 트리거
  (구체적 트리거 방식 — 요청 파라미터 vs 환경변수 vs 별도 엔드포인트 — 는 구현 단계에서 결정, 이 문서는 목표만 정의)
- 출력/노출: 실제 OCR 호출 여부와 무관하게, 고정된 더미 candidates(약품명, 매칭률)를 포함한 정상적인
  recognition job 결과. 더미 모드로 생성된 job임을 QA가 구분할 수 있는 표시 포함(실제 인식 결과와 혼동 방지).

### 완료 정의 (Definition of Done)

- [ ] CLOVA OCR API 키가 없거나 호출이 실패해도 job이 `"failed"`로 끝나지 않고, 더미 candidates를 포함한
      `"done"` 상태로 응답한다 (기존 mock 대체 동작을 결정적·검증 가능하게 정리)
- [ ] QA가 실제 OCR 성공/실패 여부와 무관하게 더미 모드를 명시적으로 트리거할 수 있다
- [ ] 더미 모드로 만들어진 candidates도 기존 `confirm_recognition_job` 플로우(사용자 최종 선택 → 스케줄 등록)를
      변경 없이 그대로 통과한다
- [ ] 응답(또는 로그)에 더미 모드 여부가 표시되어, 실제 인식 결과와 혼동되지 않는다
- [ ] T-MED-1 기존 성공요건("신뢰도가 낮거나 후보가 여러 개면 사용자 최종 선택 없이는 등록되지 않는다")이
      그대로 유지되는지 회귀 확인
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

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
- (미작성 — 코드 구현 시작 전, 문서 단계만 완료)
