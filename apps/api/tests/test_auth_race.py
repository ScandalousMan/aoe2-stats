"""T029c: a concurrent first sign-in must be idempotent, not a 500 with the whole sign-in rolled
back, in `apps/api/src/aoe2stats_api/routers/auth.py`.

Two race windows, both a check (a `SELECT`) followed by a write that is not atomic with it:

1. **The identity key.** Two callbacks for the *same brand-new* Steam account both read
   `existing_identity is None`, both compute their own `user_id`, and both attempt to insert
   `steam_identities` — whose primary key is `steam_id64` — for the same identity. Exactly one can
   win; the loser's insert collides on that primary key.
2. **The one-primary index.** Two links landing while the account still has zero active links both
   read `active_links == 0` and both attempt to insert a `profile_links` row with `is_primary=True`
   — colliding on `ix_profile_links_user_id_primary` (data-model.md), the partial unique index that
   enforces "exactly one primary link per user".

Before T029c, either collision raises `IntegrityError` straight through `session_scope` (`packages/
storage/src/aoe2stats_storage/repositories/base.py`), which rolls the whole request back and lets
it propagate to the catch-all handler as a raw 500 — for a caller who did nothing wrong beyond
signing in from two tabs, or two devices, at once. This file drives both races for real, against
the actual throwaway Postgres database (`tests/db.py`), rather than asserting against the exception
type in isolation: a caught `IntegrityError` that still leaves two identity rows, two primaries, or
an orphaned account behind would not be a fix.

**Why two separate `TestClient`s, not one.** A real race is two different callers — two browser
tabs, two devices — each with their own cookie jar; a single `TestClient`'s cookie jar can hold only
one `steam_oauth_state`/session cookie value at a time, which is not the shape of either race this
file drives. `two_apps` below builds two independent `create_app()` instances, each wired to the
*same* throwaway database through `session_factory` (`tests/db.py`) — the same database, two
separate connections, exactly like two independent server-side request handlers serving two
different browsers.

**Why a `threading.Barrier`, not just "fire two requests and hope".** Two requests fired back to
back from two Python threads are not guaranteed to reach the write phase at the same wall-clock
moment — one could easily finish (and commit) before the other's read even runs, which would prove
nothing about the race this file exists to catch. `check_authentication` (`SteamAuthProvider.
verify`, offloaded to its own worker thread by `asyncio.to_thread` — T026b) is the one point every
sign-in passes through before either race window, and is reached from a genuine OS thread on both
sides (each `TestClient`'s own portal thread, in turn offloading to a `to_thread` worker) — so a
`threading.Barrier(2)` there reliably lines both callbacks up immediately before the read-then-write
sequence that follows, without reaching into the router's internals to synchronise anything the
production code does not already expose.
"""

from __future__ import annotations

import contextlib
import secrets
import threading
import uuid
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_api import security
from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import ProfileLink, SteamIdentity, User
from aoe2stats_storage.models import Session as UserSession
from aoe2stats_storage.repositories.base import session_scope

pytestmark = [pytest.mark.usefixtures("environment")]

SESSION_COOKIE_NAME = "session_id"

_START_PATH = "/api/auth/steam/start"
_CALLBACK_PATH = "/api/auth/steam/callback"

_STEAM_CHECK_AUTH_VALID = "ns:http://specs.openid.net/auth/2.0\nis_valid:true"

# Race 1: the same brand-new Steam account, signed into from two tabs at once.
_RACE1_STEAM_ID = "76561198100000001"
_RACE1_PROFILE_ID = 800_001

# Race 2: an account with zero active links, linking two distinct brand-new Steam accounts at once.
_RACE2_STEAM_ID_X = "76561198100000002"
_RACE2_PROFILE_ID_X = 800_002
_RACE2_STEAM_ID_Y = "76561198100000003"
_RACE2_PROFILE_ID_Y = 800_003


# --- The fake upstream: httpx.Client.send / httpx.AsyncClient.send, shared by both TestClients ---


