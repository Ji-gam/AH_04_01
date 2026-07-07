"""
Service 레이어 규칙 (nickname_service.py와 동일):
- 판단은 여기서만 한다. Router는 이 함수만 부르고 내부 구현은 몰라도 된다.
실제 위치: app/services/recognition_service.py (공통모듈③, CODING_RULES.md 2번)

이 파일이 바로 CODING_RULES.md 6번(Tier 2 stub 패턴)의 실제 예시다.
아래 generate_guide_cards() 안의 TODO 주석이 'RAG 완성 후 정확히 무엇을 바꿔야 하는지'를 보여준다.
"""

from app.dtos.recognition import GuideCard, Severity
from app.repositories.interaction_rule_repository import InteractionRuleRepository


class RecognitionService:
    def __init__(self, repository: InteractionRuleRepository | None = None) -> None:
        self._repository = repository or InteractionRuleRepository()

    def generate_guide_cards(self, drug_name: str) -> list[GuideCard]:
        """
        T-DOC-2: 확정된 약품에 대한 시너지/부작용 안내 카드 생성.

        ⚠ 지금은 Tier 2 stub 구현이다 (decision_log.md 참고).
        RAG 완성 후 아래 라인만 바꾸면 된다:

            rules = self._repository.find_all_for_drug(drug_name)
            ↓ 이렇게 교체
            chunks = retriever.search(query=drug_name, context={"type": "drug_interaction"})
            rules = [chunk_to_rule(c) for c in chunks]

        Router/Schema(GuideCard)는 그대로 유지되므로 프론트/API 명세는 변경 없음.
        """
        rules = self._repository.find_all_for_drug(drug_name)

        if not rules:
            # 규칙이 하나도 없어도 빈 배열이 아니라 "특이사항 없음" 카드를 반환한다.
            # (T-LLM-1 원칙: 면책조항은 항상 노출되어야 하므로 아무것도 안 보내는 건 안 됨)
            return [
                GuideCard(
                    title="확인된 상호작용 없음",
                    content=f"{drug_name}에 대해 현재 등록된 주의사항이 없습니다.",
                    severity=Severity.INFO,
                )
            ]

        return [
            GuideCard(
                title=rule["title"],
                content=rule["content"],
                severity=Severity(rule["severity"]),
            )
            for rule in rules
        ]
