#!/usr/bin/env node
// T578: closes rows 3 and 4 of packages/design-system/specs/README.md's "Storybook documentation
// gap register" mechanically, so the closure is asserted by a test rather than by re-reading the
// register — CLAUDE.md's rule for a living fact. Three things this check reads straight from
// source rather than trusting the register's prose to stay true:
//
//   1. Every component's *.stories.tsx meta must carry a non-empty one-sentence purpose line in
//      `parameters.docs.description.component` (row 3). Every component directory under
//      packages/design-system/src/{primitives,composites,screens}/ must have a story file at all —
//      a component with no story file has nothing for this check, `spec-completeness.mjs` or
//      `story-baselines.mjs` to find, so it is checked here too rather than assumed.
//   2. Every component named in SR_ONLY_NAMING_SHAPE_COMPONENTS's own purpose line must carry an
//      actual markdown link to Foundations → Iconography's docs page (row 4) — not merely the word
//      "Iconography": a reader in Storybook with no repository access (quickstart.md scenario 9's
//      own premise) can only follow a link, not recognise an unlinked mention.
//   3. Every component directory whose own (non-story, non-test) source contains the literal text
//      `sr-only` must be classified in exactly one of two hand-maintained maps below —
//      SR_ONLY_NAMING_SHAPE_COMPONENTS (a redundant accessible name, owing the Iconography link
//      above) or SR_ONLY_SOLE_NAME_COMPONENTS (the *sole* source of a name, owing nothing more than
//      its own one-line reason) — and every entry in either map must still be true of the source:
//      a component that stops using `sr-only` and stays listed is the same stale-classification lie
//      in the other direction. This is what stops a fifth `sr-only` component from shipping
//      unclassified: the two maps used to be trusted by hand-audit alone (T578's own remediation,
//      found by review — the check enforced row 4's *wording* for four known names but never
//      re-derived the list itself from source).
//
// Both maps are hand-maintained, not derived — which components carry a redundant accessible name
// versus the sole one is a judgement call, the same shape spec-completeness.mjs's EXEMPT_SPEC_FILES
// already makes for its one hand-maintained exemption. What IS mechanical is that every `sr-only`
// occurrence in the tree is accounted for by one map or the other, and every map entry is still
// true — the judgement is recorded, not merely asserted.
//
// evaluateStoryDocs itself is pure — no filesystem access — the same shape
// spec-completeness.mjs's evaluateSpecsDirectory uses, so story-docs.test.mjs can prove every rule
// against a small fixture without touching the real (and constantly changing) src tree.
//
// Usage:  node scripts/checks/story-docs.mjs
// Exit:   0 if every component directory has a story file, every story file's meta carries a
//         non-empty purpose line, every SR_ONLY_NAMING_SHAPE_COMPONENTS entry's line carries a real
//         Foundations → Iconography link, and every `sr-only` occurrence in source is classified in
//         exactly one of the two maps and still true — 1 otherwise, naming the file and the defect.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const srcDir = path.join(rootDir, 'packages', 'design-system', 'src')

// The docs-entry id `.storybook/foundations/Iconography.stories.tsx` builds to (`title:
// 'Foundations/Iconography'`, no explicit story-level `id`, Storybook's own default docs suffix) —
// confirmed by building Storybook and reading storybook-static/index.json. A purpose line must link
// here, not merely say the word "Iconography".
export const ICONOGRAPHY_DOCS_TARGET = 'foundations-iconography--docs'

// Components whose OWN (non-story, non-test) source directly contains `sr-only` text that
// restates, for assistive technology, a fact already painted a second way (a colour, a decorative
// icon, a mouse-only tooltip) — a redundant accessible name. Each owes a purpose-line sentence
// naming the shape and linking Foundations → Iconography.
//
// `CountryFlag` is deliberately not here even though its purpose line correctly documents the same
// shape (`Tooltip`'s `relation="label"` third naming shape): its own `index.tsx` contains no
// literal `sr-only` text — the `sr-only` span that ends up in its rendered output is `Tooltip`'s
// (below), not its own. This check scans one directory at a time, not a composed render tree, so
// `CountryFlag` is the file whose accessible name depends on another component's `sr-only` text
// without owning any itself — real, but a different shape than this map classifies. Its purpose
// line keeps the link for a human reader; it is simply not enforced by this map, because enforcing
// it here would require tracing composition rather than reading one directory (found while fixing
// T578's own remediation: the previous version of this map listed `CountryFlag` and not `Tooltip`,
// which the source-scan below proved backwards).
export const SR_ONLY_NAMING_SHAPE_COMPONENTS = new Map([
  ['PlayerColourSwatch', 'a sr-only text alternative for the colour-only signal it paints'],
  ['Link', 'a sr-only span folded into the anchor’s own accessible name, beside a decorative icon'],
  ['MatchRow', 'a sr-only absolute date backing up a mouse-only `title` tooltip'],
])

