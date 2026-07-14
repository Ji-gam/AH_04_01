import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import config
from app.core.db import databases
from app.main import app
from app.models.base import Base
from app.models.disease_entries import SEED_DISEASE_SUBTYPES, DiseaseSubtype

TEST_DATABASE_URL = f"mysql+asyncmy://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/test"

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # [주의] 테스트 DB는 마이그레이션이 아니라 위 create_all로 스키마만 만들어져서, 마이그레이션
    # 0015 안에 있던 disease_subtypes 시드 INSERT문이 여기엔 안 들어간다. 원티드 스킬태그 검색을
    # 검증하는 테스트들이 이 시드 데이터를 전제로 하므로 여기서 한 번 더 심어준다.
    async with TestSessionLocal() as session:
        for category, names in SEED_DISEASE_SUBTYPES.items():
            for name in names:
                session.add(DiseaseSubtype(category=category, name=name, is_custom=False))
        await session.commit()

    yield
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def override_get_db():
    async def _get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[databases.get_db] = _get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with TestSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            # disease_subtypes는 시드 참조데이터라 테스트 사이에 지우지 않는다 - 지우면 매번
            # 새로 심어야 하고, "같은 이름 중복 안 생김" 테스트도 다른 테스트가 남긴 잔여 데이터와
            # 뒤섞여 깨질 수 있다.
            if table.name == "disease_subtypes":
                continue
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture(autouse=True)
def _no_real_external_api_keys_in_tests(monkeypatch):
    """로컬 `.env`에 실제 발급받은 키(OPENAI_API_KEY, PUBLIC_DATA_API_KEY 등)가 있어도, 이를
    모르는 테스트가 실제 네트워크를 호출해 타임아웃/비결정적 결과를 내지 않도록 기본값을 None으로
    강제한다. 실제 호출을 검증하는 테스트는 각자 monkeypatch로 필요한 키만 다시 설정한다(T-MED-4)."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", None)
