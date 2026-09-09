# Quickstart — Design System Foundations

**Feature**: `005-design-system-foundations` | **Date**: 2026-09-05

How to verify each phase, and how to regenerate baselines without producing a subtly wrong
generation. Every scenario below is runnable and states what a pass looks like.

Prerequisites: `pnpm install --frozen-lockfile`, and `pnpm exec playwright install --with-deps
chromium` once. No database, no API, no environment variable — this feature touches neither.

## The gates, in the order a phase runs them

```bash
pnpm --filter design-system tokens:build && pnpm typecheck && pnpm lint && pnpm test
```

Then the two new checks, and the visual suite:

```bash
node scripts/checks/token-scale.mjs && node scripts/checks/tier-deps.mjs
```

```bash
pnpm --filter design-system build-storybook && pnpm test:visual --changed
```

`tsc -b` runs inside `pnpm typecheck` and is the only thing in the workspace that catches a shared
type drifting between the design system and the application — the application's own unit runner is
transpile-only.

## Scenario 1 — The harness change altered no value (phase 1)

The whole point of doing the machinery first. After the matrix lands and before any token moves,
the captures at the existing axes must be **byte-identical** to the baselines T502 reconciled. The
proof is the commit the `baselines` workflow made, not Playwright's verdict — the suite's
`maxDiffPixelRatio` of 0.01 reports a sub-percent rendering change as clean.

```bash
git show --stat --format= HEAD -- packages/design-system/__screenshots__ | grep -v 'Bin 0 ->'
```

**Pass**: the command prints nothing but the summary line — every file in that commit is an
addition. Every pre-existing baseline, renamed by T504 to its light-1280 name (light-375 for the ten
stories that were `visual-mobile`), is untouched byte for byte, and every dark and other-width
capture is a new file. **Fail**: any pre-existing file listed as modified means the harness changed
rendering, which is the one thing this phase may not do — and this is the only phase in which that
is detectable.

## Scenario 2 — Every design decision has a token (US1)

```bash
node scripts/checks/token-scale.mjs
```

**Pass**: exit 0 over `packages/design-system/src` and `apps/web/src`. **Fail** on an arbitrary
bracket value carrying a length, colour, duration or shadow; a raw hex, `px`, `rem` or `ms`; or a
hand-written `var(--ds-*)` in a class name. The last is the case that survived a year: a
token-derived value written by hand is still a defect, because it means the utility vocabulary has
a hole.

Then read the register:

```bash
grep -n 'DS-[0-9]' packages/design-system/specs/README.md
```

**Pass**: no entry is open with only an interim workaround. Each is closed, or refused with a date
and the replacement named.

## Scenario 3 — Breakpoints have one definition (US1)

Change `md` in `packages/design-system/tokens/breakpoint.json`, rebuild, and confirm both consumers
moved:

```bash
pnpm --filter design-system tokens:build && grep -n 'breakpoint' packages/design-system/tokens/generated/preset.css packages/design-system/tokens/generated/tokens.ts
```

**Pass**: the new value appears in the Tailwind mapping and in the generated TypeScript record, and
`useBreakpoint` reads the record rather than a literal. Restore the value afterwards. **Fail**: a
literal anywhere in `packages/design-system/src/lib`.

## Scenario 4 — Contrast is measured against what ships (US1)

```bash
pnpm --filter design-system test
```

**Pass**: the token tests assert every pair in the measured table that carries an accessibility
floor, computed from the `color.json` that ships. **Fail**: a pair a component draws with no row —
including `text-secondary` on dark `background`, which the register names as drawn and unmeasured
today, and which this feature must add.

Confirm the pairing convention held: for any token you changed, find every component that renders
it and list the background each one paints behind it. A row asserted against a background no
component paints is the defect this repository has now hit three times.

## Scenario 5 — A screen is assembled, not re-invented (US2)

```bash
pnpm --filter web build && pnpm exec playwright test tests/visual/app-routes.spec.ts
```

**Pass**: every route renders exactly one main landmark. **Fail**: any route rendering zero or two.
Ten sources of a second landmark exist today — nine application containers plus two design-system
components, one of which is composed by a route that already nests one.

Then confirm the application writes no layout:

```bash
grep -rnE 'className="[^"]*\b(mx-auto|max-w-|px-[0-9]|py-[0-9]|mt-[0-9]|gap-[0-9])' apps/web/src --include='*.tsx' | grep -v '\.test\.'
```

**Pass**: empty. Every one of those decisions belongs to `Page`, `Section` or `Panel`.

## Scenario 6 — The reader can use the theme they need (US3)

Manual, and it must be manual: a flash of the wrong theme is a first-paint event that no still image
captures.

```bash
pnpm --filter web dev
```

1. Set the operating system to dark and open the app in a fresh profile. **Pass**: it renders dark
   immediately, with no light frame. Record it and step through if unsure.
2. Override to light, reload. **Pass**: still light.
3. Block site data in the browser's settings and reload. **Pass**: it renders the system preference,
   or light if none, and does not throw.
4. With no override stored and the system expressing no preference, **pass**: light.

Then confirm no component branches on the theme:

```bash
grep -rn "dataset.theme\|data-theme" packages/design-system/src --include='*.tsx' | grep -v '\.test\.'
```

**Pass**: matches only under `packages/design-system/src/theme`. Nothing else may know which theme
is active — the toggle sets it and styles nothing by it.

## Scenario 7 — Numbers are legible and comparable (US4)

Open Storybook and compare a column of ratings of differing digit counts.

```bash
pnpm --filter design-system storybook
```

**Pass**: digits align vertically. Now change `font.family.mono` in `font.json` to a proportional
family, rebuild, and look again. **Pass**: still aligned, because the `numeric` role declares
`tabular-nums` rather than relying on the family being monospaced. Restore the value.

