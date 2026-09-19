// Regression tests for T594's extractor (state-coverage.mjs), including the orchestrator's own
// remediation of this task's second hand-back: consistency mode now renders record 1 and every
// primitive matrix as markdown between `<!-- state-coverage:begin/end -->` markers instead of
// diffing a JSON snapshot against itself, and a coverage cell distinguishes a confirmed `'none'`
// from an `'unresolved: <reason>'` it could not settle. Follows story-docs.test.mjs's own
// `node --test` conventions: real functions, small fixtures, node:assert/strict, no mocking.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync, mkdirSync, rmSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  parseTsx,
  buildConstStringMap,
  extractPseudoClasses,
  findLocalElements,
  findVariantSizeDefaults,
  findPrimitiveInstances,
  findMeta,
  findExportedStoryObjects,
  extractVisualForceState,
  findPlayFocusTarget,
  extractStringLiteralsDeep,
  storyArgsStringLiterals,
  resolveNameMatch,
  buildAxisMatrix,
  buildElementMatrix,
  renderGeneratedRegion,
  extractGeneratedRegion,
  replaceGeneratedRegion,
  formatWithPrettier,
  findHelperInvocationGuards,
  findHelperInvocationIterationContext,
  evaluateExpr,
  evaluateGuards,
  resolveComposedStoryMatches,
  resolveDisabledFromStories,
  renderRecord1,
  findOwnStoryRenderInstances,
  parseSelector,
  resolveSelectorMatch,
  findRenderJsxProps,
  impliedRoleForPrimitiveInstance,
  computeStateCoverage,
  checkCitations,
  findUnparsedQuoteAdjacentCitations,
  findInlineCodeClaims,
  resolveBareLocationFromBullet,
  parseCitations,
  parseLineSpec,
  resolveCitationLocation,
  matchQuoteAgainstText,
  checkHandoffTally,
  findDeferralHitsInStories,
  checkDeferralVocabularyCoverage,
  countRecord1Cells,
  countRecord3Cells,
} from './state-coverage.mjs'

function parse(code, fileName = 'fixture.tsx') {
  return parseTsx(fileName, code)
}

// `computeStateCoverage`'s own `componentKeyForFile` (state-coverage.mjs) keys `localElements` by a
// path *relative to the real* `packages/design-system/src`, not by whatever prefix a fixture
// happens to use — a fixture path outside that real tree (e.g. the `/repo/...` prefix several
// `computed.matrices` fixtures below use) still drives `resolveDisabledFromStories`/`buildAxisMatrix`
// correctly, because those match `componentKey` against itself internally, but it can never key
// `computed.localElements` under the label a test expects (`primitives/Dialog`, and so on) — that
// grouping is looked up by the real relative path. Any fixture that reads `computed.localElements`
// needs its own files placed under this real directory instead.
const REPO_SRC_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  'packages',
  'design-system',
  'src',
)

function naiveTagGrepFinds(source, tag) {
  return source.includes(`<${tag} `)
}

// --- Fixture 1: a tag whose name ends its line ------------------------------------------------

const TAG_ENDS_LINE_SOURCE = `
function SkipLink() {
  return (
    <a
      href={skipToContentHref}
      className={cx('sr-only', 'focus:not-sr-only', focusRing)}
    >
      Skip to content
    </a>
  )
}
`

test('findLocalElements finds a tag whose own name ends its line (grep-missed shape)', () => {
  const sourceFile = parse(TAG_ENDS_LINE_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.length, 1)
  assert.equal(found[0].tag, 'a')
})

test('a naive `<a ` line grep misses the same tag (second proof, contrast with the parser above)', () => {
  assert.equal(naiveTagGrepFinds(TAG_ENDS_LINE_SOURCE, 'a'), false)
})

test('a naive `<a ` line grep finds a single-line tag (contrast)', () => {
  const singleLine = `const link = <a href="#" className="hover:underline">Contents</a>`
  assert.equal(naiveTagGrepFinds(singleLine, 'a'), true)
  const sourceFile = parse(singleLine)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.length, 1)
  assert.equal(found[0].hover, 'hover:underline')
})

// --- Fixture 2: a tabIndex={-1} heading carrying a focus-ring constant --------------------------

const TABINDEX_HEADING_SOURCE = `
const sectionHeadingFocusRing =
  'outline-none focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

function SectionHeading({ id, children }) {
  return (
    <h2 id={id} tabIndex={-1} className={cx('font-display text-xl', sectionHeadingFocusRing)}>
      {children}
    </h2>
  )
}
`

test('findLocalElements finds a tabIndex={-1} heading carrying a same-file focus-ring constant', () => {
  const sourceFile = parse(TABINDEX_HEADING_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  assert.ok(constMap.has('sectionHeadingFocusRing'))
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.length, 1)
  assert.equal(found[0].tag, 'h2')
  assert.equal(found[0].tabIndex, -1)
  assert.equal(found[0].hover, null)
  assert.equal(found[0].active, null)
  assert.match(found[0].focusVisible, /focus-visible:outline-ring/)
})

// --- Fixture 3: a primitive instance with no `size` ---------------------------------------------

const BUTTON_DEFAULTS_SOURCE = `
function Button({ variant = 'secondary', size = 'md', children }) {
  return <button className={variantClasses[variant]}>{children}</button>
}
`

test("findVariantSizeDefaults reads Button's own defaults from its destructured parameters", () => {
  const sourceFile = parse(BUTTON_DEFAULTS_SOURCE)
  const defaults = findVariantSizeDefaults(sourceFile)
  assert.deepEqual(defaults, { variant: 'secondary', size: 'md' })
})

test('findPrimitiveInstances resolves an omitted size prop to the primitive default', () => {
  const consumerSource = `const el = <Button variant="primary">Go</Button>`
  const sourceFile = parse(consumerSource)
  const found = findPrimitiveInstances(sourceFile, 'fixture.tsx', {
    Button: { variant: 'secondary', size: 'md' },
  })
  assert.equal(found.length, 1)
  assert.deepEqual(found[0].variant, { value: 'primary', resolved: 'explicit' })
  assert.deepEqual(found[0].size, { value: 'md', resolved: 'default' })
})

test('findPrimitiveInstances resolves an explicit size prop as explicit (contrast)', () => {
  const consumerSource = `const el = <Button variant="primary" size="lg">Go</Button>`
  const sourceFile = parse(consumerSource)
  const found = findPrimitiveInstances(sourceFile, 'fixture.tsx', {
    Button: { variant: 'secondary', size: 'md' },
  })
  assert.deepEqual(found[0].size, { value: 'lg', resolved: 'explicit' })
})

// --- Fixture 4: a focus-visible frame left only by a play() -------------------------------------

const PLAY_FOCUS_SOURCE = `
export const EscapeReturnsFocusToTrigger = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const trigger = canvas.getByRole('button')
    trigger.focus()
    await userEvent.keyboard('{Enter}')
    await canvas.findByRole('menu')
    await userEvent.keyboard('{Escape}')
    expect(canvas.queryByRole('menu')).not.toBeInTheDocument()
    await expect(trigger).toHaveFocus()
  },
}
`

test('findPlayFocusTarget resolves the last toHaveFocus() assertion to its earlier-bound locator', () => {
  const sourceFile = parse(PLAY_FOCUS_SOURCE)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const playProp = node.properties.find((p) => p.name.getText() === 'play')
  const target = findPlayFocusTarget(playProp.initializer.body)
  assert.deepEqual(target, { role: 'button', name: null })
})

// --- Fixture 5: a hover left only by a play() must NOT count ------------------------------------

const PLAY_HOVER_ONLY_SOURCE = `
export const HoverAttemptViaPlay = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.hover(canvas.getByRole('button'))
  },
}
`

test('findPlayFocusTarget finds nothing for a play() that only hovers (must not count)', () => {
  const sourceFile = parse(PLAY_HOVER_ONLY_SOURCE)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const playProp = node.properties.find((p) => p.name.getText() === 'play')
  const target = findPlayFocusTarget(playProp.initializer.body)
  assert.equal(target, null)
})

test('extractVisualForceState reads a hover force-state directly, never through play() (contrast)', () => {
  const source = `
export const Hover = {
  args: { variant: 'primary', size: 'lg' },
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}
`
  const sourceFile = parse(source)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  assert.deepEqual(extractVisualForceState(node), {
    state: 'hover',
    role: 'button',
    name: null,
    selector: null,
    nth: null,
  })
})

// --- Fixture 6: a variant whose state stories all target the other variant ----------------------

const MENU_STORIES_SOURCE = `
import { Menu } from './index'
const meta = { component: Menu, args: {} }
export default meta

export const ItemError = {
  args: { variant: 'actions', triggerLabel: 'Manage', items: [] },
}

export const Hover = {
  args: { variant: 'selection', triggerLabel: 'aoe2guy' },
  parameters: { visualForceState: { state: 'hover', role: 'menuitemradio', name: 'aoe2alt' } },
}

export const FocusVisible = {
  args: { variant: 'selection', triggerLabel: 'aoe2guy' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2alt' } },
}

export const Active = {
  args: { variant: 'selection', triggerLabel: 'aoe2guy' },
  parameters: { visualForceState: { state: 'active', role: 'menuitemradio', name: 'aoe2alt' } },
}
`

// Menu's own `variant` prop is required (no destructuring default), so `findVariantSizeDefaults`
// resolves it to `null` — the same shape the real `primitives/Menu/index.tsx` carries.
const MENU_INDEX_SOURCE = `
export function Menu({ variant }) {
  return null
}
`

