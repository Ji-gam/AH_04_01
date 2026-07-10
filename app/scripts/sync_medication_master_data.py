"""
Tier 2(MySQL `medications`) 배치 적재 스크립트(T-MED-4). 자주 언급되는 약품 이름 목록을
`fixtures/medication_sync_list.json`에서 읽어, 공공데이터포털 API(낱알식별/허가정보/e약은요/
DUR 품목정보)로 실제 데이터를 조회한 뒤 `medications` 테이블에 채운다. 이미 이름이 정확히
일치하는 레코드가 있으면 건너뛴다(최초 적재 + 재실행 시 중복 방지용 — 필드 갱신은 하지 않음).

`fixtures/medication_sync_list.json`은 예시 목록이다. 실제 "자주/종종 조회되는 약품" 목록
(Tier 1/2 경계 확정 포함)은 팀에서 별도로 채워야 한다 — `docs/tasks/T-MED-4.md` "반드시
멈춰야 하는 경우" 참고.

실행: uv run python -m app.scripts.sync_medication_master_data
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import AsyncSessionLocal
from app.models.medication_model import Medication
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "medication_sync_list.json"


async def sync_medication_master_data(session: AsyncSession, item_names: list[str]) -> dict[str, int]:
    """`item_names` 각각을 공공 API로 조회해 없는 것만 `medications`에 새로 만든다.
    반환값: {"created": 신규 생성 수, "skipped": 이미 있어 건너뛴 수, "not_found": API에도 없던 수}."""
    repo = MedicationRepository()
    created = skipped = not_found = 0

    for name in item_names:
        existing = await repo.search_medication_by_name(session, name)
        if any(m.medication_name == name for m in existing):
            skipped += 1
            continue

        fields = await medication_open_api_client.fetch_medication_master_data(name)
        if fields is None:
            not_found += 1
            continue

        standard_code = fields.pop("standard_code")
        await repo.create_medication(session, Medication(medication_name=name, standard_code=standard_code, **fields))
        created += 1

    return {"created": created, "skipped": skipped, "not_found": not_found}


async def _main() -> None:
    item_names = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as session:
        result = await sync_medication_master_data(session, item_names)
        await session.commit()
        print(f"medications 동기화 완료: {result}")


if __name__ == "__main__":
    asyncio.run(_main())
