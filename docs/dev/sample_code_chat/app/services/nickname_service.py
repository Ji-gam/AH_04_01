"""
Service 레이어 규칙:
- 여기가 '판단'이 일어나는 유일한 곳이다 (검증, 조건 분기, 여러 Repository 조합 등).
- 여기서 절대 하면 안 되는 것: SQL/쿼리 직접 작성(Repository만 호출), HTTP 관련 코드(status_code 등)
- Router는 이 Service의 함수만 호출한다. Service 내부가 어떻게 구현됐는지 Router는 몰라도 된다.
"""

from app.repositories.nickname_repository import NicknameRepository


class NicknameService:
    def __init__(self, repository: NicknameRepository | None = None) -> None:
        # 의존성 주입: 테스트할 때 가짜 Repository로 교체하기 쉽게 만드는 패턴
        self._repository = repository or NicknameRepository()

    def is_available(self, nickname: str) -> bool:
        normalized = nickname.strip().lower()
        if len(normalized) < 2:
            # 비즈니스 규칙: 2자 미만 닉네임은 애초에 사용 불가 처리
            return False
        return not self._repository.exists(normalized)
