"""Pure logic behind the publication-delay distribution `contract_sources.py` accumulates (T012a).

Split out of `contract_sources.py` so it stays importable without that script's side effects: every
`@check`-decorated function there fires a live network call the moment it is defined, and the module
also parses `sys.argv` for `--capture-fixtures` at import time. Neither belongs anywhere near a unit
test. Everything below is pure — given a sample it appends one line and rewrites a bounded summary
block; given a list of rows it computes statistics. No network, no argv, no import-time effects.

The raw corpus (`docs/data-sources/publication_delay_samples.jsonl`) and the summary regenerated
into `docs/data-sources.md` are the same measurement in the same home (`docs/`, per CLAUDE.md): the
summary is *derived* by this module from the raw file on every run, never hand-copied, so the two
can never drift apart the way two independently maintained numbers would.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Mirrors `.env.example`'s `REPLAY_PUBLICATION_GRACE_HOURS`. This is the floor the distribution
# exists to check, not a value owned here — trust `.env.example` if the two ever disagree.
# Restating it is the constraint carve-out CLAUDE.md allows ("repeating a constraint where it
# governs a decision is different [from copying a measurement], and correct"): every sample is
# compared against this floor to decide whether the floor should be raised.
REPLAY_PUBLICATION_GRACE_HOURS = 72

SUMMARY_BEGIN = "<!-- publication-delay-summary:begin -->"
SUMMARY_END = "<!-- publication-delay-summary:end -->"


def read_samples(samples_path: Path) -> list[dict[str, Any]]:
    """Every sample recorded so far, oldest first. Empty if nothing has been recorded yet."""
    if not samples_path.exists():
        return []
    return [
        json.loads(line)
        for line in samples_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_sample(
    samples_path: Path,
    *,
    observed_at_iso: str,
    game_id: int,
    age_hours: float,
    available: bool,
) -> dict[str, Any]:
    """Append one sample as a JSON line and return it.

    Append-only, like the raw responses this corpus sits beside (constitution IV): a night's
    sample is never rewritten or dropped, only added to.
    """
    row: dict[str, Any] = {
        "observed_at": observed_at_iso,
        "game_id": game_id,
        "age_hours": round(age_hours, 2),
        "available": available,
    }
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    with samples_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def render_summary(samples: list[dict[str, Any]], *, samples_relpath: str) -> str:
    """The prose block `docs/data-sources.md` carries between the summary markers.

    Every line here is computed fresh from `samples`, never carried over from a previous render,
    so a summary written by an older version of this function can never linger stale beside a
    newer corpus.
    """
    if not samples:
        return (
            "- No sample recorded yet. The nightly contract run (`contract_sources.py`) writes "
            f"the first one to `{samples_relpath}`."
        )

    unavailable_ages = [s["age_hours"] for s in samples if not s["available"]]
    available_ages = [s["age_hours"] for s in samples if s["available"]]
    breaches = [
        s for s in samples if not s["available"] and s["age_hours"] > REPLAY_PUBLICATION_GRACE_HOURS
    ]

    lines = [
        f"- Samples recorded: **{len(samples)}**, from `{samples[0]['observed_at']}` to "
        f"`{samples[-1]['observed_at']}`."
    ]
    if unavailable_ages:
        lines.append(
            "- Longest match age observed with the replay still unavailable (a lower bound on "
            f"the real publication delay): **{max(unavailable_ages):.2f} h**."
        )
    if available_ages:
        lines.append(
            "- Shortest match age observed with the replay already available (an upper bound on "
            f"the real publication delay): **{min(available_ages):.2f} h**."
        )
    if breaches:
        lines.append(
            f"- **{len(breaches)} sample(s) exceeded `REPLAY_PUBLICATION_GRACE_HOURS` "
            f"({REPLAY_PUBLICATION_GRACE_HOURS} h) while the replay was still unavailable — "
            "raise the grace in `.env.example` before anything else.**"
        )
    else:
        lines.append(
            "- No sample has exceeded `REPLAY_PUBLICATION_GRACE_HOURS` "
            f"({REPLAY_PUBLICATION_GRACE_HOURS} h)."
        )
    lines.append(f"- Raw samples: `{samples_relpath}` (one JSON object per line, append-only).")
    return "\n".join(lines)


def rewrite_summary_block(doc_path: Path, summary: str) -> None:
    """Replace the text between the summary markers in `doc_path`, and nothing else.

    Raises if the markers are missing rather than appending blindly: a doc edited to drop them is
    a signal to fix the doc, not a reason to grow a second summary block.
    """
    doc = doc_path.read_text(encoding="utf-8")
    if SUMMARY_BEGIN not in doc or SUMMARY_END not in doc:
        raise RuntimeError(
            f"{doc_path} is missing the {SUMMARY_BEGIN} / {SUMMARY_END} markers the automated "
            "publication-delay summary regenerates between."
        )
    before, rest = doc.split(SUMMARY_BEGIN, 1)
    _, after = rest.split(SUMMARY_END, 1)
    doc_path.write_text(
        f"{before}{SUMMARY_BEGIN}\n\n{summary}\n\n{SUMMARY_END}{after}", encoding="utf-8"
    )


def record_sample(
    samples_path: Path,
    doc_path: Path,
    *,
    observed_at_iso: str,
    game_id: int,
    age_hours: float,
    available: bool,
    samples_relpath: str,
) -> dict[str, Any]:
    """Append the sample and regenerate the summary in the same call.

    The two files never go out of step because nothing ever writes one without the other in the
    same breath — there is no code path that appends a sample without also refreshing the summary
    it changes.
    """
    row = append_sample(
        samples_path,
        observed_at_iso=observed_at_iso,
        game_id=game_id,
        age_hours=age_hours,
        available=available,
    )
    samples = read_samples(samples_path)
    rewrite_summary_block(doc_path, render_summary(samples, samples_relpath=samples_relpath))
    return row
