# backend/services/drug_info_service.py
# 약물 정보 자동 업데이트(캐싱) 서비스
from sqlalchemy.orm import Session
from backend.domains.record.model import Medication
import httpx
from backend.core.config import settings

async def enrich_medication_info(db: Session, medication: Medication):
    """
    약물 정보가 없으면 API를 호출하여 DB에 자동 업데이트(캐싱)하는 함수
    """
    # 1. 이미 정보가 있는지 확인
    if medication.effect and medication.caution:
        return medication

    # 2. 없으면 의약품안전나라 호출
    url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
    params = {"serviceKey": settings.MFDS_API_KEY, "itemName": medication.pill_name, "type": "json"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            # [여기에 API 응답에서 effect, caution 파싱하는 로직 추가]
            # medication.effect = parsed_effect
            # medication.caution = parsed_caution
            db.commit() # DB 자동 업데이트
            
    return medication