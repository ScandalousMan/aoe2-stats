# Phase 0 — Research: Design System Foundations

**Feature**: `005-design-system-foundations` | **Date**: 2026-09-05 |
**Spec**: [spec.md](./spec.md)

Everything below was measured against the repository at `cefc626`, not recalled. Where a number
appears here it was counted; where a mechanism is named it was read in the file that implements it.

## What the spec claimed, and what the code says

Every load-bearing claim in the spec's Context section was checked before planning against it. All
of them hold, and three are sharper than the spec states.

| Spec claim                                                    | Verified                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 32 components, 24 specs, 279 baselines, 7 token families      | Exact. 32 component directories, 32 story files, 24 specs beside `README.md`, 279 PNGs, 7 JSON families.                                                                                                                                                        |
| Six open gap-register entries                                 | Exact: DS-3, DS-4, DS-5, DS-6, DS-8, DS-9.                                                                                                                                                                                                                     |
| Arbitrary values inside the design system                     | Nine, in six files: `w-[1em]`/`h-[1em]` and `animate-[spin_…]` in the spinner, `h-[1.2em]` in `StatValue`, `animate-[pulse_…]` in `Skeleton`, `w-[1em]`/`h-[1em]` and `transition-[fill,opacity]` in `FavouriteToggle`, `max-h-[80vh]` in `Menu`, and four `w-`/`h-[var(--ds-icon-*)]` in `ProfileSummary`. |
| Breakpoints duplicated                                        | Exact. `useMediaQuery.ts` hard-codes `{md:768, lg:1024, xl:1280}`; Tailwind's own defaults carry the same three numbers; the two never consult each other.                                                                                                      |
| Nine containers each nest a second `main`                     | **Ten.** Nine application containers, plus `__root.tsx`'s own outer `main`. Two design-system components (`SignInScreen`, `ThirdPartyObjectionForm`) also render `main`, so a route composing either nests three deep.                                           |
| The word "theme" does not appear in `apps/web`                | Exact. Zero matches across `apps/web/src`, `index.html` and the Vite config.                                                                                                                                                                                    |
| Not one dark baseline; four story files capture below desktop | Exact. `stories.spec.ts` never sets a theme global; four files carry `visual-mobile` (`SiteHeader`, `UploadControl`, `ProfileSummary`, `PrivacyNotice`). No capture at 768 exists at all.                                                                        |
| One monospace treatment carrying three meanings               | Confirmed across eight files: measured numbers (`MatchRow`, `StatValue`, `FavouritesList`), machine text (`AnalysisTimeline`'s error class, `UploadControl`'s filename), unresolved identifiers (`MapThumbnail`, `ProfileSummary`'s fallback heading).           |

Three findings the spec does not carry, each of which changes the plan:

1. **The public surface already leaks.** `src/index.ts` exports 29 of the 32 components.
   `CountryFlag`, `PlayerAvatar` and `Tooltip` are used by other components and cannot be imported
   by a consumer. FR-027 has three concrete subjects, not a hypothetical.
2. **The tier boundary already exists — in Storybook titles only.** Story ids are prefixed
   `primitives-`, `composite-`, `screens-` and `chrome-`. The judgement FR-028 asks for was made
   once and recorded in the one place nothing enforces. The directory layout is flat.
3. **The accessibility addon is installed and inert.** `@storybook/addon-a11y` is in
   `.storybook/main.ts`, but nothing runs it outside the Storybook UI: there is no test runner, and
   `pnpm test` in this package runs `node --test` over the token build plus Vitest. FR-058 needs a
   runner, not an addon.
4. **None of the three named typefaces is loaded.** This is the largest finding of Phase 0 and the
   spec does not carry it. `font.json` names `Inter`, `Fraunces` and `JetBrains Mono`, and every
   surface in the product and in Storybook renders the fallback instead: `system-ui`, `Georgia`,
   `ui-monospace`. There is no `@font-face`, no stylesheet link, no font file in the repository
   outside Storybook's own chrome (`index.html` contains zero `link` tags). The typography that was
   designed has never been seen by a reader or by a reviewer, and all 279 baselines were captured
   in the fallbacks. It is the dark theme's defect exactly — specified, tokenised, unreachable —
   in the one family the spec did not check. See D6a.

5. **Twenty-five stories have no baseline, and three baselines have no story.** The suite has
   299 stories in source (counted from the story files, and matching the built Storybook index) and
   279 baseline PNGs. Thirteen of the uncaptured are `Tooltip`'s, four are `CountryFlag`'s reveal
   states, six are `ProfileSummary`'s board stories and two are `PlayerResultRow`'s — almost all of
   them interaction stories added by feature 004's Phase 8. `Tooltip`'s baselines were never
   committed at all: git records no addition or deletion for any of them. Three further baselines
   name stories that no longer exist, and two more (`app-signed-in-dashboard`,
   `app-signed-out-sign-in`) are legitimately not stories at all — they come from the
   application-route suite. Playwright writes a missing snapshot and fails the test, and the nightly
   run captures every story, so the nightly visual job cannot be green in this state. See D2a.

## D2a — Reconcile the story set and the baseline set before expanding either

**Decision.** Phase 1's first act is to make the two sets agree at the current axes, before any axis
is added: capture the 25 missing baselines, delete the 3 orphans, and add a check that fails when a
story has no baseline or a baseline has no story.

**Rationale.** Multiplying an unreconciled set by six multiplies the discrepancy with it, and the
"byte-identical at the existing axes" proof that D1 depends on is only meaningful over stories that
have a baseline to be identical to. Reconciling first also makes phase 1's diff readable: 25 new
captures at the old axes is a reviewable number, and the same 25 buried inside a 1,794-file
regeneration is not.

**What the check adds that the suite does not have.** Today a story with no baseline fails only in a
run that selects it, and the pull-request runner selects only the stories the diff touched — so a
story merged without its baseline is never selected again and the gap persists silently until the
nightly run, whose failure is a single job among many. A set-equality check runs as its own step in the
`visual` job, after `build-storybook` and ahead of the diff-scoped run — the `web` job never builds
Storybook, so the index it reads does not exist there — names the specific stories, and cannot be
outrun by diff scoping. It is the same shape as
FR-061's prohibition living in the runner: put the guarantee where it can be broken.

**Not in scope here.** Why the 25 were merged uncaptured is a question about a past pull request,
not about this feature's design. What matters is that the state is reachable and that a check now
makes it unreachable.

## D1 — Sequencing: how many times every pixel is allowed to change

**Decision.** Six phases, in this order, each independently green and separately mergeable:
**(1) verification machinery**, **(2) foundations and the re-derived palette**, **(3) theme
reachability**, **(4) the structural tier**, **(5) the retrofit**, **(6) documentation and
governance**.

**Rationale.** Three of these change rendered output globally: the palette (phase 2), the structural
tier's spacing rhythm (phase 4) and the retrofit (phase 5). A visual diff only carries information
when the change is expected to be local, so a phase that repaints everything is verified by the
contrast test, the accessibility check and `visual-reviewer` — never by the diff. That is exactly
why the machinery comes first: phase 1 changes the harness while changing **no** value, so the
captures it produces at the existing axes — 1280 light, and 375 light for the ten `visual-mobile`
stories — must be byte-identical to the baselines that exist today, proved from the regeneration
commit (only additions under `__screenshots__`), not from Playwright's 1% tolerance.
That identity is the proof the harness change is correct, and it is available only in the one phase
where nothing else moves. Run the machinery after the palette and that proof is gone forever.

Phase 3 sits between the palette and the structure deliberately: it is small, application-only, and
it is what makes the dark half of phase 2's work observable by a person rather than only by a test.

**Alternatives considered.** *Machinery last, to capture the ~1,674-baseline matrix only once*:
rejected — it saves CI minutes and spends the palette re-derivation's safety net, and dark is
precisely where a re-derived palette is most likely to be wrong. *One phase, one PR*: rejected — the
result is unreviewable, and Risk 1 in the spec asks for the opposite. *Retrofit before the
structural tier*: impossible; FR-022a's targets do not exist until FR-020's primitives do.

## D2 — The verification matrix: mechanism, volume and cost

**Decision.** Every story runs in both themes at all three review widths. The theme is driven
through Storybook's existing globals parameter; the width through the viewport.

**Mechanism, already proven in this repository.** `tests/visual/focus-ring.spec.ts` navigates to
`/iframe.html?id=<id>&viewMode=story&globals=theme:<light|dark>` and the preview decorator sets
`document.documentElement.dataset.theme` from that global. Nothing new is needed: `stories.spec.ts`
gains theme and width to its loop, and the per-story `visual-mobile` tag is retired because every
story is now captured at 375 as a matter of course. `visual-full-page` stays — it names a property
of the subject, not an axis.

**Volume.** 299 stories x 2 themes x 3 widths = **1,794 captures**, from 279 baselines covering
274 of those stories. The spec's Risk 2 estimated "on the order of 1,600" and accepted it; 1,794 is
that number, measured against the story count rather than the baseline count — the two are not the
same, which is D2a.

**Storage, which is better than it looks.** The 279 baselines occupy 18 MB, ~64 KB each. A naive
reading puts the matrix at ~115 MB, but git stores one blob per distinct content and most stories
are width-invariant, so a story's three widths are three paths onto **one** blob. Only the theme
axis is guaranteed to differ. Steady state is therefore closer to 35-40 MB, and the cost that
actually accumulates is history: each of the three global repaints writes a full new generation.
Budget ~150 MB of repository growth across the feature and state it now rather than discover it.

**Runtime.** Six times the captures on the nightly run, which has no deadline. Pull requests stay
diff-scoped by story, so a one-component change costs six captures per story rather than one — a
change nobody will notice. FR-061's prohibition binds the runner, and the runner is where it is
enforced: `run.mjs` emits the full cartesian product for every story it selects and has no flag
that removes an axis.

## D3 — Baselines are regenerated in CI, never on a developer's machine

**Decision.** Add a manually dispatched `baselines` workflow that runs the suite with
`--update-snapshots=all` on `ubuntu-latest` and commits the result to the branch it was dispatched
from. `all` rather than the default `changed`, so that every selected capture is rewritten from the CI
renderer and a baseline's provenance is never in question — which is what lets phase 1 prove
identity from the commit itself.
Local regeneration is not part of the workflow for any full-page or application-route baseline.

**Rationale.** This repository has already paid for the alternative: full-page baselines captured on
a developer machine differ from CI's Linux renderer by around 2% of pixels, which is why
`app-routes.spec.ts` carries its own `maxDiffPixelRatio: 0.05` and a comment explaining it. A
retrofit of this size regenerates baselines three times; done by hand, that is three opportunities
to commit a subtly wrong generation. The component-story baselines are more tolerant, but a single
rule is easier to keep than a rule with an exception, and the workflow costs one file.

**Alternatives considered.** *Git LFS*: rejected — it solves a storage problem this feature does not
have (see D2) and adds a checkout dependency to a repository that has none. *A tighter diff ratio to
force local capture to fail*: rejected — it makes the suite flaky rather than making regeneration
correct.

## D4 — Breakpoints: one definition, two generated consumers

**Decision.** A new `tokens/breakpoint.json` family with `sm`, `md`, `lg`, `xl`. The generator emits
`--ds-breakpoint-*` into `tokens.css`, maps them onto Tailwind's `--breakpoint-*` theme namespace in
`preset.css` so `md:` and friends derive from them, and emits a `breakpointTokens` record of raw
pixel numbers into `tokens.ts`. `useBreakpoint` imports that record instead of its literal object.

**Rationale.** Tailwind v4.3.3 exposes `--breakpoint-*` as a real theme namespace (verified in the
installed `theme.css`), so styling can be made to derive from our JSON rather than from Tailwind's
defaults. The structural decision needs a **number**, not a CSS variable, because it is passed to
`matchMedia`. Generating both from one JSON file is the only arrangement where the two cannot
disagree, and it keeps the values that ship identical to the values in use today — the review
widths do not move (spec assumption), so nothing re-renders.

**Alternatives considered.** *Read the CSS custom property from JavaScript at runtime*: rejected —
it makes a layout decision depend on stylesheet load order, is untestable in jsdom, and returns a
string that must be parsed. *Ratify Tailwind's defaults and delete the hook's constants by
importing from Tailwind*: rejected — Tailwind exposes no such import, and DS-5's "write it down
either way" is satisfied by owning the numbers, not by pointing at someone else's.

## D5 — Closing the arbitrary values: `@utility`, `--animate-*`, and a `border` family

**Decision.** Three mechanisms, chosen per gap rather than one mechanism forced across all of them.

**Icon sizes (`@utility`).** Tailwind v4 has no theme namespace that maps a fixed size scale onto
`w-`/`h-`/`size-` — the generator already says so in a comment, and that is why `ProfileSummary`
writes `h-[var(--ds-icon-2xl)]`. Tailwind v4 does support the `@utility` at-rule (verified in the
installed `dist`), so the generator emits one custom utility per icon step —
`icon-xs` … `icon-3xl`, each setting `width` and `height` from `--ds-icon-*`. Icons then read
`className="icon-md"`, in the same utility vocabulary as every other family, with no variable
written by hand. This closes the four `ProfileSummary` escapes and the four `1em` sizings.

**Looping animations (`--animate-*`).** Tailwind v4 exposes `--animate-*` as a theme namespace. A
new `animation` group in `motion.json` names the loops the system actually runs — `spin` and
`pulse` — each composing a duration from the same file, emitted as `--animate-spin` /
`--animate-pulse` in the preset alongside their `@keyframes`. `animate-spin` and `animate-pulse`
then close the two `animate-[…]` escapes, and FR-010's "every duration comes from the motion
family" becomes true of loops as well as transitions. `transition-[fill,opacity]` in
`FavouriteToggle` is a property list, not a value; it becomes an explicit `@utility`.

**Border, ring and ring-offset widths (DS-4).** Admit a small `border` family:
`hairline`, `ring`, `ring-offset`. **Not** a ratification of Tailwind's built-in numeric scale, and
this is the one place the plan overrules the register's own suggestion. FR-062 requires a mechanical
check that a value off the scale fails; Tailwind's numeric width scale is unbounded (`border-7`
compiles), so ratifying it hands the checker nothing to check. A three-value family is a scale a
linter can enforce.

