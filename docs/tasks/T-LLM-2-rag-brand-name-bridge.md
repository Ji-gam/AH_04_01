## Task ID: T-LLM-2-rag-brand-name-bridge (T-LLM-2 "AI 챗봇 상담" 하위 작업 — RAG 브랜드명 인식 범위 확대)

> 작성자: 박지은(D스쿼드, `chat_*`/`ai_worker/` 소유). **이 문서는 착수 전 계획(plan)이다.**
> 리더 승인 불필요 — 전부 `ai_worker/` 내부 파일, Chroma 재적재 없음(팀 소유권 모델의 "공용부 편집가능" 원칙,
> [[project_team_ownership_model]] 참고).

### 참조
- PRD: F-LLM-2 / TRD: T-LLM-2 / REQ: REQ-BOT-001~005
- 실측 버그(2026-07-27): "인데놀의 효능에 대해서 설명해줘" → RAG 검색이 통째로 생략됨(`sources: []`).
  로그: `쿼리에서 성분명·약 이름을 식별하지 못해 검색을 생략합니다.`
  반면 "프로프라놀롤(인데놀의 성분)의 효능"으로 물으면 정상적으로 DUR 문서 2건이 검색됨.
- 관련: `ai_worker/services/retrieve_service.py`(`_build_filters`), `ai_worker/services/drug_name_resolver.py`,
  `ai_worker/scripts/export_source_from_mysql.py`

### 배경 — 왜 인데놀이 안 걸렸나
RAG는 검색 전 "쿼리에 아는 약 이름이 있는가"부터 확인한다(`_build_filters`). 이 판정에 쓰는 이름 사전이
두 겹으로 좁다:

1. **제품명 인덱스(`drug_names`)**: ChromaDB에 실제로 적재된 문서의 `item_name` 메타데이터에서만
   뽑는다(`cache_searchable_names`). 적재 문서는 e약은요 개요정보(`drugs_data.csv`, MySQL `drugs_data`
   테이블) 기준 — 이건 MySQL 허가목록(`drug_prdt_prmsn_list`, **43,017개**)의 부분집합(**약 12,232개
   제품명**)일 뿐이다. 인데놀은 이 부분집합엔 없다.
2. **브랜드→성분 브릿지(`_item_ingredient_map.csv`)**: `export_source_from_mysql.py`가
   `item_ingredient_map m JOIN drugs_data d ON m.item_seq = d.item_seq`로 만든다 — 여기서도
   `drugs_data`와 조인해 같은 부분집합으로 좁아진다.

**MySQL엔 데이터가 이미 있다** — 확인됨: `drug_prdt_prmsn_list`에 `인데놀정10mg/40mg(프로프라놀롤염산염)`
2건, `item_ingr_name` 컬럼도 99.8%(42,934/43,017) 채워져 있다. 그리고 성분 인덱스는 이미
`프로프라놀롤염산염 → 프로프라놀롤` 정규화를 해주고, DUR 구조화 문서(`ingr_name` 메타데이터)에도
프로프라놀롤 관련 규칙이 이미 적재돼 있다(성분명으로 물으면 실제로 검색됨, 위 실측 참고). **즉 검색
대상 문서나 벡터스토어는 이미 충분하다 — 두 이름 사전(①②)만 e약은요 부분집합에 갇혀 있는 게 문제다.**

CSV 파이프라인(MySQL→CSV→ai_worker 메모리) 자체는 유지한다 — `ai_worker`가 요청 처리 중 MySQL을 직접
안 보는 건 2026-07-10 결정(`docs/decision_log/2026-07-10-ai-rag-worker.md`)에 따른 의도된 경계다.
바꾸는 건 "어느 MySQL 테이블에서 퍼내는가"뿐이다.

### 목표
- 입력: 사용자 질문 속 **브랜드명**(예: "인데놀", "이지앤6") — 성분명이 아니라 실제로 더 자주 쓰이는 형태
- 출력: 그 브랜드가 MySQL 허가목록(43K) 안에 있으면, 성분으로 정규화되어 기존 DUR 검색이 정상 동작
- 범위: 브랜드→성분 매핑과 제품명 인덱스의 **소스만** e약은요 부분집합(`drugs_data`, ~12K) →
  전체 허가목록(`drug_prdt_prmsn_list`, 43K)으로 넓힌다. 새 데이터 소스 도입이나 Chroma 재적재는 없다.

### 완료 정의 (Definition of Done)
- [x] `export_source_from_mysql.py`의 `_item_ingredient_map.csv` 생성 쿼리가 `drugs_data` 대신
      `drug_prdt_prmsn_list`(또는 그와 동등한 전체 허가목록) 기준으로 브랜드→성분 매핑을 만든다
- [x] 제품명 인덱스(`drug_names`, 현재 `cache_searchable_names`가 Chroma 메타데이터에서만 뽑음)가
      "인데놀"처럼 **DUR/e약은요 문서로 적재되지 않은 브랜드**도 인식하도록 소스가 넓어진다
      (전체 허가목록 유래 이름 사전과 병합하거나 대체)
- [x] "인데놀의 효능에 대해서 설명해줘" 질문이 `sources: []`가 아니라 실제 DUR 문서(프로프라놀롤 관련)를
      반환한다 — 수동 확인(실 MySQL export 후 재현) + 회귀 테스트로 고정
