## Task ID: T-DOC-3 (음식-약물 상호작용 안내 정확도 개선)

### 참조
- Issue: #145
- 선행 작업: `docs/tasks/T-DOC-2.md`(음식 탭 최초 연동), `docs/tasks/T-MED-4.md`(공공데이터포털 API 연동)

### 배경

T-DOC-2에서 "음식(13번)" 탭 안내 카드를 e약은요(`DrbEasyDrugInfoService`) 응답의 `intrcQesitm`
("이 약을 사용하는 동안 주의해야 할 약 또는 음식은 무엇입니까?") 필드로 실연동했다. 그런데 이 필드는
약물-약물 상호작용과 음식 상호작용이 뒤섞인 자유 텍스트라, 키워드 매칭(`_extract_food_related_sentences`)
으로 음식 관련 문장만 걸러내는 임시방편을 쓰고 있다 — 오탐/누락 가능성이 있어 부정확하다.

공공데이터포털 조사 결과, 음식-약물 상호작용을 전담하는 구조화된 공공 API/데이터셋은 없다(식약처 DUR API
9개 카테고리에도 음식 카테고리는 없음). 대신 식약처가 직접 발간한 PDF 가이드북 "약과 음식 상호작용을
피하는 복약안내서"(2016.09.30, 식품의약품안전평가원)를 파싱해 성분 단위 구조화 매핑 테이블을 만들어뒀다
(`app/database/food_drug_interaction_reference.json` — 11개 질환 카테고리, 35개 약효군, 성분 156건,
각 성분군마다 `food_interaction`/`alcohol_interaction` 원문 텍스트 포함).

### 목표
- 입력: 등록약의 성분명(e약은요 응답 또는 로컬 DUR DB에서 얻는 성분/품목명)
- 출력/노출: 매핑 테이블에 매칭되는 성분이 있으면 그 원문(정부 가이드북 근거)을 GuideCard로 반환하고,
  매칭이 안 되면 기존 e약은요 키워드 필터 방식(T-DOC-2)으로 폴백한다.

### 완료 정의 (Definition of Done)
- [ ] `app/database/food_drug_interaction_reference.json`을 로드해 성분명(한글/영문)으로 조회하는
      함수가 추가되었다
- [ ] `_build_food_interaction_guide_card`가 먼저 이 매핑 테이블에서 성분명 매칭을 시도하고, 매칭되면
      해당 `food_interaction`/`alcohol_interaction` 원문을 카드로 반환한다
- [ ] 매칭되는 성분이 없으면 기존 e약은요 `intrcQesitm` + 키워드 필터 로직(T-DOC-2)으로 그대로 폴백한다
      (기존 동작 회귀 없음)
- [ ] 카드에 출처가 구분되어 노출된다(정부 가이드북 근거 vs e약은요 자유텍스트 근거) — 문구는 자율 결정
- [ ] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다
- [ ] (공통) 모든 신규 코드에 대해 Ruff 통과, Mypy 통과

---

### 허용 경로
```
app/services/medication_service.py
app/database/food_drug_interaction_reference.json (읽기 전용 참조 데이터, 이미 생성됨)
app/tests/services/**
app/tests/medication_apis/**
docs/tasks/T-DOC-3.md (이 파일)
```

