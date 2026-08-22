#!/usr/bin/env python3
"""Mechanical consistency lint over a Spec-Kit feature directory.

Everything here was once found by hand, pass after pass, and found a different subset each time.
A hand pass over prose samples; a script scans. So each class of defect below is settled here once
and never re-derived by `/speckit-analyze`, which spends its budget on judgment instead.

The rule this file exists to enforce, from CLAUDE.md: a number, a path or a name that lives in two
places will eventually be wrong in one of them.

Run: uv run scripts/checks/spec_lint.py --feature specs/001-steam-link-replay-ingestion
Exit: 0 clean, 1 on any failure. Stdlib only, so it needs no environment.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Uppercase tokens that look like configuration but are not application configuration, and so are
# not expected in .env.example. The scan cannot tell a module constant from an environment key —
# both are ALL_CAPS in backticks — so a task that names one by its real identifier lands here
# rather than being reworded around the regex (T004a records why the prose stays as written).
ENV_TOKEN_ALLOWLIST = {
    "PYTEST_DISABLE_NETWORK",
    # `aoe2stats_ingester.run.DEFAULT_STAGES`, named by T060 because its staying `()` is the gap
    # that task closed.
    "DEFAULT_STAGES",
}

# The section of .env.example whose keys tune behaviour rather than describe infrastructure. Each of
# these must be named by the task that consumes it: a task that states the value instead of the key
# is a task that tells an implementer to hard-code it.
BEHAVIOURAL_SECTION = "Ingestion tuning"

UNIT_WORDS = {
    "DAYS": r"days?",
    "HOURS": r"hours?",
    "SECONDS": r"seconds?",
    "SECOND": r"per\s+second",
}

failures: list[str] = []
notes: list[str] = []


def fail(check: str, message: str) -> None:
    failures.append(f"{check}: {message}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# --------------------------------------------------------------------------- plan.md tree parsing


def declared_tree_paths(plan_text: str) -> set[str]:
    """Reconstruct full paths from the ASCII tree in plan.md's Source Code section."""
    paths: set[str] = set()
    for block in re.findall(r"```text\n(.*?)```", plan_text, re.DOTALL):
        stack: list[tuple[int, str]] = []
        for raw in block.splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip() or set(line.strip()) <= {"│", " "}:
                continue
            match = re.search(r"[├└]── ", line)
            if match:
                depth = match.start() // 4 + 1
                name = line[match.end() :].strip()
            else:
                depth = 0
                name = line.strip()
            if not name or name.startswith(("│", "├", "└")):
                continue
            stack = stack[:depth]
            stack.append((depth, name.rstrip("/")))
            paths.add("/".join(part for _, part in stack))
    return paths


# ------------------------------------------------------------------------------ path extraction

PATH_RE = re.compile(r"`([A-Za-z0-9_.\-$]+(?:/[A-Za-z0-9_.\-$*]+)+/?)`")


def paths_in(text: str) -> set[str]:
    found = set()
    for token in PATH_RE.findall(text):
        if token.startswith(("http", "/")) or token.startswith("api/(") or "(" in token:
            continue
        found.add(token.rstrip("/"))
    return found


def has_extension(path: str) -> bool:
    return "." in path.rsplit("/", 1)[-1]


# ------------------------------------------------------------------------------------- the checks


def check_requirement_coverage(spec: str, tasks: str) -> None:
    defined = set(re.findall(r"\*\*(FR-\d+|SC-\d+)\*\*:", spec))
    if not defined:
        fail("requirement-coverage", "no FR-/SC- definitions found in spec.md")
        return
    missing = sorted(key for key in defined if key not in tasks)
    for key in missing:
        fail("requirement-coverage", f"{key} is defined in spec.md but named by no task")
    notes.append(
        f"requirement-coverage: {len(defined) - len(missing)}/{len(defined)} "
        "requirements named by a task"
    )


def _task_number(key: str) -> int:
    """The numeric part of a task id (`T061a` -> `61`), for sorting and gap detection.

    `key` is only ever a value already matched by `T\\d+[a-z]?` (`check_task_references`'s own
    `defined` set), so the leading digits are always present — the assert documents that
    invariant instead of asking mypy to trust an `Optional` that can never actually be `None`.
    """
    match = re.match(r"T(\d+)", key)
    assert match is not None, f"malformed task id {key!r}"
    return int(match.group(1))


