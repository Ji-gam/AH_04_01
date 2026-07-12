## Task ID: T-LLM-2-dur-repository (T-LLM-2 "AI 챗봇 상담" 하위 작업 — DUR 조회 리포지토리 캡슐화)

### 참조
- PRD: F-LLM-2 / TRD: T-LLM-2 / REQ: REQ-BOT-001~005
- `chat_service.py`가 임부/노인 DUR 경고를 만들 때 참조하는 데이터 접근 로직을 정리하는
  하위 작업. 신규 최상위 TRD 요구사항이 아니다.

### 목표 (TRD 원문 그대로)
- 입력: 자연어 질문(텍스트/음성)
- 출력/노출: 스트리밍 답변, 응급 시 Fallback 메시지, 음성 출력
- (이번 하위 작업 한정) `chat_service.py`가 임부/노인 사용자에게 DUR 경고를 붙일 때 쓰는
  `app/database/dur_drug_light.db` 조회를 raw sqlite3 인라인 코드 대신 리포지토리로 캡슐화

### 완료 정의 (Definition of Done)
- [ ] `app/repositories/dur_drug_repository.py`에 `DurDrugRepository` 클래스가 있고,
      `find_drug_info(item_name)`(범용 조회: 성분/효능/용법/최대투여량/식별정보/리콜/DUR규칙)와
      `find_dur_warnings(item_name, pregnant, geriatric)`(chat_service 전용 좁은 조회)를 제공한다
- [ ] `chat_service.py`의 `_collect_dur_warnings`가 raw sqlite3 대신 이 리포지토리를 호출한다
      (기존 동작 — 임부/노인 대상 PWNM/ODSN 규칙 경고 문구 — 은 그대로 유지)
- [ ] `ChatService.__init__`에 `dur_drug_repository` 주입 파라미터가 추가되어 기존 DI 패턴과
      일관되고, 기존 `ChatService()` 무인자 호출은 그대로 동작한다
- [ ] 리포지토리 단위 테스트 + `chat_service` 주입 테스트 추가
- [ ] (공통) ruff/mypy 통과, `app/tests` 전부 통과(PR 직전 1회만 실행)

### 허용 경로
```
app/repositories/dur_drug_repository.py
app/services/chat_service.py  (_collect_dur_warnings, __init__ 주입 파라미터만)
app/tests/repositories/test_dur_drug_repository.py
app/tests/services/test_chat_service.py
docs/tasks/T-LLM-2-dur-repository.md  (이 파일의 "완료 보고" 섹션만)
docs/tasks/_active.json
```

### 금지 경로
```
app/apis/v1/medication.py  (다른 스쿼드 소유 — raw sqlite3 쿼리 그대로 둠)
app/repositories/medication_repository.py
app/database/dur_drug_light.db  (데이터 자체는 안 건드림, 조회만)
```

### 자율 판단 허용 범위
- 리포지토리 메서드 세부 반환 타입(dataclass/dict), 내부 SQL 조인 방식, 테스트 케이스 구성 — 자율 결정.

### 알려진 한계 (이번 스코프 밖, 참고만)
- `dur_drug_light.db`는 제품 27,231건 중 효능 데이터가 4,753건뿐이라 커버리지 밖 의약품엔
  DUR 경고가 안 울리는 사각지대가 있음(이미 팀에 공유됨). 스테이징 시 풀버전(`_data/dur_drug.db`)
  으로 교체 예정 — 이번 리포지토리 캡슐화 작업과 무관하게 별도 진행.

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/67-dur-repository`
