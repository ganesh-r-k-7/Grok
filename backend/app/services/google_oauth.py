"""Google OAuth service for handling Google authentication flow."""

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token

from app.config import get_settings
from app.services.encryption import get_encryption_service


class GoogleOAuthError(Exception):
    """Base exception for Google OAuth errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class InvalidStateError(GoogleOAuthError):
    """Raised when OAuth state is invalid, expired, or reused."""


class TokenExchangeError(GoogleOAuthError):
    """Raised when token exchange with Google fails."""


class GoogleIdentityError(GoogleOAuthError):
    """Raised when retrieving Google user identity fails."""


class GoogleOAuthService:
    """Service for managing Google OAuth 2.0 flow."""

    STATE_TTL_SECONDS = 600  # 10 minutes
    STATE_PREFIX = "oauth_state:"

    def __init__(self, redis_client=None, settings=None, encryption_service=None):
        self._redis = redis_client
        self._settings = settings or get_settings()
        self._encryption = encryption_service or get_encryption_service()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def client_id(self) -> str:
        if not self._settings.GOOGLE_CLIENT_ID:
            raise GoogleOAuthError("GOOGLE_CLIENT_ID not configured")
        return self._settings.GOOGLE_CLIENT_ID

    @property
    def client_secret(self) -> str:
        if not self._settings.GOOGLE_CLIENT_SECRET:
            raise GoogleOAuthError("GOOGLE_CLIENT_SECRET not configured")
        return self._settings.GOOGLE_CLIENT_SECRET

    @property
    def redirect_uri(self) -> str:
        if not self._settings.GOOGLE_REDIRECT_URI:
            raise GoogleOAuthError("GOOGLE_REDIRECT_URI not configured")
        return self._settings.GOOGLE_REDIRECT_URI

    @property
    def scopes(self) -> list[str]:
        return self._settings.GOOGLE_SCOPES_READONLY.copy()

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _generate_state(self) -> str:
        """Generate a cryptographically secure random state."""
        return secrets.token_urlsafe(32)

    def _get_state_key(self, state: str) -> str:
        """Get Redis key for storing state."""
        return f"{self.STATE_PREFIX}{state}"

    async def store_state(self, state: str, user_id: str) -> None:
        """Store OAuth state associated with user in Redis with TTL."""
        if not self._redis:
            raise GoogleOAuthError("Redis client not available")
        key = self._get_state_key(state)
        await self._redis.setex(key, self.STATE_TTL_SECONDS, user_id)

    async def validate_and_consume_state(self, state: str) -> str | None:
        """Validate and consume (delete) OAuth state. Returns user_id if valid."""
        if not self._redis:
            raise GoogleOAuthError("Redis client not available")
        key = self._get_state_key(state)
        user_id = await self._redis.get(key)
        if user_id:
            await self._redis.delete(key)
            return user_id
        return None

    def get_authorization_url(self, state: str) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "include_granted_scopes": "true",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for access and refresh tokens."""
        client = await self._get_http_client()
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            raise TokenExchangeError(
                "Failed to exchange authorization code for tokens",
                details={"status": response.status_code, "error": error_data},
            )

        token_data = response.json()
        return {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type", "Bearer"),
            "id_token": token_data.get("id_token"),
            "scope": token_data.get("scope"),
        }

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token using refresh token."""
        client = await self._get_http_client()
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            raise TokenExchangeError(
                "Failed to refresh access token",
                details={"status": response.status_code, "error": error_data},
            )

        token_data = response.json()
        return {
            "access_token": token_data.get("access_token"),
            "expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope"),
        }

    async def revoke_token(self, token: str) -> bool:
        """Revoke an access or refresh token with Google."""
        client = await self._get_http_client()
        revoke_url = "https://oauth2.googleapis.com/revoke"
        params = {"token": token}

        response = await client.post(revoke_url, params=params)
        return response.status_code == 200

    async def get_user_identity(self, access_token: str, id_token: str | None = None) -> dict:
        """Retrieve Google user identity using access token or ID token."""
        if id_token:
            try:
                claims = google_id_token.verify_oauth2_token(
                    id_token,
                    Request(),
                    self.client_id,
                    clock_skew_in_seconds=10,
                )
                return {
                    "provider_account_id": claims.get("sub"),
                    "email": claims.get("email"),
                    "name": claims.get("name"),
                    "picture": claims.get("picture"),
                    "email_verified": claims.get("email_verified", False),
                }
            except ValueError as e:
                raise GoogleIdentityError(
                    "Failed to verify ID token",
                    details={"error": str(e)},
                )

        client = await self._get_http_client()
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.get(userinfo_url, headers=headers)
        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            raise GoogleIdentityError(
                "Failed to retrieve user identity from Google",
                details={"status": response.status_code, "error": error_data},
            )

        data = response.json()
        return {
            "provider_account_id": data.get("sub"),
            "email": data.get("email"),
            "name": data.get("name"),
            "picture": data.get("picture"),
            "email_verified": data.get("email_verified", False),
        }

    def encrypt_token(self, token: str) -> bytes:
        """Encrypt a token for storage."""
        return self._encryption.encrypt(token)

    def decrypt_token(self, encrypted_token: bytes) -> str:
        """Decrypt a token for use."""
        return self._encryption.decrypt(encrypted_token)

    def calculate_expires_at(self, expires_in: int) -> datetime:
        """Calculate token expiration datetime from expires_in seconds."""
        return datetime.now(UTC) + timedelta(seconds=expires_in)


def get_google_oauth_service(redis_client=None) -> GoogleOAuthService:
    """Factory function to get GoogleOAuthService instance."""
    return GoogleOAuthService(redis_client=redis_client)