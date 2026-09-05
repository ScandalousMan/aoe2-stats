#!/usr/bin/env node
// T509: `scripts/visual/a11y-allowlist.json` (T508) names accepted accessibility debt — an entry
// is a debt with an owner and a deadline, not a silent suppression. This check enforces the two
// failure modes that are decidable from the file alone:
//   1. a malformed entry — missing or empty `component`, `rule`, `date`, `fixOwed` or `fixBy`.
//   2. an expired entry — `fixBy` earlier than today.
// It does NOT check staleness (an entry naming a component-and-rule pair this run's axe scan no
// longer reports). That needs the scan's results, which exist only in the `visual` job — see
// `scripts/visual/a11y-scan.cjs`'s `checkStaleness()`, T507's concern, not this one. Keeping the
// two apart is why this check can live in the `web` job at all: it never builds Storybook.
//
// The fix-by date is what turns FR-067's "an entry may not outlive the feature" into something
// mechanical rather than a promise a reviewer has to remember to keep — applied here to this
// feature's own output, per T508/T509's own hand-back.
//
// A missing or empty allowlist file is the normal, desirable end state once phase 5 (T559) empties
// it, so it passes cleanly rather than crashing; an empty array does too, for the same reason.
//
// Usage:  node scripts/checks/a11y-allowlist.mjs
// Exit:   0 if every entry is well-formed and unexpired (or the file is absent/empty), 1 otherwise.
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const allowlistPath = path.join(rootDir, 'scripts', 'visual', 'a11y-allowlist.json')

const REQUIRED_FIELDS = ['component', 'rule', 'date', 'fixOwed', 'fixBy']

function log(message) {
  console.log(`a11y-allowlist: ${message}`)
}

function fail(message) {
  console.error(`a11y-allowlist: ${message}`)
  process.exitCode = 1
}

// Reject anything that is not a real, unambiguous ISO calendar date (`YYYY-MM-DD`). `new
// Date("soon")` parses to `Invalid Date`, and a later `<` comparison against it is always false —
// silently never overdue — so a garbage string must fail here as malformed rather than surviving
// to the expiry check and being treated as never expiring.
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/

function isValidIsoDate(value) {
  if (typeof value !== 'string' || !ISO_DATE_RE.test(value)) return false
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return false
  // Reject calendar overflow (`2026-02-30`) that `Date` would otherwise silently roll forward.
  return parsed.toISOString().slice(0, 10) === value
}

function describeEntry(entry, index) {
  const label = entry && typeof entry.component === 'string' && entry.component
  const rule = entry && typeof entry.rule === 'string' && entry.rule
  if (label && rule) return `${label} / ${rule}`
  if (label) return `${label} (entry ${index})`
  return `entry ${index}`
}

function main() {
  if (!existsSync(allowlistPath)) {
    log(
      `no allowlist found at ${path.relative(rootDir, allowlistPath)} — nothing to validate. ` +
        'This is the desired end state once phase 5 empties it.',
    )
    return
  }

  const raw = readFileSync(allowlistPath, 'utf8')
  let allowlist
  try {
    allowlist = JSON.parse(raw)
  } catch (error) {
    fail(`${path.relative(rootDir, allowlistPath)} is not valid JSON: ${error.message}`)
    return
  }

  if (!Array.isArray(allowlist)) {
    fail(
      `${path.relative(rootDir, allowlistPath)} must be a bare JSON array, found ${typeof allowlist}.`,
    )
    return
  }

  if (allowlist.length === 0) {
    log(`${path.relative(rootDir, allowlistPath)} is empty — nothing to validate.`)
    return
  }

  const malformed = []
  for (const [index, entry] of allowlist.entries()) {
    const missing = REQUIRED_FIELDS.filter((field) => {
      const value = entry?.[field]
      return typeof value !== 'string' || value.trim() === ''
    })
    // A `fixBy` (or `date`) that is present and non-empty but not a real ISO date is malformed
    // too — it must not reach the expiry comparison and be silently treated as never overdue.
    if (!missing.includes('fixBy') && entry?.fixBy !== undefined && !isValidIsoDate(entry.fixBy)) {
      missing.push('fixBy (not a valid ISO date)')
    }
    if (!missing.includes('date') && entry?.date !== undefined && !isValidIsoDate(entry.date)) {
      missing.push('date (not a valid ISO date)')
    }
    if (missing.length > 0) {
      malformed.push({ entry, index, missing })
    }
  }

  if (malformed.length > 0) {
    fail(
      `${malformed.length} malformed entr${malformed.length === 1 ? 'y' : 'ies'} in ` +
        `${path.relative(rootDir, allowlistPath)}:`,
    )
    for (const { entry, index, missing } of malformed) {
      fail(`  - ${describeEntry(entry, index)}: missing/invalid ${missing.join(', ')}`)
    }
  }

  const today = new Date().toISOString().slice(0, 10)
  const wellFormed = allowlist.filter((entry, index) => !malformed.some((m) => m.index === index))
  const expired = wellFormed.filter((entry) => entry.fixBy < today)

  if (expired.length > 0) {
    fail(
      `${expired.length} expired entr${expired.length === 1 ? 'y' : 'ies'} in ` +
        `${path.relative(rootDir, allowlistPath)}:`,
    )
    for (const entry of expired) {
      const overdueDays = Math.round(
        (new Date(today).getTime() - new Date(entry.fixBy).getTime()) / (24 * 60 * 60 * 1000),
      )
      fail(
        `  - ${describeEntry(entry, allowlist.indexOf(entry))}: fixBy ${entry.fixBy} is ` +
          `${overdueDays} day${overdueDays === 1 ? '' : 's'} overdue`,
      )
    }
  }

  if (malformed.length > 0 || expired.length > 0) {
    return
  }

  const nearestFixBy = [...wellFormed].sort((a, b) => (a.fixBy < b.fixBy ? -1 : 1))[0]?.fixBy
  log(
    `${allowlist.length} entr${allowlist.length === 1 ? 'y' : 'ies'} validated; ` +
      `nearest fixBy is ${nearestFixBy}.`,
  )
}

main()
