import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.main import create_app
from app.database import get_db
from app.models import Base
from app.config import Settings, get_settings

# Test settings - use environment variable for database URL, fallback to localhost for local development
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://grok:grok@localhost:5432/grok_test")
TEST_POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "postgresql+asyncpg://grok:grok@localhost:5432/postgres")


@pytest.fixture(autouse=True)
def override_cookie_settings():
    """Override cookie settings for tests - use insecure cookies for HTTP testing."""
    import app.utils.auth
    import app.config
    # Patch the settings object used by auth module
    original_secure = app.utils.auth.settings.AUTH_COOKIE_SECURE
    app.utils.auth.settings.AUTH_COOKIE_SECURE = False
    # Also patch the config module's cached settings
    app.config.get_settings.cache_clear()
    yield
    app.utils.auth.settings.AUTH_COOKIE_SECURE = original_secure
    app.config.get_settings.cache_clear()


@pytest.fixture(scope="session")
async def test_engine():
    # First create the test database
    admin_engine = create_async_engine(TEST_POSTGRES_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        # Terminate existing connections to the test database
        await conn.execute(text("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = 'grok_test' AND pid <> pg_backend_pid()
        """))
        # Drop and create the test database
        await conn.execute(text("DROP DATABASE IF EXISTS grok_test"))
        await conn.execute(text("CREATE DATABASE grok_test"))
    await admin_engine.dispose()

    # Now create the test engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

    # Clean up test database
    admin_engine = create_async_engine(TEST_POSTGRES_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = 'grok_test' AND pid <> pg_backend_pid()
        """))
        await conn.execute(text("DROP DATABASE IF EXISTS grok_test"))
    await admin_engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def app(db_session):
    """Create test app without CSRF middleware."""
    from app.middleware.csrf import CSRFMiddleware
    from app.middleware.rate_limit import RateLimitMiddleware
    
    app = create_app()
    
    # Remove CSRF and rate limit middleware for testing
    app.user_middleware = [
        m for m in app.user_middleware 
        if m.cls not in (CSRFMiddleware, RateLimitMiddleware)
    ]
    app.middleware_stack = app.build_middleware_stack()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()