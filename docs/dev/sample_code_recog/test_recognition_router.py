from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def test_confirm_데모_API_정상응답_형태():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/recognition/confirm-demo", params={"drug_name": "자몽주스"})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "confirmed"
    assert isinstance(body["guide_cards"], list)
    assert len(body["guide_cards"]) >= 1
    assert "disclaimer" in body["guide_cards"][0]
