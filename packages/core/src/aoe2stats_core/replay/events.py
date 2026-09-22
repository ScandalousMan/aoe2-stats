"""The closed canonical event vocabulary and the source protocol (FR-015 to FR-020).

Everything above the replay-engine adapter imports this module and nothing else. Nothing external
is imported here, and no payload field is named, shaped or offset after an engine's output
(FR-017). ``chat`` carries a channel and no text: the text is personal data this feature has no
use for, so it is absent from the vocabulary rather than filtered downstream.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from aoe2stats_core.truth.tiers import Tier


class EventKind(Enum):
    """The closed set of event kinds. Values are the contract's kebab-case names."""

    MATCH_STARTED = "match-started"
    BUILDING_PLACED = "building-placed"
    UNIT_QUEUED = "unit-queued"
    UNIT_UNQUEUED = "unit-unqueued"
    RESEARCH_QUEUED = "research-queued"
    UNITS_COMMANDED = "units-commanded"
    MARKET_TRANSACTION = "market-transaction"
    OBJECT_DELETED = "object-deleted"
    CHAT = "chat"
    PARTICIPANT_RESIGNED = "participant-resigned"
    MATCH_ENDED = "match-ended"
    UNDECODED = "undecoded"
    STARTING_ATTRIBUTES = "starting-attributes"
    STARTING_OBJECT = "starting-object"


# Tier is per kind and fixed. ``building-placed`` is decoded: its building identifier comes from a
# payload this repository decodes, and the event takes its weakest input's tier.
KIND_TIER: Mapping[EventKind, Tier] = {
    EventKind.MATCH_STARTED: Tier.OBSERVED,
    EventKind.BUILDING_PLACED: Tier.DECODED,
    EventKind.UNIT_QUEUED: Tier.OBSERVED,
    EventKind.UNIT_UNQUEUED: Tier.OBSERVED,
    EventKind.RESEARCH_QUEUED: Tier.OBSERVED,
    EventKind.UNITS_COMMANDED: Tier.OBSERVED,
    EventKind.MARKET_TRANSACTION: Tier.DECODED,
    EventKind.OBJECT_DELETED: Tier.DECODED,
    EventKind.CHAT: Tier.DECODED,
    EventKind.PARTICIPANT_RESIGNED: Tier.OBSERVED,
    EventKind.MATCH_ENDED: Tier.OBSERVED,
    EventKind.UNDECODED: Tier.OBSERVED,
    EventKind.STARTING_ATTRIBUTES: Tier.DECODED,
    EventKind.STARTING_OBJECT: Tier.DECODED,
}

# The two kinds whose subject is the match, not a player: only they may carry no participant.
MATCH_LEVEL_KINDS: frozenset[EventKind] = frozenset(
    {EventKind.MATCH_STARTED, EventKind.MATCH_ENDED}
)

# Declared with no producer (FR-020): the day the decoder lands, no type changes.
DECLARED_ONLY_KINDS: frozenset[EventKind] = frozenset(
    {EventKind.STARTING_ATTRIBUTES, EventKind.STARTING_OBJECT}
)


@dataclass(frozen=True, slots=True)
class Position:
    """A map position in tiles."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class ParticipantEntry:
    """One participant in ``match-started``. Observers and empty slots never appear."""

    slot: int
    # The game's integer civilisation identifier, never a name: naming is the knowledge base's
    # job, not the adapter's (T629a).
    civilisation: int


@dataclass(frozen=True, slots=True)
class MatchStartedPayload:
    build: int | None
    map_name: str | None
    lobby_presets: Mapping[str, str] = field(default_factory=dict)
    participants: tuple[ParticipantEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class BuildingPlacedPayload:
    building_id: int
    position: Position


@dataclass(frozen=True, slots=True)
class UnitQueuedPayload:
    unit_id: int
    # The game's building *type* (a Town Center is 109), not an object: it names what kind of
    # building trains the unit, which the per-object id cannot.
    building_type: int
    building_object: int
    count: int


@dataclass(frozen=True, slots=True)
class UnitUnqueuedPayload:
    """A cancellation of queued units: the counterpart of ``unit-queued``, netted against it."""

    unit_id: int
    count: int


@dataclass(frozen=True, slots=True)
class ResearchQueuedPayload:
    technology_id: int
    building_object: int


@dataclass(frozen=True, slots=True)
class UnitsCommandedPayload:
    command_class: str
    # Empty for command classes whose unit ids are not decoded: never a guessed list.
    unit_objects: tuple[int, ...] = ()
    target: int | Position | None = None


@dataclass(frozen=True, slots=True)
class MarketTransactionPayload:
    direction: str  # "buy" or "sell"
    resource: str
    # The payload's own count of market steps (one click is 1, one shift-click is 5). The step's
    # size in resource units is the game's fixed constant, not carried by any recording, so it is
    # not multiplied in here (FR-014, FR-012): that belongs to 007's reconstruction layer, behind
    # a versioned constant that can gap.
    steps: int


@dataclass(frozen=True, slots=True)
class ObjectDeletedPayload:
    object_id: int


@dataclass(frozen=True, slots=True)
class ChatPayload:
    """The channel only. The message text is never carried."""

    channel: str


@dataclass(frozen=True, slots=True)
class MatchEndedPayload:
    final_clock_ms: int


@dataclass(frozen=True, slots=True)
class UndecodedPayload:
    operation: str
    payload_length: int


@dataclass(frozen=True, slots=True)
class StartingAttributesPayload:
    """Declared only (FR-020): per-participant starting attribute values."""

    values: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StartingObjectPayload:
    """Declared only (FR-020): one object present at the start."""

    object_id: int
    object_class: str
    position: Position
    owner: int


Payload = (
    MatchStartedPayload
    | BuildingPlacedPayload
    | UnitQueuedPayload
    | UnitUnqueuedPayload
    | ResearchQueuedPayload
    | UnitsCommandedPayload
    | MarketTransactionPayload
    | ObjectDeletedPayload
    | ChatPayload
    | MatchEndedPayload
    | UndecodedPayload
    | StartingAttributesPayload
    | StartingObjectPayload
)


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
    """One engine-independent occurrence.

    ``clock_ms`` is the accumulated match clock, never wall time. ``tier`` is derived from the kind.
    """

    clock_ms: int
    kind: EventKind
    participant: int | None = None
    payload: Payload | None = None

    def __post_init__(self) -> None:
        if self.participant is None and self.kind not in MATCH_LEVEL_KINDS:
            raise ValueError(f"{self.kind.value} event requires a participant")

    @property
    def tier(self) -> Tier:
        return KIND_TIER[self.kind]


@runtime_checkable
class CanonicalEventSource(Protocol):
    """What everything above the adapter depends on."""

    engine_name: str
    engine_version: str
    engine_dependencies: Mapping[str, str]  # non-empty (FR-044)

    def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]: ...
