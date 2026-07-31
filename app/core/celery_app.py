"""
T-LLM-2-async-gateway / T-LLM-3-1: Celery 앱 스켈레톤. 기존 `docker-compose.yml`의
`redis` 서비스를 브로커로 재사용한다. 이 파일 자체는 인프라 골격만 제공하고,
개별 태스크(콘텐츠 생성 등)는 각 도메인 모듈에서 `@celery_app.task`로 등록한다.

docker-compose에 `celery-worker`/`celery-beat` 서비스를 추가하는 것은 리더 소유
파일(`docker-compose.yml`) 변경이라 리더가 직접 진행한다(이 파일은 그 전제 없이도
로컬에서 `celery -A app.core.celery_app worker`로 단독 기동/테스트 가능하다).
"""

from celery import Celery

from app.core import config

celery_app = Celery("ai_health_final", broker=config.CELERY_BROKER_URL)
