#!/usr/bin/env node
// T584: closes row 3 (L1) of packages/design-system/specs/README.md's "Contrast-signal and
// duplicate-baseline gap register" — a story's own responsive-viewport pin or its own state/variant
// class can make its baseline byte-identical to another story's, independent of whether the two
// document the same fact (the sixth-pass review's L1 finding, the same benign mechanism the
// `Menu`/`Selection`/`SheetBelowMd` pair already is, T569's own prose comment). This check compares
// every story's captured six-baseline set ({light, dark} x {375, 768, 1280}) against every other
// story's, by content hash, and requires a **full** match (all six) to be accounted for one of two
// ways:
//
//   1. A `// visual-equivalence: <story-id>: <one-line reason>` comment, machine-parseable, attached
//      to a story export the same way every other doc comment in this codebase is — directly above
//      the `export const <Name>: Story = { ... }` line it explains, no blank line between. One line
//      names one other member of the group; an N-member group needs at least N-1 such lines, spread
//      across any of the group's own files (`Cross-file groups ... are allowed`, T584's own text —
//      `CaptureStateBadge` naming `Badge`, for instance). Read as an *undirected* graph: a group is
//      documented once its members form a single connected component under valid marker edges,
//      regardless of which member's file carries which line.
//   2. A dated debt entry in `scripts/visual/story-baseline-duplicates-debt.json` (the shape
//      `scripts/visual/a11y-allowlist.json` already uses, checked by `scripts/checks/a11y-
//      allowlist.mjs`) naming the group's exact story-id set, a `fixOwed` sentence and a `fixBy`
//      date — for a SUSPECT group: one whose name or comment promises a visible difference the
//      render does not show, a real gap rather than a benign equivalence. This never launders a
//      defect as deliberate (T584's own instruction): documenting a match here is a claim that
//      *something* is being tracked, either "this is fine, and here is why" (a marker) or "this is
//      not fine yet, and here is the owed fix and its deadline" (a debt entry) — never silence.
//
// **A partial match (1-5 of the six) is reported, never failed.** Responsive collapse routinely
// makes two stories agree at one width and diverge at another — that is what the breakpoint axis is
// for, not a defect. Only a full six-of-six match, which no width or theme distinguishes, needs an
// account of why.
//
// What fails, precisely:
//   - a full-set match with no marker connecting all its members and no debt entry naming its exact
//     set ("undocumented full match");
//   - a marker naming a story pair that is not (or no longer) a full-set match ("stale marker" — the
//     T578 lesson: a classification that drifts from the source it once matched is a lie a fixed
//     story or a fixed defect leaves behind if nobody removes the entry);
//   - a marker with an empty or missing reason;
//   - a debt entry whose story-id set is not currently a full-set match, or is missing a required
//     field, or has passed its `fixBy` (the same three checks `a11y-allowlist.mjs` runs, applied to
//     this file instead);
//   - zero stories found at all, however that happens (a moved `__screenshots__` directory, a
//     `packages/design-system/src` typo) — this check must not pass vacuously, so an empty result is
//     a failure, not a silent zero.
//   - a baseline file whose derived story id names no story this check's own source scan found (an
//     "unmapped baseline") — a moved or renamed component whose old baselines were never cleaned up.
//
// Story-id derivation needs no Storybook build (`story-baselines.mjs`'s own check does, which is why
// this lives beside it rather than inside its build-dependent job): every `*.stories.tsx` file
// either carries an explicit `id: '...'` on its `meta` object, or — the seven `.storybook/
// foundations/*.stories.tsx` docs pages, which carry no `id` — derives one from `title` the same way
// Storybook's own `toId` does (each `/`-separated segment lower-cased, non-alphanumeric runs folded
// to a single `-`, joined by `-`). The id's second half is the export name, camel-split and
// lower-cased the way Storybook's own `storyNameFromExport` (`lodash.startCase`-derived) splits a
// letter-case boundary AND a letter-digit boundary as two different words — `SizeXs` -> `size-xs`,
// but `NoAoe2Profile` -> `no-aoe-2-profile`, `2` its own word, not fused to `Aoe`. `deriveMetaId`
// and `kebabFromExportName` below are proven against the entire real tree (540 stories, zero
// unmapped ids either direction) by this file's own `node --test` suite, not merely a handful of
// examples — see 'derives every real story id with none unmapped either direction'.
//
// Usage:  node scripts/checks/story-baselines-duplicates.mjs
// Exit:   0 if every full-set baseline match is documented (marker or unexpired debt entry), every
//         marker and debt entry stays true of the current tree, and at least one story was found —
//         1 otherwise, naming the exact defect.
import { createHash } from 'node:crypto'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { BASELINE_NAME_RE, loadAppRouteBaselineNames } from './story-baselines.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
const defaultSrcDirs = [
  path.join(designSystemDir, 'src'),
  path.join(designSystemDir, '.storybook', 'foundations'),
]
const defaultScreenshotsDir = path.join(designSystemDir, '__screenshots__')
const defaultAppRoutesSpecPath = path.join(rootDir, 'tests', 'visual', 'app-routes.spec.ts')
const defaultDebtJsonPath = path.join(
  rootDir,
  'scripts',
  'visual',
  'story-baseline-duplicates-debt.json',
)

