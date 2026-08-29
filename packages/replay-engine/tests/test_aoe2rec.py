"""The `aoe2rec-py` adapter, `Aoe2RecValidator`, and the `Build`-action decoder (R4, T353/T354).

Covers the adapter's own well-formedness logic against the committed reference fixture and small
constructed archives. `packages/replay-engine` is the only package allowed to import the engine
(the `replay-parsing` skill) and the only place that should hold this test — T079 later extends
this same file with the full truncated/empty/non-replay matrix against `tests/fixtures/replays/`;
this task seeds it with the cases needed to prove the adapter's own logic is correct.

The bottom of the file covers `decode_build_action` (T354, not yet implemented — see the
`xfail(strict=True)` markers). Measured directly against the pinned wheel (`aoe2rec-py==0.1.21`,
the exact version this package depends on) rather than taken on trust from the docs: R4 and
ADR-0001's 2026-08-24 correction both say the wheel hands `Build` back with "no `player_id` field
at all". That is not what this wheel returns — `test_the_pinned_wheel_already_returns_a_player_id_
for_build_actions` below pins the opposite, currently-passing fact, checked on every one of the 326
`Build` actions in the reference replay. What R4 got right, and what is genuinely missing and
genuinely this repository's job, is the *building type*: it is not a named field anywhere in the
wheel's output, only recoverable from the raw bytes of `Build.data`. The offset pinned below
(byte 12, a little-endian `u32`) was found empirically, by sweeping every byte position across all
326 actions and keeping the one whose decoded value is stable per repeated build and never varies
within a byte length group in a way inconsistent with a building identifier; the resulting 17
distinct values total exactly 326 and several are unambiguous, well-known AoE2 DE Genie building
ids: 70 (House, 93 times — the single most common early build), 50 (Farm, 140 times — by far the
most rebuilt building in any game), 562 (Lumber Camp, 14), 584 (Mining Camp, 14), 68 (Mill, 7), 12
(Barracks, 2). No fixed byte offset in `data` correlates with `player_id` for even one of the 17
distinct `action_length` groups this replay contains — confirmed by the same sweep — which is why
the decoder is expected to read `player_id` from the field the wheel already provides rather than
from `data`.
"""

from __future__ import annotations

import io
import struct
import zipfile
from collections import Counter
from importlib import metadata
from pathlib import Path
from typing import cast

import pytest
from aoe2rec_py import aoe2rec_py as _native

import aoe2stats_replay_engine.aoe2rec as aoe2rec_module
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


def _lie_about_declared_size(zip_bytes: bytes, lie_size: int) -> bytes:
    """Patch the uncompressed-size field in both headers to `lie_size`, leaving the compressed
    bytes untouched.

    Simulates an archive whose central directory under-declares `member.file_size` — attacker-
    supplied, per T013a. The archive still decompresses to its true, larger size; only what it
    *claims* about that size changes.
    """
    data = bytearray(zip_bytes)
    assert data[0:4] == b"PK\x03\x04", "expected a local file header at offset 0"
    # Local file header: signature(4) + 18 bytes of fixed fields precede the 4-byte
    # uncompressed-size field, which sits at offset 22.
    data[22:26] = struct.pack("<I", lie_size)
    central_offset = zip_bytes.index(b"PK\x01\x02")
    # Central directory header: signature(4) + 20 bytes of fixed fields precede its own
    # uncompressed-size field, at a relative offset of 24.
    data[central_offset + 24 : central_offset + 28] = struct.pack("<I", lie_size)
    return bytes(data)