### 금지 경로
```
ai_worker/**
app/services/retriever_stub.py
app/services/llm_stub.py
app/core/**
app/dependencies/**
app/services/medication_open_api_client.py (기존 e약은요 연동 — 변경 불필요, 읽기만)
envs/**
infra/**
scripts/**
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 의존하는 공유 계약 (읽기만 가능, 이미 고정됨)
- `GuideCard`/`RecognitionConfirmResult`/`FoodInteractionCheckResult` 스키마 (`docs/dev/api_spec_core_v1_v1.1.yaml`) — 변경 불필요

### 자율 판단 허용 범위
- 성분명 매칭 방식(정확 일치/부분 일치/정규화 규칙), 매핑 테이블 캐싱 방식(모듈 로드시 1회 파싱 등),
  카드 문구(출처 구분 표기) — 전부 에이전트 자율 결정. 단, `food_interaction`/`alcohol_interaction`
  원문 텍스트 자체는 재가공(요약/재작성)하지 않는다(면책 목적상 원문 그대로가 더 안전, T-DOC-2와 동일 원칙).

### 반드시 멈춰야 하는 경우
- 매칭 정확도를 높이기 위해 LLM 호출이 필요해 보이는 경우 → RAG/ai_worker 영역 침범이므로 범위 밖,
  사용자에게 먼저 확인.
- 매핑 테이블 커버리지가 부족해(11개 카테고리 밖의 약) 근본적으로 다른 데이터소스 도입이 필요해 보이는 경우
  → Task Contract 범위 밖, 사용자에게 먼저 확인.

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 위 6개 항목 모두 충족.
  - `_load_food_drug_reference()` 신설 — `app/database/food_drug_interaction_reference.json`을
    모듈 전역 캐시로 최초 호출시 1회만 읽는다.
  - `_match_food_drug_reference(medication_name)` 신설 — 품목명에 참조 테이블 성분명(한글/영문)이
    부분 문자열로 포함되면 해당 카테고리 항목을 반환한다.
  - `_build_food_interaction_guide_card`가 e약은요 호출 전에 이 매칭을 먼저 시도하도록 수정 —
    매칭되면 e약은요 API 호출 자체를 생략(정확도뿐 아니라 불필요한 외부 호출도 줄임). 매칭 안 되면
    기존 T-DOC-2 로직(intrcQesitm 키워드 필터)으로 그대로 폴백.
  - 카드 내용에 `[음식]`/`[알코올]` 구분과 `(출처: 식약처 식품의약품안전평가원 「약과 음식
    상호작용을 피하는 복약안내서」)` 출처 표기를 추가해 e약은요 근거와 시각적으로 구분되게 했다.
- 가정(Assumptions):
  - 성분명 매칭은 정확 매칭이 아닌 부분 문자열 매칭이다 — 국내 일반의약품은 품목명에 성분명이
    그대로 포함되는 경우가 흔하다(예: "암로디핀베실산염정5mg")는 점에 근거. 상표명(타이레놀,
    리피토 등)은 매칭되지 않고 기존 e약은요 폴백으로 자연스럽게 넘어간다 — 별도 상표-성분
    매핑 테이블은 이번 범위 밖.
  - 기존 테스트 중 "아스피린정 100mg"을 쓰던 2개(빈 필드 처리, 접미사 제거 재시도 검증)는
    "아스피린"이 참조 테이블 성분명과 겹쳐 새 매칭 로직이 먼저 가로채므로, 검증 대상과 무관한
    약 이름("다이아벡스정 500mg")으로 교체했다 — 테스트가 원래 검증하려던 동작(e약은요 폴백
    경로의 세부 처리)은 그대로 유지된다.
- 공유 계약 변경 필요 사항: 없음. `GuideCard` 스키마 그대로, 프론트 변경 불필요(카드 content는
  이미 임의 문자열로 렌더링됨).
- 부수 발견(범위 밖): 없음.
- 테스트: `app/tests/services/test_medication_service_food_interaction.py`에 2건 신규(매칭 성공 시
  e약은요 미호출 확인, 매칭 실패 시 폴백 확인), 기존 7건 중 2건 약 이름 교체. 도커 컨테이너에서
  `uv run pytest -k food -v` 14 passed. `uv run pytest -q`(무관한 스크립트 테스트 모듈 1개 제외)
  262 passed / 3 failed — 실패 3건은 `test_recognition_job_*`(CLOVA OCR 관련)로, 이 브랜치를 만들기
  전 `dev` 베이스(병합 커밋 e3b432f)에서도 동일하게 실패함을 별도 확인(`CLOVA_OCR_SECRET_KEY` 미설정
  환경 이슈, 이 작업과 무관). `uv run ruff check`/`ruff format --check`/`mypy
  app/services/medication_service.py` 전부 통과.
- 브랜치명: `feat/145-doc3-food-drug-interaction-accuracy`
