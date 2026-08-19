"""The `aoe2rec-py` adapter, `Aoe2RecValidator`.

Covers the adapter's own well-formedness logic against the committed reference fixture and small
constructed archives. `packages/replay-engine` is the only package allowed to import the engine
(the `replay-parsing` skill) and the only place that should hold this test — T079 later extends
this same file with the full truncated/empty/non-replay matrix against `tests/fixtures/replays/`;
this task seeds it with the cases needed to prove the adapter's own logic is correct.
"""

from __future__ import annotations

import io
import zipfile
from importlib import metadata
from pathlib import Path

import pytest

from aoe2stats_core.replay.validation import EngineParseError, MalformedArchiveError
from aoe2stats_replay_engine.aoe2rec import Aoe2RecValidator

REFERENCE_REPLAY = (
    Path(__file__).resolve().parents[3] / "tests/fixtures/replays/AgeIIDE_Replay_500546441.zip"
)


def _zip_bytes(members: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=compression) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


@pytest.fixture
def validator() -> Aoe2RecValidator:
    return Aoe2RecValidator()


def test_the_committed_reference_replay_validates(validator: Aoe2RecValidator) -> None:
    zip_bytes = REFERENCE_REPLAY.read_bytes()

    result = validator.validate(zip_bytes)

    assert result.inner_filename == "AgeIIDE_Replay_500546441.aoe2record"
    assert result.inner_bytes == 6_909_299
    assert result.engine_name == "aoe2rec-py"
    assert result.engine_version == metadata.version("aoe2rec-py")


def test_not_a_zip_is_rejected(validator: Aoe2RecValidator) -> None:
    with pytest.raises(MalformedArchiveError):
        validator.validate(b"this is not a zip archive at all")


def test_an_archive_with_two_members_is_rejected(validator: Aoe2RecValidator) -> None:
    zip_bytes = _zip_bytes(
        {
            "AgeIIDE_Replay_1.aoe2record": b"x" * 100,
            "AgeIIDE_Replay_1.aoe2record.extra": b"y" * 100,
        }
    )

    with pytest.raises(MalformedArchiveError, match="exactly one member"):
        validator.validate(zip_bytes)


def test_an_unexpected_inner_filename_is_rejected(validator: Aoe2RecValidator) -> None:
    zip_bytes = _zip_bytes({"not_a_replay.txt": b"x" * 100})

    with pytest.raises(MalformedArchiveError, match="inner filename"):
        validator.validate(zip_bytes)


def test_a_zip_bomb_ratio_is_rejected(validator: Aoe2RecValidator) -> None:
    # 20 MB of zeros compresses far past the 32x cap — a real replay never does, per ADR-0001.
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": b"\x00" * 20_000_000})

    with pytest.raises(MalformedArchiveError, match="decompression ratio"):
        validator.validate(zip_bytes)


def test_an_engine_crash_on_malformed_content_is_not_caught_by_the_adapter(
    validator: Aoe2RecValidator,
) -> None:
    # Well-formed archive, garbage inner content. `aoe2rec-py`'s bridge panics on malformed input
    # (`pyo3_runtime.PanicException`, a bare BaseException) rather than raising an Exception — this
    # is exactly the crash the ingester's containment barrier (T055) exists to catch, so the
    # adapter must not turn it into `EngineParseError` or swallow it in any other way.
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": b"not a real replay" * 20})

    with pytest.raises(BaseException) as excinfo:
        validator.validate(zip_bytes)

    assert not isinstance(excinfo.value, Exception)
    assert not isinstance(excinfo.value, EngineParseError)
    assert not isinstance(excinfo.value, MalformedArchiveError)


def test_a_truncated_reference_replay_still_reaches_the_engine_uncaught(
    validator: Aoe2RecValidator,
) -> None:
    zip_bytes = REFERENCE_REPLAY.read_bytes()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        inner_name = archive.namelist()[0]
        inner_data = archive.read(inner_name)

    truncated = _zip_bytes({inner_name: inner_data[: len(inner_data) // 2]})

    with pytest.raises(BaseException) as excinfo:
        validator.validate(truncated)

    assert not isinstance(excinfo.value, Exception)
