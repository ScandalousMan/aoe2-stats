"""T765 (SC-007b, FR-022a, FR-022b): the whole-pack coverage test.

**What it asserts.** For each build's *current* snapshot (resolved by `snapshot.snapshot_for`, so a
superseded snapshot is skipped by the library and never by a label written here), and for each
civilisation that snapshot's `rules.json` lists, it asks every entity the snapshot names or aliases
(`rules.json`'s three entity kinds plus `Snapshot.aliases`) for every field the coverage pass asks
about (`coverage._QUERY_SURFACE_FUNCTIONS`, which a test below checks against the register's
required fields), through the public query surface with **no** context. A query that
raises `effects.ContextRequired` is a modelled conditional effect and counts as no gap, exactly as
the coverage pass counts it (contracts/knowledge-base.md, "Civilisation qualification"; T652u). A
gap is blocking by the classification `gaps.KnowledgeGap.severity` already computes from the
register (research.md D7), never by a rule written here. Nothing is sampled: every entity is asked,
for every civilisation, so a gap anywhere in a pack is found.

**The expectation, per civilisation.** The set of blocking gaps must equal, exactly, that
civilisation's open rows in `specs/006-replay-analysis-foundations/owner-readings.md`
(FR-022b: a closed list, and "the list lives with the test that asserts it"); for build 185872 the
list is empty since T772. The rows are held
here as literal tuples in `_OPEN_ROWS`, not parsed from the markdown, and each Phase 8 batch edits
them by hand. **Tuple shape**: `(entity_kind, entity_id, field, cause)`, all four strings, exactly
the `KnowledgeGap` columns of the same names. A sheet row that names a class of entities ("Archer
line", "each building Fortifications names") is one tuple per member the knowledge base refuses;
the comment above each group says which row it is and what the members are. Set equality catches
both directions: a closed row leaves a tuple unmatched, and a further blocker (a transcription
defect, which FR-022b says must be closed, never listed) leaves an observed tuple unmatched.

**Civilisations not yet modelled.** Each is `xfail(strict=True)`, listed by name per build in
`_NOT_YET_MODELLED`, with a reason naming the batch task that models it. The case fails today
(every query for it gaps with `civilisation-not-modelled`) and passes the moment the civilisation
is modelled, which strict `xfail` turns into a failure: the batch that models the civilisation
deletes its name from the tuple. No `skip`, no `importorskip`.

**Outside the test, by the owner's arbitration (T776).** The application's table
(`apps/api/src/aoe2stats_api/civilizations.py`) names six civilisations no vendored pack carries:
Achaemenids, Athenians, Macedonians, Puru, Spartans and Thracians, the Chronicles civilisations.
`test_the_civilisations_outside_this_test_are_the_six_chronicles_civilisations` measures that set
(the table's names minus every current pack's) rather than trusting this paragraph. T776 ruled them
out of scope (spec Clarifications, Session 2026-10-18), so a seventh civilisation appearing here is
a pack the snapshots have not caught up with, not one more Chronicles civilisation.

**Batch A (T767)** models twenty civilisations on build 185872 in
`aoe2techtree-185872-civilisations-20`; the twelve it added lost their `xfail` and each is held to
its open rows like the eight before them. Persians' Kamandaran is no longer open for that build.

**Batch B (T768)** models thirty-two in `aoe2techtree-185872-civilisations-32`; the twelve it added
lost their `xfail` too. Three of them keep open rows: Magyars' Corvinian Army and Malay's Forced
Levy (the food that replaces a gold cost is stated nowhere) and Berbers' Kasbah (a bonus that needs
a researched technology and the owner's team together, which an effect cannot express). The other
nine have none.

**Batch C (T769)** models forty-four in `aoe2techtree-185872-civilisations-44`; the twelve it added
lost their `xfail`. Four of them keep open rows: Vietnamese and Burgundians (no source says whether
the Town Center's, the Dock's and the Market's technologies are "economic upgrades"), Bohemians (the
food that replaces the gold under Hussite Reforms is stated nowhere: the Monk and eleven
technologies) and Gurjaras (no source lists the Camel and Elephant Units). The other eight have
none: the Cumans' additional Town Center and Cuman Mercenaries are refused, but the fields they gap
are not ones a register datum requires, so their gaps are informational and not blocking.

**Batch D (T770)** models the last twelve in `aoe2techtree-185872-civilisations-56`, so every
civilisation of build 185872 is modelled and no `xfail` is left for it. Two of the twelve keep open
rows: Saxons (no source says whether the ranged foot units are Foot Soldiers) and Jurchens (no
source classes nine of the Jurchens' technologies as Siege or Fortification upgrades). The
Berbers lost theirs: the Kasbah is a `researched` and `team` row now (T781), as the Cumans'
additional Town Center and Cuman Mercenaries are rows (T780, T781).

**Batch T773** models the fifty-three civilisations of build 180059's pack in
`aoe2techtree-180059-civilisations-53`, so no `xfail` is left for build 180059 either. It keeps
the open rows of build 185872 for the bonuses it carries (the Saxons, who are in no build 180059
pack, are not among them); the Persians' Kamandaran is modelled, as in build 185872.

**Batch T772** closes the owner's readings on build 185872 in
`aoe2techtree-185872-owner-readings`, which supersedes `-56`. Every row of the sheet for that build
was answered on 2026-10-31 and none was reported unreadable, so build 185872 keeps no FR-022b entry:
its tuples are gone, the expectation is the empty set for every civilisation of the pack, and
`test_build_185872_keeps_no_fr_022b_entry` says so by name. A blocking gap on that build is a
transcription defect, never an entry. A reading that arrives after the promotion waits for the next
snapshot.

**Builds.** `test_the_current_snapshots_are_the_builds_this_module_covers` fails when the library
resolves a current build this module does not cover, so a new build cannot be added without being
covered. Three builds are covered: 185872, 180059 and 177723. Build 177723's snapshot is the test
infrastructure T646 added (`aoe2techtree-177723-test`, promoted, with `rules.json` and
`effects.toml` byte for byte those of build 180059's first snapshot), so it models the same six
civilisations with the same open row, and no Phase 8 task models the other 47.

**Runtime.** Every case reads `rules.json` through `query._rules`, which is `functools.cache`d per
snapshot directory for the whole session, so the pack is parsed once per build and no fixture is
needed here.
"""

