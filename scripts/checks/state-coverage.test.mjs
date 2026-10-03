// Regression tests for T594's extractor (state-coverage.mjs), including the orchestrator's own
// remediation of this task's second hand-back: consistency mode now renders record 1 and every
// primitive matrix as markdown between `<!-- state-coverage:begin/end -->` markers instead of
// diffing a JSON snapshot against itself, and a coverage cell distinguishes a confirmed `'none'`
// from an `'unresolved: <reason>'` it could not settle. Follows story-docs.test.mjs's own
// `node --test` conventions: real functions, small fixtures, node:assert/strict, no mocking.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  mkdtempSync,
  writeFileSync,
  mkdirSync,
  rmSync,
  readFileSync,
  cpSync,
  symlinkSync,
  appendFileSync,
  readdirSync,
  realpathSync,
} from 'node:fs'
import { spawnSync } from 'node:child_process'
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
  findPlayClickTarget,
  findStateConditionalClass,
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
  getComponentPropDefaults,
  evaluateMergedArgsObject,
  buildStoryPropsScope,
  buildFileValueScope,
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
  findUnaccountedForceStates,
  describeMissingForceState,
  KNOWN_UNACCOUNTED_FORCE_STATES,
  readAllSourceFiles,
  answerSaysImpossible,
  findVocabularyBoundarySpans,
  resolveSpecAnswerForState,
  mapComponentKeyToSpecFile,
  classifyRecord1NoneCells,
  classifyRecord3NoneCells,
  classifyImpossiblePerSpec,
  parseRow8DebtEntries,
  parseRow8PermanentEntries,
  checkCellGate,
  RECORD1_HEADERS,
  RECORD3_HEADERS,
  PRIMITIVE_NAMES,
} from './state-coverage.mjs'
import { deriveVocabulary } from './spec-completeness.mjs'

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

// --- T671 (row 8, H5, Cause C, "8j"): the click-half — `findStateConditionalClass` and
// `findPlayClickTarget`, `Tooltip.stories.tsx`'s own `Pinned`/`pinOpen` shape. ---------------------

const PLAY_CLICK_SOURCE = `
export const Pinned = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const trigger = canvas.getByRole('button')
    await userEvent.click(trigger)
    await canvas.findByRole('tooltip')
    await userEvent.unhover(trigger)
    trigger.blur()
  },
}
`

test("findPlayClickTarget resolves a userEvent.click() to its earlier-bound getByRole() locator (Tooltip's own pinOpen shape)", () => {
  const sourceFile = parse(PLAY_CLICK_SOURCE)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const playProp = node.properties.find((p) => p.name.getText() === 'play')
  const target = findPlayClickTarget(playProp.initializer.body)
  assert.deepEqual(target, { role: 'button', name: null })
})

test('findPlayClickTarget finds nothing for a play() that only hovers (contrast)', () => {
  const sourceFile = parse(PLAY_HOVER_ONLY_SOURCE)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const playProp = node.properties.find((p) => p.name.getText() === 'play')
  const target = findPlayClickTarget(playProp.initializer.body)
  assert.equal(target, null)
})

test('findPlayFocusTarget finds nothing for a play() that only clicks (contrast, the mirror gap)', () => {
  const sourceFile = parse(PLAY_CLICK_SOURCE)
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const playProp = node.properties.find((p) => p.name.getText() === 'play')
  const target = findPlayFocusTarget(playProp.initializer.body)
  assert.equal(target, null)
})

test("findStateConditionalClass finds a ternary conditioned on the bare identifier `pinned` (Tooltip's own shape)", () => {
  const sourceFile = parse(
    `const el = <button className={pinned ? 'border-border-strong' : 'border-transparent'} />`,
  )
  // Walk to the JSX className attribute's own expression the same way findLocalElements does.
  let exprNode = null
  function visit(node) {
    if (exprNode) return
    if (
      node.kind !== undefined &&
      node.name &&
      node.name.getText &&
      node.name.getText() === 'className' &&
      node.initializer
    ) {
      exprNode = node.initializer.expression
      return
    }
    node.forEachChild?.(visit)
  }
  visit(sourceFile)
  const found = findStateConditionalClass(exprNode, 'active')
  assert.deepEqual(found, {
    identifier: 'pinned',
    whenTrue: "'border-border-strong'",
    whenFalse: "'border-transparent'",
  })
})

test('findStateConditionalClass finds nothing for a ternary conditioned on an unlisted identifier (contrast — never a general state-shaped-name vocabulary)', () => {
  let exprNode = null
  const sourceFile = parse(
    `const el = <button className={pressed ? 'border-border-strong' : 'border-transparent'} />`,
  )
  function visit(node) {
    if (exprNode) return
    if (node.name && node.name.getText && node.name.getText() === 'className' && node.initializer) {
      exprNode = node.initializer.expression
      return
    }
    node.forEachChild?.(visit)
  }
  visit(sourceFile)
  assert.equal(findStateConditionalClass(exprNode, 'active'), null)
})

test("findLocalElements reads Tooltip's own trigger as activeStateConditional, never as a literal active pseudo-class", () => {
  const source = `
function Tooltip() {
  return (
    <button className={cx('border-2', pinned ? 'border-border-strong' : 'border-transparent')}>
      {children}
    </button>
  )
}
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [el] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(el.active, null)
  assert.deepEqual(el.activeStateConditional, {
    identifier: 'pinned',
    whenTrue: "'border-border-strong'",
    whenFalse: "'border-transparent'",
  })
})

test('buildElementMatrix credits a state-conditional active cell directly (covered), from a play-click match — never unresolved, unlike a play-driven focus', () => {
  const elements = [
    {
      tag: 'button',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'Tooltip/index.tsx',
      line: 259,
      active: null,
      activeStateConditional: { identifier: 'pinned', whenTrue: "'a'", whenFalse: "'b'" },
    },
  ]
  const storyStates = [
    {
      exportName: 'Pinned',
      forced: null,
      playFocus: null,
      playClick: { role: 'button', name: null },
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].active, ['Pinned'])
})

test('buildElementMatrix never credits a play-click match when the element carries no state-conditional active class (contrast — the narrow gate holds for an ordinary button)', () => {
  const elements = [
    {
      tag: 'button',
      role: null,
      tabIndex: null,
      ariaHidden: false,
      isHelper: false,
      text: '',
      file: 'Widget/index.tsx',
      line: 10,
      active: null,
      activeStateConditional: null,
    },
  ]
  const storyStates = [
    {
      exportName: 'ClickedViaPlay',
      forced: null,
      playFocus: null,
      playClick: { role: 'button', name: null },
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].active, ['none'])
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
    // T686: the own-story credit is checked against what Menu renders, so the fixture's Menu must
    // render the `menuitemradio` its stories force (`MenuItemRow`'s own dynamic role); a Menu that
    // returns null depicts no such frame.
    [
      '/repo/packages/design-system/src/primitives/Menu/index.tsx',
      MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE,
    ],
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

test("buildAxisMatrix: the unresolved row's hover cell credits the row the story actually resolved to directly, not a bare pointer note (T595)", () => {
  const matrix = buildAxisMatrix('Button', redirectFixtureInstances())
  const unresolvedRow = matrix.find((r) => r.variantSize === 'ghost|unresolved')
  const resolvedRow = matrix.find((r) => r.variantSize === 'ghost|md')
  assert.ok(resolvedRow, "the story's own resolved axis ('md') gets its own row")
  assert.deepEqual(resolvedRow.hover, ['Widget:Hover'])
  // T595: real coverage the story already established on the target row is credited here too —
  // the same story name, not a `'unresolved: axis resolved only per story (→ ghost|md)'` pointer a
  // reader would otherwise have to follow by hand.
  assert.deepEqual(unresolvedRow.hover, ['Widget:Hover'])
  // The states the story never forced stay a genuine, uncontested `'none'` — the fix is scoped to
  // the one state that actually resolved elsewhere, not a blanket redirect for the whole row.
  assert.deepEqual(unresolvedRow.active, ['none'])
})

test('buildAxisMatrix: a call site is credited to every row its own stories resolve it to, never only one (T595, FavouriteToggle/Dialog shape)', () => {
  // The same source line — one dynamic `size`/`variant` no literal can key a row on — resolves to
  // `ghost|md` under one story (hover) and to `ghost|lg` under a different one (active), exactly
  // `FavouriteToggle`'s own three call sites against `Hover`/`FocusVisible`/`Active` (all default
  // `size` to `'md'`) versus `RealisticProfileHeader` (`size="lg"`, no force-state at all — so it
  // never appears here, only in `rest`). Crediting only the *first* redirect found would silently
  // drop the second story's own real knowledge; both must show up on their own state.
  const instances = [
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
    {
      kind: 'composed-story',
      componentKey: 'composites/Widget',
      file: 'composites/Widget/Widget.stories.tsx',
      storyName: 'RealisticHeader',
      variant: { value: 'ghost', resolved: 'explicit' },
      size: { value: 'lg', resolved: 'resolved-from-story' },
      forced: { state: 'active', role: 'button', name: 'Toggle', selector: null, nth: null },
      playFocus: null,
      sourceLine: 6,
      sourceFile: 'composites/Widget/index.tsx',
    },
  ]
  const matrix = buildAxisMatrix('Button', instances)
  const unresolvedRow = matrix.find((r) => r.variantSize === 'ghost|unresolved')
  assert.deepEqual(unresolvedRow.hover, ['Widget:Hover'])
  assert.deepEqual(unresolvedRow.active, ['Widget:RealisticHeader'])
  // Contrast within the same row: no story anywhere forces focus-visible on this source line, so
  // it stays a genuine, uncontested `'none'` rather than borrowing either neighbour's credit.
  assert.deepEqual(unresolvedRow.focusVisible, ['none'])
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

// --- T595 (row 8, group 3): `inertByConstruction` — an element that is `hidden` and
// `tabIndex={-1}`, both literal, cannot receive a hover, a focus-visible ring or a press in any
// frame (`UploadControl`'s own hidden file input). Both required contrasts from the task brief:
// a `hidden` element that is genuinely reachable in another state (a dynamic `hidden={…}`) must
// not be swallowed, and a `tabIndex={-1}` element that IS hoverable must not be swallowed either. ---

test('findLocalElements marks a hidden, tabIndex={-1} input as inert by construction (UploadControl shape)', () => {
  const source = `
function UploadControl() {
  return (
    <input
      type="file"
      accept=".aoe2record"
      hidden
      tabIndex={-1}
      disabled={isUploading}
      onChange={handleInputChange}
    />
  )
}
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [found] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.inertByConstruction, true)
})

test('required contrast: a dynamically hidden element (hidden={condition}) is never inert by construction, even with tabIndex={-1}', () => {
  const source = `
function Panel({ collapsed }) {
  return (
    <div hidden={collapsed} tabIndex={-1} className="hover:bg-surface-sunken">
      Detail
    </div>
  )
}
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [found] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.inertByConstruction, false)
})

test('required contrast: a tabIndex={-1} element that IS hoverable is never inert by construction (no hidden attribute at all)', () => {
  const source = `
function SectionHeading({ id, children }) {
  return (
    <h2 id={id} tabIndex={-1} className="hover:text-text-primary">
      {children}
    </h2>
  )
}
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [found] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.inertByConstruction, false)
  assert.equal(found.hover, 'hover:text-text-primary')
})

