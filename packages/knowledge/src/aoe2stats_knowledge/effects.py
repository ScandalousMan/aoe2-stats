"""T644: structured civilisation effects (research.md D5, data-model.md §6 "Civilisation effect").

Contract: [contracts/knowledge-base.md](../../../../specs/006-replay-analysis-foundations/
contracts/knowledge-base.md), "Civilisation qualification" steps 2-3. Research:
[research.md](../../../../specs/006-replay-analysis-foundations/research.md) **D5**. Data model:
[data-model.md](../../../../specs/006-replay-analysis-foundations/data-model.md) §6.

**What one effect record carries**, per data-model.md §6, and where each field is enforced:

- `civilisation` — the pack's own civilisation name (`"Byzantines"`, matching
  `normalise.py`'s `civilisations` list and `snapshot.toml`'s `civilisations_modelled`).
- `source_key` / `source_text` — "the verbatim sentence from the vendored strings, **and its
  key**": `source_key` is `strings.en.json`'s own `help_string_id` (e.g. `"120156"`), so an edit
  to that source string is detectable by re-reading the same key, and `source_text` is transcribed
  byte-for-byte from it (FR-031's provenance).
- `modelled` — `"yes"` or `"no"`, spelled exactly as data-model.md §6 spells it. `"no"` requires a
  non-blank `reason` and **must not** carry an `operation`/`operand` — research.md D5's "a bonus is
  never half-applied" is enforced here, at parse time, not left to a caller to notice a stray
  operand on an effect it should never apply.
- `selector` — "which entities it touches — by explicit identifier list, never by a fuzzy class
  name": a non-empty tuple of `(kind, id)` pairs, each resolved by hand from `rules.json`'s own
  `prerequisites`/`produced_at` structure (this module's docstring for `_effects_toml_text`-style
  provenance lives in the two committed `effects.toml` files themselves, not here — see their
  header comments for exactly how "Spearman-line" and "Ranged Soldiers and Infantry" were resolved
  to real unit ids).
- `field` — which query-level field this effect modifies. Not restricted to the six names
  `query.py` exposes (a not-modelled effect may legitimately name a field this knowledge base does
  not otherwise track at all, e.g. a unit's hit points) — restricting it would silently imply that
  every effect in the pack's prose is one this package could someday model, which is not true.
- `operation` — **closed**: `"multiply"`, `"add"`, `"set"` (data-model.md §6). Required, and
  validated against this set, exactly when `modelled == "yes"`.
- `operand` — "the amount, per resource where the field is a cost": a mapping of resource name to
  amount when `field == "cost"` and only some resources are touched (Koreans' wood-only discount is
  exactly this shape — gold is absent from the mapping and therefore untouched), or a bare number
  for a single-valued field. Required, and shape-checked, exactly when `modelled == "yes"`.
- `validated_by` — FR-030's "the second reading that validated it": who re-read the source sentence
  a second time, against which file, when — recorded as data, not a placeholder string.

**Civilisation qualification, steps 2-3** (contracts/knowledge-base.md): given an entity, a field
and a civilisation already known to be modelled (`query.py`'s step 1, `_civilisations_modelled`),
this module's `apply` finds every effect matching all three, refuses with `EffectNotModelled` if
any match is `modelled == "no"` — **never** applying the modelled matches alongside it, which is
what "a bonus is never half-applied" actually forbids — and otherwise applies every matching,
modelled effect in file order and returns the adjusted value together with the effects applied.

**Why matching and application are two separate functions** (`effects_for` reads a packaged
snapshot; `apply_matched` is pure). `test_effects.py` exercises the invariants — the closed
operation set, the never-half-applied rule, round-half-up on a cost — against synthetic `Effect`
values with no file I/O at all, and separately exercises `effects_for`/`apply` against the two real,
committed snapshots' real `effects.toml` content, so the same test suite proves both "the mechanism
is correct" and "the real transcription produces the real adjusted cost" without either proof
standing in for the other.
"""

from __future__ import annotations

import functools
import math
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Final

