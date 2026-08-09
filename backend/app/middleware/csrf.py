import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.errors import ForbiddenError
from app.config import get_settings

settings = get_settings()

CSRF_COOKIE_NAME = "grokcsrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Auth endpoints that don't require CSRF protection (entry points)
CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/callback",
}

# API endpoint prefixes that don't require CSRF protection (authenticated API with SameSite=lax cookies)
CSRF_EXEMPT_PREFIXES = (
    "/api/v1/tasks",
    "/api/v1/user",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Exempt auth endpoints from CSRF protection
        if request.url.path in CSRF_EXEMPT_PATHS:
            return await call_next(request)

        # Exempt API prefixes from CSRF protection
        if any(request.url.path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
            return await call_next(request)

        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        csrf_header = request.headers.get(CSRF_HEADER_NAME)

        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise ForbiddenError("CSRF validation failed")

        return await call_next(request)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # Frontend must read this
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAME_SITE,
        path="/",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )


def get_csrf_token_from_request(request: Request) -> str | None:
    return request.cookies.get(CSRF_COOKIE_NAME)