from datetime import date

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.core.db.databases import AsyncSessionLocal
from app.models.push_send_log import PushSendLog


class PushSendLogRepository:
    """[주의] 호출자의 session을 받지 않고 독립된 새 세션을 연다 - habit_repository.py의
    save_subtype_suggestions와 같은 이유다: 유니크 제약 충돌(다른 워커가 먼저 클레임)로
    롤백해야 하는데, 호출자 session으로 롤백하면 그 session이 이미 읽어둔 다른 객체들까지
    만료되어 이후 접근 시 MissingGreenlet 에러로 이어진다. 독립된 세션이면 이 세션 안의
    객체만 영향받고 호출자 session은 전혀 건드리지 않는다."""

    async def try_claim(self, source_type: str, source_id: int, sent_date: date, sent_time: str) -> bool:
        """이 (source_type, source_id, sent_date, sent_time) 조합을 처음 클레임하면 True(발송해도
        됨), 이미 다른 워커가 클레임했으면(유니크 제약 위반) False(건너뛰어야 함)를 반환한다."""
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    insert(PushSendLog).values(
                        source_type=source_type,
                        source_id=source_id,
                        sent_date=sent_date,
                        sent_time=sent_time,
                    )
                )
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False
