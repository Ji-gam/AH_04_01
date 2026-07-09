# Task Contract: T-MED-2 (일부 범위) — 복약 시간표 카드 내 DUR 주의사항 펼침 표시

> **문서 버전**: v1.1 · **최종 수정**: 2026-07-09
> **변경 이력**
> - v1.0 (2026-07-09): 신규 작성. TRD의 T-MED-2("약품 안전 정보 안내" = 상충 위험 경고 카드) 전체가 아니라,
>   그중 "등록된 약 각각의 DUR/효능 정보를 사용자가 펼쳐서 볼 수 있게" 하는 좁은 하위 범위만 다룬다.
>   상충/병용금기 "경고" 판단(다른 복용약·과거력과 비교)은 이 문서의 범위가 아니며 별도 T-MED-2 후속
>   작업(또는 이 문서 확장)으로 남긴다.
> - v1.1 (2026-07-09): SQLite Light DB(`dur_drug_light.db`)가 제품 27,231건 중 4,753건만 효능 데이터를
>   가져 커버리지가 낮다는 게 확인됨. 로컬 결과가 없을 때 식약처 공공데이터 API(e약은요,
>   T-MED-4에서 이미 연동된 `medication_open_api_client.py`)로 실시간 폴백하는 것을 범위에 추가.
>   이에 따라 허용 경로에 `app/apis/v1/medication.py`(해당 엔드포인트 함수 내부만) 추가.

### 참조
- PRD: F-MED-2 / TRD: T-MED-2 (부분) / 배경: 사용자가 OCR로 등록한 약이 "오늘의 복약 시간표"(SchedulePage)에
  뜨는데, 하단에 복용 주의점이 안 보인다고 보고. 조사 결과 `/medications/search-dur`(T-MED-1에서 추가된
  SQLite Light DB 검색 API)는 "더보기 > 약품검색" 모달에만 연결돼 있고 복약 시간표 화면과는 연결이 없었음.

### 목표
- 입력: `SchedulePage`에 이미 표시 중인 약 이름(`item.name` = `MedicationSchedule.drug_name`)
- 출력/노출: 각 약 아이템에 "주의사항 보기" 펼침 버튼 → 클릭 시 `/medications/search-dur?query={약이름}`을
  조회해 해당 결과의 `efficacy`/`precautions`를 카드 하단에 노출

### 완료 정의 (Definition of Done)
- [ ] 오늘의 복약 시간표(SchedulePage)의 각 약 아이템에 펼침 버튼이 있다
- [ ] 버튼을 누르면 그 약 이름으로 `search-dur`를 조회하고, 결과를 아이템 바로 아래에 표시한다
- [ ] 이름이 여러 약과 겹쳐 다른 약이 섞여 나올 수 있다는 한계를 사용자가 인지할 수 있도록,
      결과가 여러 건이면 전부 나열하거나 "여러 결과 중 참고용" 문구를 함께 보여준다(자동으로 하나만
      골라서 확정적으로 보여주지 않는다 — 오정보 위험 방지)
- [ ] 같은 약을 다시 펼칠 때 재조회하지 않도록 결과를 캐시한다
- [ ] 조회 실패/결과 없음 상태를 에러로 죽지 않고 문구로 안내한다
- [ ] `search-dur`가 로컬 SQLite Light DB에서 결과를 못 찾으면 공공데이터 API(e약은요)로 실시간 폴백해
      효능(`efcyQesitm`)/주의사항(`atpnQesitm`+`atpnWarnQesitm`+`intrcQesitm`)을 같은 응답 형태로 반환한다
- [ ] `PUBLIC_DATA_API_KEY`가 없으면(로컬 미설정 등) 폴백 호출이 조용히 빈 결과로 넘어가고 에러로 죽지 않는다
- [ ] 로컬 DB와 공공 API 둘 다에서 결과를 못 찾으면, "어디까지 찾아봤는지"(`not_found_reason`)를 사용자에게
      그대로 보여준다 — API 키 미설정으로 못 찾아본 것과 둘 다 조회했는데 없는 것을 구분해서 안내한다
