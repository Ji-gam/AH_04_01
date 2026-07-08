import asyncio
import io

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.models.medication_model import Medication
from app.repositories.medication_repository import MedicationRepository
from app.tests.conftest import TestSessionLocal


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    phone_number = "010" + str(abs(hash(email)))[:8]
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "복약테스터",
        "gender": "FEMALE",
        "birth_date": "1995-05-05",
        "phone_number": phone_number,
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def _seed_dummy_medications():
    async with TestSessionLocal() as session:
        repo = MedicationRepository()
        # 이미 존재할 수 있으므로 없는 경우에만 추가
        med1 = await repo.get_medication_by_code(session, "KD_T3001")
        if not med1:
            await repo.create_medication(
                session,
                Medication(
                    standard_code="KD_T3001",
                    medication_name="타이레놀정 500mg",
                    form_type="TABLET",
                    dosage_guideline="1회 1~2정 복용",
                    side_effects="구토, 설사 등",
                    precautions="음주 피할 것",
                    storage_method="실온 보관",
                    shape="원형",
                    color="하양",
                    letters="TYLENOL",
                ),
            )
        med2 = await repo.get_medication_by_code(session, "KD_A4002")
        if not med2:
            await repo.create_medication(
                session,
                Medication(
                    standard_code="KD_A4002",
                    medication_name="아스피린정 100mg",
                    form_type="TABLET",
                    dosage_guideline="1회 1정 복용",
                    side_effects="위장관 출혈 등",
                    precautions="수술 전 복용 중단",
                    storage_method="실온 보관",
                    shape="원형",
                    color="하양",
                    letters="ASPIRIN",
                ),
            )


