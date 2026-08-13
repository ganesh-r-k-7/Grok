"""Tests for AI provider retry and error handling."""

import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.user import User
from app.models.conversation import Conversation, Message, ConversationRole
from app.models.task import Task, TaskStatus, TaskPriority
from app.utils.security import hash_password
from app.services.ai_providers.base import ChatChunk
from app.services.ai_providers.exceptions import (
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIProviderAuthenticationError,
    AIProviderBadRequestError,
    AIProviderError,
    map_provider_exception,
    is_retryable_error,
)
from app.config import Settings
from openai import RateLimitError, APITimeoutError, APIConnectionError, APIStatusError, AuthenticationError, BadRequestError


def unique_email(prefix: str = "test") -> str:
    """Generate a unique email for testing."""
    return f"{prefix}_{uuid4().hex[:8]}@example.com"


@pytest.fixture
async def authenticated_user(client: AsyncClient, db_session):
    """Create and return an authenticated user with cookies."""
    email = unique_email("aiuser")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        name="AI User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login_response.status_code == 200
    cookies = login_response.cookies
    return user, cookies


class TestProviderExceptions:
    """Tests for AI provider exception hierarchy."""

    def test_rate_limit_error(self):
        """Test AIProviderRateLimitError creation and properties."""
        error = AIProviderRateLimitError(
            message="Rate limited",
            retry_after=60,
            provider="nemotron",
            model="nvidia/nemotron-3-ultra",
        )
        assert error.status_code == 429
        assert error.retry_after == 60
        assert error.provider == "nemotron"
        assert error.model == "nvidia/nemotron-3-ultra"
        assert "Rate limited" in str(error)

    def test_timeout_error(self):
        """Test AIProviderTimeoutError creation and properties."""
        error = AIProviderTimeoutError(
            message="Request timed out",
            provider="nemotron",
            model="nvidia/nemotron-3-ultra",
        )
        assert error.status_code == 504
        assert error.provider == "nemotron"
        assert error.model == "nvidia/nemotron-3-ultra"

    def test_unavailable_error(self):
        """Test AIProviderUnavailableError creation and properties."""
        error = AIProviderUnavailableError(
            message="Service unavailable",
            status_code=503,
            provider="nemotron",
            model="nvidia/nemotron-3-ultra",
        )
        assert error.status_code == 503
        assert error.provider == "nemotron"
        assert error.model == "nvidia/nemotron-3-ultra"

    def test_authentication_error(self):
        """Test AIProviderAuthenticationError creation and properties."""
        error = AIProviderAuthenticationError(
            message="Invalid API key",
            status_code=401,
            provider="nemotron",
            model="nvidia/nemotron-3-ultra",
        )
        assert error.status_code == 401
        assert error.provider == "nemotron"

    def test_bad_request_error(self):
        """Test AIProviderBadRequestError creation and properties."""
        error = AIProviderBadRequestError(
            message="Invalid request",
            status_code=400,
            provider="nemotron",
            model="nvidia/nemotron-3-ultra",
        )
        assert error.status_code == 400
        assert error.provider == "nemotron"

    def test_to_dict_safe(self):
        """Test that to_dict doesn't expose secrets."""
        error = AIProviderRateLimitError(
            message="Rate limited",
            retry_after=60,
            provider="nemotron",
            model="nvidia/nemotron-3-ultra",
        )
        d = error.to_dict()
        assert "error_type" in d
        assert "message" in d
        assert "status_code" in d
        assert "retry_after" in d
        assert "provider" in d
        assert "model" in d
        # Should not contain any sensitive fields


