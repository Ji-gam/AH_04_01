from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    phone_number = "010" + str(abs(hash(email)))[:8]
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "콘텐츠테스터",
        "gender": "FEMALE",
        "birth_date": "1995-05-05",
        "phone_number": phone_number,
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_get_contents_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/contents/me")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_get_contents_returns_empty_list_for_profile_without_conditions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "content1@example.com")
        response = await client.get("/api/v1/contents/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


async def test_get_contents_with_category_filter_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "content2@example.com")
        response = await client.get(
            "/api/v1/contents/me",
            params={"category": "FOOD"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


async def test_get_contents_with_invalid_category_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "content3@example.com")
        response = await client.get(
            "/api/v1/contents/me",
            params={"category": "NOT_A_CATEGORY"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
