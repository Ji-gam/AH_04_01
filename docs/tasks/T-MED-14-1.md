# Task Contract: T-MED-14-1 (품목-성분 매핑 테이블 추가)

---

## Task ID: T-MED-14-1 (item_seq -> INGR_CODE 매핑 테이블 추가 — DUR 3단계 커버리지 개선)

### 참조
- 선행 문서: `docs/tasks/T-MED-14-ingredient-mapping.md` (인수인계서).
- 1차 구현(MATERIAL_NAME 텍스트 매칭만, 52% 커버리지)에서는 인수인계서의 "제안 방향"(공공데이터포털
  새 API 활용신청)을 폐기했었으나, 같은 날(2026-07-14) 기존 코드(`app/services/
  medication_open_api_client.py`, T-MED-2-2)에서 이미 실서비스키로 검증해둔 `DrugPrdtPrmsnInfoService07`
  을 재발견 — `getDrugPrdtMcpnDtlInq07`(주성분 상세정보)이 품목당 성분 단위로 `MTRAL_CODE`(원료
  성분코드)를 주는데, 이 코드가 기존 DUR 테이블의 `ORI_INGR`/`ORI` 필드에 이미 박혀있는 `[Mxxxxxx]`
  형식과 같은 네임스페이스라 텍스트 매칭이 아니라 코드 대 코드로 정확히 잇는 경로가 있었다. 이걸로
  최종 80.0% 달성 (자세한 내용은 아래 "완료 정의"/"알려진 한계" 참고).
- 관련: PR #149 (T-MED-14 본편), `app/repositories/dur_repository.py`의
  `INGREDIENT_SOURCE_TABLES`/`get_ingredient_codes_for_items`

### 배경
3차(성분 기준) DUR 스크리닝은 입력 약의 성분코드를 품목 기준 DUR 히트 테이블에서 역추적했다 —
품목 기준 규칙이 0건인 약은 성분코드를 알아낼 방법이 없어 3차도 항상 빈 결과였다. 실측 결과
`drugs_data`(현재 검색 대상 전체 약) 4,741개 중 3,138개(66%)가 이 문제로 3단계 성분코드 0건.

### 목표
- 입력: 없음 (Phase 1에서 신규 API 3종을 전수 동기화, Phase 2에서 로컬 파생 매핑 — 둘 다
  `orchestrate_pipeline.py`가 자동 실행)
- 출력: `app/database/drugs_full.db`에 `item_ingredient_map` 테이블 신설, `get_ingredient_codes_for_items`가
  이를 우선 조회하도록 변경

### 완료 정의 (Definition of Done)
- [x] `config_db.py`의 `API_SPECS`에 신규 소스 3종 추가 (`drug_prdt_prmsn_list`,
  `drug_prdt_prmsn_detail`, `drug_prdt_mcpn_detail` — `DrugPrdtPrmsnInfoService07`). 앞으로
  `orchestrate_pipeline.py` 전수 동기화 시 자동으로 함께 갱신됨. `drug_prdt_prmsn_detail`은
  레코드당 데이터量이 커서(500건=11.2MB) 기본 페이지 크기면 `pipeline_db.py`의 고정 15초
  타임아웃에 걸려 30분 대기 루프에 빠지는 걸 실제로 겪음 — `pipeline_db.py`는 안 건드리고
  `num_of_rows=100`으로 우회
- [x] `scripts/drug_info_sync/mapping_ingredients.py` — 두 소스를 합쳐서 `item_ingredient_map`
  재계산. 1순위 `drug_prdt_mcpn_detail`의 `MTRAL_CODE`를 `ORI_INGR`/`ORI`에서 뽑은 M코드→INGR_CODE
  크로스워크로 코드 대 코드 매칭(안 되면 성분명 폴백), 2순위 기존 `MATERIAL_NAME` 텍스트 매칭(1순위가
  놓친 품목만 보충). 매 실행마다 통째로 재계산(파생 데이터라 증분 방식 불필요)
