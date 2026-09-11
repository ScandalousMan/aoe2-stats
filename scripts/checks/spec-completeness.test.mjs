// Regression tests for T571's mechanical check (spec-completeness.mjs). Follows
// token-scale.test.mjs's own `node --test` conventions: real functions, no mocking,
// `node:assert/strict`.
//
// T570 (amending the real 23 component specs to answer all ten states and declare a tier and a
// surface class per component) is a live, in-progress sibling of this task, in this same working
// tree — see this file's header on spec-completeness.mjs. Running the real check against the real
// `packages/design-system/specs/` directory is therefore expected to be red until T570 lands, and
// this suite deliberately does not do that (the one derivation smoke test below reads the real
// README.md only, never a component spec file): every rule is proven against small, self-contained
// fixtures instead, so `pnpm test`/`node --test` here stays green regardless of T570's progress.
// Each rule gets a fixture that passes and one that FAILS — a check that has never been observed to
// fail is not known to check anything (T556's own rule, applied here).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  EXEMPT_SPEC_FILES,
  deriveNineSections,
  deriveVocabulary,
  deriveSurfaceClasses,
  sectionKeyword,
  parseComponentCell,
  tierWordForSegment,
  parseIndexTable,
  extractHeadingsAndLabels,
  checkNineSections,
  checkVocabulary,
  findComponentSection,
  checkComponentVocabulary,
  extractMarkdownTables,
  annotateDeclarationsTable,
  findLabelledValue,
  classifySurfaceClassDeclaration,
  checkComponentDeclarations,
  findUnindexedComponentDirs,
  evaluateSpecsDirectory,
} from './spec-completeness.mjs'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(scriptDir, '..', '..')
const readmePath = path.join(rootDir, 'packages', 'design-system', 'specs', 'README.md')

// The ten-entry vocabulary and nine sections this suite's own fixtures are written against —
// spelled out here once, as plain data, rather than re-derived per test; `deriveVocabulary` and
// `deriveNineSections` are proven against the real README.md separately below.
const SECTIONS = [
  'Purpose',
  'Anatomy',
  'Variants and sizes',
  'States',
  'Tokens used',
  'Spacing',
  'Responsive',
  'Accessibility',
  'Visual acceptance criteria',
]
const VOCABULARY = [
  'default',
  'hover',
  'focus-visible',
  'active',
  'disabled',
  'loading',
  'error',
  'empty',
  'selection',
  'expansion',
]
const SURFACE_CLASSES = ['dense', 'prose']

// A minimal, fully complete single-component spec — every section, every state, and a tier/
// surface-class declaration in the meta-header shape `structural-tier.md` and `tooltip.md` use.
function completeSingleComponentSpec() {
  return `# Widget

**Tier**: **primitive**.
**Surface class**: **dense**.

## 1. Purpose

Renders a widget.

## 2. Anatomy

A box.

## 3. Variants and sizes

One size.

## 4. States

- **default** — resting.
- **hover** — darker.
- **focus-visible** — ring.
- **active** — darker still.
- **disabled** — greyed.
- **loading** — spinner.
- **error** — inline message.
- **empty** — nothing rendered.
- **selection** — never selectable.
- **expansion** — never expands.

## 5. Tokens used

\`surface\`.

## 6. Spacing

\`space-2\`.

## 7. Responsive

None.

## 8. Accessibility

None needed.

## 9. Visual acceptance criteria

Looks like a box.
`
}

// --- deriveNineSections / deriveVocabulary / deriveSurfaceClasses (against the real README.md) --

test('deriveNineSections reads the ten -> nine sections straight from the real README.md', () => {
  const readmeSource = readFileSync(readmePath, 'utf8')
  assert.deepEqual(deriveNineSections(readmeSource), SECTIONS)
})

test('deriveVocabulary reads the real, ten-entry state vocabulary from README.md (T569)', () => {
  const readmeSource = readFileSync(readmePath, 'utf8')
  assert.deepEqual(deriveVocabulary(readmeSource), VOCABULARY)
})

test('deriveSurfaceClasses reads dense/prose from the real "Surface density" heading', () => {
  const readmeSource = readFileSync(readmePath, 'utf8')
  assert.deepEqual(deriveSurfaceClasses(readmeSource), SURFACE_CLASSES)
})

test('deriveNineSections fails loudly if the heading it anchors on disappears', () => {
  assert.throws(() => deriveNineSections('# Nothing here'))
})

test('deriveVocabulary fails loudly if the vocabulary sentence disappears', () => {
  assert.throws(() => deriveVocabulary('# Nothing here'))
})

// --- C2 (T571 remediation): the heading's count word and the list beneath it must agree ---------
//
// A bare `=== 9` / `=== 10` literal only ever notices the list side of this drifting — these tests
// prove the check also notices the *heading*'s own count word drifting out of step with a list that
// still has the right number of names, which a bare literal cannot: it has nothing to compare the
// heading's word against.

