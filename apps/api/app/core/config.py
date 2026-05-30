"""Application settings for the PulsePress API service.

Sprint 1 keeps configuration minimal: just the identity fields the internal
`/healthz` endpoint reports. Values are overridable via ``PULSEPRESS_*``
environment variables (e.g. ``PULSEPRESS_ENVIRONMENT=dev``).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULSEPRESS_", extra="ignore")

    service_name: str = "pulsepress-api"
    version: str = "0.1.0"
    environment: str = "local"


settings = Settings()
