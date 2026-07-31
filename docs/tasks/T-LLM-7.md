## Task ID: T-LLM-7 (질환 논문 검색 에이전트 — I단계: 뼈대 세우기)

### 참조
- 배경: "ai_worker · RAG 원정기 v2" 로드맵(D스쿼드 박지은 작성, 2026-07-10) I단계.
- T-LLM-3-3(챗봇 LLM 호출을 `ai_worker`로 이전)과는 별개 작업 — T-LLM-7이 선행됨.

### 목표
- 실제 논문 검색 API 없이도, "도구를 판단해서 부르는 에이전트" 패턴을 `ai_worker` 안에서
  검증할 수 있는 최소 골격을 만든다. 진짜 검색 연동(PubMed/Semantic Scholar)은 팀 승인 후
  별도 태스크로 진행하며 이번 스코프에 포함하지 않는다.

### 완료 정의 (Definition of Done)
- [ ] 질환 5개(암/심장질환/뇌혈관질환/당뇨/간질환, `app/services/content_service.py`의
      `POPULAR_DISEASES`와 동일한 키)의 논문 제목+초록 스텁이 파일로 존재한다
- [ ] `search_disease_paper()`가 `@tool` 데코레이터로 LangChain 도구화되어 있다
- [ ] 도구 1개를 쥔 LangChain 에이전트가 `ai_worker`의 신규 엔드포인트로 호출 가능하다
- [ ] "당뇨 논문 알려줘"류 질문엔 도구를 호출하고, "오늘 날씨 어때"류 무관 질문엔 도구를
      호출하지 않는다 — pytest로 회귀 고정(LLM 호출 mock), 단 진짜 판단력 자체는 실제
      API 키로 최소 1회 수동 실행하여 육안 확인한다(모킹만으로 판단력을 검증한 것으로
      간주하지 않는다)
- [ ] "당뇨병 논문 줘"처럼 stub 키와 정확히 안 맞는 표현도 도구 설명(docstring)의 유도로
      정상 매칭되는지 확인한다
- [ ] `OPENAI_API_KEY` 미설정 시 `generate_structured.py`와 동일한 관례(명확한 에러)를 따른다
- [ ] (공통) 새 코드에 대해 ruff/mypy 통과

### 허용 경로
```
ai_worker/mock_data_for_papers/**
ai_worker/tools/**
ai_worker/tasks/paper_agent.py
ai_worker/main.py  (신규 엔드포인트 추가만, 기존 /retrieve·/generate-structured 로직 변경 금지)
ai_worker/tests/test_paper_agent.py
docs/tasks/T-LLM-7.md  (이 파일의 "완료 보고" 섹션만)
```

### 금지 경로
```
ai_worker/main.py의 /retrieve, /generate-structured 기존 로직
ai_worker/tasks/ingest.py, ai_worker/tasks/generate_structured.py (기존 DUR/구조화생성 파이프라인)
app/services/ai_worker_gateway.py  (이번 스코프는 ai_worker 내부 한정, Gateway 연동 없음)
ai_worker/core/**
```

### 의존하는 공유 계약 (읽기만 가능)
- `app/services/content_service.py`의 `POPULAR_DISEASES` — 질환 키 문자열 소스
- `ai_worker/core/config.py`의 `settings.OPENAI_API_KEY`/`OPENAI_MODEL`
- `ai_worker/tasks/generate_structured.py`의 "API 키 없으면 명확한 에러" 관례

### 자율 판단 허용 범위
- 스텁 JSON 파일의 세부 필드명, 에이전트 시스템 프롬프트 문구, 엔드포인트 경로명,
  내부 함수 분리 방식 — 전부 자율 결정.

### 반드시 멈춰야 하는 경우
- 진짜 논문 API 연동이 필요해 보이는 경우(로드맵 IV단계, 팀 승인 필요 구간)
- `app/` 쪽 Gateway 연동이 필요해 보이는 경우(이번 스코프 아님, 후속 태스크로 분리 보고)

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/T-LLM-7-...`
