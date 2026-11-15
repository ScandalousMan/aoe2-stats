"""T911: research R15 as a test. A queue order names the line's base unit, whatever was upgraded.

Across the committed canonical goldens, no unit-upgrade research is followed, for the researching
participant, by an order of the upgraded unit. The recording names the button pressed, not the unit
produced, so a unit upgrade leaves no trace in later orders (no proof rule can rest on one).

The test reads the goldens as JSON (this package depends on `aoe2stats-core` only) and the upgrade
relation (`upgrades_unit`) from the packaged rules of the build each recording reports. It is made
non-vacuous by `test_goldens_hold_upgrades_followed_by_base_line_orders`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge import query, snapshot
from aoe2stats_knowledge.gaps import KnowledgeGap

_FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays"

_GOLDENS = sorted(_FIXTURES_ROOT.glob("AgeIIDE_Replay_*.canonical.json"))


@dataclass(frozen=True)
class _Upgrade:
    recording: str
    participant: int
    technology_id: int
    upgraded_unit: int
    clock_ms: int
    later_orders: tuple[int, ...]  # unit ids ordered by that participant after the research
    earlier_orders: tuple[int, ...]  # unit ids ordered by that participant before it


def _upgrade_relation(build: int) -> dict[int, int]:
    snap = snapshot.snapshot_for(build)
    assert not isinstance(snap, KnowledgeGap), f"no snapshot for build {build}"
    technologies: dict[str, Any] = query._rules(snap.directory)["entities"]["technology"]
    return {
        int(tech_id): int(record["upgrades_unit"])
        for tech_id, record in technologies.items()
        if record.get("upgrades_unit") is not None
    }


def _upgrades_in(path: Path) -> list[_Upgrade]:
    events = json.loads(path.read_text(encoding="utf-8"))["events"]
    build = next(e["payload"]["build"] for e in events if e["kind"] == "match-started")
    relation = _upgrade_relation(build)
    found: list[_Upgrade] = []
    for index, event in enumerate(events):
        if event["kind"] != "research-queued":
            continue
        tech = event["payload"]["technology_id"]
        if tech not in relation:
            continue
        who = event["participant"]
        orders = [
            (i, e["payload"]["unit_id"])
            for i, e in enumerate(events)
            if e["kind"] == "unit-queued" and e["participant"] == who
        ]
        found.append(
            _Upgrade(
                recording=path.name,
                participant=who,
                technology_id=tech,
                upgraded_unit=relation[tech],
                clock_ms=event["clock_ms"],
                later_orders=tuple(u for i, u in orders if i > index),
                earlier_orders=tuple(u for i, u in orders if i < index),
            )
        )
    return found


@pytest.fixture(scope="module")
def upgrades() -> list[_Upgrade]:
    assert _GOLDENS, f"no committed canonical goldens under {_FIXTURES_ROOT}"
    return [u for path in _GOLDENS for u in _upgrades_in(path)]


def test_no_upgrade_research_is_followed_by_an_order_of_the_upgraded_unit(
    upgrades: list[_Upgrade],
) -> None:
    offenders = [
        (u.recording, u.participant, u.technology_id, u.clock_ms)
        for u in upgrades
        if u.upgraded_unit in u.later_orders
    ]
    assert offenders == []


def test_goldens_hold_upgrades_followed_by_base_line_orders(upgrades: list[_Upgrade]) -> None:
    """Non-vacuity: some upgrade research is followed by orders of a unit that the same
    participant was already ordering before it (the base line), and which is not the upgraded
    unit. Without this the main test could pass over goldens holding no upgrade at all."""
    assert upgrades, "the goldens hold no unit-upgrade research"
    with_base_line = [
        u
        for u in upgrades
        if {x for x in u.later_orders if x in u.earlier_orders} - {u.upgraded_unit}
    ]
    assert with_base_line, "no upgrade research is followed by orders of an earlier-ordered unit"
