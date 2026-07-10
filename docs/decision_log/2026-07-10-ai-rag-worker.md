# 2026-07-10 — AI/RAG 워커 통신 방식 확정

> 그날 팀 전체의 결정을 모아두는 날짜 파일과 달리, 이 문서는 D스쿼드(LLM/AI) 담당 박지은이
> 자신의 담당 영역(AI/RAG 워커 통신 방식)에 대해 단독으로 내린 결정이라 별도 파일로 뺐다.

> 미결사항이었던 "AI/RAG 워커 통신 방식"(`docs/decision_log/2026-07-07.md` 참고)을 확정한다.
> 프로젝트는 POC 단계를 마치고 기능 간 연계성을 고려한 리팩토링 + 세부 정책 확정 단계로
> 넘어가는 시점이다.

## 결정 사항

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 전송 방식 | 하이브리드. 실시간(챗봇 RAG 검색)은 동기 HTTP 유지, 무거운/백그라운드 작업은 Celery + 기존 Redis로 큐잉 | Redis는 이미 `docker-compose.yml`에 존재. Celery는 업계 표준이라 팀원별 AI 에이전트가 각자 구현해도 정확도가 높음. `docs/tasks/T-LLM-3.md`에서 이미 "이번 라운드는 Celery 도입 안 함"으로 예고됐던 부분을 이번에 확정 |
| 동기/비동기 경계 기준 | "사용자가 화면에서 그 결과를 기다리는가?" — 그렇다면 동기, 아니면 Celery task | 챗봇 RAG 검색 = 동기(F-LLM-2 실시간 스트리밍 요구사항). 문서 재적재·DUR 데이터 재적재·건강뉴스 수집(F-LLM-6)·목표 리포트(F-GOAL-3) = Celery task 후보 |
| 결과 반환 방식 | 별도 상태조회/폴링 API를 만들지 않는다. Task 완료 시 결과를 DB에 저장하고, 필요한 화면/서비스는 기존 레포지토리 계층으로 조회 | T-LLM-3 콘텐츠 파이프라인이 이미 쓴 "생성 → DB 저장 → 캐시만 읽음" 패턴 재사용 |
| 처방전 OCR+LLM 구조화 (F-DOC-1) | 일단 동기로 구현. API P95 3초(T-QUAL-1) 초과 여부는 구현 후 실측하여 재검토 | 지금은 OCR+LLM 체인의 실제 지연시간 데이터가 없어 선제적으로 비동기화하지 않음 |
| 공통 모듈(Gateway) 범위 | `AIWorkerGateway`에 메서드 3개만 제공: `search()`(동기 RAG 검색), `enqueue()`(비동기 작업 등록), `call_structured()`(OpenAI 구조화 응답 호출 + 재시도 + 스키마 검증만 담당). 프롬프트 문구/추출 스키마는 호출하는 도메인이 직접 정의 | 프롬프트 엔지니어링까지 D스쿼드가 전 도메인을 대신 떠안지 않도록 경계를 좁힘. 도메인 간 반복되는 패턴의 공통화는 지금 하지 않고, 안정화 단계에 코드베이스를 스캔해 실사용 패턴을 확인한 뒤 결정 |
| 에러 처리 계약 | `AIWorkerUnavailableError`(업스트림 무응답/타임아웃) / `AIWorkerInvalidRequestError`(잘못된 호출) / `AIWorkerProcessingError`(응답은 왔으나 결과 형식 이상) 세 가지로 통일. 빈 결과(정상, 예: RAG 매칭 0건)와 에러(예외)는 명확히 구분 | `app/services/medication_open_api_client.py`의 `PublicDataApiError` 패턴을 그대로 재사용. 기존 `retriever_stub.py`가 실패를 조용히 삼키던 부분도 이 계약에 맞춰 변경 필요 |
| 벡터DB(ChromaDB) 배포 방식 | Server Mode 도입은 보류. 쓰기(재색인/임베딩 추가)는 Celery worker 단일 프로세스(동시성 1)만 담당, 읽기(검색)는 기존 `ai_worker` FastAPI 프로세스가 계속 동기 처리 | 여러 프로세스의 동시 쓰기 충돌을 피하면서 별도 Chroma 서버 없이 단순하게 유지. 실제로 문제가 생기면 안정화 단계에 재검토 |
| 소유권 | RAG Retriever/Context Binder(Gateway 포함, `ai_worker/` 전체)의 공통모듈 소유자를 박지은으로 `docs/squad-map.md`에 확정 등재 | 박지은이 이 파이프라인을 E2E로 담당하기로 함. 이후 다른 스쿼드가 이 Gateway를 수정하려면 PR에 `[공통모듈 변경]` 표시 + 박지은 리뷰 필요(`CONTRIBUTING.md` 기존 규칙 적용) |
| 인프라 변경(`docker-compose.yml`) | 이번 결정에 Celery worker 서비스 추가가 포함되지만, 실행은 보류 — 박지은이 팀 리더에게 필요성을 먼저 공유하고 리더가 진행 | `docker-compose.yml`은 리더 소유 파일이라 박지은이 직접 수정할 수 없음(`AGENTS.md` 4번 "공유 구역" 원칙과 동일) |

## 후속 작업 (범위 밖, 별도로 진행)

- 실제 구현 Task Contract: `docs/tasks/T-LLM-2-async-gateway.md` (작성 완료, T-MED-1-clova-ocr-benchmark.md와 같은 "기존 T-ID + 접미사" 네이밍)
- `docs/CODING_RULES.md`에 `AIWorkerGateway` 사용 규칙 절 추가 필요
- `docker-compose.yml`에 Celery worker(및 필요 시 beat) 서비스 추가는 팀 리더와 별도 논의
- 도메인별 프롬프트/파싱 공통화는 안정화 단계 코드베이스 스캔 후 결정

## 참고 — 이번 논의 중 발견한 별개 이슈

- `docs/tasks/_active.json`에 T-LLM-3가 아직 "진행 중"으로 등록돼 있으나 실제로는 완료 보고까지 끝난 상태 — 클레임 해제 필요(이번 결정과 무관, 별도 정리 권장)
