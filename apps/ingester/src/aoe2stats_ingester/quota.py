"""The ingestion fairness quota (T058, FR-044): a per-*user* cap, never per profile.

`quota.py` is a sibling of `budget.py`, not a part of it (`budget.py`'s own module docstring, and
`plan.md`'s module table): `budget.py` bounds *how long* a run may keep working, whoever it is
working for; this module bounds *how much of one user's* work a run does this cycle, regardless of
how much time is left. The two are independent knobs and never share state.

**Read-only, over already-claimed work.** `apply_quota` takes a run's already-claimed
`ReplayCapture` rows — `capture.py`'s `_claim_batch` has already flipped their `status` and
`claimed_at` before this module ever sees them — and returns the subsequence a run may actually
*process* this cycle. A capture this drops is not written to in any way: it stays claimed exactly as
`_claim_batch` left it, so the next cycle's own claim query (`ix_replay_captures_claim_order`) picks
it up again. This module never opens a write transaction of its own.

**The cap aggregates across a user's whole account, never one profile at a time** (FR-044's own
wording: "aggregated across all their profiles, never per profile"). A user with two linked
profiles who has one far-deadline capture pending on each must not get two captures through a
`max_per_user=1` run just because each profile's own count is `1 <= 1` — the counter below is keyed
on `users.id`, resolved from `replay_captures.profile_id` through the *active* `profile_links` row
(`unlinked_at IS NULL`, mirroring `ProfileLink`'s own partial-unique-index invariant), never on
`profile_id` itself.

**The exemption is the whole point of the requirement, not an edge case bolted onto it.** A capture
whose `capture_deadline_at` is nearer than `exempt_days` runs regardless of the cap — a fairness cap
that delayed an expiring replay to make room for a fresh one would invert the priority the entire
21-day capture budget is built on. The exemption also does not spend a cap slot of its own: an
exempt capture ahead of ordinary ones in claim order leaves the full `max_per_user` untouched for
the ordinary captures behind it, so "exempt" means "bypasses the mechanism entirely", not "consumes
a free slot in it".
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import ProfileLink, ReplayCapture


async def apply_quota(
    session: AsyncSession,
    candidates: Sequence[ReplayCapture],
    *,
    max_per_user: int,
    exempt_days: int,
    now: datetime,
) -> list[ReplayCapture]:
    """Filter `candidates` (already in claim order) down to what one run may process this cycle.

    Returns the allowed subsequence in the same relative order it was given in. Everything dropped
    is left untouched for the next cycle's claim query — see the module docstring.
    """
    if not candidates:
        return []

    profile_ids = {capture.profile_id for capture in candidates}
    owner_rows = await session.execute(
        select(ProfileLink.profile_id, ProfileLink.user_id).where(
            ProfileLink.profile_id.in_(profile_ids),
            ProfileLink.unlinked_at.is_(None),
        )
    )
    owner_by_profile_id: dict[int, uuid.UUID] = {
        row.profile_id: row.user_id for row in owner_rows.all()
    }

    exempt_window = timedelta(days=exempt_days)
    # Counts are keyed on the resolved user id. A candidate whose profile has no active link (the
    # link was revoked between the claim and this check) has no user to charge a cap against; it is
    # let through rather than silently dropped, since dropping it here would be a second, hidden
    # loss path this module does not own.
    counts: dict[uuid.UUID, int] = {}
    allowed: list[ReplayCapture] = []
    for capture in candidates:
        if capture.capture_deadline_at - now < exempt_window:
            allowed.append(capture)
            continue

        owner_id = owner_by_profile_id.get(capture.profile_id)
        if owner_id is None:
            allowed.append(capture)
            continue

        spent = counts.get(owner_id, 0)
        if spent >= max_per_user:
            continue
        counts[owner_id] = spent + 1
        allowed.append(capture)

    return allowed
