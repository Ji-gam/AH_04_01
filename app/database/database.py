import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

DB_DIR = os.path.dirname(__file__)
DRUGS_FULL_DB_PATH = os.path.join(DB_DIR, "drugs_full.db")
DRUGS_LIGHT_DB_PATH = os.path.join(DB_DIR, "drug_light.db")


def get_dur_db_path() -> str:
    """drugs_full.db를 우선 찾고, 없으면 drug_light.db를 반환합니다."""
    if os.path.exists(DRUGS_FULL_DB_PATH):
        return DRUGS_FULL_DB_PATH
    return DRUGS_LIGHT_DB_PATH


@contextmanager
def dur_db_connection() -> Iterator[sqlite3.Connection]:
    """DUR 정보 조회를 위한 SQLite DB 연결 컨텍스트 매니저."""
    db_path = get_dur_db_path()
    conn = sqlite3.connect(db_path)
    # Return rows as dict-like objects for easier access by column name
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
