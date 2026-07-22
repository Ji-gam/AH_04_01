"""새 MySQL 환경(신규 EC2 인스턴스, 초기화된 DB 볼륨 등)에서 DUR 참조 데이터를 처음부터
채워야 할 때 쓰는 1회성 오프라인 부트스트랩 스크립트.

`app/scripts/seed_dur.py`는 (T-MED-15, `docs/decision_log/2026-07-17-dur-mysql-migration.md`)
"원본 데이터가 이미 운영 MySQL(ai_health)에 있다"고 가정하고 MySQL -> MySQL(주로 테스트 DB)만
복사한다. 그 가정이 성립하려면 애초에 누군가 한 번은 `app/database/drugs_full.db`(SQLite,
`scripts/drug_info_sync/` 파이프라인 산출물)를 MySQL에 넣어야 하는데, 그 SQLite -> MySQL 경로
자체가 T-MED-15 때 함께 제거되어 신규 환경에는 부트스트랩 수단이 없었다. 이 스크립트가 그 빠진
최초 적재 경로를 대체한다.

`app/scripts/build_food_drug_interaction_db.py`와 같은 성격의 "빌드/부트스트랩 오프라인 도구"이며,
sqlite3 사용은 여기 한정된다 — 요청 처리 경로(`app/repositories/dur_repository.py` 등)는 여전히
MySQL만 조회한다.

`seed_dur.py`의 `_TABLE_SPECS`(sqlite 원본 컬럼명 -> 모델 속성명 매핑, 문서화 목적으로 이미 sqlite
컬럼명을 키로 남겨두고 있음)를 그대로 재사용한다.

실행: uv run python -m app.scripts.bootstrap_dur_from_sqlite [drugs_full.db 경로]
"""

import asyncio
import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import delete, insert

from app.core.db.databases import AsyncSessionLocal
from app.scripts.seed_dur import _TABLE_SPECS, CHUNK_SIZE

DEFAULT_SQLITE_PATH = Path(__file__).parent.parent / "database" / "drugs_full.db"


def _iter_sqlite_chunks(conn: sqlite3.Connection, table: str, columns: list[str], chunk_size: int) -> Iterator[list]:
    cursor = conn.cursor()
    quoted = ", ".join(f'"{c}"' for c in columns)
    cursor.execute(f'SELECT {quoted} FROM "{table}"')
    while True:
        rows = cursor.fetchmany(chunk_size)
        if not rows:
            break
        yield rows


async def bootstrap_dur_from_sqlite(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> dict[str, int]:
    """운영 MySQL(`ai_health`)의 DUR 테이블을 `sqlite_path`(drugs_full.db) 내용으로 전체
    삭제 후 재적재한다."""
    if not sqlite_path.exists():
        raise FileNotFoundError(
            f"{sqlite_path}가 없습니다 — scripts/drug_info_sync/orchestrate_pipeline.py로 만들거나 "
            "백업(database.zip)에서 복원하세요."
        )

    conn = sqlite3.connect(sqlite_path)
    counts: dict[str, int] = {}
    try:
        async with AsyncSessionLocal() as session:
            for _table, model, _cols in reversed(_TABLE_SPECS):
                await session.execute(delete(model))
            await session.commit()

            for table, model, col_map in _TABLE_SPECS:
                sqlite_cols = list(col_map.keys())
                total = 0
                for rows in _iter_sqlite_chunks(conn, table, sqlite_cols, CHUNK_SIZE):
                    payload = [
                        {
                            col_map[col]: (value if value != "" else None)
                            for col, value in zip(sqlite_cols, row, strict=True)
                        }
                        for row in rows
                    ]
                    await session.execute(insert(model), payload)
                    total += len(payload)
                await session.commit()
                counts[table] = total
                print(f"{table}: {total:,}건 시딩 완료")
    finally:
        conn.close()

    return counts


async def _main() -> None:
    sqlite_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SQLITE_PATH
    counts = await bootstrap_dur_from_sqlite(sqlite_path)
    total = sum(counts.values())
    print(f"\nDUR 데이터 MySQL 부트스트랩 완료: 총 {total:,}건 ({len(counts)}개 테이블)")


if __name__ == "__main__":
    asyncio.run(_main())
