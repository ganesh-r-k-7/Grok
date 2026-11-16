"""Tests for Google OAuth service and endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from sqlalchemy import select
from httpx import AsyncClient

from app.models.user import User
from app.models.oauth_token import OAuthToken
from app.services.google_oauth import (
    GoogleOAuthService,
    GoogleOAuthError,
    InvalidStateError,
    TokenExchangeError,
    GoogleIdentityError,
    get_google_oauth_service,
)
from app.services.encryption import EncryptionService
from app.utils.security import hash_password


@pytest.fixture
def mock_settings():
    """Mock settings with Google OAuth config."""
    with patch("app.services.google_oauth.get_settings") as mock:
        settings = MagicMock()
        settings.GOOGLE_CLIENT_ID = "test-client-id"
        settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
        settings.GOOGLE_REDIRECT_URI = "http://localhost:8000/api/v1/auth/callback"
        settings.GOOGLE_SCOPES_READONLY = [
            "openid",
            "email",
            "profile",
            "calendar.readonly",
        ]
        settings.FRONTEND_URL = "http://localhost:3000"
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_encryption():
    """Mock encryption service."""
    with patch("app.services.google_oauth.get_encryption_service") as mock:
        encryption = MagicMock()
        encryption.encrypt = MagicMock(return_value=b"encrypted_token")
        encryption.decrypt = MagicMock(return_value="decrypted_token")
        mock.return_value = encryption
        yield encryption


@pytest.fixture
def oauth_service(mock_redis, mock_settings, mock_encryption):
    """Create GoogleOAuthService with mocked dependencies."""
    return GoogleOAuthService(redis_client=mock_redis)


@pytest.fixture
def sample_user():
    """Create a sample user."""
    return User(
        id=uuid4(),
        email="test@example.com",
        password_hash=hash_password("password"),
        name="Test User",
    )


class TestGoogleOAuthService:
    """Tests for GoogleOAuthService class."""

    def test_generate_state(self, oauth_service):
        """Test state generation produces cryptographically secure random string."""
        state1 = oauth_service._generate_state()
        state2 = oauth_service._generate_state()

        assert isinstance(state1, str)
        assert len(state1) > 20
        assert state1 != state2

    def test_get_authorization_url(self, oauth_service):
        """Test authorization URL generation includes all required parameters."""
        state = "test_state_123"
        url = oauth_service.get_authorization_url(state)

        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client_id=test-client-id" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fauth%2Fcallback" in url
        assert "response_type=code" in url
        assert "scope=openid+email+profile+calendar.readonly" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert f"state={state}" in url

    @pytest.mark.asyncio
    async def test_store_state(self, oauth_service, mock_redis):
        """Test state storage in Redis with TTL."""
        state = "test_state"
        user_id = "user-123"

        await oauth_service.store_state(state, user_id)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "oauth_state:test_state"
        assert call_args[0][1] == 600  # 10 minutes TTL
        assert call_args[0][2] == user_id

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_success(self, oauth_service, mock_redis):
        """Test valid state returns user_id and deletes state."""
        state = "valid_state"
        user_id = "user-123"
        mock_redis.get.return_value = user_id

        result = await oauth_service.validate_and_consume_state(state)

        assert result == user_id
        mock_redis.get.assert_called_once_with("oauth_state:valid_state")
        mock_redis.delete.assert_called_once_with("oauth_state:valid_state")

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_expired(self, oauth_service, mock_redis):
        """Test expired/missing state returns None."""
        state = "expired_state"
        mock_redis.get.return_value = None
        mock_redis.delete.reset_mock()

        result = await oauth_service.validate_and_consume_state(state)

        assert result is None
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_single_use(self, oauth_service, mock_redis):
        """Test state can only be used once."""
        state = "single_use_state"
        user_id = "user-123"
        mock_redis.get.return_value = user_id

        # First validation succeeds
        result1 = await oauth_service.validate_and_consume_state(state)
        assert result1 == user_id

        # Second validation fails (state deleted)
        mock_redis.get.return_value = None
        result2 = await oauth_service.validate_and_consume_state(state)
        assert result2 is None

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self, oauth_service):
        """Test successful token exchange."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_123",
            "refresh_token": "refresh_123",
            "expires_in": 3600,
            "token_type": "Bearer",
            "id_token": "id_token_123",
            "scope": "openid email profile calendar.readonly",
        }
        mock_client.post.return_value = mock_response
        oauth_service._http_client = mock_client

        result = await oauth_service.exchange_code_for_tokens("auth_code_123")

        assert result["access_token"] == "access_123"
        assert result["refresh_token"] == "refresh_123"
        assert result["expires_in"] == 3600
        assert result["id_token"] == "id_token_123"

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_failure(self, oauth_service):
        """Test token exchange failure raises TokenExchangeError."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_grant"}
        mock_client.post.return_value = mock_response
        oauth_service._http_client = mock_client

        with pytest.raises(TokenExchangeError) as exc_info:
            await oauth_service.exchange_code_for_tokens("bad_code")

        assert "Failed to exchange authorization code" in str(exc_info.value)
        assert exc_info.value.details["status"] == 400

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, oauth_service):
        """Test successful token refresh."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_123",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid email profile calendar.readonly",
        }
        mock_client.post.return_value = mock_response
        oauth_service._http_client = mock_client

        result = await oauth_service.refresh_access_token("refresh_123")

        assert result["access_token"] == "new_access_123"
        assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_revoke_token_success(self, oauth_service):
        """Test successful token revocation."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        oauth_service._http_client = mock_client

        result = await oauth_service.revoke_token("token_123")

        assert result is True
        mock_client.post.assert_called_once_with(
            "https://oauth2.googleapis.com/revoke",
            params={"token": "token_123"},
        )

    @pytest.mark.asyncio
    async def test_revoke_token_failure(self, oauth_service):
        """Test token revocation failure returns False."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_client.post.return_value = mock_response
        oauth_service._http_client = mock_client

        result = await oauth_service.revoke_token("bad_token")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_identity_from_id_token(self, oauth_service):
        """Test identity retrieval from ID token."""
        with patch("app.services.google_oauth.google_id_token.verify_oauth2_token") as mock_verify:
            mock_verify.return_value = {
                "sub": "google-sub-123",
                "email": "user@gmail.com",
                "name": "Google User",
                "picture": "https://example.com/photo.jpg",
                "email_verified": True,
            }

            identity = await oauth_service.get_user_identity(
                access_token="access_123",
                id_token="id_token_123",
            )

            assert identity["provider_account_id"] == "google-sub-123"
            assert identity["email"] == "user@gmail.com"
            assert identity["name"] == "Google User"
            assert identity["picture"] == "https://example.com/photo.jpg"
            assert identity["email_verified"] is True

    @pytest.mark.asyncio
    async def test_get_user_identity_from_userinfo(self, oauth_service):
        """Test identity retrieval from userinfo endpoint."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sub": "google-sub-456",
            "email": "user2@gmail.com",
            "name": "Another User",
            "picture": "https://example.com/photo2.jpg",
            "email_verified": True,
        }
        mock_client.get.return_value = mock_response
        oauth_service._http_client = mock_client

        identity = await oauth_service.get_user_identity(access_token="access_123", id_token=None)

        assert identity["provider_account_id"] == "google-sub-456"
        assert identity["email"] == "user2@gmail.com"

    @pytest.mark.asyncio
    async def test_get_user_identity_failure(self, oauth_service):
        """Test identity retrieval failure raises GoogleIdentityError."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "invalid_token"}
        mock_client.get.return_value = mock_response
        oauth_service._http_client = mock_client

        with pytest.raises(GoogleIdentityError):
            await oauth_service.get_user_identity(access_token="bad_token")

    def test_encrypt_decrypt_token(self, oauth_service, mock_encryption):
        """Test token encryption and decryption."""
        token = "test_token_123"

        encrypted = oauth_service.encrypt_token(token)
        decrypted = oauth_service.decrypt_token(encrypted)

        mock_encryption.encrypt.assert_called_with(token)
        mock_encryption.decrypt.assert_called_with(encrypted)

    def test_calculate_expires_at(self, oauth_service):
        """Test expiration calculation."""
        expires_in = 3600
        expires_at = oauth_service.calculate_expires_at(expires_in)

        assert isinstance(expires_at, datetime)
        assert expires_at.tzinfo == timezone.utc
        # Should be approximately 1 hour from now
        diff = expires_at - datetime.now(timezone.utc)
        assert 3590 < diff.total_seconds() < 3610


