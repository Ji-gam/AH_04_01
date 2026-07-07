"""
TDD 규칙:
- Service 함수 하나당 최소 2개 테스트: '정상 케이스' + '실패/경계 케이스'
- 단위테스트는 진짜 DB를 쓰지 않는다 — 가짜(Fake) Repository를 주입해서 Service 로직만 검증한다.
  (진짜 DB까지 테스트하고 싶으면 별도로 '통합테스트'를 만든다. 이 파일은 순수 단위테스트.)
"""

from app.services.nickname_service import NicknameService


class FakeNicknameRepository:
    """테스트 전용 가짜 Repository. 실제 DB 없이 동작을 흉내낸다."""

    def __init__(self, existing: set[str] | None = None) -> None:
        self._existing = existing or set()

    def exists(self, nickname: str) -> bool:
        return nickname in self._existing

    def save(self, nickname: str) -> None:
        self._existing.add(nickname)


def test_새로운_닉네임은_사용가능하다():
    # Arrange
    fake_repo = FakeNicknameRepository(existing=set())
    service = NicknameService(repository=fake_repo)

    # Act
    result = service.is_available("새로운닉네임")

    # Assert
    assert result is True


def test_이미_존재하는_닉네임은_사용불가하다():
    # Arrange
    fake_repo = FakeNicknameRepository(existing={"서현"})
    service = NicknameService(repository=fake_repo)

    # Act
    result = service.is_available("서현")

    # Assert
    assert result is False


def test_대소문자만_다른_닉네임도_중복으로_처리한다():
    fake_repo = FakeNicknameRepository(existing={"seohyun"})
    service = NicknameService(repository=fake_repo)

    assert service.is_available("SeoHyun") is False


def test_2자_미만_닉네임은_거부한다():
    fake_repo = FakeNicknameRepository(existing=set())
    service = NicknameService(repository=fake_repo)

    assert service.is_available("a") is False