test("buildAxisMatrix leaves Menu's actions variant with no forced state when every hover/focus-visible/active story targets selection", () => {
  // Routed through the real pipeline (`computeStateCoverage`), not hand-built instances: the
  // shape the orchestrator's REJECT on #80 (item 4b) asked for, so this fixture exercises the same
  // own-story discovery, `findVariantSizeDefaults` and `buildAllMatrices` path every other
  // primitive's matrix is built from, rather than a parallel hand-assembled one that could drift
  // from it unnoticed.
  const componentDirs = [{ segment: 'primitives', name: 'Menu' }]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Menu/index.tsx', MENU_INDEX_SOURCE],
    ['/repo/packages/design-system/src/primitives/Menu/Menu.stories.tsx', MENU_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const matrix = computed.matrices.Menu
  const actionsRow = matrix.find((r) => r.variantSize === 'actions')
  const selectionRow = matrix.find((r) => r.variantSize === 'selection')
  assert.ok(actionsRow, 'actions row must exist (a real story renders it)')
  assert.deepEqual(actionsRow.hover, ['none'])
  assert.deepEqual(actionsRow.focusVisible, ['none'])
  assert.deepEqual(actionsRow.active, ['none'])
  assert.notDeepEqual(selectionRow.hover, ['none'])
  assert.notDeepEqual(selectionRow.focusVisible, ['none'])
  assert.notDeepEqual(selectionRow.active, ['none'])
})

// --- Fixture 6b: an ambiguous composed-story match must render `unresolved` on every variant row
// it was ambiguous between (T594 B1, REJECT #5 on #80/#79). Two `Menu` instances of *different*
// variants, both role `button`, neither carrying the forced name literally and the name absent
// from the story's own args either — the live shape `README.md:1902`/`:2305` contradicted itself
// over (`ProfileSummary`'s two `Menu`s, forced name `"Country:"`, matching neither `"Manage"` nor
// `"Choose"`). Pre-fix, this landed only in the unresolved pseudo-row and left both variant rows
// at `'none'` — a confirmed absence over a comparison that actually produced an ambiguity.

const BOARD_INDEX_SOURCE = `
import { Menu } from '../../primitives/Menu'

export function Board() {
  return (
    <div>
      <Menu variant="actions" aria-label="Manage" items={[]} />
      <Menu variant="selection" aria-label="Choose" items={[]} />
    </div>
  )
}
`

const BOARD_AMBIGUOUS_STORIES_SOURCE = `
import { Board } from './index'
const meta = { component: Board, args: {} }
export default meta

export const CountryHoverRevealed = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Country:' } },
}
`

test("buildAxisMatrix renders 'unresolved', not a confirmed 'none', on every variant row an ambiguous composed-story match was ambiguous between", () => {
  const componentDirs = [
    { segment: 'composites', name: 'Board' },
    { segment: 'primitives', name: 'Menu' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/composites/Board/index.tsx', BOARD_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Board/Board.stories.tsx',
      BOARD_AMBIGUOUS_STORIES_SOURCE,
    ],
    ['/repo/packages/design-system/src/primitives/Menu/index.tsx', MENU_INDEX_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const matrix = computed.matrices.Menu
  const actionsRow = matrix.find((r) => r.variantSize === 'actions')
  const selectionRow = matrix.find((r) => r.variantSize === 'selection')
  assert.ok(actionsRow)
  assert.ok(selectionRow)
  assert.match(actionsRow.hover[0], /^unresolved: /)
  assert.match(selectionRow.hover[0], /^unresolved: /)
  // Neither row's other states were ever forced by this story — those stay a real, uncontested
  // `'none'`, the contrast that proves the fix is scoped to the state that was actually ambiguous.
  assert.deepEqual(actionsRow.focusVisible, ['none'])
  assert.deepEqual(selectionRow.focusVisible, ['none'])
})

const BOARD_RESOLVED_STORIES_SOURCE = `
import { Board } from './index'
const meta = { component: Board, args: {} }
export default meta

export const ManageHoverRevealed = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Manage' } },
}
`

test('contrast: the same shape resolves to one row when the forced name is literally unique — the other variant stays a genuine none', () => {
  const componentDirs = [
    { segment: 'composites', name: 'Board' },
    { segment: 'primitives', name: 'Menu' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/composites/Board/index.tsx', BOARD_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Board/Board.stories.tsx',
      BOARD_RESOLVED_STORIES_SOURCE,
    ],
    ['/repo/packages/design-system/src/primitives/Menu/index.tsx', MENU_INDEX_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const matrix = computed.matrices.Menu
  const actionsRow = matrix.find((r) => r.variantSize === 'actions')
  const selectionRow = matrix.find((r) => r.variantSize === 'selection')
  assert.deepEqual(actionsRow.hover, ['Board:ManageHoverRevealed'])
  assert.deepEqual(selectionRow.hover, ['none'])
})

// T594's row 8 sweep, item 2: a hand-typed count in the Method paragraph above was wrong (a
// story-name count where the real comparison is over tainted `(row, state)` cells) — printed
// instead, by `computeStateCoverage`'s own `ambiguitySummary`, never hand-counted again.

test("computeStateCoverage's ambiguitySummary counts one ambiguous instance per tainted candidate, one event per story/state, and both tainted cells as kept when nothing else on either row covers that state", () => {
  const componentDirs = [
    { segment: 'composites', name: 'Board' },
    { segment: 'primitives', name: 'Menu' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/composites/Board/index.tsx', BOARD_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Board/Board.stories.tsx',
      BOARD_AMBIGUOUS_STORIES_SOURCE,
    ],
    ['/repo/packages/design-system/src/primitives/Menu/index.tsx', MENU_INDEX_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  assert.deepEqual(computed.ambiguitySummary, {
    instances: 2,
    events: 1,
    taintedCells: 2,
    kept: 2,
    dropped: 0,
    storyNames: 1,
  })
})

test('contrast: the ambiguity tally is all zero once the forced name is literally unique (no ambiguity at all)', () => {
  const componentDirs = [
    { segment: 'composites', name: 'Board' },
    { segment: 'primitives', name: 'Menu' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/composites/Board/index.tsx', BOARD_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Board/Board.stories.tsx',
      BOARD_RESOLVED_STORIES_SOURCE,
    ],
    ['/repo/packages/design-system/src/primitives/Menu/index.tsx', MENU_INDEX_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  assert.deepEqual(computed.ambiguitySummary, {
    instances: 0,
    events: 0,
    taintedCells: 0,
    kept: 0,
    dropped: 0,
    storyNames: 0,
  })
})

// A tainted cell is 'dropped' once a *different* story gives that exact (row, state) a real,
// unambiguous match — the fixture 6/6b Menu shape extended with a second story that resolves
// `selection`'s own hover directly, so `selection`'s tainted cell drops the note while `actions`'s
// (nothing else covers it) still keeps it.
const BOARD_MIXED_STORIES_SOURCE = `
import { Board } from './index'
const meta = { component: Board, args: {} }
export default meta

export const CountryHoverRevealed = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Country:' } },
}

export const ChooseHoverRevealed = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Choose' } },
}
`

test('a tainted cell drops the note once a different story gives that exact row/state a real, unambiguous match', () => {
  const componentDirs = [
    { segment: 'composites', name: 'Board' },
    { segment: 'primitives', name: 'Menu' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/composites/Board/index.tsx', BOARD_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Board/Board.stories.tsx',
      BOARD_MIXED_STORIES_SOURCE,
    ],
    ['/repo/packages/design-system/src/primitives/Menu/index.tsx', MENU_INDEX_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const matrix = computed.matrices.Menu
  const actionsRow = matrix.find((r) => r.variantSize === 'actions')
  const selectionRow = matrix.find((r) => r.variantSize === 'selection')
  assert.match(actionsRow.hover[0], /^unresolved: /)
  assert.deepEqual(selectionRow.hover, ['Board:ChooseHoverRevealed'])
  assert.equal(computed.ambiguitySummary.taintedCells, 2)
  assert.equal(computed.ambiguitySummary.kept, 1)
  assert.equal(computed.ambiguitySummary.dropped, 1)
})

// --- Fixture 6c: a JSX candidate's own static axis and the axis its own force-state resolves to
// per story disagree (T594's REJECT on #80, item 2). `Widget`'s real button carries a literal
// `variant="ghost"` but a *dynamic* `size` prop — the same shape `FavouriteToggle`'s own real
// button and `Dialog`'s own two `Button` instances carry live in this tree. Pre-fix, the JSX
// candidate's own `rest` entry filed at `ghost|unresolved` (the static axis, size never a literal)
// while the same source line's own story-resolved match — `size` resolved to `'md'` per story —
// filed its `hover` cell at `ghost|md` instead: one source line in two rows, the first reading a
// confirmed `'none'` over a comparison that actually found a match on the second. Built directly
// against `buildAxisMatrix` (the function item 2 changed) rather than through the full
// `computeStateCoverage` file-parsing pipeline, the same level fixture 6a
// ("buildAxisMatrix renders a play-driven focus-visible match…") already uses. --------------------

function redirectFixtureInstances() {
  return [
    {
      kind: 'jsx',
      componentKey: 'composites/Widget',
      file: 'composites/Widget/index.tsx',
      line: 6,
      variant: { value: 'ghost', resolved: 'explicit' },
      size: { value: null, resolved: 'unresolved' },
      disabled: false,
    },
    {
      kind: 'composed-story',
      componentKey: 'composites/Widget',
      file: 'composites/Widget/Widget.stories.tsx',
      storyName: 'Hover',
      variant: { value: 'ghost', resolved: 'explicit' },
      size: { value: 'md', resolved: 'resolved-from-story' },
      forced: { state: 'hover', role: 'button', name: 'Toggle', selector: null, nth: null },
      playFocus: null,
      sourceLine: 6,
      sourceFile: 'composites/Widget/index.tsx',
    },
  ]
}

test("buildAxisMatrix (red first, pre-fix shape): a story-resolved match must not leave its own JSX candidate's static row reading a plain none", () => {
  // This is the contrast the fix must pass, proven directly against the row rather than against
  // the fix's own implementation: the row carrying the JSX candidate's own `rest` entry must never
  // claim a bare `'none'` once a story elsewhere resolved a match against that exact source line.
  const matrix = buildAxisMatrix('Button', redirectFixtureInstances())
  const unresolvedRow = matrix.find((r) => r.variantSize === 'ghost|unresolved')
  assert.ok(unresolvedRow, 'the static, unresolved-size row must still exist (a real rest entry)')
  assert.ok(unresolvedRow.rest[0].includes('composites/Widget'))
  assert.notDeepEqual(
    unresolvedRow.hover,
    ['none'],
    'a confirmed absence would be false: a story elsewhere matched this exact source line',
  )
})

test("buildAxisMatrix: the unresolved row's hover cell points at the row the story actually resolved to, not a bare 'unresolved' with no destination", () => {
  const matrix = buildAxisMatrix('Button', redirectFixtureInstances())
  const unresolvedRow = matrix.find((r) => r.variantSize === 'ghost|unresolved')
  const resolvedRow = matrix.find((r) => r.variantSize === 'ghost|md')
  assert.ok(resolvedRow, "the story's own resolved axis ('md') gets its own row")
  assert.deepEqual(resolvedRow.hover, ['Widget:Hover'])
  assert.deepEqual(unresolvedRow.hover, ['unresolved: axis resolved only per story (→ ghost|md)'])
  // The states the story never forced stay a genuine, uncontested `'none'` — the fix is scoped to
  // the one state that actually resolved elsewhere, not a blanket redirect for the whole row.
  assert.deepEqual(unresolvedRow.active, ['none'])
})

test('contrast: a JSX candidate with no story resolving it anywhere still reads a genuine none, not a manufactured redirect', () => {
  const [jsxOnly] = redirectFixtureInstances()
  const matrix = buildAxisMatrix('Button', [jsxOnly])
  const unresolvedRow = matrix.find((r) => r.variantSize === 'ghost|unresolved')
  assert.deepEqual(unresolvedRow.hover, ['none'])
})

test('contrast: a story-resolved match whose axis agrees with its own JSX row never needs a redirect (same row throughout)', () => {
  const instances = [
    {
      kind: 'jsx',
      componentKey: 'composites/Widget',
      file: 'composites/Widget/index.tsx',
      line: 6,
      variant: { value: 'ghost', resolved: 'explicit' },
      size: { value: 'md', resolved: 'explicit' },
      disabled: false,
    },
    {
      kind: 'composed-story',
      componentKey: 'composites/Widget',
      file: 'composites/Widget/Widget.stories.tsx',
      storyName: 'Hover',
      variant: { value: 'ghost', resolved: 'explicit' },
      size: { value: 'md', resolved: 'explicit' },
      forced: { state: 'hover', role: 'button', name: 'Toggle', selector: null, nth: null },
      playFocus: null,
      sourceLine: 6,
      sourceFile: 'composites/Widget/index.tsx',
    },
  ]
  const matrix = buildAxisMatrix('Button', instances)
  assert.equal(matrix.length, 1)
  assert.deepEqual(matrix[0].hover, ['Widget:Hover'])
})

// --- extractPseudoClasses / resolveClassParts, the primitives everything above is built from ------

test('resolveClassParts resolves a cx() call over string literals, a ternary and a same-file const', () => {
  const source = `
const focusRing = 'focus-visible:outline-2'
const el = <a className={cx('base', invalid ? 'border-danger' : 'border-strong', focusRing)} />
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.length, 1)
  assert.equal(found[0].focusVisible, 'focus-visible:outline-2')
})

// T594's row-8 remediation, item found while auditing Record 1: a `label` only counts as a local
// interactive element where it *wraps* a control (a nested JSX descendant), never for the far more
// common `htmlFor`/sibling-`input` association — the shape `SearchBox`, `ThirdPartyObjectionForm`
// and `Field` all use, painting no state of their own on the label itself.
test('findLocalElements does not count a label associated by htmlFor to a sibling input as a local interactive element', () => {
  const source = `
function Widget() {
  return (
    <div>
      <label htmlFor="name" className="font-sans text-sm">Name</label>
      <input id="name" />
    </div>
  )
}
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(
    found.find((el) => el.tag === 'label'),
    undefined,
  )
})

// Contrast: a label that nests its control as a real JSX child (`AccountErasurePanel`'s own
// acknowledgement checkbox shape) still counts.
test('findLocalElements counts a label that wraps its control as a direct JSX child', () => {
  const source = `
function Widget() {
  return (
    <label className="flex items-center gap-2">
      <input type="checkbox" />
      Acknowledge
    </label>
  )
}
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.ok(found.some((el) => el.tag === 'label'))
})

test('extractPseudoClasses returns null for a state with no matching utility', () => {
  assert.deepEqual(extractPseudoClasses(['bg-surface text-text-primary']), {
    hover: null,
    'focus-visible': null,
    active: null,
    focus: null,
  })
})

// Finding 10: `focus:` (real `:focus`, painted on any focus — pointer or keyboard) is captured
// alongside the three state pseudo-classes, and is never confused with `focus-visible:` even when
// both appear back-to-back in the same class string (`SiteHeader`'s skip link shape).
test('extractPseudoClasses captures focus: separately from focus-visible:, with no cross-match', () => {
  const result = extractPseudoClasses([
    'sr-only focus:not-sr-only focus:fixed focus-visible:outline-2 focus-visible:outline-focus-ring',
  ])
  assert.equal(result.focus, 'focus:not-sr-only focus:fixed')
  assert.equal(result['focus-visible'], 'focus-visible:outline-2 focus-visible:outline-focus-ring')
})

// --- Orchestrator remediation 2a: `aria-hidden` is excluded from every role-based candidate pool,
// the same way Playwright's own getByRole treats it — FavouriteToggle's own decoy `Button/ghost`. ---

const ARIA_HIDDEN_DECOY_SOURCE = `
function FavouriteToggle({ favourited }) {
  return (
    <span>
      <Button aria-hidden tabIndex={-1} variant="ghost">Decoy</Button>
      <Button variant="ghost" onClick={toggle}>Real</Button>
    </span>
  )
}
`

test('findPrimitiveInstances marks an aria-hidden instance, and resolveNameMatch excludes it from the pool', () => {
  const sourceFile = parse(ARIA_HIDDEN_DECOY_SOURCE)
  const found = findPrimitiveInstances(sourceFile, 'fixture.tsx', {
    Button: { variant: 'secondary', size: 'md' },
  })
  assert.equal(found.length, 2)
  assert.equal(found[0].ariaHidden, true)
  assert.equal(found[1].ariaHidden, false)
  const pool = found.filter((f) => !f.ariaHidden)
  assert.equal(pool.length, 1)
  const verdict = resolveNameMatch({ candidate: pool[0], pool, name: null, nth: null })
  assert.equal(verdict, 'match')
})

// --- Orchestrator remediation 2b: a story's own `args` (merged with the meta's default `args`)
// supplies a literal name a `visualForceState` matches even when the JSX itself renders only
// `{primaryAction.label}` — Dialog's own shape. -----------------------------------------------

test('extractStringLiteralsDeep finds a string literal nested inside an object literal', () => {
  const source = `const args = { primaryAction: { label: 'Turn it off', onClick: fn } }`
  const sourceFile = parse(source)
  const decl = sourceFile.statements[0].declarationList.declarations[0]
  const found = extractStringLiteralsDeep(decl.initializer)
  assert.ok(found.has('Turn it off'))
})

test("storyArgsStringLiterals merges a story's own args with its meta's default args", () => {
  const source = `
const meta = { component: Dialog, args: { heading: 'Default heading' } }
export default meta
export const FocusVisible = {
  parameters: { visualForceState: { state: 'focus-visible', role: 'button', name: 'Turn it off' } },
  args: { primaryAction: { label: 'Turn it off' } },
}
`
  const sourceFile = parse(source)
  const metaObj = findMeta(sourceFile)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const literals = storyArgsStringLiterals(metaObj, node)
  assert.ok(literals.has('Turn it off'))
  assert.ok(literals.has('Default heading'))
})

test("resolveNameMatch resolves a name only findable in args (not in any candidate's JSX text) via the sole iteration candidate", () => {
  // Two candidates share role `button`; neither carries literal JSX text (`{primaryAction.label}`,
  // `{secondaryAction.label}`), so only one — the one the caller marks `isInsideIteration` — can be
  // picked from an args-only name; this fixture stands in for Dialog's own two dynamic-label
  // actions, using iteration as the disambiguator this fixture controls directly.
  const primary = { text: '', isInsideIteration: true }
  const secondary = { text: '', isInsideIteration: false }
  const pool = [primary, secondary]
  const argsLiterals = new Set(['Turn it off'])
  assert.equal(
    resolveNameMatch({ candidate: primary, pool, name: 'Turn it off', nth: null, argsLiterals }),
    'match',
  )
  assert.equal(
    resolveNameMatch({ candidate: secondary, pool, name: 'Turn it off', nth: null, argsLiterals }),
    'reject',
  )
})

test('resolveNameMatch is ambiguous when a name is in args but two candidates are both inside an iteration', () => {
  const a = { text: '', isInsideIteration: true }
  const b = { text: '', isInsideIteration: true }
  const pool = [a, b]
  const argsLiterals = new Set(['Matches'])
  assert.equal(
    resolveNameMatch({ candidate: a, pool, name: 'Matches', nth: null, argsLiterals }),
    'ambiguous',
  )
})

// --- Orchestrator remediation 2c: `nth` is resolved against inline (non-helper) candidates sorted
// by source position — PrivacyNotice's own `nth: 0` shape (a literal array's first rendered item,
// excluding a reusable helper function's own declaration site from the ordering). -----------------

test('resolveNameMatch resolves nth against inline candidates sorted by line, excluding helper declarations', () => {
  const inlineFirst = { isHelper: false, line: 490 }
  const inlineSecond = { isHelper: false, line: 740 }
  const helperRecipe = { isHelper: true, line: 242 } // declared above, but not a render position
  const pool = [helperRecipe, inlineFirst, inlineSecond]
  assert.equal(resolveNameMatch({ candidate: inlineFirst, pool, name: null, nth: 0 }), 'match')
  assert.equal(resolveNameMatch({ candidate: inlineSecond, pool, name: null, nth: 0 }), 'reject')
  // T594 part A: the candidate under test is itself the excluded helper — its own real render
  // position relative to `inlineFirst`/`inlineSecond` is unknown, so this pass can neither place it
  // at `nth` nor confirm it is not there. A confident 'reject' overstated that as settled knowledge
  // this pass never established (`PrivacyNotice`'s own `InlineLink`, `README.md`'s row-8 sweep).
  assert.equal(resolveNameMatch({ candidate: helperRecipe, pool, name: null, nth: 0 }), 'ambiguous')
})

test('resolveNameMatch is ambiguous (not none) when nth exceeds the orderable pool', () => {
  const only = { isHelper: false, line: 100 }
  assert.equal(resolveNameMatch({ candidate: only, pool: [only], name: null, nth: 5 }), 'ambiguous')
})

// T594's REJECT on #80, item 5: two candidates both literally carrying the forced name used to
// each independently return `'match'` — the caller (`resolveComposedStoryMatches`) then let
// whichever a plain `for` loop visited last silently overwrite `matchedCandidate`, crediting one
// frame to both elements. Zero live occurrences in this tree today; this is the one ambiguity
// shape B1's own fixture sweep never covers.
test('resolveNameMatch is ambiguous, not a silent double match, when two candidates both literally carry the forced name', () => {
  const a = { text: 'Turn it off' }
  const b = { text: 'Turn it off' }
  const pool = [a, b]
  assert.equal(
    resolveNameMatch({ candidate: a, pool, name: 'Turn it off', nth: null }),
    'ambiguous',
  )
  assert.equal(
    resolveNameMatch({ candidate: b, pool, name: 'Turn it off', nth: null }),
    'ambiguous',
  )
})

test('contrast: resolveNameMatch still matches the sole candidate directly when only one carries the forced name', () => {
  const a = { text: 'Turn it off' }
  const b = { text: 'Keep it on' }
  const pool = [a, b]
  assert.equal(resolveNameMatch({ candidate: a, pool, name: 'Turn it off', nth: null }), 'match')
  assert.equal(resolveNameMatch({ candidate: b, pool, name: 'Turn it off', nth: null }), 'reject')
})

// --- Orchestrator remediation 1: a cell distinguishes a confirmed 'none' from an 'unresolved:
// <reason>' it could not settle — buildElementMatrix's own contract. -------------------------------

test('buildElementMatrix reports "unresolved: ..." rather than "none" when a role matches but cannot be settled', () => {
  const elements = [
    {
      tag: 'a',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'f.tsx',
      line: 10,
    },
    {
      tag: 'a',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'f.tsx',
      line: 20,
    },
  ]
  const storyStates = [
    {
      exportName: 'Active',
      forced: { state: 'active', role: 'link', name: null, nth: null },
      playFocus: null,
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.equal(rows.length, 2)
  assert.match(rows[0].active[0], /^unresolved:/)
  assert.match(rows[1].active[0], /^unresolved:/)
})

test('buildElementMatrix reports "none" (not unresolved) when no force-state shares the role at all', () => {
  const elements = [
    {
      tag: 'a',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'f.tsx',
      line: 10,
    },
  ]
  const storyStates = [
    {
      exportName: 'Hover',
      forced: { state: 'hover', role: 'button', name: null, nth: null },
      playFocus: null,
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].active, ['none'])
})

// --- Orchestrator remediation, item 1: structural consistency mode ------------------------------

const FIXTURE_COMPUTED = {
  componentDirCount: 1,
  localElements: [
    {
      componentKey: 'primitives/Widget',
      elements: [
        {
          tag: 'a',
          role: null,
          tabIndex: null,
          hover: 'hover:underline',
          focusVisible: null,
          active: null,
          ariaHidden: false,
          file: 'packages/design-system/src/primitives/Widget/index.tsx',
          line: 12,
          coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
        },
      ],
    },
  ],
  matrices: {
    Widget: [
      {
        variantSize: '(no local interactive element)',
        rest: ['N/A'],
        hover: ['N/A'],
        focusVisible: ['N/A'],
        active: ['N/A'],
        disabled: ['N/A'],
      },
    ],
  },
}

test('extractGeneratedRegion/replaceGeneratedRegion round-trip the marker-delimited region', () => {
  const region = renderGeneratedRegion(FIXTURE_COMPUTED)
  const readme = `# Title\n\nSome prose.\n\n${region}\n\nMore prose.\n`
  assert.equal(extractGeneratedRegion(readme), region)
  const replaced = replaceGeneratedRegion(
    readme,
    '<!-- state-coverage:begin -->X<!-- state-coverage:end -->',
  )
  assert.match(replaced, /X/)
  assert.match(replaced, /More prose\./)
})

test('check mode detects a hand-edited generated cell via extractGeneratedRegion inequality', () => {
  const region = renderGeneratedRegion(FIXTURE_COMPUTED)
  const readme = `# Title\n\n${region}\n`
  const formatted = formatWithPrettier(readme)
  const formattedRegion = extractGeneratedRegion(formatted)

  // Hand-edit one generated cell — exactly the shape the orchestrator's review found: the embedded
  // record says `none`/unresolved, the visible text claims otherwise. Everything else (the source
  // this would be computed from) is unchanged.
  const corruptedReadme = formatted.replace('none → none', 'hover:underline → CoveredStory')
  const corruptedRegion = extractGeneratedRegion(corruptedReadme)
  assert.notEqual(corruptedRegion, formattedRegion)
})

// The test above only ever proves a hand-corrupted region differs from a fixture-derived one — it
// never runs the real check path, `main()`'s own comparison of a *committed* region against one
// computed fresh from real source, so a defect in `computeStateCoverage` itself (as opposed to
// `renderGeneratedRegion`'s formatting) could never fail it. This drives the same pipeline `main()`
// does — `computeStateCoverage` over a real fixture source tree, then `renderGeneratedRegion` /
// `replaceGeneratedRegion` / `formatWithPrettier` — against a *stale* committed region, standing in
// for source that changed without `--write` being re-run.
const REAL_CHECK_FIXTURE_SOURCE = `
function Widget() {
  return <a className="hover:underline">Contents</a>
}
`

test('the real check path fails when source has moved and the committed region was never regenerated', () => {
  const componentDirs = [{ segment: 'primitives', name: 'Widget' }]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Widget/index.tsx', REAL_CHECK_FIXTURE_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const freshRegion = renderGeneratedRegion(computed)
  const staleReadme = `# Title\n\n${renderGeneratedRegion(FIXTURE_COMPUTED)}\n`
  const freshReadme = formatWithPrettier(replaceGeneratedRegion(staleReadme, freshRegion))
  const freshFormattedRegion = extractGeneratedRegion(freshReadme)
  // The committed text (stale — a different fixture's own region) disagrees with what real source
  // computes today.
  const committedRegion = extractGeneratedRegion(formatWithPrettier(staleReadme))
  assert.notEqual(committedRegion, freshFormattedRegion)
})

test('contrast: the real check path passes once the committed region is regenerated from the same source', () => {
  const componentDirs = [{ segment: 'primitives', name: 'Widget' }]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Widget/index.tsx', REAL_CHECK_FIXTURE_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const freshRegion = renderGeneratedRegion(computed)
  const readme = `# Title\n\n${freshRegion}\n`
  const written = formatWithPrettier(readme)
  const writtenRegion = extractGeneratedRegion(written)
  // Re-running check mode against the exact text --write just produced must agree with itself.
  const recomputed = computeStateCoverage({ componentDirs, filesByPath })
  const recomputedRegion = extractGeneratedRegion(
    formatWithPrettier(replaceGeneratedRegion(written, renderGeneratedRegion(recomputed))),
  )
  assert.equal(writtenRegion, recomputedRegion)
})

// --- Orchestrator remediation (round 3): four behaviours that moved cells, each with a fixture and
// a contrast case. Items 3 and 4 are regressions — their own pre-fix failing output is pasted in
// the task's hand-back, captured by temporarily reverting each fix in turn. -----------------------

// 1. A conditional branch picked by a literal boolean arg (`FavouriteToggle`'s own
// `if (!authenticated) { return <SignedOutControl /> } ... return <Button>Real</Button>` shape).

const CONDITIONAL_BRANCH_SOURCE = `
function SignedOutControl() {
  return <Button variant="ghost">Sign in</Button>
}
function Toggle({ authenticated }) {
  if (!authenticated) {
    return <SignedOutControl />
  }
  return <Button variant="ghost">Real</Button>
}
`

test('a conditional branch chosen by a literal boolean arg resolves reachability both ways', () => {
  const sourceFile = parse(CONDITIONAL_BRANCH_SOURCE)
  const helperGuards = findHelperInvocationGuards(sourceFile)
  const defaults = { Button: { variant: 'secondary', size: 'md' } }
  const found = findPrimitiveInstances(sourceFile, 'fixture.tsx', defaults, [], helperGuards)
  const signedOut = found.find((f) => f.text === 'Sign in')
  const real = found.find((f) => f.text === 'Real')
  assert.ok(signedOut && real)

  const scopeAuthTrue = new Map([['authenticated', { resolved: true, value: true }]])
  assert.equal(evaluateGuards(signedOut.guards, scopeAuthTrue), 'unreached')
  assert.equal(evaluateGuards(real.guards, scopeAuthTrue), 'reached')

  const scopeAuthFalse = new Map([['authenticated', { resolved: true, value: false }]])
  assert.equal(evaluateGuards(signedOut.guards, scopeAuthFalse), 'reached')
  assert.equal(evaluateGuards(real.guards, scopeAuthFalse), 'unreached')
})

test('contrast: a guard whose operand has no literal source (no arg, no default) stays unresolved', () => {
  const sourceFile = parse(CONDITIONAL_BRANCH_SOURCE)
  const helperGuards = findHelperInvocationGuards(sourceFile)
  const defaults = { Button: { variant: 'secondary', size: 'md' } }
  const found = findPrimitiveInstances(sourceFile, 'fixture.tsx', defaults, [], helperGuards)
  const real = found.find((f) => f.text === 'Real')
  // `authenticated` is absent from this scope entirely — no arg supplied it, and the fixture's own
  // `Toggle` gives it no default, so nothing resolves it.
  assert.equal(evaluateGuards(real.guards, new Map()), 'unresolved')
})

test('contrast: a guard whose operand comes from a function call (never a literal) stays unresolved', () => {
  const sourceFile = parse(CONDITIONAL_BRANCH_SOURCE)
  const helperGuards = findHelperInvocationGuards(sourceFile)
  const defaults = { Button: { variant: 'secondary', size: 'md' } }
  const found = findPrimitiveInstances(sourceFile, 'fixture.tsx', defaults, [], helperGuards)
  const real = found.find((f) => f.text === 'Real')
  // `evaluateExpr` never calls a function — an identifier whose own "value" is a call result is
  // simply absent from the scope a real story's own args would ever populate this way.
  const scope = new Map([['authenticated', { resolved: false, value: undefined }]])
  assert.equal(evaluateGuards(real.guards, scope), 'unresolved')
})

// 2. A nested-object arg label matched by name, end to end through `resolveComposedStoryMatches` —
// `Dialog`'s own `{ primaryAction: { label: 'Turn it off' } }` shape, two instances whose labels
// come from different args values, each resolving to the right one.

const DIALOG_LIKE_SOURCE = `
function Dialog({ primaryAction, secondaryAction }) {
  return (
    <div>
      <Button variant={primaryAction.variant ?? 'destructive'} size="lg">{primaryAction.label}</Button>
      <Button variant={secondaryAction.variant ?? 'secondary'} size="lg">{secondaryAction.label}</Button>
    </div>
  )
}
`

function buildDialogInstances() {
  const sourceFile = parse(DIALOG_LIKE_SOURCE, 'index.tsx')
  const found = findPrimitiveInstances(sourceFile, 'index.tsx', {
    Button: { variant: 'secondary', size: 'md' },
  })
  const instancesByPrimitive = new Map([
    ['Button', found.map((f) => ({ ...f, kind: 'jsx', componentKey: 'primitives/Dialog' }))],
    ['Link', []],
    ['Field', []],
    ['Menu', []],
  ])
  return instancesByPrimitive
}

test('a nested-object arg label resolves a visualForceState name end to end, for either instance', () => {
  const propsScope = new Map([
    ['primaryAction', { resolved: true, value: { label: 'Turn it off' } }],
    ['secondaryAction', { resolved: true, value: { label: 'Keep it on' } }],
  ])
  const makePending = (name) => [
    {
      componentKey: 'primitives/Dialog',
      file: 'Dialog.stories.tsx',
      exportName: 'FocusVisible',
      forced: { state: 'focus-visible', role: 'button', name, selector: null, nth: null },
      storyLineRange: null,
      argsLiterals: new Set(),
      propsScope,
    },
  ]

  const primaryInstances = buildDialogInstances()
  resolveComposedStoryMatches(makePending('Turn it off'), primaryInstances)
  const primaryMatched = primaryInstances.get('Button').filter((i) => i.kind === 'composed-story')
  assert.equal(primaryMatched.length, 1)
  assert.equal(primaryMatched[0].variant.value, 'destructive')
  assert.equal(primaryMatched[0].size.value, 'lg')

  const secondaryInstances = buildDialogInstances()
  resolveComposedStoryMatches(makePending('Keep it on'), secondaryInstances)
  const secondaryMatched = secondaryInstances
    .get('Button')
    .filter((i) => i.kind === 'composed-story')
  assert.equal(secondaryMatched.length, 1)
  assert.equal(secondaryMatched[0].variant.value, 'secondary')
})

test('contrast: a name with no literal arg anywhere is unresolved, never a silent none (T594 REJECT on #80: none must be positive knowledge)', () => {
  const propsScope = new Map([
    ['primaryAction', { resolved: true, value: { label: 'Turn it off' } }],
    ['secondaryAction', { resolved: true, value: { label: 'Keep it on' } }],
  ])
  const pending = [
    {
      componentKey: 'primitives/Dialog',
      file: 'Dialog.stories.tsx',
      exportName: 'FocusVisible',
      forced: {
        state: 'focus-visible',
        role: 'button',
        name: 'Not In Args',
        selector: null,
        nth: null,
      },
      storyLineRange: null,
      argsLiterals: new Set(),
      propsScope,
    },
  ]
  const instancesByPrimitive = buildDialogInstances()
  resolveComposedStoryMatches(pending, instancesByPrimitive)
  const matched = instancesByPrimitive.get('Button').filter((i) => i.kind === 'composed-story')
  const unresolved = instancesByPrimitive
    .get('Button')
    .filter((i) => i.kind === 'composed-story-unresolved')
  assert.equal(matched.length, 0, 'never guessed')
  assert.equal(unresolved.length, 1, 'unaccounted-for name renders unresolved, not a silent none')
})

// 3. Regression: a `selector`-targeted force-state (no `role`) must never be attributed to a
// `Button` by role-wildcard matching. `FavouritesList`'s own shape — two `Button`s, one
// `selector`-targeted force-state naming neither.

const TWO_BUTTONS_SOURCE = `
function FavouritesListLike() {
  return (
    <div>
      <Button variant="primary" size="lg">Sign in</Button>
      <Button variant="primary" size="lg">Try again</Button>
    </div>
  )
}
`

test('a selector-targeted force-state (no role) is never attributed to any Button by wildcard', () => {
  const sourceFile = parse(TWO_BUTTONS_SOURCE, 'index.tsx')
  const found = findPrimitiveInstances(sourceFile, 'index.tsx', {
    Button: { variant: 'secondary', size: 'md' },
  })
  const instancesByPrimitive = new Map([
    [
      'Button',
      found.map((f) => ({ ...f, kind: 'jsx', componentKey: 'composites/FavouritesList' })),
    ],
    ['Link', []],
    ['Field', []],
    ['Menu', []],
  ])
  const pending = [
    {
      componentKey: 'composites/FavouritesList',
      file: 'FavouritesList.stories.tsx',
      exportName: 'Hover',
      forced: {
        state: 'hover',
        role: null,
        name: null,
        selector: 'a[href="/players/1"]',
        nth: null,
      },
      storyLineRange: null,
      argsLiterals: new Set(),
      propsScope: new Map(),
    },
  ]
  resolveComposedStoryMatches(pending, instancesByPrimitive)
  const matched = instancesByPrimitive.get('Button').filter((i) => i.kind === 'composed-story')
  const unresolved = instancesByPrimitive
    .get('Button')
    .filter((i) => i.kind === 'composed-story-unresolved')
  assert.equal(matched.length, 0, 'a selector target must not be attributed to either Button')
  assert.equal(
    unresolved.length,
    0,
    'a selector target is not a Button candidate at all — not even ambiguous',
  )
})

// 4. Regression: a `role` attribute that is present but dynamic must never fall back to its tag's
// intrinsic role — `Menu`'s own trigger (a plain `<button>`) beside `MenuItemRow`'s
// `role={variant === 'selection' ? 'menuitemradio' : 'menuitem'}`.

// --- REJECT on #80: 'none' must be positive knowledge. A className the parser could not fully
// resolve (a call to an unknown function) must not render as a confirmed 'none' hover/focus/active
// class — that claims certainty the parser does not have. Contrast with a fully-resolved className
// that genuinely carries no pseudo-class utility, which stays 'none'. -----------------------------

const UNRESOLVED_CLASS_SOURCE = `
function Widget() {
  return <button className={getClasses()}>Click</button>
}
`

test('findLocalElements records classUnresolvedRefs when the className cannot be resolved', () => {
  const sourceFile = parse(UNRESOLVED_CLASS_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.length, 1)
  assert.equal(found[0].hover, null)
  assert.ok(found[0].classUnresolvedRefs.length > 0)
})

test("renderRecord1 renders 'unresolved: ...' rather than a confirmed 'none' when the className itself could not be resolved", () => {
  const sourceFile = parse(UNRESOLVED_CLASS_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const [el] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          { ...el, coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] } },
        ],
      },
    ],
  }
  const rendered = renderRecord1(computed)
  assert.doesNotMatch(rendered, /\bnone → none\b/)
  assert.match(rendered, /unresolved: className not fully resolved/)
})

test("renderRecord1 keeps a confirmed 'none' when the className is fully resolved and genuinely carries no pseudo-class utility (contrast)", () => {
  const source = `const el = <button className="bg-surface text-text-primary">Click</button>`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [el] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(el.classUnresolvedRefs.length, 0)
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          { ...el, coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] } },
        ],
      },
    ],
  }
  const rendered = renderRecord1(computed)
  assert.match(rendered, /\bnone → none\b/)
})

