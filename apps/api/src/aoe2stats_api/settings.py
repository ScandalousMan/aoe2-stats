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
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: SQLAlchemy's dialect for `psycopg` 3, which supports async natively (see `packages/storage`'s
#: `build_engine`). Neon and most managed Postgres providers hand out the plain `postgresql://`
#: on their connection-string page instead, which silently selects the wrong dialect.
_DATABASE_URL_SCHEME = "postgresql+psycopg://"


class Settings(BaseSettings):
    """Application configuration, resolved once from process environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
        # Pydantic's own `ValidationError.__str__` otherwise appends `input_value=...` to
        # every failure, regardless of what a validator's own message says — the exact leak
        # T006b's validators below must not have, since a configuration value like
        # DATABASE_URL carries credentials and this exception surfaces in logs and
        # sometimes in responses.
        hide_input_in_errors=True,
    )

    # --- Database (Neon in phase 1, self-hosted Postgres in phase 2) -----------------------
    # Left as a plain string rather than a Pydantic URL type: those types can normalise or
    # mutate the value (trailing slash, casing), which would silently corrupt a DSN. The
    # `_require_psycopg_scheme` validator below is not that: it rejects one specific,
    # documented, always-wrong shape rather than reformatting whatever it is given.
    database_url: str = Field(alias="DATABASE_URL")

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_scheme(cls, value: str) -> str:
        # Rejected rather than rewritten. Neon's connection-string page (like most managed
        # Postgres providers) hands out the plain `postgresql://` scheme, which selects
        # SQLAlchemy's default sync dialect instead of `psycopg` 3's async one that
        # `packages/storage.build_engine` requires — a bad value here previously cost a
        # manual rewrite of every connection string, discovered only once a query ran. A
        # `str.replace` "fix" would be exactly the silent normalisation the comment above
        # already refuses for this field; failing loudly at startup is the one behaviour
        # this module promises for every value it owns (see the module docstring).
        if not value.startswith(_DATABASE_URL_SCHEME):
            raise ValueError(
                f"DATABASE_URL must start with the '{_DATABASE_URL_SCHEME}' scheme. Neon and "
                "most managed Postgres providers hand out the plain 'postgresql://' scheme by "
                "default, which selects the wrong SQLAlchemy dialect."
            )
        return value

    # --- Object storage (Cloudflare R2 in phase 1, OVH Object Storage in phase 2) ----------
    s3_endpoint_url: str = Field(alias="S3_ENDPOINT_URL")
    s3_bucket: str = Field(alias="S3_BUCKET")
    s3_access_key_id: str = Field(alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: SecretStr = Field(alias="S3_SECRET_ACCESS_KEY")
    s3_region: str = Field(alias="S3_REGION")

    @field_validator("s3_endpoint_url")
    @classmethod
    def _reject_endpoint_with_path(cls, value: str) -> str:
        # The account host, and nothing else — the S3 client appends the bucket itself.
        # Cloudflare's bucket page displays an S3 API value that *includes the bucket path*
        # (`https://<account>.eu.r2.cloudflarestorage.com/<bucket>`); pasting it here sends
        # every request to `.../<bucket>/<bucket>`, which R2 answers with `NoSuchKey 404` —
        # an error naming a missing *object*, for a fault in the *host*. That shape is always
        # wrong, for every S3-compatible provider, in every environment, so it is rejected at
        # startup rather than left for the object store to answer as a riddle on first use.
        # Shape only: no network probe here, or process startup would depend on a third
        # party's reachability rather than on this string's own well-formedness.
        parsed = urlsplit(value)
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError(
                "S3_ENDPOINT_URL must be the account host only, with no path, query or "
                "fragment. The bucket name belongs in S3_BUCKET, not appended here."
            )
        return value

    # --- Application -------------------------------------------------------------------------
    app_env: str = Field(alias="APP_ENV")
    app_secret_key: SecretStr = Field(alias="APP_SECRET_KEY")
    public_base_url: str = Field(alias="PUBLIC_BASE_URL")

    @field_validator("public_base_url")
    @classmethod
    def _reject_trailing_slash(cls, value: str) -> str:
        # A trailing slash breaks OpenID `return_to` validation, and only at sign-in time,
        # long after startup: Steam's OpenID assertion carries this value back verbatim, and
        # the callback compares it byte-for-byte against what was sent — so a stray `/` here
        # fails every sign-in rather than failing the process that would have caught it early.
        if value.endswith("/"):
            raise ValueError("PUBLIC_BASE_URL must not end with a trailing slash.")
        return value

    # Shared secret required by the cron endpoint. Requests without it are rejected.
    # `min_length=32`: an empty or trivial value must fail loudly here, at process startup,
    # rather than silently becoming a live "Bearer " that authenticates any request —
    # constitution VIII's "never publicly invocable" is a startup-time guarantee, not
    # something the request handler alone can be trusted to enforce. 32 characters is the
    # length of a `secrets.token_hex(16)` / a 128-bit key, the floor below which comparing
    # the secret costs an attacker less than generating one honestly.
    cron_secret: SecretStr = Field(alias="CRON_SECRET", min_length=32)

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
