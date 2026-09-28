"""The determinability register: entry type, loader and dependency graph (FR-001 to FR-006).

Standard library only, so ``packages/core`` keeps its zero-dependency rule. The packaged
``register.toml`` is loaded by :func:`load_register_text` when this module is imported, so a
defective register means the module does not import. Contract: contracts/register.md.

The naming discipline for ids (FR-012, T622) is recorded in ``aoe2stats_core.truth``.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType
from typing import Any

from aoe2stats_core.truth.tiers import Tier, weakest

NON_DETERMINABLE = "non-determinable"
CLASSIFICATIONS = frozenset({t.value for t in Tier} | {NON_DETERMINABLE})
STATUSES = frozenset({"published", "planned", "blocked"})
_WEAK_TIERS = frozenset({Tier.INFERRED, Tier.PREDICTED})
_ND_FIELDS = ("reason", "impact", "approximation", "approximation_acceptable", "would_change_if")
_OPTIONAL = ("path", "non_claim", "blocked_on", "confidence_method", *_ND_FIELDS)
_REQUIRED = ("classification", "status", "source", "method", "validation", "evidence")
_KNOWN = frozenset({*_REQUIRED, *_OPTIONAL, "requires_knowledge", "depends_on"})

_ID_SHAPE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_BANNED_TOKENS = frozenset({"times", "built"})
_BANNED_SEGMENTS = frozenset({"villagers"})
_HEADER = re.compile(r'^\s*\[\s*datum\s*\.\s*"([^"]*)"\s*\]', re.MULTILINE)


class RegisterError(ValueError):
    """The register violates one of the loader's refusals."""


@dataclass(frozen=True, slots=True)
class Entry:
    """One datum's determinability record."""

    id: str
    classification: str
    status: str
    source: str
    method: str
    requires_knowledge: tuple[str, ...]
    depends_on: tuple[str, ...]
    validation: str
    evidence: str
    path: str | None = None
    blocked_on: str | None = None
    non_claim: str | None = None
    confidence_method: str | None = None
    reason: str | None = None
    impact: str | None = None
    approximation: str | None = None
    approximation_acceptable: str | None = None
    would_change_if: str | None = None

    @property
    def tier(self) -> Tier | None:
        """The truth tier, or ``None`` for a ``non-determinable`` entry."""
        if self.classification == NON_DETERMINABLE:
            return None
        return Tier(self.classification)


@dataclass(frozen=True, slots=True)
class Register:
    """A validated register: entries by id and the dependency graph."""

    entries: Mapping[str, Entry]

    @property
    def graph(self) -> Mapping[str, tuple[str, ...]]:
        """Datum id to the ids it depends on. Acyclic and closed: every target is an entry."""
        return MappingProxyType({i: e.depends_on for i, e in self.entries.items()})

    def dependents(self, datum_id: str) -> tuple[str, ...]:
        """Ids that name ``datum_id`` in ``depends_on``, in declaration order."""
        return tuple(i for i, e in self.entries.items() if datum_id in e.depends_on)

    def __getitem__(self, datum_id: str) -> Entry:
        return self.entries[datum_id]

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.entries.values())

    def __len__(self) -> int:
        return len(self.entries)


def _check_id(datum_id: str) -> None:
    if not _ID_SHAPE.match(datum_id):
        raise RegisterError(
            f"invalid id {datum_id!r}: two or more dot-separated segments, each [a-z][a-z0-9_]*"
        )
    for segment in datum_id.split("."):
        if segment in _BANNED_SEGMENTS or _BANNED_TOKENS & set(segment.split("_")):
            raise RegisterError(
                f"invalid id {datum_id!r}: segment {segment!r} names an outcome, not what was "
                "measured (FR-012)"
            )


