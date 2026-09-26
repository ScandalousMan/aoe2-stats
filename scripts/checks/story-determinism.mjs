#!/usr/bin/env node
// T673: closes item 9's second half's row ("every story is deterministic") of
// packages/design-system/specs/README.md's "Verification-coverage gap register" (deleted by T673
// once a run backed the verdict — see that file's git history for the sizing this implements).
// Nothing in this repository, before this file, rendered a story twice and compared the two
// renders: `story-baselines.mjs` proves structural completeness (every story has its six baselines
// on disk) and `story-baselines-duplicates.mjs` proves two *different* stories' units are not
// accidentally identical; neither asks whether one story's own render is stable run to run.
//
// The two renders this file compares are never a checked-in baseline
// (`packages/design-system/__screenshots__`) — they are two fresh, independent captures written by
// `tests/visual/stories.spec.ts` itself, under `playwright.config.ts`'s own `determinism` project
// (`repeatEach: 2`), to `test-results/determinism/pass-0` and `test-results/determinism/pass-1` (or
// `VISUAL_DETERMINISM_DIR`'s own children, if set — `resolveDeterminismDir` below resolves this
// file's read location the same way that project resolves its write location) — gitignored,
// ephemeral, produced fresh by the CI job this script runs beside. "Render A vs. the checked-in
// baseline" and "render A vs. render B, taken seconds apart" are different questions; this file
// only ever answers the second.
//
// Reuses `story-baselines-duplicates.mjs`'s own `pixelDiffRatio` idiom directly — the fraction of
// differing pixels between two same-dimensioned PNGs — rather than a second implementation of pixel
// comparison, and the same `DUPLICATE_MAX_DIFF_RATIO` (0.01) that file already accepts elsewhere as
// anti-aliasing noise: a genuine non-determinism (an unfrozen clock, a running animation, a
// font-swap race) moves far more of a frame than that, the same gap `story-baselines-duplicates.mjs`'s
// own header measures between noise-only pairs (≤0.065%) and a real defect (1.1-4.0%+).
//
// What fails, precisely:
//   - either pass directory missing, or found with zero PNGs — this check must not pass vacuously,
//     so "nothing to compare" is a failure, not a silent zero (the same rule every other check in
//     this directory follows);
//   - a PNG present in one pass and not the other (the two passes must have rendered the exact same
//     unit set — a mismatch means the harness itself broke, not that determinism was disproved);
//   - any pair whose `pixelDiffRatio` exceeds `threshold` — reported by name and ratio, so a finding
//     names the exact unit rather than only a count.
//
// Usage:  node scripts/checks/story-determinism.mjs [passADir] [passBDir]
// Exit:   0 if both passes captured the same non-empty unit set and every pair is within
//         `DUPLICATE_MAX_DIFF_RATIO` of each other, 1 otherwise.
import { existsSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DUPLICATE_MAX_DIFF_RATIO, pixelDiffRatio } from './story-baselines-duplicates.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

// The write location `playwright.config.ts`'s `determinism` project resolves
// `VISUAL_DETERMINISM_DIR` into (that file's own `determinismSnapshotDir`) — read here the same
// way, against the same root, so editing the env var in `nightly.yml` moves both the write and the
// read together. Reads `process.env` at call time, never a module-load-time constant, so a test
// (or a caller) can set the var and see this resolve differently within the same process.
export function resolveDeterminismDir(env = process.env) {
  return path.resolve(rootDir, env.VISUAL_DETERMINISM_DIR ?? 'test-results/determinism')
}

function defaultPassDir(index, env = process.env) {
  return path.join(resolveDeterminismDir(env), `pass-${index}`)
}

// Every `.png` filename directly inside `dir`, sorted — or `null` when `dir` does not exist at all
// (distinct from an existing, empty directory, so a caller can tell "the capture step never ran"
// apart from "it ran and captured nothing").
export function listPngFiles(dir) {
  if (!existsSync(dir)) return null
  return readdirSync(dir)
    .filter((f) => f.endsWith('.png'))
    .sort()
}

