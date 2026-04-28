import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.db.database import Base, get_db
from app.main import app

RUNNING_IN_DOCKER = os.path.exists("/.dockerenv")
TEST_DB_NAME = "monitoring_test"


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    if RUNNING_IN_DOCKER:
        yield f"postgresql+asyncpg://monitor:monitor@db:5432/{TEST_DB_NAME}"
    else:
        with PostgresContainer("postgres:16-alpine") as container:
            raw_url = container.get_connection_url()
            async_url = raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            if async_url == raw_url:
                async_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")
            yield async_url


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine(postgres_url):
    if RUNNING_IN_DOCKER:
        admin_url = "postgresql+asyncpg://monitor:monitor@db:5432/monitoring"
        admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
            )
            if result.scalar() is None:
                await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
        await admin_engine.dispose()

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE {table.name} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
