"""Build the real, provider-backed dependencies `run_once` needs, from `Settings` (T366).

Mirrors `ingest_stages.py`'s own composition-root pattern: `api/analyze.py` calls
`build_analyze_dependencies(settings)` on every invocation and passes the result straight through
to `apps/analyzer/src/aoe2stats_analyzer/run.py::run_once`'s own keyword arguments, exactly as both
production cron entrypoints (`routers/cron.py`, `api/cron/ingest.py`) call `build_ingest_stages
(settings)` and pass its result through as `run_once`'s own `stages=` — so `run_once` itself stays
the one authority over what it does with them, and `api/analyze.py` stays the "ten-line caller"
`tasks.md` asks for.

**The replay engine is imported lazily, inside `build_analyze_dependencies`, never at this
module's own top level** — the identical discipline `ingest_stages.py`'s own module docstring
carries for the identical reason: `apps/api/tests/test_engine_isolation.py` asserts importing
`aoe2stats_api.app` never loads `aoe2rec_py`. This module is reachable from `aoe2stats_api` even
though nothing under `aoe2stats_api.app`'s own import chain ever imports it — `api/analyze.py` is
the one caller, and (like `api/cron/ingest.py` importing `ingest_stages`) it is not part of that
chain.

**One shared `httpx.AsyncClient`, one rate limiter, one process-lifetime engine and session
factory, cached per `(database_url, aoems_max_requests_per_second)`** — the exact key
`ingest_stages.py::_process_resources` already uses, for the identical reason: those are the only
two `settings` fields either module's cached resources depend on, and a Vercel function instance
that stays warm across two `POST /api/analyze` calls must still pace the second one against the
first. `ingest_stages.py`'s own "what this still does not guarantee" paragraph applies here
unchanged: two separate OS processes each start their own token bucket full regardless of this
cache.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_api.settings import Settings
from aoe2stats_core.replay.analysis import ReplayExtractor
from aoe2stats_ingester.ratelimit import build_aoems_rate_limiter, build_aoems_retry_policy
from aoe2stats_providers.aoems.provider import AoemsReplayProvider
from aoe2stats_providers.base import AsyncProviderCallSink, ProviderCallRecord, TokenBucket
from aoe2stats_providers.wiring import build_async_client_resources
from aoe2stats_storage.models import ProviderCall
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

# Interactive, on-demand traffic — a person is waiting on this one call — not the ingester's own
# daily bulk cycle, matching `routers/replays.py`'s identical `_AOEMS_PROVIDER_TIMEOUT_SECONDS`.
_PROVIDER_TIMEOUT_SECONDS = 10.0

# Built once, at import time, and held for the process's lifetime — this value never varies with
# `settings`, matching `ingest_stages.py`'s own module-scope Relic client/rate-limiter pair and
# `routers/replays.py`'s own `_AOEMS_HTTP_CLIENT`. The `TokenBucket` this call also returns is
# discarded (`_`): `build_aoems_rate_limiter` below is the policy this provider actually needs
# (serial capacity of one), not `build_async_client_resources`'s generic default.
_AOEMS_HTTP_CLIENT, _ = build_async_client_resources(1.0)


@dataclass(frozen=True)
class AnalyzeDependencies:
    """Everything `run_once` needs beyond `game_id`/`budget_seconds`/`requested_by_user_id`
    (`apps/analyzer/src/aoe2stats_analyzer/run.py`'s own signature) — the composed, real
    collaborators `api/analyze.py` passes straight through."""

    session_factory: async_sessionmaker[AsyncSession]
    replay_provider: AoemsReplayProvider
    extractor: ReplayExtractor
    object_store: ObjectStore


@dataclass(frozen=True)
class _ProcessResources:
    """The one `settings`-dependent, connection-pooled object set this process holds per distinct
    `(database_url, aoems_max_requests_per_second)` pair — see the module docstring."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    aoems_rate_limiter: TokenBucket


# Keyed on the two `settings` fields that actually determine what gets built — never on `Settings`
# itself, which is unhashable and rebuilt per test (`ingest_stages.py`'s identical cache).
_process_resources_cache: dict[tuple[str, float], _ProcessResources] = {}


def _process_resources(settings: Settings) -> _ProcessResources:
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
    immediately — mirrors `ingest_stages.py::_build_call_sink` exactly."""

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


def build_analyze_dependencies(settings: Settings) -> AnalyzeDependencies:
    """The real `session_factory`/`replay_provider`/`extractor`/`object_store` `run_once` needs,
    every collaborator built from `settings` alone — see the module docstring for why this is the
    one place `api/analyze.py` ever constructs any of them."""
    # Lazy: see the module docstring's paragraph on why the engine is never imported at this
    # module's own top level.
    from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

    resources = _process_resources(settings)
    session_factory = resources.session_factory
    call_sink = _build_call_sink(session_factory)

    replay_provider = AoemsReplayProvider(
        client=_AOEMS_HTTP_CLIENT,
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

    extractor = Aoe2RecExtractor(max_raw_bytes=settings.analysis_max_raw_bytes)

    return AnalyzeDependencies(
        session_factory=session_factory,
        replay_provider=replay_provider,
        extractor=extractor,
        object_store=object_store,
    )