// Components whose OWN `sr-only` text is the *sole* source of a name or an announcement — nothing
// else repeats the fact, so there is no redundancy and no Iconography shape to link. Each still
// owes a one-line reason, so an unclassified `sr-only` occurrence can never silently default here
// either.
export const SR_ONLY_SOLE_NAME_COMPONENTS = new Map([
  ['Field', 'the sole accessible name for its own, optionally visually hidden, <label>'],
  ['Page', 'the sole accessible name for its own, optionally visually hidden, <h1>'],
  ['Section', 'the sole accessible name for its own, optionally visually hidden, heading'],
  ['Table', 'the sole accessible name for its own, optionally visually hidden, caption'],
  ['SiteHeader', 'a skip-navigation link — a keyboard-only affordance, not a name'],
  ['Menu', 'an `aria-live` announcement region — a live update, not a name'],
  [
    'Tooltip',
    'provides (`relation="label"`, default) or supplements (`relation="describe"`) its ' +
      "trigger's accessible name via a sr-only `qualifier` prefix — the mechanism a consumer " +
      'such as `CountryFlag` builds its own naming shape on, not itself a restatement of a fact ' +
      'painted a second way',
  ],
])

const TIER_SEGMENTS = ['primitives', 'composites', 'screens']

function log(message) {
  console.log(`story-docs: ${message}`)
}

function fail(message) {
  console.error(`story-docs: ${message}`)
  process.exitCode = 1
}

// Every immediate component directory under src/{primitives,composites,screens}/, as
// `{ segment, name }` — the same shape spec-completeness.mjs's listComponentDirs already uses.
export function listComponentDirs(rootSrcDir) {
  const dirs = []
  for (const segment of TIER_SEGMENTS) {
    const segmentDir = path.join(rootSrcDir, segment)
    let entries
    try {
      entries = readdirSync(segmentDir)
    } catch {
      continue
    }
    for (const entry of entries) {
      if (statSync(path.join(segmentDir, entry)).isDirectory()) {
        dirs.push({ segment, name: entry })
      }
    }
  }
  return dirs.sort((a, b) => `${a.segment}/${a.name}`.localeCompare(`${b.segment}/${b.name}`))
}

// The component's own `*.stories.tsx` path, or null if the directory has none — a component with
// several files (none today) is not this check's concern; one story file per directory is the
// convention every existing component already follows.
export function findStoryFile(rootSrcDir, segment, name) {
  const dir = path.join(rootSrcDir, segment, name)
  let entries
  try {
    entries = readdirSync(dir)
  } catch {
    return null
  }
  const storyFile = entries.find((entry) => entry.endsWith('.stories.tsx'))
  return storyFile ? path.join(dir, storyFile) : null
}

// Every file in a component's directory that is neither its story file nor a test file — the
// component's own implementation source (`index.tsx`, and any sibling module such as
// `CaptureStateBadge`'s `countdown.ts`). This is what row 4's `sr-only` audit scans: a story file
// can quote `sr-only` in prose without the component itself using it, and a test file asserts it
// rather than declaring it.
export function findComponentSourceFiles(rootSrcDir, segment, name) {
  const dir = path.join(rootSrcDir, segment, name)
  let entries
  try {
    entries = readdirSync(dir)
  } catch {
    return []
  }
  return entries
    .filter((entry) => !entry.endsWith('.stories.tsx') && !/\.test\.tsx?$/.test(entry))
    .map((entry) => path.join(dir, entry))
}

