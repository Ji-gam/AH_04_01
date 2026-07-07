"""
가짜(Fake) Repository로 격리한 단위테스트 (test_nickname_service.py와 같은 패턴).
"""

from app.dtos.recognition import Severity

from app.services.recognition_service import RecognitionService


class FakeInteractionRuleRepository:
    def __init__(self, rules: list[dict] | None = None) -> None:
        self._rules = rules or []

    def find_by_keyword(self, keyword: str) -> dict | None:
        for rule in self._rules:
            if rule.get("keyword") == keyword:
                return rule
        return None

    def find_all_for_drug(self, drug_name: str) -> list[dict]:
        return self._rules


def test_상호작용_규칙이_있으면_해당_카드를_반환한다():
    fake_repo = FakeInteractionRuleRepository(
        rules=[{"title": "이 약과 자몽주스", "content": "주의 필요", "severity": "warning"}]
    )
    service = RecognitionService(repository=fake_repo)

    cards = service.generate_guide_cards("타크로리무스")

    assert len(cards) == 1
    assert cards[0].severity == Severity.WARNING
    assert cards[0].title == "이 약과 자몽주스"


def test_상호작용_규칙이_없어도_안내카드_하나는_반드시_반환한다():
    """T-LLM-1 원칙: 면책조항 노출을 위해 빈 배열을 절대 반환하지 않는다."""
    fake_repo = FakeInteractionRuleRepository(rules=[])
    service = RecognitionService(repository=fake_repo)

    cards = service.generate_guide_cards("타이레놀")

    assert len(cards) == 1
    assert cards[0].severity == Severity.INFO


def test_모든_카드는_disclaimer_기본값을_가진다():
    fake_repo = FakeInteractionRuleRepository(rules=[])
    service = RecognitionService(repository=fake_repo)

    cards = service.generate_guide_cards("타이레놀")

    assert cards[0].disclaimer != ""