test("deriveNineSections FAILS when the heading's own count word disagrees with how many names follow it — the check has been seen to fail", () => {
  const readme = `## Every spec has eight sections

Purpose, Anatomy, Variants and sizes, States, Tokens used, Spacing, Responsive, Accessibility,
Visual acceptance criteria. A spec missing one is incomplete.
`
  assert.throws(
    () => deriveNineSections(readme),
    /says "eight" \(8\) but the sentence beneath it names 9 sections/,
  )
})

test('deriveNineSections FAILS when the list shrinks but the heading still says nine — the reverse direction — the check has been seen to fail', () => {
  const readme = `## Every spec has nine sections

Purpose, Anatomy, Variants and sizes, States, Tokens used, Spacing, Responsive, Accessibility. A
spec missing one is incomplete.
`
  assert.throws(
    () => deriveNineSections(readme),
    /says "nine" \(9\) but the sentence beneath it names 8 sections/,
  )
})

test('deriveVocabulary FAILS when "Every spec answers all ten" disagrees with the bolded list beneath it — the check has been seen to fail', () => {
  const readme = `The state vocabulary is closed: **default, hover, focus-visible, active, disabled, loading,
error, empty, selection, expansion**. Every spec answers all nine, even when the answer is "this
part is never disabled".
`
  assert.throws(
    () => deriveVocabulary(readme),
    /says "Every spec answers all nine" \(9\) but the closed state vocabulary lists 10/,
  )
})

test('deriveVocabulary FAILS when the bolded list shrinks but "Every spec answers all ten" still says ten — the reverse direction — the check has been seen to fail', () => {
  const readme = `The state vocabulary is closed: **default, hover, focus-visible, active, disabled, loading,
error, empty, selection**. Every spec answers all ten, even when the answer is "this part is never
disabled".
`
  assert.throws(
    () => deriveVocabulary(readme),
    /says "Every spec answers all ten" \(10\) but the closed state vocabulary lists 9/,
  )
})

// --- sectionKeyword -----------------------------------------------------------------------------

test('sectionKeyword derives a single discriminative word per canonical section name', () => {
  assert.equal(sectionKeyword('Purpose'), 'purpose')
  assert.equal(sectionKeyword('Variants and sizes'), 'variant')
  assert.equal(sectionKeyword('States'), 'state')
  assert.equal(sectionKeyword('Tokens used'), 'token')
  assert.equal(sectionKeyword('Visual acceptance criteria'), 'acceptance')
})

// --- Index table parsing --------------------------------------------------------------------

test('parseComponentCell expands a brace group into one component per name, tagged with its tier segment', () => {
  const components = parseComponentCell(
    '`src/primitives/{Button,Callout,Badge,Skeleton,Menu,StatValue}/`',
  )
  assert.deepEqual(
    components,
    ['Button', 'Callout', 'Badge', 'Skeleton', 'Menu', 'StatValue'].map((name) => ({
      name,
      segment: 'primitives',
    })),
  )
})

test("parseComponentCell reads two plain, comma-separated components (match-history.md's shape)", () => {
  const components = parseComponentCell(
    '`src/composites/MatchRow/`, `src/composites/MatchDetailPanel/`',
  )
  assert.deepEqual(components, [
    { name: 'MatchRow', segment: 'composites' },
    { name: 'MatchDetailPanel', segment: 'composites' },
  ])
})

test("parseComponentCell yields zero components for a non-src cell (game-asset-tokens.md's shape)", () => {
  assert.deepEqual(
    parseComponentCell('player-colour + icon-size tokens (no component; `tokens/`)'),
    [],
  )
})

test('tierWordForSegment names the tier the directory itself already carries', () => {
  assert.equal(tierWordForSegment('primitives'), 'primitive')
  assert.equal(tierWordForSegment('composites'), 'composite')
  assert.equal(tierWordForSegment('screens'), 'screen')
})

