# 2026-07-16 — 음식-약물 상호작용 참조 테이블을 SQLite에서 MySQL로 이전

> [2026-07-15-food-drug-interaction-sqlite-migration.md](2026-07-15-food-drug-interaction-sqlite-migration.md)에서
> SQLite로 형식을 통일했던 결정을 뒤집는 후속 결정. 멘토 피드백(팀 전체가 공유하는 MySQL 하나로
> 데이터를 모으라)에 따라 저장 위치만 바꾼다.

## 배경

`app/database/food_drug_interaction.db`는 팀원 각자 로컬 파일시스템에 커밋된 SQLite 파일을
그대로 읽는 구조였다. `drug_light.db`류의 정적 마스터 데이터와 같은 패턴이라 당시엔 합리적인
선택이었지만, 멘토님 피드백은 "정적 참조 데이터라도 서비스가 실제로 쓰는 DB(MySQL)에 있어야
한다"는 방향이었다.

## 결정 사항

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 원문 소스 / SQLite 빌드 스크립트 | 그대로 유지 (`food_drug_interaction_reference.json`, `app/scripts/build_food_drug_interaction_db.py`) | 원문 diff 리뷰 가능성은 이전 결정과 동일하게 여전히 유효한 요구사항. SQLite 파일은 이제 "최종 산출물"이 아니라 MySQL로 옮기기 전 중간 산출물로 역할이 바뀐다. |
| MySQL 스키마 | `app/models/food_drug_interaction.py`에 `FoodDrugSource`/`FoodDrugCategory`/`FoodDrugIngredient`/`FoodDrugFoodItem` 4개 테이블 정의, Alembic 리비전 `0021_add_food_drug_interaction_tables.py` | 이 프로젝트는 MySQL 스키마를 Alembic으로만 관리한다(`app/core/db/migrations/env.py`) — `create_all`은 테스트 전용. |
| 시딩 | `app/scripts/seed_food_drug_interaction.py` 신설. 기존 SQLite 파일을 읽어 MySQL 테이블에 전체 삭제 후 재삽입(참조 데이터라 증분 갱신할 이유 없음) | `seed_health_content.py`와 동일한 "픽스처 → MySQL" 패턴을 따름. |
| 조회 | `FoodDrugInteractionRepository`를 `sqlite3` 직접 연결에서 SQLAlchemy `AsyncSession` 기반으로 변경. `refresh(session)`이 앱 기동 시(`app.main.lifespan`) 1회 전체를 읽어 프로세스 메모리에 캐싱하고, 기존처럼 동기 `load_categories()`가 캐시를 반환 | `medication_service._match_food_drug_reference` 등 호출부가 동기 함수라 async로 바꾸는 범위를 최소화하기 위해, DB 조회만 비동기로 하고 캐시 접근은 그대로 동기 유지. 156건 규모라 캐싱 전략 자체는 이전과 동일. |

## 실행 방법 (로컬/신규 환경)

```
uv run alembic upgrade head
uv run python -m app.scripts.build_food_drug_interaction_db   # SQLite 파일이 없다면
uv run python -m app.scripts.seed_food_drug_interaction        # SQLite → MySQL
```

## 참고

- 이전 결정: `docs/decision_log/2026-07-15-food-drug-interaction-sqlite-migration.md`
- 모델: `app/models/food_drug_interaction.py`
- 마이그레이션: `app/core/db/migrations/versions/0021_add_food_drug_interaction_tables.py`
- 시드 스크립트: `app/scripts/seed_food_drug_interaction.py`
- 리포지토리: `app/repositories/food_drug_interaction_repository.py`
