import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
import app.main as main_module
import app.database as db_module


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "grok-backend"


@pytest.mark.asyncio
async def test_ready_endpoint(client: AsyncClient):
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "grok-backend"


@pytest.mark.asyncio
async def test_ready_endpoint_redis_failure(client: AsyncClient, mock_redis):
    """Test that /ready returns 503 when Redis ping fails."""
    # Create a mock Redis that raises an exception on ping
    failing_redis = AsyncMock()
    failing_redis.ping = AsyncMock(side_effect=Exception("Connection refused"))

    # Replace the global redis_client and app.state.redis
    original_redis = main_module.redis_client
    main_module.redis_client = failing_redis
    client.app = client._transport.app
    client.app.state.redis = failing_redis

    try:
        response = await client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not ready"
        assert data["reason"] == "redis unavailable"
    finally:
        # Restore original
        main_module.redis_client = original_redis
        client.app.state.redis = original_redis


@pytest.mark.asyncio
async def test_ready_endpoint_database_failure(client: AsyncClient):
    """Test that /ready returns 503 when database is unavailable."""
    # Patch the engine in app.database to fail on connect
    failing_engine = AsyncMock()
    # Create an async context manager that raises on enter
    class FailingConnect:
        async def __aenter__(self):
            raise Exception("Database connection failed")
        async def __aexit__(self, *args):
            pass
    failing_engine.connect = MagicMock(return_value=FailingConnect())

    original_engine = db_module.engine
    db_module.engine = failing_engine

    try:
        response = await client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not ready"
        assert data["reason"] == "database unavailable"
    finally:
        db_module.engine = original_engine


@pytest.mark.asyncio
async def test_openapi_docs(client: AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert data["info"]["title"] == "GROK API"


@pytest.mark.asyncio
async def test_cors_headers(client: AsyncClient):
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers