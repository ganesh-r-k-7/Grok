import pytest
import json
from app.config import Settings


class TestSettings:
    def test_app_cors_origins_default(self):
        settings = Settings(
            APP_SECRET_KEY="test-secret-key-for-testing-purposes-only-32chars",
            DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test",
            ENCRYPTION_KEY="dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdGluZy1wdXJwb3Nlcy1vbmx5",
        )
        assert settings.APP_CORS_ORIGINS == ["http://localhost:3000"]

    def test_app_cors_origins_from_env_json_array(self, monkeypatch):
        monkeypatch.setenv("APP_CORS_ORIGINS", json.dumps(["http://localhost:3000", "http://localhost:8000", "https://example.com"]))
        monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-testing-purposes-only-32chars")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
        monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdGluZy1wdXJwb3Nlcy1vbmx5")
        settings = Settings()
        assert settings.APP_CORS_ORIGINS == [
            "http://localhost:3000",
            "http://localhost:8000",
            "https://example.com",
        ]

    def test_app_cors_origins_single_origin(self, monkeypatch):
        monkeypatch.setenv("APP_CORS_ORIGINS", json.dumps(["http://localhost:3000"]))
        monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-testing-purposes-only-32chars")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
        monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdGluZy1wdXJwb3Nlcy1vbmx5")
        settings = Settings()
        assert settings.APP_CORS_ORIGINS == ["http://localhost:3000"]

    def test_app_cors_origins_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("APP_CORS_ORIGINS", json.dumps([" http://localhost:3000 ", " http://localhost:8000 "]))
        monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-testing-purposes-only-32chars")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
        monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdGluZy1wdXJwb3Nlcy1vbmx5")
        settings = Settings()
        assert settings.APP_CORS_ORIGINS == ["http://localhost:3000", "http://localhost:8000"]

    def test_app_cors_origins_empty_string_ignored(self, monkeypatch):
        monkeypatch.setenv("APP_CORS_ORIGINS", json.dumps(["http://localhost:3000", "", "http://localhost:8000", ""]))
        monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-testing-purposes-only-32chars")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
        monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdGluZy1wdXJwb3Nlcy1vbmx5")
        settings = Settings()
        assert settings.APP_CORS_ORIGINS == ["http://localhost:3000", "http://localhost:8000"]

    def test_google_scopes_readonly_parsing(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SCOPES_READONLY", json.dumps(["openid", "email", "profile"]))
        monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-testing-purposes-only-32chars")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
        monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdGluZy1wdXJwb3Nlcy1vbmx5")
        settings = Settings()
        assert settings.GOOGLE_SCOPES_READONLY == ["openid", "email", "profile"]