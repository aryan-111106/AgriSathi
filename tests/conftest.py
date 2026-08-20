import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine):
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def override_app_db(test_engine):
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async def _get_test_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()
