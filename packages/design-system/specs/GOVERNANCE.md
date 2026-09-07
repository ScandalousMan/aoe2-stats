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

| Date       | Token                                                | Family                  | Outcome  | Reason / replacement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------- | ---------------------------------------------------- | ----------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-09-05 | `hairline`, `ring`, `ring-offset`                    | border                  | admitted | Closes DS-4. Call sites: `border-hairline` is written by every structural primitive plus `Panel`, `Table` and `Field`; `outline-ring`/`outline-offset-ring` carry the shared focus ring on `Button`, `Link`, `Field` and `Menu` — well past the two-site floor. No synonym existed (the register's own DS-4 row is what this closes). Reached through hand-written `@utility` blocks in `packages/design-system/tokens/build-tokens.mjs` (`contracts/token-families.md` §2) rather than a Tailwind theme namespace, because Tailwind v4 exposes none for border width, outline width or outline offset — verified against the installed `tailwindcss` package (`packages/design-system/tokens/border.json`'s own `$comment`; research.md D5). Not a colour role, so step 5 is inapplicable. Deliberately not a ratification of Tailwind's own numeric border-width scale, which is unbounded (`border-7` compiles) and would leave FR-062's off-scale check nothing to enforce — plan.md's Complexity Tracking table records this as one of two decisions overruling a written suggestion elsewhere in the repository. |
| 2026-09-05 | opacity family — no member was ever proposed by name | opacity (never created) | refused  | FR-006a's reason: a transparent value's contrast pair depends on whatever renders behind it and is only measurable after the fact, which the measured contrast table cannot hold before it exists. Replacement is a colour route, one per attenuated appearance: disabled is `text-disabled` on `surface-sunken` with `border` (already the interim); de-emphasised is `text-secondary`; the dialog scrim is the existing `overlay` role. `overlay` keeps its own alpha (`rgb(43 32 19 / 55%)`) without contradicting the refusal — a scrim paints no foreground, so it owes no contrast pair of its own; what it owes is that the dialog above it reads, and that pair (`text-primary` on `surface`) is already measured (research.md D9; gap register row DS-3, closed by T529, PR #64).                                                                                                                                                                                                                                                                                                                             |

_Both rows are retroactive: the decisions shipped 2026-09-05 (T514, PR #64, for `border.json`; T529, PR #64, for the DS-3 refusal), one day before T573 wrote this procedure down (T573, PR #69, `2ff9f3a`, 2026-09-06 20:27). This Record supplies the application production-readiness item 14 asks for, not a contemporaneous log. Step 2's two-call-site floor is satisfied by `border` only in hindsight — no list of exactly two sites was written at admission time; the count above is taken from the shipped tree. Step 5 never applies to either row: `border` is a width family, and the opacity row was refused at step 1, before any colour role could be named._

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

| Date       | Component or variant | Kind      | Ground(s)          | Outcome  | Tier      |
| ---------- | -------------------- | --------- | ------------------ | -------- | --------- |
| 2026-09-06 | `Page`               | component | reuse, consistency | admitted | primitive |

Reuse: the need (one main landmark, one content width, one page padding) recurs at every route
spec.md's "Missing foundations" item 10 names, not one call site. Consistency: spec.md's own
design decision 2 — "the structural tier is a system concern, not an application one; the nested
landmark defect exists because layout was left to each route" — is the established-pattern
argument step 4 asks for: two routes must not diverge in structure without anyone comparing them.
Interaction complexity does not apply — `Page` holds no asynchronous state and no keyboard handling
of its own beyond the skip-link's focus target, which `tabIndex={-1}` alone expresses. Tier is
primitive, declared in `packages/design-system/specs/structural-tier.md`'s tier table and confirmed
by dependency direction: `Page` imports no domain composite and nothing under `apps/web/` (admitted
in T543, PR #67, `packages/design-system/src/primitives/Page/`).

_Not a clean application of step 2. The procedure asks that composition be attempted first and
recorded as insufficient before a component is proposed; no such attempt is recorded anywhere for
`Page`. Substantively no composition could have sufficed — at the time of this commit no existing
component supplied a landmark, a closed page-width vocabulary or a page-padding rule an application
route could assemble — so the outcome would likely have been the same, but the step itself was
never performed as a documented act, only reconstructable after the fact. This is because `Page`
was designed top-down from `packages/design-system/specs/structural-tier.md` (T539–T540, written
before `GOVERNANCE.md` existed) rather than proposed bottom-up against an assembled call site, which
is the shape step 1 assumes. See the promotion-threshold record below for the same feature's other
half of that same primitive's history._

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

| Date       | Composition                                                                                                                                                                                                                     | Occurrences (call sites)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Outcome  | Reason (if not promoted) |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------ |
| 2026-09-06 | The page wrapper — a hand-rolled `<main className="min-h-svh bg-background …">` carrying the route's landmark, a `mx-auto max-w-*` content width and a `px-4 py-6 md:px-6 md:py-8`-shaped page padding, repeated once per route | 10 — `apps/web/src/features/favourites/FavouritesContainer.tsx`, `apps/web/src/features/matches/MatchHistoryContainer.tsx`, `apps/web/src/features/players/PlayerMatchHistoryContainer.tsx`, `apps/web/src/features/players/PlayerProfileContainer.tsx`, `apps/web/src/features/privacy/ObjectContainer.tsx`, `apps/web/src/features/privacy/PrivacyContainer.tsx`, `apps/web/src/features/privacy/PrivacyNoticeContainer.tsx`, `apps/web/src/features/profile/DashboardContainer.tsx`, `apps/web/src/features/replays/MatchDetailContainer.tsx`, `apps/web/src/features/search/SearchContainer.tsx` (counted from T551–T555, PR #68, which replaced all ten in one change; `apps/web/src/routes/__root.tsx` lost its own plain shell in the same commit but never carried the wrapper's width/padding shape, and `SignInScreen`/`ThirdPartyObjectionForm` are design-system screens, not `apps/web/` occurrences, so neither counts toward the ten) | promoted | n/a                      |

_Ten is well past the threshold of three, so step 2's "fewer than three: stop" never bit — this
subject only reaches the record at all because it cleared the floor by a wide margin. Steps 3–4 do
not fit the actual order of events: the procedure assumes the count triggers the admission test on
the composition's third occurrence, with promotion and replacement landing in the same change as
that test. Here `Page` was already admitted (T543, PR #67, 2026-09-06 13:30, see §2's record
above) **before** the ten occurrences were counted or replaced; the replacement of all ten landed
almost two hours later, in a separate commit (T551–T555, PR #68, 2026-09-06 15:25) titled "the retrofit."
"Replace … in the same change" (step 4) held for admission-and-first-use in spirit — one commit
did all ten replacements together, which is the part of step 4 that matters for FR-033 — but
promotion preceded the count that was supposed to trigger it, because the structural tier's need
was named directly in spec.md's "Missing foundations" item 10 rather than discovered by counting
existing repetitions in `apps/web/`. The count and the outcome recorded above are accurate; the
sequence is evidence that this procedure, as written, fits a pattern noticed bottom-up (three
independent authors converging by accident) better than a tier planned top-down and retrofitted
onto pre-existing call sites afterward — the two ways `packages/design-system/specs/GOVERNANCE.md`
§2's own note on `Page` makes the same point from the admission side._

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

| Date       | Retired                                                                                                  | Replacement                                                                              | Consumers migrated                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-09-06 | `CaptureStateBadge`'s `context` prop (values `compact`/`detail`) and its type `CaptureStateBadgeContext` | `variant` prop and type `CaptureStateBadgeVariant`, same two values, no behaviour change | `packages/design-system/src/composites/CaptureStateBadge/index.tsx`, `packages/design-system/src/composites/CaptureStateBadge/countdown.ts`, `packages/design-system/src/composites/CaptureStateBadge/CaptureStateBadge.stories.tsx`, `packages/design-system/src/composites/CaptureStateBadge/CaptureStateBadge.test.tsx`, `packages/design-system/src/composites/MatchRow/index.tsx`, `packages/design-system/src/composites/MatchDetailPanel/index.tsx`, and the prose naming the prop in `packages/design-system/specs/capture-state-badge.md`, `packages/design-system/specs/match-history.md` and `packages/design-system/specs/README.md` rule 9 — all in T557, PR #68. `apps/web/` needed no change: its only mentions of the old name were prose in comments, never code. |

_This is the feature's only deprecation, and it predates `GOVERNANCE.md`: T557 (PR #68, `55a2b64`,
2026-09-06 16:05) landed about four hours before T573 wrote this procedure down (T573, PR #69,
`2ff9f3a`, 2026-09-06 20:27), the same day, which is why
`packages/design-system/specs/README.md` rule 9 already says so in its own words. Checked
retroactively against the five steps: step 1 (name the replacement) is the one place the letter
does not quite fit — `variant` was not admitted through §1–§3 above as a new thing to serve this
case, because it already existed as every other embedding-dependent component's name for the
identical concept (`ProfileSummary`, `StatValue`, `SignInScreen`, `CivilisationIconSize`,
`MapThumbnailSize`); `context`/`CaptureStateBadgeContext` were the outlier, so this deprecation is
closer to "conform to the existing standard" than "admit something new and then retire the old
name for it," which is the shape step 1 assumes. Steps 2–4 fit exactly: the survey found precisely
the six code consumers and three spec references listed above, and all of it — retirement,
replacement and every consumer's migration — landed in the single commit named._

<!-- T574 adds the first rows here, oldest first. Do not renumber or remove a row once recorded. -->
