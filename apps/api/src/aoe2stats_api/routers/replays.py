"""The replays router (T062, T071): `GET /api/replays/status?profile_id=` and
`GET /api/replays/{game_id}/download`.

`contracts/http-api.md`: "Counts per status, oldest pending, nearest deadline" — a dashboard-level
summary of one profile's capture backlog, distinct from the per-match archival state `GET
/api/matches` will carry per row (FR-027, T065's own note that this endpoint is the one exception
in US3 that reaches back into US2).

**Ownership follows `profiles.py`'s `_owned_active_link` convention, adapted to a query parameter.**
`profile_id` here names the profile whose backlog is being read rather than the one being mutated,
but FR-045's "one error, indistinguishable causes" applies just the same: a `profile_id` that names
no active link, an unlinked one, or one belonging to someone else all answer the identical 404 —
see `profiles.py`'s module docstring for why a differentiated answer would itself be the leak.
This module keeps its own copy of the session-resolution helpers rather than importing
`profiles.py`'s, matching `auth.py`'s, `privacy.py`'s and `profiles.py`'s own precedent: each
router in this feature is a self-contained file (`app.py`'s docstring — "never a change to this
module's structure").

**`oldest_pending` and `nearest_deadline` are both scoped to `status = 'pending'`.** `pending` is
the only status still racing the clock: `downloading` is a claim held for the duration of a single
run (data-model.md), and `stored`, `unavailable`, `expired`, `quarantined` and `failed` are all
terminal — read the state table's "Retried?" column. Ordering by `capture_deadline_at ASC` among
`pending` rows is exactly the claiming query's own `ORDER BY` (data-model.md: "the single most
consequential line in the schema"), so `nearest_deadline` names the row a run would claim first
under a backlog. `oldest_pending` orders by `first_seen_at ASC` instead — how long a capture has
sat undiscovered-but-known — which is a different question from "how soon does it expire" and is
not always the same row: a backfilled older match can be *discovered* later than a fresh one while
still carrying an earlier `capture_deadline_at`, or vice versa.

**Counts cover every `CaptureStatus` value, zero-filled.** A profile with, say, no `quarantined`
captures still gets `"quarantined": 0` rather than an absent key, so a client can read every field
without first checking it exists — the same reasoning `_status_counts` below applies is why
`profiles.py`'s rating list is built from a `dict.get(..., [])` rather than requiring the caller to
handle a missing leaderboard entry.

**`GET /api/replays/{game_id}/download` (T071, FR-028, FR-038, FR-040, FR-045).** The bucket is
never public (constitution IV, `ObjectStore`'s own docstring): the only path a caller ever reaches
is a freshly signed, short-expiry `ObjectStore.signed_get_url` — never a hand-built bucket URL —
and every successful download writes one `replay_access_log` row (FR-040). Ownership is resolved
the same way `_owned_active_link` resolves it above, except the row being reached for is a
`replay_captures` one addressed by `(game_id, profile_id)` rather than a `profile_links` one
addressed by `profile_id` alone: `_stored_capture_for_caller` joins `replay_captures` to the
caller's own active `profile_links` rows, so a `game_id` that names no match, a match the caller
did not play, or a match whose replay is not yet `stored` all answer the identical `not_found`
FR-045 requires (module docstring, `profiles.py`'s own note on why a differentiated answer would
itself be the leak — here, whether the match exists at all). Never a 403: that would already
disclose the match exists. A refusal is not an access and writes nothing to `replay_access_log`.

**`GET /api/matches/{game_id}/replay/{profile_id}` (T337, 003) — a different route from the one
above.** 001's route above is the caller's own dashboard download, reached by `game_id` alone; this
one is reachable for *any* participant's point of view of *any* match this service holds,
`profile_id` named explicitly (FR-023, US3, `contracts/http-api.md`'s "Recorded games, per point of
view"). `apps/api/tests/test_replay_download.py`'s `T335`-authored section is this route's own
specification; `specs/003-player-search-match-analysis/research.md` R8 is the state derivation it
implements to, through `availability.py`'s `derive_availability` (T336) — this router never
re-derives the four states itself.

**`profile_id` must itself be a recorded participant of `game_id`, checked before any state is
derived.** FR-023 is "one download per participant point of view" — the *participant* half of that
is enforced here, in `_match_completed_at_for_participant`; the *caller* half (does the signed-in
user own the point of view being served) is a separate question, answered only for the `archived`
branch below, where FR-026 requires it. `_match_completed_at_for_participant` answers the identical
`not_found` FR-045 requires for "no such match" for this case too, by joining `match_players` in
the same query rather than checking existence and participation separately — a caller cannot tell
"there is no such match" from "`profile_id` never played it", the same indistinguishability FR-045
already requires of ownership. This check runs *after* the rate limit below, not before it:
`check_and_increment`'s own contract is that the limit bounds *any* call this route receives,
valid pair or not, and an invalid-pair probe is itself part of the enumeration FR-028 exists to
stop — running the participation check first would let exactly that probing through uncounted. It
runs before every other query this route makes, so an invalid pair costs nothing beyond the one
query that proves it invalid: no capture lookup, no fetch-miss lookup, and — the case that matters
most, since it was reaching the source before this fix — no outbound call to `aoe.ms`.

Per-state behaviour (`contracts/http-api.md`):

- `archived` — `derive_availability` itself answers this from a `replay_captures` row in `stored`
  regardless of who owns it (FR-026's "own point of view" is not a parameter `derive_availability`
  takes — module docstring, `availability.py`); this router is what applies FR-026's ownership
  requirement, and it does so *before* that row ever reaches `derive_availability`.
  `_capture_for_point_of_view` filters *any* row the caller does not own out to `None` (B1
  remediation, widened at M12 — its own docstring), so `derive_availability` falls through to the
  ordinary age comparison for it instead — `archived` therefore cannot be reached here for a
  capture the caller does not own, and the `assert caller_owns_profile` in this branch below exists
  only to fail loudly if that ever stops being true. FR-026 is explicit that `archived` is "the
  caller's own captured replay, and only that", and `test_no_public_directory.py`'s own property-4
  test seeds a *stranger's* `stored` capture, old enough that the source has long since lost it
  too, and still requires a `404 not_found` — never `expired`, which would itself disclose that an
  archive exists for someone else's account. A caller who owns it gets the identical
  302-to-a-signed-URL-and-log shape 001's own route above already implements.
- `obtainable` — fetched from the source and returned to the caller as a plain response body,
  **never through `ObjectStore.put`** (FR-027, asserted directly against a tracking fake in
  `test_replay_download.py`: downloading is not analysing, and constitution IX permits retention
  only where a person deliberately asks for a match to be analysed).
- `expired`, `never_recorded` — `404` with the distinguishing `code`, no fetch attempted at all
  (`derive_availability` already decided this from rows and a clock — R8's whole point).

**The boundary race (FR-025, R8) needed a table of its own, `replay_fetch_misses` — see
`ReplayFetchMiss`'s docstring in `packages/storage/src/aoe2stats_storage/models.py` for why
`replay_captures` was the tempting answer and the wrong one.** In short: that table's automatic
capture pipeline claims from it with no ownership filter at all
(`apps/ingester/.../capture.py::_claim_batch`), so any row this route wrote there would either have
that pipeline fetch and *store* a third party's recording as a direct consequence of a download
click (a `pending` row — forbidden by FR-012 and FR-027) or permanently block the real capture that
pipeline owes that profile's owner if they later link an account (any terminal status —
`discover.py`'s `_enqueue_capture` no-ops on `ON CONFLICT DO NOTHING` against a row that already
exists). `replay_fetch_misses` is read-only evidence with none of `replay_captures`' readers:
`_has_recorded_fetch_miss` below feeds `derive_availability`'s own `recorded_404` parameter, and
`_record_fetch_miss` writes it, once, the moment a point of view offered as `obtainable` answers
404 at fetch time — so the identical next request reads `never_recorded` from the row instead of
probing the source a second time. **`data-model.md` now names this table explicitly as the
sixth (amended 2026-08-29, carrying its own section) — this table is no longer an
undocumented gap between the code and the artifact.**

**Every write this route makes mid-request, after other work has already happened on `db_session`,
answers to its own short-lived session instead, never `db_session`** (`_audit_session` below) —
`deps.py`'s `session_scope` rolls the whole request's transaction back the moment any exception
(including `APIError`) propagates. Three of this route's writes go through it, for the identical
reason: each only ever runs on a path that already ends in an error and would otherwise be
discarded along with it. The `rate_limited` alert (FR-028's second half) precedes a `429`, the
fetch-miss row precedes a `404`, and the `provider_calls` row (`_aoems_call_sink`) is written
mid-fetch, before either outcome is known. Mirrors `routers/players.py`'s `_relic_call_sink`, which
the same reasoning already governs there.

The rate-limit counter itself (`_apply_replay_download_rate_limit`) needs the identical durability
but gets it a different way, on `db_session` directly (M11 remediation, 2026-08-29): `check_and_
increment`'s own docstring is explicit that it does not commit and leaves that to its caller, and
every refusal this route raises is an `APIError` — `not_found`, `never_recorded`, `expired`, the
source's own `429`, `expired_since_page_load`, and the limiter's own `429` below. Before this was
first fixed, the caller deciding when that increment became durable was `db_session`, so `session_
scope` rolled it back on every one of those paths and left only the two success shapes (`archived`'s
302, `obtainable`'s 200) actually metered — the boundary-race path in particular kept making a real
outbound call to `aoe.ms` while its own accounting was discarded, unmetered third-party traffic
driven by user input (constitution I). `_apply_replay_download_rate_limit` now commits its own
increment on `db_session` itself, immediately, as the very first thing this route does inside its
`try` block — before any other read or write on `db_session` that a later rollback would need to
undo — so it survives every outcome rather than only the ones that end well, at the cost of zero
extra database connections rather than one per call. It ran through `_audit_session` briefly
between these two fixes; that traded a correctness bug (the increment discarded) for a cost one
(a second Neon connection, concurrent with `db_session`'s own, on every single call to this route —
a free-tier hosting concern, `docs/adr/0002-hosting.md`) rather than eliminating it, which
`_apply_replay_download_rate_limit`'s own docstring now explains in full.

**The rate limit (FR-028's first half, R10) applies before anything else this route does**, in its
own `replay_download` bucket (`data-model.md`'s `rate_limit_counters` section) — `contracts/
http-api.md` states it applies to the whole route, not only the `obtainable` branch.
`test_replay_download_rate_limit_applies_on_a_refused_path` exhausts it against a caller's own
`expired` point of view — a refusal that makes no outbound call at all — to prove the limit reaches
every refusal, not only a success. `test_boundary_race_path_still_consumes_the_rate_limit` proves
the one refusal that *does* make a real outbound call is metered too, the case that actually
matters. `test_replay_download_rate_limit_applies_per_user` is the contrast case: a caller's own
successful `archived` download still counts, so the fix above did not simply move the accounting
from the refusal paths onto the success ones.

**A failure of `GET /api/matches/{game_id}/replay/{profile_id}` answers a `303` back to the match
page, for a browser navigation only** — decided 2026-08-29, replacing a first fix that deferred a
client-side refetch instead and did not work: a same-tab navigation (`replay-availability.md` §10,
`apps/web/src/features/replays/api.ts`'s `triggerReplayPointOfViewDownload`) that lands on a plain
JSON error body destroys the SPA before any client code — including a `setTimeout` already
scheduled — runs again, which is exactly what every failure response from this route used to do.
`_is_browser_navigation` below tells that case apart from an API caller (this suite's own
`TestClient` calls, which carry neither signal) using the Fetch Metadata `Sec-Fetch-Mode: navigate`
header every current browser engine sends on a top-level navigation and never on a script-initiated
`fetch`, with `Accept: text/html` as the fallback for a request that omits it. `_replay_not_found`,
`_never_recorded_error`, `_expired_error`, `_expired_since_page_load_error`, `_source_unavailable_
error` (B3 remediation, third-round review — see its own docstring) and the rate-limited `429`s
(this route's own limiter and the source's) all still raise the identical `APIError` an API caller
gets as JSON; `download_replay_point_of_view` below is what translates that same error into a `303`
for a browser instead of letting it become the response body. The `303` carries the failing `code`
(and `retry_after`, where the error has one) as query parameters on the match page's own URL, which
`apps/web`'s `MatchDetailContainer` reads once on load and clears (`replay-availability.md` §5).
**Rooted at `settings.public_base_url`, absolute, never a relative `/matches/{game_id}`**
(B1/B2 remediation, 2026-08-29, `_match_page_redirect_for_download_failure`'s own docstring): a
relative redirect only ever worked because `vercel.json`'s `/api/(.*)` rewrite collapses the API
and the SPA onto one origin in production, and this repository's own documented local topology
(`.env.example`) already puts them on two — the object-store signed URL redirect's own CORS
problem does not arise here regardless, since the browser is never asked to read this response's
body across an origin, only to follow the `Location` header, exactly as it already follows any
other cross-origin redirect a top-level navigation reaches.

**B3 (third-round review): a source 5xx, timeout, or non-200/404 status also went straight to a
raw JSON `500`, browser navigation or not — the one `except` clause here caught
`ProviderRateLimited` only, and `AsyncBaseProvider._request`/`AoemsReplayProvider.fetch_replay`
raise `ProviderUnavailable` (and its `ProviderMoved` subtype) for every one of those, never that.**
A second `except ProviderUnavailable` clause below now turns it into `_source_unavailable_error()`
— `502`, `source_unavailable` — the identical `APIError` shape every other refusal on this route
already is, so it is caught by the outer `except APIError` exactly like the rest and reaches a
browser navigation as the same `303` this section already describes. No `replay_fetch_misses` row
is written on this path (`_source_unavailable_error`'s own docstring): a source failure is not
evidence the recording never existed.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from aoe2stats_api import security
from aoe2stats_api.availability import Availability, derive_availability
from aoe2stats_api.deps import ObjectStoreDep, SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.ratelimit import check_and_increment
from aoe2stats_api.settings import Settings
from aoe2stats_core.alerting import AlertRecord
from aoe2stats_ingester.ratelimit import (
    build_aoems_rate_limiter,
    build_aoems_retry_policy,
    raise_rate_limited_alert,
)
from aoe2stats_providers.aoems.provider import AoemsReplayProvider
from aoe2stats_providers.base import (
    NotFound,
    ProviderCallRecord,
    ProviderRateLimited,
    ProviderUnavailable,
)
from aoe2stats_providers.wiring import build_async_client_resources
from aoe2stats_storage.models import (
    Alert,
    CaptureStatus,
    Match,
    MatchPlayer,
    ProfileLink,
    ProviderCall,
    ReplayAccessLog,
    ReplayCapture,
    ReplayFetchMiss,
)
from aoe2stats_storage.models import Session as SessionRow

router = APIRouter(tags=["replays"])

#: `.env.example`'s own tuned `AOEMS_MAX_REQUESTS_PER_SECOND` default (`1`) — "at most 1 request
#: per second to the replay endpoint, serially" (skill `aoe2-data-sources`), the identical policy
#: `apps/ingester/src/aoe2stats_ingester/ratelimit.py::build_aoems_rate_limiter` enforces for the
#: ingester's own process. A hardcoded constant rather than read from `settings`, mirroring
#: `routers/players.py`'s own `_RELIC_RATE_PER_SECOND`/`_COMPANION_RATE_PER_SECOND`: no router in
#: this codebase reads `get_settings()` at module scope.
_AOEMS_RATE_PER_SECOND = 1.0

#: Interactive, on-demand traffic, not the ingester's own daily bulk cycle — mirrors
#: `_PROVIDER_TIMEOUT_SECONDS` in `routers/auth.py`/`routers/players.py`.
_AOEMS_PROVIDER_TIMEOUT_SECONDS = 10.0

#: Built once per process, held for its lifetime (module docstring's "Every write ..." note and
#: `routers/players.py`'s identical precedent for Relic/Companion). `build_async_client_resources`
#: is used only for the `httpx.AsyncClient` half — `apps/api` may not `import httpx` itself
#: (`tests/architecture/test_import_graph.py`, constitution III) — its own generic `TokenBucket` is
#: discarded in favour of `build_aoems_rate_limiter`'s serial-capacity-of-one policy, the one this
#: endpoint actually needs.
_AOEMS_HTTP_CLIENT, _ = build_async_client_resources(_AOEMS_RATE_PER_SECOND)
_AOEMS_RATE_LIMITER = build_aoems_rate_limiter(_AOEMS_RATE_PER_SECOND)
_AOEMS_RETRY_POLICY = build_aoems_retry_policy()

#: FR-028's own bucket name (`data-model.md`'s `rate_limit_counters` section) and the fixed window
#: "per minute" names — the same structural-constant footing `routers/players.py`'s
#: `_SEARCH_RATE_LIMIT_BUCKET`/`_SEARCH_RATE_LIMIT_WINDOW_SECONDS` stand on.
_REPLAY_DOWNLOAD_RATE_LIMIT_BUCKET = "replay_download"
_REPLAY_DOWNLOAD_RATE_LIMIT_WINDOW_SECONDS = 60


# --- Session resolution, the same discipline `auth.py`, `privacy.py` and `profiles.py` already
# establish (module docstring) -------------------------------------------------------------------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — mirrors `profiles.py`'s own helper of the same name and shape."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to view your replay capture status.",
        )
    return session_row


def _profile_not_found() -> APIError:
    """FR-045: the one answer for "no such active link", whatever the underlying reason — see the
    module docstring and `profiles.py`'s own `_profile_not_found`."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No linked profile was found for that id.",
    )