// --- Row 8's own recount (`reviewer`'s fourth REJECT on PR #80, item B): `countRecord1Cells` used
// to read `el.coveredBy` alone, so a cell whose *left* half rendered 'unresolved: className not
// fully resolved' was still counted by its right half — `none` when `coveredBy` said `none`,
// `covered` when a story happened to be named there. Both are wrong: the element's own class
// expression was never resolved, so neither half is knowledge this pass actually has. A cell whose
// class half is unresolved must count as `unresolved` regardless of what its story half says. ------

test('countRecord1Cells: a cell whose own class half is unresolved counts as unresolved even when its story half reads none', () => {
  const sourceFile = parse(UNRESOLVED_CLASS_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const [el] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          { ...el, coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] } },
        ],
      },
    ],
    matrices: {},
  }
  // Pre-fix, this rendered `unresolved: className not fully resolved → none` (asserted above) but
  // counted as `none` on all three states, since `countRecord1Cells` only ever read `coveredBy`.
  assert.deepEqual(countRecord1Cells(computed), { none: 0, unresolved: 3, covered: 0 })
})

test('countRecord1Cells: a cell whose own class half is unresolved counts as unresolved even when its story half names a real story (contrast — the other wrong half of the pre-fix bug)', () => {
  const sourceFile = parse(UNRESOLVED_CLASS_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const [el] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            ...el,
            coveredBy: { hover: ['SomeStory'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  // Pre-fix, hover's right half named a real story, so it counted as `covered` even though the
  // left half of the same cell was never resolved — the "three counted covered" half of the eight
  // cells row 8's own recount found.
  assert.deepEqual(countRecord1Cells(computed), { none: 0, unresolved: 3, covered: 0 })
})

test('countRecord1Cells: a fully-resolved className that genuinely carries no pseudo-class utility still counts a confirmed none (contrast)', () => {
  const source = `const el = <button className="bg-surface text-text-primary">Click</button>`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [el] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(el.classUnresolvedRefs.length, 0)
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          { ...el, coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] } },
        ],
      },
    ],
    matrices: {},
  }
  assert.deepEqual(countRecord1Cells(computed), { none: 3, unresolved: 0, covered: 0 })
})

