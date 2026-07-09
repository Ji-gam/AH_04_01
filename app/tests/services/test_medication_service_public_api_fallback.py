from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client, medication_service
from app.tests.conftest import TestSessionLocal


async def test_unmatched_drug_uses_public_api_data_when_available(monkeypatch):
    """Tier 2(로컬 DB)에 없는 약이어도 Tier 3(공공 API)에서 데이터를 찾으면
    AUTO_ 더미가 아니라 실제 데이터로 채워진 레코드를 생성해야 한다."""

    async def _fake_pill(item_name=None, **kwargs):
        return [{"ITEM_SEQ": "200000001", "DRUG_SHAPE": "원형", "COLOR_CLASS1": "하양", "PRINT_FRONT": "ABC"}]

    async def _fake_approval(item_name=None, **kwargs):
        return [{"ITEM_SEQ": "200000001", "UD_DOC_DATA": "1회 1정", "NB_DOC_DATA": "주의사항 텍스트"}]

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _fake_pill)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _fake_approval)

    async with TestSessionLocal() as session:
        repo = MedicationRepository()
        matched, auto_created_ids = await medication_service._match_or_create_medications(
            session, repo, ["*낫모르는약100mg"]
        )

    assert len(matched) == 1
    med = matched[0]
    assert med.id not in auto_created_ids
    assert med.standard_code == "PDP_200000001"
    assert med.shape == "원형"
    assert med.color == "하양"
    assert med.letters == "ABC"
    assert med.dosage_guideline == "1회 1정"
    assert med.side_effects == "주의사항 텍스트"


async def test_unmatched_drug_falls_back_to_auto_dummy_when_public_api_has_no_data(monkeypatch):
    """Tier 3 API도 데이터를 못 찾으면 기존 AUTO_ 더미 생성 폴백이 그대로 동작해야 한다."""

    async def _empty(item_name=None, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _empty)

    async with TestSessionLocal() as session:
        repo = MedicationRepository()
        matched, auto_created_ids = await medication_service._match_or_create_medications(
            session, repo, ["*아무데이터도없는약999mg"]
        )

    assert len(matched) == 1
    med = matched[0]
    assert med.id in auto_created_ids
    assert med.standard_code.startswith("AUTO_")


async def test_unmatched_drug_falls_back_to_auto_dummy_when_public_api_errors(monkeypatch):
    """Tier 3 API 호출이 실패(PublicDataApiError)해도 등록 자체는 막히지 않아야 한다."""

    async def _raise(item_name=None, **kwargs):
        raise medication_open_api_client.PublicDataApiError("boom")

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _raise)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _raise)

    async with TestSessionLocal() as session:
        repo = MedicationRepository()
        matched, auto_created_ids = await medication_service._match_or_create_medications(
            session, repo, ["*API장애약500mg"]
        )

    assert len(matched) == 1
    med = matched[0]
    assert med.id in auto_created_ids
    assert med.standard_code.startswith("AUTO_")
