from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app


class TestSignupAPI(TestCase):
    async def test_signup_success(self):
        signup_data = {
            "email": "test@example.com",
            "password": "Password123!",
            "name": "테스터",
            "gender": "MALE",
            "birth_date": "1990-01-01",
            "phone_number": "01012345678",
            "agreed_terms": True,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {"detail": "회원가입이 성공적으로 완료되었습니다."}

    async def test_signup_invalid_email(self):
        signup_data = {
            "email": "invalid-email",
            "password": "password123!",
            "name": "테스터",
            "gender": "MALE",
            "birth_date": "1990-01-01",
            "phone_number": "01012345678",
            "agreed_terms": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_signup_without_agreeing_to_terms_is_rejected(self):
        """[핀포인트 추가] 필수 약관에 동의(agreed_terms=True)하지 않으면 가입 자체가 막혀야 합니다."""
        base_data = {
            "email": "no_agree@example.com",
            "password": "Password123!",
            "name": "미동의테스터",
            "gender": "MALE",
            "birth_date": "1990-01-01",
            "phone_number": "01099998888",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # agreed_terms 아예 안 보낸 경우
            response_missing = await client.post("/api/v1/auth/signup", json=base_data)
            assert response_missing.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

            # agreed_terms: false로 명시한 경우
            response_false = await client.post("/api/v1/auth/signup", json={**base_data, "agreed_terms": False})
            assert response_false.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_signup_records_agreed_terms_timestamp(self):
        """[핀포인트 추가] 동의하고 가입하면 DB에 동의 시각(agreed_terms_at)이 실제로 기록되어야 합니다."""
        from app.models.users import User

        signup_data = {
            "email": "agreed_at_test@example.com",
            "password": "Password123!",
            "name": "동의시각테스터",
            "gender": "MALE",
            "birth_date": "1990-01-01",
            "phone_number": "01011119999",
            "agreed_terms": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_data)
        assert response.status_code == status.HTTP_201_CREATED

        user = await User.get(email="agreed_at_test@example.com")
        assert user.agreed_terms_at is not None