test('parseIndexTable reads a small fixture Index table into one row per spec file', () => {
  const readmeFixture = `## Index

| Spec | Component directory | Feature |
| --- | --- | --- |
| [\`widget.md\`](./widget.md) | \`src/primitives/Widget/\` | 001 |
| [\`pair.md\`](./pair.md) | \`src/composites/A/\`, \`src/composites/B/\` | 001 |
| [\`game-asset-tokens.md\`](./game-asset-tokens.md) | player-colour tokens (no component; \`tokens/\`) | 001 |

## Every spec has nine sections
`
  const rows = parseIndexTable(readmeFixture)
  assert.deepEqual(rows, [
    {
      specFile: 'widget.md',
      components: [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    },
    {
      specFile: 'pair.md',
      components: [
        { name: 'A', segment: 'composites', tierWord: 'composite' },
        { name: 'B', segment: 'composites', tierWord: 'composite' },
      ],
    },
    { specFile: 'game-asset-tokens.md', components: [] },
  ])
})

test('parseIndexTable against the real README.md finds shared-primitives.md mapped to several primitive components', () => {
  // Not an exact-length assertion: shared-primitives.md's own brace group is live editing
  // territory for T570's sibling task in this same working tree (it already grew from six names
  // to seven between this test being written and being run). What must stay true regardless of
  // that count is the shape this check depends on — every named component resolves to the
  // `primitives` tier — so that is what this test proves against real data, rather than a
  // brittle snapshot of the exact name list.
  const readmeSource = readFileSync(readmePath, 'utf8')
  const rows = parseIndexTable(readmeSource)
  const sharedPrimitives = rows.find((r) => r.specFile === 'shared-primitives.md')
  assert.ok(sharedPrimitives, 'expected an Index row for shared-primitives.md')
  const names = sharedPrimitives.components.map((c) => c.name)
  for (const expected of ['Button', 'Callout', 'Badge', 'Skeleton', 'Menu', 'StatValue']) {
    assert.ok(names.includes(expected), `expected shared-primitives.md to still cover ${expected}`)
  }
  assert.ok(sharedPrimitives.components.every((c) => c.tierWord === 'primitive'))
})

// --- checkNineSections ----------------------------------------------------------------------

test('checkNineSections passes a complete fixture', () => {
  assert.deepEqual(checkNineSections(completeSingleComponentSpec(), SECTIONS), [])
})

test('checkNineSections FAILS a fixture missing a section — the check has been seen to fail', () => {
  const withoutResponsive = completeSingleComponentSpec().replace(
    '## 7. Responsive\n\nNone.\n\n',
    '',
  )
  assert.deepEqual(checkNineSections(withoutResponsive, SECTIONS), ['Responsive'])
})

test('checkNineSections accepts the shared-primitives.md compressed bold-label shape, not only ## headings', () => {
  const compressed = `## Button

**Purpose** — commits the user to an action.

**Anatomy** — a box.

**Variants**

table here

**Sizes** — md, lg.

**States**

- **default** — rest.

**Tokens** — colour.

**Spacing** — space-2.

**Responsive** — none.

**Accessibility** — none.

**Acceptance** — looks right.
`
  assert.deepEqual(checkNineSections(compressed, SECTIONS), [])
})

test('checkNineSections does not accept "Variants, sizes and props" as a real match unless "variant" itself appears — regression guard on the keyword derivation', () => {
  // Sanity check on the derivation, not a real defect: "Variants, sizes and props" still contains
  // "variant", so it is correctly accepted — this test documents why, rather than assumes it.
  const heading = '## 3. Variants, sizes and props\n\nSome text.\n'
  assert.deepEqual(checkNineSections(heading, ['Variants and sizes']), [])
})

// --- C3 (T571 remediation): word-boundary matching, not substring ---------------------------
//
// The file header used to claim "`## 3. The four-state collapse` is not a match for \"States\""
// while the implementation actually matched it (a hyphenated compound is not a word boundary to
// `.includes`). These tests make that claim true: the tokeniser treats `four-state` as one token
// distinct from `state`, so it no longer satisfies the "States" section by accident.

test('checkNineSections does NOT accept "## 3. The four-state collapse" as a match for "States" — the check has been seen to fail (this is the exact example the file header now claims correctly)', () => {
  const heading = '## 3. The four-state collapse\n\nSome text.\n'
  assert.deepEqual(checkNineSections(heading, ['States']), ['States'])
})

test('checkNineSections still accepts a real "## States" heading and "## 6. Tokens used" for "Tokens used" — the word-boundary tightening does not break true matches', () => {
  const source = '## States\n\nSome text.\n\n## 6. Tokens used\n\nMore text.\n'
  assert.deepEqual(checkNineSections(source, ['States', 'Tokens used']), [])
})

test('checkNineSections FAILS a nine-heading document of noise that accidentally names eight sections by substring, correctly reporting "States" missing — the check has been seen to fail', () => {
  const noise = `## Purposeful noise

## Variant soup

## The four-state collapse

## Tokenism

## Accessibility theatre

## Acceptance? later
`
  assert.deepEqual(checkNineSections(noise, SECTIONS), [
    'Anatomy',
    'States',
    'Spacing',
    'Responsive',
  ])
})

// --- checkVocabulary -------------------------------------------------------------------------

test('checkVocabulary passes a complete fixture answering all ten states', () => {
  assert.deepEqual(checkVocabulary(completeSingleComponentSpec(), VOCABULARY), [])
})

test("checkVocabulary FAILS a fixture missing selection and expansion (T569's own two new entries) — the check has been seen to fail", () => {
  const eightStateSpec = completeSingleComponentSpec()
    .replace('- **selection** — never selectable.\n', '')
    .replace('- **expansion** — never expands.\n', '')
  assert.deepEqual(checkVocabulary(eightStateSpec, VOCABULARY), ['selection', 'expansion'])
})

test("checkVocabulary accepts a combined bullet answering three states at once (`README.md`'s own shipping shape)", () => {
  const spec = `## States

- **default** — rest.
- **hover / focus-visible / active** — none, this control is not interactive.
- **disabled** — n/a.
- **loading** — n/a.
- **error** — n/a.
- **empty** — n/a.
- **selection** — marks the current item.
- **expansion** — never collapses.
`
  assert.deepEqual(checkVocabulary(spec, VOCABULARY), [])
})

test("checkVocabulary accepts the bare-paragraph shape with no bullet dash (third-party-objection.md's own shape)", () => {
  const spec = `## States

**default** — idle.

**hover** — link only.

**focus-visible** — ring.

**active** — pressed.

**disabled** — never.

**loading** — submitting.

**error** — three shapes.

**empty** — the idle field is the empty state.

**selection** — n/a.

**expansion** — n/a.
`
  assert.deepEqual(checkVocabulary(spec, VOCABULARY), [])
})

test('checkVocabulary accepts a state label carrying a trailing parenthetical (tooltip.md\'s own "**default (closed)**" shape)', () => {
  const spec = `## States

- **default (closed)** — nothing visible.
- **hover (open)** — opens after a delay.
- **focus-visible (open)** — opens immediately.
- **active (open, pinned)** — stays open.
- **disabled** — never.
- **loading** — does not exist yet.
- **error** — none of its own.
- **empty** — trigger alone.
- **selection** — n/a.
- **expansion** — n/a.
`
  assert.deepEqual(checkVocabulary(spec, VOCABULARY), [])
})

// --- C1 (T571 remediation): the vocabulary is checked per component, not per file ------------
//
// `checkVocabulary` on a whole multi-component file passes as soon as *any* component answers a
// state — the exact hole T570's own reasoning about tier/surface class already named for a file
// covering several components. `findComponentSection`/`checkComponentVocabulary` scope the scan to
// each component's own `##` heading when the file draws that boundary (`shared-primitives.md`,
// `structural-tier.md`'s shape), and fall back to the whole document when it does not
// (`match-history.md`'s shape: one shared "States" section naming each component inline).

function twoHeadedComponentFixture({ alphaMissingExpansion }) {
  const alphaExpansionLine = alphaMissingExpansion ? '' : '- **expansion** — never expands.\n'
  return `# Pair

## Alpha

**Purpose** — alpha.

- **default** — rest.
- **hover** — n/a.
- **focus-visible** — n/a.
- **active** — n/a.
- **disabled** — n/a.
- **loading** — n/a.
- **error** — n/a.
- **empty** — n/a.
- **selection** — n/a.
${alphaExpansionLine}
## Beta

**Purpose** — beta.

- **default** — rest.
- **hover** — n/a.
- **focus-visible** — n/a.
- **active** — n/a.
- **disabled** — n/a.
- **loading** — n/a.
- **error** — n/a.
- **empty** — n/a.
- **selection** — n/a.
- **expansion** — never expands.
`
}

const PAIR_COMPONENTS = [
  { name: 'Alpha', segment: 'composites', tierWord: 'composite' },
  { name: 'Beta', segment: 'composites', tierWord: 'composite' },
]

test("findComponentSection returns the slice between a component's own heading and the next heading at the same level", () => {
  const source = twoHeadedComponentFixture({ alphaMissingExpansion: true })
  const alphaSection = findComponentSection(source, 'Alpha')
  assert.ok(alphaSection.includes('**default**'))
  assert.ok(!alphaSection.includes('## Beta'))
  assert.ok(!alphaSection.includes('**Purpose** — beta.'))
})

test("findComponentSection returns null when the file names no heading for the component (match-history.md's shape has no per-component heading at all)", () => {
  const source = '## 5. States\n\n`MatchRow`: **default** — as tabled.\n'
  assert.equal(findComponentSection(source, 'MatchRow'), null)
})

test('checkComponentVocabulary FAILS the one component missing a state within its own heading, even though the file as a whole answers it (Beta does) — the check has been seen to fail', () => {
  const source = twoHeadedComponentFixture({ alphaMissingExpansion: true })
  // Confirms the whole-file scan would have missed this: the file overall answers "expansion"
  // (Beta does), so the old, unscoped check would report nothing wrong here at all.
  assert.deepEqual(checkVocabulary(source, VOCABULARY), [])
  assert.deepEqual(checkComponentVocabulary(source, PAIR_COMPONENTS, VOCABULARY), [
    { component: 'Alpha', missing: ['expansion'] },
  ])
})

test('checkComponentVocabulary passes both components once each answers all ten within its own heading', () => {
  const source = twoHeadedComponentFixture({ alphaMissingExpansion: false })
  assert.deepEqual(checkComponentVocabulary(source, PAIR_COMPONENTS, VOCABULARY), [])
})

test("checkComponentVocabulary falls back to the whole document for a multi-component file with no per-component heading (match-history.md's shape), and still passes it", () => {
  const source = `## 5. States

- **default** — as tabled in §2.
- **hover** — \`MatchRow\`: fill. \`DownloadAction\`: per Button.
- **focus-visible** — n/a.
- **active** — n/a.
- **disabled** — n/a.
- **loading** — n/a.
- **error** — n/a.
- **empty** — n/a.
- **selection** — not applicable to either component.
- **expansion** — not applicable.
`
  const components = [
    { name: 'MatchRow', segment: 'composites', tierWord: 'composite' },
    { name: 'MatchDetailPanel', segment: 'composites', tierWord: 'composite' },
  ]
  assert.deepEqual(checkComponentVocabulary(source, components, VOCABULARY), [])
})

test('checkComponentVocabulary treats a single-component file as already scoped, with no heading lookup needed', () => {
  const source = completeSingleComponentSpec()
  assert.deepEqual(
    checkComponentVocabulary(
      source,
      [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
      VOCABULARY,
    ),
    [],
  )
})

test("extractLineLeadingBoldSpans-backed checkVocabulary recognises the inline, run-on-paragraph shape (shared-primitives.md's own `Callout`/`Badge`/`Skeleton` shape) as clause-leading, not only line-leading", () => {
  const inlineParagraph = `**States** — **default** as above. **hover / active** — none; the root is not interactive.
**focus-visible** — ring. **disabled** — never. **loading** — none. **error** — inline.
**empty** — nothing. **selection** — n/a. **expansion** — n/a.
`
  assert.deepEqual(checkVocabulary(inlineParagraph, VOCABULARY), [])
})

test('extractLineLeadingBoldSpans does not let an unrelated, unpaired single "*" elsewhere in the document (a glob like `--ds-icon-*` inside its own bold phrase) corrupt matches later in the file — regression guard for the bug found while implementing C1', () => {
  const source = `**Sizes** — icon sizes come from \`--ds-icon-*\`, never hand-written.**

## States

- **default** — rest.
- **hover** — n/a.
- **focus-visible** — n/a.
- **active** — n/a.
- **disabled** — n/a.
- **loading** — n/a.
- **error** — n/a.
- **empty** — n/a.
- **selection** — n/a.
- **expansion** — n/a.
`
  assert.deepEqual(checkVocabulary(source, VOCABULARY), [])
})

// --- extractMarkdownTables / annotateDeclarationsTable / findLabelledValue -------------------

test('extractMarkdownTables reads a fenced block into header + data rows, dropping the separator row', () => {
  const source = `Some text.

| Component | Tier | Surface class |
| --- | --- | --- |
| \`Button\` | primitive | dense |
| \`Callout\` | primitive | dense |

More text.
`
  const tables = extractMarkdownTables(source)
  assert.equal(tables.length, 1)
  assert.deepEqual(tables[0].header, ['Component', 'Tier', 'Surface class'])
  assert.deepEqual(tables[0].rows, [
    ['`Button`', 'primitive', 'dense'],
    ['`Callout`', 'primitive', 'dense'],
  ])
})

test('annotateDeclarationsTable recognises a table naming component, tier and surface class columns, and rejects one that does not', () => {
  const declarations = { header: ['Component', 'Tier', 'Surface class'], rows: [] }
  assert.ok(annotateDeclarationsTable(declarations))

  const unrelated = { header: ['Variant', 'Use'], rows: [] }
  assert.equal(annotateDeclarationsTable(unrelated), null)
})

test('findLabelledValue reads structural-tier.md\'s own meta-header shape ("**Tier**: all nine are **primitives**.")', () => {
  const source = '**Tier**: all nine are **primitives**. None carries domain knowledge.'
  assert.equal(
    findLabelledValue(source, ['tier']),
    'all nine are **primitives**. None carries domain knowledge.',
  )
})

test('findLabelledValue returns null when the label is absent', () => {
  assert.equal(findLabelledValue('# Nothing here', ['tier']), null)
})

// --- classifySurfaceClassDeclaration -----------------------------------------------------------
//
// Regression coverage for the defect found during T571's own verification: `.includes()` cannot
// tell a negation ("neither `dense` nor `prose` — <reason>") from a positive claim naming both
// classes at once, so both used to pass. Each case below is proven against `checkComponentDeclarations`
// too, further down, so the finding shape a real spec would trigger is also covered — not only the
// classifier in isolation.

test('classifySurfaceClassDeclaration FAILS a declaration naming both classes as a claim (not the sanctioned negation) — the check has been seen to fail', () => {
  // This is the exact case the naive `.includes()` implementation let through by accident (both
  // substrings present) — see this file's own comment above and the hand-back for the standalone
  // repro proving the pre-fix implementation returns no finding at all for this text.
  assert.deepEqual(
    classifySurfaceClassDeclaration('`dense` on the table, `prose` in the panel', SURFACE_CLASSES),
    { valid: false, kind: 'conflict' },
  )
})

test('classifySurfaceClassDeclaration FAILS a bare "N/A" — the check has been seen to fail', () => {
  assert.deepEqual(classifySurfaceClassDeclaration('N/A', SURFACE_CLASSES), {
    valid: false,
    kind: 'missing',
  })
})

test('classifySurfaceClassDeclaration FAILS the sanctioned negation with no reason after it — the check has been seen to fail', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration('neither `dense` nor `prose`', SURFACE_CLASSES),
    {
      valid: false,
      kind: 'bare-negation',
    },
  )
})