def check_task_references(feature_dir: Path, tasks: str) -> None:
    defined = set(re.findall(r"^- \[[ x]\] (T\d+[a-z]?)", tasks, re.MULTILINE))
    if not defined:
        fail("task-refs", "no task definitions found in tasks.md")
        return
    referenced: set[str] = set()
    for path in sorted(feature_dir.rglob("*.md")):
        for match in re.findall(r"\bT\d+[a-z]?\b", read(path)):
            referenced.add(match)
    for key in sorted(referenced - defined):
        fail("task-refs", f"{key} is referenced but defined by no task")
    numbers = sorted({_task_number(key) for key in defined})
    gaps = [n for n in range(numbers[0], numbers[-1] + 1) if n not in numbers]
    if gaps:
        notes.append(
            "task-refs: unreferenced numbering gaps "
            + ", ".join(f"T{n:03d}" for n in gaps)
            + " (harmless; renumbering would break cross-references)"
        )


def check_path_roots(tasks: str, tree: set[str]) -> None:
    roots = {"/".join(p.split("/")[:2]) for p in tree if "/" in p}
    roots |= {p for p in tree if "/" not in p}
    for path in sorted(paths_in(tasks)):
        if (REPO / path).exists() or (REPO / path).parent.exists():
            continue
        root = "/".join(path.split("/")[:2])
        if root in roots or path in tree:
            continue
        fail("path-roots", f"{path} is under no root declared in plan.md and no directory on disk")


def check_path_collisions(sources: dict[str, str], tree: set[str]) -> None:
    """The same directory declared in two places, which is how plan.md and tasks.md drift apart.

    plan.md declares its structure as an ASCII tree rather than as backticked paths, so the tree has
    to be reconstructed and fed in here explicitly. Comparing only backticked paths would leave the
    one artifact that defines the layout out of the comparison.
    """
    groups: dict[tuple[str, str], dict[str, set[str]]] = {}
    for name, text in {**sources, "plan.md (tree)": ""}.items():
        for path in tree if name == "plan.md (tree)" else paths_in(text):
            if has_extension(path) or "/" not in path:
                continue
            segments = path.split("/")
            key = ("/".join(segments[:2]), segments[-1])
            groups.setdefault(key, {}).setdefault(path, set()).add(name)
    for (prefix, leaf), variants in sorted(groups.items()):
        if len(variants) > 1:
            rendered = "; ".join(
                f"{path} (in {', '.join(sorted(where))})"
                for path, where in sorted(variants.items())
            )
            fail(
                "path-collisions",
                f"'{leaf}' under {prefix} is declared as {len(variants)} "
                f"different paths: {rendered}",
            )


def check_alert_kinds(data_model: str, tasks: str) -> None:
    enum_match = re.search(r"`kind` \(enum: (.+?)\)", data_model, re.DOTALL)
    if not enum_match:
        fail("alert-kinds", "no `kind` enum found in data-model.md")
        return
    canonical = set(re.findall(r"`([a-z_]+)`", enum_match.group(1)))
    producers = {
        kind: task
        for task, kind in re.findall(r"(T\d+[a-z]?) `([a-z_]+)`", data_model)
        if kind in canonical
    }
    for kind in sorted(canonical - set(producers)):
        fail("alert-kinds", f"`{kind}` is in the enum but data-model.md names no producing task")
    task_bodies = dict(re.findall(r"^- \[[ x]\] (T\d+[a-z]?) (.+)$", tasks, re.MULTILINE))
    for kind, task in sorted(producers.items()):
        if task not in task_bodies:
            fail("alert-kinds", f"`{kind}` names producer {task}, which is defined by no task")
        elif kind not in task_bodies[task]:
            fail(
                "alert-kinds", f"`{kind}` names producer {task}, whose task text never mentions it"
            )
    for kind in sorted(set(re.findall(r"severity-\d `([a-z_]+)`", tasks)) - canonical):
        fail("alert-kinds", f"tasks.md raises `{kind}`, which is not in data-model.md's enum")
    notes.append(f"alert-kinds: {len(canonical)} kinds, each with a declared producer")


def parse_env(env_text: str) -> tuple[dict[str, str], set[str]]:
    values: dict[str, str] = {}
    behavioural: set[str] = set()
    in_section = False
    for line in env_text.splitlines():
        if line.startswith("# ---"):
            in_section = BEHAVIOURAL_SECTION in line
        if match := re.match(r"^([A-Z][A-Z0-9_]+)=(.*)$", line):
            values[match.group(1)] = match.group(2).strip()
            if in_section:
                behavioural.add(match.group(1))
    return values, behavioural


