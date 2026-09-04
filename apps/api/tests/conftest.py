"""The integration-test harness (T015) for `apps/api/tests`: a throwaway Postgres database, real
migrations, and a `TestClient` wired to it.

The database lifecycle itself — create, migrate to `head`, drop — is not implemented here: it
lives once in `tests/db.py`, shared with `apps/ingester/tests/conftest.py`, and is only imported
into this module so pytest scopes it to this directory. `packages/core`'s and `packages/
providers`' unit tests, which never touch a database, must neither pay for this machinery nor be
skipped by it — a plain per-directory `conftest.py` is what keeps that true; a global fixture in
the already-registered `tests/conftest.py` plugin (T004) would not.

`client` is the one thing this module adds beyond what `tests/db.py` already exports: a FastAPI
app built with `create_app()` (T014) whose `get_session` dependency is overridden to run against
the real throwaway database through `session_scope` — the identical commit-or-rollback discipline
production requests get — rather than `test_health.py`'s and `test_cron.py`'s fakes. Every Phase
3+ integration test (T021 onward) is expected to ask for `client` (and, where it needs to seed or
inspect rows directly, `db_session` alongside it) rather than building its own app.

**T015b** consolidates what four agents wrote independently in one parallel batch, once each
believing it was the only one adding it: `_FakeObjectStore` existed byte-for-byte or near enough
in this file, `test_cron.py`, `test_health.py` and `test_index_entrypoint.py`; `_FakeSession` in
three of those; and the 18-key `REQUIRED_ENV` dict plus its autouse `_environment` fixture
existed byte-identically in `test_cron.py` and `test_cron_ingest_entrypoint.py`. Every one of
those lives here now, as fixtures — never a bare `import conftest` from a sibling test module:
`apps/api/tests` and `apps/ingester/tests` both hold a file literally named `conftest.py`, and
under pytest's default "prepend" import mode a plain `import conftest` resolves to whichever of
the two was imported *last* in the session, not the one in the importing file's own directory —
confirmed by running exactly that import from both directories in one session before writing this
comment. Fixture lookup is pytest's own directory-scoped mechanism, not the `sys.modules` cache
namespace clash a bare import goes through, which is why every name below is requested as a
fixture parameter rather than imported.

The `environment` fixture is deliberately **not** autouse here: `test_health.py`,
`test_index_entrypoint.py` and `test_settings.py` build their environment (or none at all, in
`test_index_entrypoint.py`'s and `test_engine_isolation.py`'s case) their own way, and an
autouse fixture in this file would apply to all of them whether they asked for it or not.
`test_cron.py` and `test_cron_ingest_entrypoint.py` opt in explicitly with
`pytestmark = pytest.mark.usefixtures("environment")`.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_response_cache, get_session
from aoe2stats_api.routers import matches as matches_router
from aoe2stats_api.routers import players as players_router
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.repositories.base import session_scope
from aoe2stats_storage.revision import EXPECTED_SCHEMA_REVISION

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a conftest
# module exactly as if it had been defined here, which is the whole point of keeping their one
# implementation in `tests/db.py` instead of duplicating it per directory.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"

# `data.aoe2companion.com` — `COMPANION_BASE_URL`'s own host (`packages/providers/.../companion/
# provider.py`). T420 wires `routers/matches.py::list_matches` to call
# `CompanionEnrichmentProvider.enrich_matches` unconditionally whenever a page still carries a
# `NULL` `color_id` — the shape every test row seeded without a colour has, and, since T411, only
# a row whose Relic payload the projection could not read — so `_default_companion_degraded`
# below exists to keep that call
# harmless for every test in this suite that has no reason to know companion exists at all. See
# that fixture's own docstring.
_COMPANION_HOST = "data.aoe2companion.com"

# Every entrypoint test that needs a full environment needs exactly this set of values — not
# defaults `.env.example` could supply, since most of its values are deliberately blank (secrets)
# or tuned for production (`INGEST_RUN_BUDGET_SECONDS=240` vs. the 5 s a fast test wants). What
# *can* and must agree with `.env.example` is the **set of keys**: the assertion right below reads
# that file the same way `scripts/checks/publication_delay.py` reads `REPLAY_PUBLICATION_GRACE_
# HOURS` from it, so a key added to or removed from `.env.example` fails this suite immediately
# instead of the settings surface quietly drifting one test file at a time (T015b).
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
    "BETA_ALLOWLIST_STEAM_IDS": "",
    "CAPTURE_BUDGET_DAYS": "21",
    "REPLAY_PUBLICATION_GRACE_HOURS": "72",
    "AOEMS_MAX_REQUESTS_PER_SECOND": "1",
    "INGEST_RUN_BUDGET_SECONDS": "5",
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


def _env_example_keys(env_example_path: Path = _ENV_EXAMPLE) -> set[str]:
    """Every variable name `.env.example` declares on its own `KEY=` line, comments excluded."""
    text = env_example_path.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.MULTILINE))


_missing_from_fixture = _env_example_keys() - set(REQUIRED_ENV)
_missing_from_env_example = set(REQUIRED_ENV) - _env_example_keys()
if _missing_from_fixture or _missing_from_env_example:
    raise AssertionError(
        "apps/api/tests/conftest.py's REQUIRED_ENV has drifted from .env.example: "
        f"declared in .env.example but not in REQUIRED_ENV: {sorted(_missing_from_fixture)}; "
        f"in REQUIRED_ENV but not declared in .env.example: {sorted(_missing_from_env_example)}"
    )


@pytest.fixture(autouse=True)
def _reset_companion_breaker() -> Iterator[None]:
    """MJ-4 remediation: `routers/players.py`'s `_companion_breaker` is process-lifetime
    (`functools.lru_cache`d), the same discipline `get_settings()` already gets an explicit
    `environment` fixture for above — but that fixture is opt-in, requested per module, while a
    tripped breaker is a defect any test in this suite can leak into any other. Autouse, unlike
    `environment`: `test_players_routes.py`'s own tests already clear this breaker in a `finally`
    around the one test that deliberately trips it, but that manual discipline was the *only*
    thing standing between a tripped breaker and every later test in the session — a test added
    anywhere else in this suite that reaches the transport and forgets to clear it produces an
    order-dependent heisenbug in an unrelated file. Cleared both before and after, exactly like
    `environment` clears `get_settings()`'s cache, so a trip from an earlier session leftover (or
    a future one) never leaks in either direction.

    T420 adds a second, independent breaker: `routers/matches.py`'s own `_companion_breaker`,
    built through the identical `functools.lru_cache(maxsize=1)` device for the identical reason
    (that module's own docstring) — cleared here too, rather than in a second fixture, since both
    exist to answer exactly the same question about the same class of defect.
    """
    players_router._companion_breaker.cache_clear()
    matches_router._companion_breaker.cache_clear()
    yield
    players_router._companion_breaker.cache_clear()
    matches_router._companion_breaker.cache_clear()


@pytest.fixture(autouse=True)
def _default_companion_degraded(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """T420 wires `routers/matches.py::list_matches` to call `CompanionEnrichmentProvider.
    enrich_matches` whenever a page still carries a `match_players` row with `color_id IS NULL` —
    which, before T420, is every row, since nothing else in this codebase ever wrote one. Left
    unmocked, any test in this suite that merely calls `GET /api/matches` now reaches for a real
    outbound connection: `PYTEST_DISABLE_NETWORK=1`'s `_guarded_connect` (`tests/conftest.py`)
    blocks it with a deliberately loud, non-`httpx`-shaped `RuntimeError` — by design, so a
    provider's own graceful degradation can never mask a forgotten mock — and without that flag
    set the same call instead spends this provider's full retry-and-backoff budget against a host
    that is never going to answer, several seconds per test.

    This fixture answers every request to `data.aoe2companion.com` with a plain `403` instead —
    the same "documented, expected bot-protection noise" `companion/provider.py`'s own module
    docstring already treats as ordinary degradation — so `_enrich_colours` degrades exactly the
    way FR-010 says it should, and no test outside this feature has to know companion exists at
    all. Every other host still reaches the *real*, unpatched `httpx.AsyncClient.send` this
    fixture captures before installing its own — `test_auth_flow.py`'s `fake_upstream` and every
    other test file that patches `httpx.AsyncClient.send`/`httpx.Client.send` itself for its own
    host still behaves identically, since a test's own `monkeypatch.setattr` call inside its body
    runs after this fixture's setup and simply replaces this default for the rest of that test;
    `monkeypatch` unwinds both in reverse order at teardown, so neither has to know about the
    other. `test_match_colour_enrichment.py` is exactly that case: its own `_intercept_companion`
    overrides this default to assert on the companion call itself.
    """
    real_send = httpx.AsyncClient.send

    async def _default_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _COMPANION_HOST:
            return httpx.Response(403, request=request)
        return await real_send(self, request, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(httpx.AsyncClient, "send", _default_send)
    yield


@pytest.fixture(autouse=True)
def _reset_response_cache() -> Iterator[None]:
    """T102's `ResponseCache` (`aoe2stats_api.deps.get_response_cache`) is process-lifetime, the
    same `functools.lru_cache(maxsize=1)` shape as `get_engine`/`get_object_store` above — and,
    exactly like `_reset_companion_breaker` above it, its whole purpose is to answer a later call
    without re-running the query underneath it. Left uncleared, a cache entry one test's `client`
    populates (matches, ratings or a profile list, all keyed by ids this suite reuses across many
    test functions and files — `_CALLER_PROFILE_ID` among them) would survive `clean_database`'s
    truncation and answer a *later* test's identical request with the earlier test's data. Cleared
    both before and after, the same discipline `_reset_companion_breaker` already applies, so a
    leftover from an earlier session (or a future one) never leaks in either direction. Autouse for
    the identical reason that fixture is: a process-wide cache is a defect exactly one test forgets
    to isolate away from, not one any single test introduces.
    """
    get_response_cache().clear()
    yield
    get_response_cache().clear()


@pytest.fixture
def required_env() -> dict[str, str]:
    """The full environment `test_cron.py` and `test_cron_ingest_entrypoint.py` both need,
    checked against `.env.example` above at import time rather than only where it is used."""
    return REQUIRED_ENV


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch, required_env: dict[str, str]) -> Iterator[None]:
    """Set every `required_env` key and clear the cached `Settings`, both before and after —
    requested explicitly per module (`pytestmark = pytest.mark.usefixtures("environment")`),
    never autouse here, so files that build their own environment are unaffected."""
    for key, value in required_env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeScalars:
    """The two-call tail — `.scalars().first()` — that `health.py`'s schema probe (T394) reads."""

    def __init__(self, value: object) -> None:
        self._value = value

    def first(self) -> object:
        return self._value


class _FakeResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._value)