**Pass**: no loading or unobserved value renders a digit or a zero, and an unobserved value is
visibly distinct from a measured one.

## Scenario 8 — The system is verified across the axes it claims (US5)

Four deliberate breakages, each of which must fail a check by name.

| Break                                              | Must fail                                                    |
| -------------------------------------------------- | ------------------------------------------------------------ |
| Remove a required accessible name from a component | the axe scan, naming the component                           |
| Change a dark-theme-only colour value              | a dark baseline, and the contrast test if it crosses a floor |
| Introduce an overflow at 768                       | a 768 baseline                                               |
| Import a composite from a primitive                | `scripts/checks/tier-deps.mjs`                               |

Revert each afterwards. A check that does not fail here is a check that will not fail in a pull
request either.

## Scenario 9 — Storybook explains the system without the source (US6)

Hand someone Storybook and no repository access. Ask three questions:

1. Which component to use for a stated need.
2. Which token carries a stated meaning, and on which surfaces it may be painted.
3. What a stated state looks like.

**Pass**: all three answered from the foundation pages and the navigation alone. **Fail**: any
answer that needs the source. This is the only scenario here with a human in it, and it is the one
that decides whether the system is maintainable by an agent working from a cold context.

### Result (T572, run 2026-09-07)

A fresh agent was given the built static Storybook only — no repository access, with
`packages/design-system/src/`, `specs/`, `tokens/`, `apps/` and every `*.stories.tsx` withheld — and
asked the three questions. This is a mixed verdict, not a pass.

1. **Which component for a stated need** (show a player's in-game colour beside their name, and it
   must still make sense for someone who cannot distinguish red from green): **partly answered.**
   `PlayerColourSwatch` was found in two clicks via `Composites → Player identity` — the
   tier-and-need navigation (T564) did its job. The colour-blindness half failed: the redundancy is
   `sr-only` text only, discoverable only by reading the DOM, and the governing rule (FR-011,
   Foundations → Iconography) is not linked from, or claimed by, any component story.
2. **Which token means "this failed", and on which surfaces**: **failed at the time of the run,
   fixed since.** The reader found `danger` on Foundations → Colour in one navigation and called the
   page "the strongest thing in the build", but it then delegated every number to
   `packages/design-system/specs/README.md` and `color-tokens.md` — files the scenario forbids — so
   it could show a rectangle but not the colour behind it, and captioned emphasis tiles with the role
   name four times instead of the surface. A fix landed on this branch (PR #69, following this
   run) that now computes every contrast ratio live from the token pair the tile actually paints and
   captions each tile with its surface. This question passes against the tree as it stands today; it
   did not pass during the run.
3. **What a stated state looks like** (rate-limited `SearchBox`; `selection` on a `Menu`): **half
   excellent, half failed at the time of the run, fixed since.** `SearchBox`'s rate-limited story was
   singled out as the model the rest of the library should follow — its story name is a contract and
   the render honours it line by line. `Menu/Selection`, `Menu/ProfileSwitcher` and
   `Menu/FocusVisible` rendered pixel-identically: a checked item carried `aria-checked` and no
   visual mark, so the ring visible on that row was the focus ring, not a selection mark, and a
   reader could not tell the two states apart. A fix landed on this branch (PR #69, following this
   run) that gave `Menu` an intrinsic leading checkmark, painted when checked and holding reserved
   space when not, and a follow-up spec correction in the same PR moved `FocusVisible`'s focus onto
   an unchecked item so selection and focus read as two signals; the spec files that had described
   the retired caller-supplied badge (`shared-primitives.md`, `profile-summary.md`,
   `site-header.md`) were corrected to match. (One of the two fix commits behind this paragraph was
   superseded by a rebase before landing; only the surviving commit is citable, which is why neither
   is named by hash here.)

   **Correction, fifth-pass review, 2026-09-09.** Checked against the current, checkmark-fixed
   tree, `Menu/Selection` and `Menu/ProfileSwitcher` are **not** a duplicate pair: they differ at
   1280 (a label, bounding box `(41,40)-(205,42)`). The pair that genuinely is byte-identical today
   is `Selection` == `SheetBelowMd`, and that one is benign and already honestly documented rather
   than a defect: `SheetBelowMd`'s `globals.viewport` pin (`Menu.stories.tsx`) is cosmetic to the
   browsable Storybook only, the same mechanism `MatchRow.stories.tsx:305-307` and
   `.storybook/preview.tsx:15` both say so of; the visual suite's own width axis is what actually
   governs a capture's dimensions, driven by `tests/visual/stories.spec.ts:193`
   (`page.setViewportSize`, with only `globals=theme:` in the URL it builds — no viewport global).
   `Selection` and `SheetBelowMd` carry identical `args`, so whichever width the suite captures them
   at, the two render identically by construction, not by a bug; the pin only changes what a
   developer sees browsing the story by hand. Recorded here so a sixth review pass does not have to
   re-derive it.

Two of the three fixes above landed only after this run named them, and Q1's accessibility half is
still open. What remains — no `docs` entries in the build, docgen off so no prop tables, no
component stating its purpose in a sentence, no story stating which `sr-only` naming shape it
follows — is a property of the package's Storybook build itself, not of the one run that found it,
so it is recorded beside the package rather than here: see
`packages/design-system/specs/README.md`, "Storybook documentation gap register".

## Regenerating baselines

Never locally, for any full-page or application-route baseline, and by one rule for all of them so
the rule has no exception to forget. Dispatch the `baselines` workflow from the branch; it runs on
Linux and commits the result.

