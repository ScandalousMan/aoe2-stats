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

from pydantic import Field, SecretStr, ValidationError, field_validator
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

    # --- Search, favourites and analysis tuning -------------------------------------------------
    # How many players a user may favourite — see .env.example for why.
    favourites_max_per_user: int = Field(alias="FAVOURITES_MAX_PER_USER")
    # How long a cached search result stays fresh before it is re-fetched.
    player_search_cache_ttl_seconds: int = Field(alias="PLAYER_SEARCH_CACHE_TTL_SECONDS")
    # Per-user search rate limit, so search cannot enumerate the source at volume.
    player_search_max_per_user_per_minute: int = Field(
        alias="PLAYER_SEARCH_MAX_PER_USER_PER_MINUTE"
    )
    # Per-user rate limit on recorded-game requests, downloads and retained-recording reads alike.
    replay_download_max_per_user_per_minute: int = Field(
        alias="REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE"
    )
    # Per-user daily rate limit on analysis requests.
    analysis_max_requests_per_user_per_day: int = Field(
        alias="ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY"
    )
    # Analysis's own daily allowance of requests to the replay source, kept below capture's.
    analysis_max_source_requests_per_day: int = Field(alias="ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY")
    # Total volume, in bytes, retained under constitution IX's on-demand analysis basis.
    analysis_retention_cap_bytes: int = Field(alias="ANALYSIS_RETENTION_CAP_BYTES")
    # The interruptible unit of analysis work, as INGEST_RUN_BUDGET_SECONDS is for ingestion.
    analysis_run_budget_seconds: int = Field(alias="ANALYSIS_RUN_BUDGET_SECONDS")
    # How long an analysis claim survives an invocation that died.
    analysis_lease_seconds: int = Field(alias="ANALYSIS_LEASE_SECONDS")
    # R3's memory bound: the raw recording size, in bytes, above which a recording is refused
    # before it is parsed.
    analysis_max_raw_bytes: int = Field(alias="ANALYSIS_MAX_RAW_BYTES")


class ConfigurationError(Exception):
    """`Settings` could not be built from the environment: the key names it could not resolve,
    and nothing else.

    **T390**, added 2026-08-23 after a production outage. Ten keys 003 declared
    (`ANALYSIS_*`, `PLAYER_SEARCH_*`, `FAVOURITES_MAX_PER_USER`,
    `REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE`) were never set on the deployment target, so
    `Settings()` raised while FastAPI resolved `SessionDep`/`SettingsDep` — before any route
    body ran — and every `/api/*` route answered a bare `internal_error` 500 with an empty
    `detail`. The diagnosis existed on exactly one route, `/api/health`, which wraps its own
    `Settings` resolution (T014e); `GET /api/me`, which is what a user actually hit, said
    nothing at all.

    Raising a type of this application's own is what lets `app.py` answer the *same*
    `configuration_invalid` 503 on every route without widening that handler to
    `pydantic.ValidationError` — which `parse_strict` (`packages/providers/base.py`) raises for
    a drifted third-party payload, a fault that is not configuration and must not be reported
    as configuration. `test_configuration_envelope.py` asserts both directions.

    `keys` carries alias *names* only. The `ValidationError` it was derived from is chained as
    `__cause__` and never rendered into a response or a log: `error["input"]` there holds every
    field's value, secrets included (constitution VIII).
    """

    def __init__(self, keys: list[str]) -> None:
        super().__init__(
            "Settings could not be built from the environment; "
            f"missing or invalid keys: {', '.join(keys) if keys else '(unattributed)'}"
        )
        self.keys = keys


def missing_or_invalid_keys(exc: ValidationError) -> list[str]:
    """Just the *names* a `Settings` build could not resolve, sorted and de-duplicated.

    `error["loc"]` is the environment variable alias pydantic-settings validated against (e.g.
    `S3_SECRET_ACCESS_KEY`), not the value — `error["input"]` is where the value would be, for
    every field in `Settings` at once, secrets included, and is never read here.

    Moved here from `routers/health.py` by T390: that route was the only caller while it was the
    only place a `Settings` failure was named, and two implementations of this would be two
    answers to "which keys are wrong" for one fault.
    """
    keys = {str(error["loc"][0]) for error in exc.errors() if error.get("loc")}
    return sorted(keys)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide `Settings` instance, built once and cached.

    A FastAPI dependency (`Depends(get_settings)`) or any other caller gets the same
    validated instance for the lifetime of the process; nothing here re-reads the
    environment after the first call, which keeps configuration stable for the duration of
    one request, one ingest run, or one test session.

    Raises `ConfigurationError`, never the underlying `pydantic.ValidationError` (T390). The
    exception is not cached: `lru_cache` stores return values only, so a caller that fixes the
    environment and calls again gets a fresh build attempt. Constructing `Settings()` directly —
    which `test_settings.py` does throughout — still raises `ValidationError`, and that is the
    boundary: this function is the application's entry point to configuration, the class is
    pydantic's.
    """
    try:
        return Settings()  # type: ignore[call-arg]  # values are supplied by the environment
    except ValidationError as exc:
        raise ConfigurationError(missing_or_invalid_keys(exc)) from exc