**`max-h-[80vh]` in `Menu`.** Not a token gap. A viewport-relative ceiling on a floating surface is
a containment rule, not a design decision with a reusable value, so it becomes an `@utility`
`overlay-max-h` owned by the elevation contract, and the register records that reading.

## D6 — Re-deriving the palette and the typography

**Decision.** The re-derivation is a `product-designer` deliverable that produces **values plus a
per-token rationale**, executed against the art direction the spec fixes as the brief — warm
parchment, stone, muted gold, restrained. Every token in the shipped `color.json` and `font.json`
ends the phase with one of two records: newly derived, with the reasoning; or retained, with the
reason for retaining. Silence is not a third option (FR-001a, SC-001a).

**What the current values already tell us, and what the re-derivation must fix.** The register's own
history is the brief's best evidence. Three separate contrast defects (DS-1, DS-2, T038a, T034c)
were each fixed by darkening one colour within its own hue until it cleared a floor — a palette
derived per-token under pressure rather than as a system. The result is recorded in the register in
one sentence: *"the dark theme is comfortable and the light theme is tight."* Light `warning` on
`surface-raised` clears its floor by two hundredths. Light `border` against `surface` measures 1.6
and is usable only as decoration. The re-derivation's job is to make the light theme's margins
resemble the dark theme's, which is a lightness-ramp decision made once across the whole ramp — not
eight more per-token darkenings.

