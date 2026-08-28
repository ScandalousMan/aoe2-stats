---
name: implementer-dispatch
description: How to dispatch the implementer agent — writing a test-first task against the green-tree gate, running a parallel [P] batch without agents overwriting each other, and remediating a review finding so the fix and its test do not drift together. Load before dispatching any implementer, inside /speckit-implement or outside it.
---

# Dispatching an `implementer`

**One task in `tasks.md` is one `implementer` invocation** ([`CLAUDE.md`](../../../CLAUDE.md)).
`/speckit-implement` orchestrates and does not write code itself: the `SubagentStop` hook matches
`implementer` and refuses a hand-back on red tests, so code written outside an agent never meets that
gate.

Everything below was measured on this project. The costs are kept because they are what make each
rule worth the extra sentence in a dispatch.

## Test-first tasks and the green-tree gate

A test task's own instruction ("write it, watch it fail") and the `SubagentStop` gate ("no red
hand-back") contradict each other head-on. Resolve it with `@pytest.mark.xfail(strict=True,
reason="<implementing task id> not implemented yet")`, never with a skip.

The test body runs with every assertion intact, the expected failure keeps the suite green, and
`strict=True` turns the run red the moment the implementation makes it pass — which forces the marker
off instead of letting a stale `xfail` hide a regression. Import the not-yet-existent module _inside_
the test body: a module-scope import of a missing module is a collection error that takes the whole
workspace suite down with it.

`pytest.importorskip` is the wrong tool here and was tried first. A skipped test proves nothing while
reporting green — the same fault T015a was written to close — and six of the seven Phase 3 test agents
reached for it independently under gate pressure. That is a property of the squeeze, not of the
agents: **expect the next batch to reach for it too unless the dispatch says otherwise.**

## Dispatching a parallel `[P]` batch

Every dispatch tells the agent: **do not modify a file outside your task's named paths.** If the
shared gate fails because of a sibling's file, report it and hand back — do not fix it.

Agents in a `[P]` batch share one working tree and cannot see each other's work, so an agent that
"helpfully" repairs a neighbour's file silently overwrites work from a task it knows nothing about.
Not hypothetical: it cost four files' worth of rework in the Phase 3 test batch, and was caught only
because one agent noticed its own file being rewritten underneath it and said so.

## Remediating a review finding

A fix and the test that proves it are written in the same breath, by the same agent, from the same
sentence describing the bug. So the test covers exactly the sub-case the fix covers — and the residue
is invisible, because the suite is green and the finding is marked closed.

003's Phase 3 took three review rounds on one defect for this reason. The source was reported as
returning an outage that read as "no player found". Round 1 made the circuit breaker survive the
request, and its test asserted the breaker was shared. Round 2 found the breaker's threshold is 3, so
the first two failures of every outage still cached a confident empty — and round 1's test had driven
both of those requests while asserting only `status_code == 200`. Round 2 fixed the shape-drift check
at the envelope; round 3 found the same inversion one level down, where every _record_ fails to parse
and the envelope is intact. Each round's test drifted exactly the key its own fix handled.

So, when dispatching a remediation:

- **Say what the test must fail against, and require the failure output in the hand-back.** A
  regression test that passes before the fix proves nothing, and it is the normal result of writing
  both at once.
- **Ask for the contrast case, not just the reproduction.** "All records unparseable is drift" is only
  half a claim; "one bad record among good ones is still dropped and still a success" is the half that
  fixes the boundary. Without it the next reader cannot tell the intended limit from an accident.
- **Name the level.** A guard at the envelope is not a guard at the record. Say which nesting levels,
  which thresholds, which sub-cases — the agent covers the ones named and stops.
- **Re-review after remediation, and expect it to find something.** All three rounds here were real
  defects, not nitpicks. Converging took three passes because each pass could only see the layer the
  previous one exposed.

The general rule: **an absence has no happy path, and neither does a residue.** Both need a test
written against the _shape_ of the bug rather than against the instance that was reported.

## Verifying the hand-back

Re-run the project's own gate commands rather than the agent's paraphrase of them, and run the
**whole** suite rather than the failures the agent named — see `CLAUDE.md`'s "Commits" and the
`git-workflow` skill.

A degenerate hand-back is not a no-op. Four agents in one session returned `"Holding."`, `"Unchanged.
Final."`, `"No action taken."` and `"(no further action — position unchanged)"`; every one had done
substantial, correct work and one had already committed. Check `git status`, `git log` and the suite
before re-dispatching, or you will duplicate or clobber real work.
