"""Projection unit tests for T412 — the fix for research.md's **D1**: `match_players.civ_id`,
`team_id`, `rating`, `rating_diff` and `result` have never been written (`upsert_match_player`
inserts only the primary key), even though every one of them is already sitting in
`matches.raw_payload`. This file is quickstart scenario 2's first half.

T413 implemented `aoe2stats_storage.repositories.matches.project_match_player` against exactly the
interface documented below, and every `xfail(strict=True, reason="T413 not implemented yet")`
marker that used to sit on each test — forced off by `strict=True` the moment the module landed and
these tests started passing for real, per the pattern `scripts/checks/tests/test_asset_packs.py`'s
own history records for T402/T403 — has been removed. Imports of the projected names still live
**inside each test body**, never at module scope, matching every other test file in this package
that predates its own implementation (`test_relic_matches.py`'s `_provider`) — there is no longer a
`ModuleNotFoundError` to guard against, but nothing is lost by keeping the same shape.

## The contract this file defined for T413, which it now implements

`aoe2stats_storage.repositories.matches` gains:

- `ProjectedMatchPlayer` — a frozen dataclass carrying the five columns data-model.md's
  `match_players` table names: `civ_id: int | None`, `team_id: int | None`, `rating: int | None`,
  `rating_diff: int | None`, `result: str | None` (`"win"` / `"loss"` / `None`, never a third
  string — FR-004's neutral state, `data-model.md` §1).
- `project_match_player(raw_match: Mapping[str, Any], profile_id: int) -> ProjectedMatchPlayer` —
  pure, no I/O, no session: one entry of `matches.raw_payload` (a `matchHistoryStats[]` item, the
  shape `RawMatch.raw_payload` carries verbatim) plus the profile id `upsert_match_player`'s own
  call site (`DiscoverStage.__call__`, `apps/ingester/.../discover.py`) already loops over, in and
  a `MatchPlayer`-shaped result out. Rules, straight from data-model.md's `match_players` table:
    - `civ_id` <- `matchhistorymember[].civilization_id`, direct.
    - `team_id` <- `matchhistorymember[].teamid`, direct.
    - `rating` <- `matchhistorymember[].newrating`, the value *after* the match (FR-005).
    - `rating_diff` <- `newrating - oldrating`, signed, `NULL` — never `0` — the moment either
      side is absent: a `0` is a real, symmetric rating outcome and reads as "no change" to
      anyone downstream, while `NULL` is the only value that says "unknown".
    - `result` <- `matchhistorymember[].outcome`: `1` -> `"win"`, `0` -> `"loss"`, any other value
      (including a draw code this feature does not otherwise interpret) -> `None`, FR-004's
      neutral state, never silently coerced into `"loss"`.
- `MatchProjectionMismatch(ValueError)` — raised, not swallowed and not used to pick a side, the
  moment `civilization_id` / `teamid` / the mapped result disagrees between `matchhistorymember[]`
  and that same `profile_id`'s entry in `matchhistoryreportresults[]`. data-model.md is explicit
  that the second array is "the cross-check, not a second source": a silent tie-break here is
  exactly how a wrong civ would ship looking confident, and this exception is what stops that at
  the write, rather than at whichever pixel first looks wrong.

Every scenario below is built from
`packages/providers/fixtures/relic/get_recent_match_history.json` (a deep copy per test, mutated
locally — no test leaks state into another): its `matchHistoryStats[0]` (`game_id` 500615037)
already agrees, member for member, with its own `matchhistoryreportresults[]`, so the happy-path
tests use it untouched and the mismatch tests mutate exactly the one field under test.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "providers" / "fixtures" / "relic"

# `matchHistoryStats[0]` (game 500615037): an 8-player team match whose `matchhistorymember[]`
# agrees with `matchhistoryreportresults[]` on every participant (measured against the fixture
# directly) — the clean base every happy-path test mutates from, if at all.
_LOSING_PROFILE_ID = 264353  # civ 28, team 1, outcome 0 (loss), old 1512 -> new 1498
_WINNING_PROFILE_ID = 196240  # civ 42, team 2, outcome 1 (win), old 1698 -> new 1704


def _load_raw_match(index: int = 0) -> dict[str, Any]:
    """One `matchHistoryStats[]` entry, deep-copied out of the fixture so a test mutating it can
    never leak that mutation into another test running against the same file."""
    body = json.loads((FIXTURES / "get_recent_match_history.json").read_text(encoding="utf-8"))
    return copy.deepcopy(body["matchHistoryStats"][index])


def _member(raw_match: dict[str, Any], profile_id: int) -> dict[str, Any]:
    return next(
        entry for entry in raw_match["matchhistorymember"] if entry["profile_id"] == profile_id
    )


def _report(raw_match: dict[str, Any], profile_id: int) -> dict[str, Any]:
    return next(
        entry
        for entry in raw_match["matchhistoryreportresults"]
        if entry["profile_id"] == profile_id
    )


# --- civ_id / team_id: direct from matchhistorymember --------------------------------------------


def test_civ_id_and_team_id_are_mapped_directly_from_the_fixture() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _LOSING_PROFILE_ID)

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.civ_id == member["civilization_id"] == 28
    assert projected.team_id == member["teamid"] == 1


# --- rating: newrating, the value after the match (FR-005) ---------------------------------------


def test_rating_is_newrating_not_oldrating() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _WINNING_PROFILE_ID)
    assert member["oldrating"] != member["newrating"], "fixture must exercise a real rating move"

    projected = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert projected.rating == member["newrating"] == 1704
    assert projected.rating != member["oldrating"]


# --- rating_diff: signed newrating - oldrating, NULL (never 0) when either side is missing -------


def test_rating_diff_is_signed_newrating_minus_oldrating() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()

    losing = project_match_player(raw_match, _LOSING_PROFILE_ID)
    winning = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert losing.rating_diff == 1498 - 1512 == -14
    assert winning.rating_diff == 1704 - 1698 == 6


def test_rating_diff_is_null_not_zero_when_oldrating_is_missing() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _LOSING_PROFILE_ID)
    del member["oldrating"]

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.rating_diff is None, (
        "a missing side must project to NULL — a 0 here would read as a real, symmetric rating "
        "outcome rather than 'unknown'"
    )
    assert projected.rating_diff != 0


def test_rating_diff_is_null_not_zero_when_newrating_is_missing() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _WINNING_PROFILE_ID)
    del member["newrating"]

    projected = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert projected.rating_diff is None
    assert projected.rating_diff != 0
    # FR-005 shows the post-match rating; with `newrating` itself missing there is none to show.
    assert projected.rating is None


# --- result: outcome 1 -> win, 0 -> loss, a third value -> NULL (FR-004's neutral state) ---------


def test_outcome_one_maps_to_win() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    assert _member(raw_match, _WINNING_PROFILE_ID)["outcome"] == 1

    projected = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert projected.result == "win"


def test_outcome_zero_maps_to_loss() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    assert _member(raw_match, _LOSING_PROFILE_ID)["outcome"] == 0

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.result == "loss"


def test_a_third_outcome_value_maps_to_null_not_a_coerced_loss() -> None:
    """FR-004: a result that is neither win nor loss (a draw code, or anything else Relic might
    ever send) is its own neutral state, not silently folded into a loss. Both `outcome` and the
    cross-check's `resulttype` are set to the same third value here, deliberately: this test is
    about the `outcome` mapping alone, so the cross-check (its own tests, below) is kept in
    agreement rather than incidentally exercised.
    """
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    _member(raw_match, _LOSING_PROFILE_ID)["outcome"] = 3
    _report(raw_match, _LOSING_PROFILE_ID)["resulttype"] = 3

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.result is None
    assert projected.result != "loss"
    assert projected.result != "win"


# --- matchhistoryreportresults[] is a cross-check: a disagreement raises, never a tie-break ------


def test_a_civ_id_disagreement_with_report_results_raises() -> None:
    from aoe2stats_storage.repositories.matches import MatchProjectionMismatch, project_match_player

    raw_match = _load_raw_match()
    _report(raw_match, _LOSING_PROFILE_ID)["civilization_id"] = 99

    with pytest.raises(MatchProjectionMismatch):
        project_match_player(raw_match, _LOSING_PROFILE_ID)


def test_a_team_id_disagreement_with_report_results_raises() -> None:
    from aoe2stats_storage.repositories.matches import MatchProjectionMismatch, project_match_player

    raw_match = _load_raw_match()
    report = _report(raw_match, _LOSING_PROFILE_ID)
    assert report["teamid"] == 1
    report["teamid"] = 2

    with pytest.raises(MatchProjectionMismatch):
        project_match_player(raw_match, _LOSING_PROFILE_ID)


def test_a_result_disagreement_with_report_results_raises() -> None:
    """`matchhistorymember[].outcome` says loss (`0`); `matchhistoryreportresults[].resulttype` is
    flipped to `1` (win) for the same participant here — the two must agree, and a projection that
    silently trusted one over the other is exactly the "wrong civ ships looking confident" failure
    mode `data-model.md` calls out this cross-check to prevent.
    """
    from aoe2stats_storage.repositories.matches import MatchProjectionMismatch, project_match_player

    raw_match = _load_raw_match()
    assert _member(raw_match, _LOSING_PROFILE_ID)["outcome"] == 0
    report = _report(raw_match, _LOSING_PROFILE_ID)
    assert report["resulttype"] == 0
    report["resulttype"] = 1

    with pytest.raises(MatchProjectionMismatch):
        project_match_player(raw_match, _LOSING_PROFILE_ID)


def test_an_unmodified_fixture_entry_never_raises_the_cross_check() -> None:
    """The negative space of the four tests above: `matchHistoryStats[0]` agrees with its own
    `matchhistoryreportresults[]` for every participant, unmodified, so projecting every one of
    them must succeed — the cross-check is a guard against disagreement, not a blanket rejection
    of the array's mere presence.
    """
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    profile_ids = [member["profile_id"] for member in raw_match["matchhistorymember"]]
    assert len(profile_ids) == 8

    for profile_id in profile_ids:
        project_match_player(raw_match, profile_id)  # must not raise


# --- color_id: slotinfo[].metaData.ScenarioPlayerIndex + 1 (T411) ---------------------------------
#
# 004's D2 decoded this exact record on 2026-08-30, read `ScenarioPlayerIndex` as a seat number
# and concluded Relic carries no colour. It is the colour: the player's 0-based number in the
# game, which in Age of Empires II: DE *is* the colour (0 blue, 1 red, ... 7 orange), so `+1` is
# the 1..8 scheme `PlayerColourSwatch` renders and companion's own `color` uses. The first test
# below is the proof, re-run on every suite: every participant of every match the Relic and
# companion fixtures share, joined on `(match id, profile id)`, projects to exactly companion's
# colour. `docs/data-sources.md` §1 records the measurement; this test is what keeps it true.

COMPANION_FIXTURE = FIXTURES.parent / "companion" / "matches.json"


def _companion_colours() -> dict[tuple[int, int], int]:
    body = json.loads(COMPANION_FIXTURE.read_text(encoding="utf-8"))
    return {
        (match["matchId"], player["profileId"]): player["color"]
        for match in body["matches"]
        for team in match["teams"]
        for player in team["players"]
    }


def _relic_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name in ("get_recent_match_history.json", "get_recent_match_history_batch.json"):
        body = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        entries.extend(body["matchHistoryStats"])
    return entries


def _slots(raw_match: dict[str, Any]) -> list[dict[str, Any]]:
    """Inflate `slotinfo` the way the projection does, for a test that needs to *mutate* one
    slot's `metaData` and re-pack the blob. Mirrors the decode chain in
    `aoe2stats_storage.repositories.matches._slot_colour_id` deliberately: a test that re-packs
    with a different layout would only prove the two disagree."""
    import base64
    import zlib

    text = zlib.decompress(base64.b64decode(raw_match["slotinfo"])).decode("utf-8")
    prefix, _, body = text.partition(",")
    slots, end = json.JSONDecoder().raw_decode(body)
    raw_match["__slotinfo_prefix__"] = prefix
    raw_match["__slotinfo_suffix__"] = body[end:]
    return list(slots)


def _repack_slots(raw_match: dict[str, Any], slots: list[dict[str, Any]]) -> None:
    import base64
    import zlib

    text = (
        raw_match.pop("__slotinfo_prefix__")
        + ","
        + json.dumps(slots, separators=(",", ":"))
        + raw_match.pop("__slotinfo_suffix__")
    )
    raw_match["slotinfo"] = base64.b64encode(zlib.compress(text.encode("utf-8"))).decode("ascii")


def _encode_slot_metadata(record: dict[str, str]) -> str:
    """The inverse of `_decode_slot_metadata`: count byte, then `(u32 LE length, bytes)` pairs,
    base64, wrapped as a JSON string literal, base64 again."""
    import base64
    import struct

    blob = bytes([len(record)])
    for key, value in record.items():
        key_bytes = key.encode("utf-8")
        value_bytes = value.encode("utf-8")
        blob += struct.pack("<I", len(key_bytes)) + key_bytes
        blob += struct.pack("<I", len(value_bytes)) + value_bytes
    inner = base64.b64encode(blob).decode("ascii")
    return base64.b64encode(json.dumps(inner).encode("utf-8")).decode("ascii")


def _with_slot_metadata(profile_id: int, record: dict[str, str]) -> dict[str, Any]:
    raw_match = _load_raw_match()
    slots = _slots(raw_match)
    slot = next(entry for entry in slots if entry["profileInfo.id"] == profile_id)
    slot["metaData"] = _encode_slot_metadata(record)
    _repack_slots(raw_match, slots)
    return raw_match


def test_color_id_equals_companions_colour_for_every_shared_participant() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    companion = _companion_colours()
    joined = 0
    for raw_match in _relic_entries():
        for member in raw_match["matchhistorymember"]:
            key = (raw_match["id"], member["profile_id"])
            projected = project_match_player(raw_match, member["profile_id"])
            assert projected.color_id is not None, f"no colour projected for {key}"
            assert 1 <= projected.color_id <= 8, key
            if key in companion:
                assert projected.color_id == companion[key], (
                    f"{key}: Relic's slotinfo says {projected.color_id}, companion says "
                    f"{companion[key]} — the decode chain no longer names the colour"
                )
                joined += 1
    # Three matches, eight players each, in both fixtures — a join that finds fewer pairs is
    # comparing nothing and would pass vacuously.
    assert joined >= 24, f"only {joined} participants joined across the two fixtures"


def test_color_id_for_the_documented_participants() -> None:
    """The two profiles every other test in this file names, pinned: 264353 (Somero) is index 6,
    orange-adjacent grey (7); 196240 (TheViper) is index 3, yellow (4) — companion's own values
    for match 500615037."""
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id == 7
    assert project_match_player(raw_match, _WINNING_PROFILE_ID).color_id == 4


def test_a_participant_the_repack_helper_leaves_untouched_still_projects() -> None:
    """Guards the test helpers themselves: inflating and re-packing `slotinfo` without changing a
    slot must round-trip to the same colour, or every mutation test below proves nothing."""
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    _repack_slots(raw_match, _slots(raw_match))

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id == 7


def test_color_id_is_null_when_slotinfo_is_absent() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    del raw_match["slotinfo"]

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.color_id is None
    # The other five columns do not depend on the blob and are still projected.
    assert projected.civ_id == 28


@pytest.mark.parametrize(
    "slotinfo",
    [
        "not base64!",
        "AAAA",  # valid base64, not a zlib stream
        "eJzLSM3JyVcozy/KSQEAGgsEXQ==",  # zlib of "hello world": no comma, no JSON array
        "eJwzNNKJNgQAAy0BHA==",  # zlib of "12,[1" — truncated array
    ],
)
def test_color_id_is_null_never_an_exception_on_a_malformed_slotinfo(slotinfo: str) -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    raw_match["slotinfo"] = slotinfo

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id is None


def test_color_id_is_null_when_the_profile_has_no_slot() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    slots = [entry for entry in _slots(raw_match) if entry["profileInfo.id"] != _LOSING_PROFILE_ID]
    _repack_slots(raw_match, slots)

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id is None


def test_color_id_is_null_when_metadata_lacks_scenario_player_index() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _with_slot_metadata(_LOSING_PROFILE_ID, {"Team": "2"})

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id is None


@pytest.mark.parametrize("index", ["-1", "8", "12", "blue", ""])
def test_color_id_is_null_never_a_wrong_swatch_for_an_index_outside_zero_to_seven(
    index: str,
) -> None:
    """An index no game colour is defined for is not mapped to *some* colour: `None` renders the
    neutral chip (`PlayerColourSwatch`, "empty" and "error" are byte-identical), a wrong integer
    renders someone else's colour looking confident."""
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _with_slot_metadata(_LOSING_PROFILE_ID, {"ScenarioPlayerIndex": index})

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id is None


@pytest.mark.parametrize(("index", "expected"), [("0", 1), ("7", 8)])
def test_color_id_maps_both_ends_of_the_index_range(index: str, expected: int) -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _with_slot_metadata(_LOSING_PROFILE_ID, {"ScenarioPlayerIndex": index, "Team": "2"})

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id == expected


def test_color_id_is_null_when_metadata_is_not_decodable() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    slots = _slots(raw_match)
    slot = next(entry for entry in slots if entry["profileInfo.id"] == _LOSING_PROFILE_ID)
    slot["metaData"] = "IkFBQUEi"  # base64 of '"AAAA"': inner layer is three NUL bytes, no record
    _repack_slots(raw_match, slots)

    assert project_match_player(raw_match, _LOSING_PROFILE_ID).color_id is None
