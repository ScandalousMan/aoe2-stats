"""Integration tests for T367 (US4) — `apps/api/src/aoe2stats_api/routers/analysis.py` and the
`analysis` object `GET /api/matches/{game_id}` gains alongside it (T368, `[ ]` at the time this
file is written). `contracts/http-api.md`'s "Analysis" section and `data-model.md`'s
`match_analyses` section are this file's own specification.

**Scope, drawn exactly where the task dispatch drew it.** T368 wires two things: the read-only
`GET /api/matches/{game_id}/analysis` route, and the `analysis` summary object on match-detail.
Neither performs any analysis — the work that actually claims a row, fetches a recording and
parses it is `api/analyze.py` (T366), a *separate*, currently-blocked Vercel entrypoint outside
`apps/api`'s FastAPI app entirely (`contracts/http-api.md`: "`POST /api/analyze` ... A separate
Vercel function, not the API app"), and this file neither tests nor implements it. Every state
this file exercises is therefore seeded directly into `match_analyses` — the shape T304/T305
already committed (`MatchAnalysisState`) — rather than produced by driving a real parse, exactly
as the task dispatch instructs.

**The seven states.** `match_analyses.state` (`packages/storage/src/aoe2stats_storage/models.py`)
carries six values: `queued`, `running`, `published`, `failed`, `unavailable`, `refused`. The
seventh, `absent`, is not a stored value at all — it is what the summary `analysis` object reports
when no row exists for a `game_id`, i.e. "never requested" (`contracts/http-api.md`'s own union
type names it first). `_SEVEN_STATE_CASES` below encodes `absent` as `stored_state=None`.

**`stale`, computed against the real running engine.** FR-041: "the comparison between a stored
analysis's parser version and the running engine, computed on read". The one place this repository
already reads "the running engine's version" is `Aoe2RecValidator.validate`
(`packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py`): `importlib.metadata.version
(ENGINE_NAME)`, `ENGINE_NAME = "aoe2rec-py"`. This file reads it the identical way, so a "matching"
seeded `parser_version` is drawn from the same source T368 is expected to compare against, not an
arbitrary string this file invents and hopes agrees.

**The published document.** `GET /api/matches/{game_id}/analysis` serves the artifact
`contracts/analysis.md`'s "The published analysis" section describes — `schema_version`,
`engine`, `source_recording`, `extracted_at`, `participants` — read whole from the object store at
`match_analyses.result_key`, never a redirect to a signed URL: unlike a `.aoe2record` download,
this is this service's own derived JSON, meant for the SPA to `fetch().then(r => r.json())`
directly (T371, T372 wire it into the match page), and nothing in the contract suggests the bucket
is fronted for it the way `replay_object_key` is. `_FakeAnalysisObjectStore` below overrides
`get_object_store` to answer exactly the `result_key` each test wrote into its own seeded row,
never a hand-guessed key naming scheme — the router's job is to read whatever key the row names,
so this fake never needs to know what T368 will choose to call it.

**FR-040, and why one test here is not `xfail`.** The per-user analysis-request limit is enforced
where the request itself is made — `POST /api/analyze`, i.e. `api/analyze.py`, T366 — which this
file does not implement or drive (see "Scope" above); that route's own test file, mirroring
`test_cron_ingest_entrypoint.py`'s split from `test_cron.py`, is not this one.
`test_analysis_request_bucket_enforces_the_configured_daily_cap` below proves the one part of
FR-040 that *is* this file's to prove without waiting on T366 or T368: that
`aoe2stats_api.ratelimit.check_and_increment` (T307, already implemented, already covered
generically by `test_rate_limits.py`) enforces the actual `ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY`
value (T301) over the real `analysis_request` bucket and a real calendar day — the exact
configuration FR-040 rests on, not `test_rate_limits.py`'s own arbitrary limit-and-window fixture.
Since `ratelimit.py` and `settings.py` are both real today, this test is not `xfail`: it is red
today only if the mechanism itself regresses, never because T368 has not landed.

**No import at module scope of anything T368 has not built.** Every test below drives
`aoe2stats_api.routers.analysis` only through `client` — the identical discipline `test_match_
detail.py` and `test_replay_download.py`'s own T335/T338 sections use for a route or a response
field that does not exist yet: there is nothing to import, only an HTTP call that does not yet
behave as specified. `xfail(strict=True, reason="T368 not implemented yet")` marks every test that
depends on that surface, so the marker is removed automatically — as a hard failure, not a silent
pass — the moment T368 makes one actually succeed.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from importlib import metadata
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import ratelimit, security
from aoe2stats_api.deps import get_object_store
from aoe2stats_api.settings import get_settings
from aoe2stats_replay_engine.aoe2rec import ENGINE_NAME
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_unlink.py`'s module docstring, point 1 — this suite's working assumption, not yet
#: fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: The running engine's own name and version, read the identical way `Aoe2RecValidator.validate`
#: already does — module docstring's "`stale`, computed against the real running engine".
_RUNNING_ENGINE_NAME = ENGINE_NAME
_RUNNING_ENGINE_VERSION = metadata.version(_RUNNING_ENGINE_NAME)

_PARTICIPANT_A = 930_100_001
_PARTICIPANT_B = 930_100_002

_PUBLISHED_GAME_ID = 930_200_001

_SEVEN_STATES_GAME_ID_BASE = 930_300_000

_STALE_MATCHING_GAME_ID = 930_400_001
_STALE_MISMATCHED_GAME_ID = 930_400_002

_GET_ANALYSIS_404_GAME_ID_BASE = 930_500_000

_DISTINGUISH_ABSENT_GAME_ID = 930_600_001
_DISTINGUISH_UNAVAILABLE_GAME_ID = 930_600_002
_DISTINGUISH_REFUSED_GAME_ID = 930_600_003


# --- Seeding helpers, self-contained per this suite's own convention (test_match_detail.py, ------
# test_replay_download.py: each test file in this directory keeps its own, never a shared import) -


async def _seed_user(db_session: AsyncSession) -> User:
    user = User(allowlisted_at=datetime.now(UTC))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_match_detail.py`'s own `_sign_in`."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db_session.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


async def _seed_participant(db_session: AsyncSession, *, profile_id: int, alias: str) -> None:
    """One `aoe_profiles` row. `ON CONFLICT DO NOTHING`, not a plain `add`: `_STALE_MATCHING_
    GAME_ID`/`_STALE_MISMATCHED_GAME_ID` and the three `_DISTINGUISH_*_GAME_ID` cases each seed a
    *second* (or third) match sharing this file's own default `(_PARTICIPANT_A, _PARTICIPANT_B)`
    pair — `aoe_profiles.profile_id` is a shared identity across every match a profile ever played,
    never scoped to one, so seeding it again for a second match must be a no-op rather than a
    duplicate-key error the way a second `MatchPlayer`/`Match` row for the same pair already is."""
    statement = (
        pg_insert(AoeProfile)
        .values(profile_id=profile_id, alias=alias, country="FR")
        .on_conflict_do_nothing(index_elements=[AoeProfile.profile_id])
    )
    await db_session.execute(statement)


async def _seed_match(db_session: AsyncSession, *, game_id: int) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=now - timedelta(days=2),
            source="relic",
            raw_payload={"matchHistoryId": game_id},
        )
    )


async def _seed_match_player(db_session: AsyncSession, *, game_id: int, profile_id: int) -> None:
    db_session.add(MatchPlayer(game_id=game_id, profile_id=profile_id))


async def _seed_two_participant_match(
    db_session: AsyncSession,
    *,
    game_id: int,
    participant_ids: tuple[int, int] = (_PARTICIPANT_A, _PARTICIPANT_B),
) -> None:
    """A match with two participants — every state this file exercises needs a real match to hang
    the `match_analyses` row off (its own foreign key), and every state needs "every participant"
    to mean something (FR-030)."""
    await _seed_match(db_session, game_id=game_id)
    for index, profile_id in enumerate(participant_ids):
        await _seed_participant(db_session, profile_id=profile_id, alias=f"Participant{index}")
        await _seed_match_player(db_session, game_id=game_id, profile_id=profile_id)
    await db_session.commit()


async def _seed_analysis(
    db_session: AsyncSession,
    *,
    game_id: int,
    state: MatchAnalysisState,
    point_of_view_profile_id: int,
    parser_name: str | None = None,
    parser_version: str | None = None,
    result_key: str | None = None,
    error_class: str | None = None,
    error_message: str | None = None,
) -> MatchAnalysis:
    """One `match_analyses` row, seeded directly — this file's whole reason for existing without
    `api/analyze.py`'s pipeline (module docstring, "Scope"). `attempts` and `requested_at` take
    their column defaults; the fields any given `state` would not plausibly carry are left `None`
    rather than filled in for tidiness, since T368 must derive `analysis.reason`/`stale`/etc. from
    exactly what a real row of that state would hold."""
    now = datetime.now(UTC)
    analysis = MatchAnalysis(
        game_id=game_id,
        state=state,
        point_of_view_profile_id=point_of_view_profile_id,
        parser_name=parser_name,
        parser_version=parser_version,
        result_key=result_key,
        error_class=error_class,
        error_message=error_message,
        requested_at=now,
        claimed_at=now if state == MatchAnalysisState.RUNNING else None,
        lease_expires_at=(now + timedelta(seconds=300))
        if state == MatchAnalysisState.RUNNING
        else None,
        finished_at=now
        if state
        in (
            MatchAnalysisState.PUBLISHED,
            MatchAnalysisState.FAILED,
            MatchAnalysisState.UNAVAILABLE,
            MatchAnalysisState.REFUSED,
        )
        else None,
    )
    db_session.add(analysis)
    await db_session.commit()
    await db_session.refresh(analysis)
    return analysis


def _published_document(
    *,
    game_id: int,
    point_of_view_profile_id: int,
    engine_version: str,
    participant_ids: tuple[int, ...],
) -> bytes:
    """The published-analysis shape `contracts/analysis.md` names, filled in with the minimum
    every field needs to be present and well-typed — this file asserts on `participants` alone
    (FR-030's "a result for every participant"), never on the timeline fields themselves, which are
    `apps/analyzer`'s and `packages/replay-engine`'s own contract, not this route's."""
    document = {
        "schema_version": 1,
        "game_id": game_id,
        "point_of_view_profile_id": point_of_view_profile_id,
        "engine": {"name": _RUNNING_ENGINE_NAME, "version": engine_version, "deps": {}},
        "source_recording": {
            "object_key": f"retained-recordings/{game_id}/{point_of_view_profile_id}.zip",
            "sha256": "a" * 64,
        },
        "extracted_at": datetime.now(UTC).isoformat(),
        "participants": [
            {
                "profile_id": profile_id,
                "player_number": index + 1,
                "civ_id": 1,
                "resolved_team_id": (index % 2) + 1,
                "builds": [],
                "trainings": [],
                "researches": [],
                "age_up_commands": {},
                "villagers_ordered": 0,
                "actions": 0,
                "actions_per_minute": 0.0,
                "resigned_at_ms": None,
            }
            for index, profile_id in enumerate(participant_ids)
        ],
    }
    return json.dumps(document).encode("utf-8")


class _FakeAnalysisObjectStore:
    """A `get_object_store` override that answers `get(key)` for exactly the `result_key`s this
    file seeded, and refuses anything else — mirrors `test_replay_download.py`'s own
    `_TrackingObjectStore` in spirit: a fake with no method at all would make a wrongly-behaving
    route fail with a bare `AttributeError` instead of an assertion this file can name.

    `put`/`delete` raise: this route only reads (module docstring's "Scope") — constitution V's
    isolation is exactly `api/analyze.py` writing and this route only ever reading, and a fake that
    silently accepted a write would hide a regression that put the two back in the same process.
    """

    def __init__(self, documents: dict[str, bytes]) -> None:
        self._documents = documents

    async def list_keys(self, prefix: str = "") -> list[str]:
        return list(self._documents)

    async def signed_get_url(
        self, key: str, *, expires_in: int = 300, filename: str | None = None
    ) -> str:
        return f"https://fake-object-store.example/signed/{key}?expires_in={expires_in}"

    async def get(self, key: str) -> bytes:
        try:
            return self._documents[key]
        except KeyError:
            raise AssertionError(f"unexpected object-store read of {key!r}") from None

    async def put(self, key: str, body: bytes, *, content_type: str = "application/json") -> None:
        raise AssertionError(
            "GET /api/matches/{game_id}/analysis must never write — only apps/analyzer writes "
            "(FR-042)"
        )

    async def delete(self, key: str) -> None:
        raise AssertionError("unexpected object-store delete during a read-only analysis fetch")


def _assert_no_index(response: Any) -> None:
    """FR-010, asserted on every HTTP response this file checks — this feature's established
    pattern (`test_no_index_headers.py`, `test_players_routes.py`'s own `_assert_no_index`),
    already true today via `app.py`'s T384 default regardless of whether this feature's own
    routers exist, so this alone never accounts for a test's `xfail`."""
    assert response.headers.get("x-robots-tag") == "noindex, nofollow"
    assert response.headers.get("cache-control") == "private"


def _freeze_rate_limiter_clock(monkeypatch: pytest.MonkeyPatch, *, moment: datetime) -> None:
    """Pins the clock `ratelimit.check_and_increment` reads to a single, fixed `moment` — mirrors
    `test_players_routes.py`'s and `test_replay_download.py`'s own helper of the same name byte for
    byte, so a day-long window's boundary can never fall inside this test's own run."""

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return moment if tz is None else moment.astimezone(tz)

    monkeypatch.setattr(ratelimit, "datetime", _FrozenDateTime)


# ================================================================================================
# FR-030 — a published analysis carries a result for every participant
# ================================================================================================


async def test_published_analysis_answers_a_result_for_every_participant(
    client: TestClient, db_session: AsyncSession
) -> None:
    """US4 scenario 1, FR-030: once a match's recording has been analysed and published — seeded
    directly here (module docstring's "Scope") — `GET /api/matches/{game_id}/analysis` answers the
    published document with a result for every participant, never fewer."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    game_id = _PUBLISHED_GAME_ID
    participant_ids = (_PARTICIPANT_A, _PARTICIPANT_B)
    await _seed_two_participant_match(db_session, game_id=game_id, participant_ids=participant_ids)

    result_key = f"analyses/{game_id}.json"
    document = _published_document(
        game_id=game_id,
        point_of_view_profile_id=participant_ids[0],
        engine_version=_RUNNING_ENGINE_VERSION,
        participant_ids=participant_ids,
    )
    await _seed_analysis(
        db_session,
        game_id=game_id,
        state=MatchAnalysisState.PUBLISHED,
        point_of_view_profile_id=participant_ids[0],
        parser_name=_RUNNING_ENGINE_NAME,
        parser_version=_RUNNING_ENGINE_VERSION,
        result_key=result_key,
    )
    client.app.dependency_overrides[get_object_store] = lambda: _FakeAnalysisObjectStore(  # type: ignore[attr-defined]
        {result_key: document}
    )

    response = client.get(f"/api/matches/{game_id}/analysis")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    _assert_no_index(response)
    body = response.json()
    result_profile_ids = {entry["profile_id"] for entry in body["participants"]}
    assert result_profile_ids == set(participant_ids), (
        "FR-030: the analysis must show a result for every participant, never fewer — got "
        f"{result_profile_ids}"
    )


# ================================================================================================
# SC-011 — the `analysis` object on match-detail, in each of its seven states
# ================================================================================================

#: `stored_state=None` is `absent` — no `match_analyses` row at all (module docstring, "The seven
#: states"). Each case gets its own `game_id` since they share one clean database per test.
_SEVEN_STATE_CASES: tuple[tuple[str, MatchAnalysisState | None, int], ...] = (
    ("absent", None, _SEVEN_STATES_GAME_ID_BASE + 1),
    ("queued", MatchAnalysisState.QUEUED, _SEVEN_STATES_GAME_ID_BASE + 2),
    ("running", MatchAnalysisState.RUNNING, _SEVEN_STATES_GAME_ID_BASE + 3),
    ("published", MatchAnalysisState.PUBLISHED, _SEVEN_STATES_GAME_ID_BASE + 4),
    ("failed", MatchAnalysisState.FAILED, _SEVEN_STATES_GAME_ID_BASE + 5),
    ("unavailable", MatchAnalysisState.UNAVAILABLE, _SEVEN_STATES_GAME_ID_BASE + 6),
    ("refused", MatchAnalysisState.REFUSED, _SEVEN_STATES_GAME_ID_BASE + 7),
)


@pytest.mark.parametrize(
    "expected_state,stored_state,game_id",
    _SEVEN_STATE_CASES,
    ids=[case[0] for case in _SEVEN_STATE_CASES],
)
async def test_analysis_object_appears_on_match_detail_in_every_state(
    client: TestClient,
    db_session: AsyncSession,
    expected_state: str,
    stored_state: MatchAnalysisState | None,
    game_id: int,
) -> None:
    """SC-011: a user can tell, from the match-detail response alone, whether a match can still be
    analysed and until when, without contacting support — which starts with the `analysis.state`
    itself being present and correct in every one of the seven states."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_two_participant_match(db_session, game_id=game_id)
    if stored_state is not None:
        is_published_or_failed = stored_state in (
            MatchAnalysisState.PUBLISHED,
            MatchAnalysisState.FAILED,
        )
        await _seed_analysis(
            db_session,
            game_id=game_id,
            state=stored_state,
            point_of_view_profile_id=_PARTICIPANT_A,
            parser_name=_RUNNING_ENGINE_NAME if is_published_or_failed else None,
            parser_version=_RUNNING_ENGINE_VERSION if is_published_or_failed else None,
            result_key=f"analyses/{game_id}.json"
            if stored_state == MatchAnalysisState.PUBLISHED
            else None,
            error_class="EngineParseError" if stored_state == MatchAnalysisState.FAILED else None,
            error_message="malformed recording"
            if stored_state == MatchAnalysisState.FAILED
            else None,
        )

    response = client.get(f"/api/matches/{game_id}")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    _assert_no_index(response)
    analysis = response.json()["analysis"]
    assert analysis["state"] == expected_state
    assert analysis["result_path"] == f"/api/matches/{game_id}/analysis"
    if expected_state in ("failed", "unavailable", "refused"):
        assert analysis["reason"], f"{expected_state} must carry a reason (contracts/http-api.md)"
    else:
        assert analysis["reason"] is None
    if expected_state != "published":
        assert analysis["stale"] is False, "stale is only ever true for a published analysis"


# ================================================================================================
# FR-041 — `stale` is computed on read, never a stored column
# ================================================================================================


async def test_stale_is_computed_on_read_from_the_running_engine_version(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-041: `stale` compares a published analysis's `parser_version` against the engine
    currently running, computed on every read — `MatchAnalysis` carries no `stale` column
    (`packages/storage/src/aoe2stats_storage/models.py`), so the only way this can ever be `True`
    is a live comparison at request time, proven here by seeding the identical value the real
    engine reports (module docstring, "`stale`, computed against the real running engine") and a
    deliberately different one."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    matching_game_id = _STALE_MATCHING_GAME_ID
    await _seed_two_participant_match(db_session, game_id=matching_game_id)
    await _seed_analysis(
        db_session,
        game_id=matching_game_id,
        state=MatchAnalysisState.PUBLISHED,
        point_of_view_profile_id=_PARTICIPANT_A,
        parser_name=_RUNNING_ENGINE_NAME,
        parser_version=_RUNNING_ENGINE_VERSION,
        result_key=f"analyses/{matching_game_id}.json",
    )

    mismatched_game_id = _STALE_MISMATCHED_GAME_ID
    await _seed_two_participant_match(db_session, game_id=mismatched_game_id)
    await _seed_analysis(
        db_session,
        game_id=mismatched_game_id,
        state=MatchAnalysisState.PUBLISHED,
        point_of_view_profile_id=_PARTICIPANT_A,
        parser_name=_RUNNING_ENGINE_NAME,
        parser_version=f"{_RUNNING_ENGINE_VERSION}-superseded",
        result_key=f"analyses/{mismatched_game_id}.json",
    )

    matching_response = client.get(f"/api/matches/{matching_game_id}")
    mismatched_response = client.get(f"/api/matches/{mismatched_game_id}")

    assert matching_response.status_code == 200, f"Got {matching_response.text}"
    assert mismatched_response.status_code == 200, f"Got {mismatched_response.text}"
    _assert_no_index(matching_response)
    _assert_no_index(mismatched_response)
    assert matching_response.json()["analysis"]["stale"] is False, (
        "a published analysis whose parser_version matches the running engine must not be stale"
    )
    assert mismatched_response.json()["analysis"]["stale"] is True, (
        "a published analysis whose parser_version differs from the running engine must be stale"
    )


# ================================================================================================
# `GET /api/matches/{game_id}/analysis` — 404 in every state but `published`
# ================================================================================================

_GET_ANALYSIS_CASES: tuple[tuple[str, int, MatchAnalysisState | None, int], ...] = (
    ("absent", 404, None, _GET_ANALYSIS_404_GAME_ID_BASE + 1),
    ("queued", 404, MatchAnalysisState.QUEUED, _GET_ANALYSIS_404_GAME_ID_BASE + 2),
    ("running", 404, MatchAnalysisState.RUNNING, _GET_ANALYSIS_404_GAME_ID_BASE + 3),
    ("published", 200, MatchAnalysisState.PUBLISHED, _GET_ANALYSIS_404_GAME_ID_BASE + 4),
    ("failed", 404, MatchAnalysisState.FAILED, _GET_ANALYSIS_404_GAME_ID_BASE + 5),
    ("unavailable", 404, MatchAnalysisState.UNAVAILABLE, _GET_ANALYSIS_404_GAME_ID_BASE + 6),
    ("refused", 404, MatchAnalysisState.REFUSED, _GET_ANALYSIS_404_GAME_ID_BASE + 7),
)


@pytest.mark.parametrize(
    "case_id,expected_status,stored_state,game_id",
    _GET_ANALYSIS_CASES,
    ids=[case[0] for case in _GET_ANALYSIS_CASES],
)
async def test_get_analysis_answers_404_in_every_state_but_published(
    client: TestClient,
    db_session: AsyncSession,
    case_id: str,
    expected_status: int,
    stored_state: MatchAnalysisState | None,
    game_id: int,
) -> None:
    """`contracts/http-api.md`'s "Analysis" table: "The published analysis (FR-030). `404` in
    every state but `published`" — asserted against all seven, not only a hand-picked few, since a
    fix that reaches some non-published states and misses others is exactly the failure mode a
    parametrised sweep over the full state set is for.

    Checks authentication first, before any state is seeded: "Every route below requires a
    signed-in, allowlisted caller" (`contracts/http-api.md`'s own opening line) applies to this
    route exactly as to every other one this feature adds, and an unmatched route today answers a
    plain, auth-blind `404` regardless of state — the `expected_status == 404` half of every
    non-published case below would otherwise hold by coincidence, for the wrong reason, rather than
    turn genuinely red until T368 wires a real, authenticated route."""
    unauthenticated_response = client.get(f"/api/matches/{game_id}/analysis")
    assert unauthenticated_response.status_code == 401, (
        f"{case_id}: an unauthenticated caller must be refused before any state is even looked at"
    )
    assert unauthenticated_response.json()["error"]["code"] == "not_authenticated"

    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_two_participant_match(db_session, game_id=game_id)
    result_key = f"analyses/{game_id}.json"
    if stored_state is not None:
        is_published = stored_state == MatchAnalysisState.PUBLISHED
        await _seed_analysis(
            db_session,
            game_id=game_id,
            state=stored_state,
            point_of_view_profile_id=_PARTICIPANT_A,
            parser_name=_RUNNING_ENGINE_NAME if is_published else None,
            parser_version=_RUNNING_ENGINE_VERSION if is_published else None,
            result_key=result_key if is_published else None,
        )
    document = _published_document(
        game_id=game_id,
        point_of_view_profile_id=_PARTICIPANT_A,
        engine_version=_RUNNING_ENGINE_VERSION,
        participant_ids=(_PARTICIPANT_A, _PARTICIPANT_B),
    )
    client.app.dependency_overrides[get_object_store] = lambda: _FakeAnalysisObjectStore(  # type: ignore[attr-defined]
        {result_key: document}
    )

    response = client.get(f"/api/matches/{game_id}/analysis")

    assert response.status_code == expected_status, (
        f"{case_id}: expected {expected_status}, got {response.status_code}: {response.text}"
    )
    _assert_no_index(response)
    if expected_status == 404:
        assert response.json()["error"]["code"], f"{case_id}: a 404 must still carry a code"


# ================================================================================================
# FR-040 — the per-user analysis-request limit (module docstring: "and why one test here is not
# xfail")
# ================================================================================================


async def test_analysis_request_bucket_enforces_the_configured_daily_cap(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not `xfail` — see the module docstring's own section on this test. `POST /api/analyze`
    (`api/analyze.py`, T366) is where FR-040 is actually enforced against a real request, and it is
    out of this file's scope entirely; what belongs here is proof that the mechanism it will call —
    `ratelimit.check_and_increment`, already implemented (T307) — enforces the real
    `ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY` value over the real `analysis_request` bucket and a
    real calendar day, the exact configuration FR-040 rests on rather than an arbitrary
    limit-and-window pair."""
    caller = await _seed_user(db_session)
    limit = get_settings().analysis_max_requests_per_user_per_day
    day_seconds = 24 * 60 * 60
    window_start = ratelimit._window_start(datetime.now(UTC), day_seconds)
    _freeze_rate_limiter_clock(
        monkeypatch, moment=window_start + timedelta(seconds=day_seconds // 2)
    )

    outcomes = [
        await ratelimit.check_and_increment(
            db_session,
            user_id=caller.id,
            bucket="analysis_request",
            limit=limit,
            window_seconds=day_seconds,
        )
        for _ in range(limit)
    ]
    assert all(outcome.allowed for outcome in outcomes), (
        f"every one of the configured {limit} calls per day must be allowed"
    )

    refused = await ratelimit.check_and_increment(
        db_session,
        user_id=caller.id,
        bucket="analysis_request",
        limit=limit,
        window_seconds=day_seconds,
    )
    assert refused.allowed is False, "the call past the configured daily cap must be refused"
    assert refused.retry_after is not None and refused.retry_after > 0


# ================================================================================================
# `absent` vs `unavailable` vs `refused` — distinguishable from the payload alone
# ================================================================================================


async def test_absent_unavailable_and_refused_are_distinguishable_in_the_payload(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Each of the three leads the interface somewhere different: `absent` offers the analyse CTA
    (FR-030), `unavailable` must never render one (FR-034, permanent), `refused` may be retried
    later (FR-047). All three answer `200` on match-detail and (proven above) `404` on `GET
    /api/matches/{game_id}/analysis`, so the difference has to live in the payload itself, not in
    the transport."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    absent_game_id = _DISTINGUISH_ABSENT_GAME_ID
    await _seed_two_participant_match(db_session, game_id=absent_game_id)

    unavailable_game_id = _DISTINGUISH_UNAVAILABLE_GAME_ID
    await _seed_two_participant_match(db_session, game_id=unavailable_game_id)
    await _seed_analysis(
        db_session,
        game_id=unavailable_game_id,
        state=MatchAnalysisState.UNAVAILABLE,
        point_of_view_profile_id=_PARTICIPANT_A,
    )

    refused_game_id = _DISTINGUISH_REFUSED_GAME_ID
    await _seed_two_participant_match(db_session, game_id=refused_game_id)
    await _seed_analysis(
        db_session,
        game_id=refused_game_id,
        state=MatchAnalysisState.REFUSED,
        point_of_view_profile_id=_PARTICIPANT_A,
    )

    absent_response = client.get(f"/api/matches/{absent_game_id}")
    unavailable_response = client.get(f"/api/matches/{unavailable_game_id}")
    refused_response = client.get(f"/api/matches/{refused_game_id}")

    for response in (absent_response, unavailable_response, refused_response):
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        _assert_no_index(response)

    absent_analysis = absent_response.json()["analysis"]
    unavailable_analysis = unavailable_response.json()["analysis"]
    refused_analysis = refused_response.json()["analysis"]

    states = {absent_analysis["state"], unavailable_analysis["state"], refused_analysis["state"]}
    assert states == {"absent", "unavailable", "refused"}, (
        f"the three states must be pairwise distinct in the payload — got {states}"
    )
    assert absent_analysis["reason"] is None, (
        "absent means never requested — there is nothing yet to explain"
    )
    assert unavailable_analysis["reason"], "FR-034: unavailable must carry a reason"
    assert refused_analysis["reason"], "FR-047: refused must carry a reason"
    assert unavailable_analysis["reason"] != refused_analysis["reason"], (
        "the two reasons describe different failures and must read differently, since one leads "
        "the interface to render no action at all (FR-034) while the other may be retried later "
        "(FR-047)"
    )
