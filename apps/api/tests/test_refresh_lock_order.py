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
  `test_other_database_errors_in_the_refresh_still_fail` are (d).
- `test_match_detail_identity_refresh_touches_in_profile_id_order` covers the third API caller,
  `routers/matches.py::_refresh_match_identity`.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_api import security
from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_session
from aoe2stats_api.routers import matches as matches_router
from aoe2stats_api.routers import players as players_router
from aoe2stats_api.settings import get_settings
from aoe2stats_ingester import discover
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.discover import DiscoverStage
from aoe2stats_providers.base import RawMatch, RawProfile
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchPlayer,
    ProfileLink,
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
    """A `40P01` (deadlock) or `40001` (serialisation failure) raised by the database inside the
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
    """Nothing broader than `40P01`/`40001` is swallowed: a `22012` (division by zero) raised from
    the same place propagates, and the request fails."""
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


# --- routers/matches.py::_refresh_match_identity -------------------------------------------------


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
