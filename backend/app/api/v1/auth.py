from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.middleware.csrf import generate_csrf_token, set_csrf_cookie
from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.services.encryption import get_encryption_service
from app.services.google_oauth import (
    GoogleIdentityError,
    GoogleOAuthError,
    TokenExchangeError,
    get_google_oauth_service,
)
from app.utils.auth import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    set_auth_cookies,
    verify_refresh_token,
)
from app.utils.errors import ConflictError, UnauthorizedError
from app.utils.logging import get_logger
from app.utils.security import hash_password, verify_password

router = APIRouter()

logger = get_logger(__name__)


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
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

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
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

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
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

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


class GoogleConnectResponse(BaseModel):
    """Response for Google connect initiation."""
    authorization_url: str


@router.post("/google/connect", response_model=GoogleConnectResponse)
async def connect_google_calendar(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Initiate Google OAuth flow for Calendar readonly access."""
    oauth_service = get_google_oauth_service(request.app.state.redis)

    state = oauth_service._generate_state()
    await oauth_service.store_state(state, str(user.id))

    authorization_url = oauth_service.get_authorization_url(state)

    return GoogleConnectResponse(authorization_url=authorization_url)


@router.get("/callback")
async def google_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Handle Google OAuth callback."""
    settings = get_settings()
    oauth_service = get_google_oauth_service(request.app.state.redis)
    frontend_url = f"{settings.FRONTEND_URL}/dashboard/integrations"

    if error:
        return RedirectResponse(
            url=f"{frontend_url}?error=oauth_denied&details={error}",
            status_code=status.HTTP_302_FOUND,
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}?error=invalid_callback&details=missing_code_or_state",
            status_code=status.HTTP_302_FOUND,
        )

    user_id = await oauth_service.validate_and_consume_state(state)
    if not user_id:
        return RedirectResponse(
            url=f"{frontend_url}?error=invalid_state&details=state_expired_or_reused",
            status_code=status.HTTP_302_FOUND,
        )

    from uuid import UUID

    from app.database import get_db
    async for db in get_db():
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return RedirectResponse(
                url=f"{frontend_url}?error=user_not_found",
                status_code=status.HTTP_302_FOUND,
            )

        try:
            token_data = await oauth_service.exchange_code_for_tokens(code)
        except TokenExchangeError:
            return RedirectResponse(
                url=f"{frontend_url}?error=token_exchange_failed",
                status_code=status.HTTP_302_FOUND,
            )

        try:
            identity = await oauth_service.get_user_identity(
                access_token=token_data["access_token"],
                id_token=token_data.get("id_token"),
            )
        except GoogleIdentityError:
            return RedirectResponse(
                url=f"{frontend_url}?error=identity_retrieval_failed",
                status_code=status.HTTP_302_FOUND,
            )

        encryption = get_encryption_service()
        access_token_enc = encryption.encrypt(token_data["access_token"])
        refresh_token_enc = None
        if token_data.get("refresh_token"):
            refresh_token_enc = encryption.encrypt(token_data["refresh_token"])

        expires_at = oauth_service.calculate_expires_at(token_data["expires_in"])
        scopes = token_data.get("scope", "").split() if token_data.get("scope") else oauth_service.scopes

        result = await db.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == user.id,
                OAuthToken.provider == "google",
            )
        )
        existing_token = result.scalar_one_or_none()

        if existing_token:
            existing_token.access_token_enc = access_token_enc
            existing_token.refresh_token_enc = refresh_token_enc
            existing_token.expires_at = expires_at
            existing_token.scopes = scopes
            existing_token.provider_account_id = identity.get("provider_account_id")
        else:
            new_token = OAuthToken(
                user_id=user.id,
                provider="google",
                provider_account_id=identity.get("provider_account_id"),
                access_token_enc=access_token_enc,
                refresh_token_enc=refresh_token_enc,
                expires_at=expires_at,
                scopes=scopes,
            )
            db.add(new_token)

        await db.commit()

    return RedirectResponse(
        url=f"{frontend_url}?connected=google",
        status_code=status.HTTP_302_FOUND,
    )


class GoogleStatusResponse(BaseModel):
    provider: str = "google"
    connected: bool
    email: str | None = None
    name: str | None = None
    last_synced_at: str | None = None


@router.get("/google/status", response_model=GoogleStatusResponse)
async def get_google_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Google Calendar connection status for current user."""
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == user.id,
            OAuthToken.provider == "google",
        )
    )
    oauth_token = result.scalar_one_or_none()

    if not oauth_token:
        return GoogleStatusResponse(provider="google", connected=False)

    encryption = get_encryption_service()
    email = None
    name = None
    try:
        access_token = encryption.decrypt(oauth_token.access_token_enc)
        oauth_service = get_google_oauth_service()
        identity = await oauth_service.get_user_identity(access_token=access_token)
        email = identity.get("email")
        name = identity.get("name")
    except GoogleIdentityError:
        logger.warning("Failed to retrieve Google identity for status", user_id=str(user.id))

    return GoogleStatusResponse(
        provider="google",
        connected=True,
        email=email,
        name=name,
        last_synced_at=oauth_token.updated_at.isoformat() if oauth_token.updated_at else None,
    )


@router.delete("/google/disconnect")
async def disconnect_google_calendar(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect Google Calendar and revoke tokens."""
    oauth_service = get_google_oauth_service(request.app.state.redis)

    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == user.id,
            OAuthToken.provider == "google",
        )
    )
    oauth_token = result.scalar_one_or_none()

    if oauth_token:
        encryption = get_encryption_service()
        try:
            access_token = encryption.decrypt(oauth_token.access_token_enc)
            await oauth_service.revoke_token(access_token)
        except (GoogleOAuthError, ValueError) as e:
            logger.warning("Failed to revoke access token", error=str(e))

        if oauth_token.refresh_token_enc:
            try:
                refresh_token = encryption.decrypt(oauth_token.refresh_token_enc)
                await oauth_service.revoke_token(refresh_token)
            except (GoogleOAuthError, ValueError) as e:
                logger.warning("Failed to revoke refresh token", error=str(e))

        await db.delete(oauth_token)
        await db.commit()

    return {"message": "Google Calendar disconnected successfully"}