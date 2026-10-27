"""Tests for the retention sentinel (T821). Synthetic ids and bodies; no network anywhere."""

from datetime import UTC, datetime
from typing import Any

import pytest
from scripts.checks.retention_sentinel import (
    MAX_COMPANION_PAGES,
    MAX_REQUESTS_PER_PROFILE,
    MAX_REQUESTS_PER_RUN,
    RequestsSource,
    SourceOutage,
    companion_to_matches,
    main,
    run_sentinel,
)

DAY = 86400
NOW = 1_000_000_000.0
BUDGET = 18.0
PROBES = (1, 2, 3)


def match(game_id: int, age_days: float, profile_id: int) -> dict[str, Any]:
    return {
        "id": game_id,
        "completiontime": NOW - age_days * DAY,
        "matchhistorymember": [{"profile_id": profile_id}, {"profile_id": 999}],
    }


class FakeSource:
    def __init__(
        self,
        ages: dict[int, list[float]],
        statuses: dict[int, int],
        *,
        relic_down: set[int] | None = None,
        replay_down: bool = False,
        companion_down: bool = False,
    ) -> None:
        self.companion_down = companion_down
        self.companion_pages: list[int] = []
        self.ages = ages
        self.statuses = statuses  # game id -> status
        self.relic_down = relic_down or set()
        self.replay_down = replay_down
        self.replay_calls: list[tuple[int, int]] = []

    def companion_matches(self, profile_id: int, page: int) -> list[dict[str, Any]]:
        self.companion_pages.append(page)
        if self.companion_down:
            raise SourceOutage("HTTP 403")
        entries = [
            {
                "matchId": profile_id * 1000 + i,
                "finished": datetime.fromtimestamp(NOW - age * DAY, UTC).isoformat(),
            }
            for i, age in enumerate(self.ages.get(profile_id, []))
        ]
        return entries[(page - 1) * 20 : page * 20]

    def recent_matches(self, profile_id: int) -> list[dict[str, Any]]:
        if profile_id in self.relic_down:
            raise SourceOutage("HTTP 503")
        return [
            match(profile_id * 1000 + i, age, profile_id)
            for i, age in enumerate(self.ages.get(profile_id, []))
        ]

    def replay_status(self, game_id: int, profile_id: int) -> int:
        self.replay_calls.append((game_id, profile_id))
        if self.replay_down:
            raise SourceOutage("ConnectionError")
        return self.statuses[game_id]


def statuses_for(profile_id: int, codes: list[int]) -> dict[int, int]:
    return {profile_id * 1000 + i: c for i, c in enumerate(codes)}


def run_one(ages: list[float], codes: list[int]) -> tuple[FakeSource, Any]:
    src = FakeSource({1: ages}, statuses_for(1, codes))
    return src, run_sentinel(src, (1,), BUDGET, NOW)


def test_clean_boundary_is_the_first_404_of_the_run() -> None:
    src, report = run_one([19, 20, 21, 22, 23, 24], [200, 200, 200, 404, 404, 404])
    assert report.estimates == {1: pytest.approx(22)}
    assert report.failures == []
    assert len(src.replay_calls) == len(set(src.replay_calls))  # nothing refetched


def test_survivor_beyond_the_boundary_does_not_move_it() -> None:
    ages = [19, 20, 22, 23, 24, 30, 31, 32]
    codes = [200, 200, 404, 404, 404, 200, 404, 404]
    _, report = run_one(ages, codes)
    assert report.estimates == {1: pytest.approx(22)}


def test_oldest_pair_still_200_is_a_note_not_an_estimate() -> None:
    src, report = run_one([19, 22, 23, 30], [200, 404, 404, 200])
    assert report.estimates == {} and report.failures == []
    assert "oldest" in report.notes[0]
    assert len(src.replay_calls) == 2


def test_youngest_pair_already_404_is_a_note_not_an_estimate() -> None:
    src, report = run_one([19, 22, 23, 30], [404, 404, 404, 404])
    assert report.estimates == {} and report.failures == []
    assert "youngest" in report.notes[0]
    assert len(src.replay_calls) == 1


def test_bisection_lands_on_a_never_recorded_404_and_confirmation_rejects_it() -> None:
    ages = [19, 20, 21, 22, 23, 24, 25, 26]
    codes = [200, 200, 200, 404, 200, 404, 404, 404]  # index 3 was never recorded
    src, report = run_one(ages, codes)
    assert (1003, 1) in src.replay_calls  # the search did probe the never-recorded pair
    assert report.estimates == {1: pytest.approx(24)}  # index 5, not index 3 (age 22)
    assert len(src.replay_calls) <= MAX_REQUESTS_PER_PROFILE


