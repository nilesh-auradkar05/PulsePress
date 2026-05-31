"""Application settings for the PulsePress API service.

Values are overridable via ``PULSEPRESS_*`` environment variables
(e.g. ``PULSEPRESS_ENVIRONMENT=dev``, ``PULSEPRESS_DATABASE_URL=...``).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULSEPRESS_", extra="ignore")

    service_name: str = "pulsepress-api"
    version: str = "0.1.0"
    environment: str = "local"

    # Database
    database_url: str = (
        "postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress"
    )

    # Auth — local-dev shortcut (used only when environment == "local")
    local_jwt_secret: str = "local-dev-only-secret-change-me-in-real-environments"
    jwt_algorithm_local: str = "HS256"

    # Auth — production Cognito JWT validation
    cognito_issuer: str = ""
    cognito_audience: str = ""

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


settings = Settings()
