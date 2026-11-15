"""T910: 008's research R3 as a permanent test.

No order requires an age its participant has not yet clicked.

The rule (008's P1, FR-006's first proof): the game's interface offers no command for an entity
whose age has not been reached, so an order naming an entity that needs age N proves the
participant had reached N. Read the other way round it is a free cross-check of
`query.age_requirement`: the participant's own age-up click for N must not come after an order the
knowledge base says needs N.

Over every committed canonical golden, for every order (a unit queued, a building placed, a
technology researched) the knowledge base answers `age_requirement` for, the participant's click
of the age-up that reaches that age (technology 101, 102, 103 for ages 2, 3, 4) must be at or
before the order. An entity that needs the first age needs no click. Nothing here restates a
measurement: the goldens and the knowledge base are read, and the assertion is the rule.

**The one known defect.** One participant orders a Sicilian unit before the Castle Age click, and
the knowledge base answers Castle Age for it. It is a knowledge defect, fixed by a superseding
snapshot (006's task T851), not worked around here. It is held as a strict expected failure scoped
to that single (recording, participant, entity): every other case, and every other entity of that
participant, asserts normally. The day the superseding snapshot corrects the answer, the strict
`xfail` XPASSes and the suite turns red; the fix is then to delete `_KNOWN_DEFECT` and the test
that holds it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pytest

from aoe2stats_knowledge import effects, gaps, query, snapshot

_FIXTURES: Final[Path] = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"

#: The age-up technologies, keyed by the age they reach (the pack's own age number, 1 Dark to 4).
_AGE_UP_TECHNOLOGY: Final[dict[int, int]] = {2: 101, 3: 102, 4: 103}

#: Canonical event kind -> (entity kind, payload field naming the entity).
_ORDERS: Final[dict[str, tuple[str, str]]] = {
    "unit-queued": ("unit", "unit_id"),
    "building-placed": ("building", "building_id"),
    "research-queued": ("technology", "technology_id"),
}


@dataclass(frozen=True, slots=True)
class _Order:
    clock_ms: int
    entity: query.EntityRef
    required_age: int


@dataclass(frozen=True, slots=True)
class _KnownDefect:
    recording: str
    participant: int
    entity: query.EntityRef


#: The Sicilian unit the knowledge base answers Castle Age for (006's T851). Scoped to exactly one
#: participant of one recording and one entity.
_KNOWN_DEFECT: Final[_KnownDefect] = _KnownDefect(
    recording="AgeIIDE_Replay_511523321",
    participant=2,
    entity=query.EntityRef(kind="unit", id="1658", build=185872),
)

_GOLDENS: Final[tuple[Path, ...]] = tuple(sorted(_FIXTURES.glob("*.canonical.json")))


def _load(golden: Path) -> dict[str, Any]:
    return json.loads(golden.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _participants(golden: Path) -> list[tuple[str, int]]:
    events = _load(golden)["events"]
    started = events[0]["payload"]
    return [(golden.name, p["slot"]) for p in started["participants"]]


def _cases() -> list[Any]:
    return [
        pytest.param(name, slot, id=f"{name}-p{slot}")
        for g in _GOLDENS
        for name, slot in _participants(g)
    ]


def _violations(golden: Path, participant: int) -> list[_Order]:
    """Every order of `participant` that needs an age the participant had not yet clicked."""
    document = _load(golden)
    events = document["events"]
    started = events[0]["payload"]
    build = started["build"]
    resolved = snapshot.snapshot_for(build)
    assert not isinstance(resolved, gaps.KnowledgeGap), f"no snapshot for build {build}"
    names = effects.civilisation_id_names(resolved.directory)

    seated = {p["slot"]: p for p in started["participants"]}
    own = seated[participant]
    civilisation = names[own["civilisation"]]
    context = effects.Context(
        team=frozenset(
            names[p["civilisation"]] for p in seated.values() if p["team"] == own["team"]
        )
    )

    clicks: dict[int, int] = {}
    for event in events:
        if event["participant"] != participant or event["kind"] != "research-queued":
            continue
        for age, technology in _AGE_UP_TECHNOLOGY.items():
            if event["payload"]["technology_id"] == technology:
                clicks.setdefault(age, event["clock_ms"])

    found: list[_Order] = []
    for event in events:
        shape = _ORDERS.get(event["kind"])
        if shape is None or event["participant"] != participant:
            continue
        kind, field_name = shape
        entity = query.EntityRef(kind=kind, id=str(event["payload"][field_name]), build=build)
        answer = query.age_requirement(entity, civilisation=civilisation, context=context)
        assert not isinstance(answer, gaps.KnowledgeGap), (
            f"{golden.name}: age_requirement of {kind} {entity.id} for {civilisation} is a gap "
            f"({answer.cause}); the rule cannot be checked on an order it has no answer for"
        )
        needed = answer.value
        if needed <= 1:
            continue
        clicked_at = clicks.get(needed)
        if clicked_at is None or event["clock_ms"] < clicked_at:
            found.append(_Order(event["clock_ms"], entity, needed))
    return found


def _is_known_defect(golden_name: str, participant: int, order: _Order) -> bool:
    return (
        golden_name.removesuffix(".canonical.json") == _KNOWN_DEFECT.recording
        and participant == _KNOWN_DEFECT.participant
        and order.entity == _KNOWN_DEFECT.entity
    )


def test_goldens_are_present() -> None:
    # A glob that finds nothing would make every test below vacuously absent, not green.
    assert _GOLDENS, f"no canonical golden under {_FIXTURES}"


@pytest.mark.parametrize(("golden_name", "participant"), _cases())
def test_no_order_requires_an_age_not_yet_clicked(golden_name: str, participant: int) -> None:
    """Every case asserts normally, the known defect's own entity excepted (it is held below)."""
    unexplained = [
        order
        for order in _violations(_FIXTURES / golden_name, participant)
        if not _is_known_defect(golden_name, participant, order)
    ]
    assert not unexplained, (
        f"{golden_name} participant {participant}: orders needing an unclicked age: {unexplained}"
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "knowledge defect, 006's task T851: age_requirement answers Castle Age for a Sicilian "
        "unit its participant ordered before clicking Castle Age; strict, so the suite turns red "
        "when the superseding snapshot fixes it"
    ),
)
def test_known_defect_sicilian_unit_age_requirement() -> None:
    golden_name = f"{_KNOWN_DEFECT.recording}.canonical.json"
    held = [
        order
        for order in _violations(_FIXTURES / golden_name, _KNOWN_DEFECT.participant)
        if _is_known_defect(golden_name, _KNOWN_DEFECT.participant, order)
    ]
    assert not held, f"still orders {_KNOWN_DEFECT.entity.id} before its age: {len(held)} orders"