from __future__ import annotations

import pytest

from aoe2stats_api.civilizations import KNOWN_CIVILISATION_NAMES
from aoe2stats_core.truth.register import REGISTER
from aoe2stats_knowledge import coverage, effects, gaps, query, snapshot

#: `(entity_kind, entity_id, field, cause)` - see the module docstring.
type OpenRow = tuple[str, str, str, str]

# ---------------------------------------------------------------------------------------------
# The expectation, edited by hand by each Phase 8 batch.
# ---------------------------------------------------------------------------------------------

# Build 185872's batches, in the order tasks.md files them. A batch deletes its tuple here when it
# models those civilisations (and the snapshot it promotes lists them in civilisations_modelled).
# Batch A (T767) is gone: `aoe2techtree-185872-civilisations-20` models its twelve.
# Batch B (T768) is gone: `aoe2techtree-185872-civilisations-32` models its twelve.
# Batch C (T769) is gone: `aoe2techtree-185872-civilisations-44` models its twelve.
# Batch D (T770) is gone: `aoe2techtree-185872-civilisations-56` models its twelve, and with them
# every civilisation of the pack: no civilisation of build 185872 is left to `xfail`.

# Build 177723 (`aoe2techtree-177723-test`, T646 test infrastructure): promoted, with the same six
# civilisations modelled as build 180059's snapshot, and the other 47 modelled by no task.
_BUILD_177723_UNMODELLED = (
    "Armenians",
    "Aztecs",
    "Bengalis",
    "Berbers",
    "Bohemians",
    "Britons",
    "Bulgarians",
    "Burgundians",
    "Burmese",
    "Byzantines",
    "Celts",
    "Chinese",
    "Cumans",
    "Dravidians",
    "Ethiopians",
    "Georgians",
    "Goths",
    "Gurjaras",
    "Hindustanis",
    "Huns",
    "Incas",
    "Italians",
    "Japanese",
    "Jurchens",
    "Khitans",
    "Khmer",
    "Koreans",
    "Lithuanians",
    "Magyars",
    "Malay",
    "Mapuche",
    "Mayans",
    "Mongols",
    "Muisca",
    "Poles",
    "Portuguese",
    "Romans",
    "Shu",
    "Sicilians",
    "Slavs",
    "Spanish",
    "Tupi",
    "Turks",
    "Vietnamese",
    "Vikings",
    "Wei",
    "Wu",
)


