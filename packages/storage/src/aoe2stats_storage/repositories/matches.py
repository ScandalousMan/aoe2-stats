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

**Restricted to the caller's linked profiles, at the query itself, never in a later branch** — the
same discipline `data-model.md` insists on for the consent predicate ("Enforced in the query that
selects work, not in a later branch"). The two entry points below draw that line differently
because the two routes hand this repository different information:

- `list_matches` takes one `profile_id`, already the one the router's own `_owned_active_link`
  check (`replays.py`, `profiles.py`) has proven belongs to the caller — restriction here is
  simply that every row comes from an inner join to `match_players` on that exact `profile_id`.
- `get_match_detail` takes no single `profile_id` at all: `GET /api/matches/{game_id}` names a
  match, not a profile, and FR-043 keeps every linked profile reachable, not only the primary one
  (`test_match_detail.py`'s own "reachable via a non-primary linked profile" case). So it takes
  `owner_profile_ids` — every active profile id the caller controls — and returns `None` unless at
  least one of them took part. Returning `None` for "no such match" and for "a real match the
  caller did not play" is deliberate and is what FR-038 (T067) needs: the router turns either cause
  into the *identical* `not_found`, and a repository that already collapses both into one signal is
  what keeps the router from having to reconstruct that discipline itself from two different
  answers.

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
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, literal, select, tuple_

from ..models import AoeProfile, CaptureStatus, Match, MatchPlayer, ReplayCapture
from .base import Repository

#: `GET /api/matches`'s own page size when the caller does not name one. Small enough that a
#: default-sized page and its `opponents` fan-out query both stay well under any function's
#: response-time comfort target (plan.md: "under 500 ms p95 from cached data"), large enough that
#: a normal beta player's week of matches fits on one page.
DEFAULT_PAGE_SIZE = 20

_CURSOR_SEPARATOR = "|"


@dataclass(frozen=True, slots=True)
class Opponent:
    """One other participant in a match, as `list_matches` reports it — never the caller's own
    row (`_seed_full_match`'s own assertion in `test_matches_list.py`: "the caller's own row is
    never listed among their own opponents")."""

    profile_id: int
    alias: str | None
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
    #: never an opponent's.
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
    civ_id: int | None
    color_id: int | None
    result: str | None
    rating: int | None
    rating_diff: int | None


@dataclass(frozen=True, slots=True)
class MatchDetail:
    """The full answer to one `get_match_detail` call."""

    game_id: int
    started_at: datetime | None
    completed_at: datetime
    map_name: str | None
    leaderboard_id: int
    duration_seconds: int | None
    participants: list[MatchParticipant]


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
        """Every `match_players` row for `game_ids` other than `exclude_profile_id`'s own — one
        query for the whole page rather than one per row, joined to `aoe_profiles` for the alias
        FR-010 asks for ("opponents")."""
        if not game_ids:
            return {}

        result = await self.session.execute(
            select(
                MatchPlayer.game_id, MatchPlayer.profile_id, MatchPlayer.civ_id, AoeProfile.alias
            )
            .join(AoeProfile, AoeProfile.profile_id == MatchPlayer.profile_id)
            .where(
                MatchPlayer.game_id.in_(game_ids),
                MatchPlayer.profile_id != exclude_profile_id,
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
        """FR-011: every participant of `game_id`, with team, civilisation, result and rating
        change — but only if at least one of `owner_profile_ids` (every active profile the caller
        controls, FR-043) took part. Returns `None` for both "no such match" and "a real match none
        of the caller's profiles played" (module docstring) — the single signal FR-038/T067
        requires the router to turn into one identical `not_found`, whatever the underlying cause.
        """
        owner_ids = set(owner_profile_ids)
        if not owner_ids:
            return None

        match = await self.session.get(Match, game_id)
        if match is None:
            return None

        result = await self.session.execute(
            select(MatchPlayer, AoeProfile.alias)
            .join(AoeProfile, AoeProfile.profile_id == MatchPlayer.profile_id)
            .where(MatchPlayer.game_id == game_id)
        )
        rows = result.all()
        if not any(player.profile_id in owner_ids for player, _alias in rows):
            return None

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
            for player, alias in rows
        ]

        return MatchDetail(
            game_id=match.game_id,
            started_at=match.started_at,
            completed_at=match.completed_at,
            map_name=match.map_name,
            leaderboard_id=match.leaderboard_id,
            duration_seconds=match.duration_seconds,
            participants=participants,
        )
