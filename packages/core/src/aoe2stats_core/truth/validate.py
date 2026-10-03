"""The document validator: the ten rules of ``contracts/analysis-document.md``.

Run by the analyzer before an analysis is written. It takes the register as a mapping of datum id
to a duck-typed entry (``path``, ``tier``, ``status``, ``non_claim``, ``requires_knowledge``), so it
depends on nothing but the tier type. It reports every violated rule, not only the first.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

from aoe2stats_core.truth.identity import identity_digest
from aoe2stats_core.truth.tiers import Tier

LEVELS = frozenset({"low", "medium", "high"})

# Top-level keys that are not register data, exactly as the contract's rule 1 words them: the
# wall-clock set and the blocks that describe the document rather than carry values.
# ``schema_version`` is deliberately not here: the register publishes it as
# ``document.schema_version``, so it resolves like any other datum and carries a provenance entry
# (FR-007).
_EXEMPT = frozenset({"envelope", "extracted_at", "identity", "provenance", "knowledge_gaps"})
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


# The value type each wildcard register path admits beneath its one key. The register states the
# path, not the type, so the type is stated here and a wildcard path not listed covers nothing: a
# new wildcard in ``register.toml`` is refused (rule 1) until it is declared here, never silently
# widened to "anything" (FR-011, SC-003). ``engine.deps.*`` is a dependency name to its installed
# version string; ``participants[].age_up_commands.*`` is an age-technology id to the match-clock
# time of the command in milliseconds, which the extractor emits as an integer. ``bool`` is an
# ``int`` to Python and is not a time, so it is excluded explicitly.
_WILDCARD_VALUES: dict[str, type] = {
    "engine.deps.*": str,
    "participants[].age_up_commands.*": int,
}


def _scalar_of_kind(value: object, kind: type) -> bool:
    return isinstance(value, kind) and not isinstance(value, bool)


def _leaves(node: Any, path: str, wildcards: Mapping[str, type]) -> Iterator[tuple[str, bool]]:
    """Yield each leaf as ``(path, empty_mapping)``: dict keys joined by '.', every list index
    collapsed to '[]'. ``empty_mapping`` marks the leaf an empty dict leaves behind — a mapping
    with no entry beneath it, which is not a value.

    ``wildcards`` maps a wildcard root (``engine.deps``) to the type its values must have. A mapping
    at such a root is walked key by key and each key is **one** leaf, ``<root>.*``, provided its
    value is a scalar of that type: the key is never spliced into a path, so a dependency name with
    dots in it is one key, and nothing nested beneath it is ever a leaf of the wildcard. A key whose
    value is anything else (a mapping, a list, prose where a number belongs) yields the key's own
    path, which no register datum publishes, so rule 1 refuses it by name."""
    if isinstance(node, dict):
        if not node and path:
            yield path, True
        kind = wildcards.get(path)
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            if kind is not None:
                yield (f"{path}.*" if _scalar_of_kind(value, kind) else child), False
            else:
                yield from _leaves(value, child, wildcards)
    elif isinstance(node, list):
        if not node:
            yield f"{path}[]", False
        for item in node:
            yield from _leaves(item, f"{path}[]", wildcards)
    else:
        yield path, False


def _blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip()


def validate(document: Mapping[str, Any], register: Mapping[str, Entry]) -> None:
    """Raise ``DocumentInvalid`` naming every rule the document breaks; return None if none."""
    found: list[tuple[int, str]] = []

    def fail(rule: int, text: str) -> None:
        found.append((rule, text))

    # An exact path matches one leaf. A path ending ``.*`` is the register's wildcard for a mapping
    # whose keys are data (``engine.deps.*``): the walk (``_leaves``) turns each key of such a
    # mapping whose value is a scalar of the declared type into the one leaf ``<root>.*``, so the
    # wildcard resolves like an exact path and covers exactly one key, one level deep. A wildcard
    # path with no declared value type is not resolvable at all.
    published_by_path: dict[str, list[str]] = {}
    wildcards: dict[str, type] = {}  # wildcard root (without the trailing '.*') -> value type
    for reg_id, reg_entry in register.items():
        if reg_entry.status == "published" and reg_entry.path is not None:
            kind = _WILDCARD_VALUES.get(reg_entry.path)
            if reg_entry.path.endswith(".*"):
                if kind is None:
                    continue
                wildcards[reg_entry.path[:-2]] = kind
            published_by_path.setdefault(reg_entry.path, []).append(reg_id)

    def resolve(leaf: str) -> list[str]:
        return published_by_path.get(leaf, [])

    # Rule 1 and the set of data present outside ``inferred``.
    present: set[str] = set()
    for key, value in document.items():
        if key in _EXEMPT or key == _INFERRED:
            continue
        for leaf, empty_mapping in _leaves(value, str(key), wildcards):
            matches = resolve(leaf)
            if len(matches) == 1:
                present.add(matches[0])
            elif not matches:
                if leaf.endswith("[]") and any(
                    p.startswith(leaf + ".") or p.startswith(leaf + "[]") for p in published_by_path
                ):
                    continue  # an empty list whose elements are described further down
                if empty_mapping and leaf in wildcards:
                    continue  # an empty mapping whose entries the wildcard describes: no value
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

    # Rule 8: nothing present may need knowledge a blocking gap says is missing. A gap's
    # ``prevents`` is the register data it stops, computed from the register's own
    # ``requires_knowledge`` (bare field names such as ``cost``) when the gap was made, so the
    # validator compares datum ids and never re-derives a field key. A whole-build gap names no
    # entity and no field because nothing about the build is known: it blocks every datum that
    # needs any knowledge at all, whatever its ``prevents`` lists.
    gaps = document.get("knowledge_gaps", [])
    blocked: set[str] = set()
    whole_build = False
    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, Mapping) or gap.get("severity") != "blocking":
            continue
        prevents = gap.get("prevents")
        if isinstance(prevents, list):
            blocked.update(item for item in prevents if isinstance(item, str))
        if gap.get("entity") is None and gap.get("field") is None:
            whole_build = True
    for datum in sorted(everything):
        needs = register[datum].requires_knowledge
        if needs and (whole_build or datum in blocked):
            fail(8, f"{datum!r} is present but needs {sorted(needs)}, blocked by a knowledge gap")

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
