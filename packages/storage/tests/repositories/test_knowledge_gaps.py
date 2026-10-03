"""Integration tests for `aoe2stats_storage.repositories.knowledge_gaps.KnowledgeGapsRepository`
(T652; FR-039; contracts/knowledge-base.md's "Gaps"/"Aggregate";
specs/006-replay-analysis-foundations/data-model.md §7).

`analysis_knowledge_gaps` is created by T663's revision (`53375d9435fc`), so these tests run
against the real migrated-to-head schema like every other integration test in this package.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import (
    AnalysisGapCause,
    AnalysisGapSeverity,
    AnalysisKnowledgeGap,
    Match,
)
from aoe2stats_storage.repositories.knowledge_gaps import (
    NO_BUILD,
    WHOLE_BUILD_ENTITY_ID,
    WHOLE_BUILD_ENTITY_KIND,
    WHOLE_BUILD_FIELD,
    GapToRecord,
    KnowledgeGapsRepository,
)

# Re-exported so ruff sees these names used and pytest discovers each imported fixture exactly as
# if it had been defined here — the same convention `test_captures.py` and `test_matches.py` use.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_LEADERBOARD_ID = 3


@pytest.fixture
async def gaps_session(db_session: AsyncSession) -> AsyncSession:
    """The clean, migrated database's session — kept as a named fixture so the tests below read
    as they did when the table had to be created by hand (T652, before T663's revision)."""
    return db_session


async def _seed_match(session: AsyncSession, *, game_id: int) -> None:
    """Only `matches` needs seeding: `analysis_knowledge_gaps.game_id` is a foreign key straight
    to `matches.game_id`, with no participant, profile or Steam identity anywhere in this table's
    own columns (data-model.md §7: "a participant is not a column") — there is nothing else this
    row's own foreign key requires."""
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=_LEADERBOARD_ID,
            completed_at=datetime(2026, 9, 1, tzinfo=UTC),
            source="relic",
            raw_payload={},
        )
    )
    await session.flush()


def _make_gap(
    *,
    game_id: int,
    identity_digest: str,
    build: int,
    cause: AnalysisGapCause,
    severity: AnalysisGapSeverity,
    entity_id: str,
    field_name: str,
    recorded_at: datetime,
    civilisation_id: str | None = None,
) -> AnalysisKnowledgeGap:
    return AnalysisKnowledgeGap(
        game_id=game_id,
        identity_digest=identity_digest,
        build=build,
        entity_kind="unit",
        entity_id=entity_id,
        field=field_name,
        civilisation_id=civilisation_id,
        cause=cause,
        severity=severity,
        recorded_at=recorded_at,
    )


async def test_gap_rate_groups_by_build_cause_and_severity(gaps_session: AsyncSession) -> None:
    """FR-039: two blocking `field-absent` gaps at build 101 collapse into one count of 2; a
    third, differently-caused gap at the same build is its own group."""
    await _seed_match(gaps_session, game_id=1)
    now = datetime(2026, 9, 15, tzinfo=UTC)
    gaps_session.add_all(
        [
            _make_gap(
                game_id=1,
                identity_digest="analysis-a",
                build=101,
                cause=AnalysisGapCause.FIELD_ABSENT,
                severity=AnalysisGapSeverity.BLOCKING,
                entity_id="unit-1",
                field_name="cost",
                recorded_at=now,
            ),
            _make_gap(
                game_id=1,
                identity_digest="analysis-a",
                build=101,
                cause=AnalysisGapCause.FIELD_ABSENT,
                severity=AnalysisGapSeverity.BLOCKING,
                entity_id="unit-2",
                field_name="cost",
                recorded_at=now,
            ),
            _make_gap(
                game_id=1,
                identity_digest="analysis-b",
                build=101,
                cause=AnalysisGapCause.CIVILISATION_NOT_MODELLED,
                severity=AnalysisGapSeverity.INFORMATIONAL,
                entity_id="unit-3",
                field_name="cost",
                civilisation_id="Tatars",
                recorded_at=now,
            ),
        ]
    )
    await gaps_session.commit()

    repository = KnowledgeGapsRepository(gaps_session)
    rows = await repository.gap_rate(
        window_start=now - timedelta(days=1), window_end=now + timedelta(days=1)
    )

    by_group = {(row.build, row.cause, row.severity): row.count for row in rows}
    assert by_group == {
        (101, AnalysisGapCause.FIELD_ABSENT, AnalysisGapSeverity.BLOCKING): 2,
        (101, AnalysisGapCause.CIVILISATION_NOT_MODELLED, AnalysisGapSeverity.INFORMATIONAL): 1,
    }


