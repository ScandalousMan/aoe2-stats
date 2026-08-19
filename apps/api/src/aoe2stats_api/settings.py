"""Typed application settings, loaded exclusively from environment variables.

Constitution VIII ("no secrets in the clear") and XII ("all configuration comes from
environment variables; no local filesystem state") both land here: this module owns every
key declared in the repository's ``.env.example`` and nothing here has a Python-side
default. A value the deployment target does not set is a validation error at startup, not a
silently applied fallback — the ``.env.example`` values (including the tuning knobs such as
``CAPTURE_BUDGET_DAYS=21``) are a template for what a real environment should carry, not a
second copy of the truth for this module to duplicate.

Local ``.env`` loading — if a developer wants one — is dev tooling's job (direnv, uv, an
editor plugin), not this class's: production and CI both set real environment variables, and
baking dotenv-loading into `Settings` would blur "configuration" and "local filesystem
state" back together (constitution XII).
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, resolved once from process environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    # --- Database (Neon in phase 1, self-hosted Postgres in phase 2) -----------------------
    # Left as a plain string rather than a Pydantic URL type: those types can normalise or
    # mutate the value (trailing slash, casing), which would silently corrupt a DSN.
    database_url: str = Field(alias="DATABASE_URL")

    # --- Object storage (Cloudflare R2 in phase 1, OVH Object Storage in phase 2) ----------
    s3_endpoint_url: str = Field(alias="S3_ENDPOINT_URL")
    s3_bucket: str = Field(alias="S3_BUCKET")
    s3_access_key_id: str = Field(alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: SecretStr = Field(alias="S3_SECRET_ACCESS_KEY")
    s3_region: str = Field(alias="S3_REGION")

    # --- Application -------------------------------------------------------------------------
    app_env: str = Field(alias="APP_ENV")
    app_secret_key: SecretStr = Field(alias="APP_SECRET_KEY")
    public_base_url: str = Field(alias="PUBLIC_BASE_URL")

    # Shared secret required by the cron endpoint. Requests without it are rejected.
    cron_secret: SecretStr = Field(alias="CRON_SECRET")

    # --- Steam ---------------------------------------------------------------------------------
    steam_api_key: SecretStr = Field(alias="STEAM_API_KEY")

    # --- Closed beta -----------------------------------------------------------------------------
    # Comma-separated Steam ids in the environment; exposed as a parsed, deduplicated set. The
    # variable must still be present (possibly empty) — see the module docstring on defaults.
    beta_allowlist_steam_ids: Annotated[frozenset[str], NoDecode] = Field(
        alias="BETA_ALLOWLIST_STEAM_IDS"
    )

    @field_validator("beta_allowlist_steam_ids", mode="before")
    @classmethod
    def _split_allowlist(cls, value: object) -> object:
        # `NoDecode` above stops pydantic-settings from trying to JSON-parse the raw
        # env string (the "complex type" default for a collection); this is what
        # actually turns "id1,id2" into a set.
        if isinstance(value, str):
            return frozenset(steam_id.strip() for steam_id in value.split(",") if steam_id.strip())
        return value

    # --- Ingestion tuning ------------------------------------------------------------------------
    # Retention measured at ~31 days; a capture is never let get closer than this.
    capture_budget_days: int = Field(alias="CAPTURE_BUDGET_DAYS")
    # Window inside which an identical 404 is read as "not yet" rather than "never".
    replay_publication_grace_hours: int = Field(alias="REPLAY_PUBLICATION_GRACE_HOURS")
    # A safety ceiling on the replay endpoint, not a target — see .env.example for why.
    aoems_max_requests_per_second: float = Field(alias="AOEMS_MAX_REQUESTS_PER_SECOND")
    ingest_run_budget_seconds: int = Field(alias="INGEST_RUN_BUDGET_SECONDS")
    # Fairness between users within one run. Not politeness: that is the rate limit above.
    ingest_max_captures_per_user_per_run: int = Field(alias="INGEST_MAX_CAPTURES_PER_USER_PER_RUN")
    # Captures nearer than this to their deadline ignore the fairness cap entirely.
    ingest_quota_exempt_days: int = Field(alias="INGEST_QUOTA_EXEMPT_DAYS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide `Settings` instance, built once and cached.

    A FastAPI dependency (`Depends(get_settings)`) or any other caller gets the same
    validated instance for the lifetime of the process; nothing here re-reads the
    environment after the first call, which keeps configuration stable for the duration of
    one request, one ingest run, or one test session.
    """
    return Settings()  # type: ignore[call-arg]  # values are supplied by the environment