test("classifySurfaceClassDeclaration PASSES the sanctioned negation with a non-empty reason (T570's own shape across 20+ components)", () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      'neither `dense` nor `prose` — a control, not a surface with a density of its own.',
      SURFACE_CLASSES,
    ),
    { valid: true, kind: 'inapplicable' },
  )
})

test('classifySurfaceClassDeclaration PASSES a single-class declaration, as it always has', () => {
  assert.deepEqual(classifySurfaceClassDeclaration('`dense`', SURFACE_CLASSES), {
    valid: true,
    kind: 'declared',
  })
})

test('classifySurfaceClassDeclaration PASSES the sanctioned prop-selection form (structural-tier.md\'s own `Panel`/`Table` shape, data-model.md §5\'s "or a prop" exit)', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      '`dense` or `prose`, by its own `density` prop (§3) — the caller picks exactly one',
      SURFACE_CLASSES,
    ),
    { valid: true, kind: 'prop-selected' },
  )
})

test('classifySurfaceClassDeclaration FAILS an "or"-joined pair naming no prop — that is a conflict, not the sanctioned prop-selection form — the check has been seen to fail', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration('`dense` or `prose`, depending on mood', SURFACE_CLASSES),
    {
      valid: false,
      kind: 'conflict',
    },
  )
})