def check_env(
    sources: dict[str, str], tasks: str, env_values: dict[str, str], behavioural: set[str]
) -> None:
    used: set[str] = set()
    for text in sources.values():
        used |= set(re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", text))
    for token in sorted(used - set(env_values) - ENV_TOKEN_ALLOWLIST):
        fail("env-declared", f"{token} is used by an artifact but declared in no .env.example key")
    for key in sorted(behavioural):
        if key not in tasks:
            fail(
                "env-consumed",
                f"{key} tunes behaviour but is named by no task, so nothing reads it",
            )
    notes.append(f"env: {len(behavioural)} behavioural keys, {len(env_values)} keys total")


def check_literals(
    sources: dict[str, str], env_values: dict[str, str], behavioural: set[str]
) -> None:
    """A behavioural constant restated as a literal tells the implementer to hard-code it.

    Scoped to the two artifacts an implementer reads as instructions — tasks.md and data-model.md.
    spec.md and plan.md restate constraints in prose deliberately, where the constraint governs a
    decision, and CLAUDE.md says that is correct.
    """
    patterns = []
    for key in sorted(behavioural):
        value = env_values[key].strip()
        if not value.isdigit():
            continue
        suffix = key.rsplit("_", 1)[-1]
        unit = UNIT_WORDS.get(suffix)
        if unit is None:
            continue
        patterns.append((key, re.compile(rf"\b{value}[\s-]+(?:\w+\s+){{0,2}}{unit}\b")))
    for name in ("tasks.md", "data-model.md"):
        for number, line in enumerate(sources.get(name, "").splitlines(), start=1):
            header = re.match(r"^- \[[ x]\] (T\d+[a-z]?) ", line)
            where = f"{name} {header.group(1)}" if header else f"{name}:{number}"
            for key, pattern in patterns:
                if (match := pattern.search(line)) and key not in line:
                    fail(
                        "literals",
                        f"{where} states '{match.group(0)}' as a literal; it is the value "
                        f"of {key} and must be read from it",
                    )


def check_register_commitments(tasks: str) -> None:
    """Every launch item in the processing register names who delivers it, or is out of scope.

    The register is the one file in the field of view whose content is a list of promises rather
    than a description, and three separate findings came from it: a category declared after being
    removed, a procedure promised and never written, a form promised and never built. Prose cannot
    keep a promise; a reference to a task can be checked.
    """
    register = REPO / "docs/privacy/processing-register.md"
    if not register.is_file():
        return
    defined = set(re.findall(r"^- \[[ x]\] (T\d+[a-z]?)", tasks, re.MULTILINE))
    for line in read(register).splitlines():
        item = re.match(r"^- \[([ x])\] (.+)$", line.strip())
        if not item:
            continue
        text = item.group(2)
        named = set(re.findall(r"\bT\d+[a-z]?\b", text))
        if not named and "out of scope" not in text.lower():
            fail(
                "register-commitments",
                f"launch item names no task and is not marked out of scope: {text[:80]!r}",
            )
            continue
        for task in sorted(named - defined):
            fail(
                "register-commitments",
                f"launch item names {task}, which this feature does not define",
            )
    notes.append(
        "register-commitments: every launch item is delivered by a named task or out of scope"
    )


def report_field_of_view(tasks: str) -> None:
    existing = sorted(p for p in paths_in(tasks) if (REPO / p).exists())
    if existing:
        notes.append(
            "field-of-view: tasks amend "
            f"{len(existing)} file(s) that already exist and must be read before analysis — "
            + ", ".join(existing)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True, help="path to the specs/NNN-*/ directory")
    args = parser.parse_args()

    feature_dir = (REPO / args.feature).resolve()
    if not feature_dir.is_dir():
        print(f"no such feature directory: {feature_dir}", file=sys.stderr)
        return 2

    spec = read(feature_dir / "spec.md")
    plan = read(feature_dir / "plan.md")
    tasks = read(feature_dir / "tasks.md")
    data_model = read(feature_dir / "data-model.md")
    env_text = read(REPO / ".env.example")

    for name, text in (("spec.md", spec), ("plan.md", plan), ("tasks.md", tasks)):
        if not text:
            print(f"missing required artifact: {name}", file=sys.stderr)
            return 2

    sources = {"spec.md": spec, "plan.md": plan, "tasks.md": tasks, "data-model.md": data_model}
    for contract in sorted((feature_dir / "contracts").glob("*.md")):
        sources[f"contracts/{contract.name}"] = read(contract)

    env_values, behavioural = parse_env(env_text)
    tree = declared_tree_paths(plan)

    check_requirement_coverage(spec, tasks)
    check_task_references(feature_dir, tasks)
    check_path_roots(tasks, tree)
    check_path_collisions(sources, tree)
    check_alert_kinds(data_model, tasks)
    check_env(sources, tasks, env_values, behavioural)
    check_literals(sources, env_values, behavioural)
    check_register_commitments(tasks)
    report_field_of_view(tasks)

    print(f"spec_lint: {feature_dir.relative_to(REPO)}\n")
    for note in notes:
        print(f"  note  {note}")
    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        print(f"\n{len(failures)} failure(s).")
        return 1
    print("\nclean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
