"""T709: `query.name_in_snapshot` - a name looked up in the snapshot a document's identity names.

Real, packaged snapshots throughout (builds 177723, 180059 and 185872), never a stub: the question
is what the shipped tables say. The contrast cases are the ones FR-027 is about: an identity no
loaded snapshot has must name nothing, even for a build that has a promoted snapshot, and the
digest alone does not identify a snapshot - `aoe2techtree-177723-test` and `aoe2techtree-180059`
carry one digest under two builds.
"""

from __future__ import annotations

import dataclasses

import pytest

from aoe2stats_knowledge import gaps, query, snapshot


def _identity(build: int) -> snapshot.SnapshotIdentity:
    resolved = snapshot.snapshot_for(build)
    assert isinstance(resolved, snapshot.Snapshot)
    return resolved.identity


def _answer(kind: str, entity_id: str, identity: snapshot.SnapshotIdentity) -> query.Answer[str]:
    answer = query.name_in_snapshot(kind, entity_id, identity)
    assert isinstance(answer, query.Answer), answer
    return answer


@pytest.mark.parametrize("build", [180059, 185872])
def test_a_snapshots_own_identity_names_feudal_castle_and_house(build: int) -> None:
    identity = _identity(build)

    assert _answer("technology", "101", identity).value == "Feudal Age"
    assert _answer("technology", "102", identity).value == "Castle Age"
    assert _answer("building", "70", identity).value == "House"
    assert _answer("unit", "83", identity).value == "Villager"


def test_the_answer_carries_the_matched_snapshots_identity_and_source() -> None:
    identity = _identity(185872)

    answer = _answer("technology", "101", identity)

    assert answer.snapshot_identity == identity
    assert answer.source != "unresolved"
    assert answer.effects == ()


def test_an_id_the_snapshot_does_not_name_is_the_unresolved_answer_name_gives() -> None:
    identity = _identity(185872)

    for kind in ("technology", "unit", "building"):
        answer = _answer(kind, "987654321", identity)
        assert answer.value == "987654321"
        assert answer.source == "unresolved"
        assert answer == query.name(query.EntityRef(kind=kind, id="987654321", build=185872))


def test_the_name_is_returned_as_vendored() -> None:
    """The pack's line-break markup is the caller's presentation concern, not the query's."""
    identity = _identity(185872)

    assert _answer("building", "109", identity).value == "Town<br>\nCenter"
    assert _answer("technology", "1404", identity).value == "Circum-<br>\nnavigation"


def test_it_answers_exactly_what_name_answers_for_the_promoted_snapshot() -> None:
    identity = _identity(185872)
    entity = query.EntityRef(kind="technology", id="102", build=185872)

    assert query.name_in_snapshot("technology", "102", identity) == query.name(entity)


@pytest.mark.parametrize(
    "changed",
    [
        {"digest": "sha256:" + "ab" * 32},
        {"source_version": "0" * 40},
        {"source": "another-source"},
        {"describes_build": 999_999},
    ],
    ids=["digest", "source_version", "source", "describes_build"],
)
def test_one_differing_identity_field_names_nothing(changed: dict[str, object]) -> None:
    """All four fields must match: an identity that differs in any one is a different snapshot,
    and the build's own promoted snapshot is never substituted for it."""
    identity = dataclasses.replace(_identity(185872), **changed)

    answer = query.name_in_snapshot("technology", "101", identity)

    assert isinstance(answer, gaps.KnowledgeGap)
    assert answer.cause == "no-snapshot-for-build"
    assert answer.build == identity.describes_build
    assert answer.detail is not None
    assert identity.digest in answer.detail


def test_two_snapshots_that_share_a_digest_are_told_apart_by_the_rest_of_the_identity() -> None:
    """`aoe2techtree-177723-test` and `aoe2techtree-180059` carry one digest. The digest alone
    answers for whichever is found first; the full identity answers for the one asked for."""
    old = next(s for s in snapshot.load_all_snapshots() if s.identity.describes_build == 177723)
    new = _identity(180059)
    assert old.identity.digest == new.digest

    assert _answer("technology", "101", old.identity).snapshot_identity == old.identity
    assert _answer("technology", "101", new).snapshot_identity == new
    crossed = dataclasses.replace(new, describes_build=555_555)
    assert isinstance(query.name_in_snapshot("technology", "101", crossed), gaps.KnowledgeGap)


def test_an_unpromoted_snapshot_is_answerable_by_its_own_identity() -> None:
    """A document recorded under a snapshot a refresh has since demoted must stay readable."""
    unpromoted = next(s for s in snapshot.load_all_snapshots() if not s.promoted)

    answer = query.name_in_snapshot("technology", "101", unpromoted.identity)

    assert isinstance(answer, query.Answer)
    assert answer.snapshot_identity == unpromoted.identity


def test_the_ids_apps_api_tests_treat_as_unnamed_are_unnamed_in_every_snapshot() -> None:
    """`apps/api/tests/test_analysis_routes.py` serves these three as its "outside the snapshot"
    ids; this is where that premise is held."""
    for loaded in snapshot.load_all_snapshots():
        for kind, entity_id in (
            ("technology", "987654321"),
            ("unit", "987654322"),
            ("building", "987654323"),
        ):
            assert _answer(kind, entity_id, loaded.identity).source == "unresolved"
