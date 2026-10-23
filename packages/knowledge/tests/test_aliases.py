"""T761 (FR-022d): an entity identifier the pack does not name resolves, through an alias a
referenced source states, to the pack's entity.

contracts/knowledge-base.md, "On disk", "Identity and immutability" and "Entity resolution": a
snapshot may carry `aliases.toml`, one `[[alias]]` per identifier (`kind`, `id`, `target`,
`source_name`, `source`, `read_on`). The loader refuses an alias whose target `rules.json` does not
name, an alias whose own `id` `rules.json` names, two aliases for one identifier, a missing or blank
key, an unknown key and an unknown kind. The digest covers the file when it is present and a
snapshot without one keeps the digest it has. Every rule query and `name` follow an alias to its
target, and `Answer.alias` says that it did.

Every case builds a synthetic snapshot directory under `tmp_path` and points the three readers
(`snapshot`, `query`, `effects`) at it, as `tests/snapshot_refresh.py` does; nothing here touches
the committed tree. The last section reads the committed tree instead: T767's snapshot,
`aoe2techtree-185872-civilisations-20`, carries the first `aliases.toml`, and the cases there say
what it holds and what it does not. Buildings 490 and 673 close for build 185872 only; the strict
gaps for them in `test_coverage.py` stay for build 180059 until T773.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge import effects, query
from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.gaps import KnowledgeGap

_BUILD = 900_001
_EFFECTS_TOML = b"# no effects\n"
_VALIDATION = """
[validation]
method = "second-source"
checked_against = "a test"
performed_by = "a test author"
performed_at = "2026-01-01"
"""

#: Building 487 is the pack's Gate; 490 is the identifier a recording carries that the pack does
#: not name. Unit 74 exists so a kind mismatch has something to be confused with.
_RULES: dict[str, Any] = {
    "civilisations": ["Franks"],
    "entities": {
        "building": {
            "487": {
                "age_requirement": 2,
                "construction_time": 70,
                "cost": {"stone": 30},
                "name": "Gate",
                "produced_at": None,
                "table_origin": "building",
            },
            "12": {
                "age_requirement": 1,
                "construction_time": 50,
                "cost": {"wood": 175},
                "name": "Barracks",
                "produced_at": None,
                "table_origin": "building",
            },
        },
        "unit": {
            "74": {
                "age_requirement": 1,
                "cost": {"food": 50},
                "name": "Militia",
                "produced_at": {"kind": "building", "id": "12"},
                "table_origin": "unit",
                "training_time": 21,
            }
        },
        "technology": {},
    },
}

_GATE_ALIAS = """
[[alias]]
kind = "building"
id = "490"
target = "487"
source_name = "Gate"
source = "aoc-reference-data, objects, dataset 100"
read_on = "2026-10-18"
"""


@dataclass(frozen=True)
class _Installed:
    directory: str
    root: Path


class _ResourcesShim:
    def __init__(self, package_root: Path) -> None:
        self._package_root = package_root

    def files(self, _package: str) -> Path:
        return self._package_root


def _alias_entry(**overrides: str | None) -> str:
    """One `[[alias]]` table; a value of `None` omits the key."""
    values: dict[str, str | None] = {
        "kind": "building",
        "id": "490",
        "target": "487",
        "source_name": "Gate",
        "source": "aoc-reference-data, objects, dataset 100",
        "read_on": "2026-10-18",
    }
    values.update(overrides)
    lines = ["[[alias]]"] + [f'{key} = "{value}"' for key, value in values.items() if value]
    # a blank value is written (not omitted) so a blank key is distinguishable from a missing one
    lines += [f'{key} = ""' for key, value in values.items() if value == ""]
    return "\n".join(lines) + "\n"


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., _Installed]:
    """Install one promoted snapshot of `_BUILD` under a throwaway package root, with an
    `aliases.toml` when `aliases_toml` is given. The digest is computed the way the contract says:
    over `aliases.toml` too when the file is present."""
    package_root = tmp_path / "pkg"
    snapshots = package_root / "snapshots"
    snapshots.mkdir(parents=True)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: snapshots)
    shim = _ResourcesShim(package_root)
    for module in (snapshot_module, query, effects):
        monkeypatch.setattr(module, "resources", shim)

    def _install(
        *,
        aliases_toml: str | None = None,
        rules: dict[str, Any] | None = None,
        digest_over_aliases: bool = True,
    ) -> _Installed:
        # query and effects cache by directory name for the process's life
        directory = f"aliases-{uuid.uuid4().hex[:8]}"
        target = snapshots / directory
        target.mkdir()
        rules_bytes = json.dumps(rules if rules is not None else _RULES).encode("utf-8")
        (target / "rules.json").write_bytes(rules_bytes)
        (target / "effects.toml").write_bytes(_EFFECTS_TOML)
        (target / "disagreements.toml").write_text("# none\n", encoding="utf-8")
        aliases_bytes = None
        if aliases_toml is not None:
            aliases_bytes = aliases_toml.encode("utf-8")
            (target / "aliases.toml").write_bytes(aliases_bytes)
        digest = snapshot_module.compute_digest(
            rules_bytes, _EFFECTS_TOML, aliases_bytes if digest_over_aliases else None
        )
        (target / "snapshot.toml").write_text(
            "\n".join(
                [
                    "[snapshot]",
                    'source = "aoe2techtree"',
                    'source_version = "deadbeef"',
                    f"describes_build = {_BUILD}",
                    f'digest = "{digest}"',
                    "promoted = true",
                    'civilisations_modelled = ["Franks"]',
                ]
            )
            + "\n"
            + _VALIDATION,
            encoding="utf-8",
        )
        return _Installed(directory=directory, root=snapshots)

    return _install


def _ref(kind: str, entity_id: str) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=entity_id, build=_BUILD)


# ------------------------------------------------------------------------------- following it


def test_building_490_answers_building_487s_cost_through_an_alias(
    install: Callable[..., _Installed],
) -> None:
    install(aliases_toml=_GATE_ALIAS)

    answer = query.cost(_ref("building", "490"), civilisation="Franks")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == {"stone": 30}
    assert answer.alias is not None
    assert (answer.alias.kind, answer.alias.id, answer.alias.target) == ("building", "490", "487")
    assert answer.alias.source_name == "Gate"
    assert answer.alias.read_on == "2026-10-18"
    assert answer.source == "building"


def test_name_follows_an_alias_to_its_targets_name(install: Callable[..., _Installed]) -> None:
    install(aliases_toml=_GATE_ALIAS)

    answer = query.name(_ref("building", "490"))

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == "Gate"
    assert answer.alias is not None
    assert answer.alias.target == "487"


@pytest.mark.parametrize(
    ("query_name", "expected"),
    [
        ("cost", {"stone": 30}),
        ("production_time", 70),
        ("age_requirement", 2),
        ("produced_at", ()),
        ("available_to", True),
    ],
)
def test_every_rule_query_follows_the_alias(
    install: Callable[..., _Installed], query_name: str, expected: object
) -> None:
    install(aliases_toml=_GATE_ALIAS)
    ask = getattr(query, query_name)

    aliased = ask(_ref("building", "490"), civilisation="Franks")
    direct = ask(_ref("building", "487"), civilisation="Franks")

    assert not isinstance(aliased, KnowledgeGap)
    assert aliased.value == expected
    assert aliased.value == direct.value
    assert aliased.alias is not None
    assert direct.alias is None


def test_prerequisites_follow_the_alias_before_they_refuse(
    install: Callable[..., _Installed],
) -> None:
    """`prerequisites` always refuses (the packs carry no such field), but an aliased identifier
    reaches that refusal the way a named one does - `field-absent` - and not `entity-absent`."""
    install(aliases_toml=_GATE_ALIAS)

    gap = query.prerequisites(_ref("building", "490"), civilisation="Franks")

    assert isinstance(gap, KnowledgeGap)
    assert gap.cause == "field-absent"
    assert gap.entity_id == "490"


def test_a_gap_after_following_an_alias_still_names_the_asked_identifier(
    install: Callable[..., _Installed],
) -> None:
    install(aliases_toml=_GATE_ALIAS)

    gap = query.cost(_ref("building", "490"), civilisation="Aztecs")

    assert isinstance(gap, KnowledgeGap)
    assert gap.cause == "civilisation-not-modelled"
    assert gap.entity_id == "490"


def test_an_alias_is_only_followed_within_its_own_kind(
    install: Callable[..., _Installed],
) -> None:
    install(aliases_toml=_GATE_ALIAS)

    gap = query.cost(_ref("unit", "490"), civilisation="Franks")

    assert isinstance(gap, KnowledgeGap)
    assert gap.cause == "entity-absent"


def test_an_identifier_no_one_names_stays_a_gap_with_an_alias_table_present(
    install: Callable[..., _Installed],
) -> None:
    install(aliases_toml=_GATE_ALIAS)

    gap = query.cost(_ref("building", "491"), civilisation="Franks")
    unnamed = query.name(_ref("building", "491"))

    assert isinstance(gap, KnowledgeGap)
    assert gap.cause == "entity-absent"
    assert not isinstance(unnamed, KnowledgeGap)
    assert unnamed.value == "491"
    assert unnamed.source == query.UNRESOLVED_SOURCE
    assert unnamed.alias is None


def test_the_loaded_snapshot_carries_its_aliases(install: Callable[..., _Installed]) -> None:
    installed = install(aliases_toml=_GATE_ALIAS)

    loaded = snapshot_module.load_snapshot(installed.directory)

    assert [(a.kind, a.id, a.target) for a in loaded.aliases] == [("building", "490", "487")]
    assert loaded.aliases[0].source == "aoc-reference-data, objects, dataset 100"


# --------------------------------------------------------------------------------- the contrast


def test_an_identifier_rules_json_names_is_not_reported_as_aliased(
    install: Callable[..., _Installed],
) -> None:
    install(aliases_toml=_GATE_ALIAS)

    answer = query.cost(_ref("building", "487"), civilisation="Franks")
    named = query.name(_ref("building", "487"))

    assert not isinstance(answer, KnowledgeGap)
    assert answer.alias is None
    assert not isinstance(named, KnowledgeGap)
    assert named.alias is None


def test_a_snapshot_without_aliases_toml_answers_as_before(
    install: Callable[..., _Installed],
) -> None:
    installed = install()

    answer = query.cost(_ref("building", "487"), civilisation="Franks")
    gap = query.cost(_ref("building", "490"), civilisation="Franks")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == {"stone": 30}
    assert answer.alias is None
    assert isinstance(gap, KnowledgeGap)
    assert gap.cause == "entity-absent"
    assert snapshot_module.load_snapshot(installed.directory).aliases == ()


def test_a_snapshot_without_aliases_toml_keeps_the_digest_it_has() -> None:
    """`compute_digest` over two files is unchanged by the third parameter's existence."""
    rules, effects_bytes = b'{"entities": {}}', b"# none\n"
    two_files = snapshot_module.compute_digest(rules, effects_bytes)

    assert snapshot_module.compute_digest(rules, effects_bytes, None) == two_files
    assert snapshot_module.compute_digest(rules, effects_bytes, b"") != two_files


