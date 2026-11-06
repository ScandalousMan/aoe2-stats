# Quickstart — verifying match reconstruction, phase by phase

**Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/](./contracts/) | **Model**:
[data-model.md](./data-model.md)

Every command runs from the repository root with the network blocked, as the suite already enforces.
Nothing here touches production: the local environment file points at the live database, so no step
below runs a migration or a script against it, and none needs to.

```bash
export PYTEST_DISABLE_NETWORK=1
```

## Phase 1 — Evidence and vocabulary

1. **The widening is additive.** Regenerate the canonical goldens and confirm only `unit-queued`
   lines changed, each gaining `building_objects` whose first element equals `building_object`;
   006's golden timeline must still compare byte-identical.

   ```bash
   uv run python scripts/ops/canonical_golden.py
   ```

   ```bash
   uv run pytest packages/replay-engine -q
   ```

   Expected: green, including the golden timeline and the field-by-field comparison of the old and
   regenerated streams (contracts/canonical-events-amendment.md).
2. **The baseline exists.** The analysis-time test over the three committed recordings runs and
   records today's figure before any reconstruction code exists (research R14).
3. **The age-proof consistency test knows its one defect.** It finds the Sicilian unit of research
   R3 and nothing else, held as a strict expected failure, so the suite turns red on the day 006's
   superseding snapshot fixes the age requirement, and the expectation is removed in that change.
4. **The owner has the requests.** `specs/008-match-reconstruction/owner-readings.md` lists O1 to O5
   with times; nothing in it is an answer.

## Phase 2 — The spine

```bash
uv run pytest packages/reconstruction packages/core apps/analyzer -q
```

Expected:

- The registry loads, its view matches byte for byte, and each loader guarantee of
  contracts/rules.md has a test that plants its violation and sees the import fail.
- A document from each committed recording is version 3, carries an empty `reconstructed` block,
  and its identity's `reconstruction_engine` names the installed package and registry digest.
- Validator rules 11 to 14 each reject their planted violation, including a reconstructed value at
  an observed path and an observed value inside `reconstructed`.
- Each invariant of data-model §8 refuses a synthetic stream that breaks it, and nothing is
  published.
- Reproducing a document from its identity yields identical bytes; reproducing one whose engine is
  not installed refuses and names what differs.
- The starting-attributes event appears once per human participant in each committed recording,
  and its four stockpiles agree with the lobby-and-civilisation derivation.

## Phase 3 — Gate G1

The gate closes when, for each of the 22 age-ups, the queue the model holds at the click equals the
queue the owner read (O1), and each command the owner observed in O2 places its items where the
model places them.

```bash
uv run pytest packages/reconstruction -k playback -q
```

Expected: every O1 and O2 reading agrees, D-EXEC-1 and D-DIST-1 are `adopted` in the registry with
those readings listed, and the reconstruction version is bumped. If a reading cannot be matched by
any rule written from observed facts, the gate does not close, and the plan's Complexity Tracking
says what the owner is asked.

## Phase 4 — Arrivals

For each committed recording, the published arrival of every age-up equals the owner's reading
(SC-001), every age-up counted not reached is one the game shows not reached, and every arrival's
settlement names a confirming order or D-AGE-1's resignation clause.

```bash
uv run pytest packages/reconstruction -k "arrival or playback" -q
```

## Phase 5 — Spending

Open a reconstructed document for 504695319 and pick one participant's wood spending. Follow its
settlements to the orders and rules they name, and its effects to the snapshot the identity names,
and recompute it by hand (SC-005, US3 independent test). The golden reconstruction must hold the
same number.

## Phase 6 — At scale

```bash
uv run pytest -q
```

Expected: the whole workspace green, including the synthetic stream for every civilisation of every
promoted snapshot (SC-004), the per-rule settlement table written beside each golden (SC-009), the
analysis time within twice the phase 1 baseline (SC-008), and two analyses of each recording
byte-identical outside the wall-clock set (SC-006).

## Phase 7 — The view

```bash
pnpm --filter design-system storybook
```

The modelled-value stories render each reconstructed number labelled as modelled, apart from the
observed click, with its settlement indicator, in light and dark themes. The visual reviewer passes
them locally, and the PR's visual job captures the baselines from CI's render.

## Phase 8 — Gate G2

Idle time by empty queue publishes once its readings agree. Population publishes only if a candidate
rule of research R5 agrees with every O6 reading; otherwise the two data stay `planned` and the owner
is asked, as the plan states.

## Closing

```bash
uv run scripts/checks/spec_lint.py --feature specs/008-match-reconstruction
```

Expected exit code 0. Then the three measurements of research R13 are present in
`docs/data-sources.md` §2, each asserted by a test, and this feature's research names them as its
record of origin.
