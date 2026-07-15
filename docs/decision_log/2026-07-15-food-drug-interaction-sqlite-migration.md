# 2026-07-15 — 음식-약물 상호작용 참조 테이블 저장 형식을 SQLite로 통일 (후속: T-DOC-3)

> [2026-07-14-food-drug-interaction-data-source.md](2026-07-14-food-drug-interaction-data-source.md)에서
> 확정한 데이터 소스/파싱 방식은 그대로 유지하고, 저장 형식만 바꾼 후속 결정이라 별도 파일로 뺐다.

## 배경

`app/database/`에는 이미 `drug_light.db`, `dur_drug_light.db` 등 SQLite로 저장된 참조 데이터가
있는데, 음식-약물 상호작용 참조 테이블만 `food_drug_interaction_reference.json`으로 저장돼
형식이 통일되지 않았다. 형식 통일을 위해 SQLite로 이전했다.

## 결정 사항

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 원문 소스 | `food_drug_interaction_reference.json`을 리뷰용 소스로 그대로 유지 (삭제하지 않음) | 이 데이터는 정부 발간 PDF 원문을 재가공 없이 옮긴 것이라 면책 목적상 원문 변경 여부를 git diff로 확인할 수 있어야 한다(2026-07-14 결정 유지). JSON은 diff 가독성이 좋고, SQLite 바이너리는 diff가 안 된다. |
| 파생 DB | `app/database/food_drug_interaction.db`를 새로 추가하고, `app/scripts/build_food_drug_interaction_db.py`(오프라인 1회 실행 스크립트)가 JSON → SQLite 변환을 담당 | `drugs_full.db` → `drug_light.db` 파생 패턴(`scripts/drug_info_sync/run_db.py`)과 동일. 원문을 고치려면 JSON을 고친 뒤 스크립트를 다시 실행해 DB를 재생성해야 한다(DB 파일 직접 편집 금지). |
| 스키마 | `food_drug_source`(출처 메타, 단일 행), `food_drug_categories`(카테고리/약효군/음식·알코올 상호작용 원문/출처 페이지), `food_drug_ingredients`(카테고리별 성분 한글/영문명, `category_id` FK) 3테이블 + 성분명 인덱스 | 원본 JSON의 `categories[].ingredients[]` 중첩 구조를 정규화한 것. 인덱스는 당장 매칭 로직(파이썬 부분 문자열 검사)엔 안 쓰이지만, 추후 성분명 완전일치 조회가 필요해지면 바로 활용 가능하도록 미리 추가. |
| 조회 방식 | `app/repositories/food_drug_interaction_repository.py`(`FoodDrugInteractionRepository`) 신설. `medication_service._match_food_drug_reference`는 기존과 동일하게 전체 카테고리를 한 번 캐싱해 파이썬에서 성분명 부분 문자열 매칭 | 156건 규모라 매 요청 SQL 질의보다 캐싱이 여전히 낫다. 매칭 로직 자체(품목명이 성분명을 포함하는지 검사)는 바꾸지 않아 회귀 위험 최소화 — `dur_drug_repository.py`와 동일한 리포지토리 패턴(생성자 `db_path` 주입 가능, connect-per-call)만 새로 따름. |
| 커밋 대상 | `food_drug_interaction.db`는 `drug_light.db`처럼 git에 커밋 (gitignore 대상 아님) | 파생 DB지만 크기가 작고(156건), 팀 전체가 재빌드 없이 바로 쓸 수 있어야 한다. |

## 검증

- `app/tests/services/test_medication_service_food_interaction.py`,
  `test_medication_service_food_interactions_aggregate.py`의 시나리오(와파린 매칭/타이레놀·
  다이아벡스 폴백/food_items 추출)를 수동으로 재현해 동일한 결과를 확인함(로컬 테스트 DB
  자격증명 미설정으로 `uv run pytest` 전체 스위트는 이 환경에서 실행 불가 — MySQL
  `Access denied` — 이는 이번 변경과 무관한 환경 이슈).

## 후속 업데이트 (같은 날) — 음식 항목 단위까지 구조화

