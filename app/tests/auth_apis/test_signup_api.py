from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette import status

from app.main import app
from app.models.profiles import Profile, ProfileRelation
from app.models.users import User
from app.tests.conftest import TestSessionLocal


async def test_signup_success():
    # [가입 최소화] 닉네임(name) + email + password만 받는다 - 성별/나이/휴대폰번호는 더보기 > 개인건강정보에서 나중에.
    signup_data = {
        "email": "test@example.com",
        "password": "password123!",
        "name": "테스터",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {"detail": "회원가입이 성공적으로 완료되었습니다."}

    # 회원가입 시 User와 함께 본인(SELF) Profile도 같이 생성되고, 나이/성별/휴대폰번호는 전부 null이어야 한다.
    # [2026-07-29 PII/건강정보 분리] gender/age는 이제 health_profile 경유 - selectinload로
    # 명시적으로 같이 불러온다(그래야 async 세션에서 lazy load 에러 없이 접근 가능).
    # health_profile 자체는 가입 시 항상 같이 생성되는 게 불변식이므로 None이면 안 된다.
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
        profile = (
            await session.execute(
                select(Profile).where(Profile.user_id == user.id).options(selectinload(Profile.health_profile))
            )
        ).scalar_one()
        assert profile.relation == ProfileRelation.SELF
        assert profile.name == "테스터"
        assert profile.health_profile is not None, "가입 시 health_profile이 같이 생성되지 않음"
        assert profile.health_profile.gender is None
        assert profile.age is None
        assert profile.phone_number is None


async def test_signup_invalid_email():
    signup_data = {"email": "invalid-email", "password": "password123!", "name": "테스터"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_signup_weak_password():
    # 특수문자가 빠진 비밀번호 -> validate_password가 거부해야 한다 (대문자 요건은 완화됨, 특수문자는 여전히 필요)
    signup_data = {"email": "weakpw@example.com", "password": "password123", "name": "테스터"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    body = response.json()
    messages = " ".join(err["msg"] for err in body["detail"])
    assert "비밀번호" in messages

    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "weakpw@example.com"))).scalar_one_or_none()
        assert user is None


async def test_signup_password_without_uppercase_is_allowed():
    # 대문자 요건이 완화됐다 - 소문자+숫자+특수문자만 있어도 통과해야 한다
    signup_data = {"email": "nouppercase@example.com", "password": "password123!", "name": "테스터"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == status.HTTP_201_CREATED


async def test_signup_duplicate_email():
    signup_data = {"email": "dup@example.com", "password": "password123!", "name": "중복테스터1"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        second = dict(signup_data, name="중복테스터2")
        response = await client.post("/api/v1/auth/signup", json=second)
    assert response.status_code == status.HTTP_409_CONFLICT
