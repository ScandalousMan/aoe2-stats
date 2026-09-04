"""Retention of the recording an analysis was derived from (T363), FR-033/FR-048, R9, and
`data-model.md`'s `retained_recordings` section.

`apps/analyzer/tests/test_retain.py` (T362) is this module's specification, written first. Two
functions, one table:

- `retain_recording` — idempotent per `(game_id, profile_id)`, mirroring `replay_object_key`'s own
  idempotence (`packages/storage/src/aoe2stats_storage/objects.py`). The first call for a pair
  computes the sha256, uploads the bytes under `retained_recording_object_key(game_id, profile_id)`
  — a prefix distinct from `replay_object_key`'s, so the two kinds of object can never resolve to
  the same key for the same pair — and inserts the row. Every later call for the same pair, whatever
  drove it (a recompute, a parser version change, a second analysis request), finds the existing row
  first and returns it unchanged: no second upload, no delete, no update. That lookup-before-write
  is *how* "never deleted by a recompute or a parser change" becomes a property of the write path
  itself rather than a promise nobody enforces elsewhere.
- `retrieve_recording` — downloads the object under the row's own `object_key` and recomputes its
  sha256 against `RetainedRecording.zip_sha256`, raising `RecordingIntegrityError` rather than
  handing back bytes nothing has checked. `zip_sha256` is recorded once, at retention, and verified
  on every retrieval afterwards.

**Retains for an own match too.** A match this service already holds as a `replay_captures` row
(001's capture, under the owning user's explicit consent) still gets its own, second
`retained_recordings` row and object the first time someone asks for it to be analysed. The two
objects hold the same bytes under two different legal bases and two different lifetimes — the
capture is deleted when its owner erases (constitution IV's one exception), the retained recording
is not (constitution IX, amended 2026-08-24) — so reading the capture and retaining nothing would
leave a published analysis unrecomputable the first time that capture's owner erases. This module
does not special-case that path: `retain_recording` never reads `replay_captures`, so an own match
and a third party's match go through the exact same call, which is what makes the own-match case a
consequence of the code rather than a branch someone could have skipped.

Neither function deletes anything, ever — there is no delete call anywhere in this module. Erasure
of the requester and pseudonymisation of a person appearing in the recording are both handled
entirely by the tables they touch (`users.id` cascading via `requested_by_user_id`'s own
`ondelete="SET NULL"`, `match_players.profile_id` elsewhere): `retained_recordings` carries no
foreign key to either `aoe_profiles` or `match_players` (`data-model.md`, R9), precisely so neither
act can reach this table at all.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import RetainedRecording
from aoe2stats_storage.objects import ObjectStore, retained_recording_object_key


class RecordingIntegrityError(Exception):
    """Raised by `retrieve_recording` when the object read back does not hash to
    `RetainedRecording.zip_sha256` — bit rot or an out-of-band tamper. Bytes nothing has checked
    are never handed back silently."""


async def _existing_row(
    session: AsyncSession, *, game_id: int, profile_id: int
) -> RetainedRecording | None:
    result = await session.execute(
        select(RetainedRecording).where(
            RetainedRecording.game_id == game_id,
            RetainedRecording.profile_id == profile_id,
        )
    )
    return result.scalar_one_or_none()


async def retain_recording(
    session: AsyncSession,
    object_store: ObjectStore,
    *,
    game_id: int,
    profile_id: int,
    zip_bytes: bytes,
    requested_by_user_id: UUID | None = None,
) -> RetainedRecording:
    """Retain `zip_bytes` as the recording for `(game_id, profile_id)`, or return the row already
    retained for that pair, unchanged.

    Looks the row up **before** touching the object store: a pair already retained performs no
    upload at all, which is what makes a recompute's or a parser change's re-derivation from
    already-retained bytes cost nothing here beyond the lookup, and never risk a second, divergent
    write to the object the row's checksum was computed against.

    `requested_by_user_id` is recorded only on the row's first write, matching
    `retained_recordings.requested_by_user_id`'s own meaning — who caused the *first* retention,
    never who caused a later read (that is `replay_access_log.retained_recording_id`'s job,
    T365).
    """
    existing = await _existing_row(session, game_id=game_id, profile_id=profile_id)
    if existing is not None:
        return existing

    object_key = retained_recording_object_key(game_id, profile_id)
    zip_sha256 = hashlib.sha256(zip_bytes).hexdigest()
    await object_store.put(object_key, zip_bytes)

    retained = RetainedRecording(
        game_id=game_id,
        profile_id=profile_id,
        object_key=object_key,
        zip_bytes=len(zip_bytes),
        zip_sha256=zip_sha256,
        requested_by_user_id=requested_by_user_id,
    )
    session.add(retained)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race against a concurrent caller retaining the same pair: `game_id, profile_id`
        # is unique, and the other caller's insert committed first. Both uploads targeted the
        # same deterministic key with the same bytes, so nothing here is inconsistent — read the
        # winner's row back and return it, the same idempotence `replay_object_key`'s callers
        # (capture, manual upload) already rely on for their own dedup.
        await session.rollback()
        winner = await _existing_row(session, game_id=game_id, profile_id=profile_id)
        if winner is None:  # pragma: no cover - defensive: the conflict just proved a row exists
            raise
        return winner

    await session.refresh(retained)
    return retained


async def retrieve_recording(
    session: AsyncSession,
    object_store: ObjectStore,
    *,
    game_id: int,
    profile_id: int,
) -> bytes:
    """Return the bytes retained for `(game_id, profile_id)`, verified against the sha256 recorded
    at retention. Raises `RecordingIntegrityError` on a mismatch rather than handing back bytes
    nothing has checked.
    """
    row = await _existing_row(session, game_id=game_id, profile_id=profile_id)
    if row is None:
        raise LookupError(
            f"no retained_recordings row for game_id={game_id}, profile_id={profile_id}"
        )

    data = await object_store.get(row.object_key)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != row.zip_sha256:
        raise RecordingIntegrityError(
            f"checksum mismatch for {row.object_key!r}: row records {row.zip_sha256}, "
            f"object store holds {actual_sha256}"
        )
    return data
