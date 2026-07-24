"""드롭 폴더 -> 로더 -> LangChain `index()`. 인제스천의 유일한 진입점.

**색인은 사건이지 감시 루프가 아니다.** 사람이 시킬 때만 돈다. 서비스가 켜질 때 자동으로
돌지 않는다 — 예전엔 부팅마다 전체 동기화가 돌면서 삭제 판정까지 했다. 파일이 하나
안 보이면 그 문서들이 부팅과 동시에 사라졌고, 예외는 로그로만 삼켜졌다.

`index()` + `SQLRecordManager`는 LangChain 표준이고 그대로 쓴다. 콘텐츠 해시로 안 바뀐
문서를 걸러 재임베딩을 막아준다 — 우리가 원하는 것이다. 비표준이었던 건 이 도구가 아니라
**이걸 부팅마다 고정 폴더에 대고 돌린 것**이다.
"""

import logging
from collections import defaultdict
from typing import Literal

from langchain_chroma import Chroma
from langchain_classic.indexes import SQLRecordManager
from langchain_core.documents import Document
from langchain_core.indexing import index

from ai_worker.ingest.embeddings import CHROMA_DIR, active_embedding_model, get_embeddings
from ai_worker.ingest.loaders import LOADERS, build_loader
from ai_worker.ingest.sources import Source, discover

logger = logging.getLogger("ai_worker.ingest.pipeline")

# RecordManager는 "무엇을 언제 어떤 해시로 넣었는지"의 장부다. 벡터(chroma_data/)와 짝이라
# 같이 지워지고 같이 살아야 하므로 같은 디렉터리에 둔다. 하나만 지우면 장부와 실제가
# 어긋나 재색인이 조용히 스킵된다.
RECORD_DB_PATH = CHROMA_DIR / "record_manager.sqlite"


class IngestError(Exception):
    """소스 하나의 색인이 실패했을 때. 조용히 넘어가면 "처리했다"고 보고하면서 컬렉션은
    비어 있는 상태가 되므로(이 파이프라인이 없애려던 바로 그 문제) 예외로 드러낸다."""


def build_vector_store(collection: str) -> Chroma:
    """컬렉션 메타데이터에 임베딩 모델명을 남겨, 나중에 프로바이더가 바뀌면
    `assert_embedding_compatible`이 불일치를 잡아낸다(벡터공간이 달라 검색이 무의미해짐)."""
    return Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"embedding_model": active_embedding_model()},
    )


def _record_manager(collection: str) -> SQLRecordManager:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    manager = SQLRecordManager(f"chroma/{collection}", db_url=f"sqlite:///{RECORD_DB_PATH}")
    manager.create_schema()
    return manager


def _loadable(source: Source) -> bool:
    return source.path.suffix.lower() in LOADERS


def scan() -> dict[str, list[str]]:
    """색인하면 뭐가 들어갈지 미리 본다(색인은 안 함).

    예전의 `unregistered`(있는데 선언 안 됨)/`missing`(선언됐는데 없음)/`excluded`가 전부
    사라졌다 — 그건 폴더와 별개로 "선언"이 존재해서 생기던 어긋남이었다. 폴더가 곧 진실이면
    어긋날 대상이 없다. 남는 건 "이 확장자는 읽을 줄 모른다" 하나뿐이다."""
    sources = discover()
    return {
        "indexed": sorted(s.name for s in sources if _loadable(s)),
        "unsupported": sorted(s.name for s in sources if not _loadable(s)),
    }


def _load_docs(source: Source) -> list[Document]:
    docs = list(build_loader(source).lazy_load())
    if not docs:
        # 0건은 성공이 아니라 고장이다. 드롭 폴더에 있는 파일은 문서를 내야 한다 — 안 그러면
        # "처리했다"고 보고하면서 컬렉션엔 아무것도 안 들어간다(실측: 스캔본 PDF에 한국어를
        # 못 읽는 OCR 엔진이 붙어 44페이지가 통째로 0건이 됐는데 조용히 넘어갔다).
        raise IngestError(f"{source.name}: 로더가 문서를 하나도 만들지 못했습니다.")
    return docs


def _index(collection: str, docs: list[Document], cleanup: Literal["scoped_full", "full"], force: bool) -> dict:
    result = index(
        docs,
        _record_manager(collection),
        build_vector_store(collection),
        cleanup=cleanup,
        # 이 키로 "같은 파일에서 온 문서"를 묶는다. 로더가 metadata["source"]에 파일명을 넣는다.
        source_id_key="source",
        # 기본값 sha1은 LangChain 자신이 경고를 띄운다(충돌 내성 없음). 해시가 곧 문서
        # 식별자라 충돌하면 서로 다른 문서가 하나로 뭉쳐 조용히 사라진다.
        key_encoder="blake2b",
        force_update=force,
    )
    return dict(result)