def test_every_installed_snapshot_still_verifies_and_only_the_last_two_185872_carry_aliases() -> (
    None
):
    """The committed tree, through the real resolver: nothing recorded changed, and exactly two
    promoted snapshots carry the file (T767's is the first, T768's carries it forward unchanged)."""
    installed = snapshot_module.load_all_snapshots()

    assert installed
    carrying = sorted(loaded.directory for loaded in installed if loaded.aliases)
    assert carrying == [
        "aoe2techtree-185872-civilisations-20",
        "aoe2techtree-185872-civilisations-32",
    ]


# ----------------------------------------------------------------------------- the digest covers


def test_the_digest_covers_aliases_toml_when_present(install: Callable[..., _Installed]) -> None:
    installed = install(aliases_toml=_GATE_ALIAS)
    path = installed.root / installed.directory / "aliases.toml"
    path.write_text(_GATE_ALIAS.replace("Gate", "Fortified Gate"), encoding="utf-8")

    with pytest.raises(snapshot_module.SnapshotDigestMismatch):
        snapshot_module.load_snapshot(installed.directory)


def test_a_file_added_to_a_snapshot_whose_digest_ignored_it_is_refused(
    install: Callable[..., _Installed],
) -> None:
    """Adding `aliases.toml` to a directory recorded without it changes its answers, so it must
    change its digest: the recorded one no longer matches."""
    installed = install(aliases_toml=_GATE_ALIAS, digest_over_aliases=False)

    with pytest.raises(snapshot_module.SnapshotDigestMismatch):
        snapshot_module.load_snapshot(installed.directory)


