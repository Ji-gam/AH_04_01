"""
개발/테스트용 더미 데이터 시딩 스크립트.

진단명/세부진단명 유무가 다른 데모 계정 3개를 만들고, 각각 다음 데이터를 채워 넣는다:
- 최근 10일치 습관 선택·체크 이력 (습관 트래커)
- 복약 스케줄 + 복약 알림 설정
- AI 상담 대화 기록(질문/답변 미리 작성 - 실제 LLM 호출 없음)
- 세부진단명별 습관 캐시(더미 값 - 실제 AIWorkerGateway 호출 없음)

앱을 직접 며칠씩 써보지 않아도 각 기능의 "데이터가 쌓인 상태" 화면을 바로 확인할 수 있게
하기 위한 개발 편의용 스크립트다. 외부 API/LLM 호출이 필요한 것(알약 인식 OCR, 약물
상호작용 캐시)은 일부러 포함하지 않았다 - 실제 흐름을 그럴듯하게 흉내내려면 별도 설계가
필요해서, 팀 논의 후 필요하면 추가하기로 함.

이미 존재하는 이메일(재실행 시 등)은 새로 만들지 않고 건너뛴다 - 안전하게 여러 번 실행 가능.
습관 이력은 과거 날짜라 오늘자 추천 풀 검증(select_habits())을 거치지 않는 raw insert이므로,
habit_key는 항상 유효한 정적 폴백 키(DISEASE_HABITS/BASE_HABITS)만 사용한다.

실행: uv run python -m app.scripts.seed_demo_data
"""

import asyncio
import random
from datetime import date, time, timedelta
from typing import TypedDict

from sqlalchemy import select

from app.core.db.databases import AsyncSessionLocal
from app.dtos.auth import SignUpRequest
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.disease_entries import DiagnosisEntry
from app.models.habit_logs import HabitLog
from app.models.habit_selections import HabitSelection
from app.models.habit_subtype_suggestions import HabitSubtypeSuggestion
from app.models.medication_model import Medication, MedicationSchedule
from app.models.notification_schedules import FrequencyType, NotificationSchedule
from app.models.profiles import Disease, Profile
from app.repositories.disease_entry_repository import DiagnosisEntryRepository, DiseaseSubtypeRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.auth import AuthService

DEMO_PASSWORD = "Demo1234!"
HISTORY_DAYS = 10


class MedicationSpec(TypedDict):
    medication_name: str
    form_type: str
    dosage_guideline: str
    times: list[str]


class ChatTurn(TypedDict):
    question: str
    answer: str


class SubtypeHabitSpec(TypedDict):
    label: str
    icon: str
    unit: str
    target: int


class DemoProfileSpec(TypedDict):
    email: str
    name: str
    disease: Disease | None
    disease_subtype: str | None
    subtype_habits: list[SubtypeHabitSpec]  # 세부진단명이 있을 때만 사용(더미 LLM 습관 캐시, 최대 5개)
    habit_keys: list[str]  # 목표치는 habit_service.BASE_HABITS/DISEASE_HABITS 기준(5=물마시기, 나머진 1)
    medication: MedicationSpec
    chat_turns: list[ChatTurn]


