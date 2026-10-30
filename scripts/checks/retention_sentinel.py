#!/usr/bin/env python3
"""Nightly sentinel on the source's replay retention window (T821, R1 in docs/risks.md).

The window moved from about 31 to about 26.75 days between two samples without notice
(`docs/data-sources.md` §2). The capture budget (`CAPTURE_BUDGET_DAYS`) is only safe while it sits
inside that window, and nothing else in the repository would see the window shrink: the
`contract_sources.py` probe draws its candidates from `getRecentMatchHistory`, which serves only a
recent window. This check reads the match history of a short named list of public probe profiles
from `data.aoe2companion.com` (at most 10 pages per profile, not counted against the replay
caps), falling back to that Relic feed when companion refuses, errors or answers a malformed
body (a note, never a failure: companion 403 from CI is expected noise) because Relic's history is
too shallow to reach the window of a very active profile. It keeps
the finished matches whose age lies in `[budget, budget + 15 days]`, and fetches each pair's replay
by age to locate the boundary where `aoe.ms` starts answering `404`. A walk from the young end
spends every request on `200`s first, so each profile's pairs are searched by bisection.

The estimator tolerates the two noise sources §2 records: a pair that survives far beyond the
window (a `200` that is too old) and a match that was never recorded (a `404` inside the window).
Search, per profile: fetch the youngest and the oldest in-range pairs (a youngest `404` or an oldest
`200` means no bracket, a note), bisect for adjacent pairs i (`200`) and i+1 (`404`), then confirm
with i+2 and i+3. A `200` among them means the `404` at i+1 was never recorded; the bisection
resumes once above that `200`. Fetched results are reused, never refetched. A profile that spends
its own cap yields a note and the next profile still gets its share.

Estimate, defined over the in-range pairs ordered youngest first: the boundary estimate is the age
of the youngest `404` that has a younger `200` and starts a run of three consecutive `404`s (itself
plus the next two older ones). A never-recorded `404` is followed by a `200` and so never starts
such a run; a survivor `200` sits past the boundary and so never moves it. A profile without such a
run yields no estimate and only a note.

The check fails when any estimate is shorter than `CAPTURE_BUDGET_DAYS` plus `MARGIN_DAYS`. An
outage of the source (connection error, non-200 from Relic, a replay status other than 200/404,
malformed body) is a note and never an estimate: an unreadable source must not read as a verdict.

A `200` costs a full download (`HEAD` and `Range` are unusable, §2), so at most
`MAX_REQUESTS_PER_PROFILE` replay requests are made per profile and `MAX_REQUESTS_PER_RUN` per run,
paced by
`AOEMS_MAX_REQUESTS_PER_SECOND`, with the honest identifying `User-Agent`
`contract_sources.py` uses. Bodies are never read or kept.

Configuration comes from the environment only: `CAPTURE_BUDGET_DAYS` and
`AOEMS_MAX_REQUESTS_PER_SECOND`. If either is unset the check prints a note and exits 0 rather than
guessing; a set but malformed value fails.

Usage:  uv run --with requests scripts/checks/retention_sentinel.py
Exit:   0 no estimate is under the margin (or the check could not run, noted), 1 otherwise.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NamedTuple, Protocol

USER_AGENT = "aoe2-stats/0.1 (+https://github.com/ScandalousMan/aoe2-stats)"
RELIC = "https://aoe-api.worldsedgelink.com/community/leaderboard"
REPLAY = "https://aoe.ms/replay/"
COMPANION = "https://data.aoe2companion.com/api"
TIMEOUT = 30

# Public probe profiles, 196240 first because it has the shortest window measured (2026-10-26,
# docs/data-sources.md §2); the window differs per profile.
PROBE_PROFILE_IDS = (196240, 9958277, 377935)

RANGE_WIDTH_DAYS = 15
MARGIN_DAYS = 3
MAX_REQUESTS_PER_PROFILE = 12
MAX_REQUESTS_PER_RUN = 30
MAX_COMPANION_PAGES = 10  # per profile; these do not count against the replay caps
COMPANION_PAGE_SIZE = 20
RUN_LENGTH = 3  # the boundary 404 plus the two older 404s that confirm it

_BUDGET_ENV = "CAPTURE_BUDGET_DAYS"
_RATE_ENV = "AOEMS_MAX_REQUESTS_PER_SECOND"
_SECONDS_PER_DAY = 86400


class SourceOutage(Exception):
    """The source could not be read; the caller turns this into a note, never an estimate."""


class Pair(NamedTuple):
    game_id: int
    profile_id: int
    age_days: float


class Source(Protocol):
    def companion_matches(self, profile_id: int, page: int) -> list[dict[str, Any]]: ...

    def recent_matches(self, profile_id: int) -> list[dict[str, Any]]: ...

    def replay_status(self, game_id: int, profile_id: int) -> int: ...


def companion_to_matches(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise companion entries to the Relic-shaped dicts `candidate_pairs` reads.

    `finished` is the match end; an entry with a null or unparseable `finished` is skipped.
    """
    out: list[dict[str, Any]] = []
    for entry in entries:
        finished = entry.get("finished")
        if not isinstance(finished, str) or "matchId" not in entry:
            continue
        try:
            done = datetime.fromisoformat(finished).timestamp()
        except ValueError:
            continue
        out.append({"id": entry["matchId"], "completiontime": done})
    return out


