import asyncio
import io

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client, medication_service


class _FakeDurDrugRepository:
    """(T-MED-16) 실제 마스터 DB 대신, 테스트가 통제하는 (item_seq, item_name) 목록만
    돌려준다 — 마스터 데이터에만 있는 약이 수동 등록/검색 경로에서도 잡히는지 결정적으로
    검증하기 위함."""

    def __init__(self, items: list[tuple[str, str]]):
        self._items = items

    async def search_item_names(self, session, item_name: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if item_name in name][:limit]

    async def search_item_names_by_prefix(self, session, prefix: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if name.startswith(prefix)][:limit]

    async def get_names_by_item_seqs(self, session, item_seqs: set[str]) -> dict[str, str]:
        return {seq: name for seq, name in self._items if seq in item_seqs}

    async def find_food_intrc_text(self, session, item_name: str) -> str | None:
        """(T-DOC-5) 이 가짜 저장소는 이름 검색용 픽스처만 다루므로, 음식 상호작용 빠른 조회
        (2단계 `drugs_data` 스냅샷)는 항상 "찾지 못함"으로 취급해 느린 경로로 넘긴다."""
        return None


# 마스터 데이터에 있는 것처럼 가장할 고정 픽스처. 실제 OCR 텍스트(용량 포함)와 정확히 일치하는
# 이름을 쓴다 - dummy_mode(DUMMY_OCR_RAW_TEXT = "*타이레놀정"/"*아스피린정")는 용량 표기가 없는
# 짧은 이름이라 별도 픽스처(_DUMMY_MODE_SEEDED_DRUGS)를 쓴다.
_SEEDED_DRUGS = [
    ("KD_T3001", "타이레놀정 500mg"),
    ("KD_A4002", "아스피린정 100mg"),
]
_DUMMY_MODE_SEEDED_DRUGS = [
    ("KD_T3001", "타이레놀정"),
    ("KD_A4002", "아스피린정"),
]


def _seed_dummy_medications(monkeypatch, items: list[tuple[str, str]] | None = None) -> None:
    """(T-MED-16) 더 이상 `medications` 캐시 테이블이 없으므로, `DurDrugRepository`를 가짜
    구현으로 교체해 마스터 데이터에 이 약들이 있는 것처럼 결정적으로 검증한다. 수동 등록
    (`POST /medications`)은 item_seq 존재를 앱 레벨로 검증하는데, 그 검증은 실제 마스터
    테이블(`dur_prod_master_list` 등)을 조회하므로 가짜 item_seq는 그대로면 통과하지 못한다 -
    그래서 `MedicationRepository.item_seq_exists`도 함께 우회한다."""
    monkeypatch.setattr(medication_service, "DurDrugRepository", lambda: _FakeDurDrugRepository(items or _SEEDED_DRUGS))

    async def _always_exists(self, session, item_seq):
        return True

    monkeypatch.setattr(MedicationRepository, "item_seq_exists", _always_exists)