class TestGoogleOAuthEndpoints:
    """Tests for Google OAuth API endpoints."""

    @pytest.mark.asyncio
    async def test_connect_google_requires_auth(self, client: AsyncClient):
        """Test /google/connect requires authentication."""
        response = await client.post("/api/v1/auth/google/connect")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_connect_google_returns_auth_url(self, client: AsyncClient, db_session):
        """Test /google/connect returns authorization URL."""
        # Create and login user
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password"},
        )
        assert login_response.status_code == 200
        cookies = login_response.cookies

        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service._generate_state = MagicMock(return_value="test_state")
            mock_service.store_state = AsyncMock()
            mock_service.get_authorization_url = MagicMock(return_value="https://google.com/auth?state=test_state")
            mock_get_service.return_value = mock_service

            response = await client.post(
                "/api/v1/auth/google/connect",
                cookies=cookies,
            )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert data["authorization_url"].startswith("https://google.com/auth")

    @pytest.mark.asyncio
    async def test_callback_missing_code_state(self, client: AsyncClient):
        """Test callback with missing code or state redirects with error."""
        response = await client.get("/api/v1/auth/callback", follow_redirects=False)
        assert response.status_code == 302
        assert "error=invalid_callback" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_invalid_state(self, client: AsyncClient):
        """Test callback with invalid/expired state redirects with error."""
        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_and_consume_state = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/v1/auth/callback?code=auth_code&state=bad_state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "error=invalid_state" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_success(self, client: AsyncClient, db_session, mock_redis):
        """Test successful OAuth callback flow."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(id=uuid4(), email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()
        user_id = str(user.id)

        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_and_consume_state = AsyncMock(return_value=user_id)
            mock_service.exchange_code_for_tokens = AsyncMock(return_value={
                "access_token": "access_123",
                "refresh_token": "refresh_123",
                "expires_in": 3600,
                "token_type": "Bearer",
                "id_token": "id_token_123",
                "scope": "openid email profile calendar.readonly",
            })
            mock_service.get_user_identity = AsyncMock(return_value={
                "provider_account_id": "google-sub-123",
                "email": "user@gmail.com",
                "name": "Google User",
                "picture": "https://example.com/photo.jpg",
                "email_verified": True,
            })
            mock_service.calculate_expires_at = MagicMock(
                return_value=datetime.now(timezone.utc) + timedelta(hours=1)
            )
            mock_service.scopes = ["openid", "email", "profile", "calendar.readonly"]
            mock_get_service.return_value = mock_service

            with patch("app.api.v1.auth.get_encryption_service") as mock_get_encryption:
                mock_encryption = MagicMock()
                mock_encryption.encrypt = MagicMock(return_value=b"encrypted")
                mock_get_encryption.return_value = mock_encryption

                # Patch app.database.get_db to use test session
                async def mock_get_db():
                    yield db_session
                
                with patch("app.database.get_db", mock_get_db):
                    response = await client.get(
                        "/api/v1/auth/callback?code=auth_code&state=valid_state",
                        follow_redirects=False,
                    )

        assert response.status_code == 302
        assert "connected=google" in response.headers["location"]

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite doesn't support ARRAY type for scopes column")
    async def test_callback_success_redirects_to_frontend(self, client: AsyncClient, db_session, mock_redis):
        """Test successful OAuth callback redirects to frontend URL."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(id=uuid4(), email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()
        user_id = str(user.id)

        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_and_consume_state = AsyncMock(return_value=user_id)
            mock_service.exchange_code_for_tokens = AsyncMock(return_value={
                "access_token": "access_123",
                "refresh_token": "refresh_123",
                "expires_in": 3600,
                "token_type": "Bearer",
                "id_token": "id_token_123",
                "scope": "openid email profile calendar.readonly",
            })
            mock_service.get_user_identity = AsyncMock(return_value={
                "provider_account_id": "google-sub-123",
                "email": "user@gmail.com",
                "name": "Google User",
                "picture": "https://example.com/photo.jpg",
                "email_verified": True,
            })
            mock_service.calculate_expires_at = MagicMock(
                return_value=datetime.now(timezone.utc) + timedelta(hours=1)
            )
            mock_service.scopes = ["openid", "email", "profile", "calendar.readonly"]
            mock_get_service.return_value = mock_service

            with patch("app.api.v1.auth.get_encryption_service") as mock_get_encryption:
                mock_encryption = MagicMock()
                mock_encryption.encrypt = MagicMock(return_value=b"encrypted")
                mock_get_encryption.return_value = mock_encryption

                # Patch app.database.get_db to use test session
                async def mock_get_db():
                    yield db_session
                
                with patch("app.database.get_db", mock_get_db):
                    with patch("app.api.v1.auth.get_settings") as mock_get_settings:
                        mock_settings = MagicMock()
                        mock_settings.FRONTEND_URL = "http://localhost:3000"
                        mock_get_settings.return_value = mock_settings

                        response = await client.get(
                            "/api/v1/auth/callback?code=auth_code&state=valid_state",
                            follow_redirects=False,
                        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith("http://localhost:3000/dashboard/integrations")
        assert "connected=google" in location

    @pytest.mark.asyncio
    async def test_callback_token_exchange_failure(self, client: AsyncClient, db_session):
        """Test callback handles token exchange failure."""
        user = User(id=uuid4(), email="test@example.com", password_hash=hash_password("password"))
        db_session.add(user)
        await db_session.commit()
        user_id = str(user.id)

        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_and_consume_state = AsyncMock(return_value=user_id)
            mock_service.exchange_code_for_tokens = AsyncMock(
                side_effect=TokenExchangeError("Exchange failed")
            )
            mock_get_service.return_value = mock_service

            response = await client.get(
                "/api/v1/auth/callback?code=bad_code&state=valid_state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "error=token_exchange_failed" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_disconnect_google_requires_auth(self, client: AsyncClient):
        """Test /google/disconnect requires authentication."""
        response = await client.delete("/api/v1/auth/google/disconnect")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_disconnect_google_success(self, client: AsyncClient, db_session):
        """Test successful Google disconnect."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()

        # Add OAuth token (scopes stored as JSON string for SQLite)
        import json
        oauth_token = OAuthToken(
            user_id=user.id,
            provider="google",
            provider_account_id="google-sub-123",
            access_token_enc=b"encrypted_access",
            refresh_token_enc=b"encrypted_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=json.dumps(["openid", "email", "profile", "calendar.readonly"]),
        )
        db_session.add(oauth_token)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password"},
        )
        cookies = login_response.cookies

        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.revoke_token = AsyncMock(return_value=True)
            mock_get_service.return_value = mock_service

            with patch("app.api.v1.auth.get_encryption_service") as mock_get_encryption:
                mock_encryption = MagicMock()
                mock_encryption.decrypt = MagicMock(side_effect=["access_token", "refresh_token"])
                mock_get_encryption.return_value = mock_encryption

                response = await client.delete(
                    "/api/v1/auth/google/disconnect",
                    cookies=cookies,
                )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Google Calendar disconnected successfully"

        # Verify token was deleted
        result = await db_session.execute(
            select(OAuthToken).where(OAuthToken.user_id == user.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_disconnect_google_not_connected(self, client: AsyncClient, db_session):
        """Test disconnect when not connected returns success."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password"},
        )
        cookies = login_response.cookies

        response = await client.delete(
            "/api/v1/auth/google/disconnect",
            cookies=cookies,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_get_google_status_not_connected(self, client: AsyncClient, db_session):
        """Test status endpoint when not connected."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password"},
        )
        cookies = login_response.cookies

        response = await client.get("/api/v1/auth/google/status", cookies=cookies)

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_get_google_status_connected(self, client: AsyncClient, db_session):
        """Test status endpoint when connected."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()

        import json
        oauth_token = OAuthToken(
            user_id=user.id,
            provider="google",
            provider_account_id="google-sub-123",
            access_token_enc=b"encrypted_access",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=json.dumps(["openid", "email", "profile", "calendar.readonly"]),
        )
        db_session.add(oauth_token)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password"},
        )
        cookies = login_response.cookies

        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_user_identity = AsyncMock(return_value={
                "email": "user@gmail.com",
                "name": "Google User",
            })
            mock_get_service.return_value = mock_service

            with patch("app.api.v1.auth.get_encryption_service") as mock_get_encryption:
                mock_encryption = MagicMock()
                mock_encryption.decrypt = MagicMock(return_value="access_token")
                mock_get_encryption.return_value = mock_encryption

                response = await client.get("/api/v1/auth/google/status", cookies=cookies)

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["email"] == "user@gmail.com"
        assert data["name"] == "Google User"

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_per_user_isolation(self, client: AsyncClient, db_session):
        """Test users cannot access each other's Google connections."""
        email1 = f"user1_{uuid4().hex[:8]}@example.com"
        email2 = f"user2_{uuid4().hex[:8]}@example.com"
        user1 = User(email=email1, password_hash=hash_password("password"), name="User 1")
        user2 = User(email=email2, password_hash=hash_password("password"), name="User 2")
        db_session.add_all([user1, user2])
        await db_session.commit()

        import json
        # User 1 connects Google
        oauth_token = OAuthToken(
            user_id=user1.id,
            provider="google",
            provider_account_id="google-sub-1",
            access_token_enc=b"encrypted_access",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=json.dumps(["openid", "email", "profile", "calendar.readonly"]),
        )
        db_session.add(oauth_token)
        await db_session.commit()

        # User 2 logs in
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email2, "password": "password"},
        )
        cookies = login_response.cookies

        # User 2 should not see User 1's connection
        response = await client.get("/api/v1/auth/google/status", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

        # User 2 tries to disconnect - should succeed but do nothing
        response = await client.delete("/api/v1/auth/google/disconnect", cookies=cookies)
        assert response.status_code == 200

        # User 1's token should still exist
        result = await db_session.execute(
            select(OAuthToken).where(OAuthToken.user_id == user1.id)
        )
        assert result.scalar_one_or_none() is not None


class TestTokenEncryption:
    """Tests for token encryption at rest."""

    def test_oauth_token_encryption(self, mock_encryption):
        """Test OAuth tokens are encrypted before storage."""
        encryption = EncryptionService()
        # This tests the actual encryption service
        token = "ya29.a0AfH6SMC..."
        encrypted = encryption.encrypt(token)
        decrypted = encryption.decrypt(encrypted)

        assert encrypted != token.encode()
        assert decrypted == token
        assert len(encrypted) > 12  # nonce + ciphertext

    def test_refresh_token_encryption(self, mock_encryption):
        """Test refresh tokens are encrypted."""
        encryption = EncryptionService()
        refresh_token = "1//0gRefreshToken..."
        encrypted = encryption.encrypt(refresh_token)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == refresh_token


class TestSecurityRequirements:
    """Tests verifying security requirements."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_refresh_token_never_in_response(self, client: AsyncClient, db_session):
        """Test refresh token is never exposed in API responses."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()

        import json
        oauth_token = OAuthToken(
            user_id=user.id,
            provider="google",
            access_token_enc=b"encrypted_access",
            refresh_token_enc=b"encrypted_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=json.dumps(["openid", "email"]),
        )
        db_session.add(oauth_token)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password"},
        )
        cookies = login_response.cookies

        with patch("app.api.v1.auth.get_encryption_service") as mock_get_encryption:
            mock_encryption = MagicMock()
            mock_encryption.decrypt = MagicMock(return_value="access_token")
            mock_get_encryption.return_value = mock_encryption

            response = await client.get("/api/v1/auth/google/status", cookies=cookies)

        data = response.json()
        assert "refresh_token" not in str(data).lower()
        assert "refresh" not in data

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_client_secret_never_in_logs_or_response(self, client: AsyncClient, db_session, caplog):
        """Test client secret never appears in logs or responses."""
        email = f"test_{uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("password"), name="Test User")
        db_session.add(user)
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password"},
        )
        cookies = login_response.cookies

        response = await client.post("/api/v1/auth/google/connect", cookies=cookies)
        data = response.json()

        response_text = str(data).lower()
        assert "client_secret" not in response_text
        assert "test-client-secret" not in response_text

    @pytest.mark.asyncio
    async def test_authorization_code_never_logged(self, client: AsyncClient, caplog):
        """Test authorization code is not logged."""
        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.validate_and_consume_state = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            await client.get("/api/v1/auth/callback?code=secret_code_123&state=state")

        # Check logs don't contain the code
        log_text = " ".join([record.getMessage() for record in caplog.records])
        assert "secret_code_123" not in log_text

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="SQLite test database setup issue")
    async def test_state_tied_to_correct_user(self, client: AsyncClient, db_session):
        """Test OAuth state is tied to the correct authenticated user."""
        email1 = f"user1_{uuid4().hex[:8]}@example.com"
        email2 = f"user2_{uuid4().hex[:8]}@example.com"
        user1 = User(email=email1, password_hash=hash_password("password"), name="User 1")
        user2 = User(email=email2, password_hash=hash_password("password"), name="User 2")
        db_session.add_all([user1, user2])
        await db_session.commit()

        # User 1 initiates OAuth
        login1 = await client.post("/api/v1/auth/login", json={"email": email1, "password": "password"})
        cookies1 = login1.cookies

        with patch("app.api.v1.auth.get_google_oauth_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service._generate_state.return_value = "state_for_user1"
            mock_service.store_state = AsyncMock()
            mock_service.get_authorization_url.return_value = "https://google.com/auth"
            mock_get_service.return_value = mock_service

            await client.post("/api/v1/auth/google/connect", cookies=cookies1)

        # Verify state was stored with user1's ID
        mock_service.store_state.assert_called_once()
        call_args = mock_service.store_state.call_args
        assert call_args[0][1] == str(user1.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])