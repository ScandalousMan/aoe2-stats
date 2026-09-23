# Quickstart — verifying Replay-analysis foundations

**Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/](./contracts/)

How to prove each phase works. Commands run from the repository root. Nothing here needs a network,
a database other than the test one, or a credential — and **nothing here runs a migration from a
developer machine**: the local environment file points at production, and
`docs/runbooks/database-migrations.md` is the only path for phase 5's revision.

## Prerequisites

```bash
uv sync
```

```bash
PYTEST_DISABLE_NETWORK=1 uv run pytest -q
```

The whole suite, green, before and after every phase. Check the exit code, not the summary line.

## Phase 1 — Evidence and corrections

**The second fixture** (research D2). If the served zip is recoverable, it is copied in unmodified
and its checksum recorded:

```bash
shasum -a 256 tests/fixtures/replays/*.zip
```

Expected: two archives, each matching the checksum in `tests/fixtures/replays/README.md`, each
holding exactly one recording. A fixture test asserts, for **every** committed archive, that the
post-game block list contains no statistics block — which is what lets
`docs/data-sources.md` §2 stop being an open question (FR-045).

**The corrections** (FR-046, FR-047):

```bash
grep -rn "apps/parser" .claude/skills/replay-parsing/SKILL.md docs/adr/0001-replay-parser.md .github/workflows/pr.yml
```

Expected: no output — the skill's frontmatter description included. Then read the placement paragraph of the skill against
`packages/replay-engine/tests/test_aoe2rec.py` — they must now say the same thing.

## Phase 2 — Truth types and the register

```bash
uv run pytest packages/core/tests -q
```

Expected, among others: the register loads; each loader refusal in
[contracts/register.md](./contracts/register.md) has a test that plants the defect and sees the
refusal; a numeric confidence is unconstructible; a provenance cannot claim a tier stronger than its
weakest input.

**The drift gate.** Edit one `impact` line in the register, run the suite, and expect the view test
to fail and print the regeneration command. Run it, and expect green.

**SC-012, by hand.** Open `packages/core/src/aoe2stats_core/truth/REGISTER.md`, look up unit loss,
and confirm — without opening a Python file — that it says why it cannot be known, what that costs,
that the approximation is not acceptable, and what would change the answer.

## Phase 3 — Canonical events

```bash
uv run pytest packages/replay-engine/tests -q
```

Expected:

- The golden timeline is **byte-identical** to the committed one, now produced through the
  canonical stream. `git status` shows the golden file untouched.
- The doubled age-up command in the fixture appears once (SC-010).
- Every operation is an emitted event or is counted in a named drop category (no silent drop).
- No payload field name appears in the wheel-derived deny-list (SC-009).
- The input-size refusal holds through the new entry point, and the separate peak-memory measurement
  over every committed recording stays under its recorded ceiling (FR-021). The first proves nothing
  about the second.
- Neither declared-only kind is emitted (FR-020).

## Phase 4 — The knowledge base and its gaps

```bash
uv run pytest packages/knowledge/tests -q
```

```bash
uv run scripts/checks/asset_packs.py
```

Expected: the licence check now sees `packages/knowledge/packs/aoe2techtree` and passes; remove one
of the five fields and it fails.

**US2, by hand** — a discounted building, for the civilisation that discounts it (raw id 9 is
Saracens, T652m; Saracens' Market costs 175 wood, discounted by 100):

```bash
uv run python -c "from aoe2stats_knowledge import open_snapshot_for; kb = open_snapshot_for(180059); print(kb.cost(('building', 84), civilisation=9))"
```

Expected: an answer whose value is the civilisation-adjusted cost, carrying the snapshot identity
and the one effect applied, with its source sentence. Ask the same of a civilisation that is not
modelled and expect a gap with cause `civilisation-not-modelled`, never the baseline.

**No nearest snapshot** — ask for a build one higher than any snapshot describes and expect a gap
with cause `no-snapshot-for-build`.

**SC-007a** — the coverage pass over every committed recording reports no blocking gap outside
FR-022b's enumerated list; recording 1 is clean, recording 2's two source-limited blockers are held
by a strict expectation that fails the day any of them is closed. **SC-007** — the test that removes
a field sees exactly the dependent data withheld.

**SC-006** — the suite above ran with the network blocked; a knowledge query that touched a socket
would have raised.

## Phase 5 — Identity and the published document

```bash
uv run pytest apps/analyzer/tests packages/core/tests -q
```

```bash
pnpm --filter web test -- analysis
```

Expected:

- Two analyses of the fixture, the second in a fresh process, are byte-identical outside the
  wall-clock set (SC-004).
- Publish, promote a second snapshot, recompute: two objects exist, the row names the newer, and
  `reproduce` on the first identity returns the first document's bytes (SC-005).
- A document with a coaching-style conclusion at an observed path is rejected, once per tier
  boundary (SC-003).
- A document whose dependency record is empty is rejected (SC-011).
- The web reader parses a version 2 fixture with no source change.

**After deploy**, per the runbook: the health endpoint answers **200**. Read the status, not the
revision field — that field is the build's own compiled constant and says nothing about the
database. Between applying the migration and the deploy going live it answers 503, which is the
check working. Then one analysis requested by hand shows a populated dependency record, an identity
digest, and a gap list that is empty or explains itself.

## What this feature deliberately cannot show

No resource curve, no population, no loss figure, no starting state. If any of those appears in a
document, the register gate has failed — that is a defect in this feature, not an early delivery of
the next one.
