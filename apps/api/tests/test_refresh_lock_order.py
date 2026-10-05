"""T459 — the on-view refresh must not deadlock against another writer of `aoe_profiles`, and a
lock conflict that does happen must degrade to a read from storage.

**The defect (production, 2026-10-04, `GET /api/players/212721/matches` -> 500,
`psycopg.errors.DeadlockDetected` in `discover.touch_aoe_profile`).** The player page fires
`GET /api/players/{id}` and `GET /api/players/{id}/matches` in parallel. Each request is one
transaction (`deps.py::get_session`), so every `aoe_profiles` row lock taken is held to commit.
The matches route touched profiles in Relic's *match order*, the summary route in the identity
block's order, and two non-monotonic orders over the same rows form a cycle. The ingester's
`DiscoverStage` and `ReconcileStage` wrote the same rows in match order inside their own
transactions, so the same cycle could abort **their** transaction — discovery, and with it capture
enqueueing (constitution I) — instead of a view.

**How the interleaving is made deterministic, not slept into.** `_TouchProbe` wraps
`discover.touch_aoe_profile` — the one primitive every writer goes through — and, after a session's
*first* touch has taken its row lock, parks that session until either the other session has also
made its first touch, or Postgres reports a backend waiting on a lock (`pg_stat_activity`). The
first condition is what forms the cycle against code that locks in conflicting orders (each side
then holds a different row and asks for the other's); the second is what lets code that locks in
one global order through without the harness itself deadlocking (the second session is blocked on
the first's row, so it can never "arrive"). Neither depends on a duration. `deadlock_timeout` is
lowered to 100 ms for the database so a real cycle is reported promptly instead of after the
default second.

**What each test proves.**

- `test_unordered_touches_deadlock_under_the_probe` is the positive control: two sessions touching
  the same rows in opposite orders *do* deadlock under this harness. Without it, the green route
  tests below could be green because the harness never formed a cycle at all.
- `test_parallel_summary_and_matches_views_complete` is T459 (a)/(b): the reproduction and, once
  fixed, its contrast. Against the pre-fix code it fails with `DeadlockDetected`.
- `test_ingester_discovery_racing_a_matches_view_completes` is (c).
- `test_lock_conflict_in_the_refresh_degrades_to_storage` and
  `test_other_database_errors_in_the_refresh_still_fail` are (d): `40P01`, `40001` and `55P03` (a
  `lock_timeout`) degrade, nothing else does.
- `test_match_detail_identity_refresh_touches_in_profile_id_order` covers the persistence of what
  `routers/matches.py::_fetch_match_identity` returns.

**T459a — the companion colour write is a writer too.** The review found the companion colour
fill writing `match_players` per row, in companion's order, outside the savepoint, on two routes
that T459 had just ordered. The tests at the bottom of this file are written against the *shape*
of the defect, not the two instances found:

- `test_every_row_lock_in_a_request_is_taken_in_the_global_order` records **every** row-locking
  statement (`INSERT`, `UPDATE`, `DELETE`, `SELECT ... FOR UPDATE`) each connection sends during a
  whole request, on each of the three routes, with companion answering colours, and asserts that a
  row is never *first* locked at a lower `(table rank, key)` than one already locked. A row
  already locked earlier in the transaction is exempt: touching it again cannot create a wait.
  The same test asserts that no provider call is made after the first write.
- `test_match_detail_racing_a_discovery_batch_completes` races the match-detail route against a
  `DiscoverStage` batch over the very same match, interleaved on conditions, never durations.
- `test_a_stored_colour_is_never_replaced_by_companions` is the precedence contrast.

**T459e — pseudonymisation is a writer too.** `routers/privacy.py::_pseudonymise_profile_ids`
(erasure, and the deferred third-party objection) inserts a placeholder `aoe_profiles` row,
rewrites `match_players` keys, and updates the original `aoe_profiles` row.
`test_pseudonymisation_takes_every_row_lock_in_the_global_order` drives `POST /api/privacy/erase`
(two linked profiles, stored in an order that is not ascending) and
`resolve_third_party_objection` under the recorder, and
`test_pseudonymisation_racing_a_discovery_batch_completes` races the erasure against a
`DiscoverStage` batch over a row both write.
"""

from __future__ import annotations

import asyncio
import itertools
import re
import secrets
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx
import pytest
from sqlalchemy import delete, event, select, text, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_api import security
from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_session
from aoe2stats_api.routers import matches as matches_router
from aoe2stats_api.routers import players as players_router
from aoe2stats_api.routers import privacy as privacy_router
from aoe2stats_api.settings import get_settings
from aoe2stats_core.privacy.erasure import PSEUDONYMISED_ALIAS
from aoe2stats_ingester import discover
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.discover import DiscoverStage
from aoe2stats_providers.base import (
    EnrichedParticipant,
    MatchEnrichment,
    RawMatch,
    RawProfile,
)
from aoe2stats_providers.relic.matches import RecentHistory
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    DataRequest,
    DataRequestKind,
    Match,
    MatchPlayer,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession
from aoe2stats_storage.repositories.base import session_scope

pytestmark = [pytest.mark.usefixtures("environment")]

SESSION_COOKIE_NAME = "session_id"

# Ids chosen so that *numeric* order, Relic's match order and the identity block's order are three
# visibly different things: ascending is SUBJECT < ALPHA < BRAVO.
_SUBJECT = 910_000_100
_ALPHA = 910_000_200
_BRAVO = 910_000_300

_MATCH_COMPLETED_AT = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
_VIEW_GAME_ID = 860_000_001
_INGEST_GAME_ID = 860_000_002
_STORED_GAME_ID = 860_000_003

#: Upper bound on how long a parked session waits for its peer or for a lock wait to show up. Only
#: ever reached when the harness itself is broken (never on a pass), so it is a guard against a
#: hung test run, not a tuning knob the outcome depends on.
_RENDEZVOUS_GUARD_SECONDS = 15.0


# --- Harness -------------------------------------------------------------------------------------


@pytest.fixture
async def fast_deadlock_detection(engine: AsyncEngine) -> AsyncIterator[None]:
    """Lower `deadlock_timeout` for the throwaway database so a real cycle is reported in 100 ms.
    `ALTER DATABASE ... SET` applies to connections opened afterwards; the engine is `NullPool`
    (`build_engine`), so every connection a request opens afterwards picks it up. Reset on the way
    out so the setting never outlives the test."""
    async with engine.connect() as raw_connection:
        connection = await raw_connection.execution_options(isolation_level="AUTOCOMMIT")
        name = (await connection.execute(text("SELECT current_database()"))).scalar_one()
        await connection.execute(text(f"ALTER DATABASE \"{name}\" SET deadlock_timeout = '100ms'"))
        try:
            yield
        finally:
            await connection.execute(text(f'ALTER DATABASE "{name}" RESET deadlock_timeout'))


