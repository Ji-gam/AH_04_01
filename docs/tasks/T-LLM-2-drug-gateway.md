## Task ID: T-LLM-2-drug-gateway (T-LLM-2 "AI 챗봇 상담" 하위 작업 — 의약품 데이터 게이트웨이)

### 참조
- PRD: F-LLM-2 / TRD: T-LLM-2 / REQ: REQ-BOT-001~005
- Issue: #75
- [T-LLM-2-dur-repository.md](T-LLM-2-dur-repository.md)에서 캡슐화한 `DurDrugRepository`(SQLite 단일 조회) 위에,
  MySQL 캐시와 외부 API 폴백을 더한 하위 작업. 신규 최상위 TRD 요구사항이 아니다.

### 목표
- 입력: 약품명(자연어 검색어)
- 출력: `list[DrugProfile]` + `provenance`(`sqlite` / `cache` / `api` / `miss`)
- 단일 파사드 `DurDrugRepository.drug_data(session, item_name)`가 아래 캐스케이드로 "어떻게든 답"을 만든다:
  1. SQLite(`dur_drug_light.db`) 검색
  2. 내용이 불충분하면 MySQL 캐시(`drug_data_cache`, 쿼리 문자열 정확매치) 조회 — SQLite 결과와 필드 단위 병합
  3. 그래도 불충분하면 자체 e약은요 API 클라이언트 호출 — 필드 단위 병합, 유의미한 결과는 캐시에 write-back(best-effort)

### 완료 정의 (Definition of Done)
- [x] `drug_data(session, item_name)`가 SQLite→MySQL캐시→외부API 캐스케이드로 `list[DrugProfile]` + provenance를 반환한다
- [x] 각 단계에서 핵심 필드(효능/용법/주의사항/부작용)가 비면 다음 단계로 이어 채운다(단순 "행 존재"가 아니라 "내용 있음" 기준), SQLite 전용 필드(성분/DUR규칙/최대투여량/식별정보/리콜)는 병합 시 보존된다
- [x] API 히트 중 실제 내용이 있는 결과만 MySQL 캐시(`drug_data_cache`, `query_name` 정확매치 키)에 write-back되고, 다음 동일 조회는 캐시(2단계)에서 히트한다
- [x] 캐시 쓰기 실패가 회신을 막지 않는다(best-effort, 예외 삼킴)
- [x] 자체 e약은요 클라이언트(`app/services/drug_public_api_client.py`) 신설, `medication_open_api_client.py`는 미수정
- [x] 기존 `find_drug_info`/`find_dur_warnings` 무회귀, SQLite 원본(`dur_drug_light.db`) 미변경
- [x] (공통) 테스트 함수명 영문, TDD 우선, ruff/mypy/pytest 통과(PR 직전 1회만 실행)

### 허용 경로
```
app/repositories/dur_drug_repository.py
app/services/drug_public_api_client.py  (신규)
app/models/drug_data_cache_model.py  (신규)
app/core/db/migrations/versions/0011_*.py  (신규, 공용부 — PR에 명시)
app/tests/repositories/test_dur_drug_repository.py
app/tests/services/test_drug_public_api_client.py  (신규)
docs/tasks/T-LLM-2-drug-gateway.md  (이 파일의 "완료 보고" 섹션만)
docs/tasks/_active.json  (등록만)
```

### 금지 경로
```
app/apis/v1/medication.py  (다른 스쿼드 소유)
app/**/medication_*  (다른 스쿼드 소유)
docker-compose.yml  (리더 소유)
app/database/dur_drug_light.db  (데이터 자체는 안 건드림, 조회만)
```

### 자율 판단 허용 범위
- 병합(merge) 알고리즘 세부 매칭 방식(`item_name` 기준), "내용 있음" 판정 기준 세부, 캐시 테이블 컬럼 타입, 클라이언트 에러 처리(네트워크 실패 시 빈 결과로 폴백) — 자율 결정.

### 알려진 한계 / 후속 작업 (이번 스코프 밖)
- 자체 e약은요 클라이언트는 `medication_open_api_client.py`와 일시적으로 중복된다. 외부 데이터 연동을 게이트웨이 소유로 통합하기 위한 자체 클라이언트이며, 향후 공용부 이관 시 합칠 대상.
- `chat_service.py`를 `drug_data()`에 연결하는 소비자 배선은 이번 스코프 제외 — 별도 PR.
- 음성(API도 빈) 결과는 캐시에 남기지 않는다 — 추후 데이터가 채워질 수 있으므로 매 요청마다 재시도.

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 전항목 충족. `app/tests` 전체 155개 통과, ruff check/format 통과, mypy 통과.
  신규 마이그레이션(0011)은 로컬 dev MySQL에 upgrade/downgrade/upgrade 왕복까지 직접 적용해 검증함.
- 가정(Assumptions):
  - `drug_data(name)`이 SQLite에서 여러 제품에 매칭되면 리스트 전체를 반환한다(사용자 확정 사항).
  - 단계 간 병합은 "덮어쓰기"가 아니라 "빈 필드만 채우기" 방식이며, SQLite 전용 구조화 필드(성분/DUR규칙/
    최대투여량/식별정보/리콜)는 하위 단계 데이터로 대체되지 않는다(사용자 확정 사항).
  - MySQL 캐시 키는 원 쿼리 문자열(trim만, 대소문자/부분매치 정규화 없음) 그대로 사용한다 — "동일 조회"를
    "동일한 입력 문자열"로 해석함.
  - API 응답에 실제 내용이 없으면(음성 결과) 캐시에 쓰지 않는다 — 추후 API 데이터가 채워질 가능성을 위해
    매 요청마다 재시도하도록 함(DoD에 명시된 요구는 아니나, "미스 영구 고착" 방지를 위한 자율 판단).
  - 캐시 히트가 있으면(내용이 빈약해도) 그 요청에 한해 API를 다시 호출하지 않는다 — 캐싱의 목적(외부 호출
    절감)에 부합한다고 판단.
- 공유 계약 변경 필요 사항 (있다면): 없음. `app/core/db/migrations/`(공용부)에 `0011_drug_data_cache.py` 추가 — PR에 명시.
- 브랜치명: `feat/75-drug-gateway`
