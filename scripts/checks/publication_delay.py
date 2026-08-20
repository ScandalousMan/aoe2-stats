"""Pure logic behind the publication-delay distribution `contract_sources.py` accumulates (T012a).

Split out of `contract_sources.py` so it stays importable without that script's side effects: every
`@check`-decorated function there fires a live network call the moment it is defined, and the module
also parses `sys.argv` for `--capture-fixtures` at import time. Neither belongs anywhere near a unit
test. Everything below is pure — given a sample it appends one line and computes a bounded summary
block from a corpus; given a list of rows it computes statistics. No network, no argv, no
import-time effects beyond parsing `.env.example` for the one constant below.

T012b: the raw corpus no longer lives in this repository. `contract_sources.py`'s nightly run
downloads it as a chained GitHub Actions artifact, appends this run's sample with `append_sample`,
and re-uploads the whole thing — see the "Restore" / "Re-upload" steps around the `contracts` job in
`.github/workflows/nightly.yml`. Nothing about that path touches `docs/data-sources.md`. The
`render_summary` / `rewrite_summary_block` pair below still exists, but only as a tool a human runs
by hand against a corpus they have pulled, when they choose to update the conclusion in
`docs/data-sources.md` §2 — CLAUDE.md's "the difference matters": a summary a machine regenerates
every night on data nobody reviewed is not a conclusion, and claiming it is one was exactly T012b's
finding (b).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"


def _read_grace_hours(env_example_path: Path = _ENV_EXAMPLE) -> int:
    """`REPLAY_PUBLICATION_GRACE_HOURS` has exactly one home: `.env.example`. Every consumer reads
    it from there rather than restating the digit — the running application through
    `Settings` (`apps/api/src/aoe2stats_api/settings.py`, a required field with no default, so
    production sets its own copy of this file's value the same way it sets every other
    environment variable) and this script by parsing the same line a human edits. T012b's finding
    (c): a module-level literal here could go stale the moment someone raised the grace in
    `.env.example` without also editing this file, and the generated prose would then assert a
    number that was no longer true. Parsing avoids that by construction — there is nothing here to
    forget to update.
    """
    text = env_example_path.read_text(encoding="utf-8")
    match = re.search(r"^REPLAY_PUBLICATION_GRACE_HOURS=(\d+)\s*$", text, re.MULTILINE)
    if match is None:
        raise RuntimeError(
            f"{env_example_path} does not declare REPLAY_PUBLICATION_GRACE_HOURS as a plain "
            "integer on its own line; publication_delay.py has nothing to compare samples against."
        )
    return int(match.group(1))


REPLAY_PUBLICATION_GRACE_HOURS = _read_grace_hours()

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
            "- No sample recorded yet. The nightly contract run (`contract_sources.py`) appends "
            "the first one to the chained `publication-delay-corpus` artifact "
            f"(`.github/workflows/nightly.yml`); pulled locally, it lives at `{samples_relpath}`."
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

    Not used by the nightly run (T012b) — `contract_sources.py`'s automatic path calls
    `append_sample` directly and never touches `doc_path`, because the corpus it appends to is
    downloaded fresh from the artifact chain each run and no CI job may commit the result back to
    the repository. This function is the tool a human runs locally, against a corpus they pulled
    from the `publication-delay-corpus` artifact, when they decide the conclusion in
    `docs/data-sources.md` §2 should move: the two files it touches never go out of step with each
    other *in that one call*, because nothing here writes one without the other in the same
    breath — but the call itself only happens when a person makes it.
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
