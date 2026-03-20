from enum import StrEnum

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AppSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Environment = Environment.PRODUCTION
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Required: must be set explicitly to force deliberate CORS configuration.
    ALLOWED_ORIGINS: list[str]

    ALLOWED_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE"]


class DatabaseSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required: validated as a proper PostgreSQL DSN by Pydantic.
    DATABASE_URL: PostgresDsn


class CognitoSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    COGNITO_USER_POOL_ID: str
    COGNITO_CLIENT_ID: str
    COGNITO_REGION: str
    # Base URL of the Cognito hosted UI, e.g.
    # ``https://your-domain.auth.us-east-1.amazoncognito.com``
    COGNITO_URL: str
    # App client secret — optional for public Cognito app clients.
    COGNITO_CLIENT_SECRET: str | None = None
    # Redirect URI registered in the Cognito app client.
    COGNITO_LOGIN_REDIRECT_URL: str
    # OAuth 2.0 scopes requested during the token exchange,
    # e.g. "openid email profile".
    COGNITO_SCOPE: str = "openid email profile"


class JWTSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    JWT_SECRET: str
    JWT_EXPIRATION_HOURS: int = 24


# ---------------------------------------------------------------------------
# Module-level singletons
#
# Instantiated once at import time.  If any required environment variable is
# absent, ``pydantic_settings`` raises ``pydantic.ValidationError`` before
# the ASGI server accepts a single request, providing an immediate and
# explicit failure signal.
# ---------------------------------------------------------------------------
app_settings = AppSettings()
db_settings = DatabaseSettings()
cognito_settings = CognitoSettings()
jwt_settings = JWTSettings()
