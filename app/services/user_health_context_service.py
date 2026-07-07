"""
공통모듈 — 질병/복약/목표 조회 단일창구(`docs/decision_log.md` "공통 모듈" 표).
복약/목표 도메인이 아직 없어 Tier 2 stub으로 채운다(`docs/CODING_RULES.md` 8번).
해당 도메인이 생기면 이 클래스 내부만 실제 조회 로직으로 교체한다.
"""


class UserHealthContextService:
    def get_context(self, profile_id: int) -> dict:
        return {"conditions": [], "medications": [], "goals": [], "profile_id": profile_id}
