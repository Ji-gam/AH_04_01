# backend/database.py
# SQLAlchemy를 사용하여 데이터베이스 연결 및 세션 관리를 설정하는 모듈
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus

# 1. 파일 경로를 수동으로 지정 (현재 파일 위치 기준으로 상위 폴더)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'

# 2. .env 로드 확인
if not env_path.exists():
    print(f"!!! 에러: .env 파일을 찾을 수 없습니다. 경로 확인: {env_path}")
load_dotenv(dotenv_path=env_path)

# 3. 값 가져오기
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")

# 4. 필수 값이 없는 경우 체크
if not all([DB_USER, DB_PASSWORD, DB_NAME]):
    print(f"!!! 에러: 환경변수 누락! User:{DB_USER}, PW:{bool(DB_PASSWORD)}, DB:{DB_NAME}")
    raise ValueError("DB 환경변수가 설정되지 않았습니다.")

# 5. URL 생성
safe_password = quote_plus(DB_PASSWORD)
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"DEBUG: 성공적으로 연결을 시도합니다: {DB_USER} @ {DB_HOST} / {DB_NAME}")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()