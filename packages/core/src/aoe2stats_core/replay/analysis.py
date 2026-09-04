"""The extraction Protocol and the published-analysis value objects.

`packages/core` holds this Protocol and nothing else replay-related — no parser, no bytes on disk,
no network — for the same reason `validation.py` beside it does (constitution V): `core` is what
`apps/api` imports, and the API must never load an engine. The concrete adapter that satisfies
`ReplayExtractor` lives in `packages/replay-engine`, imported only by the ingester/analyzer path.

See `specs/003-player-search-match-analysis/contracts/analysis.md` for the full contract this
module implements, including why every field name here is load-bearing (FR-043, FR-043a, FR-043b):
identifiers instead of resolved names, `age_up_commands` instead of `age_up_times`,
`villagers_ordered` instead of `villagers` or `villagers_trained`, and no resource or reconstructed
quantity anywhere. `MatchTimeline` is deliberately narrower than a full match reconstruction — a
`.aoe2record` is a command log, not a state log, and this module publishes only what was measured.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aoe2stats_core.replay.validation import EngineParseError, MalformedArchiveError

__all__ = [
    "BuildEvent",
    "MatchTimeline",
    "ParticipantTimeline",
    "ReplayExtractor",
    "ResearchEvent",
    "TrainingEvent",
]


@dataclass(frozen=True, slots=True)
class BuildEvent:
    """One building placed, identified and timed only — no name, no resolved outcome."""

    building_id: int
    world_time_ms: int


@dataclass(frozen=True, slots=True)
class TrainingEvent:
    """One training order, net of nothing: `amount` is what the command itself carries.

    `villagers_ordered` on `ParticipantTimeline` is the netted count derived from these; this event
    is the raw order, at the building that issued it.
    """

    unit_id: int
    amount: int
    building_id: int
    world_time_ms: int


@dataclass(frozen=True, slots=True)
class ResearchEvent:
    """One technology order, first occurrence only — a double-click issues the same command
    twice, and the second is not a second research (contract's "First occurrence only")."""

    technology_id: int
    world_time_ms: int


@dataclass(frozen=True, slots=True)
class ParticipantTimeline:
    """One participant's side of a `MatchTimeline`.

    Every field here is exactly what `contracts/analysis.md` specifies, in that name, for the
    reasons the contract gives in "Every name in there is load-bearing" — most pointedly
    `villagers_ordered` (FR-043b): a count of training *commands* net of observed cancellations,
    never a population, and never named in a way that could be misread as one.
    """

    profile_id: int
    player_number: int
    civ_id: int
    resolved_team_id: int
    builds: Sequence[BuildEvent]
    trainings: Sequence[TrainingEvent]
    researches: Sequence[ResearchEvent]
    age_up_commands: Mapping[int, int]
    villagers_ordered: int
    actions: int
    actions_per_minute: float
    resigned_at_ms: int | None


@dataclass(frozen=True, slots=True)
class MatchTimeline:
    """The published shape of one extracted replay.

    Engine-independent and identifier-based: `engine_name`/`engine_version` record which parser
    produced it (mirrored into `engine.deps` at publication time, per the contract's published-JSON
    shape), and `world_time_ms` is the PostGame `WorldTime` block — the match clock's end, not a
    wall-clock duration.
    """

    engine_name: str
    engine_version: str
    point_of_view_profile_id: int
    world_time_ms: int
    participants: Sequence[ParticipantTimeline]


@runtime_checkable
class ReplayExtractor(Protocol):
    """Satisfied by every replay engine adapter that can produce a `MatchTimeline`.

    `extract` performs the same well-formedness checks `ReplayValidator.validate` already performs
    before an engine sees a byte — one member, the expected inner filename, a bounded chunked read
    against a hard ceiling — sharing that path rather than reimplementing it, and raises the same
    `MalformedArchiveError` and `EngineParseError`.

    Memory is part of this contract (R3: ~631 MB resident for a 6.9 MB 1v1 against a 2 GB ceiling):
    an implementation reduces as it goes and never hands back the raw operation stream, even though
    doing so would still type-check.

    `extract` does not retry on `EngineParseError` — a parse is deterministic, so a caller that
    retries only pays for a second identical failure (FR-036, constitution V).

    `engine_name`/`engine_version` (T366) are the same two values a call to `extract` would embed
    in the `MatchTimeline` it returns, declared here as plain attributes so a caller can read "the
    engine currently running" — `run_once`'s own staleness comparison (FR-041) — **without** first
    parsing a recording. `Aoe2RecExtractor` sources both from the same `ENGINE_NAME`/
    `metadata.version(ENGINE_NAME)` its `extract` method already uses, so the two can never
    disagree with what a fresh parse would have produced.
    """

    engine_name: str
    engine_version: str

    def extract(self, zip_bytes: bytes) -> MatchTimeline:
        """Extract a `MatchTimeline` from a downloaded replay archive.

        Raises `MalformedArchiveError` for an archive that fails well-formedness on its own terms,
        or `EngineParseError` for one the engine explicitly rejected via an ordinary `Exception`.
        Any `BaseException` that is not an `Exception` is not this Protocol's to catch.
        """
        ...


# Re-exported so a caller of this module does not also need to import `validation` to catch what
# `extract` raises — the same two exception types, not a parallel pair with the same meaning.
__all__ += ["EngineParseError", "MalformedArchiveError"]