const THEMES = ['light', 'dark']
const WIDTHS = [375, 768, 1280]
const REQUIRED_DEBT_FIELDS = ['storyIds', 'found', 'fixOwed', 'fixBy']
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const MARKER_RE = /^\s*\/\/\s*visual-equivalence:\s*([a-z0-9][a-z0-9-]*)\s*:\s*(.*)$/

// ---------------------------------------------------------------------------------------------
// Story-id derivation (no Storybook build — see this file's own header).
// ---------------------------------------------------------------------------------------------

// Splits a PascalCase/camelCase export name into words the way Storybook's `storyNameFromExport`
// (lodash `startCase`) does: a run of uppercase letters immediately followed by an uppercase-then-
// lowercase pair splits before the last uppercase letter (`SheetBelowMd` -> `Sheet`, `Below`, `Md`);
// a digit run is always its own word, fused to neither its letter neighbour (`NoAoe2Profile` ->
// `No`, `Aoe`, `2`, `Profile`). Proven against the real tree by this file's own test suite.
export function kebabFromExportName(name) {
  const words = name.match(/[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+/g) || [name]
  return words.join('-').toLowerCase()
}

// One `title`/`id` path segment, folded the way Storybook's `toId`/`sanitize` folds it: lower-cased,
// every run of non-alphanumeric characters collapsed to one `-`, no leading or trailing `-`.
export function sanitizeTitleSegment(segment) {
  return segment
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

// The `meta`'s own id: the explicit `id: '...'` field when the story file carries one, otherwise
// derived from `title: '...'` the way Storybook derives it for a file with no explicit id (the
// seven `.storybook/foundations/*.stories.tsx` docs pages, today) — each `/`-separated segment
// sanitised and joined by `-`. `source` should be the whole file; only the text before the first
// `export default meta` is searched, so a later, unrelated `id:`/`title:` elsewhere in the file (a
// prop named either, in a story's own `args`) can never be mistaken for the meta's.
export function deriveMetaId(source) {
  const beforeDefault = source.split('export default meta')[0]
  const idMatch = beforeDefault.match(/id:\s*'([^']+)'/)
  if (idMatch) return idMatch[1]
  const titleMatch = beforeDefault.match(/title:\s*'([^']+)'/)
  if (!titleMatch) return null
  return titleMatch[1].split('/').map(sanitizeTitleSegment).join('-')
}

// Every `export const <Name>: ...` at the start of a line, with its 0-based line index — every
// export in every `*.stories.tsx` file in this tree is a `Story` (proven by grep across the whole
// tree, this file's own header), so no further type check narrows this.
export function findExportedStoryLines(lines) {
  const results = []
  const re = /^export const ([A-Za-z][A-Za-z0-9]*)\s*:/
  lines.forEach((line, index) => {
    const match = line.match(re)
    if (match) results.push({ exportName: match[1], lineIndex: index })
  })
  return results
}

// The contiguous `//` comment block directly above `lineIndex`, in source order — stops at the
// first line that is blank or not a `//` comment, the same "directly above, no gap" convention
// every other doc comment in this codebase already follows (confirmed by reading every story file
// this task's own classification cites). Returns an empty array when the export has no such block.
export function commentBlockAbove(lines, lineIndex) {
  const block = []
  let i = lineIndex - 1
  while (i >= 0 && /^\s*\/\//.test(lines[i])) {
    block.unshift(lines[i])
    i -= 1
  }
  return block
}

// Parses every `// visual-equivalence: <story-id>: <reason>` line out of a comment block. A line
// matching the marker prefix with a blank reason (after trimming) is still returned, with
// `reason: ''` — evaluateMarkers is what turns that into a finding, so a malformed marker is
// reported with the same machinery a stale one is, not swallowed here.
export function parseMarkersInBlock(block) {
  const markers = []
  for (const line of block) {
    const match = line.match(MARKER_RE)
    if (match) markers.push({ targetId: match[1], reason: match[2].trim() })
  }
  return markers
}

