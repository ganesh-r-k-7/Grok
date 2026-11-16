from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Response
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"


class TokenData(BaseModel):
    user_id: UUID
    email: str
    token_type: str  # "access" or "refresh"
    exp: datetime
    iat: datetime


def create_access_token(user_id: UUID, email: str) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(to_encode, settings.APP_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: UUID, email: str) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": str(user_id),
        "email": email,
        "type": "refresh",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(to_encode, settings.APP_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            user_id=UUID(payload["sub"]),
            email=payload["email"],
            token_type=payload["type"],
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        )
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")


def verify_access_token(token: str) -> TokenData:
    token_data = decode_token(token)
    if token_data.token_type != "access":
        raise ValueError("Invalid token type")
    return token_data


def verify_refresh_token(token: str) -> TokenData:
    token_data = decode_token(token)
    if token_data.token_type != "refresh":
        raise ValueError("Invalid token type")
    return token_data


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set authentication cookies on the response."""
    secure = settings.AUTH_COOKIE_SECURE
    same_site = settings.AUTH_COOKIE_SAME_SITE
    domain = settings.AUTH_COOKIE_DOMAIN

    # Access token cookie (short-lived)
    response.set_cookie(
        key="grokaccess",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        domain=domain,
        max_age=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    # Refresh token cookie (long-lived)
    response.set_cookie(
        key="grokrefresh",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        domain=domain,
        max_age=settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication cookies from the response."""
    secure = settings.AUTH_COOKIE_SECURE
    same_site = settings.AUTH_COOKIE_SAME_SITE
    domain = settings.AUTH_COOKIE_DOMAIN

    response.delete_cookie(
        key="grokaccess",
        secure=secure,
        samesite=same_site,
        domain=domain,
        path="/",
    )
    response.delete_cookie(
        key="grokrefresh",
        secure=secure,
        samesite=same_site,
        domain=domain,
        path="/",
    )
    response.delete_cookie(
        key="grokcsrf",
        secure=secure,
        samesite=same_site,
        domain=domain,
        path="/",
    )