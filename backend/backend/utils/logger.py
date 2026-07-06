# backend/utils/logger.py
#로깅 시스템 초안구성

import logging

def setup_logger(name: str):
    """프로젝트 전반에서 사용할 공통 로거를 생성합니다."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

# 사용 예시: logger = setup_logger("HealthAI")