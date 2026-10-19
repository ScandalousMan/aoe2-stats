"""T764: `produced_at` answers every building an entity is produced at, and an effect may add one.

contracts/knowledge-base.md, "The query surface": the answer is an ordered sequence of building
references, the pack's building first, then each building an effect adds in file order, each once.
`test_effects.py` proves the mechanism against synthetic effects with no I/O; this file proves the
three places that need a snapshot around them: the answer's type through `query.produced_at`, the
loader's refusal of an added building the snapshot does not know, and that the committed snapshots
answer a one-element (or empty) sequence because no committed effect adds a building yet.

Every synthetic case installs a throwaway snapshot under `tmp_path` and points the three readers
(`snapshot`, `query`, `effects`) at it, as `test_aliases.py` does; nothing here touches the
committed tree.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge import effects, query
from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.gaps import KnowledgeGap

_BUILD = 900_002
_VALIDATION = """
[validation]
method = "second-source"
checked_against = "a test"
performed_by = "a test author"
performed_at = "2026-01-01"
"""

#: Castle 82 is the pack's building for the Huskarl (unit 41); Barracks 12 and Stable 101 are the
#: buildings an effect adds. Unit 74 has no effect at all; building 12 is placed at no building.
_RULES: dict[str, Any] = {
    "civilisations": ["Goths", "Franks"],
    "entities": {
        "building": {
            "12": {"name": "Barracks", "produced_at": None, "table_origin": "building"},
            "82": {"name": "Castle", "produced_at": None, "table_origin": "building"},
            "101": {"name": "Stable", "produced_at": None, "table_origin": "building"},
        },
        "unit": {
            "41": {
                "name": "Huskarl",
                "produced_at": {"kind": "building", "id": "82"},
                "table_origin": "unit",
            },
            "74": {
                "name": "Militia",
                "produced_at": {"kind": "building", "id": "12"},
                "table_origin": "unit",
            },
        },
        "technology": {},
    },
}


def _effect(operand: str, *, civilisation: str = "Goths", condition: str = "") -> str:
    return f"""
