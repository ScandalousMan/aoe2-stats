"""Integration tests for `aoe2stats_storage.repositories.knowledge_gaps.KnowledgeGapsRepository`
(T652; FR-039; contracts/knowledge-base.md's "Gaps"/"Aggregate";
specs/006-replay-analysis-foundations/data-model.md §7).

`analysis_knowledge_gaps` is not created by any applied migration yet — T663 adds it, in the same
single additive revision that adds `match_analyses.identity_digest`. Every other integration test
in this package (`test_captures.py`, `test_matches.py`, `test_ratings.py`) runs against the real
migrated-to-head schema and never creates a table itself; this one is the first that has to, since
its own table postdates the migrations this session's throwaway database was built from. See
`gaps_session` below for exactly how, and `tests/db.py`'s own `clean_database` for the companion
fix T652 needed to keep every *other* integration test green in the meantime (a model landing in
`Base.metadata` a whole phase before its migration must not make the shared truncate-before-each-
test fixture fail on a table that does not exist yet).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import (
    AnalysisGapCause,
    AnalysisGapSeverity,
    AnalysisKnowledgeGap,
    Base,
    Match,
)
from aoe2stats_storage.repositories.knowledge_gaps import KnowledgeGapsRepository

# Re-exported so ruff sees these names used and pytest discovers each imported fixture exactly as
# if it had been defined here — the same convention `test_captures.py` and `test_matches.py` use.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_LEADERBOARD_ID = 3


@pytest.fixture
async def gaps_session(engine: AsyncEngine, db_session: AsyncSession) -> AsyncSession:
    """`db_session` alone is not enough here: the throwaway database `tests/db.py` builds is
    migrated to `head` through the real Alembic migrations (`_migrate_to_head`), and
    `analysis_knowledge_gaps` has no migration yet (T663's job). This fixture creates exactly that
    one table directly from the ORM model — `checkfirst=True` so a second test in this module does
    not try to create it twice — the same "assert against the schema the ORM defines, not a live
    database" idea `packages/storage/tests/test_models.py`'s own module docstring already states,
    applied here against a real database instead of only against `Base.metadata` in memory, because
    this test needs to actually insert and query rows, which a structural, no-database test cannot
    do.

    Requesting `db_session` as a parameter (rather than only `engine`) is what guarantees
    `clean_database` has already run — and, since T652's fix to it, already tolerated this table's
    absence — before this fixture creates it; creating it first would risk `clean_database` finding
    the table on the *next* test in the module before its own truncation query could plan around a
    schema that legitimately changed size mid-session, which is not a real risk here (`CREATE
    TABLE IF NOT EXISTS` behind `checkfirst=True` is idempotent) but is the ordering this fixture
    keeps explicit anyway.
    """
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all, tables=[AnalysisKnowledgeGap.__table__], checkfirst=True
        )
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
