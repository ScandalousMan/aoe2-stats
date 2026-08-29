"""The `aoe2rec-py` adapter satisfying `aoe2stats_core.replay.validation.ReplayValidator`, and the
`Build`-action decoder (R4, T353/T354).

Imported only by the ingester, which contains it behind the `BaseException`-catching barrier in
T055 — never by `packages/core`, which the API imports (constitution V), and never directly by
anything outside this package's own boundary (the `replay-parsing` skill: "Never import either
[engine] directly outside its adapter"). `decode_build_action` is this same kind of engine-format
knowledge — which bytes of one wheel's output mean what — and lives here for the same reason:
constitution V wants it swappable with the engine, never leaked into `apps/analyzer`, which will
consume it only through the `ReplayExtractor` Protocol (T352).

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

`decode_build_action` (T354) decodes one raw `Build` action dict from the pinned wheel
(`aoe2rec-py==0.1.21`). `player_id` is already present on the field the wheel provides — R4 and
ADR-0001's 2026-08-24 correction are wrong on this point, measured directly against the pinned
wheel in `tests/test_aoe2rec.py` — so it is passed through unchanged, never re-derived from `data`.
What the wheel genuinely does not expose as a named field is the building-type identifier: the AoE2
DE Genie building id, recovered from `data[12:16]`, an unsigned little-endian 32-bit integer. That
offset was found empirically (swept across every byte position and all 17 distinct `action_length`
groups in the reference replay) and cross-checked against known Genie ids — see the test file's
module docstring and `_EXPECTED_BUILDING_TYPE_COUNTS` for the full derivation.

`Aoe2RecExtractor` (T355) satisfies `aoe2stats_core.replay.analysis.ReplayExtractor`. It shares
`_read_member_bytes` with `Aoe2RecValidator.validate` — the same well-formedness check, the same
bounded chunked read against `_MAX_INNER_BYTES` — rather than a second copy of either (contracts/
analysis.md's "it does not re-implement them"). Once the wheel has parsed the bytes, it walks
`operations` exactly once, reducing directly into the per-participant `ParticipantTimeline` fields
and never retaining the operation list itself (R3, contracts/analysis.md's "memory is part of the
contract"): the parsed dict and everything under it fall out of scope, and are eligible for
collection, the moment `extract` returns.

Every `Research` command is collapsed to its first occurrence per `(player_id, technology_type)`
before anything downstream sees it — a double-click on a button issues the same command twice,
208 ms apart on the wire, and the reference replay carries this for several technologies including
two of its three age-ups (R5). `age_up_commands` is that same collapsed set, filtered to technology
101/102/103 and keyed by technology id: an *ordered* age, never a *reached* one — see R5 for why a
research command is not a research completion, and why that distinction is roughly two minutes, in
the direction that flatters the player.
"""

from __future__ import annotations

import re
import struct
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from io import BytesIO
from typing import cast

from aoe2rec_py import aoe2rec_py as _native

from aoe2stats_core.replay.analysis import (
    BuildEvent,
    MatchTimeline,
    ParticipantTimeline,
    ResearchEvent,
    TrainingEvent,
)
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
        # `_read_bounded` below enforces the same `_MAX_INNER_BYTES` ceiling against what is
        # actually decompressed, which is the check that cannot be lied to (T013a).
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


