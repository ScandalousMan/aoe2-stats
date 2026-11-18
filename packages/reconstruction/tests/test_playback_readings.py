"""Playback readings are well-formed (contracts/playback-readings.md, assertion 4, T924).

Every ``tests/fixtures/replays/<recording>.playback.toml`` holds a ``recording`` header naming its
recording and one ``[[reading]]`` table per reading. Every reading names a request in the
owner-readings file, a build the fixtures README lists for that recording, a reader and a date.
The committed files hold no reading yet: this test passes over them vacuously until the owner
answers, and each malformation below is planted inline to show it is refused.

``custom-games.playback.toml`` is held to the same assertion with one difference: it names no
recording (``source = "custom-games"``), so ``build_shown`` is required but matched to no README
recording, and it is not counted among the recordings' files.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPLAYS = _REPO_ROOT / "tests" / "fixtures" / "replays"
_OWNER_READINGS = _REPO_ROOT / "specs" / "008-match-reconstruction" / "owner-readings.md"
_README = _REPLAYS / "README.md"

_CUSTOM_STEM = "custom-games"

_REQUIRED = ("id", "request", "quantity", "value", "read_by", "read_on", "build_shown")
_CUSTOM_REQUIRED = ("civilisation", "preset")


def _requests() -> set[str]:
    """Top-level ids (`## O<n> `) and sub-request ids (`**O<n>.<m> —`) the file states."""
    text = _OWNER_READINGS.read_text(encoding="utf-8")
    top = re.findall(r"^## (O\d+) ", text, re.M)
    sub = re.findall(r"^\*\*(O\d+\.\d+) \u2014", text, re.M)
    return {*top, *sub}


def _builds() -> dict[str, set[str]]:
    """Recording id to the game builds the fixtures README lists for it."""
    out: dict[str, set[str]] = {}
    sections = re.split(r"^## ", _README.read_text(encoding="utf-8"), flags=re.M)
    for section in sections:
        head = re.match(r"`AgeIIDE_Replay_(\d+)\.zip`", section)
        build = re.search(r"\|\s*Game build\s*\|\s*(\d+)", section)
        if head and build:
            out.setdefault(head.group(1), set()).add(build.group(1))
    return out


def _problems(path: Path, requests: set[str], builds: dict[str, set[str]]) -> list[str]:
    """Every way the playback file at ``path`` is malformed; empty when well-formed."""
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [f"not valid TOML: {exc}"]
    problems: list[str] = []
    custom = path.name == f"{_CUSTOM_STEM}.playback.toml"
    recording = doc.get("recording")
    if custom:
        if doc.get("source") != _CUSTOM_STEM or "recording" in doc:
            problems.append(f"a custom-game file carries `source = {_CUSTOM_STEM!r}`, no recording")
    else:
        expected = path.name.removesuffix(".playback.toml").removeprefix("AgeIIDE_Replay_")
        if recording != expected:
            problems.append(f"recording {recording!r} does not match the file name ({expected!r})")
    readings = doc.get("reading", [])
    if not isinstance(readings, list):
        return [*problems, "`reading` must be an array of tables"]
    seen: set[str] = set()
    for index, reading in enumerate(readings):
        where = f"reading #{index}"
        if not isinstance(reading, dict):
            problems.append(f"{where}: not a table")
            continue
        for key in _REQUIRED:
            value = reading.get(key)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}: `{key}` missing or empty")
        if custom:
            for key in _CUSTOM_REQUIRED:
                value = reading.get(key)
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"{where}: custom-game reading `{key}` missing or empty")
        rid = reading.get("id")
        if isinstance(rid, str):
            if rid in seen:
                problems.append(f"{where}: duplicate id {rid!r}")
            seen.add(rid)
        request = reading.get("request")
        if isinstance(request, str) and request not in requests:
            problems.append(f"{where}: request {request!r} is not in the owner-readings file")
        build = reading.get("build_shown")
        if not custom and isinstance(build, str) and build not in builds.get(str(recording), set()):
            problems.append(f"{where}: build {build!r} is not listed for the recording")
        read_on = reading.get("read_on")
        if isinstance(read_on, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", read_on):
            problems.append(f"{where}: `read_on` {read_on!r} is not an ISO date")
    return problems


def _plant(tmp_path: Path, body: str, recording: str = "500546441") -> list[str]:
    path = tmp_path / f"AgeIIDE_Replay_{recording}.playback.toml"
    path.write_text(f'recording = "{recording}"\n{body}', encoding="utf-8")
    return _problems(path, _requests(), _builds())


_GOOD = """
[[reading]]
id = "R-1"
request = "O3"
participant = 2
at = "05:00"
quantity = "unit available"
value = "unreadable"
read_by = "owner"
read_on = "2026-11-20"
build_shown = "180059"
"""


def _without(key: str) -> str:
    return "\n".join(line for line in _GOOD.splitlines() if not line.startswith(f"{key} ="))


def test_every_committed_recording_has_a_playback_file() -> None:
    recordings = {p.name.split(".")[0] for p in _REPLAYS.glob("*.canonical.json")}
    files = {
        p.name.split(".")[0]
        for p in _REPLAYS.glob("*.playback.toml")
        if p.name != f"{_CUSTOM_STEM}.playback.toml"
    }
    assert recordings
    assert files == recordings


def test_committed_playback_files_are_well_formed() -> None:
    requests, builds = _requests(), _builds()
    files = sorted(_REPLAYS.glob("*.playback.toml"))
    assert files
    for path in files:
        assert _problems(path, requests, builds) == [], path.name


def test_the_sources_the_check_reads_are_not_empty() -> None:
    assert {"O3", "O4"} <= _requests()
    assert _builds()["511523321"] == {"185872"}


def test_a_well_formed_reading_passes(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD) == []


def test_refuses_a_header_that_names_another_recording(tmp_path: Path) -> None:
    path = tmp_path / "AgeIIDE_Replay_500546441.playback.toml"
    path.write_text('recording = "504695319"\n', encoding="utf-8")
    assert _problems(path, _requests(), _builds())


def test_refuses_invalid_toml(tmp_path: Path) -> None:
    assert _plant(tmp_path, "[[reading\n")


def test_refuses_a_request_absent_from_the_owner_readings(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD.replace('"O3"', '"O99"'))


def test_accepts_a_sub_request_the_owner_readings_state(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD.replace('"O3"', '"O8.1"')) == []


@pytest.mark.parametrize("unknown", ["O8.9", "O99.1"])
def test_refuses_a_sub_request_the_owner_readings_do_not_state(
    tmp_path: Path, unknown: str
) -> None:
    assert _plant(tmp_path, _GOOD.replace('"O3"', f'"{unknown}"'))


def test_refuses_a_missing_request(tmp_path: Path) -> None:
    assert _plant(tmp_path, _without("request"))


def test_refuses_a_build_not_listed_for_the_recording(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD.replace("180059", "185872"), recording="500546441")


@pytest.mark.parametrize("key", ["quantity", "value"])
def test_refuses_a_missing_quantity_or_value(tmp_path: Path, key: str) -> None:
    assert _plant(tmp_path, _without(key))


@pytest.mark.parametrize("key", ["quantity", "value"])
def test_refuses_a_blank_quantity_or_value(tmp_path: Path, key: str) -> None:
    assert _plant(tmp_path, _GOOD.replace(f'{key} = "', f'{key} = "  "\n#"', 1))


def test_refuses_a_missing_build(tmp_path: Path) -> None:
    assert _plant(tmp_path, _without("build_shown"))


def test_refuses_a_missing_reader(tmp_path: Path) -> None:
    assert _plant(tmp_path, _without("read_by"))


def test_refuses_a_blank_reader(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD.replace('"owner"', '"  "'))


def test_refuses_a_missing_date(tmp_path: Path) -> None:
    assert _plant(tmp_path, _without("read_on"))


def test_refuses_a_date_that_is_not_iso(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD.replace("2026-11-20", "20/11/2026"))


def test_refuses_a_missing_id(tmp_path: Path) -> None:
    assert _plant(tmp_path, _without("id"))


def test_refuses_a_duplicate_id(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD + _GOOD)


@pytest.mark.parametrize("recording", ["504695319", "511523321"])
def test_build_is_checked_per_recording(tmp_path: Path, recording: str) -> None:
    good = {"504695319": "180059", "511523321": "185872"}[recording]
    assert _plant(tmp_path, _GOOD.replace("180059", good), recording=recording) == []


_CUSTOM = "custom-games"

_CUSTOM_GOOD = """
[[reading]]
id = "C-1"
request = "O8.2"
civilisation = "Chinese"
preset = "Standard"
quantity = "starting resources"
value = "unreadable"
read_by = "owner"
read_on = "2026-11-20"
build_shown = "999999"
"""


def _custom_without(key: str) -> str:
    return "\n".join(line for line in _CUSTOM_GOOD.splitlines() if not line.startswith(f"{key} ="))


def _plant_custom(tmp_path: Path, body: str) -> list[str]:
    path = tmp_path / f"{_CUSTOM}.playback.toml"
    path.write_text(f'source = "{_CUSTOM}"\n{body}', encoding="utf-8")
    return _problems(path, _requests(), _builds())


def test_a_well_formed_custom_game_reading_passes_with_any_stated_build(tmp_path: Path) -> None:
    assert _plant_custom(tmp_path, _CUSTOM_GOOD) == []


def test_custom_game_reading_may_answer_o8_1(tmp_path: Path) -> None:
    assert _plant_custom(tmp_path, _CUSTOM_GOOD.replace("O8.2", "O8.1")) == []


@pytest.mark.parametrize("key", ["quantity", "value", "civilisation", "preset"])
def test_custom_game_file_refuses_a_missing_key(tmp_path: Path, key: str) -> None:
    assert _plant_custom(tmp_path, _custom_without(key))


@pytest.mark.parametrize("key", ["civilisation", "preset"])
def test_custom_game_file_refuses_a_blank_key(tmp_path: Path, key: str) -> None:
    body = _CUSTOM_GOOD.replace(f"{key} = ", f'{key} = "  "\n#', 1)
    assert _plant_custom(tmp_path, body)


def test_custom_game_file_refuses_a_missing_build(tmp_path: Path) -> None:
    assert _plant_custom(tmp_path, _custom_without("build_shown"))


def test_custom_game_file_refuses_an_unknown_request(tmp_path: Path) -> None:
    assert _plant_custom(tmp_path, _CUSTOM_GOOD.replace("O8.2", "O99"))


def test_custom_game_file_refuses_a_missing_reader(tmp_path: Path) -> None:
    assert _plant_custom(tmp_path, _custom_without("read_by"))


def test_custom_game_file_refuses_a_bad_date(tmp_path: Path) -> None:
    assert _plant_custom(tmp_path, _CUSTOM_GOOD.replace("2026-11-20", "20/11/2026"))


def test_a_recordings_file_still_refuses_a_build_the_readme_does_not_list(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD.replace("180059", "999999"), recording="500546441")


def test_the_committed_custom_game_file_is_present_and_not_an_orphan() -> None:
    path = _REPLAYS / f"{_CUSTOM}.playback.toml"
    assert path.is_file()
    assert tomllib.loads(path.read_text(encoding="utf-8")).get("source") == _CUSTOM
    assert _problems(path, _requests(), _builds()) == []
