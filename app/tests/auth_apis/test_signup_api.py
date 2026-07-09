from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette import status

from app.main import app
from app.models.profiles import Profile, ProfileRelation
from app.models.users import User
from app.tests.conftest import TestSessionLocal


async def test_signup_success():
    signup_data = {
        "email": "test@example.com",
        "password": "Password123!",
        "name": "테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01012345678",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {"detail": "회원가입이 성공적으로 완료되었습니다."}

    # 회원가입 시 User와 함께 본인(SELF) Profile도 같이 생성돼야 한다
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
        profile = (await session.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
        assert profile.relation == ProfileRelation.SELF
        assert profile.name == "테스터"
        assert profile.phone_number == "01012345678"


async def test_signup_invalid_email():
    signup_data = {
        "email": "invalid-email",
        "password": "password123!",
        "name": "테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01012345678",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_signup_weak_password():
    # 대문자/특수문자가 빠진 비밀번호 -> validate_password가 거부해야 한다
    signup_data = {
        "email": "weakpw@example.com",
        "password": "password123",
        "name": "테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01055556666",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    body = response.json()
    messages = " ".join(err["msg"] for err in body["detail"])
    assert "비밀번호" in messages

    # 검증에서 막혔으니 실제로 DB에 저장되면 안 된다
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "weakpw@example.com"))).scalar_one_or_none()
        assert user is None


async def test_signup_invalid_phone_number_format():
    # 형식에 안 맞는 휴대폰번호(자릿수 부족) -> validate_phone_number가 거부해야 한다
    signup_data = {
        "email": "badphone@example.com",
        "password": "Password123!",
        "name": "테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "0101234",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    body = response.json()
    messages = " ".join(err["msg"] for err in body["detail"])
    assert "휴대폰" in messages

    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "badphone@example.com"))).scalar_one_or_none()
        assert user is None


async def test_signup_duplicate_email():
    signup_data = {
        "email": "dup@example.com",
        "password": "Password123!",
        "name": "중복테스터1",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01011112222",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        second = dict(signup_data, name="중복테스터2", phone_number="01033334444")
        response = await client.post("/api/v1/auth/signup", json=second)
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_signup_duplicate_phone_number():
    signup_data = {
        "email": "phoneA@example.com",
        "password": "Password123!",
        "name": "폰중복1",
        "gender": "FEMALE",
        "birth_date": "1990-01-01",
        "phone_number": "01099990000",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        second = dict(signup_data, email="phoneB@example.com", name="폰중복2")
        response = await client.post("/api/v1/auth/signup", json=second)
    assert response.status_code == status.HTTP_409_CONFLICT