// --- REJECT on #80: play-driven focus is 'unresolved', not covered. `tests/visual/stories.spec.ts`
// says a script `.focus()` matches `:focus-visible` on a fresh page *and* `Page.stories.tsx`'s own
// `play()` `.focus()` captured the same frame as `Default` — the script cannot know statically
// which case a given story is, so a play-driven match must never count as a confirmed frame. -----

test('buildElementMatrix renders a play-driven focus match as unresolved, not as covered', () => {
  const elements = [
    {
      tag: 'a',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'f.tsx',
      line: 10,
    },
  ]
  const storyStates = [
    {
      exportName: 'EscapeReturnsFocusToTrigger',
      forced: null,
      playFocus: { role: 'link', name: null },
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.equal(rows[0].focusVisible.length, 1)
  assert.match(rows[0].focusVisible[0], /^unresolved:/)
  assert.match(rows[0].focusVisible[0], /play-driven; frame not provable statically/)
  assert.match(rows[0].focusVisible[0], /EscapeReturnsFocusToTrigger/)
})

test('buildAxisMatrix renders a play-driven focus-visible match as unresolved, not as covered (record 3)', () => {
  const instances = [
    {
      primitive: 'Menu',
      kind: 'own-story',
      componentKey: 'primitives/Menu',
      file: 'Menu.stories.tsx',
      storyName: 'EscapeReturnsFocusToTrigger',
      variant: { value: 'actions', resolved: 'explicit' },
      size: { value: null, resolved: 'n/a' },
      forced: null,
      playFocus: { role: 'button', name: null },
    },
  ]
  const matrix = buildAxisMatrix('Menu', instances)
  const row = matrix.find((r) => r.variantSize === 'actions')
  assert.equal(row.focusVisible.length, 1)
  assert.match(row.focusVisible[0], /^unresolved:/)
  assert.match(row.focusVisible[0], /play-driven; frame not provable statically/)
  assert.match(row.focusVisible[0], /EscapeReturnsFocusToTrigger/)
})

// --- REJECT on #80, item 4: own story files skip their JSX and take axis values from args only,
// so Button.stories.tsx's Disabled/AllVariants/RealisticPageActions (real JSX in a `render:`
// function, no `args` at all) land in the primitive's default row (`secondary|md`) instead of the
// variant/size their own JSX actually renders. -----------------------------------------------------

const BUTTON_RENDER_DISABLED_SOURCE = `
export const Disabled = {
  render: () => (
    <div>
      <Button variant="primary" size="lg" disabled>
        Continue with Steam
      </Button>
    </div>
  ),
}
`

test('findOwnStoryRenderInstances parses literal JSX inside a render() function, never falling back to defaults', () => {
  const sourceFile = parse(BUTTON_RENDER_DISABLED_SOURCE, 'Button.stories.tsx')
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const found = findOwnStoryRenderInstances(node, 'Button', { variant: 'secondary', size: 'md' })
  assert.equal(found.length, 1)
  assert.deepEqual(found[0].variant, { value: 'primary', resolved: 'explicit' })
  assert.deepEqual(found[0].size, { value: 'lg', resolved: 'explicit' })
  assert.equal(found[0].disabled, true)
})

const BUTTON_RENDER_ALL_VARIANTS_SOURCE = `
export const AllVariants = {
  render: () => (
    <div>
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  ),
}
`

test('findOwnStoryRenderInstances finds every JSX instance in a render() with more than one', () => {
  const sourceFile = parse(BUTTON_RENDER_ALL_VARIANTS_SOURCE, 'Button.stories.tsx')
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const found = findOwnStoryRenderInstances(node, 'Button', { variant: 'secondary', size: 'md' })
  assert.deepEqual(
    found.map((f) => f.variant.value),
    ['primary', 'secondary', 'ghost', 'destructive'],
  )
  // No `size` attribute anywhere in this render — falls back to the primitive default, not `n/a`.
  assert.deepEqual(found[0].size, { value: 'md', resolved: 'default' })
})

test('findOwnStoryRenderInstances returns null for a plain args-driven story (contrast, no render at all)', () => {
  const sourceFile = parse(`export const Primary = { args: { variant: 'primary', size: 'lg' } }`)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const found = findOwnStoryRenderInstances(node, 'Button', { variant: 'secondary', size: 'md' })
  assert.equal(found, null)
})

// T594's row-8 remediation of #80's hand-back, item found while auditing F18: a story's own custom
// `render` can pass a prop through `{...args}` (a spread, no literal attribute at all) rather than
// a literal JSX prop — `Field.stories.tsx`'s own shape, every story. Falling straight to the
// primitive's *default* whenever a spread is present, as this function used to, silently merged
// `SizeLg`'s real `size: 'lg'` into the `md` row: no literal `size=` attribute exists anywhere in
// its `render` for `resolveProp`'s old spread branch to read.
const FIELD_RENDER_SPREAD_SOURCE = `
const meta = {
  component: Field,
  args: { label: 'Display name' },
}
export default meta
export const SizeLg = {
  args: { size: 'lg' },
  render: (args) => (
    <div className="max-w-xs">
      <Field {...args}>
        <input />
      </Field>
    </div>
  ),
}
`

test("findOwnStoryRenderInstances resolves a spread prop through the story's own args, not the primitive default (Field SizeLg shape)", () => {
  const sourceFile = parse(FIELD_RENDER_SPREAD_SOURCE, 'Field.stories.tsx')
  const metaObj = findMeta(sourceFile)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const found = findOwnStoryRenderInstances(node, 'Field', { size: 'md' }, metaObj)
  assert.equal(found.length, 1)
  assert.deepEqual(found[0].size, { value: 'lg', resolved: 'explicit' })
})

// Contrast: a spread story that does *not* override the axis prop still resolves to the
// primitive's default, via the same args-reading path rather than losing the value entirely — the
// shape every other Field story (`Default`, `Hover`, …) carries, size never mentioned in their own
// `args` at all.
const FIELD_RENDER_SPREAD_NO_OVERRIDE_SOURCE = `
const meta = {
  component: Field,
  args: { label: 'Search' },
}
export default meta
export const Default = {
  render: (args) => (
    <div>
      <Field {...args}>
        <input />
      </Field>
    </div>
  ),
}
`

test('findOwnStoryRenderInstances still falls back to the primitive default through a spread when the story never overrides the axis prop', () => {
  const sourceFile = parse(FIELD_RENDER_SPREAD_NO_OVERRIDE_SOURCE, 'Field.stories.tsx')
  const metaObj = findMeta(sourceFile)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const found = findOwnStoryRenderInstances(node, 'Field', { size: 'md' }, metaObj)
  assert.equal(found.length, 1)
  assert.deepEqual(found[0].size, { value: 'md', resolved: 'default' })
})

test('buildAxisMatrix credits disabled from a story whose own args admit a nested disabled: true (Menu items shape)', () => {
  const instances = [
    {
      primitive: 'Menu',
      kind: 'own-story',
      componentKey: 'primitives/Menu',
      file: 'Menu.stories.tsx',
      storyName: 'ActionsWithDisabledItem',
      variant: { value: 'actions', resolved: 'explicit' },
      size: { value: null, resolved: 'n/a' },
      disabled: true,
      forced: null,
      playFocus: null,
    },
  ]
  const matrix = buildAxisMatrix('Menu', instances)
  const row = matrix.find((r) => r.variantSize === 'actions')
  assert.deepEqual(row.disabled, ['Menu:ActionsWithDisabledItem'])
})

test("buildElementMatrix stops hard-coding disabled: ['none'] — credits a story whose args admit disabled: true, for an element that carries a disabled-capable attribute", () => {
  const elements = [
    {
      tag: 'button',
      role: 'unresolved',
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'f.tsx',
      line: 10,
      hasDisabledAttr: true,
    },
  ]
  const storyStates = [
    {
      exportName: 'ActionsWithDisabledItem',
      forced: null,
      playFocus: null,
      argsLiterals: new Set(),
      argsHasDisabledTrue: true,
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].disabled, ['ActionsWithDisabledItem'])
})

test('contrast: buildElementMatrix keeps a confirmed none when the element carries no disabled-capable attribute at all', () => {
  const elements = [
    {
      tag: 'a',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'f.tsx',
      line: 10,
      hasDisabledAttr: false,
    },
  ]
  const storyStates = [
    {
      exportName: 'SomeStory',
      forced: null,
      playFocus: null,
      argsLiterals: new Set(),
      argsHasDisabledTrue: true,
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].disabled, ['none'])
})

// --- T594 row 8 sweep, item 1: `disabled` gets the same `cellFor` redirect `variant`/`size`
// already had — a dynamic `disabled`/`loading` expression on a `Button`/`Link`/`Field`/`Menu`
// call site, resolved against a story's own merged args, never a false confirmed `none`. Routed
// through the real pipeline (`computeStateCoverage`), the same level fixture 6/6b already use, so
// this exercises `resolveDisabledFromStories` exactly as `computeStateCoverage` wires it, not a
// parallel hand-assembled shape that could drift from it unnoticed. -------------------------------

// `findVariantSizeDefaults`/`getComponentPropDefaults` read this the same way they read the real
// `primitives/Button/index.tsx` — `variant`/`size` default via destructuring, `disabled`/`loading`
// folded together the same real file does (`disabled={disabled || loading}`), so a call site that
// only ever sets `loading` is real disabled coverage, not a coincidence of this fixture.
const BUTTON_INDEX_SOURCE = `
export function Button({ variant = 'secondary', size = 'md', disabled, loading, children }) {
  return <button disabled={disabled || loading}>{children}</button>
}
`

// Fixture A — a prop-driven `disabled` resolved from a story's own `args` (`FavouriteToggle`'s own
// `Bounded` shape: `disabled={bounded}`, `bounded = atLimit && !favourited`, no `visualForceState`
// at all — only `args`).
const BOUNDED_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
export function Widget({ atLimit = false, favourited = false }) {
  const bounded = atLimit && !favourited
  return <Button variant="ghost" disabled={bounded}>Toggle</Button>
}
`
const BOUNDED_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const Bounded = { args: { atLimit: true, favourited: false } }
`

test("resolveDisabledFromStories (via computeStateCoverage): credits a prop-driven disabled resolved from a story's own args, not a false none", () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    ['/repo/packages/design-system/src/composites/Widget/index.tsx', BOUNDED_WIDGET_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      BOUNDED_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'ghost')
  assert.ok(row, 'ghost must exist — the real, static axis of this call site')
  assert.deepEqual(row.disabled, ['Widget:Bounded'])
})

// Fixture B — a `loading`-driven disabled, no `disabled` attribute on the call site at all
// (`FavouriteToggle`'s own `AddingInFlight`/`RemovingInFlight` shape).
const LOADING_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
export function Widget({ loading = false }) {
  return <Button variant="ghost" loading={loading}>Toggle</Button>
}
`
const LOADING_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const AddingInFlight = { args: { loading: true } }
`

test('resolveDisabledFromStories (via computeStateCoverage): credits a loading-driven disabled with no disabled attribute on the call site at all', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    ['/repo/packages/design-system/src/composites/Widget/index.tsx', LOADING_WIDGET_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      LOADING_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'ghost')
  assert.ok(row)
  assert.deepEqual(row.disabled, ['Widget:AddingInFlight'])
})

// Fixture C (contrast) — a `disabled` expression this pass genuinely cannot resolve from any
// story's own args (a function call over a prop, not a literal, a property access or any of the
// other shapes `evaluateExpr` handles) must stay `unresolved`, never fall back to a false `none`.
const UNRESOLVABLE_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
export function Widget({ status }) {
  return <Button variant="ghost" disabled={computeDisabled(status)}>Toggle</Button>
}
`
const UNRESOLVABLE_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const Default = { args: { status: 'idle' } }
`

test('contrast: resolveDisabledFromStories leaves disabled unresolved, never a false none, when the expression cannot be statically evaluated', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Widget/index.tsx',
      UNRESOLVABLE_WIDGET_INDEX_SOURCE,
    ],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      UNRESOLVABLE_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'ghost')
  assert.ok(row)
  assert.equal(row.disabled.length, 1)
  assert.match(row.disabled[0], /^unresolved: disabled not statically resolvable/)
})

// A candidate whose own guard is `'unreached'` for a given story (the same exclusion role-based
// matching already applies) is skipped outright — that story could not possibly render it, so it
// must contribute neither a credited match nor an unresolved reason.
const GUARDED_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
function SignedOutControl() {
  return <Button variant="ghost" disabled={someExternalFlag()}>Sign in</Button>
}
export function Widget({ authenticated }) {
  if (!authenticated) {
    return <SignedOutControl />
  }
  return <Button variant="secondary">Real</Button>
}
`
const GUARDED_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const SignedIn = { args: { authenticated: true } }
`

test('resolveDisabledFromStories skips a candidate whose own guard is unreached for a given story, contributing neither a match nor an unresolved reason', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    ['/repo/packages/design-system/src/composites/Widget/index.tsx', GUARDED_WIDGET_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      GUARDED_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  // The ghost button's own static JSX `rest` entry still exists (guards never remove a candidate
  // from Record 3's own existence listing, only from a *specific story's* disabled resolution) —
  // but `SignedIn`'s own `authenticated: true` makes `SignedOutControl`'s `!authenticated` guard
  // resolve `'unreached'` for that story, so its unresolvable `disabled` expression must never
  // surface at all: a confirmed `none`, no unresolved note riding along.
  const ghostRow = computed.matrices.Button.find((r) => r.variantSize === 'ghost')
  assert.ok(ghostRow, "the candidate's own static rest entry still exists")
  assert.deepEqual(ghostRow.disabled, ['none'])
})

// --- REJECT on #80, item 1: selector targets for local elements (a script `visualForceState:
// { selector }` was dropped entirely for local elements — MatchRow/FavouritesList/PlayerResultRow's
// own row link — read as a false 'none' on hover/focus/active). -----------------------------------

test('parseSelector parses tag[attr="literal"]', () => {
  assert.deepEqual(parseSelector('a[href="/matches/1001"]'), {
    tag: 'a',
    attr: 'href',
    value: '/matches/1001',
  })
})

test('parseSelector returns null for anything else (never guessed)', () => {
  assert.equal(parseSelector('[data-visual-scope]'), null)
  assert.equal(parseSelector('a.some-class'), null)
})

test('resolveSelectorMatch resolves a literal attribute directly', () => {
  const candidate = {
    tag: 'a',
    attrExprs: new Map([['href', { literal: true, value: '/players/1', expr: null }]]),
  }
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/players/1"]',
      candidate,
      pool: [candidate],
      scope: null,
    }),
    'match',
  )
})

test('resolveSelectorMatch resolves a story-arg-derived attribute (MatchRow/FavouritesList/PlayerResultRow shape: href={match.href})', () => {
  const candidate = {
    tag: 'a',
    attrExprs: new Map([['href', { literal: false, value: undefined, expr: 'HREF_EXPR' }]]),
  }
  // Stand in for `evaluateExpr` resolving `match.href` against a scope built from the story's own
  // render-passed `match={base}` — `scope.get` is queried by `resolveSelectorMatch`'s own call to
  // `evaluateExpr`, so the fixture supplies a real property-access AST node instead of a string.
  const sourceFile = parse(`const x = match.href`)
  const exprNode = sourceFile.statements[0].declarationList.declarations[0].initializer
  candidate.attrExprs.set('href', { literal: false, value: undefined, expr: exprNode })
  const scope = new Map([['match', { resolved: true, value: { href: '/matches/1001' } }]])
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/matches/1001"]',
      candidate,
      pool: [candidate],
      scope,
    }),
    'match',
  )
})

test('resolveSelectorMatch rejects a confirmed different value, positive knowledge either way', () => {
  const candidate = {
    tag: 'a',
    attrExprs: new Map([['href', { literal: true, value: '/players/2', expr: null }]]),
  }
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/players/1"]',
      candidate,
      pool: [candidate],
      scope: null,
    }),
    'reject',
  )
})

test('resolveSelectorMatch is ambiguous (never a silent none) when the attribute cannot be resolved at all', () => {
  const candidate = { tag: 'a', attrExprs: new Map([['href', { literal: false, expr: null }]]) }
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/players/1"]',
      candidate,
      pool: [candidate],
      scope: null,
    }),
    'ambiguous',
  )
})

test('resolveSelectorMatch resolves a selector against the sole element of a single-entry iteration array (FavouritesList shape: entries.map((entry) => <a href={entry.href}>))', () => {
  const sourceFile = parse(`const x = entry.href`)
  const hrefExpr = sourceFile.statements[0].declarationList.declarations[0].initializer
  const iterationSourceFile = parse(`const y = entries`)
  const iterationArrayExpr =
    iterationSourceFile.statements[0].declarationList.declarations[0].initializer
  const candidate = {
    tag: 'a',
    attrExprs: new Map([['href', { literal: false, expr: hrefExpr }]]),
    iterationVar: 'entry',
    iterationArrayExpr,
  }
  const scope = new Map([['entries', { resolved: true, value: [{ href: '/players/1' }] }]])
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/players/1"]',
      candidate,
      pool: [candidate],
      scope,
    }),
    'match',
  )
})

