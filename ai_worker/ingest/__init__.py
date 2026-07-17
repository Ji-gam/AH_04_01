"""매니페스트 없는 인제스천.

`source/`는 드롭 폴더다. **파일을 넣으면 색인된다.** 등록 절차는 없다.
RAG 재료가 아닌 것(SQL 조회용 표 등)은 `source/_not_rag/`에 둔다.

    새 파일 추가  =  폴더에 넣기            (파이썬 0줄, YAML 0줄)
    새 포맷 추가  =  BaseLoader 구현 하나 + LOADERS에 한 줄

`_tuning.yaml`은 선택적이다. 없어도 돈다. 기계가 알 수 없는 것만 적는다 — 어떤 컬럼이
본문에 안 어울리는지, 어떤 컬럼을 무슨 이름의 메타데이터로 챙길지.

실행:
    uv run python -m ai_worker.ingest            # 드롭 폴더 전체 색인
    uv run python -m ai_worker.ingest --scan     # 뭐가 잡히는지만 보기(색인 안 함)
    uv run python -m ai_worker.ingest --force    # 내용이 같아도 재임베딩(청킹/모델을 바꿨을 때)
"""