def reset_collection(collection: str) -> None:
    """컬렉션과 그 장부를 **함께** 비운다(제로 그라운드 재색인 준비).

    둘 중 하나만 지우면 안 된다: 벡터만 지우면 장부는 "이미 넣었다"고 기억해 재색인이
    조용히 스킵되고, 장부만 지우면 유령 벡터가 남아 중복된다."""
    manager = _record_manager(collection)
    keys = manager.list_keys()
    if keys:
        manager.delete_keys(keys)
    build_vector_store(collection).delete_collection()
    logger.info(f"{collection}: 컬렉션과 장부({len(keys)}건) 삭제 완료.")


def ingest_source(source: Source, force: bool = False) -> dict:
    """**파일 하나만** 색인한다(관리자 업로드용). 그 파일 범위 안에서만 정리한다.

    `cleanup="scoped_full"`인 이유: "incremental"은 배치마다 cleanup을 도는데, 한 소스의
    문서가 여러 배치에 걸치면(기본 batch_size=100) 뒤 배치의 cleanup이 앞 배치가 방금 넣은
    문서를 지운다. 실측: 112건짜리 파일을 두 번 색인하면 매번 added 12 / deleted 12가
    반복돼 멱등하지 않았다. scoped_full은 모든 배치가 끝난 뒤 이번에 본 범위만 정리한다."""
    result = _index(source.collection, _load_docs(source), "scoped_full", force)
    logger.info(f"{source.name} -> {source.collection}: {result}")
    return {"file": source.name, "collection": source.collection, **result}


def ingest_all(force: bool = False) -> list[dict]:
    """드롭 폴더 전체를 컬렉션에 동기화한다. **폴더가 곧 진실이다.**

    파일을 폴더에서 빼고 이걸 돌리면 그 문서들도 사라진다 — 그게 맞다. 사람이 명령을 친
    그 시점의 폴더 상태가 곧 의도다. 아무도 안 불렀는데 알아서 지우는 일은 없다(이 함수를
    부팅에 걸지 않는 이유).

    컬렉션 단위로 묶어 `cleanup="full"`로 한 번에 넣는다. `ingest_source()`를 파일마다
    반복 호출하면 **폴더에서 사라진 파일의 문서가 영원히 남는다** — scoped_full은 "이번에
    본 소스"만 정리 범위로 잡는데, 사라진 파일은 애초에 처리를 안 하니 범위에도 안 든다."""
    by_collection: dict[str, list[Source]] = defaultdict(list)
    for source in discover():
        if not _loadable(source):
            # 읽을 줄 모르는 확장자는 건너뛴다. 여기서 예외를 내면 엉뚱한 파일 하나가
            # 컬렉션 전체 동기화를 막는다 — `--scan`의 "unsupported"가 이걸 알려준다.
            logger.warning(f"{source.name}: 읽을 줄 모르는 확장자라 건너뜁니다.")
            continue
        by_collection[source.collection].append(source)

    results: list[dict] = []
    for collection, sources in by_collection.items():
        docs: list[Document] = []
        loaded: dict[str, int] = {}
        errors: list[str] = []

        for source in sources:
            try:
                source_docs = _load_docs(source)
            except Exception as e:
                logger.error(f"{source.name} 로드 실패: {e}")
                errors.append(f"{source.name}: {e}")
                continue
            docs.extend(source_docs)
            loaded[source.name] = len(source_docs)

        if errors or not docs:
            # 하나라도 실패하면 이 컬렉션은 건드리지 않는다. cleanup="full"은 이번 배치에
            # 없는 문서를 전부 지우므로, 못 읽은 파일의 멀쩡한 문서를 "원천에서 사라졌다"고
            # 오해해 날려버린다. 로더가 잠깐 깨진 것과 사람이 파일을 뺀 것은 다른 사건이다.
            logger.error(f"{collection}: 실패한 소스가 있어 동기화를 건너뜁니다(기존 문서 보존).")
            results.append({"collection": collection, "files": loaded, "errors": errors or ["문서 0건"]})
            continue

        result = _index(collection, docs, "full", force)
        logger.info(f"{collection}: {result} (파일 {len(loaded)}개)")
        results.append({"collection": collection, "files": loaded, **result, "errors": []})
    return results