async def test_gap_rate_separates_groups_across_builds(gaps_session: AsyncSession) -> None:
    """The same cause and severity at two different builds are two groups, never merged — this is
    exactly the signal that makes a patch-introduced pattern visible."""
    await _seed_match(gaps_session, game_id=2)
    now = datetime(2026, 9, 15, tzinfo=UTC)
    gaps_session.add_all(
        [
            _make_gap(
                game_id=2,
                identity_digest="analysis-c",
                build=101,
                cause=AnalysisGapCause.ENTITY_ABSENT,
                severity=AnalysisGapSeverity.BLOCKING,
                entity_id="building-1",
                field_name="cost",
                recorded_at=now,
            ),
            _make_gap(
                game_id=2,
                identity_digest="analysis-d",
                build=102,
                cause=AnalysisGapCause.ENTITY_ABSENT,
                severity=AnalysisGapSeverity.BLOCKING,
                entity_id="building-1",
                field_name="cost",
                recorded_at=now,
            ),
        ]
    )
    await gaps_session.commit()

    repository = KnowledgeGapsRepository(gaps_session)
    rows = await repository.gap_rate(
        window_start=now - timedelta(days=1), window_end=now + timedelta(days=1)
    )

    by_group = {(row.build, row.cause, row.severity): row.count for row in rows}
    assert by_group == {
        (101, AnalysisGapCause.ENTITY_ABSENT, AnalysisGapSeverity.BLOCKING): 1,
        (102, AnalysisGapCause.ENTITY_ABSENT, AnalysisGapSeverity.BLOCKING): 1,
    }


async def test_gap_rate_excludes_rows_outside_the_window(gaps_session: AsyncSession) -> None:
    """A gap recorded before `window_start` or at/after `window_end` contributes to no group —
    the window bounds are `[window_start, window_end)`, half-open at the end."""
    await _seed_match(gaps_session, game_id=3)
    window_start = datetime(2026, 9, 10, tzinfo=UTC)
    window_end = datetime(2026, 9, 20, tzinfo=UTC)
    gaps_session.add_all(
        [
            _make_gap(
                game_id=3,
                identity_digest="analysis-before",
                build=101,
                cause=AnalysisGapCause.EFFECT_NOT_MODELLED,
                severity=AnalysisGapSeverity.INFORMATIONAL,
                entity_id="unit-1",
                field_name="cost",
                civilisation_id="Byzantines",
                recorded_at=window_start - timedelta(seconds=1),
            ),
            _make_gap(
                game_id=3,
                identity_digest="analysis-at-end",
                build=101,
                cause=AnalysisGapCause.EFFECT_NOT_MODELLED,
                severity=AnalysisGapSeverity.INFORMATIONAL,
                entity_id="unit-1",
                field_name="cost",
                civilisation_id="Byzantines",
                recorded_at=window_end,
            ),
            _make_gap(
                game_id=3,
                identity_digest="analysis-inside",
                build=101,
                cause=AnalysisGapCause.EFFECT_NOT_MODELLED,
                severity=AnalysisGapSeverity.INFORMATIONAL,
                entity_id="unit-1",
                field_name="cost",
                civilisation_id="Byzantines",
                recorded_at=window_start,
            ),
        ]
    )
    await gaps_session.commit()

    repository = KnowledgeGapsRepository(gaps_session)
    rows = await repository.gap_rate(window_start=window_start, window_end=window_end)

    by_group = {(row.build, row.cause, row.severity): row.count for row in rows}
    assert by_group == {
        (101, AnalysisGapCause.EFFECT_NOT_MODELLED, AnalysisGapSeverity.INFORMATIONAL): 1,
    }


async def test_gap_rate_is_empty_when_nothing_was_recorded_in_the_window(
    gaps_session: AsyncSession,
) -> None:
    now = datetime(2026, 9, 15, tzinfo=UTC)
    repository = KnowledgeGapsRepository(gaps_session)

    rows = await repository.gap_rate(
        window_start=now - timedelta(days=1), window_end=now + timedelta(days=1)
    )

    assert rows == []


async def test_the_unique_constraint_rejects_a_reproduced_analysis_recording_the_same_gap_twice(
    gaps_session: AsyncSession,
) -> None:
    """data-model.md §7: "Unique on (identity_digest, entity_kind, entity_id, field,
    civilisation_id), so a reproduced analysis records nothing twice." The same analysis identity
    recording the identical gap a second time — the exact shape a re-run against unchanged inputs
    produces — is rejected by the database itself, not by application logic that might be
    bypassed."""
    await _seed_match(gaps_session, game_id=4)
    now = datetime(2026, 9, 15, tzinfo=UTC)
    gaps_session.add(
        _make_gap(
            game_id=4,
            identity_digest="analysis-e",
            build=101,
            cause=AnalysisGapCause.FIELD_ABSENT,
            severity=AnalysisGapSeverity.BLOCKING,
            entity_id="unit-1",
            field_name="cost",
            recorded_at=now,
        )
    )
    await gaps_session.commit()

    gaps_session.add(
        _make_gap(
            game_id=4,
            identity_digest="analysis-e",
            build=101,
            cause=AnalysisGapCause.FIELD_ABSENT,
            severity=AnalysisGapSeverity.BLOCKING,
            entity_id="unit-1",
            field_name="cost",
            recorded_at=now + timedelta(minutes=1),
        )
    )
    with pytest.raises(IntegrityError):
        await gaps_session.flush()
    # A failed flush leaves the session's transaction unusable until rolled back — the same rule
    # `test_ratings.py`'s own equivalent test applies, since the `db_session` fixture's teardown
    # still needs a session it can commit.
    await gaps_session.rollback()


