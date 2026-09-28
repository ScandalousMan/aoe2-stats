"""The group-silence observable (T633, FR-013, FR-014): `participant.group_silence_episodes`.

Computed from `units-commanded` events only ([contracts/canonical-events.md](
../../../../specs/006-replay-analysis-foundations/contracts/canonical-events.md)). It consumes no
`object-deleted` and no `market-transaction` event, and is never summed with either (FR-014) — the
accumulator below never reads either kind.

The blind spot, stated here because the datum's method names it (register
`participant.group_silence_episodes`). Only `move`, `interact` and `order` carry decoded unit ids
(`UnitsCommandedPayload.command_class`); `formation`, `stance`, `patrol`, `stop` and the rest arrive
with an **empty** id list (T626), so exactly the commands that park a military group — hold
position, patrol a perimeter, garrison and wait — are invisible to this accumulator. A group parked
by one of those commands reads as silent, identically to a group that was genuinely never commanded
again. This is a structural limit of the input, not a per-instance judgement, so it is expressed as
a hard cap on the banding: `ConfidenceLevel.HIGH` is never assigned by `_band`, and
`GroupSilenceEpisode.__post_init__` refuses to construct one that carries it.

**This is the datum a reader is most likely to misread as a loss figure.** It is not: a unit leaves
the command log the moment its owner stops selecting it, alive or dead, and a unit never
individually selected is never in the log at all (see the register's `non_claim`). Every
`GroupSilenceEpisode` therefore carries `non_claim` as a required field, read verbatim from the
register at import time and checked for equality at construction — never a comment near the type,
and never a second copy of the sentence that could drift from the one in `register.toml`.

The banding thresholds (`REPEAT_MIN`, `MIN_SILENCE_MS`, `MEDIUM_INTENSITY`, `MEDIUM_DURATION_RATIO`)
are **not** Python constants. They are parsed out of the register entry's own `method` text at
import time (`_PARAMETERS` below), so that changing one is a register edit with a regenerated
`REGISTER.md` — the task this module was built for is explicit that the banding "lives in the
register entry's method" and that changing it is "a register change with a regenerated view, not a
constant edit."

Confidence basis, per instance
-------------------------------
`intensity` — the number of times the group (the same set of two or more unit object ids) was named
together in one participant's `move`, `interact` or `order` command before it was last named.
`duration_ratio` — the observed silence length divided by the match time remaining after the
group's last command, where "observed silence" ends at the participant's `participant-resigned`
clock if they resigned, or otherwise at `match-ended`, but "remaining" is always measured to the
true `match-ended` clock. A silence cut short by resignation is therefore a weaker signal than one
that ran to the match's own end, because nothing is known about what would have happened after the
participant left.

An episode publishes only when the group was named together at least `REPEAT_MIN` times and the
resulting silence is at least `MIN_SILENCE_MS` long — both read from the register text, not invented
here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast

from aoe2stats_core.replay.events import (
    CanonicalEvent,
    EventKind,
    MatchEndedPayload,
    UnitsCommandedPayload,
)
from aoe2stats_core.truth.confidence import Confidence, ConfidenceLevel
from aoe2stats_core.truth.provenance import Method, Provenance
from aoe2stats_core.truth.register import REGISTER, RegisterError
from aoe2stats_core.truth.tiers import Tier

_DATUM_ID = "participant.group_silence_episodes"
_METHOD_ID = "group-silence.banding"
_METHOD_VERSION = "1"

# Only these three command classes carry decoded unit ids (T626, T625's `_UNIT_COMMANDS` is the
# empty-id-list complement of this set). See the module docstring's "blind spot" paragraph.
_DECODED_COMMAND_CLASSES = frozenset({"move", "interact", "order"})

# A group is two or more unit ids; a lone id commanded alone is one unit, not "a group".
_MIN_GROUP_SIZE = 2

_PARAM = re.compile(r"([A-Z_]+)=(\d+(?:\.\d+)?)")
_REQUIRED_PARAMS = frozenset(
    {"REPEAT_MIN", "MIN_SILENCE_MS", "MEDIUM_INTENSITY", "MEDIUM_DURATION_RATIO"}
)


def _read_parameters(method_text: str) -> Mapping[str, float]:
    """Parse the banding thresholds out of the register entry's own `method` prose.

    Refuses at import (`RegisterError`, the same exception family the register itself raises) if a
    required threshold is missing — the register text and this parser must agree, and a silent
    fallback to an invented default would be exactly the kind of value this feature exists to
    refuse.
    """
    params = {name: float(value) for name, value in _PARAM.findall(method_text)}
    missing = _REQUIRED_PARAMS - params.keys()
    if missing:
        raise RegisterError(
            f"{_DATUM_ID}: method text is missing banding parameter(s) "
            f"{sorted(missing)} — silence.py cannot band without them"
        )
    return params


_ENTRY = REGISTER[_DATUM_ID]
_PARAMETERS = _read_parameters(_ENTRY.method)
if not _ENTRY.non_claim:
    raise RegisterError(f"{_DATUM_ID}: register entry carries no non_claim (FR-013)")
NON_CLAIM: str = _ENTRY.non_claim

_INPUTS: tuple[str, ...] = (
    "event.units_commanded.unit_object_ids",
    "event.clock_ms",
    "event.participant",
    "event.match_ended.final_clock_ms",
)


@dataclass(frozen=True, slots=True)
class GroupSilenceEpisode:
    """One instance of the group-silence observable (FR-013).

    `non_claim` is a required field of this type, not a comment beside it — this is the datum a
    reader is most likely to misread as a loss figure. It is checked at construction against the
    register's own text, so it cannot drift or be omitted by a caller.
    """

    participant: int
    unit_objects: tuple[int, ...]
    occurrences: int
    last_commanded_at_ms: int
    silence_ends_at_ms: int
    confidence: Confidence
    non_claim: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if len(self.unit_objects) < _MIN_GROUP_SIZE:
            raise ValueError("a group-silence episode needs two or more unit object ids")
        if self.occurrences < 1:
            raise ValueError("a group-silence episode needs at least one occurrence")
        if self.silence_ends_at_ms < self.last_commanded_at_ms:
            raise ValueError("a group-silence episode cannot end before its last command")
        if not isinstance(self.non_claim, str) or not self.non_claim.strip():
            raise ValueError("a group-silence episode must carry a non-empty non_claim")
        if self.non_claim != NON_CLAIM:
            raise ValueError(
                "a group-silence episode's non_claim must match the register entry verbatim"
            )
        if self.confidence.level is ConfidenceLevel.HIGH:
            # The blind spot caps the level the banding may assign (register `method`). A HIGH
            # instance would mean the banding — or a caller constructing one by hand — ignored
            # that cap, which is a defect, not a real result.
            raise ValueError(
                "a group-silence episode's confidence is capped below high by its documented "
                "blind spot; high is never a real instance of this datum"
            )
        if self.provenance.datum != _DATUM_ID:
            raise ValueError(f"a group-silence episode's provenance must bind to {_DATUM_ID!r}")


@dataclass(slots=True)
class _GroupState:
    occurrences: int = 0
    last_seen_ms: int = 0


def _band(intensity: int, duration_ratio: float) -> ConfidenceLevel:
    """Band `(intensity, duration_ratio)` into a confidence level.

    Thresholds come from `_PARAMETERS`, parsed from the register text (module docstring). `HIGH` is
    never returned: the blind spot this datum's method documents caps the level the banding may
    assign at `MEDIUM`.
    """
    if (
        intensity >= _PARAMETERS["MEDIUM_INTENSITY"]
        and duration_ratio >= _PARAMETERS["MEDIUM_DURATION_RATIO"]
    ):
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def compute_group_silence_episodes(
    events: Iterable[CanonicalEvent],
) -> tuple[GroupSilenceEpisode, ...]:
    """Compute every group-silence episode over one canonical event stream.

    Consumes `units-commanded`, `participant-resigned` and `match-ended` only — never
    `object-deleted` or `market-transaction` (FR-014). Returns an empty tuple when the stream
    carries no `match-ended` event: without the true match end, "the time remaining" cannot be
    measured and no episode can be published, only guessed at, which this module never does.
    """
    groups: dict[tuple[int, frozenset[int]], _GroupState] = {}
    resigned_at: dict[int, int] = {}
    match_end_ms: int | None = None

    for event in events:
        if event.kind is EventKind.MATCH_ENDED:
            match_end_ms = cast(MatchEndedPayload, event.payload).final_clock_ms
            continue
        if event.participant is None:
            continue
        if event.kind is EventKind.PARTICIPANT_RESIGNED:
            resigned_at[event.participant] = event.clock_ms
            continue
        if event.kind is not EventKind.UNITS_COMMANDED:
            continue
        payload = cast(UnitsCommandedPayload, event.payload)
        if payload.command_class not in _DECODED_COMMAND_CLASSES:
            continue
        group = frozenset(payload.unit_objects)
        if len(group) < _MIN_GROUP_SIZE:
            continue
        key = (event.participant, group)
        state = groups.get(key)
        if state is None:
            groups[key] = _GroupState(occurrences=1, last_seen_ms=event.clock_ms)
        else:
            state.occurrences += 1
            state.last_seen_ms = event.clock_ms

    if match_end_ms is None:
        return ()

    episodes: list[GroupSilenceEpisode] = []
    for (participant, group), state in groups.items():
        if state.occurrences < _PARAMETERS["REPEAT_MIN"]:
            continue
        remaining_ms = match_end_ms - state.last_seen_ms
        if remaining_ms <= 0:
            continue
        silence_ends_at_ms = min(resigned_at.get(participant, match_end_ms), match_end_ms)
        silence_ms = silence_ends_at_ms - state.last_seen_ms
        if silence_ms < _PARAMETERS["MIN_SILENCE_MS"]:
            continue
        duration_ratio = silence_ms / remaining_ms
        level = _band(state.occurrences, duration_ratio)
        basis = (
            f"commanded together {state.occurrences} times before the last command at "
            f"{state.last_seen_ms} ms; the observed silence covers {silence_ms} ms of the "
            f"{remaining_ms} ms remaining in the match ({duration_ratio:.0%})"
        )
        confidence = Confidence(level=level, basis=basis)
        provenance = Provenance(
            datum=_DATUM_ID,
            tier=Tier.INFERRED,
            method=Method(id=_METHOD_ID, version=_METHOD_VERSION),
            inputs=_INPUTS,
            confidence=confidence,
            non_claim=NON_CLAIM,
        )
        episodes.append(
            GroupSilenceEpisode(
                participant=participant,
                unit_objects=tuple(sorted(group)),
                occurrences=state.occurrences,
                last_commanded_at_ms=state.last_seen_ms,
                silence_ends_at_ms=silence_ends_at_ms,
                confidence=confidence,
                non_claim=NON_CLAIM,
                provenance=provenance,
            )
        )
    episodes.sort(key=lambda e: (e.participant, e.last_commanded_at_ms, e.unit_objects))
    return tuple(episodes)
