"""Which repositories a Bash command will commit in or push from, for `git-preflight.sh` (T735).

Reads the PreToolUse payload on stdin and prints one line per `git commit` or `git push` the command
carries: `<kind>\t<bypass>\t<directory>`, where kind is `commit` or `push`, bypass is `1` when that
invocation carries the escape hatch, and directory is where git will run.

The directory starts at the payload's `cwd` — the shell the command runs in, which is a worktree
when the session is in one — and follows every `cd`/`pushd` before the invocation and every
`git -C`. The hook used to `cd` to the project directory instead, which from a
`.claude/worktrees/<name>` session is the main checkout: on 2026-10-17 it refused every commit of a
branch level with `origin/main` because the main checkout was on another branch one commit behind.

The escape hatch is an environment assignment the shell would give the git process itself — a
`NO_GIT_PREFLIGHT=1` prefix on the same simple command, or an earlier `export NO_GIT_PREFLIGHT=1`.
The hook runs before the command, so an inline assignment never reaches its own environment; it has
to be read from the command text. A prefix on some other command (`NO_GIT_PREFLIGHT=1 true && git
commit`) does not reach git under the shell either, and does not bypass here.

Safe error direction: over-check. Detection is the hook's original regex, applied per simple
command, plus a direct read of git's own options, so a commit hidden where this parser cannot see
git (`bash -c "git commit"`, a commit message quoting `git push`) is still checked, in the
directory the parser had reached. A command `shlex` cannot split (an unquoted heredoc holding an
apostrophe) is checked as one piece in the payload's `cwd`, after a leading `cd <dir> &&` only.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass

# The hook's original detector, unchanged: a `git` word, any leading options, then the subcommand.
# Kept for what the parser cannot see; `_git_invocation` adds what this one misses.
_DETECT = {
    kind: re.compile(rf"(^|[;&|]|\s)git\s+(-[^ ]+\s+)*{kind}(\s|$)") for kind in ("commit", "push")
}
_SEPARATORS = {"&&", "||", ";", "|", "&", "\n", ";;", "|&"}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_BYPASS = "NO_GIT_PREFLIGHT=1"
# git's global options that consume the next word.
_GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


@dataclass(frozen=True)
class Target:
    kind: str
    bypass: bool
    directory: str

    def line(self) -> str:
        return f"{self.kind}\t{int(self.bypass)}\t{self.directory}"


def _resolve(base: str, path: str) -> str:
    path = os.path.expanduser(os.path.expandvars(path))
    return os.path.normpath(os.path.join(base, path))


def _segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    segments: list[list[str]] = [[]]
    for token in lexer:
        if token in _SEPARATORS or token in {"(", ")"}:
            segments.append([])
        else:
            segments[-1].append(token)
    return [s for s in segments if s]


def _git_invocation(words: list[str], cwd: str) -> tuple[str, str] | None:
    """The subcommand and directory of a direct `git ... commit|push`, or None if not one."""
    if not words or words[0] != "git":
        return None
    directory = cwd
    i = 1
    while i < len(words) and words[i].startswith("-"):
        option = words[i]
        if option == "-C" and i + 1 < len(words):
            directory = _resolve(directory, words[i + 1])
        if option in _GIT_OPTS_WITH_VALUE:
            i += 2
        else:
            i += 1
    if i < len(words) and words[i] in {"commit", "push"}:
        return words[i], directory
    return None


def targets(command: str, cwd: str) -> list[Target]:
    try:
        segments = _segments(command)
    except ValueError:
        return _fallback(command, cwd)

    found: list[Target] = []
    exported = False
    for tokens in segments:
        assignments = []
        while tokens and _ASSIGNMENT.match(tokens[0]):
            assignments.append(tokens[0])
            tokens = tokens[1:]
        if not tokens:
            continue
        head = tokens[0]
        if head in {"cd", "pushd"}:
            args = [t for t in tokens[1:] if not t.startswith("-")]
            if not args:
                cwd = os.path.expanduser("~")
            elif args[0] != "-":
                cwd = _resolve(cwd, args[0])
            continue
        if head == "export" and _BYPASS in tokens[1:]:
            exported = True
            continue
        text = " ".join(tokens)
        kinds = [kind for kind, pattern in _DETECT.items() if pattern.search(text)]
        directory = cwd
        direct = _git_invocation(tokens, cwd)
        if direct:
            # The regex alone misses `git -C <dir> commit` and `git -c k=v push`: an option's value
            # is not itself an option, so the old hook let both through unchecked.
            kind, directory = direct
            if kind not in kinds:
                kinds.append(kind)
        bypass = exported or _BYPASS in assignments
        found.extend(Target(kind, bypass, directory) for kind in kinds)
    return found


def _fallback(command: str, cwd: str) -> list[Target]:
    leading_cd = re.match(r"\s*cd\s+(\S+)\s*(&&|;|\n)", command)
    if leading_cd:
        cwd = _resolve(cwd, leading_cd.group(1).strip("'\""))
    bypass = re.match(rf"\s*{_BYPASS}\s", command) is not None
    return [
        Target(kind, bypass, cwd) for kind, pattern in _DETECT.items() if pattern.search(command)
    ]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    for target in targets(command, cwd):
        print(target.line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