DEMO_PROFILES: list[DemoProfileSpec] = [
    {
        "email": "demo1@example.com",
        "name": "데모_당뇨",
        "disease": Disease.DIABETES,
        "disease_subtype": "제2형 당뇨병",
        "subtype_habits": [
            {"label": "식후 30분 걷기", "icon": "🚶", "unit": "분", "target": 30},
            {"label": "혈당 체크하기", "icon": "🩺", "unit": "회", "target": 1},
            {"label": "저염식 식사하기", "icon": "🥗", "unit": "회", "target": 1},
            {"label": "스트레스 줄이기", "icon": "🧘", "unit": "회", "target": 1},
            {"label": "물 충분히 마시기", "icon": "💧", "unit": "잔", "target": 8},
        ],
        "habit_keys": ["water", "walk", "diabetes_walk"],
        "medication": {
            "medication_name": "메트포르민정",
            "form_type": "TABLET",
            "dosage_guideline": "1일 2회, 아침·저녁 식후 복용",
            "times": ["08:00", "19:00"],
        },
        "chat_turns": [
            {
                "question": "혈당 관리에 좋은 습관이 있을까요?",
                "answer": "식후 30분 이내 가벼운 걷기가 혈당 스파이크를 줄이는 데 도움이 됩니다. 규칙적인 식사 시간도 중요해요.",
            },
            {
                "question": "약을 깜빡하고 못 먹었어요, 어떻게 하나요?",
                "answer": "생각난 즉시 복용하되, 다음 복용 시간이 가까우면 그냥 건너뛰고 다음 시간에 정량만 복용하세요. 두 배로 복용하지 마세요.",
            },
        ],
    },
    {
        "email": "demo2@example.com",
        "name": "데모_심장질환",
        "disease": Disease.HEART_DISEASE,
        "disease_subtype": "협심증",
        "subtype_habits": [
            {"label": "저염식 챙기기", "icon": "🧂", "unit": "회", "target": 1},
            {"label": "매일 30분 걷기", "icon": "🚶", "unit": "분", "target": 30},
            {"label": "스트레스 관리하기", "icon": "🧘", "unit": "회", "target": 1},
            {"label": "금연 실천하기", "icon": "🚭", "unit": "회", "target": 1},
            {"label": "혈압 체크하기", "icon": "🩺", "unit": "회", "target": 1},
        ],
        "habit_keys": ["water", "heart_low_salt"],
        "medication": {
            "medication_name": "아스피린장용정",
            "form_type": "TABLET",
            "dosage_guideline": "1일 1회, 아침 식후 복용",
            "times": ["08:00"],
        },
        "chat_turns": [
            {
                "question": "가슴 답답함이 있을 때 바로 병원에 가야 하나요?",
                "answer": "5분 이상 지속되는 흉통, 팔·턱으로 퍼지는 통증, 식은땀이 동반되면 즉시 응급실을 방문하세요. 경미하더라도 반복된다면 진료를 받아보세요.",
            },
        ],
    },
    {
        "email": "demo3@example.com",
        "name": "데모_무진단",
        "disease": None,
        "disease_subtype": None,
        "subtype_habits": [],
        "habit_keys": ["water", "walk"],
        "medication": {
            "medication_name": "종합비타민정",
            "form_type": "TABLET",
            "dosage_guideline": "1일 1회, 아침 식후 복용",
            "times": ["09:00"],
        },
        "chat_turns": [
            {
                "question": "하루 물은 얼마나 마셔야 하나요?",
                "answer": "일반적으로 하루 1.5~2L(8잔 정도)를 권장해요. 활동량이나 체중에 따라 조절하시면 됩니다.",
            },
        ],
    },
]

_HABIT_TARGETS = {"water": 8, "walk": 20}  # habit_service.py의 BASE_HABITS 목표치와 맞춤 - 나머진 전부 target=1


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


async def _seed_diagnosis(session, profile: Profile, spec: DemoProfileSpec) -> int | None:
    """진단을 등록하고, 세부진단명이 있으면 그 disease_subtype_id를 반환한다(습관 캐시 시딩용)."""
    if spec["disease"] is None:
        return None
    subtype = None
    if spec["disease_subtype"]:
        subtype = await DiseaseSubtypeRepository().get_or_create(session, spec["disease"], spec["disease_subtype"])
    await DiagnosisEntryRepository().replace_all_for_profile(
        session,
        profile.id,
        [DiagnosisEntry(disease=spec["disease"], disease_subtype_id=subtype.id if subtype else None)],
    )
    return subtype.id if subtype else None