카테고리 단위 `food_interaction`/`alcohol_interaction`이 여전히 원문 문단(통짜 텍스트)이라,
사용자가 "약 → 음식별 개별 이유"까지 DB에 구조화되어 있는지 물어봄. 확인 결과 음식별 분리는
DB가 아니라 `medication_service._extract_food_items`가 요청 시점에 규칙 기반(사전 매칭)으로
문단을 쪼개 만들고 있었음 — 이를 빌드 시점으로 옮겨 DB에 저장하도록 변경.

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 추출 로직 분리 | `_KNOWN_FOOD_ITEMS`/`_extract_food_items`를 `medication_service.py`에서 `app/services/food_item_extraction.py`로 이동(`KNOWN_FOOD_ITEMS`, `extract_food_items`, `group_sentences_by_food_name`로 공개) | 빌드 스크립트(`app/scripts/build_food_drug_interaction_db.py`)도 같은 사전/로직으로 참조 테이블 원문을 미리 쪼개야 하는데, `medication_service.py`를 그대로 import하면 FastAPI/SQLAlchemy 등 무거운 의존성이 딸려온다. `medication_service.py`엔 `_extract_food_items = extract_food_items` 별칭만 남겨 기존 테스트(`test_medication_service_food_interaction.py`) 호출부 호환을 유지. |
| 새 테이블 | `food_drug_food_items(id, category_id FK, food_name, detail)` | 카테고리별 `food_interaction`/`alcohol_interaction` 원문을 빌드 시점에 `group_sentences_by_food_name()`으로 각각 쪼갠 뒤, 같은 음식명이 두 문단 모두에 나오면 문장을 병합해 한 행으로 저장(`_merged_food_items`, `build_food_drug_interaction_db.py`). |
| 조회 방식 변경 | `FoodDrugInteractionRepository.load_categories()`가 각 카테고리 dict에 `food_items` 키(이미 계산된 `[{name, detail}, ...]`)를 채워 반환. `medication_service._build_food_interaction_guide_card`는 참조 테이블 매칭 시 더 이상 요청마다 `extract_food_items()`를 호출하지 않고 `_food_items_from_reference(reference_entry)`로 DB에 저장된 결과를 그대로 읽는다(e약은요 폴백 경로는 매 요청 원문이 새로 오므로 그대로 실행 시점 추출 유지). | 정적 참조 데이터는 요청마다 재계산할 이유가 없다. |
| 회귀 검증 | 35개 카테고리 전체에 대해 "빌드 시점에 문단을 분리해 병합한 결과"와 "기존처럼 두 문단을 합친 뒤 한 번에 추출한 결과"를 이름 집합/문장 집합 단위로 비교해 100% 동일함을 확인 | 문단을 나눠서 추출(음식/알코올 각각) 후 병합하는 방식으로 바꿨는데, 원문 문단이 각각 완결된 문장으로 끝나 문장 분리 경계가 안 깨지는 것을 직접 확인해야 안전하다고 판단. |

## 후속 업데이트 (같은 날) — "권장" 음식이 "주의" 칩으로 잘못 뜨는 문제 수정

실사용 중 발견: 아스피린(NSAIDs) 등록 후 음식 탭에서 "우유"가 다른 주의 음식(카페인 등)과
똑같은 칩으로 뜨는데, 실제 원문은 "위장장애가 있으면 우유와 함께 복용하세요"(권장)였다. 규칙
기반 추출(`group_sentences_by_food_name`)은 문장에 음식명이 등장하는지만 볼 뿐 맥락(권장/회피)을
판단하지 못해 생긴 문제.

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 분류 방식 | 자동(키워드/어투) 분류 대신, 전체 187개 음식 항목을 사람이 직접 읽고 확인 | "좋습니다" 같은 긍정 어투가 있어도 실제로는 회피 지시인 경우가 많다(예: 자몽주스 "복용 후 2시간 뒤에 마시는 것이 좋다" — 여전히 회피). 자동 분류는 회피 대상 음식을 권장으로 잘못 표시할 위험이 있어(사용자에게 실제로 위험한 음식을 먹어도 된다고 알려주는 셈), 항목을 놓치는 쪽(기본값 "avoid")이 훨씬 안전하다고 판단. |
| 확인 결과 | 187개 중 딱 2건만 진짜 "권장": NSAIDs+우유(위장장애 완화), 리튬(조울증 치료제)+우유(식후 복용 권장) | 나머지는 자몽주스/오렌지 등 표현이 부드러워도 전부 회피/시간차 지시였음(수동 검토로 확인). |
| 스키마 | `food_drug_food_items`에 `polarity TEXT NOT NULL DEFAULT 'avoid' CHECK (polarity IN ('avoid','recommend'))` 컬럼 추가. 빌드 스크립트의 `_RECOMMEND_OVERRIDES`(수동 등록한 (drug_class, food_name) 쌍 집합)에 있으면 "recommend", 나머지는 "avoid" | 빌드 스크립트가 override 중 하나라도 매칭 안 되면(오타 등) `ValueError`를 던지도록 해서 조용히 무시되는 실수를 막음. |
| DTO/프론트 | `FoodItem.polarity`(기본값 "avoid") 추가, `medication_service._food_items_from_reference`가 그대로 전달. 프론트 `MedicationPage.tsx`는 칩/모달을 `polarity`로 분기(👍 초록 "권장" vs ⚠️ 핑크 "주의") — 카드 전체의 `severity`가 아니라 음식 개별 단위로 판단(같은 카드 안에 권장/주의가 섞일 수 있어서, 예: 아스피린 - 우유는 권장, 카페인은 주의) | 사용자가 실제로 스크린샷으로 발견한 버그를 재현해(아스피린 등록 → 우유 칩 클릭) 수정 확인. |
| e약은요 폴백 경로 | `extract_food_items()`는 그대로 두고 `polarity` 기본값("avoid")만 적용 — 실시간 API 원문에 대한 자동 분류는 하지 않음 | 폴백 경로는 정적 참조 데이터가 아니라 매 요청 새 텍스트라 사람이 미리 검토해둘 수 없다. 잘못 "recommend"로 자동 분류하는 위험을 피하기 위해 기본값(주의로 취급)을 유지. |

