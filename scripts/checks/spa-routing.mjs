#!/usr/bin/env node
// T109: fails when a client-side route has no way to reach the application shell on a direct
// request — a reload, a bookmark, a shared link or a browser restore, as opposed to an in-app
// navigation, which never touches the origin at all.
//
// The deployment is a static build of apps/web/dist behind exactly one rewrite, `/api/(.*)` to
// the function. Vercel resolves a request in a fixed order — a filesystem match against the
// output directory first, then `rewrites` top to bottom, first match wins — and with no
// catch-all fallback to `index.html`, every route the client-side router owns (anything that is
// not `/`, which happens to already be a file) falls through to the platform's own 404 before a
// line of the application's JavaScript runs. Measured against production: the root and `/api/me`
// both answered 200 while `/sign-in`, `/sign-in?link=false` and `/dashboard` all answered 404.
//
// The route list is derived from apps/web/src/routes/ rather than restated here, so a route
// added later is covered without anyone remembering to add it to this check.
//
// Usage:  node scripts/checks/spa-routing.mjs
// Exit:   0 if every derived route reaches the shell, the API keeps reaching the function, and a
//         built asset is still served from disk; 1 otherwise.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const distDir = path.join(rootDir, 'apps', 'web', 'dist')
const assetsDir = path.join(distDir, 'assets')
const routesDir = path.join(rootDir, 'apps', 'web', 'src', 'routes')
const apiDir = path.join(rootDir, 'api')
const vercelJsonPath = path.join(rootDir, 'vercel.json')

function log(message) {
  console.log(`spa-routing: ${message}`)
}

// Walks apps/web/src/routes/ for the files TanStack Router's file-based routing turns into
// URLs, skipping the ones that are not routes at all: `__root.tsx` (the shell every route
// renders inside, never a URL of its own) and test/story files colocated with their route.
function findRouteFiles(dir, base = dir) {
  const files = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...findRouteFiles(full, base))
      continue
    }
    if (!/\.tsx?$/.test(entry.name)) continue
    if (entry.name.startsWith('__root.')) continue
    if (entry.name.includes('.test.') || entry.name.includes('.stories.')) continue
    files.push(path.relative(base, full))
  }
  return files
}

// TanStack Router's file-based convention: `index.tsx` is the segment's own URL, everything
// else is a literal path segment, and `foo/index.tsx` is `/foo` rather than `/foo/index`.
function routeFileToUrl(relativeFile) {
  const withoutExt = relativeFile.replace(/\.tsx?$/, '')
  const segments = withoutExt.split(path.sep).filter((segment) => segment !== 'index')
  return '/' + segments.join('/')
}

// The sources in this repository's vercel.json are already regex fragments (`/api/(.*)`), not
// path-to-regexp shorthand — so anchoring the fragment is enough to reproduce Vercel's match.
// This is intentionally scoped to that style, not a general path-to-regexp implementation.
function sourceToRegex(source) {
  return new RegExp(`^${source}$`)
}

