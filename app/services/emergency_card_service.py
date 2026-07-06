from fastapi import HTTPException, status

from app.dtos.emergency_card import EmergencyCardUpsert
from app.models.emergency_cards import EmergencyCard
from app.models.users import User


class EmergencyCardService:
    async def get_card_by_user(self, user: User) -> EmergencyCard:
        card = await EmergencyCard.get_or_none(user=user)
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 응급 의료 카드가 없습니다.")
        return card

    async def upsert_card(self, user: User, data: EmergencyCardUpsert) -> EmergencyCard:
        card = await EmergencyCard.get_or_none(user=user)
        if card:
            # 업데이트
            card_dict = data.model_dump(exclude_unset=True)
            for k, v in card_dict.items():
                setattr(card, k, v)
            await card.save()
        else:
            # 생성
            card = await EmergencyCard.create(user=user, **data.model_dump())
        return card