- [ ] (공통) `ruff`/`tsc`/`lint` 통과, 변경 범위가 허용 경로 내로 한정

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
frontend/src/pages/SchedulePage/**
app/apis/v1/medication.py           (search_medications_dur 함수 내부의 폴백 로직만)
app/tests/medication_apis/**        (search-dur 폴백 테스트 추가)
envs/.local.env                     (개인 파일, gitignore 대상 — PUBLIC_DATA_API_KEY 값만)
docs/tasks/T-MED-2.md  (이 파일의 "완료 보고" 섹션만)
```

### 금지 경로 (절대 수정하지 않음 — 필요해 보여도 "공유 파일 변경 필요"로 보고만)
```
app/services/medication_open_api_client.py  (기존 함수 재사용만, 시그니처/반환값 변경 금지 — 다른 Tier 3
                                              매칭 플로우가 이미 이 함수들에 의존함)
app/services/medication_service.py
frontend/src/api/**
frontend/src/components/**
frontend/src/routes/**
frontend/src/store/**
frontend/src/types/**
frontend/src/hooks/useMedication.ts  (이번 범위는 SchedulePage 자체 fetch로 처리, 공유 훅 변경 불필요)
```

### 의존하는 공유 계약 (읽기만 가능, 이미 고정됨)
- `app/apis/v1/medication.py`의 `GET /medications/search-dur` — 응답 형태
  `{ elapsed_ms, results: [{ item_name, entp_name, efficacy, precautions }] }`
- `frontend/src/api/client.ts`의 `apiFetch`

### 자율 판단 허용 범위
- 펼침 버튼/카드 UI 스타일(기존 SchedulePage 컬러 토큰 `c` 재사용), 로딩/에러 문구, 캐시 자료구조(useState Map 등)

### 반드시 멈춰야 하는 경우 (이 Task에 한정된 추가 조건)
- "다른 복용 중인 약/과거력과의 상충 여부 판단" 로직이 필요하다고 판단되는 경우 → 이건 T-MED-2 본 범위(상충
  경고)이므로 진행하지 말고 사용자에게 확인
- `search-dur` 응답 형태를 바꿔야 할 것 같은 경우 → 공유 계약이므로 백엔드 변경 필요 사항으로만 보고

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
  - [x] SchedulePage 각 약 아이템에 "주의사항 보기 ▼" 펼침 버튼 추가 — 브라우저로 실제 확인(수동 등록 +
    OCR dummy_mode 확정 등록 두 경로 모두)
  - [x] 클릭 시 그 약 이름으로 `search-dur` 조회 → 효능/주의사항 표시
  - [x] 여러 결과 매칭 시 "다른 약이 섞여 있을 수 있어요" 문구 + 전체 나열(자동 확정 안 함) — 브라우저로 확인
  - [x] 같은 약 재조회 방지 캐시 (`durByName` Map, 이름 키)
  - [x] 조회 실패/결과 없음 상태 안내 문구
  - [x] `search-dur`가 로컬에서 못 찾으면 식약처 공공데이터(e약은요)로 실시간 폴백 — 함수 직접 호출로
    로컬 히트/폴백 히트/폴백도 빈 결과, 3가지 경로 모두 확인 (pytest는 이 환경에 연결 가능한 MySQL이
    없어 대신 함수를 직접 호출해 검증)
  - [x] `PUBLIC_DATA_API_KEY` 미설정 시 폴백이 조용히 스킵되고 에러 없음 — 직접 확인
  - [x] 로컬/공공 API 둘 다 없을 때 `not_found_reason`으로 어디까지 찾아봤는지 안내(API 키 없어서 못
    찾아본 경우와 둘 다 조회했는데 없는 경우를 구분) — 직접 확인
  - [x] `ruff check`/`mypy`(백엔드), `tsc -b --noEmit`/`eslint`(프론트) 모두 통과, 신규 warning 없음
- 가정(Assumptions):
  - e약은요 API(`fetch_drug_summary`)만으로 폴백을 구성했다. DUR 품목정보(`fetch_dur_item_info`)는
    `item_seq`를 얻으려면 낱알식별/허가정보 API를 추가로 호출해야 해서 이번 범위에서는 생략 —
    e약은요의 `atpnQesitm`/`atpnWarnQesitm`/`intrcQesitm`만으로도 로컬 라이트 DB의 암호 코드(`CPCTY` 등)보다
    훨씬 읽기 좋은 텍스트를 얻을 수 있었음.
  - e약은요 데이터셋 자체가 전체 의약품이 아니라 소비자 요약이 있는 일부 품목만 커버하므로, 폴백 후에도
    일부 약은 여전히 정보가 없을 수 있음 — 이 경우 `not_found_reason`으로 투명하게 안내.
  - `envs/.local.env`(gitignore 대상)에 사용자가 채팅으로 전달한 실제 `PUBLIC_DATA_API_KEY`를 저장함 —
    이 파일은 개인 파일이라 커밋되지 않음, 각자 로컬에 동일한 키를 채워야 폴백이 실제로 동작함.
- 공유 계약 변경 필요 사항: 없음. `app/services/medication_open_api_client.py`는 기존 함수를
  그대로 재사용만 했고 수정하지 않음.
- 검증 한계: 이 개발 환경에 연결 가능한 MySQL이 없어 `pytest`(엔드포인트 통합 테스트, 인증 의존성 포함)를
  실행하지 못함. 대신 `search_medications_dur` 함수를 직접 호출해 로컬 히트/공공 API 폴백 히트/폴백도
  빈 결과 3가지 경로를 모두 확인했고, 프론트 기능은 별도로 뜬 dev 서버 + 실제 로그인/등록 플로우로
  브라우저에서 직접 확인함(수동 등록·OCR dummy_mode 등록 둘 다).
- 브랜치명: `feature/T-MED-2-schedule-dur-precaution` (PR #35를 닫고 팀 컨벤션에 맞춰 재오픈 → PR #36)