// One story file, fully parsed: its meta id, every story export's derived id, and every
// `visual-equivalence` marker attached to one of those exports (sourceId -> targetId + reason).
// Pure — takes the file's already-read source, not a path, so story-baselines-duplicates.test.mjs
// can prove it against a small fixture string.
export function parseStoryFile(source) {
  const metaId = deriveMetaId(source)
  const lines = source.split('\n')
  const exportLines = findExportedStoryLines(lines)
  const stories = []
  const markers = []
  for (const { exportName, lineIndex } of exportLines) {
    const id = metaId ? `${metaId}--${kebabFromExportName(exportName)}` : null
    stories.push({ exportName, id })
    if (!id) continue
    const block = commentBlockAbove(lines, lineIndex)
    for (const { targetId, reason } of parseMarkersInBlock(block)) {
      markers.push({ sourceId: id, targetId, reason })
    }
  }
  return { metaId, stories, markers }
}

// Every `*.stories.tsx` file under any of `srcDirs`, recursively.
export function findStoryFiles(srcDirs) {
  const out = []
  function walk(dir) {
    let entries
    try {
      entries = readdirSync(dir, { withFileTypes: true })
    } catch {
      return
    }
    for (const entry of entries) {
      const entryPath = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(entryPath)
      else if (entry.name.endsWith('.stories.tsx')) out.push(entryPath)
    }
  }
  for (const dir of srcDirs) walk(dir)
  return out.sort()
}

// Reads and parses every story file, aggregating one index for the whole tree. `findings` here
// covers what is decidable from source alone: a file with no derivable meta id (no `id` and no
// `title`), and two exports that collide on the same derived story id (never observed in the real
// tree, guarded against rather than assumed).
export function collectStoryIndex(storyFilePaths, readFile = (p) => readFileSync(p, 'utf8')) {
  const storyIds = new Set()
  const fileByStoryId = new Map()
  const markers = []
  const findings = []

  for (const filePath of storyFilePaths) {
    const relPath = path.relative(rootDir, filePath)
    const source = readFile(filePath)
    const { metaId, stories, markers: fileMarkers } = parseStoryFile(source)
    if (!metaId) {
      findings.push(`${relPath}: no \`id:\` and no derivable \`title:\` on its \`meta\` object.`)
      continue
    }
    for (const { exportName, id } of stories) {
      if (storyIds.has(id)) {
        findings.push(
          `${relPath}: \`${exportName}\` derives story id \`${id}\`, already produced by ` +
            `${path.relative(rootDir, fileByStoryId.get(id))} — two exports collide on one id.`,
        )
        continue
      }
      storyIds.add(id)
      fileByStoryId.set(id, filePath)
    }
    for (const marker of fileMarkers) markers.push({ ...marker, filePath })
  }

  return { storyIds, fileByStoryId, markers, findings }
}

// ---------------------------------------------------------------------------------------------
// Baseline hashing.
// ---------------------------------------------------------------------------------------------

export function md5OfFile(filePath) {
  return createHash('md5').update(readFileSync(filePath)).digest('hex')
}

// The six {theme, width} hashes for one story, in a fixed order, or `null` for any unit whose file
// is missing — a story short of all six is `story-baselines.mjs`'s concern (completeness), not this
// check's; it simply never enters the duplicate comparison below.
export function storyUnitHashes(storyId, screenshotsDir, hashFile = md5OfFile) {
  const hashes = []
  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      const filePath = path.join(screenshotsDir, `${storyId}-${theme}-${width}.png`)
      if (!existsSync(filePath)) return null
      hashes.push(hashFile(filePath))
    }
  }
  return hashes
}

// Every baseline PNG in `screenshotsDir` that is not an app-route capture (`exemptBaselineNames`,
// `story-baselines.mjs`'s own `loadAppRouteBaselineNames`) and whose derived story id is in
// `knownStoryIds` — paired with the list of baselines that are neither (the "unmapped baseline"
// failure).
export function mapBaselinesToStories(baselineFiles, knownStoryIds, exemptBaselineNames) {
  const storyIdsWithBaselines = new Set()
  const unmapped = []
  for (const file of baselineFiles) {
    if (exemptBaselineNames.has(file.slice(0, -'.png'.length))) continue
    const match = file.match(BASELINE_NAME_RE)
    if (match && knownStoryIds.has(match[1])) {
      storyIdsWithBaselines.add(match[1])
    } else {
      unmapped.push(file)
    }
  }
  return { storyIdsWithBaselines, unmapped: unmapped.sort() }
}

