// Which stories a pull request's diff affects (T504, T005) — extracted from `scripts/visual/run.mjs`
// by T693 so the runtime pass (`scripts/visual/state-coverage-runtime.mjs`) selects stories the
// way `pnpm test:visual --changed` does, from this one definition rather than a second copy of the
// rule. Behaviour is unchanged: `run.mjs` imports everything below and no longer defines it.
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')

// Paths whose diff repaints or can repaint *every* story, so touching any of them selects the
// full story set rather than only the stories under the touched directory. Relative to the repo
// root, matching how `changedFiles()` reports paths.
export const GLOBAL_REACH_PREFIXES = [
  'packages/design-system/tokens/',
  'packages/design-system/.storybook/',
  'packages/design-system/src/lib/',
  'packages/design-system/src/index.ts',
  'tests/visual/',
  'scripts/visual/',
]

export const storyGlob = /\.stories\.[jt]sx?$/

// How a refusal talks: the caller's own log prefix, and the command it names as the way out. The
// defaults are `scripts/visual/run.mjs`'s own; the runtime pass (`state-coverage-runtime.mjs`) passes
// its own, so its refusal never tells a reader to run a different tool.
const RUN_MJS_VOICE = {
  prefix: 'test:visual',
  unscopedCommand: 'the full, unscoped `pnpm test:visual`',
}

function runGit(args, cwd = rootDir) {
  const result = spawnSync('git', args, { cwd, encoding: 'utf8' })
  if (result.status !== 0) return []
  return result.stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

// A git invocation whose failure is fatal rather than swallowed into `[]`. Reserved for the diff
// whose base is a name that might not resolve in this checkout at all (`${base}...HEAD` below, and
// the merge base `fileAtBase` reads from) — as opposed to a diff against `HEAD` or a listing of
// untracked files, neither of which names anything that can fail to exist. Conflating "the command
// failed" with "the command found nothing" is the defect this exists to end: a shallow CI checkout
// with no `origin/main` locally available used to make every pull-request run silently select zero
// stories and exit 0, looking identical to a docs-only change that genuinely touches none.
function gitOrFail(args, baseDescription, { prefix, unscopedCommand, cwd }) {
  const result = spawnSync('git', args, { cwd, encoding: 'utf8' })
  if (result.status !== 0) {
    const stderr = (result.stderr ?? '').trim()
    console.log(
      `${prefix}: --changed could not resolve its diff base, ${baseDescription} (\`git ${args.join(' ')}\`)` +
        (stderr ? ` — ${stderr}` : '') +
        '. This is not "nothing changed" — it is "the changed set is unknown" — so refusing to ' +
        'report zero affected stories. Set VISUAL_BASE_REF to a ref this checkout can resolve ' +
        '(a commit SHA already fetched, or a branch after `git fetch` has brought it in), or run ' +
        `${unscopedCommand} instead.`,
    )
    process.exit(1)
  }
  return result.stdout
}

function lines(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function diffBase() {
  return process.env.VISUAL_BASE_REF ?? 'origin/main'
}

// Every file that differs from the diff base, plus anything uncommitted or untracked, so a run
// before *and* after `git add` behaves the same way for a developer working locally.
//
// `--no-renames` on every diff: with rename detection (git's default for `diff` is configurable and a
// user's `diff.renames` is honoured) `--name-only` prints only a rename's NEW path, so renaming
// `Tooltip/index.tsx` away would select nothing that recorded the old one. Without it a rename is a
// deletion plus an addition and both paths are listed. For `scripts/visual/run.mjs`'s capture
// selection that can only GROW the set: it now also sees the old path's directory, which it never saw
// before, and every path it saw before is still listed.
export function changedFiles(options = {}) {
  const voice = { ...RUN_MJS_VOICE, cwd: rootDir, ...options }
  const base = diffBase()
  const files = new Set()
  for (const f of lines(
    gitOrFail(['diff', '--name-only', '--no-renames', `${base}...HEAD`], `"${base}"`, voice),
  )) {
    files.add(f)
  }
  for (const f of runGit(['diff', '--name-only', '--no-renames', 'HEAD'], voice.cwd)) files.add(f)
  for (const f of runGit(['ls-files', '--others', '--exclude-standard'], voice.cwd)) files.add(f)
  return [...files]
}

// A repository-rooted file's text as it was at the diff base — the commit `${base}...HEAD` diffs
// from, i.e. the merge base, so a base branch that moved on since this one forked does not read as a
// change this branch made. `null` when the file does not exist there; an unresolvable base is the
// same refusal `changedFiles` makes, never "no such file".
export function fileAtBase(repoPath, options = {}) {
  const voice = { ...RUN_MJS_VOICE, cwd: rootDir, ...options }
  const base = diffBase()
  const [mergeBase] = lines(gitOrFail(['merge-base', base, 'HEAD'], `"${base}"`, voice))
  const listed = lines(gitOrFail(['ls-tree', mergeBase, '--', repoPath], `"${base}"`, voice))
  if (listed.length === 0) return null
  return gitOrFail(['show', `${mergeBase}:${repoPath}`], `"${base}"`, voice)
}

// The stories a diff affects. A change under any `GLOBAL_REACH_PREFIXES` path repaints (or can
// repaint) every story — a token, the preview decorator, a shared `lib` helper, the public
// surface, or the harness itself — so it selects the full story set rather than narrowing to a
// directory. Without this, a change to `packages/design-system/tokens/color.json` would touch no
// `.stories.tsx` file and select zero stories, which is exactly the gap FR-060/FR-061 exist to
// close: an "affected" story is one whose *rendered output* the diff can change, not only one
// whose own file was edited.
//
// Otherwise a story is selected when its own file was touched, or when any file in its directory
// was (`entry.importPath`, e.g. `src/primitives/Button`, so a change to the component's
// implementation file — not only to its `.stories.tsx` — selects the story too).
export function selectChangedStories(stories, diff, dsDir = designSystemDir) {
  const globallyAffected = diff.some((f) =>
    GLOBAL_REACH_PREFIXES.some((prefix) => f.startsWith(prefix)),
  )
  if (globallyAffected) return { stories, globallyAffected }

  const touchedInPackage = diff
    .filter((f) => f.startsWith('packages/design-system/'))
    .map((f) => path.relative(dsDir, path.join(rootDir, f)).split(path.sep).join('/'))
  const touchedDesignSystemDirs = new Set(touchedInPackage.map((f) => path.posix.dirname(f)))
  const touchedStoryFiles = new Set(touchedInPackage.filter((f) => storyGlob.test(f)))

  return {
    globallyAffected,
    stories: stories.filter((entry) => {
      const importPath = (entry.importPath ?? '').replace(/^\.\//, '')
      if (touchedStoryFiles.has(importPath)) return true
      return touchedDesignSystemDirs.has(path.posix.dirname(importPath))
    }),
  }
}
