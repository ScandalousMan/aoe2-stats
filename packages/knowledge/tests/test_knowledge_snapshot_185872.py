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
_FIRST_DIGEST = "sha256:1c77d7cb5034b48dcb15641370512854a222d5f7d40baaa6129fb1b1c56fca5a"

#: The second snapshot's digest (`aoe2techtree-185872-civilisations/snapshot.toml`, T746), which the
#: third, `aoe2techtree-185872-civilisations-20`, names as the one it supersedes (T767).
_SECOND_DIGEST = "sha256:becd35a158dafb72c304aeb07bae66347b4442f62d209d8cedb23d0c1f34f004"

#: The third snapshot's digest (`aoe2techtree-185872-civilisations-20/snapshot.toml`, T767), which
#: the fourth, `aoe2techtree-185872-civilisations-32`, names as the one it supersedes (T768).
_THIRD_DIGEST = "sha256:a4f213b6e84f90ee88a916929a136165c3979f214a191556877669dd0a92b4db"

#: The fourth snapshot's digest (`aoe2techtree-185872-civilisations-32/snapshot.toml`, T768), which
#: the fifth, `aoe2techtree-185872-civilisations-44`, names as the one it supersedes (T769).
_FOURTH_DIGEST = "sha256:c24448836cade9ff724ac32935a52280a447df7278cb8cfe3f7cecd58dbf37ae"

#: The fifth snapshot's digest (`aoe2techtree-185872-civilisations-44/snapshot.toml`, T769), which
#: the sixth, `aoe2techtree-185872-civilisations-56`, names as the one it supersedes (T770). Build
#: 185872 now has a chain of six: resolution answers the last, and the first five stay loadable
#: by identity.
_FIFTH_DIGEST = "sha256:93d084ea8886b4c2d98f67a7f02524f107ffab3c3bcb29142389ceac226dc263"

#: Every replay-space civilisation id of `aoc-reference-data`'s `civilizations` table (read again
#: 2026-10-22, T767) whose name is a civilisation of the vendored pack: 56 of the dataset's 62
#: entries. The six it holds that the pack does not (46 Achaemenids, 47 Athenians, 48 Spartans,
#: 54 Macedonians, 55 Thracians, 56 Puru) are the Chronicles civilisations, outside the pack and
#: outside this snapshot (out of scope, T776). The dataset spells id 16 "Maya", the pack "Mayans".
_RAW_IDS = {
    1: "Britons",
    2: "Franks",
    3: "Goths",
    4: "Teutons",
    5: "Japanese",
    6: "Chinese",
    7: "Byzantines",
    8: "Persians",
    9: "Saracens",
    10: "Turks",
    11: "Vikings",
    12: "Mongols",
    13: "Celts",
    14: "Spanish",
    15: "Aztecs",
    16: "Mayans",
    17: "Huns",
    18: "Koreans",
    19: "Italians",
    20: "Hindustanis",
    21: "Incas",
    22: "Magyars",
    23: "Slavs",
    24: "Portuguese",
    25: "Ethiopians",
    26: "Malians",
    27: "Berbers",
    28: "Khmer",
    29: "Malay",
    30: "Burmese",
    31: "Vietnamese",
    32: "Bulgarians",
    33: "Tatars",
    34: "Cumans",
    35: "Lithuanians",
    36: "Burgundians",
    37: "Sicilians",
    38: "Poles",
    39: "Bohemians",
    40: "Dravidians",
    41: "Bengalis",
    42: "Gurjaras",
    43: "Romans",
    44: "Armenians",
    45: "Georgians",
    49: "Shu",
    50: "Wu",
    51: "Wei",
    52: "Jurchens",
    53: "Khitans",
    57: "Muisca",
    58: "Mapuche",
    59: "Tupi",
    60: "Saxons",
    61: "Varangians",
    62: "Danes",
}