test('a hidden element that is not tabIndex={-1} is never inert by construction either (hidden alone is not the rule)', () => {
  const source = `
function Widget() {
  return <input type="file" hidden onChange={handleChange} />
}
`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [found] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.inertByConstruction, false)
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

// --- T675 M2 (reviewer finding, confirmed by running `extractPseudoClasses` directly): the old
// regex only ever matched `${prefix}:` at the very start of a class token (immediately after
// whitespace or string-start) — a real Tailwind variant chain with another modifier ahead of the
// pseudo-class (`enabled:hover:ring-1`, `SearchBox`'s own input; `focus-visible:enabled:outline-2`,
// reverse order) never matched at all, silently reading as `null` ("no hover") even though the
// class genuinely paints one. Fixed by scanning every colon-delimited variant segment of each class
// token for an exact match, not only the first. ---------------------------------------------------

test('extractPseudoClasses finds hover behind a leading enabled: modifier (SearchBox/ThirdPartyObjectionForm shape)', () => {
  const result = extractPseudoClasses(['enabled:hover:ring-1 enabled:hover:border-border-strong'])
  assert.equal(result.hover, 'enabled:hover:ring-1 enabled:hover:border-border-strong')
})

test('extractPseudoClasses finds focus-visible even when another modifier follows it in the chain (reverse order)', () => {
  const result = extractPseudoClasses(['focus-visible:enabled:outline-2'])
  assert.equal(result['focus-visible'], 'focus-visible:enabled:outline-2')
})

// Contrast (required by the same finding): a plain word that merely contains "hover" as a substring
// is not a variant at all, and an arbitrary-value data attribute that merely names "hover" inside
// its brackets is not the `hover:` pseudo-class either — both must stay `null`.
test('extractPseudoClasses contrast: "hoverable" and a data-[hover=true]: arbitrary variant are never read as hover', () => {
  const result = extractPseudoClasses(['hoverable', 'data-[hover=true]:underline'])
  assert.equal(result.hover, null)
})

// The absence case the reviewer named directly: once the class is actually read, an element with a
// real (if undetected-until-now) hover utility and no story forcing Hover must render as
// `<class> → none` — a real, honest gap — never the falsely reassuring `none → none`, which reads as
// "nothing paints and nothing was missed" when something does paint and was.
test('renderRecord1: an enabled:hover:-only element with no covering story reads as "<class> → none", never "none → none"', () => {
  const source = `const el = <button className="enabled:hover:bg-surface-sunken">Click</button>`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const [el] = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(el.hover, 'enabled:hover:bg-surface-sunken')
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
  // Scoped to the Hover column alone: the other two columns genuinely are 'none → none' here (this
  // button carries no focus-visible/active class of any kind), which is correct and not the bug —
  // only the Hover cell must stop reading as a confirmed, reassuring 'none' once its real class is
  // read.
  assert.doesNotMatch(rendered, /\| none → none \| none → none \| none → none \|/)
  assert.match(rendered, /\| enabled:hover:bg-surface-sunken → none \|/)
})

// `group-hover/<name>:` (and bare `group-hover:`) paint on the ancestor carrying `group`/`group/<name>`
// — the element a pointer actually hovers — never on the descendant utility class sits on
// (`PlayerResultRow`'s alias, `FavouritesList`'s alias: neither is itself interactive, hoverable, or
// even present in Record 1 on its own). Credited into the ancestor's own `hover` field instead of
// ever becoming a row of its own.
const GROUP_HOVER_SOURCE = `
function Widget() {
  return (
    <a href="/match/1" className="group/row-link flex flex-col">
      <span className="font-sans text-sm group-hover/row-link:underline group-hover/row-link:decoration-2">
        Alias
      </span>
    </a>
  )
}
`

test('findLocalElements credits group-hover/<name>: on a descendant to the ancestor carrying group/<name>, not to the descendant', () => {
  const sourceFile = parse(GROUP_HOVER_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found.length, 1, 'the group-hover span must never become a row of its own')
  assert.equal(found[0].tag, 'a')
  assert.equal(found[0].hover, 'group-hover/row-link:underline group-hover/row-link:decoration-2')
})

// Contrast: a bare `group-hover:` (no `/<name>`) must not be credited to an ancestor carrying a
// *named* `group/<name>` — Tailwind itself never pairs the two, and neither must this checker.
const GROUP_HOVER_NAME_MISMATCH_SOURCE = `
function Widget() {
  return (
    <a href="/match/1" className="group/row-link flex flex-col">
      <span className="font-sans text-sm group-hover:underline">Alias</span>
    </a>
  )
}
`

test('contrast: a bare group-hover: is not credited to an ancestor carrying a named group/<name>', () => {
  const sourceFile = parse(GROUP_HOVER_NAME_MISMATCH_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  const anchor = found.find((el) => el.tag === 'a')
  assert.ok(anchor)
  assert.equal(anchor.hover, null)
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

// --- T674: `foreignExtents` (real elements of the same implied role this exact call's own `pool`
// cannot see) join the `nth` walk without ever being reachable as `candidate` themselves. ----------

test("resolveNameMatch never returns 'match' for a foreign entry — nth landing on its own position rejects the candidate under test instead", () => {
  const cand = { isHelper: false, line: 20 }
  const foreignBefore = { isHelper: false, line: 10 }
  // nth: 0 lands on the foreign entry's own position (sorted first) — `cand` is not there, and the
  // foreign entry itself can never be `=== candidate`, so this can never come back 'match'.
  assert.equal(
    resolveNameMatch({
      candidate: cand,
      pool: [cand],
      name: null,
      nth: 0,
      foreignExtents: [foreignBefore],
    }),
    'reject',
  )
  // nth: 1, past the foreign entry, lands on `cand` itself.
  assert.equal(
    resolveNameMatch({
      candidate: cand,
      pool: [cand],
      name: null,
      nth: 1,
      foreignExtents: [foreignBefore],
    }),
    'match',
  )
})

test('resolveNameMatch (via foreignExtents): a placed foreign entry before the candidate shifts the cursor, the same one after it does not', () => {
  const a = { isHelper: false, line: 5 }
  const cand = { isHelper: false, line: 20 }
  const pool = [a, cand]
  // Baseline, no foreign entry: nth: 1 is `cand` (position 1, after `a`'s own position 0).
  assert.equal(resolveNameMatch({ candidate: cand, pool, name: null, nth: 1 }), 'match')
  // A foreign entry at line 10, between `a` and `cand`, occupies the real position `cand` used to
  // stand in — `nth: 1` now lands on the foreign entry instead, never `cand`.
  const foreignBefore = { isHelper: false, line: 10 }
  assert.equal(
    resolveNameMatch({
      candidate: cand,
      pool,
      name: null,
      nth: 1,
      foreignExtents: [foreignBefore],
    }),
    'reject',
  )
  // Contrast: the same foreign entry placed after `cand` (line 30) never reaches the walk before
  // `nth: 1` is already settled on `cand` — no shift.
  const foreignAfter = { isHelper: false, line: 30 }
  assert.equal(
    resolveNameMatch({ candidate: cand, pool, name: null, nth: 1, foreignExtents: [foreignAfter] }),
    'match',
  )
})

test("resolveNameMatch is ambiguous, never 'match', when a foreignExtents entry is unplaceable (T674 round 2: a silently dropped unplaceable foreign entry let nth land on the wrong pool member)", () => {
  const a = { isHelper: false, line: 5 }
  const cand = { isHelper: false, line: 20 }
  const pool = [a, cand]
  // `isHelper: true` with no `helperCallSites` and no `scope` — `candidateExtent`'s own
  // `'unplaceable'` kind (`helperNthPosition`'s `!c.helperCallSites || !scope` branch).
  const unplaceableForeign = { isHelper: true, line: null }
  assert.equal(
    resolveNameMatch({
      candidate: cand,
      pool,
      name: null,
      nth: 1,
      foreignExtents: [unplaceableForeign],
    }),
    'ambiguous',
  )
  // Proven red by temporarily commenting out the early
  // `if (foreignPositions.some((e) => e.kind === 'unplaceable')) return 'ambiguous'` line in
  // resolveNameMatch: this assertion then fails with `'match'` (the walk silently drops the
  // unplaceable foreign entry from the ordering and lands nth: 1 on `cand` as if it were never
  // there) — see this task's report for the exact failure output.
})

test("resolveNameMatch is ambiguous, never 'match', when a foreignExtents entry has an unresolvable .map()/.flatMap() width ('unknown-width' — an iteration candidate whose own backing array this call's scope cannot resolve)", () => {
  const a = { isHelper: false, line: 5 }
  const cand = { isHelper: false, line: 20 }
  const pool = [a, cand]
  // `isInsideIteration: true` with no `scope` supplied to `resolveNameMatch` (and so none passed on
  // to `candidateExtent`) hits `candidateExtent`'s own `!scope` branch — `'unknown-width'`, a real,
  // sortable position whose own count cannot be settled. Placed between `a` and `cand` so the walk
  // reaches it before `nth: 1` is settled.
  const unknownWidthForeign = {
    isHelper: false,
    isInsideIteration: true,
    iterationArrayExpr: {},
    line: 10,
  }
  assert.equal(
    resolveNameMatch({
      candidate: cand,
      pool,
      name: null,
      nth: 1,
      foreignExtents: [unknownWidthForeign],
    }),
    'ambiguous',
  )
})

// Coverage note (T674): `foreignExtents` is an optional parameter, defaulting to `[]`
// (`resolveNameMatch`'s own destructuring default, above) — every `nth` test above this comment
// that never mentions `foreignExtents` at all (e.g. 'resolveNameMatch resolves nth against inline
// candidates sorted by line, excluding helper declarations') already exercises the omitted/empty
// case and its result is unchanged by this task: an empty `foreignExtents` array is filtered to
// nothing by `.filter((e) => e.kind !== 'unplaceable' && e.count !== 0)` before the walk, and
// `foreignPositions.some(...)` over an empty array is `false`, so the walk proceeds exactly as it
// did before `foreignExtents` existed.

// --- T595 (row 8, H5): closing the `nth`/`name` family's own remaining `unresolved` cells —
// PrivacyNotice's `InlineLink`, Footer's two `Link` instances, and ProfileSummary's composed
// `Tooltip` name. Routed through `computeStateCoverage` end to end, the newest tests' own style,
// since each mechanism reads real guards/call sites/composed files a hand-built object cannot carry
// honestly. Each mechanism gets its own resolving case and its own contrast. -----------------------

const INLINE_LINK_INDEX_SOURCE = `
function InlineLink({ href, children }) {
  return (
    <a href={href} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
      {children}
    </a>
  )
}
export function Notice({ hrefs }) {
  return (
    <div>
      <a href="/contents" className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
        Contents
      </a>
      <InlineLink href={hrefs.a}>A</InlineLink>
      <InlineLink href={hrefs.b}>B</InlineLink>
    </div>
  )
}
`

const INLINE_LINK_STORIES_SOURCE = `
import { Notice } from './index'
const meta = { component: Notice, args: { hrefs: { a: '/a', b: '/b' } } }
export default meta
export const Hover = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'link', nth: 0 } },
}
`

test("resolveNameMatch (via computeStateCoverage): a non-exported helper's own real call sites are enumerated and the earliest reached for this story stands in for its render position (PrivacyNotice/InlineLink shape, T595)", () => {
  const componentDirs = [{ segment: 'primitives', name: 'Notice' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Notice/index.tsx'), INLINE_LINK_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Notice/Notice.stories.tsx'), INLINE_LINK_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Notice')
  const contents = elements.find((el) => el.text === 'Contents')
  const inlineLink = elements.find((el) => el.isHelper)
  assert.ok(
    contents && inlineLink,
    'both the inline Contents link and the InlineLink recipe must be found',
  )
  // `Contents` sorts before InlineLink's own earliest call site — nth: 0 is `Contents`, confirmed.
  assert.deepEqual(contents.coveredBy.hover, ['Hover'])
  // InlineLink's own declaration is not the nth: 0 target — a real, positive `none`, not the old
  // unconditional `unresolved` this pass used to print for every helper candidate.
  assert.deepEqual(inlineLink.coveredBy.hover, ['none'])
})

test("contrast: resolveNameMatch (via computeStateCoverage) leaves an exported helper's nth cell unresolved — its call sites elsewhere are invisible to a single-file pass (T595)", () => {
  const exportedHelperSource = INLINE_LINK_INDEX_SOURCE.replace(
    'function InlineLink(',
    'export function InlineLink(',
  )
  const componentDirs = [{ segment: 'primitives', name: 'Notice' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Notice/index.tsx'), exportedHelperSource],
    [path.join(REPO_SRC_DIR, 'primitives/Notice/Notice.stories.tsx'), INLINE_LINK_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Notice')
  const inlineLink = elements.find((el) => el.isHelper)
  assert.equal(inlineLink.coveredBy.hover.length, 1)
  assert.match(inlineLink.coveredBy.hover[0], /^unresolved:/)
})

const GUARDED_CALL_SITE_INDEX_SOURCE = `
function InlineLink({ href, children }) {
  return (
    <a href={href} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
      {children}
    </a>
  )
}
export function Notice({ hrefs, extra }) {
  return (
    <div>
      <a href="/contents" className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
        Contents
      </a>
      {isExtraAllowed(extra) && <InlineLink href={hrefs.a}>A</InlineLink>}
    </div>
  )
}
`

const GUARDED_CALL_SITE_STORIES_SOURCE = `
import { Notice } from './index'
const meta = { component: Notice, args: { hrefs: { a: '/a' } } }
export default meta
export const Hover = {
  args: { extra: {} },
  parameters: { visualForceState: { state: 'hover', role: 'link', nth: 0 } },
}
`

test("contrast: resolveNameMatch (via computeStateCoverage) leaves the whole pool unresolved when a helper's own call-site guard is a function call no story's scope can evaluate (T595, 'a guard no story settles')", () => {
  const componentDirs = [{ segment: 'primitives', name: 'Notice' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Notice/index.tsx'), GUARDED_CALL_SITE_INDEX_SOURCE],
    [
      path.join(REPO_SRC_DIR, 'primitives/Notice/Notice.stories.tsx'),
      GUARDED_CALL_SITE_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Notice')
  const inlineLink = elements.find((el) => el.isHelper)
  // `isExtraAllowed(extra)` is a function call — `evaluateExpr` never evaluates one, so this
  // story's own scope cannot tell whether `InlineLink`'s own call site is even reached. Genuinely
  // unknown whether `InlineLink` renders at all, so it is neither placed at `nth: 0` nor ruled out
  // — `'ambiguous'`, never guessed into a `'reject'` this pass has not earned (`Contents` itself
  // still resolves normally: only the candidate whose own position is genuinely unknown is affected,
  // the same one-candidate-at-a-time contract every other `resolveNameMatch` call already has).
  assert.equal(inlineLink.coveredBy.hover.length, 1)
  assert.match(inlineLink.coveredBy.hover[0], /^unresolved:/)
})

// --- T595 (row 8, H5), coordinator's own finding on this task's second hand-back: the candidate
// pool above holds one AST node per declaration site, so a `.map()`-rendered group (`Contents`,
// nine real elements) used to collapse to exactly one slot in the `nth` ordering, regardless of
// how many real elements it actually renders — `nth` itself counts real, rendered elements, the
// same number Playwright's own `getByRole(...).nth(n)` resolves against at capture time. Three
// cases, matching the coordinator's own three: a `.map()` group whose backing array this story's
// own scope settles contributes that many real slots; the same shape where the array is not
// settleable keeps the whole ordering past it unresolved rather than guessing a width of one; and
// an element positioned after either shape, never the `nth` target either way, must still resolve
// to a confirmed `none` — not be dragged into `unresolved` merely because an unrelated `nth` this
// pass cannot place shares its own component's pool. ---------------------------------------------

const MAP_CARDINALITY_INDEX_SOURCE = `
const ITEMS = [
  { id: 'a', label: 'A' },
  { id: 'b', label: 'B' },
  { id: 'c', label: 'C' },
]
export function Nav({ hrefs }) {
  return (
    <nav>
      {ITEMS.map((item) => (
        <a href={'#' + item.id} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
          {item.label}
        </a>
      ))}
      <a href={hrefs.extra} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
        Extra
      </a>
    </nav>
  )
}
`

const MAP_CARDINALITY_STORIES_SOURCE = `
import { Nav } from './index'
const meta = { component: Nav, args: { hrefs: { extra: '/extra' } } }
export default meta
export const Hover = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'link', nth: 3 } },
}
`

test('resolveNameMatch (via computeStateCoverage): nth past a .map() group whose backing array this story settles lands on the real element after it, not stalled at the group’s own single AST slot (T595, coordinator’s own finding)', () => {
  const componentDirs = [{ segment: 'primitives', name: 'Nav' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Nav/index.tsx'), MAP_CARDINALITY_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Nav/Nav.stories.tsx'), MAP_CARDINALITY_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Nav')
  const items = elements.find((el) => el.isInsideIteration)
  const extra = elements.find((el) => el.text === 'Extra')
  assert.ok(
    items && extra,
    'both the ITEMS-mapped anchor and the trailing Extra link must be found',
  )
  // `ITEMS` resolves to a real, three-element array (a file-level literal, evaluated once into
  // every story's own scope) — its own group occupies real positions 0-2, so `nth: 3` is `Extra`,
  // confirmed, never the group itself.
  assert.deepEqual(extra.coveredBy.hover, ['Hover'])
  assert.deepEqual(items.coveredBy.hover, ['none'])
})

const UNSETTLEABLE_MAP_INDEX_SOURCE = `
const ITEMS = buildItems()
export function Nav({ hrefs }) {
  return (
    <nav>
      {ITEMS.map((item) => (
        <a href={'#' + item.id} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
          {item.label}
        </a>
      ))}
      <a href={hrefs.extra} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
        Extra
      </a>
    </nav>
  )
}
`

test("contrast: resolveNameMatch (via computeStateCoverage) leaves the whole ordering past an unsettleable .map() array unresolved, never guessing a width of one the way the pre-T595 model silently did (T595, 'a .map() array no story settles')", () => {
  const componentDirs = [{ segment: 'primitives', name: 'Nav' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Nav/index.tsx'), UNSETTLEABLE_MAP_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Nav/Nav.stories.tsx'), MAP_CARDINALITY_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Nav')
  const extra = elements.find((el) => el.text === 'Extra')
  assert.ok(extra, 'the trailing Extra link must be found')
  // `buildItems()` is a function call — `evaluateExpr` never evaluates one, so this story's own
  // scope cannot tell how many real slots `ITEMS.map(...)` actually occupies. Genuinely unknown
  // whether `nth: 3` falls inside that group or past it into `Extra` — `unresolved`, never a guess
  // either way.
  assert.equal(extra.coveredBy.hover.length, 1)
  assert.match(extra.coveredBy.hover[0], /^unresolved:/)
})

const INLINE_LINK_WITH_TRAILING_LINK_INDEX_SOURCE = `
function InlineLink({ href, children }) {
  return (
    <a href={href} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
      {children}
    </a>
  )
}
export function Notice({ hrefs }) {
  return (
    <div>
      <a href="/contents" className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
        Contents
      </a>
      <InlineLink href={hrefs.a}>A</InlineLink>
      <InlineLink href={hrefs.b}>B</InlineLink>
      <a href={hrefs.after} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
        After
      </a>
    </div>
  )
}
`

const INLINE_LINK_WITH_TRAILING_LINK_STORIES_SOURCE = `
import { Notice } from './index'
const meta = { component: Notice, args: { hrefs: { a: '/a', b: '/b', after: '/after' } } }
export default meta
export const Hover = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'link', nth: 1 } },
}
`

test('resolveNameMatch (via computeStateCoverage): an element after an nth-targeted helper stays a confirmed none, not dragged into unresolved merely because it shares that helper’s own pool (T595, coordinator’s own finding — PrivacyNotice’s contact-route link shape)', () => {
  const componentDirs = [{ segment: 'primitives', name: 'Notice' }]
  const filesByPath = new Map([
    [
      path.join(REPO_SRC_DIR, 'primitives/Notice/index.tsx'),
      INLINE_LINK_WITH_TRAILING_LINK_INDEX_SOURCE,
    ],
    [
      path.join(REPO_SRC_DIR, 'primitives/Notice/Notice.stories.tsx'),
      INLINE_LINK_WITH_TRAILING_LINK_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Notice')
  const inlineLink = elements.find((el) => el.isHelper)
  const after = elements.find((el) => el.text === 'After')
  assert.ok(
    inlineLink && after,
    'both the InlineLink recipe and the trailing After link must be found',
  )
  // `Contents` occupies real position 0; `InlineLink`'s own two call sites (both unconditional,
  // both reached) occupy positions 1-2 — `nth: 1` is `InlineLink`'s own first real call site,
  // confirmed. `After`, at real position 3, is never the target either way, and every candidate
  // before it resolved to an exact, known width, so its own hover cell is a confirmed `none`.
  // This is worse than an `unresolved` regression, and pins exactly that: the pre-T595 code
  // excluded every *other* helper from the ordering outright rather than counting its own real
  // width, which shifted every position after `InlineLink` down by one — `After` (real position 3)
  // fell into the slot `orderable[1]` actually pointed at, and the old code confidently `'match'`ed
  // it. Run against the pre-fix `resolveNameMatch`, this exact assertion fails with
  // `after.coveredBy.hover` reading `['Hover']`, not `['none']` — a silently wrong credit, not an
  // `unresolved` cell a reader would know to distrust (the coordinator's own finding on this task's
  // second hand-back, restated in `resolveNameMatch`'s own comment above).
  assert.deepEqual(inlineLink.coveredBy.hover, ['Hover'])
  assert.deepEqual(after.coveredBy.hover, ['none'])
})

// --- T595 (row 8, H5), coordinator's own second finding on this task's third hand-back:
// `resolveSelectorMatch`'s own caller never consulted a candidate's own guards, so a
// conditionally-rendered element this story's own scope confirms does *not* render could still
// have its own attribute value attempted and wrongly credited — the same "excluded from the
// ordering" family of defect the `nth` fix above closes, one mechanism over. `PrivacyNotice`'s own
// contact-route link (`controllerContact ? <a…> : …`) is real but this exact shape: its guard is
// `'unresolved'`, not `'unreached'` (no story here ever settles `controllerContact` either way), so
// closing this one alone does not return that specific cell to `none` — the fixture below proves
// the mechanism against a guard this pass *can* settle, which is the case this fix actually owns. --

const GUARDED_SELECTOR_INDEX_SOURCE = `
export function Panel({ showA, hrefA, hrefB }) {
  return (
    <div>
      {showA && (
        <a href={hrefA} className="hover:underline focus-visible:outline-2 active:underline">
          A
        </a>
      )}
      <a href={hrefB} className="hover:underline focus-visible:outline-2 active:underline">
        B
      </a>
    </div>
  )
}
`

const GUARDED_SELECTOR_UNREACHED_STORIES_SOURCE = `
import { Panel } from './index'
const meta = { component: Panel }
export default meta
export const Hover = {
  args: { showA: false, hrefA: '/a', hrefB: '/b' },
  parameters: { visualForceState: { state: 'hover', selector: 'a[href="/a"]' } },
}
`

test("resolveSelectorMatch (via computeStateCoverage): a conditionally-rendered candidate this story's own scope confirms unreached is excluded before its own attribute is ever attempted (T595, coordinator's own second finding)", () => {
  const componentDirs = [{ segment: 'primitives', name: 'Panel2' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Panel2/index.tsx'), GUARDED_SELECTOR_INDEX_SOURCE],
    [
      path.join(REPO_SRC_DIR, 'primitives/Panel2/Panel2.stories.tsx'),
      GUARDED_SELECTOR_UNREACHED_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Panel2')
  const a = elements.find((el) => el.text === 'A')
  assert.ok(a, 'the conditionally-rendered A link must be found')
  // `showA: false` confirms this story never renders `A` at all — before this fix,
  // `resolveSelectorMatch` never checked that, resolved `hrefA` to the literal `'/a'` from this
  // story's own args, and matched it anyway: a real element that does not render this state (it
  // does not render *at all*) credited with a frame it never paints. `a.coveredBy.hover` reads
  // `['Hover']` against the pre-fix code; `['none']` is the confirmed, positive absence this
  // story's own data actually proves.
  assert.deepEqual(a.coveredBy.hover, ['none'])
})

const GUARDED_SELECTOR_REACHED_STORIES_SOURCE = `
import { Panel } from './index'
const meta = { component: Panel }
export default meta
export const Hover = {
  args: { showA: true, hrefA: '/a', hrefB: '/b' },
  parameters: { visualForceState: { state: 'hover', selector: 'a[href="/a"]' } },
}
`

test('contrast: resolveSelectorMatch (via computeStateCoverage) still matches a conditionally-rendered candidate a story genuinely reaches — having a guard at all is never, on its own, an exclusion (T595)', () => {
  const componentDirs = [{ segment: 'primitives', name: 'Panel2' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Panel2/index.tsx'), GUARDED_SELECTOR_INDEX_SOURCE],
    [
      path.join(REPO_SRC_DIR, 'primitives/Panel2/Panel2.stories.tsx'),
      GUARDED_SELECTOR_REACHED_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Panel2')
  const a = elements.find((el) => el.text === 'A')
  assert.ok(a, 'the conditionally-rendered A link must be found')
  // `showA: true` this time — the same guard, now confirmed reached, so `A` really does render and
  // really is the `nth`-free selector target. `evaluateGuards` returning `'reached'` (not
  // `'unreached'`) must never be folded into the same exclusion as `'unreached'` — this is the
  // boundary that keeps the fix above from over-excluding.
  assert.deepEqual(a.coveredBy.hover, ['Hover'])
})

const FOOTER_LIKE_INDEX_SOURCE = `
import { Link } from '../../primitives/Link'
export function TwoLinkFooter({ aHref, bHref }) {
  const hasLinks = Boolean(aHref || bHref)
  return (
    <footer>
      {hasLinks && (
        <div>
          {aHref && <Link href={aHref} variant="standalone">A</Link>}
          {bHref && <Link href={bHref} variant="standalone">B</Link>}
        </div>
      )}
    </footer>
  )
}
`

const FOOTER_LIKE_STORIES_SOURCE = `
import { TwoLinkFooter } from './index'
const meta = { component: TwoLinkFooter }
export default meta
export const Hover = {
  args: { aHref: '/a', bHref: '/b' },
  parameters: { visualForceState: { state: 'hover', role: 'link', nth: 0 } },
}
`

test('resolveComposedStoryMatches (via computeStateCoverage): a Link instance declared directly in its own owning component is no longer isHelper: true, so nth: 0 places it correctly (Footer shape, T595)', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Link' },
    { segment: 'composites', name: 'TwoLinkFooter' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'composites/TwoLinkFooter/index.tsx'), FOOTER_LIKE_INDEX_SOURCE],
    [
      path.join(REPO_SRC_DIR, 'composites/TwoLinkFooter/TwoLinkFooter.stories.tsx'),
      FOOTER_LIKE_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Link.find((r) => r.variantSize === 'standalone')
  assert.ok(row, 'the standalone row must exist')
  assert.deepEqual(row.hover, ['TwoLinkFooter:Hover'])
})

test('contrast (findPrimitiveInstances): a primitive instance declared behind a real, nested local helper still reads isHelper: true — only the owning component itself is excluded (T595)', () => {
  const nestedHelperSource = `
    function Decoy({ href }) {
      return <Link href={href} variant="standalone">Decoy</Link>
    }
    export function TwoLinkFooter({ href }) {
      return <div><Decoy href={href} /></div>
    }
  `
  const sourceFile = parse(nestedHelperSource)
  const found = findPrimitiveInstances(
    sourceFile,
    'fixture.tsx',
    {},
    [],
    new Map(),
    'TwoLinkFooter',
  )
  assert.equal(found.length, 1)
  assert.equal(found[0].isHelper, true)
})

const TOOLTIP_LIKE_INDEX_SOURCE = `
export function Tooltip({ children }) {
  return (
    <span>
      <button type="button" className="hover:bg-surface-sunken focus-visible:outline-2">
        {children}
      </button>
    </span>
  )
}
`

const COUNTRY_FLAG_LIKE_INDEX_SOURCE = `
import { Tooltip } from '../../primitives/Tooltip'
export function Flag({ countryName }) {
  return (
    <Tooltip content={countryName} qualifier="Country:">
      <span>flag</span>
    </Tooltip>
  )
}
`

const PROFILE_BOARD_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
import { Flag } from '../../composites/Flag'
export function ProfileBoard({ countryName, onRetry }) {
  return (
    <div>
      <Flag countryName={countryName} />
      <Button variant="secondary" size="lg" onClick={onRetry}>Retry</Button>
    </div>
  )
}
`

const PROFILE_BOARD_STORIES_SOURCE = `
import { ProfileBoard } from './index'
const meta = { component: ProfileBoard, args: { countryName: 'France' } }
export default meta
export const FlagHoverRevealed = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Country:' } },
}
`

test("resolveNameMatch (via computeStateCoverage): a name composed one hop away through a locally-rendered component's own Tooltip qualifier positively rejects every candidate Record 3 tracks, and credits Tooltip's own local button instead (ProfileSummary/CountryFlag shape, T595 — coordinator's own finding on this task's first hand-back)", () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'primitives', name: 'Tooltip' },
    { segment: 'composites', name: 'Flag' },
    { segment: 'screens', name: 'ProfileBoard' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Tooltip/index.tsx'), TOOLTIP_LIKE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'composites/Flag/index.tsx'), COUNTRY_FLAG_LIKE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'screens/ProfileBoard/index.tsx'), PROFILE_BOARD_INDEX_SOURCE],
    [
      path.join(REPO_SRC_DIR, 'screens/ProfileBoard/ProfileBoard.stories.tsx'),
      PROFILE_BOARD_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'secondary|lg')
  assert.ok(row, 'the secondary|lg row must exist')
  // Before T595: `resolveNameMatch` could not place "Country:" anywhere and left this row
  // `unresolved: ... none uniquely resolved`. `Button`'s own Retry instance carries no such name and
  // is positively `reject`ed once the name is traced to `Flag`'s own composed `Tooltip`, so the row
  // reads a confirmed `none` instead — `Tooltip` is not one of `PRIMITIVE_NAMES` at all.
  assert.deepEqual(row.hover, ['none'])
  // The coordinator's own finding on this task's first hand-back: rejecting every wrong candidate
  // is not the same as crediting the right one. `Tooltip`'s own local `<button>` (record 1) is that
  // candidate — its own pool for role `button` has exactly one member, so the credit lands there,
  // labelled by the story file that forced it, the same convention `Footer:Hover` already uses.
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Tooltip')
  assert.deepEqual(elements[0].coveredBy.hover, ['ProfileBoard:FlagHoverRevealed'])
})

test("contrast: resolveNameMatch (via computeStateCoverage) stays ambiguous when the composed Tooltip's own qualifier is not a literal — a name this pass cannot trace is never guessed into a reject, and nothing is credited either (T595, 'a composed name that is not derivable')", () => {
  const dynamicQualifierSource = COUNTRY_FLAG_LIKE_INDEX_SOURCE.replace(
    'qualifier="Country:"',
    'qualifier={qualifierLabel}',
  )
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'primitives', name: 'Tooltip' },
    { segment: 'composites', name: 'Flag' },
    { segment: 'screens', name: 'ProfileBoard' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Tooltip/index.tsx'), TOOLTIP_LIKE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'composites/Flag/index.tsx'), dynamicQualifierSource],
    [path.join(REPO_SRC_DIR, 'screens/ProfileBoard/index.tsx'), PROFILE_BOARD_INDEX_SOURCE],
    [
      path.join(REPO_SRC_DIR, 'screens/ProfileBoard/ProfileBoard.stories.tsx'),
      PROFILE_BOARD_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'secondary|lg')
  assert.ok(row, 'the secondary|lg row must exist')
  assert.equal(row.hover.length, 1)
  assert.match(row.hover[0], /^unresolved:/)
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Tooltip')
  assert.deepEqual(elements[0].coveredBy.hover, ['none'])
})

// --- The coordinator's own review of this task's first hand-back, part two: a role-only
// force-state (no `name` at all, `CountryFlag`'s own `FlagHoverRevealed`) needs the *zero-hop*
// case — a component's own source composes `<Tooltip>` directly, not through a second component —
// and needs `componentHasOwnCandidateForRole`'s own guard: routing a role-only force-state
// elsewhere is only safe when the forcing component has no candidate of its own for that role. ----

const FLAG_LIKE_DIRECT_INDEX_SOURCE = `
import { Tooltip } from '../../primitives/Tooltip'
export function Flag({ countryName }) {
  return (
    <Tooltip content={countryName} qualifier="Country:">
      <span>flag</span>
    </Tooltip>
  )
}
`

const FLAG_LIKE_STORIES_SOURCE = `
import { Flag } from './index'
const meta = { component: Flag, args: { countryName: 'France' } }
export default meta
export const FlagHoverRevealed = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'button' } },
}
`

test('resolveNameMatch (via computeStateCoverage): a role-only force-state (no name, no nth) on a component that directly composes Tooltip and has no candidate of its own routes to Tooltip too (CountryFlag shape, zero-hop, T595)', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Tooltip' },
    { segment: 'composites', name: 'Flag' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Tooltip/index.tsx'), TOOLTIP_LIKE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'composites/Flag/index.tsx'), FLAG_LIKE_DIRECT_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'composites/Flag/Flag.stories.tsx'), FLAG_LIKE_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Tooltip')
  assert.deepEqual(elements[0].coveredBy.hover, ['Flag:FlagHoverRevealed'])
})

test("contrast: resolveNameMatch (via computeStateCoverage) never routes a role-only force-state elsewhere when the forcing component has a candidate of its own for that role — 'no name' is not 'no ambiguity' (T595, componentHasOwnCandidateForRole)", () => {
  const flagWithOwnButtonSource = `
    import { Tooltip } from '../../primitives/Tooltip'
    export function Flag({ countryName }) {
      return (
        <div>
          <button type="button" className="hover:bg-surface-sunken">Own button</button>
          <Tooltip content={countryName} qualifier="Country:">
            <span>flag</span>
          </Tooltip>
        </div>
      )
    }
  `
  const componentDirs = [
    { segment: 'primitives', name: 'Tooltip' },
    { segment: 'composites', name: 'Flag' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Tooltip/index.tsx'), TOOLTIP_LIKE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'composites/Flag/index.tsx'), flagWithOwnButtonSource],
    [path.join(REPO_SRC_DIR, 'composites/Flag/Flag.stories.tsx'), FLAG_LIKE_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  // `Flag` has a candidate of its own for role `button`, so `componentHasOwnCandidateForRole`
  // blocks the composed-elsewhere route entirely — `Tooltip`'s own row stays a confirmed `none`,
  // never credited on the strength of a role this pass cannot tell apart from `Flag`'s own.
  const tooltip = computed.localElements.find((c) => c.componentKey === 'primitives/Tooltip')
  assert.deepEqual(tooltip.elements[0].coveredBy.hover, ['none'])
  // `Flag`'s own button is real, positive knowledge by the *pre-existing*, unrelated "sole
  // candidate needs no further disambiguation" rule — record 1's own pool is always scoped to one
  // file, so `Flag`'s own resolution never even sees `Tooltip`'s candidate as competition. This is
  // the correct outcome, not a second bug: crediting both would be the real defect.
  const flag = computed.localElements.find((c) => c.componentKey === 'composites/Flag')
  assert.deepEqual(flag.elements[0].coveredBy.hover, ['FlagHoverRevealed'])
})

// --- Record 1's own cross-component matching path (T598): a story in component A reaching a
// *local element declared inside a tracked primitive's own file* (record 1 of `primitives/Menu`)
// through a JSX instance of that primitive A composes directly (record 3) — a different, wider
// question from the `Tooltip`-qualifier hop above, which resolves an accessible name one hop away
// and credits an *untracked* primitive's own trigger, pre-confirming a singleton pool itself.
// `Menu`/`MenuItemRow` here are fixtures, not the real component — the mechanism only ever walks
// `PRIMITIVE_NAMES`, so the fixture must use one of those four names to be reachable at all. -------

const MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE = `
export function Menu({ variant, items }) {
  return (
    <div>
      <button type="button" className="hover:bg-surface-sunken">Trigger</button>
      {items.map((item) => (
        <MenuItemRow key={item.id} item={item} variant={variant} />
      ))}
    </div>
  )
}

function MenuItemRow({ item, variant }) {
  const role = variant === 'selection' ? 'menuitemradio' : 'menuitem'
  return (
    <button
      type="button"
      role={role}
      className="hover:bg-surface-sunken focus-visible:outline-2 active:bg-background"
    >
      {item.label}
    </button>
  )
}
`

const PANEL_WITH_SELECTION_MENU_INDEX_SOURCE = `
import { Menu } from '../../primitives/Menu'
export function Panel({ subject, items }) {
  return (
    <div>
      {subject === 'self' && <Menu variant="selection" items={items} />}
    </div>
  )
}
`

const PANEL_SWITCHER_STORIES_SOURCE = `
import { Panel } from './index'
const meta = { component: Panel, args: { subject: 'self', items: [{ id: 'p1', label: 'aoe2guy' }] } }
export default meta
export const RowFocusVisible = {
  args: {},
  parameters: { visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2guy' } },
}
`

test("injectComposedPrimitiveLocalCredits (via computeStateCoverage): a story in one component reaches a local element declared inside a tracked primitive's own file, through a JSX instance that component composes directly — forced (name included) carried through unchanged, unlike T595's own Tooltip-qualifier hop which drops the name and pre-confirms a singleton pool itself (T598, ProfileSummary/MenuItemRow shape)", () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Menu' },
    { segment: 'screens', name: 'Panel' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Menu/index.tsx'), MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'screens/Panel/index.tsx'), PANEL_WITH_SELECTION_MENU_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'screens/Panel/Panel.stories.tsx'), PANEL_SWITCHER_STORIES_SOURCE],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Menu')
  // `MenuItemRow`'s own button: the one local element of `primitives/Menu` whose own `role`
  // attribute is dynamic (`role={role}`), never literal — the trigger button right above it is
  // `role: null` (its intrinsic role), not `'unresolved'`.
  const menuItemRow = elements.find((el) => el.role === 'unresolved')
  assert.ok(menuItemRow, 'MenuItemRow local element must be found')
  assert.deepEqual(menuItemRow.coveredBy.focusVisible, ['Panel:RowFocusVisible'])
})

test("contrast: injectComposedPrimitiveLocalCredits (via computeStateCoverage) never credits a composed primitive's local element by proximity when the exact call site the forcing story renders could not have produced the forced role — a reachable Menu instance whose own variant never resolves to 'menuitemradio' stays unresolved, not falsely credited (T598)", () => {
  const panelWithActionsOnlyMenuSource = `
    import { Menu } from '../../primitives/Menu'
    export function Panel({ items }) {
      return (
        <div>
          <Menu variant="actions" items={items} />
        </div>
      )
    }
  `
  const panelActionsStoriesSource = `
    import { Panel } from './index'
    const meta = { component: Panel, args: { items: [{ id: 'p1', label: 'aoe2guy' }] } }
    export default meta
    export const RowFocusVisible = {
      args: {},
      parameters: { visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2guy' } },
    }
  `
  const componentDirs = [
    { segment: 'primitives', name: 'Menu' },
    { segment: 'screens', name: 'Panel' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Menu/index.tsx'), MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'screens/Panel/index.tsx'), panelWithActionsOnlyMenuSource],
    [path.join(REPO_SRC_DIR, 'screens/Panel/Panel.stories.tsx'), panelActionsStoriesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Menu')
  const menuItemRow = elements.find((el) => el.role === 'unresolved')
  assert.ok(menuItemRow, 'MenuItemRow local element must be found')
  // `Menu` is genuinely composed and genuinely reachable here (no guard at all) — the boundary this
  // contrast plants is not "never rendered", it is "rendered, but never as the forced role": the
  // only Menu instance Panel composes always resolves `variant === 'actions'`, so `MenuItemRow`'s
  // own dynamic role can never be `'menuitemradio'` for this story, and the credit must never land
  // on the strength of "some Menu instance is reachable" alone.
  assert.notDeepEqual(menuItemRow.coveredBy.focusVisible, ['Panel:RowFocusVisible'])
  assert.ok(
    menuItemRow.coveredBy.focusVisible[0] === 'none' ||
      menuItemRow.coveredBy.focusVisible[0].startsWith('unresolved:'),
  )
})

test("contrast: injectComposedPrimitiveLocalCredits (via computeStateCoverage) never credits a composed primitive's local element when the forcing story's own guard confirms that call site does not render at all (T598, 'a composed component this story's own data does not render')", () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Menu' },
    { segment: 'screens', name: 'Panel' },
  ]
  const panelHiddenStoriesSource = `
    import { Panel } from './index'
    const meta = { component: Panel, args: { subject: 'other', items: [{ id: 'p1', label: 'aoe2guy' }] } }
    export default meta
    export const RowFocusVisible = {
      args: {},
      parameters: { visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2guy' } },
    }
  `
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Menu/index.tsx'), MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'screens/Panel/index.tsx'), PANEL_WITH_SELECTION_MENU_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'screens/Panel/Panel.stories.tsx'), panelHiddenStoriesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Menu')
  const menuItemRow = elements.find((el) => el.role === 'unresolved')
  assert.ok(menuItemRow, 'MenuItemRow local element must be found')
  // `subject: 'other'` means this story's own guard (`subject === 'self'`) never reaches the
  // `<Menu>` call site at all — `evaluateGuards` reports `'unreached'`, so no synthetic credit is
  // ever injected for it, and the real force-state stays uncredited on this element rather than
  // guessed onto it because *some* Menu, somewhere in this tree, would have matched.
  assert.notDeepEqual(menuItemRow.coveredBy.focusVisible, ['Panel:RowFocusVisible'])
})

// --- The invariant itself: every real `visualForceState` is credited or named somewhere in the
// region, or the run fails — the coordinator's own instruction, T595. --------------------------
//
// A story is accounted for by a mention *in a cell of its own state's column* (T684): Record 1's
// story part of the Hover / Focus-visible / Active cell, Record 3's Hover / Focus-visible / Press
// (active) column. The fixtures below build the region through real headers, the shape
// `renderRecord1`/`renderMatrices` print, because the check locates columns by header text.

const escCell = (cell) => String(cell).replace(/\|/g, '\\|')
function fixtureTable(headers, rows) {
  return [
    `| ${headers.join(' | ')} |`,
    `| ${headers.map(() => '---').join(' | ')} |`,
    ...rows.map((row) => `| ${row.map(escCell).join(' | ')} |`),
  ].join('\n')
}
// `record1`: rows of `r1Row`; `matrices`: section name (`Button`, `Tooltip`) to rows of `r3Row`.
function regionFixture({ record1 = [], matrices = {}, trailing = '' } = {}) {
  const sections = Object.entries(matrices).map(
    ([name, rows]) => `#### \`${name}\`\n\n${fixtureTable(RECORD3_HEADERS, rows)}`,
  )
  return [
    '<!-- state-coverage:begin -->',
    '',
    '**Record 1 — every local interactive element (2 component directories scanned).**',
    '',
    fixtureTable(RECORD1_HEADERS, record1),
    '',
    '**Record 3 — every primitive matrix.**',
    '',
    sections.join('\n\n'),
    `${trailing}<!-- state-coverage:end -->`,
  ].join('\n')
}
const r1Row = (
  key,
  { hover = 'none', focus = 'none', active = 'none', element = 'button', loc = 'index.tsx:3' } = {},
) => [
  key,
  element,
  loc,
  `hover:bg-x → ${hover}`,
  `focus-visible:outline-2 → ${focus}`,
  `active:bg-y → ${active}`,
]
const r3Row = (
  row,
  { rest = 'none', hover = 'none', focus = 'none', active = 'none', disabled = 'none' } = {},
) => [row, rest, hover, focus, active, disabled]
const EMPTY_REGION = regionFixture()
// A hand-built story entry always carries its own `storyFile` (the real pipeline always does).
const storyFixture = (componentKey, exportName, state = 'hover', extra = {}) => ({
  exportName,
  storyFile: `${componentKey.split('/').pop()}.stories.tsx`,
  forced: { state, role: 'button' },
  ...extra,
})
const missingIds = (missing) => missing.map((m) => `${m.componentKey}:${m.exportName}`).sort()

test('findUnaccountedForceStates catches a real force-state that is credited nowhere and named in no unresolved reason (T595)', () => {
  const storyStatesByComponent = new Map([
    ['composites/Lost', [storyFixture('composites/Lost', 'ForcedButNeverShown')]],
  ])
  const { missing, known, expired } = findUnaccountedForceStates(
    storyStatesByComponent,
    regionFixture({ record1: [r1Row('composites/Lost')] }),
  )
  assert.deepEqual(known, [])
  assert.deepEqual(expired, [])
  assert.equal(missing.length, 1)
  assert.equal(missing[0].exportName, 'ForcedButNeverShown')
})

test('contrast: findUnaccountedForceStates does not flag a force-state that is genuinely credited, named in an unresolved reason, from a story that never renders the component, or manufactured by this pass itself (T595)', () => {
  const storyStatesByComponent = new Map([
    ['composites/Credited', [storyFixture('composites/Credited', 'RealHover')]],
    ['composites/Named', [storyFixture('composites/Named', 'AmbiguousHover')]],
    [
      'composites/NeverRenders',
      [
        storyFixture('composites/NeverRenders', 'NotApplicablePlaceholder', 'hover', {
          rendersComponent: false,
        }),
      ],
    ],
    [
      'primitives/Tooltip',
      [
        {
          exportName: 'Flag:FlagHoverRevealed',
          forced: { state: 'hover', role: 'button' },
          synthetic: true,
        },
      ],
    ],
  ])
  const regionText = regionFixture({
    record1: [
      r1Row('composites/Credited', { hover: 'RealHover' }),
      r1Row('composites/Named', {
        hover: 'unresolved: AmbiguousHover: 2 candidates share role "button"',
      }),
    ],
  })
  const { missing, known, expired } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missing, [])
  assert.deepEqual(known, [])
  assert.deepEqual(expired, [])
})

// --- T684: a story is accounted for by its own identity and its own state's column, never by a
// bare word anywhere in the region ----------------------------------------------------------------

const SHARED_NAME_REGION = regionFixture({
  record1: [r1Row('composites/Alpha', { hover: 'Hover' }), r1Row('composites/Beta')],
})

test('findUnaccountedForceStates reports an uncredited forced story named Hover in one component while another component credits its own Hover (T684, primary case)', () => {
  const storyStatesByComponent = new Map([
    ['composites/Alpha', [storyFixture('composites/Alpha', 'Hover')]],
    ['composites/Beta', [storyFixture('composites/Beta', 'Hover')]],
  ])
  const { missing, known, expired } = findUnaccountedForceStates(
    storyStatesByComponent,
    SHARED_NAME_REGION,
  )
  assert.deepEqual(known, [])
  assert.deepEqual(expired, [])
  assert.deepEqual(missing, [
    { componentKey: 'composites/Beta', exportName: 'Hover', state: 'hover' },
  ])
})

test("findUnaccountedForceStates does not take another component's qualified credit label for a bare-named story of the same export name (T684)", () => {
  // `Footer:Hover` credits Footer's own story, on a cell of some other component. A different
  // component's own `Hover` is neither that story nor credited by it.
  const storyStatesByComponent = new Map([
    ['composites/Header', [storyFixture('composites/Header', 'Hover')]],
  ])
  const { missing } = findUnaccountedForceStates(
    storyStatesByComponent,
    regionFixture({
      record1: [r1Row('composites/Alpha', { hover: 'Footer:Hover' }), r1Row('composites/Header')],
    }),
  )
  assert.deepEqual(missing, [
    { componentKey: 'composites/Header', exportName: 'Hover', state: 'hover' },
  ])
})

test('contrast: findUnaccountedForceStates keeps a forced story accounted for through its own credit, a qualified cross-component label in its own state column, a file-qualified unresolved reason, an axis matrix label, its own element matrix section, or an unresolved reason on its own rows (T684)', () => {
  const storyStatesByComponent = new Map([
    ['composites/Alpha', [storyFixture('composites/Alpha', 'Hover')]],
    // Credited only as a cross-component label on a primitive's axis matrix (`Footer:Hover`).
    ['composites/Footer', [storyFixture('composites/Footer', 'Hover')]],
    // A story file whose basename is not its component's name keeps its own label base.
    [
      'composites/Panel',
      [storyFixture('composites/Panel', 'Hover', 'hover', { storyFile: 'Rows.stories.tsx' })],
    ],
    // Named in an axis matrix's own file-qualified unresolved reason (ambiguous-variant row).
    ['composites/Card', [storyFixture('composites/Card', 'Hover')]],
    // Named in the unresolved-matches pseudo-row, whose reason carries its own state.
    ['composites/Pseudo', [storyFixture('composites/Pseudo', 'FocusRing', 'focus-visible')]],
    // A primitive's own element matrix section prints its own stories by bare name.
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'Hover')]],
    ['composites/Named', [storyFixture('composites/Named', 'Hover')]],
    // A qualified label in another component's Record 1 state column (a composed credit).
    ['composites/Elsewhere', [storyFixture('composites/Elsewhere', 'Pressed', 'active')]],
  ])
  const regionText = regionFixture({
    record1: [
      r1Row('composites/Alpha', { hover: 'Hover' }),
      r1Row('composites/Named', {
        hover: 'unresolved: Hover: 2 candidates share role "button"',
      }),
      r1Row('primitives/Tooltip', { active: 'Elsewhere:Pressed' }),
    ],
    matrices: {
      Button: [
        r3Row('primary|md', { hover: 'Footer:Hover; Rows:Hover' }),
        r3Row('ghost|md', {
          hover:
            'unresolved: composites/Card/Card.stories.tsx:Hover — state "hover": 2 Button instances',
        }),
        r3Row('(unresolved matches — no row, printed rather than dropped)', {
          rest: 'N/A',
          hover:
            'unresolved: composites/Other/Other.stories.tsx:Hover — state "hover": 2 Button instances | composites/Pseudo/Pseudo.stories.tsx:FocusRing — state "focus-visible": 2 Button instances',
          focus: 'N/A',
          active: 'N/A',
          disabled: 'N/A',
        }),
      ],
      Tooltip: [r3Row('button @ index.tsx:9', { rest: 'index.tsx:9', hover: 'Hover' })],
    },
  })
  const { missing, known, expired } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missing, [])
  assert.deepEqual(known, [])
  assert.deepEqual(expired, [])
})

test('findUnaccountedForceStates: a bare name credited in a primitive section of a different name, or only inside a quoted accessible name, accounts for nothing (T684)', () => {
  const storyStatesByComponent = new Map([
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'Hover')]],
    ['composites/Quoted', [storyFixture('composites/Quoted', 'Hover')]],
  ])
  const regionText = regionFixture({
    record1: [
      r1Row('composites/Quoted', {
        hover:
          'unresolved: Other: 2 candidates share role "button", name "Hover" not literally resolvable',
      }),
    ],
    matrices: {
      Menu: [r3Row('actions', { rest: 'composites/Quoted (a.tsx:1)', hover: 'Hover' })],
    },
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), ['composites/Quoted:Hover', 'primitives/Tooltip:Hover'])
})

test('contrast: a filed exception for an uncredited Hover is reported as known, not missing, while the credited Hover of a sibling component with the same export name stays accounted for (T684)', () => {
  const storyStatesByComponent = new Map([
    ['composites/Alpha', [storyFixture('composites/Alpha', 'Hover')]],
    ['composites/Beta', [storyFixture('composites/Beta', 'Hover')]],
  ])
  const farFuture = new Date()
  farFuture.setFullYear(farFuture.getFullYear() + 10)
  const saved = [...KNOWN_UNACCOUNTED_FORCE_STATES]
  KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
  KNOWN_UNACCOUNTED_FORCE_STATES.push({
    componentKey: 'composites/Beta',
    exportName: 'Hover',
    date: '2026-10-03',
    fixOwed: 'T000',
    fixBy: farFuture.toISOString().slice(0, 10),
    reason: 'test fixture, not yet due',
  })
  try {
    const { missing, known, expired } = findUnaccountedForceStates(
      storyStatesByComponent,
      SHARED_NAME_REGION,
    )
    assert.deepEqual(missing, [])
    assert.deepEqual(expired, [])
    assert.equal(known.length, 1)
    assert.equal(known[0].componentKey, 'composites/Beta')
  } finally {
    KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
    KNOWN_UNACCOUNTED_FORCE_STATES.push(...saved)
  }
})

// M1 — a bare name found in a column that credits nothing: the path of the story's own component
// in File:Line / Row / Rest, the Element text, the class text.
test("findUnaccountedForceStates: a story named after its own component is not accounted for by that component's own path in the File:Line, Row or Rest column (T684, M1)", () => {
  const storyStatesByComponent = new Map([
    ['composites/SearchBox', [storyFixture('composites/SearchBox', 'SearchBox')]],
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'Tooltip')]],
  ])
  const regionText = regionFixture({
    record1: [
      r1Row('composites/SearchBox', {
        element: 'input[role=searchbox]',
        loc: 'packages/design-system/src/composites/SearchBox/index.tsx:129',
      }),
      r1Row('primitives/Tooltip', {
        loc: 'packages/design-system/src/primitives/Tooltip/index.tsx:259',
      }),
    ],
    matrices: {
      Tooltip: [
        r3Row('button @ packages/design-system/src/primitives/Tooltip/index.tsx:259', {
          rest: 'packages/design-system/src/primitives/Tooltip/index.tsx:259',
        }),
      ],
    },
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), [
    'composites/SearchBox:SearchBox',
    'primitives/Tooltip:Tooltip',
  ])
})

test("findUnaccountedForceStates: a story whose name appears only in its own row's Element or class text is not accounted for (T684, M1)", () => {
  const storyStatesByComponent = new Map([
    ['composites/SearchBox', [storyFixture('composites/SearchBox', 'input')]],
    ['composites/List', [storyFixture('composites/List', 'hover')]],
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'button')]],
  ])
  const regionText = regionFixture({
    record1: [
      r1Row('composites/SearchBox', { element: 'input[role=searchbox]' }),
      r1Row('composites/List', { element: 'a' }),
    ],
    matrices: {
      Tooltip: [r3Row('button @ index.tsx:9', { rest: 'index.tsx:9' })],
    },
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), [
    'composites/List:hover',
    'composites/SearchBox:input',
    'primitives/Tooltip:button',
  ])
})

// M2 — a story is accounted for in the column of the state it forces, never another column.
test('findUnaccountedForceStates: a hover story whose only mention is in a Disabled column (qualified label, bare name, or a disabled-unresolved reason) is not accounted for (T684, M2)', () => {
  const storyStatesByComponent = new Map([
    ['composites/FavouriteToggle', [storyFixture('composites/FavouriteToggle', 'ZzBoundedHover')]],
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'ZzDisabledBare')]],
    ['composites/Cart', [storyFixture('composites/Cart', 'ZzPending')]],
  ])
  const regionText = regionFixture({
    record1: [r1Row('composites/FavouriteToggle'), r1Row('composites/Cart')],
    matrices: {
      Button: [
        r3Row('ghost|md', { disabled: 'FavouriteToggle:ZzBoundedHover' }),
        r3Row('primary|md', {
          disabled: 'unresolved: disabled not statically resolvable (Cart:ZzPending)',
        }),
      ],
      Tooltip: [r3Row('button @ index.tsx:9', { rest: 'index.tsx:9', disabled: 'ZzDisabledBare' })],
    },
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), [
    'composites/Cart:ZzPending',
    'composites/FavouriteToggle:ZzBoundedHover',
    'primitives/Tooltip:ZzDisabledBare',
  ])
})

test('findUnaccountedForceStates: a story is accounted for only in the column of the state it forces (T684, M2, per state)', () => {
  const storyStatesByComponent = new Map([
    // Forces focus-visible; named only in the Hover column of its own row.
    ['composites/Alpha', [storyFixture('composites/Alpha', 'Ring', 'focus-visible')]],
    // Forces active; named only in the Focus-visible column.
    ['composites/Beta', [storyFixture('composites/Beta', 'Press', 'active')]],
    // Forces hover; named only in the Active column of a primitive's element matrix.
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'Over')]],
    // Forces focus-visible; the pseudo-row prints it in the Hover column, tagged `state "hover"`.
    ['composites/Gamma', [storyFixture('composites/Gamma', 'Pseudo', 'focus-visible')]],
  ])
  const regionText = regionFixture({
    record1: [
      r1Row('composites/Alpha', { hover: 'Ring' }),
      r1Row('composites/Beta', { focus: 'Press' }),
    ],
    matrices: {
      Button: [
        r3Row('(unresolved matches — no row, printed rather than dropped)', {
          rest: 'N/A',
          hover:
            'unresolved: composites/Gamma/Gamma.stories.tsx:Pseudo — state "hover": 2 Button instances',
          focus: 'N/A',
          active: 'N/A',
          disabled: 'N/A',
        }),
      ],
      Tooltip: [r3Row('button @ index.tsx:9', { rest: 'index.tsx:9', active: 'Over' })],
    },
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), [
    'composites/Alpha:Ring',
    'composites/Beta:Press',
    'composites/Gamma:Pseudo',
    'primitives/Tooltip:Over',
  ])
})

