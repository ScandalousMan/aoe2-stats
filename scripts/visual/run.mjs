#!/usr/bin/env node
// Diff-scoped visual regression runner for `pnpm test:visual` (T005, constitution VII).
//
// `pnpm test:visual`            -> every story in the built Storybook, in the full matrix below
//                                  (nightly full coverage).
// `pnpm test:visual --changed`  -> only the stories the diff *affects* (see the `changedOnly`
//                                  branch below), each still run through the full matrix
//                                  (pull-request runs — CI is a court, not a factory).
//
// T504 (FR-060, FR-061, SC-006): the suite is scoped by *story*, never by axis. Every selected
// story is expanded here into up to 6 capture units — {light, dark} x {375, 768, 1280} — and there
// is deliberately no flag, env var or CLI switch that narrows that expansion. A debugging need is
// not an exception: FR-061 forbids a narrower pull-request run outright, so no escape hatch is
// added "just for local iteration" either.
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

// The two axes every selected story is captured across. Order matters only for log readability —
// `stories.spec.ts` treats every unit independently.
const THEMES = ['light', 'dark']
const WIDTHS = [375, 768, 1280]

// Paths whose diff repaints or can repaint *every* story, so touching any of them selects the
// full story set rather than only the stories under the touched directory. Relative to the repo
// root, matching how `changedFiles()` reports paths.
const GLOBAL_REACH_PREFIXES = [
  'packages/design-system/tokens/',
  'packages/design-system/.storybook/',
  'packages/design-system/src/lib/',
  'packages/design-system/src/index.ts',
  'tests/visual/',
  'scripts/visual/',
]

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
    const diff = changedFiles()

    // A change under any of these paths repaints (or can repaint) every story — a token, the
    // preview decorator, a shared `lib` helper, the public surface, or the harness itself — so it
    // selects the full story set rather than narrowing to a directory. Without this, a change to
    // `packages/design-system/tokens/color.json` would touch no `.stories.tsx` file and select
    // zero stories, which is exactly the gap FR-060/FR-061 exist to close: an "affected" story is
    // one whose *rendered output* the diff can change, not only one whose own file was edited.
    const globallyAffected = diff.some((f) =>
      GLOBAL_REACH_PREFIXES.some((prefix) => f.startsWith(prefix)),
    )

    if (!globallyAffected) {
      // Directory of each story's own file, relative to the design-system package (matching
      // `entry.importPath`, e.g. `src/components/Button`), so a change to the component's
      // implementation file — not only to its `.stories.tsx` — selects the story too.
      const touchedInPackage = diff
        .filter((f) => f.startsWith('packages/design-system/'))
        .map((f) => path.relative(designSystemDir, path.join(rootDir, f)).split(path.sep).join('/'))
      const touchedDesignSystemDirs = new Set(touchedInPackage.map((f) => path.posix.dirname(f)))
      const touchedStoryFiles = new Set(touchedInPackage.filter((f) => storyGlob.test(f)))

      stories = stories.filter((entry) => {
        const importPath = (entry.importPath ?? '').replace(/^\.\//, '')
        if (touchedStoryFiles.has(importPath)) return true
        return touchedDesignSystemDirs.has(path.posix.dirname(importPath))
      })

      if (stories.length === 0) {
        log('--changed: nothing in the diff affects a story — nothing to test.')
        process.exit(0)
      }
    }
  }

  // Every selected story is expanded into one capture unit per {theme, width} pair — the full
  // matrix, always, with no flag anywhere that narrows it (FR-061). `stories.spec.ts` stays dumb:
  // it renders exactly the units listed here and never re-derives which axes apply to which story.
  const units = stories.flatMap((entry) =>
    THEMES.flatMap((theme) =>
      WIDTHS.map((width) => ({
        id: entry.id,
        theme,
        width,
        // A story tagged `visual-full-page` names a subject that escapes the `#storybook-root`
        // box — a `position: fixed` dialog (fixed positioning is relative to the viewport, not
        // any ancestor box) or a popover that overflows its trigger's layout box (an absolutely
        // positioned descendant does not enlarge that box, so a screenshot clipped to it never
        // reaches the popover at all). Screenshotting the whole page instead of just the root
        // element is the only way those baselines see the thing they are named for.
        fullPage: (entry.tags ?? []).includes('visual-full-page'),
      })),
    ),
  )

  log(
    `running ${stories.length} stor${stories.length === 1 ? 'y' : 'ies'}` +
      (changedOnly ? ' (diff-scoped)' : ' (full run)') +
      ` across ${THEMES.length} themes x ${WIDTHS.length} widths = ${units.length} capture units.`,
  )

  const result = spawnSync(
    'pnpm',
    ['exec', 'playwright', 'test', '--config=playwright.config.ts'],
    {
      cwd: rootDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        VISUAL_STORIES: JSON.stringify(units),
      },
    },
  )
  process.exit(result.status ?? 1)
}

main()
