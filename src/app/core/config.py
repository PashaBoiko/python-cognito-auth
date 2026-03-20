"""Application configuration module using Pydantic Settings.

Settings are split by concern into four classes:

- ``AppSettings`` — runtime behaviour, CORS, and logging
- ``DatabaseSettings`` — PostgreSQL connection string
- ``CognitoSettings`` — AWS Cognito integration credentials and OAuth endpoints
- ``JWTSettings`` — signing secret and token lifetime for issued JWTs

Each class reads from the ``.env`` file (if present) and environment
variables.  Module-level singletons are instantiated at import time so
that any missing required variable raises ``pydantic.ValidationError``
immediately, preventing the server from starting in a misconfigured state.
"""

from enum import StrEnum

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Valid deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AppSettings(BaseSettings):
    """General application runtime settings.

    All CORS-related fields that have no safe default (``ALLOWED_ORIGINS``)
    are declared without a default value so that a misconfigured deployment
    fails loudly at startup rather than silently accepting all origins.

    ``extra="ignore"`` is required because the shared ``.env`` file also
    contains ``DATABASE_URL`` and ``COGNITO_*`` keys which belong to the
    other settings classes.  Without this, pydantic raises
    ``ValidationError: Extra inputs are not permitted`` for those fields.
    """

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
    """Database connection settings.

    ``DATABASE_URL`` is required and intentionally has no default to prevent
    accidental connections to an unintended database.

    ``extra="ignore"`` prevents pydantic from rejecting the ``APP_*``,
    ``COGNITO_*``, and other keys present in the shared ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required: validated as a proper PostgreSQL DSN by Pydantic.
    DATABASE_URL: PostgresDsn


class CognitoSettings(BaseSettings):
    """AWS Cognito integration settings.

    All fields are required — there is no safe fallback for an authentication
    provider's identity or redirect URLs used in the OAuth 2.0 code flow.

    ``extra="ignore"`` prevents pydantic from rejecting the ``APP_*``,
    ``DATABASE_URL``, and other keys present in the shared ``.env`` file.
    """

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
    # App client secret used to authenticate the token-exchange request.
    COGNITO_CLIENT_SECRET: str
    # Redirect URI registered in the Cognito app client.
    COGNITO_LOGIN_REDIRECT_URL: str


class JWTSettings(BaseSettings):
    """Settings for issuing and verifying application JWTs.

    ``JWT_SECRET`` is required with no default so that a deployment without
    a configured signing key fails immediately at startup rather than
    issuing tokens that cannot be verified (or, worse, verified with a
    trivially guessable key).

    ``extra="ignore"`` prevents pydantic from rejecting the ``APP_*``,
    ``DATABASE_URL``, ``COGNITO_*``, and other keys in the shared ``.env``.
    """

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