test('classifySurfaceClassDeclaration FAILS `null` and empty text alike, as "missing"', () => {
  assert.deepEqual(classifySurfaceClassDeclaration(null, SURFACE_CLASSES), {
    valid: false,
    kind: 'missing',
  })
  assert.deepEqual(classifySurfaceClassDeclaration('   ', SURFACE_CLASSES), {
    valid: false,
    kind: 'missing',
  })
})

// --- C4 (T571 remediation): order-tolerant, occurrence-aware classification -------------------
//
// Six declarations the reviewer probed against the pre-fix implementation. Four are direction-safe
// (order-swapped or a prefix before the negation) and were false *failures*; the last two are
// wrong-but-passes the pre-fix implementation let through. Verified against the pre-fix
// implementation (git HEAD at the time of this remediation) before writing the fix:
//
//   "neither `prose` nor `dense` — a control, not a surface."          => {"valid":false,"kind":"conflict"}
//   "`prose` or `dense`, by its own `density` prop"                    => {"valid":false,"kind":"conflict"}
//   "Not applicable: neither `dense` nor `prose` — it is a control."   => {"valid":false,"kind":"conflict"}
//   "`prose`. Never `dense`: rows here are paragraphs, not data."      => {"valid":false,"kind":"conflict"}
//   "neither `dense` nor `prose` — it is `dense`."                     => {"valid":true,"kind":"inapplicable"}
//   "`dense` or `prose`, whichever the parent Panel props supply."     => {"valid":true,"kind":"prop-selected"}
//
// (reproduced by running `classifySurfaceClassDeclaration` from `git show HEAD:scripts/checks/
// spec-completeness.mjs` against these six strings — the file this remediation touches, before this
// remediation's own edits landed).

