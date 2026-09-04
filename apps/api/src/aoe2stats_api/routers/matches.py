"""The matches router (T070): `GET /api/matches` and `GET /api/matches/{game_id}`, per
`contracts/http-api.md`'s Matches table.

Both routes are read-only wrappers around `aoe2stats_storage.repositories.matches.
MatchesRepository` (T069), which already carries the query shape, the cursor discipline and the
"capture status travels intact" rule — see that module's own docstring for the reasoning behind
each. This router's job is narrower: resolve the session, prove ownership, translate the
repository's dataclasses into the JSON shape the contract fixes, and turn every failure into the
single error envelope.

**Civilisation names (T070c).** The repository's dataclasses carry only `civ_id` — Relic's own
`getRecentMatchHistory` never names one (`docs/data-sources.md` §1) — so every row and every
participant below also carries a `*_name` computed here, via `civilisation_name`
(`aoe2stats_api.civilizations`), the same shape `_latest_ratings_by_profile` (`profiles.py`)
already established for `leaderboard_name` (T033a): a hand-maintained id-to-name table for a
measured fact about the game has no business in a front-end component module, per `CLAUDE.md`'s
three-homes rule, so it is computed here and served, never re-derived by the client.
`packages/storage` cannot import from `apps/api` (the dependency runs the other way), which is
why this lookup lives at the router layer exactly like `leaderboard_name` did, rather than on the
repository's own dataclasses.

**Leaderboard names (T070f, corrected T410).** The same reasoning applies to `leaderboard_id`, but
the table is not `aoe2stats_api.leaderboards.leaderboard_name` — that table names
`getPersonalStat`'s own `leaderboard_id`, the id space `profiles.py` reads for
`GET /api/profiles`. The `leaderboard_id` column both routes below carry is
`RelicMatchHistoryProvider`'s `matchtype_id`
(`packages/providers/.../relic/matches.py`), a *different* id space Relic's `getRecentMatchHistory`
returns — until T410, both routes named it through the wrong table anyway, so a real `matchtype_id
6` ("1v1 Random Map") rendered as the "Leaderboard 6" fallback. Both routes below now carry a
`leaderboard_name` alongside `leaderboard_id` computed with `aoe2stats_api.match_types.
match_type_name` instead — see that module's own docstring for how the two id spaces were told
apart and how this one is named — so the client still reads one vocabulary from every route, just
the correct one for the id this column actually holds.

**FR-045 / FR-038 — one error for `list_matches`, indistinguishable causes**, the same discipline
`replays.py`'s and `profiles.py`'s own `_owned_active_link`/`_profile_not_found` pair already
establish, and this module keeps its own copy of rather than importing (`replays.py`'s own module
docstring: "each router in this feature is a self-contained file"). `GET /api/matches?profile_id=`
names one profile explicitly, so ownership is exactly `_owned_active_link`'s existing shape: no
active link for that id, an unlinked one, or one belonging to a different account all answer the
identical `not_found`.

**`GET /api/matches/{game_id}` carries no ownership scope at all (T327, FR-018/FR-021).**
`contracts/http-api.md`'s "Matches, widened" table states it plainly: "Any match this service holds
is readable by any signed-in caller." The route still requires a session — `_require_session`, the
same as every other route in this file — but, unlike `list_matches`, proves nothing about which
profiles the caller controls before answering; `MatchesRepository.get_match_detail` (T327's own
docstring) now returns `None` for exactly one reason, "no such `game_id`", which this router still
turns into one `not_found` carrying a specific, human-meaningful message — never Starlette's bare
"Not Found" a framework-level 404 for the unmatched-route fallback would otherwise coincide with
(`test_match_detail.py`'s own note on why that distinction is asserted explicitly). There is no
`?from_profile_id=` parameter on this route and none may be added: a parameter that could change
the presentation is one that eventually will (FR-021), and `test_match_detail.py`'s own "identical
whichever history it is reached from" assertion is what a per-caller presentation would break.
`_owned_profile_ids` is still called here, but only to resolve FR-022's own archival state — never
to decide whether the caller may see the match at all.

**Capture state travels to the client unmodified.** Per `MatchesRepository`'s own docstring and
T073's note (quoted in `test_capture_visibility.py`), the collapse of `unavailable` / `expired` /
`failed` into the badge's single "lost" state, and of `pending` / `downloading` into "still
catchable", belongs to the design-system component (T073/T074), never to this router. Every row
below carries the raw `CaptureStatus` value verbatim, including all three statuses behind "lost"
and `quarantined`, which FR-026 keeps out of both the archived and the lost columns — both
`match_row_json` and `_match_detail_json` carry the identical `capture_status`/
`capture_deadline_at` pair (T070e, FR-027: per match, not only per list), so the client reads one
vocabulary from either route rather than two.

**Cursor validation.** `MatchesRepository._decode_cursor` raises `ValueError` for any cursor this
repository did not itself issue — malformed, tampered, or built for a different shape — which this
router turns into the same `422`/`validation_error` FastAPI's own query-parameter validation
already answers with for a missing `profile_id`, rather than letting it fall through to the
generic `internal_error` handler.

**The per-participant `replay` object (T338, FR-023).** `derive_availability` (`availability.py`,
T336) is a pure function over rows and a clock; this router is what supplies those rows for every
participant of `game_id` at once — `_replay_by_profile` below issues exactly two queries scoped to
the whole match (one over `replay_captures`, one over `replay_fetch_misses`), never one per
participant, because this route answers with every participant already and a query per row would
be exactly the N+1 the task text warns against. `_replay_json` then turns each `AvailabilityView`
into the wire shape `contracts/http-api.md` fixes, with `download_path` `None` for the two states
FR-025 forbids offering as an action — `expired` and `never_recorded` — and pointing at
`replays.py`'s `GET /api/matches/{game_id}/replay/{profile_id}` (T337) for the two that are.
`obtainable_until` is carried through from `derive_availability` unmodified: it is already `None`
in every state (FR-024, amended 2026-08-29 — see `availability.py`'s own module docstring), so no
date arithmetic happens here either.

**Ownership still gates `archived`, inside this response, not only at the download route
(remediation, FR-026).** `contracts/http-api.md`'s `archived` state is "the caller's own captured
replay, and **only** that" — a `stored` `replay_captures` row this route found by `(game_id,
profile_id) IN participants` says nothing about who owns it, so `_replay_by_profile` also takes
`owner_profile_ids` — the same list `get_match_detail` already computed for FR-022's own archival
state, not a new query — and refuses to let *any* capture row the caller does not own read as
anything but absent: it falls through to `derive_availability`'s ordinary age comparison instead,
exactly as if no capture existed, and comes back `expired` or `obtainable` on its own merits.
Nulling only `_replay_json`'s `download_path` while leaving the state `archived` would not be
enough — FR-026's "and only that" is about the state itself, not merely the click it enables,
because `availability: "archived"` on a stranger's point of view is already the disclosure
`test_no_public_directory.py`'s property 4 exists to catch: it says an account controls that
profile, whether or not the button underneath it ever works.

**The `analysis` object on match-detail (T368, SC-011, FR-041).** `_analysis_json` answers the
`analysis` summary `contracts/http-api.md`'s "Analysis" section fixes, in each of its seven states
— `absent` (no `match_analyses` row at all) plus the six `MatchAnalysisState` values — so a caller
can tell from this one response whether a match can still be analysed and until when, without
opening `GET /api/matches/{game_id}/analysis` itself. `stale` is computed here, on every read, by
comparing the stored row's own `parser_version` against `_running_engine_version()` — never a
stored column (FR-041; `match_analyses` carries no such column, `packages/storage/src/
aoe2stats_storage/models.py`). `_running_engine_version()` deliberately does **not** import
`aoe2stats_replay_engine.aoe2rec` to read `ENGINE_NAME`: that module imports `aoe2rec_py`, the
native PyO3 extension, at its own module scope, and anything reachable from `aoe2stats_api.app`
doing that is exactly what constitution V and `test_engine_isolation.py`'s subprocess check forbid.
`importlib.metadata.version` reads the installed distribution's own metadata without importing its
code at all, so `_ENGINE_NAME` below — a literal duplicate of, never an import of, `aoe2stats_
replay_engine.aoe2rec.ENGINE_NAME` — is the one way this process can answer "what version of the
engine is running" without loading it. `routers/analysis.py`'s own `GET /api/matches/{game_id}/
analysis` needs no such comparison — it only ever serves the published document whole or answers
`404` — so this function and its query live here, not there (that router's own module docstring:
"share no response shape to keep in sync").

**Widened past `stored` alone (M12, third-round review).** The filter used to read `capture.status
is not CaptureStatus.STORED or capture.profile_id in owned_profile_ids` — `stored` only.
`derive_availability` also reads `unavailable` on its own (`availability.py`'s table,
`never_recorded`), so a stranger's `unavailable` capture for a recent match answered
`never_recorded` while the identical pair with no capture at all answered `obtainable` — the
account-existence asymmetry FR-026's ownership gate exists to close, one status short of complete
here too (`replays.py`'s `_capture_for_point_of_view`, widened for the same reason, is this
route's own sibling for the download route). `derive_availability` only ever branches on `stored`
and `unavailable`; every other `CaptureStatus` (`pending`, `downloading`, `failed`, `quarantined`,
`expired`) is already unreadable by it regardless of ownership, so filtering by ownership alone —
`capture.profile_id in owned_profile_ids`, full stop, dropping the status check entirely — is not a
behaviour change for those five and does not depend on remembering which two statuses currently
matter if `derive_availability` ever learns to read a third.

**Read-time colour enrichment (T420, FR-003).** `match_players.color_id` has no Relic source at
all (`research.md` **D2**) — `MatchesRepository`/`upsert_match_player` never write it (T413's own
docstring). `enrich_colours` below is this column's only writer, called from `list_matches` alone
— "batched over the page's game ids" is `list_matches`'s own vocabulary, not `get_match_detail`'s,
and every one of T419's tests drives it through `GET /api/matches` — on **the display path only**,
never from `apps/ingester` and never from the capture path: colour never changes once a match is
over, so wiring this into discovery would make it part of what is captured for no benefit, and it
is not on the FR-014 replay-quarantine surface at all. `get_match_detail` still serves whatever
`color_id` `list_matches` has already cached (per `contracts/http-api.md`: "Unchanged. It already
serves ... `color_id`") — it does not enrich on its own, so a match viewed only through its detail
route and never listed keeps `color_id: null`, the same legitimate FR-010 resting state
`data-model.md` §6 describes for a match companion does not know, rather than a second, uncontrolled
companion call on a route nothing in this feature's own test suite exercises against it. It calls
`CompanionEnrichmentProvider.enrich_matches` **once per page, batched over every game_id on it, not
once per match** — but only when at least one participant among those game_ids is still missing a
colour; once a page is fully coloured, a repeat view is a database read (`research.md` **D2**,
`data-model.md` §6). A degraded companion (a 403, an outage, a malformed body — `enrich_matches`
never raises, see `companion/provider.py`'s own module docstring) answers `{}` or a partial map: the
`UPDATE` below only fires for a `(game_id, profile_id)` pair the response actually names a
`color_id` for, and only ever replaces a `NULL` — never a colour already cached by an earlier,
successful view (`data-model.md` §6: "a degraded companion writes nothing; it does not write
`NULL`" — this is the one property `test_match_colour_enrichment.py` exists to prove, and the one
an unconditional `SET` from an empty enrichment result would silently break). The wiring below
(`_COMPANION_HTTP_CLIENT`, `_COMPANION_RATE_LIMITER`, `_companion_breaker`, `_companion_call_sink`)
is `routers/players.py`'s own `_build_search_provider` wiring, duplicated rather than imported —
this module's own convention of a self-contained file (see the docstrings above), and importing
from `players.py` here would invert the existing `players.py -> matches.py` (`match_row_json`)
dependency into a cycle.

**`enrich_colours` is also `routers/players.py`'s own writer (T450, FR-003).** `GET /api/players/
{profile_id}/matches` (`get_player_match_history`) serves the identical row shape through the
identical `match_row_json` (this module's own export, see that function's docstring) but, before
T450, never called this function at all, so `color_id` stayed `NULL` for a freshly-viewed profile
even though `GET /api/matches` had already coloured the same match. Public (no leading underscore)
for exactly the reason `match_row_json` already is: so the two routes can never drift onto two
different colour-enrichment implementations. `players.py` imports it directly rather than
duplicating its body — unlike the companion wiring above (`_COMPANION_HTTP_CLIENT` and friends),
which `players.py` already carries its own, independent copy of for `search.py`'s traffic, this
function's *behaviour*, not merely its transport, is the thing FR-003 requires to be identical
across both routes, which a second, separately-maintained copy could not guarantee. The one-way
dependency this creates (`players.py -> matches.py`) is the same direction `match_row_json` already
established; nothing here reverses it.

**Colour enrichment is now also on `get_match_detail`'s own path (defect fix, quickstart scenario
5).** T333's manual walk against production found `match_players.color_id` NULL forever on a match
this service only ever met as a third party's opponent: `enrich_colours` above was wired into
`list_matches` and `players.py::get_player_match_history` but never into `get_match_detail` itself,
so a match viewed only through its detail route stayed uncoloured no matter how many times it was
opened. `_fetch_detail_response` below now calls it too, batched over `[game_id]` alone — the same
"at most one call, only when something is still missing" discipline described above, unchanged.

**The on-view identity refresh, narrowed to this route's own need (defect fix, quickstart scenario
5).** The same manual walk found a participant this service met only as a third party still
carrying its `str(profile_id)` numeric placeholder as `alias` on the detail page, forever — nothing
on this route ever refreshed it. `routers/players.py::_refresh_profile_identity` already solves
this for its own two routes, but pulls in two further steps (ladder standing, the avatar hash) this
page has no use for; `_refresh_match_identity` below takes only its first step — Relic's
`getRecentMatchHistory` identity block (`RelicMatchHistoryProvider.recent_profiles`), persisted
through `discover.touch_aoe_profile` exactly as `players.py` already does — batched over every
participant of `game_id` still carrying a missing or placeholder alias, in one call, never one per
participant, and never called at all when every participant already has a real one (constitution I:
"capture outranks analysis" reads equally as "a view that needs nothing new must ask for nothing").
The Relic wiring below (`_RELIC_HTTP_CLIENT`, `_RELIC_RATE_LIMITER`, `_relic_call_sink`,
`_build_match_history_provider`) is `players.py`'s own wiring, duplicated rather than imported —
the identical reason the companion wiring above already gives: `players.py` imports `enrich_colours`
and `match_row_json` from this module, so importing back from `players.py` here would invert that
one-way dependency into a cycle.

**The re-read, and why the first response must not skip it.** `enrich_colours` and
`_refresh_match_identity` both write straight to the database — never to the already-materialised,
frozen `MatchDetail` this function already holds — so without reading it back, the very first
(uncached) response after either write would still serialise the stale placeholder alias or `NULL`
colour it just replaced, and a caller would only see the fix on a *second* view. `_fetch_detail_
response` below re-reads `detail` once, but only when one of the two enrichments could plausibly
have changed something — `colour_missing` (some participant still had `color_id is None` before
`enrich_colours` ran) or a non-empty `placeholder_profile_ids` — so a match where every participant
already carries a real alias and a real colour costs no second query at all.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from aoe2stats_api import security
from aoe2stats_api.availability import Availability, AvailabilityView, derive_availability
from aoe2stats_api.civilizations import civilisation_name
from aoe2stats_api.deps import ResponseCacheDep, SessionDep, SettingsDep, cache_get_or_set
from aoe2stats_api.errors import APIError
from aoe2stats_api.match_types import match_type_name
from aoe2stats_ingester import discover
from aoe2stats_providers.base import ProviderCallRecord
from aoe2stats_providers.companion.provider import CompanionEnrichmentProvider
from aoe2stats_providers.relic.matches import RelicMatchHistoryProvider
from aoe2stats_providers.wiring import (
    CircuitBreaker,
    build_async_client_resources,
    build_companion_breaker,
)
from aoe2stats_storage.models import (
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ProfileLink,
    ProviderCall,
    ReplayCapture,
    ReplayFetchMiss,
)
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.repositories.matches import (
    DEFAULT_PAGE_SIZE,
    MatchDetail,
    MatchesRepository,
    MatchListRow,
    MatchParticipant,
    Opponent,
)

router = APIRouter(tags=["matches"])


# --- Colour enrichment (T420, module docstring's "Read-time colour enrichment" note) -------------
#
# Interactive, per-request enrichment traffic against aoe2companion — mirrors `routers/players.py`'s
# own `_COMPANION_HTTP_CLIENT`/`_COMPANION_RATE_LIMITER`/`_companion_breaker`/`_companion_call_sink`
# byte for byte, duplicated rather than imported (module docstring: importing from `players.py`
# here would invert its existing `players.py -> matches.py` dependency on `match_row_json` into a
# cycle, and this router's own convention is a self-contained file, per the docstrings above).

_COMPANION_PROVIDER_TIMEOUT_SECONDS = 10.0
_COMPANION_RATE_PER_SECOND = 5.0
_COMPANION_HTTP_CLIENT, _COMPANION_RATE_LIMITER = build_async_client_resources(
    _COMPANION_RATE_PER_SECOND
)


@functools.lru_cache(maxsize=1)
def _companion_breaker() -> CircuitBreaker:
    """The one `CircuitBreaker` every request's own, otherwise disposable,
    `CompanionEnrichmentProvider` is handed (`companion/provider.py`'s "Breaker lifetime is the
    caller's decision" note) — `lru_cache`, not a bare module global, only so a test that
    deliberately trips it can reset it with `.cache_clear()` afterwards, the same device
    `routers/players.py`'s own `_companion_breaker` uses for the identical reason.
    """
    return build_companion_breaker()


def _companion_call_sink(
    db_session: AsyncSession,
) -> Callable[[ProviderCallRecord], Awaitable[None]]:
    """Writes a `provider_calls` row directly onto the request's own `db_session` — safe here for
    the same reason `routers/players.py`'s own `_companion_call_sink` is:
    `CompanionEnrichmentProvider` never raises (`companion/provider.py`'s own module docstring),
    so there is no mid-request exception this call could cause that would roll the request's
    transaction back and take the row with it."""

    async def _sink(record: ProviderCallRecord) -> None:
        db_session.add(
            ProviderCall(
                provider=record.provider,
                endpoint=record.endpoint,
                status_code=record.status_code,
                duration_ms=record.duration_ms,
                called_at=record.called_at,
                rate_limited=record.rate_limited,
            )
        )

    return _sink


def _build_enrichment_provider(db_session: AsyncSession) -> CompanionEnrichmentProvider:
    return CompanionEnrichmentProvider(
        client=_COMPANION_HTTP_CLIENT,
        timeout_seconds=_COMPANION_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_COMPANION_RATE_LIMITER,
        call_sink=_companion_call_sink(db_session),
        breaker=_companion_breaker(),
    )


async def enrich_colours(
    db_session: AsyncSession, profile_ids: Sequence[int], game_ids: Sequence[int]
) -> None:
    """T420: `match_players.color_id`'s only writer (module docstring). Public — `routers/
    players.py::get_player_match_history` imports this directly (T450), the same "one writer, not
    two" reasoning `match_row_json` already carries for the row shape itself. Calls
    `CompanionEnrichmentProvider.enrich_matches` **at most once**, batched over every `game_id` in
    `game_ids` together — never once per match — and only when at least one of them still carries a
    `match_players` row with `color_id IS NULL`. Once every participant across `game_ids` already
    has a colour cached, this returns without ever reaching the transport, which is what turns a
    second view of the same matches into a database read (`research.md` **D2**).

    `profile_ids` (T409 fix) is threaded straight through to `enrich_matches`: the companion
    endpoint is queried *by profile*, never by match (`companion/provider.py`'s "The endpoint"
    note) — a caller passes the profiles it already knows are relevant to `game_ids` (a route's own
    `profile_id`, or a match's participants), never a value derived here, since this function has
    no other way to know which profiles' recent matches to ask the source for.

    A degraded companion (`enrich_matches` never raises — see `companion/provider.py`'s own module
    docstring) answers `{}` or a partial map: the loop below only ever `UPDATE`s a `(game_id,
    profile_id)` pair the response actually names a `color_id` for, and only ever replaces a row
    still `NULL` (`MatchPlayer.color_id.is_(None)` in the `WHERE` clause) — a colour already cached
    by an earlier, successful view is never overwritten, degraded response or not (`data-model.md`
    §6, `test_match_colour_enrichment.py`'s own "does not write `NULL`" assertion). The identical
    discipline covers a `game_id` companion's default page no longer carries at all (an old match
    it stopped paging, T409's own "honest degrade"): absent from `enrichment`, so the loop below
    never reaches its row — `color_id` stays exactly whatever it already was, never coerced to `0`
    or any other placeholder.
    """
    if not profile_ids or not game_ids:
        return

    still_missing = await db_session.execute(
        select(MatchPlayer.game_id)
        .where(MatchPlayer.game_id.in_(game_ids), MatchPlayer.color_id.is_(None))
        .limit(1)
    )
    if still_missing.scalar_one_or_none() is None:
        # Every participant across `game_ids` is already coloured — a repeat view, or a page
        # nobody has ever needed companion for. No companion call at all (module docstring).
        return

    provider = _build_enrichment_provider(db_session)
    enrichment = await provider.enrich_matches(profile_ids, game_ids)
    for game_id, match_enrichment in enrichment.items():
        if match_enrichment.participants is None:
            continue
        for profile_id, participant in match_enrichment.participants.items():
            if participant.color_id is None:
                continue
            await db_session.execute(
                update(MatchPlayer)
                .where(
                    MatchPlayer.game_id == game_id,
                    MatchPlayer.profile_id == profile_id,
                    MatchPlayer.color_id.is_(None),
                )
                .values(color_id=participant.color_id)
            )


# --- On-view identity refresh, alias/country only (defect fix, module docstring) -----------------
#
# Relic traffic against `getRecentMatchHistory`'s own identity block — mirrors `routers/
# players.py`'s own `_RELIC_HTTP_CLIENT`/`_RELIC_RATE_LIMITER`/`_relic_call_sink`/
# `_build_match_history_provider`
# byte for byte, duplicated rather than imported for the identical reason the companion wiring
# above already is (module docstring's "The on-view identity refresh" note: importing from
# `players.py` here would invert its existing `players.py -> matches.py` dependency into a cycle).

_RELIC_RATE_PER_SECOND = 5.0
_RELIC_HTTP_CLIENT, _RELIC_RATE_LIMITER = build_async_client_resources(_RELIC_RATE_PER_SECOND)


def _relic_call_sink(db_session: AsyncSession) -> Callable[[ProviderCallRecord], Awaitable[None]]:
    """Writes a `provider_calls` row on its **own**, short-lived session — never queued onto
    `db_session` itself. Mirrors `routers/players.py`'s own `_relic_call_sink` byte for byte:
    `RelicMatchHistoryProvider.recent_profiles`, unlike `CompanionEnrichmentProvider`, can fail
    mid-request, and `session_scope` (`deps.py`) rolls the whole request transaction back on any
    unhandled exception — a row added to `db_session` for the very call that raised would be rolled
    back with it, losing exactly the call an operator most needs recorded (constitution III)."""

    async def _sink(record: ProviderCallRecord) -> None:
        bind = db_session.get_bind()
        assert isinstance(bind, Engine), f"expected an Engine bind, got {type(bind)}"
        audit_engine = AsyncEngine(bind)
        async with AsyncSession(bind=audit_engine) as audit_session:
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


def _build_match_history_provider(db_session: AsyncSession) -> RelicMatchHistoryProvider:
    return RelicMatchHistoryProvider(
        client=_RELIC_HTTP_CLIENT,
        timeout_seconds=_COMPANION_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_RELIC_RATE_LIMITER,
        call_sink=_relic_call_sink(db_session),
    )


async def _refresh_match_identity(db_session: AsyncSession, profile_ids: Sequence[int]) -> None:
    """T333 remediation, FR-017: the alias/country half of `routers/players.py::_refresh_profile_
    identity` alone (module docstring) — never the ladder-standing or avatar-hash steps, which
    `get_match_detail` has no use for. One `RelicMatchHistoryProvider.recent_profiles` call, batched
    over every id in `profile_ids` together, persisted through `discover.touch_aoe_profile` for
    every profile the response names (not only the ones asked for, exactly like `players.py`'s own
    step 1) — a real alias overwrites the numeric-id placeholder, a missing or still-placeholder one
    never clobbers a real alias already stored (`touch_aoe_profile`'s own "on conflict" docstring).

    Degrades silently, exactly like every other optional provider call in this codebase
    (`_refresh_third_party_history`'s own docstring in `players.py`): any exception from Relic is
    swallowed, and the caller of this function is left with whatever `aoe_profiles` already held —
    never a failed view over an identity refresh that was only ever a nice-to-have.
    """
    if not profile_ids:
        return

    relic_provider = _build_match_history_provider(db_session)
    try:
        raw_profiles = await relic_provider.recent_profiles(profile_ids)
    except Exception:
        # See the docstring above: this fetch is optional, and its failure — however it is
        # shaped — must never turn into a failed view.
        return

    for raw_profile in raw_profiles:
        await discover.touch_aoe_profile(
            db_session,
            raw_profile.profile_id,
            alias=raw_profile.alias,
            country=raw_profile.country,
        )


# --- Session resolution, the same discipline `auth.py`, `privacy.py`, `profiles.py` and
# `replays.py` already establish (module docstring) ----------------------------------------------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — mirrors `replays.py`'s own helper of the same name and shape."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to view your match history.",
        )
    return session_row


def _profile_not_found() -> APIError:
    """FR-045: the one answer for "no such active link", whatever the underlying reason — see the
    module docstring and `profiles.py`'s / `replays.py`'s own `_profile_not_found`."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No linked profile was found for that id.",
    )


def _match_not_found() -> APIError:
    """The one answer `GET /api/matches/{game_id}` gives when `game_id` names no match at all
    (T327: since the ownership scope was removed, `MatchesRepository.get_match_detail` now returns
    `None` for that single reason only — see that method's own docstring). Deliberately specific —
    never the bare "Not Found" Starlette's own unmatched-route fallback answers, so this route's
    own domain `not_found` is distinguishable from a request that never reached a handler at all
    (`test_match_detail.py`'s own note on why that matters)."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No match was found for that id.",
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


async def _owned_profile_ids(db_session: AsyncSession, *, user_id: Any) -> list[int]:
    """Every profile id the caller has *actively* linked (FR-043: all of them, not only the
    primary). `GET /api/matches/{game_id}` (T327) no longer gates a match's visibility on this
    list — it exists only so `MatchesRepository.get_match_detail` can resolve FR-022's own
    archival state, never a co-participant's."""
    result = await db_session.execute(
        select(ProfileLink.profile_id).where(
            ProfileLink.user_id == user_id, ProfileLink.unlinked_at.is_(None)
        )
    )
    return list(result.scalars().all())


# --- The per-participant `replay` object (T338, module docstring) ------------------------------


async def _replay_by_profile(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_ids: Sequence[int],
    completed_at: datetime,
    owner_profile_ids: Sequence[int],
    capture_budget_days: int,
) -> dict[int, AvailabilityView]:
    """`derive_availability` (T336) for every participant of `game_id`, from two queries scoped to
    the whole match rather than one per participant (module docstring). `derive_availability`
    itself stays pure — no provider, no I/O, no database query of its own (`availability.py`'s own
    module docstring) — so this function is the one place that supplies the rows it needs, batched
    rather than per row.

    `owner_profile_ids` is the caller's own active `profile_links` (`_owned_profile_ids`,
    `get_match_detail`'s existing call — no query added here for it): *any* capture row for a
    `profile_id` outside that set is excluded from `capture_by_profile` below, so
    `derive_availability` receives `capture=None` for it and falls through to the ordinary age
    comparison, never `archived` or `never_recorded` off a row that belongs to someone else
    (module docstring's remediation paragraph, FR-026, widened at M12).
    `capture_budget_days` is threaded straight through to `derive_availability`, which now
    requires it explicitly rather than owning its own window constant — `Settings.
    capture_budget_days` (`CAPTURE_BUDGET_DAYS`), the same value the caller already reads."""
    if not profile_ids:
        return {}

    owned_profile_ids = set(owner_profile_ids)

    captures_result = await db_session.execute(
        select(ReplayCapture).where(
            ReplayCapture.game_id == game_id, ReplayCapture.profile_id.in_(profile_ids)
        )
    )
    capture_by_profile = {
        capture.profile_id: capture
        for capture in captures_result.scalars()
        if capture.profile_id in owned_profile_ids
    }

    misses_result = await db_session.execute(
        select(ReplayFetchMiss.profile_id).where(
            ReplayFetchMiss.game_id == game_id, ReplayFetchMiss.profile_id.in_(profile_ids)
        )
    )
    recorded_404_profiles = set(misses_result.scalars().all())

    now = datetime.now(UTC)
    return {
        profile_id: derive_availability(
            completed_at=completed_at,
            now=now,
            capture=capture_by_profile.get(profile_id),
            recorded_404=profile_id in recorded_404_profiles,
            capture_budget_days=capture_budget_days,
        )
        for profile_id in profile_ids
    }


def _replay_json(
    *, game_id: int, profile_id: int, availability: AvailabilityView
) -> dict[str, Any]:
    """`contracts/http-api.md`'s per-participant `replay` object (FR-023): one entry per
    participant point of view. `download_path` is `None` for the two states FR-025 forbids
    presenting as an action that then fails — `expired` and `never_recorded` — a null path being
    the mechanism that makes rendering one impossible rather than merely discouraged (T338's own
    task text); for the other two it points at `replays.py`'s `GET /api/matches/{game_id}/replay/
    {profile_id}` (T337). `obtainable_until` is carried through from `derive_availability`
    unmodified — already `None` in every state, FR-024 amended 2026-08-29 — so no date is derived
    here either."""
    obtainable = availability.state in (Availability.ARCHIVED, Availability.OBTAINABLE)
    return {
        "profile_id": profile_id,
        "availability": availability.state.value,
        "obtainable_until": (
            availability.obtainable_until.isoformat()
            if availability.obtainable_until is not None
            else None
        ),
        "download_path": f"/api/matches/{game_id}/replay/{profile_id}" if obtainable else None,
    }


# --- The `analysis` object (T368, module docstring) ----------------------------------------------

#: `aoe2stats_replay_engine.aoe2rec.ENGINE_NAME` verbatim, duplicated rather than imported — see
#: the module docstring's own paragraph on why importing that module here would violate
#: constitution V.
_ENGINE_NAME = "aoe2rec-py"


def _running_engine_version() -> str:
    """FR-041's "the engine currently running", read without ever importing it (module docstring).
    `importlib.metadata.version` answers from the installed distribution's own metadata."""
    return metadata.version(_ENGINE_NAME)


#: FR-034: `unavailable` is permanent, and the client must never render a retry action for it —
#: a fixed reason, never derived from a stored column, since `match_analyses` records no reason
#: text of its own for this state (data-model.md's state table: "the recording could not be
#: obtained, and cannot be — the window closed").
_ANALYSIS_UNAVAILABLE_REASON = (
    "The recording expired before this match could be analysed, and it cannot be recovered."
)

#: FR-047: `refused` may be asked for again later — a different, distinguishable fixed reason from
#: `_ANALYSIS_UNAVAILABLE_REASON` above (`test_analysis_routes.py`'s own
#: "the two reasons ... must read differently" assertion).
_ANALYSIS_REFUSED_REASON = (
    "The daily analysis limit was reached. This match may be analysed again later."
)


def _analysis_failed_reason(error_message: str | None) -> str:
    """FR-036: `failed` carries the recording's own parse failure, in `error_message` — shown
    verbatim rather than a generic message, since it is the one state whose reason a stored row
    actually explains rather than a fixed policy text."""
    if error_message:
        return f"The recording could not be analysed: {error_message}"
    return "The recording could not be analysed."


def _analysis_reason(row: MatchAnalysis) -> str | None:
    if row.state is MatchAnalysisState.FAILED:
        return _analysis_failed_reason(row.error_message)
    if row.state is MatchAnalysisState.UNAVAILABLE:
        return _ANALYSIS_UNAVAILABLE_REASON
    if row.state is MatchAnalysisState.REFUSED:
        return _ANALYSIS_REFUSED_REASON
    return None


async def _analysis_row(db_session: AsyncSession, *, game_id: int) -> MatchAnalysis | None:
    """`match_analyses`'s own primary key is `game_id` alone (data-model.md) — at most one row per
    match, ever, so this is the whole lookup."""
    result = await db_session.execute(select(MatchAnalysis).where(MatchAnalysis.game_id == game_id))
    return result.scalar_one_or_none()


def _analysis_json(*, game_id: int, row: MatchAnalysis | None) -> dict[str, Any]:
    """The `analysis` object `contracts/http-api.md`'s "Analysis" section fixes, in each of its
    seven states (module docstring). `row is None` is `absent` — never requested, requestable —
    the one state that is not a stored `MatchAnalysisState` value at all."""
    result_path = f"/api/matches/{game_id}/analysis"
    if row is None:
        return {
            "state": "absent",
            "parser_version": None,
            "stale": False,
            "point_of_view_profile_id": None,
            "result_path": result_path,
            "reason": None,
        }
    stale = (
        row.state is MatchAnalysisState.PUBLISHED
        and row.parser_version is not None
        and row.parser_version != _running_engine_version()
    )
    return {
        "state": row.state.value,
        "parser_version": row.parser_version,
        "stale": stale,
        "point_of_view_profile_id": row.point_of_view_profile_id,
        "result_path": result_path,
        "reason": _analysis_reason(row),
    }


# --- Response shaping --------------------------------------------------------------------------


def _opponent_json(opponent: Opponent) -> dict[str, Any]:
    return {
        "profile_id": opponent.profile_id,
        "alias": opponent.alias,
        "civ_id": opponent.civ_id,
        "civ_name": civilisation_name(opponent.civ_id),
    }


def _participant_json(participant: MatchParticipant) -> dict[str, Any]:
    """One entry of `participants[]` (T423/T425, `contracts/http-api.md`): shared by
    `match_row_json`'s own `participants` and `_match_detail_json`'s, since both are built from the
    identical `MatchParticipant` dataclass (`MatchesRepository`'s own module docstring, "a sibling,
    not a replacement for `opponents`"). `civ_name` (FR-001) and `country` (feeds the opponent flag,
    `contracts/http-api.md`'s field-semantics table) are computed here so a client reading either
    route never derives them itself. `_match_detail_json` below still adds its own `replay` key per
    participant afterwards — a per-point-of-view object `match_row_json`'s own rows never carry
    (T338) — so this function stops one key short of that shape rather than growing an optional
    parameter for it."""
    return {
        "profile_id": participant.profile_id,
        "alias": participant.alias,
        "country": participant.country,
        "team_id": participant.team_id,
        "civ_id": participant.civ_id,
        "civ_name": civilisation_name(participant.civ_id),
        "color_id": participant.color_id,
        "result": participant.result,
        "rating": participant.rating,
        "rating_diff": participant.rating_diff,
    }


def match_row_json(row: MatchListRow) -> dict[str, Any]:
    """Public (no leading underscore): `routers/players.py`'s `GET /api/players/{profile_id}/
    matches` (T328) imports this directly rather than restating it, so the two routes can never
    drift apart on the one shape `contracts/http-api.md` promises is identical — see
    `test_players_history.py`'s own row-shape-comparison test, the reason this function is
    exported at all.

    **Widened (T425, research.md D7).** `rating`, `team_id` and `color_id` are the caller's own —
    `MatchListRow` already carries all three (T423) but nobody read them onto the wire until now.
    `participants` is `opponents`'s sibling, not a replacement for it (`MatchesRepository`'s own
    module docstring): every field already served is unchanged, so a client built against the
    narrower shape keeps working."""
    return {
        "game_id": row.game_id,
        "started_at": row.started_at.isoformat() if row.started_at is not None else None,
        "completed_at": row.completed_at.isoformat(),
        "map_name": row.map_name,
        "leaderboard_id": row.leaderboard_id,
        "leaderboard_name": match_type_name(row.leaderboard_id),
        "duration_seconds": row.duration_seconds,
        "civilisation": row.civilisation,
        "civilisation_name": civilisation_name(row.civilisation),
        "result": row.result,
        "rating_diff": row.rating_diff,
        "rating": row.rating,
        "team_id": row.team_id,
        "color_id": row.color_id,
        "opponents": [_opponent_json(opponent) for opponent in row.opponents],
        "participants": [_participant_json(participant) for participant in row.participants],
        # Every raw `CaptureStatus` value, unmodified — the badge's collapse is a front-end
        # concern (module docstring).
        "capture_status": row.capture_status.value if row.capture_status is not None else None,
        "capture_deadline_at": (
            row.capture_deadline_at.isoformat() if row.capture_deadline_at is not None else None
        ),
    }


def _match_detail_json(
    detail: MatchDetail,
    *,
    replay_by_profile: dict[int, AvailabilityView],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """`replay_by_profile` carries one `AvailabilityView` per participant (T338, `_replay_by_
    profile` above) — every id in `detail.participants` is a key in it, since both are built from
    the same participant list in `get_match_detail`. `analysis` is the T368 summary object
    (`_analysis_json`, module docstring), one per match rather than one per participant — unlike
    `replay`, it does not vary by point of view."""
    return {
        "game_id": detail.game_id,
        "started_at": detail.started_at.isoformat() if detail.started_at is not None else None,
        "completed_at": detail.completed_at.isoformat(),
        "map_name": detail.map_name,
        "leaderboard_id": detail.leaderboard_id,
        "leaderboard_name": match_type_name(detail.leaderboard_id),
        "duration_seconds": detail.duration_seconds,
        # FR-018's "game version" (T327) — `matches.patch` verbatim, never resolved to a name:
        # unlike `civ_id`/`leaderboard_id` there is no id-to-name table for it, so there is nothing
        # to look up here.
        "patch": detail.patch,
        "participants": [
            {
                **_participant_json(participant),
                # FR-023 (T338, module docstring): one download offered per participant point of
                # view, never more, never fewer.
                "replay": _replay_json(
                    game_id=detail.game_id,
                    profile_id=participant.profile_id,
                    availability=replay_by_profile[participant.profile_id],
                ),
            }
            for participant in detail.participants
        ],
        # T070e: the same two fields `match_row_json` already carries, unmodified — every raw
        # `CaptureStatus` value, the badge's collapse staying a front-end concern (module
        # docstring, "Capture state travels to the client unmodified").
        "capture_status": (
            detail.capture_status.value if detail.capture_status is not None else None
        ),
        "capture_deadline_at": (
            detail.capture_deadline_at.isoformat()
            if detail.capture_deadline_at is not None
            else None
        ),
        # T368, SC-011: whether this match can still be analysed, until when, and why not —
        # one object per match, not per participant (module docstring).
        "analysis": analysis,
    }


# --- GET /api/matches ----------------------------------------------------------------------------


@router.get("/matches")
async def list_matches(
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    cache: ResponseCacheDep,
    profile_id: int,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0),
) -> dict[str, Any]:
    """FR-010 / FR-027: `profile_id`'s matches, newest first, cursor paginated, each row carrying
    its capture status and deadline unmodified (module docstring).

    **T102.** `_owned_active_link` below always runs against the database, uncached — ownership is
    never the thing this cache is asked to remember (`ResponseCache`'s own docstring, "Ownership
    and the cache key"). Only once that has passed does the cache key fold `profile_id` in on its
    own: any caller that reaches the `cache_get_or_set` call below has already been proven to own
    `profile_id`, so a hit can only ever answer that same caller with their own data.

    **Only a page reached through an explicit `cursor` is cached — the first page, `cursor is
    None`, never is.** `test_matches_list_cursor_pagination_is_stable_across_insertions`'s own
    docstring names the property that makes the difference: a page fetched through a cursor is
    "bound to [a] match's position" and provably unaffected by any row inserted after it, newer or
    older, which is the entire reason a cursor exists instead of an `OFFSET`. The first page carries
    no such guarantee — it is defined as "whatever is newest right now", so it is exactly the page
    whose answer changes the moment a new match is discovered, whether that discovery is the daily
    ingestion cycle (`apps/ingester`, a separate process — module docstring) or, as that same test
    proves directly against this route, a plain insert in the same request/response cycle. Caching
    it would mean a player could reload their own match history and not see a match they were just
    told was captured, which is the one delay constitution I's "capture outranks analysis" (`docs/
    data-sources.md`) exists to forbid trading away for a comfort target plan.md itself calls
    exactly that. A successful upload through `routers/replays.py::upload_replay` still calls
    `cache.invalidate_prefix` on `("matches", "list", profile_id)` regardless — it clears whatever
    cached continuation pages exist for this profile too, since a capture status change on an
    existing match changes what an already-cached later page would answer with just as much as the
    first page."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    await _owned_active_link(db_session, profile_id=profile_id, user_id=session_row.user_id)

    repository = MatchesRepository(db_session)

    async def _fetch_page() -> dict[str, Any]:
        page = await repository.list_matches(profile_id=profile_id, cursor=cursor, limit=limit)
        # T420: batched over this page's own game_ids, never one call per match (module
        # docstring's "Read-time colour enrichment" note) — a no-op once every row is coloured.
        # T409: the route's own `profile_id` is companion's required query parameter.
        await enrich_colours(db_session, [profile_id], [row.game_id for row in page.matches])
        return {
            "matches": [match_row_json(row) for row in page.matches],
            "next_cursor": page.next_cursor,
        }

    try:
        if cursor is None:
            return await _fetch_page()
        return await cache_get_or_set(
            cache, ("matches", "list", profile_id, cursor, limit), _fetch_page
        )
    except ValueError as exc:
        raise APIError(
            status_code=422,
            code="validation_error",
            message="The request could not be validated.",
            detail={"errors": [str(exc)]},
        ) from exc


# --- GET /api/matches/{game_id} -------------------------------------------------------------------


@router.get("/matches/{game_id}")
async def get_match_detail(
    game_id: int,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    cache: ResponseCacheDep,
) -> dict[str, Any]:
    """FR-018/FR-021 (T327): every participant of `game_id`, with team, civilisation, result and
    rating change, plus map, ladder, game version, start time and duration — readable by any
    signed-in caller, with no ownership scope at all (module docstring). `owner_profile_ids` is
    still resolved and still passed through, but only so `MatchesRepository.get_match_detail` can
    carry FR-022's own archival state and capture deadline for this match (T070e) when the caller
    played in it — it no longer decides whether `detail` comes back at all. The same list is also
    passed to `_replay_by_profile` below, so it is the one query that both gates FR-026's
    `archived` state (module docstring's remediation paragraph) and resolves FR-022's — never a
    second query for the same fact.

    **T102.** `owner_profile_ids` is resolved fresh, uncached, on every call — the ownership
    lookup itself is never what this cache remembers (`ResponseCache`'s "Ownership and the cache
    key"). But the *response* this route builds is not caller-independent even though the route
    is readable by anyone signed in: `detail.capture_status`, `detail.capture_deadline_at` and
    every participant's `replay.availability` all narrow on `owner_profile_ids` (FR-026's ownership
    gate, the module docstring's remediation paragraph — a stranger's `archived` state must never
    be visible to a caller who does not own that point of view). Caching the finished response by
    `game_id` alone would let one caller's cached answer, complete with their own `archived` state,
    leak to the next caller who asks for the same match — so the cache key below folds in
    `frozenset(owner_profile_ids)` as well, which keeps two different callers' answers apart while
    still letting the *same* caller's repeat view of the *same* match answer from memory, which is
    what this task exists for. A successful upload through `routers/replays.py::upload_replay`
    calls `cache.invalidate_prefix` on `("match_detail", game_id)` — a prefix that matches every
    `owner_profile_ids` variant for that match, not only the uploader's own, since anyone's next
    view of a match whose capture state just changed should see the new state rather than wait out
    the TTL."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    owner_profile_ids = await _owned_profile_ids(db_session, user_id=session_row.user_id)

    repository = MatchesRepository(db_session)

    async def _fetch_detail_response() -> dict[str, Any]:
        detail = await repository.get_match_detail(
            game_id=game_id, owner_profile_ids=owner_profile_ids
        )
        if detail is None:
            raise _match_not_found()

        # Defect fix (T333, quickstart scenario 5): colour, then identity, both on this route's
        # own cache-miss path — module docstring's "Colour enrichment is now also on
        # `get_match_detail`'s own path" and "The on-view identity refresh" notes. `colour_missing`
        # is read off `detail` *before* `enrich_colours` runs, so it reflects what was true walking
        # in, which is exactly what decides whether the re-read below is worth its own query.
        colour_missing = any(participant.color_id is None for participant in detail.participants)
        # T409: companion is queried by profile, never by match — batching over both sides of the
        # match (`detail.participants`) covers the whole match in the one call `enrich_colours`
        # already promises, rather than one call per participant.
        await enrich_colours(
            db_session,
            [participant.profile_id for participant in detail.participants],
            [game_id],
        )

        placeholder_profile_ids = [
            participant.profile_id
            for participant in detail.participants
            if participant.alias is None or participant.alias == str(participant.profile_id)
        ]
        if placeholder_profile_ids:
            await _refresh_match_identity(db_session, placeholder_profile_ids)

        if colour_missing or placeholder_profile_ids:
            # Neither write above lands on this already-materialised `detail` — re-read so the
            # first (uncached) response already carries the fresh alias/colour rather than only a
            # second view (module docstring's "The re-read" note).
            detail = await repository.get_match_detail(
                game_id=game_id, owner_profile_ids=owner_profile_ids
            )
            if detail is None:
                raise _match_not_found()

        # T338: one `replay` object per participant point of view (FR-023), derived for the whole
        # match in two queries rather than one per participant (`_replay_by_profile`'s own
        # docstring).
        replay_by_profile = await _replay_by_profile(
            db_session,
            game_id=game_id,
            profile_ids=[participant.profile_id for participant in detail.participants],
            completed_at=detail.completed_at,
            owner_profile_ids=owner_profile_ids,
            capture_budget_days=settings.capture_budget_days,
        )

        # T368: the `analysis` summary object, computed from whatever `match_analyses` row (if
        # any) this exact game_id carries — `_analysis_json`'s own docstring for the seven states.
        analysis_row = await _analysis_row(db_session, game_id=game_id)
        analysis = _analysis_json(game_id=game_id, row=analysis_row)

        return _match_detail_json(detail, replay_by_profile=replay_by_profile, analysis=analysis)

    return await cache_get_or_set(
        cache, ("match_detail", game_id, frozenset(owner_profile_ids)), _fetch_detail_response
    )
