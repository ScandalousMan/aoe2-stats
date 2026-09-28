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
  from it (FR-031's provenance) — byte-for-byte for every row except a Team Bonus's: those five
  (`test_bullet_coverage.py`'s own `_bullets_for` docstring) prepend the literal label
  `"Team Bonus: "` to the source's own bullet text, since the source itself states that heading
  once, separately from the bullet it governs, and every `[[effect]]` row for a Team Bonus needs
  its own `source_text` to carry the distinction on its own.
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
- `condition` — **T652u** (2026-09-28, repository owner's arbitration of the fourth review,
  amending research.md D5: "a conditional bonus is a rule, and is modelled"). Optional, closed:
  `"age"` (`operand` becomes a table keyed by the pack's own age number, `"1"`-`"4"`, and a query at
  an age absent from the table answers the plain baseline, not a gap), `"researched"` (gated on
  `condition_technology` having been researched), `"team"` (the effect's own `civilisation` is the
  bonus's owner; it applies to every civilisation on the owner's team, decided by `Context.team`,
  never by `civilisation` equality alone). Absent means unconditional, the pre-T652u behaviour
  unchanged. A conditional effect is still `modelled = "yes"`/`"no"` exactly as any other — "no"
  still means the field it touches stays gapped (Kamandaran below: conditional on research, but the
  wood amount the pack never states is missing knowledge, not unplaced match state, so it stays
  refused) — `condition` only changes *when* a modelled effect's operand applies, never whether an
  unmodelled one is half-applied.
- `condition_technology` — required, and only present, when `condition == "researched"`: the
  technology id (as `rules.json` keys it) that must be in `Context.researched` for the effect to
  hold.

**T652g: `[[civilisation_id]]`, the replay's raw civilisation integer mapped to this pack's
civilisation name.** This is a second, independent record `effects.toml` carries, not an
`[[effect]]` entry: a replay's `match-started` participant names its civilisation only as the
game's own raw integer (`ParticipantEntry.civilisation`), and nothing else in this pack or this
repository translates that integer into one of the pack's own civilisation-name strings
(`coverage.py`'s own module docstring records why). Moved here from what was, before this task,
`coverage.py`'s own unversioned, undigested `_DEFAULT_CIVILISATION_NAMES` module constant — the
same game knowledge as an `[[effect]]`'s `selector`, and wrong for the same reason a table outside
the snapshot is wrong: the game's civilisation numbering shifts when civilisations are added, and
an un-digested table cannot be qualified by build (FR-023) or covered by the snapshot's own
digest (FR-024). Each entry's `civilisation` and `validated_by` carry the same measurement
discipline as an `[[effect]]`'s: read directly against the committed golden recordings and
cross-checked against `data.json`'s per-civilisation membership and the per-civilisation tree
files' `node_status` — see the header comment above the `[[civilisation_id]]` entries at the foot
of each snapshot's own `effects.toml` for the full per-id reading. A raw id this table does not
name is `coverage.py`'s to resolve to its `unknown-civilisation-{raw_id}` placeholder, never this
module's to guess.

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

#: data-model.md §6's closed `condition` set (T652u) — `None` (absent) means unconditional.
CONDITIONS: Final[frozenset[str]] = frozenset({"age", "researched", "team"})

#: The pack's own age numbering (confirmed directly: unit 358 "Pikeman" = 3, unit 359 "Halberdier"
#: = 4, `packages/knowledge/tests/test_effects.py`'s own Parthian Tactics test) — 1=Dark, 2=Feudal,
#: 3=Castle, 4=Imperial. An `condition = "age"` effect's `operand` table is keyed by one of these,
#: spelled as a string (TOML's own key convention, matching `SelectorEntry.id`).
_AGE_KEYS: Final[frozenset[str]] = frozenset({"1", "2", "3", "4"})

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
    of data-model.md §6's closed set, `condition` is not one of data-model.md §6's closed set
    (T652u), `condition_technology` is present without `condition == "researched"` or missing when
    it is, or `selector` is empty or malformed. Raised at parse time, in place of returning an
    `Effect` that looks complete but has a hole a query could fall through.
    """


class ContextRequired(TypeError):
    """T652u: a query reached a **modelled** conditional effect (`condition` is `"age"`,
    `"researched"` or `"team"`) without the piece of `Context` that decides whether it holds — the
    age, the researched-technology set, or the team roster. Raised, never returned as part of the
    answer-or-gap union, the same way Python's own keyword-only `civilisation` raises when a caller
    omits it (contracts/knowledge-base.md, "The query surface": "a query that reaches a conditional
    effect without the input that decides it raises ... the caller asked for a value only the match
    can fix, and neither the baseline nor a guessed age is an answer"). A subclass of `TypeError`
    for exactly that reason — a missing match-state input is a caller defect, not game knowledge a
    query can refuse and move on from, so it is never a `gaps.KnowledgeGap`
    (`coverage.py` catches this directly: reaching a modelled conditional effect with no context to
    evaluate it is complete knowledge, not a gap — see that module's own handling)."""


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
    condition: str | None = None
    condition_technology: str | None = None

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
        if self.condition is not None and self.condition not in CONDITIONS:
            raise EffectsError(
                f"effect.condition must be one of {sorted(CONDITIONS)} or absent, "
                f"got {self.condition!r}"
            )
        if self.condition == "researched":
            if (
                not isinstance(self.condition_technology, str)
                or not self.condition_technology.strip()
            ):
                raise EffectsError(
                    "effect.condition_technology is required and must be a non-blank string "
                    'when condition = "researched"'
                )
        elif self.condition_technology is not None:
            raise EffectsError(
                'effect.condition_technology must be absent unless condition = "researched"'
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
            if self.condition == "age":
                if not isinstance(self.operand, Mapping) or not self.operand:
                    raise EffectsError(
                        "effect.operand must be a non-empty table keyed by age when "
                        'condition = "age", got ' + repr(self.operand)
                    )
                if not frozenset(self.operand.keys()) <= _AGE_KEYS:
                    raise EffectsError(
                        f"effect.operand's age table keys must all be one of "
                        f"{sorted(_AGE_KEYS)}, got {sorted(self.operand.keys())!r}"
                    )


@dataclass(frozen=True, slots=True)
class Context:
    """T652u: the match state a **modelled** conditional effect (`Effect.condition`) needs to
    decide whether it holds right now (contracts/knowledge-base.md, "The query surface": "the age,
    the technologies researched, and the civilisations on the player's team, the player's own
    included"). Which condition held at a given moment is a question about the match, answered by
    the caller — never guessed by this package (research.md D5's amendment).

    Every field is independently optional (`None`, not an empty collection) so a caller supplying
    some match state but not all of it still raises `ContextRequired` exactly at the piece it left
    out, rather than an empty `frozenset()` being mistaken for "known to be empty" — omitting
    `researched` entirely must not be read as "researched nothing".

    - `age` — the pack's own age number, 1 (Dark) to 4 (Imperial).
    - `researched` — the technology ids (as `rules.json` keys them) the player has researched.
    - `team` — the civilisation names on the player's team, the player's own included — a `"team"`
      effect matches every civilisation in this set, not the bonus owner alone.
    """

    age: int | None = None
    researched: frozenset[str] | None = None
    team: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class EffectNotModelled:
    """contracts/knowledge-base.md, "Civilisation qualification" step 2: an effect for this
    civilisation touches this entity and field and is `modelled = "no"`. Carries the transcribed
    `reason` so a caller does not have to re-open `effects.toml` to explain the refusal.

    This stays the return type of `apply`/`apply_matched` — the pure, file-free half of
    civilisation qualification these functions implement has no `build` to report and no register
    to consult, so it cannot construct the full `gaps.KnowledgeGap` itself. **T647**: `query.py`'s
    `_civilisation_qualified` is the one caller, and it folds this value into a real
    `gaps.KnowledgeGap` (`cause="effect-not-modelled"`, `detail=` this `reason`) before returning
    to its own caller — no parallel gap vocabulary reaches outside this module.
    """

    civilisation: str
    kind: str
    id: str
    field: str
    reason: str
    cause: str = "effect-not-modelled"


#: TOML keys required on every `[[civilisation_id]]` table (T652g).
_CIVILISATION_ID_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "raw_id",
    "civilisation",
    "validated_by",
)


@dataclass(frozen=True, slots=True)
class CivilisationId:
    """T652g: one replay-native civilisation integer mapped to the pack's own civilisation name it
    identifies. See this module's docstring, "T652g: `[[civilisation_id]]`" for why this table
    lives in `effects.toml` rather than as code, and each committed snapshot's own `effects.toml`
    header comment (immediately above its `[[civilisation_id]]` entries) for how every mapping was
    actually measured — a summary of that same measurement is repeated in each entry's own
    `validated_by` below, in the same spirit as `Effect.validated_by`."""

    raw_id: int
    civilisation: str
    validated_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw_id, int) or isinstance(self.raw_id, bool):
            raise EffectsError(f"civilisation_id.raw_id must be an int, got {self.raw_id!r}")
        for name, value in (
            ("civilisation", self.civilisation),
            ("validated_by", self.validated_by),
        ):
            if not isinstance(value, str) or not value.strip():
                raise EffectsError(
                    f"civilisation_id.{name} must be a non-blank string, got {value!r}"
                )


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
        condition=_optional_str(table, "condition"),
        condition_technology=_optional_str(table, "condition_technology"),
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


def _parse_civilisation_id(table: Mapping[str, object]) -> CivilisationId:
    for key in _CIVILISATION_ID_REQUIRED_FIELDS:
        if key not in table:
            raise EffectsError(f"[[civilisation_id]] is missing required field {key!r}")
    raw_id = table.get("raw_id")
    if not isinstance(raw_id, int) or isinstance(raw_id, bool):
        raise EffectsError(f"civilisation_id.raw_id must be an int, got {raw_id!r}")
    return CivilisationId(
        raw_id=raw_id,
        civilisation=_require_str(table, "civilisation"),
        validated_by=_require_str(table, "validated_by"),
    )


def parse_civilisation_ids_toml(text: str) -> tuple[CivilisationId, ...]:
    """T652g: parse one snapshot's `effects.toml` `[[civilisation_id]]` entries into records.
    Unlike `[[effect]]`, file order carries no meaning here — each `raw_id` names at most one
    civilisation, checked below, and there is no "apply every match in order" step to preserve."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise EffectsError(f"effects.toml is not valid TOML: {exc}") from exc
    raw_entries = data.get("civilisation_id", [])
    if not isinstance(raw_entries, list):
        raise EffectsError("effects.toml: [[civilisation_id]] must be an array of tables")
    entries = tuple(_parse_civilisation_id(table) for table in raw_entries)
    seen: dict[int, str] = {}
    for entry in entries:
        if entry.raw_id in seen:
            raise EffectsError(
                f"effects.toml: civilisation_id.raw_id {entry.raw_id} is duplicated "
                f"({seen[entry.raw_id]!r} and {entry.civilisation!r})"
            )
        seen[entry.raw_id] = entry.civilisation
    return entries


@functools.cache
def _civilisation_ids(directory: str) -> tuple[CivilisationId, ...]:
    """One packaged snapshot's parsed `[[civilisation_id]]` entries (T652g), read directly through
    `importlib.resources` (FR-026) and cached per directory — same immutability argument as
    `_effects` above (FR-025)."""
    root = resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)
    text = root.joinpath("effects.toml").read_text(encoding="utf-8")
    return parse_civilisation_ids_toml(text)


def civilisation_id_names(directory: str) -> Mapping[int, str]:
    """T652g: this packaged snapshot's own raw-civilisation-id-to-name table, keyed by `raw_id` —
    every `[[civilisation_id]]` entry its own `effects.toml` carries, covered by that snapshot's
    digest (FR-024) and therefore qualified by the build it describes (FR-023). A raw id absent
    here is not this function's problem to solve: `coverage.py`'s own
    `unknown-civilisation-{raw_id}` fallback is what turns that absence into a gap, never a guess
    (FR-038). Empty for a snapshot whose `effects.toml` carries no such table at all (e.g.
    `aoe2techtree-test-stub`, whose `civilisations_modelled` is itself empty) — nothing calls this
    for a name it needs to resolve."""
    return {entry.raw_id: entry.civilisation for entry in _civilisation_ids(directory)}


def _matches(effect: Effect, *, civilisation: str, kind: str, id: str, field: str) -> bool:
    if effect.field != field:
        return False
    if not any(entry.kind == kind and entry.id == id for entry in effect.selector):
        return False
    if effect.condition == "team" and effect.modelled == "yes":
        # T652u remediation, defect 1 (coordinator, measured against the working tree): a team
        # effect's *value*, for every civilisation — not only its owner — depends on team
        # composition, because the owner might be that civilisation's ally. Matching is therefore
        # structural only (selector and field), regardless of `civilisation`: whether this query
        # actually needs `Context.team` to decide is `apply_matched`'s job
        # (`_resolve_conditional_operand`'s own `condition == "team"` branch), which raises
        # `ContextRequired` when `context` cannot say either way — never `_matches` silently
        # deciding "no ally" by only ever looking at the effect's own owner. Scoped to
        # `modelled == "yes"`: no committed effect pairs `condition = "team"` with
        # `modelled = "no"` today.
        return True
    return effect.civilisation == civilisation


def effects_for(
    directory: str, *, civilisation: str, kind: str, id: str, field: str
) -> tuple[Effect, ...]:
    """Every effect in this packaged snapshot whose selector and field match, and whose
    civilisation matches too — except a modelled `condition = "team"` effect, which matches
    *every* civilisation's query regardless (see `_matches`): its value depends on team
    composition for every civilisation, not only its own owner, and only `apply_matched` (with
    `context`) can decide whether that dependency actually holds. In file order — whether or not
    it is modelled. Reading through this before deciding whether to apply is what makes "never
    half-applied" possible: the caller sees every match, not only the modelled ones, before
    deciding anything."""
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


def _apply_scalar(value: float, operation: str, operand: float, *, field: str) -> int | float:
    if operation == "multiply":
        if field == "production_time":
            # T652u, data-model.md §6's amended rounding row: "'works X% faster' divides it by
            # 1 + X, so a Persians Villager in the Feudal Age takes 25 ÷ 1.10 = 22.7 s" — a time
            # keeps its fraction (never rounded), and the transcribed `operand` is the raw
            # percentage X (e.g. `0.10`), not a pre-computed factor, so this divides rather than
            # multiplies. Every other scalar field this package models never reaches a `multiply`
            # today (production_time is the only one a "works X% faster" bonus touches).
            return value / (1 + operand)
        return _round_half_up(value * operand)
    if operation == "add":
        # T652p (f): no committed effect applies a scalar `add` to a field that must stay
        # non-negative — the only scalar fields this package's `set` effects touch
        # (age_requirement, production_time) are never modified by `add`, and the one real
        # `add` effect in the pack (Saracens' Market wood discount) is a mapping (a cost),
        # guarded in `_apply_mapping` below. No guard is added here because there is no case
        # to test it against; add one the day a scalar `add` effect against a cost-like field
        # is transcribed.
        return _round_half_up(value + operand)
    if operation == "set":
        if field == "production_time":
            # T652u: a time keeps its fraction — data-model.md §6's rounding row: `set` "replaces
            # the value with the operand", so it is not forced to `int`.
            return operand
        # T652p (d): age_requirement is the only other scalar field this package models, and it
        # is an integer — `set` is a direct replacement, not a fractional derivation, so there is
        # nothing to round, but the result must still be typed as an int rather than the raw
        # float `operand`. Left uncaught before that fix, `age_requirement(436, "Persians")`-
        # shaped queries answered `3.0` instead of `3`.
        return int(operand)
    raise AssertionError(f"unreachable: unknown operation {operation!r}")  # pragma: no cover


def _apply_mapping(
    value: Mapping[str, int],
    operation: str,
    operand: Mapping[str, float],
    *,
    context: str = "",
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
            pre_effect_value = result[resource]
            adjusted = _round_half_up(pre_effect_value + amount)
            if adjusted < 0:
                # T652p (f): unreachable by any committed effect today, but `add` is live data
                # (Saracens' Market wood discount, a mapping `add` — the free-technology model
                # T652o added uses `set`, never `add`) and the invariant — a cost never goes
                # negative — was previously unasserted. Zero is a valid cost (a free
                # technology genuinely costs nothing) and must not raise; only a result below
                # zero is a defect.
                raise EffectsError(
                    f"applying 'add' to resource {resource!r} would drive it negative: "
                    f"{pre_effect_value!r} + {amount!r} = {adjusted!r}"
                    + (f" ({context})" if context else "")
                )
            result[resource] = adjusted
        elif operation == "set":
            result[resource] = int(amount)
        else:
            raise AssertionError(
                f"unreachable: unknown operation {operation!r}"
            )  # pragma: no cover
    return result


def _apply_operation(
    value: object, operation: str, operand: object, *, field: str, context: str = ""
) -> object:
    if isinstance(value, Mapping) and isinstance(operand, Mapping):
        return _apply_mapping(value, operation, operand, context=context)
    if isinstance(value, int | float) and isinstance(operand, int | float):
        return _apply_scalar(float(value), operation, float(operand), field=field)
    raise EffectsError(
        f"cannot apply operation {operation!r} with operand {operand!r} to value {value!r} — "
        "value and operand must both be mappings (a cost) or both be plain numbers"
    )


def _resolve_conditional_operand(
    effect: Effect, *, civilisation: str, context: Context | None
) -> tuple[object, bool]:
    """T652u: given one **modelled** matched `effect`, decide the operand it actually contributes
    this time (contracts/knowledge-base.md, "Civilisation qualification" step 3: "apply each
    matching effect whose condition holds in `context`"). Returns `(operand, True)` when the
    effect applies, or `(None, False)` when its condition genuinely does not hold under `context`
    (e.g. the wrong age, the technology not yet researched, or a civilisation off the owner's team)
    — not an error, just nothing to contribute; the baseline stands unadjusted for this effect.

    Raises `ContextRequired` when `context` (or the one piece of it this effect's own `condition`
    needs) is missing entirely — "reaching a conditional effect without the input that decides it
    raises ... neither the baseline nor a guessed age is an answer" (contracts/knowledge-base.md).
    An unconditional effect (`condition is None`) never reaches any of these checks at all — the
    contrast case contracts/knowledge-base.md itself asks for ("a query whose matching effects are
    unconditional ignores it").
    """
    if effect.condition is None:
        return effect.operand, True
    if effect.condition == "age":
        if context is None or context.age is None:
            raise ContextRequired(
                f"effect {effect.source_text!r} (civilisation={effect.civilisation!r}) is "
                "conditional on age, and reaching it needs Context(age=...) — neither the "
                "baseline nor a guessed age is an answer"
            )
        assert isinstance(effect.operand, Mapping)  # enforced by Effect.__post_init__
        key = str(context.age)
        if key not in effect.operand:
            return None, False
        return effect.operand[key], True
    if effect.condition == "researched":
        if context is None or context.researched is None:
            raise ContextRequired(
                f"effect {effect.source_text!r} (civilisation={effect.civilisation!r}) is "
                "conditional on a researched technology, and reaching it needs "
                "Context(researched=...)"
            )
        assert effect.condition_technology is not None  # enforced by Effect.__post_init__
        if effect.condition_technology not in context.researched:
            return None, False
        return effect.operand, True
    if effect.condition == "team":
        if context is None or context.team is None:
            raise ContextRequired(
                f"effect {effect.source_text!r} (civilisation={effect.civilisation!r}) is a team "
                "bonus, and reaching it needs Context(team=...) to know whether "
                f"{civilisation!r} is one of the owner's teammates"
            )
        if effect.civilisation not in context.team:
            return None, False
        return effect.operand, True
    raise AssertionError(f"unreachable: unknown condition {effect.condition!r}")  # pragma: no cover


def apply_matched(
    matched: Sequence[Effect],
    *,
    civilisation: str,
    kind: str,
    id: str,
    field: str,
    value: object,
    context: Context | None = None,
) -> tuple[object, tuple[Effect, ...]] | EffectNotModelled:
    """The pure half of civilisation qualification (contracts/knowledge-base.md, "Civilisation
    qualification" steps 2-3), given `matched` — already filtered to one entity and field, in file
    order (`effects_for`) — and `context`, the match state a **modelled** conditional effect needs
    (T652u).

    If **any** matched effect is `modelled = "no"`, this refuses with `EffectNotModelled` and
    applies nothing at all — not even a modelled match found alongside it. That is research.md D5's
    "a bonus is never half-applied", read literally: an unmodelled effect touching this field means
    which fields this civilisation's bonuses touch here is not fully known, so no partial answer is
    trustworthy. This check never needs `context` at all: a refusal is unconditional on the match
    state, so it is decided first, before any `ContextRequired` could even be raised.

    Otherwise, every modelled match is resolved against `context` (`_resolve_conditional_operand`)
    in file order: an unconditional effect always contributes its own operand; a conditional one
    contributes its operand only when its condition holds under `context`, contributes nothing when
    `context` says it does not (the baseline stands, unadjusted, for that effect alone — not a
    gap), and raises `ContextRequired` when `context` cannot say either way. Every effect that did
    contribute is applied, in order, and the adjusted value is returned together with exactly the
    effects that were actually applied — never the effects that merely matched but did not hold.
    """
    not_modelled = [effect for effect in matched if effect.modelled == "no"]
    if not_modelled:
        first = not_modelled[0]
        assert first.reason is not None  # enforced by Effect.__post_init__
        return EffectNotModelled(
            civilisation=civilisation, kind=kind, id=id, field=field, reason=first.reason
        )
    candidates = tuple(effect for effect in matched if effect.modelled == "yes")
    resolved: list[tuple[Effect, object]] = []
    for effect in candidates:
        operand, holds = _resolve_conditional_operand(
            effect, civilisation=civilisation, context=context
        )
        if holds:
            resolved.append((effect, operand))
    result = value
    applied: list[Effect] = []
    error_context = f"civilisation={civilisation!r} kind={kind!r} id={id!r} field={field!r}"
    for effect, operand in resolved:
        assert effect.operation is not None  # enforced by Effect.__post_init__
        result = _apply_operation(
            result, effect.operation, operand, field=field, context=error_context
        )
        applied.append(effect)
    return result, tuple(applied)


def apply(
    directory: str,
    *,
    civilisation: str,
    kind: str,
    id: str,
    field: str,
    value: object,
    context: Context | None = None,
) -> tuple[object, tuple[Effect, ...]] | EffectNotModelled:
    """`apply_matched`, reading its `matched` effects from one packaged snapshot's real
    `effects.toml` (`effects_for`) — the one function `query.py` calls."""
    matched = effects_for(directory, civilisation=civilisation, kind=kind, id=id, field=field)
    return apply_matched(
        matched,
        civilisation=civilisation,
        kind=kind,
        id=id,
        field=field,
        value=value,
        context=context,
    )
