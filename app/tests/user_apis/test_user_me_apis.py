from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def test_get_user_me_success():
    # 사용자 등록 및 로그인
    email = "me@example.com"
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "내정보테스터",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        access_token = login_response.json()["access_token"]

        # 내 정보 조회
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["email"] == email
    assert body["name"] == "내정보테스터"
    # User(id)와 Profile(profile_id)이 둘 다 노출돼야 한다
    assert "id" in body
    assert "profile_id" in body


async def test_update_user_me_success():
    # 사용자 등록 및 로그인
    email = "update_me@example.com"
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "수정전",
    }
    update_data = {"name": "수정후"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        access_token = login_response.json()["access_token"]

        # 내 정보 수정
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.patch("/api/v1/users/me", json=update_data, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "수정후"


async def test_update_user_me_email_is_ignored():
    # email은 UserUpdateRequest에 필드 자체가 없어서, 보내도 조용히 무시되고 바뀌지 않아야 한다.
    email = "email_locked@example.com"
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "이메일고정테스터",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        access_token = login_response.json()["access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.patch(
            "/api/v1/users/me", json={"email": "changed@example.com", "name": "이름만변경"}, headers=headers
        )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["email"] == email  # 변경 요청을 보냈어도 원래 이메일 그대로
    assert body["name"] == "이름만변경"  # name은 정상적으로 변경됨


async def test_get_user_me_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
