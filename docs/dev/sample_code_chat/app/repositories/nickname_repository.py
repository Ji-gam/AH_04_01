"""
Repository 레이어 규칙:
- 여기는 오직 '데이터를 어떻게 저장/조회하는지'만 안다.
- 여기서 절대 하면 안 되는 것: 비즈니스 판단(if 중복이면 어떻게 할지 등), 응답 포맷 결정
- 나중에 실제 MySQL(SQLAlchemy)로 바꿀 때, 이 파일 내부 구현만 바꾸면 되고
  Service/Router 코드는 한 줄도 안 바꿔도 되는 게 이 레이어를 분리하는 이유다.
"""

# 데모용 인메모리 저장소 (실제로는 SQLAlchemy AsyncSession으로 교체됨)
_FAKE_NICKNAME_DB: set[str] = {"admin", "관리자", "테스트"}


class NicknameRepository:
    def exists(self, nickname: str) -> bool:
        return nickname in _FAKE_NICKNAME_DB

    def save(self, nickname: str) -> None:
        _FAKE_NICKNAME_DB.add(nickname)