// M3 — a second story file in a component directory cannot ride on the first file's bare name.
test("findUnaccountedForceStates: a second story file's story is accounted for by its qualified label; its uncredited Hover is reported although the first file's qualified Hover is printed (T684, M3)", () => {
  const storyStatesByComponent = new Map([
    [
      'composites/Gallery',
      [
        storyFixture('composites/Gallery', 'Hover'),
        storyFixture('composites/Gallery', 'Hover', 'hover', { storyFile: 'Extra.stories.tsx' }),
        storyFixture('composites/Gallery', 'Credited', 'hover', { storyFile: 'Extra.stories.tsx' }),
      ],
    ],
  ])
  const regionText = regionFixture({
    record1: [r1Row('composites/Gallery', { hover: 'Gallery:Hover; Extra:Credited' })],
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  // Both files' `Hover` share one export name; only the first is printed — qualified — so the
  // second is the lost frame. The second file's `Credited` is printed qualified and stays accounted.
  assert.deepEqual(
    missing.map((m) => `${m.componentKey}:${m.exportName}`),
    ['composites/Gallery:Hover'],
  )
})

test("findUnaccountedForceStates: a bare name cannot say which of a component's story files it belongs to, so it accounts for neither (T684, M3)", () => {
  const storyStatesByComponent = new Map([
    [
      'composites/Gallery',
      [
        storyFixture('composites/Gallery', 'Hover'),
        storyFixture('composites/Gallery', 'Hover', 'hover', { storyFile: 'Extra.stories.tsx' }),
      ],
    ],
  ])
  const { missing } = findUnaccountedForceStates(
    storyStatesByComponent,
    regionFixture({ record1: [r1Row('composites/Gallery', { hover: 'Hover' })] }),
  )
  assert.deepEqual(
    missing.map((m) => m.exportName),
    ['Hover', 'Hover'],
  )
})

test('contrast: a component with a single story file is still accounted for by its bare name in its own rows (T684, M3)', () => {
  const storyStatesByComponent = new Map([
    ['composites/Solo', [storyFixture('composites/Solo', 'Hover')]],
  ])
  const { missing } = findUnaccountedForceStates(
    storyStatesByComponent,
    regionFixture({ record1: [r1Row('composites/Solo', { hover: 'Hover' })] }),
  )
  assert.deepEqual(missing, [])
})

// L2 — a section ends where its table ends, and is keyed by its primitive's own path.
test("findUnaccountedForceStates: a line planted after Record 3's last table accounts nothing in that section (T684, L2)", () => {
  const storyStatesByComponent = new Map([
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'Hover')]],
  ])
  const regionText = regionFixture({
    matrices: {
      Tooltip: [r3Row('button @ index.tsx:9', { rest: 'index.tsx:9' })],
    },
    trailing:
      '\nA stray note that names Hover and a table-looking line:\n| Hover | Hover | Hover |\n\n',
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), ['primitives/Tooltip:Hover'])
})

test("findUnaccountedForceStates: a composite or screen sharing a primitive's directory name does not read the primitive's section (T684, L2)", () => {
  const storyStatesByComponent = new Map([
    ['composites/Tooltip', [storyFixture('composites/Tooltip', 'Hover')]],
    ['primitives/Tooltip', [storyFixture('primitives/Tooltip', 'Hover')]],
  ])
  const regionText = regionFixture({
    record1: [r1Row('composites/Tooltip')],
    matrices: {
      Tooltip: [r3Row('button @ index.tsx:9', { rest: 'index.tsx:9', hover: 'Hover' })],
    },
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), ['composites/Tooltip:Hover'])
})

test('findUnaccountedForceStates: a bare name in an axis matrix section (a primitive in PRIMITIVE_NAMES) never accounts for a story, only a qualified label does (T684, L1)', () => {
  const storyStatesByComponent = new Map([
    ['primitives/Button', [storyFixture('primitives/Button', 'Hover')]],
    ['primitives/Link', [storyFixture('primitives/Link', 'Hover')]],
  ])
  const regionText = regionFixture({
    matrices: {
      Button: [r3Row('primary|md', { hover: 'Button:Hover' })],
      Link: [r3Row('(no axis)', { hover: 'Hover' })],
    },
  })
  const { missing } = findUnaccountedForceStates(storyStatesByComponent, regionText)
  assert.deepEqual(missingIds(missing), ['primitives/Link:Hover'])
})

// A renderer change must not silently empty the scope the check reads.
test('findUnaccountedForceStates throws when the region lacks Record 1, a state column, or a well-formed row (T684)', () => {
  const stories = new Map([['composites/A', [storyFixture('composites/A', 'Hover')]]])
  assert.throws(() => findUnaccountedForceStates(stories, ''), /Record 1/)
  assert.throws(
    () =>
      findUnaccountedForceStates(
        stories,
        EMPTY_REGION.replace('Focus-visible (class → story)', 'Focus ring'),
      ),
    /Focus-visible \(class → story\)/,
  )
  const withSection = regionFixture({
    matrices: { Tooltip: [r3Row('button @ index.tsx:9')] },
  })
  assert.throws(
    () =>
      findUnaccountedForceStates(stories, withSection.replace('| Press (active) |', '| Press |')),
    /Press \(active\)/,
  )
  assert.throws(
    () =>
      findUnaccountedForceStates(stories, regionFixture({ record1: [['composites/A', 'button']] })),
    /cells/,
  )
  // A Record 1 cell with no ` → ` separator is not a `class → story` cell at all.
  assert.throws(
    () =>
      findUnaccountedForceStates(
        stories,
        regionFixture({
          record1: [['composites/A', 'button', 'index.tsx:3', 'none', 'none', 'none']],
        }),
      ),
    /→/,
  )
})

test('findUnaccountedForceStates throws on a real story entry that carries no storyFile (T684, L3)', () => {
  const stories = new Map([
    ['composites/A', [{ exportName: 'Hover', forced: { state: 'hover', role: 'button' } }]],
  ])
  assert.throws(() => findUnaccountedForceStates(stories, EMPTY_REGION), /storyFile/)
})

// --- Real pipeline: the same, end to end through computeStateCoverage ------------------------------

const SHARED_NAME_NOTICE_INDEX = `
export function Notice({ href }) {
  return (
    <a href={href} className="hover:text-link-hover focus-visible:outline-2 active:text-link-hover">
      Read
    </a>
  )
}
`
const SHARED_NAME_NOTICE_STORIES = `
import { Notice } from './index'
const meta = { component: Notice, args: { href: '/a' } }
export default meta
export const Hover = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
}
`
// No element of role `link` anywhere in this component, so the forced story below can be credited
// on no cell and named in no unresolved reason: a lost frame, under a name another component's
// credited story already prints in the region.
const SHARED_NAME_PLAIN_INDEX = `
export function Plain() {
  return (
    <button type="button" className="hover:bg-surface-raised">
      Go
    </button>
  )
}
`
const SHARED_NAME_PLAIN_STORIES = `
import { Plain } from './index'
const meta = { component: Plain }
export default meta
export const Hover = {
  args: {},
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
}
`

test('findUnaccountedForceStates (via computeStateCoverage): an uncredited args-only Hover is reported although a credited Hover of another component is in the region (T684, real pipeline)', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Notice' },
    { segment: 'primitives', name: 'Plain' },
  ]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Notice/index.tsx'), SHARED_NAME_NOTICE_INDEX],
    [path.join(REPO_SRC_DIR, 'primitives/Notice/Notice.stories.tsx'), SHARED_NAME_NOTICE_STORIES],
    [path.join(REPO_SRC_DIR, 'primitives/Plain/index.tsx'), SHARED_NAME_PLAIN_INDEX],
    [path.join(REPO_SRC_DIR, 'primitives/Plain/Plain.stories.tsx'), SHARED_NAME_PLAIN_STORIES],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const notice = computed.localElements.find((c) => c.componentKey === 'primitives/Notice')
  assert.deepEqual(notice.elements[0].coveredBy.hover, ['Hover'])
  const plain = computed.localElements.find((c) => c.componentKey === 'primitives/Plain')
  assert.deepEqual(plain.elements[0].coveredBy.hover, ['none'])
  const { missing, known, expired } = computed.unaccountedForceStates
  assert.deepEqual(known, [])
  assert.deepEqual(expired, [])
  assert.deepEqual(missing, [
    { componentKey: 'primitives/Plain', exportName: 'Hover', state: 'hover' },
  ])
})

// A story named after its own component, forcing a state on a role nothing renders: the path of
// its own component in the region is not a credit (T684, M1, end to end).
test('findUnaccountedForceStates (via computeStateCoverage): a story named after its own component is reported, a uniquely named one too, and a credited one is not (T684, M1, real pipeline)', () => {
  const componentDirs = [{ segment: 'composites', name: 'Notice' }]
  const index = SHARED_NAME_NOTICE_INDEX
  const stories = `
import { Notice } from './index'
const meta = { component: Notice, args: { href: '/a' } }
export default meta
export const Hover = { args: {}, parameters: { visualForceState: { state: 'hover', role: 'link' } } }
export const Notice = { args: {}, parameters: { visualForceState: { state: 'hover', role: 'slider' } } }
export const ZzUnique = { args: {}, parameters: { visualForceState: { state: 'hover', role: 'slider' } } }
`
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'composites/Notice/index.tsx'), index],
    [path.join(REPO_SRC_DIR, 'composites/Notice/Notice.stories.tsx'), stories],
  ])
  const { missing } = computeStateCoverage({ componentDirs, filesByPath }).unaccountedForceStates
  assert.deepEqual(missingIds(missing), ['composites/Notice:Notice', 'composites/Notice:ZzUnique'])
})

// A second story file in a component directory (T684, M3, end to end): its credited story prints
// qualified, so it stays accounted; its uncredited story of the same name as the first file's
// credited one is reported.
test('findUnaccountedForceStates (via computeStateCoverage): a second story file in a component directory is accounted for by its own qualified label (T684, M3, real pipeline)', () => {
  const componentDirs = [{ segment: 'composites', name: 'Notice' }]
  const extra = `
import { Notice } from './index'
const meta = { component: Notice, args: { href: '/a' } }
export default meta
export const Hover = { args: {}, parameters: { visualForceState: { state: 'hover', role: 'slider' } } }
export const FocusVisible = { args: {}, parameters: { visualForceState: { state: 'focus-visible', role: 'link' } } }
`
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'composites/Notice/index.tsx'), SHARED_NAME_NOTICE_INDEX],
    [path.join(REPO_SRC_DIR, 'composites/Notice/Notice.stories.tsx'), SHARED_NAME_NOTICE_STORIES],
    [path.join(REPO_SRC_DIR, 'composites/Notice/Extra.stories.tsx'), extra],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const notice = computed.localElements.find((c) => c.componentKey === 'composites/Notice')
  assert.deepEqual(notice.elements[0].coveredBy.hover, ['Notice:Hover'])
  assert.deepEqual(notice.elements[0].coveredBy.focusVisible, ['Extra:FocusVisible'])
  assert.deepEqual(missingIds(computed.unaccountedForceStates.missing), ['composites/Notice:Hover'])
  assert.equal(computed.unaccountedForceStates.missing[0].state, 'hover')
})

// --- T684, round 2: the three text forms a story is read back through each name one story ---------

// M-A: a bare entry is the name followed by `: `, ` (` or the end of the entry. `<name>:` followed
// by anything else is another story's qualified label.
test("findUnaccountedForceStates: another story's qualified label `CountryFlag:FlagHoverRevealed` is not an entry of a story exported as CountryFlag (T684, M-A)", () => {
  const storyStatesByComponent = new Map([
    ['composites/Alpha', [storyFixture('composites/Alpha', 'CountryFlag')]],
  ])
  const { missing } = findUnaccountedForceStates(
    storyStatesByComponent,
    regionFixture({
      record1: [r1Row('composites/Alpha', { hover: 'CountryFlag:FlagHoverRevealed' })],
    }),
  )
  assert.deepEqual(missing, [
    { componentKey: 'composites/Alpha', exportName: 'CountryFlag', state: 'hover' },
  ])
})

test("contrast: a story's own bare reasons (`Name: N candidates …`, `Name: selector …`, `Name (play-driven; …)`, `Name (play-click-driven): …`) keep it accounted for, in every separator the reason builders print (T684, M-A)", () => {
  const reasons = [
    'unresolved: CountryFlag: 2 candidates share role "button"',
    'unresolved: CountryFlag: selector "[data-x]" not resolvable against this element\'s own "data-x"',
    'unresolved: CountryFlag (play-driven; frame not provable statically)',
    'unresolved: CountryFlag (play-click-driven): 2 candidates share role "button"',
    'unresolved: CountryFlag (play-driven): 2 candidates share role "button"',
    'CountryFlag',
    'Other; unresolved: CountryFlag: 2 candidates share role "button"',
  ]
  for (const reason of reasons) {
    const { missing } = findUnaccountedForceStates(
      new Map([['composites/Alpha', [storyFixture('composites/Alpha', 'CountryFlag')]]]),
      regionFixture({ record1: [r1Row('composites/Alpha', { hover: reason })] }),
    )
    assert.deepEqual(missing, [], reason)
  }
})

// A qualified label is not an entry of a story named like its base either.
test('findUnaccountedForceStates: a qualified label whose export part continues the name does not credit the shorter name (T684, M-A)', () => {
  const { missing } = findUnaccountedForceStates(
    new Map([['composites/Alpha', [storyFixture('composites/Alpha', 'Flag')]]]),
    regionFixture({ record1: [r1Row('composites/Alpha', { hover: 'Flag:Hover' })] }),
  )
  assert.deepEqual(missing, [
    { componentKey: 'composites/Alpha', exportName: 'Flag', state: 'hover' },
  ])
})

const PLANTED_STORY = (name, role, state = 'hover') =>
  `\nexport const ${name} = { args: {}, parameters: { visualForceState: { state: '${state}', role: '${role}' } } }\n`

// M-A on the real tree: `Tooltip` prints `CountryFlag:FlagHoverRevealed` in its own hover cell, and a
// story planted as `CountryFlag` forcing a role nothing renders must still be reported.
test("findUnaccountedForceStates (via computeStateCoverage): a story exported as CountryFlag, planted in Tooltip's stories, is reported beside its control (T684, M-A, real tree)", () => {
  const { componentDirs, filesByPath } = readAllSourceFiles()
  const tooltipStories = path.join(REPO_SRC_DIR, 'primitives/Tooltip/Tooltip.stories.tsx')
  assert.ok(filesByPath.has(tooltipStories))
  filesByPath.set(
    tooltipStories,
    filesByPath.get(tooltipStories) +
      PLANTED_STORY('CountryFlag', 'slider') +
      PLANTED_STORY('ZzCtlA', 'slider'),
  )
  const { missing, known, expired } = computeStateCoverage({
    componentDirs,
    filesByPath,
  }).unaccountedForceStates
  assert.deepEqual(known, [])
  assert.deepEqual(expired, [])
  assert.deepEqual(missingIds(missing), [
    'primitives/Tooltip:CountryFlag',
    'primitives/Tooltip:ZzCtlA',
  ])
})

// M-B: `<base>:<export>` carries no component, so two story files sharing a base are a failure.
const EXTRA_STORIES = `
import { Notice } from './index'
const meta = { component: Notice, args: { href: '/a' } }
export default meta
export const Hover = { args: {}, parameters: { visualForceState: { state: 'hover', role: 'link' } } }
`
const PLAIN_EXTRA_STORIES = `
import { Plain } from './index'
const meta = { component: Plain }
export default meta
export const Hover = { args: {}, parameters: { visualForceState: { state: 'hover', role: 'slider' } } }
`
const srcFile = (rel) => path.join(REPO_SRC_DIR, rel)

test('computeStateCoverage throws, naming both files and the shared base, when two components have a story file of the same basename (T684, M-B)', () => {
  const componentDirs = [
    { segment: 'composites', name: 'Notice' },
    { segment: 'composites', name: 'Plain' },
  ]
  const filesByPath = new Map([
    [srcFile('composites/Notice/index.tsx'), SHARED_NAME_NOTICE_INDEX],
    [srcFile('composites/Notice/Extra.stories.tsx'), EXTRA_STORIES],
    [srcFile('composites/Plain/index.tsx'), SHARED_NAME_PLAIN_INDEX],
    [srcFile('composites/Plain/Extra.stories.tsx'), PLAIN_EXTRA_STORIES],
  ])
  assert.throws(
    () => computeStateCoverage({ componentDirs, filesByPath }),
    (error) =>
      /composites\/Notice\/Extra\.stories\.tsx/.test(error.message) &&
      /composites\/Plain\/Extra\.stories\.tsx/.test(error.message) &&
      /label base "Extra"/.test(error.message),
  )
})

test('computeStateCoverage throws when a story file is not named after its component and another component has a story file of that name (T684, M-B)', () => {
  const componentDirs = [
    { segment: 'composites', name: 'Foo' },
    { segment: 'composites', name: 'Bar' },
  ]
  const filesByPath = new Map([
    [srcFile('composites/Foo/index.tsx'), SHARED_NAME_PLAIN_INDEX],
    [srcFile('composites/Foo/Bar.stories.tsx'), PLAIN_EXTRA_STORIES],
    [srcFile('composites/Bar/index.tsx'), SHARED_NAME_PLAIN_INDEX],
    [srcFile('composites/Bar/Bar.stories.tsx'), PLAIN_EXTRA_STORIES],
  ])
  assert.throws(
    () => computeStateCoverage({ componentDirs, filesByPath }),
    (error) =>
      /composites\/Foo\/Bar\.stories\.tsx/.test(error.message) &&
      /composites\/Bar\/Bar\.stories\.tsx/.test(error.message) &&
      /label base "Bar"/.test(error.message),
  )
})

test("computeStateCoverage throws when two directories of one component hold story files of the same basename, which a component's own bare-or-qualified printing cannot tell apart (T684, M-B)", () => {
  const componentDirs = [{ segment: 'composites', name: 'Notice' }]
  const filesByPath = new Map([
    [srcFile('composites/Notice/index.tsx'), SHARED_NAME_NOTICE_INDEX],
    [srcFile('composites/Notice/Extra.stories.tsx'), EXTRA_STORIES],
    [srcFile('composites/Notice/nested/Extra.stories.tsx'), EXTRA_STORIES],
  ])
  assert.throws(() => computeStateCoverage({ componentDirs, filesByPath }), /label base "Extra"/)
})

