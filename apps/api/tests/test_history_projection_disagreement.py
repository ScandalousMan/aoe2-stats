"""T459f — a Relic self-contradiction must not fail a request.

**The defect (production, 2026-10-04, `GET /api/players/212721/matches` -> 500,
an unhandled exception).** In game 331012313 Relic's `matchhistorymember[]` said profile
18558404 played civilisation 1 and its own `matchhistoryreportresults[]` said 0 — one pair of 770
in that response. `project_match_player` raised, nothing caught it, and the on-view refresh
(`_persist_on_view_refresh` -> `persist_matches_and_profiles` -> `upsert_match_players`) took the
whole request down with it, on every view.

The test drives the real route end to end through the `httpx.AsyncClient.send` seam
(`test_third_party_history.py`'s own convention): a fake Relic answers a match whose subject pair
disagrees on the civilisation, and the response must be a 200 with the pair's `match_players` row
written — the disputed field `NULL`, every agreed field kept.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import AoeProfile, MatchPlayer, User
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

_SESSION_COOKIE_NAME = "session_id"


@pytest.fixture(autouse=True)
def _storage_logger_enabled() -> None:
    """The migrations' `fileConfig` (`infra/migrations/env.py`, run by the first throwaway database
    of the session) disables every logger that already exists, which would make the warning this
    file asserts a silent no-op in a full-suite run."""
    logging.getLogger("aoe2stats_storage").disabled = False


_RELIC_HOST = "aoe-api.worldsedgelink.com"
_COMPANION_HOST = "data.aoe2companion.com"

_SUBJECT = 901_459_100
_OPPONENT = 901_459_200
_GAME_ID = 850_459_111
_COMPLETED_AT = datetime(2026, 10, 3, 12, 5, 0, tzinfo=UTC)


def _entry(*, report_civ: int) -> dict[str, Any]:
    """One `matchHistoryStats[]` entry. The subject's `matchhistorymember` civilisation is 1; the
    report-results civilisation is `report_civ`, so `report_civ=0` is the production shape and
    `report_civ=1` its agreeing contrast."""
    return {
        "id": _GAME_ID,
        "matchtype_id": 3,
        "mapname": "Arabia",
        "startgametime": int((_COMPLETED_AT - timedelta(minutes=30)).timestamp()),
        "completiontime": int(_COMPLETED_AT.timestamp()),
        "matchhistorymember": [
            {
                "profile_id": _SUBJECT,
                "civilization_id": 1,
                "teamid": 0,
                "outcome": 1,
                "oldrating": 1500,
                "newrating": 1520,
            },
            {
                "profile_id": _OPPONENT,
                "civilization_id": 12,
                "teamid": 1,
                "outcome": 0,
                "oldrating": 1510,
                "newrating": 1490,
            },
        ],
        "matchhistoryreportresults": [
            {"profile_id": _SUBJECT, "civilization_id": report_civ, "teamid": 0, "resulttype": 1},
            {"profile_id": _OPPONENT, "civilization_id": 12, "teamid": 1, "resulttype": 0},
        ],
    }


async def _sign_in(client: TestClient, db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()
    session_id = secrets.token_urlsafe(32)
    db_session.add(
        UserSession(
            id=session_id, user_id=user.id, created_at=now, expires_at=now + timedelta(days=30)
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(_SESSION_COOKIE_NAME, security._sign(session_id, secret))


def _fake_relic(monkeypatch: pytest.MonkeyPatch, entry: dict[str, Any]) -> None:
    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _COMPANION_HOST:
            return httpx.Response(403, request=request)
        if request.url.host != _RELIC_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return httpx.Response(200, json={"matchHistoryStats": [entry]})

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)


async def _rows(db_session: AsyncSession) -> dict[int, MatchPlayer]:
    db_session.expire_all()
    rows = (
        (await db_session.execute(select(MatchPlayer).where(MatchPlayer.game_id == _GAME_ID)))
        .scalars()
        .all()
    )
    return {row.profile_id: row for row in rows}


async def test_a_player_history_request_survives_a_relic_self_contradiction(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _sign_in(client, db_session)
    db_session.add(AoeProfile(profile_id=_SUBJECT, alias="Subject"))
    await db_session.commit()
    _fake_relic(monkeypatch, _entry(report_civ=0))

    with caplog.at_level("WARNING", logger="aoe2stats_storage"):
        response = client.get(f"/api/players/{_SUBJECT}/matches")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    rows = await _rows(db_session)
    assert set(rows) == {_SUBJECT, _OPPONENT}
    subject = rows[_SUBJECT]
    assert subject.civ_id is None, "the disputed field is the unknown state"
    assert (subject.team_id, subject.result) == (0, "win")
    assert (subject.rating, subject.rating_diff) == (1520, 20)
    assert (rows[_OPPONENT].civ_id, rows[_OPPONENT].result) == (12, "loss")
    assert any("civ_id" in record.getMessage() for record in caplog.records)


async def test_the_same_request_with_agreeing_lists_projects_every_field(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _sign_in(client, db_session)
    db_session.add(AoeProfile(profile_id=_SUBJECT, alias="Subject"))
    await db_session.commit()
    _fake_relic(monkeypatch, _entry(report_civ=1))

    with caplog.at_level("WARNING", logger="aoe2stats_storage"):
        response = client.get(f"/api/players/{_SUBJECT}/matches")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    subject = (await _rows(db_session))[_SUBJECT]
    assert (subject.civ_id, subject.team_id, subject.result) == (1, 0, "win")
    assert not [r for r in caplog.records if r.name == "aoe2stats_storage"]
