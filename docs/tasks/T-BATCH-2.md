# Task Contract 템플릿 (AI 워커 및 백엔드 전용)

---

## Task ID: T-BATCH-2 (Celery 13종 API 전체 수집망 및 일괄 봉인 시스템 구축)

### 참조
- PRD/TRD: N/A (이슈 #116 기반 시스템 인프라 구축, Phase 2)

### 목표
- 입력: 공공데이터포털 13종 API Endpoints (e약은요, 낱알식별, 회수 2종, 1일최대량, 묶음처방, DUR 성분별 7종)
- 출력/노출: `batch_worker/data/YYMMDD-*.csv` 파일 13종, `checkpoint.json` 상태 관리 및 봉인(Seal) 상태

### 완료 정의 (Definition of Done)
- [ ] 13종의 개별 API 수집 Task가 구현되었는가
- [ ] 공통 XML 파싱 로직 및 에러 처리 데코레이터(`handle_public_api_errors`)가 재사용 가능하게 구현되었는가
- [ ] 모든 Task가 `numOfRows=500` 단위 분할 수집 및 `checkpoint.json` Append 모드를 지원하는가
- [ ] Coordinator(코디네이터) Task를 통해 13종 파일이 모두 `"COMPLETED"` 되었을 때만 봉인을 해제(`ALL_SEAL_UNLOCKED = True`)하는가
- [ ] 기존 ReMedi 백엔드/프론트엔드 코드에 영향을 주지 않는가

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
batch_worker/**
docs/tasks/T-BATCH-2.md
docs/tasks/_active.json

### 금지 경로 (절대 수정하지 않음)
app/**
ai_worker/**
frontend/**
envs/**
infra/**
scripts/**

### 자율 판단 허용 범위
- Celery Task 함수명 설정, 코드 모듈화(공통 함수 분리 등), 봉인 체커 구현 방식(Celery chord 활용 또는 단순 스케줄 체커 등)

### 반드시 멈춰야 하는 경우
- 기존 DB 접근 권한이 필요한 경우 (아직 파싱/DB 저장 단계가 아님)

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/116-celery-batch-poc`
