# Task ID: T-MED-10 (OCR 매칭에 Tier1 SQLite 마스터 DB 연결)

### 배경

`app/database/dur_drug_light.db`(feature/db-update, PR #37)에 이미 27,231개 약품(`products` 테이블,
item_seq/item_name/entp_name)이 있지만, 지금까지 챗봇/DUR 정보 조회(`DurDrugRepository`)에만 쓰이고
약품 인식(OCR) 매칭 파이프라인은 MySQL `medications` 캐시(Tier3 지연 적재 구조라 실제 조회된 약만
쌓여 아직 작음)만 조회하고 있었다. 이미 로컬에 있는 27k 마스터 데이터를 매칭에 안 쓰는 건 낭비라,
T-MED-9(유사도 매칭)에 이어 이 데이터도 매칭 후보로 연결한다.

### 참조

- 관련 코드: `app/repositories/dur_drug_repository.py` (`search_item_names`,
  `search_item_names_by_prefix`), `app/services/medication_service.py`
  (`_resolve_or_create_drug_like_names`, `_fuzzy_match_unrecognized_fields`,
  `_get_or_create_medication_from_tier1`)
- 선행 작업: T-MED-9
- 관련 이슈/PR: #108, #109

### 범위

- **포함**: MySQL(Tier2)에 정확일치가 없을 때, AUTO_ 더미 생성 전에 Tier1 SQLite에서 먼저 찾아보고
  있으면 `PDP_{item_seq}` 코드(공공 API/Tier3와 동일한 관습)로 MySQL에 캐싱(write-through). 유사도
  매칭도 MySQL 후보로 실패하면 Tier1을 시도 — 27k 전체를 매번 스캔하지 않도록 한글 쿼리 앞 2글자로
  SQLite 후보를 먼저 좁힘. sqlite3 동기 호출은 `asyncio.to_thread`로 감싸 이벤트 루프를 막지 않음.
  같은 item_seq 재조회 시 중복 레코드 없이 캐싱된 것을 재사용.
- **제외**: Tier1 SQLite 자체의 데이터 갱신/재적재(별도 인프라 작업), 27k 전체 스캔 성능 최적화(인덱스
  추가 등) — 필요성이 확인되면 후속 태스크.

### 완료 정의 (Definition of Done)

- [x] MySQL에 없는 약도 Tier1 SQLite에 정확히 같은 이름이 있으면 매칭되고, `PDP_{item_seq}` 코드로
      MySQL에 캐싱된다
- [x] 같은 약이 다시 조회되면 캐싱된 레코드를 재사용한다(중복 생성 없음)
- [x] MySQL 유사도 매칭으로 실패한 오인식 텍스트도 Tier1 SQLite 유사도 매칭으로 구제될 수 있다
- [x] Tier1에도 없는 완전히 새로운 약은 기존처럼 AUTO_ 더미 생성으로 이어진다(회귀 없음)
- [x] (공통) 테스트를 TDD로 작성했고(실제 SQLite 파일 대신 가짜 리포지토리로 결정적 검증)
      `uv run pytest`가 통과한다
