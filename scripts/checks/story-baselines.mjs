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
// an orphan baseline, and never expected to have a story backing them.
//
// A baseline's filename is its Storybook story id plus `.png` — `composite-analysistimeline--failed`
// -> `composite-analysistimeline--failed.png` — with no other transformation, at least until T504
// lands theme and width axis suffixes onto that name.
//
// Usage:  node scripts/checks/story-baselines.mjs
// Exit:   0 if every story has exactly one baseline and every baseline names a story (or is
//         exempt), 1 otherwise.
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
const indexPath = path.join(designSystemDir, 'storybook-static', 'index.json')
const screenshotsDir = path.join(designSystemDir, '__screenshots__')

// tests/visual/app-routes.spec.ts's own two baseline names — full-page captures of the built
// application, not of a Storybook story, so this is the one set this check never expects a
// story-index entry for.
const EXEMPT_BASELINES = new Set(['app-signed-out-sign-in', 'app-signed-in-dashboard'])

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

  const baselineNames = readdirSync(screenshotsDir)
    .filter((f) => f.endsWith('.png'))
    .map((f) => f.slice(0, -'.png'.length))

  const baselineSet = new Set(baselineNames)

  const missingBaselines = [...storyIds].filter((id) => !baselineSet.has(id)).sort()
  const orphanBaselines = baselineNames
    .filter((name) => !storyIds.has(name) && !EXEMPT_BASELINES.has(name))
    .sort()

  if (missingBaselines.length > 0 || orphanBaselines.length > 0) {
    if (missingBaselines.length > 0) {
      log(
        `${missingBaselines.length} stor${missingBaselines.length === 1 ? 'y has' : 'ies have'} no baseline:`,
      )
      for (const id of missingBaselines) log(`  - ${id}`)
    }
    if (orphanBaselines.length > 0) {
      log(
        `${orphanBaselines.length} baseline${orphanBaselines.length === 1 ? '' : 's'} ` +
          `name${orphanBaselines.length === 1 ? 's' : ''} no story in the built index:`,
      )
      for (const name of orphanBaselines) log(`  - ${name}.png`)
    }
    log(
      'run `pnpm --filter design-system build-storybook` and `pnpm test:visual` with ' +
        '`--update-snapshots` to capture a missing baseline, or delete an orphan one whose ' +
        'story was removed or renamed.',
    )
    process.exit(1)
  }

  log(
    `${storyIds.size} stor${storyIds.size === 1 ? 'y' : 'ies'} and ${baselineNames.length} ` +
      `baseline${baselineNames.length === 1 ? '' : 's'} (${EXEMPT_BASELINES.size} exempt) agree.`,
  )
}

main()
