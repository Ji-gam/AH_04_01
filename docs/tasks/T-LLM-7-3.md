## Task ID: T-LLM-7-3 (질환 논문 검색 에이전트 — IV단계: PubMed 실연동)

### 참조
- 배경: "ai_worker · RAG 원정기" 로드맵 IV단계.
- T-LLM-7이 명시적으로 이번 작업을 유보했던 지점: "진짜 검색 연동(PubMed/Semantic
  Scholar)은 팀 승인 후 별도 태스크로 진행"(T-LLM-7 "반드시 멈춰야 하는 경우").
  팀 미팅에서 외부 API 연동 승인 완료(AGENTS.md §6 STOP 조건 충족, 2026-07-16).
- T-LLM-7-1/7-2는 `ai_worker/tools/paper_search.py`를 금지 경로("참조만, 수정 안 함")로
  묶어뒀음 — 이번 태스크에서 최초로 그 파일 내부를 교체한다.

### 목표
- `search_disease_paper` 스텁(질환별 로컬 JSON 1건 반환)을 PubMed E-utilities
  (esearch → efetch) 실연동으로 교체한다.
- 소스는 PubMed 단독이다(Semantic Scholar 미포함, 둘 다도 아님).
- `app/scripts/generate_health_content.py`(건강 콘텐츠 카드 생성 파이프라인)는 이번
  스코프에 포함하지 않는다 — 그 파이프라인의 논문 그라운딩 연결은 별도 후속 태스크.

### 완료 정의 (Definition of Done)
- [ ] `search_disease_paper`가 로컬 스텁 JSON 대신 PubMed esearch+efetch를 실제로 호출해
      제목/초록/출처(PMID·PubMed URL)를 반환한다
- [ ] 질환 5개(암/심장질환/뇌혈관질환/당뇨/간질환) → 영어 PubMed 검색어(MeSH) 매핑이
      존재하고, 매핑 밖 질환은 기존과 동일하게 화이트리스트 거부 메시지를 반환한다
      (이 경우 HTTP 호출이 발생하지 않는다)
- [ ] 검색 결과가 여러 건일 때 "그 중 무엇을 반환할지"에 대한 결정론적 선택 전략이
      코드로 고정되어 있다(최신순 정렬 후 초록이 있는 첫 논문)
- [ ] 반환 문자열에 PMID/PubMed URL이 포함되어, `_ANSWER_SYSTEM_PROMPT`의 "이것이
      단일 연구 결과임을 밝히세요" 지시가 실제로 인용할 근거를 가진다
- [ ] PubMed 요청 실패(타임아웃/네트워크 오류/비정상 응답/XML 파싱 실패)는 조용히
      삼키지 않고 `PaperSearchUnavailableError`로 알리며, 라우터에서 503으로 변환된다
      (`GenerationUnavailableError`와 동일한 관례)
- [ ] `search_disease_paper`가 비동기 함수로 바뀌었고, 호출부(`ask_paper_agent`)가
      `.invoke()`가 아닌 `await ... .ainvoke()`로 호출한다
- [ ] `ai_worker/core/config.py`에 `PUBMED_API_KEY`(optional), `PUBMED_TIMEOUT` 설정이
      추가된다
- [ ] `envs/example.local.env`, `envs/example.prod.env`에 `PUBMED_API_KEY=` 키 이름이
      추가된다(실값 금지)
- [ ] 기존 스텁 기반 테스트(경로 traversal, 파일 존재 여부 등)는 제거/재작성되고,
      PubMed 응답을 `httpx.MockTransport`로 모킹한 신규 테스트로 대체된다 — 화이트리스트
      검증 자체(지원 밖 질환 거부)는 계속 회귀 고정한다
- [ ] 실제 `OPENAI_API_KEY`+네트워크로 `/agent/paper-search`를 5개 질환 모두 수동
      호출해, 실제 PubMed 초록+출처가 붙어 나오는지 육안 확인한다(모킹 테스트만으로
      "진짜 검색이 된다"를 검증한 것으로 간주하지 않는다)
