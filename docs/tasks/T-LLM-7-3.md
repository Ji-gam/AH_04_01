## Task ID: T-LLM-7-3 (질환 논문 검색 에이전트 — 오프라인 인제스천+벡터검색 RAG)

### 참조
- 배경: "ai_worker · RAG 원정기" 로드맵(PubMed 연동 단계, 정확한 로마자 단계 표기는
  로드맵 원본 참고 — 이 문서 안에서는 임의로 재부여하지 않는다).
- 이번 세션 앞부분에서 `search_disease_paper` 스텁을 PubMed 실시간 API 호출(esearch→
  efetch를 질문마다 호출)로 먼저 교체했으나, "질문마다 질환 카테고리+최신순 필터로만
  조회해 사용자의 실제 질문 내용과 무관한 논문이 선택될 수 있다"는 결함이 드러나
  아키텍처를 다시 설계했다. **라이브 호출 방식은 유지하지 않고 완전히 대체한다.**
  가벼운 우회(쿼리 키워드 보강, LLM 재순위)는 명시적으로 거부하고, 오프라인
  인제스천(청킹+임베딩+Chroma 색인) + 질문 시점 벡터 검색으로 재구축했다.
- 기존 DUR 검색(`ai_worker/services/retrieve_service.py`, `ai_worker/tasks/ingest.py`)의
  임베딩/Chroma/동적 메타데이터 필터/임계값 컷 인프라를 최대한 재사용했다. 단
  `retrieve_service.py`의 `db_holder`는 건드리지 않고(다른 곳에서 이름으로 재노출·
  테스트가 직접 조작 중), 완전히 별도인 `paper_db_holder` 싱글톤을 새로 만들었다.

### 목표
- `ai_worker/tools/paper_search.py`(라이브 호출)를 삭제하고, PubMed 원본을 미리
  오프라인으로 수집·색인해둔 뒤 질문 시점엔 벡터 검색만 수행하도록 바꾼다.
- 소스는 PubMed 단독이다(Semantic Scholar 미포함).
- 인제스천은 두 단계로 분리한다: (1) 원본 수집(`fetch_and_append_category_papers`,
  질환×카테고리 조합별로 PubMed에서 수집해 `ai_worker/mock_data_for_papers_raw/{질환}.json`에
  그대로 저장 — 가공 전 원문이라 사람이 직접 검토 가능), (2) 청킹+임베딩+Chroma 저장
  (`ingest_papers`, PMID 기준 증분 — 이미 색인된 논문은 재임베딩하지 않는다).
- 매일 신규 논문을 수집해 RAG 재료를 계속 보강할 수 있도록, 두 단계를 잇는 완결된
  배치(`run_daily_pipeline`, CLI `--pipeline`)를 만든다. **다만 이 명령 자체를 매일
  자동 실행시키는 스케줄러(cron/Celery beat)는 이번 스코프에 포함하지 않는다** —
  스테이징 환경이 아직 없어, T-LLM-3와 동일한 원칙으로 배치 로직은 수동 트리거로
  완성해두고 실제 자동 스케줄링은 스테이징이 생긴 뒤 별도로 붙이기로 결정했다. 그
  때까지는 `uv run python -m ai_worker.tasks.ingest_papers --pipeline`을 사람이 매일
  한 번 수동 실행한다.
- 멀티 논문 인용으로 업그레이드: 청크 여러 개를 프롬프트에 번호 매겨 넣고, 답변이
  각 수치를 어느 PMID의 것인지 구분해 밝히도록 지시한다. `PaperAgentResponse`에
  `sources: list[{name, url}]`(PMID 기준 중복 제거)를 답변과 별도 필드로 반환해,
  프론트엔드가 출처 각주 UI를 붙일 수 있게 계약만 만들어둔다.
- `app/services/chat_service.py` 연동과 프론트엔드 출처 칩 UI(클릭 시 출처명 +
  [바로가기] 버튼)는 **의도적으로 이번 스코프에서 제외**한다 — 그 파일이 이 작업
  시작 시점에 이미 다른 무관한 작업으로 수정 중이라 충돌 위험이 있었고, 프론트엔드는
  별도 도메인이라 스코프 분리가 자연스럽다. 별도 후속 태스크로 넘긴다.

### 완료 정의 (Definition of Done)
- [x] `ai_worker/tools/paper_search.py`(라이브 호출) 삭제, `SUPPORTED_DISEASES`는
      `ai_worker/tasks/ingest_papers.py`로 이동(순환 임포트 방지 — `paper_agent.py`가
      거기서 import)
- [x] 1단계 원본 수집: 5개 질환 × 3개 카테고리(LIFESTYLE/FOOD/MEDICAL_NEWS)로
      PubMed에서 수집해 `ai_worker/mock_data_for_papers_raw/{질환}.json`에 저장,
      PMID 중복은 파일 단위로 스킵
