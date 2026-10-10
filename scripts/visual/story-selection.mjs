// Which stories a pull request's diff affects (T504, T005) — extracted from `scripts/visual/run.mjs`
// by T693 so the runtime pass (`scripts/visual/state-coverage-runtime.mjs`) selects stories the
// way `pnpm test:visual --changed` does, from this one definition rather than a second copy of the
// rule. Behaviour is unchanged: `run.mjs` imports everything below and no longer defines it.
import { spawnSync } from 'node:child_process'
import { readFileSync, statSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { collectModuleSpecifiers, findNonLiteralSpecifiers } from './module-specifiers.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
// `typescript` is a direct devDependency of packages/design-system, not of the workspace root; the same
// resolution `module-specifiers.mjs` uses, here only for `ts.createSourceFile`.
const ts = createRequire(path.join(designSystemDir, 'package.json'))('typescript')

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

const PACKAGE_PREFIX = 'packages/design-system/'

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

// The extensions a specifier without one may name, after the specifier as written; then the same on
// `<specifier>/index`. The order is irrelevant: EVERY candidate that exists is followed (below), so
// the walk never has to know which of `helper.js` and `helper.ts` the bundler loads.
const RESOLVE_EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mts', '.mjs', '.cts', '.cjs', '.json']
// A file the walk parses for further specifiers. A resolved file of any other kind (`.json`, `.css`,
// an image) is a leaf: a diff that touches it selects its importers, but it names no module.
const CODE_FILE = /\.[cm]?[jt]sx?$/
// A TypeScript importer may write the emitted extension (`./x.js`) for the source file (`./x.ts`).
const EMITTED_EXTENSION = {
  '.js': ['.ts', '.tsx'],
  '.jsx': ['.tsx'],
  '.mjs': ['.mts'],
  '.cjs': ['.cts'],
}

const isFile = (file) => {
  try {
    return statSync(file).isFile()
  } catch {
    return false
  }
}

// Every file a relative specifier can name that exists, as absolute paths (possibly none): as written,
// then with each extension, then as a directory's `index`; a specifier ending in `/`, and the bare `.`
// and `..`, name a directory and try the `index` candidates only. Each existing candidate is returned,
// not the first: over-selecting is the safe direction, so which one a bundler would load (`helper.js`
// or `helper.ts`, a file or a directory index of the same name) is a question the walk never needs to
// answer, and its extension order is irrelevant. A bare specifier (a package, an alias), one that
// resolves to nothing, and a candidate outside `dsDir` or inside `node_modules` yield nothing: not
// walked.
function resolveRelativeSpecifier(fromFile, rawSpecifier, dsDir) {
  const specifier = rawSpecifier.replace(/[?#].*$/, '')
  const bareDirectory = specifier === '.' || specifier === '..'
  if (!bareDirectory && !specifier.startsWith('./') && !specifier.startsWith('../')) return []
  const isDirectory = bareDirectory || specifier.endsWith('/')
  const base = path.resolve(path.dirname(fromFile), specifier)
  const indexes = RESOLVE_EXTENSIONS.map((ext) => path.join(base, `index${ext}`))
  let candidates
  if (isDirectory) {
    candidates = indexes
  } else {
    const emitted = EMITTED_EXTENSION[path.extname(base)] ?? []
    const stem = base.slice(0, base.length - path.extname(base).length)
    candidates = [
      base,
      ...RESOLVE_EXTENSIONS.map((ext) => base + ext),
      ...emitted.map((ext) => stem + ext),
      ...indexes,
    ]
  }
  return candidates.filter(isFile).filter((file) => {
    const rel = path.relative(dsDir, file)
    if (rel.startsWith('..') || path.isAbsolute(rel)) return false
    return !rel.split(path.sep).includes('node_modules')
  })
}

// What one file names: the files its relative specifiers resolve to, and whether it holds an
// `import()`, `require()` or `import x = require()` whose specifier is not a plain string literal.
function readImports(file, dsDir, cache) {
  const cached = cache.get(file)
  if (cached) return cached
  const result = { resolved: [], opaque: false }
  cache.set(file, result)
  if (!CODE_FILE.test(file)) return result
  let text
  try {
    text = readFileSync(file, 'utf8')
  } catch {
    return result
  }
  const sourceFile = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true)
  result.opaque = findNonLiteralSpecifiers(sourceFile).length > 0
  for (const specifier of collectModuleSpecifiers(sourceFile)) {
    result.resolved.push(...resolveRelativeSpecifier(file, specifier, dsDir))
  }
  return result
}

// Whether the story module at `storyFile` reaches, through module specifiers and transitively, a file
// in `touched` (absolute paths) — or holds a specifier it cannot read. The visited set ends the cycles
// the real tree has (a component's story file and its `index` import each other's neighbours).
function storyReachesTouched(storyFile, touched, dsDir, cache) {
  const visited = new Set()
  const pending = [storyFile]
  while (pending.length > 0) {
    const file = pending.pop()
    if (visited.has(file)) continue
    visited.add(file)
    if (touched.has(file)) return true
    const { resolved, opaque } = readImports(file, dsDir, cache)
    if (opaque) return true
    pending.push(...resolved)
  }
  return false
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
//
// T707: and when its story module imports, transitively, a file the diff touched. The module
// specifiers of the story file and of each file it reaches are read with the TypeScript parser
// (`module-specifiers.mjs`, the reader the checker uses): a static `import`, an `export … from`, an
// `import()` and a `require()` with a plain string literal, type-only included. A relative specifier
// resolves against the importing file; every file it can name is followed (T709: `.ts`, `.tsx`, `.js`,
// `.jsx`, `.mts`, `.mjs`, `.cts`, `.cjs`, `.json`, then `index` of each), so which one a bundler loads
// does not matter; a bare or unresolvable one is ignored, and the walk stays inside the package.
// A clip, a tag or a force that a story file takes from `../Panel/story-parameters.ts` is thus
// selected when that module changes, where before only the story's directory was. A file a specifier
// names is selected whatever it renders in the story. Over-selecting is the safe direction, so a story
// file, or a file it reaches, with an `import()` or `require()` whose argument is not a plain string
// literal is selected on ANY diff inside the package: what it loads is not readable.
// Known shapes that stay outside the rule, not an exhaustive list: a file a story reaches only at run
// time and not through a module specifier its story file or a reached file names (a hook's side
// effect, state a module sets that a story reads without importing it, a stylesheet's own `@import`,
// a `new URL('…', import.meta.url)` reach, a file a plugin or the bundler configuration injects).
// `selectRuntimeStories` (the runtime pass) and `pnpm test:visual --changed` both call this one function.
//
// `diff` is repository-rooted, as `changedFiles()` reports it; `dsDir` is the package directory the
// built index's `importPath`s are relative to.
export function selectChangedStories(stories, diff, dsDir = designSystemDir) {
  const globallyAffected = diff.some((f) =>
    GLOBAL_REACH_PREFIXES.some((prefix) => f.startsWith(prefix)),
  )
  if (globallyAffected) return { stories, globallyAffected }

  const touchedInPackage = diff
    .filter((f) => f.startsWith(PACKAGE_PREFIX))
    .map((f) => f.slice(PACKAGE_PREFIX.length))
  const touchedDesignSystemDirs = new Set(touchedInPackage.map((f) => path.posix.dirname(f)))
  const touchedStoryFiles = new Set(touchedInPackage.filter((f) => storyGlob.test(f)))
  const touchedAbsolute = new Set(touchedInPackage.map((f) => path.join(dsDir, f)))
  const importCache = new Map()
  // The built index lists one entry per story, a dozen to a file: walk each story file once.
  const reachesByFile = new Map()
  const reachesTouched = (importPath) => {
    if (!reachesByFile.has(importPath)) {
      reachesByFile.set(
        importPath,
        storyReachesTouched(path.join(dsDir, importPath), touchedAbsolute, dsDir, importCache),
      )
    }
    return reachesByFile.get(importPath)
  }

  return {
    globallyAffected,
    stories: stories.filter((entry) => {
      const importPath = (entry.importPath ?? '').replace(/^\.\//, '')
      if (touchedStoryFiles.has(importPath)) return true
      if (touchedDesignSystemDirs.has(path.posix.dirname(importPath))) return true
      if (touchedInPackage.length === 0) return false
      return reachesTouched(importPath)
    }),
  }
}
