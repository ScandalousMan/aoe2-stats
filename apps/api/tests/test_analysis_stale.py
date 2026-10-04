"""T666g: the `stale` flag on match-detail's `analysis` summary compares the **identity digest**,
not the parser version alone.

**The defect this pins.** `routers/matches.py` computed `stale` as "published and the row's
`parser_version` differs from the installed engine's". The web reader offers Recompute only when
`stale` is true, so a knowledge refresh or an analytics change - both of which change the identity
digest `run.py`'s staleness test (T657a) compares, and neither of which changes the parser version -
never reached a recompute outside the analyzer's own tests (`contracts/analysis-document.md`: "a
recompute has to be triggered"). Each test here seeds a published row whose stored digest was
computed under one identity, changes exactly one thing about the *current* identity, and reads what
the API tells the browser.

**The digest is computed the way the analyzer computes it.** `extract.current_identity_digest` is
the one function that builds a digest from a recording's key and checksum, a build and the installed
engine; the seeded rows below call it, and the API under test reaches it through
`aoe2stats_analyzer.staleness`, the function the analyzer's `_is_stale` also delegates to. The last
test pins the property that matters: for every case the API's answer equals what `run_once` would
decide for the same row, so the button and the recompute cannot disagree.

**What is deliberately different between the two.** A published row whose retained-recording row is
gone is *not stale* to the API (a recording that cannot be recomputed is not stale). The analyzer
still reads it as stale today and marks the match unavailable, which unpublishes a served analysis -
T666i's defect (a). The equality test carries that one case as `xfail(strict=True)`, so T666i
removes the marker or fails loudly.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.snapshot_refresh import (
    clear_snapshot_resolution_caches,
    isolate_snapshot_root,
    promote_a_refreshed_snapshot,
)

from aoe2stats_analyzer import extract
from aoe2stats_analyzer.extract import current_identity_digest
from aoe2stats_analyzer.run import _is_stale as analyzer_is_stale
from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_replay_engine.dependencies import read_engine_dependencies
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    RetainedRecording,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

SESSION_COOKIE_NAME = "session_id"

#: A build the packaged knowledge base holds a promoted snapshot for, so the identity's `knowledge`
#: component names a snapshot a refresh can then replace.
_SNAPSHOT_BUILD = 180059

_ENGINE_NAME = "aoe2rec-py"
_PROFILE_A = 940_100_001
_PROFILE_B = 940_100_002
_RECORDING_SHA = "b" * 64

_GAME_ID_BASE = 940_200_000


@dataclass(frozen=True)
class _Engine:
    """The three attributes the identity reads from the running engine, built from installed
    distribution metadata exactly as `Aoe2RecExtractor.__init__` builds them - never a constant."""

    engine_name: str
    engine_version: str
    engine_dependencies: dict[str, str]


def _installed_engine(version_suffix: str = "") -> _Engine:
    record = read_engine_dependencies(_ENGINE_NAME)
    return _Engine(
        engine_name=_ENGINE_NAME,
        engine_version=record.engine_version + version_suffix,
        engine_dependencies=record.as_mapping(),
    )


def _object_key(game_id: int) -> str:
    return f"retained-recordings/{game_id}/{_PROFILE_A}.zip"


def _digest(game_id: int, *, engine: _Engine, build: int = _SNAPSHOT_BUILD) -> str:
    return current_identity_digest(
        engine,
        recording={"object_key": _object_key(game_id), "sha256": _RECORDING_SHA},
        build=build,
    )


# --- Seeding, self-contained per this directory's convention -------------------------------------


async def _sign_in(client: TestClient, db_session: AsyncSession) -> None:
    user = User(allowlisted_at=datetime.now(UTC))
    db_session.add(user)
    await db_session.flush()
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db_session.add(
        UserSession(
            id=session_id, user_id=user.id, created_at=now, expires_at=now + timedelta(days=30)
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


async def _seed_match(db_session: AsyncSession, *, game_id: int) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=2),
            source="relic",
            raw_payload={"matchHistoryId": game_id},
        )
    )
    for profile_id in (_PROFILE_A, _PROFILE_B):
        await db_session.execute(
            pg_insert(AoeProfile)
            .values(profile_id=profile_id, alias=f"P{profile_id}", country="FR")
            .on_conflict_do_nothing(index_elements=[AoeProfile.profile_id])
        )
        db_session.add(MatchPlayer(game_id=game_id, profile_id=profile_id))
    await db_session.commit()


@dataclass(frozen=True)
class _Seed:
    """What one case stored. `digest` and `build` are what the published row carries; `retained`
    says whether the retained-recording row exists; `lease` is the open retry window, if any."""

    digest: str | None
    build: int | None = _SNAPSHOT_BUILD
    retained: bool = True
    lease: datetime | None = None


async def _seed_published(db_session: AsyncSession, *, game_id: int, seed: _Seed) -> None:
    await _seed_match(db_session, game_id=game_id)
    engine = _installed_engine()
    now = datetime.now(UTC)
    if seed.retained:
        db_session.add(
            RetainedRecording(
                game_id=game_id,
                profile_id=_PROFILE_A,
                object_key=_object_key(game_id),
                zip_bytes=1,
                zip_sha256=_RECORDING_SHA,
            )
        )
    db_session.add(
        MatchAnalysis(
            game_id=game_id,
            state=MatchAnalysisState.PUBLISHED,
            point_of_view_profile_id=_PROFILE_A,
            parser_name=engine.engine_name,
            # The parser version is the *same* in every case, deliberately: the old comparison saw
            # a published row on the running engine and answered "not stale" whatever else changed.
            parser_version=engine.engine_version,
            identity_digest=seed.digest,
            recording_build=seed.build,
            result_key=f"analyses/{game_id}/{seed.digest}.json",
            requested_at=now,
            finished_at=now,
            lease_expires_at=seed.lease,
        )
    )
    await db_session.commit()


def _api_stale(client: TestClient, game_id: int) -> bool:
    response = client.get(f"/api/matches/{game_id}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    analysis = response.json()["analysis"]
    assert analysis["state"] == "published"
    stale = analysis["stale"]
    assert isinstance(stale, bool)
    return stale


# --- Each case: how the stored identity differs from the current one ------------------------------
# A case is `(expected, prepare)`. `prepare` runs with the game id and a `MonkeyPatch`, seeds the
# row under the identity that was current *then*, then changes what is current *now* (or does not).

_Prepare = Callable[[AsyncSession, int, pytest.MonkeyPatch, Path], Awaitable[None]]


async def _parser_change(
    db_session: AsyncSession, game_id: int, _mp: pytest.MonkeyPatch, _tmp: Path
) -> None:
    """Stored under another parser version; the installed one is what the API sees."""
    stored = _digest(game_id, engine=_installed_engine("-superseded"))
    await _seed_published(db_session, game_id=game_id, seed=_Seed(digest=stored))


async def _knowledge_refresh(
    db_session: AsyncSession, game_id: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Same parser, same recording, same build; a real second snapshot is promoted afterwards."""
    root = isolate_snapshot_root(monkeypatch, tmp_path)
    stored = _digest(game_id, engine=_installed_engine())
    await _seed_published(db_session, game_id=game_id, seed=_Seed(digest=stored))
    promote_a_refreshed_snapshot(root, without_entity=("unit", "4"))


