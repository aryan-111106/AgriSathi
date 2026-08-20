from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Lightweight SQLite-safe schema patches.
# For dev: ensures columns added in newer model versions exist in older DBs.
# For production: replace with Alembic.
_SCHEMA_PATCHES = [
    "ALTER TABLE conversations ADD COLUMN pending_diagnosis JSON",
    "ALTER TABLE farmer_profiles ADD COLUMN telegram_chat_id VARCHAR(64)",
]


async def ensure_schema() -> None:
    """Idempotently add columns that older databases may be missing."""
    async with engine.begin() as conn:
        for stmt in _SCHEMA_PATCHES:
            try:
                await conn.execute(text(stmt))
            except Exception:
                # Column already exists or DB doesn't support the patch
                pass
