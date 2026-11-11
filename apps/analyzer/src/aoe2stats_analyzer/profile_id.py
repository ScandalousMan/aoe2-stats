"""The profile id an analyzer write puts in `match_analyses.point_of_view_profile_id` or
`retained_recordings.profile_id` (T845, FR-046).

Erasure and the resolution of a third-party objection rewrite those two columns from a person's
profile id to their placeholder (`routers/privacy.py::_pseudonymise_profile_ids`, T843), in the same
transaction that retargets that person's `match_players` rows. The analyzer reads a match's
participants, claims it and fetches a recording over several transactions, so an id it holds may
have been pseudonymised since it was read. `resolve_profile_id` is how every analyzer write of
either column settles that, inside the transaction that writes.

**The lock is the serialisation.** It takes the `match_players` row `(game_id, profile_id)`
`FOR KEY SHARE` and holds it to the caller's commit. Erasure locks the same rows `FOR UPDATE`
(`discover.lock_match_players`), and `FOR UPDATE` conflicts with `FOR KEY SHARE`, so one of two
things happens:

- the analyzer's lock is granted first: erasure waits for the analyzer's commit, and only then
  selects the `retained_recordings` and `match_analyses` rows it rewrites, so it finds the row the
  analyzer committed;
- erasure commits first: the row now has a different key. A `SELECT ... FOR KEY SHARE` that was
  waiting on it re-evaluates its `WHERE` against the updated row under READ COMMITTED and returns
  nothing, and a `SELECT` that starts afterwards finds no such row. Either way the original id is
  gone, the placeholder's row `(game_id, -abs(profile_id))` exists, and that is the id written.

**Lock order.** The lock comes before any `match_analyses` or `retained_recordings` row the
transaction locks or writes, as the global order in `apps/ingester/.../discover.py` requires
(`aoe_profiles`, `match_players`, then those two tables, then `replay_captures`). A caller calls
this first in its transaction.

**Neither row exists:** the id is not a participant of that match under either name, and writing it
would store an id that joins to nothing. It raises `LookupError`.

The object key of a retained row is not derived from the resolved id: it embeds the id the caller
passed (`retained_recording_object_key`), as it does for every retained row, so a row retained
after an erasure carries the original id in its key (constitution IV).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_core.privacy.erasure import pseudonymise_profile
from aoe2stats_storage.models import MatchPlayer


async def _lock_match_player(session: AsyncSession, *, game_id: int, profile_id: int) -> bool:
    result = await session.execute(
        select(MatchPlayer.profile_id)
        .where(MatchPlayer.game_id == game_id, MatchPlayer.profile_id == profile_id)
        .with_for_update(key_share=True)
    )
    return result.scalar_one_or_none() is not None


async def resolve_profile_id(session: AsyncSession, *, game_id: int, profile_id: int) -> int:
    """The id to write for `profile_id` in `game_id`, with its `match_players` row locked
    `FOR KEY SHARE` in `session`'s transaction (module docstring): `profile_id` itself while that
    row exists, otherwise the placeholder `pseudonymise_profile` names while that row exists.
    Raises `LookupError` when neither does."""
    if await _lock_match_player(session, game_id=game_id, profile_id=profile_id):
        return profile_id
    placeholder = pseudonymise_profile(profile_id).pseudonymous_profile_id
    if placeholder != profile_id and await _lock_match_player(
        session, game_id=game_id, profile_id=placeholder
    ):
        return placeholder
    raise LookupError(
        f"no match_players row for game_id={game_id} under profile_id={profile_id} "
        f"or its placeholder {placeholder}"
    )
