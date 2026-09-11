// Regression tests for T578's mechanical check (story-docs.mjs), including its own remediation
// (a reviewer found the Iconography-link check accepted an unlinked word, and found the
// sr-only/accessible-name classification was hand-audited once rather than re-derived from source
// on every run). Follows token-scale.test.mjs and spec-completeness.test.mjs's own `node --test`
// conventions: real functions, small fixtures, node:assert/strict — no mocking. `evaluateStoryDocs`
// is pure (no filesystem access), so every fixture below proves a rule without touching the live
// packages/design-system/src tree; the final test runs the real check against that real tree — live
// proof the register's four rows stay closed.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  extractPurposeLine,
  hasIconographyLink,
  containsSrOnly,
  evaluateStoryDocs,
  listComponentDirs,
  findStoryFile,
  findComponentSourceFiles,
  ICONOGRAPHY_DOCS_TARGET,
  SR_ONLY_NAMING_SHAPE_COMPONENTS,
  SR_ONLY_SOLE_NAME_COMPONENTS,
} from './story-docs.mjs'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(scriptDir, '..', '..')
const srcDir = path.join(rootDir, 'packages', 'design-system', 'src')

test('extractPurposeLine reads a plain, single-line template-literal purpose line', () => {
  const source = `
const meta = {
  component: Badge,
  parameters: { docs: { description: { component: \`Marks one item as being in a named state.\` } } },
}`
  assert.equal(extractPurposeLine(source), 'Marks one item as being in a named state.')
})

test('extractPurposeLine reads a Prettier-wrapped multi-line block', () => {
  const source = `
const meta = {
  component: Panel,
  parameters: {
    docs: {
      description: {
        component: \`Bounds a block of related content on its own surface.\`,
      },
    },
  },
}`
  assert.equal(extractPurposeLine(source), 'Bounds a block of related content on its own surface.')
})

test('extractPurposeLine un-escapes a backtick-fenced word inside the template literal', () => {
  const source =
    'parameters: { docs: { description: { component: `Uses the \\`external\\` prop.` } } }'
  assert.equal(extractPurposeLine(source), 'Uses the `external` prop.')
})

test('extractPurposeLine returns null when the docs.description.component shape is absent', () => {
  assert.equal(extractPurposeLine('const meta = { component: Badge }'), null)
})

test('extractPurposeLine returns an empty string when the shape is present but blank', () => {
  const source = 'parameters: { docs: { description: { component: `` } } }'
  assert.equal(extractPurposeLine(source), '')
})

// --- hasIconographyLink (the T578 remediation's Defect 1) -----------------------------------------

test('hasIconographyLink is false for the bare word "Iconography" with no markdown link', () => {
  assert.equal(hasIconographyLink('See Foundations → Iconography for the naming shape.'), false)
})

test('hasIconographyLink is false for a markdown link to somewhere else', () => {
  assert.equal(
    hasIconographyLink('See [Foundations → Colour](?path=/docs/foundations-colour--docs).'),
    false,
  )
})

test('hasIconographyLink is true for a real markdown link to the Iconography docs page', () => {
  assert.equal(
    hasIconographyLink(
      `See [Foundations → Iconography](?path=/docs/${ICONOGRAPHY_DOCS_TARGET}) for the shape.`,
    ),
    true,
  )
})

// --- containsSrOnly -------------------------------------------------------------------------------

test('containsSrOnly is true when any source file contains the literal text', () => {
  assert.equal(containsSrOnly(['export const x = 1', 'className="sr-only"']), true)
})

test('containsSrOnly is false when no source file contains it', () => {
  assert.equal(containsSrOnly(['export const x = 1', 'className="text-primary"']), false)
})

// --- findComponentSourceFiles (real disk, small live checks) ---------------------------------------

test('findComponentSourceFiles excludes the story and test files and includes sibling source', () => {
  // CaptureStateBadge is the one component directory with a sibling source module
  // (countdown.ts) alongside index.tsx — the shape that tells `.test.tsx`/`.test.ts` apart from
  // ordinary source by suffix, not by count.
  const files = findComponentSourceFiles(srcDir, 'composites', 'CaptureStateBadge')
  const basenames = files.map((f) => path.basename(f)).sort()
  assert.deepEqual(basenames, ['countdown.ts', 'index.tsx'])
})