test("contrast: computeStateCoverage does not throw when only one component has Extra.stories.tsx, and that file's credited story stays accounted for (T684, M-B)", () => {
  const componentDirs = [
    { segment: 'composites', name: 'Notice' },
    { segment: 'composites', name: 'Plain' },
  ]
  const filesByPath = new Map([
    [srcFile('composites/Notice/index.tsx'), SHARED_NAME_NOTICE_INDEX],
    [srcFile('composites/Notice/Extra.stories.tsx'), EXTRA_STORIES],
    [srcFile('composites/Plain/index.tsx'), SHARED_NAME_PLAIN_INDEX],
    [srcFile('composites/Plain/Plain.stories.tsx'), PLAIN_EXTRA_STORIES],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const notice = computed.localElements.find((c) => c.componentKey === 'composites/Notice')
  assert.deepEqual(notice.elements[0].coveredBy.hover, ['Hover'])
  assert.deepEqual(missingIds(computed.unaccountedForceStates.missing), ['composites/Plain:Hover'])
})

// M-B on the real tree: a copy of Footer's stories named `Extra` credits `Extra:Hover` on `Link`'s
// matrix; a second `Extra.stories.tsx` in SearchBox used to be accounted for by it.
test('computeStateCoverage (real tree): Extra.stories.tsx planted in both Footer and SearchBox throws; planted in Footer alone it does not and reports nothing (T684, M-B)', () => {
  const { componentDirs, filesByPath } = readAllSourceFiles()
  const footer = readFileSync(srcFile('composites/Footer/Footer.stories.tsx'), 'utf8')
  filesByPath.set(srcFile('composites/Footer/Extra.stories.tsx'), footer)
  const alone = computeStateCoverage({ componentDirs, filesByPath })
  assert.deepEqual(alone.unaccountedForceStates.missing, [])
  filesByPath.set(
    srcFile('composites/SearchBox/Extra.stories.tsx'),
    `import { SearchBox } from './index'\nconst meta = { component: SearchBox }\nexport default meta\n` +
      PLANTED_STORY('Hover', 'slider') +
      PLANTED_STORY('ZzCtlB', 'slider'),
  )
  assert.throws(
    () => computeStateCoverage({ componentDirs, filesByPath }),
    (error) =>
      /composites\/Footer\/Extra\.stories\.tsx/.test(error.message) &&
      /composites\/SearchBox\/Extra\.stories\.tsx/.test(error.message),
  )
})

// L-1: one function spells the label base for every printer and for the reader, whatever the
// story file's extension.
test('buildAxisMatrix prints a `.stories.ts` file under the same label base findUnaccountedForceStates reads it back by (T684, L-1)', () => {
  const instances = [
    {
      primitive: 'Menu',
      kind: 'own-story',
      componentKey: 'primitives/Menu',
      file: 'packages/design-system/src/primitives/Menu/Extra.stories.ts',
      storyName: 'Hover',
      variant: { value: 'actions', resolved: 'explicit' },
      size: { value: null, resolved: 'n/a' },
      forced: { state: 'hover', role: 'button', name: null },
      playFocus: null,
    },
  ]
  const row = buildAxisMatrix('Menu', instances).find((r) => r.variantSize === 'actions')
  assert.deepEqual(row.hover, ['Extra:Hover'])
  const { missing } = findUnaccountedForceStates(
    new Map([
      [
        'primitives/Menu',
        [storyFixture('primitives/Menu', 'Hover', 'hover', { storyFile: 'Extra.stories.ts' })],
      ],
    ]),
    regionFixture({ matrices: { Menu: [r3Row('actions', { hover: row.hover.join('; ') })] } }),
  )
  assert.deepEqual(missing, [])
})

test("findUnaccountedForceStates (via computeStateCoverage): KNOWN_UNACCOUNTED_FORCE_STATES is empty and the whole real tree reports zero missing, zero known and zero expired — T598's own completion condition, not a cell count (T595's own exception, ProfileSummary's SwitcherFocusVisibleAndOpen, closed by injectComposedPrimitiveLocalCredits)", () => {
  const { componentDirs, filesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { missing, known, expired } = computed.unaccountedForceStates
  assert.deepEqual(missing, [])
  assert.deepEqual(known, [])
  assert.deepEqual(expired, [])
  assert.deepEqual(KNOWN_UNACCOUNTED_FORCE_STATES, [])
})

// --- An allowlist with no expiry is how a temporary exception becomes permanent (the coordinator's
// own question, answered): a filed exception whose own `fixBy` has passed, or that is missing a
// required field, fails the run exactly like an unfiled loss — the same shape `a11y-allowlist.mjs`
// already enforces for its own file. ------------------------------------------------------------

test('findUnaccountedForceStates fails a filed exception once its own fixBy has passed, rather than reporting it as known forever (T595)', () => {
  const storyStatesByComponent = new Map([
    ['composites/Overdue', [storyFixture('composites/Overdue', 'StillLost')]],
  ])
  const saved = [...KNOWN_UNACCOUNTED_FORCE_STATES]
  KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
  KNOWN_UNACCOUNTED_FORCE_STATES.push({
    componentKey: 'composites/Overdue',
    exportName: 'StillLost',
    date: '2020-01-01',
    fixOwed: 'T000',
    fixBy: '2020-01-08',
    reason: 'test fixture, deliberately expired',
  })
  try {
    const { missing, known, expired } = findUnaccountedForceStates(
      storyStatesByComponent,
      EMPTY_REGION,
    )
    assert.deepEqual(missing, [])
    assert.deepEqual(known, [])
    assert.equal(expired.length, 1)
    assert.equal(expired[0].exportName, 'StillLost')
    assert.equal(expired[0].fixBy, '2020-01-08')
  } finally {
    KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
    KNOWN_UNACCOUNTED_FORCE_STATES.push(...saved)
  }
})

test('contrast: findUnaccountedForceStates keeps reporting a filed exception as known while its own fixBy is still in the future', () => {
  const storyStatesByComponent = new Map([
    ['composites/NotYetDue', [storyFixture('composites/NotYetDue', 'StillLost')]],
  ])
  const farFuture = new Date()
  farFuture.setFullYear(farFuture.getFullYear() + 10)
  const filed = [
    {
      componentKey: 'composites/NotYetDue',
      exportName: 'StillLost',
      date: '2026-09-19',
      fixOwed: 'T000',
      fixBy: farFuture.toISOString().slice(0, 10),
      reason: 'test fixture, not yet due',
    },
  ]
  const saved = [...KNOWN_UNACCOUNTED_FORCE_STATES]
  KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
  KNOWN_UNACCOUNTED_FORCE_STATES.push(...filed)
  try {
    const { missing, known, expired } = findUnaccountedForceStates(
      storyStatesByComponent,
      EMPTY_REGION,
    )
    assert.deepEqual(missing, [])
    assert.deepEqual(expired, [])
    assert.equal(known.length, 1)
    assert.equal(known[0].exportName, 'StillLost')
  } finally {
    KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
    KNOWN_UNACCOUNTED_FORCE_STATES.push(...saved)
  }
})

test('findUnaccountedForceStates fails a malformed filed exception (missing fixOwed, invalid fixBy) rather than treating it as a valid, permanent exception', () => {
  const storyStatesByComponent = new Map([
    ['composites/Malformed', [storyFixture('composites/Malformed', 'StillLost')]],
  ])
  const saved = [...KNOWN_UNACCOUNTED_FORCE_STATES]
  KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
  KNOWN_UNACCOUNTED_FORCE_STATES.push({
    componentKey: 'composites/Malformed',
    exportName: 'StillLost',
    date: '2026-09-19',
    fixOwed: '',
    fixBy: 'not-a-date',
    reason: 'test fixture, malformed',
  })
  try {
    const { missing, known, expired } = findUnaccountedForceStates(
      storyStatesByComponent,
      EMPTY_REGION,
    )
    assert.deepEqual(missing, [])
    assert.deepEqual(known, [])
    assert.equal(expired.length, 1)
    assert.ok(expired[0].malformed.includes('fixOwed'))
    assert.ok(expired[0].malformed.some((m) => m.startsWith('fixBy')))
  } finally {
    KNOWN_UNACCOUNTED_FORCE_STATES.length = 0
    KNOWN_UNACCOUNTED_FORCE_STATES.push(...saved)
  }
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

// T599: `buildStoryPropsScope` seeds a component prop that has no destructuring default as
// `UNRESOLVED` for a story unless that story's own merged `args` names it explicitly — wrong about
// what Storybook renders. A story renders `<Component {...args} />`; `args` *is* the complete prop
// set, so a name absent from it is genuinely `undefined` at render, not unknown, and
// `evaluateGuards` must read `'unreached'` there, not `'unresolved'`. `PrivacyNotice`'s own
// `controllerContact ? <a…> : null` (`index.tsx:797`) is the live shape this reproduces.

const CONTROLLER_CONTACT_SOURCE = `
function Widget({ controllerContact }) {
  return (
    <div>
      {controllerContact ? <a href={controllerContact.contactRoute}>Contact</a> : null}
    </div>
  )
}
`

test('buildStoryPropsScope resolves an optional, default-less prop a story never names in its own args to a real, confirmed undefined — and the guard it gates evaluates unreached, not unresolved (T599)', () => {
  const sourceFile = parse(CONTROLLER_CONTACT_SOURCE)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap, 'Widget')
  const anchor = found.find((f) => f.tag === 'a')
  assert.ok(anchor)

  const defaults = getComponentPropDefaults(sourceFile, 'Widget')
  // No destructuring default for `controllerContact` — a `null` default expression, the same shape
  // `PrivacyNotice`'s own optional prop carries.
  assert.equal(defaults.get('controllerContact'), null)

  // A story whose own merged `args` never name `controllerContact` at all — the exact shape
  // `PrivacyNotice`'s own `ObjectionCallToActionHover`/`FocusVisible`/`Active` stories carry.
  const mergedArgs = { resolved: true, value: { lastUpdated: '2026-08-30' } }
  const scope = buildStoryPropsScope(defaults, mergedArgs, new Map())

  assert.deepEqual(scope.get('controllerContact'), { resolved: true, value: undefined })
  assert.equal(evaluateGuards(anchor.guards, scope), 'unreached')
})

test('contrast: an optional prop supplied through render() as an explicit JSX prop still resolves to its real, supplied value, never to undefined merely because args does not name it (T599, MatchRow-shaped)', () => {
  const componentSourceFile = parse(
    `
function MatchRow({ match }) {
  return (
    <div>
      {match ? <a href={match.href}>Link</a> : null}
    </div>
  )
}
`,
    'MatchRow/index.tsx',
  )
  const constMap = buildConstStringMap(componentSourceFile)
  const found = findLocalElements(componentSourceFile, 'MatchRow/index.tsx', constMap, 'MatchRow')
  const anchor = found.find((f) => f.tag === 'a')
  assert.ok(anchor)
  const defaults = getComponentPropDefaults(componentSourceFile, 'MatchRow')
  assert.equal(defaults.get('match'), null)

  const storySourceFile = parse(
    `
const base = { href: '/real' }
export const Real = {
  render: () => <MatchRow match={base} />,
}
`,
    'MatchRow.stories.tsx',
  )
  const [{ node: storyNode }] = findExportedStoryObjects(storySourceFile)
  const storyFileScope = buildFileValueScope(storySourceFile)
  // No meta object at all, and this story's own `args` never mention `match` — `render:`'s explicit
  // JSX prop is the only signal for it.
  const mergedArgs = evaluateMergedArgsObject(null, storyNode, storyFileScope)
  assert.deepEqual(mergedArgs.value, {})

  const scope = buildStoryPropsScope(defaults, mergedArgs, storyFileScope)
  // `buildStoryPropsScope` alone (the `args`-only view) reads `match` as the real, confirmed
  // `undefined` a bare `{...args}` render would give it — the T599 fix, exercised here too.
  assert.deepEqual(scope.get('match'), { resolved: true, value: undefined })

  // The caller applies `findRenderJsxProps`'s own override *after* `buildStoryPropsScope`, the same
  // order `computeStateCoverage`'s own two call sites use — the real, explicit JSX value must win,
  // not the `args`-absent `undefined` above.
  for (const [propName, exprNode] of findRenderJsxProps(storyNode, 'MatchRow')) {
    scope.set(propName, evaluateExpr(exprNode, storyFileScope))
  }
  assert.deepEqual(scope.get('match'), { resolved: true, value: { href: '/real' } })
  assert.equal(evaluateGuards(anchor.guards, scope), 'reached')
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

// --- T595 (row 8, H5): the real `Menu` trigger shape (a script `.focus()` after an `Escape`-driven
// close, no `visualForceState`) resolves to `unresolved` through the same pipeline
// `computeStateCoverage` runs the real tree through — never a hand-built `buildElementCells` call —
// and resolves to `covered` once the story carries the real `visualForceState` T595 adds. Planted
// against this exact contrast (not just asserted after the fact): the "before" half below is the
// unfixed shape `Menu.stories.tsx`'s own `EscapeReturnsFocusToTrigger` carried before this task, and
// it fails the "after" half's own assertion — confirmed by running it against the pre-fix story text
// before adding the parameter. ------------------------------------------------------------------

const TRIGGER_INDEX_SOURCE = `
export function Trigger({ triggerLabel }) {
  return (
    <button
      type="button"
      className="outline-none focus-visible:outline-2 focus-visible:outline-focus-ring"
    >
      {triggerLabel}
    </button>
  )
}
`

function triggerStoriesSource(forced) {
  return `
import { within, userEvent, expect } from '@storybook/test'
import { Trigger } from './index'
const meta = { component: Trigger, args: {} }
export default meta

export const EscapeReturnsFocusToTrigger = {
  ${forced ? "parameters: { visualForceState: { state: 'focus-visible', role: 'button' } }," : ''}
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const trigger = canvas.getByRole('button')
    trigger.focus()
    await userEvent.keyboard('{Escape}')
    await expect(trigger).toHaveFocus()
  },
  args: { triggerLabel: 'aoe2guy' },
}
`
}

test('contrast: a Menu-trigger-shaped play-driven focus-after-Escape stays unresolved with no visualForceState (the pre-T595 shape, planted), and resolves to covered once the story carries one (real computeStateCoverage pipeline, record 1)', () => {
  const componentDirs = [{ segment: 'primitives', name: 'Trigger' }]

  const beforeFiles = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Trigger/index.tsx'), TRIGGER_INDEX_SOURCE],
    [
      path.join(REPO_SRC_DIR, 'primitives/Trigger/Trigger.stories.tsx'),
      triggerStoriesSource(false),
    ],
  ])
  const before = computeStateCoverage({ componentDirs, filesByPath: beforeFiles })
  const beforeRow = before.localElements.find((c) => c.componentKey === 'primitives/Trigger')
    .elements[0]
  assert.equal(beforeRow.coveredBy.focusVisible.length, 1)
  assert.match(beforeRow.coveredBy.focusVisible[0], /^unresolved:/)
  assert.match(beforeRow.coveredBy.focusVisible[0], /play-driven; frame not provable statically/)

  const afterFiles = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Trigger/index.tsx'), TRIGGER_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Trigger/Trigger.stories.tsx'), triggerStoriesSource(true)],
  ])
  const after = computeStateCoverage({ componentDirs, filesByPath: afterFiles })
  const afterRow = after.localElements.find((c) => c.componentKey === 'primitives/Trigger')
    .elements[0]
  assert.deepEqual(afterRow.coveredBy.focusVisible, ['EscapeReturnsFocusToTrigger'])
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

// T595: a story built entirely from `render:` and never mounting its own component at all (a
// `*NotApplicable` placeholder's own `<p>...</p>`, the shape `Dialog:EmptyHoverActiveDisabledNot
// Applicable` uses) supplies no data whatsoever about any candidate inside it — excluded before
// `resolveDisabledFromStories` runs at all (`storyRendersComponent`), never left to read
// `'unresolved'` by omission the way an ordinary story with unresolvable data correctly does
// (Fixture C / the contrast test above, `UNRESOLVABLE_WIDGET_*`). No `size` literal on the call
// site either (`Dialog`'s own `variant={...}`/no matching `size`, both dynamic) — the same
// `unresolved|lg`-shaped row a masking positive match on a *plain* `ghost` row could not prove this
// against: the only story in this fixture is the one that never renders `Widget` at all, so the
// row's own `disabled` cell has nothing else to fall back on, and the assertion actually
// distinguishes "skipped" from "happened to be outranked by real knowledge elsewhere".
const NOT_APPLICABLE_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
export function Widget({ primaryAction }) {
  return <Button variant={primaryAction.variant ?? 'ghost'} size="lg" disabled={primaryAction.disabled}>{primaryAction.label}</Button>
}
`
const NOT_APPLICABLE_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const EmptyNotApplicable = {
  render: () => <p>No candidate is ever mounted by this story.</p>,
}
`

test('resolveDisabledFromStories (via computeStateCoverage): a story that never mounts the component at all is skipped outright, not left to read unresolved by omission (T595)', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Widget/index.tsx',
      NOT_APPLICABLE_WIDGET_INDEX_SOURCE,
    ],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      NOT_APPLICABLE_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'unresolved|lg')
  assert.ok(row, "the candidate's own static rest entry still exists on its unresolved-variant row")
  // `EmptyNotApplicable` is this fixture's *only* story, and it never renders `Widget` — no
  // `primaryAction` in sight, real or otherwise — so it must contribute nothing at all: no
  // `unresolved: disabled not statically resolvable (Widget:EmptyNotApplicable)` note, real or
  // otherwise, and the cell falls to the same confirmed `'none'` every other information-free cell
  // in this matrix already reads.
  assert.deepEqual(row.disabled, ['none'])
})

// Contrast, in one fixture, so the two cannot be conflated: a story that genuinely renders the
// component but whose own data cannot resolve the expression (`Default`, a function call over a
// prop) must still read `'unresolved'` — a check that ran and could not settle, never a skip —
// while the one that never mounts the component at all (`EmptyNotApplicable`) contributes nothing,
// not even a second `'unresolved'` reason.
const CONTRAST_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
export function Widget({ status }) {
  return <Button variant="ghost" disabled={computeDisabled(status)}>Toggle</Button>
}
`
const CONTRAST_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const Default = { args: { status: 'idle' } }
export const EmptyNotApplicable = {
  render: () => <p>No candidate is ever mounted by this story.</p>,
}
`

test('contrast: resolveDisabledFromStories (via computeStateCoverage) keeps `unresolved` for a story that renders the component but cannot settle the expression, and adds nothing for the sibling that never renders it at all (T595)', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    ['/repo/packages/design-system/src/composites/Widget/index.tsx', CONTRAST_WIDGET_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      CONTRAST_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'ghost')
  assert.ok(row)
  // Exactly one unresolved reason, and it names `Default` — the story that actually rendered
  // `Widget` and left `computeDisabled(status)` unresolvable — never `EmptyNotApplicable`, which
  // never got the chance to be either resolved or unresolved.
  assert.deepEqual(row.disabled, [
    'unresolved: disabled not statically resolvable (Widget:Default)',
  ])
})

// --- Orchestrator finding on T595's own hand-back: the redirect credit `cellFor` already applies
// to hover/focus-visible/active did not reach `disabled` at all, and the fix must be a property of
// the row (every column), never a second copy of the rule filed inside
// `resolveDisabledFromStories`. `Dialog`'s real shape, reproduced generally: two call sites with a
// dynamic `variant` (no literal to key a row on) and a literal `size`, each resolving to a
// *different* target row (`primaryAction` to `destructive|lg`-shaped, `secondaryAction` to
// `secondary|lg`-shaped) — plus `Button`'s own literal, unrelated `secondary|lg` story that shares
// `secondaryAction`'s own target row by axis coincidence, the exact pollution the orchestrator's
// review caught in the first version of this fix. `Button`'s own story, not a second composite: a
// `componentKeyForFile` quirk this suite's own fixtures already lean on (every other multi-component
// fixture here pairs exactly one composite with `Button`) collapses two *composite* fixtures under
// this fabricated `/repo/...` root into the same key, which would make the two indistinguishable to
// `resolveDisabledFromStories`'s own componentKey filter and prove nothing about the row credit this
// test targets. ------------------------------------------------------------------------------------

const REDIRECT_DIALOG_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
export function Widget({ primaryAction, secondaryAction }) {
  return (
    <div>
      <Button variant={primaryAction.variant ?? 'destructive'} size="lg" disabled={primaryAction.disabled} loading={primaryAction.loading}>{primaryAction.label}</Button>
      <Button variant={secondaryAction.variant ?? 'secondary'} size="lg" disabled={secondaryAction.disabled} loading={secondaryAction.loading}>{secondaryAction.label}</Button>
    </div>
  )
}
`
const REDIRECT_DIALOG_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const PrimaryPending = {
  args: { primaryAction: { label: 'Go', loading: true }, secondaryAction: { label: 'Cancel' } },
}
export const SecondaryPending = {
  args: { primaryAction: { label: 'Go' }, secondaryAction: { label: 'Cancel', disabled: true } },
}
`
// `Button`'s own literal `secondary|lg`, disabled directly in its own args — real coverage for
// *its own* call site (an `own-story` instance, credited independently of
// `resolveDisabledFromStories` entirely), never a fact about `Widget`'s `secondaryAction`, which
// only shares `secondary|lg` by axis coincidence.
const REDIRECT_BUTTON_OWN_STORIES_SOURCE = `
import { Button } from './index'
const meta = { component: Button, args: {} }
export default meta
export const SecondaryLgDisabled = { args: { variant: 'secondary', size: 'lg', disabled: true } }
`

test('resolveDisabledFromStories redirect (via computeStateCoverage): a row whose two call sites settle disabled on two different target rows is credited with both, not just the first (T595, orchestrator finding)', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/primitives/Button/Button.stories.tsx',
      REDIRECT_BUTTON_OWN_STORIES_SOURCE,
    ],
    [
      '/repo/packages/design-system/src/composites/Widget/index.tsx',
      REDIRECT_DIALOG_WIDGET_INDEX_SOURCE,
    ],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      REDIRECT_DIALOG_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'unresolved|lg')
  assert.ok(row, "both call sites' own static axis is unresolved — the row still exists")
  const secondaryLgRow = computed.matrices.Button.find((r) => r.variantSize === 'secondary|lg')
  assert.deepEqual(
    secondaryLgRow.disabled,
    ['Button:SecondaryLgDisabled', 'Widget:SecondaryPending'].sort(),
    "sanity check: secondary|lg itself carries both — Button's own and Widget's own",
  )
  // Both of `Widget`'s own call sites are credited on the static row — `primaryAction` proves
  // `Widget:PrimaryPending` on its own target row, `secondaryAction` proves `Widget:SecondaryPending`
  // on a *different* one — and `Button:SecondaryLgDisabled`, real coverage for a wholly unrelated
  // call site that only shares `secondary|lg` by axis coincidence, never leaks in.
  assert.deepEqual(row.disabled, ['Widget:PrimaryPending', 'Widget:SecondaryPending'])
})

// Contrast: a call site whose story resolves the axis to a real target row, but whose own
// `disabled`/`loading` genuinely evaluates `false` there (real negative knowledge, nothing to
// credit) must not manufacture coverage on the static row either.
const REDIRECT_NEVER_DISABLED_WIDGET_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
export function Widget({ primaryAction }) {
  return <Button variant={primaryAction.variant ?? 'destructive'} size="lg" disabled={primaryAction.disabled}>{primaryAction.label}</Button>
}
`
const REDIRECT_NEVER_DISABLED_WIDGET_STORIES_SOURCE = `
import { Widget } from './index'
const meta = { component: Widget, args: {} }
export default meta
export const Default = { args: { primaryAction: { label: 'Go' } } }
`

test('contrast: resolveDisabledFromStories redirect (via computeStateCoverage) never manufactures coverage when the redirect target itself has none (T595, orchestrator finding)', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Widget' },
  ]
  const filesByPath = new Map([
    ['/repo/packages/design-system/src/primitives/Button/index.tsx', BUTTON_INDEX_SOURCE],
    [
      '/repo/packages/design-system/src/composites/Widget/index.tsx',
      REDIRECT_NEVER_DISABLED_WIDGET_INDEX_SOURCE,
    ],
    [
      '/repo/packages/design-system/src/composites/Widget/Widget.stories.tsx',
      REDIRECT_NEVER_DISABLED_WIDGET_STORIES_SOURCE,
    ],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'unresolved|lg')
  assert.ok(row)
  // `Default` genuinely renders `Widget` and resolves `primaryAction.disabled` to a real `false` —
  // the target row (`destructive|lg`-shaped) itself has nothing to show, so the static row must not
  // invent a `'unresolved: axis resolved only per story (→ …)'` note or any other coverage either.
  assert.deepEqual(row.disabled, ['none'])
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

// T595: a bare JSX attribute (`<FavouriteToggle authenticated size="lg" />`, no `={...}`) is JSX
// shorthand for `={true}` — `RealisticProfileHeader`'s own shape. It used to carry no initializer
// at all, so it was never added to the props map — invisible, not `false` — which left an
// unrelated guard elsewhere in the same component (`if (!authenticated) return <SignedOutControl
// />`) unresolved by omission.
const BARE_ATTR_RENDER_SOURCE = `
export const RealisticProfileHeader = {
  render: () => <FavouriteToggle authenticated size="lg" enabled={false} />,
}
`

test('findRenderJsxProps reads a bare boolean attribute (no initializer) as `={true}`, not as absent (T595)', () => {
  const sourceFile = parse(BARE_ATTR_RENDER_SOURCE, 'FavouriteToggle.stories.tsx')
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const props = findRenderJsxProps(node, 'FavouriteToggle')
  assert.ok(props.has('authenticated'), 'a bare attribute is a real prop, not an absent one')
  assert.deepEqual(evaluateExpr(props.get('authenticated'), new Map()), {
    resolved: true,
    value: true,
  })
})

test('contrast: findRenderJsxProps never invents a value for a genuinely absent attribute, and still reads an explicit `={false}` as false, not as the bare-attribute shorthand (T595)', () => {
  const sourceFile = parse(BARE_ATTR_RENDER_SOURCE, 'FavouriteToggle.stories.tsx')
  const [{ node }] = findExportedStoryObjects(sourceFile)
  const props = findRenderJsxProps(node, 'FavouriteToggle')
  // `loading` is never written on this call site at all — absent, not `false`.
  assert.ok(!props.has('loading'))
  // `enabled={false}` is a real, explicit initializer — read through the ordinary path, never
  // mistaken for the bare-attribute shape just because it also resolves falsy-adjacent.
  assert.ok(props.has('enabled'))
  assert.deepEqual(evaluateExpr(props.get('enabled'), new Map()), { resolved: true, value: false })
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

// --- T595 (row 8, H5): closing the `unresolved: className not fully resolved` family — a
// function-local `const` (`Button`'s own `classes`) resolveClassParts previously never looked up at
// all, an `ElementAccessExpression` into a module-level object literal keyed by the component's own
// default `variant`/`size` (never every value the prop can take — a real axis record 3 already
// owns), the left operand of `cond && 'classes'` no longer pushed into `unresolved` as if it were
// itself class text, and the bare `className` passthrough prop treated as the caller-controlled
// slot it is rather than a genuinely unknown fragment. Each mechanism gets its own resolving case
// and its own contrast (boundary) case below, run against the pre-T595 code first (see the task
// hand-back for the failing output this file's own history records). --------------------------------

const BUTTON_SHAPE_INDEX_SOURCE = `
const variantClasses = {
  primary: 'bg-accent hover:bg-accent-hover active:bg-accent-active',
  secondary: 'bg-surface hover:bg-surface-sunken active:bg-background active:ring-2',
}
const sizeClasses = {
  md: 'h-10 px-4',
  lg: 'h-12 px-6',
}
const focusRing = 'focus-visible:outline-2 focus-visible:outline-offset-ring'
const primaryFocusRing = 'focus-visible:outline-2 focus-visible:outline-accent-contrast'

export function Widget({ variant = 'secondary', size = 'md', className }) {
  const classes = cx(
    'inline-flex items-center',
    sizeClasses[size],
    variantClasses[variant],
    variant === 'primary' ? primaryFocusRing : focusRing,
    className,
  )
  return <button className={classes}>Go</button>
}
`

test("buildElementMatrix (via computeStateCoverage): a function-local const (Button's own `classes`) fully resolves through an ElementAccessExpression keyed on the component's own default variant, a conditional on that same prop, and the className passthrough — classUnresolvedRefs empty, class text is the DEFAULT variant's own (Button shape)", () => {
  const storiesSource = `
    import { Widget } from './index'
    const meta = { component: Widget, args: {} }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Widget' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Widget/index.tsx'), BUTTON_SHAPE_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Widget/Widget.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Widget')
  const button = elements.find((el) => el.tag === 'button')
  assert.ok(button, "Widget's own button must be found as a local element")
  assert.deepEqual(button.classUnresolvedRefs, [])
  // `secondary` (the default): its own hover/active classes, never `primary`'s — the "record 1
  // shows the default configuration" decision `resolveClassParts`'s own top comment states.
  assert.equal(button.hover, 'hover:bg-surface-sunken')
  assert.equal(button.active, 'active:bg-background active:ring-2')
  // `variant === 'primary'` is false for the default — `focusRing`, never `primaryFocusRing`.
  assert.equal(button.focusVisible, 'focus-visible:outline-2 focus-visible:outline-offset-ring')
})

test('contrast: the same ElementAccessExpression and conditional stay genuinely unresolved when the component declares no default for the prop they key on — never guessed, the dual-branch-conservative conditional fallback still runs', () => {
  const noDefaultSource = BUTTON_SHAPE_INDEX_SOURCE.replace(
    "export function Widget({ variant = 'secondary', size = 'md', className }) {",
    'export function Widget({ variant, size, className }) {',
  )
  const storiesSource = `
    import { Widget } from './index'
    const meta = { component: Widget, args: { variant: 'primary', size: 'md' } }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Widget' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Widget/index.tsx'), noDefaultSource],
    [path.join(REPO_SRC_DIR, 'primitives/Widget/Widget.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Widget')
  const button = elements.find((el) => el.tag === 'button')
  // No default for `variant` in source (a story's own `args` is not this mechanism — record 1
  // resolves against the *component's own* default, per the shared decision, never a story's) —
  // the `ElementAccessExpression` stays unresolved, and so does the conditional it shares a
  // condition-prop with, since `evaluateExpr` against an empty default scope cannot settle it
  // either; both branches of the conditional are kept instead, the pre-T595 conservative behaviour.
  assert.ok(button.classUnresolvedRefs.includes('<ElementAccessExpression>'))
  assert.equal(button.hover, null)
  // Dual-branch fallback: both `primaryFocusRing` (whenTrue) and `focusRing` (whenFalse) show, in
  // that order, since this pass cannot know which one the caller's own `variant` will pick.
  assert.equal(
    button.focusVisible,
    'focus-visible:outline-2 focus-visible:outline-accent-contrast focus-visible:outline-2 focus-visible:outline-offset-ring',
  )
})

const TABLE_HREF_GUARD_INDEX_SOURCE = `
export function Row({ rows, getHref }) {
  return (
    <table>
      <tbody>
        {rows.map((row) => {
          const href = getHref?.(row)
          return (
            <tr
              key={row.id}
              className={cx('border-b', href && 'hover:bg-surface-sunken active:bg-surface-sunken')}
            >
              <td>{row.label}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
`

test("buildElementMatrix (via computeStateCoverage): the left operand of `cond && 'classes'` (Table's own `href &&`) is never pushed into classUnresolvedRefs — only the right-hand class string is a real candidate", () => {
  const storiesSource = `
    import { Row } from './index'
    const meta = { component: Row, args: { rows: [{ id: '1', label: 'x' }] } }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Row' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Row/index.tsx'), TABLE_HREF_GUARD_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Row/Row.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Row')
  const row = elements.find((el) => el.tag === 'tr')
  assert.ok(row, "Row's own tr must be found as a local element")
  assert.deepEqual(row.classUnresolvedRefs, [])
  assert.equal(row.hover, 'hover:bg-surface-sunken')
  assert.equal(row.active, 'active:bg-surface-sunken')
  assert.equal(row.focusVisible, null)
})

const OR_GUARD_INDEX_SOURCE = `
export function Panel({ emphasis }) {
  return <div className={cx('rounded-panel', emphasis || 'hover:opacity-75')}>Content</div>
}
`

test("contrast: the left operand of `cond || 'classes'` still IS a real candidate and stays pushed into classUnresolvedRefs when it cannot resolve — the && fix does not widen to || (Table's own href shape is && specifically)", () => {
  const storiesSource = `
    import { Panel } from './index'
    const meta = { component: Panel, args: {} }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Panel' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Panel/index.tsx'), OR_GUARD_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Panel/Panel.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Panel')
  const div = elements.find((el) => el.tag === 'div')
  assert.ok(div, "Panel's own div must be found as a local element (it carries a hover: class)")
  assert.ok(div.classUnresolvedRefs.includes('emphasis'))
})

