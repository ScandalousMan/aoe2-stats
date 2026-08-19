"""Unit tests for the pure logic behind the publication-delay distribution (T012a).

No network here — `publication_delay.py` is pure by construction, exactly so it can be tested this
way instead of only ever being exercised by the nightly contract run. See
`scripts/checks/publication_delay.py`.
"""

from pathlib import Path

from scripts.checks.publication_delay import (
    REPLAY_PUBLICATION_GRACE_HOURS,
    SUMMARY_BEGIN,
    SUMMARY_END,
    append_sample,
    read_samples,
    record_sample,
    render_summary,
    rewrite_summary_block,
)


def test_read_samples_is_empty_before_anything_is_recorded(tmp_path: Path) -> None:
    assert read_samples(tmp_path / "nope.jsonl") == []


def test_append_sample_is_append_only(tmp_path: Path) -> None:
    samples_path = tmp_path / "samples.jsonl"

    first = append_sample(
        samples_path,
        observed_at_iso="2026-08-19T21:00:00Z",
        game_id=1,
        age_hours=0.55,
        available=True,
    )
    second = append_sample(
        samples_path,
        observed_at_iso="2026-08-20T03:00:00Z",
        game_id=2,
        age_hours=5.0,
        available=False,
    )

    rows = read_samples(samples_path)
    assert rows == [first, second]
    # Rounded for a readable diff, never truncated to the point of losing the distinction that
    # matters here (available vs not).
    assert rows[0]["age_hours"] == 0.55
    assert rows[0]["available"] is True
    assert rows[1]["available"] is False


def test_append_sample_never_rewrites_an_earlier_line(tmp_path: Path) -> None:
    samples_path = tmp_path / "samples.jsonl"
    append_sample(
        samples_path,
        observed_at_iso="2026-08-19T21:00:00Z",
        game_id=1,
        age_hours=0.1,
        available=True,
    )
    before = samples_path.read_text(encoding="utf-8")

    append_sample(
        samples_path,
        observed_at_iso="2026-08-20T21:00:00Z",
        game_id=2,
        age_hours=0.2,
        available=True,
    )

    after = samples_path.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert len(read_samples(samples_path)) == 2


def test_render_summary_with_no_samples_points_at_the_nightly_run() -> None:
    summary = render_summary(
        [], samples_relpath="docs/data-sources/publication_delay_samples.jsonl"
    )
    assert "No sample recorded yet" in summary
    assert "docs/data-sources/publication_delay_samples.jsonl" in summary


def test_render_summary_reports_the_worst_case_and_no_breach() -> None:
    samples = [
        {"observed_at": "2026-08-19T21:00:00Z", "game_id": 1, "age_hours": 0.55, "available": True},
        {"observed_at": "2026-08-20T03:00:00Z", "game_id": 2, "age_hours": 1.2, "available": False},
    ]
    summary = render_summary(
        samples, samples_relpath="docs/data-sources/publication_delay_samples.jsonl"
    )

    assert "Samples recorded: **2**" in summary
    assert "1.20 h" in summary  # longest age still unavailable
    assert "0.55 h" in summary  # shortest age already available
    assert "No sample has exceeded" in summary
    assert f"{REPLAY_PUBLICATION_GRACE_HOURS} h" in summary


def test_render_summary_flags_a_sample_that_breaches_the_grace() -> None:
    samples = [
        {
            "observed_at": "2026-08-19T21:00:00Z",
            "game_id": 1,
            "age_hours": REPLAY_PUBLICATION_GRACE_HOURS + 1,
            "available": False,
        }
    ]
    summary = render_summary(
        samples, samples_relpath="docs/data-sources/publication_delay_samples.jsonl"
    )

    assert "exceeded `REPLAY_PUBLICATION_GRACE_HOURS`" in summary
    assert "raise the grace" in summary


def test_rewrite_summary_block_replaces_only_the_marked_region(tmp_path: Path) -> None:
    doc_path = tmp_path / "data-sources.md"
    doc_path.write_text(
        f"before\n\n{SUMMARY_BEGIN}\nold content\n{SUMMARY_END}\n\nafter\n", encoding="utf-8"
    )

    rewrite_summary_block(doc_path, "new content")

    doc = doc_path.read_text(encoding="utf-8")
    assert doc.startswith("before\n\n")
    assert doc.endswith("\n\nafter\n")
    assert "old content" not in doc
    assert "new content" in doc


def test_rewrite_summary_block_raises_without_markers(tmp_path: Path) -> None:
    doc_path = tmp_path / "data-sources.md"
    doc_path.write_text("no markers here\n", encoding="utf-8")

    try:
        rewrite_summary_block(doc_path, "irrelevant")
    except RuntimeError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected a RuntimeError for a doc missing the summary markers")


def test_record_sample_appends_and_regenerates_in_one_call(tmp_path: Path) -> None:
    samples_path = tmp_path / "samples.jsonl"
    doc_path = tmp_path / "data-sources.md"
    doc_path.write_text(f"{SUMMARY_BEGIN}\nstale\n{SUMMARY_END}\n", encoding="utf-8")

    row = record_sample(
        samples_path,
        doc_path,
        observed_at_iso="2026-08-19T21:00:00Z",
        game_id=500572650,
        age_hours=0.6,
        available=True,
        samples_relpath="docs/data-sources/publication_delay_samples.jsonl",
    )

    assert row["game_id"] == 500572650
    assert read_samples(samples_path) == [row]
    doc = doc_path.read_text(encoding="utf-8")
    assert "stale" not in doc
    assert "Samples recorded: **1**" in doc
