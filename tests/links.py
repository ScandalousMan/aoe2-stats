"""A shared helper that gives a profile an owner in a test (T713).

`CaptureDrain._claim_batch` takes a capture only when its profile has an active link whose user has
not objected to archival (`_owner_is_archiving`, the predicate `revalidate_quarantined` already
used), so a capture seeded without a link is one the claim refuses. T713 moved onto `link_profile`
the six capture-mechanics seeding helpers in `apps/ingester/tests` (`test_capture_run_id.py`,
`test_deadline_order.py`, `test_failure_classification.py`, `test_idempotency.py`,
`test_interruption.py`, `test_quarantine.py`) and the wrapper in `test_revalidate_quarantined.py`;
`test_claim_requires_active_link.py`, `test_deadline_alert.py` and
`test_withdraw_refused_near_deadline.py` in `apps/ingester/tests`, `test_admission.py` in
`apps/analyzer/tests` and `test_capture_audit.py` in `scripts/checks/tests` use it too. Other test
files build their own `ProfileLink` rows; they are not migrated here.

Like `tests/db.py`, this is test-only infrastructure applying across app boundaries, so it sits
beside it rather than inside a workspace member.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import ProfileLink, SteamIdentity, User


async def link_profile(
    session: AsyncSession,
    profile_id: int,
    *,
    objected: bool = False,
    unlinked: bool = False,
    second_user: bool = False,
) -> uuid.UUID:
    """A user (with a Steam identity) linked to `profile_id`; returns the user's id. The default
    is the case a capture needs to be claimed: an active link whose user has not objected.

    `objected` records `users.archival_objected_at`; `unlinked` ends the link
    (`profile_links.unlinked_at`); `second_user` gives the identity a different Steam id, for a
    profile linked twice over time (the first link ended with `unlinked=True`).

    The `aoe_profiles` row must already be in `session`. The rows are added and flushed, not
    committed: the caller owns the transaction, so a fixture that commits once keeps doing so.
    """
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    steam_id64 = f"{'76561199' if second_user else '76561198'}{profile_id:010d}"
    session.add(
        User(
            id=user_id,
            created_at=now,
            allowlisted_at=now,
            archival_objected_at=now if objected else None,
        )
    )
    session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user_id, verified_at=now, last_sign_in_at=now)
    )
    # Flushed before `ProfileLink` is added: no ORM `relationship()` connects `ProfileLink` to
    # `steam_identities`, so the unit of work has no edge telling it which table must land first.
    await session.flush()
    session.add(
        ProfileLink(
            id=uuid.uuid4(),
            user_id=user_id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
            unlinked_at=now if unlinked else None,
        )
    )
    await session.flush()
    return user_id
