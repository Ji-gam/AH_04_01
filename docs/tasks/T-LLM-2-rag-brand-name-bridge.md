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
- [ ] `export_source_from_mysql.py`의 `_item_ingredient_map.csv` 생성 쿼리가 `drugs_data` 대신
      `drug_prdt_prmsn_list`(또는 그와 동등한 전체 허가목록) 기준으로 브랜드→성분 매핑을 만든다
- [ ] 제품명 인덱스(`drug_names`, 현재 `cache_searchable_names`가 Chroma 메타데이터에서만 뽑음)가
      "인데놀"처럼 **DUR/e약은요 문서로 적재되지 않은 브랜드**도 인식하도록 소스가 넓어진다
      (전체 허가목록 유래 이름 사전과 병합하거나 대체)
- [ ] "인데놀의 효능에 대해서 설명해줘" 질문이 `sources: []`가 아니라 실제 DUR 문서(프로프라놀롤 관련)를
      반환한다 — 수동 확인 + 회귀 테스트로 고정
- [ ] 기존 성분명/제품명 검색(아스피린 등, 이미 되던 것) 무회귀
- [ ] Chroma 재적재 불필요, `docker-compose.yml` 등 리더 소유 파일 미수정
- [ ] (공통) 테스트 함수명 영문, ruff/mypy 통과 (CI 게이트: `ruff check` + `ruff format --check` + `mypy`)

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
- 완료 정의 체크리스트 결과:
- 가정(Assumptions):
- 공유 계약 변경 필요 사항 (있다면):
- 브랜치명: `feat/T-LLM-2-rag-brand-name-bridge`
