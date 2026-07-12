"""
T-LLM-3-manual-content-generation: QA 전용 수동 콘텐츠 생성 트리거.

`ContentService`는 DB 캐시만 읽고 LLM을 직접 호출하지 않는다(2026-07-08 확정: 요청 안에서
매번 LLM을 부르는 건 지연/비용 문제가 있어 제거함). 이 서비스는 그 원칙을 의도적으로
벗어난다 — 프로덕션 사용자 플로우가 아니라, "더보기 > 컨텐츠생성" 화면에서 사람이 버튼을
눌러 실제로 ai_worker LLM 생성을 트리거하는 **QA 전용** 경로다. 목적: #83(게이트웨이
생성 타임아웃 분리) 수정이 실제 환경에서 동작하는지 수동으로 검증한다.

실패(AIWorkerUnavailableError 등)는 조용히 삼키지 않고 그대로 호출자(라우터)에게
전파한다 — ContentService._search_chunks류의 "실패해도 계속 진행" 정책과 다르다.
"""

import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.content_repository import ContentRepository
from app.scripts.generate_health_content import generate_content_card
from app.services import safety_service
from app.services.content_service import CATEGORIES, CATEGORY_TOPICS, POPULAR_DISEASES, _today_kst


class ContentGenerationService:
    def __init__(self, repository: ContentRepository | None = None) -> None:
        self._repository = repository or ContentRepository()

    async def generate_and_save(
        self,
        session: AsyncSession,
        disease_code: str | None = None,
        category: str | None = None,
        topic: str | None = None,
    ) -> dict:
        """생략된 값은 무작위로 고른다. 같은 (질환, 카테고리, 오늘 날짜) 캐시가 이미 있으면
        유니크 제약 위반 대신 그 행을 갱신한다 — 버튼을 여러 번 눌러도 "오늘 것을 다시
        생성"하는 동작이 되게 하기 위함."""
        disease_code = disease_code or random.choice(POPULAR_DISEASES)
        category = category or random.choice(CATEGORIES)
        topic = topic or random.choice(CATEGORY_TOPICS[category])
        content_date = _today_kst()

        card = await generate_content_card(disease_code, category, topic)

        existing = await self._repository.get_by_disease_category_date(session, disease_code, category, content_date)
        if existing is not None:
            content = await self._repository.update_card(
                session,
                existing,
                title=card["title"],
                summary=card["summary"],
                body=card["body"],
                image_prompt=card.get("image_prompt"),
            )
        else:
            content = await self._repository.save(
                session, disease_code=disease_code, category=category, content_date=content_date, **card
            )

        return self._to_response(content)

    def _to_response(self, content) -> dict:
        return {
            "id": content.id,
            "disease_code": content.disease_code,
            "category": content.category,
            "content_date": content.content_date,
            "title": content.title,
            "summary": content.summary,
            "body": content.body,
            "image_prompt": content.image_prompt,
            "disclaimer": safety_service.DISCLAIMER_TEXT,
        }