- [x] `orchestrate_pipeline.py` Phase 2에 연결
- [x] `dur_repository.py`의 `get_ingredient_codes_for_items`가 `item_ingredient_map`을 우선
  조회하고, 거기 없는 품목만 기존 역추적 로직으로 폴백 (커버리지만 개선, 회귀 없음, 기존
  "1~2쿼리" 계약 유지)
- [x] 실제로 `drugs_full.db`에서 스크립트 실행 → `item_ingredient_map` 49,669건(32,296개 품목)
  적재, `drugs_data` 커버리지 실측 **80.0%**(3,793/4,741) 확인
- [x] 관련 테스트 작성/갱신 및 통과 (`test_dur_repository.py`, `test_drug_info_sync_pipeline.py`,
  `test_dur_screening_apis.py` — 총 55개 통과)
- [x] 탐색 단계에서 만들었던 `explore_prdt_prmsn.py`(임시 스크립트)는 `config_db.py` 정식 편입 후
  중복이라 삭제

### 알려진 한계 (사용자 승인됨, 2026-07-14)
80.0% 커버리지에서 멈춘 이유: 남은 948개는 `drug_prdt_mcpn_detail`에 성분 정보 자체가 없거나,
있어도 그 원료성분코드(M코드)가 우리 DUR 테이블 어디의 `ORI_INGR`/`ORI`에도 등장하지 않아
(=INGR_CODE 자체가 DUR 시스템에 없음) 코드매칭·이름매칭 둘 다 실패하는 경우 — 이 25개 테이블
데이터로는 구조적으로 해결 불가능하다. 데모 목적이라 이 한계를 그대로 받아들이기로 확정함.

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
scripts/drug_info_sync/config_db.py
scripts/drug_info_sync/mapping_ingredients.py
scripts/drug_info_sync/orchestrate_pipeline.py
app/repositories/dur_repository.py
app/tests/repositories/test_dur_repository.py
app/tests/scripts/test_drug_info_sync_pipeline.py
app/tests/dur_apis/test_dur_screening_apis.py
docs/tasks/T-MED-14-1.md
docs/tasks/_active.json
```

### 금지 경로 (절대 수정하지 않음)
```
app/database/dur_drug_light.db 및 app/repositories/dur_drug_repository.py (재사용/참조 금지)
scripts/drug_info_sync/pipeline_db.py (범용 파이프라인 로직 — 새 소스도 APISpec 필드만으로 흡수)
```

### 자율 판단 허용 범위
- 성분명 동의어 사전 구축 방식(정확일치 vs 정규화), `item_ingredient_map` 재계산 전략
  (통째로 재생성 vs 증분)

### 반드시 멈춰야 하는 경우
- 매칭된 `INGR_CODE`가 MFDS DUR 포맷(`D0000xx`)이 아닌 다른 코드 체계로 보이는 경우 (이전에
  `drug_bundle_info.trustHiraMainingrCode`에서 HIRA 코드 포맷을 잘못 후보로 삼았다가 폐기한 전례 있음)

### 완료 보고
- 완료 정의 체크리스트: 전부 완료 (위 참고), 최종 커버리지 80.0%
- 가정(Assumptions): "데모 목적, 다소 빈틈 허용"이 사용자의 명시적 스코프 확정 — 실서비스 수준
  완전성은 이번 스코프 밖. `DrugPrdtPrmsnInfoService07`의 신규 서비스키는 활성화 지연(Forbidden)이
  있어 기존 검증된 `PUBLIC_DATA_API_KEY`로 다운로드함 — 다음 전수 동기화 때도 이 키 사용
- 공유 계약 변경 필요 사항: 없음 (`get_ingredient_codes_for_items`의 반환 타입/시그니처 불변,
  호출부인 `dur_service.py` 무변경)
- DB 용량 변화: 신규 3테이블로 `drugs_full.db`가 약 130MB 늘어남(994MB, 이전 대비)
- 브랜치명: `feat/T-MED-14-dur-screening` (T-MED-14 본편과 동일 브랜치에서 이어서 작업)