test('contrast: resolveSelectorMatch stays ambiguous when the iteration array has more than one entry (which index this candidate is cannot be picked)', () => {
  const sourceFile = parse(`const x = entry.href`)
  const hrefExpr = sourceFile.statements[0].declarationList.declarations[0].initializer
  const iterationSourceFile = parse(`const y = entries`)
  const iterationArrayExpr =
    iterationSourceFile.statements[0].declarationList.declarations[0].initializer
  const candidate = {
    tag: 'a',
    attrExprs: new Map([['href', { literal: false, expr: hrefExpr }]]),
    iterationVar: 'entry',
    iterationArrayExpr,
  }
  const scope = new Map([
    ['entries', { resolved: true, value: [{ href: '/players/1' }, { href: '/players/2' }] }],
  ])
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/players/1"]',
      candidate,
      pool: [candidate],
      scope,
    }),
    'ambiguous',
  )
})

// T594's row-8 remediation, item 4: `FavouritesList`'s own row link sits one indirection past the
// inline shape above — inside a sibling helper (`FavouriteRow`), invoked from `entries.map()` with
// `entry={entry}`, a prop passed through literally. `findHelperInvocationIterationContext` finds
// that mapping; `findLocalElements` applies it to a candidate declared inside the helper's own
// body that has no iteration context of its own.

const FAVOURITES_LIST_SHAPE_SOURCE = `
function FavouritesList({ entries }) {
  return (
    <ul>
      {entries.map((entry) => (
        <FavouriteRow key={entry.profileId} entry={entry} />
      ))}
    </ul>
  )
}

function FavouriteRow({ entry }) {
  return (
    <a href={entry.href} className="hover:bg-surface-sunken">
      {entry.alias}
    </a>
  )
}
`

test('findHelperInvocationIterationContext maps a helper invoked with a literal iteration-variable prop', () => {
  const sourceFile = parse(FAVOURITES_LIST_SHAPE_SOURCE, 'index.tsx')
  const map = findHelperInvocationIterationContext(sourceFile)
  const entry = map.get('FavouriteRow')
  assert.ok(entry, 'FavouriteRow must be mapped')
  assert.equal(entry.iterationVar, 'entry')
  assert.equal(entry.iterationArrayExpr.getText(), 'entries')
})

test('findLocalElements resolves a helper-indirected candidate end to end (FavouritesList/FavouriteRow shape)', () => {
  const sourceFile = parse(FAVOURITES_LIST_SHAPE_SOURCE, 'index.tsx')
  const constMap = buildConstStringMap(sourceFile)
  const helperIterationContext = findHelperInvocationIterationContext(sourceFile)
  const found = findLocalElements(
    sourceFile,
    'index.tsx',
    constMap,
    'FavouritesList',
    helperIterationContext,
  )
  const anchor = found.find((el) => el.tag === 'a')
  assert.ok(anchor)
  assert.equal(anchor.iterationVar, 'entry')
  assert.equal(anchor.iterationArrayExpr.getText(), 'entries')
  const scope = new Map([['entries', { resolved: true, value: [{ href: '/players/1' }] }]])
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/players/1"]',
      candidate: anchor,
      pool: [anchor],
      scope,
    }),
    'match',
  )
})

// Contrast: a prop whose value is not a bare identifier equal to the iteration variable (a
// transform, here) never maps the helper — `findLocalElements` then finds no inherited iteration
// context, and the candidate's own selector stays unresolved rather than guessed.
const FAVOURITES_LIST_NON_LITERAL_PROP_SOURCE = `
function FavouritesList({ entries }) {
  return (
    <ul>
      {entries.map((entry) => (
        <FavouriteRow key={entry.profileId} entry={{ ...entry, decorated: true }} />
      ))}
    </ul>
  )
}

function FavouriteRow({ entry }) {
  return (
    <a href={entry.href} className="hover:bg-surface-sunken">
      {entry.alias}
    </a>
  )
}
`

test('contrast: a prop whose value is not passed through literally leaves the helper unmapped', () => {
  const sourceFile = parse(FAVOURITES_LIST_NON_LITERAL_PROP_SOURCE, 'index.tsx')
  const map = findHelperInvocationIterationContext(sourceFile)
  assert.equal(map.get('FavouriteRow'), undefined)

  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'index.tsx', constMap, 'FavouritesList', map)
  const anchor = found.find((el) => el.tag === 'a')
  assert.ok(anchor)
  assert.equal(anchor.iterationVar, null)
  assert.equal(anchor.iterationArrayExpr, null)
})

test('resolveSelectorMatch rejects outright on a tag mismatch', () => {
  const candidate = { tag: 'button', attrExprs: new Map() }
  assert.equal(
    resolveSelectorMatch({
      selector: 'a[href="/players/1"]',
      candidate,
      pool: [candidate],
      scope: null,
    }),
    'reject',
  )
})

const MATCHROW_LIKE_RENDER_SOURCE = `
export const Hover = {
  render: () => <MatchRow match={base} />,
  parameters: { visualForceState: { state: 'hover', selector: 'a[href="/matches/1001"]' } },
}
`

test('findRenderJsxProps reads the explicit JSX props a render() passes to the component under test', () => {
  const sourceFile = parse(MATCHROW_LIKE_RENDER_SOURCE, 'MatchRow.stories.tsx')
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const props = findRenderJsxProps(node, 'MatchRow')
  assert.ok(props.has('match'))
  assert.equal(props.get('match').getText(), 'base')
})

test('buildElementMatrix positively resolves a selector-targeted force-state against a story-arg-derived href, end to end (MatchRow shape)', () => {
  const sourceFile = parse(`const x = match.href`)
  const hrefExpr = sourceFile.statements[0].declarationList.declarations[0].initializer
  const elements = [
    {
      tag: 'a',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'index.tsx',
      line: 397,
      attrExprs: new Map([['href', { literal: false, expr: hrefExpr }]]),
    },
  ]
  const scope = new Map([['match', { resolved: true, value: { href: '/matches/1001' } }]])
  const storyStates = [
    {
      exportName: 'Hover',
      forced: {
        state: 'hover',
        role: null,
        name: null,
        selector: 'a[href="/matches/1001"]',
        nth: null,
      },
      playFocus: null,
      argsLiterals: new Set(),
      scope,
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].hover, ['Hover'])
})

test('contrast: buildElementMatrix leaves a selector-targeted force-state unresolved (never none) when the href cannot be resolved from any scope', () => {
  const sourceFile = parse(`const x = match.href`)
  const hrefExpr = sourceFile.statements[0].declarationList.declarations[0].initializer
  const elements = [
    {
      tag: 'a',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'index.tsx',
      line: 397,
      attrExprs: new Map([['href', { literal: false, expr: hrefExpr }]]),
    },
  ]
  const storyStates = [
    {
      exportName: 'Hover',
      forced: {
        state: 'hover',
        role: null,
        name: null,
        selector: 'a[href="/matches/1001"]',
        nth: null,
      },
      playFocus: null,
      argsLiterals: new Set(),
      scope: null,
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.equal(rows[0].hover.length, 1)
  assert.match(rows[0].hover[0], /^unresolved:/)
})

// --- REJECT on #80, item 2: roles. INTRINSIC_ROLE lacked `main`/`region` and mapped every `input`
// to `textbox`, so `SearchBox`'s `role: 'searchbox'` force-state, `Page`'s `main` landmark and
// `Table`'s `region` never found a candidate to match at all. -------------------------------------

test('findLocalElements derives \'searchbox\' from a literal type="search", not the generic textbox default', () => {
  const source = `const el = <input type="search" className="hover:border-strong" />`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found[0].role, 'searchbox')
})

test('contrast: findLocalElements leaves an unlisted/dynamic input type with no derived role (falls back to textbox downstream, unchanged)', () => {
  const source = `const el = <input type="email" className="hover:border-strong" />`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found[0].role, null)
})

test("findLocalElements derives 'navigation' for a <nav>, once it otherwise qualifies for Record 1 (tabIndex here, standing in for a real hover/focus signal)", () => {
  const source = `const el = <nav aria-label="Primary" tabIndex={0} />`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found[0].role, 'navigation')
})

test("findLocalElements derives 'region' for a labelled <section>", () => {
  const source = `const el = <section aria-labelledby="heading-id" tabIndex={0} />`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found[0].role, 'region')
})

test("buildElementMatrix matches a role: 'searchbox' force-state against the derived role, end to end (SearchBox shape)", () => {
  const elements = [
    {
      tag: 'input',
      role: 'searchbox',
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'f.tsx',
      line: 10,
    },
  ]
  const storyStates = [
    {
      exportName: 'Hover',
      forced: { state: 'hover', role: 'searchbox', name: null, nth: null },
      playFocus: null,
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].hover, ['Hover'])
})

// --- REJECT on #80, item 3: also resolve names from a literal aria-label. --------------------

test("findLocalElements resolves a candidate's own name from a literal aria-label when it carries no JSX text", () => {
  const source = `const el = <nav aria-label="Primary" tabIndex={0} />`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found[0].text, 'Primary')
})

// --- REJECT on #80, item 5: composed primitives. INTRINSIC_ROLE[primitive.toLowerCase()] gave
// null for Link/Field/Menu, so a role: 'link' force-state (Footer's own shape) never found a Link
// candidate, and a universal `forced.role === 'button'` wildcard let a button-role story be
// wrongly credited to a Link/Field/Menu instance in the same component. --------------------------

test("impliedRoleForPrimitiveInstance: Link is always 'link', never null", () => {
  assert.equal(impliedRoleForPrimitiveInstance('Link', {}), 'link')
})

test("impliedRoleForPrimitiveInstance: Button is 'link' once it renders <a href>, 'button' otherwise", () => {
  assert.equal(impliedRoleForPrimitiveInstance('Button', { hasHref: true }), 'link')
  assert.equal(impliedRoleForPrimitiveInstance('Button', { hasHref: false }), 'button')
})

test("impliedRoleForPrimitiveInstance: Menu's own trigger is always 'button'", () => {
  assert.equal(impliedRoleForPrimitiveInstance('Menu', {}), 'button')
})

test('impliedRoleForPrimitiveInstance: Field has no single fixed role (null, matched by nothing, never guessed)', () => {
  assert.equal(impliedRoleForPrimitiveInstance('Field', {}), null)
})

const FOOTER_LIKE_SOURCE = `
function FooterLike() {
  return (
    <footer>
      <Link href="/privacy">Privacy notice</Link>
    </footer>
  )
}
`

test('a role: "link" force-state resolves a Link instance end to end (Footer shape, previously dropped: implied was null)', () => {
  const sourceFile = parse(FOOTER_LIKE_SOURCE, 'index.tsx')
  const found = findPrimitiveInstances(sourceFile, 'index.tsx', {})
  const instancesByPrimitive = new Map([
    ['Button', []],
    ['Link', found.map((f) => ({ ...f, kind: 'jsx', componentKey: 'composites/Footer' }))],
    ['Field', []],
    ['Menu', []],
  ])
  const pending = [
    {
      componentKey: 'composites/Footer',
      file: 'Footer.stories.tsx',
      exportName: 'FocusVisible',
      forced: { state: 'focus-visible', role: 'link', name: null, selector: null, nth: null },
      storyLineRange: null,
      argsLiterals: new Set(),
      propsScope: new Map(),
    },
  ]
  resolveComposedStoryMatches(pending, instancesByPrimitive)
  const matched = instancesByPrimitive.get('Link').filter((i) => i.kind === 'composed-story')
  assert.equal(matched.length, 1)
})

test('contrast: a role: "button" force-state is never credited to a Link instance in the same component (previously a universal wildcard)', () => {
  const sourceFile = parse(FOOTER_LIKE_SOURCE, 'index.tsx')
  const found = findPrimitiveInstances(sourceFile, 'index.tsx', {})
  const instancesByPrimitive = new Map([
    ['Button', []],
    ['Link', found.map((f) => ({ ...f, kind: 'jsx', componentKey: 'composites/Footer' }))],
    ['Field', []],
    ['Menu', []],
  ])
  const pending = [
    {
      componentKey: 'composites/Footer',
      file: 'Footer.stories.tsx',
      exportName: 'Hover',
      forced: { state: 'hover', role: 'button', name: null, selector: null, nth: null },
      storyLineRange: null,
      argsLiterals: new Set(),
      propsScope: new Map(),
    },
  ]
  resolveComposedStoryMatches(pending, instancesByPrimitive)
  const matched = instancesByPrimitive.get('Link').filter((i) => i.kind === 'composed-story')
  assert.equal(matched.length, 0)
})

// --- REJECT on #80: Record 1 must be one line per component, the ones with nothing to report
// included — previously only the directories that happened to have a local element appeared at
// all (19 of 41), so the list could not be counted against story-docs.mjs's own directory count. --

