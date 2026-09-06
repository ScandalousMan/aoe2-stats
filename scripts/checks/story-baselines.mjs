#!/usr/bin/env node
// T503: set equality between the built Storybook index and the baseline images the visual suite
// compares against, so a story merged with no baseline — or a baseline naming a story that no
// longer exists — fails on every run, not only the one that happens to select it.
//
// `pnpm test:visual --changed` (scripts/visual/run.mjs) diff-scopes to the stories the pull
// request touched, by design (CI is a court, not a factory — that script's own comment). A story
// added without ever running Playwright's `--update-snapshots` locally still passes that scoped
// run, because "no baseline yet" and "not selected" produce the same outcome: nothing compared.
// The gap surfaces only in nightly's unscoped `pnpm test:visual`, as one Playwright failure among
// many, easy to misread as flake. This check reads the whole Storybook index — every story that
// exists, not the ones a diff happened to touch — so it cannot be outrun by that scoping, and it
// runs as its own step so its failure names the exact story rather than hiding inside a full
// Playwright report.
//
// `tests/visual/app-routes.spec.ts`'s full-page captures — of the built application, not of a
// Storybook story (T108's own comment explains why) — are exempt below: never flagged as an
// orphan baseline, and never expected to have a story backing them. They carry no theme/width
// suffix (below), so `BASELINE_NAME_RE` never matches one, which is exactly why every one of them
// needs an exemption rather than falling out of the story-id parse the way a real story baseline
// does.
//
// T553 grew that file from two full-page captures (T108) to eleven routes each in both themes
// (FR-022, SC-003), so the two hardcoded names this exemption carried through T504 stopped being
// the whole set — the gap this fix closes. Two ways to widen it were rejected before landing on a
// third:
//   - Restating all 22 names by hand here reintroduces exactly the drift T553 just exposed: the
//     next route app-routes.spec.ts adds would silently need a second, matching edit in this
//     unrelated file, with nothing to fail if that edit were missed.
//   - A blanket `app-` prefix match is worse than the two-name list it would replace: it would
//     also exempt a baseline whose route had been deleted or renamed — precisely the orphan this
//     check exists to catch — because "starts with `app-`" is true of every name that file has
//     ever produced *and* every one it no longer does.
// So `loadAppRouteBaselineNames` below reads `tests/visual/app-routes.spec.ts` itself and derives
// the exempt set from the two shapes that file actually emits a screenshot name from: the four
// literal `toHaveScreenshot('app-...png', ...)` calls the original two routes still use, and every
// `routeCases` entry's `screenshotBase`, each expanded into its own light and `-dark` file the way
// that file's own test loop expands it (T553's `screenshotName` ternary, mirrored exactly). A
// baseline this derivation does not name is still an orphan, `app-` prefix or not — proof of that
// lives in story-baselines.test.mjs.
//
// T504: a baseline's filename is now its Storybook story id, a theme and a width —
// `composite-analysistimeline--failed` -> `composite-analysistimeline--failed-light-1280.png` —
// because every story is captured across the full {light, dark} x {375, 768, 1280} matrix
// (FR-060, FR-061, SC-006). "Complete" for a story is therefore redefined here to mean **all six**
// of those files exist, not merely one: a check that stayed satisfied by one baseline of any axis
// would be blind to exactly the axes this feature adds, would keep silently passing forever with
// dark and tablet never captured, and would repeat the defect the spec's own risk register names
// — "a gate that is believed and does not hold is worse than an absent one, because it displaces
// the manual check that would otherwise happen." SC-006 says a published story's appearance is
// verified "in both themes and at every declared review width"; a check that only proves one of
// six units exist does not prove that.
//
// The consequence is deliberate and is spelled out here rather than left implicit: immediately
// after this commit (T504), every story still has exactly one of its six baselines — the one
// `git mv` renamed from the pre-T504 file — because capturing the other five is T505's job, one
// task later in this same phase, dispatched separately on CI (research D3: baselines are only
// ever captured there, never locally). This check is therefore *expected* to fail red between
// T504 and T505, listing five missing units per story, and that is not a regression to silence:
// phase 1's own plan (research D1) treats this as one continuous unit of work that is not done,
// and the phase-1 pull request is not mergeable, until T505 has run and every story's baseline
// set is complete. A check that instead reported success at "one baseline per story" throughout
// would hide that T505 was still owed.
//
// Usage:  node scripts/checks/story-baselines.mjs
// Exit:   0 if every story has all six {theme, width} baselines and every baseline names a known
//         story (or is exempt), 1 otherwise.
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
const indexPath = path.join(designSystemDir, 'storybook-static', 'index.json')
const screenshotsDir = path.join(designSystemDir, '__screenshots__')
const appRoutesSpecPath = path.join(rootDir, 'tests', 'visual', 'app-routes.spec.ts')

