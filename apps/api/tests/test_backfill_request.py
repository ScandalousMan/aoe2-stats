"""Integration test for T031a: on a successful link, `profile_links.backfill_requested_at` is
stamped so the next ingestion cycle sweeps the preceding 31 days for that profile (FR-015,
SC-003 — "queued within one ingestion cycle of linking").

The link itself enqueues nothing — `replay_captures.capture_deadline_at` is computed from
`matches.completed_at` (T053), and no `matches` row exists yet for a profile nobody has ever
polled. This flag is how a link asks a later cycle (T054) to do the sweep it cannot do itself; a
link that fails to stamp it silently loses everything the player played before signing up.

Exercises the real `GET /api/auth/steam/start` -> `GET /api/auth/steam/callback` flow (T029)
against the real throwaway database (T015/T015a), the same way `test_auth_flow.py` (T021) does:
interception happens at the `httpx.Client.send` / `httpx.AsyncClient.send` boundary every provider
is built on (`packages/providers/src/aoe2stats_providers/base.py`), answered from the real frozen
fixtures T012 captured (`packages/providers/fixtures/`), rather than at any dependency name
internal to the router.

Two scenarios, both from the task text: a first link stamps the flag, and a relink of a
previously unlinked profile stamps it again — on the **new** row, never the old one. `DELETE
/api/profiles/{profile_id}` (T031) does not exist yet, so "unlink" is simulated the same way
`test_unlink.py` and `test_multi_account.py` already accept as a working assumption for state that
belongs to a router this task does not own: set `unlinked_at` directly on the row, then drive a
real returning sign-in through the callback and assert what it wrote.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import ProfileLink

_FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "providers" / "fixtures"

_STEAM_CHECK_AUTH_VALID = (_FIXTURES / "steam" / "check_authentication_valid.txt").read_text()
_RELIC_PERSONAL_STAT = json.loads((_FIXTURES / "relic" / "get_personal_stat.json").read_text())

# docs/data-sources.md: "Verified: 76561197984749679 resolves to profile 196240" — the one
# steamid64/profile_id pair backed by a real, frozen response, matching test_auth_flow.py (T021).
_STEAM_ID64 = "76561197984749679"
_PROFILE_ID = 196240

_START_PATH = "/api/auth/steam/start"
_CALLBACK_PATH = "/api/auth/steam/callback"


# --- The fake upstream: the httpx transport boundary every provider is built on -----------------


class _FakeUpstream:
    """Stands in for Steam's `check_authentication` and Relic's `getPersonalStat`. Every
    `check_authentication` call answers valid: forging or replaying the assertion is T019's and
    T021's concern, not this file's — only the effect of a *genuine* link or relink on
    `backfill_requested_at` is under test here.
    """

    def __init__(self) -> None:
        self.check_authentication_calls = 0

    def steam_response(self, request: httpx.Request) -> httpx.Response:
        self.check_authentication_calls += 1
        return httpx.Response(200, text=_STEAM_CHECK_AUTH_VALID, request=request)

    def relic_response(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_RELIC_PERSONAL_STAT, request=request)


@pytest.fixture
def fake_upstream(monkeypatch: pytest.MonkeyPatch) -> _FakeUpstream:
    fake = _FakeUpstream()
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
    return fake


@pytest.fixture(autouse=True)
def _allowlist_persona(environment: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`conftest.py`'s `REQUIRED_ENV` ships `BETA_ALLOWLIST_STEAM_IDS` empty (T022 owns that
    rejection); this file admits the one persona it uses."""
    monkeypatch.setenv("BETA_ALLOWLIST_STEAM_IDS", _STEAM_ID64)
    get_settings.cache_clear()


# --- Helpers ---------------------------------------------------------------------------------


def _begin_sign_in(client: TestClient) -> tuple[str, dict[str, str]]:
    response = client.get(_START_PATH, follow_redirects=False)
    assert response.status_code == 302, (
        f"GET {_START_PATH} did not redirect to Steam: {response.status_code} {response.text}"
    )
    location = response.headers["location"]
    parsed = urlsplit(location)
    assert parsed.hostname == "steamcommunity.com", f"expected a redirect to Steam, got {location}"
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


