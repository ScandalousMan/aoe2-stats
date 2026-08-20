"""The replay-engine Protocol: shape only. No engine is imported here — see constitution V and the
module docstring of `aoe2stats_core.replay.validation`. Adapter behaviour is tested where the
adapter lives, in `packages/replay-engine/tests/test_aoe2rec.py`.
"""

from __future__ import annotations

from aoe2stats_core.replay.validation import (
    EngineParseError,
    MalformedArchiveError,
    ReplayValidationError,
    ReplayValidationResult,
    ReplayValidator,
)


class _FakeValidator:
    """The minimal shape a `ReplayValidator` adapter must have — no engine involved."""

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        return ReplayValidationResult(
            inner_filename="AgeIIDE_Replay_1.aoe2record",
            inner_bytes=len(zip_bytes),
            engine_name="fake-engine",
            engine_version="0.0.0",
        )


def test_a_conforming_adapter_satisfies_the_protocol_structurally() -> None:
    # runtime_checkable Protocol conformance is duck typing on method presence, not a subclass
    # relationship — this is the whole point of the Protocol: `aoe2rec-py` and `aoc-mgz` adapters
    # never need to inherit from anything in core.
    assert isinstance(_FakeValidator(), ReplayValidator)


def test_a_class_without_validate_does_not_satisfy_the_protocol() -> None:
    class _NotAValidator:
        pass

    assert not isinstance(_NotAValidator(), ReplayValidator)


def test_validation_result_carries_exactly_the_replay_captures_columns() -> None:
    result = ReplayValidationResult(
        inner_filename="AgeIIDE_Replay_500546441.aoe2record",
        inner_bytes=6_909_299,
        engine_name="aoe2rec-py",
        engine_version="0.1.21",
    )
    assert result.inner_filename == "AgeIIDE_Replay_500546441.aoe2record"
    assert result.inner_bytes == 6_909_299
    assert result.engine_name == "aoe2rec-py"
    assert result.engine_version == "0.1.21"


def test_the_result_is_frozen() -> None:
    result = ReplayValidationResult(
        inner_filename="a.aoe2record", inner_bytes=1, engine_name="e", engine_version="1"
    )
    try:
        result.inner_bytes = 2  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("ReplayValidationResult must be immutable")


def test_the_exception_hierarchy_is_exception_based_not_baseexception() -> None:
    # Deliberately not BaseException: an engine crash (pyo3_runtime.PanicException, confirmed a
    # bare BaseException) is never wrapped into this hierarchy — see the module docstring.
    assert issubclass(MalformedArchiveError, ReplayValidationError)
    assert issubclass(EngineParseError, ReplayValidationError)
    assert issubclass(ReplayValidationError, Exception)
