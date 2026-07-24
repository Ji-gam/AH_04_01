## Task ID: T-LLM-2-rag-source-label (T-LLM-2 "AI 챗봇 상담" 하위 작업 — RAG 출처 표기 한글화)

### 참조
- PRD: F-LLM-2 / TRD: T-LLM-2 / REQ: REQ-BOT-001~005
- Issue: #77
- `chat_service.py`가 RAG 검색 청크(`chunk["metadata"]["source"]`)를 모아 `[출처: ...]`로
  답변 끝에 붙이는데, `ai_worker/tasks/ingest.py`가 원본 CSV 파일명(`dur_pwnm_taboo.csv` 등)을
  그대로 메타데이터에 넣어 사용자에게 raw 파일명이 노출되는 문제. 신규 최상위 TRD 요구사항이
  아니다.

### 목표
- 입력: `ai_worker/mock_data_for_rag/*.csv` 파일명
- 출력: Chroma 문서 메타데이터 `source` 필드에 사람이 읽기 좋은 한글 라벨이 들어감
- `chat_service.py`는 수정하지 않는다 — 이미 메타데이터 `source`를 그대로 노출할 뿐이므로,
  근본 원인인 ingest 단계에서 고친다.

### 완료 정의 (Definition of Done)
- [x] `ai_worker/tasks/ingest.py`에 파일명 → 한글 라벨 매핑 함수가 있고, `_load_docs_from_csv`가
      raw 파일명 대신 이 라벨을 `metadata["source"]`에 사용한다
- [x] 알려진 4개 파일(`dur_pwnm_taboo.csv`/`dur_odsn_atent.csv`/`dur_mdctn_pd_atent.csv`/
      `dur_efcy_dplct.csv`) 전부 라벨이 매핑되고, 알 수 없는 파일명은 raw 파일명으로 폴백한다
      (매핑 누락 시 조용히 사라지지 않도록)
- [x] (공통) 테스트 함수명 영문, TDD 우선, `uv run pytest ai_worker/tests -q` 통과

### 허용 경로
```
ai_worker/tasks/ingest.py
ai_worker/tests/test_ingest.py  (신규)
docs/tasks/T-LLM-2-rag-source-label.md  (이 파일의 "완료 보고" 섹션만)
docs/tasks/_active.json  (등록만)
```

### 알려진 한계 / 후속 작업 (이번 스코프 밖)
- 이미 `ai_worker/chroma_data`에 적재된 기존 문서의 `source` 메타데이터는 이 수정만으로는
  바뀌지 않는다 — 재적재(chroma_data 삭제 후 `ingest_csv_data()` 재실행)가 필요하며, 별도로
  진행 예정(사용자 확인, 2026-07-11). 임베딩 API 비용 발생 가능성 있음(OPENAI_API_KEY 설정 시).

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과: 전항목 충족. `ai_worker/tests` 전체 21개 통과, ruff check/format 통과, mypy 통과.
- 가정(Assumptions):
  - 라벨 문구(예: "식약처 DUR 임부금기 정보")는 CSV 헤더/`_build_page_content`의 기존 분류 관례를
    참고해 임의로 정한 것 — 팀 컨벤션이 따로 있다면 교체 가능.
  - `chat_service.py`는 수정하지 않음(사용자 확인) — 이미 메타데이터를 그대로 노출할 뿐이라 근본
    원인이 아니었음.
  - 기존 `ai_worker/chroma_data`에 이미 적재된 문서의 `source`는 이번 수정으로 바뀌지 않는다.
    재적재는 사용자가 별도로 진행하기로 확인함(임베딩 API 비용 발생 가능성 있어 이번 스코프에서
    자동으로 수행하지 않음).
- 공유 계약 변경 필요 사항 (있다면): 없음.
- 브랜치명: `feat/77-rag-source-label`