async def _analytics_change(
    db_session: AsyncSession, game_id: int, monkeypatch: pytest.MonkeyPatch, _tmp: Path
) -> None:
    """Same parser and knowledge; the analytics version moves on after the row was published."""
    stored = _digest(game_id, engine=_installed_engine())
    await _seed_published(db_session, game_id=game_id, seed=_Seed(digest=stored))
    monkeypatch.setattr(extract, "ANALYTICS_VERSION", f"{extract.ANALYTICS_VERSION}+next")


async def _identical(
    db_session: AsyncSession, game_id: int, _mp: pytest.MonkeyPatch, _tmp: Path
) -> None:
    stored = _digest(game_id, engine=_installed_engine())
    await _seed_published(db_session, game_id=game_id, seed=_Seed(digest=stored))


async def _open_retry_window(
    db_session: AsyncSession, game_id: int, _mp: pytest.MonkeyPatch, _tmp: Path
) -> None:
    """A stale identity whose last recompute was refused a moment ago (T666c): the lease column
    carries the retry window on a published row. Clicking would do nothing, so the button must not
    be offered."""
    stored = _digest(game_id, engine=_installed_engine("-superseded"))
    await _seed_published(
        db_session,
        game_id=game_id,
        seed=_Seed(digest=stored, lease=datetime.now(UTC) + timedelta(hours=1)),
    )


