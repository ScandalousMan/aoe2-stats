#!/usr/bin/env node
// T592: reads a `chore(visual): regenerate baselines from CI` commit so a reviewer does not have to
// read every rewritten capture by hand (how many that is, this file does not restate — see
// `packages/design-system/specs/README.md`'s "The baseline set, as it stands", the one place that
// number lives and the check that asserts it). `.github/workflows/baselines.yml` keeps
// `--update-snapshots=all` (that file's own "Challenged and kept, 2026-09-12" header comment carries the full reasoning: a
// baseline's provenance has to be a `git` fact, which `--changed` would give up) — the cost is that
// the resulting commit rewrites every selected capture, most of which only moved by anti-aliasing
// noise, and `git diff --stat` cannot tell a real move from noise. This script can: it decodes each
// rewritten PNG against its own predecessor (`git show <base>:<path>` vs `git show <head>:<path>`)
// and reports, per capture, the differing-pixel count and ratio, grouped into what moved beyond
// anti-aliasing noise and what did not.
//
// **This is a reporting tool, not a gate** — it always exits 0 (a `git`-command failure, e.g. a bad
// ref, is a usage error and exits non-zero, but a finding of "N captures moved" never does). A
// regeneration legitimately moves anything the change it followed touched; there is no count of
// moved captures that is itself wrong, so nothing here can fail a build the way the other
// `scripts/checks/*.mjs` files do.
//
// Decode reuse: the pixel-counting decode this script needs is `story-baselines-duplicates.mjs`'s
// own `pixelDiffCount` (extracted from what used to be `pixelDiffRatio`'s own inline loop, by this
// same task, specifically so this file did not have to reimplement it — see that file's own header).
// `decodePng` (the same `pngjs` call) is reused unchanged; only the source a "path" resolves to
// differs — a real file there, a `git show <rev>:<path>` buffer here — which is why `decodePng`'s own
// `readFile` parameter is injectable and this file supplies a git-backed one instead of
// `fs.readFileSync`.
//
// Threshold: measured directly against the two regenerations this file's own validation run
// (`baseline-regeneration-diff.test.mjs` and this script's own header-required manual run) checks
// itself against, `ba20f074` and `822b4904` (this task, 2026-09-12): the largest noise-only move
// seen in either is 37 pixels, on `primitives-table--row-link-active-light-1280.png`, present
// unchanged in both; the smallest real move is 580 pixels, on `primitives-link--active-standalone-*`
// in `ba20f074` (T583's press ring) — `822b4904`'s own smallest real move is 1276. `NOISE_MAX_DIFF_
// PIXELS` is set to 100: comfortably above the highest noise this task ever measured (37, in either
// commit) and comfortably below the lowest real move this task ever measured (580, in `ba20f074`) —
// the same kind of gap `DUPLICATE_MAX_DIFF_RATIO` documents for a different question, not a boundary
// either commit's own pixel deltas happen to approach. This also corrected the hand-measured "39
// baselines moved" originally recorded for `ba20f074`: `Callout`'s own `FocusVisible` story moved
// too (a cascade of T586's Button ring-offset change, missed by eye) — 10 stories moved, not 9. See
// `.github/workflows/baselines.yml`'s own "Challenged and kept" comment for the full reconciliation,
// now corrected to match this script's output.
//
// Usage:  node scripts/checks/baseline-regeneration-diff.mjs [<headRef>] [<baseRef>]
//         headRef defaults to HEAD; baseRef defaults to `<headRef>^` (its direct parent) when not
//         given — the "one regeneration commit against the commit it rewrote" shape this task's own
//         two validation commits (`ba20f074`, `822b4904`) both are.
// Exit:   0 always, unless the `git` commands themselves fail (a bad ref, not a repository). A pair
//         of refs with no differing PNG under `packages/design-system/__screenshots__/` is not an
//         error: it reports zero rewritten captures and exits 0, which is what lets
//         `.github/workflows/baselines.yml` run it unconditionally after a regeneration that turned
//         out to move nothing.
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { BASELINE_NAME_RE, loadAppRouteBaselineNames } from './story-baselines.mjs'
import { decodePng, pixelDiffCount } from './story-baselines-duplicates.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const screenshotsPathspec = 'packages/design-system/__screenshots__/'
const defaultAppRoutesSpecPath = path.join(rootDir, 'tests', 'visual', 'app-routes.spec.ts')

// See this file's own header for why 100, and why not the workflow comment's own "25"/"1276" as-is.
export const NOISE_MAX_DIFF_PIXELS = 100

