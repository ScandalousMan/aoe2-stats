#!/usr/bin/env python3
"""Contract tests against the real external APIs.

These are the only checks allowed to touch the network. They exist to detect a breaking change in a
third-party contract before our users do. Run nightly in CI, and by hand whenever a provider
misbehaves.

Every check that parses a body writes what it received into `packages/providers/fixtures/` as it
goes (see `write_json_fixture` / `write_text_fixture` below) — T012's "capture frozen real
responses" and this script's checks are the same act on purpose, run either nightly or by hand.
Provider unit tests read those files and never touch the network (`providers.md`); this script is
the only thing that can keep them true. "Can", not "does automatically": the nightly job runs with
`permissions: contents: read` and makes no commit (T012b), so a nightly run's writes here verify
that today's response still has the shape the committed fixture expects, but only refresh what unit
tests actually read when a human runs this script locally and commits the diff — see
`packages/providers/fixtures/README.md`. The one exception, spelled out below, is the
publication-delay corpus (T012a, T012b), which does accumulate on its own across nightly runs, via
a GitHub Actions artifact rather than a commit.

Usage:  uv run --with requests scripts/checks/contract_sources.py [--capture-fixtures]
Exit:   0 all contracts hold, 1 at least one broke.

`--capture-fixtures` additionally downloads one full replay body to verify it — a real zip, its
inner filename, its inner byte count — and then discards it. Every other check already fetches the
body it verifies, so recording it costs nothing extra; the replay endpoint is the one source where
"verify" and "fetch a few megabytes just to prove the endpoint still works" are different amounts
of work, so that one download stays opt-in and out of the nightly run (see `_replay_capture`
below). Only the metadata the verification produces is written to
`aoems/replay_200_meta.json` — the body itself is never committed (constitution IX: a third
party's match data has no purpose recorded for it once the shape is already proven).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from collections.abc import Callable, Collection
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from contract_shapes import assert_companion_search_shape
from publication_delay import append_sample

# An honest, identifying User-Agent. Several of these sources sit behind bot protection, and we
# would rather be recognisable than anonymous if anyone ever wants to ask us to slow down.
USER_AGENT = "aoe2-stats/0.1 (+https://github.com/ScandalousMan/aoe2-stats)"

RELIC = "https://aoe-api.worldsedgelink.com/community/leaderboard"
REPLAY = "https://aoe.ms/replay/"
COMPANION = "https://data.aoe2companion.com/api"
STEAM_OPENID = "https://steamcommunity.com/openid/login"
TIMEOUT = 30

# A public, highly active professional profile. Only public leaderboard data is read.
PROBE_STEAM_ID = "76561197984749679"
PROBE_PROFILE_ID = 196240
# A second real, active profile, only ever used alongside the first to exercise batching —
# neither Relic endpoint accepts a single profile and calls it a contract.
PROBE_PROFILE_ID_2 = 199325  # "VIT | Hera", pulled live from getLeaderBoard2 on 2026-08-19.
# An arbitrary, syntactically valid steamid64 confirmed on 2026-08-19 to hold no AoE2 profile —
# real, reproducible negative case for `ProfileProvider.resolve_profile` (FR-003).
PROBE_STEAM_ID_NO_PROFILE = "76561197960287930"

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "packages" / "providers" / "fixtures"

# T012a / T012b: the local working copy of the publication-delay corpus. In CI this path is what
# the "Restore the publication-delay corpus" step in `.github/workflows/nightly.yml` populates from
# the previous nightly's `publication-delay-corpus` artifact before this script runs, and what the
# following "Re-upload" step reads back afterwards — this script itself only ever appends to it, the
# same way it would for a developer running it locally. It is git-ignored: the corpus's home is the
# artifact chain, not the repository (see docs/data-sources.md §2).
_REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLICATION_DELAY_SAMPLES = _REPO_ROOT / "docs" / "data-sources" / "publication_delay_samples.jsonl"

_args = argparse.ArgumentParser(add_help=True)
_args.add_argument("--capture-fixtures", action="store_true")
CAPTURE_FIXTURES = _args.parse_args().capture_fixtures

failures: list[str] = []
notes: list[str] = []

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def write_json_fixture(relative_path: str, payload: Any) -> None:
    """Freeze a parsed JSON body into `packages/providers/fixtures/`, sorted and indented so a
    schema change shows up as a small, readable diff rather than a one-line churn.
    """
    path = FIXTURES_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text_fixture(relative_path: str, payload: str) -> None:
    """Freeze a non-JSON body (Steam's `check_authentication` reply, aoe.ms's 404 plain text)."""
    path = FIXTURES_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def check(
    name: str, *, blocking: bool = True
) -> Callable[[Callable[[], None]], Callable[[], None]]:
    """Run one contract check.

    `blocking=False` marks a source we have already declared degradable: a break is reported but
    does not fail the job. A watchtower that goes red every night for a source the application is
    designed to survive without is a watchtower people stop reading, and then it misses the one
    that matters.
    """

    def deco(fn: Callable[[], None]) -> Callable[[], None]:
        print(f"\n== {name}{'' if blocking else '  (non-blocking)'}")
        # One retry: these endpoints throttle intermittently, and a single 403 is not a contract
        # change. Two in a row is worth reporting.
        for attempt in (1, 2):
            try:
                fn()
                print("   OK" if attempt == 1 else "   OK (second attempt)")
                return fn
            except (AssertionError, Exception) as exc:
                if attempt == 1:
                    time.sleep(5)
                    continue
                label = (
                    f"{exc}" if isinstance(exc, AssertionError) else f"{type(exc).__name__}: {exc}"
                )
                if blocking:
                    failures.append(f"{name}: {label}")
                    print(f"   FAIL: {label}")
                else:
                    notes.append(f"{name}: {label}")
                    print(f"   WARN (not blocking): {label}")
        return fn

    return deco


def _trim_match_history(
    body: dict[str, Any], *, keep: int, must_include_profile_ids: Collection[int] = frozenset()
) -> dict[str, Any]:
    """Cap a `getRecentMatchHistory` body to `keep` matches (most recent first) so the fixture
    committed to the repository stays a reasonable size. Every kept match is byte-for-byte the
    real entry Relic returned — this only reduces *how many* of them are kept, never what is in
    one. `must_include_profile_ids` pulls in the nearest match for a profile the caller needs
    represented (a batching fixture is worthless if trimming drops the second profile entirely).
    `profiles` is filtered down to the ids the kept matches still reference.
    """
    matches = sorted(body["matchHistoryStats"], key=lambda m: m["completiontime"], reverse=True)
    kept = list(matches[:keep])
    kept_ids = {m["id"] for m in kept}
    for profile_id in must_include_profile_ids:
        if any(profile_id == r["profile_id"] for m in kept for r in m["matchhistoryreportresults"]):
            continue
        extra = next(
            (
                m
                for m in matches
                if m["id"] not in kept_ids
                and any(r["profile_id"] == profile_id for r in m["matchhistoryreportresults"])
            ),
            None,
        )
        if extra is not None:
            kept.append(extra)
            kept_ids.add(extra["id"])
    referenced_ids = {r["profile_id"] for m in kept for r in m["matchhistoryreportresults"]}
    trimmed = dict(body)
    trimmed["matchHistoryStats"] = kept
    trimmed["profiles"] = [p for p in body.get("profiles", []) if p["profile_id"] in referenced_ids]
    return trimmed


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
    r = session.get(
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

    # ProfileProvider.resolve_profile's success case: a steamid64 that resolves to a profile.
    write_json_fixture("relic/get_personal_stat.json", body)


@check("Relic: getPersonalStat on a Steam id with no AoE2 profile")
def _personal_stat_unregistered() -> None:
    r = session.get(
        f"{RELIC}/getPersonalStat",
        params={
            "title": "age2",
            "profile_names": json.dumps([f"/steam/{PROBE_STEAM_ID_NO_PROFILE}"]),
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    body = r.json()
    assert body["result"]["code"] != 0, (
        f"expected a non-zero result code for an unregistered profile, got {body['result']}"
    )
    assert not body.get("statGroups"), "expected no statGroups for an unregistered profile"

    # ProfileProvider.resolve_profile returning None (FR-003): an ordinary outcome, not an error.
    write_json_fixture("relic/get_personal_stat_unregistered.json", body)


@check("Relic: getPersonalStat batches more than one profile per call")
def _personal_stat_batch() -> None:
    r = session.get(
        f"{RELIC}/getPersonalStat",
        params={
            "title": "age2",
            "profile_ids": json.dumps([PROBE_PROFILE_ID, PROBE_PROFILE_ID_2]),
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    body = r.json()
    assert body["result"]["code"] == 0, f"result code {body['result']}"

    seen_ids = {m["profile_id"] for g in body["statGroups"] for m in g["members"]}
    assert {PROBE_PROFILE_ID, PROBE_PROFILE_ID_2} <= seen_ids, (
        f"batched call dropped a profile: expected both of "
        f"{{{PROBE_PROFILE_ID}, {PROBE_PROFILE_ID_2}}}, got {seen_ids}"
    )

    # ProfileProvider.personal_stats: batching (providers.md — up to 50 profiles per call).
    write_json_fixture("relic/get_personal_stat_batch.json", body)


@check("Relic: getRecentMatchHistory shape and batching")
def _recent_matches() -> None:
    r = session.get(
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

    # MatchHistoryProvider.recent_matches, single profile. Capped to 8 matches (real, untouched
    # entries — see `_trim_match_history`) so a ~400 KB live response does not become a ~400 KB
    # fixture committed to the repository for no gain in shape coverage.
    write_json_fixture("relic/get_recent_match_history.json", _trim_match_history(body, keep=8))


@check("Relic: getRecentMatchHistory batches more than one profile per call")
def _recent_matches_batch() -> None:
    r = session.get(
        f"{RELIC}/getRecentMatchHistory",
        params={
            "title": "age2",
            "profile_ids": json.dumps([PROBE_PROFILE_ID, PROBE_PROFILE_ID_2]),
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    body = r.json()
    assert body["result"]["code"] == 0, f"result code {body['result']}"

    matches = body["matchHistoryStats"]
    assert matches, "matchHistoryStats is empty"
    reported_profile_ids = {
        r["profile_id"] for m in matches for r in m["matchhistoryreportresults"]
    }
    assert {PROBE_PROFILE_ID, PROBE_PROFILE_ID_2} <= reported_profile_ids, (
        "batched call dropped one of the requested profiles from every returned match"
    )

    # MatchHistoryProvider.recent_matches: batching (providers.md — up to 10 profiles per call).
    write_json_fixture(
        "relic/get_recent_match_history_batch.json",
        _trim_match_history(
            body, keep=6, must_include_profile_ids={PROBE_PROFILE_ID, PROBE_PROFILE_ID_2}
        ),
    )


@check("aoe.ms: a recent replay is downloadable, an old one is not")
def _replay_window() -> None:
    r = session.get(
        f"{RELIC}/getRecentMatchHistory",
        params={"title": "age2", "profile_ids": json.dumps([PROBE_PROFILE_ID])},
        timeout=TIMEOUT,
    )
    matches = sorted(r.json()["matchHistoryStats"], key=lambda m: m["completiontime"], reverse=True)
    now = time.time()
    fresh = next(
        (m for m in matches if now - m["completiontime"] < 7 * 86400),
        None,
    )
    assert fresh is not None, "probe profile has no match in the last 7 days; pick another probe"

    # stream=True reads headers only: we never pull the body of someone else's replay.
    with session.get(
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
        assert f"AgeIIDE_Replay_{fresh['id']}.zip" in disp, f"naming convention changed: {disp!r}"

    old = next(
        (m for m in matches if now - m["completiontime"] > 40 * 86400),
        None,
    )
    if old is None:
        notes.append("no match older than 40 days available to confirm the retention boundary")
        return
    with session.get(
        REPLAY,
        params={"gameId": old["id"], "profileId": PROBE_PROFILE_ID},
        timeout=TIMEOUT,
        stream=True,
    ) as resp:
        assert resp.status_code == 404, (
            f"a 40+ day old replay returned {resp.status_code}, expected 404. "
            "If retention grew, update docs/data-sources.md and the capture budget."
        )
        # 16-ish bytes of plain text — reading this body costs nothing extra, unlike the 200 case.
        # ReplayProvider.fetch_replay's NotFound case; the caller's three-way reading of *why* is
        # owned by capture.py (T056), never by this provider (providers.md).
        write_json_fixture(
            "aoems/replay_404.json",
            {
                "game_id": old["id"],
                "profile_id": PROBE_PROFILE_ID,
                "http_status": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "body": resp.text,
            },
        )


@check("aoe.ms: publication-delay sample (distribution, non-blocking)", blocking=False)
def _publication_delay_sample() -> None:
    """One sample per run, never a poll for `200` (module docstring, T012a): the age of the probe
    profile's most recently completed match, and whether `aoe.ms` already answers `200` for it yet.
    The single observation docs/data-sources.md used to carry — 33 min, n=1 — becomes a
    distribution one point at a time; see "Publication delay: distribution" there.

    Non-blocking on purpose: a late publication is a measurement, not a broken contract —
    `_replay_window` above is what asserts the contract still holds for the case that matters
    operationally (a match within the last week). `append_sample` (`publication_delay.py`) is what
    turns this into something durable: it appends the sample to `PUBLICATION_DELAY_SAMPLES`, the
    local copy of the corpus this run restored from the `publication-delay-corpus` GitHub Actions
    artifact — see the "Restore" / "Re-upload" steps around the `contracts` job in
    `.github/workflows/nightly.yml`. T012b: this no longer touches `docs/data-sources.md`. That
    file's conclusion is written by a human who has pulled the corpus and read it, not regenerated
    by this script on every run — see `record_sample` in `publication_delay.py` for the tool that
    does that, by hand.
    """
    r = session.get(
        f"{RELIC}/getRecentMatchHistory",
        params={"title": "age2", "profile_ids": json.dumps([PROBE_PROFILE_ID])},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    matches = r.json()["matchHistoryStats"]
    assert matches, "probe profile has no matches to sample from"
    latest = max(matches, key=lambda m: m["completiontime"])
    now = time.time()
    age_hours = (now - latest["completiontime"]) / 3600

    # stream=True: read the status only, never the body. Whether the body is a real zip is
    # `_replay_window`'s and `_replay_capture`'s job; this check only ever needs the same boolean
    # the caller in capture.py (T056) reads a 404 for.
    with session.get(
        REPLAY,
        params={"gameId": latest["id"], "profileId": PROBE_PROFILE_ID},
        timeout=TIMEOUT,
        stream=True,
    ) as resp:
        assert resp.status_code in (200, 404), (
            f"unexpected status sampling publication delay: {resp.status_code}"
        )
        available = resp.status_code == 200

    append_sample(
        PUBLICATION_DELAY_SAMPLES,
        observed_at_iso=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        game_id=latest["id"],
        age_hours=age_hours,
        available=available,
    )


if CAPTURE_FIXTURES:

    @check("aoe.ms: a downloaded replay is a real zip with the expected inner file")
    def _replay_capture() -> None:
        """The one check that costs real bandwidth beyond verifying a contract, so it runs only
        under `--capture-fixtures` (module docstring) — never in the nightly job. The body is
        verified in memory and never written to disk: `ReplayProvider.fetch_replay`'s success case
        (T039) needs the response *shape* — status, headers, inner filename, inner byte count —
        and `replay_200_meta.json` carries every one of those without the body it was measured
        from. A body-level fixture already exists for what actually reads one:
        `tests/fixtures/replays/AgeIIDE_Replay_500546441.zip` (the parser engine, T079).
        """
        r = session.get(
            f"{RELIC}/getRecentMatchHistory",
            params={"title": "age2", "profile_ids": json.dumps([PROBE_PROFILE_ID])},
            timeout=TIMEOUT,
        )
        matches = sorted(
            r.json()["matchHistoryStats"], key=lambda m: m["completiontime"], reverse=True
        )
        now = time.time()
        fresh = next((m for m in matches if now - m["completiontime"] < 7 * 86400), None)
        assert fresh is not None, (
            "probe profile has no match in the last 7 days; pick another probe"
        )

        resp = session.get(
            REPLAY,
            params={"gameId": fresh["id"], "profileId": PROBE_PROFILE_ID},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
        assert len(resp.content) == int(resp.headers.get("content-length", -1)), (
            "downloaded body length does not match Content-Length"
        )

        # A real zip, holding exactly one member — the .aoe2record — never written to disk.
        archive = zipfile.ZipFile(io.BytesIO(resp.content))
        assert zipfile.is_zipfile(io.BytesIO(resp.content)), "response body is not a valid zip"
        members = archive.namelist()
        assert len(members) == 1, f"expected exactly one member, got {members}"
        inner_name = members[0]
        assert inner_name == f"AgeIIDE_Replay_{fresh['id']}.aoe2record", (
            f"unexpected inner filename: {inner_name!r}"
        )
        inner_size = archive.getinfo(inner_name).file_size

        # ReplayProvider.fetch_replay's success case (T039): every field `ReplayBlob` and its
        # caller need, without the megabytes the assertions above already consumed and verified.
        write_json_fixture(
            "aoems/replay_200_meta.json",
            {
                "game_id": fresh["id"],
                "profile_id": PROBE_PROFILE_ID,
                "http_status": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "content_disposition": resp.headers.get("content-disposition", ""),
                "content_length": len(resp.content),
                "inner_filename": inner_name,
                "inner_byte_count": inner_size,
            },
        )


@check("aoe.ms: HEAD is still unsupported (no cheap existence probe)")
def _no_head() -> None:
    resp = session.head(
        REPLAY, params={"gameId": 1, "profileId": 1}, timeout=TIMEOUT, allow_redirects=True
    )
    assert resp.status_code == 405, (
        f"HEAD returned {resp.status_code}. If it now works, the downloader can stop "
        "fetching whole bodies just to test existence."
    )


@check("aoe2companion: match feed shape (enrichment source)", blocking=False)
def _companion() -> None:
    r = session.get(
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

    # EnrichmentProvider.enrich_matches (T041). Trimmed to the first 3 matches — every one kept is
    # untouched real data, just fewer of them, per the same reasoning as `_trim_match_history`.
    # A 403 here needs no fixture of its own: nothing about its *shape* is asserted (providers.md
    # — the circuit breaker cares only about the status code), so `httpx.MockTransport` covers it.
    trimmed = dict(body)
    trimmed["matches"] = body["matches"][:3]
    write_json_fixture("companion/matches.json", trimmed)


@check("aoe2companion: profile search shape (?search=vipe)")
def _companion_search() -> None:
    """`GET /api/profiles?search=` (`docs/data-sources.md` §3, "Profile search behaviour") — the
    source `PlayerSearchProvider.search_players` (`companion/provider.py`, T313) calls. That
    provider already degrades honestly on a drifted `200` — BL-1 for the envelope, BL-5 for the
    record, both in `_parse_search_page` — but a degrade nobody watches is a degrade that tells
    nobody (T377): every search would answer `degraded: false, results: []` forever, reading
    exactly like a genuine "no such player". This check is what watches it.

    A non-200 is recorded as a note, never a failure: `docs/data-sources.md` §3's "Observed
    2026-08-19: intermittent 403" measured this exact host answering bot-protection noise from
    CI runners with no relationship to the response shape, and `_companion` above already extends
    that same leniency to the match feed on the same host. A genuine `200` whose shape has
    drifted is a different claim entirely, and is what actually fails the nightly job here —
    unlike `_companion`, this check is blocking.
    """
    r = session.get(f"{COMPANION}/profiles", params={"search": "vipe"}, timeout=TIMEOUT)
    if r.status_code != 200:
        notes.append(
            f"aoe2companion search: got {r.status_code} instead of 200 (bot-protection noise, "
            "not a shape check — docs/data-sources.md §3)"
        )
        return
    body = r.json()
    assert_companion_search_shape(body)
    profiles = body["profiles"]
    assert profiles, "search=vipe returned zero profiles; pick another probe query known to match"

    # PlayerSearchProvider.search_players (T313). `fixtures/README.md`: "one full page (20 real
    # records), uncapped" for `?search=vipe` — unlike `_companion`'s `matches.json` above, this
    # fixture is deliberately not trimmed.
    write_json_fixture("companion_profiles_search.json", body)


@check("Steam: check_authentication rejects a forged assertion")
def _steam_check_authentication_invalid() -> None:
    """The one call `SteamAuthProvider.verify` makes that this script can freeze on its own: a
    syntactically well-formed but never-issued assertion, which Steam must reject the same way a
    replayed or tampered one is rejected (FR-001, FR-002 — quickstart scenario 1). A genuine
    `is_valid:true` response cannot be captured by an unattended script: an assertion is single-use
    and tied to a completed, interactive Steam login (research.md §2), which is why
    `check_authentication_valid.txt` beside this fixture is hand-written from the OpenID 2.0 wire
    format instead of frozen from a live call — see `fixtures/steam/README.md`.
    """
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "check_authentication",
        "openid.op_endpoint": STEAM_OPENID,
        "openid.claimed_id": "https://steamcommunity.com/openid/id/76561197984749679",
        "openid.identity": "https://steamcommunity.com/openid/id/76561197984749679",
        "openid.return_to": "https://example.invalid/api/auth/steam/callback",
        "openid.response_nonce": "2026-08-19T21:00:00Zcontract-source-probe",
        "openid.assoc_handle": "never-issued",
        "openid.signed": (
            "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"
        ),
        "openid.sig": "not-a-real-signature",
    }
    r = session.post(STEAM_OPENID, data=params, timeout=TIMEOUT)
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    assert "is_valid:false" in r.text, f"expected a rejection, got: {r.text!r}"

    write_text_fixture("steam/check_authentication_invalid.txt", r.text)


@check("aoestats: dumps are still empty (V2 corpus only)", blocking=False)
def _aoestats() -> None:
    r = session.get("https://aoestats.io/api/db_dumps/", timeout=TIMEOUT)
    assert r.status_code == 200, f"expected 200, got {r.status_code}"
    dumps = r.json()["db_dumps"]
    recent = [
        d
        for d in dumps
        if d["start_date"] >= (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
    ]
    if any(d["num_matches"] > 0 for d in recent):
        notes.append(
            "aoestats has started publishing data again. It may become usable as a live source; "
            "re-evaluate docs/data-sources.md."
        )


print("\n" + "=" * 70)
if CAPTURE_FIXTURES:
    print(f"Fixtures written to {FIXTURES_DIR}")
for n in notes:
    print(f"NOTE: {n}")
if failures:
    print(f"\n{len(failures)} contract(s) broke:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("\nAll contracts hold.")