// One hash-key per story (its six unit hashes, joined) for every story that has all six baselines.
// Two stories share a key if and only if their six captures are byte-identical, in both themes and
// at every width.
export function computeHashKeys(storyIds, screenshotsDir, hashFile = md5OfFile) {
  const hashKeyByStoryId = new Map()
  for (const id of [...storyIds].sort()) {
    const hashes = storyUnitHashes(id, screenshotsDir, hashFile)
    if (hashes) hashKeyByStoryId.set(id, hashes.join(':'))
  }
  return hashKeyByStoryId
}

// Groups of two or more story ids sharing one hash key (all six baselines byte-identical), sorted
// for determinism. Only stories `computeHashKeys` found a complete set for are ever grouped.
export function findFullMatchGroups(hashKeyByStoryId) {
  const byKey = new Map()
  for (const [id, key] of hashKeyByStoryId) {
    if (!byKey.has(key)) byKey.set(key, [])
    byKey.get(key).push(id)
  }
  return [...byKey.values()]
    .filter((group) => group.length > 1)
    .map((group) => group.sort())
    .sort((a, b) => a[0].localeCompare(b[0]))
}

// Every pair of stories that share between one and five of their six units (never zero — nothing to
// report — and never six, which is a full match above) — reported, never failed (see this file's
// header): a partial match at one width is what responsive collapse ordinarily produces.
export function findPartialMatches(hashKeyByStoryId) {
  const ids = [...hashKeyByStoryId.keys()].sort()
  const unitsById = new Map(ids.map((id) => [id, hashKeyByStoryId.get(id).split(':')]))
  const partials = []
  for (let i = 0; i < ids.length; i += 1) {
    for (let j = i + 1; j < ids.length; j += 1) {
      const a = ids[i]
      const b = ids[j]
      const unitsA = unitsById.get(a)
      const unitsB = unitsById.get(b)
      let matches = 0
      for (let u = 0; u < unitsA.length; u += 1) {
        if (unitsA[u] === unitsB[u]) matches += 1
      }
      if (matches >= 1 && matches <= 5) partials.push({ a, b, matches, of: unitsA.length })
    }
  }
  return partials.sort((x, y) => y.matches - x.matches || x.a.localeCompare(y.a))
}

// ---------------------------------------------------------------------------------------------
// Marker validation (union-find over `visual-equivalence` edges).
// ---------------------------------------------------------------------------------------------

function createUnionFind(ids) {
  const parent = new Map(ids.map((id) => [id, id]))
  function find(x) {
    while (parent.get(x) !== x) x = parent.get(x)
    return x
  }
  function union(a, b) {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent.set(ra, rb)
  }
  return { find, union }
}

// Splits every parsed marker into the valid ones (both endpoints currently share a hash key — a
// real, current full-set match) and the findings a bad one produces: an empty reason, a target id
// this tree has no story for, or a pair that is not (or no longer) a full-set match ("stale").
export function evaluateMarkers({ markers, hashKeyByStoryId, knownStoryIds }) {
  const findings = []
  const validEdges = []
  for (const { sourceId, targetId, reason, filePath } of markers) {
    const relPath = path.relative(rootDir, filePath)
    const label = `${relPath}: \`// visual-equivalence: ${targetId}: ...\` on \`${sourceId}\``
    if (!reason) {
      findings.push(`${label} carries no reason.`)
      continue
    }
    if (!knownStoryIds.has(targetId)) {
      findings.push(`${label} names \`${targetId}\`, which is not a story this tree derives.`)
      continue
    }
    const sourceKey = hashKeyByStoryId.get(sourceId)
    const targetKey = hashKeyByStoryId.get(targetId)
    if (!sourceKey || !targetKey || sourceKey !== targetKey) {
      findings.push(
        `${label} — stale: \`${sourceId}\` and \`${targetId}\` are not currently a full-set ` +
          '(all six baselines) match. Either the marker is wrong, or a fix landed and it must be removed.',
      )
      continue
    }
    validEdges.push([sourceId, targetId])
  }
  return { validEdges, findings }
}