#: The fifty-six civilisations batch D models (T770), every civilisation of the pack: the forty-four
#: of the fifth snapshot (T746's eight and batches A to C) and the twelve it adds.
_MODELLED = sorted(
    [
        "Franks",
        "Teutons",
        "Persians",
        "Saracens",
        "Malians",
        "Tatars",
        "Slavs",
        "Sicilians",
        "Britons",
        "Goths",
        "Japanese",
        "Chinese",
        "Byzantines",
        "Turks",
        "Vikings",
        "Mongols",
        "Celts",
        "Spanish",
        "Aztecs",
        "Mayans",
        "Huns",
        "Koreans",
        "Italians",
        "Hindustanis",
        "Incas",
        "Magyars",
        "Portuguese",
        "Ethiopians",
        "Berbers",
        "Khmer",
        "Malay",
        "Burmese",
        "Vietnamese",
        "Bulgarians",
        "Cumans",
        "Lithuanians",
        "Burgundians",
        "Poles",
        "Bohemians",
        "Dravidians",
        "Bengalis",
        "Gurjaras",
        "Romans",
        "Armenians",
        "Georgians",
        "Shu",
        "Wu",
        "Wei",
        "Jurchens",
        "Khitans",
        "Muisca",
        "Mapuche",
        "Tupi",
        "Saxons",
        "Varangians",
        "Danes",
    ]
)


def _snapshot_by_digest(digest: str) -> snapshot.Snapshot:
    (found,) = (s for s in snapshot.load_all_snapshots() if s.identity.digest == digest)
    return found


def test_the_build_resolves_to_the_sixth_snapshot_of_its_chain() -> None:
    resolved = snapshot.snapshot_for(_BUILD)

    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.promoted
    assert resolved.directory == "aoe2techtree-185872-civilisations-56"
    assert resolved.supersedes == _FIFTH_DIGEST
    assert resolved.identity.digest not in (
        _FIRST_DIGEST,
        _SECOND_DIGEST,
        _THIRD_DIGEST,
        _FOURTH_DIGEST,
        _FIFTH_DIGEST,
    )
    assert resolved.identity.describes_build == _BUILD
    assert resolved.identity.source_version == _SOURCE_COMMIT
    third = _snapshot_by_digest(_THIRD_DIGEST)
    assert third.supersedes == _SECOND_DIGEST
    assert third.directory == "aoe2techtree-185872-civilisations-20"
    assert _snapshot_by_digest(_SECOND_DIGEST).supersedes == _FIRST_DIGEST
    fourth = _snapshot_by_digest(_FOURTH_DIGEST)
    assert fourth.supersedes == _THIRD_DIGEST
    assert fourth.directory == "aoe2techtree-185872-civilisations-32"
    fifth = _snapshot_by_digest(_FIFTH_DIGEST)
    assert fifth.supersedes == _FOURTH_DIGEST
    assert fifth.directory == "aoe2techtree-185872-civilisations-44"
    assert resolved.directory != fifth.directory


def test_the_first_snapshot_stays_loadable_by_identity_and_models_no_civilisation() -> None:
    """SC-005: the analysis published under it must still reproduce, so it is never deleted and
    never edited. Pinned, it answers as it always did: every civilisation is a gap."""
    first = _snapshot_by_digest(_FIRST_DIGEST)
    assert first.promoted
    assert first.supersedes is None

    with snapshot.pinned_snapshot(first):
        result = query.cost(
            query.EntityRef(kind="building", id="70", build=_BUILD), civilisation="Franks"
        )

    assert isinstance(result, gaps.KnowledgeGap)
    assert result.cause == "civilisation-not-modelled"
    assert result.build == _BUILD


def test_the_second_snapshot_stays_loadable_by_identity_and_models_eight_civilisations() -> None:
    """SC-005 for the link T767 superseded: pinned by identity, it still models the eight
    civilisations of T746 and nothing else, and answers its own bytes."""
    second = _snapshot_by_digest(_SECOND_DIGEST)
    assert second.promoted
    assert second.directory == "aoe2techtree-185872-civilisations"
    assert second.identity.describes_build == _BUILD

    entity = query.EntityRef(kind="building", id="70", build=_BUILD)
    with snapshot.pinned_snapshot(second):
        modelled = query.cost(entity, civilisation="Malians")
        unmodelled = query.cost(entity, civilisation="Britons")

    assert not isinstance(modelled, gaps.KnowledgeGap), f"gap: {modelled!r}"
    assert modelled.snapshot_identity.digest == _SECOND_DIGEST
    assert isinstance(unmodelled, gaps.KnowledgeGap)
    assert unmodelled.cause == "civilisation-not-modelled"


