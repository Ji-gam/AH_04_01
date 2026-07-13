import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import config
from app.core.db import databases
from app.main import app
from app.models.base import Base
from app.services import medication_service

TEST_DATABASE_URL = f"mysql+asyncmy://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/test"

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
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
async def override_background_task_session(monkeypatch):
    """run_ocr_task는 요청 세션을 재사용하지 않고 AsyncSessionLocal()로 자체 세션을 연다(BE-2).
    테스트에서는 이 세션도 운영 DB가 아닌 test DB를 보게 해야 한다."""
    monkeypatch.setattr(medication_service, "AsyncSessionLocal", TestSessionLocal)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with TestSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture(autouse=True)
def _no_real_external_api_keys_in_tests(monkeypatch):
    """로컬 `.env`에 실제 발급받은 키(OPENAI_API_KEY, PUBLIC_DATA_API_KEY 등)가 있어도, 이를
    모르는 테스트가 실제 네트워크를 호출해 타임아웃/비결정적 결과를 내지 않도록 기본값을 None으로
    강제한다. 실제 호출을 검증하는 테스트는 각자 monkeypatch로 필요한 키만 다시 설정한다(T-MED-4)."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", None)
