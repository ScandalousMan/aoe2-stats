"""The `aoe2rec-py` adapter satisfying `aoe2stats_core.replay.validation.ReplayValidator`.

Imported only by the ingester, which contains it behind the `BaseException`-catching barrier in
T055 — never by `packages/core`, which the API imports (constitution V), and never directly by
anything outside this package's own boundary (the `replay-parsing` skill: "Never import either
[engine] directly outside its adapter").

Well-formedness is checked before the engine ever sees a byte, per the skill's extraction-safety
discipline: exactly one member, an inner filename matching the naming scheme aoe.ms publishes
(`docs/data-sources.md`), and a decompression ratio that rules out a zip bomb. Only a well-formed
archive is handed to `aoe2rec_py.parse_rec`, whose job is limited here to confirming the inner
bytes are a replay it can open — nothing about match content is read or returned.
"""

from __future__ import annotations

import re
import zipfile
from importlib import metadata
from io import BytesIO

from aoe2rec_py import aoe2rec_py as _native

from aoe2stats_core.replay.validation import (
    EngineParseError,
    MalformedArchiveError,
    ReplayValidationResult,
)

ENGINE_NAME = "aoe2rec-py"

# The aoe.ms download's `content-disposition` names the inner file exactly this way
# (docs/data-sources.md §2: `AgeIIDE_Replay_{gameId}.aoe2record`). Anything else is not the replay
# we asked for, however well-formed the zip around it is.
_INNER_FILENAME_RE = re.compile(r"^AgeIIDE_Replay_\d+\.aoe2record$")

# The real archive compresses at roughly 8:1 (ADR-0001, reconfirmed against the committed fixture:
# 6,909,299 / 871,335 ≈ 7.93). Four times that leaves margin for a genuinely long game without
# opening the door to a crafted archive that inflates from a few kilobytes to gigabytes — the
# `replay-parsing` skill's "far above eight to one" test.
_MAX_DECOMPRESSION_RATIO = 32

# An absolute ceiling on top of the ratio: nothing an AoE2 DE client produces comes close to this
# (data-sources.md's own worked example is ~6.9 MB), so this only ever catches an archive the ratio
# check might otherwise let through as merely-poorly-compressed.
_MAX_INNER_BYTES = 200 * 1024 * 1024


class Aoe2RecValidator:
    """The `aoe2rec-py`-backed `ReplayValidator`. Capture-time validation only.

    Full replay parsing (match extraction, opening detection, elo) is out of scope for this
    adapter, by design — see the module docstring. This class implements no other method.
    """

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        member = self._well_formed_member(zip_bytes)
        with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
            # In memory only, never to disk — extraction safety per the `replay-parsing` skill.
            data = archive.read(member.filename)
        if len(data) != member.file_size:
            raise MalformedArchiveError(
                f"{member.filename}: declared {member.file_size} bytes, extracted {len(data)}"
            )
        self._confirm_parseable(data)
        return ReplayValidationResult(
            inner_filename=member.filename,
            inner_bytes=member.file_size,
            engine_name=ENGINE_NAME,
            engine_version=metadata.version(ENGINE_NAME),
        )

    @staticmethod
    def _well_formed_member(zip_bytes: bytes) -> zipfile.ZipInfo:
        try:
            archive = zipfile.ZipFile(BytesIO(zip_bytes))
        except zipfile.BadZipFile as exc:
            raise MalformedArchiveError(f"not a zip archive: {exc}") from exc
        with archive:
            members = archive.infolist()
            if len(members) != 1:
                raise MalformedArchiveError(f"expected exactly one member, found {len(members)}")
            member = members[0]
            if not _INNER_FILENAME_RE.match(member.filename):
                raise MalformedArchiveError(f"unexpected inner filename {member.filename!r}")
            if member.file_size > _MAX_INNER_BYTES:
                raise MalformedArchiveError(
                    f"{member.filename}: {member.file_size} bytes exceeds the "
                    f"{_MAX_INNER_BYTES}-byte cap"
                )
            ratio = _decompression_ratio(member)
            if ratio > _MAX_DECOMPRESSION_RATIO:
                raise MalformedArchiveError(
                    f"{member.filename}: decompression ratio {ratio:.1f} exceeds the "
                    f"{_MAX_DECOMPRESSION_RATIO}x cap — treated as a zip bomb, not a replay"
                )
            return member

    @staticmethod
    def _confirm_parseable(data: bytes) -> None:
        # A genuine engine crash surfaces as `pyo3_runtime.PanicException`, which inherits
        # `BaseException` directly and not `Exception` (confirmed against every malformed input
        # this package's own tests throw at it — see test_aoe2rec.py). It is deliberately left
        # uncaught here: that is the failure the ingester's containment barrier (T055) exists to
        # catch. Only an ordinary `Exception` — e.g. a future wheel returning a typed error instead
        # of panicking — is translated into this package's own error type.
        try:
            _native.parse_rec(data)
        except Exception as exc:
            raise EngineParseError(f"{ENGINE_NAME} rejected the replay: {exc}") from exc


def _decompression_ratio(member: zipfile.ZipInfo) -> float:
    if member.compress_size == 0:
        # A stored, empty member compresses to itself; anything non-empty compressing to nothing
        # is not a real zip stream and is treated as maximally suspicious.
        return 1.0 if member.file_size == 0 else float("inf")
    return member.file_size / member.compress_size
