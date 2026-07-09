from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette import status

from app.main import app
from app.models.profiles import Profile
from app.models.users import User
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