def test_never_recorded_404_with_no_older_run_is_a_note() -> None:
    _, report = run_one([19, 20, 21, 22], [200, 404, 200, 404])
    assert report.estimates == {} and report.failures == []


def test_seventeen_pairs_reach_an_estimate_within_the_profile_cap() -> None:
    ages = [18 + 0.9 * i for i in range(17)]
    src, report = run_one(ages, [200] * 9 + [404] * 8)
    assert report.estimates == {1: pytest.approx(ages[9])}
    assert len(src.replay_calls) <= MAX_REQUESTS_PER_PROFILE


def test_no_profile_reaching_the_range_is_only_a_note() -> None:
    src = FakeSource({1: [2, 5], 2: [40], 3: []}, {})
    report = run_sentinel(src, PROBES, BUDGET, NOW)
    assert report.estimates == {} and report.failures == []
    assert len(report.notes) == 3
    assert src.replay_calls == []


def test_estimate_under_the_margin_fails_naming_profile_estimate_and_budget() -> None:
    _, report = run_one([18.5, 19, 20, 21], [200, 404, 404, 404])
    assert report.estimates == {1: pytest.approx(19)}
    (failure,) = report.failures
    assert "profile 1" in failure and "19.00" in failure and "CAPTURE_BUDGET_DAYS 18" in failure


def test_estimate_exactly_at_the_margin_passes() -> None:
    _, report = run_one([18.5, 21, 22, 23], [200, 404, 404, 404])
    assert report.estimates == {1: pytest.approx(21)} and report.failures == []