def test_the_third_snapshot_stays_loadable_by_identity_and_models_twenty_civilisations() -> None:
    """SC-005 for the link T768 superseded: pinned by identity, it still models the twenty
    civilisations of T746 and T767 and nothing else, and answers its own bytes."""
    third = _snapshot_by_digest(_THIRD_DIGEST)
    assert third.promoted
    assert third.directory == "aoe2techtree-185872-civilisations-20"
    assert third.identity.describes_build == _BUILD

    entity = query.EntityRef(kind="building", id="84", build=_BUILD)
    with snapshot.pinned_snapshot(third):
        modelled = query.cost(entity, civilisation="Britons")
        unmodelled = query.cost(entity, civilisation="Huns")

    assert not isinstance(modelled, gaps.KnowledgeGap), f"gap: {modelled!r}"
    assert modelled.snapshot_identity.digest == _THIRD_DIGEST
    assert isinstance(unmodelled, gaps.KnowledgeGap)
    assert unmodelled.cause == "civilisation-not-modelled"


def test_the_fourth_snapshot_stays_loadable_by_identity_and_models_thirty_two_civilisations() -> (
    None
):
    """SC-005 for the link T769 superseded: pinned by identity, it still models the thirty-two
    civilisations of T746, T767 and T768 and nothing else, and answers its own bytes."""
    fourth = _snapshot_by_digest(_FOURTH_DIGEST)
    assert fourth.promoted
    assert fourth.directory == "aoe2techtree-185872-civilisations-32"
    assert fourth.identity.describes_build == _BUILD

    entity = query.EntityRef(kind="building", id="84", build=_BUILD)
    with snapshot.pinned_snapshot(fourth):
        modelled = query.cost(entity, civilisation="Huns")
        unmodelled = query.cost(entity, civilisation="Vietnamese")

    assert not isinstance(modelled, gaps.KnowledgeGap), f"gap: {modelled!r}"
    assert modelled.snapshot_identity.digest == _FOURTH_DIGEST
    assert isinstance(unmodelled, gaps.KnowledgeGap)
    assert unmodelled.cause == "civilisation-not-modelled"


def test_the_fifth_snapshot_stays_loadable_by_identity_and_models_forty_four_civilisations() -> (
    None
):
    """SC-005 for the link T770 superseded: pinned by identity, it still models the forty-four
    civilisations of T746 and batches A to C and nothing else, and answers its own bytes."""
    fifth = _snapshot_by_digest(_FIFTH_DIGEST)
    assert fifth.promoted
    assert fifth.directory == "aoe2techtree-185872-civilisations-44"
    assert fifth.identity.describes_build == _BUILD

    entity = query.EntityRef(kind="building", id="84", build=_BUILD)
    with snapshot.pinned_snapshot(fifth):
        modelled = query.cost(entity, civilisation="Vietnamese")
        unmodelled = query.cost(entity, civilisation="Georgians")

    assert not isinstance(modelled, gaps.KnowledgeGap), f"gap: {modelled!r}"
    assert modelled.snapshot_identity.digest == _FIFTH_DIGEST
    assert isinstance(unmodelled, gaps.KnowledgeGap)
    assert unmodelled.cause == "civilisation-not-modelled"


def test_the_current_snapshot_models_fifty_six_civilisations_and_names_every_pack_one() -> None:
    """T770: batch D models fifty-six civilisations, the whole pack; its `[[civilisation_id]]`
    table (T767's, carried) names all 56 of the pack, from `aoc-reference-data`'s keys, so every raw
    id of the pack resolves to its name, and a Chronicles civilisation's is not in it."""
    from aoe2stats_knowledge import effects

    current = snapshot.snapshot_for(_BUILD)
    assert isinstance(current, snapshot.Snapshot)

    assert dict(effects.civilisation_id_names(current.directory)) == _RAW_IDS
    assert sorted(query._civilisations_modelled(current.directory)) == _MODELLED
    for chronicles_id in (46, 47, 48, 54, 55, 56):
        assert chronicles_id not in effects.civilisation_id_names(current.directory)


def test_a_modelled_civilisation_answers_and_an_unmodelled_one_still_refuses() -> None:
    entity = query.EntityRef(kind="building", id="84", build=_BUILD)

    modelled = query.cost(entity, civilisation="Saracens")
    newly_modelled = query.cost(entity, civilisation="Georgians")
    # Every civilisation of the pack is modelled now; a Chronicles civilisation is in no pack.
    unmodelled = query.cost(entity, civilisation="Achaemenids")

    assert not isinstance(modelled, gaps.KnowledgeGap), f"gap: {modelled!r}"
    assert modelled.value == {"wood": 75}
    assert not isinstance(newly_modelled, gaps.KnowledgeGap), f"gap: {newly_modelled!r}"
    assert newly_modelled.value == {"wood": 175}
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
