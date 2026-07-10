# Task ID: T-LLM-2-async-gateway (AI Worker 비동기 처리 인프라 — Gateway 도입)

> 신규 F/T-그룹이 아니라, 기존 T-LLM-2(챗봇)·T-LLM-3(콘텐츠 파이프라인)와 향후 T-DOC-1(처방전 인식)이
> 공통으로 쓸 통신 인프라를 다지는 서브 계약이다. `docs/tasks/T-MED-1-clova-ocr-benchmark.md`와 같은
> "기존 T-ID + 설명 접미사" 네이밍 방식을 그대로 따랐다. 결정 배경은
> `docs/decision_log/2026-07-10-ai-rag-worker.md` 전체를 참고.

### 참조
- 결정 배경: `docs/decision_log/2026-07-10-ai-rag-worker.md` (전체)
- 관련 PRD/TRD: F-LLM-2/T-LLM-2(챗봇, 실시간 소비자), F-LLM-3/T-LLM-3(콘텐츠 파이프라인, 이미 완료), F-DOC-1/T-DOC-1(처방전 인식, 향후 소비자) — 이 계약 자체는 TRD의 새 항목이 아니라 이들을 뒷받침하는 공통 인프라

### 목표
- 입력: 없음(신규 기능이 아니라 기존 `retriever_stub.py`/`llm_stub.py` 호출부를 대체하는 내부 인프라)
- 출력: `AIWorkerGateway`(가칭, 최종 파일/클래스명은 자율 판단 범위) — `search()`/`enqueue()`/`call_structured()` 3개 공개 메서드, 통일된 예외 3종, Celery worker 스캐폴드

### 완료 정의 (Definition of Done)
- [ ] `search(query, context)`: 기존 `Retriever.search()`와 동일하게 `ai_worker`의 `/retrieve`를 동기 HTTP로 호출한다 (실시간 소비자 = 챗봇)
- [ ] `enqueue(task_name, payload)`: Celery(+기존 Redis)로 비동기 작업을 등록하고 즉시 리턴한다. 결과는 별도 폴링 API 없이 태스크가 직접 DB에 저장한다(T-LLM-3 콘텐츠 파이프라인 패턴 재사용)
- [ ] `call_structured(system_prompt, user_input, schema)`: OpenAI 구조화 응답 호출 + 재시도 + Pydantic 스키마 검증만 담당. 프롬프트 문구/스키마 정의는 호출하는 도메인이 소유(Gateway가 도메인 프롬프트를 대신 작성하지 않는다)
- [ ] 예외 3종 통일: `AIWorkerUnavailableError`(업스트림 무응답/타임아웃) / `AIWorkerInvalidRequestError`(잘못된 호출) / `AIWorkerProcessingError`(응답은 왔으나 형식 이상). 빈 결과(정상)와 예외(실패)를 명확히 구분하고, 기존 `search()`가 실패를 조용히 삼키던 부분도 이 계약으로 변경
- [ ] 벡터DB(Chroma) 쓰기(재색인/임베딩 추가)는 Celery worker 단일 프로세스(동시성 1)만 수행하도록 구성. 읽기(검색)는 기존 `ai_worker` FastAPI 프로세스가 계속 동기 처리
- [ ] `app/services/chat_service.py`가 새 Gateway를 쓰도록 최소 배선만 교체(로직 변경 없음, import/클래스 교체 수준)
- [ ] (공통) 테스트를 TDD로 먼저 작성했고 `uv run pytest -v`가 통과하는가
- [ ] (공통) 모든 신규 코드에 대해 Ruff 포맷 및 Mypy 타입체크 통과

---

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
ai_worker/**
app/services/retriever_stub.py, app/services/llm_stub.py  (Gateway로 교체/통합 가능)
app/tests/services/test_retriever*.py, test_llm*.py (또는 신규 test_ai_worker_gateway.py)
docs/CODING_RULES.md  (AIWorkerGateway 사용 규칙 절 신설분만)
docs/tasks/T-LLM-2-async-gateway.md  (이 파일의 "완료 보고" 섹션만)
```

### 제한적 허용 (배선 교체만, 로직 변경 금지)
```
app/services/chat_service.py  (Retriever/LLM stub 호출부를 새 Gateway 호출로 교체하는 import/인스턴스화 수준만. 응급감지→컨텍스트조회→검색→스트리밍→저장 순서와 각 단계 책임은 그대로 유지)
```

### 금지 경로 (절대 수정하지 않음 — 필요해 보여도 "공유 파일 변경 필요"로 보고만)
```
docker-compose.yml  (리더 소유 — Celery worker 서비스 추가는 팀 리더와 별도 논의 후 리더가 진행)
app/core/**
app/dependencies/**
docs/plan/**  (PRD/TRD 수정 금지)
envs/**
infra/**
frontend/**
app/services/medication_*, auth_*, content_*, notification_*, tracking_*, diet_*  (다른 스쿼드 도메인)
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 의존하는 공유 계약 (읽기만 가능, 이미 고정됨)
- `app/core/config.py` — `AI_WORKER_RETRIEVE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` (Celery/Redis 관련 신규 설정값은 이 파일에 추가가 필요할 수 있음 → "공유 파일 변경 필요"로 보고)
- `docker-compose.yml`의 기존 `redis` 서비스 (브로커로 재사용, 새 서비스 추가는 금지 경로 참고)

### 자율 판단 허용 범위
- Gateway/예외 클래스의 정확한 파일 위치·이름(`retriever_stub.py`를 그대로 확장할지 새 `ai_worker_gateway.py`로 분리할지), Celery task 이름 규칙, 재시도 횟수/백오프 정책, `call_structured`의 재시도 최대 횟수 — 전부 자율 결정.

### 반드시 멈춰야 하는 경우 (이 Task에 한정된 추가 조건)
- `app/core/config.py`에 Celery/Redis 관련 설정을 추가해야만 진행 가능한 경우(공유 파일이므로 진행 전 보고)
- `chat_service.py`의 응급감지→컨텍스트조회→검색→스트리밍→저장 순서 자체를 바꿔야 할 필요가 생기는 경우

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feature/T-LLM-2-async-gateway-...`
