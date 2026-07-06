# backend/utils/helpers.py
# 필요 데이터 도구 초안!
from datetime import datetime

def format_date(date_str: str) -> str:
    """OCR에서 추출된 날짜 형식을 표준화합니다."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y년 %m월 %d일")
    except:
        return date_str

def is_valid_medication_data(data: dict) -> bool:
    """필수 데이터가 포함되어 있는지 검증합니다."""
    required = ["pill_name", "dosage"]
    return all(key in data for key in required)