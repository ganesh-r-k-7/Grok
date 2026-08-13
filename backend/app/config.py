from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_ENV: str = Field(default="development", pattern="^(development|staging|production)$")
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_SECRET_KEY: str = Field(..., min_length=32)
    APP_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = Field(..., pattern=r"^postgresql\+asyncpg://")
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", pattern=r"^redis://")

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    GOOGLE_SCOPES_READONLY: List[str] = [
        "openid",
        "email",
        "profile",
        "gmail.readonly",
        "calendar.readonly",
        "tasks.readonly",
    ]

    # Encryption
    ENCRYPTION_KEY: str = Field(..., min_length=43)  # base64 encoded 32 bytes
    ENCRYPTION_ALGORITHM: str = "AES-256-GCM"

    # AI Provider
    AI_PROVIDER: str = Field(default="mock", pattern="^(nemotron|openai|mock)$")
    NEMOTRON_API_URL: Optional[str] = None
    NEMOTRON_API_KEY: Optional[str] = None
    NEMOTRON_MODEL: str = "nemotron-3-ultra"
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 4096

    # AI Provider Retry/Timeout Configuration
    AI_MAX_RETRIES: int = 2
    AI_RETRY_BASE_DELAY: float = 1.0
    AI_RETRY_MAX_DELAY: float = 8.0
    AI_REQUEST_TIMEOUT: float = 60.0

    # Celery
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", pattern=r"^redis://")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", pattern=r"^redis://")

    # Sync Intervals (minutes)
    SYNC_GMAIL_INTERVAL: int = 5
    SYNC_CALENDAR_INTERVAL: int = 5
    SYNC_TASKS_INTERVAL: int = 15

    # Briefing
    BRIEFING_DEFAULT_TIME: str = "07:00"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Authentication
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAME_SITE: str = "lax"
    AUTH_COOKIE_DOMAIN: str | None = None

    # Logging
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = Field(default="json", pattern="^(json|console)$")

    @model_validator(mode="before")
    @classmethod
    def parse_list_fields(cls, values):
        """Parse list fields from environment variables (JSON or comma-separated)."""
        import json
        import os
        
        # Handle APP_CORS_ORIGINS
        if "APP_CORS_ORIGINS" in os.environ:
            v = os.environ["APP_CORS_ORIGINS"]
            if isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        values["APP_CORS_ORIGINS"] = [origin.strip() for origin in parsed if origin.strip()]
                except json.JSONDecodeError:
                    values["APP_CORS_ORIGINS"] = [origin.strip() for origin in v.split(",") if origin.strip()]
        
        # Handle GOOGLE_SCOPES_READONLY
        if "GOOGLE_SCOPES_READONLY" in os.environ:
            v = os.environ["GOOGLE_SCOPES_READONLY"]
            if isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        values["GOOGLE_SCOPES_READONLY"] = [scope.strip() for scope in parsed if scope.strip()]
                except json.JSONDecodeError:
                    values["GOOGLE_SCOPES_READONLY"] = [scope.strip() for scope in v.split(",") if scope.strip()]
        
        return values

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()