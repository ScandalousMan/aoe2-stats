"""Integration test for quickstart scenario 2 (T042): "Nothing happens without consent".

Targets the discovery stage T053 ships in `aoe2stats_ingester.discover` — not implemented yet at
this point in the sequence, hence the module-level `pytestmark` below. The module is imported
*inside* the test body rather than at module scope, per this project's test-first convention: a
missing module at import time must fail one test, not take the whole `apps/ingester/tests`
collection down with it.

The requirement under test (quickstart.md scenario 2, FR-034, and the part of FR-016 that is
easiest to get wrong): a user who never granted ingestion consent must produce zero
`replay_captures` rows and zero requests to the replay endpoint recorded in `provider_calls` after
a cycle. "Consent must be a condition of the query that selects work, not a branch somewhere
downstream — a branch can be bypassed by a new code path, a `WHERE` clause cannot."

A downstream branch and a selecting `WHERE` clause are indistinguishable by inspecting rows alone
— both can honestly produce zero `replay_captures` rows. What tells them apart is whether the
*provider* is ever reached for the declined user's profile at all: a branch has to call the
provider (or at least run enough of the pipeline to reach a point after the call) before it can
decide to discard the result, whereas a `WHERE` clause never selects the row as work in the first
place. `_RaisingMatchHistoryProvider` below turns that distinction into an assertion: it raises
the instant it is asked about the declined user's profile, so this test fails loudly at the first
line of code that would prove the branch shape instead of the query shape.

A second, *consenting* user is seeded alongside the declined one so a discovery stage that simply
does nothing for anybody cannot pass this test for the wrong reason: the assertions below require
the consenting user's profile to actually have been requested.

**Assumed contract**, since none of this exists yet and this test is what defines it for T053:

- `aoe2stats_ingester.discover.DiscoverStage(*, session_factory, match_history_provider,
  capture_budget_days)` — a `Stage` (`aoe2stats_ingester.run.Stage`) constructed directly against a
  `session_factory` and a `MatchHistoryProvider` (`contracts/providers.md`), exactly as this
  package's own `run.py` docstring describes T053 doing ("build one against ... session_factory").
  `capture_budget_days` is passed as a plain `int`, not a full `Settings` object: nothing here
  needs `DATABASE_URL`, S3 credentials or a cron secret, and `budget.py` already sets the
  precedent of a narrow, single-purpose constructor argument over threading the whole application
  settings object through a module that does not need most of it.
- `MatchHistoryProvider.recent_matches(profile_ids)` per `contracts/providers.md`, batched.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_storage.models import (
    AoeProfile,
    ProfileLink,
    ProviderCall,
    ReplayCapture,
    SteamIdentity,
    User,
)

pytestmark = pytest.mark.xfail(strict=True, reason="T053 not implemented yet")


class _RaisingMatchHistoryProvider:
    """A `MatchHistoryProvider` stand-in (`contracts/providers.md`) that records every profile it
    is asked about, and raises immediately if that profile belongs to a user who never consented.

    Raising from inside the fake, rather than merely asserting on its recorded calls afterwards,
    is the point: it proves the forbidden profile was never even handed to the provider, which is
    what "no code path downstream can reach the provider" (T042) actually means. A downstream
    branch that discarded the *result* of a call would still have made the call, and would trip
    this before ever getting the chance to discard anything.
    """

    def __init__(self, forbidden_profile_ids: set[int]) -> None:
        self._forbidden = forbidden_profile_ids
        self.requested_profile_ids: list[int] = []

    async def recent_matches(self, profile_ids):
        for profile_id in profile_ids:
            assert profile_id not in self._forbidden, (
                f"MatchHistoryProvider.recent_matches was called with profile_id={profile_id}, "
                "which belongs to a user who declined ingestion consent. The consent condition "
                "must be part of the query that selects work, not a branch downstream of a "
                "provider call that has already happened (quickstart.md scenario 2, FR-034)."
            )
        self.requested_profile_ids.extend(profile_ids)
        # No matches for anyone: nothing left for discovery to upsert or enqueue either way, so
        # a bug here cannot manufacture a `replay_captures` row for the consenting profile and
        # mask a leak on the declined one.
        return []


async def _seed_linked_user(
    db_session: AsyncSession, *, profile_id: int, consented: bool
) -> uuid.UUID:
    """Insert a fully linked user — `users`, `steam_identities`, `aoe_profiles`,
    `profile_links` — and commit, exactly the shape discovery's own query walks. The only
    difference between the two users this test seeds is `ingest_consent_at`; everything else
    (allowlisted, a primary linked profile) is identical, so a leak cannot be explained by
    anything but the consent column itself.
    """
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    steam_id64 = f"76561198{profile_id:010d}"

    db_session.add(
        User(
            id=user_id,
            created_at=now,
            allowlisted_at=now,
            ingest_consent_at=now if consented else None,
        )
    )
    db_session.add(
        SteamIdentity(
            steam_id64=steam_id64,
            user_id=user_id,
            verified_at=now,
            last_sign_in_at=now,
        )
    )
    db_session.add(
        AoeProfile(
            profile_id=profile_id,
            alias=f"player-{profile_id}",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db_session.add(
        ProfileLink(
            id=uuid.uuid4(),
            user_id=user_id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
        )
    )
    # Committed here, mid-test, rather than left for the fixture's own teardown: the discovery
    # stage below opens its *own* session through `session_factory`, a separate connection from
    # `db_session` — an uncommitted insert on this one is invisible to that one until this runs
    # (the same discipline `apps/api/tests/test_consent.py`'s `_seed_signed_in_user` applies for
    # its own two-session setup).
    await db_session.commit()
    return user_id


async def test_declined_consent_produces_no_captures_and_no_replay_provider_calls(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """quickstart.md scenario 2: decline consent, trigger a cycle, expect zero `replay_captures`
    rows and zero requests to the replay endpoint in `provider_calls` — proven here by showing the
    declined user's profile is never even handed to the match-history provider, let alone the
    replay one (FR-034, and the easiest-to-get-wrong part of FR-016)."""
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    declined_profile_id = 100_000_001
    consenting_profile_id = 100_000_002
    await _seed_linked_user(db_session, profile_id=declined_profile_id, consented=False)
    await _seed_linked_user(db_session, profile_id=consenting_profile_id, consented=True)

    provider = _RaisingMatchHistoryProvider(forbidden_profile_ids={declined_profile_id})
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=provider,
        capture_budget_days=21,
    )

    await stage(Budget(seconds=60))

    # The declined profile was never requested, and the consenting one was — proving the
    # exclusion is the consent condition and not a discovery stage that quietly does nothing for
    # anybody, which would pass the assertion inside the fake for the wrong reason.
    assert provider.requested_profile_ids == [consenting_profile_id]

    async with session_factory() as session:
        capture_count = await session.scalar(select(func.count()).select_from(ReplayCapture))
        assert capture_count == 0

        replay_endpoint_calls = await session.scalar(
            select(func.count())
            .select_from(ProviderCall)
            .where(ProviderCall.endpoint.ilike("%replay%"))
        )
        assert replay_endpoint_calls == 0

        # No provider was reached for *any* purpose on this run — the match-history provider is
        # a fake that writes no `provider_calls` row of its own, so an empty table here also
        # confirms discovery made no other, unaccounted-for outbound attempt.
        total_provider_calls = await session.scalar(select(func.count()).select_from(ProviderCall))
        assert total_provider_calls == 0
