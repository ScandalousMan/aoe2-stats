"""The document validator: the ten rules of ``contracts/analysis-document.md``.

Run by the analyzer before an analysis is written. It takes the register as a mapping of datum id
to a duck-typed entry (``path``, ``tier``, ``status``, ``non_claim``, ``requires_knowledge``), so it
depends on nothing but the tier type. It reports every violated rule, not only the first.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Any, Protocol

from aoe2stats_core.truth.tiers import Tier

LEVELS = frozenset({"low", "medium", "high"})

# Top-level keys that are not register data: the wall-clock set, the format version and the
# blocks that describe the document rather than carry values.
_EXEMPT = frozenset(
    {"schema_version", "envelope", "extracted_at", "identity", "provenance", "knowledge_gaps"}
)
_INFERRED = "inferred"


class Entry(Protocol):
    """What the validator reads of a register entry."""

    @property
    def path(self) -> str | None: ...
    @property
    def tier(self) -> Tier: ...
    @property
    def status(self) -> str: ...
    @property
    def non_claim(self) -> str | None: ...
    @property
    def requires_knowledge(self) -> tuple[str, ...]: ...


class DocumentInvalid(ValueError):
    """The document breaks at least one rule; ``rules`` holds every rule number broken."""

    def __init__(self, violations: list[tuple[int, str]]) -> None:
        self.rules: frozenset[int] = frozenset(rule for rule, _ in violations)
        self.violations = tuple(violations)
        super().__init__("; ".join(f"rule {rule}: {text}" for rule, text in violations))


def identity_digest(identity: Mapping[str, Any]) -> str:
    """Digest of every identity field except ``digest`` itself, over canonical JSON."""
    body = {k: v for k, v in identity.items() if k != "digest"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _leaves(node: Any, path: str) -> Iterator[str]:
    """Yield the path of each leaf: dict keys joined by '.', every list index collapsed to '[]'."""
    if isinstance(node, dict):
        if not node and path:
            yield path
        for key, value in node.items():
            yield from _leaves(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        if not node:
            yield f"{path}[]"
        for item in node:
            yield from _leaves(item, f"{path}[]")
    else:
        yield path


def _blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip()


def validate(document: Mapping[str, Any], register: Mapping[str, Entry]) -> None:
    """Raise ``DocumentInvalid`` naming every rule the document breaks; return None if none."""
    found: list[tuple[int, str]] = []

    def fail(rule: int, text: str) -> None:
        found.append((rule, text))

    published_by_path: dict[str, list[str]] = {}
    for reg_id, reg_entry in register.items():
        if reg_entry.status == "published" and reg_entry.path is not None:
            published_by_path.setdefault(reg_entry.path, []).append(reg_id)

    # Rule 1 and the set of data present outside ``inferred``.
    present: set[str] = set()
    for key, value in document.items():
        if key in _EXEMPT or key == _INFERRED:
            continue
        for leaf in _leaves(value, str(key)):
            matches = published_by_path.get(leaf, [])
            if len(matches) == 1:
                present.add(matches[0])
            elif not matches:
                if leaf.endswith("[]") and any(
                    p.startswith(leaf + ".") or p.startswith(leaf + "[]") for p in published_by_path
                ):
                    continue  # an empty list whose elements are described further down
                fail(1, f"leaf {leaf!r} resolves to no published register datum")
            else:
                fail(1, f"leaf {leaf!r} resolves to several data: {sorted(matches)}")

    # Rules 5 to 7 on the inferred block.
    inferred = document.get(_INFERRED, {})
    inferred_present: set[str] = set()
    if not isinstance(inferred, Mapping):
        fail(5, "the inferred block must be a mapping of datum id to instances")
        inferred = {}
    for datum, instances in inferred.items():
        entry = register.get(datum)
        if entry is None or entry.status != "published":
            fail(1, f"inferred datum {datum!r} is not a published register datum")
            continue
        inferred_present.add(datum)
        if entry.tier < Tier.INFERRED:
            fail(6, f"{datum!r} is {entry.tier.value}; it may not appear inside inferred")
        if not isinstance(instances, list):
            fail(5, f"{datum!r} must be a list of instances")
            continue
        for i, instance in enumerate(instances):
            where = f"{datum!r} instance {i}"
            if not isinstance(instance, Mapping):
                fail(5, f"{where} must be a mapping")
                continue
            confidence = instance.get("confidence")
            if not isinstance(confidence, Mapping):
                fail(5, f"{where} carries no confidence")
            else:
                level = confidence.get("level")
                if not isinstance(level, str) or level not in LEVELS:
                    fail(5, f"{where} has a confidence level outside {sorted(LEVELS)}")
                if _blank(confidence.get("basis")):
                    fail(5, f"{where} has an empty confidence basis")
            if entry.non_claim is not None and _blank(instance.get("non_claim")):
                fail(7, f"{where} does not carry the non-claim its register entry declares")

    # Rules 5 and 6, first halves: a weak datum outside ``inferred``.
    for datum in sorted(present):
        if register[datum].tier >= Tier.INFERRED:
            fail(5, f"{datum!r} is {register[datum].tier.value} and appears outside inferred")
            fail(6, f"{datum!r} is {register[datum].tier.value} and appears outside inferred")

    everything = present | inferred_present

    # Rules 2 to 4 on provenance.
    provenance = document.get("provenance", {})
    if not isinstance(provenance, Mapping):
        fail(2, "provenance must be a mapping of datum id to entry")
        provenance = {}
    for datum in sorted(everything - set(provenance)):
        fail(2, f"{datum!r} is present without a provenance entry")
    for datum in sorted(set(provenance) - everything):
        fail(2, f"provenance names {datum!r}, which is not in the document")
    for datum, prov in provenance.items():
        if datum not in everything:
            continue
        if not isinstance(prov, Mapping):
            fail(3, f"provenance of {datum!r} must be a mapping")
            fail(4, f"provenance of {datum!r} names no method")
            continue
        if _blank(prov.get("method")):
            fail(4, f"provenance of {datum!r} names no method")
        try:
            tier = Tier(prov.get("tier"))
        except ValueError:
            fail(3, f"provenance of {datum!r} has a missing or unknown tier")
            continue
        if tier is not register[datum].tier:
            fail(
                3,
                f"{datum!r} is {tier.value} in provenance but {register[datum].tier.value} "
                "in the register",
            )
        inputs = prov.get("inputs", [])
        if not isinstance(inputs, list):
            fail(3, f"inputs of {datum!r} must be a list")
            continue
        for source in inputs:
            source_entry = register.get(source) if isinstance(source, str) else None
            if source_entry is None:
                fail(3, f"{datum!r} names input {source!r}, which is not a register datum")
            elif tier < source_entry.tier:
                fail(
                    3,
                    f"{datum!r} is {tier.value}, stronger than its input {source!r} "
                    f"({source_entry.tier.value})",
                )

    # Rule 8: nothing present may need knowledge a blocking gap says is missing.
    gaps = document.get("knowledge_gaps", [])
    blocked: set[str] = set()
    for gap in gaps if isinstance(gaps, list) else []:
        if isinstance(gap, Mapping) and gap.get("severity") == "blocking":
            entity = gap.get("entity")
            kind = entity.get("kind") if isinstance(entity, Mapping) else None
            blocked.add(f"{kind}.{gap.get('field')}")
    for datum in sorted(everything):
        hit = blocked.intersection(register[datum].requires_knowledge)
        if hit:
            fail(8, f"{datum!r} is present but needs {sorted(hit)}, blocked by a knowledge gap")

    # Rules 9 and 10.
    identity = document.get("identity")
    if not isinstance(identity, Mapping):
        fail(9, "the document has no identity block")
    else:
        deps = identity.get("parser_dependencies")
        if not isinstance(deps, Mapping) or not deps:
            fail(9, "identity.parser_dependencies is empty")
        if identity.get("digest") != identity_digest(identity):
            fail(10, "identity.digest does not recompute from the other identity fields")

    if found:
        raise DocumentInvalid(found)