async def _wait_for_job_done(client: AsyncClient, headers: dict, job_id: str, timeout: float = 10.0) -> dict:
    """백그라운드 OCR 태스크는 LLM 보완 경로(ai_worker 네트워크 호출)까지 기다리므로, DNS
    실패 등 네트워크 환경에 따라 완료 시점이 들쭉날쭉하다 - 고정 sleep 대신 상태가 "pending"을
    벗어날 때까지 짧게 반복 조회한다."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        get_response = await client.get(f"/api/v1/recognition/jobs/{job_id}", headers=headers)
        result_data = get_response.json()
        if result_data["status"] != "pending":
            return result_data
        await asyncio.sleep(0.2)
    return result_data


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


async def test_recognition_job_creation_and_completion(monkeypatch):
    async def _fake_drug_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "이 약을 복용하는 동안 자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_drug_summary)
    _seed_dummy_medications(monkeypatch)

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

        # 2. 백그라운드 태스크 완료 대기 & 결과 조회
        result_data = await _wait_for_job_done(client, headers, job_id)
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


async def test_recognition_job_dummy_mode_returns_deterministic_candidates_and_is_marked(monkeypatch):
    """OCR이 실패하든 성공하든과 무관하게, QA가 dummy_mode=true로 명시 요청하면
    결정적인 더미 후보를 즉시 받고, extracted_fields로 더미임을 구분할 수 있어야 한다."""
    _seed_dummy_medications(monkeypatch, _DUMMY_MODE_SEEDED_DRUGS)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "dummy_mode_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("pill.jpg", io.BytesIO(b"fake pill photo bytes"), "image/jpeg")}
        data = {"source_type": "pill_photo", "dummy_mode": "true"}

        response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
        assert response.status_code == status.HTTP_202_ACCEPTED
        job_id = response.json()["job_id"]

        result_data = await _wait_for_job_done(client, headers, job_id)
        assert result_data["status"] == "done"
        assert result_data["extracted_fields"]["dummy_mode"] is True
        drug_names = [c["drug_name"] for c in result_data["candidates"]]
        assert any("타이레놀정" in name for name in drug_names)
        assert any("아스피린정" in name for name in drug_names)
        # (T-MED-6) 더미 텍스트는 confidence=1.0으로 취급되므로, 마스터 데이터에 이미 있는 이
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


async def test_recognition_job_real_ocr_failure_does_not_silently_fall_back_to_dummy(monkeypatch):
    """dummy_mode를 요청하지 않았는데 실제 OCR 호출이 안 되는/실패하는 환경(CLOVA 키 미설정 등)이면,
    더미 텍스트(*타이레놀정/*아스피린정)를 진짜 인식 결과인 것처럼 confidence=1.0으로 섞어 넣으면
    안 된다 — "OCR 근거가 아예 없을 때"의 기존 폴백(마스터 데이터 상위 몇 개를 낮은 match_rate로 참고
    제시, T-MED-6)과 동일하게 처리되어야 한다."""
    _seed_dummy_medications(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ocr_failure_fallback@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("pill.jpg", io.BytesIO(b"fake pill photo bytes"), "image/jpeg")}
        data = {"source_type": "pill_photo"}

        response = await client.post("/api/v1/recognition/jobs", headers=headers, files=files, data=data)
        job_id = response.json()["job_id"]

        result_data = await _wait_for_job_done(client, headers, job_id)
        # 테스트 환경에는 CLOVA_OCR_SECRET_KEY가 설정되어 있지 않다 — 더미로 위장한 결과가 아니라
        # "근거 없음" 폴백(낮은 match_rate의 참고용 후보)이어야 한다
        assert result_data["extracted_fields"]["dummy_mode"] is False
        assert result_data["candidates"]
        assert all(c["match_rate"] == 0.3 for c in result_data["candidates"])


async def test_manual_schedule_registration_and_search(monkeypatch):
    _seed_dummy_medications(monkeypatch)

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


async def test_search_medications_finds_drug_only_in_master_data(monkeypatch):
    """(T-MED-16) 마스터 데이터(dur_prod_master_list)에서 찾은 약도, 수동 등록 검색
    자동완성에서 "없음"으로 뜨지 않고 후보로 나와야 한다."""
    _seed_dummy_medications(monkeypatch, [("409900001", "게보린정")])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "master_data_search_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.get("/api/v1/medications/search?query=게보린", headers=headers)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert any(m["medication_name"] == "게보린정" and m["item_seq"] == "409900001" for m in body)


async def test_quick_register_with_master_data_match_promotes_instead_of_auto_dummy(monkeypatch):
    """(T-MED-16) 빠른 등록에서 마스터 데이터에 정확히 일치하는 약이 있으면, "마스터 데이터에
    없음"(AUTO_ 더미) 대신 그 약으로 정상 등록해야 한다."""
    monkeypatch.setattr(
        medication_service, "DurDrugRepository", lambda: _FakeDurDrugRepository([("409900002", "게보린정")])
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "master_quick_register@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.post(
            "/api/v1/medications/quick-register",
            headers=headers,
            json={"drug_name": "게보린정", "times": ["08:00"]},
        )
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert body["status"] == "registered"
        assert body["auto_created"] is False
        assert body["schedule"]["drug_name"] == "게보린정"


async def test_delete_schedule_removes_it_from_list(monkeypatch):
    _seed_dummy_medications(monkeypatch)

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


async def test_delete_schedule_of_another_profile_is_forbidden(monkeypatch):
    _seed_dummy_medications(monkeypatch)

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


async def test_quick_register_with_exact_name_match_registers_immediately(monkeypatch):
    """약품명을 정확히 입력하고 바로 등록하면, 검색 단계 없이 한 번에 스케줄이 등록되어야 한다."""
    _seed_dummy_medications(monkeypatch)

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


async def test_quick_register_with_hospital_name_saves_and_returns_it(monkeypatch):
    """병원명을 함께 입력하면 저장되고, 목록 조회에서도 병원명이 내려와야 한다(T-NTFY-2 복약 시간표 표시용)."""
    _seed_dummy_medications(monkeypatch)

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


async def test_update_schedule_times_success(monkeypatch):
    """복약 스케줄의 복용 시간을 부분 수정(PATCH)하면 변경된 시간이 반영되어야 한다(T-NTFY-2 알림 화면 인라인 수정용)."""
    _seed_dummy_medications(monkeypatch)

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


async def test_update_schedule_rejects_empty_times(monkeypatch):
    """times를 빈 리스트로 PATCH하면 거부해야 한다 - 등록은 남고 복용 시각만 없는
    좀비 상태를 막기 위함(#192 리뷰: 마지막 알림 삭제 시 재현됨). 등록 자체를 지우려면
    DELETE를 써야 한다."""
    _seed_dummy_medications(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "schedule_patch_empty_times@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        created = await client.post(
            "/api/v1/medications/quick-register",
            headers=headers,
            json={"drug_name": "아스피린정 100mg", "times": ["08:00"]},
        )
        schedule_id = created.json()["schedule"]["id"]

        res = await client.patch(
            f"/api/v1/medications/{schedule_id}",
            headers=headers,
            json={"times": []},
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        list_res = await client.get("/api/v1/medications", headers=headers)
        mine = [s for s in list_res.json() if s["id"] == schedule_id]
        assert mine and mine[0]["times"] == ["08:00"]


async def test_update_schedule_not_owned_returns_404(monkeypatch):
    """다른 프로필의 복약 스케줄은 수정할 수 없어야 한다."""
    _seed_dummy_medications(monkeypatch)

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
