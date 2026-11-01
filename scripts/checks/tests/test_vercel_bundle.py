"""The bundle guard for `vercel.json`: what each Python function leaves out of its deployment
(007, T807; FR-002, FR-012; `specs/007-shrink-deployment-storage/research.md` R1 and
`contracts/function-layout.md` invariant 1).

Every function entry carries the same `excludeFiles` string: one brace-glob whose alternatives are
every top-level entry the upload contains, except `api`, the two files named in `KEPT_IN_BUNDLE`,
the entries the builder drops itself and the directories `.vercelignore` drops whole (`/<name>/`),
each an exact root file name or `<dir>/**`. No entry is both upload-ignored and listed, and the
value is at most `EXCLUDE_VALUE_MAX_LENGTH` characters. This file holds that rule as small pure
functions and asserts it twice over:

- **Planted defects**, on synthetic input, which pass today: a new top-level directory nobody
  listed, a nested alternative, a list that covers `api` or a kept file, an entry whose value
  differs, a stale alternative, a third root file next to the kept two. They prove the guard fires,
  so a green run on the real file means something. Also a value one character over the length cap
  and an upload-ignored directory that is still listed.
- **The real `vercel.json` against the real `git ls-files`**: three entries at their limits, one
  identical value, every tracked top-level entry accounted for.

The matching is a prefix test on the first path segment, never a glob engine, so the node-glob
dialect the builder uses and Python cannot disagree about it (research R1, "Why this shape"). The
failure direction the rule accepts is benign: an entry nobody listed ships extra bytes and turns
this guard red; it never removes a file a function needs.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

SHORT_LIMIT = 10
LONG_LIMIT = 300
EXPECTED_LIMITS: dict[str, int] = {
    "api/index.py": SHORT_LIMIT,
    "api/analyze.py": LONG_LIMIT,
    "api/cron/ingest.py": LONG_LIMIT,
}

# The top-level names the Python builder drops on its own, so `excludeFiles` need not list them.
# Source: research R1, "Built-in excludes", read from the builder's `packages/python/src/index.ts`
# (the `glob('**', { ignore })` call). R1 writes the directory names as `**/<name>`, which also
# matches at the root, and the three lock files as "every" file of that name. Kept here as a
# constant, not read from the builder: when the builder changes, this list is what to re-read.
BUILDER_EXCLUDES: frozenset[str] = frozenset(
    {
        ".git",
        ".gitignore",
        ".vercel",
        ".pnpm-store",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "public",
        "pnpm-lock.yaml",
        "yarn.lock",
        "package-lock.json",
    }
)

# The two root files `excludeFiles` must NOT list, on purpose (T808, check 2). The Python builder
# (`packages/python/src/dependency-externalizer.ts` and `python/vercel-runtime/src/vercel_runtime/
# vc_init.py`, `vercel/vercel` at commit c628be78, builder package 13.0.1) switches a function to
# installing part of its dependencies at cold start when the bundle exceeds its size threshold. It
# then writes `_uv/_runtime_config.json` with `projectDir` pointing at the project root and runs
# `uv sync --frozen` there, and the source comment says `pyproject.toml` and `uv.lock` "are already
# part of the Lambda zip (globbed from workPath)": it adds them itself only when the project root
# lies above the work path, which is not our layout. Excluding them would be harmless today, because
# the bundle is far below that threshold, and would make the function fail to boot the day it
# crosses it, an outage no offline check sees. They weigh kilobytes; keeping them is the cheap side.
# Re-read those two files when the builder changes; drop this constant only if that path is gone.
KEPT_IN_BUNDLE: frozenset[str] = frozenset({"pyproject.toml", "uv.lock"})

# The host's cap on one `excludeFiles` value. Source: the schema validation error of the production
# build of merge 45a8dc4c on 2026-11-01, "functions.api/cron/ingest.py.excludeFiles should NOT be
# longer than 256 characters" (the host's `vercel.json` schema). Not in the builder's documentation.
EXCLUDE_VALUE_MAX_LENGTH = 256

_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
_DIR_SUFFIX = "/**"


# ---------------------------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------------------------


def parse_exclude(value: object) -> list[str]:
    """The alternatives of an `excludeFiles` value, or `ValueError` if it is not one brace-glob.

    The value must be a string (the builder's validator rejects any other type) of the form
    `{a,b,...}`. Two alternatives at least: a brace pair without a comma is not expanded by the glob
    engine, so a single alternative would be read as a literal.
    """
    if not isinstance(value, str):
        raise ValueError(f"excludeFiles must be a string, got {type(value).__name__}")
    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError("excludeFiles must be one brace-glob: {a,b,...}")
    alternatives = value[1:-1].split(",")
    if len(alternatives) < 2:
        raise ValueError("a brace-glob needs a comma to expand: at least two alternatives")
    return alternatives


def vercelignore_directories(text: str) -> frozenset[str]:
    """The top-level directories `.vercelignore` drops whole: lines exactly `/<name>/`.

    Every other line (comments, blanks, negations, unanchored globs such as `.env*`, nested paths)
    is not a whole-entry rule and is ignored, so the guard never credits a partial exclusion."""
    names = set()
    for line in text.splitlines():
        if len(line) > 2 and line.startswith("/") and line.endswith("/"):
            name = line[1:-1]
            if _NAME.match(name):
                names.add(name)
    return frozenset(names)


def alternative_name(alternative: str) -> str:
    """The top-level name an alternative stands for: `docs/**` -> `docs`, `README.md` -> itself."""
    return alternative.removesuffix(_DIR_SUFFIX)


def alternative_problems(alternatives: list[str]) -> list[str]:
    """Why a list of alternatives breaks the shape: nested, wildcarded, covering `api` or a file the
    runtime install needs, repeated."""
    problems: list[str] = []
    for alternative in alternatives:
        name = alternative_name(alternative)
        if not _NAME.match(name):
            problems.append(
                f"{alternative!r}: must be an exact root name or <dir>/**, "
                "nothing nested and no wildcard in a name"
            )
        elif name == "api":
            problems.append(f"{alternative!r}: `api` must never be excluded")
        elif name in KEPT_IN_BUNDLE:
            problems.append(
                f"{alternative!r}: the builder's runtime install reads it from the bundle"
            )
    for alternative in sorted(set(alternatives)):
        if alternatives.count(alternative) > 1:
            problems.append(f"{alternative!r}: listed more than once")
    return problems


def top_level_entries(tracked: list[str]) -> dict[str, bool]:
    """Each tracked top-level entry mapped to whether it is a directory."""
    entries: dict[str, bool] = {}
    for path in tracked:
        head, separator, _ = path.partition("/")
        entries[head] = entries.get(head, False) or bool(separator)
    return entries


def is_excluded(path: str, alternatives: list[str]) -> bool:
    """The whole-entry rule: a file alternative drops exactly that root file, a `<dir>/**`
    alternative drops everything under that directory and nothing else."""
    head, separator, _ = path.partition("/")
    if separator:
        return f"{head}{_DIR_SUFFIX}" in alternatives
    return head in alternatives


def uncovered_entries(
    tracked: list[str],
    alternatives: list[str],
    builder_excludes: frozenset[str],
    kept: frozenset[str] = KEPT_IN_BUNDLE,
    upload_ignored: frozenset[str] = frozenset(),
) -> list[str]:
    """Top-level entries that are not `api`, not dropped by the builder, not a named exception in
    `kept`, not a directory `.vercelignore` drops whole, and not fully excluded."""
    uncovered = []
    for entry in top_level_entries(tracked):
        if entry == "api" or entry in builder_excludes or entry in kept or entry in upload_ignored:
            continue
        files = [p for p in tracked if p == entry or p.startswith(f"{entry}/")]
        if not all(is_excluded(path, alternatives) for path in files):
            uncovered.append(entry)
    return sorted(uncovered)


def stale_alternatives(
    tracked: list[str],
    alternatives: list[str],
    upload_ignored: frozenset[str] = frozenset(),
) -> list[str]:
    """Alternatives that match no tracked file, or name a directory `.vercelignore` already drops
    whole, so the list stays exact and not only sufficient."""
    return sorted(
        alternative
        for alternative in alternatives
        if alternative_name(alternative) in upload_ignored
        or not any(is_excluded(path, [alternative]) for path in tracked)
    )


def layout_problems(functions: Mapping[str, Mapping[str, object]]) -> list[str]:
    """Exactly the three function entries, at the limits the layout contract names."""
    problems: list[str] = []
    for name in sorted(set(functions) - set(EXPECTED_LIMITS)):
        problems.append(f"{name}: not one of the three functions")
    for name, limit in EXPECTED_LIMITS.items():
        if name not in functions:
            problems.append(f"{name}: missing")
        elif functions[name].get("maxDuration") != limit:
            problems.append(f"{name}: maxDuration must be {limit}")
    return problems


def exclude_value_problems(functions: Mapping[str, Mapping[str, object]]) -> list[str]:
    """Each entry carries an `excludeFiles` string within the host's length cap, and the strings
    are identical."""
    problems: list[str] = []
    values: set[str] = set()
    for name in sorted(functions):
        value = functions[name].get("excludeFiles")
        if not isinstance(value, str):
            problems.append(f"{name}: excludeFiles must be a string")
        else:
            values.add(value)
            if len(value) > EXCLUDE_VALUE_MAX_LENGTH:
                problems.append(
                    f"{name}: excludeFiles is {len(value)} characters, "
                    f"the host allows at most {EXCLUDE_VALUE_MAX_LENGTH}"
                )
    if len(values) > 1:
        problems.append("excludeFiles differs between entries")
    return problems


# ---------------------------------------------------------------------------------------------
# Planted defects: synthetic input, passing now
# ---------------------------------------------------------------------------------------------

_TRACKED = [
    "api/index.py",
    "api/cron/ingest.py",
    "apps/web/src/main.tsx",
    "docs/data-sources.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    "pnpm-lock.yaml",
]
_GOOD = ["apps/**", "docs/**", "README.md"]
_GOOD_FUNCTIONS: dict[str, dict[str, object]] = {
    name: {"maxDuration": limit, "excludeFiles": "{apps/**,docs/**}"}
    for name, limit in EXPECTED_LIMITS.items()
}


def test_a_complete_list_passes_every_check() -> None:
    assert alternative_problems(_GOOD) == []
    assert uncovered_entries(_TRACKED, _GOOD, BUILDER_EXCLUDES) == []
    assert stale_alternatives(_TRACKED, _GOOD) == []
    assert layout_problems(_GOOD_FUNCTIONS) == []
    assert exclude_value_problems(_GOOD_FUNCTIONS) == []


def test_parse_exclude_reads_one_brace_glob() -> None:
    assert parse_exclude("{apps/**,README.md}") == ["apps/**", "README.md"]


@pytest.mark.parametrize(
    "value", [None, ["apps/**"], "apps/**", "{apps/**}", "{apps/**,docs/**", ""]
)
def test_parse_exclude_refuses_anything_but_a_brace_glob_string(value: object) -> None:
    with pytest.raises(ValueError):
        parse_exclude(value)


def test_a_new_top_level_directory_is_reported_until_it_is_listed() -> None:
    tracked = [*_TRACKED, "newdir/thing.py"]
    assert uncovered_entries(tracked, _GOOD, BUILDER_EXCLUDES) == ["newdir"]
    assert uncovered_entries(tracked, [*_GOOD, "newdir/**"], BUILDER_EXCLUDES) == []


def test_a_new_top_level_file_is_reported_until_it_is_listed() -> None:
    tracked = [*_TRACKED, "NOTES.md"]
    assert uncovered_entries(tracked, _GOOD, BUILDER_EXCLUDES) == ["NOTES.md"]


def test_a_file_alternative_does_not_cover_a_directory_and_the_reverse() -> None:
    assert uncovered_entries(_TRACKED, ["apps", "docs/**", "README.md"], BUILDER_EXCLUDES) == [
        "apps"
    ]
    assert uncovered_entries(
        _TRACKED, ["apps/**", "docs/**", "README.md/**"], BUILDER_EXCLUDES
    ) == ["README.md"]


def test_an_entry_the_builder_drops_needs_no_alternative() -> None:
    # `.gitignore` and `pnpm-lock.yaml` are tracked in _TRACKED and absent from _GOOD.
    assert uncovered_entries(_TRACKED, _GOOD, BUILDER_EXCLUDES) == []
    assert uncovered_entries(_TRACKED, _GOOD, frozenset()) == [".gitignore", "pnpm-lock.yaml"]


@pytest.mark.parametrize(
    "alternative", ["apps/web/**", "apps/web/src/main.tsx", "apps/*", "*.md", "a?b", "{a}", "./x"]
)
def test_a_nested_or_wildcarded_alternative_is_reported(alternative: str) -> None:
    assert len(alternative_problems([*_GOOD, alternative])) == 1


def test_the_two_kept_files_need_no_alternative_and_a_third_root_file_still_does() -> None:
    # `pyproject.toml` and `uv.lock` are tracked in _TRACKED and absent from _GOOD.
    assert uncovered_entries(_TRACKED, _GOOD, BUILDER_EXCLUDES) == []
    # the exception is exactly those two names: it does not widen into a pass for anything else
    assert uncovered_entries([*_TRACKED, "setup.cfg"], _GOOD, BUILDER_EXCLUDES) == ["setup.cfg"]
    assert uncovered_entries(
        [*_TRACKED, "pyproject.toml.bak", "NOTES.md"], _GOOD, BUILDER_EXCLUDES
    ) == ["NOTES.md", "pyproject.toml.bak"]
    # without the exception the same two files are reported
    assert uncovered_entries(_TRACKED, _GOOD, BUILDER_EXCLUDES, frozenset()) == [
        "pyproject.toml",
        "uv.lock",
    ]


@pytest.mark.parametrize("alternative", ["pyproject.toml", "uv.lock"])
def test_a_list_that_excludes_a_kept_file_is_reported(alternative: str) -> None:
    problems = alternative_problems([*_GOOD, alternative])
    assert len(problems) == 1
    assert "runtime install" in problems[0]


@pytest.mark.parametrize("alternative", ["api", "api/**"])
def test_a_list_that_covers_api_is_reported(alternative: str) -> None:
    problems = alternative_problems([*_GOOD, alternative])
    assert len(problems) == 1
    assert "api" in problems[0]


def test_a_repeated_alternative_is_reported() -> None:
    assert len(alternative_problems([*_GOOD, "docs/**"])) == 1


def test_an_alternative_naming_a_dropped_entry_is_reported_as_stale() -> None:
    assert stale_alternatives(_TRACKED, [*_GOOD, "gone/**", "OLD.md"]) == ["OLD.md", "gone/**"]
    # a directory alternative for a name that is now a file, and the reverse, match nothing
    assert stale_alternatives(_TRACKED, ["README.md/**", "docs"]) == ["README.md/**", "docs"]


def test_an_entry_whose_value_differs_is_reported() -> None:
    functions = {name: dict(entry) for name, entry in _GOOD_FUNCTIONS.items()}
    functions["api/analyze.py"]["excludeFiles"] = "{apps/**,docs/**,infra/**}"
    assert exclude_value_problems(functions) == ["excludeFiles differs between entries"]


@pytest.mark.parametrize("value", [None, ["apps/**"], 1])
def test_an_entry_without_a_string_value_is_reported(value: object) -> None:
    functions = {name: dict(entry) for name, entry in _GOOD_FUNCTIONS.items()}
    functions["api/index.py"]["excludeFiles"] = value
    assert exclude_value_problems(functions) == ["api/index.py: excludeFiles must be a string"]


def test_a_missing_value_is_reported() -> None:
    functions = {name: {"maxDuration": limit} for name, limit in EXPECTED_LIMITS.items()}
    assert len(exclude_value_problems(functions)) == 3


def test_a_fourth_function_a_missing_one_or_a_moved_limit_is_reported() -> None:
    extra: dict[str, dict[str, object]] = {
        **_GOOD_FUNCTIONS,
        "api/other.py": {"maxDuration": 10},
    }
    assert layout_problems(extra) == ["api/other.py: not one of the three functions"]

    merged = {k: v for k, v in _GOOD_FUNCTIONS.items() if k != "api/analyze.py"}
    assert layout_problems(merged) == ["api/analyze.py: missing"]

    # the parser's function folded into the short one, or the ingestion run into a short limit
    slow = {name: dict(entry) for name, entry in _GOOD_FUNCTIONS.items()}
    slow["api/index.py"]["maxDuration"] = LONG_LIMIT
    slow["api/cron/ingest.py"]["maxDuration"] = SHORT_LIMIT
    assert layout_problems(slow) == [
        f"api/index.py: maxDuration must be {SHORT_LIMIT}",
        f"api/cron/ingest.py: maxDuration must be {LONG_LIMIT}",
    ]


def test_an_exclude_value_over_the_length_cap_is_reported_and_one_at_it_is_not() -> None:
    def functions_with(length: int) -> dict[str, dict[str, object]]:
        value = "{" + "a" * (length - 2) + "}"
        assert len(value) == length
        return {"api/index.py": {"excludeFiles": value}}

    assert exclude_value_problems(functions_with(EXCLUDE_VALUE_MAX_LENGTH)) == []
    problems = exclude_value_problems(functions_with(EXCLUDE_VALUE_MAX_LENGTH + 1))
    assert len(problems) == 1
    assert "257 characters" in problems[0]


def test_the_vercelignore_parser_keeps_only_whole_top_level_directory_rules() -> None:
    text = "\n".join(
        [
            "# a comment",
            "",
            "/docs/",
            "!.env.example",
            ".env*",
            "/packages/design-system/__screenshots__/",
            ".mypy_cache/",
            "/test-results/",
        ]
    )
    assert vercelignore_directories(text) == {"docs", "test-results"}


def test_an_upload_ignored_directory_needs_no_alternative() -> None:
    tracked = [*_TRACKED, "specs/001/spec.md"]
    assert uncovered_entries(tracked, _GOOD, BUILDER_EXCLUDES) == ["specs"]
    assert (
        uncovered_entries(tracked, _GOOD, BUILDER_EXCLUDES, upload_ignored=frozenset({"specs"}))
        == []
    )


def test_a_directory_both_upload_ignored_and_listed_is_reported() -> None:
    ignored = frozenset({"docs"})
    assert stale_alternatives(_TRACKED, _GOOD) == []
    assert stale_alternatives(_TRACKED, _GOOD, ignored) == ["docs/**"]


def test_is_excluded_is_a_whole_entry_prefix_test() -> None:
    assert is_excluded("docs/a/b.md", ["docs/**"])
    assert not is_excluded("docs", ["docs/**"])
    assert not is_excluded("docs-extra/a.md", ["docs/**"])
    assert is_excluded("README.md", ["README.md"])
    assert not is_excluded("README.md/x", ["README.md"])


# ---------------------------------------------------------------------------------------------
# The real vercel.json against the real git ls-files
# ---------------------------------------------------------------------------------------------


def _functions() -> dict[str, dict[str, object]]:
    config = json.loads((_REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    functions: dict[str, dict[str, object]] = config["functions"]
    return functions


def _tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [path for path in result.stdout.split("\0") if path]


def _upload_ignored() -> frozenset[str]:
    text = (_REPO_ROOT / ".vercelignore").read_text(encoding="utf-8")
    return vercelignore_directories(text)


def _alternatives() -> list[str]:
    problems = exclude_value_problems(_functions())
    assert problems == []
    return parse_exclude(next(iter(_functions().values()))["excludeFiles"])


def test_vercel_json_keeps_the_three_functions_at_their_limits() -> None:
    """True today: the layout is not what this feature changes (FR-012)."""
    assert layout_problems(_functions()) == []


def test_every_function_carries_the_same_exclude_string() -> None:
    assert exclude_value_problems(_functions()) == []


def test_the_exclude_string_is_one_brace_glob_of_exact_names_and_directories() -> None:
    assert alternative_problems(_alternatives()) == []


def test_every_tracked_top_level_entry_is_api_listed_or_dropped_by_the_builder() -> None:
    assert (
        uncovered_entries(
            _tracked(), _alternatives(), BUILDER_EXCLUDES, upload_ignored=_upload_ignored()
        )
        == []
    )


def test_no_alternative_names_an_entry_that_is_no_longer_tracked() -> None:
    assert stale_alternatives(_tracked(), _alternatives(), _upload_ignored()) == []


def test_the_exclude_string_is_within_the_hosts_length_cap() -> None:
    assert [
        problem for problem in exclude_value_problems(_functions()) if "characters" in problem
    ] == []
