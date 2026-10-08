"""T671: a native engine panic on the analysis path is contained, as capture contains it.

Production, 2026-10-05: `POST /api/analyze` answered 500 for match 511523321 (game build 185872).
`aoe2rec-py` raised `pyo3_runtime.PanicException` from inside `extract`, which inherits
`BaseException` directly and not `Exception`, so `_extract_and_publish`'s `(ReplayValidationError,
ValueError)` clause never saw it: the request failed, the claimed row stayed `running`, and once its
lease lapsed the next request fetched the recording from the source again (constitution I).

`aoe2stats_ingester.capture._validate_with_barrier` is the capture path's barrier and
`apps/ingester/tests/test_quarantine.py` is its test: a bespoke `BaseException` subclass stands in
for the panic, because the real class is only importable where the native module is. The same is
done here, so this file needs no engine and no recording.

Three things are pinned:

- A panic ends a first analysis `failed`, with the real class name and a fixed sentence recorded -
  never the engine's own text, which `routers/matches.py` would show to the person who asked (T672a)
  - and the recording is fetched from the source exactly once however often it is asked for. The
  full text reaches the log instead.
- A panic on a recompute leaves the analysis being replaced exactly as it was served (T666c).
- `asyncio.CancelledError`, `KeyboardInterrupt`, `SystemExit` and `GeneratorExit` are not a verdict
  on the recording: they propagate out of `run_once` and leave the row as the claim left it. Each
  inherits `BaseException` directly, exactly as the panic does, so it is the clause order in
  `_extract_and_publish` that these cases pin.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_analyzer import run as run_module
from aoe2stats_core.replay.events import CanonicalEvent
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    User,
)
from aoe2stats_storage.objects import ObjectNotFound
from aoe2stats_storage.repositories.base import session_scope

# `session_factory` and `clean_database` come from `apps/analyzer/tests/conftest.py`.

_BUDGET_SECONDS = 300
_LEASE_SECONDS = 300  # ANALYSIS_LEASE_SECONDS: not below api/analyze.py's maxDuration
_MAX_ATTEMPTS = 3
_ENGINE_NAME = "aoe2rec-py"
_ENGINE_VERSION_1 = "0.1.21"
_ENGINE_VERSION_2 = "0.1.22"  # a later parser version: the published analysis is stale under it

#: The text of a real `pyo3_runtime.PanicException`, measured from `aoe2rec-py` 0.1.21 on a
#: recording of game build 185872 (T672a): 770 characters of terminal escape codes (`\x1b[1m`), a
#: backtrace banner and the engine's crate paths. Embedded as a literal, not rebuilt from a sketch
#: of it, so the assertions below meet the text a person would have been shown.
_MEASURED_PANIC_MESSAGE = (
    "called `Result::unwrap()` on an `Err` value: \n"
    " \u257a\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2505 Bac"
    "ktrace \u2505\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2578\n"
    "\n"
    " 0: \x1b[1m\x1b[1mError: bad magic at 0x7f376: [0, 0]\x1b[22m\n"
    "           \x1b[1mWhile parsing field 'unknown1' in InnerUnknownPlayer"
    "Struct\x1b[22m\x1b[22m\n"
    "     at crates/aoe2rec/src/header/mod.rs:422\n"
    " 1: \x1b[1mWhile parsing field 'unknown_inner' in UnknownPlayerStruct"
    "\x1b[22m\n"
    "     at crates/aoe2rec/src/header/mod.rs:445\n"
    " 2: \x1b[1mWhile parsing field 'unknown_struct' in PlayerInit\x1b[22m"
    "\n"
    "     at crates/aoe2rec/src/header/mod.rs:501\n"
    " 3: \x1b[1mWhile parsing field 'players' in Initial\x1b[22m\n"
    "     at crates/aoe2rec/src/header/mod.rs:404\n"
    " 4: \x1b[1mWhile parsing field 'initial' in RecHeader\x1b[22m\n"
    "     at crates/aoe2rec/src/header/mod.rs:38\n"
    "\n"
    " \u257a\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2578\n"
    "\n"
    ""
)


_FIXED_SENTENCE = "the replay engine crashed while reading this recording"


@pytest.fixture(autouse=True)
def _enable_the_analyzer_logger() -> Iterator[None]:
    """`infra/migrations/env.py` runs `logging.config.fileConfig` the first time the throwaway
    database is migrated, which disables every logger that already exists - this package's among
    them - so a `caplog` assertion would otherwise depend on test order (the identical fixture in
    `test_run_once.py`)."""
    run_module.logger.disabled = False
    yield
    run_module.logger.disabled = False


class PanicException(BaseException):
    """Stands in for `pyo3_runtime.PanicException`: inherits `BaseException` directly and not
    `Exception`, which is the property the production failure turned on. Named as the real class
    is, because the class name is what a `failed` row records."""


@dataclass(frozen=True, slots=True)
class _Timeline:
    engine_name: str
    engine_version: str
    point_of_view_profile_id: int
    world_time_ms: int
    participants: tuple = ()


class _Provider:
    """Counts fetches and raises past `max_calls`: a second fetch is the failure under test."""

    def __init__(self, *, max_calls: int) -> None:
        self._max_calls = max_calls
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        if len(self.calls) >= self._max_calls:
            raise AssertionError(f"fetch_replay called a {len(self.calls) + 1}th time")
        self.calls.append((game_id, profile_id))
        return ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip")


class _ForbiddenProvider:
    """A recompute reads the retained bytes; the source must never be reached."""

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        raise AssertionError("a recompute must not reach the source")


class _Store:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.objects[key] = body
        self.put_calls.append(key)

    async def put_if_absent(
        self, key: str, body: bytes, *, content_type: str = "application/zip"
    ) -> bool:
        if key in self.objects:
            return False
        await self.put(key, body, content_type=content_type)
        return True

    async def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]


class _Extractor:
    """Returns an empty timeline, or raises `raises` from `extract` - the call the native engine
    sits behind. `max_calls` is a canary on a parse that must not happen again."""

    def __init__(
        self,
        *,
        point_of_view_profile_id: int,
        engine_version: str = _ENGINE_VERSION_1,
        raises: BaseException | None = None,
        max_calls: int | None = None,
    ) -> None:
        self.engine_name = _ENGINE_NAME
        self.engine_version = engine_version
        self.engine_dependencies = {_ENGINE_NAME: engine_version}
        self._profile_id = point_of_view_profile_id
        self._raises = raises
        self._max_calls = max_calls
        self.calls = 0

    def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]:
        return iter(())

    def extract(self, zip_bytes: bytes) -> _Timeline:
        if self._max_calls is not None and self.calls >= self._max_calls:
            raise AssertionError(f"extract() called a {self.calls + 1}th time")
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return _Timeline(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            point_of_view_profile_id=self._profile_id,
            world_time_ms=1_200_000,
        )


async def _seed(
    session_factory: async_sessionmaker[AsyncSession], *, game_id: int
) -> tuple[int, uuid.UUID]:
    """A match completed a day ago with two participants, and a user to ask. Returns the profile id
    the run will take its point of view from and the user."""
    profile_a, profile_b = game_id + 1, game_id + 2
    user_id = uuid.uuid4()
    async with session_scope(session_factory) as session:
        session.add(User(id=user_id))
        for profile_id in (profile_a, profile_b):
            session.add(AoeProfile(profile_id=profile_id, alias=f"Player {profile_id}"))
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=datetime.now(UTC) - timedelta(days=1),
                duration_seconds=1800,
                source="relic",
                raw_payload={},
            )
        )
        for index, profile_id in enumerate((profile_a, profile_b)):
            session.add(
                MatchPlayer(
                    game_id=game_id,
                    profile_id=profile_id,
                    team_id=index,
                    civ_id=1,
                    color_id=index,
                    result="win" if index == 0 else "loss",
                )
            )
    return profile_a, user_id


async def _row(session_factory: async_sessionmaker[AsyncSession], game_id: int) -> MatchAnalysis:
    async with session_scope(session_factory) as session:
        row = await session.get(MatchAnalysis, game_id)
    assert row is not None
    return row


async def _ask(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    user_id: uuid.UUID,
    provider: Any,
    extractor: _Extractor,
    store: _Store,
) -> None:
    await run_module.run_once(
        game_id,
        _BUDGET_SECONDS,
        user_id,
        lease_seconds=_LEASE_SECONDS,
        max_attempts=_MAX_ATTEMPTS,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )


async def test_a_panic_fails_a_first_analysis_and_the_source_is_fetched_once(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    game_id = 500_671_100
    profile_id, user_id = await _seed(session_factory, game_id=game_id)
    provider = _Provider(max_calls=1)
    store = _Store()

    def panicking() -> _Extractor:
        return _Extractor(
            point_of_view_profile_id=profile_id,
            raises=PanicException(_MEASURED_PANIC_MESSAGE),
            max_calls=1,
        )

    extractor = panicking()
    caplog.set_level(logging.WARNING, logger="aoe2stats_analyzer")
    # Must not raise: a panic that escapes is a 500 and leaves the row `running`.
    await _ask(
        session_factory,
        game_id=game_id,
        user_id=user_id,
        provider=provider,
        extractor=extractor,
        store=store,
    )

    row = await _row(session_factory, game_id)
    assert row.state == MatchAnalysisState.FAILED
    assert row.error_class == "PanicException"
    # What `routers/matches.py` prints verbatim: a fixed sentence, none of the engine's text.
    assert row.error_message == _FIXED_SENTENCE
    assert "\x1b" not in row.error_message
    assert "crates/" not in row.error_message
    assert "Backtrace" not in row.error_message
    # The full text is for the operator: it reaches the log, escape codes and all.
    assert any(_MEASURED_PANIC_MESSAGE in record.getMessage() for record in caplog.records)
    assert row.result_key is None
    assert row.identity_digest is None
    assert not any(key.startswith("analyses/") for key in store.put_calls)
    assert len(provider.calls) == 1
    assert extractor.calls == 1

    # Even once the claim's lease would have lapsed, the next request neither fetches nor parses
    # again: `failed` is terminal, and `provider` and `extractor` raise past their first call.
    async with session_scope(session_factory) as session:
        stored = await session.get(MatchAnalysis, game_id)
        assert stored is not None
        stored.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5)
    await _ask(
        session_factory,
        game_id=game_id,
        user_id=user_id,
        provider=provider,
        extractor=extractor,
        store=store,
    )
    assert len(provider.calls) == 1
    assert (await _row(session_factory, game_id)).state == MatchAnalysisState.FAILED


async def test_a_panic_on_a_recompute_keeps_the_analysis_it_was_replacing(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    game_id = 500_671_200
    profile_id, user_id = await _seed(session_factory, game_id=game_id)
    store = _Store()
    await _ask(
        session_factory,
        game_id=game_id,
        user_id=user_id,
        provider=_Provider(max_calls=1),
        extractor=_Extractor(point_of_view_profile_id=profile_id, max_calls=1),
        store=store,
    )
    published = await _row(session_factory, game_id)
    assert published.state == MatchAnalysisState.PUBLISHED
    assert published.result_key is not None
    objects_before = dict(store.objects)
    puts_before = list(store.put_calls)

    # A newer parser makes the row stale, so this asks to recompute from the retained bytes.
    caplog.set_level(logging.WARNING, logger="aoe2stats_analyzer")
    panicking = _Extractor(
        point_of_view_profile_id=profile_id,
        engine_version=_ENGINE_VERSION_2,
        raises=PanicException(_MEASURED_PANIC_MESSAGE),
        max_calls=1,
    )
    await _ask(
        session_factory,
        game_id=game_id,
        user_id=user_id,
        provider=_ForbiddenProvider(),
        extractor=panicking,
        store=store,
    )

    after = await _row(session_factory, game_id)
    assert panicking.calls == 1
    assert any(_MEASURED_PANIC_MESSAGE in record.getMessage() for record in caplog.records)
    assert after.state == MatchAnalysisState.PUBLISHED
    assert after.result_key == published.result_key
    assert after.identity_digest == published.identity_digest
    assert after.parser_version == published.parser_version
    assert after.error_class is None
    assert store.objects == objects_before
    assert store.put_calls == puts_before


@pytest.mark.parametrize(
    "interruption",
    [asyncio.CancelledError(), KeyboardInterrupt(), SystemExit(1), GeneratorExit()],
    ids=["CancelledError", "KeyboardInterrupt", "SystemExit", "GeneratorExit"],
)
async def test_an_interruption_is_not_a_verdict_on_the_recording(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    interruption: BaseException,
) -> None:
    """The contrast to the panic: these inherit `BaseException` directly too, and must still leave
    `run_once`. The row stays as the claim left it - `running`, with its lease - for the next
    request to resume once the lease lapses, exactly as for an invocation killed mid-parse."""
    game_id = 500_671_300
    profile_id, user_id = await _seed(session_factory, game_id=game_id)
    provider = _Provider(max_calls=1)

    with pytest.raises(type(interruption)):
        await _ask(
            session_factory,
            game_id=game_id,
            user_id=user_id,
            provider=provider,
            extractor=_Extractor(
                point_of_view_profile_id=profile_id, raises=interruption, max_calls=1
            ),
            store=_Store(),
        )

    row = await _row(session_factory, game_id)
    assert row.state == MatchAnalysisState.RUNNING
    assert row.error_class is None
    assert row.error_message is None
    assert len(provider.calls) == 1