test('renderRecord1 emits a row for a component with no local interactive element, rather than omitting it', () => {
  const computed = {
    localElements: [
      { componentKey: 'primitives/EmptyOne', elements: [] },
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'a',
            role: null,
            tabIndex: null,
            hover: 'hover:underline',
            focusVisible: null,
            active: null,
            ariaHidden: false,
            classUnresolvedRefs: [],
            file: 'f.tsx',
            line: 12,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
  }
  const rendered = renderRecord1(computed)
  assert.match(rendered, /primitives\/EmptyOne \| \(no local interactive element\) \| N\/A/)
  assert.match(rendered, /primitives\/Widget/)
})

test('a dynamic role={…} element is excluded from the plain button’s implied-role pool', () => {
  const plainButton = {
    tag: 'button',
    role: null,
    tabIndex: null,
    ariaHidden: false,
    isHelper: false,
    text: '',
    file: 'f.tsx',
    line: 10,
  }
  const dynamicRoleButton = {
    tag: 'button',
    role: 'unresolved',
    tabIndex: null,
    ariaHidden: false,
    isHelper: false,
    text: '',
    file: 'f.tsx',
    line: 20,
    // A real class on every state, matching what a production `MenuItemRow`-shaped element always
    // carries — `cellFor` (state-coverage.mjs) only routes a null-implied-role element to
    // `noImpliedRoleReason` at all when it carries a class for that state (T595); an empty fixture
    // would instead trip the confirmed-`'none'` shortcut this test is not about.
    hover: 'hover:bg-surface-sunken',
    focusVisible: 'focus-visible:outline-2',
    active: 'active:bg-background',
  }
  const storyStates = [
    {
      exportName: 'Hover',
      forced: { state: 'hover', role: 'button', name: null, nth: null },
      playFocus: null,
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix([plainButton, dynamicRoleButton], storyStates)
  assert.deepEqual(rows[0].hover, ['Hover'])
  // T594 part A: a dynamic `role={…}` is excluded from every implied-role pool, so this pass never
  // even compared a force-state against it — 'none' would overstate that as a confirmed absence.
  assert.equal(rows[1].hover.length, 1)
  assert.match(rows[1].hover[0], /^unresolved: dynamic role$/)
})

// --- T594 part A (still true, unaffected by T595 below): a hand-built fixture that carries no
// `attrExprs`/`localConsts` at all never reaches T595's per-story dynamic-role resolution (gated on
// `el.attrExprs?.get('role')?.expr`, absent here), so `impliedRoleOf` returning `null` for a dynamic
// `role={…}` still means the whole matching loop is skipped and the cell reads `'unresolved: dynamic
// role'`, never a false confirmed `'none'`. -----------------------------------------------------

test('buildElementMatrix: a dynamic role={…} element reads "unresolved: dynamic role" on every state, not "none" (Menu shape)', () => {
  const dynamicRoleButton = {
    tag: 'button',
    role: 'unresolved',
    tabIndex: null,
    ariaHidden: false,
    isHelper: false,
    text: '',
    file: 'Menu/index.tsx',
    line: 352,
    // Real classes on every state, the same reason the sibling fixture above now carries them.
    hover: 'hover:bg-surface-sunken',
    focusVisible: 'focus-visible:outline-2',
    active: 'active:bg-background',
  }
  // No story targets role 'button' or any literal role at all — the dynamic role means this pass
  // cannot even attempt a comparison, on any of the three states.
  const storyStates = [
    {
      exportName: 'Selection',
      forced: { state: 'hover', role: 'menuitemradio', name: 'aoe2alt', nth: null },
      playFocus: null,
      argsLiterals: new Set(['aoe2alt']),
    },
  ]
  const rows = buildElementMatrix([dynamicRoleButton], storyStates)
  assert.match(rows[0].hover[0], /^unresolved: dynamic role$/)
  assert.match(rows[0].focusVisible[0], /^unresolved: dynamic role$/)
  assert.match(rows[0].active[0], /^unresolved: dynamic role$/)
})

// --- T595 (row 8, H5): closing the three `noImpliedRoleReason` shapes — `INTRINSIC_ROLE` widened
// to the heading and table families, a dynamic `role={…}` resolved per story, and `hover`/`active`
// credited from a confirmed descendant match. Routed through `computeStateCoverage`, not hand-built
// instances, wherever a fixture needs `attrExprs`/`localConsts`/`guards`/`nodeStart`/`nodeEnd` —
// none of which a hand-built object can carry honestly. Each mechanism gets its own resolving case
// and its own contrast (boundary) case, run against the pre-T595 code first (see the task hand-back
// for the failing output). ------------------------------------------------------------------------

const HEADING_INDEX_SOURCE = `
export function Dialog({ heading }) {
  return (
    <div role="dialog">
      <h2 tabIndex={-1} className="outline-none">
        {heading}
      </h2>
    </div>
  )
}
`

test('buildElementMatrix (via computeStateCoverage): INTRINSIC_ROLE now resolves h2 to "heading" — no story targets it, so the cell is a confirmed "none", never "unresolved: no implied role" (Dialog shape)', () => {
  const storiesSource = `
    import { Dialog } from './index'
    const meta = { component: Dialog, args: { heading: 'Turn off replay archival?' } }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Dialog' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Dialog/index.tsx'), HEADING_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Dialog/Dialog.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Dialog')
  const heading = elements.find((el) => el.tag === 'h2')
  assert.ok(heading, "Dialog's own h2 must be found as a local element")
  assert.deepEqual(heading.coveredBy.hover, ['none'])
  assert.deepEqual(heading.coveredBy.focusVisible, ['none'])
  assert.deepEqual(heading.coveredBy.active, ['none'])
})

test("buildElementMatrix (via computeStateCoverage): a role: 'heading' force-state now actually matches h2 (the resolution working, not only the fallback)", () => {
  const indexSource = `
    export function Dialog({ heading }) {
      return (
        <div role="dialog">
          <h2 tabIndex={-1} className="outline-none focus-visible:outline-2">
            Turn off replay archival?
          </h2>
        </div>
      )
    }
  `
  const storiesSource = `
    import { Dialog } from './index'
    const meta = { component: Dialog, args: {} }
    export default meta
    export const FocusVisible = {
      args: {},
      parameters: { visualForceState: { state: 'focus-visible', role: 'heading', name: 'Turn off replay archival?' } },
    }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Dialog' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Dialog/index.tsx'), indexSource],
    [path.join(REPO_SRC_DIR, 'primitives/Dialog/Dialog.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Dialog')
  const heading = elements.find((el) => el.tag === 'h2')
  assert.deepEqual(heading.coveredBy.focusVisible, ['FocusVisible'])
  assert.deepEqual(heading.coveredBy.hover, ['none'])
  assert.deepEqual(heading.coveredBy.active, ['none'])
})

const TABLE_ROW_LINK_INDEX_SOURCE = `
export function Table({ rows }) {
  return (
    <table>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.id}
            className="hover:bg-surface-sunken active:bg-surface-sunken active:border-l-border-strong"
          >
            <td>
              <a href={row.href} className="focus-visible:outline-ring">
                {row.label}
              </a>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
`

test('buildElementMatrix (via computeStateCoverage): hover/active cascade from a confirmed descendant match to the tr that wraps it, and focus-visible does not (Table row-link shape)', () => {
  const storiesSource = `
    import { Table } from './index'
    const meta = { component: Table, args: {} }
    export default meta
    export const RowLinkHover = {
      args: { rows: [{ id: '1', href: '/matches/1', label: 'RedBull_Barley' }] },
      parameters: { visualForceState: { state: 'hover', role: 'link', name: 'RedBull_Barley' } },
    }
    export const RowLinkActive = {
      args: { rows: [{ id: '1', href: '/matches/1', label: 'RedBull_Barley' }] },
      parameters: { visualForceState: { state: 'active', role: 'link', name: 'RedBull_Barley' } },
    }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Table' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Table/index.tsx'), TABLE_ROW_LINK_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Table/Table.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Table')
  const row = elements.find((el) => el.tag === 'tr')
  assert.ok(row, "Table's own tr must be found as a local element")
  // `hover`/`active`: a real, CDP-backed pointer move/mouse-down on the row link also matches the
  // ancestor `tr` in a real capture — credited directly, not left as an unresolved ancestor note.
  assert.deepEqual(row.coveredBy.hover, ['RowLinkHover'])
  assert.deepEqual(row.coveredBy.active, ['RowLinkActive'])
  // `focus-visible`: the `tr` itself carries no `focus-visible:` class of its own (only the link
  // does), so there is nothing for a cascade to credit — a confirmed `none`, not an ancestor note.
  assert.deepEqual(row.coveredBy.focusVisible, ['none'])
})

const AMBIGUOUS_SIBLING_LINKS_INDEX_SOURCE = `
export function Widget() {
  return (
    <span className="hover:bg-surface-sunken">
      <a href="/x" className="hover:underline">One</a>
      <a href="/y" className="hover:underline">Two</a>
    </span>
  )
}
`

test('contrast: buildElementMatrix does not credit an ancestor from a merely ambiguous descendant match — stays "unresolved: ancestor of a forced descendant …", never "none" and never covered', () => {
  const storiesSource = `
    import { Widget } from './index'
    const meta = { component: Widget, args: {} }
    export default meta
    export const Hover = {
      args: {},
      parameters: { visualForceState: { state: 'hover', role: 'link' } },
    }
  `
  const componentDirs = [{ segment: 'composites', name: 'Widget' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'composites/Widget/index.tsx'), AMBIGUOUS_SIBLING_LINKS_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'composites/Widget/Widget.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'composites/Widget')
  const span = elements.find((el) => el.tag === 'span')
  assert.ok(span, "Widget's own span must be found as a local element (it carries a hover: class)")
  assert.equal(span.coveredBy.hover.length, 1)
  assert.match(span.coveredBy.hover[0], /^unresolved: ancestor of a forced descendant/)
  assert.match(span.coveredBy.hover[0], /a@.*index\.tsx:\d+/)
})

const LABEL_WRAPS_CHECKBOX_INDEX_SOURCE = `
export function Panel({ acknowledged, onChange }) {
  return (
    <label className="mt-6 flex items-center gap-2">
      <input
        type="checkbox"
        checked={acknowledged}
        onChange={onChange}
        className="focus-visible:outline-2"
      />
      <span>I understand this cannot be undone.</span>
    </label>
  )
}
`

test('buildElementMatrix (via computeStateCoverage): a <label> ARIA gives no role of its own reads a confirmed "none" on every state once it carries no class for any of them, never guessing a role (AccountErasurePanel shape)', () => {
  const storiesSource = `
    import { Panel } from './index'
    const meta = { component: Panel, args: { acknowledged: false } }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'screens', name: 'Panel' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'screens/Panel/index.tsx'), LABEL_WRAPS_CHECKBOX_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'screens/Panel/Panel.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'screens/Panel')
  const label = elements.find((el) => el.tag === 'label')
  assert.ok(label, 'the label must be captured (it wraps its own checkbox as a direct JSX child)')
  assert.equal(label.role, null, 'ARIA gives <label> no role — never invented here')
  assert.deepEqual(label.coveredBy.hover, ['none'])
  assert.deepEqual(label.coveredBy.focusVisible, ['none'])
  assert.deepEqual(label.coveredBy.active, ['none'])
})

const HEADER_CELL_INDEX_SOURCE = `
export function Grid() {
  return (
    <table>
      <thead>
        <tr>
          <th className="hover:underline">Name</th>
        </tr>
      </thead>
    </table>
  )
}
`

test('contrast: a <th> stays "unresolved: no implied role" — INTRINSIC_ROLE\'s table family deliberately excludes it, and the no-class-is-none rule does not apply because it does carry a class', () => {
  const storiesSource = `
    import { Grid } from './index'
    const meta = { component: Grid, args: {} }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Grid' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Grid/index.tsx'), HEADER_CELL_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Grid/Grid.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Grid')
  const th = elements.find((el) => el.tag === 'th')
  assert.ok(th, 'the th must be captured (it carries a hover: class)')
  assert.deepEqual(th.coveredBy.hover, ['unresolved: no implied role'])
})

const DYNAMIC_ROLE_INDEX_SOURCE = `
function RosterItemRow({ item, variant }) {
  const role = variant === 'selection' ? 'menuitemradio' : 'menuitem'
  return (
    <button
      role={role}
      className="hover:bg-surface-sunken focus-visible:outline-2 active:bg-background"
    >
      {item.label}
    </button>
  )
}

export function Roster({ variant, items }) {
  return (
    <div>
      {items.map((item) => (
        <RosterItemRow key={item.id} item={item} variant={variant} />
      ))}
    </div>
  )
}
`

test("buildElementMatrix (via computeStateCoverage): a dynamic role={…} resolves per story against that story's own scope, matching hover/focus-visible/active (MenuItemRow shape)", () => {
  const args = `{
      variant: 'selection',
      items: [{ id: 'p1', label: 'aoe2guy' }, { id: 'p2', label: 'aoe2alt' }],
    }`
  const storiesSource = `
    import { Roster } from './index'
    const meta = { component: Roster, args: {} }
    export default meta
    export const Hover = {
      args: ${args},
      parameters: { visualForceState: { state: 'hover', role: 'menuitemradio', name: 'aoe2alt' } },
    }
    export const FocusVisible = {
      args: ${args},
      parameters: { visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2alt' } },
    }
    export const Active = {
      args: ${args},
      parameters: { visualForceState: { state: 'active', role: 'menuitemradio', name: 'aoe2alt' } },
    }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Roster' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Roster/index.tsx'), DYNAMIC_ROLE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Roster/Roster.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Roster')
  const row = elements.find((el) => el.tag === 'button')
  assert.ok(row, "RosterItemRow's own button must be found as a local element")
  assert.deepEqual(row.coveredBy.hover, ['Hover'])
  assert.deepEqual(row.coveredBy.focusVisible, ['FocusVisible'])
  assert.deepEqual(row.coveredBy.active, ['Active'])
})

test('contrast: a dynamic role={…} stays "unresolved: dynamic role" when no story ever supplies the data the expression needs (never a blanket resolution)', () => {
  const storiesSource = `
    import { Roster } from './index'
    const meta = { component: Roster, args: {} }
    export default meta
    export const NoVariantSet = {
      args: { items: [{ id: 'p1', label: 'aoe2guy' }] },
      parameters: { visualForceState: { state: 'hover', role: 'menuitemradio', name: 'aoe2guy' } },
    }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Roster' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Roster/index.tsx'), DYNAMIC_ROLE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Roster/Roster.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Roster')
  const row = elements.find((el) => el.tag === 'button')
  assert.deepEqual(row.coveredBy.hover, ['unresolved: dynamic role'])
  assert.deepEqual(row.coveredBy.focusVisible, ['unresolved: dynamic role'])
  assert.deepEqual(row.coveredBy.active, ['unresolved: dynamic role'])
})

// --- Citation checker (reviewer's third REJECT on PR #80) --------------------------------------

test('parseLineSpec: single line, a range, and a comma list of both', () => {
  assert.deepEqual(parseLineSpec('39'), [[39, 39]])
  assert.deepEqual(parseLineSpec('550-551'), [[550, 551]])
  assert.deepEqual(parseLineSpec('441,344-345'), [
    [441, 441],
    [344, 345],
  ])
})

test('matchQuoteAgainstText: a plain quote matches a literal substring, whitespace-collapsed', () => {
  const text = 'line one\n  line two has the phrase right here\nline three'
  assert.equal(matchQuoteAgainstText('the phrase right here', text, [[1, 3]]), true)
  assert.equal(matchQuoteAgainstText('the phrase nowhere here', text, [[1, 3]]), false)
})

test('matchQuoteAgainstText: an ellipsis elides a run of text, matched as an ordered pair', () => {
  const text = 'a bare, unstyled\nButton firing POST has no bespoke states beyond Button own'
  assert.equal(
    matchQuoteAgainstText('a bare, unstyled … has no bespoke states beyond Button own', text, [
      [1, 2],
    ]),
    true,
  )
  // Out of order — the suffix appears before the prefix in the text — must not match.
  assert.equal(matchQuoteAgainstText('has no bespoke … a bare, unstyled', text, [[1, 2]]), false)
})

test('matchQuoteAgainstText: a range concatenates every listed line, in order, into one target', () => {
  const text = 'one\ntwo\nthree\nfour'
  assert.equal(matchQuoteAgainstText('two three', text, [[2, 3]]), true)
  assert.equal(
    matchQuoteAgainstText('one four', text, [
      [1, 1],
      [4, 4],
    ]),
    true,
  )
})

test('parseCitations: a table row supplies a bare citation its own file column', () => {
  const scope =
    '| File | Handoffs | Cited lines |\n' +
    '| --- | --- | --- |\n' +
    '| `example.md` | 1 | `:39` "a quoted excerpt" (filed under Foo). |\n'
  const citations = parseCitations(scope)
  assert.equal(citations.length, 1)
  assert.equal(citations[0].location, null)
  assert.deepEqual(citations[0].tableContext, { kind: 'md', name: 'example.md' })
  assert.equal(citations[0].lineSpec, '39')
  assert.equal(citations[0].quote, 'a quoted excerpt')
})

test('parseCitations: table context resets outside the table and does not leak into prose', () => {
  const scope =
    '| `example.md` | 1 | `:39` "quoted" |\n\nProse after the table `:40` "unquoted-ish"\n'
  const citations = parseCitations(scope)
  // The prose line's `:40` carries no location and no table row above it (a blank line ended the
  // table), so it is not attributed to `example.md` — this citation is unresolvable, not silently
  // inherited from the last table row.
  assert.equal(citations.length, 2)
  assert.equal(citations[1].tableContext, null)
})

test('parseCitations: a quote wrapped across a hard line break is still found, flattened to one line', () => {
  // Mirrors what prettier's own prose wrap does to a long bullet — the citation and the first half
  // of its quote end one physical line, the rest starts the next (T594's own second hand-back was
  // rejected for exactly this shape going unrecognised).
  const scope =
    '- **N1.** `structural-tier.md:441` "A Panel is never itself\n  interactive" — no owner.\n'
  const citations = parseCitations(scope)
  assert.equal(citations.length, 1)
  assert.equal(citations[0].location, 'structural-tier.md')
  // `parseCitations` flattens `\n` to a single space before matching (its own header explains
  // why), so the captured quote carries that flattened form — `matchQuoteAgainstText` is what
  // collapses runs of whitespace down to one, not this step.
  assert.equal(citations[0].quote, 'A Panel is never itself   interactive')
})

test('parseCitations: an escaped double quote inside the quoted text is unescaped, not a boundary', () => {
  const scope = '| `x.md` | 1 | `:1` "carries \\"Try again\\" verbatim" |\n'
  const citations = parseCitations(scope)
  assert.equal(citations.length, 1)
  assert.equal(citations[0].quote, 'carries "Try again" verbatim')
})

test('parseCitations: a bare `:line` citation with no adjacent quote is not recognised at all', () => {
  const scope = 'See `structural-tier.md:441` for more, discussed later without a quote.\n'
  assert.equal(parseCitations(scope).length, 0)
})

function withFixtureTree(build) {
  const dir = mkdtempSync(path.join(tmpdir(), 'state-coverage-citations-'))
  try {
    return build(dir)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

test('resolveCitationLocation: a bare .md filename resolves under specsDir', () => {
  withFixtureTree((dir) => {
    const specsDir = path.join(dir, 'specs')
    mkdirSync(specsDir, { recursive: true })
    writeFileSync(path.join(specsDir, 'example.md'), 'line one\nline two\n')
    const resolved = resolveCitationLocation(
      { location: 'example.md', tableContext: null },
      { specsDir, allSrcFiles: [] },
    )
    assert.equal(resolved, path.join(specsDir, 'example.md'))
  })
})

test('resolveCitationLocation: a bare component name from an 8c-bis table row resolves its own .stories.tsx', () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Widget', 'Widget.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    writeFileSync(storyFile, '// story\n')
    const allSrcFiles = [storyFile.split(path.sep).join('/')]
    const resolved = resolveCitationLocation(
      { location: null, tableContext: { kind: 'stories', name: 'Widget' } },
      { specsDir: path.join(dir, 'specs'), allSrcFiles },
    )
    assert.equal(resolved, storyFile)
  })
})

test('resolveCitationLocation: an ambiguous suffix (two files with the same tail) fails rather than guessing', () => {
  const allSrcFiles = ['/repo/a/Widget/index.tsx', '/repo/b/Widget/index.tsx']
  const resolved = resolveCitationLocation(
    { location: 'Widget/index.tsx', tableContext: null },
    { specsDir: '/repo/specs', allSrcFiles },
  )
  assert.equal(resolved, null)
})

// --- `reviewer`'s fourth REJECT on PR #80, item A3: `checkCitations` was never called by any test
// — only its own pieces (`parseCitations`, `resolveCitationLocation`, `matchQuoteAgainstText`) were.
// `checkCitations` itself reads the live tree for resolution (`specsDir`/`srcDir` are module-level
// constants, not injectable — the same reason `checkDeferralVocabularyCoverage`'s own live-tree
// call is the one made injectable instead), so these end-to-end tests point at real, stable files
// under this package's own `specs/` and `src/`, reading their content fresh rather than hard-coding
// it, so the test cannot drift from what it asserts against. ------------------------------------

test('checkCitations: a citation whose quote text is not present at its own cited location fails (mis-cited quote), end to end', () => {
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    'prose `GOVERNANCE.md:1` "this exact sentence does not appear on that line, guaranteed by ' +
    'construction" more prose.\n\n' +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /quote not found/)
})

test('checkCitations: a citation whose quote text is present at its own cited location passes, end to end (contrast)', () => {
  const firstLine = readFileSync(
    path.join('packages', 'design-system', 'src', 'primitives', 'Text', 'index.tsx'),
    'utf8',
  )
    .split('\n')[0]
    .trim()
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    `prose \`Text/index.tsx:1\` "${firstLine}" more prose.\n\n` +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.deepEqual(result.failures, [])
  assert.equal(result.parsedCount, 1)
})

test('checkCitations: a citation whose location resolves to no file fails', () => {
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    'prose `NoSuchComponent/index.tsx:1` "anything" more prose.\n\n' +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /did not resolve to exactly one file/)
})

