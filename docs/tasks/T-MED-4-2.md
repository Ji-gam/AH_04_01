# Task Contract 템플릿 (AI 워커 및 백엔드 전용)

---

## Task ID: T-MED-4-2 (약품 마스터 DB Tier 1 SQLite 자동 동기화 파이프라인)

### 참조
- 선행 문서: `docs/tasks/T-MED-4.md` — "Tier 1(SQLite)은 이번 작업 범위 밖이므로, 이번 단계는 API
  연동 확장까지만 진행하고, SQLite 연동은 팀원이 별도로 완성한 뒤 진행할 예정"이라 명시된 후속 작업.
- 관련 데이터: 공공데이터포털 의약품 관련 API 21종(e약은요, 낱알식별, 회수 2종, 1일최대량, 묶음처방,
  DUR 성분 기준 7종, DUR 제품 기준 9종)

### 목표
- 입력: 공공데이터포털 API 21종 Endpoint
- 출력/노출: `app/database/drugs_full.db`(전체 원본 DB), `app/database/drug_light.db`(경량화 DB),
  각 API별 `checkpoint_*.json` 재개 상태

### 완료 정의 (Definition of Done)
- [x] 21종 API를 페이지 단위(`numOfRows=500`)로 분할 수집하여 SQLite에 DB-First로 직접 적재
- [x] 중간 실패(네트워크 에러/정합성 불일치) 시 API별 체크포인트로 재개 가능
- [x] 전체 수집 완료 후 경량화 DB(`drug_light.db`) 자동 생성
- [x] 회수정보(PRDUCT) ↔ 마스터(itemSeq) 후처리 매핑 스크립트 포함
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가 — 아직 미작성, 후속 커밋 필요
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
scripts/drug_info_sync/**
docs/tasks/T-MED-4-2.md
docs/tasks/_active.json
```

### 금지 경로 (절대 수정하지 않음)
```
app/**  (단, app/database/*.db 산출물 생성은 허용 — 코드/스키마 수정은 금지)
ai_worker/**
frontend/**
envs/**
infra/**
```

### 자율 판단 허용 범위
- SQLite 스키마(동적 UNIQUE/INDEX 생성 방식), 체크포인트 파일 포맷, 병렬 처리 방식(멀티프로세스)

### 반드시 멈춰야 하는 경우
- `app/database/dur_drug_light.db`(기존에 커밋되어 있고 `app/repositories/dur_drug_repository.py`가
  실제로 참조하는 프로덕션 DB)를 대체하거나 이름을 맞추려면 리포지토리 코드 수정이 필요 — 이는
  `app/**` 영역이라 별도 태스크/승인 필요. 이번 단계에서는 신규 파이프라인 산출물
  (`drugs_full.db`, `drug_light.db`)만 만들고, 기존 프로덕션 DB 교체는 하지 않는다.

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: DB-First 수집/체크포인트/경량화 DB 생성/회수정보 매핑까지 구현. 테스트는
  아직 없음.
- 가정(Assumptions): 기존 `_data/api_test/` 프로토타입(CSV 기반, T-BATCH-1/2 Celery PoC)을 대체하는
  것으로 간주하고 폐기함. Celery 기반 13-Task/Coordinator 구조는 이 DB-First 파이프라인이
  기능적으로 상위 호환하므로 별도로 유지하지 않음(PR #119 폐기).
- 공유 계약 변경 필요 사항: 없음 (프로덕션 DB 교체는 후속 과제로 분리)
- 브랜치명: `feat/T-MED-4-2-drug-db-sync`
