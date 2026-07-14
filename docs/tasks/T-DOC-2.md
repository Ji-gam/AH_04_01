## Task ID: T-DOC-2 (인식 데이터 기반 맞춤 가이드 — 약물·음식 상호작용 안내)

### 참조
- PRD: F-DOC-2 / TRD: T-DOC-2 / REQ: REQ-DOC-009
- 선행 작업: `docs/tasks/T-MED-4.md`(공공데이터포털 API 연동), `docs/decision_log/2026-07-07.md`(Tier 2 stub 전략)

### 배경

`frontend/src/pages/medication/MedicationPage.tsx`의 "음식 (13번)" 탭과 `confirm_recognition_job`의
`guide_cards`가 지금 완전 고정 stub이다("등록하신 약품의 부작용 및 상호작용 정보(DUR)는 추후
연동될 예정입니다"). Tier 2 설계(decision_log)상 RAG 완성 전까지 규칙기반 stub으로 채우기로
되어 있었는데, 실제 데이터 소스를 조사해보니 새 API 연동 없이 채울 수 있다:

- 식약처 DUR API(병용금기/특정연령대금기/임부금기/용량주의/투여기간주의/노인주의/효능군중복주의/
  서방정분할주의)에는 "음식" 전용 카테고리가 없다.
- 이미 연동돼 있는 e약은요(`DrbEasyDrugInfoService`, `medication_open_api_client.fetch_drug_summary`)
  응답에 `intrcQesitm`("이 약을 사용하는 동안 주의해야 할 약 또는 음식은 무엇입니까?") 필드가
  이미 포함되어 있다 — `_normalize_items`가 필드를 거르지 않고 그대로 통과시키므로 응답 안에는
  이미 들어있고, 지금 코드가 이 필드를 안 꺼내 쓰고 있을 뿐이다.

### 목표
- 입력: 확정된 복약 스케줄(등록약)
- 출력/노출: 약물·음식 시너지/부작용 안내 카드(GuideCard, `docs/dev/api_spec_core_v1_v1.1.yaml` 기존 스키마)
- **RAG/ai_worker/ 미사용** — LLM/AI 스쿼드(박지은) 소유 영역은 건드리지 않는다(`docs/SQUAD_MAP.md`).

### 완료 정의 (Definition of Done)
- [ ] `confirm_recognition_job`이 등록된 약의 `intrcQesitm`(e약은요)을 조회해 실제 GuideCard로 반환한다
      (지금처럼 고정 문구 대신)
- [ ] e약은요 API가 실패/빈 응답이어도 등록 자체는 막히지 않고, guide_cards만 비거나 폴백 카드로 채워진다
- [ ] `intrcQesitm`이 빈 문자열/"없음"류 응답이면 "특별한 주의사항 없음" 카드로 처리하고, 빈 배열로
      두지 않는다(사용자가 "확인이 안 됐다"와 "주의사항이 없다"를 구분할 수 있어야 함)
- [ ] 프론트 "음식 (13번)" 탭에서 등록약 기준으로 실제 안내 카드가 노출된다
- [ ] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다
- [ ] (공통) 모든 신규 코드에 대해 Ruff 통과, Mypy 통과

---

### 허용 경로
```
app/services/medication_service.py
app/services/medication_open_api_client.py
app/tests/services/**
app/tests/medication_apis/**
frontend/src/pages/medication/MedicationPage.tsx
frontend/src/hooks/useMedication.ts
docs/tasks/T-DOC-2.md (이 파일)
```

### 금지 경로
```
ai_worker/**
app/services/retriever_stub.py
app/services/llm_stub.py
app/core/**
app/dependencies/**
envs/**
infra/**
scripts/**
docs/tasks/_active.json (등록/해제 외 수정 금지)
```

### 자율 판단 허용 범위
- `intrcQesitm`/`atpnQesitm` 중 어느 필드(또는 둘 다)를 카드에 쓸지, 텍스트를 그대로 노출할지
  간단히 가공(문장 분리 등)할지 — 전부 에이전트 자율 결정. 단, 원문 의미를 왜곡하는 재작성/요약은
  하지 않는다(면책 목적상 원문 그대로가 더 안전).

### 반드시 멈춰야 하는 경우
- 음식 키워드 추출/분류에 LLM 호출이 필요해 보이는 경우 → RAG/ai_worker 영역 침범이므로 범위 밖,
  사용자에게 먼저 확인.

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 위 5개 항목 모두 충족.
  - `_build_food_interaction_guide_card(medication_name)` 신설 — e약은요 `fetch_drug_summary`의
    `intrcQesitm` 필드를 원문 그대로 GuideCard로 변환. 필드가 비어있으면(빈 문자열) "확인된
    음식·음주 관련 주의사항이 없습니다"(severity=info)로 명시하고, API 실패/빈 응답이면 카드
    자체를 생략(None)해 "확인 실패"와 "주의사항 없음"을 구분한다.
  - `confirm_recognition_job`의 고정 stub("추후 연동될 예정입니다")을 실제 조회로 교체.
  - 프론트 "음식 (13번)" 탭에 `guideCards` 렌더링을 이동(기존 "조합(12번)" 탭의 임시 표시 제거),
    등록 확정 전/후 상태를 문구로 구분.
  - 실 서비스키로 로컬 도커 스택에서 확정(confirm) API를 직접 호출해 실제 e약은요 응답
    (`intrcQesitm`)이 GuideCard로 반환되는 것을 확인함(2026-07-14).
- 가정(Assumptions):
  - `intrcQesitm` 원문은 재가공(요약/키워드 추출)하지 않고 그대로 노출한다 — 면책 목적상 식약처
    원문 그대로가 더 안전하다고 판단(자율 판단 허용 범위에 명시된 대로).
  - e약은요 API가 여러 건을 반환해도 첫 번째 결과만 사용한다(기존 `fetch_medication_master_data`와
    동일한 관례).
- 공유 계약 변경 필요 사항: 없음. `GuideCard`/`RecognitionConfirmResult` 스키마는 기존 그대로이고
  (`docs/dev/api_spec_core_v1_v1.1.yaml`), 프론트 타입(`useMedication.ts`)도 이미 `severity: string`
  으로 되어 있어 변경 불필요.
- 부수 발견(범위 밖, 별도 이슈로 분리): `_fetch_medication_from_public_api`가 `httpx.HTTPError`를
  안 잡아서 공공데이터 API 타임아웃 시 OCR 백그라운드 태스크가 죽고 job이 `processing`에 영구
  멈추는 버그를 발견 — GitHub 이슈 #138로 분리 등록함.
- 테스트: `app/tests/services/test_medication_service_food_interaction.py` 신규(4건: 실제 텍스트/
  빈 필드/빈 응답/API 에러). `app/tests/medication_apis/test_medication_apis.py`의 기존 e2e
  테스트도 실제 데이터 기반 검증으로 갱신. `uv run pytest app -q` 226 passed. `uv run ruff check`/
  `format --check`/`mypy app/services/medication_service.py` 전부 통과. 프론트
  `npm run typecheck`/`npm run lint` 통과(기존 경고 4건 외 신규 이슈 없음).
- 브랜치명: `feat/137-doc2-food-drug-interaction`