// T594's REJECT on #80, item 7: `extractCitationScope` used to stop at `**Cell counts`, so nothing
// from there to the end of row 8 was ever checked — the "Six cells moved again" paragraph, the
// Owners paragraph, and the closing "Also recorded" note (roughly the last hundred lines of row 8
// at the time of that REJECT), each carrying its own citations no run ever verified. Row 8 is the
// last thing in `README.md`, so the scope now runs to the end of the document.
test('checkCitations: a bad citation placed after the old `**Cell counts` boundary now fails — item 7 widened the scope to the whole of row 8, not only up to that heading', () => {
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    'prose before the old boundary.\n\n' +
    '**Cell counts, printed by the script, never restated here.**\n\n' +
    "Prose past the old boundary, the shape `8e`'s Owners paragraph and the closing note take: " +
    '`GOVERNANCE.md:1` "this exact sentence does not appear on that line, guaranteed by ' +
    'construction" trailing prose.\n'
  const result = checkCitations({ readmeText })
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /quote not found/)
})

test('contrast: the same citation, placed before the old `**Cell counts` boundary, already failed before this pass — proving the widened scope adds coverage rather than changing what a citation before the old boundary does', () => {
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    'prose `GOVERNANCE.md:1` "this exact sentence does not appear on that line, guaranteed by ' +
    'construction" more prose.\n\n' +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /quote not found/)
})

test('findUnparsedQuoteAdjacentCitations: a `file:line` span outside every recognised gap shape, followed closely by a real quote, is flagged', () => {
  const scopeText = '`index.tsx:218-220` renders "Erase my account" `destructive`.'
  const results = findUnparsedQuoteAdjacentCitations(scopeText)
  assert.equal(results.length, 1)
  assert.equal(results[0].raw, '`index.tsx:218-220`')
  assert.equal(results[0].gap, ' renders ')
})

test('findUnparsedQuoteAdjacentCitations: a structural pointer with no nearby quote at all is never flagged (contrast)', () => {
  const scopeText = "`index.tsx:127,138`, `variant={primaryAction.variant ?? 'destructive'}`."
  assert.deepEqual(findUnparsedQuoteAdjacentCitations(scopeText), [])
})

test('findUnparsedQuoteAdjacentCitations: a span already recognised by the widened CITATION_RE is never double-flagged (contrast)', () => {
  const scopeText = '`:138`\'s focus-visible bullet ("standard ring on the trigger").'
  assert.deepEqual(findUnparsedQuoteAdjacentCitations(scopeText), [])
})

// T594 B2, REJECT #5 on #80/#79: a plain inline-code span in the gap (no `:digit`, so it is prose,
// never another citation's own location marker) used to be an escape hatch — the scan bailed at
// its opening backtick and never reached the real quote past it, exactly the shape that let F20's
// own mis-cited quote through both this check and `checkCitations` untouched. The F20 gap itself
// (`... dialog's \`destructive\` action has "..."`) crosses a backtick at offset 20 of its own 40.
test('findUnparsedQuoteAdjacentCitations: a plain inline-code span in the gap is not an escape hatch — the real quote past it is still found (T594 B2)', () => {
  const scopeText = '`x/y.tsx:1-2` says the `Button` state is "already covered".'
  const results = findUnparsedQuoteAdjacentCitations(scopeText)
  assert.equal(results.length, 1)
  assert.equal(results[0].raw, '`x/y.tsx:1-2`')
  assert.equal(results[0].gap, ' says the `Button` state is ')
})

test('contrast: a citation-shaped backtick span in the gap (`foo:123`) still bails — it is the next citation, not prose', () => {
  const scopeText = '`x/y.tsx:1-2` says `:9` state is "already covered".'
  const results = findUnparsedQuoteAdjacentCitations(scopeText)
  // Only `:9`'s own gap is flagged (it finds its own nearby quote); the first span, `x/y.tsx:1-2`,
  // bails at the citation-shaped `:9` span exactly as before and is never reported.
  assert.equal(results.length, 1)
  assert.equal(results[0].raw, '`:9`')
})

// --- T594 M2/M3, REJECT #5 on #80/#79: an inline-code span next to a `file:line` is a claim about
// that line, and about half of row 8's own inline-code spans were never verified — F17 cited
// `Table/index.tsx:96` for a string that is at `:97`; F19 cited `FavouritesList/index.tsx:293` for
// `size="lg"`, which is at `:298`. Both escaped `checkCitations` because the code span was a few
// words off from its citation, outside `CITATION_RE`'s own immediately-adjacent grammar. ----------

test('findInlineCodeClaims: a code-shaped span (real source punctuation) a few words after a citation is found', () => {
  const scopeText =
    '`FavouritesList/index.tsx:298` gives `RemoveControl` (`FavouriteToggle`) `size="lg"`, but more.'
  const claims = findInlineCodeClaims(scopeText)
  assert.equal(claims.length, 1)
  assert.equal(claims[0].location, 'FavouritesList/index.tsx')
  assert.equal(claims[0].lineSpec, '298')
  assert.equal(claims[0].claim, 'size="lg"')
})

test('contrast: a bare identifier span (no source punctuation) is a reference, not a claim — skipped rather than reported', () => {
  const scopeText = '`Widget/index.tsx:1` renders `Button` and nothing else, plain prose past it.'
  assert.deepEqual(findInlineCodeClaims(scopeText), [])
})

test("contrast: a bare identifier immediately followed by a possessive 's reassigns the subject — the scan bails rather than misattribute a later code span (play() shape)", () => {
  const scopeText =
    '`Menu/index.tsx:144` has no hover frame of its own anywhere. Focus-visible is not a gap: ' +
    "`EscapeReturnsFocusToTrigger`'s `play()` ends on a toHaveFocus() assertion."
  assert.deepEqual(findInlineCodeClaims(scopeText), [])
})

test('contrast: a citation already followed immediately by its own quote is never double-claimed here', () => {
  const scopeText =
    '`index.tsx:97` (`focus-visible:outline-ring`) more prose `size="lg"` far past it.'
  // The immediately-adjacent backtick quote is `checkCitations`' own citation grammar; this
  // function only ever looks past a `file:line` that CITATION_RE did *not* already consume.
  assert.deepEqual(findInlineCodeClaims(scopeText), [])
})

test("resolveBareLocationFromBullet: resolves `index.tsx` against the bullet's own possessive-marked subject, never the nearest-preceding one", () => {
  // `Button` sits textually between `Dialog` (the bullet's real subject, marked possessive: `` `Dialog`'s ``)
  // and the citation — the nearest-preceding rule would misattribute this to `Button`'s own
  // `index.tsx`; the possessive-subject rule gets `Dialog`'s (T594's row 8 sweep, item 5).
  const scopeText =
    '**8e. Findings.**\n\n' +
    "- **F3.** `Dialog`'s own two `Button` instances (`index.tsx:127`, `variant={x}`) resolve.\n" +
    '- **F4.** unrelated bullet.\n'
  const allSrcFiles = [
    'packages/design-system/src/primitives/Dialog/index.tsx',
    'packages/design-system/src/primitives/Button/index.tsx',
  ]
  const resolved = resolveBareLocationFromBullet(scopeText, 3, 'index.tsx', allSrcFiles)
  assert.equal(resolved, 'packages/design-system/src/primitives/Dialog/index.tsx')
})

// T594's row 8 sweep, item 5: the possessive-subject rule alone gets this real, live shape wrong —
// `AccountErasurePanel`'s own bullet possessive-marks `` `Button`'s own stories `` (the *deferral
// target*, not the subject) while its real subject, `AccountErasurePanel`, is never itself marked
// possessive anywhere in the block. A fully qualified citation for the *same basename* elsewhere in
// the same block (`` `AccountErasurePanel/index.tsx:224` ``) outranks the possessive signal, because
// it is the prose disambiguating itself rather than a heuristic guessing at intent.
test('resolveBareLocationFromBullet: a self-qualified citation for the same basename elsewhere in the block outranks a possessive mention of a different, unrelated directory', () => {
  const scopeText =
    '**8e. Findings.**\n\n' +
    '- **F20.** `AccountErasurePanel.stories.tsx:106` "covered by `Button`\'s own stories". ' +
    '`index.tsx:218-220` renders the button. `AccountErasurePanel/index.tsx:224` "Erase my account" ' +
    'is the accessible name.\n' +
    '- **F21.** unrelated bullet.\n'
  const allSrcFiles = [
    'packages/design-system/src/screens/AccountErasurePanel/index.tsx',
    'packages/design-system/src/primitives/Button/index.tsx',
  ]
  const resolved = resolveBareLocationFromBullet(scopeText, 3, 'index.tsx', allSrcFiles)
  assert.equal(resolved, 'packages/design-system/src/screens/AccountErasurePanel/index.tsx')
})

// The ambiguous-bullet case the fix is for: two real component directories, both genuinely marked
// as this bullet's own subject (possessive `'s` on each), and nothing elsewhere in the block
// self-qualifies the bare citation's own basename against either one. No heuristic gets to break
// this tie — `resolveBareLocationFromBullet` fails outright rather than silently picking whichever
// name happens to come first.
test('contrast: resolveBareLocationFromBullet fails, never guesses, when a bullet genuinely names more than one component directory as its own subject and the location is bare', () => {
  const scopeText =
    '**8e. Findings.**\n\n' +
    "- **F9.** `Widget`'s own control and `Gadget`'s own control both render similarly " +
    '(`index.tsx:5`, some shared detail) — ambiguous.\n' +
    '- **F10.** unrelated bullet.\n'
  const allSrcFiles = [
    'packages/design-system/src/primitives/Widget/index.tsx',
    'packages/design-system/src/primitives/Gadget/index.tsx',
  ]
  const resolved = resolveBareLocationFromBullet(scopeText, 3, 'index.tsx', allSrcFiles)
  assert.equal(resolved, null)
})

test("checkCitations: an inline-code claim against a bare `index.tsx`, resolved through the bullet's own named component, passes end to end (real file, F3/Dialog shape)", () => {
  const firstLine = readFileSync(
    path.join('packages', 'design-system', 'src', 'primitives', 'Text', 'index.tsx'),
    'utf8',
  )
    .split('\n')[0]
    .trim()
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    `- **F1.** \`Text\`'s own file (\`index.tsx:1\`) opens with \`${firstLine}\` and more prose after it.\n\n` +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.deepEqual(result.failures, [])
  assert.equal(result.inlineClaimCount, 1)
  assert.equal(result.inlineClaimFailureCount, 0)
})

test('contrast: the same shape fails when the claimed code is not actually at the cited line', () => {
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    "- **F1.** `Text`'s own file (`index.tsx:1`) opens with `this text is not really there=1`.\n\n" +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.inlineClaimFailureCount, 1)
  assert.match(
    result.failures.find((f) => f.reason.includes('inline-code claim')).reason,
    /not found at/,
  )
})

// T594's REJECT on #80, item 1: `LOCATION_ONLY_RE`'s own `location` group (`[\w./-]*`) matches
// empty, so a genuinely bare `` `:1` `` (no filename at all, F17's own `` `:96` `` shape) parsed
// with `location === ''` — falsy exactly like a real absence — and `if (!claim.location) continue`
// dropped it unverified rather than routing it through `resolveBareLocationFromBullet` the way a
// *named* bare filename (`index.tsx`) already was. Proof this was a real, false "verified": before
// this fix, swapping the true claim below for a false one (`bogusNeverExists`) left `failures`
// empty and `inlineClaimCount` still counting it — the claim was never actually compared.
test("checkCitations: a genuinely bare `:line` inline claim (no filename at all) resolves through the bullet's own named component and is verified, not silently skipped (F17's own `:96` shape)", () => {
  const firstLine = readFileSync(
    path.join('packages', 'design-system', 'src', 'primitives', 'Text', 'index.tsx'),
    'utf8',
  )
    .split('\n')[0]
    .trim()
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    `- **F1.** \`Text\`'s own file opens with \`:1\` is the \`${firstLine}\` line.\n\n` +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.deepEqual(result.failures, [])
  assert.equal(result.inlineClaimCount, 1)
  assert.equal(result.inlineClaimVerifiedCount, 1)
  assert.equal(result.inlineClaimFailureCount, 0)
  assert.equal(result.inlineClaimUnresolvableCount, 0)
})

test('contrast: the same genuinely bare `:line` shape fails when the claimed code is not actually there — proving the claim above is really checked, not merely counted', () => {
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    "- **F1.** `Text`'s own file opens with `:1` is the `bogusNeverExists=1` line.\n\n" +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.inlineClaimVerifiedCount, 0)
  assert.equal(result.inlineClaimFailureCount, 1)
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /not found at/)
})

test('checkCitations: a bare inline-code claim whose location resolves to no file at all is counted as unresolvable, never as verified', () => {
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    "- **F1.** `NoSuchComponentAnywhere`'s own file opens with `:1` is the `whatever=1` line.\n\n" +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.inlineClaimVerifiedCount, 0)
  assert.equal(result.inlineClaimUnresolvableCount, 1)
  assert.equal(result.inlineClaimFailureCount, 0)
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /did not resolve to exactly one file/)
})

// --- T595: the out-of-range hole in `--check-citations` mode ---------------------------------
// `findInlineCodeClaims` skips every span `CITATION_RE` already parsed, so the out-of-range branch
// a few lines above (the one guarding double-quoted citations) never sees an inline-code claim —
// it has to be caught in this loop or nowhere. Before this fix it was a bare `continue`: dropped
// from every printed count, and `--check-citations` still exited 0.

test('checkCitations: an inline-code claim whose cited line is past the end of its real file fails, naming the real line count (T595, was silently skipped and still exited 0)', () => {
  const filePath = path.join('packages', 'design-system', 'src', 'primitives', 'Text', 'index.tsx')
  const lineCount = readFileSync(filePath, 'utf8').split('\n').length
  const outOfRangeLine = lineCount + 1000
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    `- **F1.** \`Text\`'s own file (\`index.tsx:${outOfRangeLine}\`) opens with \`size="lg"\` and more prose after it.\n\n` +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.inlineClaimCount, 1)
  assert.equal(result.inlineClaimOutOfRangeCount, 1)
  assert.equal(result.inlineClaimVerifiedCount, 0)
  assert.equal(result.inlineClaimFailureCount, 0)
  assert.equal(result.inlineClaimUnresolvableCount, 0)
  const failure = result.failures.find((f) => f.reason.includes('inline-code claim'))
  assert.ok(failure, 'expected an inline-code-claim failure')
  assert.match(failure.reason, new RegExp(`has ${lineCount} lines, cited up to :${outOfRangeLine}`))
})

test('contrast: the same inline-code claim shape, cited in range with the text really on that line, still passes and is counted as verified — the fix is a boundary, not a blanket rejection', () => {
  const firstLine = readFileSync(
    path.join('packages', 'design-system', 'src', 'primitives', 'Text', 'index.tsx'),
    'utf8',
  )
    .split('\n')[0]
    .trim()
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    `- **F1.** \`Text\`'s own file (\`index.tsx:1\`) opens with \`${firstLine}\` and more prose after it.\n\n` +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.deepEqual(result.failures, [])
  assert.equal(result.inlineClaimCount, 1)
  assert.equal(result.inlineClaimVerifiedCount, 1)
  assert.equal(result.inlineClaimOutOfRangeCount, 0)
})

