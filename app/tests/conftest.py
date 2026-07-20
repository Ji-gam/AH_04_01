import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import config
from app.core.db import databases
from app.main import app
from app.models.base import Base
from app.models.disease_entries import SEED_DISEASE_SUBTYPES, DiseaseSubtype
from app.models.dur import ALL_DUR_MODELS
from app.scripts.seed_dur import seed_dur
from app.scripts.seed_food_drug_interaction import seed_food_drug_interaction
from app.services.medication_service import refresh_food_drug_interaction_cache

_FOOD_DRUG_REFERENCE_TABLES = {
    "food_drug_sources",
    "food_drug_categories",
    "food_drug_ingredients",
    "food_drug_food_items",
}
_DUR_REFERENCE_TABLES = {model.__tablename__ for model in ALL_DUR_MODELS}

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

    # `_food_drug_interaction_repository`(app/services/medication_service.py)는 프로덕션처럼
    # app.main.lifespan에서 채워지지 않으므로, 여기서 테스트 DB에 같은 참조 데이터를 시딩하고
    # 캐시를 직접 채운다 — 안 하면 실제 참조 테이블 매칭(예: 와파린-비타민K)을 검증하는
    # 테스트들이 빈 캐시 때문에 실패한다.
    await seed_food_drug_interaction(session_factory=TestSessionLocal)
    async with TestSessionLocal() as session:
        await refresh_food_drug_interaction_cache(session)

    # DUR 참조 데이터도 운영 MySQL(ai_health, 이미 전체 수집본이 적재되어 있음)에서 그대로 테스트
    # DB로 복사한다 - `dur_prod_usjnt_taboo`가 80만 행대라 세션당 1회뿐이라도 시간이 걸릴 수 있다.
    await seed_dur(session_factory=TestSessionLocal)

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
            # disease_subtypes/food_drug_*/DUR 테이블은 시드 참조데이터라 테스트 사이에 지우지
            # 않는다 - 지우면 매번 새로 심어야 하고(세션 시작 시 1회만 시딩, DUR은 80만 행대라
            # 특히 비용이 큼), 캐시된 `_food_drug_interaction_repository`가 이제 빈 DB를 가리키게
            # 되어 불일치가 생긴다.
            if (
                table.name == "disease_subtypes"
                or table.name in _FOOD_DRUG_REFERENCE_TABLES
                or table.name in _DUR_REFERENCE_TABLES
            ):
                continue
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture(autouse=True)
def _no_real_external_api_keys_in_tests(monkeypatch):
    """로컬 `.env`에 실제 발급받은 키(OPENAI_API_KEY, PUBLIC_DATA_API_KEY 등)가 있어도, 이를
    모르는 테스트가 실제 네트워크를 호출해 타임아웃/비결정적 결과를 내지 않도록 기본값을 None으로
    강제한다. 실제 호출을 검증하는 테스트는 각자 monkeypatch로 필요한 키만 다시 설정한다(T-MED-4)."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", None)


@pytest.fixture(autouse=True)
def _reset_food_guide_card_cache():
    """(#195) `_build_food_interaction_guide_card`에 붙인 프로세스 메모리 캐시는 약품명 기준이라,
    같은 약품명을 서로 다른 mock 응답으로 재사용하는 테스트들 사이에서 결과가 새어 나가면 안 된다."""
    from app.services import medication_service

    medication_service._food_guide_card_cache.clear()
    yield
    medication_service._food_guide_card_cache.clear()
