from sqlalchemy import select

from app.models.disease_entries import DiseaseSubtype
from app.models.profiles import Disease
from app.repositories.habit_repository import HabitRepository
from app.tests.conftest import TestSessionLocal


async def _seeded_subtype_id(session) -> int:
    result = await session.execute(select(DiseaseSubtype).where(DiseaseSubtype.category == Disease.HEART_DISEASE))
    return result.scalars().first().id


async def test_save_subtype_suggestions_recovers_from_concurrent_insert_conflict():
    """캐시 미스 판단과 저장 사이엔 잠금이 없어, 같은 진단명에 대한 두 요청이 동시에 캐시가
    비어있는 걸 보고 둘 다 저장을 시도할 수 있다(PR #168 리뷰에서 프론트가 GET /habits/
    recommendations와 GET /habits/today를 Promise.all로 동시 호출해 실제로 재현된 500 에러).
    늦게 커밋을 시도하는 쪽은 (disease_subtype_id, slot) unique 제약 위반으로 실패하지만,
    예외를 그대로 던지는 대신 먼저 저장된 값을 재조회해서 반환해야 한다.

    save_subtype_suggestions()는 독립된 세션을 직접 여는데(REPEATABLE READ 재조회 문제 회피),
    운영 코드와 같은 ai_health DB가 아니라 격리된 test DB를 쓰도록 TestSessionLocal을
    주입한다."""
    repo = HabitRepository(session_factory=TestSessionLocal)
    async with TestSessionLocal() as session:
        subtype_id = await _seeded_subtype_id(session)

    winner = await repo.save_subtype_suggestions(
        subtype_id, [{"label": "먼저 저장된 습관", "icon": "🥇", "unit": "회", "target": 1}]
    )
    # "늦게 도착한 요청"을 흉내낸다 - 캐시(슬롯 0)가 이미 채워진 뒤에 저장을 시도.
    loser = await repo.save_subtype_suggestions(
        subtype_id, [{"label": "늦게 도착한 요청이 만든 습관", "icon": "🥈", "unit": "회", "target": 1}]
    )

    assert loser[0].label == winner[0].label == "먼저 저장된 습관"