# ----------------------------------------------------------------------------------- refusals


def test_an_alias_whose_target_rules_json_does_not_name_is_refused(
    install: Callable[..., _Installed],
) -> None:
    installed = install(aliases_toml=_alias_entry(target="9999"))

    with pytest.raises(snapshot_module.SnapshotError, match="target"):
        snapshot_module.load_snapshot(installed.directory)


def test_an_alias_whose_target_is_named_under_another_kind_is_refused(
    install: Callable[..., _Installed],
) -> None:
    """Unit 74 exists; a building alias to "74" does not (the target is of the same kind)."""
    installed = install(aliases_toml=_alias_entry(target="74"))

    with pytest.raises(snapshot_module.SnapshotError, match="target"):
        snapshot_module.load_snapshot(installed.directory)


def test_an_alias_whose_own_id_rules_json_names_is_refused(
    install: Callable[..., _Installed],
) -> None:
    installed = install(aliases_toml=_alias_entry(id="12", target="487"))

    with pytest.raises(snapshot_module.SnapshotError, match="names"):
        snapshot_module.load_snapshot(installed.directory)


def test_two_aliases_for_one_identifier_are_refused(install: Callable[..., _Installed]) -> None:
    installed = install(aliases_toml=_alias_entry() + "\n" + _alias_entry(target="12"))

    with pytest.raises(snapshot_module.SnapshotError, match="more than one"):
        snapshot_module.load_snapshot(installed.directory)