// Every `M` or `R###` entry `git diff --name-status` reports between `baseRef` and `headRef`, under
// `pathspec`, plus every `A` (added, nothing to compare against) and `D` (removed, nothing to compare
// against) — parsed once so callers never re-run the same `git diff` twice. A rename's "new" path is
// what every other field of this function's result is keyed on; its "old" path (the third
// tab-separated field `R###` alone carries) is threaded through so the old blob is still read from
// where it actually was.
export function listChangedBaselines({
  baseRef,
  headRef,
  pathspec = screenshotsPathspec,
  run = (args) => execFileSync('git', args, { cwd: rootDir, encoding: 'utf8' }),
}) {
  const output = run(['diff', '--name-status', baseRef, headRef, '--', pathspec])
  const modified = []
  const added = []
  const removed = []
  for (const line of output.split('\n')) {
    if (!line.trim()) continue
    const fields = line.split('\t')
    const status = fields[0]
    if (status.startsWith('R')) {
      modified.push({ oldPath: fields[1], newPath: fields[2] })
    } else if (status === 'M') {
      modified.push({ oldPath: fields[1], newPath: fields[1] })
    } else if (status === 'A') {
      added.push(fields[1])
    } else if (status === 'D') {
      removed.push(fields[1])
    }
    // Any other status (`C`opy, `T`ype-change, `U`nmerged) never occurs for a baseline PNG in this
    // repository's own history — a baseline is written by one workflow, never copied or retyped —
    // so none is handled here; a future one would silently be neither reported nor mis-reported.
  }
  return { modified, added, removed }
}

// Raw bytes for one path at one git ref (`git show <ref>:<path>`) — the same thing
// `fs.readFileSync` returns for a working-tree file, so `decodePng` (T584's own decode, reused
// unchanged below) does not need to know the difference. Binary-safe (`encoding` deliberately left
// unset): a PNG's own bytes must reach `pngjs` untouched.
export function readGitBlob(ref, filePath) {
  return execFileSync('git', ['show', `${ref}:${filePath}`], {
    cwd: rootDir,
    maxBuffer: 1024 * 1024 * 256,
  })
}

// `pixelDiffCount`'s own decode (T584's, reused unchanged), applied to the same PNG at two different
// refs rather than two different files on disk — `readBlob` is injectable so
// baseline-regeneration-diff.test.mjs can prove this against in-memory fixtures instead of a real
// `git show`. Exceptions (an unreadable blob — the path did not exist at that ref, which
// `listChangedBaselines`'s own `M`/`R`/`A`/`D` split should prevent, but a rename across a history
// rewrite is exactly the case worth not trusting blindly) fall through to `pixelDiffCount`'s own
// `dimensionMismatch: true` path via `decodePng`'s ordinary throw-on-bad-input behaviour.
// `pixelDiffCount` identifies its two inputs by the "path" string alone, which collides the instant
// `oldPath === newPath` — every ordinary `M` (not a rename) has exactly that shape. `ref:path`
// composite keys keep the two calls distinct (a `baseRef`/`headRef` pair is never equal to itself
// when this function is ever worth calling) without `pixelDiffCount` itself needing to know refs
// exist at all.
export function pixelDiffCountAcrossRefs({
  baseRef,
  headRef,
  oldPath,
  newPath,
  readBlob = readGitBlob,
}) {
  const oldKey = `${baseRef}:${oldPath}`
  const newKey = `${headRef}:${newPath}`
  const decode = (key) => {
    const ref = key === oldKey ? baseRef : headRef
    const filePath = key === oldKey ? oldPath : newPath
    return decodePng(filePath, () => readBlob(ref, filePath))
  }
  return pixelDiffCount(oldKey, newKey, decode)
}

// This capture's story id (the six-unit `{id}-{theme}-{width}.png` shape `BASELINE_NAME_RE` already
// parses for `story-baselines.mjs` and `story-baselines-duplicates.mjs`), or `null` for anything that
// is not one — today, only the app-route full-page captures `appRouteNames` names (theme suffix, no
// width, T553's own shape). A baseline neither pattern explains is reported under its own bare
// filename rather than dropped, the same "never silently miss a file" instinct
// `story-baselines-duplicates.mjs`'s "unmapped baseline" finding follows, even though this script
// itself never fails on one.
export function deriveGroupLabel(fileName, appRouteNames) {
  const baseName = fileName.slice(0, -'.png'.length)
  const match = fileName.match(BASELINE_NAME_RE)
  if (match) return { kind: 'story', id: match[1] }
  if (appRouteNames.has(baseName)) return { kind: 'app-route', id: baseName }
  return { kind: 'unmapped', id: baseName }
}

// `bucket` for one capture's diff: `'moved'` beyond `NOISE_MAX_DIFF_PIXELS`, including every
// dimension change (a resized capture is never merely noise — see this file's header on
// `pixelDiffCount`'s `dimensionMismatch`), otherwise `'noise'`.
export function classifyDiff({ dimensionMismatch, diffPixels }, threshold = NOISE_MAX_DIFF_PIXELS) {
  if (dimensionMismatch) return 'moved'
  return diffPixels > threshold ? 'moved' : 'noise'
}

