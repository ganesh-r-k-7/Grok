import pytest
from httpx import AsyncClient
from uuid import uuid4
from app.models.user import User
from app.utils.security import hash_password


def unique_email(prefix: str = "test") -> str:
    """Generate a unique email for testing."""
    return f"{prefix}_{uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful user registration."""
    email = unique_email("register")
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepassword123",
            "name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == email
    assert data["user"]["name"] == "Test User"
    assert "password_hash" not in data["user"]
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Verify cookies are set
    assert "grokaccess" in response.cookies
    assert "grokrefresh" in response.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db_session):
    """Test registration with duplicate email fails."""
    email = unique_email("duplicate")
    # Create existing user
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        name="Existing User",
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "differentpassword123",
            "name": "Another User",
        },
    )
    assert response.status_code == 409
    data = response.json()
    assert data["type"] == "https://grok.dev/errors/conflict"


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """Test registration with invalid email fails."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "password123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Test registration with short password fails."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email("short"),
            "password": "short",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session):
    """Test successful login."""
    email = unique_email("login")
    # Create user
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        name="Login User",
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == email
    assert data["user"]["name"] == "Login User"
    assert "access_token" in data
    
    # Verify cookies are set
    assert "grokaccess" in response.cookies
    assert "grokrefresh" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, db_session):
    """Test login with invalid credentials fails."""
    email = unique_email("invalid")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    # Wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert data["type"] == "https://grok.dev/errors/unauthorized"

    # Non-existent user
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_user(client: AsyncClient, db_session):
    """Test login with deactivated user fails."""
    email = unique_email("deactivated")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_authenticated(client: AsyncClient, db_session):
    """Test /auth/me with valid authentication."""
    email = unique_email("me")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        name="Me User",
    )
    db_session.add(user)
    await db_session.commit()

    # Login first
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert login_response.status_code == 200

    # Use cookies to call /me
    cookies = login_response.cookies
    response = await client.get(
        "/api/v1/auth/me",
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email
    assert data["name"] == "Me User"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_auth_me_unauthenticated(client: AsyncClient):
    """Test /auth/me without authentication fails."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["type"] == "https://grok.dev/errors/unauthorized"


@pytest.mark.asyncio
async def test_auth_me_invalid_token(client: AsyncClient):
    """Test /auth/me with invalid token fails."""
    response = await client.get(
        "/api/v1/auth/me",
        cookies={"grokaccess": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, db_session):
    """Test logout clears cookies."""
    email = unique_email("logout")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    # Login first
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert login_response.status_code == 200
    cookies = login_response.cookies

    # Logout
    response = await client.post("/api/v1/auth/logout", cookies=cookies)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Logged out successfully"

    # Cookies should be cleared
    assert "grokaccess" not in response.cookies or response.cookies.get("grokaccess") == ""
    assert "grokrefresh" not in response.cookies or response.cookies.get("grokrefresh") == ""


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, db_session):
    """Test token refresh."""
    email = unique_email("refresh")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    # Login first
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert login_response.status_code == 200
    cookies = login_response.cookies

    # Refresh token
    response = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # New cookies should be set
    assert "grokaccess" in response.cookies
    assert "grokrefresh" in response.cookies


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Test token refresh with invalid refresh token fails."""
    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"grokrefresh": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_dashboard_requires_auth(client: AsyncClient):
    """Test that protected endpoints require authentication."""
    # This would test an actual protected endpoint
    # For now, we test /auth/me which is protected
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_hashing():
    """Test password hashing and verification."""
    from app.utils.security import hash_password, verify_password

    password = "securepassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False
    assert len(hashed) > 50  # bcrypt hash length


@pytest.mark.asyncio
async def test_register_without_name(client: AsyncClient):
    """Test registration without optional name field."""
    email = unique_email("noname")
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["name"] is None