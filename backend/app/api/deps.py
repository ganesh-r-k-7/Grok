from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.utils.auth import verify_access_token
from app.utils.errors import UnauthorizedError
from app.models.user import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    # First try to get token from cookie (for browser)
    # Then fall back to Authorization header (for API clients)
    token = request.cookies.get("grokaccess")
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise UnauthorizedError("Not authenticated")

    try:
        token_data = verify_access_token(token)
    except ValueError as e:
        raise UnauthorizedError(str(e))

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("User not found")

    if not user.is_active:
        raise UnauthorizedError("Account deactivated")

    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    try:
        return await get_current_user(request, db, credentials)
    except (UnauthorizedError, HTTPException):
        return None


def require_user(user: User = Depends(get_current_user)) -> User:
    return user