"""Playback readings are well-formed (contracts/playback-readings.md, assertion 4, T924).

Every ``tests/fixtures/replays/<recording>.playback.toml`` holds a ``recording`` header naming its
recording and one ``[[reading]]`` table per reading. Every reading names a request in the
owner-readings file, a build the fixtures README lists for that recording, a reader and a date.
The committed files hold no reading yet: this test passes over them vacuously until the owner
answers, and each malformation below is planted inline to show it is refused.
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

_REQUIRED = ("id", "request", "read_by", "read_on", "build_shown")


def _requests() -> set[str]:
    return set(re.findall(r"^## (O\d+) ", _OWNER_READINGS.read_text(encoding="utf-8"), re.M))


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
    recording = doc.get("recording")
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
        rid = reading.get("id")
        if isinstance(rid, str):
            if rid in seen:
                problems.append(f"{where}: duplicate id {rid!r}")
            seen.add(rid)
        request = reading.get("request")
        if isinstance(request, str) and request not in requests:
            problems.append(f"{where}: request {request!r} is not in the owner-readings file")
        build = reading.get("build_shown")
        if isinstance(build, str) and build not in builds.get(str(recording), set()):
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
    files = {p.name.split(".")[0] for p in _REPLAYS.glob("*.playback.toml")}
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


def test_refuses_a_missing_request(tmp_path: Path) -> None:
    assert _plant(tmp_path, _without("request"))


def test_refuses_a_build_not_listed_for_the_recording(tmp_path: Path) -> None:
    assert _plant(tmp_path, _GOOD.replace("180059", "185872"), recording="500546441")


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
