"""Boundary guard for feature 006 against feature 003 and against capture (T666, FR-048, FR-049).

**What this guards.** Constitution I: an analysis feature may not degrade capture. 006 adds a
knowledge base (`packages/knowledge`), truth types (`packages/core/.../truth`) and a gap-rate report
(`packages/storage/.../repositories/knowledge_gaps.py`, `scripts/checks/knowledge_gap_rate.py`).
None of it is allowed to become a scheduled job, a step on the request path, or a consumer of the
budget replay capture depends on (**FR-049**, 003 FR-039/FR-044), and none of it may restate 003's
request, fetch, parse-once, retention, recompute, isolation, rate-limiting or legal-basis behaviour
(**FR-048**: where the two meet, 003 stands). The cheapest moment to assert that is while the
feature's diff is still in hand.

**Method — the real repository state against a recorded baseline.** Every check reads what is on
disk now and compares it with a named constant recorded from `origin/main` before 006 changed
anything. A baseline difference fails with the offending entry named. The checks are:

1. The set of scheduled workflows and their crons, plus the job ids of each scheduled workflow, and
   `vercel.json`'s crons and function entries (`_BASELINE_*`). The assertion is on the *set of
   scheduled units*, never on the steps inside a job: T663 adds one step to `nightly.yml`'s existing
   job set to run the gap-rate report, which is not a new scheduled job and must stay allowed.
2. No module on the request path (`api/`, `apps/api/src`, the analyzer's request/lease/dedupe/
   admission/run code, and the ingester's capture code) imports `aoe2stats_knowledge` or
   `aoe2stats_core.truth`. The analyzer's `extract.py` is the parse step itself, off the
   request/lease path, and is deliberately not in the set.
3. The new 006 code never names the capture budget: not `CAPTURE_BUDGET_DAYS`/`capture_budget_days`,
   not a capture deadline, not the `replay_captures` or `provider_calls` tables or their models, and
   it imports neither `aoe2stats_ingester` nor `aoe2stats_providers` (the budget's two homes).
4. The new 006 code imports none of 003's packages (`aoe2stats_analyzer`, `aoe2stats_api`,
   `aoe2stats_ingester`) and defines no top-level function or class named in 003's vocabulary
   (lease, claim, admission, retention, rate limit, dedupe, fetch, erasure, consent). This is the
   mechanical proxy for FR-048: a second implementation of one of those behaviours needs a name.

**No YAML dependency.** The workspace carries no YAML parser, and a test that adds a dependency to
guard a boundary is its own kind of drift. The workflow files are read by a small line-based
extractor limited to the two shapes this repository uses (block-style `on:` with a `schedule:`
list, and block-style `jobs:`); a flow-style `on:` that mentions `schedule` is refused loudly
rather than guessed at.

**Every check is proven able to fail.** Each real-tree test has a contrast test below feeding the
same detector a synthetic input that violates the rule, so a green run is evidence of a clean tree
and not of a detector that matches nothing. Scope is `src/` and the named entrypoints, never
`tests/`, the same line `test_import_graph.py` draws.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"

# --- Baseline recorded from `git show origin/main:` (b9f1ca48), before 006 added anything --------
# FR-049: this feature adds no scheduled job. These are the scheduled units that existed before it.
# A change here is a decision about scheduling, to be made in its own task and spec, never as a
# side effect of an analysis feature.

# Workflow file -> its `schedule` crons. `baselines.yml`, `pr.yml` and `smoke.yml` have no schedule.
_BASELINE_SCHEDULED_WORKFLOWS: Mapping[str, tuple[str, ...]] = {
    "nightly.yml": ("0 3 * * *",),
}

# Job ids of every scheduled workflow. A new job in a scheduled workflow runs on the schedule too,
# so it is a new scheduled job; a new *step* inside an existing job is not, and is not asserted.
_BASELINE_SCHEDULED_JOBS: Mapping[str, frozenset[str]] = {
    "nightly.yml": frozenset(
        {
            "contracts",
            "parser-canary",
            "asset-packs",
            "cron-liveness",
            "capture-audit",
            "alert-audit",
            "production-smoke",
            "free-tier-watch",
            "visual-full",
            "state-signal-sweep",
            "report",
        }
    ),
}

# `vercel.json`'s cron entries as (path, schedule), and its function entries: the platform-side
# scheduled work and the platform-side request handlers.
_BASELINE_VERCEL_CRONS: frozenset[tuple[str, str]] = frozenset({("/api/cron/ingest", "0 4 * * *")})
_BASELINE_VERCEL_FUNCTIONS: frozenset[str] = frozenset(
    {"api/cron/ingest.py", "api/analyze.py", "api/index.py"}
)
# The handler files under `api/`: any new one is new request-path work.
_BASELINE_API_HANDLERS: frozenset[str] = frozenset(
    {"api/analyze.py", "api/index.py", "api/cron/ingest.py"}
)

# --- What is new in 006, and what is the request path ---------------------------------------------

_NEW_006_CODE: tuple[Path, ...] = (
    _REPO_ROOT / "packages" / "knowledge" / "src",
    _REPO_ROOT / "packages" / "core" / "src" / "aoe2stats_core" / "truth",
    _REPO_ROOT / "packages" / "storage" / "src" / "aoe2stats_storage" / "repositories"
    / "knowledge_gaps.py",
    _REPO_ROOT / "scripts" / "checks" / "knowledge_gap_rate.py",
)  # fmt: skip

_ANALYZER_SRC = _REPO_ROOT / "apps" / "analyzer" / "src" / "aoe2stats_analyzer"
_REQUEST_PATH_CODE: tuple[Path, ...] = (
    _REPO_ROOT / "api",
    _REPO_ROOT / "apps" / "api" / "src",
    _ANALYZER_SRC / "claim.py",
    _ANALYZER_SRC / "admission.py",
    _ANALYZER_SRC / "run.py",
    _ANALYZER_SRC / "retain.py",
    # The capture path: constitution I's other side of the tie-break.
    _REPO_ROOT / "apps" / "ingester" / "src",
)

_NEW_PACKAGES = ("aoe2stats_knowledge", "aoe2stats_core.truth")
_CAPTURE_BUDGET_PACKAGES = ("aoe2stats_ingester", "aoe2stats_providers")
_FEATURE_003_PACKAGES = ("aoe2stats_analyzer", "aoe2stats_api", "aoe2stats_ingester")
_CAPTURE_BUDGET_NAMES = (
    "CAPTURE_BUDGET_DAYS",
    "capture_budget_days",
    "capture_deadline_at",
    "replay_captures",
    "ReplayCapture",
    "provider_calls",
    "ProviderCall",
)
_FEATURE_003_VOCABULARY = (
    "lease",
    "claim",
    "admission",
    "admit",
    "retention",
    "retain",
    "ratelimit",
    "rate_limit",
    "dedupe",
    "fetch",
    "erasure",
    "erase",
    "consent",
)

# --- Scheduled units: the line-based workflow extractor -------------------------------------------


@dataclass(frozen=True)
class WorkflowFacts:
    crons: tuple[str, ...]
    jobs: frozenset[str]


_ON_KEY = re.compile(r"""^["']?on["']?:\s*(?P<inline>[^#\n]*)""")
_TOP_KEY = re.compile(r"^[^\s#-]")
_CRON_ITEM = re.compile(r"""^\s*-\s*cron:\s*["']?(?P<cron>[^"'#]+?)["']?\s*(?:#.*)?$""")
_JOB_KEY = re.compile(r"^  (?P<job>[A-Za-z0-9_-]+):\s*(?:#.*)?$")


def parse_workflow(text: str) -> WorkflowFacts:
    """The crons under `on.schedule` and the job ids under `jobs` of one workflow's text."""
    lines = text.splitlines()
    crons: list[str] = []
    jobs: set[str] = set()
    section = ""
    in_schedule = False
    for line in lines:
        if line.lstrip().startswith("#") or not line.strip():
            continue
        if _TOP_KEY.match(line):
            in_schedule = False
            on_match = _ON_KEY.match(line)
            if on_match:
                section = "on"
                if "schedule" in on_match.group("inline"):
                    raise ValueError("flow-style `on:` naming `schedule` is not supported")
            elif line.startswith("jobs:"):
                section = "jobs"
            else:
                section = ""
            continue
        if section == "on":
            if re.match(r"^  schedule:\s*(?:#.*)?$", line):
                in_schedule = True
            elif re.match(r"^  \S", line):
                in_schedule = False
            elif in_schedule:
                cron_match = _CRON_ITEM.match(line)
                if cron_match:
                    crons.append(cron_match.group("cron").strip())
        elif section == "jobs":
            job_match = _JOB_KEY.match(line)
            if job_match:
                jobs.add(job_match.group("job"))
    return WorkflowFacts(crons=tuple(crons), jobs=frozenset(jobs))


def scheduled_workflows(workflows: Mapping[str, str]) -> dict[str, WorkflowFacts]:
    """Workflow file name -> facts, for the workflows that have at least one cron."""
    parsed = {name: parse_workflow(text) for name, text in workflows.items()}
    return {name: facts for name, facts in parsed.items() if facts.crons}


def scheduling_violations(scheduled: Mapping[str, WorkflowFacts]) -> list[str]:
    """Every difference between the scheduled units given and the pre-006 baseline."""
    problems: list[str] = []
    for name, facts in sorted(scheduled.items()):
        if name not in _BASELINE_SCHEDULED_WORKFLOWS:
            problems.append(f"{name}: a new scheduled workflow (crons {list(facts.crons)})")
            continue
        extra_crons = set(facts.crons) - set(_BASELINE_SCHEDULED_WORKFLOWS[name])
        if extra_crons:
            problems.append(f"{name}: new schedule trigger(s) {sorted(extra_crons)}")
        extra_jobs = facts.jobs - _BASELINE_SCHEDULED_JOBS[name]
        if extra_jobs:
            problems.append(f"{name}: new job(s) in a scheduled workflow {sorted(extra_jobs)}")
    for name in sorted(set(_BASELINE_SCHEDULED_WORKFLOWS) - set(scheduled)):
        problems.append(f"{name}: a baseline scheduled workflow lost its schedule or was removed")
    return problems


def vercel_violations(config: Mapping[str, object]) -> list[str]:
    """New cron entries or new function entries in a parsed `vercel.json`."""
    problems: list[str] = []
    raw_crons = config.get("crons", [])
    crons = {
        (str(entry["path"]), str(entry["schedule"]))
        for entry in (raw_crons if isinstance(raw_crons, list) else [])
    }
    for path, schedule in sorted(crons - _BASELINE_VERCEL_CRONS):
        problems.append(f"vercel.json: new cron {path!r} at {schedule!r}")
    raw_functions = config.get("functions", {})
    functions = set(raw_functions) if isinstance(raw_functions, dict) else set()
    for function in sorted(functions - _BASELINE_VERCEL_FUNCTIONS):
        problems.append(f"vercel.json: new function entry {function!r}")
    return problems


def _read_workflows() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in _WORKFLOWS_DIR.glob("*.yml")}


