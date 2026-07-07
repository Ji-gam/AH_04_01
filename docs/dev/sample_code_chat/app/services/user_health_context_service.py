"""
공통② 질병/복약/목표 조회 단일창구 데모. T-LLM-2, T-GOAL-2, T-GUIDE-1, T-ADH-2가 사용.
실제 위치: app/services/user_health_context_service.py — 공통모듈이므로 소유자 지정 필요 (`docs/squad-map.md`).

CODING_RULES.md 2-1: 사용자 관련 조회는 profile_id 기준으로 한다 (user_id 아님).
"""


class UserHealthContextService:
    def __init__(self, repository: object | None = None) -> None:
        self._repository = repository

    def get_context(self, profile_id: int) -> dict:
        # TODO: 실제 repository 연결 시 질병/복약/목표/최근 대화요약을 조회해 채운다.
        return {"conditions": [], "medications": [], "goals": [], "profile_id": profile_id}