class _RaceFakeUpstream:
    """Always answers `check_authentication` as valid and `getPersonalStat` from whichever
    persona a request names — like `test_multi_account.py`'s `_FakeUpstream`, since forging or
    replaying the Steam assertion is T019's and T021's concern, not this file's. The one addition
    is `steam_barrier`: see the module docstring for why the rendezvous lives here.
    """

    def __init__(self, *, participants: int) -> None:
        self.personas: dict[str, tuple[int, str, str]] = {}
        self.steam_barrier = threading.Barrier(participants, timeout=10)
        self.check_authentication_calls = 0

    def add_persona(self, steam_id64: str, profile_id: int, alias: str, country: str) -> None:
        self.personas[steam_id64] = (profile_id, alias, country)

    def steam_response(self, request: httpx.Request) -> httpx.Response:
        # Line every racing callback up here — see the module docstring — so the read-then-write
        # sequence that follows actually overlaps in wall-clock time.
        with contextlib.suppress(threading.BrokenBarrierError):
            self.steam_barrier.wait()
        self.check_authentication_calls += 1
        return httpx.Response(200, text=_STEAM_CHECK_AUTH_VALID, request=request)

    def relic_response(self, request: httpx.Request) -> httpx.Response:
        # `resolve_profile` names the Steam id (`/steam/<id>` in `profile_names`); `personal_
        # stats` names the already-resolved `profile_id` instead (`profile_ids`) — both requests
        # this module's flow makes per sign-in, so both shapes must resolve to the same persona.
        haystack = request.url.query.decode() + (request.content or b"").decode(errors="ignore")
        persona = next(
            (persona for steam_id64, persona in self.personas.items() if steam_id64 in haystack),
            None,
        )
        if persona is None:
            persona = next(
                (
                    candidate
                    for candidate in self.personas.values()
                    if str(candidate[0]) in haystack
                ),
                None,
            )
        if persona is None:
            raise AssertionError(f"unrecognised persona in Relic request: {haystack}")
        profile_id, alias, country = persona
        member_groups = [
            {
                "id": profile_id,
                "type": 1,
                "name": "",
                "members": [
                    {
                        "profile_id": profile_id,
                        "name": next(
                            f"/steam/{steam_id64}"
                            for steam_id64, p in self.personas.items()
                            if p == persona
                        ),
                        "alias": alias,
                        "country": country,
                        "personal_statgroup_id": profile_id,
                        "clanlist_name": "",
                        "leaderboardregion_id": 0,
                        "level": 1,
                        "xp": 0,
                    }
                ],
            }
        ]
        leaderboard_stats = [
            {
                "statgroup_id": profile_id,
                "leaderboard_id": 3,
                "rating": 1000,
                "rank": -1,
                "ranklevel": 0,
                "ranktotal": 0,
                "regionrank": -1,
                "regionranktotal": 0,
                "wins": 0,
                "losses": 0,
                "streak": 0,
                "drops": 0,
                "disputes": 0,
                "highestrank": 0,
                "highestranklevel": 0,
                "highestrating": 1000,
                "lastmatchdate": 0,
            }
        ]
        body = {
            "result": {"code": 0, "message": "OK"},
            "statGroups": member_groups,
            "leaderboardStats": leaderboard_stats,
        }
        return httpx.Response(200, json=body, request=request)