def _text(datum_id: str, raw: Mapping[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RegisterError(f"{datum_id}: {key} must be a string")
    return value


def _id_list(datum_id: str, raw: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise RegisterError(f"{datum_id}: {key} must be a list of strings")
    return tuple(value)


def _build_entry(datum_id: str, raw: Mapping[str, Any]) -> Entry:
    _check_id(datum_id)
    unknown = sorted(set(raw) - _KNOWN)
    if unknown:
        raise RegisterError(f"{datum_id}: unknown field(s) {', '.join(unknown)}")
    for key in _REQUIRED:
        if not (_text(datum_id, raw, key) or "").strip():
            if key == "evidence":
                raise RegisterError(f"{datum_id}: evidence is missing or empty (SC-013)")
            raise RegisterError(f"{datum_id}: required field {key} is missing or empty")
    classification = str(raw["classification"])
    status = str(raw["status"])
    if classification not in CLASSIFICATIONS:
        raise RegisterError(
            f"{datum_id}: classification {classification!r} is outside {sorted(CLASSIFICATIONS)}"
        )
    if status not in STATUSES:
        raise RegisterError(f"{datum_id}: status {status!r} is outside {sorted(STATUSES)}")
    entry = Entry(
        id=datum_id,
        classification=classification,
        status=status,
        source=str(raw["source"]),
        method=str(raw["method"]),
        requires_knowledge=_id_list(datum_id, raw, "requires_knowledge"),
        depends_on=_id_list(datum_id, raw, "depends_on"),
        validation=str(raw["validation"]),
        evidence=str(raw["evidence"]),
        **{k: _text(datum_id, raw, k) for k in _OPTIONAL},
    )
    if classification == NON_DETERMINABLE:
        for key in _ND_FIELDS:
            if not (getattr(entry, key) or "").strip():
                raise RegisterError(
                    f"{datum_id}: non-determinable entry needs {key} (FR-003), missing or empty"
                )
        if entry.approximation_acceptable not in ("yes", "no"):
            raise RegisterError(
                f"{datum_id}: approximation_acceptable must be 'yes' or 'no', "
                f"got {entry.approximation_acceptable!r} (FR-003)"
            )
    if status == "blocked" and not (entry.blocked_on or "").strip():
        raise RegisterError(f"{datum_id}: a blocked entry must name blocked_on (FR-005)")
    if (
        status == "published"
        and entry.tier in _WEAK_TIERS
        and not (entry.confidence_method or "").strip()
    ):
        raise RegisterError(
            f"{datum_id}: a published {classification} entry states no confidence_method"
        )
    return entry


def _check_graph(entries: Mapping[str, Entry]) -> None:
    for entry in entries.values():
        for dep in entry.depends_on:
            if dep not in entries:
                raise RegisterError(f"{entry.id}: dangling dependency {dep!r}")
    done: set[str] = set()
    for start in entries:
        if start in done:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        on_path = [start]
        while stack:
            node, index = stack.pop()
            deps = entries[node].depends_on
            if index < len(deps):
                stack.append((node, index + 1))
                nxt = deps[index]
                if nxt in on_path:
                    loop = " -> ".join([*on_path[on_path.index(nxt) :], nxt])
                    raise RegisterError(f"dependency cycle: {loop}")
                if nxt not in done:
                    stack.append((nxt, 0))
                    on_path.append(nxt)
            else:
                done.add(node)
                on_path.pop()


def _check_tiers(entries: Mapping[str, Entry]) -> None:
    for entry in entries.values():
        if entry.tier is None:
            continue
        dep_tiers = [t for d in entry.depends_on if (t := entries[d].tier) is not None]
        if dep_tiers and entry.tier < weakest(*dep_tiers):
            raise RegisterError(
                f"{entry.id}: tier {entry.classification} is stronger than its weakest "
                f"dependency, {weakest(*dep_tiers).value} (FR-008)"
            )


def load_register_text(text: str) -> Register:
    """Parse and validate register TOML text; raise :class:`RegisterError` on any refusal."""
    seen: set[str] = set()
    for match in _HEADER.finditer(text):
        if match.group(1) in seen:
            raise RegisterError(f"duplicate id {match.group(1)!r}")
        seen.add(match.group(1))
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RegisterError(
            f"register is not valid TOML (a duplicate id is one cause): {exc}"
        ) from exc
    unexpected = sorted(set(data) - {"datum"})
    if unexpected:
        raise RegisterError(f"unexpected top-level key(s) {', '.join(unexpected)}")
    table = data.get("datum", {})
    if not isinstance(table, dict):
        raise RegisterError("datum must be a table of tables")
    entries: dict[str, Entry] = {}
    for datum_id, raw in table.items():
        if not isinstance(raw, dict):
            raise RegisterError(f"{datum_id}: an entry must be a table")
        entries[datum_id] = _build_entry(datum_id, raw)
    _check_graph(entries)
    _check_tiers(entries)
    return Register(MappingProxyType(entries))


def load_packaged_register() -> Register:
    """Load the ``register.toml`` shipped beside this module."""
    text = resources.files("aoe2stats_core.truth").joinpath("register.toml").read_text("utf-8")
    return load_register_text(text)


REGISTER = load_packaged_register()

VIEW_FILENAME = "REGISTER.md"
REGENERATE_COMMAND = "uv run python -m aoe2stats_core.truth.register"

_HEADING = {
    NON_DETERMINABLE: (
        "Non-determinable",
        "These data cannot be known from the recording. Each is stated in full: why, what it "
        "costs, what stands in for it, and what would change the answer.",
    ),
    "observed": ("observed", "Read directly from the recording."),
    "decoded": ("decoded", "Read from the recording after decoding an encoded field."),
    "reconstructed": ("reconstructed", "Rebuilt from several recorded facts."),
    "derived": ("derived", "Computed from other published data."),
    "inferred": ("inferred", "A signal read from behaviour, not a recorded fact."),
    "predicted": ("predicted", "A forecast."),
}
_ORDER = (NON_DETERMINABLE, *(t.value for t in Tier))


def _code_list(items: tuple[str, ...]) -> str:
    return ", ".join(f"`{i}`" for i in items) if items else "none"


def _render_entry(entry: Entry) -> list[str]:
    lines = [f"### `{entry.id}`", "", f"- status: {entry.status}"]
    if entry.blocked_on:
        lines.append(f"- blocked on: {entry.blocked_on}")
    if entry.classification == NON_DETERMINABLE:
        lines += [
            f"- reason: {entry.reason}",
            f"- impact: {entry.impact}",
            f"- approximation: {entry.approximation}",
            f"- approximation_acceptable: {entry.approximation_acceptable}",
            f"- would change if: {entry.would_change_if}",
        ]
    lines += [f"- source: {entry.source}", f"- method: {entry.method}"]
    if entry.path:
        lines.append(f"- document path: `{entry.path}`")
    if entry.non_claim:
        lines.append(f"- non-claim: {entry.non_claim}")
    if entry.confidence_method:
        lines.append(f"- confidence method: {entry.confidence_method}")
    lines += [
        f"- requires knowledge: {_code_list(entry.requires_knowledge)}",
        f"- depends on: {_code_list(entry.depends_on)}",
        f"- validation: {entry.validation}",
        f"- evidence: {entry.evidence}",
        "",
    ]
    return lines


def render_view(register: Register) -> str:
    """Render the human-readable view: non-determinable first, then tiers strongest first.

    Deterministic: no timestamp, entries in declaration order within a group.
    """
    out = [
        "# The determinability register",
        "",
        "<!-- GENERATED FILE. Do not edit. -->",
        "",
        "This file is generated from `register.toml`, the only place a classification is written "
        f"(FR-006a). Regenerate it with `{REGENERATE_COMMAND}`; a test fails when the two diverge.",
        "",
    ]
    for group in _ORDER:
        members = [e for e in register if e.classification == group]
        if not members:
            continue
        title, blurb = _HEADING[group]
        out += [f"## {title} ({len(members)})", "", blurb, ""]
        for entry in members:
            out += _render_entry(entry)
    return "\n".join(out).rstrip("\n") + "\n"


def write_view() -> None:
    """Regenerate ``REGISTER.md`` beside this module from the packaged register."""
    target = resources.files("aoe2stats_core.truth").joinpath(VIEW_FILENAME)
    target.write_text(render_view(REGISTER), encoding="utf-8")  # type: ignore[attr-defined]


if __name__ == "__main__":
    write_view()
