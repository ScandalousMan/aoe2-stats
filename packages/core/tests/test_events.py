"""Tests for the canonical event vocabulary (T624), written before T623 as strict xfails.

T623 removes the markers when ``aoe2stats_core.replay.events`` lands.

Names T623 must use (the contract fixes the kinds and tiers, not the Python names):

- ``EventKind``: enum whose values are the contract's kebab-case kind names.
- ``KIND_TIER``: mapping ``EventKind -> Tier`` covering every kind (tier is per kind, fixed).
- ``MATCH_LEVEL_KINDS``: the kinds that may carry no participant: ``match-started`` and
  ``match-ended`` (the two whose subject is the match, not a player).
- ``CanonicalEvent(clock_ms, kind, participant=None, payload=None)``: frozen record; ``tier`` is
  derived from the kind, never passed. Construction raises ``ValueError`` when ``participant``
  is None and the kind is not match-level.
- ``StartingAttributesPayload``, ``StartingObjectPayload`` and ``ChatPayload``: payload
  dataclasses; the first two are the declared-only kinds (FR-020), and ``ChatPayload`` carries a
  channel and no text.
"""

from __future__ import annotations

import pytest

XFAIL = pytest.mark.xfail(strict=True, reason="T623 not implemented yet")

CONTRACT_TIERS = {
    "match-started": "OBSERVED",
    "building-placed": "DECODED",
    "unit-queued": "OBSERVED",
    "research-queued": "OBSERVED",
    "units-commanded": "OBSERVED",
    "market-transaction": "DECODED",
    "object-deleted": "DECODED",
    "chat": "DECODED",
    "participant-resigned": "OBSERVED",
    "match-ended": "OBSERVED",
    "undecoded": "OBSERVED",
    "starting-attributes": "DECODED",
    "starting-object": "DECODED",
}
MATCH_LEVEL = {"match-started", "match-ended"}
DECLARED_ONLY = {"starting-attributes", "starting-object"}


@XFAIL
def test_vocabulary_is_closed_and_matches_the_contract() -> None:
    from aoe2stats_core.replay.events import EventKind

    assert {k.value for k in EventKind} == set(CONTRACT_TIERS)
    assert len(EventKind) == 13


@XFAIL
def test_every_kind_has_the_contract_tier() -> None:
    from aoe2stats_core.replay.events import KIND_TIER, EventKind

    assert set(KIND_TIER) == set(EventKind)
    for kind in EventKind:
        assert KIND_TIER[kind].name == CONTRACT_TIERS[kind.value]


@XFAIL
def test_event_tier_is_derived_from_its_kind() -> None:
    from aoe2stats_core.replay.events import KIND_TIER, CanonicalEvent, EventKind

    for kind in EventKind:
        event = CanonicalEvent(clock_ms=0, kind=kind, participant=1)
        assert event.tier is KIND_TIER[kind]


@XFAIL
def test_building_placed_takes_the_weaker_decoded_tier() -> None:
    from aoe2stats_core.replay.events import CanonicalEvent, EventKind
    from aoe2stats_core.truth.tiers import Tier

    event = CanonicalEvent(clock_ms=5, kind=EventKind("building-placed"), participant=2)
    assert event.tier is Tier.DECODED


@XFAIL
def test_match_level_kinds_are_exactly_the_two_match_subject_kinds() -> None:
    from aoe2stats_core.replay.events import MATCH_LEVEL_KINDS

    assert {k.value for k in MATCH_LEVEL_KINDS} == MATCH_LEVEL


@XFAIL
def test_participantless_event_is_constructible_only_for_match_level_kinds() -> None:
    from aoe2stats_core.replay.events import CanonicalEvent, EventKind

    for kind in EventKind:
        if kind.value in MATCH_LEVEL:
            assert CanonicalEvent(clock_ms=0, kind=kind).participant is None
        else:
            with pytest.raises(ValueError):
                CanonicalEvent(clock_ms=0, kind=kind)
            with pytest.raises(ValueError):
                CanonicalEvent(clock_ms=0, kind=kind, participant=None)


@XFAIL
def test_match_level_kinds_may_still_carry_a_participant() -> None:
    from aoe2stats_core.replay.events import CanonicalEvent, EventKind

    event = CanonicalEvent(clock_ms=0, kind=EventKind("match-ended"), participant=3)
    assert event.participant == 3


@XFAIL
def test_declared_only_kinds_exist_as_types() -> None:
    from aoe2stats_core.replay.events import (
        KIND_TIER,
        EventKind,
        StartingAttributesPayload,
        StartingObjectPayload,
    )
    from aoe2stats_core.truth.tiers import Tier

    assert isinstance(StartingAttributesPayload, type)
    assert isinstance(StartingObjectPayload, type)
    for value in DECLARED_ONLY:
        assert KIND_TIER[EventKind(value)] is Tier.DECODED


@XFAIL
def test_chat_payload_carries_no_text() -> None:
    from dataclasses import fields, is_dataclass

    from aoe2stats_core.replay import events

    payload_type = getattr(events, "ChatPayload", None)
    assert payload_type is not None and is_dataclass(payload_type)
    names = {f.name for f in fields(payload_type)}
    assert "channel" in names
    assert not names & {"text", "message", "content", "body"}