def test_contrast_the_same_identifier_under_two_kinds_is_two_aliases(
    install: Callable[..., _Installed],
) -> None:
    """One alias per identifier means per (kind, id): 490 as a building and 490 as a unit are two
    identifiers."""
    installed = install(
        aliases_toml=_alias_entry() + "\n" + _alias_entry(kind="unit", target="74"),
    )

    loaded = snapshot_module.load_snapshot(installed.directory)

    assert [(a.kind, a.id) for a in loaded.aliases] == [("building", "490"), ("unit", "490")]


@pytest.mark.parametrize("key", ["kind", "id", "target", "source_name", "source", "read_on"])
def test_an_alias_missing_a_key_is_refused(install: Callable[..., _Installed], key: str) -> None:
    installed = install(aliases_toml=_alias_entry(**{key: None}))

    with pytest.raises(snapshot_module.SnapshotError, match=key):
        snapshot_module.load_snapshot(installed.directory)


@pytest.mark.parametrize("key", ["kind", "id", "target", "source_name", "source", "read_on"])
def test_an_alias_with_a_blank_key_is_refused(install: Callable[..., _Installed], key: str) -> None:
    installed = install(aliases_toml=_alias_entry(**{key: "  "}))

    with pytest.raises(snapshot_module.SnapshotError, match=key):
        snapshot_module.load_snapshot(installed.directory)


def test_an_alias_of_an_unknown_kind_is_refused(install: Callable[..., _Installed]) -> None:
    installed = install(aliases_toml=_alias_entry(kind="wonder"))

    with pytest.raises(snapshot_module.SnapshotError, match="kind"):
        snapshot_module.load_snapshot(installed.directory)


def test_an_alias_with_a_key_the_contract_does_not_name_is_refused(
    install: Callable[..., _Installed],
) -> None:
    installed = install(aliases_toml=_GATE_ALIAS + 'note = "a typo for source_name"\n')

    with pytest.raises(snapshot_module.SnapshotError, match="note"):
        snapshot_module.load_snapshot(installed.directory)


def test_a_non_string_id_is_refused(install: Callable[..., _Installed]) -> None:
    installed = install(aliases_toml=_GATE_ALIAS.replace('id = "490"', "id = 490"))

    with pytest.raises(snapshot_module.SnapshotError, match="id"):
        snapshot_module.load_snapshot(installed.directory)


def test_a_table_other_than_alias_is_refused(install: Callable[..., _Installed]) -> None:
    installed = install(aliases_toml=_GATE_ALIAS + '\n[other]\nkey = "x"\n')

    with pytest.raises(snapshot_module.SnapshotError, match="other"):
        snapshot_module.load_snapshot(installed.directory)


def test_malformed_toml_in_aliases_toml_is_a_snapshot_error(
    install: Callable[..., _Installed],
) -> None:
    installed = install(aliases_toml="[[alias\nkind = ")

    with pytest.raises(snapshot_module.SnapshotError, match=r"aliases\.toml"):
        snapshot_module.load_snapshot(installed.directory)


def test_a_refused_alias_table_refuses_the_whole_installed_set(
    install: Callable[..., _Installed],
) -> None:
    """There is no partial load: a snapshot with one bad alias is a deployment fault, as a digest
    mismatch is."""
    install(aliases_toml=_alias_entry(target="9999"))

    with pytest.raises(snapshot_module.SnapshotError):
        snapshot_module.load_all_snapshots()


# ------------------------------------------------------------- the committed first aliases.toml

#: The identifiers `aoc-reference-data`'s `objects` table (data/datasets/100.json, read 2026-10-22,
#: T767) names "Fortified Gate", "Sea Gate", "City Gate", "Paifang Gate" or "Trowulan Gate", with or
#: without an orientation qualifier: differently named gates, which FR-022d does not alias by name.
#: Transcribed from the source here so the absence is asserted, not just remembered.
_DIFFERENTLY_NAMED_GATES = (
    "63", "67", "80", "85", "90", "92", "488", "491", "660", "662", "664", "666", "668", "670",
    "672", "674", "1176", "1379", "1380", "1381", "1382", "1383", "1384", "1385", "1386", "1387",
    "1388", "1389", "1390", "1391", "1392", "1393", "1394", "1562", "1579", "1580", "1581", "1582",
    "1583", "1584", "1585", "1586", "1587", "1588", "1589", "1590", "1591", "1592", "1593", "1594",
)  # fmt: skip

