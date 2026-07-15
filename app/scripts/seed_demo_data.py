"""
습관 트래커 개발/테스트용 더미 데이터 시딩 스크립트.

진단명/세부진단명 유무가 다른 데모 계정 3개를 만들고, 각각 최근 10일치 습관 선택·체크
이력을 채워 넣는다. "오늘의 추천 습관"과 향후 건강분석 페이지에서 쓸 누적 이력을, 앱을
직접 며칠씩 써보지 않고도 바로 화면에서 확인할 수 있게 하기 위한 개발 편의용 스크립트다.

이미 존재하는 이메일(재실행 시 등)은 새로 만들지 않고 건너뛴다 - 안전하게 여러 번 실행 가능.
습관 이력은 과거 날짜라 오늘자 추천 풀 검증(select_habits())을 거치지 않는 raw insert이므로,
habit_key는 항상 유효한 정적 폴백 키(DISEASE_HABITS/BASE_HABITS)만 사용한다 - LLM(subtype_*)
습관은 실제 사용 시 AIWorkerGateway 호출로 그때그때 생기는 것이라 시딩 대상이 아니다.

실행: uv run python -m app.scripts.seed_demo_data
"""

import asyncio
import random
from datetime import date, timedelta
from typing import TypedDict

from app.core.db.databases import AsyncSessionLocal
from app.dtos.auth import SignUpRequest
from app.models.disease_entries import DiagnosisEntry
from app.models.habit_logs import HabitLog
from app.models.habit_selections import HabitSelection
from app.models.profiles import Disease, Profile
from app.repositories.disease_entry_repository import DiagnosisEntryRepository, DiseaseSubtypeRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.auth import AuthService

DEMO_PASSWORD = "Demo1234!"
HISTORY_DAYS = 10


class DemoProfileSpec(TypedDict):
    email: str
    name: str
    disease: Disease | None
    disease_subtype: str | None
    habit_keys: list[str]  # 목표치는 habit_service.BASE_HABITS/DISEASE_HABITS 기준(5=물마시기, 나머진 1)


DEMO_PROFILES: list[DemoProfileSpec] = [
    {
        "email": "demo1@example.com",
        "name": "데모_당뇨",
        "disease": Disease.DIABETES,
        "disease_subtype": "제2형 당뇨병",
        "habit_keys": ["water", "walk", "diabetes_walk"],
    },
    {
        "email": "demo2@example.com",
        "name": "데모_심장질환",
        "disease": Disease.HEART_DISEASE,
        "disease_subtype": "협심증",
        "habit_keys": ["water", "heart_low_salt"],
    },
    {
        "email": "demo3@example.com",
        "name": "데모_무진단",
        "disease": None,
        "disease_subtype": None,
        "habit_keys": ["water", "walk"],
    },
]

_HABIT_TARGETS = {"water": 5}  # 명시 안 된 키는 전부 target=1(habit_service.py의 기본/질환 습관과 동일)


async def _get_or_create_demo_profile(session, spec: DemoProfileSpec) -> tuple[Profile, bool]:
    user_repo = UserRepository()
    existing_user = await user_repo.get_user_by_email(session, spec["email"])
    if existing_user is not None:
        profile = await ProfileRepository().get_default_profile_for_user(session, existing_user.id)
        assert profile is not None  # 회원가입 시 SELF 프로필이 항상 같이 생기므로 존재가 보장된다
        return profile, False

    _, profile = await AuthService().signup(
        session,
        SignUpRequest(email=spec["email"], password=DEMO_PASSWORD, name=spec["name"]),
    )
    return profile, True


async def _seed_diagnosis(session, profile: Profile, spec: DemoProfileSpec) -> None:
    if spec["disease"] is None:
        return
    subtype = None
    if spec["disease_subtype"]:
        subtype = await DiseaseSubtypeRepository().get_or_create(session, spec["disease"], spec["disease_subtype"])
    await DiagnosisEntryRepository().replace_all_for_profile(
        session,
        profile.id,
        [DiagnosisEntry(disease=spec["disease"], disease_subtype_id=subtype.id if subtype else None)],
    )


async def _seed_habit_history(session, profile: Profile, habit_keys: list[str]) -> None:
    today = date.today()
    for days_ago in range(1, HISTORY_DAYS + 1):
        log_date = today - timedelta(days=days_ago)
        # 매일 다 채우면 부자연스러우니, 하루 정도는 하나도 안 한 날도 섞는다(현실적인 이력).
        if random.random() < 0.15:
            continue
        session.add_all(HabitSelection(profile_id=profile.id, select_date=log_date, habit_key=key) for key in habit_keys)
        for key in habit_keys:
            target = _HABIT_TARGETS.get(key, 1)
            progress = random.randint(0, target)  # 매일 목표를 다 채우진 못했을 수도 있는 현실적인 분포
            session.add(HabitLog(profile_id=profile.id, log_date=log_date, habit_key=key, progress=progress))
    await session.flush()


async def seed_demo_data() -> list[str]:
    created_emails: list[str] = []
    async with AsyncSessionLocal() as session:
        for spec in DEMO_PROFILES:
            profile, is_new = await _get_or_create_demo_profile(session, spec)
            if not is_new:
                continue
            await _seed_diagnosis(session, profile, spec)
            await _seed_habit_history(session, profile, spec["habit_keys"])
            await session.commit()
            created_emails.append(spec["email"])
    return created_emails


async def _main() -> None:
    created = await seed_demo_data()
    if created:
        print(f"{len(created)}개 데모 계정 생성 완료 (비밀번호: {DEMO_PASSWORD}): {', '.join(created)}")
    else:
        print("이미 모든 데모 계정이 존재합니다 - 새로 만든 것 없음.")


if __name__ == "__main__":
    asyncio.run(_main())
