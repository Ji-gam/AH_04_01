"""매니페스트 -> 로더 -> `index()`. 인제스천의 유일한 진입점.

예전 파이프라인이 손으로 짰던 것들을 전부 LangChain 표준으로 대체한다:

  `_needs_reingest()`  -> SQLRecordManager (문서 **개수** 비교 대신 콘텐츠 해시)
  `_upsert_file_docs()`-> index(cleanup="incremental")
  `_indexed_pmids()`   -> 위와 동일 (논문 전용 중복 구현이었다)
  `id_fields` 복합키    -> index()가 콘텐츠 해시로 키를 만든다 (기계장치 자체가 불필요)

특히 `_needs_reingest()`는 이 파일에 담긴 변경의 핵심 이유다. 그건 적재된 문서 수와
파싱된 문서 수가 같으면 "안 바뀌었다"고 보고 재임베딩을 건너뛰었다 — 즉 **행 수가 그대로면
내용을 아무리 고쳐도 반영되지 않았다**(원래 docstring도 이 한계를 자인하고 있었다).
`index()`는 page_content+metadata 해시로 판단하므로 내용 변경을 정확히 잡고,
cleanup="incremental"은 원천에서 사라진 행까지 컬렉션에서 지운다.
"""

import logging

from langchain_chroma import Chroma
from langchain_classic.indexes import SQLRecordManager
from langchain_core.indexing import index

from ai_worker.ingest.loaders import build_loader
from ai_worker.ingest.manifest import SourceSpec, load_manifest
from ai_worker.tasks.ingest import CHROMA_DIR, get_embeddings

logger = logging.getLogger("ai_worker.ingest.pipeline")

# RecordManager는 "무엇을 언제 어떤 해시로 넣었는지"의 장부다. 벡터(chroma_data/)와 짝이라
# 같이 지워지고 같이 살아야 하므로 같은 디렉터리에 둔다. 하나만 지우면 장부와 실제가
# 어긋나 재색인이 조용히 스킵된다.
RECORD_DB_PATH = CHROMA_DIR / "record_manager.sqlite"


def build_vector_store(collection: str) -> Chroma:
    """컬렉션 이름만 다른 같은 스토어. 예전엔 컬렉션마다 별도 팩토리 함수가 있었다
    (`ingest.build_vector_store`, `ingest_papers.build_paper_vector_store`)."""
    return Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def _record_manager(collection: str) -> SQLRecordManager:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    manager = SQLRecordManager(f"chroma/{collection}", db_url=f"sqlite:///{RECORD_DB_PATH}")
    manager.create_schema()
    return manager


def ingest_source(spec: SourceSpec, force: bool = False) -> dict:
    """소스 하나를 색인한다. 이미 색인된 것 중 내용이 안 바뀐 문서는 재임베딩하지 않고,
    원천에서 사라진 문서는 컬렉션에서 지운다 — 전부 `index()`가 한다.

    `force=True`는 임베딩 모델이 바뀌었을 때처럼 내용이 같아도 다시 임베딩해야 하는 경우다."""
    docs = list(build_loader(spec).lazy_load())
    result = index(
        docs,
        _record_manager(spec.collection),
        build_vector_store(spec.collection),
        # "incremental"이 아니라 "scoped_full"인 이유: incremental은 배치마다 cleanup을
        # 돌리는데, 한 소스의 문서가 여러 배치에 걸치면(기본 batch_size=100) 뒤 배치의
        # cleanup이 앞 배치가 방금 넣은 문서를 지운다. 실측: 112건짜리 파일을 두 번
        # 색인하면 매번 added 12 / deleted 12가 반복돼 멱등하지 않았다. scoped_full은
        # 모든 배치가 끝난 뒤 이번에 본 source_id 범위만 정리하므로 둘 다 만족한다 —
        # 안 바뀌면 전부 skip, 원천에서 사라진 행은 컬렉션에서도 삭제(실측 확인).
        cleanup="scoped_full",
        # 이 키로 "같은 파일에서 온 문서"를 묶어 cleanup 범위를 정한다. 로더가
        # metadata["source"]에 파일명을 넣는다.
        source_id_key="source",
        # 기본값 sha1은 LangChain 자신이 경고를 띄운다(충돌 내성 없음). 해시가 곧 문서
        # 식별자라 충돌하면 서로 다른 문서가 하나로 뭉쳐 조용히 사라진다.
        key_encoder="blake2b",
        force_update=force,
    )
    logger.info(f"{spec.file} -> {spec.collection}: {result}")
    return {"file": spec.file, "collection": spec.collection, **dict(result)}


def ingest_all(force: bool = False) -> list[dict]:
    """매니페스트의 rag=true 소스를 전부 색인한다. 파일이 없으면 건너뛰되 로그를 남긴다 —
    원천 데이터는 각자 로컬에 받아두는 것이라(대용량 CSV는 git에 없다) 없는 게 정상일 수 있다."""
    results = []
    for spec in load_manifest():
        if not spec.rag:
            continue
        if not spec.path.exists():
            logger.warning(f"매니페스트에 있으나 source/에 없음, 건너뜀: {spec.file}")
            continue
        results.append(ingest_source(spec, force=force))
    return results
