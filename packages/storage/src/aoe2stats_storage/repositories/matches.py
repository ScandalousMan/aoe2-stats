"""`MatchesRepository` — the read path for a user's match history (T069).

`contracts/http-api.md`'s Matches table fixes the shape both callers need: `GET /api/matches`
("Newest first, cursor paginated. Each row carries its capture status and `capture_deadline_at`",
FR-027) and `GET /api/matches/{game_id}` ("All participants, teams, civs, results, rating
changes", FR-011). Both are read-only; unlike `RatingsRepository` this module never writes.

**Cursor, not offset.** `data-model.md`'s claim query already establishes the discipline this
schema leans on for a moving window under concurrent writes: never `OFFSET`, always a seek on a
stable key. `OFFSET N` names a *position*, and a row inserted above that position shifts every
later page by exactly one — duplicating or skipping a row depending on which side of the insertion
the offset lands. A newer match can arrive between two page requests at any time (US2 runs daily,
independently of anyone browsing their history), so this repository seeks instead: the cursor
carries `(completed_at, game_id)` of the last row already served, and the next page asks for rows
strictly *after* that position in the same order — a position a later insertion can only ever land
on one side of, never inside.

`game_id` is the tiebreak because `completed_at` alone is not unique (two matches can finish in the
same second) and `matches.game_id` is Relic's own identifier, stable and already the table's
primary key (`models.py`) — nothing this repository invents. Ordering is `completed_at DESC,
game_id DESC` (newest first, FR-010), so "the next page" is every row whose `(completed_at,
game_id)` tuple sorts strictly *below* the cursor's in that same order, which a row-wise `<`
comparison expresses directly without a `CASE` or an `OR` chain.

The cursor is base64 of `"<completed_at.isoformat()>|<game_id>"` — opaque to the caller (the
contract's own word), not signed: it names a position in an already-authorized, already-scoped
query (`profile_id` is re-validated by the router on every call, `list_matches` never trusts a
cursor to widen what it can see), so forging one only ever seeks to a different position in the
same caller's own history, never into someone else's.

**`list_matches` stays restricted to the caller's linked profiles, at the query itself, never in a
later branch** — the same discipline `data-model.md` insists on for the consent predicate
("Enforced in the query that selects work, not in a later branch"). It takes one `profile_id`,
already the one the router's own `_owned_active_link` check (`replays.py`, `profiles.py`) has
proven belongs to the caller — restriction here is simply that every row comes from an inner join
to `match_players` on that exact `profile_id`.

**`get_match_detail` is not restricted at all (T327, FR-018/FR-021).** It takes no single
`profile_id`: `GET /api/matches/{game_id}` names a match, not a profile, and this feature widens
that route so any match this service holds is readable by any signed-in caller, whichever history
it is reached from. It still takes `owner_profile_ids` — every active profile id the caller
controls, FR-043 — but only to resolve FR-022's own archival state, never to gate the match itself;
`None` now means exactly one thing, "no such `game_id`" — the router (`apps/api/.../routers/
matches.py`) still turns that into one `not_found`, the same envelope as before, just for one
cause instead of two.

**Capture status travels intact.** Per T073's own note (quoted in `test_capture_visibility.py`),
the collapse of `unavailable`/`expired`/`failed` into a single "lost" badge state belongs to the
design-system component, not the data layer. This module returns `ReplayCapture.status` — all
seven raw values, including `quarantined` — completely unmodified, via a `LEFT OUTER JOIN` so a
match that has not yet acquired a capture row (should not happen once discovery has run per
`data-model.md`, but is not this repository's invariant to enforce) still comes back rather than
being silently dropped by an inner join.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, literal, or_, select, tuple_
from sqlalchemy.orm import aliased

from ..models import AoeProfile, CaptureStatus, Match, MatchPlayer, ReplayCapture
from .base import Repository

#: `GET /api/matches`'s own page size when the caller does not name one. Small enough that a
#: default-sized page and its `opponents` fan-out query both stay well under any function's
#: response-time comfort target (plan.md: "under 500 ms p95 from cached data"), large enough that
#: a normal beta player's week of matches fits on one page.
DEFAULT_PAGE_SIZE = 20

_CURSOR_SEPARATOR = "|"


# --- projection: matches.raw_payload -> match_players (T413, research.md D1) ---------------------
#
# `upsert_match_player` (`apps/ingester/.../discover.py`) inserted only the `(game_id, profile_id)`
# primary key: `civ_id`, `team_id`, `rating`, `rating_diff` and `result` were declared columns,
# read by three routers and the privacy export, and written by nobody. Every one of them is
# already sitting, unread, in `matches.raw_payload` — this section is the pure mapping T413 exists
# to write once so both writers of `match_players` (`DiscoverStage.__call__` and
# `apps/api/.../routers/players.py`'s `_refresh_third_party_history`) share it rather than each
# growing its own copy.


@dataclass(frozen=True, slots=True)
class ProjectedMatchPlayer:
    """The five Relic-derived `match_players` columns, projected from one `matchHistoryStats[]`
    entry for one participant. `color_id` is deliberately absent — Relic's match history response
    carries no such field; T420's read-time companion enrichment is that column's only writer."""

    civ_id: int | None
    team_id: int | None
    rating: int | None
    rating_diff: int | None
    result: str | None


class MatchProjectionMismatch(ValueError):
    """Raised when `matchhistorymember[]` disagrees with the same participant's own entry in
    `matchhistoryreportresults[]` on `civilization_id`, `teamid` or the mapped result.
    `matchhistoryreportresults[]` is a cross-check, not a second source (data-model.md's own
    wording): a disagreement is not resolved by picking a side here, because a silent tie-break is
    exactly how a wrong civilisation would ship looking confident. The caller decides what to do
    with a payload that fails its own internal cross-check; this function only refuses to guess."""


def _map_outcome(value: Any) -> str | None:
    """`matchhistorymember[].outcome` / `matchhistoryreportresults[].resulttype` share this same
    two-code vocabulary: `1` -> `"win"`, `0` -> `"loss"`, and — FR-004's neutral state — anything
    else (a draw code, `None`, a value Relic has not documented) maps to `None` rather than being
    coerced into a loss."""
    if value == 1:
        return "win"
    if value == 0:
        return "loss"
    return None


def project_match_player(raw_match: Mapping[str, Any], profile_id: int) -> ProjectedMatchPlayer:
    """Project `profile_id`'s entry out of one `matchHistoryStats[]` item (`raw_match` — the exact
    shape `Match.raw_payload`/`RawMatch.raw_payload` carry verbatim, constitution IV) into the five
    Relic-derived `match_players` columns. Pure: no I/O, no session, safe to call as many times as
    a match is rediscovered.

    - `civ_id` <- `matchhistorymember[].civilization_id`, direct.
    - `team_id` <- `matchhistorymember[].teamid`, direct.
    - `rating` <- `matchhistorymember[].newrating`, the value *after* the match (FR-005) — never
      `oldrating`.
    - `rating_diff` <- `newrating - oldrating`, signed, and `NULL` (never `0`) the moment either
      side is missing: a `0` is a real, symmetric rating outcome, and a stand-in that means
      "unknown" would be a lie the interface cannot see through.
    - `result` <- `_map_outcome(matchhistorymember[].outcome)`.

    Every field above is cross-checked against `profile_id`'s own entry in
    `matchhistoryreportresults[]`, when that array carries one: `civilization_id`, `teamid` and
    the mapped result must agree, or this raises `MatchProjectionMismatch` rather than picking a
    side (see that class's own docstring).

    `raw_match` carrying no `matchhistorymember[]` entry for `profile_id` at all — a payload
    shape from before this projection existed, or a caller assembling a synthetic `raw_payload`
    (several `apps/ingester` tests do exactly this) — is not a fault to raise on: it projects to
    every field `None`, the same "nothing written yet" state `upsert_match_player` produced before
    T413, so a payload this function cannot yet interpret degrades rather than blocking the write
    of the row it *does* know how to place (the primary key).
    """
    member = next(
        (
            entry
            for entry in raw_match.get("matchhistorymember", [])
            if entry.get("profile_id") == profile_id
        ),
        None,
    )
    if member is None:
        return ProjectedMatchPlayer(
            civ_id=None, team_id=None, rating=None, rating_diff=None, result=None
        )

    civ_id = member.get("civilization_id")
    team_id = member.get("teamid")
    old_rating = member.get("oldrating")
    new_rating = member.get("newrating")
    result = _map_outcome(member.get("outcome"))

    report = next(
        (
            entry
            for entry in raw_match.get("matchhistoryreportresults", [])
            if entry.get("profile_id") == profile_id
        ),
        None,
    )
    if report is not None:
        report_civ_id = report.get("civilization_id")
        if report_civ_id != civ_id:
            raise MatchProjectionMismatch(
                f"profile {profile_id}: civilization_id disagreement between "
                f"matchhistorymember ({civ_id!r}) and matchhistoryreportresults "
                f"({report_civ_id!r})"
            )
        report_team_id = report.get("teamid")
        if report_team_id != team_id:
            raise MatchProjectionMismatch(
                f"profile {profile_id}: teamid disagreement between matchhistorymember "
                f"({team_id!r}) and matchhistoryreportresults ({report_team_id!r})"
            )
        report_result = _map_outcome(report.get("resulttype"))
        if report_result != result:
            raise MatchProjectionMismatch(
                f"profile {profile_id}: result disagreement between matchhistorymember's "
                f"outcome ({result!r}) and matchhistoryreportresults' resulttype "
                f"({report_result!r})"
            )

    rating_diff = (
        new_rating - old_rating if new_rating is not None and old_rating is not None else None
    )

    return ProjectedMatchPlayer(
        civ_id=civ_id,
        team_id=team_id,
        rating=new_rating,
        rating_diff=rating_diff,
        result=result,
    )


@dataclass(frozen=True, slots=True)
class Opponent:
    """One other participant in a match, as `list_matches` reports it — never the caller's own
    row (`_seed_full_match`'s own assertion in `test_matches_list.py`: "the caller's own row is
    never listed among their own opponents"), and, since T070d, never a teammate's row either
    (`_opponents_by_game`'s own docstring): the field is named `opponents`, so it holds only
    participants on a different team than the caller's."""

    profile_id: int
    alias: str | None
    #: A bare Relic id, nothing more — this package cannot import `apps/api` (the dependency runs
    #: the other way), so `civilisation_name` (`aoe2stats_api.civilizations`, T070c) is attached
    #: at the router layer, never here.
    civ_id: int | None


@dataclass(frozen=True, slots=True)
class MatchListRow:
    """One row of `GET /api/matches` — FR-010's list plus the capture status/deadline
    `contracts/http-api.md` adds to every row."""

    game_id: int
    started_at: datetime | None
    completed_at: datetime
    map_name: str | None
    leaderboard_id: int
    duration_seconds: int | None
    #: The caller's own `civ_id` for this match — FR-010 says "civilisation", meaning the caller's,
    #: never an opponent's. A bare Relic id (see `Opponent.civ_id`'s own note on why the name it
    #: resolves to, T070c, is attached by the router rather than here).
    civilisation: int | None
    #: The caller's own result.
    result: str | None
    #: The caller's own rating change.
    rating_diff: int | None
    opponents: list[Opponent] = field(default_factory=list)
    #: `None` only for a match that has not yet acquired a `replay_captures` row (module
    #: docstring) — every raw `CaptureStatus` value otherwise, never collapsed.
    capture_status: CaptureStatus | None = None
    capture_deadline_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MatchesPage:
    """The full answer to one `list_matches` call: a page of rows plus the opaque cursor for the
    next one, `None` once there is nothing left (`contracts/http-api.md`'s
    `{"matches": [...], "next_cursor": ...}` shape)."""

    matches: list[MatchListRow]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class MatchParticipant:
    """One participant of `GET /api/matches/{game_id}` — FR-011: team, civilisation, result,
    rating change, for every player, not only the caller."""

    profile_id: int
    alias: str | None
    team_id: int | None
    #: A bare Relic id (see `Opponent.civ_id`'s own note, T070c).
    civ_id: int | None
    color_id: int | None
    result: str | None
    rating: int | None
    rating_diff: int | None


@dataclass(frozen=True, slots=True)
class MatchDetail:
    """The full answer to one `get_match_detail` call — FR-027's capture state alongside FR-011's
    participants, the same two fields `MatchListRow` already carries (T070e): the list and detail
    routes answer with one vocabulary, not two.

    `patch` (T327, FR-018's "game version") is `matches.patch` verbatim, carried by the ingester's
    own `discover.py` from the source since 001 but never surfaced by any route until the widened
    `GET /api/matches/{game_id}` needed it."""

    game_id: int
    started_at: datetime | None
    completed_at: datetime
    map_name: str | None
    leaderboard_id: int
    duration_seconds: int | None
    patch: str | None
    participants: list[MatchParticipant]
    #: `None` only for a match that has not yet acquired a `replay_captures` row for any of the
    #: caller's own linked profiles (`MatchListRow`'s own note) — every raw `CaptureStatus`
    #: otherwise, never collapsed (module docstring, "capture status travels intact").
    capture_status: CaptureStatus | None = None
    capture_deadline_at: datetime | None = None


def _encode_cursor(completed_at: datetime, game_id: int) -> str:
    payload = f"{completed_at.isoformat()}{_CURSOR_SEPARATOR}{game_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    """The inverse of `_encode_cursor`. Raises `ValueError` for anything malformed — a cursor this
    repository never produced, tampered with, or built for a different shape entirely — so the
    router (T070) can turn that into a `422`, the same way it already validates every other query
    parameter, rather than this module returning a page seeked from nowhere in particular.
    """
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        completed_at_raw, separator, game_id_raw = payload.partition(_CURSOR_SEPARATOR)
        if not separator:
            raise ValueError("cursor payload is missing its separator")
        return datetime.fromisoformat(completed_at_raw), int(game_id_raw)
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise ValueError(f"invalid matches cursor: {cursor!r}") from exc


def _pick_capture_state(
    candidates: Iterable[tuple[CaptureStatus, datetime]],
) -> tuple[CaptureStatus | None, datetime | None]:
    """`get_match_detail`'s own note: among the caller's own `replay_captures` rows for one match
    (ordinarily exactly one), prefer `stored` — the one status `replays.py`'s own
    `_stored_capture_for_caller` looks for — so this route's badge and the download control it
    gates never disagree. `(None, None)` for no candidates at all, the same "not yet acquired a
    capture row" case `MatchListRow` already leaves unfilled."""
    best: tuple[CaptureStatus, datetime] | None = None
    for status, deadline in candidates:
        if best is None or (status is CaptureStatus.STORED and best[0] is not CaptureStatus.STORED):
            best = (status, deadline)
    if best is None:
        return None, None
    return best


class MatchesRepository(Repository):
    """Read-only queries over `matches`, `match_players` and `replay_captures`, scoped to one
    user's own linked profiles (module docstring)."""

    async def list_matches(
        self,
        *,
        profile_id: int,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> MatchesPage:
        """FR-010 / FR-027: `profile_id`'s matches, newest first, cursor paginated, each row
        carrying its capture status and deadline (module docstring).

        `profile_id` is assumed already proven to belong to the caller — the same division of
        labour `replays.py`'s `replay_status` already applies (`_owned_active_link` first, then a
        query scoped to that `profile_id`): this repository restricts every row to `profile_id` by
        construction (the inner join below), but does not itself decide whose `profile_id` the
        caller is allowed to name. `cursor`, if given, must be one this repository itself issued;
        anything else raises `ValueError` (see `_decode_cursor`).
        """
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit!r}")

        order_by = (Match.completed_at.desc(), Match.game_id.desc())
        stmt = (
            select(
                Match.game_id,
                Match.started_at,
                Match.completed_at,
                Match.map_name,
                Match.leaderboard_id,
                Match.duration_seconds,
                MatchPlayer.civ_id,
                MatchPlayer.result,
                MatchPlayer.rating_diff,
                ReplayCapture.status,
                ReplayCapture.capture_deadline_at,
            )
            .join(
                MatchPlayer,
                and_(MatchPlayer.game_id == Match.game_id, MatchPlayer.profile_id == profile_id),
            )
            .outerjoin(
                ReplayCapture,
                and_(
                    ReplayCapture.game_id == Match.game_id,
                    ReplayCapture.profile_id == profile_id,
                ),
            )
            .order_by(*order_by)
            # One extra row, never returned, is how `next_cursor` is decided without a second
            # `COUNT` query: exactly `limit` rows plus one more still existing is "there is a next
            # page", not a re-derivation from an offset (module docstring).
            .limit(limit + 1)
        )

        if cursor is not None:
            cursor_completed_at, cursor_game_id = _decode_cursor(cursor)
            stmt = stmt.where(
                tuple_(Match.completed_at, Match.game_id)
                < tuple_(literal(cursor_completed_at), literal(cursor_game_id))
            )

        rows = (await self.session.execute(stmt)).all()
        has_more = len(rows) > limit
        page_rows = rows[:limit]

        opponents_by_game = await self._opponents_by_game(
            [row.game_id for row in page_rows], exclude_profile_id=profile_id
        )

        matches = [
            MatchListRow(
                game_id=row.game_id,
                started_at=row.started_at,
                completed_at=row.completed_at,
                map_name=row.map_name,
                leaderboard_id=row.leaderboard_id,
                duration_seconds=row.duration_seconds,
                civilisation=row.civ_id,
                result=row.result,
                rating_diff=row.rating_diff,
                opponents=opponents_by_game.get(row.game_id, []),
                capture_status=row.status,
                capture_deadline_at=row.capture_deadline_at,
            )
            for row in page_rows
        ]

        next_cursor = (
            _encode_cursor(page_rows[-1].completed_at, page_rows[-1].game_id)
            if has_more and page_rows
            else None
        )
        return MatchesPage(matches=matches, next_cursor=next_cursor)

    async def _opponents_by_game(
        self, game_ids: Sequence[int], *, exclude_profile_id: int
    ) -> dict[int, list[Opponent]]:
        """Every `match_players` row for `game_ids` that is on a **different team** than
        `exclude_profile_id`'s own — one query for the whole page rather than one per row, joined
        to `aoe_profiles` for the alias FR-010 asks for ("opponents").

        T070d: before this, the filter was only `profile_id != exclude_profile_id`, so a
        teammate came back under the same name as a genuine opponent — the field was named
        `opponents` but held every other participant, teammates included. Fixed here, at the
        query, rather than by carrying `team_id` on the wire and asking the client to separate
        them: `MatchRow` (`packages/design-system/specs/match-history.md` §4) never needs a
        teammate's row, so there is nothing for the client to do with one, and a field that
        already holds only opponents needs no further disambiguation to be honest about its name.
        `caller_row` is a second join to `match_players` for the same game, `exclude_profile_id`'s
        own — always exactly one row, because every `game_id` here came from a query that already
        inner-joined `match_players` on that exact `profile_id` (`list_matches`). A participant is
        kept when its `team_id` is distinct from the caller's; `is_distinct_from` rather than
        `!=` because plain SQL equality against `NULL` evaluates to `NULL`, never `TRUE` — a
        `!=` would silently drop every participant of a match with no team data recorded at all.
        When the caller's own `team_id` is itself `NULL` there is nothing to compare against, so
        nothing is excluded: the same behaviour this method had before this fix, for the one case
        it still cannot resolve, rather than a stricter one invented here.
        """
        if not game_ids:
            return {}

        caller_row = aliased(MatchPlayer)
        result = await self.session.execute(
            select(
                MatchPlayer.game_id, MatchPlayer.profile_id, MatchPlayer.civ_id, AoeProfile.alias
            )
            .join(AoeProfile, AoeProfile.profile_id == MatchPlayer.profile_id)
            .join(
                caller_row,
                and_(
                    caller_row.game_id == MatchPlayer.game_id,
                    caller_row.profile_id == exclude_profile_id,
                ),
            )
            .where(
                MatchPlayer.game_id.in_(game_ids),
                MatchPlayer.profile_id != exclude_profile_id,
                or_(
                    caller_row.team_id.is_(None),
                    MatchPlayer.team_id.is_distinct_from(caller_row.team_id),
                ),
            )
        )
        by_game: dict[int, list[Opponent]] = {}
        for game_id, opponent_profile_id, civ_id, alias in result.all():
            by_game.setdefault(game_id, []).append(
                Opponent(profile_id=opponent_profile_id, alias=alias, civ_id=civ_id)
            )
        return by_game

    async def get_match_detail(
        self, *, game_id: int, owner_profile_ids: Sequence[int]
    ) -> MatchDetail | None:
        """FR-018/FR-021 (T327): every participant of `game_id`, with team, civilisation, result
        and rating change, plus map, ladder, game version, start time and duration — for *any*
        signed-in caller, whether or not one of `owner_profile_ids` took part. The ownership scope
        this method enforced before T327 is gone; `None` now means exactly one thing, "no such
        match" (`match is None` below), never "a real match this caller's profiles did not play" —
        `GET /api/matches/{game_id}` names no profile at all and FR-021 requires the identical
        response whichever history it is reached from, an identity a caller-shaped gate would
        itself have broken.

        `owner_profile_ids` (every active profile the caller controls, FR-043) still narrows one
        thing: FR-022's own archival state, never anyone else's. FR-027 (T070e) resolves it here,
        the same field pair `list_matches` already carries, via the identical `LEFT OUTER JOIN`
        (class docstring), joined into this same participants query rather than a second, `None`-
        swallowing path, so a match discovered before its capture row exists still resolves rather
        than 404ing. `replay_captures` is keyed `(game_id, profile_id)` (`ReplayCapture`'s own
        docstring: "whose point of view"), and this route names no single `profile_id`, so the join
        condition matches on every id in `owner_ids` at once — ordinarily exactly one, since a
        capture row only exists for a profile that actually discovered this match through its own
        history. The one caller-owned row that carries a non-`None` status among the joined
        participant rows is the caller's own capture state; `stored` wins should more than one
        exist, since that is also the exact row `replays.py`'s `_stored_capture_for_caller` would
        find for this caller and this `game_id` — the badge shown here and the control it gates
        never disagree. A caller with no active links at all (`owner_ids` empty) sees the match in
        full and simply carries no archival state of their own, the same as any other participant
        who never captured a replay for it.
        """
        owner_ids = set(owner_profile_ids)

        match = await self.session.get(Match, game_id)
        if match is None:
            return None

        result = await self.session.execute(
            select(
                MatchPlayer,
                AoeProfile.alias,
                ReplayCapture.status,
                ReplayCapture.capture_deadline_at,
            )
            .join(AoeProfile, AoeProfile.profile_id == MatchPlayer.profile_id)
            .outerjoin(
                ReplayCapture,
                and_(
                    ReplayCapture.game_id == MatchPlayer.game_id,
                    ReplayCapture.profile_id == MatchPlayer.profile_id,
                    MatchPlayer.profile_id.in_(owner_ids),
                ),
            )
            .where(MatchPlayer.game_id == game_id)
        )
        rows = result.all()

        participants = [
            MatchParticipant(
                profile_id=player.profile_id,
                alias=alias,
                team_id=player.team_id,
                civ_id=player.civ_id,
                color_id=player.color_id,
                result=player.result,
                rating=player.rating,
                rating_diff=player.rating_diff,
            )
            for player, alias, _status, _deadline in rows
        ]

        capture_status, capture_deadline_at = _pick_capture_state(
            (status, deadline) for _player, _alias, status, deadline in rows if status is not None
        )

        return MatchDetail(
            game_id=match.game_id,
            started_at=match.started_at,
            completed_at=match.completed_at,
            map_name=match.map_name,
            leaderboard_id=match.leaderboard_id,
            duration_seconds=match.duration_seconds,
            patch=match.patch,
            participants=participants,
            capture_status=capture_status,
            capture_deadline_at=capture_deadline_at,
        )