// The full report for one `baseRef`..`headRef` comparison: every modified capture's diff (grouped by
// story/app-route/unmapped label), plus the added/removed lists `listChangedBaselines` already
// separated out (neither has a "before" or "after" to decode against, so neither is ever classified).
export function buildReport({
  baseRef,
  headRef,
  pathspec = screenshotsPathspec,
  appRoutesSpecPath = defaultAppRoutesSpecPath,
  run,
  readBlob,
  readSpecFile = (p) => readFileSync(p, 'utf8'),
}) {
  const { modified, added, removed } = listChangedBaselines({ baseRef, headRef, pathspec, run })
  let appRouteNames
  try {
    appRouteNames = loadAppRouteBaselineNames(readSpecFile(appRoutesSpecPath))
  } catch {
    appRouteNames = new Set()
  }

  const captures = modified.map(({ oldPath, newPath }) => {
    const fileName = path.basename(newPath)
    const { dimensionMismatch, diffPixels, totalPixels } = pixelDiffCountAcrossRefs({
      baseRef,
      headRef,
      oldPath,
      newPath,
      ...(readBlob ? { readBlob } : {}),
    })
    const ratio = dimensionMismatch ? null : diffPixels / totalPixels
    const bucket = classifyDiff({ dimensionMismatch, diffPixels })
    const label = deriveGroupLabel(fileName, appRouteNames)
    return {
      path: newPath,
      fileName,
      label,
      dimensionMismatch,
      diffPixels,
      totalPixels,
      ratio,
      bucket,
    }
  })

  const groups = new Map()
  for (const capture of captures) {
    const key = `${capture.label.kind}:${capture.label.id}`
    if (!groups.has(key))
      groups.set(key, { kind: capture.label.kind, id: capture.label.id, captures: [] })
    groups.get(key).captures.push(capture)
  }

  return {
    baseRef,
    headRef,
    captures,
    groups: [...groups.values()].sort((a, b) => a.id.localeCompare(b.id)),
    added,
    removed,
  }
}

// ---------------------------------------------------------------------------------------------
// Console formatting.
// ---------------------------------------------------------------------------------------------

function formatRatio(ratio) {
  if (ratio === null) return 'n/a (dimensions changed)'
  return `${(ratio * 100).toFixed(3)}%`
}

function formatCaptureLine(capture) {
  const diff = capture.dimensionMismatch ? 'dimensions changed' : `${capture.diffPixels}px`
  return `      ${capture.fileName}: ${diff} (${formatRatio(capture.ratio)})`
}

export function formatReport(report) {
  const lines = []
  lines.push(
    `baseline-regeneration-diff: comparing ${report.baseRef}..${report.headRef} under ` +
      `${screenshotsPathspec}`,
  )
  lines.push(
    `  ${report.captures.length} capture(s) rewritten, ${report.added.length} added, ` +
      `${report.removed.length} removed.`,
  )

  const movedGroups = report.groups
    .map((g) => ({ ...g, captures: g.captures.filter((c) => c.bucket === 'moved') }))
    .filter((g) => g.captures.length > 0)
  const noiseGroups = report.groups
    .map((g) => ({ ...g, captures: g.captures.filter((c) => c.bucket === 'noise') }))
    .filter((g) => g.captures.length > 0)
  const movedCount = movedGroups.reduce((n, g) => n + g.captures.length, 0)
  const noiseCount = noiseGroups.reduce((n, g) => n + g.captures.length, 0)

  lines.push('')
  lines.push(
    `  Moved beyond anti-aliasing noise (> ${NOISE_MAX_DIFF_PIXELS}px, or a dimension change): ` +
      `${movedGroups.length} group(s), ${movedCount} capture(s).`,
  )
  for (const group of movedGroups) {
    lines.push(`    [${group.kind}] ${group.id} (${group.captures.length}):`)
    for (const capture of group.captures) lines.push(formatCaptureLine(capture))
  }

  lines.push('')
  lines.push(
    `  Did not move (at or under ${NOISE_MAX_DIFF_PIXELS}px, anti-aliasing noise): ` +
      `${noiseGroups.length} group(s), ${noiseCount} capture(s).`,
  )
  for (const group of noiseGroups) {
    lines.push(`    [${group.kind}] ${group.id} (${group.captures.length}):`)
    for (const capture of group.captures) lines.push(formatCaptureLine(capture))
  }

  if (report.added.length > 0) {
    lines.push('')
    lines.push(`  Added (no predecessor to compare against): ${report.added.length}`)
    for (const file of report.added) lines.push(`    ${file}`)
  }
  if (report.removed.length > 0) {
    lines.push('')
    lines.push(`  Removed (no successor to compare against): ${report.removed.length}`)
    for (const file of report.removed) lines.push(`    ${file}`)
  }

  return lines.join('\n')
}

// Only run when invoked directly — baseline-regeneration-diff.test.mjs imports the functions above
// without triggering a real `git` call, the same guard token-scale.mjs and story-baselines.mjs use.
function main() {
  const [, , headRefArg, baseRefArg] = process.argv
  const headRef = headRefArg ?? 'HEAD'
  const baseRef = baseRefArg ?? `${headRef}^`
  const report = buildReport({ baseRef, headRef })
  console.log(formatReport(report))
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
