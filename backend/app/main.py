from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import close_db, init_db
from app.utils.logging import setup_logging, get_logger
from app.utils.errors import register_exception_handlers
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
import redis.asyncio as redis

settings = get_settings()
logger = get_logger(__name__)

redis_client: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global redis_client
    setup_logging()
    logger.info("starting_application", env=settings.APP_ENV)

    await init_db()

    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    app.state.redis = redis_client

    logger.info("application_started")
    yield

    logger.info("shutting_down_application")
    await redis_client.close()
    await close_db()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="GROK API",
        description="Personal AI Command Center API",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.APP_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-CSRF-Token", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    # Security middleware (order matters: rate limit first, then CSRF)
    app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
    app.add_middleware(CSRFMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Health endpoints
    @app.get("/health", tags=["health"])
    async def health() -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "service": "grok-backend"},
        )

    @app.get("/ready", tags=["health"])
    async def ready() -> JSONResponse:
        # Check database connection
        from app.database import engine
        from sqlalchemy import text

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            logger.error("readiness_check_failed", error=str(e))
            return JSONResponse(
                status_code=503,
                content={"status": "not ready", "reason": "database unavailable"},
            )

        # Check Redis connection
        try:
            await redis_client.ping()
        except Exception as e:
            logger.error("readiness_check_failed", error=str(e))
            return JSONResponse(
                status_code=503,
                content={"status": "not ready", "reason": "redis unavailable"},
            )

        return JSONResponse(
            status_code=200,
            content={"status": "ready", "service": "grok-backend"},
        )

    # API v1 router
    from app.api.v1 import api_router
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()