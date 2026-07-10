from app.repositories.medication_repository import MedicationRepository
from app.scripts.sync_medication_master_data import sync_medication_master_data
from app.services import medication_open_api_client
from app.tests.conftest import TestSessionLocal


async def test_sync_creates_medications_from_public_api_for_new_names(monkeypatch):
    async def _fake_master_data(item_name: str) -> dict | None:
        return {
            "standard_code": f"PDP_{item_name}",
            "dosage_guideline": "1회 1정",
            "side_effects": None,
            "storage_method": "실온",
            "shape": "원형",
            "color": "하양",
            "letters": None,
        }

    monkeypatch.setattr(medication_open_api_client, "fetch_medication_master_data", _fake_master_data)

    async with TestSessionLocal() as session:
        result = await sync_medication_master_data(session, ["동기화테스트약A", "동기화테스트약B"])

    assert result == {"created": 2, "skipped": 0, "not_found": 0}

    async with TestSessionLocal() as session:
        repo = MedicationRepository()
        meds = await repo.search_medication_by_name(session, "동기화테스트약A")
        assert len(meds) == 1
        assert meds[0].standard_code == "PDP_동기화테스트약A"
        assert meds[0].dosage_guideline == "1회 1정"


async def test_sync_skips_names_that_already_exist(monkeypatch):
    async def _should_not_be_called(item_name: str) -> dict | None:
        raise AssertionError("이미 DB에 있는 약품은 API를 호출하면 안 된다")

    monkeypatch.setattr(medication_open_api_client, "fetch_medication_master_data", _should_not_be_called)

    async with TestSessionLocal() as session:
        from app.models.medication_model import Medication

        repo = MedicationRepository()
        await repo.create_medication(session, Medication(medication_name="이미있는약", standard_code="KD_EXIST1"))

        result = await sync_medication_master_data(session, ["이미있는약"])

    assert result == {"created": 0, "skipped": 1, "not_found": 0}


async def test_sync_counts_not_found_when_api_has_no_data(monkeypatch):
    async def _fake_master_data(item_name: str) -> dict | None:
        return None

    monkeypatch.setattr(medication_open_api_client, "fetch_medication_master_data", _fake_master_data)

    async with TestSessionLocal() as session:
        result = await sync_medication_master_data(session, ["데이터없는약"])

    assert result == {"created": 0, "skipped": 0, "not_found": 1}