// Compares every unit both passes captured, reusing `pixelDiffRatio` (injectable so
// story-determinism.test.mjs can prove this against small in-memory-derived fixtures rather than a
// real Playwright run). Returns every finding rather than throwing, and the number of pairs actually
// compared — `runCheck` is what turns this into a process exit code.
export function compareRenderPasses({
  passADir,
  passBDir,
  threshold = DUPLICATE_MAX_DIFF_RATIO,
  getPixelDiffRatio = pixelDiffRatio,
}) {
  const findings = []

  const filesA = listPngFiles(passADir)
  const filesB = listPngFiles(passBDir)

  if (filesA === null) {
    findings.push(`no pass directory found at ${path.relative(rootDir, passADir)}.`)
  }
  if (filesB === null) {
    findings.push(`no pass directory found at ${path.relative(rootDir, passBDir)}.`)
  }
  if (filesA === null || filesB === null) {
    return { findings, comparedCount: 0 }
  }

  if (filesA.length === 0 || filesB.length === 0) {
    findings.push(
      `zero captures found (pass-0: ${filesA.length}, pass-1: ${filesB.length}) — a determinism ` +
        'check with nothing to compare must not pass vacuously.',
    )
    return { findings, comparedCount: 0 }
  }

  const setA = new Set(filesA)
  const setB = new Set(filesB)
  const onlyInA = filesA.filter((f) => !setB.has(f))
  const onlyInB = filesB.filter((f) => !setA.has(f))
  for (const name of onlyInA) {
    findings.push(`${name}: captured in pass-0, missing from pass-1.`)
  }
  for (const name of onlyInB) {
    findings.push(`${name}: captured in pass-1, missing from pass-0.`)
  }

  const common = filesA.filter((f) => setB.has(f)).sort()
  for (const name of common) {
    const pathA = path.join(passADir, name)
    const pathB = path.join(passBDir, name)
    const ratio = getPixelDiffRatio(pathA, pathB)
    if (ratio > threshold) {
      findings.push(
        `${name}: pass-0 and pass-1 differ by ${(ratio * 100).toFixed(3)}% of pixels, over the ` +
          `${(threshold * 100).toFixed(2)}% tolerance — this story is not deterministic.`,
      )
    }
  }

  return { findings, comparedCount: common.length }
}

function log(message) {
  console.log(`story-determinism: ${message}`)
}

function fail(message) {
  console.error(`story-determinism: ${message}`)
}

export function runCheck({
  // `undefined` here, not a module-load-time constant: the default is resolved below, at call
  // time, so it reads whatever `VISUAL_DETERMINISM_DIR` is set to *now* — explicit argv/caller
  // values still win outright.
  passADir,
  passBDir,
  threshold = DUPLICATE_MAX_DIFF_RATIO,
  getPixelDiffRatio = pixelDiffRatio,
} = {}) {
  const { findings, comparedCount } = compareRenderPasses({
    passADir: passADir ?? defaultPassDir(0),
    passBDir: passBDir ?? defaultPassDir(1),
    threshold,
    getPixelDiffRatio,
  })
  return { findings, comparedCount, exitCode: findings.length > 0 ? 1 : 0 }
}

function main() {
  const [passADirArg, passBDirArg] = process.argv.slice(2)
  const passADir = passADirArg ? path.resolve(rootDir, passADirArg) : defaultPassDir(0)
  const passBDir = passBDirArg ? path.resolve(rootDir, passBDirArg) : defaultPassDir(1)

  const { findings, comparedCount, exitCode } = runCheck({ passADir, passBDir })
  if (findings.length > 0) {
    for (const finding of findings) fail(finding)
    fail(`${findings.length} finding${findings.length === 1 ? '' : 's'}.`)
  } else {
    log(`${comparedCount} render pair(s) compared; every one is within tolerance.`)
  }
  process.exitCode = exitCode
}

// Only run when invoked directly — story-determinism.test.mjs imports the functions above without
// triggering the scan or the process exit code, the same guard every other check in this directory
// uses.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
