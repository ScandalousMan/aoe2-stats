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
// The two `tests/visual/app-routes.spec.ts` full-page captures — `app-signed-out-sign-in` and
// `app-signed-in-dashboard` — are not Storybook stories at all (they screenshot the built
// application, T108's own comment explains why) and are declared exempt below: never flagged as
// an orphan baseline, and never expected to have a story backing them. They carry no theme/width
// suffix (below) and are matched by their literal, unrenamed filename.
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

// tests/visual/app-routes.spec.ts's own two baseline names — full-page captures of the built
// application, not of a Storybook story, so this is the one set this check never expects a
// story-index entry for, and never expects a theme/width suffix on.
const EXEMPT_BASELINES = new Set(['app-signed-out-sign-in', 'app-signed-in-dashboard'])

// The axes `scripts/visual/run.mjs` expands every selected story across (T504). Duplicated here,
// not imported, because this check has to be able to name a missing unit for a story that
// run.mjs's own VISUAL_STORIES payload may never have produced yet.
const THEMES = ['light', 'dark']
const WIDTHS = [375, 768, 1280]

// Recovers the story id from a baseline's filename by stripping the trailing `-<theme>-<width>`,
// e.g. `composite-button--primary-dark-768.png` -> `composite-button--primary`. A filename that
// does not match this shape at all (no recognised theme/width suffix) cannot name any story this
// check knows about and is therefore an orphan by construction, same as a name that parses but
// names no story in the index.
const BASELINE_NAME_RE = /^(.+)-(?:light|dark)-(?:375|768|1280)\.png$/

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

  const baselineFiles = readdirSync(screenshotsDir).filter((f) => f.endsWith('.png'))
  const baselineSet = new Set(baselineFiles)

  const incompleteStories = [...storyIds]
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

  const orphanBaselines = baselineFiles
    .filter((f) => !EXEMPT_BASELINES.has(f.slice(0, -'.png'.length)))
    .filter((f) => {
      const match = f.match(BASELINE_NAME_RE)
      return !match || !storyIds.has(match[1])
    })
    .sort()

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
      `(${EXEMPT_BASELINES.size} exempt) agree with the built index.`,
  )
}

main()
