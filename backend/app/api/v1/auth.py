from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.utils.errors import UnauthorizedError, ConflictError
from app.api.deps import get_current_user
from app.models.user import User
from app.utils.security import hash_password, verify_password
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    set_auth_cookies,
    clear_auth_cookies,
)

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: str
    email: str
    name: str | None
    picture: str | None
    timezone: str
    briefing_time: str
    briefing_enabled: bool
    is_active: bool

    @classmethod
    def from_user(cls, user: User) -> "UserProfile":
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            picture=user.picture,
            timezone=user.timezone,
            briefing_time=user.briefing_time,
            briefing_enabled=user.briefing_enabled,
            is_active=user.is_active,
        )


class AuthResponse(BaseModel):
    user: UserProfile
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new user with email and password."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise ConflictError("Email already registered", details={"email": request.email})

    # Hash password
    password_hash = hash_password(request.password)

    # Create user
    user = User(
        email=request.email,
        password_hash=password_hash,
        name=request.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)

    # Set cookies
    set_auth_cookies(response, access_token, refresh_token)

    return AuthResponse(
        user=UserProfile.from_user(user),
        access_token=access_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("Invalid credentials")

    if not user.is_active:
        raise UnauthorizedError("Account deactivated")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise UnauthorizedError("Invalid credentials")

    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)

    # Set cookies
    set_auth_cookies(response, access_token, refresh_token)

    return AuthResponse(
        user=UserProfile.from_user(user),
        access_token=access_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token from cookie."""
    refresh_token = request.cookies.get("grokrefresh")
    if not refresh_token:
        raise UnauthorizedError("Refresh token not found")

    try:
        token_data = verify_refresh_token(refresh_token)
    except ValueError as e:
        clear_auth_cookies(response)
        raise UnauthorizedError(str(e))

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        clear_auth_cookies(response)
        raise UnauthorizedError("User not found or deactivated")

    # Create new tokens
    new_access_token = create_access_token(user.id, user.email)
    new_refresh_token = create_refresh_token(user.id, user.email)

    # Set new cookies
    set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(access_token=new_access_token)


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and clear authentication cookies."""
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserProfile.from_user(user)