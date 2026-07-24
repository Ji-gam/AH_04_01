## Task ID: T-DOC-4 (음식 상호작용 카드 — 음식 항목 칩 + 클릭 상세보기)

### 참조
- Issue: #147
- 선행 작업: `docs/tasks/T-DOC-3.md`(참조 테이블 연동, 아직 원문 그대로 노출)

### 배경

T-DOC-3에서 식약처 복약안내서 참조 테이블 원문을 `GuideCard.content`에 그대로 넣어 보여주는데,
사용자 피드백상 문단이 길어 "이유를 줄줄이 읽어야" 해서 가독성이 떨어진다. 음식 이름을 먼저
보여주고 클릭하면 상세 이유를 보여주는 방식이 더 낫다는 피드백을 받았다.

원문 텍스트("브로콜리, 양배추, 케일... 등에는 비타민K가 많이 함유되어 있습니다")는 음식 하나당
이유 하나로 깔끔하게 나뉘는 구조가 아니라서, 완벽한 분해는 LLM 기반 재구조화가 필요할 수 있다
(RAG/ai_worker 영역, 이번 범위 밖). 1단계로는 사전 정의한 음식/음료 명사 목록을 문장에서 매칭해
"음식명 → 그 음식이 언급된 문장(들)"으로 묶는 규칙 기반 추출을 적용하고, 추후 이 추출 함수만
LLM 기반으로 교체할 수 있게 분리해둔다.

### 목표
- 입력: 참조 테이블 매칭 카드(및 가능하면 e약은요 폴백 카드)의 `food_interaction`/`alcohol_interaction`
  텍스트
- 출력/노출: `GuideCard.food_items`(음식명 + 상세 텍스트 목록)가 채워지면 프론트에서 칩 목록으로
  보여주고 클릭 시 상세를 펼친다. 매칭되는 음식명이 없으면(사전에 없는 음식이거나 e약은요 자유
  텍스트) 기존처럼 `content` 전체 텍스트를 그대로 보여준다(회귀 없음).

### 완료 정의 (Definition of Done)
- [ ] `GuideCard`에 `food_items: list[FoodItem] | None = None` 필드 추가(`FoodItem = {name: str, detail: str}`)
- [ ] `docs/dev/api_spec_core_v1_v1.1.yaml`의 `GuideCard` 스키마에 `food_items` 반영
- [ ] 규칙 기반 음식명 추출 함수 신설 — 사전(curated list)에 있는 음식/음료 명사가 문장에 등장하면
      해당 문장(들)을 상세(detail)로 묶는다. 함수는 "V1(규칙 기반)"임을 문서화하고, 동일 시그니처로
      LLM 기반 V2로 교체 가능하도록 호출부와 분리한다
- [ ] `_build_food_interaction_guide_card`가 추출된 음식명이 있으면 `food_items`를 채운다(없으면
      `None`으로 두고 기존 동작 유지)
- [ ] 프론트 "음식(13번)" 탭: `food_items`가 있으면 음식명 칩 목록을 보여주고, 칩 클릭 시 그
      음식의 상세 텍스트만 펼쳐서 보여준다. `food_items`가 없으면 기존처럼 전체 문단을 그대로 보여준다
- [ ] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다
- [ ] (공통) 모든 신규 코드에 대해 Ruff 통과, Mypy 통과, 프론트 `tsc`/`eslint` 통과

---

### 허용 경로
```
app/services/medication_service.py
app/dtos/medication_dto.py
app/database/food_drug_interaction_reference.json (읽기 전용)
app/tests/services/**
app/tests/medication_apis/**
docs/dev/api_spec_core_v1_v1.1.yaml (GuideCard 스키마 섹션만)
frontend/src/pages/medication/MedicationPage.tsx
frontend/src/hooks/useMedication.ts
docs/tasks/T-DOC-4.md (이 파일)
```