async def test_recognition_job_creation_and_completion():
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ocr_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. 업로드 & 비동기 Job 생성 요청
        file_content = b"fake pill photo bytes"
        files = {"file": ("pill.jpg", io.BytesIO(file_content), "image/jpeg")}
        data = {"source_type": "pill_photo"}

        response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
        assert response.status_code == status.HTTP_202_ACCEPTED

        job_id = response.json()["job_id"]
        assert job_id is not None
        assert response.json()["status"] == "pending"

        # 백그라운드 태스크가 돌아갈 시간 제공
        await asyncio.sleep(1.0)

        # 2. 결과 조회
        get_response = await client.get(f"/api/v1/recognition/jobs/{job_id}", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        result_data = get_response.json()
        assert result_data["status"] == "done"
        assert len(result_data["candidates"]) > 0

        # 첫 번째 후보 확인
        top_candidate = result_data["candidates"][0]
        assert "타이레놀정 500mg" in top_candidate["drug_name"]

        # 3. 사용자 확정 -> 복약 스케줄 등록
        confirm_data = {
            "selected_candidate_drug_code": top_candidate["drug_code"],
            "confirmed_fields": {"times": ["08:00", "12:00", "20:00"]},
        }
        confirm_response = await client.post(
            f"/api/v1/recognition/jobs/{job_id}/confirm", headers=headers, json=confirm_data
        )
        assert confirm_response.status_code == status.HTTP_200_OK
        assert confirm_response.json()["status"] == "confirmed"
        assert len(confirm_response.json()["guide_cards"]) > 0

        # 4. 복약 스케줄 목록 조회 검증
        list_response = await client.get("/api/v1/medications", headers=headers)
        assert list_response.status_code == status.HTTP_200_OK
        schedules = list_response.json()
        assert len(schedules) == 1
        assert schedules[0]["drug_name"] == top_candidate["drug_name"]
        assert schedules[0]["times"] == ["08:00", "12:00", "20:00"]


async def test_recognition_job_dummy_mode_returns_deterministic_candidates_and_is_marked():
    """OCR이 실패하든 성공하든과 무관하게, QA가 dummy_mode=true로 명시 요청하면
    결정적인 더미 후보를 즉시 받고, extracted_fields로 더미임을 구분할 수 있어야 한다."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "dummy_mode_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("pill.jpg", io.BytesIO(b"fake pill photo bytes"), "image/jpeg")}
        data = {"source_type": "pill_photo", "dummy_mode": "true"}

        response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
        assert response.status_code == status.HTTP_202_ACCEPTED
        job_id = response.json()["job_id"]

        await asyncio.sleep(1.0)

        get_response = await client.get(f"/api/v1/recognition/jobs/{job_id}", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        result_data = get_response.json()
        assert result_data["status"] == "done"
        assert result_data["extracted_fields"]["dummy_mode"] is True
        drug_names = [c["drug_name"] for c in result_data["candidates"]]
        assert any("타이레놀정 500mg" in name for name in drug_names)
        assert any("아스피린정 100mg" in name for name in drug_names)

        # 더미 후보도 기존 confirm 플로우를 그대로 통과해 스케줄 등록까지 이어져야 한다
        top_candidate = result_data["candidates"][0]
        confirm_response = await client.post(
            f"/api/v1/recognition/jobs/{job_id}/confirm",
            headers=headers,
            json={"selected_candidate_drug_code": top_candidate["drug_code"]},
        )
        assert confirm_response.status_code == status.HTTP_200_OK
        assert confirm_response.json()["status"] == "confirmed"


async def test_recognition_job_real_ocr_failure_falls_back_to_dummy_mode_marker():
    """dummy_mode를 요청하지 않아도, 실제 OCR 호출이 안 되는/실패하는 환경(CLOVA 키 미설정 등)에서는
    자동으로 더미 폴백이 걸리고 그 사실이 extracted_fields에 표시되어야 한다."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ocr_failure_fallback@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("pill.jpg", io.BytesIO(b"fake pill photo bytes"), "image/jpeg")}
        data = {"source_type": "pill_photo"}

        response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
        job_id = response.json()["job_id"]

        await asyncio.sleep(1.0)

        get_response = await client.get(f"/api/v1/recognition/jobs/{job_id}", headers=headers)
        result_data = get_response.json()
        assert result_data["status"] == "done"
        # 테스트 환경에는 CLOVA_OCR_SECRET_KEY가 설정되어 있지 않으므로 자동 폴백이 걸려야 한다
        assert result_data["extracted_fields"]["dummy_mode"] is True


async def test_manual_schedule_registration_and_search():
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "manual_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. 약물 검색 자동완성 기능 검증
        search_res = await client.get("/api/v1/medications/search?query=아스피린", headers=headers)
        assert search_res.status_code == status.HTTP_200_OK
        search_data = search_res.json()
        assert len(search_data) >= 1
        assert "아스피린" in search_data[0]["medication_name"]

        # 2. 수동 복약 등록
        manual_req = {"drug_code": "KD_A4002", "times": ["09:00", "21:00"]}
        create_res = await client.post("/api/v1/medications", headers=headers, json=manual_req)
        assert create_res.status_code == status.HTTP_201_CREATED
        assert create_res.json()["drug_name"] == "아스피린정 100mg"
        assert create_res.json()["times"] == ["09:00", "21:00"]


async def test_delete_schedule_removes_it_from_list():
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "delete_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # 잘못 등록된 스케줄을 만들고
        manual_req = {"drug_code": "KD_A4002", "times": ["09:00"]}
        create_res = await client.post("/api/v1/medications", headers=headers, json=manual_req)
        schedule_id = create_res.json()["id"]

        # 삭제하면
        delete_res = await client.delete(f"/api/v1/medications/{schedule_id}", headers=headers)
        assert delete_res.status_code == status.HTTP_204_NO_CONTENT

        # 목록에서 사라져야 한다
        list_res = await client.get("/api/v1/medications", headers=headers)
        assert all(s["id"] != schedule_id for s in list_res.json())


async def test_delete_schedule_of_another_profile_is_forbidden():
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token1 = await _signup_and_login(client, "owner@example.com")
        token2 = await _signup_and_login(client, "intruder@example.com")

        headers1 = {"Authorization": f"Bearer {token1}"}
        manual_req = {"drug_code": "KD_A4002", "times": ["09:00"]}
        create_res = await client.post("/api/v1/medications", headers=headers1, json=manual_req)
        schedule_id = create_res.json()["id"]

        headers2 = {"Authorization": f"Bearer {token2}"}
        delete_res = await client.delete(f"/api/v1/medications/{schedule_id}", headers=headers2)
        assert delete_res.status_code == status.HTTP_404_NOT_FOUND


async def test_cross_profile_job_access_is_forbidden():
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token1 = await _signup_and_login(client, "user1@example.com")
        token2 = await _signup_and_login(client, "user2@example.com")

        # user1로 Job 생성
        files = {"file": ("pill.jpg", io.BytesIO(b"pill"), "image/jpeg")}
        data = {"source_type": "pill_photo"}
        headers1 = {"Authorization": f"Bearer {token1}"}
        res = await client.post("/api/v1/recognition/jobs", headers=headers1, files=files, data=data)
        job_id = res.json()["job_id"]

        # user2로 타인 Job 조회 -> 404 발생해야 함
        headers2 = {"Authorization": f"Bearer {token2}"}
        get_res = await client.get(f"/api/v1/recognition/jobs/{job_id}", headers=headers2)
        assert get_res.status_code == status.HTTP_404_NOT_FOUND