def _install_fake_upstream(monkeypatch: pytest.MonkeyPatch, fake: _RaceFakeUpstream) -> None:
    original_sync_send = httpx.Client.send

    def sync_send(self: httpx.Client, request: httpx.Request, **kwargs: object) -> httpx.Response:
        if request.url.host == "steamcommunity.com":
            return fake.steam_response(request)
        return original_sync_send(self, request, **kwargs)  # type: ignore[no-any-return]

    async def async_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host != "aoe-api.worldsedgelink.com":
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return fake.relic_response(request)

    monkeypatch.setattr(httpx.Client, "send", sync_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", async_send)


@pytest.fixture(autouse=True)
def _allowlist_every_persona(environment: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "BETA_ALLOWLIST_STEAM_IDS",
        ",".join([_RACE1_STEAM_ID, _RACE2_STEAM_ID_X, _RACE2_STEAM_ID_Y]),
    )
    get_settings.cache_clear()


# --- Two independent TestClients over the same throwaway database --------------------------------


@pytest.fixture
def two_apps(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[tuple[TestClient, TestClient]]:
    """Two independent `create_app()` instances, each wired to the *same* database — two separate
    browsers, one server. See the module docstring for why one `TestClient` cannot model this.
    """

    def _build_client(stack: contextlib.ExitStack) -> TestClient:
        app = create_app()

        async def _get_session() -> AsyncIterator[AsyncSession]:
            async with session_scope(session_factory) as session:
                yield session

        app.dependency_overrides[get_session] = _get_session
        app.dependency_overrides[get_object_store] = lambda: None
        client = stack.enter_context(TestClient(app, base_url="https://testserver"))
        return client

    with contextlib.ExitStack() as stack:
        yield _build_client(stack), _build_client(stack)


@pytest.fixture
async def db_session_for_setup(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_scope(session_factory) as session:
        yield session


async def _seed_user_with_no_active_links(db_session: AsyncSession) -> User:
    """An account with zero active links — the precondition race 2 needs. Realistic paths there
    (unlinking a last profile, T031b) are exercised elsewhere; what matters here is only the state
    itself, seeded directly rather than re-derived through a flow this file is not testing.
    """
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4(), created_at=now, allowlisted_at=now, ingest_consent_at=now)
    db_session.add(user)
    await db_session.commit()
    return user


async def _sign_in_as(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand `client` its cookie — the same convention
    `test_multi_account.py` uses for an account that must simply already exist."""
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


def _begin(client: TestClient, *, link: bool) -> tuple[str, dict[str, str]]:
    path = f"{_START_PATH}?link=1" if link else _START_PATH
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 302, (
        f"{path} did not redirect to Steam: {response.status_code} {response.text}"
    )
    location = response.headers["location"]
    parsed = urlsplit(location)
    assert parsed.hostname == "steamcommunity.com"
    start_params = dict(parse_qsl(parsed.query))
    return_to = start_params["openid.return_to"]
    return_to_query = dict(parse_qsl(urlsplit(return_to).query))
    return return_to, return_to_query


def _callback_params(steam_id64: str, return_to: str) -> dict[str, str]:
    identity = f"https://steamcommunity.com/openid/id/{steam_id64}"
    return {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "id_res",
        "openid.op_endpoint": "https://steamcommunity.com/openid/login",
        "openid.claimed_id": identity,
        "openid.identity": identity,
        "openid.return_to": return_to,
        "openid.response_nonce": f"2026-08-20T12:00:00Z{steam_id64}",
        "openid.assoc_handle": "1234567890",
        "openid.signed": (
            "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"
        ),
        "openid.sig": "dGVzdC1zaWduYXR1cmUtdmFsdWU=",
    }


def _sign_in(client: TestClient, steam_id64: str, *, link: bool) -> httpx.Response:
    """One full begin-then-callback round trip. Everything up to and including `_begin` runs
    before the two racing threads are started (see the two tests below) — only the callback
    itself, where both race windows live, needs to run concurrently.
    """
    return_to, return_to_query = _begin(client, link=link)
    params = {**return_to_query, **_callback_params(steam_id64, return_to)}
    return client.get(_CALLBACK_PATH, params=params, follow_redirects=False)


def _callback_only(
    client: TestClient, steam_id64: str, return_to: str, return_to_query: dict[str, str]
) -> httpx.Response:
    params = {**return_to_query, **_callback_params(steam_id64, return_to)}
    return client.get(_CALLBACK_PATH, params=params, follow_redirects=False)


# --- Race 1: two callbacks for the same brand-new Steam account ----------------------------------


async def test_concurrent_first_sign_in_for_the_same_steam_account_is_idempotent(
    two_apps: tuple[TestClient, TestClient],
    db_session_for_setup: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two browsers sign into the *same*, never-before-seen Steam account at the same moment.
    Both must come back with a real, working session — never a 500 — and the database must end up
    with exactly one `User`, one `SteamIdentity`, and one active `ProfileLink` between them, not
    one of each per browser.
    """
    client_a, client_b = two_apps
    fake = _RaceFakeUpstream(participants=2)
    fake.add_persona(_RACE1_STEAM_ID, _RACE1_PROFILE_ID, "RacePlayer", "FR")
    _install_fake_upstream(monkeypatch, fake)

    # Each browser mints its own CSRF state before the race starts — only the callback itself,
    # where steam_identities' primary key is actually contested, needs to run concurrently.
    return_to_a, query_a = _begin(client_a, link=False)
    return_to_b, query_b = _begin(client_b, link=False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(_callback_only, client_a, _RACE1_STEAM_ID, return_to_a, query_a)
        future_b = pool.submit(_callback_only, client_b, _RACE1_STEAM_ID, return_to_b, query_b)
        response_a = future_a.result(timeout=15)
        response_b = future_b.result(timeout=15)

    assert response_a.status_code < 500, (
        f"browser A's sign-in answered a server error: {response_a.status_code} {response_a.text}"
    )
    assert response_b.status_code < 500, (
        f"browser B's sign-in answered a server error: {response_b.status_code} {response_b.text}"
    )
    assert response_a.is_redirect, f"browser A did not come back signed in: {response_a.text}"
    assert response_b.is_redirect, f"browser B did not come back signed in: {response_b.text}"

    me_a = client_a.get("/api/me").json()
    me_b = client_b.get("/api/me").json()
    assert me_a["authenticated"] is True, "browser A must end up signed in despite the race"
    assert me_b["authenticated"] is True, "browser B must end up signed in despite the race"
    assert me_a["user_id"] == me_b["user_id"], (
        "both browsers signed into the same Steam account and must land on the same aoe2-stats "
        "account, not two separate ones each holding half of one sign-in"
    )

    identities = (
        (
            await db_session_for_setup.execute(
                select(SteamIdentity).where(SteamIdentity.steam_id64 == _RACE1_STEAM_ID)
            )
        )
        .scalars()
        .all()
    )
    assert len(identities) == 1, (
        f"steam_identities must hold exactly one row for {_RACE1_STEAM_ID}, found "
        f"{len(identities)} — the identity-key race was not made idempotent"
    )

    users = (await db_session_for_setup.execute(select(User))).scalars().all()
    assert len(users) == 1, f"exactly one account must exist, found {len(users)}"

    active_links = (
        (
            await db_session_for_setup.execute(
                select(ProfileLink).where(
                    ProfileLink.profile_id == _RACE1_PROFILE_ID, ProfileLink.unlinked_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(active_links) == 1, (
        f"exactly one active profile_links row must exist for the profile, found "
        f"{len(active_links)}"
    )
    assert active_links[0].is_primary is True, "the account's one active link must be primary"


# --- Race 2: two links landing while the account has zero active links ---------------------------


async def test_concurrent_links_into_an_account_with_no_active_link_stay_single_primary(
    two_apps: tuple[TestClient, TestClient],
    db_session_for_setup: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One account, currently with zero active links, has two *distinct* brand-new Steam accounts
    linked to it at the same moment (two devices, both already signed in as the same
    aoe2-stats account). Both links must succeed — never a 500 — and end with exactly one of the
    two primary, never zero and never both.
    """
    client_a, client_b = two_apps
    fake = _RaceFakeUpstream(participants=2)
    fake.add_persona(_RACE2_STEAM_ID_X, _RACE2_PROFILE_ID_X, "RacePlayerX", "FR")
    fake.add_persona(_RACE2_STEAM_ID_Y, _RACE2_PROFILE_ID_Y, "RacePlayerY", "FR")
    _install_fake_upstream(monkeypatch, fake)

    user = await _seed_user_with_no_active_links(db_session_for_setup)
    # Both browsers are already signed in as the same account — the same session, held by two
    # cookie jars, exactly as two tabs of one real browser would carry it.
    await _sign_in_as(client_a, db_session_for_setup, user)
    await _sign_in_as(client_b, db_session_for_setup, user)

    return_to_a, query_a = _begin(client_a, link=True)
    return_to_b, query_b = _begin(client_b, link=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(_callback_only, client_a, _RACE2_STEAM_ID_X, return_to_a, query_a)
        future_b = pool.submit(_callback_only, client_b, _RACE2_STEAM_ID_Y, return_to_b, query_b)
        response_a = future_a.result(timeout=15)
        response_b = future_b.result(timeout=15)

    assert response_a.status_code < 500, (
        f"linking X answered a server error: {response_a.status_code} {response_a.text}"
    )
    assert response_b.status_code < 500, (
        f"linking Y answered a server error: {response_b.status_code} {response_b.text}"
    )
    assert response_a.is_redirect, f"linking X did not succeed: {response_a.text}"
    assert response_b.is_redirect, f"linking Y did not succeed: {response_b.text}"

    active_links = (
        (
            await db_session_for_setup.execute(
                select(ProfileLink).where(
                    ProfileLink.user_id == user.id, ProfileLink.unlinked_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    assert {link.profile_id for link in active_links} == {
        _RACE2_PROFILE_ID_X,
        _RACE2_PROFILE_ID_Y,
    }, "both concurrent links must have succeeded, neither silently dropped"
    primary_count = sum(1 for link in active_links if link.is_primary)
    details = [(link.profile_id, link.is_primary) for link in active_links]
    assert primary_count == 1, (
        f"exactly one active link must be primary (FR-043, ix_profile_links_user_id_primary), "
        f"found {primary_count} among {details}"
    )