- [ ] (공통) ruff/mypy 통과, `ai_worker/tests` 전부 통과

### 허용 경로
```
ai_worker/tools/paper_search.py
ai_worker/tasks/paper_agent.py  (search_disease_paper 호출부의 .invoke → .ainvoke 변경만)
ai_worker/core/config.py  (PUBMED_API_KEY/PUBMED_TIMEOUT 설정 추가만)
ai_worker/routers/paper_agent_router.py  (PaperSearchUnavailableError 캐치 + 설명 문구 갱신만)
ai_worker/tests/test_paper_agent.py
ai_worker/mock_data_for_papers/**  (스텁 역할 종료로 삭제 대상)
envs/example.local.env, envs/example.prod.env  (PUBMED_API_KEY= 키 이름만 추가 — 실값 금지)
docs/tasks/T-LLM-7-3.md  (이 파일의 "완료 보고" 섹션만)
docs/tasks/_active.json  (T-LLM-7-3 등록/해제)
```

### 금지 경로
```
app/scripts/generate_health_content.py  (별도 후속 태스크 스코프, 이번 작업과 무관)
ai_worker/tasks/generate_structured.py
ai_worker/tasks/ingest.py
ai_worker/main.py  (엔드포인트 계약 변경 없음 — /agent/paper-search 경로 그대로)
app/services/ai_worker_gateway.py  (이번 스코프는 ai_worker 내부 한정)
ai_worker/core/config.py의 기존 필드(OPENAI_*, RAG_SIMILARITY_THRESHOLD 등)
```

### 의존하는 공유 계약 (읽기만 가능)
- `ai_worker/tasks/generate_structured.py`의 `GenerationUnavailableError` → 503 관례
  (`PaperSearchUnavailableError`가 동일 패턴을 따른다)
- `app/services/drug_public_api_client.py` / `app/tests/services/test_drug_public_api_client.py`
  — httpx 호출·모킹 컨벤션의 참고 선례

### 자율 판단 허용 범위
- 질환→PubMed 검색어(MeSH 쿼리) 문구 세부 튜닝, 결과 선택 전략의 구체 파라미터
  (retmax 개수 등), NCBI `tool`/`email` 식별 파라미터 부착 여부, mock_data_for_papers
  삭제 여부, 에러 메시지 문구, 내부 함수 분리 방식 — 전부 자율 결정.

### 반드시 멈춰야 하는 경우
- PubMed API가 요구사항(논문 수치 그라운딩 품질)을 충족 못 해 Semantic Scholar 등
  다른 소스 추가가 필요해 보이는 경우(이번 스코프는 PubMed 단독으로 확정됨)
- `app/scripts/generate_health_content.py` 쪽 연동이 필요해 보이는 경우(별도 태스크)

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 전항목 충족. `uv run pytest ai_worker/tests` 48 passed,
  `ruff check`/`ruff format --check`/`mypy ai_worker/` 클린. 실제 `OPENAI_API_KEY`+
  네트워크로 5개 질환 전체(`search_disease_paper` 직접 호출) 및 `ask_paper_agent`
  전체 파이프라인(정보요청/관용구/무관 질문 3케이스) 수동 검증 완료 — 모두 실제
  PubMed 제목/초록/PMID가 붙어 나옴. `PUBMED_TIMEOUT` 극단값으로 503 경로도 확인.
- 가정(Assumptions): PubMed 검색어는 5개 질환 모두 "Clinical Trial OR RCT" 필터를
  적용(Review 제외) — 기존 스텁 초록의 "단일 연구 수치 인용" 톤 유지 목적. 결과
  선택은 최신순 정렬 후 초록이 있는 첫 논문(재현 가능한 스코어링 없음, MVP 수준).
  `mock_data_for_papers/*.json`은 스텁 역할 종료로 삭제(테스트 fixture는 인라인 내장).
- 공유 계약 변경 필요 사항: 없음(`ai_worker/` 내부 자기소유 파일만 변경).
- 브랜치명: `feat/T-LLM-7-3-pubmed-integration`
