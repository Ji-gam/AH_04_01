from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette import status

from app.main import app
from app.models.profiles import Profile
from app.models.users import User
from app.models.withdrawn_stats import WithdrawnHealthStat
from app.tests.conftest import TestSessionLocal


async def _signup_and_login(client: AsyncClient, email: str, password: str = "Password123!") -> str:
    signup_data = {
        "email": email,
        "password": password,
        "name": "탈퇴테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01044445555",
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login_response.json()["access_token"]


async def test_withdraw_success_deletes_user_and_profile():
    email = "withdraw1@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, email)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.request(
            "DELETE", "/api/v1/auth/withdraw", json={"password": "Password123!"}, headers=headers
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # User와 Profile이 실제로 DB에서 완전히 사라졌는지 확인 (소프트삭제 아님)
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        assert user is None
        profile = (
            await session.execute(select(Profile).where(Profile.phone_number == "01044445555"))
        ).scalar_one_or_none()
        assert profile is None


async def test_withdraw_wrong_password():
    email = "withdraw2@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, email)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.request(
            "DELETE", "/api/v1/auth/withdraw", json={"password": "WrongPassword1!"}, headers=headers
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # 탈퇴 안 됐어야 한다
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        assert user is not None


async def test_withdraw_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request("DELETE", "/api/v1/auth/withdraw", json={"password": "Password123!"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_withdraw_then_reregister_with_same_email_and_phone():
    # 탈퇴 후 같은 이메일/전화번호로 재가입이 가능해야 한다 (완전 삭제됐다는 증거이기도 함)
    email = "withdraw3@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, email)
        headers = {"Authorization": f"Bearer {token}"}
        await client.request("DELETE", "/api/v1/auth/withdraw", json={"password": "Password123!"}, headers=headers)

        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "Password123!",
                "name": "재가입테스터",
                "gender": "MALE",
                "birth_date": "1990-01-01",
                "phone_number": "01044445555",
            },
        )
    assert response.status_code == status.HTTP_201_CREATED


async def test_withdraw_archives_anonymized_health_stats_and_leaves_no_identifying_link():
    """탈퇴 시 진단병력/가족력이 익명화된 통계로 남고, 그 레코드에서 원래 계정으로 역추적할
    수 있는 컬럼(profile_id/user_id/이름 등)이 전혀 없어야 한다."""
    email = "withdraw_stats@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, email)
        headers = {"Authorization": f"Bearer {token}"}

        await client.patch(
            "/api/v1/users/me/health-info",
            json={
                "birth_date": "1990-01-01",
                "diagnosis_history": [{"disease": "DIABETES", "detail": None}],
                "family_history": [{"disease": "CANCER", "detail": None}],
            },
            headers=headers,
        )

        before_count = await _count_withdrawn_stats()

        response = await client.request(
            "DELETE", "/api/v1/auth/withdraw", json={"password": "Password123!"}, headers=headers
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    async with TestSessionLocal() as session:
        stats = (await session.execute(select(WithdrawnHealthStat))).scalars().all()

    new_stats = stats[before_count:]
    assert len(new_stats) == 2

    diagnosis_stat = next(s for s in new_stats if s.is_family_history is False)
    assert diagnosis_stat.disease.value == "DIABETES"
    assert diagnosis_stat.age_group == "30대"  # 1990-01-01생 -> 테스트 시점 기준 30대

    family_stat = next(s for s in new_stats if s.is_family_history is True)
    assert family_stat.disease.value == "CANCER"

    # 이 테이블 컬럼 자체에 profile_id/user_id/이름 등 식별 컬럼이 없다는 것을 스키마 레벨로 확인
    columns = {c.name for c in WithdrawnHealthStat.__table__.columns}
    assert "profile_id" not in columns
    assert "user_id" not in columns
    assert "email" not in columns
    assert "name" not in columns


async def _count_withdrawn_stats() -> int:
    async with TestSessionLocal() as session:
        return len((await session.execute(select(WithdrawnHealthStat))).scalars().all())