def test_an_archive_that_under_declares_its_size_is_rejected_without_full_inflation(
    validator: Aoe2RecValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T013a: `member.file_size` and `member.compress_size` come from the archive's own central
    directory — attacker-supplied. An archive that under-declares `file_size` must still be
    rejected, and rejected *before* the whole member has been decompressed into memory: the old
    code called `archive.read(member.filename)`, an unbounded read, and only compared the result
    against the declared size afterwards. The fix reads through `archive.open()` in small, fixed
    chunks and stops the instant the cap is crossed, never trusting the header enough to ask for
    more than one bounded chunk at a time.
    """
    small_cap = 64
    monkeypatch.setattr(aoe2rec_module, "_MAX_INNER_BYTES", small_cap)

    true_size = 5_000_000
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": b"\x00" * true_size})
    lied_zip_bytes = _lie_about_declared_size(zip_bytes, lie_size=1)

    # Generous slack for one legitimate chunk on top of the cap — anything requesting more than
    # this in a single `.read()` call is not reading in bounded chunks.
    max_single_read = small_cap + 1024 * 1024
    original_read = zipfile.ZipExtFile.read

    def _spying_read(
        self: zipfile.ZipExtFile, n: int = -1, *args: object, **kwargs: object
    ) -> bytes:
        # `archive.read(name)` — the whole-member convenience method — calls exactly this, with no
        # bound (`n == -1`), which is precisely the pattern that inflates the full member before
        # an under-declared size is ever caught.
        assert 0 < n <= max_single_read, (
            f"ZipExtFile.read() was called with n={n!r}, not a small bounded chunk — the member "
            "is being inflated without a cap"
        )
        return original_read(self, n, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", _spying_read)

    with pytest.raises(MalformedArchiveError, match="cap"):
        validator.validate(lied_zip_bytes)


# --- `Build`-action decoding (R4, T353/T354) -----------------------------------------------


# The building-type identifier at byte offset 12 of `Build.data`, an unsigned little-endian 32-bit
# integer, for every one of the 326 `Build` actions in the reference replay — grouped by value, not
# by order, because the golden fact worth pinning is the *distribution*: this is what proves the
# offset generalises across all 17 distinct `action_length` values this replay's `Build` actions
# take (32 to 108 bytes), rather than happening to work on the first few. Several are unambiguous,
# well-known AoE2 DE Genie building ids, cross-checked against the values below: 70 (House, the
# single most common early build), 50 (Farm, by far the most-rebuilt building in any game — farms
# wear out and are replaced constantly), 562 (Lumber Camp), 584 (Mining Camp), 68 (Mill), and 12
# (Barracks). The counts sum to exactly 326, matching ADR-0001's own count for this replay.
_EXPECTED_BUILDING_TYPE_COUNTS = {
    70: 93,
    50: 140,
    562: 14,
    584: 14,
    87: 12,
    101: 8,
    79: 8,
    68: 7,
    598: 6,
    84: 5,
    621: 4,
    49: 4,
    103: 3,
    82: 3,
    12: 2,
    209: 2,
    104: 1,
}


def _reference_build_actions() -> list[dict[str, object]]:
    """Every raw `Build` action dict — `{"player_id", "action_length", "data"}` — the pinned wheel
    hands back for the committed reference replay, in stream order.
    """
    zip_bytes = REFERENCE_REPLAY.read_bytes()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        inner_name = archive.namelist()[0]
        inner_bytes = archive.read(inner_name)
    parsed = _native.parse_rec(inner_bytes)
    return [
        operation["Action"]["action_data"]["Build"]
        for operation in parsed["operations"]
        if "Action" in operation and "Build" in operation["Action"]["action_data"]
    ]


def test_the_reference_replay_has_326_build_actions() -> None:
    # ADR-0001's own count for this exact file. Every other test below depends on this holding.
    assert len(_reference_build_actions()) == 326


def test_the_pinned_wheel_already_returns_a_player_id_for_build_actions() -> None:
    """Pins a fact about the pinned dependency (`aoe2rec-py==0.1.21`) that contradicts R4 and
    ADR-0001's 2026-08-24 correction, both of which say `Build` comes back as
    `{"action_length": 36, "data": [...]}` with no `player_id` field at all. Measured directly
    against this package's own pinned version: every `Build` action already carries a top-level
    `player_id`, the same way every other action variant does (`Move`, `Research`, `Resign`, ...).

    This is not an `xfail` — it is true today, of the wheel as it actually installs, independent of
    T354's decoder. It exists so the next reader does not have to re-run the same measurement to
    find out the docs are wrong about this one field: only the building type is genuinely missing
    from the wheel's output and genuinely this repository's job to decode (the tests below).
    """
    builds = _reference_build_actions()
    assert len(builds) == 326
    for build in builds:
        assert "player_id" in build
        assert build["player_id"] in (1, 2)  # the reference replay is a 1v1


def test_no_fixed_byte_offset_in_build_data_recovers_player_id() -> None:
    """The corollary of the fact above: since `player_id` is already available on the action
    envelope, a decoder has no reason to also hunt for it inside the opaque `data` payload — and
    this proves it could not, even if it wanted to. Swept every byte position within each
    `action_length` group that contains builds from *both* players (a byte's meaning is positional
    and only comparable within actions of the same shape, and a group with only one player's builds
    would let any offset "match" trivially by never having to distinguish anything): no position's
    decoded byte equals `player_id` for every action in any such group. `decode_build_action`
    (T354) is therefore expected to read `player_id` straight from the field the wheel provides,
    never from `data`.
    """
    builds = _reference_build_actions()
    by_length: dict[int, list[dict[str, object]]] = {}
    for build in builds:
        by_length.setdefault(int(build["action_length"]), []).append(build)

    mixed_player_groups = [
        group for group in by_length.values() if {b["player_id"] for b in group} == {1, 2}
    ]
    assert len(mixed_player_groups) >= 2, "need groups mixing both players to make this a real test"

    for group in mixed_player_groups:
        for offset in range(min(int(b["action_length"]) for b in group)):
            matches_every_action = all(
                cast(list[int], b["data"])[offset] == b["player_id"] for b in group
            )
            assert not matches_every_action, (
                f"byte offset {offset} happened to equal player_id for every action in an "
                f"action_length={group[0]['action_length']} group — decode_build_action must not "
                "rely on this, it does not hold across the other groups"
            )


def test_decode_build_action_recovers_the_pinned_building_type_offset() -> None:
    """A single golden example, pinned literally: the very first `Build` action in the reference
    replay's operation stream (`world_time=1352`), a 2-villager House build. `data[12:16]`, read as
    an unsigned little-endian 32-bit integer, is `70` — the AoE2 DE Genie id for House.
    """
    from aoe2stats_replay_engine.aoe2rec import decode_build_action

    build_action = {
        "player_id": 1,
        "action_length": 36,
        "data": [
            2,
            0,
            0,
            0,
            0,
            0,
            64,
            65,
            0,
            0,
            138,
            66,
            70,
            0,
            0,
            0,
            255,
            255,
            255,
            255,
            255,
            255,
            255,
            255,
            1,
            0,
            0,
            1,
            117,
            16,
            0,
            0,
            119,
            16,
            0,
            0,
        ],
    }

    decoded = decode_build_action(build_action)

    assert decoded.player_id == 1
    assert decoded.building_id == 70


def test_all_326_build_actions_in_the_reference_replay_decode() -> None:
    """The golden test proper: every one of the 326 `Build` actions in the committed reference
    replay decodes to a `player_id` and a building identifier, and the resulting distribution of
    building identifiers matches `_EXPECTED_BUILDING_TYPE_COUNTS` — pinned above from byte offset
    12 of `Build.data`, cross-checked against known AoE2 DE Genie building ids.
    """
    from aoe2stats_replay_engine.aoe2rec import decode_build_action

    builds = _reference_build_actions()
    assert len(builds) == 326

    decoded = [decode_build_action(build) for build in builds]

    for build, one_decoded in zip(builds, decoded, strict=True):
        assert one_decoded.player_id == build["player_id"]
        assert one_decoded.player_id in (1, 2)

    building_id_counts = Counter(one_decoded.building_id for one_decoded in decoded)
    assert dict(building_id_counts) == _EXPECTED_BUILDING_TYPE_COUNTS
    assert building_id_counts.total() == 326
