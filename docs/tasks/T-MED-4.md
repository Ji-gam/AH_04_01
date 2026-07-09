# Task ID: T-MED-4 (약품 마스터 데이터 DB 적재 및 활용)

### 배경 (2026-07-08)

T-MED-1(PR #16, `feat/T-MED-1-pill-ocr`) 구현 조사 중 다음이 확인됨:

- `app/models/medication_model.py`의 `Medication` 테이블 주석은 "의약품 마스터 데이터 테이블
  (DUR / 식약처 의약품 사전 등 기준)"이라 되어 있으나, 실제로는 **시드 데이터가 전혀 없는 빈 테이블**로
  마이그레이션됨(`0004_create_medications_and_schedules_tables.py`).
- `app/services/medication_service.py`의 `_match_or_create_medications`는 OCR 텍스트가 DB에서
  매칭되지 않으면 `standard_code=f"AUTO_{uuid4()}"`, `match_rate=0.5`로 **이름만 채운 더미 레코드를
  즉석 생성**한다. 성분/효능/DUR 등 실제 약품 정보는 채워지지 않음.
- `docs/decision_log.md` "미결사항"의 "DUR 병용금기 데이터 수집" 항목이 이 공백을 시사하고 있었으나,
  약품 마스터 데이터 자체를 어디서/어떻게 적재할지에 대한 팀 결정은 없었음.
- 응답 속도 요건(사용자 목표: 알약 인식 3~5초 이내 응답)을 고려하면, 매칭 시점마다 외부 공공 API를
  동기 호출하는 방식은 지연/장애 리스크가 크다고 판단 — 배치 동기화 후 로컬 DB 조회 방식으로 결정.

### 방향 전환 — 3계층(Tier) 조회 전략 (사용자 확정, 2026-07-08 추가 논의)

팀원 피드백: 전체 의약품(수만 건)을 전부 로컬 DB에 적재하면 무거워지므로, 자주 조회되는 약품만 로컬에
캐싱하고 나머지는 API로 실시간 조회하는 계층 구조로 변경:

- **Tier 1 (자주 쓰이는 약 100~200건)**: SQLite에 적재 — **단, SQLite 연동 자체는 팀원이 별도로 DB
  연결 구조를 완성한 뒤 진행할 예정.** 이번 T-MED-4 범위에서는 SQLite 파일을 직접 만들지 않는다.
- **Tier 2 (종종 쓰이는 약)**: 기존 MySQL `medications` 테이블에 적재.
- **Tier 3 (거의 안 보는 약)**: 로컬에 없으면 공공데이터포털 API를 실시간 호출해서 가져옴.

→ 이전에 "실시간 매칭 경로는 외부 API를 호출하지 않는다"고 했던 결정은 **Tier 3에 한해 뒤집힘**
(응답속도 3~5초 목표는 Tier 1/2, 즉 자주 조회되는 약품 기준으로 완화 적용). Tier 1(SQLite)은 이번
작업 범위 밖이므로, 이번 단계는 **API 연동 확장(DUR, e약은요 추가)까지만** 진행하고, Tier 라우팅
로직(어떤 약을 SQLite/MySQL/API 중 어디서 찾을지 결정하는 부분)은 SQLite 연동이 준비된 후 후속
작업으로 넘긴다.

### 참조

- TRD: T-MED-1 성공요건(`docs/plan/TRD_ReMedi_v1.1.md` 86-93줄)의 "식별 후보 리스트(약품명, 매칭률),
  최종 선택된 약품 상세정보" 출력을 실제 약품 마스터 데이터로 채우기 위한 선행/후속 작업. TRD에는
  데이터 출처가 명시되어 있지 않아 이번 문서에서 정의함(사용자 확인, 2026-07-08).
- 관련 파일: `app/models/medication_model.py`, `app/services/medication_service.py`,
  `app/repositories/medication_repository.py`, `app/core/db/migrations/versions/0004_*.py`

### 범위 — API 연동 확장 (사용자 확정, 2026-07-08 갱신)

- **포함**:
  - 공공데이터포털 식약처 **의약품 낱알식별 API** + **의약품제품 허가정보 API**(완료) 에 이어,
    **e약은요(의약품개요정보) API** + **DUR 품목정보(병용금기 등) API** 연동 추가.
  - 위 API에서 약품 데이터를 가져와 `medications` 테이블(Tier 2)에 적재하는 동기화 로직(배치/스크립트 형태).
  - `medication_service.py`의 매칭 로직에서, 로컬 DB(Tier 1/2)에 없는 약품은 API(Tier 3)로 실시간 조회하는
    폴백 경로 추가 — 단, Tier 1(SQLite) 자리는 비워두고 Tier 2(MySQL) → Tier 3(API) 순서로만 구현.
- **제외**: SQLite(Tier 1) 실제 연동(팀원이 DB 연결 구조 완성 후 별도 진행), OCR 자체(CLOVA OCR) 변경,
  T-MED-3(수동 폴백 모드) 로직, DUR 안내 화면(T-MED-2) — 이번 작업은 데이터 원천 확보 + 3단계 조회
  경로의 뼈대(Tier 2/3)까지만.

### 목표

- 입력: 식약처 공공데이터포털 API 응답(낱알식별/허가정보/e약은요/DUR 품목정보), 동기화 실행 트리거(배치
  스케줄 또는 수동 커맨드 — 구체 방식은 구현 단계에서 결정).
- 출력/노출: `medications` 테이블(Tier 2)에 표준코드(`standard_code`) 기준으로 upsert된 약품 레코드.
  Tier 2에도 없는 약품은 매칭 시점에 API(Tier 3)를 호출해 조회하고, 그 결과로 매칭 후보를 구성한다.
  매칭 실패 시의 `AUTO_` 더미 생성 로직은 유지.

### 완료 정의 (Definition of Done)

- [ ] e약은요 API + DUR 품목정보 API를 호출해 데이터를 가져오는 클라이언트 함수가 있다
      (`app/services/medication_open_api_client.py`에 낱알식별/허가정보와 같은 패턴으로 추가).
- [ ] 식약처 4개 API(낱알식별/허가정보/e약은요/DUR) 응답을 `standard_code` 기준으로 하나의
      `medications` 레코드에 병합해 저장하는 동기화 로직이 있다.
- [ ] 동기화는 API 키 미설정/호출 실패 시 서비스 기동이나 기존 OCR 매칭 흐름을 깨뜨리지 않는다(스킵/로그만).
- [ ] `medication_service.py`의 실시간 매칭 경로: 로컬 DB(Tier 2)에 없으면 API(Tier 3)를 호출해 후보를
      구성하되, API 미설정/실패 시에도 기존 `AUTO_` 더미 생성 폴백으로 안전하게 떨어진다.
- [ ] DB 스키마 변경이 있다면 Alembic 리비전과 `docs/dev/ERD.dbml`을 함께 갱신했다.
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가.
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과.

---

### 허용 경로 (T-MED-1과 동일 범위 — 이 안에서만 자유롭게 작업)
```
app/apis/v1/medication.py
app/services/medication_service.py
app/repositories/medication_repository.py
app/models/medication_model.py
app/dtos/medication_dto.py
app/core/db/migrations/versions/**
app/tests/medication_apis/**
scripts/**medication**, scripts/**sync**  (신규 동기화 스크립트)
docs/dev/ERD.dbml
docs/tasks/T-MED-4.md (이 파일의 "완료 보고" 섹션만)
envs/example.*.env (신규 API 키 "이름"만 추가 — 실값 금지)
```

### 금지 경로
```
app/core/** (위 example.*.env 항목 제외)
app/dependencies/**
frontend/**
infra/**
docs/plan/** (TRD/PRD 원본 — 이번 작업 범위에서는 수정하지 않음, 위 "참조" 절 참고)
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 자율 판단 허용 범위

- 동기화 스크립트의 실행 방식(CLI 커맨드/Alembic data migration/별도 배치 엔트리포인트 중 선택),
  두 API 응답 필드를 `Medication` 컬럼에 매핑하는 구체적 방식, upsert 배치 크기/재시도 전략 — 에이전트
  자율 결정.

### 반드시 멈춰야 하는 경우

- 전체 의약품 데이터(수만 건) 전량 적재가 필요한지, 일부 샘플만으로 충분한지 판단이 서지 않는 경우 →
  사용자에게 먼저 확인.
- API 키 발급이 필요한 경우 — 에이전트가 임의로 발급/설정하지 않고, 필요한 키 이름만 `envs/example.*.env`에
  추가한 뒤 사용자에게 실제 키 발급을 요청.
- SQLite(Tier 1) 파일을 직접 만들거나 연결해야 할 것 같다고 판단되는 경우 → 범위 밖(팀원 작업), 사용자에게
  먼저 확인.
- DUR 정보를 T-MED-2(안내 화면)에도 노출해야 할 것 같다고 판단되는 경우 → 범위 밖(이번 작업은 데이터
  확보/매칭 후보 구성까지만), 사용자에게 먼저 확인.

---

### 완료 보고 (에이전트가 작성)
- (미작성 — 코드 구현 시작 전, 문서 단계만 완료)
