import asyncio
import io

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.models.medication_model import Medication
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client
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


async def test_recognition_job_creation_and_completion(monkeypatch):
    async def _fake_drug_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "이 약을 복용하는 동안 자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_drug_summary)

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
        guide_cards = confirm_response.json()["guide_cards"]
        assert len(guide_cards) == 1
        assert "자몽주스" in guide_cards[0]["content"]

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
        # (T-MED-6) 더미 텍스트는 confidence=1.0으로 취급되므로, 마스터 DB에 이미 등록된 이
        # 두 약(코드로 식별)의 match_rate도 1.0이어야 한다(하드코딩된 "타이레놀만 1.0" 로직이 아님을 확인).
        seeded_candidates = [c for c in result_data["candidates"] if c["drug_code"] in ("KD_T3001", "KD_A4002")]
        assert len(seeded_candidates) == 2
        assert all(c["match_rate"] == 1.0 for c in seeded_candidates)

        # 더미 후보도 기존 confirm 플로우를 그대로 통과해 스케줄 등록까지 이어져야 한다
        top_candidate = result_data["candidates"][0]
        confirm_response = await client.post(
            f"/api/v1/recognition/jobs/{job_id}/confirm",
            headers=headers,
            json={"selected_candidate_drug_code": top_candidate["drug_code"]},
        )
        assert confirm_response.status_code == status.HTTP_200_OK
        assert confirm_response.json()["status"] == "confirmed"


async def test_recognition_job_real_ocr_failure_does_not_silently_fall_back_to_dummy():
    """dummy_mode를 요청하지 않았는데 실제 OCR 호출이 안 되는/실패하는 환경(CLOVA 키 미설정 등)이면,
    더미 텍스트(*타이레놀정/*아스피린정)를 진짜 인식 결과인 것처럼 confidence=1.0으로 섞어 넣으면
    안 된다 — "OCR 근거가 아예 없을 때"의 기존 폴백(마스터 DB 상위 몇 개를 낮은 match_rate로 참고
    제시, T-MED-6)과 동일하게 처리되어야 한다."""
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
        # 테스트 환경에는 CLOVA_OCR_SECRET_KEY가 설정되어 있지 않다 — 더미로 위장한 결과가 아니라
        # "근거 없음" 폴백(낮은 match_rate의 참고용 후보)이어야 한다
        assert result_data["extracted_fields"]["dummy_mode"] is False
        assert result_data["candidates"]
        assert all(c["match_rate"] == 0.3 for c in result_data["candidates"])


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


async def test_quick_register_with_exact_name_match_registers_immediately():
    """약품명을 정확히 입력하고 바로 등록하면, 검색 단계 없이 한 번에 스케줄이 등록되어야 한다."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "quick_register_exact@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.post(
            "/api/v1/medications/quick-register",
            headers=headers,
            json={"drug_name": "아스피린정 100mg", "times": ["08:00"]},
        )
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert body["status"] == "registered"
        assert body["auto_created"] is False
        assert body["schedule"]["drug_name"] == "아스피린정 100mg"
        assert body["schedule"]["times"] == ["08:00"]

        list_res = await client.get("/api/v1/medications", headers=headers)
        assert any(s["drug_name"] == "아스피린정 100mg" for s in list_res.json())


async def test_quick_register_with_hospital_name_saves_and_returns_it():
    """병원명을 함께 입력하면 저장되고, 목록 조회에서도 병원명이 내려와야 한다(T-NTFY-2 복약 시간표 표시용)."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "quick_register_hospital@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.post(
            "/api/v1/medications/quick-register",
            headers=headers,
            json={"drug_name": "아스피린정 100mg", "times": ["08:00"], "hospital_name": "서울건강내과"},
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["schedule"]["hospital_name"] == "서울건강내과"

        list_res = await client.get("/api/v1/medications", headers=headers)
        mine = [s for s in list_res.json() if s["drug_name"] == "아스피린정 100mg"]
        assert mine and mine[0]["hospital_name"] == "서울건강내과"


async def test_update_schedule_times_success():
    """복약 스케줄의 복용 시간을 부분 수정(PATCH)하면 변경된 시간이 반영되어야 한다(T-NTFY-2 알림 화면 인라인 수정용)."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "schedule_patch@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        created = await client.post(
            "/api/v1/medications/quick-register",
            headers=headers,
            json={"drug_name": "아스피린정 100mg", "times": ["08:00", "20:00"]},
        )
        schedule_id = created.json()["schedule"]["id"]

        res = await client.patch(
            f"/api/v1/medications/{schedule_id}",
            headers=headers,
            json={"times": ["09:30", "20:00"]},
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["times"] == ["09:30", "20:00"]


async def test_update_schedule_not_owned_returns_404():
    """다른 프로필의 복약 스케줄은 수정할 수 없어야 한다."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_token = await _signup_and_login(client, "schedule_patch_owner@example.com")
        created = await client.post(
            "/api/v1/medications/quick-register",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"drug_name": "아스피린정 100mg", "times": ["08:00"]},
        )
        schedule_id = created.json()["schedule"]["id"]

        other_token = await _signup_and_login(client, "schedule_patch_other@example.com")
        res = await client.patch(
            f"/api/v1/medications/{schedule_id}",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"times": ["10:00"]},
        )
        assert res.status_code == status.HTTP_404_NOT_FOUND