def _sign_in(client: TestClient, steam_id64: str = _STEAM_ID64) -> httpx.Response:
    """One full begin-then-callback round trip. `_STEAM_CHECK_AUTH_VALID` is not single-use here
    (unlike `test_auth_flow.py`'s replay scenario), so this can be called more than once against
    the same `client` to drive a returning sign-in."""
    return_to, return_to_query = _begin_sign_in(client)
    params = {**return_to_query, **_callback_params(steam_id64, return_to)}
    return client.get(_CALLBACK_PATH, params=params, follow_redirects=False)


async def _active_profile_link(
    db_session: AsyncSession, *, profile_id: int = _PROFILE_ID
) -> ProfileLink:
    result = await db_session.execute(
        select(ProfileLink).where(
            ProfileLink.profile_id == profile_id, ProfileLink.unlinked_at.is_(None)
        )
    )
    return result.scalar_one()


# --- Tests -------------------------------------------------------------------------------------


async def test_first_link_stamps_backfill_requested_at(
    client: TestClient, db_session: AsyncSession, fake_upstream: _FakeUpstream
) -> None:
    """A brand-new sign-in creates a `profile_links` row with `backfill_requested_at` already set,
    so T054 finds it waiting on the very next ingestion cycle (FR-015, SC-003)."""
    before = datetime.now(UTC)
    response = _sign_in(client)
    assert response.is_redirect, f"sign-in failed: {response.status_code} {response.text}"
    assert fake_upstream.check_authentication_calls == 1

    link = await _active_profile_link(db_session)
    assert link.linked_at is not None
    assert link.backfill_requested_at is not None, (
        "linking must queue the 31-day backfill sweep (T031a) — otherwise a newly linked "
        "profile's past matches are never rescued (FR-015, SC-003)"
    )
    assert link.backfill_requested_at >= before, (
        "the stamp must be set at link time, not inherited from some earlier default"
    )


async def test_relink_after_unlink_stamps_backfill_requested_at_on_the_new_row(
    client: TestClient, db_session: AsyncSession, fake_upstream: _FakeUpstream
) -> None:
    """`profile_links` carries a partial unique index allowing one active link per profile
    (`unlinked_at IS NULL`), so a relink creates a **new** row rather than reviving the old one —
    and that new row must carry its own `backfill_requested_at`, or a player who unlinks and later
    relinks would silently lose the sweep the first link already queued and cleared."""
    first_response = _sign_in(client)
    assert first_response.is_redirect

    original_link = await _active_profile_link(db_session)
    original_link_id = original_link.id

    # Simulate the outcome of `DELETE /api/profiles/{profile_id}` (T031, not yet implemented —
    # out of this task's scope): set `unlinked_at`, matching data-model.md's "set rather than
    # deleted", and clear `backfill_requested_at` the way T054 would once its sweep had already
    # run — so a fresh, non-null value on the new row can only come from this relink, not a
    # leftover from the first link.
    original_link.unlinked_at = datetime.now(UTC) - timedelta(days=1)
    original_link.backfill_requested_at = None
    await db_session.commit()

    client.post("/api/auth/signout")

    relink_response = _sign_in(client)
    assert relink_response.is_redirect, (
        f"relink failed: {relink_response.status_code} {relink_response.text}"
    )
    assert fake_upstream.check_authentication_calls == 2

    db_session.expire_all()
    new_link = await _active_profile_link(db_session)
    assert new_link.id != original_link_id, (
        "a relink must insert a new row, never resurrect the unlinked one (data-model.md)"
    )
    assert new_link.backfill_requested_at is not None, (
        "relinking a previously unlinked profile must queue its own 31-day sweep (T031a) — "
        "otherwise everything played between unlink and relink is silently lost"
    )

    old_row = await db_session.get(ProfileLink, original_link_id)
    assert old_row is not None
    assert old_row.unlinked_at is not None, "the original unlink record must survive a relink"
    assert old_row.backfill_requested_at is None, (
        "the stale row must not be mistaken for the new sweep request"
    )
