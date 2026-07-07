"""
Repository 레이어 규칙 (nickname_repository.py와 동일): 데이터 저장/조회만 안다.
실제 위치: app/repositories/chat_repository.py — 실제로는 SQLAlchemy AsyncSession으로 교체됨.
"""

_FAKE_CHAT_LOG: list[dict] = []


class ChatRepository:
    def save_message(self, session_id: int, message: str, response: str) -> None:
        _FAKE_CHAT_LOG.append({"session_id": session_id, "message": message, "response": response})

    def history_for(self, session_id: int) -> list[dict]:
        return [row for row in _FAKE_CHAT_LOG if row["session_id"] == session_id]