def _reasons(civilisations: tuple[str, ...], reason: str) -> dict[str, str]:
    return dict.fromkeys(civilisations, reason)


#: build -> civilisation -> the reason it is expected to fail today, naming the task that models it.
_NOT_YET_MODELLED: dict[int, dict[str, str]] = {
    185872: {},
    180059: {},
    177723: _reasons(
        _BUILD_177723_UNMODELLED,
        "no Phase 8 task models build 177723 (T646 test infrastructure)",
    ),
}

#: build -> civilisation -> that civilisation's open rows of owner-readings.md, expanded to one
#: tuple per refused entity. Empty is the target (FR-022b).
_OPEN_ROWS: dict[int, dict[str, tuple[OpenRow, ...]]] = {
    # Build 185872 keeps no FR-022b entry (T772): the seventh snapshot,
    # `aoe2techtree-185872-owner-readings`, models every row the owner's readings answered, and no
    # row was reported unreadable. The tuples the batches held (Aztecs, Bohemians, Burgundians,
    # Chinese, Gurjaras, Jurchens, Magyars, Malay, Slavs, Sicilians, Saxons, Turks, Vietnamese) are
    # gone, and a blocking gap on this build is a transcription defect, never an entry.
    185872: {},
    180059: {
        # T773: the open rows of build 185872 that the carried bonuses keep, with the same members:
        # every entity they name is in the build 180059 pack. Measured on the snapshot, not copied.
        # Persians' Kamandaran is modelled here as in build 185872 (carried row); Saxons are in no
        # build 180059 pack.
        "Aztecs": (
            ("unit", "21", "production_time", "effect-not-modelled"),
            ("unit", "125", "production_time", "effect-not-modelled"),
            ("unit", "527", "production_time", "effect-not-modelled"),
            ("unit", "529", "production_time", "effect-not-modelled"),
            ("unit", "532", "production_time", "effect-not-modelled"),
            ("unit", "539", "production_time", "effect-not-modelled"),
            ("unit", "1103", "production_time", "effect-not-modelled"),
            ("unit", "1104", "production_time", "effect-not-modelled"),
            ("unit", "2626", "production_time", "effect-not-modelled"),
            ("unit", "2627", "production_time", "effect-not-modelled"),
            ("unit", "2628", "production_time", "effect-not-modelled"),
            ("unit", "2633", "production_time", "effect-not-modelled"),
        ),
        "Bohemians": (
            ("technology", "45", "cost", "effect-not-modelled"),
            ("technology", "46", "cost", "effect-not-modelled"),
            ("technology", "230", "cost", "effect-not-modelled"),
            ("technology", "231", "cost", "effect-not-modelled"),
            ("technology", "233", "cost", "effect-not-modelled"),
            ("technology", "252", "cost", "effect-not-modelled"),
            ("technology", "316", "cost", "effect-not-modelled"),
            ("technology", "319", "cost", "effect-not-modelled"),
            ("technology", "438", "cost", "effect-not-modelled"),
            ("technology", "439", "cost", "effect-not-modelled"),
            ("technology", "441", "cost", "effect-not-modelled"),
            ("unit", "125", "cost", "effect-not-modelled"),
        ),
        "Burgundians": (
            ("technology", "15", "cost", "effect-not-modelled"),
            ("technology", "17", "cost", "effect-not-modelled"),
            ("technology", "23", "cost", "effect-not-modelled"),
            ("technology", "48", "cost", "effect-not-modelled"),
            ("technology", "65", "cost", "effect-not-modelled"),
            ("technology", "213", "cost", "effect-not-modelled"),
            ("technology", "249", "cost", "effect-not-modelled"),
            ("technology", "906", "cost", "effect-not-modelled"),
        ),
        "Chinese": (
            ("technology", "102", "cost", "effect-not-modelled"),
            ("technology", "103", "cost", "effect-not-modelled"),
        ),
        "Gurjaras": (
            ("unit", "329", "production_time", "effect-not-modelled"),
            ("unit", "330", "production_time", "effect-not-modelled"),
            ("unit", "873", "production_time", "effect-not-modelled"),
            ("unit", "875", "production_time", "effect-not-modelled"),
            ("unit", "1744", "production_time", "effect-not-modelled"),
            ("unit", "1746", "production_time", "effect-not-modelled"),
            ("unit", "1751", "production_time", "effect-not-modelled"),
            ("unit", "1753", "production_time", "effect-not-modelled"),
            ("unit", "1755", "production_time", "effect-not-modelled"),
        ),
        "Jurchens": (
            ("technology", "47", "production_time", "effect-not-modelled"),
            ("technology", "93", "cost", "effect-not-modelled"),
            ("technology", "93", "production_time", "effect-not-modelled"),
            ("technology", "199", "production_time", "effect-not-modelled"),
            ("technology", "200", "production_time", "effect-not-modelled"),
            ("technology", "201", "production_time", "effect-not-modelled"),
            ("technology", "377", "cost", "effect-not-modelled"),
            ("technology", "377", "production_time", "effect-not-modelled"),
            ("technology", "379", "cost", "effect-not-modelled"),
            ("technology", "379", "production_time", "effect-not-modelled"),
            ("technology", "608", "cost", "effect-not-modelled"),
            ("technology", "608", "production_time", "effect-not-modelled"),
            ("technology", "996", "cost", "effect-not-modelled"),
            ("technology", "996", "production_time", "effect-not-modelled"),
        ),
        "Magyars": (
            ("unit", "869", "cost", "effect-not-modelled"),
            ("unit", "871", "cost", "effect-not-modelled"),
        ),
        "Malay": (
            ("unit", "74", "cost", "effect-not-modelled"),
            ("unit", "75", "cost", "effect-not-modelled"),
            ("unit", "77", "cost", "effect-not-modelled"),
            ("unit", "473", "cost", "effect-not-modelled"),
            ("unit", "567", "cost", "effect-not-modelled"),
        ),
        "Sicilians": (
            ("building", "79", "production_time", "effect-not-modelled"),
            ("building", "234", "production_time", "effect-not-modelled"),
            ("building", "235", "production_time", "effect-not-modelled"),
            ("building", "236", "production_time", "effect-not-modelled"),
            ("building", "1251", "production_time", "effect-not-modelled"),
        ),
        "Slavs": (
            ("building", "79", "cost", "effect-not-modelled"),
            ("building", "82", "cost", "effect-not-modelled"),
            ("building", "234", "cost", "effect-not-modelled"),
            ("building", "235", "cost", "effect-not-modelled"),
        ),
        "Turks": (
            ("technology", "10", "cost", "effect-not-modelled"),
            ("technology", "64", "cost", "effect-not-modelled"),
            ("technology", "369", "cost", "effect-not-modelled"),
            ("technology", "376", "cost", "effect-not-modelled"),
            ("unit", "46", "production_time", "effect-not-modelled"),
            ("unit", "557", "production_time", "effect-not-modelled"),
            ("unit", "771", "production_time", "effect-not-modelled"),
            ("unit", "773", "production_time", "effect-not-modelled"),
        ),
        "Vietnamese": (
            ("technology", "15", "production_time", "effect-not-modelled"),
            ("technology", "17", "production_time", "effect-not-modelled"),
            ("technology", "22", "production_time", "effect-not-modelled"),
            ("technology", "23", "production_time", "effect-not-modelled"),
            ("technology", "48", "production_time", "effect-not-modelled"),
            ("technology", "65", "cost", "effect-not-modelled"),
            ("technology", "65", "production_time", "effect-not-modelled"),
            ("technology", "213", "cost", "effect-not-modelled"),
            ("technology", "213", "production_time", "effect-not-modelled"),
            ("technology", "249", "cost", "effect-not-modelled"),
            ("technology", "249", "production_time", "effect-not-modelled"),
            ("technology", "906", "cost", "effect-not-modelled"),
            ("technology", "906", "production_time", "effect-not-modelled"),
        ),
    },
    177723: {
        # Row: Persians / Archer line / cost / Kamandaran researched / "the replacement amount is
        # never stated". Measured on this snapshot, not assumed: the six civilisations it models
        # are Franks, Malians, Persians, Saracens, Tatars and Teutons, and Persians alone keeps
        # blocking gaps, the three Archer-line costs below.
        "Persians": (
            ("unit", "4", "cost", "effect-not-modelled"),
            ("unit", "24", "cost", "effect-not-modelled"),
            ("unit", "492", "cost", "effect-not-modelled"),
        ),
    },
}

