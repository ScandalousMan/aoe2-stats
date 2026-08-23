"""Unit tests for `aoe2stats_api.settings`.

Every key declared in the repository's `.env.example` is exercised here: happy-path loading,
type coercion for the numeric tuning knobs, the comma-separated allowlist parsing, secrets not
leaking through `repr`/`str`, and a `ValidationError` for any variable the environment omits —
this module has no defaults, so "missing" must fail loudly rather than fall back silently
(constitution VIII, constitution XII).

This is a self-contained unit test using `monkeypatch.setenv`/`delenv`, ahead of the shared
integration-test harness T015 builds; it needs no database and no network.
"""

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from aoe2stats_api.settings import Settings, get_settings

REQUIRED_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+psycopg://user:password@host/dbname?sslmode=require",
    "S3_ENDPOINT_URL": "https://account.eu.r2.cloudflarestorage.com",
    "S3_BUCKET": "aoe2-stats-replays",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
    "S3_REGION": "auto",
    "APP_ENV": "development",
    "APP_SECRET_KEY": "test-app-secret",
    "PUBLIC_BASE_URL": "http://localhost:5173",
    "CRON_SECRET": "not-a-real-secret-not-a-real-secret",
    "STEAM_API_KEY": "test-steam-api-key",
    "BETA_ALLOWLIST_STEAM_IDS": "76561198000000001,76561198000000002",
    "CAPTURE_BUDGET_DAYS": "21",
    "REPLAY_PUBLICATION_GRACE_HOURS": "72",
    "AOEMS_MAX_REQUESTS_PER_SECOND": "1",
    "INGEST_RUN_BUDGET_SECONDS": "240",
    "INGEST_MAX_CAPTURES_PER_USER_PER_RUN": "20",
    "INGEST_QUOTA_EXEMPT_DAYS": "7",
    "FAVOURITES_MAX_PER_USER": "100",
    "PLAYER_SEARCH_CACHE_TTL_SECONDS": "300",
    "PLAYER_SEARCH_MAX_PER_USER_PER_MINUTE": "20",
    "REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE": "6",
    "ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY": "10",
    "ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY": "60",
    "ANALYSIS_RETENTION_CAP_BYTES": "2147483648",
    "ANALYSIS_RUN_BUDGET_SECONDS": "240",
    "ANALYSIS_LEASE_SECONDS": "300",
    "ANALYSIS_MAX_RAW_BYTES": "25165824",
}


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove every settings key from the real environment and clear the `get_settings` cache.

    Without this, a variable already exported in the shell running the tests (or left behind by
    a previous test) would silently make a "missing variable" case pass for the wrong reason.
    """
    for key in REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_all(monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str] | None = None) -> None:
    values = dict(REQUIRED_ENV)
    if overrides:
        values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_loads_every_env_example_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all(monkeypatch)

    settings = get_settings()

    assert settings.database_url == REQUIRED_ENV["DATABASE_URL"]
    assert settings.s3_endpoint_url == REQUIRED_ENV["S3_ENDPOINT_URL"]
    assert settings.s3_bucket == REQUIRED_ENV["S3_BUCKET"]
    assert settings.s3_access_key_id == REQUIRED_ENV["S3_ACCESS_KEY_ID"]
    assert settings.s3_secret_access_key.get_secret_value() == REQUIRED_ENV["S3_SECRET_ACCESS_KEY"]
    assert settings.s3_region == REQUIRED_ENV["S3_REGION"]
    assert settings.app_env == REQUIRED_ENV["APP_ENV"]
    assert settings.app_secret_key.get_secret_value() == REQUIRED_ENV["APP_SECRET_KEY"]
    assert settings.public_base_url == REQUIRED_ENV["PUBLIC_BASE_URL"]
    assert settings.cron_secret.get_secret_value() == REQUIRED_ENV["CRON_SECRET"]
    assert settings.steam_api_key.get_secret_value() == REQUIRED_ENV["STEAM_API_KEY"]
    assert settings.beta_allowlist_steam_ids == frozenset(
        {"76561198000000001", "76561198000000002"}
    )


def test_numeric_fields_are_typed_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all(monkeypatch)

    settings = get_settings()

    assert isinstance(settings.capture_budget_days, int)
    assert settings.capture_budget_days == 21
    assert isinstance(settings.replay_publication_grace_hours, int)
    assert settings.replay_publication_grace_hours == 72
    assert isinstance(settings.aoems_max_requests_per_second, float)
    assert settings.aoems_max_requests_per_second == 1.0
    assert isinstance(settings.ingest_run_budget_seconds, int)
    assert settings.ingest_run_budget_seconds == 240
    assert isinstance(settings.ingest_max_captures_per_user_per_run, int)
    assert settings.ingest_max_captures_per_user_per_run == 20
    assert isinstance(settings.ingest_quota_exempt_days, int)
    assert settings.ingest_quota_exempt_days == 7
    assert isinstance(settings.favourites_max_per_user, int)
    assert settings.favourites_max_per_user == 100
    assert isinstance(settings.player_search_cache_ttl_seconds, int)
    assert settings.player_search_cache_ttl_seconds == 300
    assert isinstance(settings.player_search_max_per_user_per_minute, int)
    assert settings.player_search_max_per_user_per_minute == 20
    assert isinstance(settings.replay_download_max_per_user_per_minute, int)
    assert settings.replay_download_max_per_user_per_minute == 6
    assert isinstance(settings.analysis_max_requests_per_user_per_day, int)
    assert settings.analysis_max_requests_per_user_per_day == 10
    assert isinstance(settings.analysis_max_source_requests_per_day, int)
    assert settings.analysis_max_source_requests_per_day == 60
    assert isinstance(settings.analysis_retention_cap_bytes, int)
    assert settings.analysis_retention_cap_bytes == 2147483648
    assert isinstance(settings.analysis_run_budget_seconds, int)
    assert settings.analysis_run_budget_seconds == 240
    assert isinstance(settings.analysis_lease_seconds, int)
    assert settings.analysis_lease_seconds == 300
    assert isinstance(settings.analysis_max_raw_bytes, int)
    assert settings.analysis_max_raw_bytes == 25165824


def test_beta_allowlist_deduplicates_and_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all(
        monkeypatch,
        {"BETA_ALLOWLIST_STEAM_IDS": " 111 , 222,111 ,222"},
    )

    settings = get_settings()

    assert settings.beta_allowlist_steam_ids == frozenset({"111", "222"})


def test_beta_allowlist_may_be_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all(monkeypatch, {"BETA_ALLOWLIST_STEAM_IDS": ""})

    settings = get_settings()

    assert settings.beta_allowlist_steam_ids == frozenset()


def test_secrets_never_appear_in_str_or_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all(monkeypatch)

    settings = get_settings()
    rendered = f"{settings!r} {settings}"

    for secret in (
        REQUIRED_ENV["S3_SECRET_ACCESS_KEY"],
        REQUIRED_ENV["APP_SECRET_KEY"],
        REQUIRED_ENV["CRON_SECRET"],
        REQUIRED_ENV["STEAM_API_KEY"],
    ):
        assert secret not in rendered


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all(monkeypatch)

    assert get_settings() is get_settings()


def test_empty_cron_secret_is_rejected_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """The defect T018b fixes: an empty `CRON_SECRET` must never validate — it authenticated a
    bare `Authorization: Bearer ` header when `cron_secret` had no length floor."""
    _set_all(monkeypatch, {"CRON_SECRET": ""})

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_short_cron_secret_is_rejected_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all(monkeypatch, {"CRON_SECRET": "too-short"})

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


@pytest.mark.parametrize("missing_key", sorted(REQUIRED_ENV))
def test_missing_required_variable_raises(
    monkeypatch: pytest.MonkeyPatch, missing_key: str
) -> None:
    values = dict(REQUIRED_ENV)
    del values[missing_key]
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_valid_configuration_is_unaffected_by_shape_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T006b: the new shape checks must not reject any value already in `REQUIRED_ENV` — a
    correctly-formed configuration passes exactly as it did before this task."""
    _set_all(monkeypatch)

    settings = get_settings()

    assert settings.database_url == REQUIRED_ENV["DATABASE_URL"]
    assert settings.s3_endpoint_url == REQUIRED_ENV["S3_ENDPOINT_URL"]
    assert settings.public_base_url == REQUIRED_ENV["PUBLIC_BASE_URL"]


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:password@host/dbname?sslmode=require",
        "postgres://user:password@host/dbname",
        "mysql+psycopg://user:password@host/dbname",
    ],
)
def test_database_url_without_psycopg_scheme_is_rejected(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """The defect T006b fixes: Neon (and most managed Postgres providers) hand out the plain
    `postgresql://` scheme, which silently selects the wrong SQLAlchemy dialect rather than
    failing at startup."""
    _set_all(monkeypatch, {"DATABASE_URL": database_url})

    with pytest.raises(ValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert database_url not in message


@pytest.mark.parametrize(
    "s3_endpoint_url",
    [
        "https://account.eu.r2.cloudflarestorage.com/aoe2-stats-replays",
        "https://account.eu.r2.cloudflarestorage.com?foo=bar",
        "https://account.eu.r2.cloudflarestorage.com#fragment",
    ],
)
def test_s3_endpoint_url_with_path_query_or_fragment_is_rejected(
    monkeypatch: pytest.MonkeyPatch, s3_endpoint_url: str
) -> None:
    """The defect T006b fixes: Cloudflare's bucket page displays an S3 API value that
    *includes the bucket path*; pasting it produced a live outage whose only symptom was
    `NoSuchKey 404` on a list call — an error naming a missing object, for a fault in the
    host."""
    _set_all(monkeypatch, {"S3_ENDPOINT_URL": s3_endpoint_url})

    with pytest.raises(ValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    message = str(exc_info.value)
    assert "S3_ENDPOINT_URL" in message
    assert s3_endpoint_url not in message


def test_s3_endpoint_url_with_bare_trailing_slash_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A root path (`/`) carries no bucket segment and is not the double-bucket shape the
    outage produced — equivalent to no path at all, and not worth rejecting."""
    _set_all(monkeypatch, {"S3_ENDPOINT_URL": "https://account.eu.r2.cloudflarestorage.com/"})

    settings = get_settings()

    assert settings.s3_endpoint_url == "https://account.eu.r2.cloudflarestorage.com/"


def test_public_base_url_with_trailing_slash_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trailing slash breaks OpenID `return_to` validation, and only at sign-in time, long
    after startup."""
    _set_all(monkeypatch, {"PUBLIC_BASE_URL": "http://localhost:5173/"})

    with pytest.raises(ValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    assert "PUBLIC_BASE_URL" in str(exc_info.value)
