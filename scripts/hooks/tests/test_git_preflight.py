"""Tests for `scripts/hooks/git-preflight.sh` judging the repository a command acts on (T735).

The hook used to `cd` to the project directory, which from a `.claude/worktrees/<name>` session is
the main checkout. On 2026-10-17 the main checkout sat on another session's branch one commit behind
`origin/main`, and the hook refused every commit of a worktree branch that was level with it, while
an inline `NO_GIT_PREFLIGHT=1` could not reach the hook's own environment.

Every test below runs the real hook against a planted layout: a bare `origin`, a main checkout on a
branch one commit behind `origin/main`, and two worktrees under its `.claude/worktrees/` — one cut
from `origin/main` (fresh), one from the commit before it (stale). The hook is given the main
checkout as its project directory and its working directory, as Claude Code gives it, and the
payload's `cwd` is the shell the command would run in.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "git-preflight.sh"


# The layout is module-scoped, so it is built before any function-scoped fixture could set an
# identity; and a CI runner has no global one. Each call carries its own, and signing is off so a
# user's signing configuration cannot fail the planted commits either.
_IDENTITY = {
    f"{role}_{field}": value
    for role in ("GIT_AUTHOR", "GIT_COMMITTER")
    for field, value in (("NAME", "Preflight Test"), ("EMAIL", "preflight@example.invalid"))
}


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        env={**os.environ, **_IDENTITY},
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def layout(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("preflight")
    origin = root / "origin.git"
    main = root / "main"
    _git("init", "--quiet", "--bare", "-b", "main", str(origin), cwd=root)
    _git("clone", "--quiet", str(origin), str(main), cwd=root)
    for name in ("first", "second"):
        _git("commit", "--quiet", "--allow-empty", "-m", name, cwd=main)
        _git("push", "--quiet", "origin", "HEAD:main", cwd=main)
    behind = _git("rev-parse", "HEAD~1", cwd=main)
    # The main checkout is on someone else's branch, one commit behind `origin/main`.
    _git("switch", "--quiet", "-c", "other-session", behind, cwd=main)
    worktrees = main / ".claude" / "worktrees"
    fresh, stale = worktrees / "fresh", worktrees / "stale"
    _git("worktree", "add", "--quiet", "-b", "fresh", str(fresh), "origin/main", cwd=main)
    _git("worktree", "add", "--quiet", "-b", "stale", str(stale), behind, cwd=main)
    return {"main": main, "fresh": fresh, "stale": stale}


@pytest.fixture(autouse=True)
def _no_ambient_escape_hatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_GIT_PREFLIGHT", raising=False)


def _run(command: str, cwd: Path | None, main: Path) -> subprocess.CompletedProcess[str]:
    payload: dict[str, object] = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        cwd=main,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(main)},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_a_fresh_worktree_commits_while_the_main_checkout_is_behind(layout: dict[str, Path]):
    result = _run("git commit -m x", layout["fresh"], layout["main"])
    assert result.returncode == 0, result.stderr


def test_a_stale_worktree_is_still_refused(layout: dict[str, Path]):
    result = _run("git commit -m x", layout["stale"], layout["main"])
    assert result.returncode == 2
    assert "1 commit(s) behind origin/main" in result.stderr


def test_a_stale_worktree_push_is_refused_before_the_suite_runs(layout: dict[str, Path]):
    result = _run("git push -u origin HEAD", layout["stale"], layout["main"])
    assert result.returncode == 2
    assert "behind origin/main" in result.stderr


def test_the_inline_escape_hatch_reaches_the_hook(layout: dict[str, Path]):
    result = _run("NO_GIT_PREFLIGHT=1 git commit -m x", layout["stale"], layout["main"])
    assert result.returncode == 0, result.stderr


def test_an_exported_escape_hatch_reaches_the_hook(layout: dict[str, Path]):
    command = "export NO_GIT_PREFLIGHT=1 && git commit -m x"
    assert _run(command, layout["stale"], layout["main"]).returncode == 0


def test_the_escape_hatch_on_another_command_does_not_reach_git(layout: dict[str, Path]):
    # Under the shell this assignment is `true`'s environment, not git's.
    command = "NO_GIT_PREFLIGHT=1 true && git commit -m x"
    assert _run(command, layout["stale"], layout["main"]).returncode == 2


def test_the_escape_hatch_covers_only_the_invocation_it_prefixes(layout: dict[str, Path]):
    command = "NO_GIT_PREFLIGHT=1 git commit -m x && git push"
    assert _run(command, layout["stale"], layout["main"]).returncode == 2


@pytest.mark.parametrize(
    ("command", "cwd", "expected"),
    [
        ("cd {stale} && git commit -m x", "fresh", 2),
        ("cd {fresh} && git commit -m x", "stale", 0),
        ("cd ../stale && git commit -m x", "fresh", 2),
        ("cd ../fresh; git commit -m x", "stale", 0),
        ("git -C {stale} commit -m x", "fresh", 2),
        ("git -C {fresh} commit -m x", "stale", 0),
        ("git -C ../stale -c core.quotepath=off commit -m x", "fresh", 2),
    ],
)
def test_a_cd_or_git_dash_c_in_the_command_picks_the_repository(
    layout: dict[str, Path], command: str, cwd: str, expected: int
):
    command = command.format(stale=layout["stale"], fresh=layout["fresh"])
    assert _run(command, layout[cwd], layout["main"]).returncode == expected


def test_a_commit_the_parser_cannot_see_is_still_checked(layout: dict[str, Path]):
    assert _run('bash -c "git commit -m x"', layout["stale"], layout["main"]).returncode == 2


def test_a_command_shlex_cannot_split_is_checked_where_it_runs(layout: dict[str, Path]):
    # An unquoted heredoc with an apostrophe in it: an unbalanced quote to `shlex`.
    command = "git commit -F - <<EOF\nit's a message\nEOF"
    assert _run(command, layout["stale"], layout["main"]).returncode == 2
    assert _run(command, layout["fresh"], layout["main"]).returncode == 0
    assert (
        _run(f"cd {layout['stale']} && {command}", layout["fresh"], layout["main"]).returncode == 2
    )


def test_a_payload_without_cwd_falls_back_to_the_project_directory(layout: dict[str, Path]):
    # The main checkout is on a branch behind `origin/main`, so the fallback is visibly in use.
    assert _run("git commit -m x", None, layout["main"]).returncode == 2


def test_a_command_that_is_not_a_commit_or_push_is_never_checked(layout: dict[str, Path]):
    assert _run("git status && git log -1", layout["stale"], layout["main"]).returncode == 0