[[effect]]
civilisation = "{civilisation}"
source_key = "0"
source_text = "Huskarls can be trained at Barracks"
modelled = "yes"
field = "produced_at"
operation = "add"
operand = "{operand}"
{condition}selector = [{{ kind = "unit", id = "41" }}]
validated_by = "synthetic"
"""


_ANARCHY = 'condition = "researched"\ncondition_technology = "457"\n'
_GATE_ALIAS = """
[[alias]]
kind = "building"
id = "490"
target = "12"
source_name = "Barracks"
source = "a test"
read_on = "2026-10-19"
"""


class _ResourcesShim:
    def __init__(self, package_root: Path) -> None:
        self._package_root = package_root

    def files(self, _package: str) -> Path:
        return self._package_root


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., str]:
    package_root = tmp_path / "pkg"
    snapshots = package_root / "snapshots"
    snapshots.mkdir(parents=True)
    monkeypatch.setattr(snapshot_module, "_snapshots_root", lambda: snapshots)
    shim = _ResourcesShim(package_root)
    for module in (snapshot_module, query, effects):
        monkeypatch.setattr(module, "resources", shim)

    def _install(effects_toml: str, *, aliases_toml: str | None = None) -> str:
        directory = f"produced-at-{uuid.uuid4().hex[:8]}"
        target = snapshots / directory
        target.mkdir()
        rules_bytes = json.dumps(_RULES).encode("utf-8")
        effects_bytes = effects_toml.encode("utf-8")
        aliases_bytes = aliases_toml.encode("utf-8") if aliases_toml is not None else None
        (target / "rules.json").write_bytes(rules_bytes)
        (target / "effects.toml").write_bytes(effects_bytes)
        (target / "disagreements.toml").write_text("# none\n", encoding="utf-8")
        if aliases_bytes is not None:
            (target / "aliases.toml").write_bytes(aliases_bytes)
        digest = snapshot_module.compute_digest(rules_bytes, effects_bytes, aliases_bytes)
        (target / "snapshot.toml").write_text(
            "\n".join(
                [
                    "[snapshot]",
                    'source = "aoe2techtree"',
                    'source_version = "deadbeef"',
                    f"describes_build = {_BUILD}",
                    f'digest = "{digest}"',
                    "promoted = true",
                    'civilisations_modelled = ["Goths", "Franks"]',
                ]
            )
            + "\n"
            + _VALIDATION,
            encoding="utf-8",
        )
        return directory

    return _install


def _ref(kind: str, entity_id: str) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=entity_id, build=_BUILD)


def _building(building_id: str) -> query.EntityRef:
    return _ref("building", building_id)


# ------------------------------------------------------------------------------- the answer


def test_an_entity_no_effect_touches_answers_a_one_element_sequence(
    install: Callable[..., str],
) -> None:
    install(_effect("12"))

    answer = query.produced_at(_ref("unit", "74"), civilisation="Goths")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == (_building("12"),)
    assert answer.effects == ()


def test_an_entity_the_pack_places_at_no_building_answers_the_empty_sequence(
    install: Callable[..., str],
) -> None:
    install("# none\n")

    answer = query.produced_at(_ref("building", "12"), civilisation="Goths")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == ()


def test_an_unconditional_addition_follows_the_packs_building(install: Callable[..., str]) -> None:
    install(_effect("12"))

    answer = query.produced_at(_ref("unit", "41"), civilisation="Goths")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == (_building("82"), _building("12"))
    assert [e.source_text for e in answer.effects] == ["Huskarls can be trained at Barracks"]


def test_a_researched_addition_answers_before_and_after_with_the_packs_building_first(
    install: Callable[..., str],
) -> None:
    install(_effect("12", condition=_ANARCHY))
    before = query.produced_at(
        _ref("unit", "41"),
        civilisation="Goths",
        context=query.Context(researched=frozenset()),
    )
    after = query.produced_at(
        _ref("unit", "41"),
        civilisation="Goths",
        context=query.Context(researched=frozenset({"457"})),
    )

    assert not isinstance(before, KnowledgeGap)
    assert not isinstance(after, KnowledgeGap)
    assert before.value == (_building("82"),)
    assert after.value == (_building("82"), _building("12"))


def test_a_researched_addition_raises_without_a_context(install: Callable[..., str]) -> None:
    install(_effect("12", condition=_ANARCHY))

    with pytest.raises(effects.ContextRequired):
        query.produced_at(_ref("unit", "41"), civilisation="Goths")


def test_additions_follow_in_file_order_each_once(install: Callable[..., str]) -> None:
    install(_effect("101") + _effect("12") + _effect("101") + _effect("82"))

    answer = query.produced_at(_ref("unit", "41"), civilisation="Goths")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == (_building("82"), _building("101"), _building("12"))


def test_an_addition_for_one_civilisation_does_not_reach_another(
    install: Callable[..., str],
) -> None:
    install(_effect("12", civilisation="Goths"))

    goths = query.produced_at(_ref("unit", "41"), civilisation="Goths")
    franks = query.produced_at(_ref("unit", "41"), civilisation="Franks")

    assert not isinstance(goths, KnowledgeGap)
    assert not isinstance(franks, KnowledgeGap)
    assert goths.value == (_building("82"), _building("12"))
    assert franks.value == (_building("82"),)


def test_an_unmodelled_civilisation_still_gaps(install: Callable[..., str]) -> None:
    install(_effect("12"))

    gap = query.produced_at(_ref("unit", "41"), civilisation="Aztecs")

    assert isinstance(gap, KnowledgeGap)
    assert gap.cause == "civilisation-not-modelled"


# ------------------------------------------------------------- the loader checks what is added


def test_the_loader_refuses_an_added_building_the_snapshot_does_not_name(
    install: Callable[..., str],
) -> None:
    directory = install(_effect("9999"))

    with pytest.raises(snapshot_module.SnapshotError, match="9999"):
        snapshot_module.load_snapshot(directory)


def test_the_loader_refuses_an_added_unit_or_technology_identifier_read_as_a_building(
    install: Callable[..., str],
) -> None:
    """Unit 41 exists, building 41 does not: an identifier is a building only if the building table
    names it."""
    directory = install(_effect("41"))

    with pytest.raises(snapshot_module.SnapshotError, match="41"):
        snapshot_module.load_snapshot(directory)


def test_the_loader_accepts_an_added_building_the_snapshot_names(
    install: Callable[..., str],
) -> None:
    directory = install(_effect("12"))

    assert snapshot_module.load_snapshot(directory).directory == directory


def test_the_loader_accepts_an_added_building_the_snapshot_aliases(
    install: Callable[..., str],
) -> None:
    directory = install(_effect("490"), aliases_toml=_GATE_ALIAS)

    assert snapshot_module.load_snapshot(directory).directory == directory
    answer = query.produced_at(_ref("unit", "41"), civilisation="Goths")
    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == (_building("82"), _building("490"))


def test_the_loader_refuses_a_malformed_effects_file_naming_produced_at(
    install: Callable[..., str],
) -> None:
    directory = install(_effect("12").replace('operation = "add"', 'operation = "set"'))

    with pytest.raises(snapshot_module.SnapshotError, match="produced_at"):
        snapshot_module.load_snapshot(directory)


def test_a_not_modelled_produced_at_effect_adds_nothing_to_check(
    install: Callable[..., str],
) -> None:
    text = (
        _effect("12")
        .replace('modelled = "yes"', 'modelled = "no"\nreason = "synthetic"')
        .replace('operation = "add"\n', "")
        .replace('operand = "12"\n', "")
    )
    directory = install(text)

    assert snapshot_module.load_snapshot(directory).directory == directory


# --------------------------------------------------------------- the committed snapshots


@pytest.mark.parametrize(
    ("entity_id", "expected_building"),
    [("358", "12"), ("1787", "1665")],
)
def test_a_committed_snapshot_answers_the_packs_building_alone_when_no_effect_adds_one(
    entity_id: str, expected_building: str
) -> None:
    answer = query.produced_at(
        query.EntityRef(kind="unit", id=entity_id, build=180059), civilisation="Franks"
    )

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == (query.EntityRef("building", expected_building, 180059),)
    assert answer.effects == ()


# ------------------------------------------------------------------------- the coverage pass


def test_the_coverage_pass_hands_context_to_exactly_the_queries_that_accept_it() -> None:
    """The pass passes `context=` to the fields it lists; a query that does not accept the keyword
    would raise `TypeError` rather than gap, and one that does but is not listed would never see
    the team the pass knows. T764 added `produced_at` to both sides."""
    import inspect

    from aoe2stats_knowledge import coverage

    for field_name, function in coverage._QUERY_SURFACE_FUNCTIONS:
        accepts = "context" in inspect.signature(function).parameters
        assert accepts == (field_name in coverage._CONTEXT_AWARE_FIELDS), field_name
    assert "produced_at" in coverage._CONTEXT_AWARE_FIELDS