- [x] 2단계 청킹+임베딩+Chroma 저장(`build_documents`/`build_paper_vector_store`/
      `ingest_papers`): 제목+초록 결합 1000자 이하는 단일 문서, 초과분은
      `RecursiveCharacterTextSplitter(1000/100)`로 분할. 컬렉션 `pubmed_papers`(DUR의
      `dur_rules`와 도메인 분리), 같은 `CHROMA_DIR` 아래
- [x] **PMID 기준 증분 인제스천**: 이미 색인된 논문은 재임베딩하지 않고, 신규 논문만
      임베딩한다(`_indexed_pmids`) — 전체 재임베딩 방식은 초기에 시도했다가 "원본이
      늘어날 때마다 이미 낸 임베딩 비용을 계속 반복 청구한다"는 문제로 폐기
  ```
      uv run python -m ai_worker.tasks.ingest_papers --pipeline
  ```
  (자동 스케줄러는 스테이징 이후 별도 작업)
- [x] `ai_worker/services/paper_retrieve_service.py` 신규: `paper_db_holder`(DUR의
      `db_holder`와 완전 별개 싱글톤), `ensure_paper_db()`, `search_papers()`
      (`filter={"disease": disease}` 정확 매칭 — `classify_query()`가 이미 질환을
      결정론적으로 뽑아주므로 DUR처럼 substring 매칭 흉내 불필요)
- [x] `ai_worker/tasks/paper_agent.py`: `@tool` 에이전틱 호출 제거, `search_papers()`
      직접 함수 호출로 교체. 멀티 논문 인용 프롬프트, `sources` 구조화 반환
- [x] `ai_worker/routers/paper_agent_router.py`: `PaperSearchUnavailableError`(삭제됨)
      대신 `/retrieve`와 동일한 `EmbeddingUnavailableError`/`EmbeddingMismatchError`
      매핑으로 교체
- [x] `ai_worker/core/config.py`에 `PAPER_SIMILARITY_THRESHOLD`(1.6, 잠정값),
      `PAPER_RETRIEVAL_LIMIT`(5) 추가. `PUBMED_API_KEY`/`PUBMED_TIMEOUT`은 유지(역할만
      "질문 시점 조회"에서 "배치 수집 전용"으로 바뀜)
- [x] `pyproject.toml` `ai` 그룹에 `langchain-text-splitters` 명시 선언(기존엔 전이
      의존성으로만 존재해 조용히 깨질 수 있었음)
- [x] 기존 라이브 호출 mock 테스트(`httpx.MockTransport` 패턴)는 `test_ingest_papers.py`로
      이관해 "배치 대량 수집"을 검증하도록 재작성. `test_paper_agent.py`는
      `ensure_paper_db`/`search_papers` 몽키패치 방식으로 재작성(멀티 논문 인용,
      sources 중복 제거, 빈 결과 케이스 포함). `test_paper_retrieve_service.py` 신규
- [x] `ai_worker/scripts/eval_paper_agent.py`(수동 평가 스크립트)도 새
      `ask_paper_agent(question, db)` 시그니처에 맞춰 갱신
- [x] 실제 `OPENAI_API_KEY`+네트워크로 `/agent/paper-search`를 여러 질환·여러
      질문으로 수동 호출해, 질문이 바뀌면 실제로 다른 PMID/내용이 나오는지 확인
      (라이브 호출 버전과의 핵심 차이 — 카테고리+최신순 고정이 아니라 질문에 반응)
- [x] (공통) `ruff check`/`ruff format --check`/`mypy ai_worker/` 클린,
      `uv run pytest ai_worker/tests` 전부 통과(58 passed)

### 허용 경로
```
ai_worker/tasks/ingest_papers.py
ai_worker/services/paper_retrieve_service.py  (신규)
ai_worker/tasks/paper_agent.py
ai_worker/routers/paper_agent_router.py
ai_worker/schemas/retrieval_schema.py  (PaperSourceRef 추가, PaperAgentResponse.sources)
ai_worker/core/config.py  (PAPER_SIMILARITY_THRESHOLD/PAPER_RETRIEVAL_LIMIT 추가만)
ai_worker/scripts/eval_paper_agent.py
ai_worker/tests/test_ingest_papers.py, test_paper_agent.py, test_paper_retrieve_service.py
ai_worker/mock_data_for_papers_raw/**  (1단계 원본, 재현성 확보 목적으로 보관)
pyproject.toml  (langchain-text-splitters 의존성 선언만)
docs/tasks/T-LLM-7-3.md  (이 파일)
docs/tasks/_active.json  (T-LLM-7-3 등록/해제)
```