const CALLER_CLASSNAME_ONLY_INDEX_SOURCE = `
export function Region({ className }) {
  return (
    <div role="region" tabIndex={0} className={cx('overflow-auto rounded-panel', focusRing, className)}>
      Content
    </div>
  )
}
const focusRing = 'focus-visible:outline-ring'
`

test("buildElementMatrix (via computeStateCoverage): a bare className passthrough (Table's own div shape) contributes no parts and is never pushed into classUnresolvedRefs — the element's own hover/active read a confirmed absence once nothing else paints them", () => {
  const storiesSource = `
    import { Region } from './index'
    const meta = { component: Region, args: {} }
    export default meta
    export const FocusVisible = {
      args: {},
      parameters: { visualForceState: { state: 'focus-visible', role: 'region', name: 'Content' } },
    }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Region' }]
  const filesByPath = new Map([
    [path.join(REPO_SRC_DIR, 'primitives/Region/index.tsx'), CALLER_CLASSNAME_ONLY_INDEX_SOURCE],
    [path.join(REPO_SRC_DIR, 'primitives/Region/Region.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Region')
  const div = elements.find((el) => el.tag === 'div')
  assert.ok(div, "Region's own div must be found as a local element")
  assert.deepEqual(div.classUnresolvedRefs, [])
  assert.equal(div.hover, null)
  assert.equal(div.active, null)
  assert.equal(div.focusVisible, 'focus-visible:outline-ring')
})

const CALLER_CLASSNAME_PLUS_CALL_INDEX_SOURCE = `
export function Region({ className }) {
  return (
    <div className={cx('overflow-auto hover:bg-surface-sunken', getExtraClasses(), className)}>
      Content
    </div>
  )
}
`

test('contrast: a genuinely unresolvable fragment that is not literally named `className` (an unknown function call) still stays in classUnresolvedRefs — the passthrough rule is narrowly scoped to that one identifier, not a blanket "ignore what this pass cannot read"', () => {
  const storiesSource = `
    import { Region } from './index'
    const meta = { component: Region, args: {} }
    export default meta
    export const Default = { args: {} }
  `
  const componentDirs = [{ segment: 'primitives', name: 'Region' }]
  const filesByPath = new Map([
    [
      path.join(REPO_SRC_DIR, 'primitives/Region/index.tsx'),
      CALLER_CLASSNAME_PLUS_CALL_INDEX_SOURCE,
    ],
    [path.join(REPO_SRC_DIR, 'primitives/Region/Region.stories.tsx'), storiesSource],
  ])
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Region')
  const div = elements.find((el) => el.tag === 'div')
  assert.ok(div, "Region's own div must be found as a local element (it carries a hover: class)")
  assert.ok(div.classUnresolvedRefs.includes('<call:getExtraClasses>'))
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

// --- T595 (row 8, H5, bucket b): "a state the component's own spec answers as impossible" -------
//
// A small `## Index` (`parseIndexTable`'s own fixture shape, `spec-completeness.test.mjs`) plus the
// closed state vocabulary sentence `deriveVocabulary` needs, covering the three scoping shapes this
// recogniser has to tell apart: `widget.md` (one component, whole document is its own scope),
// `pair.md` (two components, each under its own `##` heading — `findComponentSection` can isolate
// them), `shared-inline.md` (two components, one shared numbered section naming each inline — no
// heading boundary exists at all, `match-history.md`'s own real shape).
const IMPOSSIBLE_README_FIXTURE = `## Index

| Spec | Component directory | Feature |
| --- | --- | --- |
| [\`widget.md\`](./widget.md) | \`src/primitives/Widget/\` | 001 |
| [\`pair.md\`](./pair.md) | \`src/primitives/{Alpha,Beta}/\` | 001 |
| [\`shared-inline.md\`](./shared-inline.md) | \`src/primitives/{Gamma,Delta}/\` | 001 |

## Every spec has nine sections

The state vocabulary is closed: **default, hover, focus-visible, active, disabled, loading,
error, empty, selection, expansion**. Every spec answers all ten, even when the answer is "this
part is never disabled".
`

const WIDGET_SPEC = `## Widget

**States**

- **hover** — the control lifts with a soft shadow.
- **focus-visible** — a ring appears around the control.
- **active** — never. A widget cannot be pressed; pressing it does nothing because nothing here
  reacts.
- **disabled** — inapplicable today; see the open question below.
`

// The unrelated-clause regression fixture (`answerSaysImpossible`'s own header comment): a real,
// substantive first sentence with no closed-vocabulary phrase in it, followed by a *second*
// sentence that happens to contain "never" about something else entirely — the shape
// `tooltip.md:139`'s own "this used to say 'its `Button` state,' which was never true" lives in.
const WIDGET_UNRELATED_NEVER_SPEC = `## Widget

- **active** — the trigger shows a pressed ring while held. This used to say the control never
  pressed anything, which was never true.
`

const PAIR_SPEC = `## Alpha

- **active** — none; the root is not interactive.

## Beta

- **active** — a real pressed ring appears on every press, clearly painted.
`

const SHARED_INLINE_SPEC = `## 5. States

- **active** — \`Gamma\`: none; the root is not interactive. \`Delta\`: a real pressed ring appears on
  every press.
`

function fixtureVocabulary() {
  return deriveVocabulary(IMPOSSIBLE_README_FIXTURE)
}

// --- answerSaysImpossible / leadingSentence ------------------------------------------------------

test('answerSaysImpossible: matches a closed-vocabulary phrase in the leading sentence', () => {
  assert.equal(
    answerSaysImpossible('none; the root is not interactive. Actions have their own.'),
    true,
  )
  assert.equal(
    answerSaysImpossible('— never. A table whose data is stale says so elsewhere.'),
    true,
  )
  assert.equal(answerSaysImpossible('The table itself has no active state.'), true)
})

test('answerSaysImpossible: declines a real answer that never uses the closed vocabulary', () => {
  assert.equal(
    answerSaysImpossible('the control’s own text-entry state; no separate paint.'),
    false,
  )
  assert.equal(answerSaysImpossible('inapplicable today; see the open question below.'), false)
})

test('answerSaysImpossible: a coincidental match outside the leading sentence never counts (the false positive this task found live)', () => {
  // Mirrors `tooltip.md:139` exactly: the state's own first sentence is real prose with no closed
  // phrase in it, and only a *later*, unrelated sentence contains "never" — about a stale sentence
  // in the spec itself, not about whether this state happens. Without `leadingSentence`'s own
  // restriction to the first sentence, this string reads `true` (a bare pattern scan finds "never"
  // twice); this recogniser must read `false`.
  const text =
    'the trigger shows a pressed ring while held. This used to say the control never pressed ' +
    'anything, which was never true: the trigger clearly presses.'
  assert.equal(answerSaysImpossible(text), false)
})

// --- findVocabularyBoundarySpans ------------------------------------------------------------------

test('findVocabularyBoundarySpans: finds one span per bold state label, splitting a combined label into its own tokens', () => {
  const spans = findVocabularyBoundarySpans(
    '- **hover / active** — none; the root is not interactive.\n- **focus-visible** — a ring appears.',
    fixtureVocabulary(),
  )
  assert.deepEqual(
    spans.map((s) => s.tokens),
    [['hover', 'active'], ['focus-visible']],
  )
})

test('findVocabularyBoundarySpans: a nested, clause-leading bold span whose own token is not a vocabulary word is not a boundary', () => {
  // `structural-tier.md:667`'s own shape: "— **a link is never disabled.**" is itself a
  // clause-leading bold span (preceded by an em dash), but its own first token is "a", not a
  // vocabulary word — it must not be read as the *next* state's own label and truncate the real
  // answer before "never".
  const spans = findVocabularyBoundarySpans(
    '- **disabled** — **a link is never disabled.** A destination renders as `Text` instead.\n' +
      '- **loading** — none.',
    fixtureVocabulary(),
  )
  assert.deepEqual(
    spans.map((s) => s.tokens),
    [['disabled'], ['loading']],
  )
})

// --- resolveSpecAnswerForState ---------------------------------------------------------------------

test('resolveSpecAnswerForState: the passing case — a genuine closed-vocabulary "impossible" answer', () => {
  const result = resolveSpecAnswerForState({
    specSource: WIDGET_SPEC,
    components: [{ name: 'Widget', segment: 'primitives' }],
    componentName: 'Widget',
    state: 'active',
    vocabulary: fixtureVocabulary(),
  })
  assert.equal(result.status, 'impossible')
  assert.match(result.answerText, /never/)
})

test('resolveSpecAnswerForState: declines a real answer that does not use the closed vocabulary', () => {
  const result = resolveSpecAnswerForState({
    specSource: WIDGET_SPEC,
    components: [{ name: 'Widget', segment: 'primitives' }],
    componentName: 'Widget',
    state: 'disabled',
    vocabulary: fixtureVocabulary(),
  })
  assert.equal(result.status, 'decline')
  assert.match(result.reason, /not with the closed impossible vocabulary/)
})

test('resolveSpecAnswerForState: declines when the state is never answered in scope at all', () => {
  const result = resolveSpecAnswerForState({
    specSource: WIDGET_SPEC,
    components: [{ name: 'Widget', segment: 'primitives' }],
    componentName: 'Widget',
    state: 'loading',
    vocabulary: fixtureVocabulary(),
  })
  assert.equal(result.status, 'decline')
  assert.match(result.reason, /never answers "loading"/)
})

test('resolveSpecAnswerForState: required contrast — a bullet whose "never" is about a different state than the cell’s', () => {
  // `disabled` reads its own bullet ("inapplicable today"), never `active`'s "never" — proven by
  // asking for `disabled` against `WIDGET_SPEC`, whose `active` bullet is the one that says "never".
  const result = resolveSpecAnswerForState({
    specSource: WIDGET_SPEC,
    components: [{ name: 'Widget', segment: 'primitives' }],
    componentName: 'Widget',
    state: 'disabled',
    vocabulary: fixtureVocabulary(),
  })
  assert.notEqual(result.status, 'impossible')
})

test('resolveSpecAnswerForState: the unrelated-later-sentence regression (mirrors tooltip.md:139)', () => {
  const result = resolveSpecAnswerForState({
    specSource: WIDGET_UNRELATED_NEVER_SPEC,
    components: [{ name: 'Widget', segment: 'primitives' }],
    componentName: 'Widget',
    state: 'active',
    vocabulary: fixtureVocabulary(),
  })
  assert.equal(result.status, 'decline')
})

test('resolveSpecAnswerForState: required contrast — a bullet in a different component’s own section must not be borrowed across', () => {
  const forAlpha = resolveSpecAnswerForState({
    specSource: PAIR_SPEC,
    components: [
      { name: 'Alpha', segment: 'primitives' },
      { name: 'Beta', segment: 'primitives' },
    ],
    componentName: 'Alpha',
    state: 'active',
    vocabulary: fixtureVocabulary(),
  })
  const forBeta = resolveSpecAnswerForState({
    specSource: PAIR_SPEC,
    components: [
      { name: 'Alpha', segment: 'primitives' },
      { name: 'Beta', segment: 'primitives' },
    ],
    componentName: 'Beta',
    state: 'active',
    vocabulary: fixtureVocabulary(),
  })
  // Alpha's own section says "none; the root is not interactive" — impossible, for Alpha only.
  assert.equal(forAlpha.status, 'impossible')
  // Beta's own section says a real ring appears — Alpha's own "none" must never leak across into
  // Beta's own verdict, which is exactly what a whole-document (unscoped) read would do.
  assert.equal(forBeta.status, 'decline')
})

test('resolveSpecAnswerForState: a multi-component file with no per-component heading boundary declines rather than reading the whole document unscoped', () => {
  const result = resolveSpecAnswerForState({
    specSource: SHARED_INLINE_SPEC,
    components: [
      { name: 'Gamma', segment: 'primitives' },
      { name: 'Delta', segment: 'primitives' },
    ],
    componentName: 'Gamma',
    state: 'active',
    vocabulary: fixtureVocabulary(),
  })
  assert.equal(result.status, 'decline')
  assert.match(result.reason, /no per-component heading to scope to/)
})

// --- mapComponentKeyToSpecFile ----------------------------------------------------------------------

test('mapComponentKeyToSpecFile: resolves a componentKey to its own Index row', () => {
  const mapping = mapComponentKeyToSpecFile(IMPOSSIBLE_README_FIXTURE, 'primitives/Widget')
  assert.equal(mapping.specFile, 'widget.md')
  assert.equal(mapping.componentName, 'Widget')
  assert.equal(mapping.components.length, 1)
})

test('mapComponentKeyToSpecFile: declines (null) for a component the Index never names', () => {
  assert.equal(mapComponentKeyToSpecFile(IMPOSSIBLE_README_FIXTURE, 'primitives/Ghost'), null)
})

test('mapComponentKeyToSpecFile: declines (null) when more than one Index row claims the same componentKey', () => {
  const readme = `## Index

| Spec | Component directory | Feature |
| --- | --- | --- |
| [\`one.md\`](./one.md) | \`src/primitives/Widget/\` | 001 |
| [\`two.md\`](./two.md) | \`src/primitives/Widget/\` | 001 |

## Every spec has nine sections
`
  assert.equal(mapComponentKeyToSpecFile(readme, 'primitives/Widget'), null)
})

// --- classifyRecord1NoneCells / classifyRecord3NoneCells --------------------------------------------

const SPEC_SOURCES = new Map([
  ['widget.md', WIDGET_SPEC],
  ['pair.md', PAIR_SPEC],
  ['shared-inline.md', SHARED_INLINE_SPEC],
])

test('classifyRecord1NoneCells: the passing case end to end — one element, one confirmed-impossible state', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 10,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const results = classifyRecord1NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const activeCell = results.find((r) => r.state === 'active')
  assert.equal(activeCell.status, 'impossible')
})

test('classifyRecord1NoneCells: required contrast — a real class painted on the exact element is never classifiable as impossible', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 10,
            hover: null,
            focus: null,
            focusVisible: null,
            // A real `active:` utility is painted on this exact element, even though `WIDGET_SPEC`'s
            // own `active` bullet says "never" — the class is proof the component visually responds,
            // so this must decline, never read `impossible`.
            active: 'active:bg-surface-sunken',
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const results = classifyRecord1NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const activeCell = results.find((r) => r.state === 'active')
  assert.equal(activeCell.status, 'decline')
  assert.match(activeCell.reason, /a real class is painted/)
})

test('classifyRecord1NoneCells: a sibling element with real coverage for the same state declines every none cell of that state in the component', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'a',
            file: 'f.tsx',
            line: 1,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
          {
            tag: 'button',
            file: 'f.tsx',
            line: 5,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            // This sibling's own `active` state IS covered by a real story — proof `WIDGET_SPEC`'s
            // own "active — never" cannot describe every candidate in this component.
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['SomeStory'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const results = classifyRecord1NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const firstElementActive = results.find((r) => r.line === 1 && r.state === 'active')
  assert.equal(firstElementActive.status, 'decline')
  assert.match(firstElementActive.reason, /another local element/)
})

test('classifyRecord1NoneCells: a multi-component file with no per-component boundary declines rather than crediting the wrong component', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Gamma',
        elements: [
          {
            tag: 'button',
            file: 'g.tsx',
            line: 1,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const results = classifyRecord1NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  assert.equal(results[0].status, 'decline')
})

// --- T595 (row 8, group 3): `inertByConstruction` closes a cell directly, with no spec lookup at
// all — `componentKey: 'composites/Unmapped'` deliberately maps to no `## Index` row here (unlike
// every other fixture above, which resolves through `IMPOSSIBLE_README_FIXTURE`), so a passing
// result can only come from the inert-by-construction guard itself, never from the ordinary spec
// path this task's other guards already cover.
test('classifyRecord1NoneCells: an inert-by-construction element (UploadControl shape) is impossible with no spec lookup at all', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'composites/Unmapped',
        elements: [
          {
            tag: 'input',
            file: 'f.tsx',
            line: 274,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            inertByConstruction: true,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const results = classifyRecord1NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  for (const state of ['hover', 'focus-visible', 'active']) {
    const cell = results.find((r) => r.state === state)
    assert.equal(cell.status, 'impossible')
    assert.match(cell.reason, /inert by construction/)
  }
})

// Required contrast: a sibling that is NOT inert by construction, and does not carry a painted
// class either, still goes through the ordinary spec-mapping path (declining here, since
// `composites/Unmapped` maps to no Index row) — the inert guard must never leak from one element
// onto another in the same component.
test('classifyRecord1NoneCells: inertByConstruction on one element never swallows a sibling that is not inert', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'composites/Unmapped',
        elements: [
          {
            tag: 'input',
            file: 'f.tsx',
            line: 274,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            inertByConstruction: true,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
          {
            tag: 'button',
            file: 'f.tsx',
            line: 290,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            inertByConstruction: false,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const results = classifyRecord1NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const inertCell = results.find((r) => r.line === 274 && r.state === 'active')
  const realCell = results.find((r) => r.line === 290 && r.state === 'active')
  assert.equal(inertCell.status, 'impossible')
  assert.equal(realCell.status, 'decline')
  assert.equal(realCell.reason, 'component does not map to exactly one Index row')
})

test('classifyRecord3NoneCells: the passing case end to end — a non-axis row (Table-shaped), one confirmed-impossible state', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 10,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {
      Widget: [
        {
          variantSize: 'button @ f.tsx:10',
          rest: ['f.tsx:10'],
          hover: ['none'],
          focusVisible: ['none'],
          active: ['none'],
          disabled: ['none'],
        },
      ],
    },
  }
  const results = classifyRecord3NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const activeCell = results.find((r) => r.state === 'active')
  assert.equal(activeCell.status, 'impossible')
})

test('classifyRecord3NoneCells: a non-axis row cross-references its own exact record-1 element, never a component-wide guess', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 10,
            hover: null,
            focus: null,
            focusVisible: null,
            // Painted on the exact element this row is about.
            active: 'active:bg-surface-sunken',
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {
      Widget: [
        {
          variantSize: 'button @ f.tsx:10',
          rest: ['f.tsx:10'],
          hover: ['none'],
          focusVisible: ['none'],
          active: ['none'],
          disabled: ['none'],
        },
      ],
    },
  }
  const results = classifyRecord3NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const activeCell = results.find((r) => r.state === 'active')
  assert.equal(activeCell.status, 'decline')
  assert.match(activeCell.reason, /a real class is painted/)
})

test('classifyRecord3NoneCells: an axis row (no single element to pin a class to) declines when the primitive’s own record-1 element paints the class elsewhere', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 10,
            hover: null,
            focus: null,
            focusVisible: null,
            // The primitive's own local element paints `active:` — real evidence the DOM responds
            // to this state somewhere, even though this specific axis row's own default class is
            // unresolved (record 1's own Method: only the default variant's class is ever known).
            active: 'active:bg-surface-sunken',
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['SomeStory'] },
          },
        ],
      },
    ],
    matrices: {
      Widget: [
        {
          variantSize: 'ghost|lg',
          rest: ['x.tsx:1'],
          hover: ['none'],
          focusVisible: ['none'],
          // No axis-row sibling covers `active` either — only the primitive-own-class guard should
          // be the reason this declines, not the sibling guard.
          active: ['none'],
          disabled: ['none'],
        },
      ],
    },
  }
  const results = classifyRecord3NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const activeCell = results.find((r) => r.state === 'active')
  assert.equal(activeCell.status, 'decline')
  assert.match(activeCell.reason, /own local element paints a class/)
})

test('classifyRecord3NoneCells: another row of the same primitive matrix with real coverage declines every none row for that state', () => {
  const computed = {
    localElements: [],
    matrices: {
      Widget: [
        {
          variantSize: 'ghost|lg',
          rest: ['x.tsx:1'],
          hover: ['none'],
          focusVisible: ['none'],
          active: ['none'],
          disabled: ['none'],
        },
        {
          variantSize: 'primary|md',
          rest: ['y.tsx:2'],
          hover: ['none'],
          focusVisible: ['none'],
          // A sibling axis row DOES have real `active` coverage.
          active: ['SomeStory'],
          disabled: ['none'],
        },
      ],
    },
  }
  const results = classifyRecord3NoneCells(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    vocabulary: fixtureVocabulary(),
  })
  const ghostActive = results.find((r) => r.variantSize === 'ghost|lg' && r.state === 'active')
  assert.equal(ghostActive.status, 'decline')
  assert.match(ghostActive.reason, /another row of this primitive matrix/)
})

test('classifyImpossiblePerSpec: derives its own vocabulary from readmeSource and returns both records', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 10,
            hover: null,
            focus: null,
            focusVisible: null,
            active: null,
            coveredBy: { hover: ['none'], focusVisible: ['none'], active: ['none'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const { record1, record3 } = classifyImpossiblePerSpec(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
  })
  assert.equal(record1.find((r) => r.state === 'active').status, 'impossible')
  assert.deepEqual(record3, [])
})

// --- parseRow8DebtEntries / checkCellGate (T595's own closing commit) -------------------------
//
// T595's own three closures for a `'none'` cell: a story (the cell reads `'covered'` and this gate
// never reaches it), the spec answering it impossible (`classifyImpossiblePerSpec`, already
// covered above), or a dated entry in row 8's own prose naming it exactly. These tests are the
// third closure and the gate requiring one of the three — the required contrast the task brief
// itself names twice: an entry must never close a cell it does not name, and an entry past its own
// `fixBy` must never keep closing anything. Each fixture below plants the shape the gate must catch
// and is run against the gate to prove it actually catches it, never merely that it can pass.

function readmeWithDebtBlock(blockBody) {
  return `${IMPOSSIBLE_README_FIXTURE}\n<!-- state-coverage-debt\n${blockBody}\n-->\n`
}

test('parseRow8DebtEntries: reads date/fixBy/owner fields and R1/R3 cell lines out of a block', () => {
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'owner: T999',
      'R1 primitives/Widget hover button@f.tsx:10',
      'R3 Button active destructive|lg',
    ].join('\n'),
  )
  const entries = parseRow8DebtEntries(readmeSource)
  assert.equal(entries.length, 1)
  const [entry] = entries
  assert.equal(entry.date, '2026-09-20')
  assert.equal(entry.fixBy, '2026-09-27')
  assert.equal(entry.owner, 'T999')
  assert.deepEqual(entry.cells, [
    {
      record: 1,
      componentKey: 'primitives/Widget',
      state: 'hover',
      tag: 'button',
      file: 'f.tsx',
      line: 10,
    },
    { record: 3, primitiveName: 'Button', state: 'active', variantSize: 'destructive|lg' },
  ])
})

test('parseRow8DebtEntries: a free-text line beside the fields is silently ignored rather than misread as a field or a cell', () => {
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'owner: no fixed owner',
      'This sentence explains why in plain English and names no cell of its own.',
      'R1 primitives/Widget active button@f.tsx:10',
    ].join('\n'),
  )
  const [entry] = parseRow8DebtEntries(readmeSource)
  assert.equal(entry.cells.length, 1)
  assert.equal(entry.owner, 'no fixed owner')
})

// `hover`/`focus-visible` are real story coverage on purpose — `Beta`'s own spec (`PAIR_SPEC`)
// answers only `active`, so leaving the other two states `'none'` would decline them too (no
// per-component boundary answers them at all) and pollute every assertion below with cells these
// tests are not about. Isolating `active` as the fixture's one declining cell is what lets each
// test assert an exact `uncovered`/`unresolved` list rather than filtering it down first.
function widgetActiveNoneComputed(extraElement) {
  const elements = [
    {
      tag: 'button',
      file: 'f.tsx',
      line: 1,
      hover: null,
      focus: null,
      focusVisible: null,
      active: null,
      coveredBy: { hover: ['SomeStory'], focusVisible: ['SomeStory'], active: ['none'] },
    },
  ]
  if (extraElement) elements.push(extraElement)
  return {
    localElements: [{ componentKey: 'primitives/Beta', elements }],
    matrices: {},
  }
}

test('checkCellGate: a live entry naming a none cell exactly closes it', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'owner: T999',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.deepEqual(gate.uncovered, [])
  assert.deepEqual(gate.unresolved, [])
  assert.equal(gate.liveEntries.length, 1)
})

// The task's own required boundary: "an entry must not be able to close a cell it does not name."
// Two `'none'` cells in the same component, same state (`Beta`'s own spec answer for `active` is a
// real, substantive, non-impossible paragraph, so neither cell is classifiable `impossible`, and
// neither is a sibling-coverage decline either — both reach the entry check on their own merits).
// An entry names only the first. The second must still fail the gate even though *an* entry exists
// in the register — the exact failure a gate satisfied by "some entry exists somewhere" would miss.
test('checkCellGate: required contrast — an entry never closes a cell it does not name, even when another cell of the same component and state is covered', () => {
  const secondElement = {
    tag: 'a',
    file: 'f.tsx',
    line: 2,
    hover: null,
    focus: null,
    focusVisible: null,
    active: null,
    coveredBy: { hover: ['SomeStory'], focusVisible: ['SomeStory'], active: ['none'] },
  }
  const computed = widgetActiveNoneComputed(secondElement)
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'owner: T999',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.uncovered.length, 1)
  assert.equal(gate.uncovered[0].line, 2)
  assert.equal(gate.uncovered[0].tag, 'a')
})

test('checkCellGate: required contrast — record 3 holds the same boundary as record 1 (an entry names one axis row, never a sibling row it does not)', () => {
  const computed = {
    localElements: [],
    matrices: {
      Button: [
        {
          variantSize: 'destructive|lg',
          rest: ['f.tsx:1'],
          hover: ['SomeStory'],
          focusVisible: ['SomeStory'],
          active: ['none'],
          disabled: ['SomeStory'],
        },
        {
          variantSize: 'ghost|lg',
          rest: ['f.tsx:2'],
          hover: ['SomeStory'],
          focusVisible: ['SomeStory'],
          active: ['none'],
          disabled: ['SomeStory'],
        },
      ],
    },
  }
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'owner: T999',
      'R3 Button active destructive|lg',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.uncovered.length, 1)
  assert.equal(gate.uncovered[0].variantSize, 'ghost|lg')
  assert.equal(gate.uncovered[0].state, 'active')
})

test('checkCellGate: an entry not yet past its own fixBy still closes the cell it names', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'owner: T999',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-26',
  })
  assert.deepEqual(gate.uncovered, [])
  assert.deepEqual(gate.expiredCovering, [])
  assert.equal(gate.liveEntries.length, 1)
})

// The task's own second required boundary: "an expired entry must not silently keep passing."
test('checkCellGate: required contrast — an entry past its own fixBy stops closing the cell it names, and is reported rather than silently dropped', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-08-01',
      'fixBy: 2026-09-19',
      'owner: T999',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.deepEqual(gate.uncovered, [])
  assert.equal(gate.expiredCovering.length, 1)
  assert.equal(gate.expiredCovering[0].line, 1)
  assert.equal(gate.expiredEntries.length, 1)
  assert.equal(gate.liveEntries.length, 0)
})

test('checkCellGate: a malformed entry (missing fixBy) never closes the cell it names', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithDebtBlock(
    ['date: 2026-09-20', 'owner: T999', 'R1 primitives/Beta active button@f.tsx:1'].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.uncovered.length, 1)
  assert.equal(gate.malformedEntries.length, 1)
  assert.deepEqual(gate.malformedEntries[0].malformed, ['fixBy'])
  assert.equal(gate.malformedEntries[0].kind, 'debt')
})

test('checkCellGate: a debt entry missing owner (date and fixBy both present) never closes the cell it names — a debt entry must carry all three', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithDebtBlock(
    ['date: 2026-09-20', 'fixBy: 2026-09-27', 'R1 primitives/Beta active button@f.tsx:1'].join(
      '\n',
    ),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.uncovered.length, 1)
  assert.equal(gate.malformedEntries.length, 1)
  assert.deepEqual(gate.malformedEntries[0].malformed, ['owner'])
  assert.equal(gate.malformedEntries[0].kind, 'debt')
})

