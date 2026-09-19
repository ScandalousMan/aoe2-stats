"""The committed reference recordings (T603, FR-045): bytes anyone can re-measure.

Parameterised over every `*.zip` under `tests/fixtures/replays/` — never over named files — so a
third recording is covered the moment it is committed. For each archive: the checksum recorded in
the fixtures README matches (an archive with no recorded checksum fails, it is not skipped), the
archive holds exactly one `.aoe2record`, and the `PostGame` operation parsed by the pinned engine
carries no statistics block.

How a "statistics block" is identified: the wheel returns each `PostGame` block as a dict with one
key, the wheel's own name for the block kind. The two kinds observed in every recording are
`Leaderboards` (per-player rank and elo) and `WorldTime`. The wheel offers no dedicated name that
was observed for a statistics block, so the absence claim is asserted two ways: the set of observed
kinds is exactly that set, and no kind name suggests statistics, achievements or scores.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest
from aoe2rec_py import aoe2rec_py as _native

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "replays"
README = FIXTURES / "README.md"
ARCHIVES = sorted(FIXTURES.glob("*.zip"))

OBSERVED_BLOCK_KINDS = {"Leaderboards", "WorldTime"}
STATISTICS_HINTS = ("stat", "achievement", "score", "summary", "military", "economy")


def _recorded_checksum(archive_name: str) -> str | None:
    """The `SHA-256:` line under the README heading for `archive_name`, or None."""
    sections = re.split(r"^## ", README.read_text(encoding="utf-8"), flags=re.MULTILINE)
    for section in sections:
        if section.startswith(f"`{archive_name}`"):
            match = re.search(r"^SHA-256: `([0-9a-f]{64})`\s*$", section, flags=re.MULTILINE)
            return match.group(1) if match else None
    return None


def _post_game_operations(archive: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(archive) as zf:
        inner = zf.read(zf.namelist()[0])
    parsed = _native.parse_rec(inner)
    return [op["PostGame"] for op in parsed["operations"] if "PostGame" in op]


@pytest.fixture(scope="module")
def post_game_by_archive() -> dict[str, list[dict[str, Any]]]:
    """Each archive is parsed once per session, however many assertions read it."""
    return {archive.name: _post_game_operations(archive) for archive in ARCHIVES}


def test_the_fixture_directory_still_holds_the_known_recordings() -> None:
    assert len(ARCHIVES) >= 2, f"expected at least two reference recordings under {FIXTURES}"


@pytest.mark.parametrize("archive", ARCHIVES, ids=lambda path: path.name)
def test_the_archive_matches_its_recorded_checksum(archive: Path) -> None:
    recorded = _recorded_checksum(archive.name)

    assert recorded is not None, f"{archive.name} has no recorded SHA-256 in {README.name}"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == recorded


@pytest.mark.parametrize("archive", ARCHIVES, ids=lambda path: path.name)
def test_the_archive_holds_exactly_one_recording(archive: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(archive.read_bytes())) as zf:
        names = zf.namelist()

    assert len(names) == 1
    assert names[0].endswith(".aoe2record")


@pytest.mark.parametrize("archive", ARCHIVES, ids=lambda path: path.name)
def test_the_post_game_block_list_carries_no_statistics_block(
    archive: Path, post_game_by_archive: dict[str, list[dict[str, Any]]]
) -> None:
    post_games = post_game_by_archive[archive.name]

    # Not vacuous: a PostGame operation exists and its block list is populated.
    assert len(post_games) == 1
    blocks = post_games[0]["blocks"]
    assert blocks, "PostGame block list is empty"

    kinds = {kind for block in blocks for kind in block}
    assert kinds == OBSERVED_BLOCK_KINDS
    suspicious = {k for k in kinds if any(hint in k.lower() for hint in STATISTICS_HINTS)}
    assert not suspicious, f"statistics-like PostGame blocks: {sorted(suspicious)}"
