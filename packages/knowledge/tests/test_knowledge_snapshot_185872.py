"""T707: a build 185872 recording's identifiers resolve to names through `query.name`.

Production, 2026-10-08, match 511523321 (game build 185872, `tests/fixtures/replays/README.md`):
the analysis named no knowledge snapshot because only build 180059 had a promoted one, so
`snapshot_for(185872)` answered a `no-snapshot-for-build` gap. This file is what stays true once
`aoe2techtree-185872` exists: `query.name` resolves, from the snapshot imported from the pack
revision whose commit names the build, and nothing the snapshot does not model is invented for it.
It does not say an analysis shows those names: as of 2026-10-08 none did, for any build (T709).
"""

from __future__ import annotations

import pytest

from aoe2stats_knowledge import gaps, query, snapshot

_BUILD = 185872

#: The pack revision whose commit message names this build (`snapshot.toml`'s validation record).
_SOURCE_COMMIT = "3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f"


def test_the_build_resolves_to_its_own_promoted_snapshot() -> None:
    resolved = snapshot.snapshot_for(_BUILD)

    assert isinstance(resolved, snapshot.Snapshot), (
        f"build {_BUILD} resolved to a gap: {resolved!r}"
    )
    assert resolved.promoted
    assert resolved.identity.describes_build == _BUILD
    assert resolved.identity.source_version == _SOURCE_COMMIT


@pytest.mark.parametrize(
    ("kind", "entity_id", "expected"),
    [
        ("technology", "101", "Feudal Age"),
        ("technology", "102", "Castle Age"),
        ("building", "70", "House"),
    ],
)
def test_the_names_of_the_ids_a_recording_carries_resolve_for_the_build(
    kind: str, entity_id: str, expected: str
) -> None:
    answer = query.name(query.EntityRef(kind=kind, id=entity_id, build=_BUILD))

    assert not isinstance(answer, gaps.KnowledgeGap), f"gap: {answer!r}"
    assert answer.value == expected
    assert answer.snapshot_identity.describes_build == _BUILD


#: The first build 185872 snapshot's digest (`aoe2techtree-185872/snapshot.toml`), which the second
#: names as the one it supersedes (T746). A promoted snapshot is never edited (FR-025), so modelling
#: civilisations for the build could not be done in it.
_SUPERSEDED_DIGEST = "sha256:1c77d7cb5034b48dcb15641370512854a222d5f7d40baaa6129fb1b1c56fca5a"

#: The raw civilisation ids the committed build 185872 recording seats (Slavs, Sicilians) and the
#: six `aoe2techtree-180059` models (Franks, Teutons, Persians, Saracens, Malians, Tatars).
_MODELLED_RAW_IDS = {
    2: "Franks",
    4: "Teutons",
    8: "Persians",
    9: "Saracens",
    23: "Slavs",
    26: "Malians",
    33: "Tatars",
    37: "Sicilians",
}


def _first_snapshot() -> snapshot.Snapshot:
    (first,) = (s for s in snapshot.load_all_snapshots() if s.identity.digest == _SUPERSEDED_DIGEST)
    return first


def test_the_build_resolves_to_the_snapshot_that_supersedes_the_first() -> None:
    resolved = snapshot.snapshot_for(_BUILD)

    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.promoted
    assert resolved.supersedes == _SUPERSEDED_DIGEST
    assert resolved.identity.digest != _SUPERSEDED_DIGEST
    assert resolved.identity.describes_build == _BUILD
    assert resolved.identity.source_version == _SOURCE_COMMIT
    assert resolved.directory != _first_snapshot().directory


def test_the_first_snapshot_stays_loadable_by_identity_and_models_no_civilisation() -> None:
    """SC-005: the analysis published under it must still reproduce, so it is never deleted and
    never edited. Pinned, it answers as it always did: every civilisation is a gap."""
    first = _first_snapshot()
    assert first.promoted
    assert first.supersedes is None

    with snapshot.pinned_snapshot(first):
        result = query.cost(
            query.EntityRef(kind="building", id="70", build=_BUILD), civilisation="Franks"
        )

    assert isinstance(result, gaps.KnowledgeGap)
    assert result.cause == "civilisation-not-modelled"
    assert result.build == _BUILD


def test_the_current_snapshot_models_the_scoped_civilisations_and_only_those() -> None:
    """Raw ids 23 and 37 (the recording's seats) and the six 180059 models; 5, 10, 49 and 51 stay
    the aggregate gap report's backlog (research.md D5)."""
    from aoe2stats_knowledge import effects

    current = snapshot.snapshot_for(_BUILD)
    assert isinstance(current, snapshot.Snapshot)

    assert dict(effects.civilisation_id_names(current.directory)) == _MODELLED_RAW_IDS
    for out_of_scope in (5, 10, 49, 51):
        assert out_of_scope not in effects.civilisation_id_names(current.directory)


def test_a_modelled_civilisation_answers_and_an_unmodelled_one_still_refuses() -> None:
    entity = query.EntityRef(kind="building", id="84", build=_BUILD)

    modelled = query.cost(entity, civilisation="Saracens")
    unmodelled = query.cost(entity, civilisation="Britons")

    assert not isinstance(modelled, gaps.KnowledgeGap), f"gap: {modelled!r}"
    assert modelled.value == {"wood": 75}
    assert isinstance(unmodelled, gaps.KnowledgeGap)
    assert unmodelled.cause == "civilisation-not-modelled"
    assert unmodelled.build == _BUILD


def test_the_older_snapshot_is_untouched_by_the_new_one() -> None:
    old = snapshot.snapshot_for(180059)
    assert isinstance(old, snapshot.Snapshot)
    assert old.identity.source_version == "b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0"
    assert query.name(query.EntityRef(kind="technology", id="101", build=180059)).value == (
        "Feudal Age"
    )