**Method.** Derive each theme as a ramp with stated lightness steps, then measure. The eight
`player-*` pairs are **excluded**: they are canonical game colours, theme-invariant by
`game-asset-tokens.md`'s decision, and re-deriving them would change what a player's colour means.
They are recorded as retained, with that reason.

**What the re-derivation must add before it is complete.** The register names one pair a component
draws and the table does not carry — `text-secondary` on dark `background`, drawn by
`ProfileSummary`. Adding it is part of this phase, not a follow-up, because FR-052 makes an
unmeasured drawn pair a defect. The pairing convention (assert against the background the component
actually paints, found by reading the component) is the existing rule and is kept verbatim; the new
roles from D8 and D10 enter the table the same way.

**Alternatives considered.** *Keep the values and only close the gaps*: rejected by the
clarification session — a foundation nobody decided is the same defect as a token nobody named.
*Change the character*: out of scope by the spec, and Risk 10 makes the boundary explicit.

## D6a — The typefaces are loaded, or the stacks are re-derived against what renders

**Decision.** Phase 2 resolves this explicitly and may not leave it implied. Two outcomes are
admissible and the `product-designer` chooses between them with the palette:

- **Load them.** Self-host `Inter`, `Fraunces` and `JetBrains Mono` under
  `packages/design-system/tokens/fonts/`, each with the five-field licence record a pack carries,
  and a preload so the first paint is not a swap. `scripts/checks/asset_packs.py` is hard-scoped to
  `packages/game-assets` and `pr.yml`'s `asset-packs` filter lists only that directory, so the check
  and the filter are extended to the font directory in the same change — otherwise the gate
  constitution X requires would neither see nor run on a font (T523). All three carry open
  licences (SIL OFL), so nothing here depends on Microsoft's Game Content Usage Rules.