#: The orientation qualifiers `objects` writes in parentheses (up., down., hori., vert.).
_ORIENTATION = re.compile(r"\s*\((?:up\.|down\.|hori\.|vert\.)\)$")

_CURRENT_BUILD = 185872


def _current() -> snapshot_module.Snapshot:
    resolved = snapshot_module.snapshot_for(_CURRENT_BUILD)
    assert isinstance(resolved, snapshot_module.Snapshot)
    return resolved


def test_buildings_490_and_673_answer_the_gate_of_the_third_snapshot() -> None:
    """The two identifiers two committed recordings place and the pack never named."""
    gate_cost = query.cost(
        query.EntityRef(kind="building", id="487", build=_CURRENT_BUILD), civilisation="Franks"
    )
    assert not isinstance(gate_cost, KnowledgeGap)
    for identifier in ("490", "673"):
        entity = query.EntityRef(kind="building", id=identifier, build=_CURRENT_BUILD)
        answer = query.cost(entity, civilisation="Franks")
        assert not isinstance(answer, KnowledgeGap), f"{identifier}: {answer!r}"
        assert answer.value == gate_cost.value == {"stone": 30}
        assert answer.alias is not None
        assert (answer.alias.id, answer.alias.target, answer.alias.source_name) == (
            identifier,
            "487",
            "Gate",
        )
        assert answer.alias.read_on == "2026-10-22"
        assert "aoc-reference-data" in answer.alias.source
        name = query.name(entity)
        assert not isinstance(name, KnowledgeGap)
        assert name.value == "Gate"


def test_every_alias_names_its_target_exactly_apart_from_an_orientation_qualifier() -> None:
    """FR-022d: never inferred from a name other than the pack entity's own."""
    rules = json.loads(
        (
            Path(str(snapshot_module._snapshots_root())) / _current().directory / "rules.json"
        ).read_text(encoding="utf-8")
    )["entities"]
    assert _current().aliases
    for alias in _current().aliases:
        assert alias.kind in ("unit", "building")
        assert _ORIENTATION.sub("", alias.source_name) == rules[alias.kind][alias.target]["name"], (
            alias
        )
        assert alias.id not in rules[alias.kind], alias
        assert alias.read_on == "2026-10-22"


def test_every_gate_and_palisade_gate_goes_to_the_packs_own() -> None:
    by_name: dict[str, set[str]] = {}
    for alias in _current().aliases:
        by_name.setdefault(_ORIENTATION.sub("", alias.source_name), set()).add(alias.target)
    assert by_name["Gate"] == {"487"}
    assert by_name["Palisade Gate"] == {"792"}
    assert {alias.id for alias in _current().aliases if alias.source_name.startswith("Gate")} >= {
        "64", "78", "81", "88", "91", "95", "490", "659", "661", "663", "665", "667", "669",
        "671", "673", "1192",
    }  # fmt: skip
    assert len([a for a in _current().aliases if a.source_name.startswith("Palisade Gate")]) == 15


def test_a_differently_named_gate_is_not_aliased_by_name() -> None:
    aliased = {alias.id for alias in _current().aliases if alias.kind == "building"}
    assert not aliased & set(_DIFFERENTLY_NAMED_GATES)
    assert not any(
        word in alias.source_name
        for alias in _current().aliases
        for word in ("Fortified", "Sea Gate", "City Gate", "Paifang", "Trowulan")
    )
    # Contrast: such an identifier is still an absent entity, not a guess at the nearest gate.
    absent = query.cost(
        query.EntityRef(kind="building", id="488", build=_CURRENT_BUILD), civilisation="Franks"
    )
    assert isinstance(absent, KnowledgeGap)
    assert absent.cause == "entity-absent"


def test_an_object_whose_qualifier_is_not_an_orientation_is_not_aliased() -> None:
    """`objects` 204 is "Trade Cart (Full)": a qualifier that is not an orientation. The pack's
    Trade Cart (unit 128) is not its alias."""
    assert _current().alias_for("unit", "204") is None
    absent = query.cost(
        query.EntityRef(kind="unit", id="204", build=_CURRENT_BUILD), civilisation="Franks"
    )
    assert isinstance(absent, KnowledgeGap)
    assert absent.cause == "entity-absent"
