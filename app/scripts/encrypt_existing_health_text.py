"""[1회성 마이그레이션] EncryptedText 적용 이전에 평문으로 저장돼있던 기존 건강정보
텍스트(HealthProfile.special_notes/other_notes, DiagnosisEntry.detail,
FamilyHistoryEntry.detail)를 암호화해서 다시 써넣는다.

사용법 (FIELD_ENCRYPTION_KEY를 .env에 설정한 뒤 딱 한 번만 실행):
    uv run python app/scripts/encrypt_existing_health_text.py

[동작 방식] SQLAlchemy ORM(EncryptedText 타입 적용됨)을 거치지 않고, 원시 SQL(raw SQL)로
직접 읽고 쓴다 - ORM을 거치면 이미 EncryptedText가 활성화된 상태라 "읽을 때 복호화
시도 → 평문이라 실패 → 그대로 반환"이 되는데, 그걸 다시 저장하면 그제서야 암호화되지만
이 흐름이 명시적이지 않아 헷갈리기 쉽다. 대신 이 스크립트는 각 값에 대해 "이미 암호화된
값인지"를 직접 확인(Fernet 복호화 시도)해서, 안 된 것만 골라 암호화해 원시 SQL UPDATE로
써넣는다 - 두 번 실행해도 안전(이미 암호화된 값은 건너뜀).

[주의] 실행 전 반드시 DB 백업을 떠두세요. 되돌릴 수 없는 작업입니다."""

import asyncio

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text

from app.core import config
from app.core.db.databases import AsyncSessionLocal

# (테이블명, 기본키 컬럼명, 암호화 대상 컬럼명)
# [2026-07-29] special_notes/other_notes는 PII/건강정보 분리로 profiles → health_profiles로
# 이관됐다 - 이 스크립트를 다시 돌릴 일이 생기면(예: 새로 유입된 평문 데이터) 옮겨진
# 테이블을 대상으로 해야 한다.
_TARGETS = [
    ("health_profiles", "id", "special_notes"),
    ("health_profiles", "id", "other_notes"),
    ("diagnosis_entries", "id", "detail"),
    ("family_history_entries", "id", "detail"),
]


def _is_already_encrypted(fernet: Fernet, value: str) -> bool:
    try:
        fernet.decrypt(value.encode("utf-8"))
        return True
    except InvalidToken:
        return False


async def _migrate_table(session, fernet: Fernet, table: str, pk_col: str, target_col: str) -> None:
    result = await session.execute(text(f"SELECT {pk_col}, {target_col} FROM {table} WHERE {target_col} IS NOT NULL"))
    rows = result.fetchall()

    migrated = 0
    skipped = 0
    for row in rows:
        pk_value, raw_value = row[0], row[1]
        if not raw_value:
            continue
        if _is_already_encrypted(fernet, raw_value):
            skipped += 1
            continue
        encrypted = fernet.encrypt(raw_value.encode("utf-8")).decode("utf-8")
        await session.execute(
            text(f"UPDATE {table} SET {target_col} = :encrypted WHERE {pk_col} = :pk"),
            {"encrypted": encrypted, "pk": pk_value},
        )
        migrated += 1

    await session.commit()
    print(f"  {table}.{target_col}: 신규 암호화 {migrated}건, 이미 암호화됨(건너뜀) {skipped}건")


async def main() -> None:
    if not config.FIELD_ENCRYPTION_KEY:
        print("FIELD_ENCRYPTION_KEY가 .env에 설정되지 않았습니다. 먼저 설정한 뒤 다시 실행하세요.")
        return

    fernet = Fernet(config.FIELD_ENCRYPTION_KEY.encode("utf-8"))

    print("기존 건강정보 텍스트 암호화 마이그레이션을 시작합니다...")
    async with AsyncSessionLocal() as session:
        for table, pk_col, target_col in _TARGETS:
            await _migrate_table(session, fernet, table, pk_col, target_col)
    print("완료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())
