## Task ID: T-LLM-2-dur-interaction-warning (T-LLM-2 "AI 챗봇 상담" 하위 작업 — 등록 약물 간 병용금기 경고 연결)

### 참조
- PRD: F-LLM-2 / TRD: T-LLM-2 / REQ: REQ-BOT-001~005
- `chat_service.py`가 임부/노인 단일 약물 경고(`_collect_dur_warnings`)만 챗봇에 주입하던 것을,
  medication 스쿼드(T-MED-14)가 이미 만든 `DurScreeningService.screen_interactions()`(병용금기/
  효능군중복)까지 연결하는 하위 작업. 신규 최상위 TRD 요구사항이 아니다.

### 목표 (TRD 원문 그대로)
- 입력: 자연어 질문(텍스트/음성)
- 출력/노출: 스트리밍 답변, 응급 시 Fallback 메시지, 음성 출력
- (이번 하위 작업 한정) 사용자가 등록한 복약 목록이 2개 이상이면, 그 약물들 간의 병용금기/
  효능군중복 정보를 `injected_context`로 만들어 챗봇 프롬프트에 반영한다.

### 완료 정의 (Definition of Done)
- [x] `ChatService.__init__`에 `dur_screening_service` 주입 파라미터 추가(기존 DI 패턴과 일관,
      무인자 호출은 그대로 동작)
- [x] `_collect_interaction_warnings(meds)` 추가: 등록 약물 2개 미만이면 호출 생략, 2개 이상이면
      `DurScreeningService.screen_interactions()`를 호출해 `병용금기`/`효능군중복주의` 결과를
      `[병용금기 경고] ...` 문자열로 포맷해 `injected_context`에 병합
    - 임신/노인 게이팅과 무관하게 항상 계산(약물 조합 위험은 전체 사용자 대상)
- [x] `app/services/dur_service.py`, `app/repositories/dur_repository.py` 등 medication 스쿼드
      소유 파일은 무수정(순수 임포트·호출, 읽기 전용 SQLite 조회)
- [x] 단위 테스트 추가: 2개 미만이면 미호출 / 스크리닝 결과 포맷 검증 / `stream_reply` 통합 흐름에서
      `injected_context` 반영 확인
- [x] ruff/mypy 통과, 관련 테스트 전부 통과

### 허용 경로
```
app/services/chat_service.py  (__init__ 주입 파라미터, _collect_interaction_warnings, stream_reply)
app/tests/services/test_chat_service.py
docs/tasks/T-LLM-2-dur-interaction-warning.md  (이 파일)
docs/tasks/_active.json
```

### 금지 경로
```
app/services/dur_service.py        (medication 스쿼드 소유 — 순수 소비만)
app/repositories/dur_repository.py (medication 스쿼드 소유)
ai_worker/**                       (injected_context를 그대로 받아 쓰는 구조라 변경 불필요)
```

---

### 완료 보고
- 완료 정의 체크리스트: 전부 충족
- 가정(Assumptions): 이번 스코프는 "사용자가 이미 등록한 복약 목록끼리의 병용금기"만 커버한다.
  채팅 메시지에 실시간으로 타이핑된 임의의 약물명(예: "타이레놀이랑...")까지 인식하는 것은
  별도의 약물명 추출(NER/매칭) 작업이 필요해 이번 범위에서 제외했다.
- 공유 계약 변경 필요 사항: 없음
- 브랜치명: `feature/T-LLM-2-dur-interaction-warning`
- 검증:
  - `docker compose exec fastapi uv run pytest app/tests/services/test_chat_service.py -q` → 19 passed
  - `docker compose exec fastapi uv run mypy app/services/chat_service.py app/tests/services/test_chat_service.py` → Success
  - `docker compose exec fastapi uv run ruff check app/services/chat_service.py app/tests/services/test_chat_service.py` → All checks passed