// Reproduces Vercel's resolution order for one request path: a filesystem match against the
// output directory first, then `rewrites` top to bottom, first match wins.
function resolve(urlPath, rewrites) {
  const filePath = urlPath === '/' ? 'index.html' : urlPath.replace(/^\//, '')
  const onDisk = path.join(distDir, filePath)
  if (existsSync(onDisk) && statSync(onDisk).isFile()) {
    return { via: 'filesystem', target: filePath }
  }

  for (const rewrite of rewrites) {
    if (sourceToRegex(rewrite.source).test(urlPath)) {
      return { via: 'rewrite', target: rewrite.destination.replace(/^\//, '') }
    }
  }

  return { via: 'none', target: null }
}

// A dedicated Vercel function (`api/analyze.py`, `api/cron/ingest.py`) is itself a filesystem
// match — Vercel builds one from every `api/**/*.py` file and resolves a request against it
// before `vercel.json`'s own `rewrites` ever run, the same "filesystem first" ordering `resolve`
// above reproduces for the static build output. `distDir` is the wrong tree to check this
// against: these files live under `api/` at the repository root, never in the built SPA bundle,
// so this is a second, dedicated resolver rather than a second branch bolted onto `resolve`.
function resolveApiFunction(urlPath, rewrites) {
  const relativePyPath = `${urlPath.replace(/^\/api\//, '')}.py`
  const onDisk = path.join(apiDir, relativePyPath)
  if (existsSync(onDisk) && statSync(onDisk).isFile()) {
    return { via: 'filesystem', target: path.join('api', relativePyPath) }
  }

  for (const rewrite of rewrites) {
    if (sourceToRegex(rewrite.source).test(urlPath)) {
      return { via: 'rewrite', target: rewrite.destination.replace(/^\//, '') }
    }
  }

  return { via: 'none', target: null }
}

function main() {
  if (!existsSync(distDir)) {
    log(`no build found at ${path.relative(rootDir, distDir)} — run \`pnpm --filter web build\` first.`)
    process.exit(1)
  }

  const vercelConfig = JSON.parse(readFileSync(vercelJsonPath, 'utf8'))
  const rewrites = vercelConfig.rewrites ?? []

  const routeFiles = findRouteFiles(routesDir)
  if (routeFiles.length === 0) {
    log(`no route files found under ${path.relative(rootDir, routesDir)} — nothing to check.`)
    process.exit(1)
  }
  const routes = routeFiles.map(routeFileToUrl)

  const failures = []

  for (const route of routes) {
    const result = resolve(route, rewrites)
    if (result.target !== 'index.html') {
      failures.push(
        `${route} resolved via ${result.via} to ${result.target ?? '(nothing)'}, not index.html — ` +
          'a direct request to this route would hit the platform 404 before the client-side router runs.',
      )
    }
  }

  const apiResult = resolve('/api/me', rewrites)
  if (apiResult.target === 'index.html') {
    failures.push(
      '/api/me resolved to index.html instead of the API function — the catch-all rewrite is ' +
        'shadowing /api/(.*), most likely because it sits above it in vercel.json\'s `rewrites` list.',
    )
  } else if (apiResult.via !== 'rewrite') {
    failures.push(`/api/me resolved via ${apiResult.via} instead of the /api/(.*) rewrite.`)
  }

  // T366: `api/analyze.py` must resolve by the filesystem before `/api/(.*)` — the same ordering
  // `api/cron/ingest.py` already relies on — so `POST /api/analyze` reaches its own 300 s
  // `maxDuration`, not `api/index.py`'s 10 s one (this module's own docstring, R6).
  const apiFunctionCases = [
    ['/api/analyze', path.join('api', 'analyze.py')],
    ['/api/cron/ingest', path.join('api', 'cron', 'ingest.py')],
  ]
  for (const [urlPath, expectedFile] of apiFunctionCases) {
    const result = resolveApiFunction(urlPath, rewrites)
    if (result.via !== 'filesystem' || result.target !== expectedFile) {
      failures.push(
        `${urlPath} resolved via ${result.via} to ${result.target ?? '(nothing)'} instead of the ` +
          `filesystem match at ${expectedFile} — its own dedicated Vercel function would be ` +
          `shadowed by the /api/(.*) rewrite, most likely because the file is missing or was ` +
          `moved.`,
      )
    }
  }

  if (!existsSync(assetsDir)) {
    log(`no built assets found in ${path.relative(rootDir, assetsDir)} — run \`pnpm --filter web build\` first.`)
    process.exit(1)
  }
  const sampleAsset = readdirSync(assetsDir)[0]
  if (!sampleAsset) {
    log(`${path.relative(rootDir, assetsDir)} is empty — run \`pnpm --filter web build\` first.`)
    process.exit(1)
  }
  const assetResult = resolve(`/assets/${sampleAsset}`, rewrites)
  if (assetResult.via !== 'filesystem') {
    failures.push(
      `/assets/${sampleAsset} resolved via ${assetResult.via} instead of the filesystem — a real ` +
        'built asset must be served from disk, never through the catch-all rewrite.',
    )
  }

  if (failures.length > 0) {
    log(`${failures.length} routing failure(s):`)
    for (const failure of failures) log(`  - ${failure}`)
    process.exit(1)
  }

  log(
    `${routes.length} route(s) reach the shell, /api/me reaches the function, ` +
      `${apiFunctionCases.length} dedicated function(s) resolve by the filesystem before the ` +
      `rewrite, and /assets/${sampleAsset} is served from disk.`,
  )
}

main()