// The `component:` value inside `parameters.docs.description.component: \`...\`` — a template
// literal, matched non-greedily up to its own closing backtick. Returns null when the whole
// `docs.description.component` shape is absent, and '' when it is present but empty (both are
// findings; the caller distinguishes them for a clearer message).
export function extractPurposeLine(storySource) {
  // `(?:\\`|[^`])*` rather than `[^`]*`: several purpose lines name a prop or a value in backticks
  // inside the template literal (`` `external` ``), which the source escapes as `` \` `` — a bare
  // `[^`]*` stops at the first of those, truncating the match long before the real closing backtick.
  const match = storySource.match(/docs:\s*\{\s*description:\s*\{\s*component:\s*`((?:\\`|[^`])*)`/)
  if (!match) return null
  // Collapse the source's own line-wrapping (Prettier wraps a long template literal's surrounding
  // object, never the string itself, but this stays robust either way), un-escape `\``, and trim.
  return match[1].replace(/\\`/g, '`').replace(/\s+/g, ' ').trim()
}

// True when `text` carries a real markdown link (`](...)`) whose target contains
// ICONOGRAPHY_DOCS_TARGET — never satisfied by the bare word "Iconography" appearing unlinked.
export function hasIconographyLink(text) {
  for (const match of text.matchAll(/\]\(([^)]*)\)/g)) {
    if (match[1].includes(ICONOGRAPHY_DOCS_TARGET)) return true
  }
  return false
}

// True when any of a component's own source files (findComponentSourceFiles's contents) contains
// the literal text `sr-only`.
export function containsSrOnly(sourceFileContents) {
  return sourceFileContents.some((content) => content.includes('sr-only'))
}

// Pure: takes `componentDirs` (`listComponentDirs`'s own shape) and three maps keyed off it —
// `storyPathByComponent` (`"<segment>/<name>"` -> absolute story path, or undefined when none
// exists), `storySourceByPath` (absolute story path -> file contents), and
// `sourceFilesByComponent` (`"<segment>/<name>"` -> array of that component's own non-story,
// non-test file contents) — and returns one finding string per problem. No filesystem access, so
// story-docs.test.mjs proves every rule on a fixture.
export function evaluateStoryDocs({
  componentDirs,
  storyPathByComponent,
  storySourceByPath,
  sourceFilesByComponent,
}) {
  const findings = []

  // A name may not be classified as both a redundant accessible name and a sole one — "exactly one
  // of two maps", checked before either loop below so a configuration mistake is its own finding
  // rather than being silently resolved by whichever loop runs first.
  for (const name of SR_ONLY_NAMING_SHAPE_COMPONENTS.keys()) {
    if (SR_ONLY_SOLE_NAME_COMPONENTS.has(name)) {
      findings.push(
        `\`${name}\` is listed in both SR_ONLY_NAMING_SHAPE_COMPONENTS and ` +
          'SR_ONLY_SOLE_NAME_COMPONENTS — a component is one or the other, never both.',
      )
    }
  }

  for (const { segment, name } of componentDirs) {
    const key = `${segment}/${name}`
    const storyPath = storyPathByComponent.get(key)
    const sourceFiles = sourceFilesByComponent.get(key) ?? []
    const hasSrOnly = containsSrOnly(sourceFiles)
    const inRedundantMap = SR_ONLY_NAMING_SHAPE_COMPONENTS.has(name)
    const inSoleNameMap = SR_ONLY_SOLE_NAME_COMPONENTS.has(name)

    if (hasSrOnly && !inRedundantMap && !inSoleNameMap) {
      findings.push(
        `packages/design-system/src/${key}/: source contains \`sr-only\` but \`${name}\` is not ` +
          'classified in SR_ONLY_NAMING_SHAPE_COMPONENTS or SR_ONLY_SOLE_NAME_COMPONENTS (row 4 of ' +
          'the register) — add it to whichever map matches (redundant accessible name vs. the sole ' +
          'source of one) with a one-line reason.',
      )
    }

    if (!storyPath) {
      findings.push(
        `packages/design-system/src/${key}/ has no *.stories.tsx file — nothing to carry a ` +
          'purpose line at all (FR-040, row 3).',
      )
      continue
    }
    const relStoryPath = path.relative(rootDir, storyPath)
    const source = storySourceByPath.get(storyPath)
    if (source === undefined) {
      findings.push(`${relStoryPath}: could not be read.`)
      continue
    }

    const purpose = extractPurposeLine(source)
    if (purpose === null) {
      findings.push(
        `${relStoryPath}: meta carries no \`parameters.docs.description.component\` purpose line ` +
          '(FR-040, row 3 of the Storybook documentation gap register).',
      )
      continue
    }
    if (purpose.length === 0) {
      findings.push(`${relStoryPath}: \`docs.description.component\` is present but empty.`)
      continue
    }

    if (inRedundantMap && !hasIconographyLink(purpose)) {
      findings.push(
        `${relStoryPath}: \`${name}\` carries a redundant accessible name (` +
          `${SR_ONLY_NAMING_SHAPE_COMPONENTS.get(name)}) but its purpose line carries no markdown ` +
          `link to Foundations → Iconography's docs page (\`${ICONOGRAPHY_DOCS_TARGET}\`) — the ` +
          'word "Iconography" alone is not enough; a reader with no repository access can only ' +
          'follow a link (row 4 of the register).',
      )
    }
  }

  // Stale classifications: a map entry whose component's source no longer contains `sr-only` at
  // all — the same lie in the other direction as an unclassified occurrence. Scoped to entries
  // whose component this run's own `componentDirs` actually covers: main() always passes every
  // real component, so a real map entry is always checked in production, but a fixture that
  // deliberately covers one or two directories (story-docs.test.mjs) must not be told a real map
  // entry it never mentioned "no longer exists" — a map entry naming a component absent from the
  // tree entirely is instead caught by story-docs.test.mjs's own directory-existence assertion.
  for (const [name] of [...SR_ONLY_NAMING_SHAPE_COMPONENTS, ...SR_ONLY_SOLE_NAME_COMPONENTS]) {
    const dir = componentDirs.find((d) => d.name === name)
    if (!dir) continue
    const sourceFiles = sourceFilesByComponent.get(`${dir.segment}/${dir.name}`) ?? []
    if (!containsSrOnly(sourceFiles)) {
      findings.push(
        `\`${name}\` is classified in the story-docs.mjs sr-only maps, but its source no longer ` +
          'contains `sr-only` — remove the entry (row 4 of the register).',
      )
    }
  }

  return findings
}

function main() {
  const componentDirs = listComponentDirs(srcDir)
  const storyPathByComponent = new Map()
  const storySourceByPath = new Map()
  const sourceFilesByComponent = new Map()
  for (const { segment, name } of componentDirs) {
    const key = `${segment}/${name}`
    const storyPath = findStoryFile(srcDir, segment, name)
    if (storyPath) {
      storyPathByComponent.set(key, storyPath)
      storySourceByPath.set(storyPath, readFileSync(storyPath, 'utf8'))
    }
    const sourceFiles = findComponentSourceFiles(srcDir, segment, name).map((filePath) =>
      readFileSync(filePath, 'utf8'),
    )
    sourceFilesByComponent.set(key, sourceFiles)
  }

  const findings = evaluateStoryDocs({
    componentDirs,
    storyPathByComponent,
    storySourceByPath,
    sourceFilesByComponent,
  })

  if (findings.length > 0) {
    for (const finding of findings) fail(finding)
    fail(
      `${findings.length} finding${findings.length === 1 ? '' : 's'} across ` +
        `${componentDirs.length} component directories.`,
    )
    return
  }

  log(
    `${componentDirs.length} component directories each have a story file carrying a purpose ` +
      `line; every \`sr-only\` occurrence in source is classified in exactly one of ` +
      `SR_ONLY_NAMING_SHAPE_COMPONENTS (${SR_ONLY_NAMING_SHAPE_COMPONENTS.size}) or ` +
      `SR_ONLY_SOLE_NAME_COMPONENTS (${SR_ONLY_SOLE_NAME_COMPONENTS.size}), and every redundant ` +
      'one links Foundations → Iconography.',
  )
}

// Only run when invoked directly — story-docs.test.mjs imports the functions above without
// triggering the scan or the process exit code, the same guard token-scale.mjs and
// spec-completeness.mjs use.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
