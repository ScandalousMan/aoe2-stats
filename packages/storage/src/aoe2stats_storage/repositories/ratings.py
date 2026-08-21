"""`RatingsRepository` — the write path for `rating_snapshots` (FR-009, data-model.md).

`rating_snapshots` is append-only: "one row per observation per cycle" (data-model.md). This
module is the single place that sentence gets enforced, so every caller that resolves a rating —
the sign-in flow that must start the history "from the first sign-in" (T033) and the daily
discovery cycle (T053) alike — goes through the same `record_snapshot` rather than each inventing
its own `INSERT`.

**An unchanged rating still appends a row.** `record_snapshot` never compares against the previous
observation and never skips a write because the value did not move. Two things force that choice:

- The composite primary key is `(profile_id, leaderboard_id, captured_at)` (T007) — the schema
  itself is shaped around "one row per time we looked", not "one row per time the value changed".
  A dedup-on-unchanged design would need a different key (or a mutable "current" row plus a
  separate history), and this schema has neither.
- The whole point of a snapshot is to be honest about what was *observed* and *when* — the same
  discipline `ingest_runs` applies to captures (FR-024) and `provider_calls` applies to every
  external call. Skipping a write because the value repeated conflates two different facts: "we
  did not check" and "we checked and nothing moved". A reader of the curve later cannot tell them
  apart from an absent row, and the second fact is exactly what a flat stretch of the rating curve
  is supposed to show. A daily cron produces at most one row per profile/leaderboard/day, so this
  costs one small, cheap row for an unremarkable day — never unbounded growth — in exchange for a
  series that never has to be trusted on faith.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import RatingSnapshot
from .base import Repository


class RatingsRepository(Repository):
    """Appends observations to `rating_snapshots`. Never updates or deletes a row: the table is
    append-only by design (data-model.md), and this repository is the only thing permitted to
    write to it.
    """

    async def record_snapshot(
        self,
        *,
        profile_id: int,
        leaderboard_id: int,
        rating: int,
        rank: int | None = None,
        wins: int | None = None,
        losses: int | None = None,
        streak: int | None = None,
        highest_rating: int | None = None,
        captured_at: datetime | None = None,
    ) -> RatingSnapshot:
        """Append one `rating_snapshots` row for one profile's standing on one leaderboard.

        `captured_at` defaults to "now" (UTC) — the moment the rating was resolved — and is never
        derived from the caller's own clock elsewhere, so every snapshot this repository writes is
        timestamped consistently regardless of which flow (sign-in, discovery cycle) called it.
        Always inserts: see the module docstring for why an unchanged rating still appends.
        """
        snapshot = RatingSnapshot(
            profile_id=profile_id,
            leaderboard_id=leaderboard_id,
            captured_at=captured_at if captured_at is not None else datetime.now(UTC),
            rating=rating,
            rank=rank,
            wins=wins,
            losses=losses,
            streak=streak,
            highest_rating=highest_rating,
        )
        self.session.add(snapshot)
        # Flush rather than commit: this repository does one unit of work inside whatever
        # `session_scope` (base.py) the caller already opened, and never decides on its own when
        # that unit of work ends. The flush surfaces a constraint violation — an unknown
        # `profile_id`, or two calls racing to the same `(profile_id, leaderboard_id, captured_at)`
        # — against this insert specifically, rather than against whichever statement happens to
        # run next.
        await self.session.flush()
        return snapshot
