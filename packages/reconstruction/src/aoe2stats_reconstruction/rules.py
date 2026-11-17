"""The proof and deduction rules registry: record type, loader and view (FR-005 to FR-007).

Standard library only. The packaged ``rules.toml`` is loaded by :func:`load_rules_text` when this
module is imported, so a defective registry means the package does not import. Contract:
``specs/008-match-reconstruction/contracts/rules.md``; model: data-model section 6.

Reading ids (guarantee 5) live in ``tests/fixtures/replays/*.playback.toml``, which is a repository
path and is not shipped in the wheel. An installed package cannot discover them, so the packaged
registry is loaded with no known readings: it may cite none, and every rule's ``readings`` is empty
until a change that transcribes a reading also gives the packaged loader a way to know it. A test
with the repository at hand supplies the real set through ``known_readings``.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType
from typing import Any

FAMILIES = frozenset({"proof", "deduction"})
SETTLES = frozenset(
    {
        "age",
        "researched",
        "team",
        "team_researched",
        "controlled",
        "executed",
        "alive",
        "refund",
        "cancellation",
        "tie",
        "distribution",
        "winner",
        "housing",
    }
)
STATUSES = frozenset({"candidate", "adopted", "retired", "refuted"})

_ID_SHAPE = re.compile(r"P[0-9]+|D-[A-Z]+-[0-9]+")
_REQUIRED = ("family", "settles", "statement", "status")
_OPTIONAL = ("evidence", "ruling", "limits", "applies")
_KNOWN = frozenset({*_REQUIRED, *_OPTIONAL, "readings"})
_HEADER = re.compile(r'^\s*\[\s*rule\s*\.\s*"([^"]*)"\s*\]', re.MULTILINE)


class RuleError(ValueError):
    """The registry violates one of the loader's refusals."""


@dataclass(frozen=True, slots=True)
class Rule:
    """One proof or deduction rule."""

    id: str
    family: str
    settles: str
    statement: str
    status: str
    readings: tuple[str, ...]
    evidence: str | None = None
    ruling: str | None = None
    limits: str | None = None
    applies: str | None = None


@dataclass(frozen=True, slots=True)
class Rules:
    """A validated registry: rules by id, in declaration order."""

    entries: Mapping[str, Rule]

    def __getitem__(self, rule_id: str) -> Rule:
        return self.entries[rule_id]

    def __iter__(self) -> Iterator[Rule]:
        return iter(self.entries.values())

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self.entries


