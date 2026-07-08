import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import config
from app.core.db import databases
from app.core.rate_limit import limiter
from app.main import app
from app.models.base import Base

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
def reset_rate_limiter():
    """[T-AUTH-6] 테스트마다 같은 IP(127.0.0.1)로 signup/login을 여러 번 호출하는데,
    Limiter 상태가 테스트 사이에 그대로 남아있으면 나중 테스트가 429로 실패한다."""
    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with TestSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()
