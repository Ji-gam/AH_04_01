"""
Repository 레이어 규칙 (nickname_repository.py와 동일):
- 여기는 '데이터를 어디서 가져오는지'만 안다. 판단은 Service가 한다.

⚠ Tier 2 stub 전용 파일이다 (decision_log.md 참고).
지금은 하드코딩된 규칙 몇 개만 가진 가짜 저장소지만,
RAG가 완성되면 이 클래스를 통째로 안 쓰고
Service가 대신 rag.retriever.Retriever를 호출하도록 바뀐다.
Router는 이 교체를 전혀 몰라도 된다 — 이게 계층 분리의 요점이다.
"""

# 데모용 하드코딩 규칙 (실제로는 DUR 데이터 기반으로 훨씬 커질 수 있음)
_FAKE_INTERACTION_RULES: dict[str, dict] = {
    "자몽주스": {
        "title": "이 약과 자몽주스",
        "content": "일부 약물은 자몽주스와 함께 복용 시 혈중 농도가 비정상적으로 높아질 수 있습니다.",
        "severity": "warning",
    },
    "카페인": {
        "title": "이 약과 카페인",
        "content": "카페인과 함께 복용하면 심박수 증가 등의 부작용이 강해질 수 있습니다.",
        "severity": "caution",
    },
}


class InteractionRuleRepository:
    def find_by_keyword(self, keyword: str) -> dict | None:
        return _FAKE_INTERACTION_RULES.get(keyword)

    def find_all_for_drug(self, drug_name: str) -> list[dict]:
        # Tier 2 stub 단순화: 실제로는 drug_name 기반 매핑 테이블을 조회해야 하지만
        # 데모에서는 항상 동일한 규칙 세트를 리턴한다.
        return list(_FAKE_INTERACTION_RULES.values())