test('findComponentSourceFiles returns an empty array for a directory that does not exist', () => {
  assert.deepEqual(findComponentSourceFiles(srcDir, 'primitives', 'DoesNotExist'), [])
})

// --- evaluateStoryDocs (pure, fixture-only) ---------------------------------------------------------

const BADGE_DIR = { segment: 'primitives', name: 'Badge' }
const BADGE_PATH = '/fake/primitives/Badge/Badge.stories.tsx'

function metaWithPurpose(purposeLine) {
  return `const meta = {
  component: Badge,
  parameters: { docs: { description: { component: \`${purposeLine}\` } } },
}`
}

// The redundant-name and sole-name maps are real, module-level data — every fixture below picks a
// concrete member of one or the other rather than inventing a synthetic name, so the fixture stays
// honest about which map it is exercising.
const [REDUNDANT_NAME] = SR_ONLY_NAMING_SHAPE_COMPONENTS.keys()
const [SOLE_NAME] = SR_ONLY_SOLE_NAME_COMPONENTS.keys()

test('evaluateStoryDocs passes when the component has a non-empty purpose line and no sr-only', () => {
  const findings = evaluateStoryDocs({
    componentDirs: [BADGE_DIR],
    storyPathByComponent: new Map([['primitives/Badge', BADGE_PATH]]),
    storySourceByPath: new Map([[BADGE_PATH, metaWithPurpose('Marks one item as a state.')]]),
    sourceFilesByComponent: new Map([['primitives/Badge', ['export function Badge() {}']]]),
  })
  assert.deepEqual(findings, [])
})

test('evaluateStoryDocs fails a component directory with no story file', () => {
  const findings = evaluateStoryDocs({
    componentDirs: [BADGE_DIR],
    storyPathByComponent: new Map(),
    storySourceByPath: new Map(),
    sourceFilesByComponent: new Map(),
  })
  assert.equal(findings.length, 1)
  assert.ok(findings[0].includes('has no *.stories.tsx file'))
})

test('evaluateStoryDocs fails a story file with no purpose line at all', () => {
  const findings = evaluateStoryDocs({
    componentDirs: [BADGE_DIR],
    storyPathByComponent: new Map([['primitives/Badge', BADGE_PATH]]),
    storySourceByPath: new Map([[BADGE_PATH, 'const meta = { component: Badge }']]),
    sourceFilesByComponent: new Map([['primitives/Badge', ['export function Badge() {}']]]),
  })
  assert.equal(findings.length, 1)
  assert.ok(findings[0].includes('carries no `parameters.docs.description.component`'))
})

test('evaluateStoryDocs fails a story file whose purpose line is present but empty', () => {
  const findings = evaluateStoryDocs({
    componentDirs: [BADGE_DIR],
    storyPathByComponent: new Map([['primitives/Badge', BADGE_PATH]]),
    storySourceByPath: new Map([[BADGE_PATH, metaWithPurpose('')]]),
    sourceFilesByComponent: new Map([['primitives/Badge', ['export function Badge() {}']]]),
  })
  assert.equal(findings.length, 1)
  assert.ok(findings[0].includes('is present but empty'))
})

// (a) — Defect 1's own regression: the word "Iconography" with no link must fail.
test('(a) a redundant-name component whose purpose line has the word "Iconography" but no link fails', () => {
  const dir = { segment: 'composites', name: REDUNDANT_NAME }
  const storyPath = `/fake/composites/${REDUNDANT_NAME}/${REDUNDANT_NAME}.stories.tsx`
  const findings = evaluateStoryDocs({
    componentDirs: [dir],
    storyPathByComponent: new Map([[`composites/${REDUNDANT_NAME}`, storyPath]]),
    storySourceByPath: new Map([
      [
        storyPath,
        `const meta = { component: ${REDUNDANT_NAME}, parameters: { docs: { description: { component: \`Shows something. Foundations → Iconography documents the shape.\` } } } }`,
      ],
    ]),
    sourceFilesByComponent: new Map([[`composites/${REDUNDANT_NAME}`, ['className="sr-only"']]]),
  })
  assert.equal(findings.length, 1)
  assert.ok(findings[0].includes('carries no markdown link'))
})

