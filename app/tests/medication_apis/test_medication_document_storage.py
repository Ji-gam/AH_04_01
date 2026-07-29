"""REQ-DOC-003: 처방전/약봉투/진료기록 원본 이미지 보관 + 완전 삭제 검증.

[테스트 이미지 정책] 실제 처방전/약봉투 샘플 이미지는 수량이 한정돼 있으므로, 이 파일의
모든 테스트는 Pillow로 그 자리에서 생성한 합성 더미 JPEG(`_dummy_jpeg_bytes`)만 쓴다.
"""

import io
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from PIL import Image, UnidentifiedImageError
from starlette import status

from app.core import config
from app.main import app
from app.services import medication_service
from app.services.medication_service import _execute_ocr_logic
from app.tests.conftest import TestSessionLocal
from app.tests.medication_apis.test_medication_apis import (
    _DUMMY_MODE_SEEDED_DRUGS,
    _seed_dummy_medications,
    _signup_and_login,
)

pytestmark = pytest.mark.asyncio


def _dummy_jpeg_bytes(color: str = "red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _document_storage_env(tmp_path, monkeypatch):
    """이 파일의 모든 테스트는 실제 암호화 저장이 일어나야 검증 가능하므로, 키를 설정하고
    저장 경로를 tmp_path로 돌린다 - 다른 테스트 파일에 영향 주지 않도록 끝나면 원복된다
    (monkeypatch가 자동으로 원복)."""
    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    monkeypatch.setattr(config, "DOCUMENT_STORAGE_ROOT", str(tmp_path))


async def _upload_document(client: AsyncClient, headers: dict, image_bytes: bytes | None = None) -> str:
    files = {"file": ("presc.jpg", io.BytesIO(image_bytes or _dummy_jpeg_bytes()), "image/jpeg")}
    data = {"source_type": "prescription", "dummy_mode": "true"}
    response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
    assert response.status_code == status.HTTP_202_ACCEPTED
    return response.json()["job_id"]


async def _run_ocr_in_test_db(job_id: str, file_bytes: bytes) -> None:
    """(docs/tasks/T-MED-16.md 기존 인프라 이슈) `run_ocr_task`(실제 백그라운드 경로)는
    `AsyncSessionLocal`(운영 DB, .env의 DB_NAME)에 자체 세션을 열지만, 이 테스트의 HTTP
    요청 경로는 `TestSessionLocal`("test" 스키마)로 오버라이드되어 있어 서로 다른 DB를 본다
    - 백그라운드 완료 폴링은 이 프로젝트에서 이미 "수정하지 않음"으로 문서화된 기존 결함이라,
    후보/추출데이터가 필요한 테스트는 같은 TestSessionLocal로 OCR 로직을 직접 실행해
    우회한다."""
    async with TestSessionLocal() as session:
        await _execute_ocr_logic(session, job_id, file_bytes, "presc.jpg", dummy_mode=True)
        await session.commit()


async def test_upload_persists_encrypted_file_and_job_metadata(monkeypatch):
    _seed_dummy_medications(monkeypatch, _DUMMY_MODE_SEEDED_DRUGS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "doc_upload@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        original_bytes = _dummy_jpeg_bytes()

        job_id = await _upload_document(client, headers, original_bytes)

        list_res = await client.get("/api/v1/recognition/jobs", headers=headers)
        assert list_res.status_code == status.HTTP_200_OK
        jobs = list_res.json()
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == job_id
        assert jobs[0]["has_image"] is True
        assert jobs[0]["source_type"] == "prescription"

        # 디스크에 저장된 파일은 암호화되어있어 평문 이미지로 열리지 않아야 한다
        stored_files = list(Path(config.DOCUMENT_STORAGE_ROOT).rglob("*.enc"))
        assert len(stored_files) == 1
        raw_on_disk = stored_files[0].read_bytes()
        assert raw_on_disk != original_bytes
        with pytest.raises(UnidentifiedImageError):
            Image.open(io.BytesIO(raw_on_disk)).verify()


async def test_owner_can_view_and_roundtrip_matches_original(monkeypatch):
    _seed_dummy_medications(monkeypatch, _DUMMY_MODE_SEEDED_DRUGS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "doc_view@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        original_bytes = _dummy_jpeg_bytes()
        job_id = await _upload_document(client, headers, original_bytes)

        image_res = await client.get(f"/api/v1/recognition/jobs/{job_id}/image", headers=headers)
        assert image_res.status_code == status.HTTP_200_OK
        assert image_res.headers["content-type"] == "image/jpeg"
        assert image_res.content == original_bytes


async def test_job_without_image_returns_404_on_view(monkeypatch):
    """FIELD_ENCRYPTION_KEY 미설정 상태에서 업로드하면 이미지는 저장되지 않는다(OCR
    성공 여부와 무관 - 이미지 저장은 create_recognition_job의 동기 경로에서 즉시
    결정되고 OCR 완료를 기다리지 않는다). 문서함에는 "이미지 없음"으로, 조회는 404로
    처리되어야 한다."""
    _seed_dummy_medications(monkeypatch, _DUMMY_MODE_SEEDED_DRUGS)
    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "doc_no_key@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        job_id = await _upload_document(client, headers)

        list_res = await client.get("/api/v1/recognition/jobs", headers=headers)
        jobs = list_res.json()
        assert jobs[0]["has_image"] is False

        image_res = await client.get(f"/api/v1/recognition/jobs/{job_id}/image", headers=headers)
        assert image_res.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_document_purges_file_and_extracted_data_but_keeps_job_and_schedule(monkeypatch):
    _seed_dummy_medications(monkeypatch, _DUMMY_MODE_SEEDED_DRUGS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "doc_delete@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        original_bytes = _dummy_jpeg_bytes()
        job_id = await _upload_document(client, headers, original_bytes)
        await _run_ocr_in_test_db(job_id, original_bytes)

        get_res = await client.get(f"/api/v1/recognition/jobs/{job_id}", headers=headers)
        result_data = get_res.json()
        top_candidate = result_data["candidates"][0]

        confirm_res = await client.post(
            f"/api/v1/recognition/jobs/{job_id}/confirm",
            headers=headers,
            json={"selected_candidate_drug_code": top_candidate["drug_code"]},
        )
        assert confirm_res.status_code == status.HTTP_200_OK

        stored_files_before = list(Path(config.DOCUMENT_STORAGE_ROOT).rglob("*.enc"))
        assert len(stored_files_before) == 1

        delete_res = await client.delete(f"/api/v1/recognition/jobs/{job_id}/document", headers=headers)
        assert delete_res.status_code == status.HTTP_204_NO_CONTENT

        # 파일이 실제로 지워졌는지
        assert list(Path(config.DOCUMENT_STORAGE_ROOT).rglob("*.enc")) == []

        # job 행은 유지되지만 이미지/추출데이터는 비워짐
        get_res = await client.get(f"/api/v1/recognition/jobs/{job_id}", headers=headers)
        assert get_res.status_code == status.HTTP_200_OK
        job_data = get_res.json()
        assert job_data["candidates"] == []
        assert job_data["extracted_fields"] == {}

        image_res = await client.get(f"/api/v1/recognition/jobs/{job_id}/image", headers=headers)
        assert image_res.status_code == status.HTTP_404_NOT_FOUND

        # 확정된 복약 스케줄(source_job_id로 이 job을 참조)은 그대로 남아있어야 한다
        list_res = await client.get("/api/v1/medications", headers=headers)
        assert list_res.status_code == status.HTTP_200_OK
        assert len(list_res.json()) == 1

        # 멱등 삭제: 두 번째 호출도 204
        delete_again_res = await client.delete(f"/api/v1/recognition/jobs/{job_id}/document", headers=headers)
        assert delete_again_res.status_code == status.HTTP_204_NO_CONTENT


async def test_oversized_upload_is_rejected(monkeypatch):
    monkeypatch.setattr(medication_service, "_MAX_DOCUMENT_UPLOAD_BYTES", 100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "doc_oversize@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": ("presc.jpg", io.BytesIO(_dummy_jpeg_bytes()), "image/jpeg")}
        data = {"source_type": "prescription"}
        response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_non_image_bytes_with_spoofed_content_type_is_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "doc_spoofed@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": ("presc.jpg", io.BytesIO(b"not actually an image"), "image/jpeg")}
        data = {"source_type": "prescription"}
        response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


async def _link_guardian_and_member(client: AsyncClient, guardian_headers: dict, member_headers: dict) -> None:
    """(REQ-DOC-003) 초대코드 발급/사용 - 승인 대기 없이 즉시 ACCEPTED 상태가 되는 경로가
    가장 간단해서 테스트에서는 이걸 쓴다. guardian_headers 쪽이 보호자(guardian_profile_id),
    member_headers 쪽이 관리 대상(member_profile_id, 즉 문서 소유자)이 된다."""
    invite_res = await client.post(
        "/api/v1/family/invite-code", headers=guardian_headers, json={"relation_label": "부모"}
    )
    assert invite_res.status_code == status.HTTP_201_CREATED
    code = invite_res.json()["code"]
    redeem_res = await client.post("/api/v1/family/invite-code/redeem", headers=member_headers, json={"code": code})
    assert redeem_res.status_code == status.HTTP_200_OK


async def test_guardian_view_gated_by_opt_in_toggle(monkeypatch):
    _seed_dummy_medications(monkeypatch, _DUMMY_MODE_SEEDED_DRUGS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        guardian_token = await _signup_and_login(client, "guardian@example.com")
        member_token = await _signup_and_login(client, "member@example.com")
        guardian_headers = {"Authorization": f"Bearer {guardian_token}"}
        member_headers = {"Authorization": f"Bearer {member_token}"}

        await _link_guardian_and_member(client, guardian_headers, member_headers)

        job_id = await _upload_document(client, member_headers)

        # 기본값(OFF) 상태 - 보호자가 봐도 404
        settings_res = await client.get(
            "/api/v1/recognition/jobs/settings/guardian-document-access", headers=member_headers
        )
        assert settings_res.status_code == status.HTTP_200_OK
        assert settings_res.json()["allow_guardian_document_access"] is False

        guardian_view_before = await client.get(f"/api/v1/recognition/jobs/{job_id}/image", headers=guardian_headers)
        assert guardian_view_before.status_code == status.HTTP_404_NOT_FOUND

        # 본인이 토글 ON
        toggle_res = await client.patch(
            "/api/v1/recognition/jobs/settings/guardian-document-access",
            headers=member_headers,
            json={"allow_guardian_document_access": True},
        )
        assert toggle_res.status_code == status.HTTP_200_OK
        assert toggle_res.json()["allow_guardian_document_access"] is True

        guardian_view_after = await client.get(f"/api/v1/recognition/jobs/{job_id}/image", headers=guardian_headers)
        assert guardian_view_after.status_code == status.HTTP_200_OK

        # 삭제는 토글 여부와 무관하게 보호자에게 항상 거부되어야 한다
        guardian_delete_res = await client.delete(
            f"/api/v1/recognition/jobs/{job_id}/document", headers=guardian_headers
        )
        assert guardian_delete_res.status_code == status.HTTP_404_NOT_FOUND

        # 본인은 여전히 삭제 가능
        owner_delete_res = await client.delete(f"/api/v1/recognition/jobs/{job_id}/document", headers=member_headers)
        assert owner_delete_res.status_code == status.HTTP_204_NO_CONTENT