def read_candidates(
    source: Source,
    profile_id: int,
    now: float,
    budget_days: float,
    pace: Callable[[], None],
    notes: list[str],
) -> list[Pair]:
    """In-range pairs, youngest first: companion pages first, Relic when companion refuses."""
    limit = budget_days + RANGE_WIDTH_DAYS
    matches: list[dict[str, Any]] = []
    try:
        for page in range(1, MAX_COMPANION_PAGES + 1):
            pace()
            entries = source.companion_matches(profile_id, page)
            finished = companion_to_matches(entries)
            matches.extend(finished)
            oldest = min((m["completiontime"] for m in finished), default=None)
            if (
                len(entries) < COMPANION_PAGE_SIZE
                or oldest is None
                or (now - oldest) / _SECONDS_PER_DAY > limit
            ):
                break
    except SourceOutage as exc:
        notes.append(f"profile {profile_id}: companion unavailable ({exc}); fell back to Relic")
        pace()
        matches = source.recent_matches(profile_id)
    return candidate_pairs(profile_id, matches, now, budget_days)


@dataclass
class Report:
    estimates: dict[int, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def candidate_pairs(
    profile_id: int, matches: list[dict[str, Any]], now: float, budget_days: float
) -> list[Pair]:
    """Finished matches aged in `[budget, budget + RANGE_WIDTH_DAYS]`, youngest first."""
    pairs: list[Pair] = []
    for match in matches:
        done = match.get("completiontime")
        if not isinstance(done, int | float) or done <= 0:
            continue
        members = match.get("matchhistorymember")
        if isinstance(members, list) and not any(
            isinstance(m, dict) and m.get("profile_id") == profile_id for m in members
        ):
            continue
        age = (now - done) / _SECONDS_PER_DAY
        if budget_days <= age <= budget_days + RANGE_WIDTH_DAYS:
            pairs.append(Pair(int(match["id"]), profile_id, age))
    return sorted(pairs, key=lambda p: p.age_days)


class _CapReached(Exception):
    """This profile's own request cap is spent."""


class _Search:
    """Memoised replay statuses for one profile's pairs; each real request counts once."""

    def __init__(self, source: Source, pairs: list[Pair], budget: int, pace: Callable[[], None]):
        self._source = source
        self._pairs = pairs
        self._budget = budget
        self._pace = pace
        self.known: dict[int, int] = {}

    @property
    def spent(self) -> int:
        return len(self.known)

    def status(self, index: int) -> int:
        if index not in self.known:
            if self.spent >= self._budget:
                raise _CapReached
            self._pace()
            pair = self._pairs[index]
            self.known[index] = self._source.replay_status(pair.game_id, pair.profile_id)
        return self.known[index]

    def bisect(self, lo: int, hi: int) -> int:
        """From a known 200 at `lo` and 404 at `hi`, return `i` with 200 at i and 404 at i+1."""
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.status(mid) == 200:
                lo = mid
            else:
                hi = mid
        return lo


def find_boundary(search: _Search, count: int) -> tuple[int | None, str]:
    """Index of the boundary 404 (the youngest 404 with a younger 200 starting a run of three
    consecutive 404s), or `None` and the reason. Bisection is only how it is reached cheaply."""
    if search.status(0) == 404:
        return None, "the youngest in-range pair is already 404 (no bracket)"
    if search.status(count - 1) == 200:
        return None, "the oldest in-range pair is still 200 (no bracket)"
    lo, hi = 0, count - 1
    for attempt in range(2):
        i = search.bisect(lo, hi)
        if i + RUN_LENGTH - 1 >= count:
            return None, "too few older pairs to confirm the transition"
        # Reuses anything already fetched; checks the nearer pair first so a 200 short-circuits.
        for k in range(i + 2, i + RUN_LENGTH):
            if search.status(k) == 200:
                # The 404 at i+1 was never recorded: resume above the 200 just found.
                lo, hi = k, count - 1
                break
        else:
            return i + 1, ""
        if attempt == 1:
            break
    return None, "the transition was not confirmed by two older 404s"


def run_sentinel(
    source: Source,
    profile_ids: tuple[int, ...],
    budget_days: float,
    now: float,
    pace: Callable[[], None] = lambda: None,
) -> Report:
    report = Report()
    requests_made = 0
    for profile_id in profile_ids:
        try:
            pairs = read_candidates(source, profile_id, now, budget_days, pace, report.notes)
        except SourceOutage as exc:
            report.notes.append(f"profile {profile_id}: Relic unreadable ({exc}); no estimate")
            continue
        if not pairs:
            report.notes.append(
                f"profile {profile_id}: no finished match aged {budget_days:g} to "
                f"{budget_days + RANGE_WIDTH_DAYS:g} days; no estimate"
            )
            continue
        search = _Search(
            source, pairs, min(MAX_REQUESTS_PER_PROFILE, MAX_REQUESTS_PER_RUN - requests_made), pace
        )
        index: int | None
        try:
            index, why = find_boundary(search, len(pairs))
        except _CapReached:
            index, why = None, "its request cap was reached"
        except SourceOutage as exc:
            requests_made += search.spent
            report.notes.append(f"profile {profile_id}: aoe.ms unreadable ({exc}); stopping")
            break
        requests_made += search.spent
        if index is None:
            report.notes.append(
                f"profile {profile_id}: {search.spent} of {len(pairs)} pairs fetched, {why}; "
                "no estimate"
            )
            continue
        estimate = pairs[index].age_days
        report.estimates[profile_id] = estimate
        if estimate < budget_days + MARGIN_DAYS:
            report.failures.append(
                f"profile {profile_id}: retention estimate {estimate:.2f} days is under "
                f"CAPTURE_BUDGET_DAYS {budget_days:g} + {MARGIN_DAYS} margin"
            )
    return report


class RequestsSource:
    """The real source, over a `requests`-style session. Any `OSError` is an outage."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def companion_matches(self, profile_id: int, page: int) -> list[dict[str, Any]]:
        try:
            resp = self._session.get(
                f"{COMPANION}/matches",
                params={"profile_ids": profile_id, "page": page},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                raise SourceOutage(f"HTTP {resp.status_code}")
            body = resp.json()
        except (OSError, ValueError) as exc:
            raise SourceOutage(type(exc).__name__) from exc
        entries = body.get("matches") if isinstance(body, dict) else None
        if not isinstance(entries, list):
            raise SourceOutage("unexpected body shape")
        return [e for e in entries if isinstance(e, dict)]

    def recent_matches(self, profile_id: int) -> list[dict[str, Any]]:
        try:
            resp = self._session.get(
                f"{RELIC}/getRecentMatchHistory",
                params={"title": "age2", "profile_ids": json.dumps([profile_id])},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                raise SourceOutage(f"HTTP {resp.status_code}")
            body = resp.json()
        except (OSError, ValueError) as exc:
            raise SourceOutage(type(exc).__name__) from exc
        matches = body.get("matchHistoryStats") if isinstance(body, dict) else None
        if not isinstance(matches, list):
            raise SourceOutage("unexpected body shape")
        return [m for m in matches if isinstance(m, dict) and "id" in m]

    def replay_status(self, game_id: int, profile_id: int) -> int:
        try:
            # stream=True: the body of someone else's replay is never pulled.
            with self._session.get(
                REPLAY,
                params={"gameId": game_id, "profileId": profile_id},
                timeout=TIMEOUT,
                stream=True,
            ) as resp:
                status = int(resp.status_code)
        except OSError as exc:
            raise SourceOutage(type(exc).__name__) from exc
        if status not in (200, 404):
            raise SourceOutage(f"HTTP {status}")
        return status


def _positive(env: Mapping[str, str], name: str) -> float | None:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return None
    value = float(raw)  # a malformed value raises: misconfiguration must be loud
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {raw!r}")
    return value


def main(env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    budget = _positive(env, _BUDGET_ENV)
    rate = _positive(env, _RATE_ENV)
    if budget is None or rate is None:
        missing = [n for n, v in ((_BUDGET_ENV, budget), (_RATE_ENV, rate)) if v is None]
        print(f"NOTE retention sentinel not run: {', '.join(missing)} unset")
        return 0

    import requests  # imported here so the pure logic above needs no HTTP library

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    report = run_sentinel(
        RequestsSource(session),
        PROBE_PROFILE_IDS,
        budget,
        time.time(),
        pace=lambda: time.sleep(1.0 / rate),
    )
    for note in report.notes:
        print(f"NOTE {note}")
    for profile_id, estimate in report.estimates.items():
        print(f"ESTIMATE profile {profile_id}: {estimate:.2f} days (budget {budget:g})")
    if not report.estimates:
        print("NOTE no profile yielded a retention estimate tonight")
    for failure in report.failures:
        print(f"FAIL {failure}")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