class _FakeSession:
    """Stands in for `AsyncSession`: every route this harness fakes a session for only calls
    `execute`. `fails=True` raises the way a real outage would, for `test_health.py`'s checks;
    every other caller takes the default and never sees the exception path.

    **T394.** `execute` used to return `None`, because no route this harness serves read a result
    — `/api/health`'s database probe was `SELECT 1` and nothing looked at what came back. It now
    also reads `alembic_version`, so the fake answers `schema_revision` (head, by default) for
    that pair of statements and `None` for everything else, keeping every existing caller's
    behaviour intact.

    This fake agrees with the build by construction, which is deliberate and is why it proves
    nothing about the schema: `test_schema_revision.py` owns that claim and asserts it against a
    real database at a real revision. What this keeps true is `test_health.py`'s own subject —
    the configuration guard, the two outage envelopes, and no configuration value in any of them.
    """

    def __init__(self, *, fails: bool = False, schema_revision: str | None = None) -> None:
        self._fails = fails
        self._schema_revision = (
            schema_revision if schema_revision is not None else EXPECTED_SCHEMA_REVISION
        )

    async def execute(self, statement: object) -> _FakeResult:
        if self._fails:
            raise RuntimeError("simulated database outage")
        sql = str(statement)
        if "to_regclass" in sql:
            return _FakeResult("alembic_version" if self._schema_revision is not None else None)
        if "version_num" in sql:
            return _FakeResult(self._schema_revision)
        return _FakeResult(None)


