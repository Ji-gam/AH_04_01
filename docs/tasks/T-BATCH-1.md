# Task Contract 템플릿 (AI 워커 및 백엔드 전용)

---

## Task ID: T-BATCH-1 (Celery 기반 단일 공공데이터 API 수집기 및 이어받기 PoC)

### 참조
- PRD/TRD: N/A (이슈 #116 기반 시스템 인프라 구축)

### 목표
- 입력: 공공데이터 `e약은요` API Endpoint
- 출력/노출: `batch_worker/data/YYMMDD-e약은요.csv` 파일, `checkpoint.json` 상태 저장

### 완료 정의 (Definition of Done)
- [ ] `batch_worker` 전용 디렉토리에 Celery Worker가 완전히 격리되어 구축되었는가
- [ ] 1개 API(e약은요)를 `numOfRows=500` 단위로 분할 요청하여 정상적으로 CSV 파일이 생성되는가
- [ ] 중간 실패(의도적 에러) 후 재실행 시, `checkpoint.json`의 `last_success_page` 이후부터 중복/누락 없이 Append 모드로 이어받는가
- [ ] 기존 ReMedi 백엔드/프론트엔드 코드(`app/`, `frontend/`)에 일절 영향을 주지 않는가
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가 (배치 워커용 테스트)
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
batch_worker/**
docs/tasks/T-BATCH-1.md
docs/tasks/_active.json

### 금지 경로 (절대 수정하지 않음)
app/**
ai_worker/**
frontend/**
envs/**
infra/**
scripts/**

### 자율 판단 허용 범위
- Celery Task 함수명 설정, Checkpoint JSON 포맷(스키마), CSV 파싱/저장 방식 설계

### 반드시 멈춰야 하는 경우
- `batch_worker` 내부에서 ReMedi 메인 데이터베이스나 기존 공유 인프라에 접근이 필요한 경우 (Phase 1에서는 금지)

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 모두 통과 (Celery 앱 격리, 500건 단위 분할 저장, Resume 테스트 등)
- 가정(Assumptions): `SIMULATE_ERROR` 환경변수를 통해 인위적 실패를 유도하여 `checkpoint.json`의 덧붙이기(Append) 동작을 검증함. 
- 공유 계약 변경 필요 사항 (있다면): 없음
- 브랜치명: `feat/116-celery-batch-poc`