- [x] 기존 성분명/제품명 검색(아스피린 등, 이미 되던 것) 무회귀 — 오히려 타이레놀 DUR 경고 누락(아래
      "범위 밖에서 같이 고친 것" 참고)까지 개선됨
- [x] Chroma 재적재 불필요, `docker-compose.yml` 등 리더 소유 파일 미수정
- [x] (공통) 테스트 함수명 영문, ruff/mypy 통과 (CI 게이트: `ruff check` + `ruff format --check` + `mypy`, 334 files 통과)

### 범위 밖에서 같이 고친 것 — 성분 브릿지 검색 문구 정규화
계획 당시엔 몰랐던 2차 문제가 구현 중 실측으로 드러났다: 이름 인식(위 DoD)만 고치면 필터는 정확히
만들어지지만(`인데놀` → `프로프라놀롤` 정규화 확인됨), **최종 검색 결과가 여전히 0건**이었다 —
DUR 문서는 브랜드명을 전혀 안 쓰고 성분명만 쓰는데, 유사도 비교를 원본 질의("인데놀 노인이 먹어도
돼?") 그대로 하면 임베딩 거리가 나빠져(실측 0.42) 임계값(0.35)에 걸려 탈락했다. **같은 문제가
"타이레놀" 등 기존에 "잘 되던" 브랜드에도 이미 있었다** — e약은요 문서(본문에 브랜드명이 있어 통과)가
같이 걸려 화면엔 뭔가 뜨니 아무도 몰랐을 뿐, DUR 노인주의/병용금기 경고는 조용히 빠지고 있었다
(실측: "타이레놀 노인이 먹어도 돼?"의 DUR 문서 점수 0.378~0.385, e약은요 0.31~0.32).

임계값(0.35)을 올리는 방식은 검토 후 기각 — 그 값은 "무관 질문 점수 0.38~0.51"과 뚜렷한 간격을 두려고
정한 방어선이라(2026-07-16 "혈당 관리 운동" 오탐 사고 재발 방지), 숫자를 올리면 그 방어선이 같이
느슨해진다. 대신 `_build_filters`가 (필터, 검색문구) 쌍을 반환하도록 바꿔, **성분 브릿지로 찾은
필터에 한해서만** 검색 문구에 정규화된 성분명을 덧붙였다(임계값·다른 필터의 검색문구는 그대로).
LLM 최종 답변에는 영향 없음 — 검색용 문구 치환일 뿐 사용자 질문 원문은 그대로 LLM에 전달되며, 실측
확인 결과 "인데놀(프로프라놀롤)은..."처럼 두 이름을 자연스럽게 엮어 답했다.

### 허용 경로
```
ai_worker/scripts/export_source_from_mysql.py
ai_worker/services/retrieve_service.py
ai_worker/services/drug_name_resolver.py
ai_worker/tests/**
docs/tasks/T-LLM-2-rag-brand-name-bridge.md  (이 파일)
```

### 금지 경로
```
docker-compose.yml / infra/**        (리더 소유, Chroma 서버화 등 불필요)
app/**                                (MySQL 스키마/테이블 자체는 안 건드림 — 읽기만)
frontend/**
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 자율 판단 허용 범위
- 넓힌 이름 사전을 별도 CSV로 분리할지 기존 `_item_ingredient_map.csv`를 확장할지,
  `drug_names` 인덱스 병합 방식, 브랜드가 여러 성분(복합제)일 때 처리 — 전부 자율 결정.

### 반드시 멈춰야 하는 경우
- 이 작업을 위해 `ai_worker`가 요청 처리 중 MySQL에 실시간 접속해야 한다는 결론이 나면 — 진행하지 말고
  보고. (2026-07-10 결정으로 의도된 경계를 깨는 것이라 별도 논의 필요.)
- 전체 허가목록 43K를 다 CSV로 내보내는 게 크기/시간상 문제가 되면 — 보고 후 범위 조정.

### 완료 보고 (구현 후 작성)
- 완료 정의 체크리스트 결과: 전 항목 충족(위 체크박스). 실 MySQL export → 재적재 없이 인메모리
  재로드 → 인데놀 검색 3건(score 0.30~0.32) → 실제 챗봇 파이프라인(`stream_chat_answer`)까지
  전체 실행해 최종 LLM 답변("인데놀(프로프라놀롤)은...")까지 확인. 아스피린/타이레놀 등 기존
  브랜드 무회귀(타이레놀은 DUR 경고 누락 문제까지 부수적으로 개선). ruff/mypy(334 files)/pytest
  (retrieve_service·chat_agent·export_source_from_mysql·generate_structured·observability, 36건) 통과.
- 가정(Assumptions):
  - `item_ingredient_map.ingr_name`이 염(鹽) 형태일 수 있다는 전제로 `ingr_names` 정규화를 거치게
    했다 — 정규화 실패(그 성분의 DUR 문서가 아예 없음) 시 해당 필터를 조용히 건너뛴다(에러 아님).
  - 브릿지 CSV 규모 8,095건 → 49,624건으로 6배 확대. 메모리/CSV 크기 문제 없음(실측).
- 공유 계약 변경 필요 사항: 없음. `ai_worker/` 내부 파일만 변경, 사용자 대면 응답 스키마 무변경.
- 브랜치명: `feat/T-LLM-2-rag-brand-name-bridge`
