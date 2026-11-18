"""The rules registry loader and its generated view (FR-005 to FR-007, T916).

The loader API these tests fix (``aoe2stats_reconstruction.rules``, T917):

- ``RuleError(ValueError)``: raised by every refusal.
- ``load_rules_text(text, *, known_readings) -> Rules``: parses and validates rules TOML text.
  ``known_readings`` is required: a collection of reading ids found in committed ``playback.toml``
  files, checked (guarantee 5), or ``None``, which means "not checked". The packaged loader passes
  ``None`` because the playback files are not in the wheel; a repository test supplies the real set.
- ``Rules``: a mapping by id (``rules["P1"]``, ``len``, ``in``) iterating ``Rule`` records;
  ``Rule`` has ``id, family, settles, statement, evidence, ruling, readings, status, limits,
  applies`` (optional fields ``None``, ``readings`` a tuple).
- ``RULES``: the packaged registry, loaded at import (constitution XII: ``importlib.resources``).
- ``render_view(rules) -> str``, ``REGENERATE_COMMAND``, ``VIEW_FILENAME == "RULES.md"``.
- ``applies`` is an optional text key stating a rule's applicability; two adopted rules settling the
  same kind overlap unless both state an ``applies`` and the two differ.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

import pytest

_PLAYBACK_FILES = sorted(
    (Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays").glob("*.playback.toml")
)

# The contract's "Enters as" column, for the rules present in the initial set.
INITIAL_STATUS = {
    "P0": "adopted",
    "P1": "adopted",
    "P2": "adopted",
    "P3": "adopted",
    "D-AGE-1": "candidate",
    "D-HOUSE-0": "candidate",
    "D-TECH-1": "adopted",
    "D-CONTROL-1": "candidate",
    "D-CANCEL-1": "candidate",
    "D-TIE-1": "candidate",
    "D-REFUND-1": "candidate",
    "D-WIN-1": "adopted",
}


def _rule(
    rule_id: str = "P1",
    *,
    family: str = "proof",
    settles: str = "age",
    status: str = "candidate",
    evidence: str = "research R3",
    extra: str = "",
) -> str:
    evidence_line = f'evidence = "{evidence}"\n' if evidence is not None else ""
    return (
        f'[rule."{rule_id}"]\n'
        f'family = "{family}"\n'
        f'settles = "{settles}"\n'
        'statement = "s"\n'
        f"{evidence_line}"
        "readings = []\n"
        f'status = "{status}"\n'
        f"{extra}\n"
    )


def _refuses(text: str, known_readings: object = ()) -> None:
    from aoe2stats_reconstruction.rules import RuleError, load_rules_text

    with pytest.raises(RuleError):
        load_rules_text(text, known_readings=known_readings)  # type: ignore[arg-type]


def test_a_well_formed_text_loads() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    rules = load_rules_text(
        _rule("P1", status="adopted") + _rule("D-AGE-1", family="deduction"), known_readings=()
    )
    assert rules["P1"].status == "adopted"
    assert rules["D-AGE-1"].family == "deduction"


def test_guarantee_1_a_duplicated_id_fails() -> None:
    from aoe2stats_reconstruction.rules import RuleError, load_rules_text

    # TOML itself rejects a repeated table, so the message is what shows the loader's own check ran.
    with pytest.raises(RuleError, match="duplicate id 'P1'"):
        load_rules_text(_rule("P1") + _rule("P1"), known_readings=())


@pytest.mark.parametrize("bad_id", ["p1", "P", "X1", "D-AGE", "D-age-1", "P1a", "D--1"])
def test_guarantee_1_an_id_outside_the_two_shapes_fails(bad_id: str) -> None:
    _refuses(_rule(bad_id))


@pytest.mark.parametrize(
    ("key", "value"),
    [("family", "estimate"), ("settles", "mood"), ("status", "maybe")],
)
def test_guarantee_2_a_value_outside_its_closed_set_fails(key: str, value: str) -> None:
    kwargs = {key: value}
    _refuses(_rule("P1", **kwargs))  # type: ignore[arg-type]


def test_guarantee_3_an_adopted_rule_with_an_empty_evidence_fails() -> None:
    # One adopted proof, no readings, no sibling: only guarantee 3 can refuse it.
    _refuses(_rule("P1", status="adopted", evidence=""))
    _refuses(_rule("P1", status="adopted", evidence=None))  # type: ignore[arg-type]


def test_guarantee_3_an_adopted_deduction_with_a_ruling_and_an_evidence_loads() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    ruled = _rule(
        "D-REFUND-1",
        family="deduction",
        settles="refund",
        status="adopted",
        extra='ruling = "spec Clarifications"',
    )
    assert load_rules_text(ruled, known_readings=())["D-REFUND-1"].status == "adopted"


def test_guarantee_4_a_refuted_rule_with_no_reading_fails() -> None:
    _refuses(_rule("D-AGE-1", family="deduction", status="refuted"))


def test_guarantee_4_a_refuted_rule_citing_a_known_reading_loads() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    text = _rule("D-AGE-1", family="deduction", status="refuted").replace(
        "readings = []", 'readings = ["R1"]'
    )
    assert load_rules_text(text, known_readings={"R1"})["D-AGE-1"].status == "refuted"


def test_guarantee_5_a_reading_in_no_playback_file_fails() -> None:
    text = _rule("P1").replace("readings = []", 'readings = ["511523321.O3"]')
    _refuses(text, known_readings={"another.O1"})
    _refuses(text, known_readings=())


def test_guarantee_5_a_known_reading_loads() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    text = _rule("P1").replace("readings = []", 'readings = ["511523321.O3"]')
    assert load_rules_text(text, known_readings={"511523321.O3"})["P1"].readings == (
        "511523321.O3",
    )


def test_guarantee_6_two_adopted_rules_settling_one_kind_overlap_and_fail() -> None:
    _refuses(_rule("P1", status="adopted") + _rule("D-AGE-1", family="deduction", status="adopted"))


def test_guarantee_6_one_stated_applicability_is_not_disjoint() -> None:
    _refuses(
        _rule("P1", status="adopted", extra='applies = "case a"')
        + _rule("D-AGE-1", family="deduction", status="adopted")
    )


def test_guarantee_6_equal_stated_applicability_overlaps() -> None:
    _refuses(
        _rule("P1", status="adopted", extra='applies = "case a"')
        + _rule("D-AGE-1", family="deduction", status="adopted", extra='applies = "case a"')
    )


def test_guarantee_6_a_candidate_beside_an_adopted_rule_does_not_overlap() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    rules = load_rules_text(
        _rule("P1", status="adopted") + _rule("D-AGE-1", family="deduction", status="candidate"),
        known_readings=(),
    )
    assert len(rules) == 2


def test_guarantee_6_disjoint_stated_applicability_does_not_overlap() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    rules = load_rules_text(
        _rule("P1", status="adopted", extra='applies = "case a"')
        + _rule(
            "D-AGE-1",
            family="deduction",
            status="adopted",
            extra='applies = "case b"\nruling = "r"',
        ),
        known_readings=(),
    )
    assert len(rules) == 2


def test_the_packaged_registry_loads_with_every_initial_rule_at_its_status() -> None:
    from aoe2stats_reconstruction.rules import RULES

    assert {rule.id: rule.status for rule in RULES} == INITIAL_STATUS


def test_d_exec_1_and_d_dist_1_are_absent_and_no_p4_exists() -> None:
    from aoe2stats_reconstruction.rules import RULES

    ids = {rule.id for rule in RULES}
    assert ids.isdisjoint({"D-EXEC-1", "D-DIST-1", "P4"})


def test_the_view_is_deterministic_and_lists_every_rule() -> None:
    from aoe2stats_reconstruction.rules import RULES, render_view

    view = render_view(RULES)
    assert render_view(RULES) == view
    assert view.endswith("\n") and not view.endswith("\n\n")
    assert "rules.toml" in view.split("\n## ", 1)[0]
    for rule in RULES:
        assert f"`{rule.id}`" in view


def test_the_committed_view_matches_the_registry_byte_for_byte() -> None:
    from aoe2stats_reconstruction.rules import REGENERATE_COMMAND, RULES, VIEW_FILENAME, render_view

    assert VIEW_FILENAME == "RULES.md"
    committed = resources.files("aoe2stats_reconstruction").joinpath("RULES.md").read_text("utf-8")
    assert committed == render_view(RULES), (
        "RULES.md has drifted from rules.toml. Regenerate it with: " + REGENERATE_COMMAND
    )


def test_guarantee_5_not_checked_accepts_a_cited_reading() -> None:
    # What the packaged loader does: the playback files are not in the wheel.
    from aoe2stats_reconstruction.rules import load_rules_text

    text = _rule("P1").replace("readings = []", 'readings = ["511523321.O3"]')
    assert load_rules_text(text, known_readings=None)["P1"].readings == ("511523321.O3",)


def test_guarantee_5_a_collection_still_refuses_an_unknown_reading() -> None:
    text = _rule("P1").replace("readings = []", 'readings = ["511523321.O3"]')
    _refuses(text, known_readings={"another.O1"})
    _refuses(text, known_readings=frozenset())


def test_the_known_readings_argument_has_no_default() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    with pytest.raises(TypeError):
        load_rules_text(_rule("P1"))  # type: ignore[call-arg]


def _repository_reading_ids() -> set[str]:
    ids: set[str] = set()
    for path in _PLAYBACK_FILES:
        data = tomllib.loads(path.read_text("utf-8"))
        ids |= {str(reading["id"]) for reading in data.get("reading", [])}
    return ids


def _packaged_text() -> str:
    return resources.files("aoe2stats_reconstruction").joinpath("rules.toml").read_text("utf-8")


def test_guarantee_5_every_cited_reading_is_in_a_committed_playback_file() -> None:
    from aoe2stats_reconstruction.rules import load_rules_text

    assert _PLAYBACK_FILES, "no *.playback.toml found: the repository check would pass vacuously"
    load_rules_text(_packaged_text(), known_readings=_repository_reading_ids())


def test_guarantee_5_the_repository_check_fails_on_a_stray_reading() -> None:
    text = _packaged_text().replace("readings = []", 'readings = ["no-such.O99"]', 1)
    assert text != _packaged_text()
    _refuses(text, known_readings=_repository_reading_ids())