async def _expired_retry_window(
    db_session: AsyncSession, game_id: int, _mp: pytest.MonkeyPatch, _tmp: Path
) -> None:
    """The contrast: the same stale identity with the window already closed is stale again."""
    stored = _digest(game_id, engine=_installed_engine("-superseded"))
    await _seed_published(
        db_session,
        game_id=game_id,
        seed=_Seed(digest=stored, lease=datetime.now(UTC) - timedelta(minutes=1)),
    )


async def _no_stored_digest(
    db_session: AsyncSession, game_id: int, _mp: pytest.MonkeyPatch, _tmp: Path
) -> None:
    await _seed_published(db_session, game_id=game_id, seed=_Seed(digest=None))


async def _no_recorded_build(
    db_session: AsyncSession, game_id: int, _mp: pytest.MonkeyPatch, _tmp: Path
) -> None:
    stored = _digest(game_id, engine=_installed_engine())
    await _seed_published(db_session, game_id=game_id, seed=_Seed(digest=stored, build=None))


async def _no_retained_row(
    db_session: AsyncSession, game_id: int, _mp: pytest.MonkeyPatch, _tmp: Path
) -> None:
    """A stale identity, but nothing retained to recompute it from: not stale (T666i makes the
    analyzer serve the prior analysis here too)."""
    stored = _digest(game_id, engine=_installed_engine("-superseded"))
    await _seed_published(db_session, game_id=game_id, seed=_Seed(digest=stored, retained=False))


_CASES: tuple[tuple[str, bool, _Prepare], ...] = (
    ("parser-change", True, _parser_change),
    ("knowledge-refresh", True, _knowledge_refresh),
    ("analytics-change", True, _analytics_change),
    ("identical-identity", False, _identical),
    ("open-retry-window", False, _open_retry_window),
    ("expired-retry-window", True, _expired_retry_window),
    ("no-stored-digest", True, _no_stored_digest),
    ("no-recorded-build", True, _no_recorded_build),
    ("no-retained-row", False, _no_retained_row),
)


@pytest.fixture(autouse=True)
def _isolated_snapshot_caches() -> Any:
    """`snapshot_for` is `functools.cache`d for a process's lifetime; the knowledge-refresh case
    swaps the snapshot root, so a cached answer must never cross a test boundary."""
    clear_snapshot_resolution_caches()
    yield
    clear_snapshot_resolution_caches()


@pytest.mark.parametrize(
    ("index", "expected", "prepare"),
    [
        pytest.param(index, expected, prepare, id=case_id)
        for index, (case_id, expected, prepare) in enumerate(_CASES)
    ],
)
async def test_stale_compares_the_identity_digest_not_the_parser_version(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    index: int,
    expected: bool,
    prepare: _Prepare,
) -> None:
    """The row's parser version equals the installed engine's in every case, so a flag that reads
    only the parser version answers `False` everywhere. Only the identity digest tells these
    apart, and only the cases whose identity moved (or whose digest or build is unknown) are
    stale."""
    game_id = _GAME_ID_BASE + index
    await _sign_in(client, db_session)
    await prepare(db_session, game_id, monkeypatch, tmp_path)

    assert _api_stale(client, game_id) is expected


# --- The one-function property -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("index", "prepare"),
    [
        pytest.param(
            index,
            prepare,
            id=case_id,
            marks=(
                pytest.mark.xfail(
                    strict=True,
                    reason="T666i (a): the analyzer still reads a missing retained row as stale",
                )
                if case_id == "no-retained-row"
                else ()
            ),
        )
        for index, (case_id, _, prepare) in enumerate(_CASES)
    ],
)
async def test_the_apis_answer_is_the_analyzers_verdict_for_the_same_row(
    client: TestClient,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    index: int,
    prepare: _Prepare,
) -> None:
    """The button and the recompute cannot disagree: the flag the browser is given is exactly
    whether `run_once` would recompute this row on the next request. Both go through the one
    function in `aoe2stats_analyzer.staleness`, and this is what keeps it that way if either caller
    grows a condition of its own."""
    game_id = _GAME_ID_BASE + 100 + index
    await _sign_in(client, db_session)
    await prepare(db_session, game_id, monkeypatch, tmp_path)

    async with session_factory() as session:
        row = await session.get(MatchAnalysis, game_id)
    assert row is not None
    analyzer_verdict = await analyzer_is_stale(
        session_factory, row, extractor=_installed_engine(), now=datetime.now(UTC)
    )

    assert _api_stale(client, game_id) is analyzer_verdict