// The inline loop's own malformed-line-spec branch (`if (!ranges) continue`, now a counted
// failure) cannot be exercised the same end-to-end way: `claim.lineSpec` is always
// `LOCATION_ONLY_RE`'s own capture group (`` `([\w./-]*):(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)`` `` —
// see `scripts/checks/state-coverage.mjs`), built from exactly the atoms `parseLineSpec`'s
// per-part regex accepts, so `parseLineSpec` can never return `null` for a `lineSpec` that regex
// produced — confirmed here directly, the same unreachable-by-construction shape `parseLineSpec`'s
// own comment already documents for its citation-level twin (`parseCitations`'s `!ranges` branch:
// "the citation regex already guarantees digits and dashes only, so this is a belt"). No
// `readmeText` reaches the inline loop's `!ranges` branch today, so no end-to-end `checkCitations`
// test can turn it red — one written to "prove" that would pass before the fix too, on both sides
// of it, and prove nothing. The fix (a counted failure instead of a silent `continue`) is still
// correct defence against a future widening of that regex; this is what the regex guarantees today.
test("parseLineSpec never returns null for output shaped by LOCATION_ONLY_RE — the inline loop's malformed-line-spec branch is unreachable through any real citation text, the same as its citation-level twin", () => {
  assert.deepEqual(parseLineSpec('39'), [[39, 39]])
  assert.deepEqual(parseLineSpec('550-551'), [[550, 551]])
  assert.deepEqual(parseLineSpec('441,344-345'), [
    [441, 441],
    [344, 345],
  ])
  // Genuinely malformed input parseLineSpec was written to reject — never producible by
  // LOCATION_ONLY_RE, but this is the contract the unreachable branch defends.
  assert.equal(parseLineSpec('abc'), null)
  assert.equal(parseLineSpec('1-'), null)
  assert.equal(parseLineSpec(''), null)
})

test('checkCitations: the inline-claim counts it returns always sum to the number of claims found (sum invariant, T595) — a fixture mixing a verified and a failing claim', () => {
  const firstLine = readFileSync(
    path.join('packages', 'design-system', 'src', 'primitives', 'Text', 'index.tsx'),
    'utf8',
  )
    .split('\n')[0]
    .trim()
  const filePath = path.join('packages', 'design-system', 'src', 'primitives', 'Text', 'index.tsx')
  const lineCount = readFileSync(filePath, 'utf8').split('\n').length
  const outOfRangeLine = lineCount + 1000
  const readmeText =
    '**8c. Record 2 — every handoff.**\n\n' +
    `- **F1.** \`Text\`'s own file (\`index.tsx:1\`) opens with \`${firstLine}\` and more prose after it.\n` +
    `- **F2.** \`Text\`'s own file (\`index.tsx:${outOfRangeLine}\`) opens with \`size="lg"\` and more prose after it.\n` +
    "- **F3.** `NoSuchComponentAnywhere`'s own file opens with `:1` is the `whatever=1` line.\n\n" +
    '**Cell counts,'
  const result = checkCitations({ readmeText })
  assert.equal(result.inlineClaimCount, 3)
  const sum =
    result.inlineClaimVerifiedCount +
    result.inlineClaimFailureCount +
    result.inlineClaimUnresolvableCount +
    result.inlineClaimOutOfRangeCount +
    result.inlineClaimMalformedLineSpecCount
  assert.equal(sum, result.inlineClaimCount)
  assert.equal(result.inlineClaimVerifiedCount, 1)
  assert.equal(result.inlineClaimOutOfRangeCount, 1)
  assert.equal(result.inlineClaimUnresolvableCount, 1)
})

test('checkHandoffTally: passes when every row (row-8-scoped) agrees with its own citation count', () => {
  const readme =
    '**8c. Record 2 — every handoff.**\n\n' +
    '| File | Handoffs | Cited lines |\n' +
    '| --- | --- | --- |\n' +
    '| `a.md` | 2 | `:1` "one" and `:2` "two" |\n' +
    '| `b.md` | 0 | — |\n\n' +
    '**Total: 2 handoffs across 1 files with at least one**\n\n' +
    '**Cell counts,'
  assert.deepEqual(checkHandoffTally(readme).failures, [])
})

test('checkHandoffTally: fails when a row Handoffs number disagrees with its own citation count', () => {
  const readme =
    '**8c. Record 2 — every handoff.**\n\n' +
    '| File | Handoffs | Cited lines |\n' +
    '| --- | --- | --- |\n' +
    '| `a.md` | 3 | `:1` "one" and `:2` "two" |\n\n' +
    '**Total: 3 handoffs across 1 files with at least one**\n\n' +
    '**Cell counts,'
  const result = checkHandoffTally(readme)
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /a\.md.*reads 3 but 2/)
})

test('checkHandoffTally: fails when the Total line disagrees with the table row sum', () => {
  const readme =
    '**8c. Record 2 — every handoff.**\n\n' +
    '| File | Handoffs | Cited lines |\n' +
    '| --- | --- | --- |\n' +
    '| `a.md` | 1 | `:1` "one" |\n\n' +
    '**Total: 2 handoffs across 1 files with at least one**\n\n' +
    '**Cell counts,'
  const result = checkHandoffTally(readme)
  assert.equal(result.failures.length, 1)
  assert.match(result.failures[0].reason, /disagrees with the table's own row sum, 1/)
})

test('findDeferralHitsInStories: finds the vocabulary in a story file and attributes it to its own component', () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Widget', 'Widget.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    writeFileSync(
      storyFile,
      '// hover — none; owned by `Button` and by nothing else.\nexport const X = {}\n',
    )
    const allSrcFiles = [storyFile.split(path.sep).join('/')]
    const hits = findDeferralHitsInStories(allSrcFiles)
    assert.equal(hits.length, 1)
    assert.equal(hits[0].component, 'Widget')
    assert.equal(hits[0].line, 1)
  })
})

test('findDeferralHitsInStories: a non-story .tsx file is never scanned', () => {
  withFixtureTree((dir) => {
    const indexFile = path.join(dir, 'src', 'primitives', 'Widget', 'index.tsx')
    mkdirSync(path.dirname(indexFile), { recursive: true })
    writeFileSync(indexFile, '// owned by `Button`\n')
    const allSrcFiles = [indexFile.split(path.sep).join('/')]
    assert.deepEqual(findDeferralHitsInStories(allSrcFiles), [])
  })
})

// --- `reviewer`'s fourth REJECT on PR #80, item A3: no test proved any of the three row-8 gates
// actually fails on bad input — this one was named "…fails" but only ever exercised
// `parseCitations` by hand, never called `checkDeferralVocabularyCoverage` itself. `allSrcFiles` is
// injectable for exactly this reason: the check has to see the live source on every real run (the
// same reason `state-coverage.mjs`'s own consistency mode never takes a fixture tree either), but a
// test proving the *gate* fails needs a fixture it controls, not the live tree. -------------------

test('checkDeferralVocabularyCoverage: a real hit whose component has no table row and no exclusion fails, end to end', () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Stray', 'Stray.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    writeFileSync(storyFile, '// hover — none; owned by `Button` and by nothing else.\n')
    const readme =
      '**8c-bis. Story comments.**\n\n' +
      '| Component | Quotes |\n' +
      '| --- | --- |\n' +
      '| `Known` | `:1` "owned by `Button`" — filed. |\n\n' +
      'No exclusions here.\n\n' +
      '**8d. The no-owner list**\n'
    const result = checkDeferralVocabularyCoverage(readme, {
      allSrcFiles: [storyFile.split(path.sep).join('/')],
    })
    assert.equal(result.failures.length, 1)
    assert.match(result.failures[0].reason, /Stray\.stories\.tsx:1 carries deferral vocabulary/)
  })
})

test('checkDeferralVocabularyCoverage: the same hit passes once its own line is cited in its table row (contrast)', () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Known', 'Known.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    writeFileSync(storyFile, '// hover — none; owned by `Button` and by nothing else.\n')
    const readme =
      '**8c-bis. Story comments.**\n\n' +
      '| Component | Quotes |\n' +
      '| --- | --- |\n' +
      '| `Known` | `:1` "owned by `Button` and by nothing else." — filed. |\n\n' +
      'No exclusions here.\n\n' +
      '**8d. The no-owner list**\n'
    const result = checkDeferralVocabularyCoverage(readme, {
      allSrcFiles: [storyFile.split(path.sep).join('/')],
    })
    assert.deepEqual(result.failures, [])
  })
})

test('checkDeferralVocabularyCoverage: two hits in one prose block are both excused by one cited line inside it (block-joining, latent-proof against a wrapped phrase)', () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Known', 'Known.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    // Two lines, one block (no blank line between them): the table only cites line 1, but line 2
    // carries its own, independent deferral hit.
    writeFileSync(
      storyFile,
      '// hover — none; owned by `Button` and by nothing else.\n' +
        '// press — none either; covered by `Button` alone.\n',
    )
    const readme =
      '**8c-bis. Story comments.**\n\n' +
      '| Component | Quotes |\n' +
      '| --- | --- |\n' +
      '| `Known` | `:1` "owned by `Button` and by nothing else." — filed. |\n\n' +
      'No exclusions here.\n\n' +
      '**8d. The no-owner list**\n'
    const result = checkDeferralVocabularyCoverage(readme, {
      allSrcFiles: [storyFile.split(path.sep).join('/')],
    })
    // Both lines sit in the same prose block as the cited `:1`, so both are excused.
    assert.deepEqual(result.failures, [])
  })
})

test("checkDeferralVocabularyCoverage: a hit in a *second, separate* prose block of an already-listed component still fails (quote-level, not component-level — the fourth REJECT's own second finding)", () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Known', 'Known.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    // Two blocks, separated by a blank line: the table cites a line in the first block only. The
    // second block carries its own, independent deferral hit that no citation names.
    writeFileSync(
      storyFile,
      '// hover — none; owned by `Button` and by nothing else.\n' +
        '\n' +
        '// press — none either; covered by `Button` alone.\n',
    )
    const readme =
      '**8c-bis. Story comments.**\n\n' +
      '| Component | Quotes |\n' +
      '| --- | --- |\n' +
      '| `Known` | `:1` "owned by `Button` and by nothing else." — filed. |\n\n' +
      'No exclusions here.\n\n' +
      '**8d. The no-owner list**\n'
    const result = checkDeferralVocabularyCoverage(readme, {
      allSrcFiles: [storyFile.split(path.sep).join('/')],
    })
    // Pre-fix, `Known` having *any* table row excused every hit anywhere in its own file — this is
    // exactly the shape `reviewer`'s fourth REJECT found: a new, false deferral in an
    // already-listed component's own second block passed unseen.
    assert.equal(result.failures.length, 1)
    assert.match(result.failures[0].reason, /Known\.stories\.tsx:3 carries deferral vocabulary/)
  })
})

// T594 M4, REJECT #5 on #80/#79: the excuse condition used to check only block *membership* — a
// citation anywhere in the same, no-blank-line-broken block excused every hit in it, and this
// package's own blocks run 30+ lines (`AccountErasurePanel.stories.tsx` 101-135). A single hit far
// from its citation, still in the same one continuous block, used to pass; this plants that exact
// shape with a filler-padded block, no blank line anywhere, so it stays one block by the same rule
// the block-joining test above relies on.
test('checkDeferralVocabularyCoverage: a hit far from its own citation, but still in the same one continuous block, now fails — block membership alone is no longer enough (T594 M4)', () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Known', 'Known.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    const filler = Array.from({ length: 20 }, (_, i) => `// filler line ${i + 1}, no vocabulary`)
    writeFileSync(
      storyFile,
      '// hover — none; owned by `Button` and by nothing else.\n' +
        filler.join('\n') +
        '\n' +
        '// press — none either; covered by `Button` alone.\n',
    )
    const readme =
      '**8c-bis. Story comments.**\n\n' +
      '| Component | Quotes |\n' +
      '| --- | --- |\n' +
      '| `Known` | `:1` "owned by `Button` and by nothing else." — filed. |\n\n' +
      'No exclusions here.\n\n' +
      '**8d. The no-owner list**\n'
    const result = checkDeferralVocabularyCoverage(readme, {
      allSrcFiles: [storyFile.split(path.sep).join('/')],
    })
    assert.equal(result.failures.length, 1)
    assert.match(result.failures[0].reason, /Known\.stories\.tsx:22 carries deferral vocabulary/)
  })
})

test('contrast: a hit close to its own citation, in the same block, still passes (T594 M4)', () => {
  withFixtureTree((dir) => {
    const storyFile = path.join(dir, 'src', 'primitives', 'Known', 'Known.stories.tsx')
    mkdirSync(path.dirname(storyFile), { recursive: true })
    writeFileSync(
      storyFile,
      '// hover — none; owned by `Button` and by nothing else.\n' +
        '// press — none either; covered by `Button` alone.\n',
    )
    const readme =
      '**8c-bis. Story comments.**\n\n' +
      '| Component | Quotes |\n' +
      '| --- | --- |\n' +
      '| `Known` | `:1` "owned by `Button` and by nothing else." — filed. |\n\n' +
      'No exclusions here.\n\n' +
      '**8d. The no-owner list**\n'
    const result = checkDeferralVocabularyCoverage(readme, {
      allSrcFiles: [storyFile.split(path.sep).join('/')],
    })
    assert.deepEqual(result.failures, [])
  })
})

test('countRecord1Cells/countRecord3Cells: classify none, the one play-driven unresolved, and covered', () => {
  const computed = {
    localElements: [
      {
        elements: [
          {
            coveredBy: {
              hover: ['none'],
              focusVisible: [
                'unresolved: EscapeReturnsFocusToTrigger (play-driven; frame not provable statically)',
              ],
              active: ['SomeStory'],
            },
          },
          {
            coveredBy: {
              hover: ['unresolved: no implied role'],
              focusVisible: ['none'],
              active: ['none'],
            },
          },
        ],
      },
    ],
    matrices: {
      Widget: [
        {
          variantSize: '(no local interactive element)',
          rest: ['N/A'],
          hover: ['N/A'],
          focusVisible: ['N/A'],
          active: ['N/A'],
          disabled: ['N/A'],
        },
      ],
      Other: [
        {
          variantSize: '(unresolved matches — no row, printed rather than dropped)',
          rest: ['N/A'],
          hover: ['unresolved: x'],
          focusVisible: ['N/A'],
          active: ['N/A'],
          disabled: ['N/A'],
        },
        {
          variantSize: 'md',
          rest: ['2 real call sites'],
          hover: ['none'],
          focusVisible: ['Story'],
          active: ['none'],
          disabled: ['none'],
        },
      ],
    },
  }
  const r1 = countRecord1Cells(computed)
  // Element 1: hover=none, focusVisible=unresolved (play-driven), active=covered.
  // Element 2: hover=unresolved ("no implied role" — counts as unresolved, whatever the reason,
  // never folded into `none`: the orchestrator's own correction after the play-driven-only version
  // shipped), focusVisible=none, active=none.
  assert.deepEqual(r1, { none: 3, unresolved: 2, covered: 1 })

  const r3 = countRecord3Cells(computed)
  // Only `Other`'s real `md` row counts (the placeholder and the unresolved-matches info row are
  // both excluded): rest=covered, hover=none, focusVisible=covered, active=none, disabled=none.
  assert.deepEqual(r3, { none: 3, unresolved: 0, covered: 2 })
})

test('countRecord1Cells/countRecord3Cells: never folds an unresolved reason into none, whatever the reason', () => {
  // Plants one cell of each of the three renderable values, in both records, so a future version
  // that re-merges `unresolved` into `none` (the exact defect this test exists to catch — see the
  // orchestrator's own correction above) fails here first, loudly, rather than only in a hand-read
  // of the printed line.
  const computed = {
    localElements: [
      {
        elements: [
          {
            coveredBy: {
              hover: ['none'],
              focusVisible: ['unresolved: dynamic role'],
              active: ['SomeStory'],
            },
          },
        ],
      },
    ],
    matrices: {
      Widget: [
        {
          variantSize: 'md',
          rest: ['none'],
          hover: ['unresolved: ancestor of a forced descendant (…)'],
          focusVisible: ['Story'],
          active: ['none'],
          disabled: ['unresolved: no implied role'],
        },
      ],
    },
  }
  assert.deepEqual(countRecord1Cells(computed), { none: 1, unresolved: 1, covered: 1 })
  // Record 3's fixture row carries 2 `unresolved` (hover, disabled), 2 `none` (rest, active) and 1
  // `covered` (focus-visible) — a distinct 2/2/1 shape from Record 1's 1/1/1, on purpose, so the
  // two records cannot pass by accidentally sharing one counter.
  assert.deepEqual(countRecord3Cells(computed), { none: 2, unresolved: 2, covered: 1 })
})