# --- T662: recording the gaps, insert-or-ignore ---------------------------------------------------


def _gap(
    *,
    entity_id: str = "unit-1",
    field_name: str = "cost",
    civilisation_id: str | None = None,
    cause: str = "field-absent",
    severity: str = "blocking",
    build: int = 101,
) -> GapToRecord:
    return GapToRecord(
        build=build,
        entity_kind="unit",
        entity_id=entity_id,
        field=field_name,
        civilisation_id=civilisation_id,
        cause=cause,
        severity=severity,
    )


async def _stored(session: AsyncSession) -> list[AnalysisKnowledgeGap]:
    result = await session.execute(select(AnalysisKnowledgeGap).order_by(AnalysisKnowledgeGap.id))
    return list(result.scalars())


async def test_record_gaps_inserts_one_row_per_gap(gaps_session: AsyncSession) -> None:
    await _seed_match(gaps_session, game_id=10)
    repository = KnowledgeGapsRepository(gaps_session)

    inserted = await repository.record_gaps(
        game_id=10,
        identity_digest="digest-a",
        gaps=[_gap(entity_id="1"), _gap(entity_id="2", civilisation_id="Franks")],
    )

    assert inserted == 2
    rows = await _stored(gaps_session)
    assert [(row.entity_id, row.civilisation_id) for row in rows] == [("1", None), ("2", "Franks")]
    assert {row.identity_digest for row in rows} == {"digest-a"}
    assert {row.cause for row in rows} == {AnalysisGapCause.FIELD_ABSENT}
    assert {row.severity for row in rows} == {AnalysisGapSeverity.BLOCKING}


async def test_a_second_identical_record_adds_zero_rows_and_raises_nothing(
    gaps_session: AsyncSession,
) -> None:
    """T662: a reproduced or re-run analysis records nothing twice. Both a gap with a civilisation
    and one with none — the case a plain unique constraint would let through, NULL being unequal to
    NULL — are ignored the second time."""
    await _seed_match(gaps_session, game_id=11)
    repository = KnowledgeGapsRepository(gaps_session)
    gaps = [_gap(entity_id="1", civilisation_id="Franks"), _gap(entity_id="2")]
    await repository.record_gaps(game_id=11, identity_digest="digest-a", gaps=gaps)
    before = await _stored(gaps_session)

    inserted = await repository.record_gaps(game_id=11, identity_digest="digest-a", gaps=gaps)

    assert inserted == 0
    after = await _stored(gaps_session)
    assert [row.id for row in after] == [row.id for row in before]


async def test_a_different_identity_records_its_own_rows_and_leaves_the_old_ones_alone(
    gaps_session: AsyncSession,
) -> None:
    """FR-042: history is not rewritten. The same gaps under a new identity digest are new rows;
    the old identity's rows keep their ids and their recording time."""
    await _seed_match(gaps_session, game_id=12)
    repository = KnowledgeGapsRepository(gaps_session)
    gaps = [_gap(entity_id="1"), _gap(entity_id="2", civilisation_id="Franks")]
    await repository.record_gaps(game_id=12, identity_digest="digest-old", gaps=gaps)
    old = [(row.id, row.recorded_at) for row in await _stored(gaps_session)]

    inserted = await repository.record_gaps(game_id=12, identity_digest="digest-new", gaps=gaps)

    assert inserted == 2
    rows = await _stored(gaps_session)
    assert [(row.id, row.recorded_at) for row in rows if row.identity_digest == "digest-old"] == old
    assert sum(1 for row in rows if row.identity_digest == "digest-new") == 2


async def test_record_gaps_with_nothing_to_record_writes_nothing(
    gaps_session: AsyncSession,
) -> None:
    await _seed_match(gaps_session, game_id=13)

    inserted = await KnowledgeGapsRepository(gaps_session).record_gaps(
        game_id=13, identity_digest="digest-a", gaps=[]
    )

    assert inserted == 0
    assert await _stored(gaps_session) == []


async def test_the_no_build_sentinel_is_a_negative_number_no_real_build_can_be() -> None:
    assert NO_BUILD == -1
    assert (WHOLE_BUILD_ENTITY_KIND, WHOLE_BUILD_ENTITY_ID, WHOLE_BUILD_FIELD) == (
        "build",
        "*",
        "*",
    )
