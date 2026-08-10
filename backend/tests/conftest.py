import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

from app.main import create_app
from app.database import get_db
from app.models import Base
from app.config import Settings, get_settings

# Import test dialect to register custom SQLite dialect
import tests.test_dialect  # noqa: F401

# Test settings - use custom SQLite dialect in-memory for testing
TEST_DATABASE_URL = "sqlite+custom:///:memory:"


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
    # Create the test engine with SQLite in-memory
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


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