// --- parseRow8PermanentEntries / checkCellGate's permanent-entry half (this branch's own fix) ---
//
// A `<!-- state-coverage-debt -->` entry is time-boxed by construction: a well-formed one always
// expires once `today` passes its own `fixBy`, proven above. Some declining cells (row 8's own
// Cause B and Cause E, `packages/design-system/specs/README.md`) are never owed any work at all —
// the guard that declines them, or the spec answer it defers to, is a structural fact, not debt —
// so no `fixBy` could ever be chosen honestly. `<!-- state-coverage-permanent -->` is the distinct
// entry kind that closes those without expiring, and these tests are its own required contrasts:
// it still closes exactly the cell it names, at any date, and the gate rejects either shape
// carrying the other's fields.

function readmeWithPermanentBlock(blockBody) {
  return `${IMPOSSIBLE_README_FIXTURE}\n<!-- state-coverage-permanent\n${blockBody}\n-->\n`
}

test('parseRow8PermanentEntries: reads date/reason fields and R1/R3 cell lines out of a block, and carries no fixBy/owner at all', () => {
  const readmeSource = readmeWithPermanentBlock(
    [
      'date: 2026-09-20',
      'reason: a sibling already carries real coverage for this state — nothing is owed.',
      'R1 primitives/Widget hover button@f.tsx:10',
    ].join('\n'),
  )
  const [entry] = parseRow8PermanentEntries(readmeSource)
  assert.equal(entry.date, '2026-09-20')
  assert.equal(
    entry.reason,
    'a sibling already carries real coverage for this state — nothing is owed.',
  )
  assert.equal(entry.fixBy, undefined)
  assert.equal(entry.owner, undefined)
  assert.deepEqual(entry.cells, [
    {
      record: 1,
      componentKey: 'primitives/Widget',
      state: 'hover',
      tag: 'button',
      file: 'f.tsx',
      line: 10,
    },
  ])
})

// The defect this branch fixes, planted directly against the pre-fix shape: a permanent entry read
// as a debt entry would read `today: '2027-01-01'` as past every real `fixBy` this register has
// ever carried and fail. Proves the entry closes its cell at a date far past today, not merely not
// yet expired the way a debt entry's own "not yet past fixBy" test already shows.
test('checkCellGate: a permanent entry still closes its cell at a date far past today (2027-01-01) — it never expires', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithPermanentBlock(
    [
      'date: 2026-09-20',
      'reason: Guard 2 — a sibling element already carries real, story-proven coverage for this state.',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2027-01-01',
  })
  assert.deepEqual(gate.uncovered, [])
  assert.deepEqual(gate.expiredCovering, [])
  assert.deepEqual(gate.expiredEntries, [])
  assert.equal(gate.malformedEntries.length, 0)
  assert.equal(gate.permanentEntries.length, 1)
})

// Required contrast: a debt entry past its own fixBy must still expire and still fail, even once a
// permanent entry kind exists beside it — the new kind must not blunt the old one's own enforcement.
test('checkCellGate: required contrast — a debt entry past its own fixBy still expires and still fails, permanent entries notwithstanding', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-08-01',
      'fixBy: 2026-09-19',
      'owner: T999',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-28',
  })
  assert.deepEqual(gate.uncovered, [])
  assert.equal(gate.expiredCovering.length, 1)
  assert.equal(gate.expiredEntries.length, 1)
  assert.equal(gate.liveEntries.length, 0)
  assert.equal(gate.permanentEntries.length, 0)
})

test('checkCellGate: a permanent entry carrying a fixBy is malformed and fails, even with a real reason and date', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithPermanentBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'reason: Guard 2 — a sibling element already carries real, story-proven coverage.',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.uncovered.length, 1)
  assert.equal(gate.malformedEntries.length, 1)
  assert.equal(gate.malformedEntries[0].kind, 'permanent')
  assert.deepEqual(gate.malformedEntries[0].malformed, [
    'fixBy (a permanent entry may not carry fixBy)',
  ])
  assert.equal(gate.permanentEntries.length, 0)
})

test('checkCellGate: a permanent entry carrying an owner is malformed and fails (contrast — the other forbidden field)', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithPermanentBlock(
    [
      'date: 2026-09-20',
      'owner: T999',
      'reason: Guard 2 — a sibling element already carries real, story-proven coverage.',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.uncovered.length, 1)
  assert.equal(gate.malformedEntries.length, 1)
  assert.equal(gate.malformedEntries[0].kind, 'permanent')
  assert.deepEqual(gate.malformedEntries[0].malformed, [
    'owner (a permanent entry may not carry owner)',
  ])
})

test('checkCellGate: a permanent entry missing its reason is malformed and fails', () => {
  const computed = widgetActiveNoneComputed()
  const readmeSource = readmeWithPermanentBlock(
    ['date: 2026-09-20', 'R1 primitives/Beta active button@f.tsx:1'].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.uncovered.length, 1)
  assert.equal(gate.malformedEntries.length, 1)
  assert.equal(gate.malformedEntries[0].kind, 'permanent')
  assert.deepEqual(gate.malformedEntries[0].malformed, ['reason'])
})

test('checkCellGate: an unresolved cell fails regardless of any entry or spec answer — unresolved is not one of the three closures', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Beta',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 1,
            // `hover`/`focus-visible` carry a real, literal class of their own, so their class
            // half reads `'covered'` regardless of `classUnresolvedRefs` (`classifyClassHalf`
            // checks a non-null class text first) — isolating the element's one *unresolved*
            // expression to `active` alone, the state this test is actually about.
            hover: 'hover:bg-surface-sunken',
            focus: null,
            focusVisible: 'focus-visible:outline-2',
            active: null,
            // A real class expression this pass could not resolve — `classUnresolvedRefs`
            // non-empty forces the class half `'unresolved'` regardless of what `coveredBy` says
            // (`countRecord1Cells`'s own rule, mirrored here on purpose).
            classUnresolvedRefs: ['someDynamicExpr'],
            coveredBy: { hover: ['SomeStory'], focusVisible: ['SomeStory'], active: ['SomeStory'] },
          },
        ],
      },
    ],
    matrices: {},
  }
  const readmeSource = readmeWithDebtBlock(
    [
      'date: 2026-09-20',
      'fixBy: 2026-09-27',
      'owner: T999',
      'R1 primitives/Beta active button@f.tsx:1',
    ].join('\n'),
  )
  const gate = checkCellGate(computed, {
    readmeSource,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(gate.unresolved.length, 1)
  assert.equal(gate.unresolved[0].state, 'active')
  assert.deepEqual(gate.uncovered, [])
})

test('checkCellGate: a covered cell and an impossible cell need no entry at all', () => {
  const computed = {
    localElements: [
      {
        componentKey: 'primitives/Widget',
        elements: [
          {
            tag: 'button',
            file: 'f.tsx',
            line: 10,
            hover: null,
            focus: null,
            focusVisible: 'focus-visible:outline-2',
            active: null,
            coveredBy: {
              hover: ['none'],
              focusVisible: ['SomeStory'],
              active: ['none'],
            },
          },
        ],
      },
    ],
    matrices: {},
  }
  // No `state-coverage-debt` block at all — `focus-visible` is real story coverage and `active`
  // resolves `impossible` from `WIDGET_SPEC`'s own "active — never" (`Widget`'s own bullet); `hover`
  // is a real, substantive answer ("the control lifts with a soft shadow") and would need its own
  // entry, so this fixture only asserts the two cells that need none.
  const gate = checkCellGate(computed, {
    readmeSource: IMPOSSIBLE_README_FIXTURE,
    specSourcesByFile: SPEC_SOURCES,
    today: '2026-09-20',
  })
  assert.equal(
    gate.uncovered.find((c) => c.state === 'active'),
    undefined,
  )
  assert.equal(
    gate.uncovered.find((c) => c.state === 'focus-visible'),
    undefined,
  )
})

// --- T685 (row 8, H5): a raw element is not a primitive instance ---------------------------------
//
// A story whose `render:` mounts a raw `<button>` (and no `<MatchRow>`, no `<Button>`) used to be
// credited to the `Button` instance the *component under the story* composes elsewhere
// (`MatchRow`'s own `<Button variant="primary" size="lg">` retry control): with no instance of the
// primitive inside the story's own line range, `resolveComposedStoryMatches` fell back to every
// instance in the component's own source, and a single role match there needs no further
// disambiguation. The raw element is not that instance, and a story that mounts none of the
// component renders none of its source either — the frame depicts nothing in this component.
// The same path credited a raw `<a href>` to the component's own local `<a>` (record 1) and, for a
// story mounting `<Menu>`, to the unrelated `Button` the component composes. Every case below is
// planted against a small composite (`Row`) that composes one `Button` and one `Link` and declares
// one local `<a>`, so the unfixed fallback has a single, unambiguous wrong target to land on.

const T685_PRIMITIVE_SOURCES = {
  Button: `
export function Button({ variant = 'secondary', size = 'md', disabled, loading, children }) {
  return <button disabled={disabled || loading}>{children}</button>
}
`,
  Link: `
export function Link({ variant = 'inline', href, children }) {
  return <a href={href}>{children}</a>
}
`,
  Field: `
export function Field({ variant = 'text', size = 'md', children }) {
  return <input />
}
`,
  Menu: MENU_INDEX_SOURCE,
}

const T685_ROW_INDEX_SOURCE = `
import { Button } from '../../primitives/Button'
import { Link } from '../../primitives/Link'
export function Row({ onRetry, href }) {
  return (
    <div>
      <a href={href} className="hover:underline">
        Open
      </a>
      <Link href="/help" variant="standalone">
        Help
      </Link>
      <Button variant="primary" size="lg" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}
`

// Every cell any planted story is credited on, flattened to `<Primitive>|<row>|<state>` (record 3,
// `computed.matrices`) and `local:<componentKey>:<tag>|<state>` (record 1, `computed.localElements`,
// every component's local elements, primitives' own included). The state keys are read off what the
// script actually emits, never listed here: every own key of a matrix row holding an array of
// strings but `variantSize`, and every key of a record-1 element's `coveredBy`. A hard-coded list
// went stale once already (it read `focus-visible` and `press`, which no row carries).
// A non-axis primitive's matrix rows re-print its record 1 (`<tag> @ <file>:<line>` rows), so the
// keys `coveredBy` already carries are skipped there rather than credited twice; any other key of
// those rows (`disabled`, which only the matrix holds) is read. A cell names a credit when one
// entry IS the planted story's label (`Planted` or `<basename>:Planted`): an `unresolved: …` note
// that mentions it is not a credit.
const T685_STATE_KEYS = (row) =>
  Object.keys(row).filter((k) => k !== 'variantSize' && isStringArray(row[k]))
function isStringArray(value) {
  return Array.isArray(value) && value.every((v) => typeof v === 'string')
}
function plantedCredits(computed, label = 'Planted') {
  const isPlanted = (c) => c === label || c.endsWith(`:${label}`)
  const reprintedByRecord1 = new Set(
    computed.localElements.flatMap(({ elements }) =>
      elements.flatMap((el) => Object.keys(el.coveredBy)),
    ),
  )
  const credits = []
  for (const [primitive, rows] of Object.entries(computed.matrices)) {
    const isAxis = PRIMITIVE_NAMES.includes(primitive)
    for (const row of rows) {
      for (const state of T685_STATE_KEYS(row)) {
        if (!isAxis && reprintedByRecord1.has(state)) continue
        if (row[state].some(isPlanted)) credits.push(`${primitive}|${row.variantSize}|${state}`)
      }
    }
  }
  for (const { componentKey, elements } of computed.localElements) {
    for (const el of elements) {
      for (const state of Object.keys(el.coveredBy)) {
        if (el.coveredBy[state].some(isPlanted)) {
          credits.push(`local:${componentKey}:${el.tag}|${state}`)
        }
      }
    }
  }
  return credits.sort()
}

function t685Computed(
  renderJsx,
  forced,
  {
    rowIndexSource = T685_ROW_INDEX_SOURCE,
    storyImports = "import { Row } from './index'",
    storyMeta = 'const meta = { component: Row }\nexport default meta',
    storyHelpers = '',
    storyExtra = '',
    renderHead = '()',
    extraFiles = [],
    extraDirs = [],
    state = 'hover',
  } = {},
) {
  const componentDirs = [
    ...Object.keys(T685_PRIMITIVE_SOURCES).map((name) => ({ segment: 'primitives', name })),
    { segment: 'composites', name: 'Row' },
    ...extraDirs,
  ]
  const filesByPath = new Map(
    Object.entries(T685_PRIMITIVE_SOURCES).map(([name, source]) => [
      path.join(REPO_SRC_DIR, `primitives/${name}/index.tsx`),
      source,
    ]),
  )
  filesByPath.set(path.join(REPO_SRC_DIR, 'composites/Row/index.tsx'), rowIndexSource)
  filesByPath.set(
    path.join(REPO_SRC_DIR, 'composites/Row/Row.stories.tsx'),
    `
${storyImports}
${storyMeta}
${storyHelpers}
export const Planted = {
  render: ${renderHead} => (${renderJsx}),
  ${storyExtra}
  parameters: { visualForceState: { state: '${state}', ${forced} } },
}
`,
  )
  for (const [rel, source] of extraFiles) filesByPath.set(path.join(REPO_SRC_DIR, rel), source)
  return computeStateCoverage({ componentDirs, filesByPath })
}

function t685Credits(renderJsx, forced, options = {}) {
  return plantedCredits(t685Computed(renderJsx, forced, options))
}

test('T685: a story whose render mounts only a raw <button> credits no Button cell (the fallback onto Row’s own composed Button is closed)', () => {
  assert.deepEqual(
    t685Credits('<button type="button">Raw</button>', "role: 'button'"),
    [],
    'a raw <button> is not a Button instance, and Row is not mounted',
  )
})

test('T685 contrast: a story mounting <Button> at the same variant and size is still credited to that cell', () => {
  assert.deepEqual(
    t685Credits('<Button variant="primary" size="lg">Retry</Button>', "role: 'button'"),
    ['Button|primary|lg|hover'],
  )
})

test('T685 contrast: a story mounting <Button> at a different variant credits that variant’s cell, never Row’s composed primary|lg', () => {
  assert.deepEqual(
    t685Credits('<Button variant="ghost" size="sm">Back</Button>', "role: 'button'"),
    ['Button|ghost|sm|hover'],
  )
})

test('T685 sibling: a raw <a href> credits no Link cell and no local <a> of Row (it is neither a Link nor Row)', () => {
  assert.deepEqual(t685Credits('<a href="/x">Raw</a>', "role: 'link'"), [])
})

test('T685 sibling contrast: a story mounting <Link> credits only that Link cell, not Row’s local <a>', () => {
  assert.deepEqual(t685Credits('<Link href="/x" variant="standalone">L</Link>', "role: 'link'"), [
    'Link|standalone|hover',
  ])
})

test('T685 sibling: a raw <input>, <select> or <textarea> credits no cell anywhere', () => {
  assert.deepEqual(t685Credits('<input aria-label="x" />', "role: 'textbox'"), [])
  assert.deepEqual(
    t685Credits('<select aria-label="x"><option>a</option></select>', "role: 'combobox'"),
    [],
  )
  assert.deepEqual(t685Credits('<textarea aria-label="x" />', "role: 'textbox'"), [])
})

test('T685 sibling contrast: a story mounting <Field> credits no record-3 cell (Field renders under no single fixed role) but does credit Field’s own local <input> in record 1', () => {
  // The record-1 half used to be invisible: the helper read only `composites/Row`'s local elements,
  // so the credit `injectComposedPrimitiveLocalCredits` gives the primitive’s own `<input>` (a real
  // one — the story mounts `<Field>`, whose `<input>` is the textbox the force targets) never
  // showed. Pinned now that the helper reads every component’s record 1.
  assert.deepEqual(t685Credits('<Field variant="text" size="md" />', "role: 'textbox'"), [
    'local:primitives/Field:input|hover',
  ])
})

test('T685 sibling: a raw element carrying role="button" credits no Button cell', () => {
  assert.deepEqual(t685Credits('<div role="button" tabIndex={0}>Raw</div>', "role: 'button'"), [])
})

test('T685 sibling contrast: a story mounting <Menu> credits Menu’s cell, and no longer the unrelated Button Row composes', () => {
  // Before T685 this also read `Button|primary|lg|hover`: Menu renders role `button` too, and the
  // fallback matched Row's own composed Button for the same forced role.
  assert.deepEqual(t685Credits('<Menu variant="actions" />', "role: 'button'"), [
    'Menu|actions|hover',
  ])
})

test('T685: a raw <button> beside a real <Button> in one render adds nothing — only the real one is credited, and only at its own cell', () => {
  assert.deepEqual(
    t685Credits(
      '<><button type="button">Raw</button><Button variant="secondary" size="sm">Real</Button></>',
      "role: 'button'",
    ),
    ['Button|secondary|sm|hover'],
  )
})

test('T685: Row itself mounted is unchanged — the force still resolves against Row’s own composed Button and local elements (the component-is-rendered path)', () => {
  // `render: () => <Row />` mounts the component, so its own source is the right candidate set.
  // `name: "Retry"` pins Row's composed Button (primary|lg); Row's raw local <a> is another role.
  assert.deepEqual(t685Credits('<Row />', "role: 'button', name: 'Retry'"), [
    'Button|primary|lg|hover',
  ])
})

test('T685: a raw <button> inside a component that itself composes a real Button elsewhere is not credited as that Button', () => {
  const rowWithRawButton = `
import { Button } from '../../primitives/Button'
export function Row({ onRetry }) {
  return (
    <div>
      <button type="button" className="hover:bg-surface-sunken">
        Raw
      </button>
      <Button variant="primary" size="lg" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}
`
  // The story mounts a raw <button> only: neither Row's raw local button nor its composed Button
  // is on screen, so neither is credited.
  assert.deepEqual(
    t685Credits('<button type="button">Raw</button>', "role: 'button'", {
      rowIndexSource: rowWithRawButton,
    }),
    [],
  )
  // Row mounted and the force naming the composed Button's own text: the Button is credited, the
  // raw local button is not (it is left `unresolved`, never `covered`, which the helper above
  // reads as no credit).
  assert.deepEqual(
    t685Credits('<Row />', "role: 'button', name: 'Retry'", { rowIndexSource: rowWithRawButton }),
    ['Button|primary|lg|hover'],
  )
})

// The wider question T685's gate asks is "can this render reach anything of the component's own
// module", not "does it spell `<Row>`": the real tree mounts a sibling export of the module
// (`AccountErasurePanel`'s `<ErasedScreen>`) and a wrapper declared in the story file
// (`SearchBox.stories.tsx`'s `<DemoSearchBox>`), and both still depict the component.
test('T685 contrast: a render mounting a sibling export of the component’s own module still resolves against the component’s source (ErasedScreen shape)', () => {
  const rowWithSibling = `${T685_ROW_INDEX_SOURCE}
export function RowCompact(props) {
  return <Row {...props} />
}
`
  assert.deepEqual(
    t685Credits('<RowCompact />', "role: 'button'", {
      rowIndexSource: rowWithSibling,
      storyImports: "import { Row, RowCompact } from './index'",
    }),
    ['Button|primary|lg|hover'],
  )
})

test('T685 contrast: a render mounting a story-file wrapper that mounts the component still resolves against the component’s source (DemoSearchBox shape)', () => {
  assert.deepEqual(
    t685Credits('<Demo />', "role: 'button'", {
      storyHelpers: 'function Demo() {\n  return <Row />\n}',
    }),
    ['Button|primary|lg|hover'],
  )
})

test('T685: a story-file wrapper that mounts only a raw element does not reach the component, so it still credits nothing', () => {
  assert.deepEqual(
    t685Credits('<Demo />', "role: 'button'", {
      storyHelpers: 'function Demo() {\n  return <button type="button">Raw</button>\n}',
    }),
    [],
  )
})

test('T685: an import from another component’s module (../../) is not the component’s own module and does not reach it', () => {
  assert.deepEqual(
    t685Credits('<Other />', "role: 'button'", {
      storyImports: "import { Row } from './index'\nimport { Other } from '../../composites/Other'",
    }),
    [],
  )
})

// --- T685, remediation of the adversarial review of #111 ------------------------------------------
//
// The first T685 fix gated three paths. The review found the same defect — a story credited to a
// component's cells although its `render:` never mounts that component — on every other path that
// reads a story's render instances or falls back to the component's source. One `describe`-less
// group per path, each a separate level: record 1 (forced role, forced selector, dynamic role,
// play-click, play-focus), record 3 (composed primitive cells), the composed-elsewhere hop, and the
// injected local credits. Each plants the raw-element story and keeps a contrast that stays credited.

const T685_SELECTOR = `selector: 'a[href="/x"]'`
const T685_HREF_ARGS = "args: { href: '/x' }"

test('T685 record 1, selector branch: a raw <a href> story whose selector the component’s own <a> would resolve credits no local element', () => {
  assert.deepEqual(
    t685Credits('<a href="/x">Raw</a>', T685_SELECTOR, { storyExtra: T685_HREF_ARGS }),
    [],
  )
})

test('T685 record 1, selector branch contrast: the same selector on a story mounting <Row> is still credited to Row’s own <a>', () => {
  assert.deepEqual(t685Credits('<Row />', T685_SELECTOR, { storyExtra: T685_HREF_ARGS }), [
    'local:composites/Row:a|hover',
  ])
  assert.deepEqual(
    t685Credits('<Row {...args} />', T685_SELECTOR, {
      storyExtra: T685_HREF_ARGS,
      renderHead: '(args)',
    }),
    ['local:composites/Row:a|hover'],
  )
})

// The injected local credits: `Panel` composes a `Menu` whose `MenuItemRow` carries a dynamic role.
// A story that mounts a raw `<div role="menuitemradio">` and names the item through the meta `args`
// is not a rendering of `Panel`'s `<Menu>`, so it cannot be what `MenuItemRow`'s frame depicts.
test('T685 injected local credits: a raw role="menuitemradio" story credits no local element of a composed primitive, and the real story on the same element stays credited', () => {
  const stories = `
    import { Panel } from './index'
    const meta = { component: Panel, args: { subject: 'self', items: [{ id: 'p1', label: 'aoe2guy' }] } }
    export default meta
    export const RowFocusVisible = {
      args: {},
      parameters: { visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2guy' } },
    }
    export const PlantedRaw = {
      render: () => <div role="menuitemradio" tabIndex={0}>aoe2guy</div>,
      args: {},
      parameters: { visualForceState: { state: 'focus-visible', role: 'menuitemradio', name: 'aoe2guy' } },
    }
  `
  const computed = computeStateCoverage({
    componentDirs: [
      { segment: 'primitives', name: 'Menu' },
      { segment: 'screens', name: 'Panel' },
    ],
    filesByPath: new Map([
      [path.join(REPO_SRC_DIR, 'primitives/Menu/index.tsx'), MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE],
      [path.join(REPO_SRC_DIR, 'screens/Panel/index.tsx'), PANEL_WITH_SELECTION_MENU_INDEX_SOURCE],
      [path.join(REPO_SRC_DIR, 'screens/Panel/Panel.stories.tsx'), stories],
    ]),
  })
  const { elements } = computed.localElements.find((c) => c.componentKey === 'primitives/Menu')
  const menuItemRow = elements.find((el) => el.role === 'unresolved')
  assert.deepEqual(menuItemRow.coveredBy.focusVisible, ['Panel:RowFocusVisible'])
})

// Record 1 of a primitive's own dynamic-role element (`MenuItemRow`'s `role={role}`), resolved per
// story. Asserts on record 1 only: the same planted story also reaches `Menu`'s own axis matrix
// through the own-story path (`findOwnStoryRenderInstances` falling back to `args`), which is T686's.
function menuRecord1Credits(storyBody) {
  const computed = computeStateCoverage({
    componentDirs: [{ segment: 'primitives', name: 'Menu' }],
    filesByPath: new Map([
      [path.join(REPO_SRC_DIR, 'primitives/Menu/index.tsx'), MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE],
      [
        path.join(REPO_SRC_DIR, 'primitives/Menu/Menu.stories.tsx'),
        `import { Menu } from './index'\nconst meta = { component: Menu }\nexport default meta\n${storyBody}`,
      ],
    ]),
  })
  return plantedCredits(computed).filter((c) => c.startsWith('local:primitives/Menu:'))
}
const MENU_PLANTED_ARGS = `args: { variant: 'selection', items: [{ id: 'p2', label: 'aoe2alt' }] }`
const MENU_PLANTED_FORCE = (role, name) =>
  `parameters: { visualForceState: { state: 'hover', role: '${role}', ${name ? `name: '${name}'` : ''} } }`

test('T685 record 1, dynamic-role branch: a raw role="menuitemradio" story credits no dynamic-role element (record 1 only; Menu’s axis matrix is T686’s)', () => {
  assert.deepEqual(
    menuRecord1Credits(`export const Planted = {
      render: () => <div role="menuitemradio" tabIndex={0}>aoe2alt</div>,
      ${MENU_PLANTED_ARGS},
      ${MENU_PLANTED_FORCE('menuitemradio', 'aoe2alt')},
    }`),
    [],
  )
})

test('T685 record 1, dynamic-role branch contrast: an args-only story and a render mounting <Menu> both stay credited to the dynamic-role element', () => {
  assert.deepEqual(
    menuRecord1Credits(`export const Planted = {
      ${MENU_PLANTED_ARGS},
      ${MENU_PLANTED_FORCE('menuitemradio', 'aoe2alt')},
    }`),
    ['local:primitives/Menu:button|hover'],
  )
  assert.deepEqual(
    menuRecord1Credits(`export const Planted = {
      render: (args) => <Menu {...args} />,
      ${MENU_PLANTED_ARGS},
      ${MENU_PLANTED_FORCE('menuitemradio', 'aoe2alt')},
    }`),
    ['local:primitives/Menu:button|hover'],
  )
})