- **Re-derive the stacks against what actually renders.** Name `Georgia` and `ui-monospace` as the
  chosen families, deliberately, and delete the three names nothing serves.

**What is not admissible** is shipping a third pass of the same defect: a family named in the token
source that no reader ever sees.

**Rationale.** FR-001a requires every typographic role's family to be *chosen*, and a family that
was named but never loaded is the clearest case of a value nobody decided — the spec's own standard
for what this feature exists to fix. It also decides what phase 2 is re-deriving *against*: a type
scale tuned for Inter is the wrong scale for `system-ui`, and Fraunces and Georgia have different
optical sizes at the same nominal step, so the display scale changes with the answer.

**Consequence for the baselines, which is why this is a phase 2 decision and not a later one.**
Loading the fonts repaints every glyph in the product. That is the same "every pixel" event as the
palette, and putting the two in one phase means one regeneration instead of two. Deferring it means
a third global repaint after the retrofit, which D1 exists to prevent.

**Constitution X, checked.** `font.json`'s own comment says no font file is copied into the
repository and that self-hosting "is a separate decision with its licence documented". This is that
decision. The licence gate that already exists for asset packs is the mechanism, so nothing new is
invented to hold it.

## D7 — Typography: one meaning per role

**Decision.** Add a `role` group to `font.json` naming roles by function, and emit one `@utility`
per role. The three meanings currently sharing `font-mono` split into three:

| Role         | Function                                        | Composition                                                        |
| ------------ | ------------------------------------------------ | ------------------------------------------------------------------ |
| `display`    | Page and section headings                       | `font.family.display`                                              |
| `body`       | Prose and control labels                        | `font.family.sans`                                                 |
| `supporting` | Secondary and explanatory text                  | `font.family.sans`, one size step down                             |
| `numeric`    | A measured number                               | `font.family.mono` **plus `font-variant-numeric: tabular-nums`**   |
| `machine`    | A filename, an error class, a raw string        | `font.family.mono`, no numeric variant                             |
| `identifier` | A value the product could not resolve to a name | `font.family.mono`, `text-secondary` by contract                   |

**Rationale.** `tabular-nums` is what makes digit alignment a decision rather than a coincidence:
today it rides on `font.family.mono` happening to be monospaced, so swapping to a proportional
family would silently break every rating column (DS-8's own words). Declaring the variant means
alignment survives a family change, which is SC-009 exactly. Splitting `machine` and `identifier`
from `numeric` is what makes that possible — with one role, adding `tabular-nums` would also apply
it to filenames and error classes, where it is meaningless.

`identifier` carrying `text-secondary` by contract is a deliberate widening: it is how FR-036's
"an unobserved value is visibly distinct from a measured one" survives contact with a developer who
reaches for the role without reading its spec.

## D8 — Container, panel and reading-measure widths (DS-6)

**Decision.** A `size` family — `page`, `panel`, `measure` — mapped onto Tailwind's `--container-*`
theme namespace (verified present in v4.3.3), so `max-w-page`, `max-w-panel` and `max-w-measure`
are ordinary utilities. `Page` owns `max-w-page`; `measure` replaces the current `max-w-prose`.

**Rationale.** FR-021 gives the page primitive the content width, which requires a name for it, and
DS-6's interim ("Tailwind's `max-w-*` scale") is precisely what produced "one route constrains its
width; eight do not" — an unnamed decision is one every route re-makes. `max-w-prose` is Tailwind's
own opinion about reading measure, not ours; naming it makes it reviewable.

## D9 — Opacity: the dated refusal, and the one value that survives it (DS-3, FR-006a)

**Decision.** No opacity family, refused 2026-09-05. The register entry closes with the refusal and
names the colour route as the replacement. The three attenuated appearances resolve as: disabled →
`text-disabled` on `surface-sunken` with `border` (unchanged, already the interim); de-emphasised →
`text-secondary`; dialog scrim → the existing `overlay` role.

**The `overlay` role keeps its alpha, and that is not a contradiction.** `overlay` is
`rgb(43 32 19 / 55%)` — a translucent value inside a named colour role. FR-006a's reason for
refusing an opacity family is that a transparent value's contrast pair depends on whatever sits
behind it and is only measurable after rendering. A scrim carries no foreground: nothing is read
against it, so it owes no pair. What it owes is that the dialog **above** it reads, and that pair is
`text-primary` on `surface`, already measured. The refusal therefore bites on attenuating a
foreground, which is the case it was written for. This reading is recorded in the register beside
the refusal so the next reader does not have to re-derive it or, worse, "fix" `overlay`.

## D10 — A link role (DS-9)

**Decision.** Add `link`, `link-hover` and `link-visited` semantic roles, each declaring the
surfaces it may be painted on (FR-005), measured against `surface`, `surface-raised`,
`surface-sunken` and `background` in both themes. The permanent underline stays: FR-006 forbids
colour-alone, and rule 4 in the specs README already governs it.

**Rationale.** The interim is a restriction with a real cost — "no component paints a link on a
raised surface" — which `privacy-notice.md` hit first and every future prose surface will hit again.
Measuring `accent` on the other three backgrounds would close the contrast half of DS-9 without
closing the semantic half: `accent` means "the product's emphasis colour", and a link is not that.
A role that means "this text navigates" is what FR-005 asks for.

## D11 — Theme delivery, and the flash (FR-014, FR-015, FR-016)

**Decision.** Four parts.

1. **A blocking inline script in `index.html`**, before the stylesheet, reading `localStorage` then
   `matchMedia('(prefers-color-scheme: dark)')` and setting `documentElement.dataset.theme`.
2. **A `ThemeProvider` and `useTheme` in the design system**, owning the stored override and the
   `matchMedia` subscription so a system change is honoured live for a reader who has not overridden.
3. **A control in `SiteHeader`**, three-state: system, light, dark.
4. **Light as the defined default** when storage is unreadable and the system expresses nothing.

**Rationale.** FR-015's no-flash requirement is a first-paint problem and nothing that runs after
React mounts can satisfy it — hence the inline script, which is the one place in this codebase where
a few lines outside the component tree are the correct answer. It is also the one place theme
selection can fail closed: `localStorage` throws in a browser configured to block site data, so both
reads are wrapped and fall through to the system preference and then to light. Portability holds
(constitution XII): the script is static markup, identical on Vercel and on a VPS, with no
server-side rendering assumed.

**The one component that knows the theme.** FR-017 forbids a component branching on the active
theme; the toggle necessarily reads it. The distinction is that the toggle **sets** the theme and
styles nothing by it — it draws the same tokens in both. This is recorded as a standing rule so a
reviewer does not read the toggle as a violation, and so nothing else acquires the same exemption.

**Alternatives considered.** *`prefers-color-scheme` in CSS only*: rejected — it satisfies FR-014's
first clause and makes FR-014's override impossible. *A cookie so a future server render can read
it*: rejected — server rendering is out of scope, and a cookie is personal data this feature has no
basis to add (constitution IX).

## D12 — Automated accessibility checking (FR-058)

**Decision.** Run `axe-core` inside the existing Playwright story loop, once per story per theme,
gated by a dated allowlist. Not the Storybook test runner.

**Rationale.** The suite already navigates to every story's iframe, in both themes, and waits for
the render to settle — that wait is the hard part and it is solved. Adding an axe scan at the point
where the screenshot is taken reuses the scoping, the theme mechanism and the settle logic for the
cost of one dependency. The Storybook test runner would be a second harness with its own scoping
rules, and FR-061's "scoped by story, never by axis" would then have two places to be true.

**Risk 8, sized rather than deferred.** The finding volume on 32 existing components is unknown until
it runs, and it lands in the same phase as the machinery. `scripts/visual/a11y-allowlist.json`
carries one entry per accepted finding: component, rule, date, and the fix owed. An entry is a debt
with a name, not a suppression — the file is empty by the end of phase 5, and a check fails if an
entry outlives the feature. If the volume is large enough to stall phase 1, the allowlist absorbs it
and phase 5 pays it down; that is a sequencing valve, chosen now, not a discovery later.

## D13 — Tiers, and where a component lives (FR-028, FR-029)

**Decision.** Three directories under `packages/design-system/src` — `primitives`, `composites`,
`screens` — replacing the flat `components` directory, with a dependency check that fails when a
primitive imports a composite or a screen, or when anything imports from `apps/`.

**Rationale.** The judgement is already made: Storybook story ids carry `primitives-`, `composite-`,
`screens-` and `chrome-` prefixes assigned component by component. It is recorded in the one place
nothing can enforce, which is why FR-028 asks for the tier to determine where a component lives. The
move is mechanical, touches every import, and is lintable afterwards — the check is what makes
FR-029 a gate rather than a convention.

`chrome` collapses into `composites`: `SiteHeader` and `Footer` are domain composites that happen to
be mounted once. A fourth tier for "mounted by the root layout" would be a location, not a
dependency rule, and FR-028 asks for tiers that determine dependencies.

**Cost, stated.** Every story id changes, so every baseline filename changes. This is why the move
belongs in phase 4 alongside the structural tier and not in phase 1: one rename of 279 baseline
files, not two.

## D14 — The structural tier, and the single main landmark

**Decision.** Nine primitives, from FR-020, all in `src/primitives`: `Page`, `Section`, `Panel`,
`Text`, `Link`, `Table`, `Field`, `EmptyState`, `ErrorState`. `Page` renders
`<main id="main-content" tabIndex={-1}>` and owns `max-w-page` and the page padding.

**The landmark, concretely.** `__root.tsx` currently renders `<main id="main-content">`, and ten
descendants render a second one. After the retrofit `__root.tsx` renders a plain `div`, and the skip
link's target moves onto `Page` with it. `SignInScreen` and `ThirdPartyObjectionForm` stop rendering
`main` and become `Page` content like every route. That is the whole of SC-003, and it is verifiable
by a check that counts `<main>` in every rendered route — cheaper and more reliable than reading a
screenshot.

**Spacing, which is the drift the primitives exist to end.** FR-008 asks the system to say which
step expresses which relationship. Today section spacing is `mt-6` in three places, `mt-8` in three
others and `gap-12` in one. The rule ships as three named steps — within a component, between
components, between sections — assigned to scale steps by the `product-designer`, owned by
`Section` and `Page`, and unavailable to the application because FR-021 removes the application's
ability to write spacing at all.

**Density (FR-012).** Two surface classes, `dense` and `prose`, declared per component in its spec
and carried as a prop on `Panel` and `Table`. Not a reader-facing setting — out of scope by
assumption — and not a per-component choice, which is the drift it prevents.

## D15 — The mechanical check for off-scale values (FR-062)

**Decision.** One Node check, `scripts/checks/token-scale.mjs`, run in the `web` job. It reads the
generated token set and fails on: any arbitrary bracket value in a `className` outside an
allowlisted shape; any hex colour, `px`, `rem` or `ms` literal in a component; and any
`var(--ds-*)` written by hand in JSX rather than reached through a utility.

**Rationale.** The last clause is what makes this check different from a grep for hex codes, and it
is the clause `ProfileSummary` would have failed for a year: `h-[var(--ds-icon-2xl)]` is
token-derived and still a defect, because it means the utility vocabulary has a hole. A check that
only looks for raw values would have passed it, which is how the hole survived. The allowlist covers
the shapes that are not values — `transition-[…]` property lists and `[overflow-wrap:anywhere]` —
and every entry names why.

## D16 — Governance that an agent can apply alone (FR-064, FR-067)

**Decision.** One document, `packages/design-system/specs/GOVERNANCE.md`, carrying four mechanical
procedures and nothing else: the token admission test, the component and variant admission test, the
promotion threshold, and the deprecation procedure. Each is a numbered sequence of steps with a
recorded outcome; none requires a synchronous human decision.

**The promotion threshold is three.** A composition appearing in the application a third time is
promoted, or the reason it is not is recorded beside the third occurrence. Three is the smallest
number that distinguishes a pattern from a coincidence, and it is the number the spec's own User
Story 7 narrates.

**Applied at least once during this feature (production-readiness item 14).** All four have subjects
already: the token admission test decides D5's `border` family and rejects the opacity family; the
component test admits `Page`; the promotion threshold promotes the page wrapper, which occurs ten
times; the deprecation procedure retires whatever FR-032's prop reconciliation renames.

**Rationale.** FR-067 is the binding constraint and it is applied to this feature's own output:
every rule above is a checklist an agent working from a cold context can execute. Anything that
would need a person in the loop was not written.

## D17 — The filing rule amendment (FR-064a)

**Decision.** `CLAUDE.md`'s three-homes table gains one sentence: a living fact whose subject is a
package in this repository is filed with that package; a living fact about the outside world is
filed in `docs/`. The contrast table and the gap register stay in
`packages/design-system/specs/README.md` and neither moves.

**Rationale.** The current test — *does this need updating when the world changes?* — returns "yes"
for the contrast table and would file it in `docs/`, which is wrong: recomputing it is triggered by
editing `color.json`, an event entirely inside this repository. The distinction is subject, not
liveness. Both files stay asserted by a test, which is the property that made them trustworthy in
the first place and the one the amendment must not weaken.

## Constitution VII, read exactly

Constitution VII says CI "tests only the stories the diff affects; full coverage runs nightly." The
matrix expansion in D2 does not touch that: the scope is still the affected stories, and each of
them is now captured across its full axis set. FR-061 and constitution VII agree, and the plan's
Constitution Check records the reading rather than leaving it implied.

## What remains unknown

Two things, both bounded and both scheduled rather than blocking.

1. **The accessibility finding volume** on the 32 existing components. Unknown until phase 1 runs
   it. D12's allowlist is the valve, and the debt is paid in phase 5.
2. **The exact palette values, and the typeface question in D6a.** Both are
   `product-designer` deliverables in phase 2, not planning outputs. What phase 0 fixes is the method (D6), the brief (the art direction), the
   exclusions (the eight player colours) and the acceptance test (every pair a component draws is
   measured and asserted, and every token carries a derived-or-retained record).

No NEEDS CLARIFICATION remains. The spec's five open decisions were settled in its own clarification
session of 2026-09-05.