// (b) — the contrast case: a real markdown link to the docs page passes.
test('(b) a redundant-name component whose purpose line has a real markdown link to Iconography passes', () => {
  const dir = { segment: 'composites', name: REDUNDANT_NAME }
  const storyPath = `/fake/composites/${REDUNDANT_NAME}/${REDUNDANT_NAME}.stories.tsx`
  const findings = evaluateStoryDocs({
    componentDirs: [dir],
    storyPathByComponent: new Map([[`composites/${REDUNDANT_NAME}`, storyPath]]),
    storySourceByPath: new Map([
      [
        storyPath,
        `const meta = { component: ${REDUNDANT_NAME}, parameters: { docs: { description: { component: \`Shows something. [Foundations → Iconography](?path=/docs/${ICONOGRAPHY_DOCS_TARGET}) documents the shape.\` } } } }`,
      ],
    ]),
    sourceFilesByComponent: new Map([[`composites/${REDUNDANT_NAME}`, ['className="sr-only"']]]),
  })
  assert.deepEqual(findings, [])
})

// (c) — Defect 2's own regression: an unclassified component whose own source contains `sr-only`
// must fail and must name the file/directory.
test('(c) a component directory whose source has sr-only and sits in neither map fails, naming it', () => {
  const dir = { segment: 'primitives', name: 'GhostWithSrOnly' }
  const storyPath = '/fake/primitives/GhostWithSrOnly/GhostWithSrOnly.stories.tsx'
  const findings = evaluateStoryDocs({
    componentDirs: [dir],
    storyPathByComponent: new Map([['primitives/GhostWithSrOnly', storyPath]]),
    storySourceByPath: new Map([
      [
        storyPath,
        'const meta = { component: GhostWithSrOnly, parameters: { docs: { description: { component: `Does a thing.` } } } }',
      ],
    ]),
    sourceFilesByComponent: new Map([
      [
        'primitives/GhostWithSrOnly',
        ['export function GhostWithSrOnly() { return <span className="sr-only">x</span> }'],
      ],
    ]),
  })
  assert.equal(findings.length, 1)
  assert.ok(findings[0].includes('packages/design-system/src/primitives/GhostWithSrOnly/'))
  assert.ok(findings[0].includes('not classified'))
})

// (d) — the contrast case: a component in the sole-name map passes with no Iconography requirement.
test('(d) a component in the sole-name map passes with no Iconography requirement', () => {
  const dir = { segment: 'primitives', name: SOLE_NAME }
  const storyPath = `/fake/primitives/${SOLE_NAME}/${SOLE_NAME}.stories.tsx`
  const findings = evaluateStoryDocs({
    componentDirs: [dir],
    storyPathByComponent: new Map([[`primitives/${SOLE_NAME}`, storyPath]]),
    storySourceByPath: new Map([
      [
        storyPath,
        `const meta = { component: ${SOLE_NAME}, parameters: { docs: { description: { component: \`Does a thing, with no mention of Iconography at all.\` } } } }`,
      ],
    ]),
    sourceFilesByComponent: new Map([[`primitives/${SOLE_NAME}`, ['className="sr-only"']]]),
  })
  assert.deepEqual(findings, [])
})

// (e) — Defect 2's stale-entry half: a map entry (either map) whose component source no longer
// contains sr-only must fail.
test('(e) a redundant-map entry whose component source has no sr-only fails', () => {
  const dir = { segment: 'composites', name: REDUNDANT_NAME }
  const storyPath = `/fake/composites/${REDUNDANT_NAME}/${REDUNDANT_NAME}.stories.tsx`
  const findings = evaluateStoryDocs({
    componentDirs: [dir],
    storyPathByComponent: new Map([[`composites/${REDUNDANT_NAME}`, storyPath]]),
    storySourceByPath: new Map([
      [
        storyPath,
        `const meta = { component: ${REDUNDANT_NAME}, parameters: { docs: { description: { component: \`Shows something. [Foundations → Iconography](?path=/docs/${ICONOGRAPHY_DOCS_TARGET}) documents the shape.\` } } } }`,
      ],
    ]),
    // No sr-only anywhere in this component's own source — the map entry is now stale.
    sourceFilesByComponent: new Map([[`composites/${REDUNDANT_NAME}`, ['export function X() {}']]]),
  })
  assert.ok(
    findings.some((f) => f.includes(`\`${REDUNDANT_NAME}\``) && f.includes('no longer contain')),
  )
})