**Before dispatching**, know which of the three global repaints you are in — the palette and
typefaces, the structural rhythm, or the retrofit — and say so in the commit body. A regeneration
with no stated cause is 1,794 files nobody can review. A regeneration whose cause is named is one
sentence a reviewer can check against the diff's shape.

**After it lands**, spot-check by hand rather than by count: open three stories in both themes at
all three widths and confirm the change is the one you intended. The diff is uninformative in these
phases by construction, which is why the contrast test, the axe scan and `visual-reviewer` carry
them instead.

## Production-readiness walk (T577, run 2026-09-08)

Run against `git log --oneline main..HEAD` = `b6952d0` on `feat/005-storybook-governance` (PR #69),
one commit ahead of `origin/feat/005-storybook-governance` (`1b795bc`). Per this task's explicit
constraint, Storybook was not built and no browser was driven; scenarios that genuinely need one
are recorded as what they require and what evidence already exists, not attempted. Every mechanical
gate below was actually executed in this session, not paraphrased from an earlier hand-back.

### The gates, run individually

| Command                                                           | Exit | Evidence                                                                                                                                                                                     |
| ----------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm test`                                                       | 0    | apps/web 38 files / 497 tests; `design-system` 43 files / 713 tests (vitest) + 25/25 (`node --test tokens/*.test.mjs`); `game-assets` 1 file / 21 tests. All green                           |
| `pnpm typecheck`                                                  | 0    | `tsc --noEmit` (design-system, game-assets) and `tsr generate && tsc -b` (apps/web) all report `Done`                                                                                        |
| `pnpm lint`                                                       | 0    | `oxlint` over apps/web, `Done`                                                                                                                                                               |
| `node scripts/checks/config-preflight.mjs --contract`             | 0    | "28 configuration keys declared, and `.env.example` documents the same 28"                                                                                                                   |
| `node scripts/checks/token-scale.mjs`                             | 0    | "43 files under `packages/design-system/src` carry no off-scale value. 27 files under `apps/web/src` carry no application-authored layout class" — this is scenario 2 and half of scenario 5 |
| `node scripts/checks/tier-deps.mjs`                               | 0    | "136 files … respect the tier boundary — no primitive imports a composite or a screen, and nothing imports from `apps/`"                                                                     |
| `node scripts/checks/spec-completeness.mjs`                       | 0    | "25 Index rows and 41 component directories agree: every mapped spec answers all 9 sections and all 10 states, and declares a tier and a surface class for every component it covers"        |
| `node scripts/checks/spa-routing.mjs`                             | 0    | "12 route(s) reach the shell … 2 dedicated function(s) resolve by the filesystem"                                                                                                            |
| `node scripts/checks/a11y-allowlist.mjs`                          | 0    | "`scripts/visual/a11y-allowlist.json` is empty — nothing to validate" (T559 closed every entry)                                                                                              |
| `node scripts/checks/story-baselines.mjs`                         | 0    | "537 stories each have all 6 baselines; 3244 baseline files total (22 app-route captures exempt) agree with the built index" — theme x width completeness, structurally, not pixel-by-pixel  |
| `node --test scripts/checks/spec-completeness.test.mjs`           | 0    | 72/72 pass                                                                                                                                                                                   |
| `node --test scripts/checks/story-baselines.test.mjs`             | 0    | 9/9 pass                                                                                                                                                                                     |
| `node --test scripts/checks/token-scale.test.mjs`                 | 0    | 24/24 pass, including "running the application-layout rule against the actual `apps/web/src` tree is clean"                                                                                  |
| `node --test packages/design-system/tokens/build-tokens.test.mjs` | 0    | 25/25 pass, including "no `@utility` block sets a `*-width` property without its matching `*-style` property" — the regression test for the `outline-ring` defect fixed in `c9fff2e`         |

All fourteen commands are green in this working tree, run individually as instructed rather than in
a loop.

**A gate this list does not cover, found while verifying rather than assumed clean**: the
repository's own `scripts/checks/spec_lint.py --feature specs/005-design-system-foundations`
(distinct from `spec-completeness.mjs`, which is design-system-scoped and was already run above)
fails with 3 findings, reproduced locally in this session:

```
FAIL  path-roots: .storybook/preview.tsx is under no root declared in plan.md and no directory on disk
FAIL  path-roots: src/composites/MatchDetailPanel/index.tsx is under no root declared in plan.md and no directory on disk
FAIL  env-declared: GLOBAL_REACH_PREFIXES is used by an artifact but declared in no .env.example key
```

All three are pre-existing prose in this file's own Phase 6 section (the paragraph amended in
`b161d2f`, still present unchanged), not introduced by this task, and both failure classes match
known false positives of this checker (a relative path where it wants repository-rooted, and an
ALL_CAPS constant tripping the env-key heuristic on a non-configuration name). `git log --grep`
confirms CI's "Specs — cross-artifact lint" job failed on this same feature at the last commit
that touched it (`b161d2f`) and has not been re-run clean since. This is not this task's brief and
is out of T577's scope to fix (it would touch prose written by an earlier task, and the fix belongs
with whichever task next amends that paragraph), but it must not be recorded as passing: **the
"Specs — cross-artifact lint" CI job is red on this branch as of this walk**, independent of and in
addition to the two general-reviewer REJECTs below.

**CI's actual state, checked via `gh run list`/`gh run view` rather than assumed**: the last
completed pull-request check against this branch (`34188744388`, against the PR's HEAD at the
moment it ran, effectively `c9fff2e`) failed on two jobs — the spec-lint failure above, and
"Visual regression — affected stories and the built application" (72 failed comparisons, all
`PrivacyNotice`/`ThirdPartyObjectionForm` screen stories across both themes and all three widths).
A `baselines` workflow dispatch (`34188746865`) ran immediately afterward with cause "state stories
now capture real :hover/:active/:focus-visible via Playwright input … and the focus ring now paints
on Page/Link/Table/Text", producing `1b795bc` — the same class of global-reach change
(`GLOBAL_REACH_PREFIXES` re-rendering every story) that explains the 72 stale comparisons. No PR
check has completed against `1b795bc` to confirm the regeneration actually cleared them: the
triggered run (`34190984187`) sits at `action_required`, blocked pending workflow approval, and
ran for 0 seconds. **Recorded as: visual regression was red at the last completed check, a
regeneration addressing the same cause has landed, and nothing has confirmed it green.** A further
local, uncommitted-to-remote fix (`b6952d0`, "Field's story fixture dropped the size class Field
injects") exists on top of `1b795bc` for a separate, genuinely distinct defect (`SizeLg` and
`Default` were byte-identical baselines because a story fixture clobbered the prop under test) and
has not been exercised by any CI run either.

### Quickstart scenarios, walked end to end

1. **The harness change altered no value.** Not re-run: this is a phase-1-only proof by
   construction (the `baselines` workflow commit T502/T504 produced), and no later phase can
   re-create its precondition (an unmoved harness) without reverting five phases of real value
   changes. Recorded as settled by Phase 1 (PR #62/#63), not re-verified here.
2. **Every design decision has a token.** `token-scale.mjs` exit 0 (above) plus the gap register
   grep, done live this session (below). **Pass.**
3. **Breakpoints have one definition.** Not re-run destructively (flipping `breakpoint.json` and
   rebuilding needs reverting cleanly, and this task's scope excludes touching `tokens/`).
   Verified statically instead: `tokens/breakpoint.json` is the only file defining `sm`/`md`/`lg`/`xl`,
   and `packages/design-system/src/lib/useMediaQuery.ts` and the generated Tailwind preset both read
   it — no literal breakpoint number appears under `packages/design-system/src/lib` (confirmed by
   `token-scale.mjs`'s pass, which asserts exactly that for `apps/web/src` and would fail the
   design-system half too). **Pass, by static inspection rather than by the destructive edit-and-revert
   quickstart describes.**
4. **Contrast is measured against what ships.** `pnpm --filter design-system test` is included in
   the `pnpm test` run above (0 failures) and directly asserts the measured table's pairs against
   `color.json`'s shipped hexes. **Pass.**
5. **A screen is assembled, not re-invented.** The main-landmark half needs
   `pnpm --filter web build && pnpm exec playwright test tests/visual/app-routes.spec.ts` — a
   browser, not run here. `tests/visual/app-routes.spec.ts`'s `expectExactlyOneMain` helper is
   confirmed present and wired to enumerate all twelve route files in both themes (read, not run).
   The no-application-layout half was run live: `grep -rnE '...' apps/web/src` returns empty. **Half
   proven this session (the grep); half requires the browser check named above, whose last known CI
   result is the failing run described above (which failed on Storybook stories, not on
   `app-routes.spec.ts` itself — that job's own sub-results were not broken out further from this
   session's log inspection).**
6. **The reader can use the theme they need.** Manual by the scenario's own text; not run.
   Static evidence gathered instead: `apps/web/index.html` carries the inline pre-hydration script
   that reads `localStorage.getItem('ds-theme-override')`, falls back to
   `matchMedia('(prefers-color-scheme: dark)')`, and paints `data-theme` before any stylesheet
   renders (T533). `packages/design-system/src/theme/ThemeProvider.test.tsx` unit-covers the
   override persisting to `localStorage`, a live system-preference change being honoured only absent
   an override, and `localStorage` throwing without crashing. The no-component-branches-on-theme
   check was run live: `grep -rn "dataset.theme\|data-theme" packages/design-system/src --include='*.tsx' | grep -v '\.test\.'`
   matches only `ThemeProvider.tsx` itself plus one documentation comment in `SiteHeader/index.tsx`
   that names the mechanism without branching on it. **The unit-level and static half is proven; the
   first-paint flash and the reload-persistence halves are exactly the browser scenario this task
   was told not to attempt, and remain unverified by this session.**
7. **Numbers are legible and comparable.** Needs Storybook running in a browser to eyeball digit
   alignment; not run. Static evidence: `tokens/font.json`'s `role` group names `type-numeric` with
   `font-variant-numeric: tabular-nums` declared on the role rather than inferred from the mono
   family (`packages/design-system/specs/README.md`, "Closed — DS-8"), and `pnpm test` (above)
   passes the design-system suite that exercises it. **Not independently re-verified visually this
   session.**
8. **The system is verified across the axes it claims.** Not re-run (each of the four breakages is
   a deliberate, reverted regression against `packages/design-system/src` or `color.json`, which
   this task's scope excludes touching). Historical evidence instead: T511 (Phase 2, PR #64) ran and
   reverted three of the four breakages — a removed accessible name failing the axe scan by name, a
   dark-theme-only colour change failing a dark baseline, and a 768px overflow failing a 768
   baseline — and T541 (Phase 4, PR #67) ran and reverted the fourth (a primitive importing a
   composite, caught by `tier-deps.mjs`, itself re-run clean above). This is the citation
   `docs/risks.md`'s "Storybook renders components in both themes" item is ticked on below: the
   dark-only breakage is what proved a dark capture is actually compared, not merely captured.
9. **Storybook explains the system without the source.** Already run and recorded above in this
   file, "Scenario 9 — Result": a mixed verdict, not a pass. Q1's colour-blind-redundancy half is
   still open; Q2 and Q3 failed at run time and were fixed after, which is carried forward here
   unchanged rather than re-summarised as a pass.

### The fifteen production-readiness criteria (spec.md)

1. **No arbitrary value, no hand-written variable reference, no comment reporting a missing
   token.** **Met.** `token-scale.mjs` exit 0 over both trees (evidence above); the gap register
   (`packages/design-system/specs/README.md`, "Token gap register") states "No gap is open as of
   2026-09-05 (T529)."
2. **The gap register has no entry open with only an interim workaround.** **Met.** Same register:
   every DS-1/2/4/5/6/7/8/9/10 row is closed, DS-3 is a dated refusal (2026-09-05) naming the colour
   route as replacement. Read directly this session (`packages/design-system/specs/README.md` lines
   610–810).
3. **Every route renders exactly one main landmark; no route declares its own content width or
   page padding.** **Partly met — the padding/width half is proven, the landmark-count half is not
   re-verified this session.** `token-scale.mjs`'s application-layout pass (27 files clean) is
   direct, live evidence for the second half. The first half needs
   `tests/visual/app-routes.spec.ts` run in a browser; T553 wired it to enumerate all twelve routes
   in both themes and it is read, not executed, here. Its last completed CI run (see "CI's actual
   state" above) failed on Storybook-story baselines, not named as a landmark-count failure in the
   log excerpt this session captured, but that CI run's own app-routes results were not isolated
   from this session's log inspection — recorded as unconfirmed rather than assumed passing.
4. **Both themes reachable, honour system preference, remember override, no flash.** **Partly
   met.** The mechanism exists and is unit-tested (`ThemeProvider.test.tsx`) and statically wired
   (`index.html`'s pre-hydration script); the flash-free first paint and the reload-survives-override
   behaviours are the manual scenario 6 above and were not run this session.
5. **Every drawn colour pair measured and asserted in both themes; a colour change fails a test.**
   **Met**, with the pairing-convention caveat the register itself carries: `build-tokens.test.mjs`
   (25/25, above) asserts the table `README.md` carries, and the pairing-convention fixes (T034c,
   DS-10) closed three real instances of "asserted the wrong background" found by reading components
   rather than by re-checking a table — the mechanism this criterion asks for, demonstrated by having
   actually caught something.
6. **The verification suite captures both themes at all three widths, diff-scoped on PR, full
   nightly.** **Structurally met, not confirmed green on the current commit.** `story-baselines.mjs`
   (above) confirms every one of 537 stories has all 6 theme x width baselines on disk and the count
   agrees with the built index — the coverage claim holds structurally. Whether the comparison
   itself currently passes is exactly what the "CI's actual state" paragraph above records as
   unconfirmed (last completed run red on other-than-app-routes stories; no green run yet against
   the regenerated baselines).
7. **An automated accessibility check runs and fails the change on a finding.** **Partly met, and
   recorded more narrowly than the first pass of this walk recorded it.** `a11y-allowlist.mjs` exit
   0, "empty — nothing to validate" — T559 drove every prior entry to zero by fixing what it named
   rather than deleting it, and the check is wired into the `web` job of `.github/workflows/pr.yml`
   (read, not re-verified here since that file is out of this task's touch-scope). That is real, but
   it proves only that no _known_ violation is currently suppressed; it says nothing about _when_
   the scan that would catch a new one runs. `axe-core` executes exactly once in this codebase,
   inside `tests/visual/stories.spec.ts` (~line 317), which needs a built Storybook and a real
   browser — CI only, never at the point a component is authored. The two `landmark-unique` guards
   that exist outside it — `Panel.test.tsx` (~lines 121-131) and `MatchDetailPanel.test.tsx`
   (~line 283) — are hand-written per-composition DOM assertions pinned to the two cases that were
   caught, not a check for the class. This matters concretely, not hypothetically: this exact defect
   (a hidden `Table` caption repeating an ancestor heading) has shipped three separate times within
   this one phase, caught by CI's axe pass each time and never at write-time — two point-fixes have
   not stopped a third. Recorded as a dated gap rather than closed silently:
   `packages/design-system/specs/README.md`'s "Accessibility mechanism gap register", **owner T579,
   fix by 2026-09-15** — the fix is cheap, one generic vitest assertion reusing `axe-core` (already a
   dependency) against a rendered tree, reused across component test files instead of hand-written
   per composition.
8. **Every component spec answers every state in the closed vocabulary, verified mechanically.**
   **Met.** `spec-completeness.mjs` exit 0: "41 component directories … answers all 9 sections and
   all 10 states" (above), and the check is wired into CI (T571). **What "met" does not cover**: the
   check is lexical — it verifies a state is _answered_, not that the answer is _true_ against the
   component it describes. It cannot catch a spec that confidently describes behaviour the code does
   not have, which is exactly what the fifth-pass review's finding B2 was: six specs answered
   `active` in full, passed this check, and still asserted the pre-fix behaviour a code change had
   already retired (see "Reviewer gates" below, round 5). A green run here is evidence the closed
   vocabulary is covered, not evidence any one answer is correct — that is what a review, not this
   script, is for.
9. **Every component has stories for variants, applicable states, a realistic composition,
   responsive behaviour, accessibility behaviour; every story deterministic.** **Met for coverage
   and structure, not re-verified for determinism this session.** `story-baselines.mjs` confirms
   structural completeness; determinism itself (T568, "render each twice and compare") needs
   `pnpm test:visual`, which drives a browser and was not run. The clock-freeze fix (`37f0c02`) and
   its regression are cited as the mechanism, not re-exercised.
10. **Storybook documents every foundation interactively; comprehensible without the application
    source.** **Not met.** Recorded exactly as `packages/design-system/specs/README.md`'s
    "Storybook documentation gap register" and scenario 9 above state: zero `docs`/autodocs entries,
    docgen off (no prop tables), no component states its purpose in a sentence, no component links
    its `sr-only` naming shape to Foundations → Iconography. **Owner: T578, fix by 2026-09-21.**
    FR-040 is likewise not met, for the same four reasons.
11. **Every component declares its tier; no primitive depends on a domain composite.** **Met.**
    `tier-deps.mjs` exit 0 (above), and `spec-completeness.mjs`'s per-component tier/surface-class
    check (T571) is part of the same green run.
12. **Everything intended for use is reachable from the package's public surface.** **Not
    independently re-verified this session.** No script in the seven-command gate list checks
    `packages/design-system/src/index.ts` against the component directory tree; this criterion's
    evidence, if any, would need a dedicated grep or a read of `index.ts` against every exported
    directory, which this walk did not perform. Recorded as **unverified**, not asserted met.
13. **Keyboard operation, focus visibility, touch footprints and reduced motion verified on every
    route in both themes.** **Partly met.** Component-level: `Dialog`'s focus trap has a regression
    test since `2b8d05c` (fails on the pre-fix implementation, focus on `<body>`); `tests/visual/focus-ring.spec.ts`
    exists and is wired to check focus-visible contrast per component per theme (read, not run);
    reduced-motion is unit-tested on at least `Table` and `Menu`
    (`Table.test.tsx`, `Menu.test.tsx`, confirmed present this session). Route-level, both-themes
    coverage is the browser scenario this task was told not to attempt and is not confirmed here.
14. **Promotion threshold, admission test, deprecation procedure, breaking-change rule written and
    each applied at least once.** **Met.** `packages/design-system/specs/GOVERNANCE.md` (read this
    session): token admission decided `border` (admitted) and refused an opacity family, both with
    reasoning and call-site counts; the page-wrapper composition is recorded as promoted at its tenth
    occurrence (ten named consumer files); T557's prop-vocabulary reconciliation is recorded as the
    deprecation procedure's one subject. All four procedures have at least one recorded outcome.
15. **`visual-reviewer` returns a pass for every affected component; the general reviewer approves
    against the spec and the constitution.** **Not met, on either half — recorded more narrowly
    than the first pass of this walk recorded it.** This walk found `visual-reviewer` had never been
    run in this feature and ran it immediately afterwards, which has real value: it drove a browser
    and measured rather than reading a diff, and it caught its own missing `visualForceState`. But
    the criterion asks for a pass covering **every affected component**, and T565/T566/T567 touched
    all 41; the run this walk triggered covered six. It was also **run by the same session that
    authored the code** — self-verification, not the independent gate the criterion assumes. The
    honest form is **met for six components, by a non-independent run**, not a flat "met": it
    returned PASS for the six named below, and it did not catch the three blocking defects a later,
    independent third-pass review found — a stale `Field` baseline contradicting the very "48px vs
    40px" evidence this run itself cites, `ProfileSummary`'s `UnlinkInFlight` opening the wrong menu,
    and `Button`'s active state being identical to hover on three variants. The second half is not
    met either: the general reviewer has returned REJECT four times as of this update, and the pass
    over the remediated tree is outstanding. See "Reviewer gates" below.

**FR-037** (not one of the fifteen numbered criteria above, and no named success criterion below
covers it either — checked here because a third-pass adversarial review found it silently absent
from both, finding M2c): "Two states of the same component MUST be distinguishable from one another
by more than colour, and MUST be distinguishable in a still image."

**Updated 2026-09-09, after the third and fourth review rounds' fixes both landed and were
independently verified against the checked-in baselines, not narration.** The third pass named three
breaches (`Button`'s `secondary`/`ghost`/`destructive` `active`==`hover`; `ProfileSummary`'s
`UnlinkInFlight`==`SwitcherFocusVisibleAndOpen`; `AccountErasurePanel`'s `minting`==`confirming`);
that fix landed and a capture confirmed all three pairs now hash differently. The **fourth** pass then
found the same literal pattern — one surface token repeated at both `hover:` and `active:` — live in
eleven more files, measured byte-identical against the same capture: `Table`, `Link`, `MatchRow`,
`FavouritesList`, `PlayerResultRow`, `Footer`, `PrivacyNotice` (three call sites),
`ThirdPartyObjectionForm`, `AccountErasurePanel`. Two specs (`structural-tier.md`) had stated the
identity as deliberate design, citing FR-038's "a difference a spec states" clause — which governs
consistency _between_ controls, not a control's own two states; FR-037 carries no such clause. That
misreading is why the class went unnoticed through two review rounds.

The class-wide fix landed in the commit after this walk was last touched and has since been
independently verified, pair by pair, against the checked-in baselines (`md5`, not the fix's own
claim): every one of the fourteen pairs now hashes differently. Rows and inline links moved to a
non-colour signal (a reserved left border painted on press; an underline-offset shift) rather than a
second fill, which is what the requirement's "more than colour" actually asks for.

**Updated again 2026-09-09, after the fifth review round.** The fifth pass found two more things of
the same shape: **B2** — the fourth pass's code fix had landed but only two of its eleven call
sites' specs were corrected to match, so six specs (`footer.md`, `privacy-notice.md`,
`third-party-objection.md`, `favourites-list.md`, `player-search.md`, `match-history.md`) still
asserted the pre-fix, colour-only behaviour even though the code no longer did — and **three
components with no `hover:`/`active:` class at all** (`Tooltip`, `CountryFlag`,
`ProfileSummary`'s flag render), which every prior round's grep for a repeated fill missed because
there was no class to repeat: hover and pressed render as byte-identical images by omission, not by
a shared token. The six spec passages are corrected in the same change that records this update (see
"Reviewer gates" below, round 5); the three components are being fixed by a concurrent change not
yet confirmed landed as of this sentence.

**FR-037 now holds against every instance a review has found through round four**, verified
independently, and the six specs above are now accurate against the code that already existed. This
is not the same claim as "no instance remains" — five rounds each found what the previous round's
fix or its spec did not cover, and a sixth review pass, once the concurrent `Tooltip`/`CountryFlag`/
`ProfileSummary` fix has actually landed, is what decides whether the pattern has stopped this time.
Do not read either sentence above as "APPROVE"; read the "Reviewer gates" section for the actual
verdict history.

### Named success criteria

- **SC-001** (no off-scale value, no missing-token comment): **holds.** `token-scale.mjs` exit 0,
  both trees.
- **SC-001a** (every colour/typography value newly derived or recorded as retained; contrast
  re-measured against shipped values): **holds.** `packages/design-system/specs/README.md`'s "Token
  gap register" section documents every closure with the re-derivation reasoning (DS-1/2 darkened
  `accent`/`border-strong`; DS-8 split the mono role; the "Rounding correction, T526" paragraph
  states the whole table was re-measured from `color.json`'s shipped hexes rather than transcribed
  from the decision record, finding and correcting two stale numbers in the process).
- **SC-002** (no gap open with only an interim workaround): **holds.** Same register, "No gap is
  open as of 2026-09-05."
- **SC-003** (every route exactly one main landmark; no route declares content width/padding):
  **partly holds** — the layout-class half is live-verified (the scenario-5 grep, empty); the
  landmark-count half needs the browser run named above and is not reconfirmed this session.
- **SC-003a** (nothing remains on pre-existing foundations): **partly holds** — `token-scale.mjs`'s
  clean pass over both trees is direct evidence there is no retired-token or application-layout
  residue in source; T558's sweep task is `[x]` in `tasks.md`. Not independently re-swept this
  session beyond what the token-scale gate itself catches.
- **SC-005** (dark-preferring reader opens dark, no flash, override survives reload): **does not
  hold as demonstrated** — this is exactly quickstart scenario 6, manual by its own definition, not
  run in this session. The mechanism exists (cited above) but SC-005 asks for the observed outcome,
  which only a browser shows.
- **SC-006** (every published story verified in both themes at all three widths; diff-scoped PR
  gate, full nightly): **does not hold as confirmed on the current commit** — see "CI's actual
  state" above. Structural coverage (`story-baselines.mjs`) holds; the comparison itself is
  unconfirmed green on `1b795bc`.
- **SC-008** (changing a colour token re-asserts every pair a component paints): **holds, and was
  demonstrated three times finding a real defect** — the T034c/DS-10 pairing-convention fixes in
  the gap register are the citation: each found a pair a component actually painted that an
  assertion against the "conventional" background had missed.
- **SC-010** (no loading/unobserved value renders as a digit; unobserved is visibly distinct):
  **holds.** `StatValue.test.tsx` (read this session) asserts "never renders 0, – or -- while
  loading", "states why in words, in secondary colour never `text-primary` … never an em dash", and
  "never renders a digit for a genuinely-zero delta or value, and a real zero still renders as
  data" — all three exercised by `pnpm test` above.
- **SC-011** (a person with Storybook and no repository access names the component, the token, the
  state for a stated need): **partly holds** — quickstart scenario 9's own recorded result: Q1
  partly answered (found the component, missed the accessibility half), Q2 and Q3 failed at run
  time and pass against the tree as it stands today after fixes. Not re-run this session; carried
  forward as recorded.
- **SC-013** (every spec answers every state, verified mechanically): **holds, with the same limit
  named at production-readiness item 8 above** — `spec-completeness.mjs` exit 0, wired into CI
  (T571), verifies every state is answered, not that the answer is true.
- **SC-014** (a composition repeated past the promotion threshold is promoted or the refusal is
  recorded): **holds.** `GOVERNANCE.md`'s promotion-threshold record: the page wrapper, ten
  occurrences, promoted.
- **SC-016** (reduced motion stops every loop and gives every transition no perceptible duration):
  **partly holds** — unit-tested on at least `Table` and `Menu` (confirmed present this session);
  not confirmed as a system-wide property across all 41 components by this walk, and the
  Storybook reduced-motion stories (T567, FR-055) that would demonstrate it visually were not
  opened in a browser.

### Reviewer gates

**`visual-reviewer`**: no invocation of this agent — a PASS or a reasoned FAIL naming a component —
appears anywhere in feature 005's commit history, across all six phases (`git log --grep
"visual-reviewer"` over `main..HEAD` and over each of the five already-merged phase branches
returned only artifact edits to `.claude/agents/visual-reviewer.md` itself, never a verdict; contrast
with 003/004, which each carry commits literally named "visual-reviewer PASS"). The gate had never
been run, so it could not have passed — a gate believed rather than held, which is the shape phase
1 exists to end.

**It was run as soon as this walk exposed that**, against the remediated tree, and returned **PASS
for six components — not every component Phase 6 touched, and not by an independent gate**: `Menu`'s
intrinsic checkmark (reserved width confirmed to hold unchecked labels flush, so the mark is a shape
difference and not a shift), `ProfileSummary`'s three coexisting signals on one row, the focus ring
painting for the first time on `Page`, `Link` and `Table` in both themes at all three widths with no
clipping, `Dialog`'s Shift+Tab landing on the last action instead of `<body>`, `Field`'s `lg`
measured at 48px against `md`'s 40px, and `MatchDetailPanel`'s two landmarks no longer sharing an
accessible name. It verified by driving a real browser and measuring, not by reading the diff — and
reported that its own first capture pass had forgotten to apply `visualForceState`, the same defect
class this phase fixed — which is real value a post-hoc self-run has. It is not, however, what the
criterion asks: T565/T566/T567 touched all 41 components, this run covered six of them, and the
session that ran it is the same one that wrote the code, not an independent gate. It also did not
catch the three blocking defects an independent third-pass review found afterwards on components
this run itself had passed or left unexamined: a stale `Field` baseline that contradicts this run's
own "48px vs 40px" citation above, `ProfileSummary`'s `UnlinkInFlight` opening the wrong menu, and
`Button`'s active state being identical to hover on three variants. Item 15's first half is therefore
**met for six components, by a non-independent run** — not a flat "met" — and the second is not met
at all.

`docs/risks.md`'s "visual-reviewer returns a reasoned FAIL" item still stays unticked below: the
verdict was a PASS, and that item asks for a reasoned FAIL specifically.

**General `reviewer`**: run five times as of this update, **REJECT all five**, each round's findings
remediated in the commits that follow it:

1. `b161d2f` — the tree was red (`tier-deps.mjs` failing on `Page` importing `MatchList`), eleven
   state answers the completeness check had never checked per-component, `SearchBox`'s module-scoped
   clock freeze bleeding across stories, a 320px-pinned story width, a duplicated accessible name,
   several `GOVERNANCE.md` citation errors, and "no value changes in this phase" being false.
2. `2b8d05c` — `Dialog`'s focus trap excluding its own mount-focus target from the tabbable set, a
   `GOVERNANCE.md` date arithmetic error, an attribution note naming a capture "HEAD" one commit
   before it stopped being HEAD, and 375px living in two files.
3. Findings against the tree at `eeec847`: `Field`'s size fix shipped without a recapture, so its
   baselines still encoded the bug the fix closed; `ProfileSummary`'s `UnlinkInFlight` opened the
   wrong menu; `Button`'s `secondary`/`ghost`/`destructive` active state was identical to hover.
   Remediated in `1ca55e7`.
4. Findings against the tree at `bc3849f`'s predecessor: the `Button` fix covered one component and
   the identical `hover:X active:X` pattern was live in eleven more files (`structural-tier.md`
   citing FR-038's escape clause for a shape FR-037 governs, which has none); `Dialog` and `Callout`
   were painting Chromium's user-agent focus outline while two specs written in this same phase
   described it in opposite, both-wrong directions; the `UnlinkInFlight` fix from round 3 only
   worked at 375 because `Menu`'s popover had no inline-axis collision handling; `ProfileSummary`'s
   `PrimaryChangeInFlight` was `UnlinkInFlight`'s sibling and had been left behind again. Remediated
   in `bc3849f`.
5. Findings against the tree at `dd3041d`: **B2 (blocking)** — round 4's code fix (the
   reserved-border / underline-offset technique) landed in eleven files, but only two of the specs
   describing those call sites were corrected (`structural-tier.md`'s `Table` and `Link` sections);
   six more still asserted the pre-fix, colour-only behaviour — `footer.md`, `privacy-notice.md`
   (three call sites), `third-party-objection.md` (which also named two wrong tokens,
   `accent-active` and `accent-hover`, retired from inline links by T522), `favourites-list.md`,
   `player-search.md` and `match-history.md` — the identical failure mode round 4 itself was named
   for, one layer up: a fix landing in the code without its spec passages following it. **M4** —
   this section and the FR-037 note above it would go stale the moment a sibling change landed,
   with nothing forcing either back into agreement. **Three further live FR-037 gaps** — `Tooltip`,
   `CountryFlag` and `ProfileSummary`'s flag render hover and pressed as byte-identical images,
   carrying no `hover:`/`active:` class at all, so they matched none of round 4's greps — found and,
   as of this entry, being fixed by a change concurrent with this one, not yet confirmed landed. A
   corrected record, not a defect: this file's own scenario-9 note that `Menu/Selection`,
   `Menu/ProfileSwitcher` and `Menu/FocusVisible` render pixel-identically was itself wrong (see the
   FR-037 note's own correction below). Remediated in the same change that lands this documentation
   pass: the six spec passages, the two wrong token names and this section's own accuracy are
   corrected together; the three additional components are tracked as open against the concurrent
   fix, not asserted closed here.

**A sixth pass, against the tree this remediation lands on, is what settles whether the pattern has
finally stopped.** Production-readiness item 15's second half and the general "the general reviewer
approves" clause of T577 itself are recorded **REJECT x5, remediated, re-review outstanding** — not
approved. Five rounds each finding what the previous round's fix did not cover is itself evidence
worth weighing: either the sixth pass finds nothing left of this shape, or it does not, and only
running it settles which. Read this note as of its own date — 2026-09-09 — and re-derive nothing
from it once a sixth pass has actually run; that pass's own entry, appended above rather than
overwriting this one, is what carries forward.

### `docs/risks.md` front-end items

Ticked only where a scenario in this walk actually proves the line, per this task's explicit
instructions:

- **"Storybook renders components in both themes"** — ticked. Evidence: quickstart scenario 8 (T511,
  Phase 2, PR #64) changed a dark-theme-only colour value and confirmed a dark baseline failed —
  proof that a dark capture is compared, not merely taken, which is what this line asks.
- **"`visual-reviewer` returns a reasoned FAIL on a component deviated from its spec"** — left
  unticked. No invocation of `visual-reviewer` returning any verdict, pass or fail, exists anywhere
  in this feature's history (see "Reviewer gates" above). Ticking this would assert an event that
  did not happen.
- **"Pull-request visual regression runs only on touched stories"** — left exactly as it was found
  (unticked). This property is architectural (FR-061, design decision 11: scoped by story, never by
  axis) rather than something this walk's scenarios demonstrate, and re-verifying a PR's own CI
  scoping needs a live PR run, which is also where this walk found the branch's actual CI state to
  be unconfirmed on the current commit (see above) — left untouched rather than ticked on inference.
