"""The `aoe2rec-py` adapter satisfying `aoe2stats_core.replay.validation.ReplayValidator`.

Imported only by the ingester, which contains it behind the `BaseException`-catching barrier in
T055 — never by `packages/core`, which the API imports (constitution V), and never directly by
anything outside this package's own boundary (the `replay-parsing` skill: "Never import either
[engine] directly outside its adapter").

Well-formedness is checked before the engine ever sees a byte, per the skill's extraction-safety
discipline: exactly one member, an inner filename matching the naming scheme aoe.ms publishes
(`docs/data-sources.md`), and a decompression ratio that rules out a zip bomb. Those checks read
`member.file_size` and `member.compress_size` from the archive's own central directory, which is
attacker-supplied and not trusted on its own: the member is then decompressed through a bounded,
chunked stream (`_read_bounded`) that enforces the same size ceiling against what actually comes
out, so an archive that under-declares its size is still caught, and caught before it is fully
inflated in memory (T013a). Only a well-formed archive is handed to `aoe2rec_py.parse_rec`, whose
job is limited here to confirming the inner bytes are a replay it can open — nothing about match
content is read or returned.
"""

from __future__ import annotations

import re
import zipfile
from importlib import metadata
from io import BytesIO
from typing import cast

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
#
# This is also the hard cap enforced while actually reading the member (see `_read_bounded`), not
# just a pre-check on the declared `file_size`: `member.file_size` and `member.compress_size` are
# read from the archive's own central directory, i.e. attacker-supplied (T013a). An archive that
# under-declares `file_size` would otherwise pass this check on the header alone and still be
# fully decompressed into memory by the time anything noticed.
_MAX_INNER_BYTES = 200 * 1024 * 1024

# The chunk size used while streaming a member through `archive.open()`. A module constant, never
# derived from anything the archive declares about itself — an under-declared `file_size` must not
# be able to buy a bigger single read.
_READ_CHUNK_BYTES = 1024 * 1024


class Aoe2RecValidator:
    """The `aoe2rec-py`-backed `ReplayValidator`. Capture-time validation only.

    Full replay parsing (match extraction, opening detection, elo) is out of scope for this
    adapter, by design — see the module docstring. This class implements no other method.
    """

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        member = self._well_formed_member(zip_bytes)
        with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
            # In memory only, never to disk — extraction safety per the `replay-parsing` skill.
            #
            # `archive.open()` decompresses lazily, so `_read_bounded` can enforce the hard cap
            # chunk by chunk instead of trusting `member.file_size` — attacker-supplied, from the
            # archive's own central directory (T013a) — enough to call the unbounded
            # `archive.read(member.filename)` first and check the declared size after the fact.
            try:
                # `archive.open()` is typed as `IO[bytes]` (the Protocol every `zipfile` reader
                # satisfies) but always actually returns a `zipfile.ZipExtFile` at runtime for a
                # real archive member — `_read_bounded` needs that concrete type to neutralize its
                # `_left` truncation guard.
                with archive.open(member) as raw_stream:
                    stream = cast(zipfile.ZipExtFile, raw_stream)
                    data = _read_bounded(stream, cap=_MAX_INNER_BYTES, filename=member.filename)
            except zipfile.BadZipFile as exc:
                # `ZipExtFile` truncates its output to the declared `file_size` internally (it
                # tracks a `_left` countdown seeded from that same attacker-supplied field) and
                # then checks the running CRC the instant that countdown reaches zero. An archive
                # whose declared size disagrees with what it actually contains therefore fails the
                # CRC check inside the stdlib reader itself, under the cap, before `_read_bounded`
                # ever sees a mismatch to report — still rejected, just by a different signal, and
                # still translated to this package's own error type rather than leaking `zipfile`'s.
                raise MalformedArchiveError(
                    f"{member.filename}: failed reading under the {_MAX_INNER_BYTES}-byte cap — "
                    f"the archive's own bytes disagree with its declared size: {exc}"
                ) from exc
        if len(data) != member.file_size:
            # The stream finished within the cap, but what actually came out still disagrees with
            # what the header declared. Still malformed, still rejected — the declared-size check
            # is not redundant with the cap, it catches the opposite lie (a header that
            # over-declares, or simply gets it wrong, while staying under the cap).
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
            # A cheap pre-filter on the declared fields, rejecting an honestly-labelled oversized
            # archive before a single byte is decompressed. Not the authoritative check: both
            # fields come from the archive's own central directory, i.e. attacker-supplied, and an
            # archive that under-declares `file_size` sails through this and the ratio check below.
            # `_read_bounded` in `validate` enforces the same `_MAX_INNER_BYTES` ceiling against
            # what is actually decompressed, which is the check that cannot be lied to (T013a).
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


def _read_bounded(stream: zipfile.ZipExtFile, *, cap: int, filename: str) -> bytes:
    """Read `stream` in fixed-size chunks, refusing to materialize more than `cap` bytes (T013a).

    `member.file_size` and `member.compress_size` — what `_well_formed_member`'s pre-check and the
    decompression-ratio check are computed from — are read from the archive's own central
    directory, i.e. attacker-supplied. An archive that under-declares `file_size` passes both of
    those header-only checks and would still fully inflate if handed to `archive.read(name)`,
    which decompresses the entire member before anything downstream gets a chance to reject it.

    This reads through `archive.open(member)` instead, in chunks whose size is a module constant
    never derived from anything the archive claims about itself, and checks the running total
    against `cap` after every chunk — so an archive that inflates past the cap is caught mid-stream,
    having materialized at most one chunk beyond it, rather than after the whole member is already
    sitting in memory.

    `ZipExtFile` itself still trusts `file_size`, though: internally it tracks `_left`, seeded from
    `zinfo.file_size`, and truncates every `read()` to it — so an archive that *under*-declares its
    size is silently cut short by zipfile before this loop ever sees the overrun, and the truncated
    read then fails a CRC check computed for the true, larger member instead of raising the cap
    error this function exists to raise. `_left` is widened here to neutralize that: it is a
    truncation guard layered on top of the actual end-of-stream signal (the decompressor exhausting
    `compress_size`'s worth of input), which is what really stops the read and is not a single
    header field an archive can lie about in isolation the way `file_size` is. Widening `_left`
    therefore only removes zipfile's redundant trust in `file_size` — it cannot make this function
    read a single byte that was not really in the archive, and the cap below still bounds every
    call regardless of what `_left` allows.
    """
    stream._left = cap + _READ_CHUNK_BYTES  # type: ignore[attr-defined]  # see docstring above
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = stream.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise MalformedArchiveError(
                f"{filename}: decompressed past the {cap}-byte cap while reading — rejected "
                "regardless of what the archive's own central directory declares"
            )
        chunks.append(chunk)
    return b"".join(chunks)
