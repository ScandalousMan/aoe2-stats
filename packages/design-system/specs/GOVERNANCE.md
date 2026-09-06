# Governance

Four mechanical procedures and nothing else: token admission, component and variant admission, the
promotion threshold, and deprecation (FR-064, FR-067). Each is a numbered sequence an agent applies
alone, from a cold context, with no step that waits on another person — a rule this system cannot
apply without one is not a rule it keeps (FR-067), and that constraint is applied to this feature's
own output first: T574 runs all four below at least once and records the outcome in the Record
subsection under each.

## 1. Token admission

Applies to every proposed addition to `packages/design-system/tokens/*.json`
(`contracts/token-families.md` §5, FR-064).

1. Name the design decision the token expresses, without naming a call site.
2. Name at least two call sites that would use it, present or specified in a component spec. Fewer
   than two is a rejection.
3. Search the existing token families for a synonym under a different name (grep
   `packages/design-system/tokens/*.json` and the family tables in
   `packages/design-system/specs/README.md`). A synonym is a rejection, and the rejection names the
   token that serves instead.
4. State the utility class a component will write to reach it. If none exists, the token's family
   is incomplete: extend `packages/design-system/tokens/build-tokens.mjs` and the family's `@utility`
   block before continuing, then return to this step.
5. If the token is a colour role, name every surface it may be painted on and add the resulting
   pairs to the measured contrast table in `packages/design-system/specs/README.md`, including
   whether each pair carries an accessibility floor.
6. Record the outcome below: admitted, or refused with the reason and the token that serves instead.
   Where an admission leaves the family temporarily short of what a waiting component needs, the
   interim also goes in the gap register in `packages/design-system/specs/README.md` (FR-064a); this
   Record is the permanent decision log, that register is only ever the currently open items.

### Record

| Date | Token | Family | Outcome | Reason / replacement |
| ---- | ----- | ------ | ------- | -------------------- |

<!-- T574 adds the first rows here, oldest first. Do not renumber or remove a row once recorded. -->

## 2. Component and variant admission

Decides whether a proposed component or variant is admitted, which of reuse, consistency or
interaction complexity justified it, and prefers composition where composition suffices (FR-030,
FR-031).

1. State the need: the call site or specified requirement driving the proposal, and whether it
   proposes a new component or a new variant of an existing one.
2. Attempt composition first — assemble the need from existing primitives and domain composites
   through props, slots and arrangement alone, adding nothing new. If this satisfies the need in
   full, stop here: record "composition suffices," name the composition, and admit nothing.
3. If the proposal is a variant: state the distinct meaning it expresses that no existing variant of
   the same component expresses. If the only justification is a single call site's requirement,
   reject it and record that call site together with the existing variant or composition it must use
   instead. Otherwise continue to step 5.
4. If the proposal is a new component: name every one of reuse, consistency and interaction
   complexity that applies, and require at least one.
   - **Reuse** applies when the need recurs at more than one present or specified call site.
   - **Consistency** applies when an existing visual or interaction pattern is already established
     elsewhere in the system and a new call site must not diverge from it.
   - **Interaction complexity** applies when the behaviour — keyboard handling, focus management,
     asynchronous state, or a similar concern that is not just prop plumbing — cannot be expressed
     by composing existing primitives without duplicating it at every call site.

   If none applies, reject the proposal and record the composition the call site must use instead.

5. For an admitted component, declare its tier — primitive, domain composite or screen — per the
   boundary FR-028 fixes, and confirm the dependency direction FR-029 requires: a primitive depends
   on no domain composite, and no component depends on the application.
6. Record the outcome below: admitted, with its tier (for a component) or the distinct meaning it
   expresses (for a variant) and the deciding ground(s); or rejected, with the alternative the call
   site must use instead.

### Record

| Date | Component or variant | Kind | Ground(s) | Outcome | Tier |
| ---- | -------------------- | ---- | --------- | ------- | ---- |

<!-- T574 adds the first rows here, oldest first. Do not renumber or remove a row once recorded. -->

## 3. Promotion threshold

An application composition repeated beyond the threshold is promoted to the system, or the reason
it is not is recorded beside the third occurrence (FR-033, SC-014). The threshold is **three**: the
smallest count that distinguishes a pattern from a coincidence — two could still be an accident of
two authors reaching for the same shape independently, three cannot.

1. Identify the composition: a specific arrangement of existing primitives or domain composites
   serving one recognisable purpose, appearing in application code under `apps/web/`. Reusing the
   same components for a different purpose is not the same composition.
2. Count its occurrences in `apps/web/` by searching for the same arrangement, not from memory.
   Fewer than three: no action, the count is not recorded, and this procedure stops here.
3. On the third occurrence, run the component and variant admission test (§2 above) on the
   composition, using the third occurrence as its stated need.
4. If §2 admits it: promote it into `packages/design-system/src/` at the tier §2 declared, replace
   all three occurrences with the promoted component in the same change, and record the promotion
   below, naming the three replaced call sites.
5. If §2 rejects it: record the specific reason beside the third occurrence in `apps/web/` (a code
   comment citing this section), and record the same reason below. A reason recorded in only one of
   the two places fails FR-033. The reason stands for later occurrences unless it names a condition
   under which to re-run this procedure.

### Record

| Date | Composition | Occurrences (call sites) | Outcome | Reason (if not promoted) |
| ---- | ----------- | ------------------------ | ------- | ------------------------ |

<!-- T574 adds the first rows here, oldest first. Do not renumber or remove a row once recorded. -->

## 4. Deprecation

Retires a token, component, variant or prop by naming its replacement, enumerating every consumer,
and landing the removal together with the change that updates them (FR-065, FR-066).

1. Name the replacement that serves every use case the deprecated thing served. If none exists yet,
   deprecation cannot proceed: admit the replacement first, through whichever of §1–§3 above applies
   to it, then continue.
2. Enumerate every consumer across the repository by searching for the import, prop name, class name
   or token name being retired — in `apps/web/`, `packages/design-system/src/` and every other
   package that could reference it.
3. Prepare the migration of every enumerated consumer to the replacement, in the same change as the
   removal.
4. Land the removal and every consumer's migration as one change. Never split "add the replacement"
   from "remove the deprecated thing and migrate its consumers" across separate changes, and never
   merge a change that leaves a consumer referencing the retired thing.
5. Record the deprecation below: the retired thing, its replacement, and the full list of migrated
   consumers.

### Record

| Date | Retired | Replacement | Consumers migrated |
| ---- | ------- | ----------- | ------------------ |

<!-- T574 adds the first rows here, oldest first. Do not renumber or remove a row once recorded. -->
