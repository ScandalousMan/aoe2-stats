"""The group-silence observable (T633, FR-013, FR-014): `participant.group_silence_episodes`.

`silence.py`'s module docstring carries the full derivation; this file is the register's own
`validation` field for the datum — "synthetic silence streams and both committed recordings"
(`register.toml`, `participant.group_silence_episodes`). Most cases here are synthetic, built
directly from `CanonicalEvent` values rather than through the wheel, because the behaviour under
test is about the accumulator's own rules (repeat count, silence length, the resignation-shortens-
the-ratio rule, the blind spot) and not about anything the parser decodes. The two committed
recordings are driven through the real adapter once, at the bottom of this file, to prove the
accumulator does not crash or misbehave on real data — this repository's actual recordings may
carry zero episodes, and that is not a failure of this datum.

Test-first (T633): every test below imports `aoe2stats_replay_engine.silence` inside its own body,
not at module scope, so the file was collectable and every test below ran `xfail(strict=True,
reason="T633 not implemented yet")` and failed for that reason (`ModuleNotFoundError`, confirmed by
hand before the module existed) before `silence.py` landed and the markers were removed.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import cast

import pytest

from aoe2stats_core.replay.events import (
    CanonicalEvent,
    EventKind,
    MarketTransactionPayload,
    MatchEndedPayload,
    ObjectDeletedPayload,
    UnitsCommandedPayload,
)
from aoe2stats_core.truth.confidence import ConfidenceLevel
from aoe2stats_core.truth.register import REGISTER
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

_FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"
_RECORDINGS = sorted(_FIXTURES.glob("AgeIIDE_Replay_*.zip"))

_ENTRY = REGISTER["participant.group_silence_episodes"]
# The register's own thresholds (module under test parses the same text): REPEAT_MIN=2,
# MIN_SILENCE_MS=180000, MEDIUM_INTENSITY=4, MEDIUM_DURATION_RATIO=0.5.
_REPEAT_MIN = 2
_MIN_SILENCE_MS = 180_000
_MEDIUM_INTENSITY = 4
_MEDIUM_DURATION_RATIO = 0.5


def _commanded(
    clock_ms: int, participant: int, unit_objects: tuple[int, ...], command_class: str = "move"
) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock_ms,
        kind=EventKind.UNITS_COMMANDED,
        participant=participant,
        payload=UnitsCommandedPayload(command_class=command_class, unit_objects=unit_objects),
    )


def _resigned(clock_ms: int, participant: int) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock_ms, kind=EventKind.PARTICIPANT_RESIGNED, participant=participant
    )


def _match_ended(clock_ms: int) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock_ms,
        kind=EventKind.MATCH_ENDED,
        payload=MatchEndedPayload(final_clock_ms=clock_ms),
    )


def _deleted(clock_ms: int, participant: int, object_id: int) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock_ms,
        kind=EventKind.OBJECT_DELETED,
        participant=participant,
        payload=ObjectDeletedPayload(object_id=object_id),
    )


def _market(clock_ms: int, participant: int) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock_ms,
        kind=EventKind.MARKET_TRANSACTION,
        participant=participant,
        payload=MarketTransactionPayload(direction="sell", resource="wood", steps=1),
    )


# A group commanded `_REPEAT_MIN` times, then never again, with a silence comfortably over
# `_MIN_SILENCE_MS` and a high enough intensity/duration to reach MEDIUM.
_MATCH_END_MS = 4_000_000
_LAST_COMMAND_MS = 3_000_000  # 1,000,000 ms remaining; silence of 1,000,000 ms is a 100% ratio


def _medium_confidence_stream() -> list[CanonicalEvent]:
    group = (10, 11, 12)
    commands = [_commanded(200_000 * i, 1, group) for i in range(1, _MEDIUM_INTENSITY + 1)]
    commands[-1] = _commanded(_LAST_COMMAND_MS, 1, group)
    return [*commands, _match_ended(_MATCH_END_MS)]


def test_a_group_commanded_repeatedly_then_never_again_is_one_episode() -> None:
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    (episode,) = compute_group_silence_episodes(_medium_confidence_stream())
    assert episode.participant == 1
    assert episode.unit_objects == (10, 11, 12)
    assert episode.occurrences == _MEDIUM_INTENSITY
    assert episode.last_commanded_at_ms == _LAST_COMMAND_MS
    assert episode.silence_ends_at_ms == _MATCH_END_MS
    assert episode.confidence.level == ConfidenceLevel.MEDIUM


def test_a_group_commanded_only_once_is_not_an_episode() -> None:
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    stream = [_commanded(100, 1, (10, 11)), _match_ended(_MATCH_END_MS)]
    assert compute_group_silence_episodes(stream) == ()


def test_a_silence_under_the_minimum_length_is_not_an_episode() -> None:
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    last = _MATCH_END_MS - (_MIN_SILENCE_MS - 1)
    stream = [
        _commanded(100, 1, (10, 11)),
        _commanded(last, 1, (10, 11)),
        _match_ended(_MATCH_END_MS),
    ]
    assert compute_group_silence_episodes(stream) == ()


def test_a_single_unit_named_alone_is_not_a_group() -> None:
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    stream = [
        _commanded(100, 1, (10,)),
        _commanded(200, 1, (10,)),
        _match_ended(_MATCH_END_MS),
    ]
    assert compute_group_silence_episodes(stream) == ()


def test_no_match_ended_event_yields_no_episodes() -> None:
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    stream = _medium_confidence_stream()[:-1]  # drop the match-ended event
    assert compute_group_silence_episodes(stream) == ()


def test_resignation_shortens_the_observed_silence_and_can_only_lower_the_ratio() -> None:
    """The same group, same intensity and last-command time, but the participant resigns soon
    after: the observed silence is capped at the resignation clock while the match time
    "remaining" is still measured to the true match end, so the ratio (and therefore the band) can
    only be lower than the same stream without a resignation — never higher."""
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    # 300,000 ms of the 1,000,000 ms remaining (30%) — above `_MIN_SILENCE_MS` so an episode still
    # publishes, but below `_MEDIUM_DURATION_RATIO` (50%) so the band drops to low.
    resigned_at = _LAST_COMMAND_MS + 300_000
    stream = [
        *_medium_confidence_stream()[:-1],
        _resigned(resigned_at, 1),
        _match_ended(_MATCH_END_MS),
    ]
    (episode,) = compute_group_silence_episodes(stream)
    assert episode.silence_ends_at_ms == resigned_at
    assert episode.confidence.level == ConfidenceLevel.LOW
    without_resignation = compute_group_silence_episodes(_medium_confidence_stream())
    assert without_resignation[0].confidence.level == ConfidenceLevel.MEDIUM


def test_confidence_high_is_never_assigned_even_at_the_most_extreme_inputs() -> None:
    """The blind spot caps the banding at medium, structurally — not because no stream happens to
    reach a higher threshold. Feed absurdly high intensity and a 100% duration ratio and confirm
    the level still stops at medium."""
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    group = (10, 11, 20, 30)
    commands = [_commanded(1_000 * i, 1, group) for i in range(1, 501)]
    stream = [*commands, _match_ended(_MATCH_END_MS)]
    (episode,) = compute_group_silence_episodes(stream)
    assert episode.confidence.level == ConfidenceLevel.MEDIUM
    assert episode.confidence.level != ConfidenceLevel.HIGH


def test_constructing_an_episode_with_high_confidence_directly_is_refused() -> None:
    """`GroupSilenceEpisode` enforces its own cap at construction, independent of `_band` — a
    caller building one by hand cannot smuggle a high-confidence instance past the type."""
    from aoe2stats_core.truth.confidence import Confidence
    from aoe2stats_core.truth.provenance import Method, Provenance
    from aoe2stats_core.truth.tiers import Tier
    from aoe2stats_replay_engine.silence import NON_CLAIM, GroupSilenceEpisode

    confidence = Confidence(level=ConfidenceLevel.HIGH, basis="a contrived high confidence")
    provenance = Provenance(
        datum="participant.group_silence_episodes",
        tier=Tier.INFERRED,
        method=Method(id="group-silence.banding", version="1"),
        inputs=("event.clock_ms",),
        confidence=confidence,
        non_claim=NON_CLAIM,
    )
    with pytest.raises(ValueError, match="capped below high"):
        GroupSilenceEpisode(
            participant=1,
            unit_objects=(10, 11),
            occurrences=10,
            last_commanded_at_ms=0,
            silence_ends_at_ms=1_000_000,
            confidence=confidence,
            non_claim=NON_CLAIM,
            provenance=provenance,
        )


def test_the_blind_spot_a_group_parked_by_an_undecoded_command_still_reads_as_silent() -> None:
    """The documented blind spot, made concrete: a `stop` command names the same group as the
    prior moves (in reality — the game knows what it was told to stop), but `units-commanded`
    events for `stop` always carry an empty id list (T626), so this accumulator cannot see that
    the group was addressed again. It reads exactly as if abandoned, which is the failure mode
    the register's `non_claim` and this module's docstring both name."""
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    group = (10, 11, 12)
    stream = [
        *[_commanded(200_000 * i, 1, group) for i in range(1, _MEDIUM_INTENSITY + 1)],
        # A real `stop` command addressing this exact group — but emitted with an empty id list,
        # as every non-move/interact/order command class is (T626).
        _commanded(_LAST_COMMAND_MS + 500_000, 1, (), command_class="stop"),
        _match_ended(_MATCH_END_MS),
    ]
    (episode,) = compute_group_silence_episodes(stream)
    # The episode's last-commanded time is still the *last decoded* command, not the stop that
    # actually addressed the group afterward: the accumulator has no way to know the group was
    # touched again, which is exactly the blind spot.
    assert episode.last_commanded_at_ms == 200_000 * _MEDIUM_INTENSITY
    assert episode.confidence.level in (ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM)


def test_every_instance_carries_the_registers_non_claim_verbatim() -> None:
    from aoe2stats_replay_engine.silence import NON_CLAIM, compute_group_silence_episodes

    assert _ENTRY.non_claim == NON_CLAIM
    (episode,) = compute_group_silence_episodes(_medium_confidence_stream())
    assert episode.non_claim == _ENTRY.non_claim
    assert episode.provenance.non_claim == _ENTRY.non_claim


def test_it_consumes_no_deletion_and_no_market_event_fr_014() -> None:
    """Deletion and market events interleaved with the exact same commands change nothing: the
    accumulator never reads either kind, and neither is summed with this datum (FR-014)."""
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    plain = compute_group_silence_episodes(_medium_confidence_stream())
    with_noise = compute_group_silence_episodes(
        [
            _deleted(50, 1, 999),
            _market(75, 1),
            *_medium_confidence_stream(),
            _deleted(_MATCH_END_MS - 1, 1, 998),
            _market(_MATCH_END_MS - 1, 1),
        ]
    )
    assert with_noise == plain

    # And a stream of nothing but deletion and market events, with no units-commanded at all,
    # yields no episode — there is nothing for this datum to consume there.
    only_noise = [_deleted(100, 1, 1), _market(200, 1), _match_ended(_MATCH_END_MS)]
    assert compute_group_silence_episodes(only_noise) == ()


def test_provenance_names_the_method_and_the_inputs() -> None:
    from aoe2stats_core.truth.tiers import Tier
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    (episode,) = compute_group_silence_episodes(_medium_confidence_stream())
    assert episode.provenance.datum == "participant.group_silence_episodes"
    assert episode.provenance.tier is Tier.INFERRED
    assert episode.provenance.method.id == "group-silence.banding"
    assert "event.units_commanded.unit_object_ids" in episode.provenance.inputs
    assert "event.match_ended.final_clock_ms" in episode.provenance.inputs


def test_deterministic_ordering_over_repeated_calls() -> None:
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    stream = [
        *[_commanded(200_000 * i, 2, (30, 31, 32)) for i in range(1, _MEDIUM_INTENSITY + 1)],
        *[_commanded(200_000 * i, 1, (10, 11, 12)) for i in range(1, _MEDIUM_INTENSITY + 1)],
        _match_ended(_MATCH_END_MS),
    ]
    first = compute_group_silence_episodes(stream)
    second = compute_group_silence_episodes(stream)
    assert first == second
    assert [e.participant for e in first] == [1, 2]


# --- Both committed recordings: the register's validation field names them too ------------------

_Parsed = Mapping[str, object]


@pytest.fixture(scope="module", params=_RECORDINGS, ids=lambda p: p.stem)
def canonical_stream(request: pytest.FixtureRequest) -> Iterator[CanonicalEvent]:
    extractor = Aoe2RecExtractor(max_raw_bytes=50_000_000)
    zip_bytes = cast(Path, request.param).read_bytes()
    return extractor.events(zip_bytes)


def test_both_committed_recordings_compute_without_error(
    canonical_stream: Iterator[CanonicalEvent],
) -> None:
    from aoe2stats_core.truth.confidence import ConfidenceLevel as _Level
    from aoe2stats_replay_engine.silence import compute_group_silence_episodes

    episodes = compute_group_silence_episodes(canonical_stream)
    assert isinstance(episodes, tuple)
    for episode in episodes:
        assert episode.non_claim == _ENTRY.non_claim
        assert episode.confidence.level is not _Level.HIGH
