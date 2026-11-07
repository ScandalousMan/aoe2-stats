"""T459n: the sweep that removes an erased user's recording a dying writer left behind (FR-037).

Two writers can leave `replays/{game_id}/{profile_id}.zip` in the bucket with no row naming it,
after the user's erasure has committed: the capture drain, killed or failed between its
`put_if_absent` and its cleanup (`CaptureDrain._process_one`, T459j), and the erasure itself when
its post-commit delete fails or is killed (`routers/privacy.py`, pass 3, T459q). Nothing else
revisits such an object, so this sweep does, once per drain call.

**Mechanism: the erasure's own committed trace, not a new record.** `erase_account` inserts the
placeholder `aoe_profiles` row `-abs(profile_id)` (`pseudonymise_profile`) for every profile the
user owned, in the transaction that deletes their rows and the user, so it is committed exactly when
the erasure is. A replay key is removed only when all three hold:

1. the key has the exact shape `replays/{game_id}/{profile_id}.zip`;
2. no `replay_captures` row exists for `(game_id, profile_id)`;
3. the placeholder `aoe_profiles` row for `profile_id` exists.

Condition 3 is what separates an erased user's leftover from an object that merely has no row yet or
any more: a manual upload writes its object before its row, and one whose row write then fails
(`CaptureNoLongerOpen`, say) leaves an object of a user who never erased. Constitution IV keeps
that original, so a key whose profile was never pseudonymised is never removed. Condition 2 keeps
the object of any live row, an in-flight drain's included (the drain's row exists from its claim
until it is erased), and the read that confirms it is `CaptureDrain._pair_has_row`'s `FOR SHARE`
read, which waits for an erasure holding the row. An erasure in progress or rolled back has no
committed placeholder, so condition 3 fails and its objects are kept.

The residual: a profile id an erasure pseudonymised and a user later links again gets a fresh row
(condition 2 then keeps its object). The placeholder is also written by a third-party objection
(FR-039); such a profile has no user and so no capture row or object of its own.

**Budget.** The sweep takes the drain's `Budget` and runs at the start of `CaptureDrain.__call__`,
before the claim loop. It does nothing, not even a listing, when the budget is already expired, and
checks it before each key it examines, stopping cleanly. The single `list_keys` call and the
one read or delete in progress are not interrupted, so the budget is honoured between those calls,
not within them.

Every failure is contained: the sweep never raises into the drain, and its log line carries a count
and the exception's type name, never a key, because the object store's exceptions carry the request
URL, which holds the key. Deletes per call are capped at `MAX_DELETES_PER_SWEEP`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.privacy.erasure import pseudonymise_profile
from aoe2stats_ingester.budget import Budget
from aoe2stats_storage.models import AoeProfile

logger = logging.getLogger(__name__)

#: The most keys one sweep deletes; the rest wait for the next cycle.
MAX_DELETES_PER_SWEEP = 50

#: Profile ids looked up per `IN` query.
_LOOKUP_CHUNK = 500

_REPLAY_KEY = re.compile(r"^replays/(\d+)/(\d+)\.zip$")


@runtime_checkable
class ErasedRecordingStore(Protocol):
    """The two `ObjectStore` methods the sweep calls. A store without both is not swept."""

    async def list_keys(self, prefix: str = "") -> list[str]: ...
    async def delete(self, key: str) -> None: ...


async def _pseudonymised(
    session_factory: async_sessionmaker[AsyncSession], profile_ids: set[int]
) -> set[int]:
    """The profile ids among `profile_ids` whose placeholder row exists (condition 3)."""
    found: set[int] = set()
    ordered = sorted(profile_ids)
    async with session_factory() as session:
        for start in range(0, len(ordered), _LOOKUP_CHUNK):
            chunk = ordered[start : start + _LOOKUP_CHUNK]
            placeholders = {pseudonymise_profile(p).pseudonymous_profile_id: p for p in chunk}
            rows = await session.scalars(
                select(AoeProfile.profile_id).where(AoeProfile.profile_id.in_(list(placeholders)))
            )
            found.update(placeholders[placeholder] for placeholder in rows)
        await session.rollback()
    return found


async def sweep_erased_recordings(
    store: ErasedRecordingStore,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    pair_has_row: Callable[[int, int], Awaitable[bool]],
    budget: Budget,
) -> int:
    """Delete the replay objects that conditions 1-3 (module docstring) mark as an erased user's
    leftover; returns how many were deleted. `pair_has_row` is the waiting `FOR SHARE` read
    (`CaptureDrain._pair_has_row`). Stops when `budget` expires. Never raises."""
    deleted = 0
    if budget.expired:
        return 0
    try:
        pairs: list[tuple[int, int, str]] = []
        for key in await store.list_keys("replays/"):
            match = _REPLAY_KEY.match(key)
            if match is not None:
                pairs.append((int(match.group(1)), int(match.group(2)), key))
        erased = await _pseudonymised(session_factory, {profile_id for _, profile_id, _ in pairs})
        for game_id, profile_id, key in pairs:
            if deleted >= MAX_DELETES_PER_SWEEP or budget.expired:
                break
            if profile_id not in erased or await pair_has_row(game_id, profile_id):
                continue
            await store.delete(key)
            deleted += 1
    except Exception as exc:
        logger.warning(
            "erased-recording sweep stopped after %d deletion(s): %s", deleted, type(exc).__name__
        )
    if deleted:
        logger.info("erased-recording sweep deleted %d object(s)", deleted)
    return deleted