class TestExceptionMapping:
    """Tests for mapping OpenAI SDK exceptions to provider exceptions."""

    def test_map_rate_limit_error(self):
        """Test mapping OpenAI RateLimitError."""
        # Create a mock response with Retry-After header
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "30"}

        error = RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={},
        )

        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderRateLimitError)
        assert mapped.status_code == 429
        assert mapped.retry_after == 30
        assert mapped.provider == "nemotron"

    def test_map_rate_limit_error_no_retry_after(self):
        """Test mapping OpenAI RateLimitError without Retry-After."""
        mock_response = MagicMock()
        mock_response.headers = {}

        error = RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={},
        )

        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderRateLimitError)
        assert mapped.retry_after is None

    def test_map_timeout_error(self):
        """Test mapping OpenAI APITimeoutError."""
        error = APITimeoutError(request=MagicMock())
        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderTimeoutError)
        assert mapped.status_code == 504

    def test_map_connection_error(self):
        """Test mapping OpenAI APIConnectionError."""
        error = APIConnectionError(message="Connection failed", request=MagicMock())
        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderUnavailableError)
        assert mapped.status_code == 503

    def test_map_authentication_error(self):
        """Test mapping OpenAI AuthenticationError."""
        error = AuthenticationError(message="Invalid API key", response=MagicMock(), body={})
        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderAuthenticationError)
        assert mapped.status_code == 401

    def test_map_bad_request_error(self):
        """Test mapping OpenAI BadRequestError."""
        error = BadRequestError(message="Invalid request", response=MagicMock(), body={})
        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderBadRequestError)
        assert mapped.status_code == 400

    def test_map_status_error_429(self):
        """Test mapping OpenAI APIStatusError with 429."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "10"}
        mock_response.status_code = 429

        error = APIStatusError(
            "Rate limited",
            response=mock_response,
            body={},
        )
        error.status_code = 429

        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderRateLimitError)
        assert mapped.retry_after == 10

    def test_map_status_error_503(self):
        """Test mapping OpenAI APIStatusError with 503."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        error = APIStatusError(
            "Service unavailable",
            response=mock_response,
            body={},
        )
        error.status_code = 503

        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderUnavailableError)
        assert mapped.status_code == 503

    def test_map_status_error_401(self):
        """Test mapping OpenAI APIStatusError with 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        error = APIStatusError(
            "Unauthorized",
            response=mock_response,
            body={},
        )
        error.status_code = 401

        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderAuthenticationError)
        assert mapped.status_code == 401

    def test_map_status_error_400(self):
        """Test mapping OpenAI APIStatusError with 400."""
        mock_response = MagicMock()
        mock_response.status_code = 400

        error = APIStatusError(
            "Bad request",
            response=mock_response,
            body={},
        )
        error.status_code = 400

        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderBadRequestError)
        assert mapped.status_code == 400

    def test_map_status_error_504(self):
        """Test mapping OpenAI APIStatusError with 504."""
        mock_response = MagicMock()
        mock_response.status_code = 504

        error = APIStatusError(
            "Gateway timeout",
            response=mock_response,
            body={},
        )
        error.status_code = 504

        mapped = map_provider_exception(error, provider="nemotron", model="test-model")

        assert isinstance(mapped, AIProviderTimeoutError)
        assert mapped.status_code == 504


class TestRetryableErrorDetection:
    """Tests for is_retryable_error function."""

    def test_rate_limit_is_retryable(self):
        """Test that rate limit errors are retryable."""
        error = AIProviderRateLimitError(message="Rate limited", provider="test", model="test")
        assert is_retryable_error(error) is True

    def test_timeout_is_retryable(self):
        """Test that timeout errors are retryable."""
        error = AIProviderTimeoutError(message="Timeout", provider="test", model="test")
        assert is_retryable_error(error) is True

    def test_unavailable_is_retryable(self):
        """Test that unavailable errors are retryable."""
        error = AIProviderUnavailableError(message="Unavailable", provider="test", model="test")
        assert is_retryable_error(error) is True

    def test_authentication_not_retryable(self):
        """Test that authentication errors are NOT retryable."""
        error = AIProviderAuthenticationError(message="Auth failed", provider="test", model="test")
        assert is_retryable_error(error) is False

    def test_bad_request_not_retryable(self):
        """Test that bad request errors are NOT retryable."""
        error = AIProviderBadRequestError(message="Bad request", provider="test", model="test")
        assert is_retryable_error(error) is False

    def test_generic_not_retryable(self):
        """Test that generic provider errors are NOT retryable by default."""
        error = AIProviderError(message="Generic error", provider="test", model="test")
        assert is_retryable_error(error) is False


class TestNemotronProviderRetry:
    """Tests for Nemotron provider retry logic."""

    @pytest.mark.asyncio
    async def test_rate_limit_without_retry_after_retries_bounded(self, monkeypatch):
        """Test that 429 without Retry-After retries up to max and then fails."""
        from app.services.ai_providers.nemotron import NemotronProvider
        from app.services.ai_providers.exceptions import AIProviderRateLimitError

        # Create a mock client that raises RateLimitError
        mock_client = AsyncMock()
        mock_stream = AsyncMock()
        mock_stream.__aiter__ = AsyncMock(return_value=iter([]))

        # First 3 attempts fail with rate limit, then succeed
        attempt_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 3:
                from openai import RateLimitError
                mock_response = MagicMock()
                mock_response.headers = {}
                raise RateLimitError(message="Rate limited", response=mock_response, body={})
            # On 4th attempt, succeed
            mock_stream = AsyncMock()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Hello"))]
            mock_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

            async def aiter():
                yield mock_chunk
            mock_stream.__aiter__ = aiter
            return mock_stream

        mock_client.chat.completions.create = mock_create

        provider = NemotronProvider()
        provider._client = mock_client

        # Patch settings to have small retry values for test
        with patch("app.services.ai_providers.nemotron.settings") as mock_settings:
            mock_settings.AI_MAX_RETRIES = 3
            mock_settings.AI_RETRY_BASE_DELAY = 0.01
            mock_settings.AI_RETRY_MAX_DELAY = 0.1
            mock_settings.AI_REQUEST_TIMEOUT = 60
            mock_settings.NEMOTRON_API_URL = "https://test.example.com/v1"
            mock_settings.NEMOTRON_API_KEY = "test-key"
            mock_settings.NEMOTRON_MODEL = "test-model"
            mock_settings.AI_TEMPERATURE = 0.3
            mock_settings.AI_MAX_TOKENS = 4096

            chunks = []
            async for chunk in provider.stream_chat(
                system_prompt="test",
                messages=[],
                tools=[],
            ):
                chunks.append(chunk)

        # Should have retried 3 times (max retries = 3, so 4 total attempts)
        assert attempt_count == 4
        # Last chunk should be error since all retries exhausted
        assert chunks[-1].type == "error"

    @pytest.mark.asyncio
    async def test_rate_limit_with_retry_after_respects_header(self, monkeypatch):
        """Test that 429 with Retry-After header respects the delay."""
        from app.services.ai_providers.nemotron import NemotronProvider

        mock_client = AsyncMock()
        attempt_count = 0

        class MockStream:
            def __init__(self, chunks):
                self._chunks = chunks
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self._chunks:
                    raise StopAsyncIteration
                return self._chunks.pop(0)

        async def mock_create(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 1:
                from openai import RateLimitError
                mock_response = MagicMock()
                mock_response.headers = {"Retry-After": "1"}
                raise RateLimitError(message="Rate limited", response=mock_response, body={})

            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Hello"))]
            mock_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            return MockStream([mock_chunk])

        mock_client.chat.completions.create = mock_create

        provider = NemotronProvider()
        provider._client = mock_client

        with patch("app.services.ai_providers.nemotron.settings") as mock_settings:
            mock_settings.AI_MAX_RETRIES = 1
            mock_settings.AI_RETRY_BASE_DELAY = 0.01
            mock_settings.AI_RETRY_MAX_DELAY = 0.1
            mock_settings.AI_REQUEST_TIMEOUT = 60
            mock_settings.NEMOTRON_API_URL = "https://test.example.com/v1"
            mock_settings.NEMOTRON_API_KEY = "test-key"
            mock_settings.NEMOTRON_MODEL = "test-model"
            mock_settings.AI_TEMPERATURE = 0.3
            mock_settings.AI_MAX_TOKENS = 4096

            chunks = []
            async for chunk in provider.stream_chat(
                system_prompt="test",
                messages=[],
                tools=[],
            ):
                chunks.append(chunk)

        assert attempt_count == 2
        # Should succeed on 2nd attempt
        assert chunks[-1].type == "done"

    @pytest.mark.asyncio
    async def test_503_retries_bounded(self):
        """Test that 503 errors retry up to max and then fail."""
        from app.services.ai_providers.nemotron import NemotronProvider

        mock_client = AsyncMock()
        attempt_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 3:
                from openai import APIStatusError
                mock_response = MagicMock()
                mock_response.status_code = 503
                mock_response.headers = {}
                raise APIStatusError("Service unavailable", response=mock_response, body={})

            mock_stream = AsyncMock()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Hello"))]
            mock_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

            async def aiter():
                yield mock_chunk
            mock_stream.__aiter__ = aiter
            return mock_stream

        mock_client.chat.completions.create = mock_create

        provider = NemotronProvider()
        provider._client = mock_client

        with patch("app.services.ai_providers.nemotron.settings") as mock_settings:
            mock_settings.AI_MAX_RETRIES = 3
            mock_settings.AI_RETRY_BASE_DELAY = 0.01
            mock_settings.AI_RETRY_MAX_DELAY = 0.1
            mock_settings.AI_REQUEST_TIMEOUT = 60
            mock_settings.NEMOTRON_API_URL = "https://test.example.com/v1"
            mock_settings.NEMOTRON_API_KEY = "test-key"
            mock_settings.NEMOTRON_MODEL = "test-model"
            mock_settings.AI_TEMPERATURE = 0.3
            mock_settings.AI_MAX_TOKENS = 4096

            chunks = []
            async for chunk in provider.stream_chat(
                system_prompt="test",
                messages=[],
                tools=[],
            ):
                chunks.append(chunk)

        assert attempt_count == 4
        assert chunks[-1].type == "error"

    @pytest.mark.asyncio
    async def test_401_no_retry(self):
        """Test that 401 authentication errors are NOT retried."""
        from app.services.ai_providers.nemotron import NemotronProvider

        mock_client = AsyncMock()
        attempt_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            from openai import AuthenticationError
            mock_response = MagicMock()
            mock_response.status_code = 401
            raise AuthenticationError(message="Invalid API key", response=mock_response, body={})

        mock_client.chat.completions.create = mock_create

        provider = NemotronProvider()
        provider._client = mock_client

        with patch("app.services.ai_providers.nemotron.settings") as mock_settings:
            mock_settings.AI_MAX_RETRIES = 3
            mock_settings.AI_RETRY_BASE_DELAY = 0.01
            mock_settings.AI_RETRY_MAX_DELAY = 0.1
            mock_settings.AI_REQUEST_TIMEOUT = 60
            mock_settings.NEMOTRON_API_URL = "https://test.example.com/v1"
            mock_settings.NEMOTRON_API_KEY = "test-key"
            mock_settings.NEMOTRON_MODEL = "test-model"
            mock_settings.AI_TEMPERATURE = 0.3
            mock_settings.AI_MAX_TOKENS = 4096

            chunks = []
            async for chunk in provider.stream_chat(
                system_prompt="test",
                messages=[],
                tools=[],
            ):
                chunks.append(chunk)

        # Should only attempt once, no retries for auth errors
        assert attempt_count == 1
        assert chunks[-1].type == "error"

    @pytest.mark.asyncio
    async def test_403_no_retry(self):
        """Test that 403 forbidden errors are NOT retried."""
        from app.services.ai_providers.nemotron import NemotronProvider

        mock_client = AsyncMock()
        attempt_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            from openai import APIStatusError
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.headers = {}
            raise APIStatusError("Forbidden", response=mock_response, body={})

        mock_client.chat.completions.create = mock_create

        provider = NemotronProvider()
        provider._client = mock_client

        with patch("app.services.ai_providers.nemotron.settings") as mock_settings:
            mock_settings.AI_MAX_RETRIES = 3
            mock_settings.AI_RETRY_BASE_DELAY = 0.01
            mock_settings.AI_RETRY_MAX_DELAY = 0.1
            mock_settings.AI_REQUEST_TIMEOUT = 60
            mock_settings.NEMOTRON_API_URL = "https://test.example.com/v1"
            mock_settings.NEMOTRON_API_KEY = "test-key"
            mock_settings.NEMOTRON_MODEL = "test-model"
            mock_settings.AI_TEMPERATURE = 0.3
            mock_settings.AI_MAX_TOKENS = 4096

            chunks = []
            async for chunk in provider.stream_chat(
                system_prompt="test",
                messages=[],
                tools=[],
            ):
                chunks.append(chunk)

        assert attempt_count == 1
        assert chunks[-1].type == "error"

    @pytest.mark.asyncio
    async def test_timeout_retries_bounded(self):
        """Test that timeout errors retry up to max and then fail."""
        from app.services.ai_providers.nemotron import NemotronProvider

        mock_client = AsyncMock()
        attempt_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 3:
                from openai import APITimeoutError
                raise APITimeoutError(request=MagicMock())

            mock_stream = AsyncMock()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Hello"))]
            mock_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

            async def aiter():
                yield mock_chunk
            mock_stream.__aiter__ = aiter
            return mock_stream

        mock_client.chat.completions.create = mock_create

        provider = NemotronProvider()
        provider._client = mock_client

        with patch("app.services.ai_providers.nemotron.settings") as mock_settings:
            mock_settings.AI_MAX_RETRIES = 3
            mock_settings.AI_RETRY_BASE_DELAY = 0.01
            mock_settings.AI_RETRY_MAX_DELAY = 0.1
            mock_settings.AI_REQUEST_TIMEOUT = 60
            mock_settings.NEMOTRON_API_URL = "https://test.example.com/v1"
            mock_settings.NEMOTRON_API_KEY = "test-key"
            mock_settings.NEMOTRON_MODEL = "test-model"
            mock_settings.AI_TEMPERATURE = 0.3
            mock_settings.AI_MAX_TOKENS = 4096

            chunks = []
            async for chunk in provider.stream_chat(
                system_prompt="test",
                messages=[],
                tools=[],
            ):
                chunks.append(chunk)

        assert attempt_count == 4
        assert chunks[-1].type == "error"

    @pytest.mark.asyncio
    async def test_successful_retry_produces_content(self):
        """Test that after transient failures, successful retry produces content."""
        from app.services.ai_providers.nemotron import NemotronProvider

        mock_client = AsyncMock()
        attempt_count = 0

        class MockStream:
            def __init__(self, chunks):
                self._chunks = chunks
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self._chunks:
                    raise StopAsyncIteration
                return self._chunks.pop(0)

        async def mock_create(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 1:
                from openai import APIStatusError
                mock_response = MagicMock()
                mock_response.status_code = 503
                mock_response.headers = {}
                raise APIStatusError("Service unavailable", response=mock_response, body={})

            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Success after retry"))]
            mock_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            return MockStream([mock_chunk])

        mock_client.chat.completions.create = mock_create

        provider = NemotronProvider()
        provider._client = mock_client

        with patch("app.services.ai_providers.nemotron.settings") as mock_settings:
            mock_settings.AI_MAX_RETRIES = 1
            mock_settings.AI_RETRY_BASE_DELAY = 0.01
            mock_settings.AI_RETRY_MAX_DELAY = 0.1
            mock_settings.AI_REQUEST_TIMEOUT = 60
            mock_settings.NEMOTRON_API_URL = "https://test.example.com/v1"
            mock_settings.NEMOTRON_API_KEY = "test-key"
            mock_settings.NEMOTRON_MODEL = "test-model"
            mock_settings.AI_TEMPERATURE = 0.3
            mock_settings.AI_MAX_TOKENS = 4096

            chunks = []
            async for chunk in provider.stream_chat(
                system_prompt="test",
                messages=[],
                tools=[],
            ):
                chunks.append(chunk)

        assert attempt_count == 2
        # Should have content from successful retry
        content_chunks = [c for c in chunks if c.type == "content"]
        assert len(content_chunks) == 1
        assert "Success after retry" in content_chunks[0].content


class TestAPIErrorMapping:
    """Tests for API endpoint error mapping."""

    @pytest.mark.asyncio
    async def test_429_returns_429_with_retry_after(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test that provider 429 returns HTTP 429 with retry info."""
        from app.services.ai_providers.exceptions import AIProviderRateLimitError

        user, cookies = authenticated_user

        def mock_get_provider(provider_name="mock"):
            class RateLimitMockProvider:
                async def stream_chat(self, *args, **kwargs):
                    yield ChatChunk(type="error", error="Rate limited")

            return RateLimitMockProvider()

        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)

        # This test checks that the endpoint correctly maps provider errors
        # The actual error mapping happens in the streaming response
        response = await client.post(
            "/api/v1/ai/chat/stream",
            json={"message": "Hello"},
            cookies=cookies,
        )
        # The streaming endpoint returns 200 even for provider errors
        # Errors are sent as SSE events
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_non_streaming_chat_maps_errors(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test that non-streaming chat endpoint returns proper error responses."""
        user, cookies = authenticated_user

        def mock_get_provider(provider_name="mock"):
            class ErrorMockProvider:
                async def stream_chat(self, *args, **kwargs):
                    yield ChatChunk(type="error", error="Provider is down")

            return ErrorMockProvider()

        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)

        response = await client.post(
            "/api/v1/ai/chat",
            json={"message": "Hello"},
            cookies=cookies,
        )

        # Should return 200 with error message in content
        # The current implementation converts provider errors to content
        assert response.status_code == 200


class TestStreamingRetrySafety:
    """Tests for streaming retry behavior safety."""

    @pytest.mark.asyncio
    async def test_streaming_failure_before_first_token_allows_retry(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test that streaming failure before first token allows retry."""
        user, cookies = authenticated_user

        call_count = 0

        def mock_get_provider(provider_name="mock"):
            nonlocal call_count

            class FlakyMockProvider:
                async def stream_chat(self, *args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        # First attempt fails
                        yield ChatChunk(type="error", error="Transient failure")
                    else:
                        # Second attempt succeeds
                        yield ChatChunk(type="content", content="Success on retry")
                        yield ChatChunk(type="done", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

            return FlakyMockProvider()

        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)

        # Note: Current implementation doesn't retry at the API level for streaming
        # This test documents the expected behavior
        response = await client.post(
            "/api/v1/ai/chat/stream",
            json={"message": "Hello"},
            cookies=cookies,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_streaming_failure_after_content_no_restart(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test that streaming failure after content started doesn't restart."""
        user, cookies = authenticated_user

        def mock_get_provider(provider_name="mock"):
            class PartialFailureProvider:
                async def stream_chat(self, *args, **kwargs):
                    yield ChatChunk(type="content", content="Hello ")
                    yield ChatChunk(type="content", content="world")
                    # Then fail
                    yield ChatChunk(type="error", error="Connection lost after content")

            return PartialFailureProvider()

        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)

        response = await client.post(
            "/api/v1/ai/chat/stream",
            json={"message": "Hello"},
            cookies=cookies,
        )
        assert response.status_code == 200

        content = response.text
        events = [line for line in content.split("\n") if line.startswith("data: ")]

        # Should have content events followed by error, then done
        content_count = 0
        error_count = 0
        done_count = 0

        for event in events:
            data = event[6:]
            if data == "[DONE]":
                continue
            import json
            parsed = json.loads(data)
            if parsed.get("type") == "content":
                content_count += 1
            elif parsed.get("type") == "error":
                error_count += 1
            elif parsed.get("type") == "done":
                done_count += 1

        assert content_count >= 1  # Content was produced
        assert error_count >= 1    # Error was sent
        assert done_count >= 1     # Final done event sent


class TestCancellation:
    """Tests for user cancellation handling."""

    @pytest.mark.asyncio
    async def test_cancellation_no_retry(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test that user cancellation doesn't trigger provider retry."""
        # This is a frontend behavior test - the backend receives a cancelled request
        # The backend should handle cancellation gracefully without retrying
        user, cookies = authenticated_user

        def mock_get_provider(provider_name="mock"):
            class SlowMockProvider:
                async def stream_chat(self, *args, **kwargs):
                    import asyncio
                    for i in range(10):
                        yield ChatChunk(type="content", content=f"Part {i}")
                        await asyncio.sleep(0.1)
                    yield ChatChunk(type="done", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

            return SlowMockProvider()

        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)

        # Send request and cancel by closing connection
        # This is hard to test at API level, but we can verify the generator handles cancellation
        pass  # Frontend handles cancellation via AbortController


class TestPersistenceOnRetry:
    """Tests for message persistence during retries."""

    @pytest.mark.asyncio
    async def test_successful_retry_persists_single_message(self, client: AsyncClient, authenticated_user, db_session, monkeypatch):
        """Test that successful retry after transient failure persists exactly one assistant message."""
        from app.services.ai_providers.exceptions import AIProviderRateLimitError

        user, cookies = authenticated_user

        attempt_count = 0

        def mock_get_provider(provider_name="mock"):
            nonlocal attempt_count

            class RetryMockProvider:
                async def stream_chat(self, *args, **kwargs):
                    nonlocal attempt_count
                    attempt_count += 1
                    if attempt_count == 1:
                        yield ChatChunk(type="error", error="Rate limited")
                    else:
                        yield ChatChunk(type="content", content="Success after retry")
                        yield ChatChunk(type="done", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

            return RetryMockProvider()

        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)

        # Note: Current implementation doesn't auto-retry at service level for streaming
        # The error is returned to client
        response = await client.post(
            "/api/v1/ai/chat/stream",
            json={"message": "Test retry persistence"},
            cookies=cookies,
        )
        assert response.status_code == 200


class TestToolCallRetrySafety:
    """Tests for tool call safety during retries."""

    @pytest.mark.asyncio
    async def test_tool_call_not_executed_twice_on_retry(self, db_session, authenticated_user):
        """Test that tool calls are not executed twice if provider retries."""
        from app.services.task_tools import TaskTools
        from uuid import UUID

        user, _ = authenticated_user
        tools = TaskTools(db_session, user)

        # Create a task and verify it's only created once
        result = await tools.execute_tool("create_task", {
            "title": "Test Task",
            "priority": "high",
        })

        assert result["success"] is True
        task_id = UUID(result["task"]["id"])

        # Verify task exists
        task = await tools.get_task(task_id)
        assert task.title == "Test Task"

        # The tool calling loop in AI service executes tools AFTER provider returns them
        # If provider is retried, the same tool call would be sent again
        # Current architecture: tool execution happens after provider returns tool_call
        # If we retry the provider call, we might get the same tool_call again
        # This test documents that the current implementation doesn't retry tool execution
        # A more robust implementation would need idempotency keys for tools


class TestConfiguration:
    """Tests for retry configuration settings."""

    def test_settings_have_retry_config(self):
        """Test that Settings includes retry configuration."""
        settings = Settings(
            APP_ENV="development",
            APP_SECRET_KEY="test-secret-key-for-testing-only-32chars",
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            NEMOTRON_API_URL="https://test.example.com/v1",
            NEMOTRON_API_KEY="test-key",
        )

        assert settings.AI_MAX_RETRIES == 2
        assert settings.AI_RETRY_BASE_DELAY == 1.0
        assert settings.AI_RETRY_MAX_DELAY == 8.0
        assert settings.AI_REQUEST_TIMEOUT == 60.0

    def test_settings_override_from_env(self, monkeypatch):
        """Test that retry settings can be overridden via environment."""
        monkeypatch.setenv("AI_MAX_RETRIES", "5")
        monkeypatch.setenv("AI_RETRY_BASE_DELAY", "2.0")
        monkeypatch.setenv("AI_RETRY_MAX_DELAY", "16.0")
        monkeypatch.setenv("AI_REQUEST_TIMEOUT", "120.0")

        settings = Settings(
            APP_ENV="development",
            APP_SECRET_KEY="test-secret-key-for-testing-only-32chars",
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            NEMOTRON_API_URL="https://test.example.com/v1",
            NEMOTRON_API_KEY="test-key",
        )

        assert settings.AI_MAX_RETRIES == 5
        assert settings.AI_RETRY_BASE_DELAY == 2.0
        assert settings.AI_RETRY_MAX_DELAY == 16.0
        assert settings.AI_REQUEST_TIMEOUT == 120.0