# Implementation Plan: Design System Foundations

**Branch**: `005-design-system-foundations` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-design-system-foundations/spec.md`

## Summary

Turn thirty-two good components into a system: complete the token foundations and re-derive the
palette and typography against them, add the structural tier that assembles a screen, make the dark
theme reachable, and bring the verification suite up to the axes its own review protocol already
claims. Every existing component and every existing route moves onto the new foundations inside this
feature.

**Phase 0 confirmed every claim the spec makes, and found five the spec does not.** The nested-main
defect is ten deep, not nine, and two of the ten are inside the design system. Three components are
built and unimportable. The tier boundary the spec asks for already exists, assigned component by
component, in Storybook story ids — the one place nothing enforces it.

Two findings change the plan rather than only adding to it. **None of the three named typefaces is
loaded anywhere**: `Inter`, `Fraunces` and `JetBrains Mono` are named in the token source, and every
surface in the product and in Storybook has always rendered `system-ui`, `Georgia` and
`ui-monospace` instead — the unreachable dark theme's defect in the one family the spec did not
check, and it decides what phase 2 re-derives against. And **the suite's coverage is smaller than
its baseline count suggests**: there are 299 stories and 279 baselines, so 25 stories have never been
captured — `Tooltip`'s thirteen were never committed at all — while 3 baselines name stories that no
longer exist. The matrix is therefore 1,794 captures, not the 1,674 the baseline count implies, and
phase 1 reconciles the two sets before expanding either.

**The plan's central engineering problem is that three phases repaint every pixel** — the palette
and typefaces, the structural tier's rhythm, and the retrofit — and a visual diff carries no
information when everything is expected to change. The ordering below is chosen so that repaint
happens as few times as possible, and so that the one phase that changes the harness changes no
value: phase 1's captures at the existing axes — 1280 light, and 375 light for the ten stories
tagged `visual-mobile` today — must come back **byte-identical** to the baselines that exist today,
proved from the regeneration commit rather than from Playwright's tolerance, which is the only proof
available that the harness change is correct, and it is available only before anything else moves.

Full reasoning and evidence: [research.md](./research.md).

## Technical Context

**Language/Version**: TypeScript 5 / React 19 (design system, application); Node 20+ (token
generator, checks, visual runner). No Python changes.

**Primary Dependencies**: Tailwind v4.3.3, Storybook 10.5.9, Playwright 1.62, Vite 8, Vitest 3,
TanStack Router/Query 5. **Two additions**: `@axe-core/playwright` (FR-058) and, conditional on
[research.md](./research.md) D6a resolving in favour of loading them, three self-hosted open-licence
typeface families. No runtime dependency is added to the application bundle beyond the fonts.

**Storage**: None. No database change, no migration, no API change. The theme override is a
`localStorage` key in the reader's own browser, never transmitted.

**Testing**: Vitest + Testing Library (behaviour); `node --test` (token generator); Playwright
visual regression against the static Storybook build, diff-scoped by `scripts/visual/run.mjs`;
`axe-core` inside that same story loop; `tsc -b` across the workspace, which is the only thing that
catches shared-type drift between the design system and the application.

**Target Platform**: Vercel Hobby `cdg1` (phase 1 hosting); OVH VPS (phase 2 hosting). Browser-side
only; no server rendering is assumed and none is introduced.

**Project Type**: Web application — this feature touches the shared design system and the React SPA
only.

**Performance Goals**: No regression in first paint. The theme resolution script is inline,
synchronous and under 500 bytes, and it runs before the stylesheet so no reader sees a flash
(FR-015). Self-hosted fonts, if adopted, are preloaded and subset so the first paint is not a swap.

**Constraints**: No arbitrary value and no hand-written `var(--ds-*)` anywhere in the design system
or the application, enforced by a check rather than by review; both themes reachable and verified;
every pair a component actually paints measured and asserted; every route exactly one main landmark;
no component left on the pre-existing foundations.

**Scale/Scope**: 7 user stories, 71 functional requirements, 18 success criteria. 32 components
retrofitted and re-tiered, 9 application routes, 24 component specs amended, 9 new structural
primitives, 6 gap-register entries closed, 3 unexported components published, 2 new token families
and 3 new token groups. **279 baselines become 1,794** — 299 stories x 2 themes x 3 review widths —
and are regenerated three times across the feature. Six phases, each independently green and separately
mergeable.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — the verdicts below are
the post-design ones._

| #        | Principle                                     | Verdict                                    | How this feature satisfies it                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| -------- | --------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **I**    | Capture Outranks Analysis                     | **N/A**                                    | Nothing in this feature reaches the ingester, the capture enqueue, the budget or the replay path. No Python file changes. `expired_total` cannot move. The one thing to hold: this is a large display feature, and principle I resolves any contention over review attention in favour of capture — so no phase here may block a capture fix behind its baseline regeneration.                                                                                     |
| **II**   | Python Backend                                | **PASS**                                   | No business logic is added to the front end: the structural primitives carry layout, not domain rules, and FR-028's tier boundary makes that enforceable rather than aspirational. The new checks are Node, consistent with `built-css.mjs`, `spa-routing.mjs` and `config-preflight.mjs` — front-end build checks have always been Node here; the principle's "parsing and data analysis are Python" is untouched.                                                |
| **III**  | All External Data Goes Through a DataProvider | **PASS**                                   | No outbound connection is added. The typeface decision (D6a) is deliberately constrained to **self-hosting or nothing**: a Google Fonts link would be a runtime request from `apps/web` to a third party, which this principle forbids and which would also hand a reader's IP address to a non-EU host. Fonts are copied in at development time by a person and served as static files, the same rule feature 004 adopted for asset packs.                       |
| **IV**   | Raw Is Sacred, Derived Is Disposable          | **N/A**                                    | No replay, no raw artifact, no derived record. The generated token files are recomputed from `packages/design-system/tokens/*.json` by `build-tokens.mjs` on every build, which is the principle's shape applied to a much smaller thing.                                                                                                                                                                                                                                                |
| **V**    | Parsing Runs in an Isolated, Pluggable Engine | **N/A**                                    | No parsing.                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **VI**   | Tokens First                                  | **PASS** — this feature is the principle's subject | Principle VI is violated inside the design system today, in nine places, because six token gaps left components nothing to reach for. All six close (research D5, D7, D8, D9, D10), the utility vocabulary gains the namespaces it was missing, and `scripts/checks/token-scale.mjs` turns "no hard-coded value" from a review habit into a gate — including the case that has survived a year unnoticed, a hand-written `var(--ds-*)` in a class name.        |
| **VII**  | Visual Tests Are Mandatory                    | **PASS** — and the gate stops overstating itself | The court/factory split is unchanged: pull requests test the stories the diff affects, full coverage runs nightly. What changes is that a story under test is now captured across the axes the review protocol always claimed — both themes, all three review widths — so "verified" means one thing. FR-061 and this principle agree; the scoping is by story and never by axis.                                                                            |
| **VIII** | No Secrets in the Clear                       | **PASS**                                   | No new secret and no new environment variable. The baseline-regeneration workflow (research D3) commits with the Actions runner's own built-in token under `contents: write`, scoped to that job, with no secret added to the repository.                                                                                                                                                                                                                                     |
| **IX**   | GDPR by Design                                | **PASS**                                   | No new personal data, so no processing-register change. The theme override is a preference in the reader's own browser: never sent to this service, never joined to a profile, and readable by nobody but the reader. A cookie was rejected for exactly that reason (research D11). All regions remain EU, and D6a's self-hosting rule keeps a reader's browser from contacting a font CDN at all.                                                              |
| **X**    | Intellectual Property                         | **PASS, with one mandatory gate**          | The palette is re-derived to express the established character more deliberately, never by reusing a Microsoft asset — the eight `player-*` colours are canonical game colours already licensed and recorded by feature 004, and are explicitly **excluded** from the re-derivation and marked retained. If D6a resolves in favour of self-hosting, every font file lands with the five-field licence record, and `scripts/checks/asset_packs.py` plus the `asset-packs` paths filter are extended to `packages/design-system/tokens/fonts/` in the same change — the check is hard-scoped to `packages/game-assets` today and would neither see nor run on a font anywhere else (T523). |
| **XI**   | Documentation Is in English                   | **PASS**                                   | Every artifact, spec, comment and commit message is English.                                                                                                                                                                                                                                                                                                                                                                                                     |
| **XII**  | Portable by Construction                      | **PASS**                                   | The theme script is static markup in `index.html`, identical under Vite, Vercel and any static server. Fonts, if adopted, are static files under one prefix, mounted the same way `packages/game-assets` already is. No filesystem read at runtime, no local state, nothing that runs only on Vercel or only on a VPS.                                                                                                                                        |

**Post-design re-check**: no verdict changed between the pre-Phase-0 and post-Phase-1 passes. Two
items gained a named obligation they did not have before — III and X, both from the typeface finding
in research D6a, which did not exist as a question until Phase 0 measured it.

**One reading recorded rather than left implied.** Constitution VII says CI "tests only the stories
the diff affects". The matrix expansion does not weaken that: the *selection* is still the affected
stories, and each selected story is now captured across its full axis set. A future change that
narrows the axes to save time would satisfy the letter of VII and break FR-061, which is why the
prohibition lives in the runner and not only in prose.

## Project Structure

### Documentation (this feature)

```text
specs/005-design-system-foundations/
├── plan.md              # This file
├── research.md          # Phase 0 — D1..D17, the four findings the spec does not carry
├── data-model.md        # Phase 1 — token families, tiers, surface classes, the review matrix
├── quickstart.md        # Phase 1 — how to verify each phase, and how to regenerate baselines
├── contracts/
│   ├── token-families.md      # Every family, its admission test, and its utility vocabulary
│   ├── structural-tier.md     # The nine primitives: props, landmarks, what each owns
│   └── verification-matrix.md # What is captured, when, and what fails the change
├── checklists/
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
packages/design-system/
├── tokens/
│   ├── breakpoint.json            # NEW — one definition, consumed by styling and by structure
│   ├── border.json                # NEW — hairline, ring, ring-offset (closes DS-4)
│   ├── color.json                 # re-derived; + link roles; player-* retained and recorded
│   ├── font.json                  # re-derived; + role group (display/body/supporting/numeric/machine/identifier)
│   ├── size.json                  # NEW — page, panel, measure (closes DS-6)
│   ├── motion.json                # + animation group (spin, pulse) for looping animations
│   ├── space.json                 # + the rhythm rule: within, between, section
│   ├── icon.json                  # unchanged values; now reachable as utilities
│   ├── elevation.json             # + what may sit at each level
│   ├── build-tokens.mjs           # emits @utility blocks, --animate-*, --breakpoint-*, --container-*
│   ├── build-tokens.test.mjs      # the contrast assertions, re-measured against what ships
│   ├── tailwind.css               # the one stylesheet every consumer imports
│   ├── fonts/                     # conditional on research D6a — self-hosted, licence-recorded
│   └── generated/                 # tokens.css, preset.css, tokens.ts — never hand-edited
├── specs/
│   ├── README.md                  # gap register emptied; contrast table re-measured; rules extended
│   ├── GOVERNANCE.md              # NEW — admission, promotion, deprecation, breaking change
│   └── structural-tier.md         # NEW — the nine primitives' specs
├── src/
│   ├── primitives/                # NEW tier — Page, Section, Panel, Text, Link, Table, Field,
│   │                              # EmptyState, ErrorState, plus the existing primitives
│   ├── composites/                # NEW tier — the domain components, including SiteHeader/Footer
│   ├── screens/                   # NEW tier — SignInScreen and the panels routes mount
│   ├── theme/                     # NEW — ThemeProvider, useTheme, the toggle
│   ├── lib/                       # cx, rowLink, useDelayedVisible, useBreakpoint (now generated)
│   └── index.ts                   # the deliberate public surface (FR-027)
├── .storybook/                    # foundation documentation pages; a11y addon kept
└── __screenshots__/               # 279 -> ~1,674 baselines, regenerated in CI only

apps/web/
├── index.html                     # the inline, blocking theme-resolution script (FR-015)
└── src/
    ├── routes/                    # __root.tsx stops rendering <main>; routes compose Page
    ├── features/                  # ten containers lose their wrappers, widths and spacing
    └── index.css                  # unchanged — it already imports the one preset

tests/visual/
├── stories.spec.ts                # theme x width axes; axe scan at the capture point
├── focus-ring.spec.ts             # extended to every focusable primitive, both themes
└── app-routes.spec.ts             # one main landmark per route; both themes

scripts/
├── visual/
│   ├── run.mjs                    # emits the full matrix per selected story; no axis flag
│   └── a11y-allowlist.json        # NEW — dated, named, empty by the end of phase 5
└── checks/
    ├── token-scale.mjs            # NEW — arbitrary values, raw literals, hand-written var()
    └── tier-deps.mjs              # NEW — no primitive imports a composite; nothing imports apps/

.github/workflows/
├── pr.yml                         # + token-scale, tier-deps; visual job runs the matrix
├── nightly.yml                    # full matrix over every story
└── baselines.yml                  # NEW — manual dispatch, regenerates on Linux, commits

CLAUDE.md                          # the filing rule gains the subject-vs-liveness distinction
```

**Structure Decision**: The feature stays inside `packages/design-system` and `apps/web`, plus the
three shared directories that hold the verification suite (`tests/visual`, `scripts`,
`.github/workflows`). No new package. The one structural change is inside the design system's own
`src`, where the flat `components` directory becomes the three tiers FR-028 requires, because a tier
that does not determine where a component lives is a label rather than a boundary — and the
judgement has already been made once, in Storybook story ids, where nothing can enforce it.

## Phases

Six, in this order. Each is independently green and separately mergeable, which is deliberate: one
pull request carrying all of this would be unreviewable, and the spec's own Risk 1 asks for the
opposite. `/speckit-implement` is run one phase at a time, naming the task range and the stop
condition.

| # | Phase                            | Stories        | Repaints everything | Why here                                                                                       |
| - | -------------------------------- | -------------- | ------------------- | ---------------------------------------------------------------------------------------------- |
| 1 | Verification machinery           | US5            | no                  | The only phase where the 1280-light captures can prove the harness change by being identical.  |
| 2 | Foundations, palette, typefaces  | US1, US4       | **yes**             | Everything downstream needs tokens that exist; the palette and the fonts repaint together once. |
| 3 | Theme reachability               | US3            | no                  | Small and application-only; makes phase 2's dark half observable by a person, not only a test. |
| 4 | The structural tier and the tiers| US2            | **yes**             | Needs phase 2's tokens; carries the directory move, so baseline names change once.             |
| 5 | The retrofit                     | US2, US4       | **yes**             | Its targets do not exist until phase 4; pays down phase 1's accessibility allowlist.           |
| 6 | Storybook and governance         | US6, US7       | no                  | Governance is written once there is something to govern; documentation once the system is done.|

Phase 1 opens by reconciling the story set and the baseline set at the existing axes — capturing the
25 uncaptured stories, deleting the 3 orphans, and adding a set-equality check — because multiplying
an unreconciled set by six multiplies the discrepancy with it, and phase 1's identity proof only
means something over stories that have a baseline to be identical to.

Phase 1 also carries the one unknown the plan cannot size in advance: the accessibility finding
volume across 32 existing components. `scripts/visual/a11y-allowlist.json` is the valve — each entry
dated and naming the fix owed — and phase 5 empties it. A check fails if an entry outlives the
feature.

## Complexity Tracking

No constitution violation requires justification. Two decisions overrule a written suggestion
elsewhere in the repository and are recorded here so a reader does not treat either as an oversight.

| Decision                                                     | Why                                                                                                                                                                                                                                   | Alternative rejected because                                                                                                                                                       |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| A `border` family, rather than ratifying Tailwind's widths   | DS-4's own entry suggests ratification is defensible. FR-062 needs a mechanical check that an off-scale value fails, and Tailwind's numeric width scale is unbounded — `border-7` compiles — so ratifying it gives the checker nothing to enforce. | Ratification costs nothing to write and leaves FR-062 unenforceable on the one family it was raised about.                                                                          |
| Moving 32 components into three tier directories             | FR-028 requires the tier to determine where a component lives. The judgement already exists in Storybook story ids, unenforced; `tier-deps.mjs` can only check a boundary that is expressed in the filesystem.                          | A manifest naming each component's tier would be a second place for the truth to live, and this repository's stated law is that a fact written twice goes stale in one copy.        |