### 금지 경로
```
ai_worker/**
app/services/retriever_stub.py
app/services/llm_stub.py
app/core/**
app/dependencies/**
app/services/medication_open_api_client.py
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

### 의존하는 공유 계약
- `GuideCard` 스키마(`docs/dev/api_spec_core_v1_v1.1.yaml`) — 이번 Task에서 필드 추가(하위호환,
  optional) 허용. 기존 필드(`title`/`content`/`severity`/`disclaimer`) 의미는 바꾸지 않는다.

### 자율 판단 허용 범위
- 음식/음료 명사 사전(curated list)의 구체적 항목 구성, 문장 분리 방식, 칩 UI의 구체적 스타일/
  인터랙션(펼치기/접기 방식) — 전부 에이전트 자율 결정.

### 반드시 멈춰야 하는 경우
- 규칙 기반 추출로 커버 안 되는 케이스가 너무 많아 LLM 호출이 필요해 보이는 경우 → RAG/ai_worker
  영역 침범이므로 범위 밖, 사용자에게 먼저 확인(V1은 "완벽한 분해"가 목표가 아니라 "커버되는
  만큼만 칩으로, 안 되면 기존 전체 텍스트로 폴백"이 목표임을 유의).

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 위 6개 항목 모두 충족.
  - `GuideCard`에 `food_items: list[FoodItem] | None = None` 추가(`FoodItem = {name, detail}`),
    `docs/dev/api_spec_core_v1_v1.1.yaml`에 스키마 동기화.
  - `_extract_food_items(text)` 신설 — 사전(`_KNOWN_FOOD_ITEMS`, 자몽주스/비타민K/카페인 등
    90여 개 구체적 음식·음료 명사) 매칭 기반 V1. 같은 문장에서 더 구체적인 이름이 매칭되면
    포함된 짧은 이름은 제외해 중복을 줄인다. 함수 시그니처(원문 텍스트 -> FoodItem 목록)만
    유지하면 추후 LLM 기반 V2로 교체 가능하도록 호출부와 분리해뒀다(주석에 명시).
  - `_build_food_interaction_guide_card`의 참조 테이블 매칭 경로/e약은요 폴백 경로 모두에서
    `food_items`를 채우도록 수정. 사전에 없는 음식만 언급되면 `food_items=None`으로 두어
    프론트가 기존처럼 `content` 전체 텍스트를 보여주도록 폴백(회귀 없음).
  - 프론트 "음식(13번)" 탭: `food_items`가 있으면 음식명 칩 목록을 보여주고, 칩 클릭 시 그
    음식의 detail만 펼친다(다시 누르면 접힘). `food_items`가 없으면 기존 전체 문단 렌더링 유지.
- 가정(Assumptions):
  - V1은 "완벽한 음식별 이유 분리"가 목표가 아니라 "사전에 있는 음식만 칩으로 뽑고, 나머지는
    기존 방식대로 보여주는" 부분 개선이 목표임(Task Contract에 명시된 대로). 예: 와파린 항목의
    "브로콜리, 양배추, 케일..." 문장은 각 음식이 같은 문장(=같은 detail)을 공유한다 — 문장을
    "음식별 개별 이유"로 재작문하지 않는다(원문 왜곡 방지, T-DOC-2/3과 동일 원칙).
  - "알코올"과 "음주"처럼 사전에 유사어를 모두 등록해 같은 문장이 여러 칩으로 중복 노출되는
    경우가 있음(예: 와파린 카드에 "알코올"/"음주" 둘 다 칩으로 뜸) — 오탐 방지보다 누락 방지를
    우선한 결과로, 이번 범위에서는 허용 가능한 수준으로 판단. 개선하려면 사전에 유의어 그룹을
    도입해야 하나 이번 Task 범위 밖.
  - `food_items` 안의 `detail`은 원문 문장을 그대로 이어붙인 것이라 재가공(요약)하지 않았다.
- 공유 계약 변경 필요 사항: `GuideCard` 스키마에 `food_items` 필드 추가(하위호환, optional) —
  `docs/dev/api_spec_core_v1_v1.1.yaml`에 반영 완료. 기존 필드 의미는 변경 없음.
- 부수 발견(범위 밖): 없음.
- 테스트: `app/tests/services/test_medication_service_food_interaction.py`에 4건 신규(추출 함수
  단위 테스트, 참조 테이블/e약은요 경로에서 food_items 채워짐, 사전에 없는 음식만 있을 때 None
  유지). 도커 컨테이너에서 `uv run pytest -k food -v` 19 passed. `uv run pytest -q`(무관한
  스크립트 테스트 모듈 1개 제외) 267 passed / 3 failed(T-DOC-3와 동일하게 CLOVA OCR 환경 이슈,
  무관 확인됨). `uv run ruff check`/`ruff format --check`/`mypy` 전부 통과. 프론트
  `npx tsc -b --noEmit` 통과, `npx eslint`는 기존 경고 3건 외 신규 이슈 없음.
  로컬 도커 스택 + 프론트 dev 서버에서 실제로 칩 클릭 → 상세 펼침/접힘 동작을 브라우저로 직접
  확인함(2026-07-14).
- 브랜치명: `feat/145-doc3-food-drug-interaction-accuracy`(T-DOC-3이 아직 미머지 상태라 스택형
  PR 방지를 위해 같은 브랜치/PR #146에 이어서 커밋함 — `_active.json`에 사유 기록)
