"""Build the real, provider-backed ingest stages from `Settings` (T060).

`run.py`'s own module docstring named the gap this module closes precisely: `DiscoverStage`
(`discover.py`, T053), `ReconcileStage` (`reconcile.py`, T054) and `CaptureDrain` (`capture.py`,
T055-T058) all exist, complete and tested, but none of them can be constructed without a real
`MatchHistoryProvider`/`ProfileProvider`/`ReplayProvider`, an `ObjectStore`, a `ReplayValidator`
and the `Settings` values those need — and `Settings` lives in `apps/api`, which `apps/ingester`
cannot import (constitution XII's package boundary: the ingester is a library, not a dependant of
the API). Composition is therefore necessarily a caller's job, and this module is that caller and
the only one: both production entrypoints (`routers/cron.py`, `api/cron/ingest.py`) call
`build_ingest_stages(settings)` and pass its result straight through as `run_once`'s own `stages=`,
so `run_once` itself stays the one authority over ordering, budget and the `ingest_runs` row
(T018, T059) and neither entrypoint grows past the "ten-line caller" shape T060 asks for.

**Every value below is read from `settings`, never a literal that silently disables a feature.**
`max_captures_per_user_per_run`/`quota_exempt_days` are always supplied to `CaptureDrain` together
— its own constructor guard rejects one without the other — because that exact pair going missing
once already made FR-044's fairness cap inert in production (fixed once already, in f0c9a6e and
e8d9a4e). This module is the one place production ever constructs a `CaptureDrain`, so it is the
one place that regression can happen again; it must not.

**The replay engine is imported lazily, inside `build_ingest_stages`, never at this module's own
top level.** Both entrypoints reach this module only from inside their own request handler —
`routers/cron.py`'s `ingest()` imports it exactly where it already imports `run_once` (T018c) —
never from `aoe2stats_api.app`'s own import chain, so a module-scope import here would be no safer
than one in `routers/cron.py` itself. `apps/api/tests/test_engine_isolation.py` is the guard this
discipline keeps green: importing the app must never load `aoe2rec_py`.

**One shared `httpx.AsyncClient`, two rate limiters, built once per process (T060a) —
`build_ingest_stages` used to build a fresh one on every call.** Both production entrypoints call
`build_ingest_stages(settings)` inline on every invocation, never as a context manager, and never
`aclose()`/`dispose()` what it built. `api/cron/ingest.py` is a fresh process each time, so the
leak only ever shows up as wasted work — but `routers/cron.py`, the local *and* the phase-2-VPS
path ADR-0002 names, is a long-lived process, where every trigger used to leak one more connection
pool and its sockets until the file-descriptor ceiling.

The Relic client and its rate limiter never vary with `settings` at all — `_RELIC_RATE_PER_SECOND`
below is a fixed constant, not a `Settings` field — so they are built exactly once, at this
module's own top level, precisely the way `routers/auth.py`'s own `_RELIC_HTTP_CLIENT`/
`_RELIC_RATE_LIMITER` already are: a plain, unannotated module-scope assignment from
`build_async_client_resources`, which is what lets this file build a shared client without ever
writing `import httpx` itself (`tests/architecture/test_import_graph.py` enforces constitution
III by scanning this file, among others, for exactly that import — `packages/providers` is "the
one place a network client is allowed to live", per that test's own docstring). Module-scope, not
function-scope, is safe here specifically because `ingest_stages.py` itself is never imported at
application cold start (`routers/cron.py`'s own docstring: `build_ingest_stages` is imported
*inside* the one handler that calls it) — so this runs once, the first time that handler actually
fires, and never merely because the app was imported.

The AOEMS rate limiter and the database engine *do* vary with `settings`
(`AOEMS_MAX_REQUESTS_PER_SECOND`, `DATABASE_URL`), so they cannot be built at module scope before
any `Settings` exists; `_process_resources` below builds each once, lazily, on first use, and
caches it for the rest of the process — reused across calls within one process, never torn down
explicitly.

Caching was chosen over explicit teardown (closing the old client/engine and building fresh ones
every call) because teardown alone would still leave the *rate limiter* wrong: a `TokenBucket`
starts full, so a fresh one built and immediately used on every invocation re-arms the burst
allowance every cycle regardless of whether the previous one was ever closed. Only something that
survives *between* calls in the same process — a cache, not a release — keeps `ratelimit.py`'s
"serially, at most 1 request per second" holding across invocations rather than only within one.
Caching also needs no host-specific hook to be correct: it works identically whether the process
serves one invocation (`api/cron/ingest.py`) or thousands (`routers/cron.py`), which explicit
teardown-and-rebuild does too for the *leak*, but not for the pacing — so caching is the one choice
that fixes both halves of the defect with a single, host-agnostic mechanism (constitution XII).

**What this still does not guarantee.** A serverless platform is free to run two invocations of
the same logical cron trigger in two separate OS processes (a retried Vercel invocation, two
overlapping triggers). No in-process cache — caching or teardown, either one — can pace those
against each other: each process starts its own token bucket full. The 21-day capture budget and
the "stop the whole run" behaviour on `ProviderRateLimited` (`ratelimit.py`, `contracts/
providers.md`) are what absorb that gap; this module only makes the *common* case (one process,
many sequential calls, which is what `routers/cron.py` actually does) correctly serial.

**The cache key is `settings`' own values, never `Settings` identity or a bare process-wide
singleton.** `Settings` is not hashable (no `frozen=True` in its `model_config`) and is rebuilt
per test (`environment`'s `get_settings.cache_clear()`), so a cache keyed on the `Settings` object
itself, or on nothing at all, would either raise or — worse — silently hand a `CaptureDrain` built
for one `DATABASE_URL` an engine that was actually built for a different one the moment a test (or
a future multi-tenant deployment) builds two different `Settings` in one process. The cache is
therefore keyed on `(database_url, aoems_max_requests_per_second)`, the two `settings` fields that
actually change what gets built.

**A cached `AsyncEngine`, matching `deps.get_engine`'s own choice, not the `deps.py` instance
itself.** `packages/storage`'s `build_engine` docstring already says an `AsyncEngine` is "the one
... a process should hold for its lifetime"; building a fresh one per call ignored that. `NullPool`
(research §4) is about the *connection pool* — each checkout opens a DBAPI connection and closes it
immediately on checkin, so no pool of idle connections sits between calls regardless of how many
engines exist — but the engine object itself is not free to construct repeatedly, and repeated
construction is exactly the leak this task closes for the long-lived process. It is not reused from
`deps.py` directly: `deps.get_engine` is bound to `deps.get_settings()`'s own singleton and cannot
answer for a caller that (as `test_build_ingest_stages_wires_the_fairness_quota_from_settings`
does) passes a `settings` built independently of that singleton. Caching here, keyed on
`database_url`, gets the same "one engine per process" property without adding that dependency.

Every provider call is recorded through a `provider_calls` row (constitution III: "a
`provider_calls` record of every call"), written on its own short-lived session — the same
discipline `routers/auth.py`'s own `_async_call_sink` already established for sign-in, applied here
for the first time to the daily bulk cycle.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_api.settings import Settings
from aoe2stats_ingester.capture import CaptureDrain
from aoe2stats_ingester.discover import DiscoverStage
from aoe2stats_ingester.ratelimit import build_aoems_rate_limiter, build_aoems_retry_policy
from aoe2stats_ingester.reconcile import ReconcileStage
from aoe2stats_ingester.run import Stage
from aoe2stats_providers.aoems.provider import AoemsReplayProvider
from aoe2stats_providers.base import AsyncProviderCallSink, ProviderCallRecord, TokenBucket
from aoe2stats_providers.relic.matches import RelicMatchHistoryProvider
from aoe2stats_providers.relic.profile import RelicProfileProvider
from aoe2stats_providers.wiring import build_async_client_resources
from aoe2stats_storage.models import ProviderCall
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

# Bulk-cycle traffic against Relic's match-history/profile endpoints, not the interactive sign-in
# traffic `routers/auth.py`'s own `_RELIC_RATE_PER_SECOND` constant governs. No `Settings` field
# covers this source specifically — only the replay endpoint (`AOEMS_MAX_REQUESTS_PER_SECOND`) is
# tuned through configuration — so this is a fixed, documented constant, exactly like that sibling.
_RELIC_RATE_PER_SECOND = 5.0

# `contracts/providers.md`'s shared obligation: "takes an explicit timeout; there is no default
# that means 'forever'." A bulk cycle can afford to wait longer per call than an interactive
# sign-in, so this is more generous than `routers/auth.py`'s own 10 s constant.
_PROVIDER_TIMEOUT_SECONDS = 30.0

# Built once, at import time, and held for the process's lifetime — see the module docstring's
# T060a paragraph on why this mirrors `routers/auth.py`'s own module-scope `_RELIC_HTTP_CLIENT`/
# `_RELIC_RATE_LIMITER` instead of a per-`Settings` cache: neither value ever varies with
# `settings`. Deliberately unannotated, exactly like that sibling — the type is inferred from
# `build_async_client_resources`'s own return annotation, which is what lets this module share an
# `httpx.AsyncClient` without ever writing `import httpx` itself.
_RELIC_HTTP_CLIENT, _RELIC_RATE_LIMITER = build_async_client_resources(_RELIC_RATE_PER_SECOND)


@dataclass(frozen=True)
class _ProcessResources:
    """The one `settings`-dependent, connection-pooled object set this process holds per distinct
    `(database_url, aoems_max_requests_per_second)` pair — see the module docstring's T060a
    paragraphs for why these are cached rather than rebuilt, or torn down, on every call. The
    Relic client and its rate limiter are not here: they never vary with `settings` and are held
    as the module-scope constants above instead.
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    aoems_rate_limiter: TokenBucket