// Recovers every baseline name `tests/visual/app-routes.spec.ts` can produce, from the two literal
// shapes it emits a screenshot name from — see this file's header for why this is derived rather
// than hardcoded or prefix-matched. Exported (and covered directly, not only through `main`) so
// story-baselines.test.mjs can prove it stays exact as that spec file grows.
export function loadAppRouteBaselineNames(specSource) {
  const names = new Set()
  // The two original routes' own `toHaveScreenshot('app-....png', ...)` calls — a literal string
  // argument, never the `screenshotName` variable the loop below builds, so this pattern alone
  // never double-counts a `routeCases` entry.
  for (const match of specSource.matchAll(/toHaveScreenshot\(\s*'([a-z0-9-]+)\.png'/g)) {
    names.add(match[1])
  }
  // Every `routeCases` entry's `screenshotBase`, expanded into its own light and `-dark` file —
  // T553's own `theme === 'light' ? \`${screenshotBase}.png\` : \`${screenshotBase}-dark.png\``
  // ternary, mirrored here rather than re-derived some other way.
  for (const match of specSource.matchAll(/screenshotBase:\s*'([a-z0-9-]+)'/g)) {
    names.add(match[1])
    names.add(`${match[1]}-dark`)
  }
  return names
}

// The axes `scripts/visual/run.mjs` expands every selected story across (T504). Duplicated here,
// not imported, because this check has to be able to name a missing unit for a story that
// run.mjs's own selected-units payload may never have produced yet.
const THEMES = ['light', 'dark']
const WIDTHS = [375, 768, 1280]

// Recovers the story id from a baseline's filename by stripping the trailing `-<theme>-<width>`,
// e.g. `composite-button--primary-dark-768.png` -> `composite-button--primary`. A filename that
// does not match this shape at all (no recognised theme/width suffix) cannot name any story this
// check knows about and is therefore an orphan by construction, same as a name that parses but
// names no story in the index.
export const BASELINE_NAME_RE = /^(.+)-(?:light|dark)-(?:375|768|1280)\.png$/

// Every story's six {theme, width} units it does not already have.
export function findIncompleteStories(storyIds, baselineSet) {
  return [...storyIds]
    .sort()
    .map((id) => ({
      id,
      missingUnits: THEMES.flatMap((theme) =>
        WIDTHS.filter((width) => !baselineSet.has(`${id}-${theme}-${width}.png`)).map(
          (width) => `${id}-${theme}-${width}.png`,
        ),
      ),
    }))
    .filter(({ missingUnits }) => missingUnits.length > 0)
}

// Every baseline file that names neither a known story (via `BASELINE_NAME_RE`) nor a name
// `exemptBaselines` carries. Exported so story-baselines.test.mjs can prove this still reports a
// baseline that merely starts with `app-` without being one `loadAppRouteBaselineNames` actually
// produced — the case a blanket prefix match would have missed (see this file's header).
export function findOrphanBaselines(baselineFiles, storyIds, exemptBaselines) {
  return baselineFiles
    .filter((f) => !exemptBaselines.has(f.slice(0, -'.png'.length)))
    .filter((f) => {
      const match = f.match(BASELINE_NAME_RE)
      return !match || !storyIds.has(match[1])
    })
    .sort()
}

function log(message) {
  console.log(`story-baselines: ${message}`)
}

function main() {
  if (!existsSync(indexPath)) {
    log(
      `no Storybook build found at ${path.relative(rootDir, indexPath)} — run ` +
        '`pnpm --filter design-system build-storybook` first.',
    )
    process.exit(1)
  }

  const index = JSON.parse(readFileSync(indexPath, 'utf8'))
  const entries = Object.values(index.entries ?? index.stories ?? {})
  const stories = entries.filter((entry) => entry.type === undefined || entry.type === 'story')
  const storyIds = new Set(stories.map((entry) => entry.id))

  if (!existsSync(screenshotsDir)) {
    log(`no baseline directory found at ${path.relative(rootDir, screenshotsDir)}.`)
    process.exit(1)
  }

  const exemptBaselines = loadAppRouteBaselineNames(readFileSync(appRoutesSpecPath, 'utf8'))

  const baselineFiles = readdirSync(screenshotsDir).filter((f) => f.endsWith('.png'))
  const baselineSet = new Set(baselineFiles)

  const incompleteStories = findIncompleteStories(storyIds, baselineSet)
  const orphanBaselines = findOrphanBaselines(baselineFiles, storyIds, exemptBaselines)

  if (incompleteStories.length > 0 || orphanBaselines.length > 0) {
    if (incompleteStories.length > 0) {
      const totalMissingUnits = incompleteStories.reduce((n, s) => n + s.missingUnits.length, 0)
      log(
        `${incompleteStories.length} stor${incompleteStories.length === 1 ? 'y is' : 'ies are'} ` +
          `missing ${totalMissingUnits} baseline unit${totalMissingUnits === 1 ? '' : 's'} ` +
          `(of ${THEMES.length * WIDTHS.length} per story):`,
      )
      for (const { id, missingUnits } of incompleteStories) {
        log(`  - ${id}: missing ${missingUnits.join(', ')}`)
      }
    }
    if (orphanBaselines.length > 0) {
      log(
        `${orphanBaselines.length} baseline${orphanBaselines.length === 1 ? '' : 's'} ` +
          `name${orphanBaselines.length === 1 ? 's' : ''} no story in the built index:`,
      )
      for (const name of orphanBaselines) log(`  - ${name}`)
    }
    log(
      'dispatch `.github/workflows/baselines.yml` to capture a missing unit (research D3 — ' +
        'baselines are only ever captured on CI, never locally), or delete an orphan whose ' +
        'story was removed, renamed, or whose filename no longer matches the ' +
        '`<story-id>-<light|dark>-<375|768|1280>.png` shape.',
    )
    process.exit(1)
  }

  log(
    `${storyIds.size} stor${storyIds.size === 1 ? 'y' : 'ies'} each have all ` +
      `${THEMES.length * WIDTHS.length} baselines; ${baselineFiles.length} baseline files total ` +
      `(${exemptBaselines.size} app-route captures exempt) agree with the built index.`,
  )
}

// Only run when invoked directly (`node scripts/checks/story-baselines.mjs`) —
// story-baselines.test.mjs imports the functions above without triggering the scan or the process
// exit code, the same guard token-scale.mjs uses.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