@pytest.fixture
async def http(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[httpx.AsyncClient]:
    """The real app, its `get_session` pointed at the throwaway database through `session_scope`
    (the identical commit-or-rollback unit of work production gets), driven through httpx's ASGI
    transport so that several requests can be in flight on one event loop — `TestClient` serialises
    them. A server-side exception propagates out of `get`, which is exactly how a test reads a
    `500`."""
    app = create_app()

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


class _TouchProbe:
    """See the module docstring. It wraps `AsyncSession.execute` and acts on every `INSERT INTO
    aoe_profiles` — whether the pre-fix one-statement-per-row shape or the fixed multi-row one — so
    the same test drives both. `touches` maps a session's identity to the profile ids its profile
    inserts carried, in the order the statements carried them, so a test can also assert the
    *order* a writer used, not only that it survived."""

    def __init__(self, engine: AsyncEngine, *, peers: int = 2) -> None:
        self._engine = engine
        self._peers = peers
        self._arrived: set[int] = set()
        self.touches: dict[int, list[int]] = {}
        self.forced_error_sqlstate: str | None = None
        self._forced = False

    @staticmethod
    def _profile_ids_in(statement: Any) -> list[int] | None:
        """The `profile_id`s an `INSERT INTO aoe_profiles` statement carries, in `VALUES` order;
        `None` for any other statement."""
        table = getattr(statement, "table", None)
        if not getattr(statement, "is_insert", False) or getattr(table, "name", None) != (
            "aoe_profiles"
        ):
            return None
        params = statement.compile(dialect=postgresql.dialect()).params
        indexed: list[tuple[int, int]] = []
        for key, value in params.items():
            match = re.fullmatch(r"profile_id(?:_m(\d+))?", key)
            if match:
                indexed.append((int(match.group(1) or 0), value))
        return [value for _, value in sorted(indexed)]

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_execute = AsyncSession.execute

        async def spy(self_session: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
            profile_ids = self._profile_ids_in(statement)
            if profile_ids is None:
                return await real_execute(self_session, statement, *args, **kwargs)
            if self.forced_error_sqlstate is not None and not self._forced:
                self._forced = True
                await real_execute(
                    self_session,
                    text(
                        "DO $$ BEGIN RAISE EXCEPTION 'forced by T459' "
                        f"USING ERRCODE = '{self.forced_error_sqlstate}'; END $$"
                    ),
                )
            result = await real_execute(self_session, statement, *args, **kwargs)
            key = id(self_session)
            self.touches.setdefault(key, []).extend(profile_ids)
            if self.forced_error_sqlstate is None and key not in self._arrived:
                self._arrived.add(key)
                await self._park()
            return result

        monkeypatch.setattr(AsyncSession, "execute", spy)

    async def _park(self) -> None:
        deadline = asyncio.get_running_loop().time() + _RENDEZVOUS_GUARD_SECONDS
        while len(self._arrived) < self._peers:
            if await self._someone_is_waiting_on_a_lock():
                return
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError("the harness's peer never arrived and nothing is lock-blocked")
            await asyncio.sleep(0.01)

    async def _someone_is_waiting_on_a_lock(self) -> bool:
        async with self._engine.connect() as connection:
            waiting = await connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
            )
            return bool(waiting.scalar_one())


class _FakeRelic:
    """Stands in for `RelicMatchHistoryProvider`: history in one order, the identity block in
    another — the disagreement is the whole point."""

    def __init__(self, matches: Sequence[RawMatch], block: Sequence[RawProfile]) -> None:
        self._matches = list(matches)
        self._block = list(block)

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        return list(self._matches)

    async def recent_profiles(self, profile_ids: Sequence[int]) -> list[RawProfile]:
        return list(self._block)

    async def recent_matches_and_profiles(self, profile_ids: Sequence[int]) -> RecentHistory:
        return RecentHistory(matches=list(self._matches), profiles=list(self._block))


class _NoStandings:
    async def personal_stats(self, profile_ids: Sequence[int]) -> list[Any]:
        return []


class _DegradedCompanion:
    def is_degraded(self) -> bool:
        return True


def _install_fake_providers(monkeypatch: pytest.MonkeyPatch, relic: _FakeRelic) -> None:
    monkeypatch.setattr(players_router, "_build_match_history_provider", lambda _s: relic)
    monkeypatch.setattr(players_router, "_build_profile_provider", lambda _s: _NoStandings())
    monkeypatch.setattr(players_router, "_build_search_provider", lambda _s: _DegradedCompanion())
    monkeypatch.setattr(matches_router, "_build_match_history_provider", lambda _s: relic)


def _raw_match(game_id: int, players: tuple[int, ...]) -> RawMatch:
    return RawMatch(
        game_id=game_id,
        leaderboard_id=3,
        map_name="Arabia",
        patch="101.101",
        started_at=_MATCH_COMPLETED_AT - timedelta(minutes=30),
        completed_at=_MATCH_COMPLETED_AT,
        duration_seconds=1_800,
        player_profile_ids=players,
        raw_payload={"id": game_id, "source": "test_refresh_lock_order"},
    )


#: Relic's order for the viewed match: the subject first, then BRAVO, then ALPHA — not ascending.
_VIEW_MATCH = _raw_match(_VIEW_GAME_ID, (_SUBJECT, _BRAVO, _ALPHA))

#: The identity block's order: ALPHA, BRAVO, then the subject — the reverse of the match's, and
#: not ascending either.
_IDENTITY_BLOCK = (
    RawProfile(profile_id=_ALPHA, alias="Alpha", country="FR"),
    RawProfile(profile_id=_BRAVO, alias="Bravo", country="DE"),
    RawProfile(profile_id=_SUBJECT, alias="Subject", country="SE"),
)


async def _seed_signed_in_caller(
    http: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    async with session_factory() as session:
        user = User(allowlisted_at=now)
        session.add(user)
        await session.flush()
        session.add(
            UserSession(
                id=session_id, user_id=user.id, created_at=now, expires_at=now + timedelta(days=30)
            )
        )
        await session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    http.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


async def _seed_subject(
    session_factory: async_sessionmaker[AsyncSession], *, alias: str = "StoredSubject"
) -> None:
    async with session_factory() as session:
        session.add(
            AoeProfile(profile_id=_SUBJECT, alias=alias, alias_observed_at=datetime.now(UTC))
        )
        await session.commit()


async def _stored_aliases(session_factory: async_sessionmaker[AsyncSession]) -> dict[int, str]:
    async with session_factory() as session:
        rows = await session.execute(select(AoeProfile.profile_id, AoeProfile.alias))
        return dict(rows.all())  # type: ignore[arg-type]


# --- The positive control --------------------------------------------------------------------


async def test_unordered_touches_deadlock_under_the_probe(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    fast_deadlock_detection: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two sessions touching the same new rows in opposite orders deadlock under this harness.
    This is the shape of the production defect reduced to the primitive; if it ever stopped
    deadlocking, the route-level tests below would be green for the wrong reason."""
    probe = _TouchProbe(engine)
    probe.install(monkeypatch)

    async def touch_in_order(order: Sequence[int]) -> None:
        async with session_scope(session_factory) as session:
            for profile_id in order:
                await discover.touch_aoe_profile(session, profile_id)

    outcomes = await asyncio.gather(
        touch_in_order((_ALPHA, _BRAVO)), touch_in_order((_BRAVO, _ALPHA)), return_exceptions=True
    )

    failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    assert len(failures) == 1, f"expected exactly one deadlock victim, got {outcomes!r}"
    assert isinstance(failures[0], DBAPIError)
    assert getattr(failures[0].orig, "sqlstate", None) == "40P01"


# --- T459 (a) / (b) ----------------------------------------------------------------------------


async def test_parallel_summary_and_matches_views_complete(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    fast_deadlock_detection: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The player page's two parallel requests, interleaved so that code locking in match order
    on one side and identity-block order on the other forms a cycle: the matches request holds the
    subject (first in Relic's match order), the summary request holds ALPHA (first in the block),
    and each then asks for what the other holds. Both must complete, and — after the fix — each
    must have taken its locks in ascending profile id order."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    _install_fake_providers(monkeypatch, _FakeRelic([_VIEW_MATCH], _IDENTITY_BLOCK))
    probe = _TouchProbe(engine)
    probe.install(monkeypatch)

    outcomes = await asyncio.gather(
        http.get(f"/api/players/{_SUBJECT}"),
        http.get(f"/api/players/{_SUBJECT}/matches"),
        return_exceptions=True,
    )

    assert not [o for o in outcomes if isinstance(o, BaseException)], outcomes
    assert [o.status_code for o in outcomes if isinstance(o, httpx.Response)] == [200, 200]

    assert len(probe.touches) == 2, "both requests must have gone through the touch primitive"
    for order in probe.touches.values():
        assert order == sorted(order), f"profiles must be locked in ascending order, got {order}"

    stored = await _stored_aliases(session_factory)
    assert stored[_ALPHA] == "Alpha"
    assert stored[_BRAVO] == "Bravo"
    assert stored[_SUBJECT] == "Subject"


# --- T459 (c) ----------------------------------------------------------------------------------


async def _seed_linked_profile(
    session_factory: async_sessionmaker[AsyncSession], profile_id: int
) -> None:
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4())
    steam = SteamIdentity(
        steam_id64="76500000000000459",
        user_id=user.id,
        verified_at=now - timedelta(days=30),
        last_sign_in_at=now - timedelta(days=1),
    )
    async with session_factory() as session:
        session.add_all([user, steam, AoeProfile(profile_id=profile_id, alias="Linked")])
        await session.flush()
        session.add(
            ProfileLink(
                id=uuid.uuid4(),
                user_id=user.id,
                profile_id=profile_id,
                steam_id64=steam.steam_id64,
                is_primary=True,
                linked_at=now - timedelta(days=30),
            )
        )
        await session.commit()


class _IngesterRelic:
    """Discovery's `MatchHistoryProvider`: one match whose participants are listed in *descending*
    order — the opposite of ascending, and different again from the viewed match's order."""

    def __init__(self, raw_match: RawMatch) -> None:
        self._raw_match = raw_match

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        return [self._raw_match]


async def test_ingester_discovery_racing_a_matches_view_completes(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    fast_deadlock_detection: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A discovery cycle and an on-view refresh over overlapping profiles (the two matches are
    different games, so they are not serialised on a shared `matches` row — only the profiles
    overlap, which is the production shape). Both complete, and discovery's capture enqueue is
    intact: it is the work constitution I says a view must never cost."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    await _seed_linked_profile(session_factory, _BRAVO)
    _install_fake_providers(monkeypatch, _FakeRelic([_VIEW_MATCH], _IDENTITY_BLOCK))
    probe = _TouchProbe(engine)
    probe.install(monkeypatch)

    ingest_match = _raw_match(_INGEST_GAME_ID, (_BRAVO, _ALPHA, _SUBJECT))
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=_IngesterRelic(ingest_match),
        capture_budget_days=21,
    )

    outcomes = await asyncio.gather(
        stage(Budget(seconds=30)),
        http.get(f"/api/players/{_SUBJECT}/matches"),
        return_exceptions=True,
    )

    assert not [o for o in outcomes if isinstance(o, BaseException)], outcomes
    report, response = outcomes
    assert isinstance(response, httpx.Response) and response.status_code == 200
    assert isinstance(report, dict) and report["captures_enqueued"] == 1

    assert len(probe.touches) == 2
    for order in probe.touches.values():
        assert order == sorted(order), f"profiles must be locked in ascending order, got {order}"


# --- T459 (d) ----------------------------------------------------------------------------------


async def _seed_stored_history(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        session.add(
            Match(
                game_id=_STORED_GAME_ID,
                leaderboard_id=3,
                map_name="Black Forest",
                completed_at=_MATCH_COMPLETED_AT - timedelta(days=1),
                source=discover.MATCH_SOURCE,
                raw_payload={"id": _STORED_GAME_ID},
            )
        )
        await session.flush()
        session.add(MatchPlayer(game_id=_STORED_GAME_ID, profile_id=_SUBJECT, civ_id=7))
        await session.commit()


@pytest.mark.parametrize("sqlstate", ["40P01", "40001", "55P03"])
@pytest.mark.parametrize("route", ["summary", "matches"])
async def test_lock_conflict_in_the_refresh_degrades_to_storage(
    route: str,
    sqlstate: str,
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `40P01` (deadlock), `40001` (serialisation failure) or `55P03` (a lock wait past
    `lock_timeout`) raised by the database inside the
    refresh's persistence rolls back only that refresh and the route answers `200` from storage —
    the same silent degrade FR-017 promises for a source failure. The error is raised by the
    server (`RAISE ... USING ERRCODE`), not constructed in Python, so the connection really is in
    an aborted-savepoint state and the request's own commit only succeeds if the savepoint was
    rolled back."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    await _seed_stored_history(session_factory)
    _install_fake_providers(monkeypatch, _FakeRelic([_VIEW_MATCH], _IDENTITY_BLOCK))
    probe = _TouchProbe(engine)
    probe.forced_error_sqlstate = sqlstate
    probe.install(monkeypatch)

    path = f"/api/players/{_SUBJECT}" + ("/matches" if route == "matches" else "")
    response = await http.get(path)

    assert response.status_code == 200
    body = response.json()
    if route == "matches":
        assert [row["game_id"] for row in body["matches"]] == [_STORED_GAME_ID]
    else:
        assert body["alias"] == "StoredSubject"

    # The refresh persisted nothing: the savepoint took the whole batch with it.
    assert await _stored_aliases(session_factory) == {_SUBJECT: "StoredSubject"}
    async with session_factory() as session:
        stored_games = (await session.execute(select(Match.game_id))).scalars().all()
    assert list(stored_games) == [_STORED_GAME_ID]


@pytest.mark.parametrize("route", ["summary", "matches"])
async def test_other_database_errors_in_the_refresh_still_fail(
    route: str,
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing broader than `40P01`/`40001`/`55P03` is swallowed: a `22012` (division by zero)
    raised from the same place propagates, and the request fails."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    _install_fake_providers(monkeypatch, _FakeRelic([_VIEW_MATCH], _IDENTITY_BLOCK))
    probe = _TouchProbe(engine)
    probe.forced_error_sqlstate = "22012"
    probe.install(monkeypatch)

    path = f"/api/players/{_SUBJECT}" + ("/matches" if route == "matches" else "")
    with pytest.raises(DBAPIError) as raised:
        await http.get(path)

    assert getattr(raised.value.orig, "sqlstate", None) == "22012"


@pytest.mark.parametrize("route", ["summary", "matches"])
async def test_refresh_blocked_by_another_transactions_lock_gives_up_and_serves_storage(
    route: str,
    http: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production aftermath of a killed function: a transaction left open with a row lock on
    `aoe_profiles` that nothing will release. A refresh that needs that row waits for it; without a
    `lock_timeout` it would wait until the platform killed the request too. With one, it gives up
    inside the savepoint (`55P03`) and the route answers from storage. Here the stuck transaction
    is a real second connection holding `FOR UPDATE` on ALPHA's row for the whole request, and the
    timeout is shortened so the test does not wait the production value."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    await _seed_stored_history(session_factory)
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_ALPHA, alias="StoredAlpha"))
        await session.commit()
    _install_fake_providers(monkeypatch, _FakeRelic([_VIEW_MATCH], _IDENTITY_BLOCK))
    monkeypatch.setattr(discover, "ON_VIEW_LOCK_TIMEOUT_MS", 300)

    path = f"/api/players/{_SUBJECT}" + ("/matches" if route == "matches" else "")
    async with session_factory() as stuck:
        await stuck.execute(
            select(AoeProfile).where(AoeProfile.profile_id == _ALPHA).with_for_update()
        )
        response = await asyncio.wait_for(http.get(path), timeout=10)
        await stuck.rollback()

    assert response.status_code == 200
    assert (await _stored_aliases(session_factory))[_ALPHA] == "StoredAlpha"
    assert _BRAVO not in await _stored_aliases(session_factory)


async def test_savepoint_restores_lock_timeout_when_the_block_succeeds(
    db_session: AsyncSession,
) -> None:
    """`SET LOCAL lock_timeout` must not leak into the rest of the request: colour enrichment, for
    one, runs after the refresh and never asked for a three-second timeout."""
    before = (await db_session.execute(text("SHOW lock_timeout"))).scalar_one()
    async with discover.savepoint_tolerating_lock_conflicts(db_session):
        inside = (await db_session.execute(text("SHOW lock_timeout"))).scalar_one()
    after = (await db_session.execute(text("SHOW lock_timeout"))).scalar_one()

    assert inside == f"{discover.ON_VIEW_LOCK_TIMEOUT_MS // 1000}s"
    assert after == before


# --- routers/matches.py::_fetch_match_identity ---------------------------------------------------


async def test_match_detail_identity_refresh_touches_in_profile_id_order(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`GET /api/matches/{game_id}` batch-touches every placeholder-aliased participant from the
    identity block, in whatever order Relic lists it. It must lock them ascending."""
    await _seed_signed_in_caller(http, session_factory)
    async with session_factory() as session:
        session.add_all(
            [AoeProfile(profile_id=pid, alias=str(pid)) for pid in (_SUBJECT, _ALPHA, _BRAVO)]
        )
        session.add(
            Match(
                game_id=_STORED_GAME_ID,
                leaderboard_id=3,
                completed_at=_MATCH_COMPLETED_AT,
                source=discover.MATCH_SOURCE,
                raw_payload={"id": _STORED_GAME_ID},
            )
        )
        await session.flush()
        session.add_all(
            [
                MatchPlayer(game_id=_STORED_GAME_ID, profile_id=pid, color_id=1)
                for pid in (_SUBJECT, _ALPHA, _BRAVO)
            ]
        )
        await session.commit()

    _install_fake_providers(monkeypatch, _FakeRelic([], _IDENTITY_BLOCK))
    probe = _TouchProbe(engine, peers=1)
    probe.install(monkeypatch)

    response = await http.get(f"/api/matches/{_STORED_GAME_ID}")

    assert response.status_code == 200
    (order,) = probe.touches.values()
    assert order == sorted(order) == [_SUBJECT, _ALPHA, _BRAVO]
    stored = await _stored_aliases(session_factory)
    assert stored == {_SUBJECT: "Subject", _ALPHA: "Alpha", _BRAVO: "Bravo"}


# --- T459a: the companion colour write ----------------------------------------------------------

_RANK = {"matches": 1, "aoe_profiles": 2, "match_players": 3, "replay_captures": 4}
_KEY_COLUMNS = {
    "matches": ("game_id",),
    "aoe_profiles": ("profile_id",),
    "match_players": ("game_id", "profile_id"),
    "replay_captures": ("game_id", "profile_id"),
}
_BOUND = re.compile(r"%\((\w+)\)s")
#: Bound parameters are rewritten to `<<name>>` before parsing so their own parentheses never read
#: as the parentheses of a `VALUES` row.
_PLACEHOLDER = re.compile(r"<<(\w+)>>")


@dataclass(frozen=True)
class _RowLock:
    table: str
    key: tuple[int, ...]
    statement: str
    #: Postgres, not the statement's text, decides the order this lock was taken in.
    unordered: bool = False


@dataclass
class _LockRecorder:
    """Every row-locking statement each database connection sends while it is installed, read off
    the SQL that reaches the driver (`before_cursor_execute`), so a writer cannot hide behind the
    ORM or behind a helper: `INSERT`, `UPDATE`, `DELETE` and `SELECT ... FOR UPDATE` against the
    four ranked tables (`_RANK`), with the key of every row each one carries — multi-row `VALUES`
    lists, `INSERT ... SELECT` and `IN (...)` lists included. An `executemany` is recorded once per
    parameter set, in order.

    An `INSERT ... VALUES`, `UPDATE` or `DELETE` against a ranked table whose keys this class
    cannot read **fails the test** instead of being skipped. Other statement shapes may go
    unrecorded; `_keys` is what decides.

    Only a multi-row `INSERT` takes its row locks in the order its `VALUES` list gives, and a
    `SELECT ... FOR UPDATE` that really carries `ORDER BY <table>.<key columns>` takes them in
    ascending key order. Any other statement that locks several rows (`UPDATE ...
    FROM (VALUES ...)`, a `SELECT ... FOR UPDATE` without that `ORDER BY`) locks them in a join or
    scan order Postgres chooses: it is recorded as **unordered**, and is a violation unless every
    key it touches is already held earlier in the transaction.

    A statement that names only `profile_id` of a two-column key by `IN (...)` carries no key the
    SQL can show. A `SELECT ... FOR UPDATE` of that shape with `ORDER BY <both key columns>` is
    recorded as one ordered lock at its table's rank with an empty key (the rows are whichever
    match, in key order); an `UPDATE` or `DELETE` of that shape is credited only after such a lock
    on the same connection and is otherwise **unordered**. Tables outside the four
    (`provider_calls`, `rating_snapshots`) are never ranked.
    """

    engine: AsyncEngine
    by_connection: dict[int, list[_RowLock]] = field(default_factory=dict)
    executemany_statements: int = 0
    _ids: ClassVar[Iterator[int]] = itertools.count(1)

    def __enter__(self) -> _LockRecorder:
        event.listen(self.engine.sync_engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc: object) -> None:
        event.remove(self.engine.sync_engine, "before_cursor_execute", self._record)

    @staticmethod
    def _tuples(section: str) -> list[list[str]]:
        return [
            [element.strip() for element in group.split(",")]
            for group in re.findall(r"\(([^()]*)\)", section)
        ]

    @staticmethod
    def _value(element: str, parameters: dict[str, Any]) -> int:
        name = _PLACEHOLDER.search(element)
        assert name is not None, f"a key that is not a bound parameter: {element!r}"
        return int(parameters[name.group(1)])

    def _keys(
        self, sql: str, parameters: dict[str, Any]
    ) -> tuple[str, list[tuple[int, ...]], bool] | None:
        """`(table, keys, unordered)` for a row-locking statement against a ranked table, else
        `None`."""
        insert = re.match(
            r"INSERT INTO (\w+) \(([^)]*)\) VALUES (.*?)(?: ON CONFLICT| RETURNING|$)", sql
        )
        insert_select = re.match(
            r"INSERT INTO (\w+) \(([^)]*)\) SELECT (.*?) (?:WHERE|ON CONFLICT|RETURNING|$)", sql
        )
        update = re.match(r"(?:UPDATE|DELETE FROM) (\w+)\b", sql)
        select = re.match(r"SELECT .* FROM (\w+)\b.* FOR (?:NO KEY )?UPDATE", sql)
        if insert_select:
            table = insert_select.group(1)
            if table not in _RANK:
                return None
            columns = [column.strip() for column in insert_select.group(2).split(",")]
            positions = [columns.index(column) for column in _KEY_COLUMNS[table]]
            row = re.split(r", (?=<<)", insert_select.group(3))
            return table, [tuple(self._value(row[i], parameters) for i in positions)], False
        if insert:
            table = insert.group(1)
            if table not in _RANK:
                return None
            columns = [column.strip() for column in insert.group(2).split(",")]
            positions = [columns.index(column) for column in _KEY_COLUMNS[table]]
            rows = self._tuples(insert.group(3))
            return (
                table,
                [tuple(self._value(row[i], parameters) for i in positions) for row in rows],
                False,
            )
        if update:
            table = update.group(1)
            if table not in _RANK:
                return None
            values = re.search(r"FROM \(VALUES (.*?)\) AS \w+ \(([^)]*)\)", sql)
            if values:
                columns = [column.strip() for column in values.group(2).split(",")]
                positions = [columns.index(column) for column in _KEY_COLUMNS[table]]
                rows = self._tuples(values.group(1))
                return (
                    table,
                    [tuple(self._value(row[i], parameters) for i in positions) for row in rows],
                    True,
                )
            equalities = dict(re.findall(rf"{table}\.(\w+) = <<(\w+)>>", sql))
            if not all(column in equalities for column in _KEY_COLUMNS[table]):
                raise AssertionError(f"cannot read the key of a locking statement: {sql}")
            return (
                table,
                [tuple(int(parameters[equalities[column]]) for column in _KEY_COLUMNS[table])],
                False,
            )
        if select:
            table = select.group(1)
            if table not in _RANK:
                return None
            width = len(_KEY_COLUMNS[table])
            members = re.findall(rf"\(((?:<<\w+>>(?:::\w+)?(?:, )?){{{width}}})\)", sql)
            if not members:
                equalities = dict(re.findall(rf"{table}\.(\w+) = <<(\w+)>>", sql))
                if all(column in equalities for column in _KEY_COLUMNS[table]):
                    return (
                        table,
                        [tuple(int(parameters[equalities[c]]) for c in _KEY_COLUMNS[table])],
                        False,
                    )
                raise AssertionError(f"cannot read the keys of a locking select: {sql}")
            keys = [
                tuple(int(parameters[name]) for name in _PLACEHOLDER.findall(member))
                for member in members
            ]
            ordered = " ORDER BY " + ", ".join(f"{table}.{c}" for c in _KEY_COLUMNS[table])
            return table, sorted(keys) if ordered in sql else keys, ordered not in sql
        return None

    @staticmethod
    def _predicate(sql: str, parameters: dict[str, Any]) -> tuple[str, int, int] | None:
        """`(table, position in the key, value)` for an `UPDATE` or `DELETE` against a ranked table
        whose `WHERE` names **one** of its key columns by equality and not the rest — a statement
        that locks every row matching that column, in a scan order Postgres chooses, and whose
        keys the SQL does not carry. `None` for any other statement."""
        found = re.match(r"(?:UPDATE|DELETE FROM) (\w+)\b", sql)
        if found is None or found.group(1) not in _RANK or "FROM (VALUES" in sql:
            return None
        table = found.group(1)
        equalities = dict(re.findall(rf"{table}\.(\w+) = <<(\w+)>>", sql))
        named = [column for column in _KEY_COLUMNS[table] if column in equalities]
        if len(named) != 1 or len(_KEY_COLUMNS[table]) == 1:
            return None
        return table, _KEY_COLUMNS[table].index(named[0]), int(parameters[equalities[named[0]]])

    @staticmethod
    def _partial_in(sql: str) -> tuple[str, bool] | None:
        """`(table, locks)` for a statement against a two-column-key ranked table whose `WHERE`
        names one key column by `IN (...)`, else `None`. `locks` is true for a `SELECT ... FOR
        UPDATE` whose `ORDER BY` is the whole key, the only shape that takes its rows in key
        order."""
        found = re.match(r"(?:UPDATE|DELETE FROM) (\w+)\b", sql) or re.match(
            r"SELECT .*? FROM (\w+)\b.* FOR (?:NO KEY )?UPDATE", sql
        )
        if found is None or found.group(1) not in _RANK or "FROM (VALUES" in sql:
            return None
        table = found.group(1)
        key = _KEY_COLUMNS[table]
        if len(key) == 1 or not any(re.search(rf"{table}\.{c} IN \(<<", sql) for c in key):
            return None
        ordered = " ORDER BY " + ", ".join(f"{table}.{c}" for c in key) + " FOR "
        return table, sql.startswith("SELECT") and ordered in sql

    def _record(
        self, conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        sql = _BOUND.sub(lambda found: f"<<{found.group(1)}>>", " ".join(statement.split()))
        # A list of parameter sets is an `executemany`: every set is a write and is recorded. A
        # dict is one statement (a batched `INSERT` suffixes its names per row). A set that is not
        # a dict cannot be read; against a ranked table `_keys` then fails the test instead of the
        # statement going unrecorded.
        if isinstance(parameters, dict):
            parameter_sets = [parameters]
        else:
            parameter_sets = list(parameters or [])
            self.executemany_statements += bool(parameter_sets)
        for parameter_set in parameter_sets:
            parameter_dict = parameter_set if isinstance(parameter_set, dict) else {}
            partial = self._partial_in(sql)
            if partial is not None:
                table, takes_ordered_lock = partial
                driver = conn.connection.driver_connection
                if not hasattr(driver, "_lock_recorder_id"):
                    driver._lock_recorder_id = next(self._ids)  # type: ignore[arg-type]
                locks = self.by_connection.setdefault(driver._lock_recorder_id, [])
                is_select = sql.startswith("SELECT")
                held = any(
                    lock.table == table and lock.key == () and not lock.unordered for lock in locks
                )
                locks.append(
                    _RowLock(
                        table,
                        (),
                        sql,
                        unordered=not (takes_ordered_lock or (not is_select and held)),
                    )
                )
                continue
            predicate = self._predicate(sql, parameter_dict)
            found = None if predicate is not None else self._keys(sql, parameter_dict)
            if predicate is None and found is None:
                return
            driver = conn.connection.driver_connection
            if not hasattr(driver, "_lock_recorder_id"):
                driver._lock_recorder_id = next(self._ids)  # type: ignore[arg-type]
            locks = self.by_connection.setdefault(driver._lock_recorder_id, [])
            if predicate is not None:
                # The rows are whichever match; the SQL cannot say which. Credit exactly the rows
                # this connection had already locked for that value, and, when it had locked none,
                # record the statement as unordered so it is a violation. That every matching row
                # was among the held ones is the caller's to assert (`locked`).
                table, position, value = predicate
                held = [
                    lock.key
                    for lock in locks
                    if lock.table == table and lock.key and lock.key[position] == value
                ]
                locks.extend(
                    [_RowLock(table, key, sql) for key in held]
                    or [_RowLock(table, (), sql, unordered=True)]
                )
                continue
            assert found is not None
            table, keys, unordered = found
            if not keys:
                raise AssertionError(f"a locking statement with no readable key: {sql}")
            locks.extend(_RowLock(table, key, sql, unordered) for key in keys)

    def count(self) -> int:
        return sum(len(locks) for locks in self.by_connection.values())

    def locked(self, table: str) -> set[tuple[int, ...]]:
        """Every key of `table` any connection locked or re-touched, by whatever statement."""
        return {
            lock.key
            for locks in self.by_connection.values()
            for lock in locks
            if lock.table == table and lock.key
        }

    def violations(self) -> list[str]:
        """Every row first locked at a lower `(rank, key)` than one this connection had already
        locked, and every row first locked by an unordered statement. A row locked earlier on the
        same connection is a re-touch, not an acquisition."""
        problems: list[str] = []
        for connection, locks in self.by_connection.items():
            held: set[tuple[str, tuple[int, ...]]] = set()
            highest: tuple[int, tuple[int, ...]] = (0, ())
            highest_lock: _RowLock | None = None
            for lock in locks:
                if (lock.table, lock.key) in held:
                    continue
                held.add((lock.table, lock.key))
                if lock.unordered:
                    problems.append(
                        f"connection {connection}: {lock.table}{lock.key} was first locked by a "
                        f"statement whose lock order Postgres chooses, not the statement -- "
                        f"`{lock.statement[:160]}`"
                    )
                    continue
                position = (_RANK[lock.table], lock.key)
                if position < highest:
                    assert highest_lock is not None
                    problems.append(
                        f"connection {connection}: {lock.table}{lock.key} was first locked after "
                        f"{highest_lock.table}{highest_lock.key} -- by `{lock.statement[:160]}`"
                    )
                else:
                    highest, highest_lock = position, lock
        return problems

    def sequence(self) -> str:
        return "\n".join(
            f"  conn {connection}: " + ", ".join(f"{lock.table}{lock.key}" for lock in locks)
            for connection, locks in self.by_connection.items()
        )


class _FakeCompanion:
    """`CompanionEnrichmentProvider.enrich_matches` answering a colour for every `(game_id,
    profile_id)` it is given, in **descending** order — the opposite of the order the database
    must be written in. `calls_after_writes` records how many row locks the recorder had seen when
    each call was made: a network call after the first write holds those locks across it."""

    def __init__(
        self, colours: dict[tuple[int, int], int], recorder: _LockRecorder | None = None
    ) -> None:
        self._colours = colours
        self._recorder = recorder
        self.game_ids_asked: list[int] = []
        self.calls_after_writes: list[int] = []

    async def enrich_matches(
        self, profile_ids: Sequence[int], game_ids: Sequence[int]
    ) -> dict[int, MatchEnrichment]:
        self.game_ids_asked.extend(game_ids)
        self.calls_after_writes.append(self._recorder.count() if self._recorder else 0)
        answer: dict[int, MatchEnrichment] = {}
        for (game_id, profile_id), colour in sorted(self._colours.items(), reverse=True):
            if game_id in game_ids:
                enrichment = answer.setdefault(
                    game_id, MatchEnrichment(game_id=game_id, participants={})
                )
                assert enrichment.participants is not None
                enrichment.participants[profile_id] = EnrichedParticipant(color_id=colour)
        return answer


class _RecordingRelic(_FakeRelic):
    """`_FakeRelic` that notes how many row locks existed when it was called."""

    def __init__(
        self, matches: Sequence[RawMatch], block: Sequence[RawProfile], recorder: _LockRecorder
    ) -> None:
        super().__init__(matches, block)
        self._recorder = recorder
        self.calls_after_writes: list[int] = []

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        self.calls_after_writes.append(self._recorder.count())
        return await super().recent_matches(profile_ids)

    async def recent_profiles(self, profile_ids: Sequence[int]) -> list[RawProfile]:
        self.calls_after_writes.append(self._recorder.count())
        return await super().recent_profiles(profile_ids)

    async def recent_matches_and_profiles(self, profile_ids: Sequence[int]) -> RecentHistory:
        self.calls_after_writes.append(self._recorder.count())
        return await super().recent_matches_and_profiles(profile_ids)


_STORED_OLD_GAMES = (860_000_011, 860_000_012)
_FETCHED_GAMES = (870_000_001, 870_000_002)
_PROFILES = (_SUBJECT, _ALPHA, _BRAVO)


async def _seed_stored_matches(
    session_factory: async_sessionmaker[AsyncSession],
    games: Sequence[int],
    *,
    completed_at: datetime,
    colours: dict[tuple[int, int], int] | None = None,
    placeholders: bool = True,
) -> None:
    """Stored matches over the three profiles, every colour `NULL` unless `colours` names one."""
    colours = colours or {}
    async with session_factory() as session:
        for profile_id in _PROFILES:
            if await session.get(AoeProfile, profile_id) is None:
                session.add(
                    AoeProfile(
                        profile_id=profile_id,
                        alias=str(profile_id) if placeholders else f"Stored{profile_id}",
                    )
                )
        for offset, game_id in enumerate(games):
            session.add(
                Match(
                    game_id=game_id,
                    leaderboard_id=3,
                    map_name="Arabia",
                    completed_at=completed_at - timedelta(days=offset),
                    source=discover.MATCH_SOURCE,
                    raw_payload={"id": game_id},
                )
            )
        await session.flush()
        for game_id in games:
            for profile_id in _PROFILES:
                session.add(
                    MatchPlayer(
                        game_id=game_id,
                        profile_id=profile_id,
                        civ_id=7,
                        color_id=colours.get((game_id, profile_id)),
                    )
                )
        await session.commit()


async def _stored_colours(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[tuple[int, int], int | None]:
    async with session_factory() as session:
        rows = await session.execute(
            select(MatchPlayer.game_id, MatchPlayer.profile_id, MatchPlayer.color_id)
        )
        return {(game_id, profile_id): colour for game_id, profile_id, colour in rows.all()}


@pytest.mark.parametrize("route", ["summary", "matches", "detail"])
async def test_every_row_lock_in_a_request_is_taken_in_the_global_order(
    route: str,
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T459a (a): the whole request, on each route, with companion answering colours. Whatever a
    route writes — the batch, the identity block, the colour fills — each connection must acquire
    row locks in one ascending `(table rank, key)` sequence, and make its network calls before the
    first of them.

    The stored page is deliberately *older* than the fetched matches (lower `game_id`s), so a
    colour write that follows the batch, even one sorted among itself, steps backwards; and
    companion answers in descending order, so one that follows companion's order does too."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)

    fetched = [_raw_match(game_id, (_SUBJECT, _BRAVO, _ALPHA)) for game_id in _FETCHED_GAMES]
    all_games = (*_STORED_OLD_GAMES, *_FETCHED_GAMES)
    colours = {
        (game_id, profile_id): 1 + index % 8
        for index, (game_id, profile_id) in enumerate(
            (game_id, profile_id) for game_id in all_games for profile_id in _PROFILES
        )
    }

    with _LockRecorder(engine) as recorder:
        relic = _RecordingRelic(fetched if route == "matches" else [], _IDENTITY_BLOCK, recorder)
        companion = _FakeCompanion(colours, recorder)
        _install_fake_providers(monkeypatch, relic)
        monkeypatch.setattr(matches_router, "_build_enrichment_provider", lambda _s: companion)

        path = {
            "summary": f"/api/players/{_SUBJECT}",
            "matches": f"/api/players/{_SUBJECT}/matches",
            "detail": f"/api/matches/{_STORED_OLD_GAMES[0]}",
        }[route]
        response = await http.get(path)

    assert response.status_code == 200, response.text
    assert recorder.count() > 0, "the request wrote nothing: the recorder proved nothing"
    assert not recorder.violations(), (
        "row locks taken against the global order:\n  "
        + "\n  ".join(recorder.violations())
        + "\nfull sequence per connection:\n"
        + recorder.sequence()
    )
    assert relic.calls_after_writes, "the route never reached Relic"
    assert set(relic.calls_after_writes + companion.calls_after_writes) == {0}, (
        "a provider call was made after the request had already taken row locks: "
        f"relic {relic.calls_after_writes}, companion {companion.calls_after_writes}"
    )
    if route != "summary":
        assert companion.calls_after_writes, "companion was never asked for the colours"
        stored = await _stored_colours(session_factory)
        served = set(all_games) if route == "matches" else {_STORED_OLD_GAMES[0]}
        wanted = {key: value for key, value in colours.items() if key[0] in served}
        assert {key: stored[key] for key in wanted} == wanted, "companion's colours were not filled"
    if route == "matches":
        assert set(companion.game_ids_asked) == set(all_games), (
            "companion must be asked about the fetched matches and the stored page together, once: "
            f"{sorted(companion.game_ids_asked)}"
        )


# --- T459a (b): match detail against a discovery batch over the same match ---------------------

_RACE_GAME_ID = 880_000_001


class _WriteProbe(_TouchProbe):
    """`_TouchProbe`'s rendezvous, keyed on *any* write to the two tables whose locks cross
    between writers — `aoe_profiles` and `match_players` — instead of on the profile touch alone.
    The colour write the review found is a `match_players` update that comes *before* the profile
    touch, so a probe that only parks at the profile touch never forms the cycle against it."""

    @staticmethod
    def _profile_ids_in(statement: Any) -> list[int] | None:
        table = getattr(statement, "table", None)
        if getattr(table, "name", None) in {"aoe_profiles", "match_players"} and any(
            getattr(statement, flag, False) for flag in ("is_insert", "is_update", "is_delete")
        ):
            return []
        if getattr(statement, "_for_update_arg", None) is not None and re.search(
            r"\b(?:aoe_profiles|match_players)\b", str(statement)
        ):
            return []
        return None


async def test_match_detail_racing_a_discovery_batch_completes(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    fast_deadlock_detection: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T459a (b): the match page of a match with a `NULL` colour and a placeholder participant,
    while a `DiscoverStage` batch writes the same match. Before the fix the page wrote
    `match_players` (companion's colour) and only then `aoe_profiles` (the identity refresh),
    while the batch wrote `aoe_profiles` and then `match_players`: each held what the other wanted.
    After it, both write `aoe_profiles` before `match_players` and neither waits on the other in a
    cycle. Capture enqueueing, constitution I's concern, must survive the race.

    The interleaving is made by conditions (`_WriteProbe`), never durations: each side parks after
    its first write until the other has made one, or until Postgres reports a backend waiting on a
    lock — which is how the ordered code gets through without the harness deadlocking it."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_linked_profile(session_factory, _ALPHA)
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_BRAVO, alias=str(_BRAVO)))
        session.add(
            Match(
                game_id=_RACE_GAME_ID,
                leaderboard_id=3,
                completed_at=_MATCH_COMPLETED_AT,
                source=discover.MATCH_SOURCE,
                raw_payload={"id": _RACE_GAME_ID},
            )
        )
        await session.flush()
        session.add_all(
            [MatchPlayer(game_id=_RACE_GAME_ID, profile_id=pid) for pid in (_ALPHA, _BRAVO)]
        )
        await session.commit()

    bravo_identity = [RawProfile(profile_id=_BRAVO, alias="Bravo", country="DE")]
    _install_fake_providers(monkeypatch, _FakeRelic([], bravo_identity))
    monkeypatch.setattr(
        matches_router,
        "_build_enrichment_provider",
        lambda _s: _FakeCompanion({(_RACE_GAME_ID, _ALPHA): 1, (_RACE_GAME_ID, _BRAVO): 2}),
    )
    probe = _WriteProbe(engine)
    probe.install(monkeypatch)

    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=_IngesterRelic(_raw_match(_RACE_GAME_ID, (_BRAVO, _ALPHA))),
        capture_budget_days=21,
    )
    outcomes = await asyncio.gather(
        stage(Budget(seconds=30)),
        http.get(f"/api/matches/{_RACE_GAME_ID}"),
        return_exceptions=True,
    )

    assert not [o for o in outcomes if isinstance(o, BaseException)], outcomes
    report, response = outcomes
    assert isinstance(response, httpx.Response) and response.status_code == 200
    assert isinstance(report, dict) and report["captures_enqueued"] == 1
    assert len(probe.touches) == 2, "both sides must have reached the rendezvous"

    async with session_factory() as session:
        captures = (await session.execute(select(ReplayCapture.profile_id))).scalars().all()
    assert list(captures) == [_ALPHA], "the capture the batch enqueues must survive the page view"
    assert await _stored_colours(session_factory) == {
        (_RACE_GAME_ID, _ALPHA): 1,
        (_RACE_GAME_ID, _BRAVO): 2,
    }
    assert (await _stored_aliases(session_factory))[_BRAVO] == "Bravo"


# --- T459a (c): precedence -----------------------------------------------------------------------


@pytest.mark.parametrize("route", ["matches", "detail"])
async def test_a_stored_colour_is_never_replaced_by_companions(
    route: str,
    http: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T459a (c): companion fills a `NULL` and nothing else. ALPHA's colour is already stored (as
    an earlier Relic projection or an earlier fill would have left it); companion disagrees about
    it and also names a colour for the `NULL` rows. Only the `NULL` rows change."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    stored_before = {(_STORED_OLD_GAMES[0], _ALPHA): 3, (_STORED_OLD_GAMES[1], _ALPHA): 4}
    await _seed_stored_matches(
        session_factory,
        _STORED_OLD_GAMES,
        completed_at=_MATCH_COMPLETED_AT,
        colours=stored_before,
        placeholders=False,
    )
    companion = _FakeCompanion(
        {(game_id, profile_id): 8 for game_id in _STORED_OLD_GAMES for profile_id in _PROFILES}
    )
    _install_fake_providers(monkeypatch, _FakeRelic([], []))
    monkeypatch.setattr(matches_router, "_build_enrichment_provider", lambda _s: companion)

    path = (
        f"/api/players/{_SUBJECT}/matches"
        if route == "matches"
        else f"/api/matches/{_STORED_OLD_GAMES[0]}"
    )
    response = await http.get(path)

    assert response.status_code == 200, response.text
    assert companion.calls_after_writes, "companion must have been asked: a row was still NULL"
    stored = await _stored_colours(session_factory)
    for key, colour in stored_before.items():
        assert stored[key] == colour, f"companion replaced the stored colour of {key}"
    served = set(_STORED_OLD_GAMES) if route == "matches" else {_STORED_OLD_GAMES[0]}
    for (game_id, profile_id), colour in stored.items():
        if (game_id, profile_id) not in stored_before and game_id in served:
            assert colour == 8, f"companion did not fill the NULL colour of {(game_id, profile_id)}"


# --- T459d: the recorder must fail on what it cannot read, and prove it does ---------------------


@pytest.mark.parametrize("late_writer", [False, True])
async def test_recorder_reports_an_executemany_write_after_the_batch(
    late_writer: bool,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """An ORM flush that updates two or more `match_players` rows is one `executemany` with a list
    of parameter sets. A writer that does that after the batch, on rows *below* the batch's keys,
    is exactly the inversion the invariant forbids; the recorder must see every parameter set.

    The control (`late_writer=False`) is the same transaction without that writer."""
    await _seed_subject(session_factory)
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)

    with _LockRecorder(engine) as recorder:
        async with session_factory() as session:
            await discover.persist_matches_and_profiles(
                session, [_raw_match(game_id, _PROFILES) for game_id in _FETCHED_GAMES]
            )
            if late_writer:
                rows = (
                    (
                        await session.execute(
                            select(MatchPlayer).where(MatchPlayer.game_id.in_(_STORED_OLD_GAMES))
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(rows) >= 2
                for row in rows:
                    row.color_id = 5
                await session.flush()
            await session.commit()

    if late_writer:
        assert recorder.violations(), "the recorder missed an executemany write below the batch"
        assert recorder.executemany_statements >= 1, "the late writer was not an executemany"
    else:
        assert recorder.count() > 0
        assert not recorder.violations(), recorder.violations()


async def test_recorder_reports_a_fills_only_request_whose_lock_pass_is_removed(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`UPDATE ... FROM (VALUES ...)` locks its rows in join order, not `VALUES` order, so the
    statement alone proves nothing about order: it is only safe when `lock_match_players` has
    already taken every key it touches. Remove that pass and the recorder must fail; with it
    (`test_every_row_lock_in_a_request_is_taken_in_the_global_order`, route `detail`) it must
    not."""

    async def _no_lock_pass(session: AsyncSession, keys: Any) -> None:
        return None

    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    await _seed_stored_matches(
        session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT, placeholders=False
    )
    game_id = _STORED_OLD_GAMES[0]
    companion = _FakeCompanion({(game_id, profile_id): 4 for profile_id in _PROFILES})
    _install_fake_providers(monkeypatch, _FakeRelic([], []))
    monkeypatch.setattr(matches_router, "_build_enrichment_provider", lambda _s: companion)
    monkeypatch.setattr(discover, "lock_match_players", _no_lock_pass)

    with _LockRecorder(engine) as recorder:
        response = await http.get(f"/api/matches/{game_id}")

    assert response.status_code == 200, response.text
    assert (await _stored_colours(session_factory))[(game_id, _SUBJECT)] == 4, "no fill happened"
    assert recorder.violations(), (
        "the recorder credited a VALUES list with an order it does not have"
    )


# --- T459d: companion is not asked about a match the served page cannot contain ------------------


@pytest.mark.parametrize(("fetched_age_days", "companion_asked"), [(30, False), (-1, True)])
async def test_an_uncoloured_match_outside_the_served_page_costs_no_companion_call(
    fetched_age_days: int,
    companion_asked: bool,
    http: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stored page (`limit=2`) is full and fully coloured. A fetched match that Relic left
    uncoloured and that is *older* than the page's oldest row cannot be on the page served, so it
    is not asked about. One *newer* than the page can be on it, and is asked about."""
    await _seed_signed_in_caller(http, session_factory)
    await _seed_subject(session_factory)
    colours = {
        (game_id, profile_id): 2 for game_id in _STORED_OLD_GAMES for profile_id in _PROFILES
    }
    await _seed_stored_matches(
        session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT, colours=colours
    )
    fetched = _raw_match(_FETCHED_GAMES[0], _PROFILES).model_copy(
        update={"completed_at": _MATCH_COMPLETED_AT - timedelta(days=fetched_age_days)}
    )
    companion = _FakeCompanion({(_FETCHED_GAMES[0], profile_id): 6 for profile_id in _PROFILES})
    _install_fake_providers(monkeypatch, _FakeRelic([fetched], []))
    monkeypatch.setattr(matches_router, "_build_enrichment_provider", lambda _s: companion)

    response = await http.get(f"/api/players/{_SUBJECT}/matches?limit=2")

    assert response.status_code == 200, response.text
    assert bool(companion.game_ids_asked) is companion_asked, companion.game_ids_asked
    served = [row["game_id"] for row in response.json()["matches"]]
    assert (_FETCHED_GAMES[0] in served) is companion_asked, served


# --- T459e: pseudonymisation --------------------------------------------------------------------


async def _seed_owner_of(
    http: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    linked: Sequence[int],
) -> None:
    """A signed-in user whose profile links are inserted **in the order given** (the order
    `erase_account` reads them back in is the database's, not sorted), over profiles that already
    exist (`_seed_stored_matches`)."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    async with session_factory() as session:
        user = User(allowlisted_at=now)
        session.add(user)
        await session.flush()
        steam = SteamIdentity(
            steam_id64="76500000000000460", user_id=user.id, verified_at=now, last_sign_in_at=now
        )
        session.add_all(
            [
                steam,
                UserSession(
                    id=session_id,
                    user_id=user.id,
                    created_at=now,
                    expires_at=now + timedelta(days=30),
                ),
            ]
        )
        await session.flush()
        for index, profile_id in enumerate(linked):
            session.add(
                ProfileLink(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    profile_id=profile_id,
                    steam_id64=steam.steam_id64,
                    is_primary=index == 0,
                    linked_at=now,
                )
            )
            await session.flush()
        await session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    http.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


async def _erase(http: httpx.AsyncClient) -> httpx.Response:
    token = (await http.get("/api/privacy/erase")).json()["confirmation_token"]
    return await http.post("/api/privacy/erase", json={"confirmation_token": token})


async def _assert_pseudonymised(
    session_factory: async_sessionmaker[AsyncSession], profile_ids: Sequence[int]
) -> None:
    """The same rows end up with the same values whatever the lock order: every
    `(game, original)` key of `match_players` is now `(game, -original)` with its other columns
    intact, the original `aoe_profiles` row is masked, and the placeholder row exists."""
    async with session_factory() as session:
        players = {
            (row.game_id, row.profile_id): row.civ_id
            for row in (await session.execute(select(MatchPlayer))).scalars()
        }
        profiles = {
            row.profile_id: row for row in (await session.execute(select(AoeProfile))).scalars()
        }
    for profile_id in profile_ids:
        for game_id in _STORED_OLD_GAMES:
            assert (game_id, profile_id) not in players
            assert players[(game_id, -profile_id)] == 7
        for row in (profiles[profile_id], profiles[-profile_id]):
            assert (row.alias, row.country, row.avatar_hash) == (PSEUDONYMISED_ALIAS, None, None)
    for untouched in set(_PROFILES) - set(profile_ids):
        assert all((game_id, untouched) in players for game_id in _STORED_OLD_GAMES)
        assert profiles[untouched].alias == str(untouched)
        assert -untouched not in profiles


@pytest.mark.parametrize("entry", ["erase", "objection"])
async def test_pseudonymisation_takes_every_row_lock_in_the_global_order(
    entry: str,
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """T459e: whatever the pseudonymisation writes, each connection acquires row locks in one
    ascending `(table rank, key)` sequence — through the real `POST /api/privacy/erase`
    (`erase`), and through `resolve_third_party_objection` (`objection`, the function FR-039's
    resolution runs).

    `erase` links BRAVO before SUBJECT, so reading the links back is not ascending: a loop that
    pseudonymises one profile at a time takes `aoe_profiles(-SUBJECT)` after
    `match_players(.., BRAVO)`. Every `match_players` row of the pseudonymised profiles must be
    among the locked ones (`locked`), because a `UPDATE ... WHERE profile_id = ...` names no key
    the recorder could read."""
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)
    if entry == "erase":
        pseudonymised: tuple[int, ...] = (_BRAVO, _SUBJECT)
        await _seed_owner_of(http, session_factory, pseudonymised)
        with _LockRecorder(engine) as recorder:
            response = await _erase(http)
        assert response.status_code == 200, response.text
    else:
        pseudonymised = (_ALPHA,)
        async with session_factory() as session:
            data_request = DataRequest(
                kind=DataRequestKind.THIRD_PARTY_OBJECTION, subject_profile_id=_ALPHA
            )
            session.add(data_request)
            await session.commit()
        with _LockRecorder(engine) as recorder:
            async with session_scope(session_factory) as session:
                await privacy_router.resolve_third_party_objection(session, data_request.id)

    assert recorder.count() > 0, "the pseudonymisation wrote nothing: the recorder proved nothing"
    assert not recorder.violations(), (
        "row locks taken against the global order:\n  "
        + "\n  ".join(recorder.violations())
        + "\nfull sequence per connection:\n"
        + recorder.sequence()
    )
    assert recorder.locked("match_players") >= {
        (game_id, profile_id) for game_id in _STORED_OLD_GAMES for profile_id in pseudonymised
    }
    assert recorder.locked("aoe_profiles") >= {
        (key,) for profile_id in pseudonymised for key in (profile_id, -profile_id)
    }
    await _assert_pseudonymised(session_factory, pseudonymised)


async def test_recorder_reports_a_key_rewrite_with_no_lock_pass_before_it(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """The recorder cannot read the keys of `UPDATE match_players SET profile_id = .. WHERE
    profile_id = ..`; it must not credit one it never saw locked. With no lock pass first it is a
    violation — the shape the pre-T459e pseudonymisation had."""
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=-_SUBJECT, alias=PSEUDONYMISED_ALIAS))
        await session.commit()
    with _LockRecorder(engine) as recorder:
        async with session_scope(session_factory) as session:
            await session.execute(
                update(MatchPlayer)
                .where(MatchPlayer.profile_id == _SUBJECT)
                .values(profile_id=-_SUBJECT)
            )
    assert recorder.violations()


class _Rendezvous:
    """Parks a session until a peer reaches a point or Postgres reports a lock wait, so a race is
    formed from conditions and never from durations."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def _park_until(self, reached: asyncio.Event) -> None:
        deadline = asyncio.get_running_loop().time() + _RENDEZVOUS_GUARD_SECONDS
        while not reached.is_set():
            if await self._someone_is_waiting_on_a_lock():
                return
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError("the peer never arrived and nothing is lock-blocked")
            await asyncio.sleep(0.01)

    async def _someone_is_waiting_on_a_lock(self) -> bool:
        async with self._engine.connect() as connection:
            waiting = await connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
            )
            return bool(waiting.scalar_one())


class _PseudonymisationRace(_Rendezvous):
    """The interleave that deadlocks the pre-T459e code, formed from conditions and never from
    durations. Two parks, each released by the *other* side's progress or by Postgres reporting a
    backend that waits on a lock (how code that locks in one global order gets through: its second
    transaction is blocked on the first's row, so the awaited progress can never happen):

    - the pseudonymiser, after it has executed an `UPDATE match_players` (the key rewrite), waits
      until the discovery batch has upserted `aoe_profiles`;
    - the discovery batch, before it executes its `INSERT INTO match_players`, waits until the
      pseudonymiser has executed that `UPDATE`.

    Against the old order that leaves the pseudonymiser holding `match_players(game, profile)` and
    asking for `aoe_profiles(profile)`, and the batch holding the second and asking for the first.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine)
        self.rewrote_keys = asyncio.Event()
        self.touched_profiles = asyncio.Event()

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_execute = AsyncSession.execute

        async def spy(self_session: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
            name = getattr(getattr(statement, "table", None), "name", None)
            is_key_rewrite = name == "match_players" and getattr(statement, "is_update", False)
            is_batch_insert = name == "match_players" and getattr(statement, "is_insert", False)
            is_profile_touch = name == "aoe_profiles" and getattr(statement, "is_insert", False)
            if is_batch_insert:
                await self._park_until(self.rewrote_keys)
            result = await real_execute(self_session, statement, *args, **kwargs)
            if is_profile_touch:
                self.touched_profiles.set()
            if is_key_rewrite:
                self.rewrote_keys.set()
                await self._park_until(self.touched_profiles)
            return result

        monkeypatch.setattr(AsyncSession, "execute", spy)


async def test_pseudonymisation_racing_a_discovery_batch_completes(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    fast_deadlock_detection: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T459e: an erasure and a `DiscoverStage` batch over a `match_players` row both write. The
    batch's match lists the erased profile (SUBJECT) and ALPHA; SUBJECT's stored row for that game
    is the one the erasure rewrites. Before the fix the erasure took the `match_players` row and
    then asked for `aoe_profiles(SUBJECT)`, which the batch held while asking for the row: a
    deadlock that aborts whichever transaction Postgres picks, discovery's included. After it both
    complete.

    **T459g: and no capture survives.** The batch holds `aoe_profiles(SUBJECT)` first in this
    interleave, so it enqueues SUBJECT's capture before the erasure commits; the erasure then
    locks and deletes that row, and `replay_captures` is empty for every game the race touches.
    The opposite order - the erasure committing first - is
    `test_a_batch_that_read_the_archiving_set_before_an_erasure_enqueues_no_capture`.
    """
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)
    await _seed_owner_of(http, session_factory, (_SUBJECT,))
    race = _PseudonymisationRace(engine)
    race.install(monkeypatch)

    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=_IngesterRelic(_raw_match(_STORED_OLD_GAMES[0], (_SUBJECT, _ALPHA))),
        capture_budget_days=21,
    )
    outcomes = await asyncio.gather(stage(Budget(seconds=30)), _erase(http), return_exceptions=True)

    assert not [o for o in outcomes if isinstance(o, BaseException)], outcomes
    report, response = outcomes
    assert isinstance(response, httpx.Response) and response.status_code == 200, response
    assert isinstance(report, dict) and report["matches_discovered"] == 1, report
    assert race.rewrote_keys.is_set() and race.touched_profiles.is_set()

    async with session_factory() as session:
        captures = (
            await session.execute(select(ReplayCapture.game_id, ReplayCapture.profile_id))
        ).all()
        alias = (await session.get(AoeProfile, _SUBJECT)).alias  # type: ignore[union-attr]
        rewritten = (
            await session.execute(
                select(MatchPlayer.profile_id).where(MatchPlayer.game_id == _STORED_OLD_GAMES[1])
            )
        ).scalars()
        others = set(rewritten)
    assert captures == [], f"a capture survived the erasure: {captures}"
    assert alias == PSEUDONYMISED_ALIAS
    assert -_SUBJECT in others and _SUBJECT not in others


class _CaptureDeleteRace(_Rendezvous):
    """The interleave of reviewer finding 1 on #123, formed from conditions:

    - the erasure, after it has executed `DELETE FROM replay_captures`, waits until the discovery
      batch has upserted `aoe_profiles`;
    - the batch, before it executes its `INSERT INTO replay_captures`, waits until the erasure has
      executed that `DELETE`.

    With the delete before the pseudonymisation that leaves the erasure holding the capture row
    and asking for `aoe_profiles(profile)`, and the batch holding the second and inserting the
    capture row the erasure has deleted but not committed: the insert waits on the erasure.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine)
        self.deleted_captures = asyncio.Event()
        self.touched_profiles = asyncio.Event()

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_execute = AsyncSession.execute

        async def spy(self_session: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
            name = getattr(getattr(statement, "table", None), "name", None)
            is_insert = getattr(statement, "is_insert", False)
            is_capture_delete = name == "replay_captures" and getattr(statement, "is_delete", False)
            is_capture_insert = name == "replay_captures" and is_insert
            is_profile_touch = name == "aoe_profiles" and is_insert
            if is_capture_insert:
                await self._park_until(self.deleted_captures)
            result = await real_execute(self_session, statement, *args, **kwargs)
            if is_profile_touch:
                self.touched_profiles.set()
            if is_capture_delete:
                self.deleted_captures.set()
                await self._park_until(self.touched_profiles)
            return result

        monkeypatch.setattr(AsyncSession, "execute", spy)


async def test_erasure_deleting_a_stored_capture_racing_a_discovery_batch_completes(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    fast_deadlock_detection: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T459g: SUBJECT already has a capture row for the game the batch rediscovers. The erasure
    deletes it; the batch's `INSERT ... ON CONFLICT DO NOTHING` meets that row. Before the fix the
    erasure deleted the row first and then waited on `aoe_profiles(SUBJECT)`, which the batch held:
    `DeadlockDetected`, and discovery the victim. After it both complete and no capture is left."""
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)
    await _seed_owner_of(http, session_factory, (_SUBJECT,))
    async with session_factory() as session:
        session.add_all(
            ReplayCapture(
                game_id=game_id,
                profile_id=_SUBJECT,
                status=CaptureStatus.PENDING,
                capture_deadline_at=_MATCH_COMPLETED_AT + timedelta(days=21),
                source=CaptureSource.AUTOMATIC,
            )
            for game_id in _STORED_OLD_GAMES
        )
        await session.commit()
    race = _CaptureDeleteRace(engine)
    race.install(monkeypatch)

    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=_IngesterRelic(_raw_match(_STORED_OLD_GAMES[0], (_SUBJECT, _ALPHA))),
        capture_budget_days=21,
    )
    outcomes = await asyncio.gather(stage(Budget(seconds=30)), _erase(http), return_exceptions=True)

    assert not [o for o in outcomes if isinstance(o, BaseException)], outcomes
    report, response = outcomes
    assert isinstance(response, httpx.Response) and response.status_code == 200, response
    assert isinstance(report, dict) and report["matches_discovered"] == 1, report
    assert race.deleted_captures.is_set() and race.touched_profiles.is_set()
    async with session_factory() as session:
        captures = (
            await session.execute(select(ReplayCapture.game_id, ReplayCapture.profile_id))
        ).all()
    assert captures == [], f"a capture survived the erasure: {captures}"


class _GatedRelic(_IngesterRelic):
    """Answers only once `released` is set, which happens after the erasure has committed:
    `DiscoverStage` reads its archiving set before it calls the provider, so the set it persists
    with is the one from before the erasure."""

    def __init__(self, match: RawMatch, released: asyncio.Event) -> None:
        super().__init__(match)
        self._released = released

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        await asyncio.wait_for(self._released.wait(), _RENDEZVOUS_GUARD_SECONDS)
        return await super().recent_matches(profile_ids)


async def test_a_batch_that_read_the_archiving_set_before_an_erasure_enqueues_no_capture(
    http: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """T459g, FR-037: the erasure commits between the batch's read of the archiving set and its
    capture enqueue. SUBJECT is still in the set, so only the `INSERT`'s own check of
    `profile_links` stops the capture. `matches_discovered` shows the batch ran."""
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)
    await _seed_owner_of(http, session_factory, (_SUBJECT,))
    erased = asyncio.Event()
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=_GatedRelic(
            _raw_match(_STORED_OLD_GAMES[0], (_SUBJECT, _ALPHA)), erased
        ),
        capture_budget_days=21,
    )
    batch = asyncio.ensure_future(stage(Budget(seconds=30)))
    response = await _erase(http)
    erased.set()
    report = await batch

    assert response.status_code == 200, response.text
    assert report["matches_discovered"] == 1, report
    assert report["captures_enqueued"] == 0, report
    async with session_factory() as session:
        captures = (
            await session.execute(select(ReplayCapture.game_id, ReplayCapture.profile_id))
        ).all()
    assert captures == [], f"a capture was enqueued for an erased profile: {captures}"


async def test_erasure_locks_the_captures_it_deletes_after_the_pseudonymisation(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """T459g: with stored captures for both erased profiles, `POST /api/privacy/erase` still takes
    every lock in the global order, `replay_captures` last, and the rows are gone."""
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)
    await _seed_owner_of(http, session_factory, (_BRAVO, _SUBJECT))
    async with session_factory() as session:
        session.add_all(
            ReplayCapture(
                game_id=game_id,
                profile_id=profile_id,
                status=CaptureStatus.PENDING,
                capture_deadline_at=_MATCH_COMPLETED_AT + timedelta(days=21),
                source=CaptureSource.AUTOMATIC,
            )
            for game_id in _STORED_OLD_GAMES
            for profile_id in (_BRAVO, _SUBJECT, _ALPHA)
        )
        await session.commit()
    with _LockRecorder(engine) as recorder:
        response = await _erase(http)
    assert response.status_code == 200, response.text

    assert not recorder.violations(), (
        "row locks taken against the global order:\n  "
        + "\n  ".join(recorder.violations())
        + "\nfull sequence per connection:\n"
        + recorder.sequence()
    )
    assert "replay_captures" in recorder.sequence()
    async with session_factory() as session:
        remaining = (
            await session.execute(select(ReplayCapture.game_id, ReplayCapture.profile_id))
        ).all()
    assert sorted(remaining) == [(game_id, _ALPHA) for game_id in _STORED_OLD_GAMES]


async def test_recorder_reports_a_capture_delete_that_precedes_the_pseudonymisation(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """The order `erase_account` had before T459g: captures deleted, then an `aoe_profiles` row
    locked. The recorder must flag it whether or not the delete was preceded by a locking select."""
    await _seed_stored_matches(session_factory, _STORED_OLD_GAMES, completed_at=_MATCH_COMPLETED_AT)

    async def erase_in(session: AsyncSession, *, lock_first: bool) -> None:
        if lock_first:
            await session.execute(
                select(ReplayCapture)
                .where(ReplayCapture.profile_id.in_([_SUBJECT]))
                .order_by(ReplayCapture.game_id, ReplayCapture.profile_id)
                .with_for_update()
            )
        await session.execute(delete(ReplayCapture).where(ReplayCapture.profile_id.in_([_SUBJECT])))
        await session.execute(
            select(AoeProfile)
            .where(AoeProfile.profile_id == _SUBJECT)
            .with_for_update(key_share=True)
        )

    for lock_first in (False, True):
        with _LockRecorder(engine) as recorder:
            async with session_scope(session_factory) as session:
                await erase_in(session, lock_first=lock_first)
        assert recorder.violations(), f"lock_first={lock_first}\n{recorder.sequence()}"
