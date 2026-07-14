# Task Contract 템플릿 (AI 워커 및 백엔드 전용)

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-14

---

## Task ID: T-MED-14 (DUR 3단계 심화 스크리닝 API 구축)

### 참조
- PRD: 사용자 복약 관리 (처방전 기반)
- 관련 데이터: 공공데이터포털 DUR 22개 API 테이블

### 목표
- 입력: 약품명 배열 (e.g. `["액티피드정", "부루펜정"]`)
- 출력/노출:
  - 1차: 개별 약품 기본 정보 및 단일 금기 사항 (`/api/v1/dur/screening/basic`)
  - 2차: 복수 약품 간 상호작용 및 리콜 정보 (`/api/v1/dur/screening/interaction`)
  - 3차: 성분 기준 심층 분석 리포트 (`/api/v1/dur/screening/ingredient`)

### 완료 정의 (Definition of Done)
- [x] 3단계 API 엔드포인트 분리 구현 완료 (`/dur/screening/basic`, `/interaction`, `/ingredient`)
- [x] 단일 쿼리(SQL IN/UNION ALL) 기반 성능 최적화 적용 — 리포지토리 테스트에서 `execute` 호출 횟수를 직접 카운트해 강제
- [x] `dur_drug_light.db`(T-LLM-2 소유, 미사용) 대신 `drugs_full.db`(우선)/`drug_light.db`(폴백)를 직접 조회 — 별도 import 스크립트 불필요
- [x] (공통) 테스트를 TDD로 먼저 작성했고 통과 (레포지토리 16개 + API 10개 = 26개)
- [x] (공통) API P95 Latency ≤ 3초
- [x] 프론트 소비 편의를 위한 응답 재설계 반영 (`dur_simple` 고정 6슬롯 배열, `drug_detail` 확장, `drug_intrc`+item_seq 참조) — 4화면 와이어프레임 기준

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
app/apis/v1/dur.py
app/services/dur_service.py
app/repositories/dur_repository.py
app/dtos/dur_dto.py
app/tests/dur_apis/**
app/database/database.py
docs/tasks/T-MED-14.md
```

### 금지 경로
```
app/core/**
app/dependencies/**
envs/**
infra/**
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 모두 완료
- 가정(Assumptions):
  - 약품명 매핑은 정확일치 IN 쿼리 1개 + 미매칭분에 한해 LIKE 쿼리 1개(최대 2쿼리)로 처리.
  - 1차 스크리닝의 DUR 규칙은 임부금기/노인주의/특정연령대금기/투여기간주의/분할주의/용량주의 6종(e약은요 효능/용법/경고/이미지 포함).
  - 2차는 병용금기(USJNT)+효능군중복주의(EFCY)를 `interactions`로 통합, 리콜은 별도 `recalls`로 제공.
  - 3차는 입력 약품의 성분코드를 품목 기준 DUR 히트 테이블에서 역추적한 뒤, 성분 기준(ITEM_SEQ 없이 INGR_CODE만 있는, 품목 기준보다 완성도 높은) 7개 테이블을 재조회 — 품목 기준에서 놓친 규칙을 성분 단위에서 잡아내기 위함. 단, 품목 기준 규칙이 0건인 약품은 성분코드를 알아낼 방법이 없어 3차도 빈 결과가 된다(제품-성분 매핑 테이블이 22개 원본 테이블에 별도로 없음).
  - 성분 기준 원본 테이블에 동일 (성분,규칙,내용) 조합이 조합 파트너별로 반복 저장돼 있어(예: 이부프로펜 임부금기가 12개 병용조합 행으로 중복) 서비스 계층에서 중복 제거함.
  - 용량/1일 복용횟수는 이번 스코프에서는 요청 DTO에 받지 않음(초과 여부 판정 없이 DB의 정적 용량주의 문구만 노출).
  - 응답 재설계(2번째 라운드): 화면 4개(처방입력/목록/상세/상호작용리포트) 와이어프레임 기준으로 필드를 다시 맞춤.
    - `BasicScreeningResult`: `drug_info`/`dur_rules`(희소 hit-list) → `drug_detail`/`dur_simple`(항상 6개 고정 순서, `present`로 온오프 표시)로 교체. 목록 화면에서 "없으면 표시 안 함" 판단 로직이 프론트로 새는 걸 막기 위함.
    - `drug_detail`에 `se_qesitm`(부작용)·`deposit_method_qesitm`(보관방법)·`identification`(모양/색상/마크, `drug_identification` 테이블 신규 조인)·`etc_otc_name`/`form_name` 추가. `atpn_qesitm`/`intrc_qesitm`은 화면에 없어서 제외.
    - `InteractionScreeningResponse`: `interactions`/`recalls` 평면 필드 → `drug_intrc{interactions, recalls}`로 감쌈. `drug_a_name`/`drug_b_name`(문자열) → `drug_a`/`drug_b`(`{item_seq, item_name}`)로 교체해 프론트가 이름 매칭 없이 상세로 링크 가능하게 함. `remark` 추가(병용금기 REMARK에 "24시간 이내" 같은 실질 정보가 있었는데 누락돼 있었음). 리콜에 `entp_name`/`enforced` 추가.
    - `dur_simple`에서 같은 rule_code에 조합 파트너별 중복 행이 여러 개 있으면 첫 번째 것만 대표로 노출(전체 변형은 3차에서 확인 가능).
- 데이터 완성도 관련 주의사항: 세션 시작 시점의 `drugs_full.db`/`drug_light.db`는 `scripts/drug_info_sync`의 `once=True`(파일럿) 모드로 수집되어 테이블당 최대 5,000행이었음(병용금기 실제 규모는 수십만 행). 사용자가 별도로 전수 동기화(`--all`)를 직접 실행하기로 함 — 동기화가 끝나면 코드 변경 없이 데이터만 확장된다(쿼리는 스키마 기준이라 행 수와 무관).
- 기존 코드 처리: `_active.json`에 owner로 등록되어 있던 agent-Antigravity의 기존 스캐폴딩(리포지토리/서비스/DTO)은 스키마가 실제 DB와 다르거나(`dur_prod_pwnm_taboo` 등 UPPER_CASE 원본 컬럼을 그대로 노출) 1차 규칙 6종 중 2종(특정연령대금기/분할주의) 누락, 3차 로직이 "성분 재조회"가 아닌 "품목 기준 재나열"이라 사용자가 의도한 값을 못 냄 — 전량 재작성함. `database.py`/`dur.py`(라우터)는 스키마·인증 방식이 맞아 그대로 유지.
- 공유 계약 변경 필요 사항 (있다면): 없음
- 브랜치명: `feat/T-MED-14-dur-screening`