class _FakeObjectStore:
    """Stands in for `ObjectStore` (T010): no test built on this harness reaches for a real
    bucket yet, and constitution III's unit tests never touch the network — `list_keys` is the
    one method `GET /api/health` calls today. `fails=True` raises the way a real outage would,
    for `test_health.py`'s checks; every other caller takes the default and gets an empty list.

    `signed_get_url` (T066) never touches the network either: it deterministically encodes `key`,
    `expires_in` and, when given, `filename` into the returned string, so a test can assert on the
    redirect target alone without needing the same instance the route handler received — the
    `client` fixture builds a fresh one per request through a bare lambda, so nothing can be
    asserted on shared state here. `filename` (2026-08-29 fix) is encoded as its own query
    parameter, deliberately never folded into the path the way the real `response-content-
    disposition` signed parameter would be for a caller — a test decodes it with `parse_qs`
    exactly like `expires_in`, so the shape stays symmetric with the rest of this fake.
    """

    def __init__(self, *, fails: bool = False) -> None:
        self._fails = fails
        #: `test_manual_upload.py` (T080): every `put` this fake receives, in call order — the
        #: blob-first-row-second write ordering that route's own module docstring fixes means a
        #: test can assert on this list directly, the same shape `apps/ingester`'s own
        #: `_FakeObjectStore` fakes (`test_idempotency.py`, `test_interruption.py`) already use.
        self.put_calls: list[tuple[str, bytes]] = []

    async def list_keys(self, prefix: str = "") -> list[str]:
        if self._fails:
            raise RuntimeError("simulated object store outage")
        return []

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        if self._fails:
            raise RuntimeError("simulated object store outage")
        self.put_calls.append((key, body))

    async def signed_get_url(
        self, key: str, *, expires_in: int = 300, filename: str | None = None
    ) -> str:
        if self._fails:
            raise RuntimeError("simulated object store outage")
        url = f"https://fake-object-store.example/signed/{key}?expires_in={expires_in}"
        if filename is not None:
            url += f"&filename={quote(filename)}"
        return url


@pytest.fixture
def fake_session_class() -> type[_FakeSession]:
    return _FakeSession


@pytest.fixture
def fake_object_store_class() -> type[_FakeObjectStore]:
    return _FakeObjectStore


@pytest.fixture
def client(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    """A `TestClient` over a fresh `create_app()`, its `get_session` dependency pointed at the
    real throwaway database and its `get_object_store` dependency faked out. `clean_database` is
    requested (and ignored) purely to order the truncation before the app is ever exercised.

    `base_url="https://testserver"` (T015c): every cookie `security.py` sets carries
    `secure=True` (constitution VIII), and a cookie jar never sends a secure cookie back over
    plain HTTP. `TestClient`'s default `base_url` is `http://testserver`, so without this every
    session and CSRF-state cookie a router sets would silently vanish before the next request in
    the same test — a defect in the harness, not in the routers it drives, and not one to fix by
    weakening `secure=True`.
    """
    app = create_app()

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_object_store] = lambda: _FakeObjectStore()

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