#: The package this module's data is anchored to — see `snapshot.py`'s module docstring for why
#: `importlib.resources` and never a bare filesystem path.
_PACKAGE: Final[str] = "aoe2stats_knowledge"

#: data-model.md §6's closed operation set. Nothing outside this set is a valid `operation` on a
#: `modelled = "yes"` effect — checked at parse time, not at application time, so a malformed
#: `effects.toml` fails to load rather than failing silently the first time a query reaches it.
OPERATIONS: Final[frozenset[str]] = frozenset({"multiply", "add", "set"})

#: data-model.md §6's `modelled` values, spelled exactly as the data model spells them — a string
#: enum rather than a bool, because `effects.toml` is meant to read as prose beside `source_text`,
#: and "modelled = yes" reads the way the rest of that file's keys do.
_MODELLED_VALUES: Final[frozenset[str]] = frozenset({"yes", "no"})

#: TOML keys required on every `[[effect]]` table, whatever `modelled` says.
_COMMON_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "civilisation",
    "source_key",
    "source_text",
    "modelled",
    "field",
    "selector",
    "validated_by",
)


class EffectsError(ValueError):
    """A snapshot's `effects.toml` is malformed: a required field is missing or blank, `modelled`
    is not `"yes"`/`"no"`, a `"no"` effect carries an `operation`/`operand` it must not (research.md
    D5: "a bonus is never half-applied"), a `"yes"` effect is missing one, `operation` is not one
    of data-model.md §6's closed set, or `selector` is empty or malformed. Raised at parse time, in
    place of returning an `Effect` that looks complete but has a hole a query could fall through.
    """


@dataclass(frozen=True, slots=True)
class SelectorEntry:
    """One entity an effect's `selector` names explicitly — never a fuzzy class name
    (data-model.md §6). `kind` is one of `rules.json`'s three entity kinds; `id` is the entity's
    own identifier exactly as `rules.json` keys it."""

    kind: str
    id: str


@dataclass(frozen=True, slots=True)
class Effect:
    """One hand-transcribed civilisation effect (data-model.md §6). See this module's docstring
    for what every field means and how `modelled == "no"` constrains `operation`/`operand`."""

    civilisation: str
    source_key: str
    source_text: str
    modelled: str
    selector: tuple[SelectorEntry, ...]
    field: str
    validated_by: str
    reason: str | None = None
    operation: str | None = None
    operand: object | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("civilisation", self.civilisation),
            ("source_key", self.source_key),
            ("source_text", self.source_text),
            ("field", self.field),
            ("validated_by", self.validated_by),
        ):
            if not isinstance(value, str) or not value.strip():
                raise EffectsError(f"effect.{name} must be a non-blank string, got {value!r}")
        if self.modelled not in _MODELLED_VALUES:
            raise EffectsError(
                f"effect.modelled must be one of {sorted(_MODELLED_VALUES)}, got {self.modelled!r}"
            )
        if not self.selector:
            raise EffectsError(
                "effect.selector must name at least one entity explicitly — never empty, and "
                "never a fuzzy class name in place of one"
            )
        if self.modelled == "no":
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise EffectsError(
                    'effect.reason must be a non-blank string when modelled = "no" '
                    "(research.md D5: team-wide, age-gated-beyond-the-recording, or "
                    "conditional-on-state bonuses are recorded not modelled, with why)"
                )
            if self.operation is not None or self.operand is not None:
                raise EffectsError(
                    'a modelled = "no" effect must not carry an operation or operand — '
                    'research.md D5: "a bonus is never half-applied"'
                )
        else:
            if self.reason is not None:
                raise EffectsError('a modelled = "yes" effect must not carry a reason')
            if self.operation not in OPERATIONS:
                raise EffectsError(
                    f"effect.operation must be one of {sorted(OPERATIONS)} when "
                    f'modelled = "yes", got {self.operation!r}'
                )
            if self.operand is None:
                raise EffectsError('effect.operand is required when modelled = "yes"')


