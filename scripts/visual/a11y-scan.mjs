// Shared between `scripts/visual/run.mjs` (the orchestrator: resets state before the run, gates
// the exit code on staleness after it) and `tests/visual/stories.spec.ts` (the scan itself: writes
// what it found). Kept in one small module rather than duplicated, per T507 (FR-057, FR-058,
// SC-007) — the scan owns the staleness half of the allowlist T508 creates, because it is the only
// thing that has this run's results in hand.
//
// `scripts/visual/a11y-allowlist.json` (created by T508, read here, absent today) is an array of:
//   { "component": "site-header", "rule": "color-contrast", "date": "2026-09-05",
//     "fixOwed": "...", "fixBy": "2026-..." }
// `component` MUST be the kebab-case form `componentFromTitle` below produces (the last path
// segment of the story's Storybook title, e.g. "Chrome/SiteHeader" -> "site-header"), and `rule`
// MUST be the axe-core rule id (e.g. "color-contrast", "aria-allowed-attr"). Only `component` and
// `rule` are read here; the date fields are T509's concern (`scripts/checks/a11y-allowlist.mjs`),
// not this scan's.
import { existsSync, mkdirSync, readFileSync, appendFileSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

export const allowlistPath = path.join(rootDir, 'scripts/visual/a11y-allowlist.json')

// Not committed (`test-results/` is gitignored) and reset once per `run.mjs` invocation, never per
// test — the whole point is to answer "what did *this run* cover", and a leftover file from an
// earlier, differently-scoped run would misreport a component as covered when it was not reselected.
const resultsDir = path.join(rootDir, 'test-results', 'a11y-scan')
const scannedLogPath = path.join(resultsDir, 'scanned.ndjson')
const violationsLogPath = path.join(resultsDir, 'violations.ndjson')

/**
 * A Storybook title's last path segment, in the kebab-case the design system's own spec files use
 * (`packages/design-system/specs/site-header.md`), so an allowlist entry reads the same way a
 * component is named everywhere else in this repository. `VISUAL_STORIES` only carries the story
 * id, not the title, which is why `stories.spec.ts` reads the built Storybook index itself to
 * recover it — see the comment at that call site.
 */
export function componentFromTitle(title) {
  const name = title.split('/').pop() ?? title
  return name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()
}

/** Called once by `run.mjs`, before Playwright starts, never by a test. */
export function resetResultsDir() {
  rmSync(resultsDir, { recursive: true, force: true })
  mkdirSync(resultsDir, { recursive: true })
}

function appendLine(file, record) {
  mkdirSync(path.dirname(file), { recursive: true })
  appendFileSync(file, `${JSON.stringify(record)}\n`)
}

// Recorded unconditionally — whether or not the rule is allowlisted, and even when no violation is
// found at all — because the staleness check needs to know every component this run actually
// scanned, not only the ones that failed.
export function recordScanned(component, theme) {
  appendLine(scannedLogPath, { component, theme })
}

export function recordViolation(component, theme, rule) {
  appendLine(violationsLogPath, { component, theme, rule })
}

function readNdjson(file) {
  if (!existsSync(file)) return []
  return readFileSync(file, 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line))
}

let cachedAllowlist
export function readAllowlist() {
  if (cachedAllowlist) return cachedAllowlist
  cachedAllowlist = existsSync(allowlistPath) ? JSON.parse(readFileSync(allowlistPath, 'utf8')) : []
  return cachedAllowlist
}

export function isAllowed(component, rule) {
  return readAllowlist().some((entry) => entry.component === component && entry.rule === rule)
}

/**
 * The staleness half of T509's allowlist (owned here, not there, per T507's task text): an entry
 * whose component-and-rule pair this run scanned and did not report is a stale suppression hiding
 * a fix that already happened. An entry naming a component this run never selected is neither
 * fresh nor stale — a diff-scoped run has no evidence either way — so it is skipped, not failed.
 * Called once by `run.mjs`, after Playwright exits, over the files every worker's test wrote.
 */
export function checkStaleness() {
  const allowlist = readAllowlist()
  if (allowlist.length === 0) return []

  const covered = new Set(readNdjson(scannedLogPath).map((entry) => entry.component))
  const found = new Set(
    readNdjson(violationsLogPath).map((entry) => `${entry.component}::${entry.rule}`),
  )

  return allowlist.filter(
    (entry) => covered.has(entry.component) && !found.has(`${entry.component}::${entry.rule}`),
  )
}
