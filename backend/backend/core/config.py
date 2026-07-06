# backend/config.py
# 환경 변수 로드 및 설정 관리
import os
from dotenv import load_dotenv

load_dotenv() # .env 파일의 내용을 환경변수로 로드

class Settings:
    MFDS_API_KEY: str = os.getenv("MFDS_API_KEY", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-insecure-secret-CHANGE-ME")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

settings = Settings()