def test_caps_hold_per_profile_and_per_run_and_a_capped_profile_does_not_starve_the_next() -> None:
    # Alternating statuses never confirm a transition, so each profile searches until its cap.
    ages = [18 + 0.3 * i for i in range(40)]
    codes = [200 if i % 2 == 0 else 404 for i in range(40)]
    statuses = {**statuses_for(1, codes), **statuses_for(2, codes), **statuses_for(3, codes)}
    src = FakeSource({1: ages, 2: ages, 3: ages}, statuses)
    paced: list[int] = []
    report = run_sentinel(src, PROBES, BUDGET, NOW, pace=lambda: paced.append(1))
    per_profile = [sum(1 for g, _ in src.replay_calls if g // 1000 == p) for p in PROBES]
    assert (MAX_REQUESTS_PER_PROFILE, MAX_REQUESTS_PER_RUN) == (12, 30)
    assert all(0 < n <= MAX_REQUESTS_PER_PROFILE for n in per_profile)
    assert len(src.replay_calls) <= MAX_REQUESTS_PER_RUN
    assert len(paced) == len(src.replay_calls) + len(src.companion_pages)
    assert report.estimates == {} and report.failures == []
    assert len(report.notes) == 3


def test_a_profile_that_hits_its_cap_leaves_the_next_profile_its_share() -> None:
    ages = [18 + 0.3 * i for i in range(40)]
    noisy = [200 if i % 2 == 0 else 404 for i in range(40)]
    clean_ages = [19, 20, 21, 22, 23, 24]
    statuses = {
        **statuses_for(1, noisy),
        **statuses_for(2, [200, 200, 200, 404, 404, 404]),
    }
    src = FakeSource({1: ages, 2: clean_ages}, statuses)
    report = run_sentinel(src, (1, 2), BUDGET, NOW)
    assert 1 not in report.estimates
    assert report.estimates[2] == pytest.approx(22)


def test_relic_outage_is_a_note_and_other_profiles_still_run() -> None:
    codes = [200, 404, 404, 404]
    src = FakeSource(
        {2: [19, 22, 23, 24]}, statuses_for(2, codes), relic_down={1}, companion_down=True
    )
    report = run_sentinel(src, (1, 2), BUDGET, NOW)
    assert 1 not in report.estimates and 2 in report.estimates
    assert any("profile 1" in n and "Relic unreadable" in n for n in report.notes)


def test_companion_refusal_falls_back_to_relic_with_a_note() -> None:
    src = FakeSource(
        {1: [19, 20, 21, 22, 23, 24]},
        statuses_for(1, [200, 200, 200, 404, 404, 404]),
        companion_down=True,
    )
    report = run_sentinel(src, (1,), BUDGET, NOW)
    assert report.estimates == {1: pytest.approx(22)} and report.failures == []
    assert any("companion unavailable" in n and "fell back to Relic" in n for n in report.notes)


def test_companion_malformed_body_falls_back_to_relic() -> None:
    session = FakeSession(FakeResponse(200, {"nope": []}))
    with pytest.raises(SourceOutage):
        RequestsSource(session).companion_matches(1, 1)
    forbidden = FakeSession(FakeResponse(403))
    with pytest.raises(SourceOutage):
        RequestsSource(forbidden).companion_matches(1, 1)


def test_companion_null_finished_entries_are_skipped() -> None:
    entries = [
        {"matchId": 1, "started": "2026-01-01T00:00:00Z", "finished": None},
        {"matchId": 2, "finished": "2026-01-01T01:00:00Z"},
        {"matchId": 3, "finished": "garbage"},
    ]
    assert [m["id"] for m in companion_to_matches(entries)] == [2]


def test_companion_paging_stops_once_a_page_is_older_than_the_range() -> None:
    # 20 per page, newest first: page 1 is ages 1..20 days, page 2 reaches past 33 days.
    ages = [1 + 1.0 * i for i in range(60)]
    src = FakeSource({1: ages}, statuses_for(1, [200] * 60))
    run_sentinel(src, (1,), BUDGET, NOW)
    assert src.companion_pages == [1, 2]


def test_companion_paging_is_capped_per_profile() -> None:
    ages = [1 + 0.05 * i for i in range(400)]  # never leaves the recent end of the feed
    src = FakeSource({1: ages}, statuses_for(1, [200] * 400))
    run_sentinel(src, (1,), BUDGET, NOW)
    assert MAX_COMPANION_PAGES == 10
    assert src.companion_pages == list(range(1, MAX_COMPANION_PAGES + 1))


def test_companion_requests_do_not_count_against_replay_caps() -> None:
    ages = [18 + 0.5 * i for i in range(30)]
    src = FakeSource({1: ages}, statuses_for(1, [200] * 15 + [404] * 15))
    paced: list[int] = []
    report = run_sentinel(src, (1,), BUDGET, NOW, pace=lambda: paced.append(1))
    assert report.estimates and len(paced) == len(src.companion_pages) + len(src.replay_calls)
    assert len(src.replay_calls) <= MAX_REQUESTS_PER_PROFILE


def test_replay_outage_is_a_note_never_an_estimate_and_stops_fetching() -> None:
    src = FakeSource({1: [19, 22], 2: [19, 22]}, {}, replay_down=True)
    report = run_sentinel(src, (1, 2), BUDGET, NOW)
    assert report.estimates == {} and report.failures == []
    assert len(src.replay_calls) == 1
    assert any("aoe.ms unreadable" in n for n in report.notes)


class FakeResponse:
    def __init__(self, status: int, body: Any = None) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no json")
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeSession:
    def __init__(self, response: FakeResponse | None) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if self.response is None:
            raise ConnectionError("down")
        return self.response


@pytest.mark.parametrize("response", [None, FakeResponse(503), FakeResponse(429)])
def test_requests_source_maps_outages(response: FakeResponse | None) -> None:
    source = RequestsSource(FakeSession(response))
    with pytest.raises(SourceOutage):
        source.recent_matches(1)
    with pytest.raises(SourceOutage):
        source.replay_status(10, 1)


def test_requests_source_reads_statuses_and_streams_the_replay() -> None:
    session = FakeSession(FakeResponse(404))
    assert RequestsSource(session).replay_status(10, 1) == 404
    assert session.calls[0]["stream"] is True
    ok = FakeSession(FakeResponse(200, {"matchHistoryStats": [{"id": 5}, "junk"]}))
    assert RequestsSource(ok).recent_matches(1) == [{"id": 5}]
    bad = FakeSession(FakeResponse(200, {"other": 1}))
    with pytest.raises(SourceOutage):
        RequestsSource(bad).recent_matches(1)


def test_unset_configuration_is_a_note_and_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main({}) == 0
    assert main({"CAPTURE_BUDGET_DAYS": "18"}) == 0
    assert "NOTE" in capsys.readouterr().out


def test_malformed_configuration_is_loud() -> None:
    with pytest.raises(ValueError):
        main({"CAPTURE_BUDGET_DAYS": "abc", "AOEMS_MAX_REQUESTS_PER_SECOND": "1"})
