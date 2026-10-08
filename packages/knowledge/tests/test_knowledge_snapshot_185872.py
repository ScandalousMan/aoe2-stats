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


def test_the_build_models_no_civilisation_so_a_cost_is_a_gap_not_a_baseline() -> None:
    """research.md D5: the 180059 civilisation effects are not carried across a major update no one
    has read the notes of, so a civilisation-qualified cost refuses (FR-023) - for a civilisation
    the 180059 snapshot does model, too."""
    entity = query.EntityRef(kind="building", id="70", build=_BUILD)

    result = query.cost(entity, civilisation="Franks")

    assert isinstance(result, gaps.KnowledgeGap)
    assert result.cause == "civilisation-not-modelled"
    assert result.build == _BUILD


def test_the_older_snapshot_is_untouched_by_the_new_one() -> None:
    old = snapshot.snapshot_for(180059)
    assert isinstance(old, snapshot.Snapshot)
    assert old.identity.source_version == "b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0"
    assert query.name(query.EntityRef(kind="technology", id="101", build=180059)).value == (
        "Feudal Age"
    )