### 금지 경로
```
app/services/chat_service.py  (별도 후속 태스크 스코프 — 이 작업 시작 시점에 이미
  다른 무관한 작업으로 수정 중이었음, 충돌 방지를 위해 건드리지 않는다)
frontend/**  (출처 칩 UI는 별도 후속 태스크)
ai_worker/services/retrieve_service.py  (db_holder 구조 변경 금지 — DUR 쪽이 깨짐)
ai_worker/tasks/ingest.py  (get_embeddings/active_embedding_model/CHROMA_DIR/
  assert_embedding_compatible는 import해서 재사용만, 파일 자체는 안 건드림)
ai_worker/main.py  (엔드포인트 계약 변경 없음 — /agent/paper-search 경로 그대로)
app/services/ai_worker_gateway.py  (이번 스코프는 ai_worker 내부 한정)
ai_worker/core/config.py의 기존 필드(OPENAI_*, RAG_SIMILARITY_THRESHOLD 등)
```

### 의존하는 공유 계약 (읽기만 가능)
- `ai_worker/tasks/ingest.py`의 `get_embeddings`/`active_embedding_model`/`CHROMA_DIR`/
  `assert_embedding_compatible`/`EmbeddingUnavailableError`/`EmbeddingMismatchError`
- `ai_worker/tasks/generate_structured.py`의 `GenerationUnavailableError` → 503 관례

### 자율 판단 허용 범위
- 청킹 임계값/크기(1000자/오버랩 100) 구체 파라미터, `PAPER_SIMILARITY_THRESHOLD`
  잠정값 조정, 출처 각주 스키마(`name`/`url`) 세부 형태, 내부 함수 분리 방식 — 전부
  자율 결정.

### 반드시 멈춰야 하는 경우
- PubMed 단독으로는 커버 안 되는 요구(예: 논문 전문(full-text) 필요)가 생겨 다른
  소스 추가가 필요해 보이는 경우
- `app/services/chat_service.py` 연동 또는 프론트엔드 출처 칩 UI 작업이 필요해
  보이는 경우(별도 후속 태스크로 분리됨)

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 전항목 충족. `uv run pytest ai_worker/tests` 58 passed,
  `ruff check`/`ruff format --check`/`mypy ai_worker/` 클린.
- 실제 검증: `/agent/paper-search`를 TestClient로 실제 호출해 "심장질환 환자한테
  운동이 도움이 되나요?" 질문에 PMID 5건을 각각 구분해 수치 인용(예: "인터루킨-6이
  42.4% 증가", "VO2peak가 5.6±2.3 mL/kg/min 증가")하는 답변과 `sources` 5건(제목+URL)을
  확인. "당뇨 저혈당 관리" vs "당뇨 환자 식이요법"(같은 질환, 다른 질문)에서 3건 중
  겹치는 PMID가 1개뿐임을 확인해, 질문 내용에 실제로 반응하는 검색임을 검증(라이브
  호출 버전과의 핵심 차이). 논문과 무관한 질문("오늘 날씨 어때?")은 분류 단계에서
  걸러져 DB 호출 없이 정중히 거절, `sources: []`.
  `--pipeline` 실제 실행으로 신규 논문 75건 수집 후 신규분만(268청크) 증분 색인,
  기존 663건(2280청크)은 재임베딩 안 됨을 로그로 확인(2280→2548건).
- 가정(Assumptions)/이탈 기록:
  - 청킹 설계 당시 "제목+초록 결합이 1000자 이하인 게 대부분"이라 가정했으나, 실제
    수집된 663건 중 98.3%(652건)가 1000자를 초과해 분할 대상이었다(중앙값 1968자,
    Clinical Trial/RCT 원 연구라 구조화 초록이 많은 탓으로 추정). 기능적으로는
    문제없이 동작하나(청크당 pmid/title 메타데이터 유지), 설계 가정과 실제 데이터
    특성이 다르다는 점을 남겨둔다. 청크 크기(1000/오버랩 100)는 그대로 유지.
  - 최초 인제스천 구현은 "컬렉션에 뭔가 있으면 통째로 스킵"(전체 재임베딩 아니면
    전체 스킵) 게이트였는데, 사용자 지적으로 "PMID 기준 증분"(이미 색인된 것만
    스킵, 신규만 임베딩)으로 교체했다 — 원본이 계속 늘어날 때마다 기존 임베딩
    비용을 반복 청구하는 결함이었음.
  - 라이브 호출 버전에 있던 카테고리 무분류 수집 방식(질환만으로 넓게 수집)은
    1단계 진행 중 "약물/치료 위주로 쏠림" 문제로 폐기하고, 항상 질환×카테고리
    조합으로 수집(`ai_worker/tasks/ingest_papers.py` 참고).
- 공유 계약 변경 필요 사항: 없음(`ai_worker/` 내부 자기소유 파일만 변경. `db_holder`
  구조는 손대지 않음).
- 후속 작업(별도 태스크로 이관): `app/services/chat_service.py`에 paper-search 연동
  추가 + 프론트엔드(`ChatPage`) 출처 칩 UI("[출처]" 클릭 → 출처명 + [바로가기]) 제작.
  자동 스케줄러(cron/Celery beat)로 `--pipeline`을 매일 자동 실행시키는 것은 스테이징
  환경이 생긴 뒤 진행.
- 브랜치명: `feat/T-LLM-7-3-pubmed-integration`