async def _owned_active_link(
    db_session: AsyncSession, *, profile_id: int, user_id: Any
) -> ProfileLink:
    """The caller's own active `profile_links` row for `profile_id`, or the single `not_found`
    error FR-045 requires for every other case (module docstring)."""
    result = await db_session.execute(
        select(ProfileLink).where(
            ProfileLink.profile_id == profile_id, ProfileLink.unlinked_at.is_(None)
        )
    )
    link = result.scalar_one_or_none()
    if link is None or link.user_id != user_id:
        raise _profile_not_found()
    return link


# --- GET /api/replays/status ----------------------------------------------------------------------


async def _status_counts(db_session: AsyncSession, profile_id: int) -> dict[str, int]:
    """Every `CaptureStatus` value, zero-filled (module docstring), for `profile_id`."""
    result = await db_session.execute(
        select(ReplayCapture.status, func.count())
        .where(ReplayCapture.profile_id == profile_id)
        .group_by(ReplayCapture.status)
    )
    counts = {status.value: 0 for status in CaptureStatus}
    for status, count in result.all():
        counts[status.value] = int(count)
    return counts


async def _oldest_pending(db_session: AsyncSession, profile_id: int) -> ReplayCapture | None:
    """The `pending` capture that has sat undiscovered-but-known longest, or `None` if there is
    none (module docstring)."""
    result = await db_session.execute(
        select(ReplayCapture)
        .where(
            ReplayCapture.profile_id == profile_id,
            ReplayCapture.status == CaptureStatus.PENDING,
        )
        .order_by(ReplayCapture.first_seen_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _nearest_deadline(db_session: AsyncSession, profile_id: int) -> ReplayCapture | None:
    """The `pending` capture the claiming query would fetch first under a backlog — the same
    `ORDER BY capture_deadline_at ASC` data-model.md fixes for that query (module docstring)."""
    result = await db_session.execute(
        select(ReplayCapture)
        .where(
            ReplayCapture.profile_id == profile_id,
            ReplayCapture.status == CaptureStatus.PENDING,
        )
        .order_by(ReplayCapture.capture_deadline_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _capture_summary(capture: ReplayCapture, *, with_first_seen_at: bool) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "game_id": capture.game_id,
        "capture_deadline_at": capture.capture_deadline_at.isoformat(),
    }
    if with_first_seen_at:
        summary["first_seen_at"] = capture.first_seen_at.isoformat()
    return summary


@router.get("/replays/status")
async def replay_status(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-027 / SC-010 support, at the profile level: counts per capture status, the oldest still
    pending, and the nearest deadline among those still pending (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    await _owned_active_link(db_session, profile_id=profile_id, user_id=session_row.user_id)

    counts = await _status_counts(db_session, profile_id)
    oldest_pending = await _oldest_pending(db_session, profile_id)
    nearest_deadline = await _nearest_deadline(db_session, profile_id)

    return {
        "counts": counts,
        "oldest_pending": (
            _capture_summary(oldest_pending, with_first_seen_at=True)
            if oldest_pending is not None
            else None
        ),
        "nearest_deadline": (
            _capture_summary(nearest_deadline, with_first_seen_at=False)
            if nearest_deadline is not None
            else None
        ),
    }


# --- GET /api/replays/{game_id}/download -----------------------------------------------------


def _replay_not_found() -> APIError:
    """FR-045: the identical `not_found` answer, whatever the underlying reason — no such match,
    a match the caller did not play, or a replay not yet `stored` (module docstring). Never a
    403, which would itself disclose that the match exists."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No archived replay was found for that match.",
    )


async def _stored_capture_for_caller(
    db_session: AsyncSession, *, game_id: int, user_id: Any
) -> tuple[ReplayCapture, str]:
    """The caller's own `stored` capture for `game_id`, joined through their active
    `profile_links` rows, and its `object_key` narrowed to `str` — or the single `not_found`
    error FR-045 requires for every other case (module docstring)."""
    result = await db_session.execute(
        select(ReplayCapture)
        .join(ProfileLink, ProfileLink.profile_id == ReplayCapture.profile_id)
        .where(
            ReplayCapture.game_id == game_id,
            ReplayCapture.status == CaptureStatus.STORED,
            ProfileLink.user_id == user_id,
            ProfileLink.unlinked_at.is_(None),
        )
    )
    capture = result.scalars().first()
    if capture is None or capture.object_key is None:
        raise _replay_not_found()
    return capture, capture.object_key


@router.get("/replays/{game_id}/download")
async def download_replay(
    game_id: int,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    object_store: ObjectStoreDep,
) -> RedirectResponse:
    """FR-028, FR-038, FR-040, FR-045 (module docstring): a 302 to a freshly signed, short-expiry
    URL for the caller's own archived replay from `game_id`, logging the access. The signed URL
    always comes from `ObjectStore.signed_get_url` — the bucket is never public — and a refusal
    writes nothing to `replay_access_log`, since it is not an access."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    capture, object_key = await _stored_capture_for_caller(
        db_session, game_id=game_id, user_id=session_row.user_id
    )

    signed_url = await object_store.signed_get_url(object_key)

    db_session.add(
        ReplayAccessLog(
            replay_capture_id=capture.id,
            user_id=session_row.user_id,
            purpose="download",
        )
    )

    return RedirectResponse(url=signed_url, status_code=302)


# --- GET /api/matches/{game_id}/replay/{profile_id} (T337, 003) ------------------------------


def _audit_session(db_session: AsyncSession) -> AsyncSession:
    """A session bound to the same engine as `db_session`, independent of its transaction —
    mirrors `routers/players.py`'s `_relic_call_sink` exactly (module docstring's "Every write ..."
    note). Used as `async with _audit_session(db_session) as audit_session: ...`; every write this
    route makes that precedes a `raise APIError(...)` goes through this, never `db_session` itself,
    because `deps.py`'s `session_scope` rolls `db_session`'s own transaction back the moment that
    exception propagates."""
    bind = db_session.get_bind()
    assert isinstance(bind, Engine), f"expected an Engine bind, got {type(bind)}"
    return AsyncSession(bind=AsyncEngine(bind))


async def _match_completed_at_for_participant(
    db_session: AsyncSession, *, game_id: int, profile_id: int
) -> datetime:
    """`Match.completed_at` for `game_id`, but only once `profile_id` is confirmed as a recorded
    participant of it — FR-023's "one download per participant point of view", the participant half
    (module docstring's own paragraph on this). Joins `match_players` in the same query as the
    match lookup, rather than checking existence and participation separately, which is what makes
    "no such match" and "profile_id never played it" answer the identical `not_found` FR-045
    requires for free: there is exactly one query and one branch, so there is nothing for a second
    branch to drift out of sync with (`_replay_not_found`'s own reasoning). Without this join,
    `profile_id` never needed to have played `game_id` at all: any `aoe_profiles` row — or, worse,
    an unknown one, see `_record_fetch_miss`'s foreign key — would fall through to `obtainable` for
    a pair `docs/data-sources.md` documents the source as never meaningfully answering for."""
    result = await db_session.execute(
        select(Match.completed_at)
        .join(MatchPlayer, MatchPlayer.game_id == Match.game_id)
        .where(Match.game_id == game_id, MatchPlayer.profile_id == profile_id)
    )
    completed_at = result.scalar_one_or_none()
    if completed_at is None:
        raise _replay_not_found()
    return completed_at


async def _capture_for_point_of_view(
    db_session: AsyncSession, *, game_id: int, profile_id: int, caller_owns_profile: bool
) -> ReplayCapture | None:
    """The `replay_captures` row for this exact `(game_id, profile_id)` pair — but *any* row the
    caller does not own is treated as if it did not exist, mirroring `routers/matches.py`'s own
    `_replay_by_profile`, which excludes exactly this same shape from `capture_by_profile` before
    `derive_availability` ever sees it. `derive_availability` (T336) then falls through to the
    ordinary age comparison for that pair instead of reading anything off a row that belongs to
    someone else, since FR-026 is "the caller's own captured replay, and only that" — never
    "whoever it belongs to".

    Before this fix (B1), this function returned the row regardless of ownership and left the check
    to the `archived` branch below, which produced two violations at once: a stranger's `stored`
    capture made `derive_availability` answer `archived` while the identical point of view with no
    capture at all answered `obtainable`, so a caller who clicked the `obtainable` button the match
    page (`routers/matches.py`, already ownership-filtered) had offered them landed here and got
    `not_found` instead of a fetch (FR-025's "MUST NOT present an unobtainable download as an
    action that then fails"); and, independently, `not_found` for that one pair shape became an
    account-existence oracle (FR-045) — the identical `(game_id, profile_id)` answers `not_found`
    only when a stranger's account happens to hold a `stored` capture for it, `expired`/
    `expired_since_page_load`/`200` otherwise. Filtering here removes the second query this route
    used to answer differently from the first, rather than reconciling the two.

    **Widened past `stored` alone (M12, third-round review).** B1's filter checked
    `capture.status is CaptureStatus.STORED` explicitly, leaving `unavailable` unfiltered:
    `derive_availability` also reads `unavailable` on its own (`availability.py`'s own table,
    `never_recorded`), so a stranger's `unavailable` capture for a recent match answered
    `never_recorded` while the identical pair with no capture at all answered `obtainable` — the
    same shape of asymmetry B1 closed, one status short of complete, and observable as a timing
    difference too (no outbound call in the `unavailable` case). Every other `CaptureStatus` value
    (`pending`, `downloading`, `failed`, `quarantined`, `expired`) is already unreadable by
    `derive_availability` regardless of ownership — it only branches on `stored` and `unavailable` —
    so filtering by ownership alone, rather than re-deriving which statuses currently matter, is not
    a behaviour change for those five: it costs nothing today and, unlike enumerating the two
    statuses that happen to matter now, does not quietly reopen this exact finding the next time
    `derive_availability` learns to read a third one. The predicate is now the simplest one that is
    still correct: *any* row the caller does not own reads as absent, full stop."""
    result = await db_session.execute(
        select(ReplayCapture).where(
            ReplayCapture.game_id == game_id, ReplayCapture.profile_id == profile_id
        )
    )
    capture = result.scalar_one_or_none()
    if capture is not None and not caller_owns_profile:
        return None
    return capture


async def _caller_owns_profile(db_session: AsyncSession, *, profile_id: int, user_id: Any) -> bool:
    """Whether `user_id` holds an active `profile_links` row for `profile_id` — the ownership test
    FR-026 requires before an `archived` point of view may be served (module docstring). Called
    once, before `_capture_for_point_of_view`, so a stranger's `stored` capture is filtered out of
    `capture` before `derive_availability` ever runs, rather than checked only after `derive_
    availability` has already answered `archived` for it (B1 remediation)."""
    result = await db_session.execute(
        select(ProfileLink.profile_id).where(
            ProfileLink.profile_id == profile_id,
            ProfileLink.user_id == user_id,
            ProfileLink.unlinked_at.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


async def _has_recorded_fetch_miss(
    db_session: AsyncSession, *, game_id: int, profile_id: int
) -> bool:
    """Whether `replay_fetch_misses` already carries evidence for this exact point of view —
    `derive_availability`'s own `recorded_404` parameter (module docstring, `ReplayFetchMiss`'s
    docstring in `models.py`)."""
    result = await db_session.execute(
        select(ReplayFetchMiss.game_id).where(
            ReplayFetchMiss.game_id == game_id, ReplayFetchMiss.profile_id == profile_id
        )
    )
    return result.scalar_one_or_none() is not None


async def _record_fetch_miss(db_session: AsyncSession, *, game_id: int, profile_id: int) -> None:
    """Persists the boundary-race evidence on its own short-lived session (`_audit_session`),
    since this call always precedes an `expired_since_page_load` `404` (module docstring).
    `ON CONFLICT DO NOTHING` on the primary key: two callers racing the same boundary each try to
    record the same fact, and the first one wins with no error for the second."""
    async with _audit_session(db_session) as audit_session:
        statement = (
            pg_insert(ReplayFetchMiss)
            .values(game_id=game_id, profile_id=profile_id)
            .on_conflict_do_nothing(
                index_elements=[ReplayFetchMiss.game_id, ReplayFetchMiss.profile_id]
            )
        )
        await audit_session.execute(statement)
        await audit_session.commit()


def _never_recorded_error() -> APIError:
    return APIError(
        status_code=404,
        code="never_recorded",
        message="This game does not appear to have been recorded.",
    )


def _expired_error() -> APIError:
    return APIError(
        status_code=404,
        code="expired",
        message="This recording is past the source's retention window.",
    )


def _expired_since_page_load_error() -> APIError:
    return APIError(
        status_code=404,
        code="expired_since_page_load",
        message="This recording expired between page load and this request.",
    )


def _source_rate_limited_error() -> APIError:
    return APIError(
        status_code=429,
        code="rate_limited",
        message="The replay source is throttling requests. Try again later.",
    )


def _source_unavailable_error() -> APIError:
    """B3 remediation, third-round review: `AsyncBaseProvider._request` raises
    `ProviderUnavailable` for a 5xx that outlives the retry budget or a timeout, and
    `AoemsReplayProvider.fetch_replay` raises it (via its `ProviderMoved` subtype, or directly for
    an unnamed status — see that module's own docstring) for a residual 3xx or any status this
    endpoint has never been measured to send as a terminal answer, including the ordinary case
    left live by the 2026-08-28 `aoe.ms` -> `api.ageofempires.com` move. Before this fix, none of
    those was an `APIError`, so none was caught here: they fell to `app.py`'s generic
    `@app.exception_handler(Exception)` and became a bare `500`, which for a browser navigation
    means the exact raw-JSON stranding the `303` remediation above exists to eliminate, on the
    third-party failure most likely to actually occur.

    `502`, not `404`/`429`: this is not evidence the recording never existed (`never_recorded`
    would say that) and it is not this route's or the source's own rate limit (`rate_limited`
    already names that) — it is the upstream itself failing to answer at all, which is what a
    Bad Gateway means for a service that proxies a third party's bytes through. `source_unavailable`
    is a new, stable `code` (`contracts/http-api.md`'s "Error codes this feature adds" table),
    chosen to match the client's own reading of it rather than invented independently.

    No `replay_fetch_misses` row is written for this path, unlike the boundary-race 404 branch
    below: a source failure says nothing about whether the recording exists, so it must never be
    read later as evidence that it does not (module docstring's own reasoning for why that table
    exists at all)."""
    return APIError(
        status_code=502,
        code="source_unavailable",
        message="The replay source is temporarily unavailable. Try again later.",
    )


def _aoems_call_sink(db_session: AsyncSession) -> Callable[[ProviderCallRecord], Awaitable[None]]:
    """Writes a `provider_calls` row on its own short-lived session (`_audit_session`), never
    `db_session` — mirrors `routers/players.py`'s `_relic_call_sink` exactly, and for the
    identical reason: `AoemsReplayProvider.fetch_replay` can raise `ProviderRateLimited` mid-call,
    and `deps.py`'s `session_scope` would roll a row added to `db_session` back along with it."""

    async def _sink(record: ProviderCallRecord) -> None:
        async with _audit_session(db_session) as audit_session:
            audit_session.add(
                ProviderCall(
                    provider=record.provider,
                    endpoint=record.endpoint,
                    status_code=record.status_code,
                    duration_ms=record.duration_ms,
                    called_at=record.called_at,
                    rate_limited=record.rate_limited,
                )
            )
            await audit_session.commit()

    return _sink


def _build_replay_provider(db_session: AsyncSession) -> AoemsReplayProvider:
    return AoemsReplayProvider(
        client=_AOEMS_HTTP_CLIENT,
        timeout_seconds=_AOEMS_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_AOEMS_RATE_LIMITER,
        call_sink=_aoems_call_sink(db_session),
        retry_policy=_AOEMS_RETRY_POLICY,
    )


class _RequestAlertSink:
    """The `AlertSink` (`aoe2stats_core.alerting`) `raise_rate_limited_alert` writes through, on
    its own short-lived session (`_audit_session`) rather than `db_session` — this route only ever
    raises this alert on a path that ends in `429` (module docstring), which `deps.py`'s
    `session_scope` would otherwise roll back along with the alert itself. Structurally identical
    to `apps/ingester/src/aoe2stats_ingester/run.py`'s own `_AlertSink`, scoped to a request's
    engine bind instead of a `session_factory`."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: Any,
    ) -> AlertRecord:
        async with _audit_session(self._db_session) as audit_session:
            row = Alert(
                kind=kind,
                severity=severity,
                detail=dict(detail) if detail is not None else None,
                ingest_run_id=ingest_run_id,
            )
            audit_session.add(row)
            await audit_session.commit()
            await audit_session.refresh(row)
            return AlertRecord(
                id=row.id,
                kind=row.kind,
                severity=row.severity,
                detail=row.detail,
                raised_at=row.raised_at,
                ingest_run_id=row.ingest_run_id,
                acknowledged_at=row.acknowledged_at,
            )

    async def unacknowledged_severity_one(self) -> Sequence[AlertRecord]:
        raise NotImplementedError(
            "this sink only ever writes a rate_limited alert from this route; the nightly audit's "
            "own read path is apps/ingester's _AlertSink, not this one"
        )


async def _apply_replay_download_rate_limit(
    db_session: AsyncSession, *, user_id: Any, limit: int
) -> None:
    """Increments FR-028's `replay_download` counter for `user_id` and raises the `429`
    `rate_limited` error the moment this call's own increment exceeds `limit` (module docstring's
    "The rate limit ... applies before anything else" paragraph).

    Committed on `db_session` itself, immediately — **not** `_audit_session` (M11 remediation,
    2026-08-29). `check_and_increment`'s own docstring is explicit that it does not commit and
    leaves that to its caller; every refusal this route raises is an `APIError`, and `deps.py`'s
    `session_scope` rolls `db_session`'s whole transaction back the moment one propagates. Not
    committing at all here would silently discard the increment on every refusal — `not_found`,
    `never_recorded`, `expired`, the source's own `429`, `expired_since_page_load`, and this
    function's own `429` below — leaving only the two success shapes actually metered, which is
    exactly the bug this function exists to not have.

    `_audit_session` is what the other three writes below use for the identical durability need,
    but each of those runs mid-request, after other reads and writes this route has already made on
    `db_session` — opening a second, independent connection there is the only way to commit just
    that one write without also committing (or needing to roll back) everything `db_session` is
    mid-way through. This call is different: it is the very first thing `download_replay_point_of_
    view` does inside its `try` block, before any other query, so `db_session` carries nothing else
    yet to commit early. `db_session.commit()` here therefore commits only this increment — real,
    durable, survives every later rollback exactly as `_audit_session` would — for the cost of zero
    extra connections rather than one per call (`docs/adr/0002-hosting.md`: free-tier Neon, no
    connection pool of this process's own, `build_engine`'s own `NullPool`).
    `expire_on_commit=False` (`build_session_factory`) is what makes this safe: `session_row`,
    already loaded above, stays readable after this commit with no implicit re-fetch, which an
    `AsyncSession` would otherwise need an `await` for and could not get from a plain attribute
    access.
    """
    outcome = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket=_REPLAY_DOWNLOAD_RATE_LIMIT_BUCKET,
        limit=limit,
        window_seconds=_REPLAY_DOWNLOAD_RATE_LIMIT_WINDOW_SECONDS,
    )
    await db_session.commit()

    if not outcome.allowed:
        raise APIError(
            status_code=429,
            code="rate_limited",
            message="Too many replay downloads. Try again shortly.",
            detail={"retry_after": outcome.retry_after},
        )


def _is_browser_navigation(request: Request) -> bool:
    """Tells a top-level browser navigation — `apps/web`'s `triggerReplayPointOfViewDownload`
    (`api.ts`), a plain `window.location.assign` reaching this exact route — apart from a
    programmatic or API caller (module docstring's "for a browser navigation only").

    `Sec-Fetch-Mode: navigate` is the primary signal and, when present, the only one consulted:
    every current major browser engine implements the Fetch Metadata Request Headers spec and
    sets this header on a top-level navigation, and never on a script-initiated `fetch` or
    `XMLHttpRequest` — a JSON API client (`apps/web/src/lib/api.ts`'s `apiRequest`, and every
    call this suite's own `TestClient` makes) never sends it either. `Accept: text/html` is the
    fallback for the one case the primary signal cannot see: a browser, or a network layer in
    front of it, that strips or predates that header. A plain navigation still always asks for
    `text/html` first; an API client of this service never does (`apiRequest`'s own
    `Accept: application/json`, and this file's own JSON error envelope, `errors.py`).
    """
    sec_fetch_mode = request.headers.get("sec-fetch-mode")
    if sec_fetch_mode is not None:
        return sec_fetch_mode == "navigate"
    accept = request.headers.get("accept", "")
    return "text/html" in accept


def _match_page_redirect_for_download_failure(
    *, settings: Settings, game_id: int, profile_id: int, error: APIError
) -> RedirectResponse:
    """The `303` a browser navigation gets instead of `error`'s own JSON body (module docstring's
    closing paragraph) — an absolute redirect back to `{settings.public_base_url}/matches/
    {game_id}`, the same match page `apps/web/src/routes/matches.$gameId.tsx` already renders,
    carrying the failure as query parameters `MatchDetailContainer` reads once on load and then
    clears (`replay-availability.md` §5): `replay_error` is `error.code` verbatim — the identical
    string an API caller reads from the JSON envelope's own `code` field, never a restatement of it
    — `replay_error_profile_id` names which row the failure belongs to (this route is reachable for
    any participant's point of view, never only the caller's own), and
    `replay_error_retry_after` is carried only when `error.detail` has one
    (`_apply_replay_download_rate_limit`'s own `{"retry_after": ...}`) —
    `_source_rate_limited_error` raises the identical `rate_limited` code with no such figure to
    give, and the client falls back to the generic failed-request copy for that case
    (`replay-availability.md` §5's own "never a rounded or invented figure" rule, extended to
    "never an absent one either").

    **Absolute, rooted at `settings.public_base_url` — never a relative `/matches/{game_id}`
    (B2 remediation).** `PUBLIC_BASE_URL` is this service's own SPA origin (`routers/auth.py` uses
    it for every other browser redirect back to the SPA, `settings.py`'s own field), and
    `.env.example`'s documented local topology puts the API and the SPA on different origins
    (`http://localhost:5173` for the SPA, a different port for the API) — a relative redirect from
    an API route lands on the API's own origin and 404s there. It only ever worked in production
    because `vercel.json`'s `/api/(.*)` rewrite collapses the two origins into one; Phase 2
    (OVH VPS + Docker Compose, `docs/adr/0002-hosting.md`) carries no such rewrite, and nothing in
    this codebase may depend on running specifically on Vercel or specifically on a VPS
    (constitution)."""
    params: dict[str, str] = {
        "replay_error": error.code,
        "replay_error_profile_id": str(profile_id),
    }
    retry_after = error.detail.get("retry_after") if error.detail else None
    if retry_after is not None:
        params["replay_error_retry_after"] = str(retry_after)
    location = f"{settings.public_base_url}/matches/{game_id}?{urlencode(params)}"
    return RedirectResponse(url=location, status_code=303)


@router.get("/matches/{game_id}/replay/{profile_id}")
async def download_replay_point_of_view(
    game_id: int,
    profile_id: int,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    object_store: ObjectStoreDep,
) -> Response:
    """FR-023, FR-025, FR-026, FR-027, FR-028, FR-029 (module docstring): one download per
    participant point of view, of any match this service holds. `derive_availability` (T336)
    decides which of the four states applies; this route only supplies the rows it needs, checks
    participation and ownership for the states that require it, and carries out the state's own
    action.

    Every failure below still raises the identical `APIError` an API caller gets as JSON
    (`test_replay_download.py`'s existing assertions on `code` are unchanged); the `try`/`except`
    here only decides, for a browser navigation (`_is_browser_navigation`), whether that error
    becomes this response's body or a `303` back to the match page instead (module docstring's
    closing paragraph). `_require_session` above it is deliberately outside this: an
    unauthenticated visit to this route is not a scenario the match page itself can reach — every
    query it makes already requires a session — so it is out of this fix's scope and keeps
    answering JSON exactly as it always has.
    """
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    is_browser_navigation = _is_browser_navigation(request)

    try:
        await _apply_replay_download_rate_limit(
            db_session,
            user_id=session_row.user_id,
            limit=settings.replay_download_max_per_user_per_minute,
        )

        completed_at = await _match_completed_at_for_participant(
            db_session, game_id=game_id, profile_id=profile_id
        )
        caller_owns_profile = await _caller_owns_profile(
            db_session, profile_id=profile_id, user_id=session_row.user_id
        )
        capture = await _capture_for_point_of_view(
            db_session,
            game_id=game_id,
            profile_id=profile_id,
            caller_owns_profile=caller_owns_profile,
        )
        recorded_404 = await _has_recorded_fetch_miss(
            db_session, game_id=game_id, profile_id=profile_id
        )
        availability = derive_availability(
            completed_at=completed_at,
            now=datetime.now(UTC),
            capture=capture,
            recorded_404=recorded_404,
            capture_budget_days=settings.capture_budget_days,
        )

        if availability.state is Availability.ARCHIVED:
            # `caller_owns_profile` gates `_capture_for_point_of_view` above, not this branch: any
            # row the caller does not own was already filtered out of `capture` before
            # `derive_availability` ran, so `ARCHIVED` cannot be reached here for one under
            # ordinary operation. **L20 remediation (third-round review): a real, raised check, not
            # a bare `assert`.** `assert` is a no-op under `python -O`, which would turn a
            # regression in the filtering above into a stranger's replay served silently instead of
            # failing loudly — the exact failure mode this check exists to prevent cannot depend on
            # an interpreter flag nobody here controls at deploy time. `_replay_not_found()` is the
            # identical FR-045 answer `_stored_capture_for_caller` (001's own route above) already
            # gives for the equivalent anomaly (a missing `object_key` on an otherwise-matched row),
            # never a differentiated code that would itself become new evidence for FR-045's
            # "indistinguishable causes" rule.
            if capture is None or capture.object_key is None or not caller_owns_profile:
                raise _replay_not_found()
            signed_url = await object_store.signed_get_url(capture.object_key)
            db_session.add(
                ReplayAccessLog(
                    replay_capture_id=capture.id,
                    user_id=session_row.user_id,
                    purpose="download",
                )
            )
            return RedirectResponse(url=signed_url, status_code=302)

        if availability.state is Availability.NEVER_RECORDED:
            raise _never_recorded_error()

        if availability.state is Availability.EXPIRED:
            raise _expired_error()

        # Availability.OBTAINABLE: fetch from the source and stream it straight through — FR-027
        # forbids storing it (module docstring).
        provider = _build_replay_provider(db_session)
        try:
            result = await provider.fetch_replay(game_id, profile_id)
        except ProviderRateLimited as error:
            await raise_rate_limited_alert(_RequestAlertSink(db_session), error, run_id=None)
            raise _source_rate_limited_error() from error
        except ProviderUnavailable as error:
            # `ProviderMoved` is a `ProviderUnavailable` subtype (`base.py`'s own docstring) and is
            # caught here too, deliberately not ahead of this clause: this route has no separate
            # reaction to "the source moved" versus "the source is down" (`_source_unavailable_
            # error`'s own docstring).
            raise _source_unavailable_error() from error

        if isinstance(result, NotFound):
            await _record_fetch_miss(db_session, game_id=game_id, profile_id=profile_id)
            raise _expired_since_page_load_error()

        return Response(
            content=result.content,
            media_type=result.content_type,
            headers={"content-disposition": f'attachment; filename="{result.filename}"'},
        )
    except APIError as error:
        if is_browser_navigation:
            return _match_page_redirect_for_download_failure(
                settings=settings, game_id=game_id, profile_id=profile_id, error=error
            )
        raise