def test_no_scheduled_workflow_or_job_was_added() -> None:
    """FR-049: the set of scheduled workflows, their crons and their job ids is the pre-006 set.

    Deliberately silent about *steps*: T663 adds one step to `nightly.yml`'s existing job to run the
    gap-rate report, which is not a scheduled job.
    """
    problems = scheduling_violations(scheduled_workflows(_read_workflows()))
    assert not problems, f"006 must add no scheduled job (FR-049, 003 FR-044): {problems}"


def test_vercel_json_gained_no_cron_and_no_function() -> None:
    config = json.loads((_REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    problems = vercel_violations(config)
    assert not problems, f"006 must add no cron and no request-path function (FR-049): {problems}"


def test_no_new_api_handler_file_was_added() -> None:
    handlers = {
        path.relative_to(_REPO_ROOT).as_posix()
        for path in (_REPO_ROOT / "api").rglob("*.py")
        if "__pycache__" not in path.parts and path.name != "__init__.py"
    }
    assert handlers == _BASELINE_API_HANDLERS, (
        "api/ holds the request-path handlers; 006 adds none (FR-049). "
        f"Unexpected: {sorted(handlers - _BASELINE_API_HANDLERS)}, "
        f"missing: {sorted(_BASELINE_API_HANDLERS - handlers)}"
    )


# --- Import and name scans over the real tree -----------------------------------------------------


def _python_files(roots: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(files)


def _imported_modules(tree: ast.AST) -> set[str]:
    """Absolute module names a parsed file imports, dotted `from` forms and dynamic imports
    included (see `test_import_graph.py` for why the syntax tree and not a text search)."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            dynamic = (isinstance(func, ast.Name) and func.id == "__import__") or (
                isinstance(func, ast.Attribute) and func.attr == "import_module"
            )
            first = node.args[0]
            if dynamic and isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.add(first.value)
    return found


def _is_under(dotted: str, packages: Iterable[str]) -> bool:
    return any(dotted == p or dotted.startswith(f"{p}.") for p in packages)


def imports_of(source: str, packages: Iterable[str]) -> list[str]:
    modules = _imported_modules(ast.parse(source))
    return sorted(m for m in modules if _is_under(m, packages))


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def capture_budget_mentions(source: str) -> list[str]:
    """Capture-budget names used as code: identifiers, attributes, parameters, keywords and
    non-docstring string constants (SQL text, column names). Prose in docstrings and comments may
    explain the boundary and is not use."""
    tree = ast.parse(source)
    skip = _docstring_nodes(tree)
    mentioned: set[str] = set()
    for node in ast.walk(tree):
        candidates: list[str] = []
        if isinstance(node, ast.Name):
            candidates.append(node.id)
        elif isinstance(node, ast.Attribute):
            candidates.append(node.attr)
        elif isinstance(node, ast.arg) or (isinstance(node, ast.keyword) and node.arg):
            candidates.append(node.arg)
        elif isinstance(node, ast.alias):
            candidates.append(node.name)
        elif (
            isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
        ):
            candidates.append(node.value)
        for text in candidates:
            mentioned.update(name for name in _CAPTURE_BUDGET_NAMES if name in text)
    return sorted(mentioned)


def analysis_key_literals(source: str) -> list[str]:
    """String constants, f-string fragments included, that spell the analysis key layout's prefix.
    Docstrings and comments may name it; code may not, because the layout has one owner."""
    tree = ast.parse(source)
    skip = _docstring_nodes(tree)
    return sorted(
        {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and "analyses/" in node.value
        }
    )


def vocabulary_definitions(source: str) -> list[str]:
    """Top-level function and class names that reuse 003's behaviour vocabulary."""
    tree = ast.parse(source)
    names = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    ]
    return sorted(
        name for name in names if any(word in name.lower() for word in _FEATURE_003_VOCABULARY)
    )


def _violations(
    roots: Iterable[Path], detector: Callable[[str], list[str]]
) -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}
    for path in _python_files(roots):
        found = detector(path.read_text(encoding="utf-8"))
        if found:
            violations[path.relative_to(_REPO_ROOT).as_posix()] = found
    return violations


def test_the_scanned_roots_exist() -> None:
    """A guard over a moved directory scans nothing and passes; refuse that."""
    for root in (*_NEW_006_CODE, *_REQUEST_PATH_CODE):
        assert root.exists(), f"guarded path moved or was removed: {root}"
    assert _python_files(_NEW_006_CODE), "no new-006 source files found"
    assert _python_files(_REQUEST_PATH_CODE), "no request-path source files found"


def test_no_request_path_module_imports_the_new_packages() -> None:
    """FR-049: analysis knowledge and truth types never reach the request path or capture path."""
    violations = _violations(_REQUEST_PATH_CODE, lambda source: imports_of(source, _NEW_PACKAGES))
    assert not violations, (
        f"006 packages must stay off the request/capture path (FR-049): {violations}"
    )


def test_the_document_builder_imports_nothing_from_storage() -> None:
    """T666e: `extract.py` turns a recording into a document and knows no table. The conversion of
    the document's gaps into rows is the run side's (`run.py` may import `packages/storage`), so a
    storage repository type or sentinel never reaches the builder."""
    source = (_ANALYZER_SRC / "extract.py").read_text(encoding="utf-8")

    assert imports_of(source, ("aoe2stats_storage",)) == []


def test_the_analysis_key_layout_is_written_in_the_storage_package_only() -> None:
    """T666e: `contracts/analysis-document.md` names `packages/storage` as the owner of the key
    layout. The analyzer asks `analysis_object_key` for a key and `read_analysis` for an object; a
    second spelling of the prefix in `apps/analyzer` is a second layout waiting to drift."""
    violations = _violations((_ANALYZER_SRC,), analysis_key_literals)

    assert not violations, f"the analysis key layout belongs to packages/storage: {violations}"


def test_new_code_does_not_use_the_capture_budget() -> None:
    """FR-049, 003 FR-039: nothing 006 added reads, spends or imports the capture budget."""
    by_name = _violations(_NEW_006_CODE, capture_budget_mentions)
    by_import = _violations(
        _NEW_006_CODE, lambda source: imports_of(source, _CAPTURE_BUDGET_PACKAGES)
    )
    assert not by_name, f"006 code must not name the capture budget (FR-049): {by_name}"
    assert not by_import, f"006 code must not import the budget's homes (FR-049): {by_import}"


def test_new_code_does_not_restate_003() -> None:
    """FR-048: no import of 003's packages and no definition under 003's behaviour vocabulary."""
    by_import = _violations(_NEW_006_CODE, lambda source: imports_of(source, _FEATURE_003_PACKAGES))
    by_name = _violations(_NEW_006_CODE, vocabulary_definitions)
    assert not by_import, f"006 must build on 003, not import into it (FR-048): {by_import}"
    assert not by_name, f"006 must not re-specify 003's behaviour (FR-048): {by_name}"


# --- Contrast cases: the same detectors against input built to violate each rule -----------------

_NIGHTLY_SHAPED = """\
name: Nightly watchtower
on:
  schedule:
    - cron: "0 3 * * *"
  workflow_dispatch:
jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - run: echo one
  report:
    runs-on: ubuntu-latest
"""


def test_parse_workflow_reads_crons_and_jobs() -> None:
    facts = parse_workflow(_NIGHTLY_SHAPED)
    assert facts.crons == ("0 3 * * *",)
    assert facts.jobs == frozenset({"contracts", "report"})


def test_the_real_nightly_workflow_parses_to_the_recorded_baseline() -> None:
    """Self-check of the extractor: it finds exactly the baseline on the real file, so a green
    scheduling test is not an extractor that finds nothing."""
    facts = parse_workflow((_WORKFLOWS_DIR / "nightly.yml").read_text(encoding="utf-8"))
    assert facts.crons == _BASELINE_SCHEDULED_WORKFLOWS["nightly.yml"]
    assert facts.jobs >= _BASELINE_SCHEDULED_JOBS["nightly.yml"]


def test_a_new_step_in_an_existing_scheduled_job_is_allowed() -> None:
    """T663's shape: the real `nightly.yml` plus one more step at the end of its last job. No new
    job and no new trigger, so the scheduled-unit set is unchanged and nothing is flagged."""
    real = (_WORKFLOWS_DIR / "nightly.yml").read_text(encoding="utf-8")
    step = "\n      - run: uv run scripts/checks/knowledge_gap_rate.py\n"
    with_step = real.rstrip("\n") + step
    assert scheduling_violations(scheduled_workflows({"nightly.yml": with_step})) == []


def test_the_gap_rate_step_cannot_turn_the_capture_audit_red() -> None:
    """T666f: the gap-rate report shares a job with the capture audit, and constitution I outranks
    a report - so a report that cannot run (a missing table, a connection blip) must not fail the
    job. Pinned on the real file: the step carries `continue-on-error: true` and keeps `always()`.
    """
    real = (_WORKFLOWS_DIR / "nightly.yml").read_text(encoding="utf-8")
    start = real.index("      - name: Report the knowledge-gap rate")
    step = real[start : real.index("\n\n", start)]
    assert "run: uv run scripts/checks/knowledge_gap_rate.py" in step
    assert "        continue-on-error: true" in step.splitlines()
    assert "if: always()" in step


def test_an_extra_schedule_on_an_existing_workflow_is_flagged() -> None:
    synthetic = {
        "nightly.yml": WorkflowFacts(
            crons=("0 3 * * *", "*/15 * * * *"),
            jobs=_BASELINE_SCHEDULED_JOBS["nightly.yml"],
        )
    }
    problems = scheduling_violations(synthetic)
    assert problems and "*/15 * * * *" in problems[0]


def test_a_new_scheduled_workflow_is_flagged() -> None:
    text = "on:\n  schedule:\n    - cron: '5 * * * *'\njobs:\n  analyse:\n    runs-on: x\n"
    scheduled = scheduled_workflows({"nightly.yml": _NIGHTLY_SHAPED, "analysis.yml": text})
    problems = scheduling_violations(scheduled)
    assert any(
        "analysis.yml" in problem and "new scheduled workflow" in problem for problem in problems
    )


def test_a_new_job_in_a_scheduled_workflow_is_flagged() -> None:
    synthetic = {
        "nightly.yml": WorkflowFacts(
            crons=_BASELINE_SCHEDULED_WORKFLOWS["nightly.yml"],
            jobs=_BASELINE_SCHEDULED_JOBS["nightly.yml"] | {"analysis-sweep"},
        )
    }
    assert any("analysis-sweep" in problem for problem in scheduling_violations(synthetic))


def test_a_removed_schedule_is_flagged_as_baseline_drift() -> None:
    assert scheduling_violations({}) != []


def test_a_flow_style_schedule_is_refused_not_guessed() -> None:
    try:
        parse_workflow("on: { schedule: [{cron: '* * * * *'}] }\n")
    except ValueError:
        return
    raise AssertionError("a flow-style `on:` naming `schedule` must be refused")


def test_vercel_violations_flag_a_new_cron_and_a_new_function() -> None:
    config: dict[str, object] = {
        "crons": [
            {"path": "/api/cron/ingest", "schedule": "0 4 * * *"},
            {"path": "/api/cron/analyse", "schedule": "0 5 * * *"},
        ],
        "functions": {"api/cron/ingest.py": {}, "api/sweep.py": {}},
    }
    problems = vercel_violations(config)
    assert any("/api/cron/analyse" in problem for problem in problems)
    assert any("api/sweep.py" in problem for problem in problems)


def test_vercel_violations_accept_the_baseline() -> None:
    config: dict[str, object] = {
        "crons": [{"path": "/api/cron/ingest", "schedule": "0 4 * * *"}],
        "functions": {name: {} for name in _BASELINE_VERCEL_FUNCTIONS},
    }
    assert vercel_violations(config) == []


def test_imports_of_finds_every_import_form_of_a_new_package() -> None:
    for source in (
        "import aoe2stats_knowledge\n",
        "import aoe2stats_knowledge.query as q\n",
        "from aoe2stats_knowledge import query\n",
        "from aoe2stats_core.truth import tiers\n",
        "from aoe2stats_core.truth.tiers import Tier\n",
        "import importlib\nimportlib.import_module('aoe2stats_knowledge')\n",
        "__import__('aoe2stats_core.truth')\n",
    ):
        assert imports_of(source, _NEW_PACKAGES), source


def test_imports_of_does_not_flag_sibling_core_modules_or_lookalikes() -> None:
    assert imports_of("from aoe2stats_core.replay import analysis\n", _NEW_PACKAGES) == []
    assert imports_of("import aoe2stats_core\n", _NEW_PACKAGES) == []
    assert imports_of("import aoe2stats_knowledge_other\n", _NEW_PACKAGES) == []


def test_imports_of_flags_a_storage_repository_type_in_the_builder() -> None:
    """The contrast to the builder test: the shape it forbids is detected."""
    source = (
        "from aoe2stats_storage.repositories.knowledge_gaps import GapToRecord\n"
        "import aoe2stats_storage.models\n"
    )

    assert imports_of(source, ("aoe2stats_storage",)) == [
        "aoe2stats_storage.models",
        "aoe2stats_storage.repositories.knowledge_gaps",
        "aoe2stats_storage.repositories.knowledge_gaps.GapToRecord",
    ]


def test_analysis_key_literals_flags_a_private_layout_but_not_prose() -> None:
    assert analysis_key_literals('def key(g, d):\n    return f"analyses/{g}/{d}.json"\n') == [
        "analyses/"
    ]
    assert analysis_key_literals('def f():\n    """Reads `analyses/1/x.json`."""\n') == []
    assert analysis_key_literals("# analyses/1/x.json\nx = 1\n") == []


def test_capture_budget_mentions_flags_code_use_but_not_prose() -> None:
    assert capture_budget_mentions("x = settings.capture_budget_days\n") == ["capture_budget_days"]
    assert capture_budget_mentions("def f(capture_deadline_at): ...\n") == ["capture_deadline_at"]
    assert capture_budget_mentions("q = 'SELECT 1 FROM replay_captures'\n") == ["replay_captures"]
    assert capture_budget_mentions("from m import ReplayCapture\n") == ["ReplayCapture"]
    assert capture_budget_mentions('"""Never touches CAPTURE_BUDGET_DAYS."""\nx = 1\n') == []
    assert capture_budget_mentions("# capture_budget_days\nx = 1\n") == []


def test_vocabulary_definitions_flag_a_restated_003_behaviour() -> None:
    assert vocabulary_definitions("def claim_for_analysis(): ...\n") == ["claim_for_analysis"]
    assert vocabulary_definitions("class RateLimiter: ...\n") == ["RateLimiter"]
    assert vocabulary_definitions("class Retention: ...\n") == ["Retention"]
    assert vocabulary_definitions("def lookup(): ...\n") == []
