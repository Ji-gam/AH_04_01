# 2026-07-17 — DUR(의약품안전사용서비스) 데이터를 SQLite에서 MySQL로 이전

> [2026-07-16-food-drug-interaction-mysql-migration.md](2026-07-16-food-drug-interaction-mysql-migration.md)와
> 동일한 방향(팀 전체가 공유하는 MySQL로 데이터를 모은다)을 DUR에도 적용한 후속 결정.

## 배경

DUR 조회가 느리다는 문제 제기가 있었고, 두 경로 모두 요청마다 SQLite 파일을 직접 여는 구조였다:

- `DurScreeningRepository`(`app/repositories/dur_repository.py`) — 병용금기 스크리닝 3단계, `app/database/database.py`의 `dur_db_connection()`으로 `app/database/drugs_full.db`(없으면 `drug_light.db`)를 매 요청 연결
- `DurDrugRepository`(`app/repositories/dur_drug_repository.py`) — 단일 약품 상세조회 게이트웨이, `app/database/dur_drug_light.db`(효능 데이터 커버리지 17%뿐)를 직접 조회 → MySQL 캐시 → 외부 e약은요 API 순으로 캐스케이드

`dur_drug_light.db`는 커버리지가 낮아 그대로 이전하지 않고, `scripts/drug_info_sync/`(공공데이터포털 API 22종 수집 파이프라인, 이 리포지토리가 만든 게 아니라 그대로 둠)를 전수 재실행해 만든 `app/database/drugs_full.db`를 두 경로 공통의 유일한 소스로 삼기로 했다.

## 결정 사항

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 원문 수집 파이프라인 / SQLite 산출물 | `scripts/drug_info_sync/`와 `app/database/drugs_full.db`는 그대로 유지 | 이 프로젝트가 만든 파이프라인이 아니고, 여전히 "빌드 산출물 → MySQL 시딩"의 중간 산출물 역할로 유효하다. |
| MySQL 스키마 | `app/models/dur.py`에 21개 테이블 정의(22개 원본 API 테이블 중 두 리포지토리가 실제로 조회하는 것만 — `drug_bundle_info`/`drug_max_dosage`/`drug_prdt_prmsn_list`는 제외), Alembic 리비전 `0026_add_dur_tables.py` | 조인/필터 키(`item_seq`, `ingr_code` 등)만 인덱스가 필요한 `String`, 나머지 원문 텍스트는 실제 데이터 최대 길이가 `String(255)`를 넘는 경우가 있어(`chart` 최대 262자, `medicine_recalls.prduct` 최대 819자, `dur_prod_usjnt_taboo`/`dur_prod_master_list`의 item_name류 최대 391/383자) 전부 `Text`로 잡았다 — 실제 시딩(98만 건) 중 "Data too long" 에러로 확인. |
| 품목 마스터 | `dur_prod_master_list`(DUR 품목 마스터, 23,417건)를 `DurDrugRepository`의 이름 검색/조회 기준으로 추가 | 처음엔 두 리포지토리 어디에서도 안 쓰인다고 보고 제외했으나, 실사용 검증 중 `drugs_data`(e약은요 API, 4,758건)만으로 이름 검색을 하면 거기 없는 약(예: 테라싸이클린)이 아예 검색이 안 되는 회귀를 발견 — 예전 `dur_drug_light.db`의 `products` 테이블(27,000여 건)과 같은 역할이 필요했다. |
| 시딩 | `app/scripts/seed_dur.py` 신설. `drugs_full.db`를 테이블별로 청크(5,000행) 단위로 읽어 MySQL에 전체 삭제 후 재삽입 | 최대 테이블(`dur_prod_usjnt_taboo`)이 80만 행대라 ORM 객체를 하나씩 `session.add`하지 않고 Core `insert()` executemany로 처리. |
| DurScreeningRepository | `sqlite3.Connection` → `AsyncSession`, 기존 UNION ALL 원시 SQL은 `text()`로 그대로 유지(플레이스홀더만 `?`→named param) | 쿼리 구조(다단계 UNION, 성분코드 역추적 캐스케이드)는 검증된 로직이라 재작성하지 않고 파라미터 바인딩 방식만 MySQL에 맞게 변경. |
| DurDrugRepository | 전체 재작성 — 모든 조회 메서드가 `AsyncSession`을 받는 async 메서드로 변경, 데이터 소스를 `dur_drug_light.db` 전용 스키마에서 새 `drugs_full.db` 기반 스키마로 매핑 | 기존 SQLite 스키마(products/drugs_einfo/ingredient_mappings 등)는 없어졌으므로 조회 자체를 새 스키마에 맞게 다시 짬. 캐스케이드(MySQL 1단계 → 캐시 → API) 로직 자체는 유지. |
| 호출부 | `app/services/dur_service.py`, `app/services/medication_service.py`(4곳), `app/services/chat_service.py`(1곳), `app/apis/v1/dur.py` | 기존에 `asyncio.to_thread`로 감싸던 동기 SQLite 호출을 실제 `await`로 교체 — 이미 다들 async 함수 안에서 호출되고 있어 파급 범위가 크지 않았다. |

## 알려진 한계

- **1일 최대투여량(`max_dosages`)을 재구성할 수 없다.** 예전 `dur_drug_light.db`는 `ingredient_mappings`라는 파생 테이블로 INGR_CODE↔CPNT_CD(최대투여량 API가 쓰는 별도 코드체계)를 이어줬는데, 이 매핑은 이번 22종 API 전수 수집 범위 밖이라 소스가 없다. `DurDrugRepository.find_drug_info()`가 반환하는 `max_dosages`는 항상 빈 리스트다.
- 회수정보(`medicine_recalls`)는 품목코드(ITEM_SEQ) 매칭률이 낮다(`scripts/drug_info_sync/mapping_recalls.py` 기준 10.7%) — 원본 API 자체가 품목코드 대신 품목명 텍스트만 주는 경우가 많아 발생하는 근본적 한계다.

## 검증

실제 MySQL(docker compose)에 `drugs_full.db` 전량(96만~98만여 건, 21개 테이블)을 시딩하고 확인:
- `/dur/screening/basic`, `/interaction`, `/ingredient` 3개 엔드포인트 실호출 정상 응답
- `pytest app/tests/` 320개 통과(사전에 존재하던 CLOVA OCR 네트워크 의존 테스트 3개, `scripts/drug_info_sync` 파이프라인 테스트 1개는 이 작업과 무관하게 실패/스킵)
- 이 과정에서 컬럼 길이 부족(위 표), `dur_prod_seobang_partition`/`dur_prod_pwnm_taboo`류에 없는 컬럼 조회, 품목 마스터 커버리지 부족 등 실데이터로만 드러나는 버그 여러 건을 발견해 수정

## 실행 방법 (로컬/신규 환경)

```
uv run alembic upgrade head
uv run python scripts/drug_info_sync/orchestrate_pipeline.py   # drugs_full.db가 없다면 (전수 수집, 시간이 오래 걸림)
uv run python -m app.scripts.seed_dur                            # drugs_full.db → MySQL
```

## 참고

- 모델: `app/models/dur.py`
- 마이그레이션: `app/core/db/migrations/versions/0026_add_dur_tables.py`
- 시드 스크립트: `app/scripts/seed_dur.py`
- 리포지토리: `app/repositories/dur_repository.py`, `app/repositories/dur_drug_repository.py`
