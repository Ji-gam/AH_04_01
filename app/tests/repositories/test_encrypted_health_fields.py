"""건강정보 텍스트 필드 DB 암호화(EncryptedText) 검증.

[배경] 개인정보보호법 제23조(민감정보) 대응으로 Profile.special_notes/other_notes,
DiagnosisEntry.detail, FamilyHistoryEntry.detail을 DB 레벨에서 암호화했다(2026-07-21).
이 테스트가 특히 중요하게 확인하는 것: 암호화 적용 전 전체 코드를 grep해서 찾아낸
"암호화하면 절대 안 되는 필드" 2개(DiagnosisEntry.disease - 라이프스타일 콘텐츠 알림
발송 대상을 SQL로 직접 필터링, Profile.phone_number - 회원가입 시 중복확인 SQL 조회)가
암호화 도입 이후에도 여전히 정상 동작하는지 - 이게 깨지면 조용히(에러 없이) 기능이
망가지므로 회귀 테스트로 반드시 남겨둔다."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, text

import app.models  # noqa: F401 - 전체 모델 등록 보장
from app.core import config
from app.models.disease_entries import DiagnosisEntry, FamilyHistoryEntry
from app.models.health_profiles import HealthProfile
from app.models.profiles import Disease, Profile
from app.models.users import User
from app.repositories.disease_entry_repository import DiagnosisEntryRepository
from app.repositories.profile_repository import ProfileRepository
from app.tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _field_encryption_key():
    """이 테스트 파일 안에서만 암호화 키를 설정한다 - 다른 테스트에 영향 안 가게
    끝나면 원래 값(None, 로컬 개발 기본값)으로 되돌린다."""
    original = config.FIELD_ENCRYPTION_KEY
    config.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")
    yield
    config.FIELD_ENCRYPTION_KEY = original


async def _create_user_and_profile(session, email: str) -> Profile:
    """[2026-07-29 PII/건강정보 분리] special_notes/other_notes는 이제 Profile이 아니라
    HealthProfile에 있다 - 이 테스트가 필요로 하는 health_profile도 같이 만들어둔다."""
    user = User(email=email, hashed_password="x")
    session.add(user)
    await session.flush()
    profile = Profile(user_id=user.id, name="테스트")
    profile.health_profile = HealthProfile()
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def test_encrypted_field_stores_ciphertext_but_reads_back_plaintext():
    """ORM으로 평문을 저장하면, DB에는 암호문이 저장되지만(raw SQL로 확인) ORM으로
    다시 읽으면 평문 그대로 보인다(투명 복호화) - EncryptedText의 핵심 동작.
    [2026-07-29] special_notes는 이제 health_profiles 테이블에 있다."""
    async with TestSessionLocal() as session:
        profile = await _create_user_and_profile(session, "encrypt_roundtrip@example.com")
        profile.health_profile.special_notes = "땅콩 알레르기 있음"
        await session.commit()

        raw = await session.execute(
            text("SELECT special_notes FROM health_profiles WHERE profile_id = :id"), {"id": profile.id}
        )
        raw_value = raw.scalar_one()
        assert raw_value != "땅콩 알레르기 있음", "DB에 평문 그대로 저장됨 - 암호화가 전혀 안 됨"
        assert "땅콩" not in raw_value, "DB에 평문 일부가 그대로 노출됨"

        await session.refresh(profile, attribute_names=["health_profile"])
        await session.refresh(profile.health_profile)
        assert profile.health_profile.special_notes == "땅콩 알레르기 있음"


async def test_diagnosis_detail_encrypted_but_disease_stays_queryable_by_sql():
    """DiagnosisEntry.detail(암호화 대상)은 암호화되면서도, disease(암호화 제외 대상)는
    여전히 SQL WHERE절로 정확히 필터링돼야 한다 - list_profile_ids_by_disease()가
    content_notification_service.py(라이프스타일 알림 발송 대상 선정)에서 실제로 이
    방식을 쓰고 있어서, 이게 깨지면 그 기능이 조용히 0건이 된다."""
    async with TestSessionLocal() as session:
        profile = await _create_user_and_profile(session, "disease_filter@example.com")
        entry = DiagnosisEntry(
            profile_id=profile.id,
            disease=Disease.DIABETES,
            detail="2019년 진단, 인슐린 사용중",
        )
        session.add(entry)
        await session.commit()

        # detail(암호화 대상)이 DB엔 암호문으로 있는지
        raw = await session.execute(
            text("SELECT detail FROM diagnosis_entries WHERE profile_id = :pid"), {"pid": profile.id}
        )
        raw_detail = raw.scalar_one()
        assert "인슐린" not in raw_detail

        # disease(암호화 제외 대상)로 SQL 필터링이 여전히 정상 동작하는지
        repo = DiagnosisEntryRepository()
        ids = await repo.list_profile_ids_by_disease(session, Disease.DIABETES)
        assert profile.id in ids, "disease로 SQL 필터링이 깨짐 - 암호화 대상에서 반드시 제외됐어야 하는 필드"


async def test_family_history_detail_encrypted():
    """FamilyHistoryEntry.detail도 같은 방식으로 암호화되는지 확인."""
    async with TestSessionLocal() as session:
        profile = await _create_user_and_profile(session, "family_history@example.com")
        entry = FamilyHistoryEntry(
            profile_id=profile.id,
            disease=Disease.CANCER,
            detail="어머니 유방암 진단",
        )
        session.add(entry)
        await session.commit()

        raw = await session.execute(
            text("SELECT detail FROM family_history_entries WHERE profile_id = :pid"), {"pid": profile.id}
        )
        assert "유방암" not in raw.scalar_one()

        session.expire(entry)
        reloaded = (
            await session.execute(select(FamilyHistoryEntry).where(FamilyHistoryEntry.profile_id == profile.id))
        ).scalar_one()
        assert reloaded.detail == "어머니 유방암 진단"


async def test_phone_number_stays_queryable_by_sql_for_signup_duplicate_check():
    """Profile.phone_number(암호화 제외 대상)로 SQL 조회가 여전히 정상 동작하는지 확인 -
    auth.py의 회원가입 중복확인(exists_by_phone_number)이 이 방식을 쓰고 있어서, 이게
    깨지면 중복확인이 항상 실패(또는 항상 통과)하게 된다."""
    async with TestSessionLocal() as session:
        await _create_user_and_profile(session, "phone_check@example.com")
        profile = (await session.execute(select(Profile).where(Profile.user_id.isnot(None)).limit(1))).scalars().first()
        assert profile is not None
        profile.phone_number = "01099998888"
        await session.commit()

        repo = ProfileRepository()
        exists = await repo.exists_by_phone_number(session, "01099998888")
        assert exists is True, "phone_number로 SQL 조회가 깨짐 - 암호화 대상에서 반드시 제외됐어야 하는 필드"
        not_exists = await repo.exists_by_phone_number(session, "01000000000")
        assert not_exists is False


async def test_encryption_is_off_when_key_not_configured(monkeypatch):
    """FIELD_ENCRYPTION_KEY가 설정 안 된 상태(로컬 개발 초기 등)에서는, 평문 그대로
    저장/조회돼서 기존 동작과 100% 동일해야 한다(하위호환). [2026-07-29] other_notes는
    이제 health_profiles 테이블에 있다."""
    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", None)
    async with TestSessionLocal() as session:
        profile = await _create_user_and_profile(session, "no_key@example.com")
        profile.health_profile.other_notes = "키 없을 때 평문 테스트"
        await session.commit()

        raw = await session.execute(
            text("SELECT other_notes FROM health_profiles WHERE profile_id = :id"), {"id": profile.id}
        )
        assert raw.scalar_one() == "키 없을 때 평문 테스트", "키 미설정 시에도 암호화되어버림 - 하위호환 깨짐"