// For every full-match group: documented if a debt entry names its exact story-id set (a tracked
// SUSPECT, not laundered as deliberate), or if valid marker edges connect every member into one
// component. Otherwise, an "undocumented full match" finding.
export function evaluateFullMatchDocumentation({ fullMatchGroups, validEdges, debtEntries }) {
  const findings = []
  const debtSets = debtEntries.map((entry) => new Set(entry.storyIds))

  const allIds = [...new Set(fullMatchGroups.flat())]
  const uf = createUnionFind(allIds)
  for (const [a, b] of validEdges) {
    if (allIds.includes(a) && allIds.includes(b)) uf.union(a, b)
  }

  for (const group of fullMatchGroups) {
    const coveredByDebt = debtSets.some(
      (debtSet) => debtSet.size === group.length && group.every((id) => debtSet.has(id)),
    )
    if (coveredByDebt) continue

    const roots = new Set(group.map((id) => uf.find(id)))
    if (roots.size === 1) continue

    findings.push(
      `undocumented full-set match: ${group.join(' = ')} — every one of the six baselines is ` +
        'byte-identical across all of these stories, but no `visual-equivalence` marker connects ' +
        'all of them and no debt entry in ' +
        `${path.relative(rootDir, defaultDebtJsonPath)} names this exact set. Add a marker (if this ` +
        'is deliberate — cite the mechanism or the spec) or a debt entry (if it is a real gap).',
    )
  }

  return findings
}

// ---------------------------------------------------------------------------------------------
// Debt entries (scripts/visual/story-baseline-duplicates-debt.json).
// ---------------------------------------------------------------------------------------------

function isValidIsoDate(value) {
  if (typeof value !== 'string' || !ISO_DATE_RE.test(value)) return false
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return false
  return parsed.toISOString().slice(0, 10) === value
}

// Parses and validates the debt JSON: a bare array, each entry carrying `storyIds` (an array of at
// least two story ids), `found`, `fixOwed` and `fixBy` — modelled on `scripts/visual/a11y-
// allowlist.json`'s own shape and `scripts/checks/a11y-allowlist.mjs`'s own field/date checks,
// applied to a story-id set instead of a `component`/`rule` pair. `today` is injected (not read from
// `Date.now()` directly) so story-baselines-duplicates.test.mjs can prove the fixBy check against a
// fixed clock.
export function evaluateDebtEntries(raw, today) {
  const findings = []
  if (raw === undefined) return { entries: [], findings }
  if (!Array.isArray(raw)) {
    return {
      entries: [],
      findings: [
        `${path.relative(rootDir, defaultDebtJsonPath)} must be a bare JSON array, found ${typeof raw}.`,
      ],
    }
  }

  const entries = []
  raw.forEach((entry, index) => {
    const label = Array.isArray(entry?.storyIds) ? entry.storyIds.join(' = ') : `entry ${index}`
    const missing = REQUIRED_DEBT_FIELDS.filter((field) => {
      const value = entry?.[field]
      if (field === 'storyIds') return !Array.isArray(value) || value.length < 2
      return typeof value !== 'string' || value.trim() === ''
    })
    if (!missing.includes('fixBy') && entry?.fixBy !== undefined && !isValidIsoDate(entry.fixBy)) {
      missing.push('fixBy (not a valid ISO date)')
    }
    if (!missing.includes('found') && entry?.found !== undefined && !isValidIsoDate(entry.found)) {
      missing.push('found (not a valid ISO date)')
    }
    if (missing.length > 0) {
      findings.push(`debt entry (${label}): missing/invalid ${missing.join(', ')}.`)
      return
    }
    entries.push(entry)
  })

  const expired = entries.filter((entry) => entry.fixBy < today)
  for (const entry of expired) {
    const overdueDays = Math.round(
      (new Date(today).getTime() - new Date(entry.fixBy).getTime()) / (24 * 60 * 60 * 1000),
    )
    findings.push(
      `debt entry (${entry.storyIds.join(' = ')}): fixBy ${entry.fixBy} is ${overdueDays} ` +
        `day${overdueDays === 1 ? '' : 's'} overdue.`,
    )
  }

  return { entries, findings }
}

// A debt entry whose exact story-id set is not currently a full-set match — the SUSPECT was fixed
// (good) but the entry was not removed (T578's stale-classification lesson, applied to a debt entry
// instead of a marker).
export function findStaleDebtEntries(entries, fullMatchGroups) {
  const findings = []
  const groupKeys = new Set(fullMatchGroups.map((group) => group.join(' ')))
  for (const entry of entries) {
    const key = [...entry.storyIds].sort().join(' ')
    if (!groupKeys.has(key)) {
      findings.push(
        `debt entry (${entry.storyIds.join(' = ')}) is not a current full-set match — either the ` +
          'fix landed and the entry must be removed, or the story-id set is wrong.',
      )
    }
  }
  return findings
}