test('T685 record 1, dynamic-role branch, play-focus half: a raw story whose play() asserts focus on the role is not even considered', () => {
  const play = `play: async ({ canvasElement }) => {
      const item = within(canvasElement).getByRole('menuitemradio')
      item.focus()
      await expect(item).toHaveFocus()
    }`
  const computed = (storyBody) =>
    computeStateCoverage({
      componentDirs: [{ segment: 'primitives', name: 'Menu' }],
      filesByPath: new Map([
        [path.join(REPO_SRC_DIR, 'primitives/Menu/index.tsx'), MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE],
        [
          path.join(REPO_SRC_DIR, 'primitives/Menu/Menu.stories.tsx'),
          `import { Menu } from './index'\nconst meta = { component: Menu }\nexport default meta\n${storyBody}`,
        ],
      ]),
    })
  const focusCell = (c) =>
    c.localElements
      .find((e) => e.componentKey === 'primitives/Menu')
      .elements.find((el) => el.role === 'unresolved')
      .coveredBy.focusVisible.join(' ')
  const raw = computed(`export const Planted = {
    render: () => <div role="menuitemradio" tabIndex={0}>aoe2alt</div>,
    ${MENU_PLANTED_ARGS},
    ${play},
  }`)
  assert.doesNotMatch(focusCell(raw), /Planted/)
  const real = computed(`export const Planted = { ${MENU_PLANTED_ARGS}, ${play} }`)
  assert.match(focusCell(real), /Planted \(play-driven/)
})

test('T685 record 1, forced role on a primitive’s own static element: a raw <button> story credits Menu’s trigger no more than a Button does elsewhere; <Menu> still does', () => {
  assert.deepEqual(
    menuRecord1Credits(`export const Planted = {
      render: () => <button type="button">Raw</button>,
      ${MENU_PLANTED_FORCE('button')},
    }`),
    [],
  )
  assert.deepEqual(
    menuRecord1Credits(`export const Planted = {
      render: () => <Menu variant="actions" items={[]} />,
      ${MENU_PLANTED_FORCE('button')},
    }`),
    ['local:primitives/Menu:button|hover'],
  )
})

// The play-click and play-focus branches of record 1: `Tooltip`'s own trigger paints `active`
// through `pinned ? … : …`, and a story whose play() clicks a `getByRole('button')` pins it.
const TOOLTIP_PINNABLE_INDEX_SOURCE = `
export function Tooltip({ children }) {
  return (
    <span>
      <button type="button" className={cx('border-2', pinned ? 'border-border-strong' : 'border-transparent')}>
        {children}
      </button>
    </span>
  )
}
`
const TOOLTIP_PLAY_STORIES_SOURCE = `
import { Tooltip } from './index'
async function pinOpen({ canvasElement }) {
  const canvas = within(canvasElement)
  const trigger = canvas.getByRole('button')
  await userEvent.click(trigger)
}
async function focusOpen({ canvasElement }) {
  const canvas = within(canvasElement)
  const trigger = canvas.getByRole('button')
  trigger.focus()
  await expect(trigger).toHaveFocus()
}
const meta = { component: Tooltip }
export default meta
export const Pinned = { play: pinOpen, args: { content: 'France' } }
export const Focused = { play: focusOpen, args: { content: 'France' } }
export const PlantedPin = {
  render: () => <button type="button">Raw</button>,
  play: pinOpen,
  args: { content: 'France' },
}
export const PlantedFocus = {
  render: () => <button type="button">Raw</button>,
  play: focusOpen,
  args: { content: 'France' },
}
`
function tooltipPlayCoverage() {
  const computed = computeStateCoverage({
    componentDirs: [{ segment: 'primitives', name: 'Tooltip' }],
    filesByPath: new Map([
      [path.join(REPO_SRC_DIR, 'primitives/Tooltip/index.tsx'), TOOLTIP_PINNABLE_INDEX_SOURCE],
      [
        path.join(REPO_SRC_DIR, 'primitives/Tooltip/Tooltip.stories.tsx'),
        TOOLTIP_PLAY_STORIES_SOURCE,
      ],
    ]),
  })
  const [button] = computed.localElements.find(
    (c) => c.componentKey === 'primitives/Tooltip',
  ).elements
  return { computed, coveredBy: button.coveredBy }
}

test('T685 record 1, play-click branch: a raw <button> story whose play() clicks the role credits no Active cell; the real Pinned story stays credited', () => {
  const { computed, coveredBy } = tooltipPlayCoverage()
  assert.deepEqual(plantedCredits(computed, 'PlantedPin'), [])
  assert.deepEqual(coveredBy.active, ['Pinned'])
})

test('T685 record 1, play-focus branch: a raw <button> story whose play() asserts focus is not considered at all, while the real Focused story stays an unresolved play-driven note', () => {
  const { coveredBy } = tooltipPlayCoverage()
  const cell = coveredBy.focusVisible.join(' ')
  assert.doesNotMatch(cell, /PlantedFocus/)
  assert.match(cell, /Focused \(play-driven; frame not provable statically\)/)
})

// The composed-elsewhere hop: a name or a role-only force on a component that composes `Tooltip` is
// routed to `Tooltip`'s own trigger. A story that mounts only a raw `<button>` never shows that
// component's `<Tooltip>`, so the hop must not fire for it.
const FLAG_HOP_STORIES = (storyBody) => `
  import { Flag } from './index'
  const meta = { component: Flag, args: { countryName: 'France' } }
  export default meta
  ${storyBody}
`
function flagHopCredits(storyBody) {
  const computed = computeStateCoverage({
    componentDirs: [
      { segment: 'primitives', name: 'Tooltip' },
      { segment: 'composites', name: 'Flag' },
    ],
    filesByPath: new Map([
      [path.join(REPO_SRC_DIR, 'primitives/Tooltip/index.tsx'), TOOLTIP_LIKE_INDEX_SOURCE],
      [path.join(REPO_SRC_DIR, 'composites/Flag/index.tsx'), FLAG_LIKE_DIRECT_INDEX_SOURCE],
      [path.join(REPO_SRC_DIR, 'composites/Flag/Flag.stories.tsx'), FLAG_HOP_STORIES(storyBody)],
    ]),
  })
  return plantedCredits(computed)
}

test('T685 composed-elsewhere hop: a raw <button> story forcing a role-only hover (or the composed qualifier as name) credits Tooltip’s trigger to nobody', () => {
  assert.deepEqual(
    flagHopCredits(`export const Planted = {
      render: () => <button type="button">Raw</button>,
      parameters: { visualForceState: { state: 'hover', role: 'button' } },
    }`),
    [],
  )
  assert.deepEqual(
    flagHopCredits(`export const Planted = {
      render: () => <button type="button">Raw</button>,
      parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Country:' } },
    }`),
    [],
  )
})

test('T685 composed-elsewhere hop contrast: the same forces on a story that mounts <Flag> (render-less, or render mounting it) credit Tooltip’s trigger', () => {
  const role = `parameters: { visualForceState: { state: 'hover', role: 'button' } }`
  const named = `parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Country:' } }`
  assert.deepEqual(flagHopCredits(`export const Planted = { args: {}, ${role} }`), [
    'local:primitives/Tooltip:button|hover',
  ])
  assert.deepEqual(
    flagHopCredits(`export const Planted = { render: (args) => <Flag {...args} />, ${named} }`),
    ['local:primitives/Tooltip:button|hover'],
  )
})

// The predicate itself counts value references only. Each plant below is a raw `<button>` story
// whose text names `Row` somewhere that is not a use of the component; none reaches `Row`'s module,
// so none credits Row's composed `Button` (primary|lg). The shapes that do use it are further down.
const T685_RAW_BUTTON = '<button type="button">Raw</button>'
const T685_BUTTON_ROLE = "role: 'button'"

test('T685 predicate: a `typeof Row` inside a type annotation does not reach the component', () => {
  assert.deepEqual(
    t685Credits(T685_RAW_BUTTON, T685_BUTTON_ROLE, {
      renderHead: '(args: React.ComponentProps<typeof Row>)',
    }),
    [],
  )
})

test('T685 predicate: `meta.title` does not reach the component — meta is an object that merely names it (component: Row)', () => {
  assert.deepEqual(
    t685Credits('<button type="button" title={meta.title}>Raw</button>', T685_BUTTON_ROLE),
    [],
  )
})

test('T685 predicate: an object-literal key spelling the component does not reach it', () => {
  assert.deepEqual(
    t685Credits('<button type="button" data-x={{ Row: 1 }}>Raw</button>', T685_BUTTON_ROLE),
    [],
  )
})

test('T685 predicate: a property-access member spelling the component does not reach it', () => {
  assert.deepEqual(
    t685Credits('<button type="button" data-x={meta.Row}>Raw</button>', T685_BUTTON_ROLE),
    [],
  )
})

test('T685 predicate: a JSX attribute name spelling the component does not reach it', () => {
  assert.deepEqual(t685Credits('<button type="button" Row="x">Raw</button>', T685_BUTTON_ROLE), [])
})

// A data object that holds the component (`{ C: Row }`) is indistinguishable, by reference alone,
// from one a story mounts through (`<registry.C />`): both hold a value reference to `Row`. The
// predicate's safe error is `true` (a wrongly-true verdict only repeats the over-credit it closes,
// in a contrived shape; a wrongly-false one drops a real credit), so the object reaches — in the
// mounting use and in the data use alike. This replaces the first remediation's expectation that
// such an object "is not a helper", which held only because it special-cased objects and so turned
// `{ row: zzRow }` and `{ rows: { error: () => <Row /> } }` wrongly false. The meta object, which
// holds the component as data and cannot be mounted through, stays closed below.
test('T685 predicate: a story-file object holding the component as a value reaches, whether the story mounts through it or only reads it', () => {
  const storyHelpers = 'const registry = { C: Row }'
  assert.deepEqual(
    t685Credits('<registry.C />', T685_BUTTON_ROLE, { storyHelpers }),
    ['Button|primary|lg|hover'],
    'mounting through the object',
  )
  assert.deepEqual(
    t685Credits('<button type="button" data-x={registry.C.name}>Raw</button>', T685_BUTTON_ROLE, {
      storyHelpers,
    }),
    ['Button|primary|lg|hover'],
    'reading the object cannot be told from mounting through it, and errs toward reaching',
  )
})

test('T685 predicate: the meta object never reaches, however the file identifies it — each identifying rule alone is enough', () => {
  const metas = {
    'default export, with a component key': 'const meta = { component: Row }\nexport default meta',
    // The one rule each: the rest of these objects give the other rules nothing to find.
    'default export only (no component key, no type)':
      'const meta = { title: "Row", subcomponents: { Row } }\nexport default meta',
    'declared type only': 'const meta: Meta<typeof Row> = { subcomponents: { Row } }',
    'satisfies only': 'const meta = { subcomponents: { Row } } satisfies Meta<typeof Row>',
    'as only': 'const meta = { subcomponents: { Row } } as Meta<typeof Row>',
  }
  for (const [how, storyMeta] of Object.entries(metas)) {
    assert.deepEqual(
      t685Credits(
        '<button type="button" title={meta.title} data-x={meta.subcomponents}>Raw</button>',
        T685_BUTTON_ROLE,
        { storyMeta },
      ),
      [],
      how,
    )
  }
})

// `findMeta` returns the first top-level object with a `component` key and unwraps no
// `satisfies`/`as`, so it is not a meta-identification rule here: a story-file helper that merely
// carries a `component` key is a helper, and a story mounting through it reaches. The wrongly-false
// verdict is the one direction this predicate must never take.
const T685_CREDITED = ['Button|primary|lg|hover']
const T685_COMPONENT_KEY_HELPER = 'const zzHelpers = { component: Row, error: () => <Row /> }'

test('T685 predicate (P1a): a component-key helper declared before the default-exported meta is not the meta — a story mounting through it reaches', () => {
  assert.deepEqual(
    t685Credits('zzHelpers.error()', T685_BUTTON_ROLE, {
      storyMeta: `${T685_COMPONENT_KEY_HELPER}\nconst meta = { component: Row }\nexport default meta`,
    }),
    T685_CREDITED,
  )
})

test('T685 predicate (P1b): a component-key helper declared after a `satisfies Meta<…>` meta is not the meta — a story mounting through it reaches', () => {
  assert.deepEqual(
    t685Credits('zzHelpers.error()', T685_BUTTON_ROLE, {
      storyMeta: 'const meta = { component: Row } satisfies Meta<typeof Row>',
      storyHelpers: T685_COMPONENT_KEY_HELPER,
    }),
    T685_CREDITED,
  )
})

test('T685 predicate: a component-key object default-exported under another name is not the meta — a story mounting through it reaches', () => {
  assert.deepEqual(
    t685Credits('zzOther.error()', T685_BUTTON_ROLE, {
      storyMeta:
        'const zzOther = { component: Row, error: () => <Row /> }\nconst other = {}\nexport default other',
    }),
    T685_CREDITED,
  )
})

test('T685 predicate (P1c control): a helper without a component key reaches (already credited, stays so)', () => {
  assert.deepEqual(
    t685Credits('zzHelpers.error()', T685_BUTTON_ROLE, {
      storyHelpers: 'const zzHelpers = { error: () => <Row /> }',
    }),
    T685_CREDITED,
  )
})

test('T685 predicate: reading the real meta (`meta.title`) stays closed after the findMeta rule is gone', () => {
  assert.deepEqual(
    t685Credits('<button type="button" title={meta.title}>Raw</button>', T685_BUTTON_ROLE),
    [],
  )
})

test('T685 predicate: a name that only labels a member does not reach — a destructuring property name, a class property, method and accessors', () => {
  const rawWith = (renderHead, storyHelpers = '') =>
    t685Credits('<button type="button">Raw</button>', T685_BUTTON_ROLE, {
      renderHead,
      storyHelpers,
    })
  assert.deepEqual(rawWith('({ Row: R })'), [], 'a binding element property name')
  const members = {
    property: 'class ZzK { Row = 1 }',
    method: 'class ZzK { Row() { return 1 } }',
    getter: 'class ZzK { get Row() { return 1 } }',
    setter: 'class ZzK { set Row(v) {} }',
  }
  for (const [kind, storyHelpers] of Object.entries(members)) {
    assert.deepEqual(
      t685Credits('<button type="button" data-x={new ZzK()}>Raw</button>', T685_BUTTON_ROLE, {
        storyHelpers,
      }),
      [],
      kind,
    )
  }
})

test('T685 predicate: an intrinsic tag is a DOM element even when a story-file binding shares its name', () => {
  assert.deepEqual(
    t685Credits('<button type="button">Raw</button>', T685_BUTTON_ROLE, {
      storyHelpers: 'const button = () => <Row />',
    }),
    [],
  )
})

test('T685 predicate: a string that spells the component name does not reach it (pin, unchanged)', () => {
  assert.deepEqual(
    t685Credits('<button type="button" aria-label="Row">Raw</button>', T685_BUTTON_ROLE),
    [],
  )
})

test('T685 predicate contrast: a value reference still reaches — the tag with spread args, a function helper, a helper object holding a render function (arrow and method), a wrapped component, a JSX constant', () => {
  const credited = ['Button|primary|lg|hover']
  const cases = [
    ['<Row {...args} />', { renderHead: '(args)' }],
    ['<Demo />', { storyHelpers: 'const Demo = () => <Row />' }],
    ['tpl.render()', { storyHelpers: 'const tpl = { render: () => <Row /> }' }],
    ['tpl.render()', { storyHelpers: 'const tpl = { render() { return <Row /> } }' }],
    ['<Demo />', { storyHelpers: 'const Demo = memo(() => <Row />)' }],
    ['<>{row}</>', { storyHelpers: 'const row = <Row />' }],
  ]
  for (const [jsx, options] of cases) {
    assert.deepEqual(
      t685Credits(jsx, T685_BUTTON_ROLE, options),
      credited,
      `${jsx} ${options.storyHelpers ?? ''}`,
    )
  }
})

// The predicate's safe error is `true`, so a declaration reaches if ANY value reference in its
// initializer does, of whatever shape. Each plant below mounts `Row` (which composes
// `Button primary|lg`) through one shape and must be credited exactly as the direct tag is. The first
// nine were wrongly false after the first remediation (it admitted only functions, JSX constants,
// `memo(...)` of an inline function and an object's function members); a class declared in the story
// file and `render: (args, { component: C })` were false before it too.
const T685_SHAPES = {
  'shorthand member': [
    'zzHelpers.zzRow()',
    { storyHelpers: 'function zzRow() { return <Row /> }\nconst zzHelpers = { zzRow }' },
  ],
  'member whose value is an identifier': [
    'zzHelpers.row()',
    { storyHelpers: 'function zzRow() { return <Row /> }\nconst zzHelpers = { row: zzRow }' },
  ],
  'nested object': [
    'zzHelpers.rows.error()',
    { storyHelpers: 'const zzHelpers = { rows: { error: () => <Row /> } }' },
  ],
  'memo of an identifier': [
    '<ZzMemo />',
    { storyHelpers: 'function ZzInner() { return <Row /> }\nconst ZzMemo = memo(ZzInner)' },
  ],
  'alias of the component': ['<ZzAlias />', { storyHelpers: 'const ZzAlias = Row' }],
  'array of elements': ['<>{zzRows}</>', { storyHelpers: 'const zzRows = [<Row />]' }],
  conditional: [
    '<ZzPick />',
    { storyHelpers: 'const zzFlag = true\nconst ZzPick = zzFlag ? Row : Row' },
  ],
  'bound template (callee)': [
    '<ZzBound />',
    { storyHelpers: 'const ZzTpl = () => <Row />\nconst ZzBound = ZzTpl.bind({})' },
  ],
  'meta.component': [
    '(() => { const C = meta.component!; return <C {...args} /> })()',
    { renderHead: '(args)' },
  ],
  'class declared in the story file': [
    '<ZzWrap />',
    { storyHelpers: 'class ZzWrap extends Component { render() { return <Row /> } }' },
  ],
  'class extending the component': ['<ZzSub />', { storyHelpers: 'class ZzSub extends Row {}' }],
  'destructured render context': ['<C {...args} />', { renderHead: '(args, { component: C })' }],
  'render context read off a parameter': [
    '(() => { const C = ctx.component; return <C {...args} /> })()',
    { renderHead: '(args, ctx)' },
  ],
}
for (const [shape, [jsx, options]] of Object.entries(T685_SHAPES)) {
  test(`T685 predicate shape: ${shape} reaches the component, so the story is credited as a direct mount is`, () => {
    assert.deepEqual(t685Credits(jsx, T685_BUTTON_ROLE, options), ['Button|primary|lg|hover'])
  })
}

test('T685 predicate shapes: the same shapes holding only a raw element still reach nothing', () => {
  const rawShapes = [
    [
      'zzHelpers.zzRow()',
      'function zzRow() { return <button type="button">Raw</button> }\nconst zzHelpers = { zzRow }',
    ],
    [
      '<ZzBound />',
      'const ZzTpl = () => <button type="button">Raw</button>\nconst ZzBound = ZzTpl.bind({})',
    ],
    [
      '<ZzWrap />',
      'class ZzWrap extends Component { render() { return <button type="button">Raw</button> } }',
    ],
    ['<>{zzRows}</>', 'const zzRows = [<button type="button">Raw</button>]'],
  ]
  for (const [jsx, storyHelpers] of rawShapes) {
    assert.deepEqual(t685Credits(jsx, T685_BUTTON_ROLE, { storyHelpers }), [], jsx)
  }
})

// The `Disabled` cell of a non-axis primitive's element matrix credits every story whose `args`
// admit `disabled: true`. A story that mounts only a raw element shows none of the primitive's
// elements, so its `args` do not render one disabled.
test('T685 element matrix, Disabled cell: a raw-render story with args disabled: true credits no element; an args-only story and a render mounting the component do', () => {
  const index = `export function Switch({ disabled }) {
    return <input type="checkbox" disabled={disabled} className="hover:bg-surface-sunken" />
  }`
  const disabledCell = (storyBody) =>
    computeStateCoverage({
      componentDirs: [{ segment: 'primitives', name: 'Switch' }],
      filesByPath: new Map([
        [path.join(REPO_SRC_DIR, 'primitives/Switch/index.tsx'), index],
        [
          path.join(REPO_SRC_DIR, 'primitives/Switch/Switch.stories.tsx'),
          `import { Switch } from './index'\nconst meta = { component: Switch }\nexport default meta\n${storyBody}`,
        ],
      ]),
    }).matrices.Switch[0].disabled
  assert.deepEqual(
    disabledCell(
      `export const Planted = { render: () => <div>Raw</div>, args: { disabled: true } }`,
    ),
    ['none'],
  )
  assert.deepEqual(disabledCell(`export const Planted = { args: { disabled: true } }`), ['Planted'])
  assert.deepEqual(
    disabledCell(
      `export const Planted = { render: (args) => <Switch {...args} />, args: { disabled: true } }`,
    ),
    ['Planted'],
  )
})

// The check's own unaccounted-force-state report. A forced story that reaches nothing of its
// component credits nothing; the report must name it, or a wrongly-false predicate would make a
// credit vanish with no failure anywhere. Its entry carries `reachedNothing`, which is what lets the
// failure line say the predicate's verdict is the cause and not the resolver's.
test('T685 report: a forced story whose render reaches nothing of the component is reported as unaccounted with reachedNothing, and a story that reaches it and is credited is not', () => {
  const planted = t685Computed('<button type="button">Raw</button>', "role: 'slider'")
  assert.deepEqual(planted.unaccountedForceStates.missing, [
    { componentKey: 'composites/Row', exportName: 'Planted', state: 'hover', reachedNothing: true },
  ])
  const contrast = t685Computed('<Row />', "role: 'button', name: 'Retry'")
  assert.deepEqual(contrast.unaccountedForceStates.missing, [])
  const wrapper = t685Computed('<Demo />', "role: 'button'", {
    storyHelpers: 'function Demo() {\n  return <Row />\n}',
  })
  assert.deepEqual(wrapper.unaccountedForceStates.missing, [])
})

test('T685 report: a story that reaches the component and is still credited nowhere is reported without reachedNothing', () => {
  const reaching = t685Computed('<Row />', "role: 'slider'")
  assert.deepEqual(reaching.unaccountedForceStates.missing, [
    { componentKey: 'composites/Row', exportName: 'Planted', state: 'hover' },
  ])
})

test('T685 report: findUnaccountedForceStates skips a render-less-of-the-component story only while it still reaches the module (wrapper), never when it reaches nothing', () => {
  const entry = (extra) => ({
    exportName: 'Planted',
    storyFile: 'Row.stories.tsx',
    forced: { state: 'hover', role: 'button' },
    rendersComponent: false,
    ...extra,
  })
  const region = regionFixture({})
  const run = (e) => findUnaccountedForceStates(new Map([['composites/Row', [e]]]), region).missing
  assert.deepEqual(run(entry({ reachesComponentModule: true })), [])
  assert.deepEqual(run(entry({})), [], 'a fixture predating the flag keeps its old meaning')
  assert.deepEqual(run(entry({ reachesComponentModule: false })), [
    { componentKey: 'composites/Row', exportName: 'Planted', state: 'hover', reachedNothing: true },
  ])
})

test('T685 report message: a story reported because its render reaches nothing says the predicate found no value reference, and that a mounted component means the predicate missed a shape', () => {
  const message = describeMissingForceState({
    componentKey: 'composites/Row',
    exportName: 'Planted',
    state: 'hover',
    reachedNothing: true,
  })
  assert.match(message, /composites\/Row's own Planted forces "hover"/)
  assert.match(message, /reach predicate \(storyReachesComponentModule\) found no value reference/)
  assert.match(message, /render: to composites\/Row's module/)
  assert.match(message, /If the story does mount the component, the predicate missed that shape/)
  assert.doesNotMatch(message, /lost frame/)
})

test('T685 report message: a story that reaches the component and is credited nowhere keeps the lost-frame message', () => {
  const message = describeMissingForceState({
    componentKey: 'composites/Row',
    exportName: 'Planted',
    state: 'hover',
  })
  assert.equal(
    message,
    `composites/Row's own Planted forces "hover" but is credited on no cell and named in no unresolved reason anywhere in the region — a lost frame.`,
  )
})

test('T685 report message: the message follows the computed entry end to end, for both causes', () => {
  const entryOf = (computed) => computed.unaccountedForceStates.missing[0]
  assert.match(
    describeMissingForceState(
      entryOf(t685Computed('<button type="button">Raw</button>', "role: 'slider'")),
    ),
    /the predicate missed that shape/,
  )
  assert.match(
    describeMissingForceState(entryOf(t685Computed('<Row />', "role: 'slider'"))),
    /a lost frame/,
  )
})

// The wiring from the report to the failure line, end to end: the script itself, run on a copy of
// the real tree with one forced story appended, must exit 1 and print the message for its cause.
// A copy, because the script reads a fixed `packages/design-system/src` beside itself; symlinks only
// for `node_modules`.
function runCheckOnPlantedTree(
  storyAppendix,
  storyFileSegments = ['composites', 'MatchRow', 'MatchRow.stories.tsx'],
) {
  const checksDir = path.dirname(fileURLToPath(import.meta.url))
  const repoRoot = path.resolve(checksDir, '..', '..')
  const dsDir = path.join(repoRoot, 'packages', 'design-system')
  // The script runs `main` only when its own url is its argv[1]: the real path, not a symlinked tmpdir.
  const tmp = realpathSync(mkdtempSync(path.join(tmpdir(), 'state-coverage-planted-')))
  try {
    mkdirSync(path.join(tmp, 'scripts', 'checks'), { recursive: true })
    for (const f of readdirSync(checksDir).filter(
      (n) => n.endsWith('.mjs') && !n.endsWith('.test.mjs'),
    )) {
      cpSync(path.join(checksDir, f), path.join(tmp, 'scripts', 'checks', f))
    }
    mkdirSync(path.join(tmp, 'packages', 'design-system'), { recursive: true })
    for (const rel of ['src', 'specs', 'package.json']) {
      cpSync(path.join(dsDir, rel), path.join(tmp, 'packages', 'design-system', rel), {
        recursive: true,
      })
    }
    cpSync(path.join(repoRoot, '.prettierrc.json'), path.join(tmp, '.prettierrc.json'))
    symlinkSync(path.join(repoRoot, 'node_modules'), path.join(tmp, 'node_modules'))
    symlinkSync(
      path.join(dsDir, 'node_modules'),
      path.join(tmp, 'packages', 'design-system', 'node_modules'),
    )
    appendFileSync(
      path.join(tmp, 'packages', 'design-system', 'src', ...storyFileSegments),
      storyAppendix,
    )
    return spawnSync(
      process.execPath,
      [path.join(tmp, 'scripts', 'checks', 'state-coverage.mjs')],
      {
        encoding: 'utf8',
        timeout: 120000,
      },
    )
  } finally {
    rmSync(tmp, { recursive: true, force: true })
  }
}

test('T685 report, end to end: the check fails with the predicate message for a forced story whose render reaches nothing, and with the lost-frame message for one that reaches the component', () => {
  const forced = "parameters: { visualForceState: { state: 'hover', role: 'slider' } }"
  const reachesNothing = runCheckOnPlantedTree(
    `\nexport const ZzPlanted: Story = { render: () => <button type="button">Raw</button>, ${forced} }\n`,
  )
  assert.equal(reachesNothing.status, 1)
  assert.match(
    reachesNothing.stderr,
    /composites\/MatchRow's own ZzPlanted forces "hover" and is credited on no cell: the reach predicate \(storyReachesComponentModule\) found no value reference/,
  )
  assert.doesNotMatch(reachesNothing.stderr, /lost frame/)
  const reaches = runCheckOnPlantedTree(
    `\nexport const ZzPlanted: Story = { render: (args) => <MatchRow {...args} />, ${forced} }\n`,
  )
  assert.equal(reaches.status, 1)
  assert.match(
    reaches.stderr,
    /composites\/MatchRow's own ZzPlanted forces "hover" but is credited on no cell and named in no unresolved reason anywhere in the region — a lost frame\./,
  )
  assert.doesNotMatch(reaches.stderr, /reach predicate/)
})

// Finding of the second review: the helper skipped non-axis primitives' matrices, and `disabled`
// lives only there. These two tests read the `Disabled` cell THROUGH `plantedCredits`, so removing
// the `argsHasDisabledTrue && reachesComponentModule !== false` gate of `buildElementMatrix` fails
// here and not only in the test that reads `matrices.Switch[0].disabled` directly.
function switchPlantedCredits(storyBody) {
  return plantedCredits(
    computeStateCoverage({
      componentDirs: [{ segment: 'primitives', name: 'Switch' }],
      filesByPath: new Map([
        [
          path.join(REPO_SRC_DIR, 'primitives/Switch/index.tsx'),
          `export function Switch({ disabled }) {
            return <input type="checkbox" disabled={disabled} className="hover:bg-surface-sunken" />
          }`,
        ],
        [
          path.join(REPO_SRC_DIR, 'primitives/Switch/Switch.stories.tsx'),
          `import { Switch } from './index'\nconst meta = { component: Switch }\nexport default meta\n${storyBody}`,
        ],
      ]),
    }),
  )
}

test('T685 helper: plantedCredits reads a non-axis primitive’s Disabled cell, so an args-only Switch story with disabled: true is a credit', () => {
  assert.deepEqual(switchPlantedCredits(`export const Planted = { args: { disabled: true } }`), [
    `Switch|input[role=checkbox] @ packages/design-system/src/primitives/Switch/index.tsx:2|disabled`,
  ])
})

test('T685 helper: a raw-render Switch story with disabled: true credits no Disabled cell, read through plantedCredits', () => {
  assert.deepEqual(
    switchPlantedCredits(
      `export const Planted = { render: () => <div>Raw</div>, args: { disabled: true } }`,
    ),
    [],
  )
})

// --- T686 (row 8, H5): an own story's credit is checked against what the primitive renders --------
//
// Level: the own-story axis-matrix path of the primitive pool (`computeStateCoverage`'s own-story
// branch → `buildAxisMatrix`), not record 1 and not the composed-story paths. Two defects, one
// shape — a primitive's own story was credited to its axis matrix without verifying it depicts the
// primitive: (1) a forced role/selector the primitive never renders, (2) a `render:` that never
// mounts the primitive, which fell back to the story's `args`.
function menuAxisComputed(storyBody, indexSource = MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE) {
  return computeStateCoverage({
    componentDirs: [{ segment: 'primitives', name: 'Menu' }],
    filesByPath: new Map([
      [path.join(REPO_SRC_DIR, 'primitives/Menu/index.tsx'), indexSource],
      [
        path.join(REPO_SRC_DIR, 'primitives/Menu/Menu.stories.tsx'),
        `import { Menu } from './index'\nconst meta = { component: Menu }\nexport default meta\n${storyBody}`,
      ],
    ]),
  })
}
const menuAxisCredits = (storyBody) =>
  plantedCredits(menuAxisComputed(storyBody)).filter((c) => c.startsWith('Menu|'))
const menuAxisReport = (storyBody) => menuAxisComputed(storyBody).unaccountedForceStates.missing
const T686_FORCE = (state, target) =>
  `parameters: { visualForceState: { state: '${state}', ${target} } }`
const T686_SELECTION_ARGS = `args: { variant: 'selection', items: [{ id: 'p2', label: 'aoe2alt' }] }`
const T686_MENU_RENDER = `render: (args) => <Menu {...args} />`

test('T686 (a): a story forcing a role Menu never renders credits no cell, whatever the state, and is reported', () => {
  for (const state of ['hover', 'focus-visible', 'active']) {
    const body = `export const Planted = {
      ${T686_MENU_RENDER},
      ${T686_SELECTION_ARGS},
      ${T686_FORCE(state, "role: 'slider'")},
    }`
    assert.deepEqual(menuAxisCredits(body), [], state)
    const matrixRows = menuAxisComputed(body).matrices.Menu
    assert.doesNotMatch(JSON.stringify(matrixRows), /Planted/, state)
    assert.equal(
      matrixRows.some((r) => r.variantSize === '(no axis)'),
      false,
      `${state}: no (no axis) row is opened for a story that credits nothing`,
    )
    const missing = menuAxisReport(body)
    assert.deepEqual(
      missing.map((m) => [m.componentKey, m.exportName, m.state]),
      [['primitives/Menu', 'Planted', state]],
      state,
    )
    assert.match(describeMissingForceState(missing[0]), /slider/, 'the report names the role')
    assert.match(describeMissingForceState(missing[0]), /renders no element/)
  }
})

test('T686 (a): a name or nth beside the unrendered role changes nothing, and a role-only force on it is refused the same way', () => {
  for (const target of [
    "role: 'slider', name: 'aoe2alt'",
    "role: 'slider', nth: 0",
    "role: 'slider'",
  ]) {
    const body = `export const Planted = {
      ${T686_MENU_RENDER},
      ${T686_SELECTION_ARGS},
      ${T686_FORCE('hover', target)},
    }`
    assert.deepEqual(menuAxisCredits(body), [], target)
    assert.equal(menuAxisReport(body).length, 1, target)
  }
})

test('T686 (a): a selector no element of Menu matches credits no cell, and one that does is still credited', () => {
  // An args-only story, so the credit lands on a real cell of the matrix (`selection`), not on the
  // `(no axis)` row a `{...args}` spread opens for a primitive with no `variant` default.
  const selectorStory = (selector) => `export const Planted = {
      ${T686_SELECTION_ARGS},
      ${T686_FORCE('hover', `selector: '${selector}'`)},
    }`
  assert.deepEqual(menuAxisCredits(selectorStory('a[href="/x"]')), [])
  assert.equal(menuAxisReport(selectorStory('a[href="/x"]')).length, 1)
  assert.deepEqual(menuAxisCredits(selectorStory('button[type="button"]')), [
    'Menu|selection|hover',
  ])
  assert.deepEqual(menuAxisReport(selectorStory('button[type="button"]')), [])
})

test('T686 (a): a force naming neither a role nor a selector resolves against nothing, so it credits no cell and is reported', () => {
  const body = `export const Planted = {
    ${T686_MENU_RENDER},
    ${T686_SELECTION_ARGS},
    ${T686_FORCE('hover', "name: 'aoe2alt'")},
  }`
  assert.deepEqual(menuAxisCredits(body), [])
  assert.equal(menuAxisReport(body).length, 1)
})

test('T686 (a) contrast: a story forcing a role Menu renders is credited at the same cell as before, for every state and for the trigger, the static and the dynamic role', () => {
  // Args-only stories: each credit lands on the real row its `variant` names.
  const credit = (state, target, args = T686_SELECTION_ARGS) =>
    menuAxisCredits(`export const Planted = {
      ${args},
      ${T686_FORCE(state, target)},
    }`)
  assert.deepEqual(credit('hover', "role: 'menuitemradio', name: 'aoe2alt'"), [
    'Menu|selection|hover',
  ])
  assert.deepEqual(credit('focus-visible', "role: 'menuitemradio', name: 'aoe2alt'"), [
    'Menu|selection|focusVisible',
  ])
  assert.deepEqual(credit('active', "role: 'menuitemradio'"), ['Menu|selection|active'])
  assert.deepEqual(credit('hover', "role: 'button'"), ['Menu|selection|hover'])
  assert.deepEqual(
    credit(
      'hover',
      "role: 'menuitem'",
      `args: { variant: 'actions', items: [{ id: 'a', label: 'Open' }] }`,
    ),
    ['Menu|actions|hover'],
  )
  assert.deepEqual(
    menuAxisReport(`export const Planted = {
      ${T686_SELECTION_ARGS},
      ${T686_FORCE('hover', "role: 'menuitemradio', name: 'aoe2alt'")},
    }`),
    [],
  )
})

test('T686 (a): a dynamic role is checked per story — a force on menuitemradio from a story whose args render menuitem credits nothing', () => {
  const body = `export const Planted = {
    ${T686_MENU_RENDER},
    args: { variant: 'actions', items: [{ id: 'a', label: 'aoe2alt' }] },
    ${T686_FORCE('hover', "role: 'menuitemradio', name: 'aoe2alt'")},
  }`
  assert.deepEqual(menuAxisCredits(body), [])
  assert.equal(menuAxisReport(body).length, 1)
})

test('T686 (a): when the role cannot be told — a dynamic role no story data settles — the credit is refused, never kept (the safe error direction)', () => {
  const body = `export const Planted = {
    ${T686_MENU_RENDER},
    args: { items: [{ id: 'a', label: 'aoe2alt' }] },
    ${T686_FORCE('hover', "role: 'menuitemradio', name: 'aoe2alt'")},
  }`
  const index = MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE.replace(
    "variant === 'selection' ? 'menuitemradio' : 'menuitem'",
    'pickRole(item)',
  ).replace('<button type="button" className="hover:bg-surface-sunken">Trigger</button>', '')
  const computed = menuAxisComputed(body, index)
  assert.deepEqual(
    plantedCredits(computed).filter((c) => c.startsWith('Menu|')),
    [],
  )
  assert.match(describeMissingForceState(computed.unaccountedForceStates.missing[0]), /cannot tell/)
})

test('T686 (a), play-focus half: a play() focusing a role Menu never renders adds no focus-visible note, while one focusing a rendered role keeps its note', () => {
  const play = (role) => `play: async ({ canvasElement }) => {
      const item = within(canvasElement).getByRole('${role}')
      item.focus()
      await expect(item).toHaveFocus()
    }`
  const focusText = (role) =>
    JSON.stringify(
      menuAxisComputed(`export const Planted = {
        ${T686_MENU_RENDER},
        ${T686_SELECTION_ARGS},
        ${play(role)},
      }`).matrices.Menu,
    )
  assert.doesNotMatch(focusText('slider'), /play-driven/)
  assert.match(
    focusText('menuitemradio'),
    /Menu:Planted \(play-driven; frame not provable statically\)/,
  )
})

test('T686 (c): a story whose render is only a raw <div role="menuitemradio"> credits no cell of Menu’s axis matrix, forced or not, and a forced one is reported as reaching nothing', () => {
  const raw = (extra) => `export const Planted = {
    render: () => <div role="menuitemradio" tabIndex={0}>aoe2alt</div>,
    ${T686_SELECTION_ARGS},
    ${extra}
  }`
  const forced = raw(`${T686_FORCE('hover', "role: 'menuitemradio', name: 'aoe2alt'")},`)
  assert.deepEqual(menuAxisCredits(forced), [])
  assert.doesNotMatch(JSON.stringify(menuAxisComputed(forced).matrices.Menu), /Planted/)
  const missing = menuAxisReport(forced)
  assert.equal(missing.length, 1)
  assert.equal(missing[0].reachedNothing, true)
  assert.deepEqual(menuAxisCredits(raw('')), [])
  assert.deepEqual(
    menuAxisCredits(raw(`args: { variant: 'selection', items: [], disabled: true },`)),
    [],
  )
})

test('T686 (a): a forced story mounting Menu only through a story-file wrapper, on a role Menu never renders, is reported though its render holds no <Menu> tag', () => {
  const body = `function Demo(props) { return <Menu {...props} /> }
  export const Planted = {
    render: (args) => <Demo {...args} />,
    ${T686_SELECTION_ARGS},
    ${T686_FORCE('hover', "role: 'slider'")},
  }`
  assert.deepEqual(menuAxisCredits(body), [])
  const missing = menuAxisReport(body)
  assert.equal(missing.length, 1)
  assert.match(describeMissingForceState(missing[0]), /renders no element of role "slider"/)
})

test('T686 (d) contrast: a story whose render mounts <Menu>, an args-only story, and a render mounting through a story-file wrapper that hands its props to <Menu> are all still credited at the same cell', () => {
  const force = T686_FORCE('hover', "role: 'menuitemradio', name: 'aoe2alt'")
  assert.deepEqual(
    menuAxisCredits(`export const Planted = {
      render: () => <Menu variant="selection" items={[{ id: 'p2', label: 'aoe2alt' }]} />,
      ${force},
    }`),
    ['Menu|selection|hover'],
  )
  assert.deepEqual(menuAxisCredits(`export const Planted = { ${T686_SELECTION_ARGS}, ${force} }`), [
    'Menu|selection|hover',
  ])
  assert.deepEqual(
    menuAxisCredits(`function Demo(props) { return <Menu {...props} /> }
    export const Planted = { render: (args) => <Demo {...args} />, ${T686_SELECTION_ARGS}, ${force} }`),
    ['Menu|selection|hover'],
  )
})

// `Field` renders the control its caller passes; its own source holds no input element. What a
// story forcing `textbox` depicts is therefore the control its own render supplies.
const FIELD_CLONING_INDEX_SOURCE = `
export function Field({ label, size = 'md', children }) {
  const control = cloneElement(children, { id: 'x' })
  return (
    <div>
      <label>{label}</label>
      {control}
    </div>
  )
}
`
function fieldAxisCredits(storyBody) {
  return plantedCredits(
    computeStateCoverage({
      componentDirs: [{ segment: 'primitives', name: 'Field' }],
      filesByPath: new Map([
        [path.join(REPO_SRC_DIR, 'primitives/Field/index.tsx'), FIELD_CLONING_INDEX_SOURCE],
        [
          path.join(REPO_SRC_DIR, 'primitives/Field/Field.stories.tsx'),
          `import { Field } from './index'\nimport { Foreign } from '../Elsewhere'\nconst meta = { component: Field }\nexport default meta\n${storyBody}`,
        ],
      ]),
    }),
  ).filter((c) => c.startsWith('Field|'))
}
const FIELD_FORCE = T686_FORCE('hover', "role: 'textbox'")

test('T686 (a), a primitive that renders its caller’s control: the control the story’s own render supplies decides the role', () => {
  const story = (child) => `export const Planted = {
    render: () => <Field label="Name">${child}</Field>,
    ${FIELD_FORCE},
  }`
  assert.deepEqual(fieldAxisCredits(story('<input />')), ['Field|md|hover'])
  assert.deepEqual(
    fieldAxisCredits(
      `function DemoInput() { return <input className="x" /> }\n${story('<DemoInput />')}`,
    ),
    ['Field|md|hover'],
  )
  assert.deepEqual(fieldAxisCredits(story('<div />')), [])
  assert.deepEqual(fieldAxisCredits(story('<Foreign />')), [], 'an imported control cannot be told')
})

test('T686 report, end to end: the real tree with a slider story appended to Menu’s own story file fails the check, names the role, and credits no cell', () => {
  const planted = `
export const ZzPlanted: Story = {
  render: (args) => <Menu {...args} />,
  args: { variant: 'selection', items: [{ id: 'p2', label: 'aoe2alt' }] },
  parameters: { visualForceState: { state: 'focus-visible', role: 'slider' } },
}
`
  const result = runCheckOnPlantedTree(planted, ['primitives', 'Menu', 'Menu.stories.tsx'])
  assert.equal(result.status, 1, result.stdout + result.stderr)
  assert.match(
    result.stderr,
    /primitives\/Menu's own ZzPlanted forces "focus-visible" and is credited on no cell: .*"slider"/,
  )
})

// --- T686 remediation (review of #112): one verdict per own story, shared by every record --------
//
// Three defects, one shape. (1) The `args` fallback credited a story whose `render:` merely REACHES
// the primitive's module (a wrapper that mounts a different `<Menu>`, a render context's `component`
// that is never mounted): reach is a reporting predicate, never a credit gate. (2) The verdict
// reached for the axis matrix was not the verdict record 1 read, so a refused own story was still
// credited on an element of the primitive's own record. (3) A selector resolved by tag alone.
const T686R_BUTTON_INDEX_SOURCE = `
export function Button({ variant = 'primary', size = 'md', href, disabled, children }) {
  if (href !== undefined) {
    return <a href={href} className="hover:bg-surface-sunken focus-visible:outline-2">{children}</a>
  }
  return (
    <button type="button" disabled={disabled} className="hover:bg-surface-sunken focus-visible:outline-2">
      {children}
    </button>
  )
}
`
function t686rComputed(name, indexSource, storyBody) {
  return computeStateCoverage({
    componentDirs: [{ segment: 'primitives', name }],
    filesByPath: new Map([
      [path.join(REPO_SRC_DIR, `primitives/${name}/index.tsx`), indexSource],
      [
        path.join(REPO_SRC_DIR, `primitives/${name}/${name}.stories.tsx`),
        `import { ${name} } from './index'\nconst meta = { component: ${name} }\nexport default meta\n${storyBody}`,
      ],
    ]),
  })
}
const t686rMenu = (storyBody) =>
  t686rComputed('Menu', MENU_WITH_DYNAMIC_ROW_INDEX_SOURCE, storyBody)
const t686rButton = (storyBody) => t686rComputed('Button', T686R_BUTTON_INDEX_SOURCE, storyBody)
const t686rReport = (computed) =>
  computed.unaccountedForceStates.missing.filter((m) => m.exportName === 'Planted')
const T686R_ITEM = `{ id: 'p2', label: 'aoe2alt' }`
const T686R_RADIO_FORCE = T686_FORCE('hover', "role: 'menuitemradio', name: 'aoe2alt'")

// HIGH 1 -------------------------------------------------------------------------------------------

test('T686r HIGH 1: a render that reaches Menu through a wrapper mounting ANOTHER Menu, with the forced role in a raw child, credits no cell of any record and is reported', () => {
  const body = `function Frame({ children }) {
    return <div><Menu variant="actions" triggerLabel="x" items={[]} />{children}</div>
  }
  export const Planted = {
    render: () => <Frame><div role="menuitemradio" tabIndex={0}>aoe2alt</div></Frame>,
    args: { variant: 'selection', items: [${T686R_ITEM}] },
    ${T686R_RADIO_FORCE},
  }`
  const computed = t686rMenu(body)
  assert.deepEqual(plantedCredits(computed), [])
  const missing = t686rReport(computed)
  assert.equal(missing.length, 1)
  assert.match(describeMissingForceState(missing[0]), /credited on no cell/)
})

test('T686r HIGH 1: a render that reads the render context’s component but mounts a raw element credits no cell of any record and is reported', () => {
  const body = `export const Planted = {
    render: (_args, { component: C }) => <div role="menuitemradio" tabIndex={0} data-c={String(C)}>aoe2alt</div>,
    args: { variant: 'selection', items: [${T686R_ITEM}] },
    ${T686R_RADIO_FORCE},
  }`
  const computed = t686rMenu(body)
  assert.deepEqual(plantedCredits(computed), [])
  assert.equal(t686rReport(computed).length, 1)
})

test('T686r HIGH 1: the same two renders UNFORCED, with a nested disabled item, credit no Rest or Disabled cell either, in any record', () => {
  const wrapper = `function Frame({ children }) {
    return <div><Menu variant="actions" items={[]} />{children}</div>
  }
  export const Planted = {
    render: () => <Frame><div role="menuitemradio">aoe2alt</div></Frame>,
    args: { variant: 'selection', items: [{ id: 'p2', label: 'aoe2alt', disabled: true }] },
  }`
  const raw = `export const Planted = {
    render: (_args, { component: C }) => <div data-c={String(C)} />,
    args: { variant: 'selection', items: [{ id: 'p2', label: 'aoe2alt', disabled: true }] },
  }`
  // The wrapper does mount a Menu — of variant "actions", literally — so it may be credited at
  // THAT row (what it shows), never at the row its args name.
  const credits = plantedCredits(t686rMenu(wrapper))
  assert.deepEqual(
    credits.filter((c) => c.startsWith('Menu|selection')),
    [],
    'nothing is credited on the args-named row',
  )
  assert.deepEqual(plantedCredits(t686rMenu(raw)), [])
})

test('T686r HIGH 1 contrast: a render context component used AS A JSX TAG is a mount, credited at the row its props name', () => {
  assert.deepEqual(
    plantedCredits(
      t686rMenu(`export const Planted = {
        render: (args, { component: C }) => <C {...args} />,
        args: { variant: 'selection', items: [${T686R_ITEM}] },
        ${T686R_RADIO_FORCE},
      }`),
    ).filter((c) => c.startsWith('Menu|')),
    ['Menu|selection|hover'],
  )
})

test('T686r HIGH 1 contrast: a wrapper whose own <Menu> tag fixes its axis is credited at THAT tag’s row, not the row the story args name', () => {
  const body = `function Frame() { return <Menu variant="selection" items={[${T686R_ITEM}]} /> }
  export const Planted = {
    render: () => <Frame />,
    args: { variant: 'actions', items: [] },
    ${T686R_RADIO_FORCE},
  }`
  assert.deepEqual(
    plantedCredits(t686rMenu(body)).filter((c) => c.startsWith('Menu|')),
    ['Menu|selection|hover'],
  )
})

test('T686r HIGH 1 contrast: a wrapper that forwards its props to <Menu> is credited at the row the story args name, and its call site’s literal prop wins over them', () => {
  const wrapper = `function Demo(props) { return <Menu {...props} /> }`
  assert.deepEqual(
    plantedCredits(
      t686rMenu(`${wrapper}
      export const Planted = {
        render: (args) => <Demo {...args} />,
        args: { variant: 'selection', items: [${T686R_ITEM}] },
        ${T686R_RADIO_FORCE},
      }`),
    ).filter((c) => c.startsWith('Menu|')),
    ['Menu|selection|hover'],
  )
  assert.deepEqual(
    plantedCredits(
      t686rMenu(`${wrapper}
      export const Planted = {
        render: (args) => <Demo {...args} variant="selection" />,
        args: { variant: 'actions', items: [${T686R_ITEM}] },
        ${T686R_RADIO_FORCE},
      }`),
    ).filter((c) => c.startsWith('Menu|')),
    ['Menu|selection|hover'],
  )
})

test('T686r HIGH 1: what the check cannot follow is refused and reported with a reason, never credited — a wrapper spreading something else, a non-literal axis, an imported wrapper, a render that is not a function', () => {
  const cases = {
    'a spread of something other than the wrapper’s props': `function Demo() { return <Menu {...pick()} /> }
      export const Planted = { render: () => <Demo />, args: { variant: 'selection', items: [${T686R_ITEM}] }, ${T686R_RADIO_FORCE} }`,
    'a non-literal axis': `function Demo({ v }) { return <Menu variant={v} items={[${T686R_ITEM}]} /> }
      export const Planted = { render: () => <Demo v="selection" />, args: {}, ${T686R_RADIO_FORCE} }`,
    'an imported wrapper': `export const Planted = { render: () => <Elsewhere />, args: { variant: 'selection', items: [${T686R_ITEM}] }, ${T686R_RADIO_FORCE} }`,
    'a render that is not a function': `const Tpl = (args) => <Menu {...args} />
      export const Planted = { render: Tpl.bind({}), args: { variant: 'selection', items: [${T686R_ITEM}] }, ${T686R_RADIO_FORCE} }`,
  }
  for (const [label, body] of Object.entries(cases)) {
    const computed = t686rMenu(`import { Elsewhere } from '../Elsewhere'\n${body}`)
    assert.deepEqual(plantedCredits(computed), [], label)
    const missing = t686rReport(computed)
    assert.equal(missing.length, 1, label)
    assert.match(describeMissingForceState(missing[0]), /credited on no cell: .+/, label)
  }
})

// HIGH 2 -------------------------------------------------------------------------------------------

test('T686r HIGH 2: an args-only Button story forcing a link with no href is refused by every record — no Button row and no element of Button’s own record is credited — and reported once', () => {
  const body = `export const Planted = {
    args: { variant: 'secondary', size: 'md' },
    ${T686_FORCE('hover', "role: 'link'")},
  }`
  const computed = t686rButton(body)
  assert.deepEqual(plantedCredits(computed), [])
  const missing = t686rReport(computed)
  assert.equal(missing.length, 1)
  assert.match(describeMissingForceState(missing[0]), /renders no element of role "link"/)
  // Contrast: with an href the `<a>` is rendered, and both records credit it.
  const withHref = t686rButton(`export const Planted = {
    args: { variant: 'secondary', size: 'md', href: '/x' },
    ${T686_FORCE('hover', "role: 'link'")},
  }`)
  assert.deepEqual(plantedCredits(withHref), [
    'Button|secondary|md|hover',
    'local:primitives/Button:a|hover',
  ])
  assert.deepEqual(t686rReport(withHref), [])
})

// One story, every record that credits an own story: the axis matrix, record 1's element cells (hover,
// focus-visible, active; the selector, dynamic-role and play-focus paths) and the Disabled column.
// A story refused by one is credited by none and reported exactly once; a story accepted by one is
// credited by every record that has a cell for it.
test('T686r HIGH 2, agreement: for every planted story, refused-by-one means credited-by-none and reported once; accepted means credited and not reported', () => {
  const FORCE_HOVER_RADIO = T686R_RADIO_FORCE
  const menuSel = `args: { variant: 'selection', items: [${T686R_ITEM}] }`
  const stories = [
    {
      label: 'Button forced link without href',
      compute: t686rButton,
      body: `args: { variant: 'secondary', size: 'md' }, ${T686_FORCE('hover', "role: 'link'")}`,
      refused: true,
    },
    {
      label: 'Button forced link with href',
      compute: t686rButton,
      body: `args: { variant: 'secondary', size: 'md', href: '/x' }, ${T686_FORCE('hover', "role: 'link'")}`,
      refused: false,
    },
    {
      label: 'Button forced focus-visible link without href',
      compute: t686rButton,
      body: `args: { size: 'md' }, ${T686_FORCE('focus-visible', "role: 'link'")}`,
      refused: true,
    },
    {
      label: 'Button forced selector a[href] without href',
      compute: t686rButton,
      body: `args: { size: 'md' }, ${T686_FORCE('hover', `selector: 'a[href="/x"]'`)}`,
      refused: true,
    },
    {
      label: 'Button forced selector a[href] with that href',
      compute: t686rButton,
      body: `args: { size: 'md', href: '/x' }, ${T686_FORCE('hover', `selector: 'a[href="/x"]'`)}`,
      refused: false,
    },
    {
      label: 'Menu forced slider',
      compute: t686rMenu,
      body: `${menuSel}, ${T686_FORCE('hover', "role: 'slider'")}`,
      refused: true,
    },
    {
      label: 'Menu forced radio from an args-only story',
      compute: t686rMenu,
      body: `${menuSel}, ${FORCE_HOVER_RADIO}`,
      refused: false,
    },
    {
      label: 'Menu raw render naming the radio through the context component only',
      compute: t686rMenu,
      body: `render: (_a, { component: C }) => <div role="menuitemradio">aoe2alt</div>, ${menuSel}, ${FORCE_HOVER_RADIO}`,
      refused: true,
    },
    {
      label: 'Menu dynamic role resolved to menuitem, force names menuitemradio',
      compute: t686rMenu,
      body: `args: { variant: 'actions', items: [${T686R_ITEM}] }, ${FORCE_HOVER_RADIO}`,
      refused: true,
    },
  ]
  const problems = []
  for (const { label, compute, body, refused } of stories) {
    const computed = compute(`export const Planted = { ${body} }`)
    const credits = plantedCredits(computed)
    const missing = t686rReport(computed)
    if (refused) {
      if (credits.length > 0) problems.push(`${label}: refused but credited by ${credits}`)
      if (missing.length !== 1) problems.push(`${label}: refused but reported ${missing.length}x`)
    } else {
      if (missing.length !== 0) problems.push(`${label}: accepted but reported`)
      if (!(
        credits.some((c) => c.startsWith('local:')) && credits.some((c) => !c.startsWith('local:'))
      )) {
        problems.push(`${label}: accepted but not credited by both records (${credits})`)
      }
    }
  }
  assert.deepEqual(problems, [])
})

// Record 1's cells of Button's own elements, as text (the element objects carry syntax nodes).
const record1Text = (computed) =>
  JSON.stringify(
    computed.localElements
      .find((l) => l.componentKey === 'primitives/Button')
      .elements.map((el) => el.coveredBy),
  )

const T686R_PLAY = `play: async ({ canvasElement }) => {
      const item = within(canvasElement).getByRole('link')
      item.focus()
      await expect(item).toHaveFocus()
    }`

test('T686r HIGH 2, sibling Disabled column: a render that never mounts the primitive adds no Disabled credit, a mounting one keeps it', () => {
  // The Disabled column of a tracked primitive lives in its axis matrix alone (record 1 prints no
  // such column for it), so that is the one place this sibling is read.
  const disabledStory = (render) => `export const Planted = {
    ${render}
    args: { variant: 'secondary', size: 'md', disabled: true },
  }`
  assert.ok(
    plantedCredits(
      t686rButton(
        disabledStory('render: () => <Button variant="secondary" size="md" disabled>Go</Button>,'),
      ),
    ).includes('Button|secondary|md|disabled'),
    'a mounting render keeps its Disabled credit',
  )
  assert.deepEqual(
    plantedCredits(
      t686rButton(disabledStory('render: (_a, { component: C }) => <div data-c={String(C)} />,')),
    ),
    [],
    'a render that never mounts Button credits no cell, in any record',
  )
})

test('T686r HIGH 2, sibling play-focus note: a play() focusing a link the story does not render adds no note in the axis matrix or in record 1', () => {
  const noHref = t686rButton(
    `export const Planted = { args: { variant: 'secondary', size: 'md' }, ${T686R_PLAY} }`,
  )
  assert.doesNotMatch(JSON.stringify(noHref.matrices.Button), /play-driven/)
  assert.doesNotMatch(
    record1Text(noHref),
    /play-driven/,
    'record 1 holds no play-focus note for a link the story does not render',
  )
})

test('T686r HIGH 2, sibling play-focus note, contrast: a play() focusing a link the story renders keeps its note in both records', () => {
  const withHref = t686rButton(
    `export const Planted = { args: { variant: 'secondary', size: 'md', href: '/x' }, ${T686R_PLAY} }`,
  )
  assert.match(JSON.stringify(withHref.matrices.Button), /play-driven/)
  assert.match(record1Text(withHref), /play-driven/)
})

// MEDIUM 4 -----------------------------------------------------------------------------------------

test('T686r MEDIUM 4: a selector whose tag matches but whose attribute does not credits no cell and is reported; the matching attribute is still credited', () => {
  const menu = (selector) => `export const Planted = {
    args: { variant: 'selection', items: [${T686R_ITEM}] },
    ${T686_FORCE('hover', `selector: '${selector}'`)},
  }`
  const wrongAttr = t686rMenu(menu('button[data-nothing="never"]'))
  assert.deepEqual(plantedCredits(wrongAttr), [])
  assert.equal(t686rReport(wrongAttr).length, 1)
  assert.match(describeMissingForceState(t686rReport(wrongAttr)[0]), /data-nothing/)
  const wrongValue = t686rMenu(menu('button[type="submit"]'))
  assert.deepEqual(plantedCredits(wrongValue), [])
  assert.equal(t686rReport(wrongValue).length, 1)
  const rightAttr = t686rMenu(menu('button[type="button"]'))
  assert.deepEqual(
    plantedCredits(rightAttr).filter((c) => c.startsWith('Menu|')),
    ['Menu|selection|hover'],
  )
  assert.deepEqual(t686rReport(rightAttr), [])
})

test('T686r MEDIUM 4: a selector whose attribute comes from the story’s own props is resolved against them — the right value is credited, the wrong one refused, an unresolvable one refused with a reason', () => {
  const button = (args, selector) => `export const Planted = {
    args: { size: 'md'${args} },
    ${T686_FORCE('hover', `selector: '${selector}'`)},
  }`
  const right = t686rButton(button(", href: '/x'", 'a[href="/x"]'))
  assert.deepEqual(
    plantedCredits(right).filter((c) => c.startsWith('Button|')),
    ['Button|primary|md|hover'],
  )
  assert.deepEqual(t686rReport(right), [])
  const wrong = t686rButton(button(", href: '/x'", 'a[href="/y"]'))
  assert.deepEqual(plantedCredits(wrong), [])
  assert.equal(t686rReport(wrong).length, 1)
  // The element carries no literal or story-resolvable `data-x`: ambiguous, so refused, not guessed.
  const ambiguous = t686rButton(button(", href: '/x'", 'a[data-x="1"]'))
  assert.deepEqual(plantedCredits(ambiguous), [])
  assert.equal(t686rReport(ambiguous).length, 1)
})

test('T686r report, end to end: the real tree with E1 (no href, forced link) appended to Button’s own story file and E3 (a wrapper mounting another Menu) appended to Menu’s fails the check once each and leaves the generated region unchanged', () => {
  const e1 = runCheckOnPlantedTree(
    `
export const ZzE1: Story = {
  args: { variant: 'secondary', size: 'md' },
  parameters: { visualForceState: { state: 'hover', role: 'link' } },
}
`,
    ['primitives', 'Button', 'Button.stories.tsx'],
  )
  assert.equal(e1.status, 1, e1.stdout + e1.stderr)
  assert.match(
    e1.stderr,
    /primitives\/Button's own ZzE1 forces "hover" and is credited on no cell: .*"link"/,
  )
  assert.doesNotMatch(
    e1.stderr,
    /disagrees with a fresh render/,
    'no cell moved, so the region is unchanged',
  )
  const e3 = runCheckOnPlantedTree(
    `
function ZzFrame({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <Menu variant="actions" triggerLabel="x" items={[]} />
      {children}
    </div>
  )
}
export const ZzE3: Story = {
  render: () => (
    <ZzFrame>
      <div role="menuitemradio" tabIndex={0}>aoe2alt</div>
    </ZzFrame>
  ),
  args: { variant: 'selection', triggerLabel: 'aoe2guy', items: [{ id: 'p2', label: 'aoe2alt' }] },
  parameters: { visualForceState: { state: 'hover', role: 'menuitemradio', name: 'aoe2alt' } },
}
`,
    ['primitives', 'Menu', 'Menu.stories.tsx'],
  )
  assert.equal(e3.status, 1, e3.stdout + e3.stderr)
  assert.match(e3.stderr, /primitives\/Menu's own ZzE3 forces "hover" and is credited on no cell: /)
  assert.doesNotMatch(e3.stderr, /disagrees with a fresh render/)
})

test('T686r: an UNFORCED own story the verdict refuses is listed in refusedOwnStories with its reason, a forced one is not (it fails the run instead), an accepted one is not', () => {
  const unforced = t686rMenu(`export const Planted = {
    render: (_a, { component: C }) => <div data-c={String(C)} />,
    args: { variant: 'selection', items: [] },
  }`)
  assert.deepEqual(
    unforced.refusedOwnStories.map((r) => [r.componentKey, r.exportName]),
    [['primitives/Menu', 'Planted']],
  )
  assert.match(unforced.refusedOwnStories[0].refusal, /mounts no <Menu>/)
  const forced = t686rMenu(`export const Planted = {
    render: (_a, { component: C }) => <div data-c={String(C)} />,
    args: { variant: 'selection', items: [] },
    ${T686_FORCE('hover', "role: 'button'")},
  }`)
  assert.deepEqual(forced.refusedOwnStories, [])
  assert.equal(t686rReport(forced).length, 1)
  assert.deepEqual(
    t686rMenu(`export const Planted = { args: { variant: 'selection', items: [] } }`)
      .refusedOwnStories,
    [],
  )
})
