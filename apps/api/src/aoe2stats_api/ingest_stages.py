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

**One shared `httpx.AsyncClient`, two rate limiters.** `RelicMatchHistoryProvider` and
`RelicProfileProvider` share one process-wide client and one generic token bucket — there is no
per-source Relic rate configured in `Settings` for the bulk cycle, so `_RELIC_RATE_PER_SECOND`
below is a fixed, documented constant, the same shape as `routers/auth.py`'s own interactive-
traffic constant. `AoemsReplayProvider` reuses that same client but never that bucket:
`AOEMS_MAX_REQUESTS_PER_SECOND` is a `Settings` value precisely because the replay endpoint's
politeness ceiling is independently tuned (`.env.example`), and `ratelimit.build_aoems_rate_limiter`
(T052) is what caps it to exactly one outstanding request regardless of the configured rate —
reusing the generic Relic bucket here would silently drop that "serially, not merely paced"
guarantee `contracts/providers.md` documents for this one source.

**A fresh `AsyncEngine`, not the FastAPI request-scoped one `deps.py` caches.** `deps.get_engine`/
`get_session_factory` are bound to `deps.get_settings()`'s own cached, process-wide instance and
never cleared between calls; building straight from the `settings` this function is actually
handed keeps this module pure and independently testable (a caller can pass a differently built
`Settings`), and costs nothing extra: `build_engine`'s `NullPool` (`packages/storage`) means this
process never holds a connection open between calls regardless of how many `AsyncEngine` objects
point at the same database — `run_once`'s own `_default_session_factory` already makes exactly
this same choice for its own, separate, `ingest_runs` bookkeeping.

Every provider call is recorded through a `provider_calls` row (constitution III: "a
`provider_calls` record of every call"), written on its own short-lived session — the same
discipline `routers/auth.py`'s own `_async_call_sink` already established for sign-in, applied here
for the first time to the daily bulk cycle.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_api.settings import Settings
from aoe2stats_ingester.capture import CaptureDrain
from aoe2stats_ingester.discover import DiscoverStage
from aoe2stats_ingester.ratelimit import build_aoems_rate_limiter, build_aoems_retry_policy
from aoe2stats_ingester.reconcile import ReconcileStage
from aoe2stats_ingester.run import Stage
from aoe2stats_providers.aoems.provider import AoemsReplayProvider
from aoe2stats_providers.base import AsyncProviderCallSink, ProviderCallRecord
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

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    call_sink = _build_call_sink(session_factory)

    client, relic_rate_limiter = build_async_client_resources(_RELIC_RATE_PER_SECOND)

    match_history_provider = RelicMatchHistoryProvider(
        client=client,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=relic_rate_limiter,
        call_sink=call_sink,
    )
    profile_provider = RelicProfileProvider(
        client=client,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=relic_rate_limiter,
        call_sink=call_sink,
    )
    replay_provider = AoemsReplayProvider(
        client=client,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=build_aoems_rate_limiter(settings.aoems_max_requests_per_second),
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
