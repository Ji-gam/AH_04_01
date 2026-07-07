# Task Contract 템플릿 (AI 워커 및 백엔드 전용)

> 사용법: T-그룹 하나당 이 템플릿을 복사해 `docs/tasks/T-XXX-N.md`로 저장하고 채웁니다.
> "입력/출력/성공요건"은 TRD에서 그대로 복사해오면 됩니다 — 이미 에이전트가 쓰기 좋은 형태입니다.
> 아래는 T-MED-1을 채운 예시입니다.

---

## Task ID: T-MED-1 (알약 인식 및 복약 스케줄 등록)

### 참조
- PRD: F-MED-1 / TRD: T-MED-1 / REQ: REQ-MED-001~004, REQ-MED-006~010

### 목표 (TRD 원문 그대로)
- 입력: 알약 사진 또는 처방전 PDF/이미지
- 출력/노출: 식별 후보 리스트(약품명, 매칭률), 최종 선택된 약품 상세정보, 등록된 복약 스케줄

### 완료 정의 (Definition of Done — TRD 성공요건 = 자동 검증 대상)
- [ ] 신뢰도가 낮거나 후보가 여러 개면 사용자 최종 선택 없이는 등록되지 않는다
- [ ] 식별 실패 시 수동 검색으로 전환되며 등록 자체가 막히지 않는다
- [ ] 스케줄 등록은 시간 선택 외 추가 입력 없이 완료 가능해야 한다
- [ ] (공통) 새 테이블/조회 로직은 `profile_id` 기준으로 설계되었는가 (`user_id` 직접 참조 금지)
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가
- [ ] (공통) API P95 Latency ≤ 3초
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

> 위 체크리스트를 그대로 테스트 케이스명으로 사용하세요. 예:
> `test("신뢰도 낮으면 자동 등록되지 않는다", ...)`

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
app/apis/v1/medication.py
app/services/medication_service.py
app/repositories/medication_repository.py
app/dtos/medication_dto.py
app/tests/medication_apis/**
ai_worker/tasks/medication_task.py
ai_worker/schemas/medication_schema.py
frontend/src/pages/medication/**
frontend/src/hooks/useMedication*.ts
docs/tasks/T-MED-1.md  (이 파일의 "완료 보고" 섹션만)
```

### 금지 경로 (절대 수정하지 않음 — 필요해 보여도 "공유 파일 변경 필요"로 보고만)
```
app/core/**
app/dependencies/**
ai_worker/core/**
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

### 의존하는 공유 계약 (읽기만 가능, 이미 고정됨)
- `app/dependencies/` — 로그인 사용자 인증 의존성 (`get_current_user`, `get_current_profile`)
- `app/models/medication_model.py` — 데이터베이스 테이블 모델 (SQLAlchemy ORM, `profile_id` FK)
- `frontend/src/api/endpoints/medication.ts` — API 클라이언트 정의

> 만약 위 계약을 변경해야만 성공요건을 충족할 수 있다면, 진행하지 말고 "완료 보고"에
> "공유 계약 변경 필요" 항목으로 구체적 변경 내용을 적어 보고합니다.

### 자율 판단 허용 범위
- OCR/Vision 라이브러리 내부 파라미터 튜닝, 매칭률 임계값 초기값 설정, 에러 메시지 문구,
  내부 함수 분리 방식 — 전부 에이전트 자율 결정.

### 반드시 멈춰야 하는 경우 (이 Task에 한정된 추가 조건)
- 매칭률 계산 로직이 다른 도메인(예: F-MED-2 상충 경고)의 데이터 구조 변경을 요구하는 경우

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/T-MED-1-...`