test('(e) a sole-name-map entry whose component source has no sr-only fails', () => {
  const dir = { segment: 'primitives', name: SOLE_NAME }
  const storyPath = `/fake/primitives/${SOLE_NAME}/${SOLE_NAME}.stories.tsx`
  const findings = evaluateStoryDocs({
    componentDirs: [dir],
    storyPathByComponent: new Map([[`primitives/${SOLE_NAME}`, storyPath]]),
    storySourceByPath: new Map([
      [
        storyPath,
        `const meta = { component: ${SOLE_NAME}, parameters: { docs: { description: { component: \`Does a thing.\` } } } }`,
      ],
    ]),
    sourceFilesByComponent: new Map([[`primitives/${SOLE_NAME}`, ['export function X() {}']]]),
  })
  assert.ok(findings.some((f) => f.includes(`\`${SOLE_NAME}\``) && f.includes('no longer contain')))
})

test('the real maps never overlap (a static invariant, not the runtime guard below)', () => {
  assert.equal(
    [...SR_ONLY_NAMING_SHAPE_COMPONENTS.keys()].some((name) =>
      SR_ONLY_SOLE_NAME_COMPONENTS.has(name),
    ),
    false,
    'a component name must not be classified in both maps at once',
  )
})

test('evaluateStoryDocs fails when a name is registered in both sr-only maps', () => {
  // The two maps are module-level, not passed as arguments, so exercising the guard's own finding
  // text needs a real overlap — created here by mutating the live Map objects (not their `const`
  // bindings) for the duration of one assertion, then removed in `finally` so no other test in this
  // file ever sees it. `REDUNDANT_NAME` is a real SR_ONLY_NAMING_SHAPE_COMPONENTS key; temporarily
  // adding it to SR_ONLY_SOLE_NAME_COMPONENTS too reproduces exactly the configuration mistake the
  // guard exists to catch.
  SR_ONLY_SOLE_NAME_COMPONENTS.set(REDUNDANT_NAME, 'temporary, for this test only')
  try {
    const findings = evaluateStoryDocs({
      componentDirs: [],
      storyPathByComponent: new Map(),
      storySourceByPath: new Map(),
      sourceFilesByComponent: new Map(),
    })
    assert.equal(findings.length, 1)
    assert.ok(findings[0].includes(`\`${REDUNDANT_NAME}\` is listed in both`))
  } finally {
    SR_ONLY_SOLE_NAME_COMPONENTS.delete(REDUNDANT_NAME)
  }
})

test('every SR_ONLY_NAMING_SHAPE_COMPONENTS and SR_ONLY_SOLE_NAME_COMPONENTS entry names a real component directory', () => {
  const realDirs = new Set(listComponentDirs(srcDir).map((d) => d.name))
  for (const name of SR_ONLY_NAMING_SHAPE_COMPONENTS.keys()) {
    assert.ok(realDirs.has(name), `${name} is not a real component directory`)
  }
  for (const name of SR_ONLY_SOLE_NAME_COMPONENTS.keys()) {
    assert.ok(realDirs.has(name), `${name} is not a real component directory`)
  }
})

// --- Live proof -----------------------------------------------------------------------------------

function buildRealInputs() {
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
    sourceFilesByComponent.set(
      key,
      findComponentSourceFiles(srcDir, segment, name).map((f) => readFileSync(f, 'utf8')),
    )
  }
  return { componentDirs, storyPathByComponent, storySourceByPath, sourceFilesByComponent }
}

test('the real check passes against the real packages/design-system/src tree', () => {
  // Rebuilds main()'s own inputs and calls the pure evaluateStoryDocs directly — never main()
  // itself, which sets process.exitCode — the same idiom token-scale.test.mjs's own final "live
  // tree" assertion uses (calling checkFile per file rather than the script's own main()).
  const findings = evaluateStoryDocs(buildRealInputs())
  assert.deepEqual(findings, [])
})

test('every real component whose own source contains sr-only is classified in exactly one map', () => {
  const { componentDirs, sourceFilesByComponent } = buildRealInputs()
  const classified = new Set([
    ...SR_ONLY_NAMING_SHAPE_COMPONENTS.keys(),
    ...SR_ONLY_SOLE_NAME_COMPONENTS.keys(),
  ])
  const unclassified = componentDirs
    .filter(({ segment, name }) =>
      containsSrOnly(sourceFilesByComponent.get(`${segment}/${name}`) ?? []),
    )
    .filter(({ name }) => !classified.has(name))
  assert.deepEqual(unclassified, [])
})
