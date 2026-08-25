#!/usr/bin/env node
// T393: asks the deployed application whether it is actually serving, from outside it.
//
// Nothing did, before this. `/` is a static build of `apps/web/dist` and answers 200 from the CDN
// whatever state the function is in, so "the site is up" was true and useless throughout the
// 2026-08-23 outage, in which every `/api/*` route answered 500 for the whole day. The one route
// that could have said why — `GET /api/health`, which reports configuration, database and bucket
// reachability *from the function process* — was never called by anything except a human who
// already suspected something.
//
// Two assertions, and the second is not redundant:
//   1. `/api/health` answers 200. Configuration, Postgres and the bucket, from inside the process.
//   2. `GET /api/me` answers 200 with `authenticated: false`. This is the front end's bootstrap
//      call (`apps/web/src/routes/__root.tsx`): the application is unusable when it fails, and it
//      is the exact request that reported the outage. `/api/health` is reachable through its own
//      dependency ordering and a route can break in ways a probe route does not — an unhandled
//      exception in `auth.py`, a router that failed to register — so the bootstrap call is
//      asserted directly rather than inferred.
//
// **The schema.** `/api/health`'s database probe used to be `SELECT 1` alone, which succeeds
// against a schema missing every column a migration would have added — so the first version of
// this file passed while the 2026-08-23 outage was still live. T394 gave the route a revision
// probe: it compares `alembic_version` against the revision the deployed build expects and
// answers `schema_out_of_date` when they differ, which this check reports below by name. What it
// still does not do is *apply* the migration; that gap is T392's, and a green run here means the
// deployed schema matches the deployed code, never that the pipeline can make it so.
//
// Usage:  node scripts/checks/production-health.mjs [--settle 120] [--confirmations 2]
// Env:    SMOKE_BASE_URL  origin to probe (default https://aoe2-stats.com)
// Exit:   0 if both routes answer as above, on every confirmation; 1 otherwise.
const baseUrl = (process.env.SMOKE_BASE_URL ?? 'https://aoe2-stats.com').replace(/\/+$/, '')

function argValue(name, fallback) {
  const index = process.argv.indexOf(name)
  if (index === -1 || index === process.argv.length - 1) return fallback
  const value = Number(process.argv[index + 1])
  return Number.isFinite(value) ? value : fallback
}

// Seconds to wait before the first probe. A deploy replaces the function some time after the push
// that triggered this run, so probing immediately reads the *previous* deployment — which is
// exactly the one that was fine. The workflow that runs on a push passes a settle window; the
// nightly run, which is not racing a deploy, does not.
const settleSeconds = argValue('--settle', 0)
// Consecutive successful probes required. One 200 during a rollout can come from either
// deployment; two, spaced apart, cannot both come from the old one for long.
const confirmations = argValue('--confirmations', 2)
const intervalSeconds = argValue('--interval', 15)
// A transient network failure — DNS, a dropped connection — is not evidence about the
// deployment. A non-200 *is*, and is never retried.
const networkRetries = argValue('--network-retries', 3)

const sleep = (seconds) => new Promise((resolve) => setTimeout(resolve, seconds * 1000))

function log(message) {
  console.log(`production-health: ${message}`)
}

function fail(message) {
  console.error(`production-health: ${message}`)
}

async function get(pathname) {
  let lastError
  for (let attempt = 1; attempt <= networkRetries; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}${pathname}`, {
        headers: { accept: 'application/json' },
        redirect: 'manual',
      })
      const text = await response.text()
      let body
      try {
        body = JSON.parse(text)
      } catch {
        body = null
      }
      return { status: response.status, text, body }
    } catch (error) {
      lastError = error
      fail(`${pathname}: network failure on attempt ${attempt}/${networkRetries}: ${error.message}`)
      if (attempt < networkRetries) await sleep(5)
    }
  }
  throw lastError
}

// The failure this whole file exists for names its own cause in the response body — `/api/health`
// answers `configuration_invalid` 503 with the key names, and since T390 so does every other
// route. Surfacing it here means the workflow log holds the diagnosis, rather than a status code
// and an instruction to go and look somewhere else.
function describe(pathname, result) {
  const code = result.body?.error?.code
  const keys = result.body?.error?.detail?.missing_or_invalid_keys
  if (code === 'configuration_invalid' && Array.isArray(keys)) {
    return (
      `${pathname} answered ${result.status} configuration_invalid — the deployment target is` +
      ` missing or has invalid: ${keys.join(', ')}. Set them and redeploy.`
    )
  }
  if (code === 'schema_out_of_date') {
    const { expected, found } = result.body.error.detail ?? {}
    return (
      `${pathname} answered ${result.status} schema_out_of_date — this build expects revision` +
      ` ${expected} and the database is at ${found ?? 'no revision at all'}. Run` +
      ` \`alembic upgrade head\` against the direct endpoint, not the pooler.`
    )
  }
  if (code) return `${pathname} answered ${result.status} ${code}: ${result.text.slice(0, 500)}`
  return `${pathname} answered ${result.status}: ${result.text.slice(0, 500)}`
}

async function probe() {
  const health = await get('/api/health')
  if (health.status !== 200) {
    fail(describe('/api/health', health))
    return false
  }

  const me = await get('/api/me')
  if (me.status !== 200) {
    fail(describe('/api/me', me))
    return false
  }
  // 200 with the wrong shape is the bootstrap call still being broken. `authenticated` is the one
  // field `__root.tsx` branches on before anything renders.
  if (typeof me.body?.authenticated !== 'boolean') {
    fail(`/api/me answered 200 without a boolean "authenticated": ${me.text.slice(0, 500)}`)
    return false
  }
  return true
}

log(`probing ${baseUrl}`)
if (settleSeconds > 0) {
  log(`waiting ${settleSeconds}s for the deployment to become current before the first probe`)
  await sleep(settleSeconds)
}

for (let confirmation = 1; confirmation <= confirmations; confirmation += 1) {
  if (confirmation > 1) await sleep(intervalSeconds)
  if (!(await probe())) {
    fail(`failed on confirmation ${confirmation}/${confirmations}`)
    process.exit(1)
  }
  log(`confirmation ${confirmation}/${confirmations}: /api/health and /api/me both answered 200`)
}

log('the deployment is serving')