@dataclass(frozen=True, slots=True)
class EffectNotModelled:
    """contracts/knowledge-base.md, "Civilisation qualification" step 2: an effect for this
    civilisation touches this entity and field and is `modelled = "no"`. Carries the transcribed
    `reason` so a caller does not have to re-open `effects.toml` to explain the refusal.

    **Interim**, like `query.EntityAbsent`/`query.CivilisationNotModelled` — T647 folds this into
    `gaps.py`'s full `KnowledgeGap` (data-model.md §7's closed cause `effect-not-modelled`).
    """

    civilisation: str
    kind: str
    id: str
    field: str
    reason: str
    cause: str = "effect-not-modelled"


def _require_str(table: Mapping[str, object], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EffectsError(f"effect.{key} must be a non-blank string, got {value!r}")
    return value


def _parse_selector(raw: object) -> tuple[SelectorEntry, ...]:
    if not isinstance(raw, list) or not raw:
        raise EffectsError(
            f"effect.selector must be a non-empty list of {{kind, id}} tables, got {raw!r}"
        )
    entries: list[SelectorEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            raise EffectsError(f"effect.selector entries must be tables, got {item!r}")
        entries.append(SelectorEntry(kind=_require_str(item, "kind"), id=_require_str(item, "id")))
    return tuple(entries)


def _optional_str(table: Mapping[str, object], key: str) -> str | None:
    """`table[key]` as a string, or `None` when the key is entirely absent — `Effect.__post_init__`
    is what decides whether a `None` is actually allowed here (`reason` only when `modelled ==
    "no"` is refused, `operation` only when `modelled == "yes"` is required); this only rejects a
    present-but-non-string value, which is always a malformed `effects.toml` regardless of
    `modelled`."""
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise EffectsError(f"effect.{key} must be a string when present, got {value!r}")
    return value


def _parse_effect(table: Mapping[str, object]) -> Effect:
    for key in _COMMON_REQUIRED_FIELDS:
        if key not in table:
            raise EffectsError(f"[[effect]] is missing required field {key!r}")
    modelled = table.get("modelled")
    if not isinstance(modelled, str):
        raise EffectsError(f"effect.modelled must be a string, got {modelled!r}")
    return Effect(
        civilisation=_require_str(table, "civilisation"),
        source_key=_require_str(table, "source_key"),
        source_text=_require_str(table, "source_text"),
        modelled=modelled,
        selector=_parse_selector(table.get("selector")),
        field=_require_str(table, "field"),
        validated_by=_require_str(table, "validated_by"),
        reason=_optional_str(table, "reason"),
        operation=_optional_str(table, "operation"),
        operand=table.get("operand"),
    )


def parse_effects_toml(text: str) -> tuple[Effect, ...]:
    """Parse one snapshot's `effects.toml` into effect records, in file order — order matters,
    because `apply_matched` applies every matching, modelled effect in exactly this order
    (contracts/knowledge-base.md, "Civilisation qualification" step 3: "apply each matching effect
    in file order")."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise EffectsError(f"effects.toml is not valid TOML: {exc}") from exc
    raw_effects = data.get("effect", [])
    if not isinstance(raw_effects, list):
        raise EffectsError("effects.toml: [[effect]] must be an array of tables")
    return tuple(_parse_effect(table) for table in raw_effects)


@functools.cache
def _effects(directory: str) -> tuple[Effect, ...]:
    """One packaged snapshot's parsed `effects.toml`, read directly through `importlib.resources`
    (FR-026, SC-006) and cached per directory — a snapshot directory is immutable once committed
    (FR-025), so re-reading it can never observe a different answer."""
    root = resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)
    text = root.joinpath("effects.toml").read_text(encoding="utf-8")
    return parse_effects_toml(text)


def _matches(effect: Effect, *, civilisation: str, kind: str, id: str, field: str) -> bool:
    if effect.civilisation != civilisation or effect.field != field:
        return False
    return any(entry.kind == kind and entry.id == id for entry in effect.selector)


def effects_for(
    directory: str, *, civilisation: str, kind: str, id: str, field: str
) -> tuple[Effect, ...]:
    """Every effect in this packaged snapshot whose civilisation, field and selector all match, in
    file order — whether or not it is modelled. Reading through this before deciding whether to
    apply is what makes "never half-applied" possible: the caller sees every match, not only the
    modelled ones, before deciding anything."""
    return tuple(
        effect
        for effect in _effects(directory)
        if _matches(effect, civilisation=civilisation, kind=kind, id=id, field=field)
    )


def _round_half_up(value: float) -> int:
    """This package's stated rounding convention for a fractional resource amount
    (`packages/knowledge/tests/test_query.py`'s module docstring): round half up, matching the
    community-known in-game value for a Korean Crossbowman (45 gold, 13 wood) rather than Python's
    own banker's rounding, which would round `12.5` to `12`."""
    return math.floor(value + 0.5)


def _apply_scalar(value: float, operation: str, operand: float) -> float | int:
    if operation == "multiply":
        return _round_half_up(value * operand)
    if operation == "add":
        return _round_half_up(value + operand)
    if operation == "set":
        return operand
    raise AssertionError(f"unreachable: unknown operation {operation!r}")  # pragma: no cover


def _apply_mapping(
    value: Mapping[str, int], operation: str, operand: Mapping[str, float]
) -> dict[str, int]:
    result = dict(value)
    for resource, amount in operand.items():
        if resource not in result:
            # The operand names a resource this entity's own cost does not carry at all (e.g. a
            # gold operand against a unit with no gold cost) — nothing to touch, not an error.
            continue
        if operation == "multiply":
            result[resource] = _round_half_up(result[resource] * amount)
        elif operation == "add":
            result[resource] = _round_half_up(result[resource] + amount)
        elif operation == "set":
            result[resource] = int(amount)
        else:
            raise AssertionError(
                f"unreachable: unknown operation {operation!r}"
            )  # pragma: no cover
    return result


def _apply_operation(value: object, operation: str, operand: object) -> object:
    if isinstance(value, Mapping) and isinstance(operand, Mapping):
        return _apply_mapping(value, operation, operand)
    if isinstance(value, int | float) and isinstance(operand, int | float):
        return _apply_scalar(float(value), operation, float(operand))
    raise EffectsError(
        f"cannot apply operation {operation!r} with operand {operand!r} to value {value!r} — "
        "value and operand must both be mappings (a cost) or both be plain numbers"
    )


def apply_matched(
    matched: Sequence[Effect], *, civilisation: str, kind: str, id: str, field: str, value: object
) -> tuple[object, tuple[Effect, ...]] | EffectNotModelled:
    """The pure half of civilisation qualification (contracts/knowledge-base.md, "Civilisation
    qualification" steps 2-3), given `matched` — already filtered to one civilisation, entity and
    field, in file order (`effects_for`).

    If **any** matched effect is `modelled = "no"`, this refuses with `EffectNotModelled` and
    applies nothing at all — not even a modelled match found alongside it. That is research.md D5's
    "a bonus is never half-applied", read literally: an unmodelled effect touching this field means
    which fields this civilisation's bonuses touch here is not fully known, so no partial answer is
    trustworthy. Otherwise every modelled match is applied, in order, and the adjusted value is
    returned together with the effects that produced it.
    """
    not_modelled = [effect for effect in matched if effect.modelled == "no"]
    if not_modelled:
        first = not_modelled[0]
        assert first.reason is not None  # enforced by Effect.__post_init__
        return EffectNotModelled(
            civilisation=civilisation, kind=kind, id=id, field=field, reason=first.reason
        )
    applied = tuple(effect for effect in matched if effect.modelled == "yes")
    result = value
    for effect in applied:
        assert effect.operation is not None  # enforced by Effect.__post_init__
        result = _apply_operation(result, effect.operation, effect.operand)
    return result, applied


def apply(
    directory: str, *, civilisation: str, kind: str, id: str, field: str, value: object
) -> tuple[object, tuple[Effect, ...]] | EffectNotModelled:
    """`apply_matched`, reading its `matched` effects from one packaged snapshot's real
    `effects.toml` (`effects_for`) — the one function `query.py` calls."""
    matched = effects_for(directory, civilisation=civilisation, kind=kind, id=id, field=field)
    return apply_matched(
        matched, civilisation=civilisation, kind=kind, id=id, field=field, value=value
    )