// ---------------------------------------------------------------------------------------------
// Orchestration.
// ---------------------------------------------------------------------------------------------

function log(message) {
  console.log(`story-baselines-duplicates: ${message}`)
}

function fail(message) {
  console.error(`story-baselines-duplicates: ${message}`)
}

export function runCheck({
  srcDirs = defaultSrcDirs,
  screenshotsDir = defaultScreenshotsDir,
  appRoutesSpecPath = defaultAppRoutesSpecPath,
  debtJsonPath = defaultDebtJsonPath,
  today = new Date().toISOString().slice(0, 10),
} = {}) {
  const findings = []
  const infoLines = []

  const storyFilePaths = findStoryFiles(srcDirs)
  const { storyIds, markers, findings: indexFindings } = collectStoryIndex(storyFilePaths)
  findings.push(...indexFindings)

  if (storyIds.size === 0) {
    findings.push(
      `zero stories found under ${srcDirs.map((d) => path.relative(rootDir, d)).join(', ')} — a ` +
        'moved or empty source directory cannot pass vacuously.',
    )
    return { findings, infoLines, exitCode: 1 }
  }

  const exemptBaselineNames = existsSync(appRoutesSpecPath)
    ? loadAppRouteBaselineNames(readFileSync(appRoutesSpecPath, 'utf8'))
    : new Set()

  if (!existsSync(screenshotsDir)) {
    findings.push(`no baseline directory found at ${path.relative(rootDir, screenshotsDir)}.`)
    return { findings, infoLines, exitCode: 1 }
  }
  const baselineFiles = readdirSync(screenshotsDir).filter((f) => f.endsWith('.png'))
  const { storyIdsWithBaselines, unmapped } = mapBaselinesToStories(
    baselineFiles,
    storyIds,
    exemptBaselineNames,
  )
  for (const file of unmapped) {
    findings.push(`unmapped baseline: ${file} names no story this tree derives.`)
  }

  const hashKeyByStoryId = computeHashKeys(storyIdsWithBaselines, screenshotsDir)
  const fullMatchGroups = findFullMatchGroups(hashKeyByStoryId)
  const partialMatches = findPartialMatches(hashKeyByStoryId)

  const { validEdges, findings: markerFindings } = evaluateMarkers({
    markers,
    hashKeyByStoryId,
    knownStoryIds: storyIds,
  })
  findings.push(...markerFindings)

  let debtRaw
  if (existsSync(debtJsonPath)) {
    try {
      debtRaw = JSON.parse(readFileSync(debtJsonPath, 'utf8'))
    } catch (error) {
      findings.push(`${path.relative(rootDir, debtJsonPath)} is not valid JSON: ${error.message}`)
      debtRaw = []
    }
  } else {
    debtRaw = []
  }
  const { entries: debtEntries, findings: debtFindings } = evaluateDebtEntries(debtRaw, today)
  findings.push(...debtFindings)
  findings.push(...findStaleDebtEntries(debtEntries, fullMatchGroups))

  findings.push(...evaluateFullMatchDocumentation({ fullMatchGroups, validEdges, debtEntries }))

  infoLines.push(
    `${storyIdsWithBaselines.size} stories with a complete baseline set, ` +
      `${fullMatchGroups.length} full-set duplicate group(s), ${partialMatches.length} partial ` +
      'match(es) (reported only, never failed):',
  )
  for (const group of fullMatchGroups) infoLines.push(`  full match: ${group.join(' = ')}`)
  for (const { a, b, matches, of } of partialMatches) {
    infoLines.push(`  partial match (${matches}/${of}): ${a} ~ ${b}`)
  }

  return { findings, infoLines, exitCode: findings.length > 0 ? 1 : 0 }
}

function main() {
  const { findings, infoLines, exitCode } = runCheck()
  for (const line of infoLines) log(line)
  if (findings.length > 0) {
    for (const finding of findings) fail(finding)
    fail(`${findings.length} finding${findings.length === 1 ? '' : 's'}.`)
  } else {
    log('every full-set baseline match is documented (marker or unexpired debt entry).')
  }
  process.exitCode = exitCode
}

// Only run when invoked directly — story-baselines-duplicates.test.mjs imports the functions above
// without triggering the scan or the process exit code, the same guard token-scale.mjs and
// story-docs.mjs use.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