def _text(rule_id: str, raw: Mapping[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuleError(f"{rule_id}: {key} must be a string")
    return value


def _filled(value: str | None) -> bool:
    return bool((value or "").strip())


def _build_rule(rule_id: str, raw: Mapping[str, Any], known_readings: frozenset[str]) -> Rule:
    # Guarantee 1: the id is one of the two shapes (duplicates: see load_rules_text).
    if not _ID_SHAPE.fullmatch(rule_id):
        raise RuleError(f"invalid id {rule_id!r}: expected P<n> or D-<NAME>-<n>")
    unknown = sorted(set(raw) - _KNOWN)
    if unknown:
        raise RuleError(f"{rule_id}: unknown field(s) {', '.join(unknown)}")
    for key in _REQUIRED:
        if not _filled(_text(rule_id, raw, key)):
            raise RuleError(f"{rule_id}: required field {key} is missing or empty")
    readings = raw.get("readings")
    if not isinstance(readings, list) or not all(isinstance(r, str) for r in readings):
        raise RuleError(f"{rule_id}: readings must be a list of strings")
    rule = Rule(
        id=rule_id,
        family=str(raw["family"]),
        settles=str(raw["settles"]),
        statement=str(raw["statement"]),
        status=str(raw["status"]),
        readings=tuple(readings),
        **{k: _text(rule_id, raw, k) for k in _OPTIONAL},
    )
    # Guarantee 2: family, settles and status are in their closed sets.
    for name, value, closed in (
        ("family", rule.family, FAMILIES),
        ("settles", rule.settles, SETTLES),
        ("status", rule.status, STATUSES),
    ):
        if value not in closed:
            raise RuleError(f"{rule_id}: {name} {value!r} is outside {sorted(closed)}")
    # Guarantee 5: every cited reading is in a committed playback file.
    stray = [r for r in rule.readings if r not in known_readings]
    if stray:
        raise RuleError(f"{rule_id}: reading(s) {', '.join(stray)} are in no playback file")
    # Guarantee 3: an adopted rule has an evidence. The loader cannot read prose, so whether an
    # adopted deduction's basis is sound (a ruling, readings, or the game's own definition of a
    # command) is a reviewer's gate, not a loader check.
    if rule.status == "adopted" and not _filled(rule.evidence):
        raise RuleError(f"{rule_id}: an adopted rule needs a non-empty evidence")
    # Guarantee 4: a refuted rule cites the reading that refutes it.
    if rule.status == "refuted" and not rule.readings:
        raise RuleError(f"{rule_id}: a refuted rule must cite the reading that refutes it")
    return rule


def _check_overlap(entries: Mapping[str, Rule]) -> None:
    # Guarantee 6: no two adopted rules settle one kind with overlapping applicability.
    adopted: dict[str, list[Rule]] = {}
    for rule in entries.values():
        if rule.status == "adopted":
            adopted.setdefault(rule.settles, []).append(rule)
    for kind, group in adopted.items():
        for i, first in enumerate(group):
            for second in group[i + 1 :]:
                disjoint = (
                    _filled(first.applies)
                    and _filled(second.applies)
                    and first.applies != second.applies
                )
                if not disjoint:
                    raise RuleError(
                        f"{first.id} and {second.id} are both adopted for {kind!r} with "
                        "overlapping applicability: state a differing `applies` on both"
                    )


def load_rules_text(text: str, *, known_readings: Collection[str] = ()) -> Rules:
    """Parse and validate rules TOML text; raise :class:`RuleError` on any refusal."""
    # Guarantee 1: a duplicated id.
    seen: set[str] = set()
    for match in _HEADER.finditer(text):
        if match.group(1) in seen:
            raise RuleError(f"duplicate id {match.group(1)!r}")
        seen.add(match.group(1))
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RuleError(f"rules are not valid TOML (a duplicate id is one cause): {exc}") from exc
    unexpected = sorted(set(data) - {"rule"})
    if unexpected:
        raise RuleError(f"unexpected top-level key(s) {', '.join(unexpected)}")
    table = data.get("rule", {})
    if not isinstance(table, dict):
        raise RuleError("rule must be a table of tables")
    known = frozenset(known_readings)
    entries: dict[str, Rule] = {}
    for rule_id, raw in table.items():
        if not isinstance(raw, dict):
            raise RuleError(f"{rule_id}: a rule must be a table")
        entries[rule_id] = _build_rule(rule_id, raw, known)
    _check_overlap(entries)
    return Rules(MappingProxyType(entries))


def load_packaged_rules() -> Rules:
    """Load the ``rules.toml`` shipped beside this module (no known readings; see module doc)."""
    text = resources.files("aoe2stats_reconstruction").joinpath("rules.toml").read_text("utf-8")
    return load_rules_text(text)


RULES = load_packaged_rules()

VIEW_FILENAME = "RULES.md"
REGENERATE_COMMAND = "uv run python -m aoe2stats_reconstruction.rules"


def _code_list(items: tuple[str, ...]) -> str:
    return ", ".join(f"`{i}`" for i in items) if items else "none"


def _render_rule(rule: Rule) -> list[str]:
    lines = [
        f"### `{rule.id}`",
        "",
        f"- status: {rule.status}",
        f"- settles: {rule.settles}",
        f"- statement: {rule.statement}",
    ]
    if rule.applies:
        lines.append(f"- applies: {rule.applies}")
    if rule.evidence:
        lines.append(f"- evidence: {rule.evidence}")
    if rule.ruling:
        lines.append(f"- ruling: {rule.ruling}")
    lines.append(f"- readings: {_code_list(rule.readings)}")
    if rule.limits:
        lines.append(f"- limits: {rule.limits}")
    lines.append("")
    return lines


def render_view(rules: Rules) -> str:
    """Render the human-readable view: proofs, then deductions, in declaration order.

    Deterministic: no timestamp.
    """
    out = [
        "# The proof and deduction rules",
        "",
        "<!-- GENERATED FILE. Do not edit. -->",
        "",
        "This file is generated from `rules.toml`, the only place a rule is written. Regenerate it "
        f"with `{REGENERATE_COMMAND}`; a test fails when the two diverge.",
        "",
    ]
    for family, title in (("proof", "Proofs"), ("deduction", "Deductions")):
        members = [r for r in rules if r.family == family]
        if not members:
            continue
        out += [f"## {title} ({len(members)})", ""]
        for rule in members:
            out += _render_rule(rule)
    return "\n".join(out).rstrip("\n") + "\n"


def write_view() -> None:
    """Regenerate ``RULES.md`` beside this module from the packaged registry."""
    target = resources.files("aoe2stats_reconstruction").joinpath(VIEW_FILENAME)
    target.write_text(render_view(RULES), encoding="utf-8")  # type: ignore[attr-defined]


if __name__ == "__main__":
    write_view()
