"""
T-LLM-3: 건강 콘텐츠 생성 파이프라인.

`ContentService`는 DB 캐시를 읽고 픽스처를 시드하는 것만 한다 — LLM을 직접 호출하지
않는다(2026-07-08 확정: 사용자 요청 안에서 매번 LLM을 부르는 건 지연/비용 문제가 있어
제거함). 실제 LLM 생성은 `app/scripts/generate_health_content.py`가 오프라인으로 1회
실행해 JSON 픽스처를 만들고, `app/scripts/seed_health_content.py`가 그 픽스처를 이
서비스의 `seed_from_fixture`를 통해 DB에 채운다.

profile/개인화 개념을 전혀 모르는 순수 조회 모듈이다 — "누구의 질환인지" 판단은
`ContentPersonalizationService`가 전담하고, 이 서비스는 disease_code 목록만 받아
mysql을 조회한다. 그래야 다른 모듈(예: 메인화면 미리보기)도 profile/session 없이
"질환+개수"만으로 이 서비스를 바로 재사용할 수 있다.
"""

import datetime as dt
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.repositories.content_repository import ContentRepository
from app.services import safety_service

POPULAR_DISEASES = ["암", "심장질환", "뇌혈관질환", "당뇨", "간질환", "기타"]
CATEGORIES = ["LIFESTYLE", "FOOD", "MEDICAL_NEWS"]

# 카테고리마다 최소 3장은 보여야 한다는 요구에 맞춰, 질환당 카테고리별로 이 소주제 3개를
# 각각 생성한다(`generate_health_content.py`가 사용). "기타"도 동일한 소주제 축을 쓰되,
# 프롬프트에서 특정 질환명 대신 일반 건강정보로 치환된다.
CATEGORY_TOPICS: dict[str, list[str]] = {
    "LIFESTYLE": ["운동과 활동량 관리", "수면 위생", "스트레스 관리"],
    "FOOD": ["식단 구성 원칙", "피해야 할 음식과 성분", "챙겨 먹으면 좋은 영양소"],
    "MEDICAL_NEWS": ["최신 치료 동향", "예방·관리 연구 결과", "진료 가이드라인 업데이트"],
}


def _today_kst() -> date:
    return dt.datetime.now(config.TIMEZONE).date()


class ContentService:
    def __init__(self, repository: ContentRepository | None = None) -> None:
        self._repository = repository or ContentRepository()

    async def get_contents(
        self,
        session: AsyncSession,
        diseases: list[str] | None,
        category: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """캐시에 있는 것만 반환하는 누적 피드(라이브 생성 없음).
        `diseases`가 None이면 질환 필터 없이 전체를 반환한다 — 호출자가 비로그인/질환
        미등록 여부를 판단해서 넘겨준다(이 서비스는 그 판단을 하지 않는다)."""
        contents = await self._repository.list_by_diseases(session, diseases, category, limit=limit)
        return [self._to_response(content) for content in contents]

    async def seed_from_fixture(self, session: AsyncSession, entries: list[dict]) -> int:
        """오프라인 생성 스크립트가 만든 픽스처 항목들을 DB에 채운다.
        항목에 `content_date`(ISO 문자열)가 있으면 그 날짜로, 없으면 오늘 날짜로 시드한다 —
        같은 (질환, 카테고리) 안에서 여러 소주제 카드를 유니크 제약 위반 없이 공존시키려면
        생성 스크립트가 소주제별로 날짜를 하루씩 다르게 배정해야 하기 때문이다(조회 API는
        날짜로 거르지 않으므로 화면에는 그대로 다 보인다). 이미 같은 (질환, 카테고리, 날짜)
        캐시가 있으면 건너뛴다."""
        today = _today_kst()
        inserted = 0
        for entry in entries:
            entry = dict(entry)
            content_date_str = entry.pop("content_date", None)
            content_date = date.fromisoformat(content_date_str) if content_date_str else today
            existing = await self._repository.get_by_disease_category_date(
                session, entry["disease_code"], entry["category"], content_date
            )
            if existing is not None:
                continue
            await self._repository.save(session, content_date=content_date, **entry)
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
