#!/usr/bin/env node
// T391: fails the *build* when the deployment target is missing a configuration key the
// application requires — before the deployment exists, rather than on every request it serves.
//
// On 2026-08-23 production answered 500 on every `/api/*` route for the whole day. Nothing was
// wrong with the code: 003 declared ten new keys (`ANALYSIS_*`, `PLAYER_SEARCH_*`,
// `FAVOURITES_MAX_PER_USER`, `REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE`), they were added to
// `.env.example` and to the local environment, and they were never added to the deployment
// target — so `Settings()` raised while FastAPI resolved each route's dependencies. The same
// class of fault had already been paid for twice: T014e ("three production faults in one
// evening, two missing environment variables") and T106's `csrf_states` migration.
//
// The repository checks its own internal coherence thoroughly — `spec_lint.py` holds
// `.env.example` against the feature artifacts, `alembic check` holds the models against the
// migrations — and nothing ever held any of it against the environment the code actually runs
// in. This is that check, and it runs in the one place with a view of both: the platform's build,
// where `vercel.json`'s `buildCommand` invokes it ahead of the web build.
//
// Two sources, deliberately, because this check's own failure mode is silence. If the pattern
// below ever stops matching a field — a differently-quoted alias, a new declaration style — the
// environment assertion would keep passing while covering fewer keys, which is indistinguishable
// from success. So the extracted list is held against `.env.example`'s keys first, in both
// directions, and any disagreement is a failure of this check rather than a smaller check.
//
// Usage:  node scripts/checks/config-preflight.mjs [--contract]
//         --contract  run the two-source agreement only, skipping the environment assertion.
//                     For CI, which can see the repository and not the deployment target.
// Env:    CONFIG_PREFLIGHT_ALLOW_ABSENT  comma-separated keys permitted to be absent from the
//                     build environment. For a key the platform genuinely does not expose at
//                     build time — not for one nobody has got round to setting. Every entry is
//                     printed on every run, so an exemption cannot become invisible.
// Exit:   0 if the two sources agree and (unless --contract) every key is set; 1 otherwise.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const settingsPath = path.join(rootDir, 'apps', 'api', 'src', 'aoe2stats_api', 'settings.py')
const envExamplePath = path.join(rootDir, '.env.example')

const contractOnly = process.argv.includes('--contract')

function log(message) {
  console.log(`config-preflight: ${message}`)
}

function fail(message) {
  console.error(`config-preflight: ${message}`)
  process.exitCode = 1
}

// `Field(alias="KEY")` is the one declaration form settings.py uses, and its module docstring
// promises no field there has a Python-side default — so every alias is a *required* key. Both
// quote styles are matched so a `ruff format` preference can never quietly shrink this list.
function declaredKeys() {
  const source = readFileSync(settingsPath, 'utf8')
  const keys = new Set()
  for (const match of source.matchAll(/alias\s*=\s*["']([A-Z][A-Z0-9_]*)["']/g)) {
    keys.add(match[1])
  }
  return keys
}

// `KEY=value` at the start of a line. Comments (`# KEY=value`) are not declarations: `.env.example`
// uses them for prose about the key above, and counting them would invent keys `Settings` does
// not have.
function documentedKeys() {
  const source = readFileSync(envExamplePath, 'utf8')
  const keys = new Set()
  for (const match of source.matchAll(/^([A-Z][A-Z0-9_]*)=/gm)) {
    keys.add(match[1])
  }
  return keys
}

function difference(left, right) {
  return [...left].filter((key) => !right.has(key)).sort()
}

const declared = declaredKeys()
const documented = documentedKeys()

if (declared.size === 0) {
  fail(
    `no Field(alias="...") declaration found in ${path.relative(rootDir, settingsPath)} — the` +
      ' extraction pattern no longer matches this file, so this check covers nothing',
  )
}

const undocumented = difference(declared, documented)
const unread = difference(documented, declared)

if (undocumented.length > 0) {
  fail(`declared in settings.py and absent from .env.example: ${undocumented.join(', ')}`)
}
if (unread.length > 0) {
  fail(`present in .env.example and read by no Settings field: ${unread.join(', ')}`)
}
if (process.exitCode === 1) {
  fail('the two sources disagree; the environment assertion below would cover the wrong set')
  process.exit(1)
}

log(
  `${declared.size} configuration keys declared, and .env.example documents the same ${declared.size}`,
)

if (contractOnly) {
  log('--contract: the environment assertion is skipped')
  process.exit(0)
}

const allowedAbsent = new Set(
  (process.env.CONFIG_PREFLIGHT_ALLOW_ABSENT ?? '')
    .split(',')
    .map((key) => key.trim())
    .filter(Boolean),
)
if (allowedAbsent.size > 0) {
  log(`exempt from the environment assertion: ${[...allowedAbsent].sort().join(', ')}`)
}

// Present-and-empty is a failure for every key but one. `BETA_ALLOWLIST_STEAM_IDS` is
// legitimately empty — settings.py's own comment says the variable must be present, possibly
// empty — and an empty `CRON_SECRET` is precisely the defect T018b closed, so "set to nothing"
// must never read as "set".
const MAY_BE_EMPTY = new Set(['BETA_ALLOWLIST_STEAM_IDS'])

const missing = []
const empty = []
for (const key of [...declared].sort()) {
  if (allowedAbsent.has(key)) continue
  const value = process.env[key]
  if (value === undefined) missing.push(key)
  else if (value.trim() === '' && !MAY_BE_EMPTY.has(key)) empty.push(key)
}

// Names only, never values: this output lands in a build log (constitution VIII).
if (missing.length > 0) {
  fail(`missing from this build's environment: ${missing.join(', ')}`)
}
if (empty.length > 0) {
  fail(`set but empty in this build's environment: ${empty.join(', ')}`)
}

if (process.exitCode === 1) {
  fail(
    'set them on the deployment target, then redeploy — every /api/* route would answer' +
      ' 503 configuration_invalid until they are',
  )
  process.exit(1)
}

log(`every configuration key is set in this build's environment`)