async def _seed_subtype_habit_cache(session, disease_subtype_id: int, specs: list[SubtypeHabitSpec]) -> None:
    """실제 AIWorkerGateway를 호출하지 않고, 진단명별 습관 캐시(habit_subtype_suggestions)에
    더미 값을 슬롯 0부터 최대 5개까지 미리 넣어둔다 - 데모 계정으로 추천 목록을 열어봐도
    ai_worker 없이 바로 뜬다. 이미 캐시가 있으면(실제 사용 중 생성됐을 수도 있음) 건드리지
    않는다 - (disease_subtype_id, slot) unique 제약 위반 방지. 한 진단명당 여러 슬롯이 있을
    수 있어 first()로 존재만 확인한다(scalar_one_or_none은 슬롯이 2개 이상이면 예외를 던진다)."""
    result = await session.execute(
        select(HabitSubtypeSuggestion).where(HabitSubtypeSuggestion.disease_subtype_id == disease_subtype_id)
    )
    if result.scalars().first() is not None:
        return
    session.add_all(
        HabitSubtypeSuggestion(
            disease_subtype_id=disease_subtype_id,
            slot=slot,
            label=spec["label"],
            icon=spec["icon"],
            unit=spec["unit"],
            target=spec["target"],
        )
        for slot, spec in enumerate(specs)
    )


async def _seed_habit_history(session, profile: Profile, habit_keys: list[str]) -> None:
    today = date.today()
    for days_ago in range(1, HISTORY_DAYS + 1):
        log_date = today - timedelta(days=days_ago)
        # 매일 다 채우면 부자연스러우니, 하루 정도는 하나도 안 한 날도 섞는다(현실적인 이력).
        if random.random() < 0.15:
            continue
        session.add_all(
            HabitSelection(profile_id=profile.id, select_date=log_date, habit_key=key) for key in habit_keys
        )
        for key in habit_keys:
            target = _HABIT_TARGETS.get(key, 1)
            progress = random.randint(0, target)  # 매일 목표를 다 채우진 못했을 수도 있는 현실적인 분포
            session.add(HabitLog(profile_id=profile.id, log_date=log_date, habit_key=key, progress=progress))


async def _get_or_create_medication(session, spec: MedicationSpec) -> Medication:
    result = await session.execute(select(Medication).where(Medication.medication_name == spec["medication_name"]))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    medication = Medication(
        medication_name=spec["medication_name"],
        form_type=spec["form_type"],
        dosage_guideline=spec["dosage_guideline"],
    )
    session.add(medication)
    await session.flush()
    return medication


async def _seed_medication_and_alarm(session, profile: Profile, spec: MedicationSpec) -> None:
    medication = await _get_or_create_medication(session, spec)
    session.add(MedicationSchedule(profile_id=profile.id, medication_id=medication.id, times=spec["times"]))
    for alarm in spec["times"]:
        hour, minute = (int(part) for part in alarm.split(":"))
        session.add(
            NotificationSchedule(
                profile_id=profile.id,
                medication_name=spec["medication_name"],
                frequency_type=FrequencyType.DAILY,
                alarm_time=time(hour, minute),
            )
        )


async def _seed_chat_history(session, profile: Profile, turns: list[ChatTurn]) -> None:
    if not turns:
        return
    chat_session = ChatSession(profile_id=profile.id)
    session.add(chat_session)
    await session.flush()
    for turn in turns:
        session.add(ChatMessage(session_id=chat_session.id, role=MessageRole.USER, content=turn["question"]))
        session.add(ChatMessage(session_id=chat_session.id, role=MessageRole.ASSISTANT, content=turn["answer"]))


async def seed_demo_data() -> list[str]:
    created_emails: list[str] = []
    async with AsyncSessionLocal() as session:
        for spec in DEMO_PROFILES:
            profile, is_new = await _get_or_create_demo_profile(session, spec)
            if not is_new:
                continue
            subtype_id = await _seed_diagnosis(session, profile, spec)
            if subtype_id is not None and spec["subtype_habits"]:
                await _seed_subtype_habit_cache(session, subtype_id, spec["subtype_habits"])
            await _seed_habit_history(session, profile, spec["habit_keys"])
            await _seed_medication_and_alarm(session, profile, spec["medication"])
            await _seed_chat_history(session, profile, spec["chat_turns"])
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