## 후속 업데이트 (같은 날) — "시간차를 두면 괜찮은" 회피 항목을 세 번째 폴라리티로 분리

사용자 피드백: "~하는 것이 좋다"는 표현이 있는 항목(예: 자몽주스 "복용 후 2시간 뒤에 마시는
것이 좋다")도 "권장"으로 봐야 하지 않냐는 질문. 다시 확인해보니 이건 "이 음식을 먹어라"가 아니라
"동시 섭취는 피하되, 꼭 먹어야 한다면 시간차를 두라"는 회피 방법 안내라 `recommend`(NSAIDs+우유처럼
같이 먹으면 도움되는 경우)와는 성격이 다르다고 판단 — 그렇다고 다른 순수 회피 항목과 똑같이
`avoid`로 묶기엔 "시간차를 두면 섭취 가능"이라는 유용한 정보가 묻히므로, 세 번째 폴라리티
`timing_caution`으로 분리해 강조하기로 함.

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 재검토 방법 | "함께 복용", "드세요", "~시간 이후/전/안에" 등 패턴으로 187개 항목을 다시 스캔해 후보를 추리고, 각 문장을 다시 직접 읽어 판단 | 자동 판별을 신뢰하지 않는 원칙(위 표 참고)을 그대로 유지 — 패턴은 후보를 좁히는 용도일 뿐, 최종 분류는 사람이 원문 맥락을 읽고 확정. 예: 항진균제+세인트존스워트 문장엔 "1시간 전/후"가 있지만 이는 그 약의 식사 시점 안내일 뿐 세인트존스워트와는 무관해 제외함(패턴만 믿었으면 오분류할 뻔한 사례). |
| 확인 결과 | 8건이 `timing_caution`: 칼슘채널차단제+자몽주스/포멜로(2시간 후 섭취 가능), 디곡신+식이섬유(전후 2시간 회피), 테트라사이클린+우유/유제품/치즈/아이스크림(1시간 전~2시간 안 회피), 변비약+유제품(1시간 후 복용 가능) | 나머지는 여전히 순수 `avoid`(회피 방법 자체가 원문에 없음)이거나 이미 확정된 `recommend` 2건. |
| 스키마 | `food_drug_food_items.polarity` CHECK 제약에 `'timing_caution'` 추가, 빌드 스크립트에 `_TIMING_CAUTION_OVERRIDES` 추가(매칭 안 되면 `_RECOMMEND_OVERRIDES`와 동일하게 `ValueError`로 오타 방지) | 기존 `_RECOMMEND_OVERRIDES` 검증 패턴 재사용. |
| DTO/프론트 | `FoodItem.polarity`에 `"timing_caution"` 추가. 프론트는 `FOOD_POLARITY_STYLES` 맵으로 세 폴라리티(avoid=⚠️ 핑크 "주의", recommend=👍 초록 "권장", timing_caution=⏰ 호박색 "시간차 주의")를 한 곳에서 관리하도록 리팩터링(`foodPolarityStyle()` 헬퍼) | 분기 로직이 칩/모달 두 군데에 흩어져 있던 걸(권장 2-way 분기) 한 곳으로 모아, 세 번째 값 추가가 스타일 객체 갱신만으로 끝나게 함. |

## 참고

- 이전 결정: `docs/decision_log/2026-07-14-food-drug-interaction-data-source.md`
- 원문 소스: `app/database/food_drug_interaction_reference.json`
- 빌드 스크립트: `app/scripts/build_food_drug_interaction_db.py`
- 파생 DB: `app/database/food_drug_interaction.db`
- 리포지토리: `app/repositories/food_drug_interaction_repository.py`
- 추출 로직: `app/services/food_item_extraction.py`
- 프론트 UI: `frontend/src/pages/medication/MedicationPage.tsx`
