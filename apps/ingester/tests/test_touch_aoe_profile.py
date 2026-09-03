"""T452 — `discover.touch_aoe_profile` must persist a real alias/country, not only the
`str(profile_id)` placeholder it writes today (FR-007, partial).

**The defect this closes.** Every player `DiscoverStage`/the on-demand third-party history route
(`apps/api/src/aoe2stats_api/routers/players.py`) meets for the first time gets an `aoe_profiles`
row whose `alias` is the numeric id, never the real name — `touch_aoe_profile`'s `ON CONFLICT DO
UPDATE` sets only `last_seen_at`, so that placeholder never gets replaced, and a viewed third-party
profile shows the numeric id forever (the exact production defect T447's SC-004 walk found). This
task widens `touch_aoe_profile` to accept an optional real `alias`/`country` and persist them —
**but the direction matters more than the write**: once a row holds a real alias, a later sighting
that carries no alias (a plain discovery cycle, still calling this function with none — T453 is
what teaches a caller to pass one) must never overwrite that real alias back to the placeholder.
That inversion is the one an implementer under pressure gets backwards, so it is asserted below as
its own test, not folded into the "replace" case as an afterthought.

**Written test-first.** `touch_aoe_profile` exists today but takes only `(session, profile_id)`;
every call below that passes `alias=`/`country=` keywords failed with a `TypeError` until T452
widened the signature — those three tests carried `@pytest.mark.xfail(strict=True, reason="T452
not implemented yet")` until the implementation made them pass for real, at which point
`strict=True` turned the run red and forced the marker off (the same discipline `test_relic_matches
.py` established). The one test that never carried the marker is the no-alias case: it calls
`touch_aoe_profile` exactly as `DiscoverStage.__call__` does today and already passed before T452
— see its own docstring. `aoe2stats_ingester.discover` is imported inside each test body rather
than at module scope — the same convention `test_favourite_no_capture.py` and `test_reconcile.py`
already use — so a signature mismatch would have been this file's own expected failure, not a
collection error for the whole `apps/ingester/tests` suite.

**Backward compatibility is a separate, already-green property.** `DiscoverStage.__call__` and
`apps/api/src/aoe2stats_api/routers/players.py`'s `_refresh_third_party_history` both call
`touch_aoe_profile(session, profile_id)` with no alias/country today, and every existing ingester
integration test that exercises them (`test_shared_match.py`, `test_capture_objection.py`,
`test_favourite_no_capture.py`, `test_reconcile.py`) keeps passing unmodified once T452 lands,
because the new parameters default to `None` — this file adds coverage for the widened surface, it
does not replace the coverage those files already carry for the unchanged one.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import AoeProfile

#: Arbitrary profile ids, distinct from every other `apps/ingester/tests` file's own range (see
#: e.g. `test_reconcile.py`'s `900_1xx`/`900_2xx`/`900_4xx`) so a `clean_database`-scoped run never
#: collides across files sharing the one throwaway database within a session.
_FIRST_SIGHT_WITH_ALIAS_PROFILE_ID = 901_100
_FIRST_SIGHT_NO_ALIAS_PROFILE_ID = 901_101
_LATER_SIGHT_REPLACES_PLACEHOLDER_PROFILE_ID = 901_102
_LATER_SIGHT_NEVER_CLOBBERS_PROFILE_ID = 901_103


async def _fetch(db_session: AsyncSession, profile_id: int) -> AoeProfile:
    """`populate_existing=True`: `build_session_factory` (`repositories/base.py`) sets
    `expire_on_commit=False` deliberately, for production's own reason (a value read right after a
    commit must stay readable with no implicit re-fetch) — but that same setting means a second
    `touch_aoe_profile` call against a row this same session already loaded would otherwise hand
    back the identity map's stale copy here, not the row `touch_aoe_profile` just wrote. Every
    test below calls `touch_aoe_profile` more than once against the same `profile_id`, so this
    forces the ORM to overwrite that cached copy from the database on every fetch.
    """
    result = await db_session.execute(
        select(AoeProfile)
        .where(AoeProfile.profile_id == profile_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def test_first_sight_with_a_real_alias_and_country_is_stored(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_ingester.discover import touch_aoe_profile

    profile_id = _FIRST_SIGHT_WITH_ALIAS_PROFILE_ID
    await touch_aoe_profile(db_session, profile_id, alias="Azhague33", country="FR")
    await db_session.commit()

    stored = await _fetch(db_session, profile_id)
    assert stored.alias == "Azhague33"
    assert stored.country == "FR"


async def test_first_sight_with_no_alias_stores_the_placeholder_and_null_country(
    db_session: AsyncSession,
) -> None:
    """Not `xfail`: this is the already-green backward-compatible call — `DiscoverStage.__call__`
    and `_refresh_third_party_history` supply neither `alias` nor `country` today, and this
    exact call already stores the placeholder before T452 as well as after it. It stays here,
    unmarked, precisely so a T452 implementation that breaks the unchanged path turns this test
    red rather than merely `xfail`.
    """
    from aoe2stats_ingester.discover import touch_aoe_profile

    profile_id = _FIRST_SIGHT_NO_ALIAS_PROFILE_ID
    # No alias/country supplied at all — the exact call `DiscoverStage.__call__` and
    # `_refresh_third_party_history` make today, and must keep making unchanged.
    await touch_aoe_profile(db_session, profile_id)
    await db_session.commit()

    stored = await _fetch(db_session, profile_id)
    assert stored.alias == str(profile_id)
    assert stored.country is None


async def test_a_later_sight_with_a_real_alias_replaces_the_placeholder_and_sets_country(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_ingester.discover import touch_aoe_profile

    profile_id = _LATER_SIGHT_REPLACES_PLACEHOLDER_PROFILE_ID
    # First sight: no real alias yet, exactly as an ordinary discovery cycle leaves it today.
    await touch_aoe_profile(db_session, profile_id)
    await db_session.commit()
    first_seen = await _fetch(db_session, profile_id)
    assert first_seen.alias == str(profile_id)
    original_first_seen_at = first_seen.first_seen_at

    # A later sighting — the on-view identity refresh (T453) — now knows the real name.
    await touch_aoe_profile(db_session, profile_id, alias="Viper", country="BY")
    await db_session.commit()

    stored = await _fetch(db_session, profile_id)
    assert stored.alias == "Viper"
    assert stored.country == "BY"
    # `first_seen_at` is untouched by a conflict update — only `last_seen_at` moves on a repeat
    # sighting (the property `ON CONFLICT DO UPDATE` already preserved before this task).
    assert stored.first_seen_at == original_first_seen_at
    assert stored.last_seen_at >= original_first_seen_at


async def test_a_later_sight_with_no_real_alias_never_clobbers_an_existing_real_alias(
    db_session: AsyncSession,
) -> None:
    """The inversion this task exists to get right: once a row holds a real alias, a later
    sighting that carries none — or, equivalently, the `str(profile_id)` placeholder itself —
    must leave that real alias exactly as it was. An ordinary discovery cycle still calls
    `touch_aoe_profile` with no alias at all (T453 has not wired a real one through yet), so this
    is also the property that keeps that unmodified caller from regressing a name T452's own new
    capability, or a later on-view refresh, already established.
    """
    from aoe2stats_ingester.discover import touch_aoe_profile

    profile_id = _LATER_SIGHT_NEVER_CLOBBERS_PROFILE_ID
    # The row already holds a real alias — as if T453's on-view refresh had already run once.
    await touch_aoe_profile(db_session, profile_id, alias="TheViper", country="BY")
    await db_session.commit()
    real_alias_seen_at = (await _fetch(db_session, profile_id)).last_seen_at

    # An ordinary discovery cycle re-touches the same profile with no alias at all — the exact
    # call `DiscoverStage.__call__` makes for every participant of every match it discovers.
    await touch_aoe_profile(db_session, profile_id)
    await db_session.commit()

    stored = await _fetch(db_session, profile_id)
    assert stored.alias == "TheViper", "a real alias must never be clobbered by the placeholder"
    assert stored.country == "BY"
    assert stored.last_seen_at >= real_alias_seen_at

    # Passing the placeholder string itself explicitly (equivalent to "no real alias") must be
    # just as inert as passing none at all.
    now_placeholder = str(profile_id)
    await touch_aoe_profile(db_session, profile_id, alias=now_placeholder)
    await db_session.commit()

    stored_again = await _fetch(db_session, profile_id)
    assert stored_again.alias == "TheViper"
