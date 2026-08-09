from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client: redis.Redis | None = None):
        super().__init__(app)
        self.redis = redis_client
        self.enabled = settings.RATE_LIMIT_REQUESTS > 0

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled or not self.redis:
            return await call_next(request)

        # Skip rate limiting for health/ready endpoints
        if request.url.path in ("/health", "/ready"):
            return await call_next(request)

        # Get client identifier (IP + user agent)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")[:50]
        key = f"ratelimit:{client_ip}:{hash(user_agent)}"

        current = await self.redis.get(key)
        if current is None:
            await self.redis.setex(key, settings.RATE_LIMIT_WINDOW, 1)
        else:
            count = int(current)
            if count >= settings.RATE_LIMIT_REQUESTS:
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "type": "https://grok.dev/errors/rate_limited",
                        "title": "Rate Limited",
                        "status": HTTP_429_TOO_MANY_REQUESTS,
                        "detail": f"Too many requests. Limit: {settings.RATE_LIMIT_REQUESTS} per {settings.RATE_LIMIT_WINDOW}s",
                        "instance": str(request.url),
                    },
                    headers={
                        "Retry-After": str(settings.RATE_LIMIT_WINDOW),
                        "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(settings.RATE_LIMIT_WINDOW),
                    },
                )
            await self.redis.incr(key)

        response = await call_next(request)

        # Add rate limit headers
        remaining = max(0, settings.RATE_LIMIT_REQUESTS - (count + 1) if current else settings.RATE_LIMIT_REQUESTS - 1)
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(settings.RATE_LIMIT_WINDOW)

        return response