test('classifySurfaceClassDeclaration PASSES the sanctioned negation with the classes named in the opposite order — order must not matter — the check has been seen to fail (pre-fix: {"valid":false,"kind":"conflict"})', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      'neither `prose` nor `dense` — a control, not a surface.',
      SURFACE_CLASSES,
    ),
    { valid: true, kind: 'inapplicable' },
  )
})

test('classifySurfaceClassDeclaration PASSES the sanctioned prop-selection form with the classes named in the opposite order — the check has been seen to fail (pre-fix: {"valid":false,"kind":"conflict"})', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      '`prose` or `dense`, by its own `density` prop',
      SURFACE_CLASSES,
    ),
    { valid: true, kind: 'prop-selected' },
  )
})

test('classifySurfaceClassDeclaration PASSES the sanctioned negation preceded by a prefix ("Not applicable: ") — not anchored to the string\'s start — the check has been seen to fail (pre-fix: {"valid":false,"kind":"conflict"})', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      'Not applicable: neither `dense` nor `prose` — it is a control.',
      SURFACE_CLASSES,
    ),
    { valid: true, kind: 'inapplicable' },
  )
})

test('classifySurfaceClassDeclaration PASSES a positive claim of one class that explicitly, separately negates the other — a correct claim naming the class it is not, not a conflict — the check has been seen to fail (pre-fix: {"valid":false,"kind":"conflict"})', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      '`prose`. Never `dense`: rows here are paragraphs, not data.',
      SURFACE_CLASSES,
    ),
    { valid: true, kind: 'declared' },
  )
})

test('classifySurfaceClassDeclaration FAILS the sanctioned negation whose own reason contradicts it by claiming the class it just ruled out — the check has been seen to fail (pre-fix: {"valid":true,"kind":"inapplicable"})', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      'neither `dense` nor `prose` — it is `dense`.',
      SURFACE_CLASSES,
    ),
    { valid: false, kind: 'contradiction' },
  )
})

test('classifySurfaceClassDeclaration FAILS an "or"-joined pair whose only "prop" mention names no actual prop of this component — the check has been seen to fail (pre-fix: {"valid":true,"kind":"prop-selected"})', () => {
  assert.deepEqual(
    classifySurfaceClassDeclaration(
      '`dense` or `prose`, whichever the parent Panel props supply.',
      SURFACE_CLASSES,
    ),
    { valid: false, kind: 'conflict' },
  )
})

// --- checkComponentDeclarations ---------------------------------------------------------------

