"""T925 (FR-026): the starting-objects table, `starting_objects.toml`, loaded through 006's snapshot
mechanism.

Two layers. The parser's refusals are tested on a small synthetic `rules.json` body, each refusal
with the row that loads as its contrast. The committed snapshot
`aoe2techtree-188329-starting-objects` is then read through the real loader: it supersedes the
snapshot it copies byte for byte, its rows are the pack's bullets verbatim, its baseline is open and
names owner requests that exist, and the digest covers the file.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.snapshot import (
    ANY_PRESET,
    SnapshotError,
    compute_digest,
    load_snapshot,
    parse_starting_objects,
)

_REPO = Path(__file__).resolve().parents[3]
_NEW = "aoe2techtree-188329-starting-objects"
_OLD = "aoe2techtree-188329-civilisations-56"
_PACK_STRINGS = _REPO / "packages/knowledge/packs/aoe2techtree-e56728e/strings.en.json"
_OWNER_READINGS = _REPO / "specs/008-match-reconstruction/owner-readings.md"

_RULES: dict[str, Any] = {
    "civilisations": {"Chinese": {}, "Franks": {}},
    "entities": {"unit": {"83": {"name": "Villager"}, "74": {"name": "Militia"}}},
}


def _row(**overrides: Any) -> str:
    values: dict[str, Any] = {
        "civilisation": "Chinese",
        "role": "bonus",
        "preset": "any",
        "kind": "unit",
        "object": "Villager",
        "unit_id": "83",
        "count": 3,
        "applies": "always",
        "source_key": "120155",
        "source_text": "Start with +3 Villagers",
        "read_on": "2026-11-17",
    }
    values.update(overrides)
    lines = ["[[starting_object]]"]
    for key, value in values.items():
        if value is None:
            continue
        lines.append(f"{key} = {json.dumps(value)}")
    return "\n".join(lines) + "\n"


def test_a_well_formed_row_loads_and_answers_by_preset() -> None:
    rows, owed = parse_starting_objects(_row(), _RULES)
    assert owed == ()
    assert rows[0].count == 3
    assert rows[0].unit_id == "83"
    assert rows[0].preset == ANY_PRESET


@pytest.mark.parametrize(
    "text",
    [
        "not toml [",
        "[alias]\nx = 1\n",
        _row(role="extra"),
        _row(role=None),
        _row(civilisation="*"),
        _row(role="baseline", civilisation="Atlantis"),
        _row(count=0),
        _row(count=True),
        _row(count="3"),
        _row(kind="monument"),
        _row(applies="sometimes"),
        _row(civilisation="Atlantis"),
        _row(unit_id="74"),
        _row(unit_id="999"),
        _row(kind="building", unit_id="83"),
        _row(source_text=""),
        _row(source_key=None),
        _row() + _row(),
        _row(role="baseline") + _row(role="baseline"),
        _row() + "stray = 1\n",
    ],
)
def test_a_malformed_table_is_refused(text: str) -> None:
    with pytest.raises(SnapshotError):
        parse_starting_objects(text, _RULES)


def test_an_object_the_pack_does_not_name_needs_no_unit_id() -> None:
    rows, _ = parse_starting_objects(
        _row(object="Llama", unit_id=None, count=1, applies="team"), _RULES
    )
    assert rows[0].unit_id is None


def test_a_baseline_row_may_name_every_civilisation_and_answers_for_all() -> None:
    text = _row(role="baseline", civilisation="*", count=3) + _row(count=1, source_key="2")
    rows, _ = parse_starting_objects(text, _RULES)
    assert rows[0].civilisation == "*"
    # The same object may be a baseline and a bonus: the role is part of a row's identity.
    snap = snapshot_module.Snapshot(
        directory="x",
        identity=load_snapshot(_NEW).identity,
        starting_objects=rows,
        has_starting_objects=True,
    )
    answer = snap.starting_objects_for("Franks", "any")
    assert answer.has_baseline
    assert [row.count for row in answer.added] == [3]
    chinese = snap.starting_objects_for("Chinese", "any")
    assert sorted(row.count for row in chinese.added) == [1, 3]
    bonus_only = snapshot_module.Snapshot(
        directory="x",
        identity=load_snapshot(_NEW).identity,
        starting_objects=rows[1:],
        has_starting_objects=True,
    )
    assert not bonus_only.starting_objects_for("Chinese", "any").has_baseline


def test_open_rows_name_a_modelled_civilisation_or_star() -> None:
    star = '[[open]]\ncivilisation = "*"\npreset = "*"\nwhat = "w"\nrequest = "O8.1"\n'
    _, owed = parse_starting_objects(star, _RULES)
    assert owed[0].request == "O8.1"
    with pytest.raises(SnapshotError):
        parse_starting_objects(star.replace('"*"\npreset', '"Atlantis"\npreset', 1), _RULES)
    with pytest.raises(SnapshotError):
        parse_starting_objects(star + 'extra = "x"\n', _RULES)


def test_the_digest_covers_the_table_when_present_and_not_otherwise() -> None:
    two = compute_digest(b"{}", b"e")
    assert compute_digest(b"{}", b"e", None, None) == two
    assert compute_digest(b"{}", b"e", None, b"") != two
    assert compute_digest(b"{}", b"e", None, b"a") != compute_digest(b"{}", b"e", None, b"b")
    assert compute_digest(b"{}", b"e", b"a", b"b") != compute_digest(b"{}", b"e", b"b", b"a")


# ------------------------------------------------------------------ the committed snapshot


def _dir(name: str) -> Path:
    return _REPO / "packages/knowledge/snapshots" / name


def test_the_snapshot_supersedes_the_one_it_copies_and_resolves_by_build() -> None:
    new, old = load_snapshot(_NEW), load_snapshot(_OLD)
    assert new.promoted
    assert new.supersedes == old.identity.digest
    assert new.identity.describes_build == old.identity.describes_build == 188329
    resolved = snapshot_module.snapshot_for(188329)
    assert isinstance(resolved, snapshot_module.Snapshot)
    assert resolved.directory == _NEW
    assert new.has_starting_objects
    assert not old.has_starting_objects


@pytest.mark.parametrize(
    "name", ["rules.json", "effects.toml", "aliases.toml", "disagreements.toml"]
)
def test_the_snapshot_carries_the_superseded_files_byte_for_byte(name: str) -> None:
    assert (_dir(_NEW) / name).read_bytes() == (_dir(_OLD) / name).read_bytes()


def test_every_row_is_a_pack_bullet_verbatim_under_its_key() -> None:
    strings = json.loads(_PACK_STRINGS.read_text(encoding="utf-8"))
    rows = load_snapshot(_NEW).starting_objects
    assert rows
    for row in rows:
        bullets = [line.strip(" •\n") for line in strings[row.source_key].split("<br>")]
        assert row.source_text in bullets, row
        assert row.preset == ANY_PRESET


def test_the_table_states_exactly_the_six_object_bonuses() -> None:
    rows = load_snapshot(_NEW).starting_objects
    assert {(row.civilisation, row.object, row.count, row.applies) for row in rows} == {
        ("Chinese", "Villager", 3, "always"),
        ("Mayans", "Villager", 1, "always"),
        ("Incas", "Llama", 1, "team"),
        ("Gurjaras", "Forage Bush", 2, "always"),
        ("Georgians", "Mule Cart", 1, "always"),
        ("Huns", "Horse", 1, "nomadic-map"),
    }
    assert {row.role for row in rows} == {"bonus"}
    # No source string gives an entity id, so none is stated (FR-026): 83 is only the male Villager.
    assert all(row.unit_id is None for row in rows)


def test_the_baseline_is_open_never_a_default() -> None:
    loaded = load_snapshot(_NEW)
    answer = loaded.starting_objects_for("Franks", "any")
    assert answer.added == ()
    assert not answer.has_baseline
    assert {row.request for row in answer.open} == {"O8.1", "O8.2"}
    chinese = loaded.starting_objects_for("Chinese", "any")
    assert [row.object for row in chinese.added] == ["Villager"]
    assert "O8.3" in {row.request for row in chinese.open}


def test_every_open_request_is_asked_in_the_owner_readings_file() -> None:
    text = _OWNER_READINGS.read_text(encoding="utf-8")
    asked = set(re.findall(r"\*\*(O8\.\d) ", text))
    requests = {row.request for row in load_snapshot(_NEW).starting_objects_open}
    assert requests
    assert requests <= asked


def test_the_header_and_validation_name_the_open_values() -> None:
    table = tomllib.loads((_dir(_NEW) / "snapshot.toml").read_text(encoding="utf-8"))
    assert "starting_objects.toml" in table["validation"]["not_checked"]
