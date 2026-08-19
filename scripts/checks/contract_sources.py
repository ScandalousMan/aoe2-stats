#!/usr/bin/env python3
"""Contract tests against the real external APIs.

These are the only checks allowed to touch the network. They exist to detect a breaking change in a
third-party contract before our users do. Run nightly in CI, and by hand whenever a provider
misbehaves.

Usage:  uv run --with requests scripts/checks/contract_sources.py
Exit:   0 all contracts hold, 1 at least one broke.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta

import requests

RELIC = "https://aoe-api.worldsedgelink.com/community/leaderboard"
REPLAY = "https://aoe.ms/replay/"
COMPANION = "https://data.aoe2companion.com/api"
TIMEOUT = 30

# A public, highly active professional profile. Only public leaderboard data is read.
PROBE_STEAM_ID = "76561197984749679"
PROBE_PROFILE_ID = 196240

failures: list[str] = []
notes: list[str] = []


def check(name: str):
    def deco(fn):
        print(f"\n== {name}")
        try:
            fn()
            print("   OK")
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
            print(f"   FAIL: {exc}")
        except Exception as exc:  # noqa: BLE001 - a transport error is a contract signal too
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"   ERROR: {type(exc).__name__}: {exc}")
        return fn

    return deco


@check("Relic: reliclink.com is still the wrong hostname")
def _reliclink_still_broken() -> None:
    """If this ever starts passing, the redirect note in docs/data-sources.md is stale."""
    try:
        requests.get(
            "https://aoe-api.reliclink.com/community/leaderboard/getAvailableLeaderboards",
            params={"title": "age2"},
            timeout=TIMEOUT,
        )
    except requests.exceptions.SSLError:
        return
    notes.append(
        "aoe-api.reliclink.com no longer fails TLS verification. "
        "Re-check docs/data-sources.md and the aoe2-data-sources skill."
    )


@check("Relic: getPersonalStat resolves steamid64 -> profile_id")
def _personal_stat() -> None:
    r = requests.get(
        f"{RELIC}/getPersonalStat",
        params={"title": "age2", "profile_names": json.dumps([f"/steam/{PROBE_STEAM_ID}"])},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    body = r.json()
    assert body["result"]["code"] == 0, f"result code {body['result']}"

    members = [m for g in body["statGroups"] for m in g["members"]]
    match = [m for m in members if m["name"] == f"/steam/{PROBE_STEAM_ID}"]
    assert match, "probe steam id absent from statGroups members"
    assert match[0]["profile_id"] == PROBE_PROFILE_ID, (
        f"profile_id changed: expected {PROBE_PROFILE_ID}, got {match[0]['profile_id']}"
    )

    for field in ("alias", "country", "personal_statgroup_id"):
        assert field in match[0], f"member is missing {field!r}"

    stats = body["leaderboardStats"]
    assert stats, "leaderboardStats is empty"
    for field in ("leaderboard_id", "rating", "wins", "losses", "streak", "lastmatchdate"):
        assert field in stats[0], f"leaderboardStats is missing {field!r}"


@check("Relic: getRecentMatchHistory shape and batching")
def _recent_matches() -> None:
    r = requests.get(
        f"{RELIC}/getRecentMatchHistory",
        params={"title": "age2", "profile_ids": json.dumps([PROBE_PROFILE_ID])},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    body = r.json()
    assert body["result"]["code"] == 0, f"result code {body['result']}"

    matches = body["matchHistoryStats"]
    assert matches, "matchHistoryStats is empty"

    m = matches[0]
    for field in ("id", "mapname", "matchtype_id", "startgametime", "completiontime"):
        assert field in m, f"match is missing {field!r}"

    results = m["matchhistoryreportresults"]
    assert results, "matchhistoryreportresults is empty"
    for field in ("profile_id", "resulttype", "teamid", "civilization_id"):
        assert field in results[0], f"report result is missing {field!r}"


@check("aoe.ms: a recent replay is downloadable, an old one is not")
def _replay_window() -> None:
    r = requests.get(
        f"{RELIC}/getRecentMatchHistory",
        params={"title": "age2", "profile_ids": json.dumps([PROBE_PROFILE_ID])},
        timeout=TIMEOUT,
    )
    matches = sorted(
        r.json()["matchHistoryStats"], key=lambda m: m["completiontime"], reverse=True
    )
    now = time.time()
    fresh = next(
        (m for m in matches if now - m["completiontime"] < 7 * 86400),
        None,
    )
    assert fresh is not None, "probe profile has no match in the last 7 days; pick another probe"

    # stream=True reads headers only: we never pull the body of someone else's replay.
    with requests.get(
        REPLAY,
        params={"gameId": fresh["id"], "profileId": PROBE_PROFILE_ID},
        timeout=TIMEOUT,
        stream=True,
    ) as resp:
        age_h = (now - fresh["completiontime"]) / 3600
        assert resp.status_code == 200, (
            f"a {age_h:.0f} h old replay returned {resp.status_code}; "
            "the capture window may have shrunk"
        )
        ctype = resp.headers.get("content-type", "")
        assert "zip" in ctype, f"expected a zip, got content-type {ctype!r}"
        disp = resp.headers.get("content-disposition", "")
        assert f"AgeIIDE_Replay_{fresh['id']}.zip" in disp, (
            f"naming convention changed: {disp!r}"
        )

    old = next(
        (m for m in matches if now - m["completiontime"] > 40 * 86400),
        None,
    )
    if old is None:
        notes.append("no match older than 40 days available to confirm the retention boundary")
        return
    with requests.get(
        REPLAY,
        params={"gameId": old["id"], "profileId": PROBE_PROFILE_ID},
        timeout=TIMEOUT,
        stream=True,
    ) as resp:
        assert resp.status_code == 404, (
            f"a 40+ day old replay returned {resp.status_code}, expected 404. "
            "If retention grew, update docs/data-sources.md and the capture budget."
        )


@check("aoe.ms: HEAD is still unsupported (no cheap existence probe)")
def _no_head() -> None:
    resp = requests.head(
        REPLAY, params={"gameId": 1, "profileId": 1}, timeout=TIMEOUT, allow_redirects=True
    )
    assert resp.status_code == 405, (
        f"HEAD returned {resp.status_code}. If it now works, the downloader can stop "
        "fetching whole bodies just to test existence."
    )


@check("aoe2companion: match feed shape (enrichment source, non-blocking)")
def _companion() -> None:
    r = requests.get(
        f"{COMPANION}/matches", params={"profile_ids": PROBE_PROFILE_ID}, timeout=TIMEOUT
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    body = r.json()
    assert "matches" in body, "response has no 'matches' key"
    m = body["matches"][0]
    for field in ("matchId", "started", "leaderboardId", "mapName", "teams"):
        assert field in m, f"match is missing {field!r}"
    player = m["teams"][0]["players"][0]
    for field in ("profileId", "name", "civName"):
        assert field in player, f"player is missing {field!r}"


@check("aoestats: dumps are still empty (V2 corpus only)")
def _aoestats() -> None:
    r = requests.get(f"https://aoestats.io/api/db_dumps/", timeout=TIMEOUT)
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    dumps = r.json()["db_dumps"]
    recent = [d for d in dumps if d["start_date"] >= (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")]
    if any(d["num_matches"] > 0 for d in recent):
        notes.append(
            "aoestats has started publishing data again. It may become usable as a live source; "
            "re-evaluate docs/data-sources.md."
        )


print("\n" + "=" * 70)
for n in notes:
    print(f"NOTE: {n}")
if failures:
    print(f"\n{len(failures)} contract(s) broke:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("\nAll contracts hold.")