# ---------------------------------------------------------------------------------------------
# The measurement.
# ---------------------------------------------------------------------------------------------

#: The fields the coverage pass asks about, each with its public query function. Reused, not
#: re-derived (T765): a field added to the pass is a field asked here.
_FIELDS = tuple(name for name, _ in coverage._QUERY_SURFACE_FUNCTIONS)

#: The register fields the coverage pass leaves out, and why (coverage.py's docstring): `name` is
#: the query that degrades to the bare identifier and never gaps, `line_of_sight` belongs to a
#: different reconstruction domain.
_NOT_ASKED = frozenset({"name", "line_of_sight"})


def _current_snapshot(build: int) -> snapshot.Snapshot:
    resolved = snapshot.snapshot_for(build)
    if isinstance(resolved, gaps.KnowledgeGap):  # pragma: no cover - a defect, reported loudly
        raise RuntimeError(f"build {build} resolves to no snapshot: {resolved}")
    return resolved


def _civilisations(build: int) -> tuple[str, ...]:
    """Every civilisation the build's current snapshot's `rules.json` lists (a list of names in a
    first-version file, a table keyed by name in a second-version one)."""
    return tuple(query._rules(_current_snapshot(build).directory)["civilisations"])


def _entities(build: int) -> tuple[tuple[str, str], ...]:
    """Every entity the build's current snapshot names or aliases, as `(kind, id)`."""
    current = _current_snapshot(build)
    named = {
        (kind, entity_id)
        for kind, table in query._rules(current.directory)["entities"].items()
        for entity_id in table
    }
    aliased = {(alias.kind, alias.id) for alias in current.aliases}
    return tuple(sorted(named | aliased))


