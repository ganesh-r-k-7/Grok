"""AI Provider exception hierarchy."""

from typing import Optional


class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after
        self.provider = provider
        self.model = model
        super().__init__(message)

    def to_dict(self) -> dict:
        """Safe representation for logging (no secrets)."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "retry_after": self.retry_after,
            "provider": self.provider,
            "model": self.model,
        }


class AIProviderRateLimitError(AIProviderError):
    """Raised when provider returns HTTP 429 (rate limit)."""

    def __init__(
        self,
        message: str = "Provider rate limit exceeded",
        retry_after: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=429,
            retry_after=retry_after,
            provider=provider,
            model=model,
        )


class AIProviderTimeoutError(AIProviderError):
    """Raised when provider request times out."""

    def __init__(
        self,
        message: str = "Provider request timed out",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=504,
            provider=provider,
            model=model,
        )


class AIProviderUnavailableError(AIProviderError):
    """Raised when provider is temporarily unavailable (502, 503)."""

    def __init__(
        self,
        message: str = "Provider temporarily unavailable",
        status_code: int = 503,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            provider=provider,
            model=model,
        )


class AIProviderAuthenticationError(AIProviderError):
    """Raised when provider authentication fails (401, 403)."""

    def __init__(
        self,
        message: str = "Provider authentication failed",
        status_code: int = 401,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            provider=provider,
            model=model,
        )


class AIProviderBadRequestError(AIProviderError):
    """Raised when provider returns 400 (invalid request)."""

    def __init__(
        self,
        message: str = "Invalid request to provider",
        status_code: int = 400,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            provider=provider,
            model=model,
        )


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable (transient failure)."""
    if isinstance(error, AIProviderRateLimitError):
        return True
    if isinstance(error, AIProviderTimeoutError):
        return True
    if isinstance(error, AIProviderUnavailableError):
        return True
    if isinstance(error, AIProviderAuthenticationError):
        return False
    if isinstance(error, AIProviderBadRequestError):
        return False
    return False


def map_provider_exception(error: Exception, provider: str = "unknown", model: str = "unknown") -> AIProviderError:
    """Map a generic exception to the appropriate AI provider exception."""
    if isinstance(error, AIProviderError):
        return error

    # Handle OpenAI SDK exceptions
    try:
        from openai import (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            BadRequestError,
        )

        if isinstance(error, RateLimitError):
            retry_after = None
            if hasattr(error, "response") and error.response is not None:
                retry_after_header = error.response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        retry_after = int(retry_after_header)
                    except ValueError:
                        pass
            return AIProviderRateLimitError(
                message=str(error),
                retry_after=retry_after,
                provider=provider,
                model=model,
            )

        if isinstance(error, APITimeoutError):
            return AIProviderTimeoutError(
                message=str(error),
                provider=provider,
                model=model,
            )

        if isinstance(error, APIConnectionError):
            return AIProviderUnavailableError(
                message=str(error),
                status_code=503,
                provider=provider,
                model=model,
            )

        if isinstance(error, AuthenticationError):
            return AIProviderAuthenticationError(
                message=str(error),
                status_code=401,
                provider=provider,
                model=model,
            )

        if isinstance(error, BadRequestError):
            return AIProviderBadRequestError(
                message=str(error),
                status_code=400,
                provider=provider,
                model=model,
            )

        if isinstance(error, APIStatusError):
            status_code = error.status_code if hasattr(error, "status_code") else 500
            if status_code == 429:
                retry_after = None
                if hasattr(error, "response") and error.response is not None:
                    retry_after_header = error.response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = int(retry_after_header)
                        except ValueError:
                            pass
                return AIProviderRateLimitError(
                    message=str(error),
                    retry_after=retry_after,
                    provider=provider,
                    model=model,
                )
            elif status_code in (502, 503):
                return AIProviderUnavailableError(
                    message=str(error),
                    status_code=status_code,
                    provider=provider,
                    model=model,
                )
            elif status_code in (401, 403):
                return AIProviderAuthenticationError(
                    message=str(error),
                    status_code=status_code,
                    provider=provider,
                    model=model,
                )
            elif status_code == 400:
                return AIProviderBadRequestError(
                    message=str(error),
                    status_code=400,
                    provider=provider,
                    model=model,
                )
            elif status_code == 504:
                return AIProviderTimeoutError(
                    message=str(error),
                    provider=provider,
                    model=model,
                )
    except ImportError:
        pass

    # Fallback for unknown exceptions
    return AIProviderError(
        message=str(error),
        provider=provider,
        model=model,
    )