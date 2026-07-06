from fastapi import HTTPException, status

from app.dtos.generated_guide import GuideCreate
from app.models.generated_guides import GeneratedGuide
from app.models.users import User


class GeneratedGuideService:
    async def create_guide(self, user: User, data: GuideCreate) -> GeneratedGuide:
        placeholder_content = (
            f"[플레이스홀더] {data.guide_type} 가이드 - 실제 LLM 연동 전까지 이 문구가 대신 저장됩니다."
        )
        new_guide = await GeneratedGuide.create(
            user=user, record_id=data.record_id, guide_type=data.guide_type, content=placeholder_content
        )
        return new_guide

    async def get_guide(self, user: User, guide_id: int) -> GeneratedGuide:
        guide = await GeneratedGuide.get_or_none(id=guide_id, user=user)
        if not guide:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="가이드를 찾을 수 없습니다.")
        return guide