def _blocking_gaps(build: int, civilisation: str) -> frozenset[OpenRow]:
    """The blocking gaps of `civilisation` over every entity and every field, with no context."""
    found: set[OpenRow] = set()
    for kind, entity_id in _entities(build):
        entity = query.EntityRef(kind=kind, id=entity_id, build=build)
        for field_name, query_function in coverage._QUERY_SURFACE_FUNCTIONS:
            try:
                answer_or_gap = query_function(entity, civilisation=civilisation)
            except effects.ContextRequired:
                # A modelled conditional effect: complete knowledge, no gap (coverage.py, T652u).
                continue
            if (
                isinstance(answer_or_gap, gaps.KnowledgeGap)
                and answer_or_gap.severity == "blocking"
            ):
                found.add((kind, entity_id, field_name, answer_or_gap.cause))
    return frozenset(found)


def _cases() -> list[object]:
    cases: list[object] = []
    for build in _NOT_YET_MODELLED:
        for civilisation in _civilisations(build):
            reason = _NOT_YET_MODELLED[build].get(civilisation)
            marks = (
                [pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)]
                if reason is not None
                else []
            )
            cases.append(
                pytest.param(build, civilisation, marks=marks, id=f"{build}-{civilisation}")
            )
    return cases


def _render(rows: frozenset[OpenRow], limit: int = 12) -> str:
    """At most `limit` rows: a civilisation not modelled gaps on every entity, and the message
    should say so rather than print thousands of lines."""
    ordered = sorted(rows)
    lines = [f"    {row!r}" for row in ordered[:limit]]
    if len(ordered) > limit:
        lines.append(f"    ... and {len(ordered) - limit} more ({len(ordered)} in all)")
    return "\n".join(lines) or "    (none)"