def _read_member_bytes(zip_bytes: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    """The one extraction-safety path shared by `Aoe2RecValidator.validate` and
    `Aoe2RecExtractor.extract` (T355): well-formedness, then a bounded chunked read against the
    same hard ceiling, then a check of what actually came out against what the archive's own
    central directory declared. Two copies of this is one copy that falls behind, which is the
    reason it is a module-level function neither class re-implements.
    """
    member = _well_formed_member(zip_bytes)
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
    return member, data


class Aoe2RecValidator:
    """The `aoe2rec-py`-backed `ReplayValidator`. Capture-time validation only.

    Full replay parsing (match extraction, opening detection, elo) is out of scope for this
    adapter, by design — see the module docstring. This class implements no other method.
    """

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        member, data = _read_member_bytes(zip_bytes)
        self._confirm_parseable(data)
        return ReplayValidationResult(
            inner_filename=member.filename,
            inner_bytes=member.file_size,
            engine_name=ENGINE_NAME,
            engine_version=metadata.version(ENGINE_NAME),
        )

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


# The offset within `Build.data` where the AoE2 DE Genie building-type identifier sits, an
# unsigned little-endian 32-bit integer. Found empirically and pinned by
# `tests/test_aoe2rec.py`: see this module's docstring for the derivation.
_BUILDING_TYPE_OFFSET = 12
_BUILDING_TYPE_STRUCT = struct.Struct("<I")


@dataclass(frozen=True, slots=True)
class DecodedBuildAction:
    """One `Build` action's `player_id` and building-type identifier (T354, R4).

    `player_id` is read straight from the field the pinned wheel already provides on every `Build`
    action, never re-derived from `data` — see `test_the_pinned_wheel_already_returns_a_player_id_
    for_build_actions` and `test_no_fixed_byte_offset_in_build_data_recovers_player_id` in
    `tests/test_aoe2rec.py`, which pin this as measured fact against the pinned
    `aoe2rec-py==0.1.21` wheel and correct R4 / ADR-0001's now-superseded claim that the field is
    missing entirely. `building_id` is the one piece genuinely absent from the wheel's own output:
    the AoE2 DE Genie building id, decoded from raw bytes.
    """

    player_id: int
    building_id: int


def decode_build_action(build_action: Mapping[str, object]) -> DecodedBuildAction:
    """Decode a raw `Build` action dict from the pinned `aoe2rec-py` wheel.

    `build_action` is the `{"player_id", "action_length", "data"}` dict the wheel hands back for
    one `Build` action (`parsed["operations"][i]["Action"]["action_data"]["Build"]`). `player_id`
    passes through unchanged. `building_id` is decoded from `data[12:16]`, an unsigned
    little-endian 32-bit integer — the offset `tests/test_aoe2rec.py` pins against all 326 `Build`
    actions in the reference replay, cross-checked there against known AoE2 DE Genie building ids.
    """
    data = cast(Sequence[int], build_action["data"])
    building_bytes = bytes(data[_BUILDING_TYPE_OFFSET : _BUILDING_TYPE_OFFSET + 4])
    (building_id,) = _BUILDING_TYPE_STRUCT.unpack(building_bytes)
    return DecodedBuildAction(
        player_id=cast(int, build_action["player_id"]),
        building_id=building_id,
    )


# --- `extract()` (T355, R1/R2/R5) -----------------------------------------------------------

# The DE train command for a villager (`DeQueue.unit_id`), confirmed against the reference
# replay's own `_EXPECTED_BUILDING_TYPE_COUNTS`-style cross-check: every `DeQueue` naming this
# unit id is issued at a Town Center in this game. `villagers_ordered` counts these, net of the
# cancellations below (R1, FR-043b) — never a population.
_VILLAGER_UNIT_ID = 83

# The DE action vocabulary's cancellation counterparts to `DeQueue`, per R1: "the action
# vocabulary carries `Unqueue`, `FarmUnqueue` and `FishtrapUnqueue` — verified present in the
# parser's own type table, though absent from this particular game". None of the three appears
# in the committed reference replay (`villagers_ordered` there is the raw `DeQueue` sum with
# nothing to net against), so this set is exercised only once a recording that cancels a queued
# villager is captured — carried here rather than left to be discovered then, on the same
# `{"player_id", "unit_id", "amount"}` shape `DeQueue` already has.
_TRAINING_CANCELLATION_VARIANTS = frozenset({"Unqueue", "FarmUnqueue", "FishtrapUnqueue"})

# Technology 101 (Feudal Age), 102 (Castle Age), 103 (Imperial Age) — named here because the
# analysis is about them (R13); every other technology id ships as an identifier, unnamed.
_AGE_UP_TECHNOLOGY_IDS = frozenset({101, 102, 103})


class Aoe2RecExtractor:
    """The `aoe2rec-py`-backed `ReplayExtractor` (T355).

    Shares `_read_member_bytes` with `Aoe2RecValidator.validate` — see that function's docstring —
    so this class implements no well-formedness check of its own. Once the wheel has parsed the
    bytes, `extract` walks `parsed["operations"]` exactly once, reducing directly into the
    returned `MatchTimeline` and never retaining the operation list (R3): everything the wheel
    materialised is eligible for collection the moment this method returns.

    `max_raw_bytes` (T357, R3) is a **required** keyword-only constructor argument, not a module
    constant: it is the analysis memory ceiling (`ANALYSIS_MAX_RAW_BYTES`), a number this package
    must never hard-code or duplicate — its home is `.env.example`, read by `apps/analyzer`'s
    settings and passed in here, so this package stays importable and config-agnostic
    (constitution V; CLAUDE.md's "never copy a measurement between homes"). It is unrelated to
    `_MAX_INNER_BYTES` above: that constant is a zip-bomb guard shared with `Aoe2RecValidator`,
    sized to catch an archive that inflates far past any real replay's ~8:1 ratio, and it is ~9x
    too permissive to protect memory (R3 — 200 MB inner bytes still amplifies to well past the 2 GB
    resident ceiling once every operation is materialised). `max_raw_bytes` is the additional,
    tighter check that exists only on this path, refusing what R3 measured as certainly too large
    to parse in memory, before a single byte reaches the engine.
    """

    def __init__(self, *, max_raw_bytes: int) -> None:
        self._max_raw_bytes = max_raw_bytes

    def extract(self, zip_bytes: bytes) -> MatchTimeline:
        # The declared, uncompressed member size — read from the archive's own central directory,
        # exactly like `_well_formed_member`'s own `_MAX_INNER_BYTES` check — is compared against
        # the configured ceiling before a single byte is decompressed or handed to the engine.
        # `_well_formed_member` still runs its own checks first (single member, expected filename,
        # `_MAX_INNER_BYTES`, decompression ratio); this is an additional, stricter refusal on top,
        # not a replacement for any of them.
        member = _well_formed_member(zip_bytes)
        if member.file_size > self._max_raw_bytes:
            raise MalformedArchiveError(
                f"{member.filename}: {member.file_size} bytes exceeds this analysis's "
                f"{self._max_raw_bytes}-byte ceiling — refused before parsing (R3)"
            )
        _member, data = _read_member_bytes(zip_bytes)
        parsed = _parse_or_raise(data)
        return _build_timeline(parsed)


def _parse_or_raise(data: bytes) -> Mapping[str, object]:
    # Same uncaught-BaseException discipline as `Aoe2RecValidator._confirm_parseable`: a native
    # engine crash (`pyo3_runtime.PanicException`, a bare `BaseException`) is T055's containment
    # barrier's to catch, not this adapter's.
    try:
        return cast(Mapping[str, object], _native.parse_rec(data))
    except Exception as exc:
        raise EngineParseError(f"{ENGINE_NAME} rejected the replay: {exc}") from exc


def _postgame_world_time_ms(parsed: Mapping[str, object]) -> int:
    """The `PostGame` `WorldTime` block: the match clock's end (contracts/analysis.md).

    `PostGame` is one operation, present exactly once, carrying a list of typed `blocks` — this
    replay's carries `Leaderboards` and `WorldTime` (R1's `Achievements` is a block the engine
    knows how to read, not one this game contains). Only `WorldTime` is this repository's to read.
    """
    operations = cast(Sequence[Mapping[str, object]], parsed["operations"])
    for operation in operations:
        if "PostGame" not in operation:
            continue
        postgame = cast(Mapping[str, object], operation["PostGame"])
        blocks = cast(Sequence[Mapping[str, object]], postgame["blocks"])
        for block in blocks:
            if "WorldTime" in block:
                world_time_block = cast(Mapping[str, object], block["WorldTime"])
                return cast(int, world_time_block["world_time"])
        raise EngineParseError("PostGame block carries no WorldTime entry")
    raise EngineParseError("no PostGame block in the parsed replay")


def _build_timeline(parsed: Mapping[str, object]) -> MatchTimeline:
    zheader = cast(Mapping[str, object], parsed["zheader"])
    game_settings = cast(Mapping[str, object], zheader["game_settings"])
    raw_players = cast(Sequence[Mapping[str, object]], game_settings["players"])

    # `meta.rec_owner` is a zero-based index into `game_settings.players`, not a `player_number`
    # (R2): confirmed against the reference replay, whose `rec_owner` is `1` and whose recording
    # owner is `players[1]` (profile 196240), not the player whose own `player_number` is `1`
    # (profile 288714) — the two disagree on this exact recording, which is what makes this worth
    # pinning rather than assuming.
    meta = cast(Mapping[str, object], parsed["meta"])
    rec_owner_index = cast(int, meta["rec_owner"])
    point_of_view_profile_id = cast(int, raw_players[rec_owner_index]["profile_id"])

    world_time_ms = _postgame_world_time_ms(parsed)

    builds: dict[int, list[BuildEvent]] = defaultdict(list)
    trainings: dict[int, list[TrainingEvent]] = defaultdict(list)
    # player_id -> technology_id -> the first world_time_ms it was ordered at. A `dict` preserves
    # insertion order, which is stream order here, and `setdefault` below is exactly "first
    # occurrence wins" (R5): a later, duplicate command for the same pair never overwrites it.
    researches: dict[int, dict[int, int]] = defaultdict(dict)
    villagers_ordered: dict[int, int] = defaultdict(int)
    actions: dict[int, int] = defaultdict(int)
    resigned_at_ms: dict[int, int] = {}

    operations = cast(Sequence[Mapping[str, object]], parsed["operations"])
    for operation in operations:
        if "Action" not in operation:
            # `Sync`, `Viewlock`, `Chat`, `PostGame` — none of them an ordered command.
            continue
        action = cast(Mapping[str, object], operation["Action"])
        action_world_time_ms = cast(int, action["world_time"])
        action_data = cast(Mapping[str, Mapping[str, object]], action["action_data"])
        variant, payload = next(iter(action_data.items()))
        player_id = cast(int, payload["player_id"])
        actions[player_id] += 1

        if variant == "Build":
            decoded = decode_build_action(payload)
            builds[decoded.player_id].append(
                BuildEvent(building_id=decoded.building_id, world_time_ms=action_world_time_ms)
            )
        elif variant == "DeQueue":
            unit_id = cast(int, payload["unit_id"])
            amount = cast(int, payload["amount"])
            building_id = cast(int, payload["building_type"])
            trainings[player_id].append(
                TrainingEvent(
                    unit_id=unit_id,
                    amount=amount,
                    building_id=building_id,
                    world_time_ms=action_world_time_ms,
                )
            )
            if unit_id == _VILLAGER_UNIT_ID:
                villagers_ordered[player_id] += amount
        elif variant in _TRAINING_CANCELLATION_VARIANTS:
            unit_id = cast(int, payload.get("unit_id", -1))
            if unit_id == _VILLAGER_UNIT_ID:
                villagers_ordered[player_id] -= cast(int, payload.get("amount", 0))
        elif variant == "Research":
            technology_id = cast(int, payload["technology_type"])
            researches[player_id].setdefault(technology_id, action_world_time_ms)
        elif variant == "Resign":
            resigned_at_ms.setdefault(player_id, action_world_time_ms)

    participants = [
        _build_participant(
            raw_player,
            builds=builds,
            trainings=trainings,
            researches=researches,
            villagers_ordered=villagers_ordered,
            actions=actions,
            resigned_at_ms=resigned_at_ms,
            world_time_ms=world_time_ms,
        )
        for raw_player in sorted(raw_players, key=lambda player: cast(int, player["player_number"]))
    ]

    return MatchTimeline(
        engine_name=ENGINE_NAME,
        engine_version=metadata.version(ENGINE_NAME),
        point_of_view_profile_id=point_of_view_profile_id,
        world_time_ms=world_time_ms,
        participants=participants,
    )


def _build_participant(
    raw_player: Mapping[str, object],
    *,
    builds: Mapping[int, list[BuildEvent]],
    trainings: Mapping[int, list[TrainingEvent]],
    researches: Mapping[int, dict[int, int]],
    villagers_ordered: Mapping[int, int],
    actions: Mapping[int, int],
    resigned_at_ms: Mapping[int, int],
    world_time_ms: int,
) -> ParticipantTimeline:
    player_number = cast(int, raw_player["player_number"])
    player_researches = researches.get(player_number, {})
    player_actions = actions.get(player_number, 0)
    return ParticipantTimeline(
        profile_id=cast(int, raw_player["profile_id"]),
        player_number=player_number,
        civ_id=cast(int, raw_player["civ_id"]),
        resolved_team_id=cast(int, raw_player["resolved_team_id"]),
        builds=tuple(builds.get(player_number, [])),
        trainings=tuple(trainings.get(player_number, [])),
        researches=tuple(
            ResearchEvent(technology_id=technology_id, world_time_ms=t)
            for technology_id, t in player_researches.items()
        ),
        age_up_commands={
            technology_id: t
            for technology_id, t in player_researches.items()
            if technology_id in _AGE_UP_TECHNOLOGY_IDS
        },
        villagers_ordered=villagers_ordered.get(player_number, 0),
        actions=player_actions,
        actions_per_minute=(
            player_actions / (world_time_ms / 60_000) if world_time_ms > 0 else 0.0
        ),
        resigned_at_ms=resigned_at_ms.get(player_number),
    )