async def test_quick_register_with_no_match_auto_creates_and_registers():
    """DB에 없는 약도 등록 자체는 막히지 않도록, OCR 플로우처럼 새 약품을 즉석 생성해 등록해야 한다."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "quick_register_new@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.post(
            "/api/v1/medications/quick-register",
            headers=headers,
            json={"drug_name": "존재하지않는약품12345", "times": ["10:00"]},
        )
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert body["status"] == "registered"
        assert body["auto_created"] is True
        assert body["schedule"]["drug_name"] == "존재하지않는약품12345"


async def test_quick_register_with_multiple_matches_returns_candidates_without_registering():
    """이름이 여러 약과 부분일치하면, 자동 등록하지 않고 사용자가 고를 후보 목록만 반환해야 한다
    (T-MED-1 원칙: 후보가 여러 개면 사용자 최종 선택 없이는 등록되지 않는다)."""
    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "quick_register_multi@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.post(
            "/api/v1/medications/quick-register",
            headers=headers,
            json={"drug_name": "정", "times": ["10:00"]},
        )
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert body["status"] == "multiple_matches"
        assert len(body["candidates"]) >= 2
        assert body["schedule"] is None

        list_res = await client.get("/api/v1/medications", headers=headers)
        assert list_res.json() == []


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


async def test_search_medications_dur_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "dur_search_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # 정상 검색 성공 케이스
        response = await client.get("/api/v1/medications/search-dur?query=콘서타", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "elapsed_ms" in data
        assert "results" in data
        assert isinstance(data["results"], list)


async def test_search_medications_dur_missing_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "dur_search_test2@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # 필수 query 인자가 누락된 경우 422 Unprocessable Entity 에러 검증
        response = await client.get("/api/v1/medications/search-dur", headers=headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_search_medications_dur_retries_with_dosage_suffix_stripped():
    """로컬 DB의 품목명은 'mg'가 아니라 '밀리그람' 등 한글 단위 표기라, OCR 등록명처럼
    'NN mg' 접미사가 붙은 검색어는 그대로면 매칭이 안 될 수 있다(T-MED-2-2에서 발견).
    '바이엘아스피린정500밀리그람'은 로컬 DB에 실제 효능 데이터가 있는 품목이라, 접미사를
    떼지 못하면 결과가 아예 없어야(0건) 재시도 로직이 실제로 동작했는지 구분할 수 있다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "dur_search_dosage_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        exact_response = await client.get("/api/v1/medications/search-dur?query=바이엘아스피린정500mg", headers=headers)
        stripped_response = await client.get("/api/v1/medications/search-dur?query=바이엘아스피린정", headers=headers)

        assert exact_response.status_code == status.HTTP_200_OK
        assert stripped_response.status_code == status.HTTP_200_OK
        exact_results = exact_response.json()["results"]
        stripped_results = stripped_response.json()["results"]
        assert len(exact_results) > 0
        assert len(exact_results) == len(stripped_results)


async def test_search_medications_dur_filters_out_items_with_no_content():
    """같은 이름으로 여러 품목이 매칭돼도(제형/제조사 차이 등), 효능·주의사항이 둘 다 없는
    빈 항목은 결과에서 제외한다 — '아스피린정'은 로컬 DB에 3건이 매칭되지만 1건만 실제
    내용이 있다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "dur_search_no_empty_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/medications/search-dur?query=아스피린정", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) > 0
        for result in results:
            assert result["efficacy"] != "정보 없음" or result["precautions"] != "특이사항 없음"


async def test_search_medications_dur_keeps_single_match_even_without_content():
    """매칭된 품목이 하나뿐인데 그 품목에 효능·주의사항 데이터가 전혀 없는 경우(로컬 라이트
    DB의 커버리지 한계), "제외할 다른 후보"가 없으므로 그 품목명 그대로 보여준다 — "정보
    없음"으로라도 무엇을 찾았는지 보여주는 게 "아예 못 찾았다"는 인상을 주는 것보다 낫다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "dur_no_content_single@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/medications/search-dur?query=레마이드정100mg", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 1
        assert "레마이드정" in data["results"][0]["item_name"]
        assert data["not_found_reason"] is None