# Keyed on the two `settings` fields that actually determine what gets built — never on `Settings`
# itself, which is unhashable and rebuilt per test. See the module docstring's "cache key"
# paragraph. Module-level and process-wide by construction: this is the one cache every call to
# `build_ingest_stages` in this process shares, exactly what T060a asks for.
_process_resources_cache: dict[tuple[str, float], _ProcessResources] = {}


def _process_resources(settings: Settings) -> _ProcessResources:
    """The cached engine/rate-limiter set for `settings`' `(database_url,
    aoems_max_requests_per_second)`, building it once and reusing it on every later call with an
    equal key. No `await` happens below, so this is atomic with respect to the event loop even
    though it is called from async code — no lock is needed."""
    key = (settings.database_url, settings.aoems_max_requests_per_second)
    resources = _process_resources_cache.get(key)
    if resources is None:
        engine = build_engine(settings.database_url)
        resources = _ProcessResources(
            engine=engine,
            session_factory=build_session_factory(engine),
            aoems_rate_limiter=build_aoems_rate_limiter(settings.aoems_max_requests_per_second),
        )
        _process_resources_cache[key] = resources
    return resources


def _build_call_sink(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncProviderCallSink:
    """Writes one `provider_calls` row per call, on its own short-lived session committed
    immediately — see the module docstring for why this mirrors `routers/auth.py`'s own
    `_async_call_sink` rather than queuing onto a session a stage's own unit of work might roll
    back.
    """

    async def _sink(record: ProviderCallRecord) -> None:
        async with session_factory() as session:
            session.add(
                ProviderCall(
                    provider=record.provider,
                    endpoint=record.endpoint,
                    status_code=record.status_code,
                    duration_ms=record.duration_ms,
                    called_at=record.called_at,
                    rate_limited=record.rate_limited,
                )
            )
            await session.commit()

    return _sink


def build_ingest_stages(settings: Settings) -> tuple[Stage, ...]:
    """`(DiscoverStage, ReconcileStage, CaptureDrain)`, in that order — the whole cycle `run.py`
    drains stage by stage (discover, reconcile, drain), every collaborator built from `settings`
    alone. See the module docstring for why this is the one place production ever constructs any
    of the three.
    """
    # Lazy: see the module docstring's paragraph on why the engine is never imported at this
    # module's own top level.
    from aoe2stats_replay_engine.aoe2rec import Aoe2RecValidator

    # T060a: built once per process and cached, never rebuilt (and never torn down) on every
    # call — see the module docstring's paragraphs on why caching, not teardown, is the fix.
    resources = _process_resources(settings)
    session_factory = resources.session_factory
    call_sink = _build_call_sink(session_factory)

    match_history_provider = RelicMatchHistoryProvider(
        client=_RELIC_HTTP_CLIENT,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_RELIC_RATE_LIMITER,
        call_sink=call_sink,
    )
    profile_provider = RelicProfileProvider(
        client=_RELIC_HTTP_CLIENT,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_RELIC_RATE_LIMITER,
        call_sink=call_sink,
    )
    replay_provider = AoemsReplayProvider(
        client=_RELIC_HTTP_CLIENT,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=resources.aoems_rate_limiter,
        retry_policy=build_aoems_retry_policy(),
        call_sink=call_sink,
    )

    object_store = ObjectStore(
        ObjectStoreConfig(
            endpoint_url=settings.s3_endpoint_url,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            region=settings.s3_region,
        )
    )

    discover = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_history_provider,
        profile_provider=profile_provider,
        capture_budget_days=settings.capture_budget_days,
    )
    reconcile = ReconcileStage(
        session_factory=session_factory,
        match_history_provider=match_history_provider,
        capture_budget_days=settings.capture_budget_days,
    )
    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=replay_provider,
        object_store=object_store,
        validator=Aoe2RecValidator(),
        capture_budget_days=settings.capture_budget_days,
        replay_publication_grace_hours=settings.replay_publication_grace_hours,
        max_captures_per_user_per_run=settings.ingest_max_captures_per_user_per_run,
        quota_exempt_days=settings.ingest_quota_exempt_days,
    )

    return (discover, reconcile, drain)
