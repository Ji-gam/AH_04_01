# backend/routers/drug_test_router.py
# FastAPI 라우터를 사용하여 의약품안전나라 API 테스트 엔드포인트를 제공하는 모듈(문제없으면 제거예정)
from fastapi import APIRouter
import httpx
from backend.core.config import settings

router = APIRouter()

@router.get("/test-drug-api/{pill_name}")
async def test_drug_api(pill_name: str):
    url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
    params = {
        "serviceKey": settings.MFDS_API_KEY,
        "itemName": pill_name,
        "type": "json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=5.0)
            return response.json()
        except Exception as e:
            return {"error": str(e)}