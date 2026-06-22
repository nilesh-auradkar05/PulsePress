"""Application settings for the PulsePress API service.

Values are overridable via ``PULSEPRESS_*`` environment variables
(e.g. ``PULSEPRESS_ENVIRONMENT=dev``, ``PULSEPRESS_DATABASE_URL=...``).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULSEPRESS_", extra="ignore")

    service_name: str = "pulsepress-api"
    version: str = "0.1.0"
    environment: str = "production"

    # Database
    database_url: str = (
        "postgresql+psycopg://pulsepress:pulsepress@localhost:5432/pulsepress"
    )

    # Auth — local-dev shortcut (used only when environment == "local")
    local_jwt_secret: str = ""
    jwt_algorithm_local: str = "HS256"

    # Auth — production Cognito JWT validation
    cognito_issuer: str = ""
    cognito_audience: str = ""

    # Browser origins allowed to call the API. Empty by default so non-local
    # deployments must opt into their exact web origins.
    cors_allowed_origins: list[str] = []

    # Money — flat global bill split (SPEC §7.1). Phase 1 has no per-jurisdiction
    # tax and no per-author rates. Tax is added on top of the price; the platform
    # fee is deducted from the author's share. Both round half-up to integer cents.
    platform_fee_pct: Decimal = Decimal("0.10")
    tax_pct: Decimal = Decimal("0.08")
    currency: str = "USD"

    @property
    def is_local(self) -> bool:
        return self.environment.lower() == "local"

    def validate_runtime_config(self) -> None:
        """Fail startup when auth settings are unsafe for the selected environment."""
        if self.is_local:
            if len(self.local_jwt_secret) < 32:
                raise RuntimeError(
                    "PULSEPRESS_LOCAL_JWT_SECRET must be at least 32 characters "
                    "when PULSEPRESS_ENVIRONMENT=local"
                )
            return

        missing = [
            name
            for name, value in {
                "PULSEPRESS_COGNITO_ISSUER": self.cognito_issuer,
                "PULSEPRESS_COGNITO_AUDIENCE": self.cognito_audience,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required production auth settings: " + ", ".join(missing)
            )


settings = Settings()