test('checkComponentDeclarations passes a single-component file using the meta-header shape', () => {
  const source = '**Tier**: **primitive**.\n**Surface class**: **dense**.\n'
  const findings = checkComponentDeclarations(
    source,
    [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    SURFACE_CLASSES,
  )
  assert.deepEqual(findings, [])
})

test('checkComponentDeclarations FAILS a single-component file declaring no tier or surface class at all — the check has been seen to fail', () => {
  const findings = checkComponentDeclarations(
    '# Widget\n\nNo declarations here.\n',
    [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    SURFACE_CLASSES,
  )
  assert.deepEqual(findings, [
    { component: 'Widget', kind: 'tier', detail: null },
    { component: 'Widget', kind: 'surface-class', detail: null },
  ])
})

test('checkComponentDeclarations passes a multi-component file with a complete declarations table', () => {
  const source = `# Pair

| Component | Tier | Surface class |
| --- | --- | --- |
| \`A\` | domain composite | dense |
| \`B\` | domain composite | prose |
`
  const components = [
    { name: 'A', segment: 'composites', tierWord: 'composite' },
    { name: 'B', segment: 'composites', tierWord: 'composite' },
  ]
  assert.deepEqual(checkComponentDeclarations(source, components, SURFACE_CLASSES), [])
})

test("checkComponentDeclarations FAILS a multi-component file with no table at all — a tier is a property of a component, and a file covering more than one cannot declare one without it (T570's own reasoning) — the check has been seen to fail", () => {
  const source = '**Tier**: **primitive**.\n**Surface class**: **dense**.\n'
  const components = [
    { name: 'Button', segment: 'primitives', tierWord: 'primitive' },
    { name: 'Callout', segment: 'primitives', tierWord: 'primitive' },
  ]
  const findings = checkComponentDeclarations(source, components, SURFACE_CLASSES)
  assert.deepEqual(findings, [
    { component: 'Button', kind: 'no-row' },
    { component: 'Callout', kind: 'no-row' },
  ])
})

test('checkComponentDeclarations FAILS a single-component file declaring both surface classes as a claim, not the sanctioned negation — the check has been seen to fail', () => {
  const source =
    '**Tier**: **primitive**.\n**Surface class**: `dense` on the table, `prose` in the panel.\n'
  const findings = checkComponentDeclarations(
    source,
    [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    SURFACE_CLASSES,
  )
  assert.deepEqual(findings, [
    {
      component: 'Widget',
      kind: 'surface-class-conflict',
      detail: '`dense` on the table, `prose` in the panel.',
    },
  ])
})

test('checkComponentDeclarations FAILS a single-component file recording the negation with no reason after it — the check has been seen to fail', () => {
  const source = '**Tier**: **primitive**.\n**Surface class**: neither `dense` nor `prose`.\n'
  const findings = checkComponentDeclarations(
    source,
    [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    SURFACE_CLASSES,
  )
  assert.deepEqual(findings, [
    {
      component: 'Widget',
      kind: 'surface-class-bare-negation',
      detail: 'neither `dense` nor `prose`.',
    },
  ])
})

test("checkComponentDeclarations passes a single-component file using the sanctioned negation with a reason (T570's own shape)", () => {
  const source =
    '**Tier**: **primitive**.\n' +
    '**Surface class**: neither `dense` nor `prose` — a control, not a surface with a density of its own.\n'
  const findings = checkComponentDeclarations(
    source,
    [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    SURFACE_CLASSES,
  )
  assert.deepEqual(findings, [])
})

test("checkComponentDeclarations passes a table row using the sanctioned prop-selection form (structural-tier.md's real `Panel`/`Table` shape)", () => {
  const source = `| Component | Tier | Surface class |
| --- | --- | --- |
| \`Panel\` | primitive | \`dense\` or \`prose\`, by its own \`density\` prop (§3) — the caller picks exactly one |
`
  const components = [{ name: 'Panel', segment: 'primitives', tierWord: 'primitive' }]
  assert.deepEqual(checkComponentDeclarations(source, components, SURFACE_CLASSES), [])
})

test('checkComponentDeclarations FAILS the one row in a table declaring both surface classes as a claim, distinguished from the sanctioned negation the sibling row uses — the check has been seen to fail', () => {
  const source = `| Component | Tier | Surface class |
| --- | --- | --- |
| \`A\` | domain composite | \`dense\` on the table, \`prose\` in the panel |
| \`B\` | domain composite | neither \`dense\` nor \`prose\` — a control, not a surface with a density of its own |
`
  const components = [
    { name: 'A', segment: 'composites', tierWord: 'composite' },
    { name: 'B', segment: 'composites', tierWord: 'composite' },
  ]
  const findings = checkComponentDeclarations(source, components, SURFACE_CLASSES)
  assert.deepEqual(findings, [
    {
      component: 'A',
      kind: 'surface-class-conflict',
      detail: '`dense` on the table, `prose` in the panel',
    },
  ])
})

test('checkComponentDeclarations FAILS the one row in a table whose tier does not match its own directory (e.g. a screen mislabelled primitive) — the check has been seen to fail', () => {
  const source = `| Component | Tier | Surface class |
| --- | --- | --- |
| \`A\` | screen | dense |
| \`B\` | domain composite | prose |
`
  const components = [
    { name: 'A', segment: 'composites', tierWord: 'composite' },
    { name: 'B', segment: 'composites', tierWord: 'composite' },
  ]
  const findings = checkComponentDeclarations(source, components, SURFACE_CLASSES)
  assert.deepEqual(findings, [{ component: 'A', kind: 'tier', detail: 'screen' }])
})

// --- findUnindexedComponentDirs -----------------------------------------------------------------

test('findUnindexedComponentDirs reports a real component directory the Index never names', () => {
  const onDisk = ['primitives/Button', 'primitives/Dialog']
  const indexed = new Set(['primitives/Button'])
  assert.deepEqual(findUnindexedComponentDirs(onDisk, indexed), ['primitives/Dialog'])
})

test('findUnindexedComponentDirs is silent once every directory is indexed', () => {
  const onDisk = ['primitives/Button']
  const indexed = new Set(['primitives/Button'])
  assert.deepEqual(findUnindexedComponentDirs(onDisk, indexed), [])
})

// --- evaluateSpecsDirectory: the full orchestration, against small fixtures ----------------------

const BASE_ARGS = {
  sections: SECTIONS,
  vocabulary: VOCABULARY,
  surfaceClasses: SURFACE_CLASSES,
  exemptFiles: EXEMPT_SPEC_FILES,
}

test('evaluateSpecsDirectory passes a small, fully complete fixture directory', () => {
  const indexRows = [
    {
      specFile: 'widget.md',
      components: [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    },
  ]
  const specSources = new Map([['widget.md', completeSingleComponentSpec()]])
  const findings = evaluateSpecsDirectory({
    ...BASE_ARGS,
    indexRows,
    specSources,
    componentDirsOnDisk: ['primitives/Widget'],
  })
  assert.deepEqual(findings, [])
})

test('evaluateSpecsDirectory FAILS a fixture directory with a missing section, an unanswered state, no tier declaration and an unindexed directory, all at once — the check has been seen to fail', () => {
  const incompleteSource = completeSingleComponentSpec()
    .replace('## 7. Responsive\n\nNone.\n\n', '')
    .replace('- **expansion** — never expands.\n', '')
    .replace('**Tier**: **primitive**.\n', '')

  const indexRows = [
    {
      specFile: 'widget.md',
      components: [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    },
  ]
  const specSources = new Map([['widget.md', incompleteSource]])
  const findings = evaluateSpecsDirectory({
    ...BASE_ARGS,
    indexRows,
    specSources,
    componentDirsOnDisk: ['primitives/Widget', 'primitives/Orphan'],
  })

  assert.ok(
    findings.some((f) => f.includes('widget.md') && f.includes('missing section "Responsive"')),
  )
  assert.ok(
    findings.some(
      (f) => f.includes('widget.md') && f.includes('state "expansion" is not answered'),
    ),
  )
  assert.ok(findings.some((f) => f.includes('widget.md') && f.includes('declares no tier')))
  assert.ok(
    findings.some((f) => f.includes('primitives/Orphan') && f.includes('no row in README.md')),
  )
})

test('evaluateSpecsDirectory FAILS a spec declaring both surface classes as a claim, naming the rule it breaks — the check has been seen to fail', () => {
  const source = completeSingleComponentSpec().replace(
    '**Surface class**: **dense**.',
    '**Surface class**: `dense` on the table, `prose` in the panel.',
  )
  const indexRows = [
    {
      specFile: 'widget.md',
      components: [{ name: 'Widget', segment: 'primitives', tierWord: 'primitive' }],
    },
  ]
  const findings = evaluateSpecsDirectory({
    ...BASE_ARGS,
    indexRows,
    specSources: new Map([['widget.md', source]]),
    componentDirsOnDisk: ['primitives/Widget'],
  })
  assert.ok(
    findings.some(
      (f) =>
        f.includes('widget.md') &&
        f.includes('more than one surface class') &&
        f.includes('data-model.md §5'),
    ),
  )
})

test('evaluateSpecsDirectory skips an exempt file entirely, even one that names no component of its own', () => {
  const indexRows = [{ specFile: 'game-asset-tokens.md', components: [] }]
  const specSources = new Map([['game-asset-tokens.md', '# Not a component spec at all\n']])
  const findings = evaluateSpecsDirectory({
    ...BASE_ARGS,
    indexRows,
    specSources,
    componentDirsOnDisk: [],
  })
  assert.deepEqual(findings, [])
})

test('evaluateSpecsDirectory FAILS when the Index names a file that does not exist on disk — the check has been seen to fail', () => {
  const indexRows = [{ specFile: 'missing.md', components: [] }]
  const findings = evaluateSpecsDirectory({
    ...BASE_ARGS,
    indexRows,
    specSources: new Map(),
    componentDirsOnDisk: [],
  })
  assert.ok(findings.some((f) => f.includes('missing.md') && f.includes('does not exist')))
})

test('EXEMPT_SPEC_FILES names game-asset-tokens.md with a reason beside it, as the task requires', () => {
  assert.ok(EXEMPT_SPEC_FILES.has('game-asset-tokens.md'))
  assert.match(EXEMPT_SPEC_FILES.get('game-asset-tokens.md'), /token/i)
})
