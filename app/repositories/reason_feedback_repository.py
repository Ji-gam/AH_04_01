from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reason_feedback import FeedbackValue, ReasonFeedback, ReasonFeedbackFeature


class ReasonFeedbackRepository:
    async def get(
        self, session: AsyncSession, profile_id: int, feature: ReasonFeedbackFeature, target_key: str
    ) -> ReasonFeedback | None:
        result = await session.execute(
            select(ReasonFeedback).where(
                ReasonFeedback.profile_id == profile_id,
                ReasonFeedback.feature == feature,
                ReasonFeedback.target_key == target_key,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        session: AsyncSession,
        profile_id: int,
        feature: ReasonFeedbackFeature,
        target_key: str,
        value: FeedbackValue,
        comment: str | None,
    ) -> ReasonFeedback:
        existing = await self.get(session, profile_id, feature, target_key)
        if existing is not None:
            existing.value = value
            existing.comment = comment
        else:
            existing = ReasonFeedback(
                profile_id=profile_id, feature=feature, target_key=target_key, value=value, comment=comment
            )
            session.add(existing)
        try:
            await session.commit()
        except IntegrityError:
            # diet_repository.save_kcal_reason과 같은 패턴 - 동시에 같은 대상에 피드백을
            # 남기려던 다른 요청이 먼저 커밋한 경우, 재조회해서 그 값을 갱신한다.
            await session.rollback()
            existing = await self.get(session, profile_id, feature, target_key)
            assert existing is not None
            existing.value = value
            existing.comment = comment
            await session.commit()
        await session.refresh(existing)
        return existing