@pytest.mark.parametrize(("build", "civilisation"), _cases())
def test_a_civilisations_blocking_gaps_are_exactly_its_open_owner_rows(
    build: int, civilisation: str
) -> None:
    observed = _blocking_gaps(build, civilisation)
    expected = frozenset(_OPEN_ROWS.get(build, {}).get(civilisation, ()))
    assert observed == expected, (
        f"build {build}, {civilisation}: blocking gaps differ from the open rows of "
        f"owner-readings.md.\n  unexpected (a gap with no open row, FR-022b: close it, do not "
        f"list it):\n{_render(observed - expected)}\n  unmatched (an open row with no gap, "
        f"delete its tuple):\n{_render(expected - observed)}"
    )


def test_build_185872_keeps_no_fr_022b_entry() -> None:
    """T772: the tuples for build 185872 equal the FR-022b entries by set equality, and there are
    none, so the expectation is empty for every civilisation of the pack and the parametrised case
    above fails on any blocking gap at all."""
    assert not _OPEN_ROWS[185872]
    assert not _NOT_YET_MODELLED[185872]
    current = _current_snapshot(185872)
    assert current.directory == "aoe2techtree-185872-owner-readings"
    for civilisation in _civilisations(185872):
        assert not _blocking_gaps(185872, civilisation), civilisation


def test_the_current_snapshots_are_the_builds_this_module_covers() -> None:
    current = {s.identity.describes_build for s in snapshot.load_current_snapshots()}
    assert current == set(_NOT_YET_MODELLED)
    assert set(_OPEN_ROWS) == set(_NOT_YET_MODELLED)


def test_every_name_the_expectation_holds_is_a_civilisation_of_its_pack() -> None:
    for build in _NOT_YET_MODELLED:
        listed = set(_civilisations(build))
        for table in (
            _NOT_YET_MODELLED[build],
            _OPEN_ROWS[build],
        ):
            assert set(table) <= listed, (build, sorted(set(table) - listed))
        assert not set(_NOT_YET_MODELLED[build]) & set(_OPEN_ROWS[build])


def test_the_fields_asked_are_the_fields_a_register_datum_requires() -> None:
    required = {name for entry in REGISTER for name in entry.requires_knowledge}
    assert set(_FIELDS) == required - _NOT_ASKED


def test_the_civilisations_outside_this_test_are_the_six_chronicles_civilisations() -> None:
    carried: set[str] = set()
    for build in _NOT_YET_MODELLED:
        carried |= set(_civilisations(build))
    outside = set(KNOWN_CIVILISATION_NAMES.values()) - carried
    assert outside == {
        "Achaemenids",
        "Athenians",
        "Macedonians",
        "Puru",
        "Spartans",
        "Thracians",
    }


def test_the_open_rows_are_blocking_gaps_by_the_register_not_by_this_module() -> None:
    """A tuple of `_OPEN_ROWS` is held only if the gap it names really is blocking by the
    register's own classification (research.md D7): the tuple is built into a `KnowledgeGap`, whose
    `severity` the register computes, and that severity must be blocking. A field leaving the
    register's required set turns the row informational, so its tuple fails here instead of going
    stale unseen."""
    for build, by_civilisation in _OPEN_ROWS.items():
        for civilisation, rows in by_civilisation.items():
            for kind, entity_id, field_name, cause in rows:
                gap = gaps.KnowledgeGap(
                    cause=cause,
                    build=build,
                    entity_kind=kind,
                    entity_id=entity_id,
                    field=field_name,
                    civilisation=civilisation,
                )
                assert gap.severity == gaps.BLOCKING, (
                    build,
                    civilisation,
                    kind,
                    entity_id,
                    field_name,
                )


def test_a_field_only_a_blocked_register_datum_requires_is_informational() -> None:
    """The contrast: the check above can fail. `available_to` is required only by a blocked datum,
    so a gap on it is informational, and a tuple naming it would be refused."""
    gap = gaps.KnowledgeGap(
        cause="effect-not-modelled",
        build=185872,
        entity_kind="building",
        entity_id="82",
        field="available_to",
        civilisation="Slavs",
    )
    assert gap.severity == gaps.INFORMATIONAL
