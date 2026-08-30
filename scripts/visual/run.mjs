#!/usr/bin/env node
// Diff-scoped visual regression runner for `pnpm test:visual` (T005, constitution VII).
//
// `pnpm test:visual`            -> every story in the built Storybook (nightly full coverage).
// `pnpm test:visual --changed`  -> only stories whose `.stories.tsx` file the diff touched
//                                  (pull-request runs — CI is a court, not a factory).
//
// Two things short-circuit before Playwright, and neither is an error: no Storybook build yet
// (packages/design-system doesn't exist until T003/T016), and --changed finding no touched story.
// Both print a message and exit 0, mirroring how pytest tolerates a missing testpaths entry.
import { existsSync, readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
const storybookStaticDir = path.join(designSystemDir, 'storybook-static')
const indexPath = path.join(storybookStaticDir, 'index.json')

const changedOnly = process.argv.slice(2).includes('--changed')

function log(message) {
  console.log(`test:visual: ${message}`)
}

function runGit(args) {
  const result = spawnSync('git', args, { cwd: rootDir, encoding: 'utf8' })
  if (result.status !== 0) return []
  return result.stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

// Every file that differs from the diff base, plus anything uncommitted or untracked, so a run
// before *and* after `git add` behaves the same way for a developer working locally.
function changedFiles() {
  const base = process.env.VISUAL_BASE_REF ?? 'origin/main'
  const files = new Set()
  for (const f of runGit(['diff', '--name-only', `${base}...HEAD`])) files.add(f)
  for (const f of runGit(['diff', '--name-only', 'HEAD'])) files.add(f)
  for (const f of runGit(['ls-files', '--others', '--exclude-standard'])) files.add(f)
  return [...files]
}

const storyGlob = /\.stories\.[jt]sx?$/

function main() {
  if (!existsSync(indexPath)) {
    log(
      'no Storybook build found at packages/design-system/storybook-static/index.json — nothing ' +
        'to test. Run `pnpm --filter design-system build-storybook` first if stories already exist.',
    )
    process.exit(0)
  }

  const index = JSON.parse(readFileSync(indexPath, 'utf8'))
  const entries = Object.values(index.entries ?? index.stories ?? {})
  let stories = entries.filter((entry) => entry.type === undefined || entry.type === 'story')

  if (stories.length === 0) {
    log('Storybook build has no stories — nothing to test.')
    process.exit(0)
  }

  if (changedOnly) {
    const touchedStoryFiles = changedFiles()
      .filter((f) => f.startsWith('packages/design-system/') && storyGlob.test(f))
      .map((f) => path.relative(designSystemDir, path.join(rootDir, f)))

    if (touchedStoryFiles.length === 0) {
      log('--changed: no story file differs from the diff base — nothing to test.')
      process.exit(0)
    }

    const touched = new Set(touchedStoryFiles.map((f) => f.split(path.sep).join('/')))
    stories = stories.filter((entry) => {
      const importPath = (entry.importPath ?? '').replace(/^\.\//, '')
      return touched.has(importPath)
    })

    if (stories.length === 0) {
      log('--changed: changed story files are not part of the built Storybook — nothing to test.')
      process.exit(0)
    }
  }

  log(
    `running ${stories.length} stor${stories.length === 1 ? 'y' : 'ies'}` +
      (changedOnly ? ' (diff-scoped)' : ' (full run)') +
      '.',
  )

  // A story tagged `visual-full-page` names a subject that escapes the `#storybook-root` box —
  // a `position: fixed` dialog (fixed positioning is relative to the viewport, not any ancestor
  // box) or a popover that overflows its trigger's layout box (an absolutely positioned
  // descendant does not enlarge that box, so a screenshot clipped to it never reaches the
  // popover at all). Screenshotting the whole page instead of just the root element is the only
  // way those baselines see the thing they are named for.
  const result = spawnSync(
    'pnpm',
    ['exec', 'playwright', 'test', '--config=playwright.config.ts'],
    {
      cwd: rootDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        VISUAL_STORIES: JSON.stringify(
          stories.map((entry) => ({
            id: entry.id,
            fullPage: (entry.tags ?? []).includes('visual-full-page'),
            // A story tagged `visual-mobile` names a subject whose bug is invisible at the
            // suite's default (desktop) viewport — PrivacyNotice's storage tables (T096 defect 1)
            // shipped because no story captured the width their overflow only shows at. Captured
            // at 375px, alongside (never instead of) the desktop baseline for the same component.
            mobile: (entry.tags ?? []).includes('visual-mobile'),
          })),
        ),
      },
    },
  )
  process.exit(result.status ?? 1)
}

main()
