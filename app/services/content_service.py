"""
T-LLM-3: 건강 콘텐츠 생성 파이프라인.

`ContentService`는 DB 캐시를 읽고 픽스처를 시드하는 것만 한다 — LLM을 직접 호출하지
않는다(2026-07-08 확정: 사용자 요청 안에서 매번 LLM을 부르는 건 지연/비용 문제가 있어
제거함). 실제 LLM 생성은 `app/scripts/generate_health_content.py`가 오프라인으로 1회
실행해 JSON 픽스처를 만들고, `app/scripts/seed_health_content.py`가 그 픽스처를 이
서비스의 `seed_from_fixture`를 통해 DB에 채운다.
"""

import datetime as dt
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.repositories.content_repository import ContentRepository
from app.services import safety_service
from app.services.user_health_context_service import UserHealthContextService

POPULAR_DISEASES = ["암", "심장질환", "뇌혈관질환", "당뇨", "간질환"]
CATEGORIES = ["LIFESTYLE", "FOOD", "MEDICAL_NEWS"]


def _today_kst() -> date:
    return dt.datetime.now(config.TIMEZONE).date()


class ContentService:
    def __init__(
        self,
        repository: ContentRepository | None = None,
        health_context_service: UserHealthContextService | None = None,
    ) -> None:
        self._repository = repository or ContentRepository()
        self._health_context_service = health_context_service or UserHealthContextService()

    async def get_contents(self, session: AsyncSession, profile_id: int | None, category: str | None = None) -> dict:
        """캐시에 있는 것만 반환하는 누적 피드(라이브 생성 없음).
        비로그인(profile_id=None)이거나 등록된 질환이 없으면 전체 질환의 콘텐츠를 그대로
        반환한다 — "정보" 탭은 로그인/질환 등록 여부와 무관하게 볼 수 있어야 하기 때문이다.
        `personalized`로 두 경우를 프론트가 구분할 수 있게 한다(질환 등록 유도 배너 표시 판단용)."""
        conditions = self._health_context_service.get_context(profile_id)["conditions"] if profile_id else []
        personalized = bool(conditions)
        disease_filter = conditions if personalized else None
        contents = await self._repository.list_by_diseases(session, disease_filter, category)
        return {
            "personalized": personalized,
            "items": [self._to_response(content) for content in contents],
        }

    async def seed_from_fixture(self, session: AsyncSession, entries: list[dict]) -> int:
        """오프라인 생성 스크립트가 만든 픽스처 항목들을 오늘 날짜로 DB에 채운다.
        이미 오늘자 캐시가 있는 (질환, 카테고리) 조합은 건너뛴다."""
        today = _today_kst()
        inserted = 0
        for entry in entries:
            existing = await self._repository.get_by_disease_category_date(
                session, entry["disease_code"], entry["category"], today
            )
            if existing is not None:
                continue
            await self._repository.save(session, content_date=today, **entry)
            inserted += 1
        return inserted

    def _to_response(self, content) -> dict:
        return {
            "disease_code": content.disease_code,
            "category": content.category,
            "content_date": content.content_date,
            "title": content.title,
            "summary": content.summary,
            "body": content.body,
            "image_prompt": content.image_prompt,
            "disclaimer": safety_service.DISCLAIMER_TEXT,
        }
