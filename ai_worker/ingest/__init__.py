"""매니페스트 기반 인제스천.

`source/`는 드롭 폴더다. 무엇이 RAG 재료인지는 `source/_manifest.yaml`이 선언하고,
파일을 Document로 만드는 건 로더(`loaders.py`)가, 색인은 LangChain의 `index()`가
한다(`pipeline.py`).

  새 파일 추가 = 매니페스트 블록 1개 (파이썬 0줄)
  새 포맷 추가 = BaseLoader 구현 1개 + LOADERS에 한 줄

실행:
    uv run python -m ai_worker.ingest            # 매니페스트의 rag=true 전부 색인
    uv run python -m ai_worker.ingest --scan     # source/ 대조만 (색인 안 함)
    uv run python -m ai_worker.ingest --force    # 내용이 같아도 재임베딩(임베딩 모델 교체 시)
"""
