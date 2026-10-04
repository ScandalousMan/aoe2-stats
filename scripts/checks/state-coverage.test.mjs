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
  buildAxisMatrix,
  buildElementMatrix,
  renderGeneratedRegion,
  extractGeneratedRegion,
  replaceGeneratedRegion,
  formatWithPrettier,
  findHelperInvocationIterationContext,
  renderRecord1,
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
  readManifest,
  resolveRuntimeForce,
  entryShapeProblem,
  readAxisValues,
  stableMounts,
  rowAxesOf,
  PRIMITIVE_AXES,
  REGION_LEGEND,
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
import { REWRITE_COMMAND } from '../visual/state-coverage-runtime-model.mjs'
import { REVIEW_WIDTHS } from '../visual/review-widths.mjs'
import { BUILD_STORYBOOK_COMMAND } from '../visual/missing-index.mjs'

function parse(code, fileName = 'fixture.tsx') {
  return parseTsx(fileName, code)
}

// `computeStateCoverage`'s own `componentKeyForFile` (state-coverage.mjs) keys `localElements` by a
// path *relative to the real* `packages/design-system/src`, not by whatever prefix a fixture
// happens to use — a fixture path outside that real tree (e.g. the `/repo/...` prefix several
// `computed.matrices` fixtures below use) still drives `buildAxisMatrix` correctly, because it
// matches `componentKey` against itself internally, but it can never key
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

// T693: `Button`, `Field` and `Link` read their axis defaults from one exported constant each
// (`BUTTON_AXIS_DEFAULTS`, ...), which the runtime pass also reads. The static reading must follow
// that reference, or every row of those primitives' matrices would lose its axis. A member that is
// not a string literal, or a constant that is not a top-level object, still resolves to `null`.
test('findVariantSizeDefaults follows a member of a top-level as-const constant, and only that', () => {
  const read = (source) => findVariantSizeDefaults(parse(source))
  assert.deepEqual(
    read(`
      const DEFAULTS = { variant: 'secondary', size: 'md' } as const satisfies Shape
      function Button({ variant = DEFAULTS.variant, size = DEFAULTS.size }) { return <button /> }
    `),
    { variant: 'secondary', size: 'md' },
  )
  assert.deepEqual(
    read(`
      const DEFAULTS = { variant: pick(), size: 3 }
      function Button({ variant = DEFAULTS.variant, size = DEFAULTS.size }) { return <button /> }
    `),
    { variant: null, size: null },
  )
  assert.deepEqual(
    read(`function Button({ variant = ELSEWHERE.variant, size = 'lg' }) { return <button /> }`),
    { variant: null, size: 'lg' },
  )
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

// M-B on the real tree: a copy of Footer's stories named `Extra` credits `Extra:Hover` on `Link`'s
// matrix; a second `Extra.stories.tsx` in SearchBox used to be accounted for by it.
test('computeStateCoverage (real tree): Extra.stories.tsx planted in both Footer and SearchBox throws; planted in Footer alone it does not and reports nothing (T684, M-B)', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const footer = readFileSync(srcFile('composites/Footer/Footer.stories.tsx'), 'utf8')
  filesByPath.set(srcFile('composites/Footer/Extra.stories.tsx'), footer)
  // The copy's entries are the original's, re-keyed to the copy: the browser rendered the same thing.
  const manifest = { ...readManifest().manifest }
  for (const [id, entry] of Object.entries(manifest)) {
    if (entry.importPath === './src/composites/Footer/Footer.stories.tsx') {
      manifest[`${id}-extra`] = {
        ...entry,
        importPath: './src/composites/Footer/Extra.stories.tsx',
      }
    }
  }
  const alone = computeStateCoverage({ componentDirs, filesByPath, storyFilesByPath, manifest })
  assert.deepEqual(alone.unaccountedForceStates.missing, [])
  assert.deepEqual(alone.manifestProblems, [])
  assert.ok(creditsOf(alone, 'Extra:Hover').length > 0, 'the copy is credited under its own label')
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

test("findUnaccountedForceStates (via computeStateCoverage): KNOWN_UNACCOUNTED_FORCE_STATES is empty and the whole real tree, read through the committed manifest, reports zero missing, zero known and zero expired — T598's own completion condition, not a cell count", () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest: readManifest().manifest,
  })
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

// --- Orchestrator remediation 1: a cell distinguishes a confirmed 'none' from an 'unresolved:
// <reason>' it could not settle — buildElementMatrix's own contract. -------------------------------

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

// --- REJECT on #80, item 4: own story files skip their JSX and take axis values from args only,
// so Button.stories.tsx's Disabled/AllVariants/RealisticPageActions (real JSX in a `render:`
// function, no `args` at all) land in the primitive's default row (`secondary|md`) instead of the
// variant/size their own JSX actually renders. -----------------------------------------------------

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
    },
  ]
  const rows = buildElementMatrix(elements, storyStates)
  assert.deepEqual(rows[0].disabled, ['none'])
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

// --- REJECT on #80, item 3: also resolve names from a literal aria-label. --------------------

test("findLocalElements resolves a candidate's own name from a literal aria-label when it carries no JSX text", () => {
  const source = `const el = <nav aria-label="Primary" tabIndex={0} />`
  const sourceFile = parse(source)
  const constMap = buildConstStringMap(sourceFile)
  const found = findLocalElements(sourceFile, 'fixture.tsx', constMap)
  assert.equal(found[0].text, 'Primary')
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

// =================================================================================================
// T694 (row 8, H5): what every story credits comes from the runtime manifest, not from reading source
// =================================================================================================
//
// `packages/design-system/specs/state-coverage-runtime.json` records, for every story, what a real
// browser did with it (T693). `computeStateCoverage` reads that record and nothing else about a
// forced story: which element the force reached (its source stamp), which tracked primitive instance
// placed it, and which instances the story mounts. These tests plant the shapes T687–T692 reproduced
// in memory against the static reading, and T683's story files outside a component directory, and
// assert on the reason each refusal prints — not on `credited on no cell`, which every refusal prints.
//
// The T693 plants are the real ones: `Plants.stories.tsx` is planted into `Button`'s directory under
// another name and each of its entries in the committed manifest is re-keyed to it, so a plant's
// verdict is the browser's recorded answer, not a literal typed here.

const DS_DIR = path.resolve(REPO_SRC_DIR, '..')
const STAMP_ROOT = 'packages/design-system/src/'
// The widths every story is captured and recorded at: one source, `scripts/visual/review-widths.mjs`.
const WIDTHS = REVIEW_WIDTHS.map(String)
const atEveryWidth = (record) => Object.fromEntries(WIDTHS.map((w) => [w, record]))
const placedInstance = (component, variant, size, disabledAt = []) => ({
  component,
  variant,
  size,
  disabledAt,
})
const manifestEntry = (relStory, exportName, record, files = []) => ({
  importPath: `./${relStory}`,
  exportName,
  files,
  widths: atEveryWidth(record),
})

// The credits a story label earns anywhere in the region, by cell: `record1|<file>:<line>|<state>` and
// `<Primitive>|<row>|<column>`. A label is matched whole (`Base:Export`, or the bare export name of a
// component with one story file) in a cell's own list, never as a substring of another label.
function creditsOf(computed, label) {
  const named = (list) => list.some((entry) => entry === label || entry.endsWith(`:${label}`))
  const found = []
  for (const { elements } of computed.localElements) {
    for (const el of elements) {
      for (const [state, list] of Object.entries(el.coveredBy)) {
        if (named(list)) found.push(`record1|${el.file}:${el.line}|${state}`)
      }
    }
  }
  for (const [primitive, rows] of Object.entries(computed.matrices)) {
    for (const row of rows) {
      for (const column of ['rest', 'hover', 'focusVisible', 'active', 'disabled']) {
        if (named(row[column])) found.push(`${primitive}|${row.variantSize}|${column}`)
      }
    }
  }
  return found.sort()
}
// The credits that depict the state a story forces — the Hover, Focus-visible and Press columns, not
// the Rest and Disabled columns a story's mounted instances fill whatever its force does.
const stateCreditsOf = (computed, label) =>
  creditsOf(computed, label).filter((cell) => !/\|(rest|disabled)$/.test(cell))
const refusalOf = (computed, componentKey, exportName) =>
  computed.unaccountedForceStates.missing.find(
    (m) => m.componentKey === componentKey && m.exportName === exportName,
  )

// ---- The verdict, on its own: every plant's recorded answer and every reason --------------------

const recordOneKeys = new Set([`${STAMP_ROOT}primitives/Button/index.tsx:213`])
const forceWidths = (force) => atEveryWidth({ mounts: [], force })

test('resolveRuntimeForce: a force the browser found no element for is refused with that reason, naming every width', () => {
  const verdict = resolveRuntimeForce(
    { widths: forceWidths({ count: 0, stamp: null, placedBy: null }) },
    { recordOneKeys },
  )
  assert.match(verdict.refusal, /^no element matched the force at 375px, 768px, 1280px:/)
  assert.doesNotMatch(verdict.refusal, /credited on no cell/)
})

test('resolveRuntimeForce: two matches are refused as strict-mode ambiguity, with the count at each width', () => {
  const verdict = resolveRuntimeForce(
    { widths: forceWidths({ count: 2, stamp: null, placedBy: null }) },
    { recordOneKeys },
  )
  assert.match(
    verdict.refusal,
    /^more than one element matched the force \(2 at 375px, 2 at 768px, 2 at 1280px\): Playwright's strict mode refuses it/,
  )
})

test('resolveRuntimeForce: a stamp that differs across widths is refused, naming each width and its stamp', () => {
  const stampAt = (stamp) => ({ mounts: [], force: { count: 1, stamp, placedBy: null } })
  const verdict = resolveRuntimeForce(
    {
      widths: {
        375: stampAt(`${STAMP_ROOT}primitives/Button/index.tsx:213`),
        768: stampAt(`${STAMP_ROOT}primitives/Button/index.tsx:195`),
        1280: stampAt(`${STAMP_ROOT}primitives/Button/index.tsx:213`),
      },
    },
    { recordOneKeys },
  )
  assert.match(verdict.refusal, /^the located element's stamp differs across widths/)
  assert.match(verdict.refusal, /index\.tsx:195 at 768px/)
})

test('resolveRuntimeForce: a placing instance that differs across widths is refused', () => {
  const at = (variant) => ({
    mounts: [],
    force: {
      count: 1,
      stamp: `${STAMP_ROOT}primitives/Button/index.tsx:213`,
      placedBy: placedInstance('Button', variant, 'md'),
    },
  })
  const verdict = resolveRuntimeForce(
    { widths: { 375: at('primary'), 768: at('ghost'), 1280: at('ghost') } },
    { recordOneKeys },
  )
  assert.match(verdict.refusal, /^the primitive instance that placed the located element differs/)
})

test('resolveRuntimeForce: a stamp in no record-1 element and no placing instance is refused, naming the stamp', () => {
  const stamp = `${STAMP_ROOT}primitives/Callout/index.tsx:59`
  const verdict = resolveRuntimeForce(
    { widths: forceWidths({ count: 1, stamp, placedBy: null }) },
    { recordOneKeys },
  )
  assert.equal(
    verdict.refusal,
    `the located element's stamp ${stamp} is in no record-1 element and no tracked primitive placed it`,
  )
})

test('resolveRuntimeForce: an element no design-system file wrote (a raw element in the story) is refused as carrying no stamp', () => {
  const verdict = resolveRuntimeForce(
    { widths: forceWidths({ count: 1, stamp: null, placedBy: null }) },
    { recordOneKeys },
  )
  assert.match(
    verdict.refusal,
    /^the located element carries no source stamp: no design-system source file wrote it/,
  )
})

test('resolveRuntimeForce: an entry recording no force at a width is refused and names the rewrite command; no width at all is a malformed entry', () => {
  const noForce = resolveRuntimeForce({ widths: atEveryWidth({ mounts: [] }) }, { recordOneKeys })
  assert.match(noForce.refusal, /records no force target at 375px, 768px, 1280px/)
  assert.ok(noForce.refusal.includes(REWRITE_COMMAND))
  assert.match(
    resolveRuntimeForce({ widths: {} }, { recordOneKeys }).malformed,
    /^it records no captured width/,
  )
})

test('resolveRuntimeForce: the axis the runtime renders — a spread that wins over a literal credits the variant the browser reports, record 1 and record 3 both', () => {
  const stamp = `${STAMP_ROOT}primitives/Button/index.tsx:213`
  const verdict = resolveRuntimeForce(
    {
      widths: forceWidths({
        count: 1,
        stamp,
        placedBy: placedInstance('Button', 'destructive', 'md'),
      }),
    },
    { recordOneKeys },
  )
  assert.equal(verdict.refusal, undefined)
  assert.equal(verdict.stamp, stamp)
  assert.equal(verdict.placedBy.variant, 'destructive')
  assert.deepEqual(verdict.placedBy.row, {
    variant: { value: 'destructive', resolved: 'runtime' },
    size: { value: 'md', resolved: 'runtime' },
  })
})

test('resolveRuntimeForce: a Menu rendered with no variant has no matrix row — its trigger is credited in record 1 and the record-3 half is a named note, never a (no axis) row', () => {
  const stamp = `${STAMP_ROOT}primitives/Menu/index.tsx:144`
  const verdict = resolveRuntimeForce(
    {
      widths: forceWidths({ count: 1, stamp, placedBy: placedInstance('Menu', null, null) }),
    },
    { recordOneKeys: new Set([stamp]) },
  )
  assert.equal(verdict.stamp, stamp)
  assert.equal(verdict.placedBy, null)
  assert.deepEqual(verdict.notes, [
    'Menu rendered with no variant (none passed, no default), so no row of its matrix is keyed by it',
  ])
  const refused = resolveRuntimeForce(
    { widths: forceWidths({ count: 1, stamp, placedBy: placedInstance('Menu', null, null) }) },
    { recordOneKeys },
  )
  assert.match(
    refused.refusal,
    /is in no record-1 element and no tracked primitive placed it \(Menu rendered with no variant/,
  )
})

test('resolveRuntimeForce: Field (no variant) and Link (no size) key on their own axes only', () => {
  assert.deepEqual(rowAxesOf(placedInstance('Field', null, 'md')).size, {
    value: 'md',
    resolved: 'runtime',
  })
  assert.deepEqual(rowAxesOf(placedInstance('Field', null, 'md')).variant, {
    value: null,
    resolved: 'n/a',
  })
  assert.deepEqual(rowAxesOf(placedInstance('Link', 'inline', null)).size, {
    value: null,
    resolved: 'n/a',
  })
  assert.match(
    rowAxesOf(placedInstance('Button', 'primary', null)).reason,
    /Button rendered with no size/,
  )
  assert.match(
    rowAxesOf(placedInstance('Badge', null, null)).reason,
    /Badge is not a tracked primitive/,
  )
})

test('stableMounts: an instance one width renders and another does not credits nothing, and a count is the smallest across widths', () => {
  const button = placedInstance('Button', 'primary', 'md')
  const ghost = placedInstance('Button', 'ghost', 'md')
  const entry = {
    widths: {
      375: { mounts: [button, ghost, ghost] },
      768: { mounts: [button, ghost] },
      1280: { mounts: [button, ghost, ghost, button] },
    },
  }
  assert.deepEqual(stableMounts(entry), [button, ghost])
  assert.deepEqual(stableMounts({ widths: {} }), [])
})

test('PRIMITIVE_AXES agrees with the axes each tracked primitive exports and the preview registers', () => {
  for (const name of ['Button', 'Link', 'Field']) {
    const source = readFileSync(path.join(REPO_SRC_DIR, 'primitives', name, 'index.tsx'), 'utf8')
    const declared = source.match(/export const [A-Z]+_AXIS_DEFAULTS = \{([^}]*)\}/)
    assert.ok(declared, `${name} exports its axis defaults`)
    const axes = [...declared[1].matchAll(/(\w+):/g)].map((m) => m[1])
    assert.deepEqual(axes, PRIMITIVE_AXES[name], name)
  }
  const preview = readFileSync(path.join(DS_DIR, '.storybook', 'preview.tsx'), 'utf8')
  assert.match(preview, /Menu: \{[^}]*axes: \{ variant: null \}/s)
  assert.deepEqual(PRIMITIVE_AXES.Menu, ['variant'])
  assert.deepEqual(Object.keys(PRIMITIVE_AXES).sort(), [...PRIMITIVE_NAMES].sort())
})

// ---- The T693 plants, end to end through `computeStateCoverage` ---------------------------------

let plantedRunMemo = null
function plantedRun() {
  if (plantedRunMemo) return plantedRunMemo
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const manifest = { ...readManifest().manifest }
  const plants = readFileSync(
    path.join(DS_DIR, '.storybook', 'fixtures', 'Plants.stories.tsx'),
    'utf8',
  )
  const plantedFile = srcFile('primitives/Button/ZzPlants.stories.tsx')
  // The plants are tagged `state-coverage-fixture`, which makes a story a fixture wherever it sits (the
  // region never reads one). Re-keyed into `Button`'s directory to be read, they are planted untagged.
  const untagged = plants.replace(
    "tags: ['state-coverage-fixture', '!dev', '!autodocs']",
    'tags: []',
  )
  assert.notEqual(untagged, plants, 'the plants file carries the fixture tag the plant strips')
  filesByPath.set(plantedFile, untagged)
  const entries = {}
  for (const [id, entry] of Object.entries(manifest)) {
    if (entry.importPath !== './.storybook/fixtures/Plants.stories.tsx') continue
    entries[entry.exportName] = entry
    manifest[`zz-${id}`] = { ...entry, importPath: './src/primitives/Button/ZzPlants.stories.tsx' }
  }
  plantedRunMemo = {
    entries,
    computed: computeStateCoverage({ componentDirs, filesByPath, storyFilesByPath, manifest }),
  }
  return plantedRunMemo
}
const plantStamp = (entries, name) => entries[name].widths['1280'].force.stamp
const BUTTON_FILE = `${STAMP_ROOT}primitives/Button/index.tsx`

test('the committed manifest records every T693 plant the verdicts below assert on', () => {
  const { entries } = plantedRun()
  assert.equal(Object.keys(entries).length, 26)
  for (const [name, entry] of Object.entries(entries)) {
    assert.ok(entry.widths['1280'], name)
  }
})

test('T693 plants: a force with no match, two matches, a raw element or an unstamped one credits no state cell and is reported with its own reason', () => {
  const { computed } = plantedRun()
  const refused = {
    NoMatch: /^no element matched the force at 375px, 768px, 1280px:/,
    TwoMatches: /^more than one element matched the force \(2 at 375px, 2 at 768px, 2 at 1280px\)/,
    RawAnchorBesideLink: /^more than one element matched the force \(2 at /,
    NoPlacingInstance: /^the located element carries no source stamp/,
    RawAnchorPickedByName: /^the located element carries no source stamp/,
    RawButtonPickedByName: /^the located element carries no source stamp/,
    GuardedMenuBesideRaw: /^the located element carries no source stamp/,
    SliderInsideButton: /^the located element carries no source stamp/,
    HiddenAncestor: /^no element matched the force at 375px/,
    ArgsHrefIgnored: /^no element matched the force at 375px/,
    ButtonHrefViaSpreadConstant: /^no element matched the force at 375px/,
    NthPastTheLast: /^no element matched the force at 375px/,
    ArgsDisabledSpread:
      /^the located element's stamp .*Button\/index\.tsx:213 is in its placing Button's disabledAt/,
    DisabledControlInField: /is in its placing Field's disabledAt/,
    StampOutsideThePrimitive:
      /^the located element's stamp .*Callout\/index\.tsx:59 is in no record-1 element and no tracked primitive placed it$/,
    ForcedCalloutHeading:
      /^the located element's stamp .*Callout\/index\.tsx:64 is in no record-1 element and no tracked primitive placed it$/,
  }
  for (const [name, reason] of Object.entries(refused)) {
    assert.deepEqual(
      stateCreditsOf(computed, `ZzPlants:${name}`),
      [],
      `${name} credits no state cell`,
    )
    const missing = refusalOf(computed, 'primitives/Button', name)
    assert.ok(missing, `${name} is reported`)
    assert.match(missing.refusal, reason, name)
    assert.match(
      describeMissingForceState(missing),
      new RegExp(reason.source.replace(/^\^/, '').replace(/\$$/, '')),
      `${name}: the printed report carries the reason`,
    )
  }
})

test('T693 plants (record 3, primitive axis cells): the axis the runtime renders is the row credited — a spread that wins, a bare Button, an href Button, the Field clone, a Menu given a variant', () => {
  const { computed, entries } = plantedRun()
  const stamp = (name) => plantStamp(entries, name)
  const credited = (name) => creditsOf(computed, `ZzPlants:${name}`)
  assert.deepEqual(credited('SpreadWinsOverLiteral'), [
    'Button|destructive|md|hover',
    `record1|${stamp('SpreadWinsOverLiteral')}|hover`,
  ])
  assert.deepEqual(credited('BareButton'), [
    'Button|secondary|md|hover',
    `record1|${BUTTON_FILE}:213|hover`,
  ])
  assert.deepEqual(credited('HrefAndDisabled'), [
    'Button|secondary|md|hover',
    `record1|${BUTTON_FILE}:195|hover`,
  ])
  assert.deepEqual(credited('ClonedControl'), ['Field|md|focusVisible'])
  assert.deepEqual(credited('MenuSpreadWithVariant'), [
    'Menu|selection|hover',
    `record1|${STAMP_ROOT}primitives/Menu/index.tsx:144|hover`,
  ])
  for (const name of [
    'SpreadWinsOverLiteral',
    'BareButton',
    'HrefAndDisabled',
    'ClonedControl',
    'MenuSpreadWithVariant',
  ]) {
    assert.equal(
      refusalOf(computed, 'primitives/Button', name),
      undefined,
      `${name} is accounted for`,
    )
  }
})

test('T693 plants (Disabled column): a story whose args say disabled but whose render never passes them credits no Disabled cell, and a spread that does pass them credits the row the browser rendered', () => {
  const { computed } = plantedRun()
  assert.deepEqual(creditsOf(computed, 'ZzPlants:ArgsDisabledIgnored'), [
    'Button|destructive|md|hover',
    `record1|${BUTTON_FILE}:213|hover`,
  ])
  // A hover forced on a disabled Button paints disabled, not hover: the Disabled column is credited
  // from the mount, the forced state is refused (T694 review, B3).
  assert.deepEqual(creditsOf(computed, 'ZzPlants:ArgsDisabledSpread'), [
    'Button|secondary|md|disabled',
  ])
  assert.match(
    refusalOf(computed, 'primitives/Button', 'ArgsDisabledSpread').refusal,
    /^the located element's stamp .*Button\/index\.tsx:213 is in its placing Button's disabledAt/,
  )
  assert.deepEqual(creditsOf(computed, 'ZzPlants:DisabledControlInField'), ['Field|md|disabled'])
  assert.match(
    refusalOf(computed, 'primitives/Button', 'DisabledControlInField').refusal,
    /is in its placing Field's disabledAt/,
  )
  assert.deepEqual(
    creditsOf(computed, 'ZzPlants:HrefAndDisabled').filter((c) => c.endsWith('|disabled')),
    [],
  )
})

test('T693 plants: a Menu rendered with no variant is credited in record 1 only, the record-3 half named as a note', () => {
  const { computed } = plantedRun()
  assert.deepEqual(creditsOf(computed, 'ZzPlants:MenuWithoutVariant'), [
    `record1|${STAMP_ROOT}primitives/Menu/index.tsx:144|hover`,
  ])
  assert.deepEqual(
    computed.partialRefusals
      .filter((p) => p.exportName === 'MenuWithoutVariant')
      .map((p) => p.note),
    [
      'Menu rendered with no variant (none passed, no default), so no row of its matrix is keyed by it',
    ],
  )
  // The plant's own `<Menu {...args} />` call site opens a `(no axis)` row (a static call site); the
  // story credits nothing on it.
  const noAxis = computed.matrices.Menu.find((r) => r.variantSize === '(no axis)')
  assert.doesNotMatch(JSON.stringify(noAxis ?? {}), /MenuWithoutVariant/)
})

test('T693 plants: a play() that holds focus on a Callout heading, or a Button, credits no cover (a focus note is never a frame)', () => {
  const { computed } = plantedRun()
  assert.deepEqual(creditsOf(computed, 'ZzPlants:PlayFocusCalloutHeading'), [])
  assert.deepEqual(creditsOf(computed, 'ZzPlants:PlayFocus'), [])
})

test('T693 plants, contrast (record 3, primitive axis cells): a name selecting one of two Buttons credits exactly that one and never the other mounted row', () => {
  const { computed } = plantedRun()
  assert.deepEqual(creditsOf(computed, 'ZzPlants:NameSelectsOneOfTwo'), [
    'Button|ghost|lg|hover',
    `record1|${BUTTON_FILE}:213|hover`,
  ])
})

test('T693 plants: no plant is silently dropped — each is credited on some cell or reported, none is both and none is neither', () => {
  const { computed, entries } = plantedRun()
  for (const [name, entry] of Object.entries(entries)) {
    if (!entry.widths['1280'].force) continue
    const credited = stateCreditsOf(computed, `ZzPlants:${name}`).length > 0
    const reported = refusalOf(computed, 'primitives/Button', name) !== undefined
    assert.notEqual(credited, reported, `${name}: credited ${credited}, reported ${reported}`)
  }
  assert.deepEqual(computed.manifestProblems, [])
})

// ---- T683 outcome (1): where a story file lives decides nothing ---------------------------------

const RAW_FORCE_STORY = (name) => `
import { Foo } from './index'
const meta = { title: 'Zz/${name}' }
export default meta
export const ${name} = {
  render: () => <button type="button">Raw</button>,
  parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Raw' } },
}
`

function outsideRun({ files, manifest }) {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const merged = { ...readManifest().manifest, ...manifest }
  for (const [rel, text] of Object.entries(files)) {
    // Outside a component's own walk: a tier directory's own file, `src/lib`, `foundations`, a `.stories.ts`.
    storyFilesByPath.set(path.join(DS_DIR, rel), text)
  }
  return computeStateCoverage({ componentDirs, filesByPath, storyFilesByPath, manifest: merged })
}
const FOUNDATIONS = '.storybook/foundations/ZzFoundationsPage.stories.tsx'
const TIER_ROOT = 'src/primitives/ZzTierRootPage.stories.tsx'
const LIB = 'src/lib/ZzLibPage.stories.tsx'
const COMPONENT_TS = 'src/primitives/Button/ZzExtraButton.stories.ts'

test('T683 outcome (1): a forced story under foundations, a tier root, src/lib or a *.stories.ts in a component directory is credited or reported with a reason, never dropped', () => {
  const buttonStamp = `${BUTTON_FILE}:213`
  const forcesButton = (name) => `
import { Button } from './index'
const meta = { component: Button }
export default meta
export const ${name} = { parameters: { visualForceState: { state: 'hover', role: 'button' } } }
`
  const computed = outsideRun({
    files: {
      [FOUNDATIONS]: RAW_FORCE_STORY('ZzFoundationsHover'),
      [TIER_ROOT]: forcesButton('ZzTierRootHover'),
      [LIB]: RAW_FORCE_STORY('ZzLibHover'),
      [COMPONENT_TS]: forcesButton('ZzExtraButtonHover'),
    },
    manifest: {
      'zz-foundations': manifestEntry(FOUNDATIONS, 'ZzFoundationsHover', {
        mounts: [],
        force: { count: 1, stamp: null, placedBy: null },
      }),
      'zz-tier-root': manifestEntry(TIER_ROOT, 'ZzTierRootHover', {
        mounts: [placedInstance('Button', 'secondary', 'md')],
        force: {
          count: 1,
          stamp: buttonStamp,
          placedBy: placedInstance('Button', 'secondary', 'md'),
        },
      }),
      'zz-lib': manifestEntry(LIB, 'ZzLibHover', {
        mounts: [],
        force: { count: 1, stamp: null, placedBy: null },
      }),
      'zz-component-ts': manifestEntry(COMPONENT_TS, 'ZzExtraButtonHover', {
        mounts: [placedInstance('Button', 'ghost', 'lg')],
        force: { count: 1, stamp: buttonStamp, placedBy: placedInstance('Button', 'ghost', 'lg') },
      }),
    },
  })
  assert.deepEqual(computed.manifestProblems, [])
  // A raw element no tracked cell can credit: reported, under a key of its own, with the true reason.
  const raw = { reason: /^the located element carries no source stamp/ }
  for (const [key, name] of [
    ['.storybook/foundations', 'ZzFoundationsHover'],
    ['src/lib', 'ZzLibHover'],
  ]) {
    const missing = refusalOf(computed, key, name)
    assert.ok(missing, `${name} is reported under ${key}`)
    assert.match(missing.refusal, raw.reason)
    assert.deepEqual(creditsOf(computed, `${name.replace(/Hover$/, '')}Page:${name}`), [])
  }
  // A real element: credited in both records, under the qualified label, and not reported.
  assert.deepEqual(creditsOf(computed, 'ZzTierRootPage:ZzTierRootHover'), [
    'Button|secondary|md|hover',
    `record1|${buttonStamp}|hover`,
  ])
  assert.deepEqual(creditsOf(computed, 'ZzExtraButton:ZzExtraButtonHover'), [
    'Button|ghost|lg|hover',
    `record1|${BUTTON_FILE}:213|hover`,
  ])
  assert.equal(refusalOf(computed, 'src/primitives', 'ZzTierRootHover'), undefined)
  assert.equal(refusalOf(computed, 'primitives/Button', 'ZzExtraButtonHover'), undefined)
})

test('T683 outcome (1), contrast: a <tier>/<Component>/*.stories.tsx state story is credited exactly as before', () => {
  const { computed } = plantedRun()
  const hover = computed.matrices.Button.find((r) => r.variantSize === 'ghost|md')
  assert.ok(hover.hover.includes('Button:GhostHover'))
  assert.deepEqual(
    computed.unaccountedForceStates.missing.filter((m) => m.componentKey === 'primitives/Menu'),
    [],
  )
})

test('T683 outcome (1): the story files the walk reads are the ones the Storybook globs index', () => {
  const main = readFileSync(path.join(DS_DIR, '.storybook', 'main.ts'), 'utf8')
  const globs = [...main.matchAll(/'((?:\.\.?\/)[^']*\.stories\.@\(ts\|tsx\))'/g)].map((m) => m[1])
  assert.deepEqual(globs, [
    '../src/**/*.stories.@(ts|tsx)',
    './foundations/**/*.stories.@(ts|tsx)',
    './fixtures/**/*.stories.@(ts|tsx)',
  ])
  const { storyFilesByPath, filesByPath } = readAllSourceFiles()
  const rel = (f) => path.relative(DS_DIR, f).split(path.sep).join('/')
  const read = [...storyFilesByPath.keys()].map(rel)
  assert.ok(
    read.some((f) => f.startsWith('.storybook/foundations/')),
    'foundations is read',
  )
  assert.ok(
    read.some((f) => f.startsWith('src/composites/')),
    'a component story is read',
  )
  assert.equal(
    read.some((f) => f.startsWith('.storybook/fixtures/')),
    false,
    'the plants are not',
  )
  assert.ok(read.every((f) => /\.stories\.tsx?$/.test(f)))
  for (const f of filesByPath.keys()) {
    if (/\.stories\.tsx$/.test(f))
      assert.ok(storyFilesByPath.has(f), `${rel(f)} is in the story set`)
  }
})

// ---- A story with no manifest entry fails, naming the story and the refresh command -------------

test('a story with no manifest entry is a problem naming the story, its file and the command that refreshes the manifest', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const manifest = readManifest().manifest
  storyFilesByPath.set(
    path.join(DS_DIR, LIB),
    `export default {}\nexport const ZzUnrecorded = { parameters: { visualForceState: { state: 'hover', role: 'button' } } }\n`,
  )
  const { manifestProblems } = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest,
  })
  assert.equal(manifestProblems.length, 1)
  assert.equal(manifestProblems[0].kind, 'no-entry')
  assert.match(
    manifestProblems[0].detail,
    /story ZzUnrecorded of src\/lib\/ZzLibPage\.stories\.tsx has no entry in packages\/design-system\/specs\/state-coverage-runtime\.json/,
  )
  assert.ok(manifestProblems[0].detail.includes(REWRITE_COMMAND), 'names the rewrite command')
  assert.ok(manifestProblems[0].detail.includes(BUILD_STORYBOOK_COMMAND), 'names the build command')
})

test('an entry for a story no file exports is a stale-entry problem naming the entry and the rewrite command', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const manifest = {
    ...readManifest().manifest,
    'zz-gone': manifestEntry('src/lib/ZzGone.stories.tsx', 'ZzGone', { mounts: [] }),
  }
  const { manifestProblems } = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest,
  })
  assert.equal(manifestProblems.length, 1)
  assert.equal(manifestProblems[0].kind, 'stale-entry')
  assert.match(
    manifestProblems[0].detail,
    /entry \(zz-gone\) for ZzGone of src\/lib\/ZzGone\.stories\.tsx/,
  )
  assert.ok(manifestProblems[0].detail.includes(REWRITE_COMMAND))
})

test('a manifest with a force record for a story whose visualForceState state is not a literal is a problem, not a silent drop', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  storyFilesByPath.set(
    path.join(DS_DIR, LIB),
    `export default {}\nconst state = 'hover'\nexport const ZzDynamicState = { parameters: { visualForceState: { state, role: 'button' } } }\n`,
  )
  const manifest = {
    ...readManifest().manifest,
    'zz-dynamic': manifestEntry(LIB, 'ZzDynamicState', {
      mounts: [],
      force: { count: 1, stamp: null, placedBy: null },
    }),
  }
  const { manifestProblems } = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest,
  })
  assert.deepEqual(
    manifestProblems.map((p) => p.kind),
    ['unreadable-force'],
  )
  assert.match(manifestProblems[0].detail, /visualForceState carries no string-literal state/)
})

test('the check fails (exit 1) on the real tree with a story appended that has no manifest entry, naming it and the refresh command', () => {
  const run = runCheckOnPlantedTree(
    `\nexport const ZzUnrecordedStory = { parameters: { visualForceState: { state: 'hover', role: 'link' } } }\n`,
  )
  assert.equal(run.status, 1, run.stdout + run.stderr)
  assert.match(
    run.stderr,
    /story ZzUnrecordedStory of src\/composites\/MatchRow\/MatchRow\.stories\.tsx has no entry in packages\/design-system\/specs\/state-coverage-runtime\.json/,
  )
  assert.match(run.stderr, /pnpm test:visual:state-coverage-runtime --write/)
})

// The wiring from the report to the failure line, end to end: the script itself, run on a copy of the
// real tree with one story appended. A copy, because the script reads a fixed
// `packages/design-system/src` beside itself; symlinks only for `node_modules`.
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
    for (const dir of ['checks', 'visual']) {
      mkdirSync(path.join(tmp, 'scripts', dir), { recursive: true })
      const from = path.join(repoRoot, 'scripts', dir)
      for (const f of readdirSync(from).filter(
        (n) => n.endsWith('.mjs') && !n.endsWith('.test.mjs'),
      )) {
        cpSync(path.join(from, f), path.join(tmp, 'scripts', dir, f))
      }
    }
    mkdirSync(path.join(tmp, 'packages', 'design-system'), { recursive: true })
    for (const rel of ['src', 'specs', 'package.json', '.storybook']) {
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

// ---- Contrasts that must still be credited, on the real tree and the committed manifest ----------

test('contrast (record 1 and record 3): Menu’s KeyboardNavigation, FooterItemHover and FooterItemActive are credited at the footer item and the selection row', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest: readManifest().manifest,
  })
  const menuIndex = `${STAMP_ROOT}primitives/Menu/index.tsx`
  assert.deepEqual(creditsOf(computed, 'FooterItemHover'), [
    'Menu|selection|hover',
    `record1|${menuIndex}:248|hover`,
  ])
  assert.deepEqual(creditsOf(computed, 'FooterItemActive'), [
    'Menu|selection|active',
    `record1|${menuIndex}:248|active`,
  ])
  assert.deepEqual(
    creditsOf(computed, 'KeyboardNavigation'),
    ['Menu|selection|focusVisible', `record1|${menuIndex}:248|focusVisible`].sort(),
  )
  assert.deepEqual(computed.unaccountedForceStates.missing, [])
  assert.deepEqual(computed.manifestProblems, [])
})

test('contrast (record 3, primitive axis cells): Field’s cloned control is credited at the Field row for a force on that control’s role', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest: readManifest().manifest,
  })
  const md = computed.matrices.Field.find((r) => r.variantSize === 'md')
  assert.deepEqual(md.hover, ['Field:Hover'])
  assert.deepEqual(md.focusVisible, ['Field:FocusVisible'])
  assert.deepEqual(md.disabled, ['Field:Disabled', 'Field:Loading'])
})

// ---- The own-story mounts, the Disabled column and record 3's call-site rows, on a small tree ----

const MINI_BUTTON = `export function Button({ variant = 'secondary', size = 'md', disabled, children }) {
  return (
    <button
      type="button"
      disabled={disabled}
      className="hover:bg-surface-sunken focus-visible:outline-2 active:bg-background"
    >
      {children}
    </button>
  )
}
`
const MINI_BUTTON_STAMP = `${BUTTON_FILE}:3`
const MINI_STORIES = 'primitives/Button/Button.stories.tsx'
function miniRun(
  storiesSource,
  manifest,
  { componentDirs = [{ segment: 'primitives', name: 'Button' }], extra = [] } = {},
) {
  const filesByPath = new Map([
    [srcFile('primitives/Button/index.tsx'), MINI_BUTTON],
    [
      srcFile(MINI_STORIES),
      `import { Button } from './index'\nconst meta = { component: Button }\nexport default meta\n${storiesSource}`,
    ],
    ...extra,
  ])
  return computeStateCoverage({ componentDirs, filesByPath, manifest })
}
const miniRecord = (mounts, force) => ({ mounts, ...(force ? { force } : {}) })
const miniEntry = (exportName, record) =>
  manifestEntry(`src/${MINI_STORIES}`, exportName, record, [BUTTON_FILE])

test('contrast (Disabled column and own-story mounts): an args-only Button story with disabled: true credits Disabled and Rest at the row the browser mounted it', () => {
  const computed = miniRun(`export const ZzDisabledArgs = { args: { disabled: true } }\n`, {
    'zz-disabled-args': miniEntry(
      'ZzDisabledArgs',
      miniRecord([placedInstance('Button', 'secondary', 'md', [MINI_BUTTON_STAMP])]),
    ),
  })
  assert.deepEqual(creditsOf(computed, 'ZzDisabledArgs'), [
    'Button|secondary|md|disabled',
    'Button|secondary|md|rest',
  ])
})

test('own-story mounts (record 3, Rest): a story mounting several variants credits Rest at each row as rendered, and a forced own story credits its state at the placing instance only', () => {
  const computed = miniRun(
    `export const ZzAllVariants = {}\nexport const ZzGhostHover = { parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Ghost' } } }\n`,
    {
      'zz-all': miniEntry(
        'ZzAllVariants',
        miniRecord([
          placedInstance('Button', 'primary', 'lg'),
          placedInstance('Button', 'ghost', 'md'),
        ]),
      ),
      'zz-hover': miniEntry(
        'ZzGhostHover',
        miniRecord(
          [placedInstance('Button', 'primary', 'lg'), placedInstance('Button', 'ghost', 'md')],
          { count: 1, stamp: MINI_BUTTON_STAMP, placedBy: placedInstance('Button', 'ghost', 'md') },
        ),
      ),
    },
  )
  assert.deepEqual(creditsOf(computed, 'ZzAllVariants'), [
    'Button|ghost|md|rest',
    'Button|primary|lg|rest',
  ])
  assert.deepEqual(creditsOf(computed, 'ZzGhostHover'), [
    'Button|ghost|md|hover',
    `record1|${MINI_BUTTON_STAMP}|hover`,
  ])
})

test('Disabled column: the DOM decides — a mounted instance whose rendered element is not disabled (an href Button, an ignored arg) credits no Disabled cell, whatever args say', () => {
  const computed = miniRun(
    `export const ZzIgnoredArgs = { args: { disabled: true }, render: () => <Button>Go</Button> }\n`,
    {
      'zz-ignored': miniEntry(
        'ZzIgnoredArgs',
        miniRecord([placedInstance('Button', 'secondary', 'md', [])]),
      ),
    },
  )
  assert.deepEqual(creditsOf(computed, 'ZzIgnoredArgs'), ['Button|secondary|md|rest'])
})

test('a mount with no row to land on is listed, never credited and never given a (no axis) row', () => {
  const computed = miniRun(`export const ZzNoVariant = {}\n`, {
    'zz-no-variant': miniEntry('ZzNoVariant', miniRecord([placedInstance('Button', null, 'md')])),
  })
  assert.deepEqual(creditsOf(computed, 'ZzNoVariant'), [])
  assert.deepEqual(
    computed.unkeyedMounts.map((u) => [u.exportName, u.reason]),
    [
      [
        'ZzNoVariant',
        'Button rendered with no variant (none passed, no default), so no row of its matrix is keyed by it',
      ],
    ],
  )
})

test('play-driven focus (record 3 and record 1): a play() asserting focus leaves an unresolved note at the instance and the element the browser says held focus, never a cover', () => {
  const stories = `export const ZzFocused = {
    play: async ({ canvasElement }) => {
      const button = within(canvasElement).getByRole('button')
      button.focus()
      await expect(button).toHaveFocus()
    },
  }\n`
  const focus = { stamp: MINI_BUTTON_STAMP, placedBy: placedInstance('Button', 'ghost', 'md') }
  const computed = miniRun(stories, {
    'zz-focused': miniEntry('ZzFocused', {
      mounts: [placedInstance('Button', 'ghost', 'md')],
      focus,
    }),
  })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'ghost|md')
  assert.deepEqual(row.focusVisible, [
    'unresolved: Button:ZzFocused (play-driven; frame not provable statically)',
  ])
  assert.deepEqual(row.rest, ['none'])
  const element = computed.localElements.find((c) => c.componentKey === 'primitives/Button')
    .elements[0]
  assert.match(
    element.coveredBy.focusVisible[0],
    /^unresolved: .*ZzFocused \(play-driven; frame not provable statically\)$/,
  )
  assert.deepEqual(creditsOf(computed, 'ZzFocused'), [])
})

test('a forced story credits a record-1 element of another component under its qualified label, and a story of its own component under its bare name', () => {
  const componentDirs = [
    { segment: 'primitives', name: 'Button' },
    { segment: 'composites', name: 'Card' },
  ]
  const computed = miniRun(
    `export const ZzOwnHover = { parameters: { visualForceState: { state: 'hover', role: 'button' } } }\n`,
    {
      'zz-own': miniEntry(
        'ZzOwnHover',
        miniRecord([placedInstance('Button', 'secondary', 'md')], {
          count: 1,
          stamp: MINI_BUTTON_STAMP,
          placedBy: placedInstance('Button', 'secondary', 'md'),
        }),
      ),
      'zz-card': manifestEntry(
        'src/composites/Card/Card.stories.tsx',
        'ZzCardHover',
        miniRecord([placedInstance('Button', 'secondary', 'md')], {
          count: 1,
          stamp: MINI_BUTTON_STAMP,
          placedBy: placedInstance('Button', 'secondary', 'md'),
        }),
      ),
    },
    {
      componentDirs,
      extra: [
        [srcFile('composites/Card/index.tsx'), `export function Card() { return <div /> }\n`],
        [
          srcFile('composites/Card/Card.stories.tsx'),
          `import { Card } from './index'\nconst meta = { component: Card }\nexport default meta\nexport const ZzCardHover = { parameters: { visualForceState: { state: 'hover', role: 'button' } } }\n`,
        ],
      ],
    },
  )
  const button = computed.localElements.find((c) => c.componentKey === 'primitives/Button')
    .elements[0]
  assert.deepEqual(button.coveredBy.hover, ['ZzOwnHover', 'Card:ZzCardHover'])
  assert.deepEqual(computed.unaccountedForceStates.missing, [])
})

// ---- The element cells, on hand-built entries: stamp credit, play-click, cascade, Disabled -------

const elementFixture = (extra = {}) => ({
  tag: 'button',
  role: null,
  tabIndex: null,
  ariaHidden: false,
  isHelper: false,
  text: '',
  file: 'Tooltip/index.tsx',
  line: 259,
  active: null,
  ...extra,
})

test('buildElementMatrix (record 1): a forced story credits the element at its stamp and no other, whatever the roles and names', () => {
  const elements = [elementFixture({ line: 10 }), elementFixture({ line: 20 })]
  const rows = buildElementMatrix(elements, [
    { exportName: 'Hover', forced: { state: 'hover' }, credit: { stamp: 'Tooltip/index.tsx:20' } },
    {
      exportName: 'Refused',
      forced: { state: 'active' },
      credit: null,
      refusal: 'no element matched',
    },
  ])
  assert.deepEqual(rows[0].hover, ['none'])
  assert.deepEqual(rows[1].hover, ['Hover'])
  assert.deepEqual(rows[1].active, ['none'], 'a refused story credits nothing')
})

test('buildElementMatrix (record 1): hover and active cascade from a credited descendant to an ancestor that paints them, and focus-visible does not', () => {
  const parent = elementFixture({
    tag: 'tr',
    line: 5,
    nodeStart: 0,
    nodeEnd: 100,
    hover: 'hover:bg-x',
    active: 'active:bg-y',
    focusVisible: null,
  })
  const child = elementFixture({ tag: 'a', line: 6, nodeStart: 10, nodeEnd: 50 })
  const rows = buildElementMatrix(
    [parent, child],
    [
      {
        exportName: 'RowLinkHover',
        forced: { state: 'hover' },
        credit: { stamp: 'Tooltip/index.tsx:6' },
      },
      {
        exportName: 'RowLinkActive',
        forced: { state: 'active' },
        credit: { stamp: 'Tooltip/index.tsx:6' },
      },
      {
        exportName: 'RowLinkFocus',
        forced: { state: 'focus-visible' },
        credit: { stamp: 'Tooltip/index.tsx:6' },
      },
    ],
  )
  assert.deepEqual(rows[0].hover, ['RowLinkHover'])
  assert.deepEqual(rows[0].active, ['RowLinkActive'])
  assert.deepEqual(rows[0].focusVisible, ['none'])
})

test('buildElementMatrix (record 1, static play-click credit): a click credits a state-conditional active cell only when the story rendered the element’s own file', () => {
  const elements = [
    elementFixture({
      activeStateConditional: { identifier: 'pinned', whenTrue: "'a'", whenFalse: "'b'" },
    }),
  ]
  const story = (files) => ({
    exportName: 'Pinned',
    forced: null,
    playClick: { role: 'button', name: null },
    argsLiterals: new Set(),
    files,
  })
  assert.deepEqual(buildElementMatrix(elements, [story(['Tooltip/index.tsx'])])[0].active, [
    'Pinned',
  ])
  assert.deepEqual(buildElementMatrix(elements, [story(['Other/index.tsx'])])[0].active, ['none'])
  assert.deepEqual(buildElementMatrix(elements, [story(undefined)])[0].active, ['none'])
})

test('buildElementMatrix (record 1, Disabled column): a story’s args credit no Disabled cell, whatever the element carries and whatever files the story rendered', () => {
  const elements = [elementFixture({ hasDisabledAttr: true })]
  const story = (files) => ({
    exportName: 'ActionsWithDisabledItem',
    forced: null,
    argsHasDisabledTrue: true,
    files,
  })
  assert.deepEqual(buildElementMatrix(elements, [story(['Tooltip/index.tsx'])])[0].disabled, [
    'none',
  ])
  assert.deepEqual(buildElementMatrix(elements, [story(['Other/index.tsx'])])[0].disabled, ['none'])
})

test('buildAxisMatrix (record 3): forced, play-focus, rest and disabled instances land in their own columns; a real credit outranks a play-driven note', () => {
  const base = {
    primitive: 'Menu',
    kind: 'own-story',
    componentKey: 'primitives/Menu',
    file: 'packages/design-system/src/primitives/Menu/Menu.stories.tsx',
    variant: { value: 'selection', resolved: 'runtime' },
    size: { value: null, resolved: 'n/a' },
  }
  const rows = buildAxisMatrix('Menu', [
    { ...base, storyName: 'Hover', forced: { state: 'hover' }, rest: false },
    { ...base, storyName: 'Focused', forced: null, playFocus: true, rest: false },
    { ...base, storyName: 'Default', forced: null, rest: true },
    { ...base, storyName: 'Loading', forced: null, disabled: true, rest: false },
  ])
  assert.deepEqual(
    rows.map((r) => [r.variantSize, r.rest, r.hover, r.focusVisible, r.active, r.disabled]),
    [
      [
        'selection',
        ['Menu:Default'],
        ['Menu:Hover'],
        ['unresolved: Menu:Focused (play-driven; frame not provable statically)'],
        ['none'],
        ['Menu:Loading'],
      ],
    ],
  )
  const outranked = buildAxisMatrix('Menu', [
    { ...base, storyName: 'FocusVisible', forced: { state: 'focus-visible' }, rest: false },
    { ...base, storyName: 'Focused', forced: null, playFocus: true, rest: false },
  ])
  assert.deepEqual(outranked[0].focusVisible, ['Menu:FocusVisible'])
})

test('the region legend names what is still static and what the manifest decides', () => {
  assert.match(REGION_LEGEND, /state-coverage-runtime\.json/)
  assert.match(REGION_LEGEND, /Still static/)
  assert.match(REGION_LEGEND, /`play\(\)`-click credit/)
  assert.match(REGION_LEGEND, /prints as `N credits`/)
  assert.doesNotMatch(REGION_LEGEND, /real call sites/)
  assert.ok(renderGeneratedRegion(FIXTURE_COMPUTED).includes(REGION_LEGEND))
})

test('the committed manifest and the source agree: the real tree has no manifest problem, no refused forced story and no partial refusal', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest: readManifest().manifest,
  })
  assert.deepEqual(computed.manifestProblems, [])
  assert.deepEqual(computed.unaccountedForceStates.missing, [])
  assert.deepEqual(computed.partialRefusals, [])
  assert.deepEqual(computed.unkeyedMounts, [])
})

test('findUnaccountedForceStates (via computeStateCoverage, record 1): an uncredited Hover is reported although a credited Hover of another component is in the region (T684, from the manifest)', () => {
  const index = `export function Notice() {\n  return <a href="/a" className="hover:underline">Notice</a>\n}\n`
  const stories = `import { Notice } from './index'\nconst meta = { component: Notice }\nexport default meta\nexport const Hover = { parameters: { visualForceState: { state: 'hover', role: 'link' } } }\n`
  const componentDirs = [
    { segment: 'primitives', name: 'Notice' },
    { segment: 'primitives', name: 'Plain' },
  ]
  const filesByPath = new Map([
    [srcFile('primitives/Notice/index.tsx'), index],
    [srcFile('primitives/Notice/Notice.stories.tsx'), stories],
    [srcFile('primitives/Plain/index.tsx'), index.replace('Notice', 'Plain')],
    [srcFile('primitives/Plain/Plain.stories.tsx'), stories.replaceAll('Notice', 'Plain')],
  ])
  const stamp = `${STAMP_ROOT}primitives/Notice/index.tsx:2`
  const entry = (file, record) => manifestEntry(`src/primitives/${file}`, 'Hover', record)
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    manifest: {
      'notice--hover': entry('Notice/Notice.stories.tsx', {
        mounts: [],
        force: { count: 1, stamp, placedBy: null },
      }),
      'plain--hover': entry('Plain/Plain.stories.tsx', {
        mounts: [],
        force: { count: 0, stamp: null, placedBy: null },
      }),
    },
  })
  const notice = computed.localElements.find((c) => c.componentKey === 'primitives/Notice')
  assert.deepEqual(notice.elements[0].coveredBy.hover, ['Hover'])
  const plain = computed.localElements.find((c) => c.componentKey === 'primitives/Plain')
  assert.deepEqual(plain.elements[0].coveredBy.hover, ['none'])
  assert.equal(computed.unaccountedForceStates.missing.length, 1)
  assert.deepEqual(
    [
      computed.unaccountedForceStates.missing[0].componentKey,
      computed.unaccountedForceStates.missing[0].exportName,
    ],
    ['primitives/Plain', 'Hover'],
  )
  assert.match(
    describeMissingForceState(computed.unaccountedForceStates.missing[0]),
    /no element matched the force at 375px, 768px, 1280px/,
  )
})

// ---- T694 review remediation: what a story file, a clip, a disabled target and a manifest shape credit ----
//
// Every plant below is red against the pre-remediation check (the commit's hand-back lists each one's
// failing output) and each has a contrast that is still credited after.

const BUTTON_STORIES_HEADER = `import { Button } from './index'\nconst meta = { component: Button }\nexport default meta\n`
const CARD_STORIES = 'composites/Card/Card.stories.tsx'
const CARD_INDEX = 'composites/Card/index.tsx'
const CARD_INDEX_FILE = `${STAMP_ROOT}${CARD_INDEX}`
const CARD_DIRS = [
  { segment: 'primitives', name: 'Button' },
  { segment: 'composites', name: 'Card' },
]
const cardStoriesSource = (stories, meta = `{ component: Card }`) =>
  `import { Card } from './index'\nimport { Button } from '../../primitives/Button'\nconst meta = ${meta}\nexport default meta\n${stories}`

// A tree of the `Button` primitive and a `Card` composite, each story of `Card` read as the manifest
// entries say it rendered.
function cardRun({
  cardIndex = 'export function Card() { return <div /> }\n',
  stories,
  meta,
  manifest,
}) {
  const filesByPath = new Map([
    [srcFile('primitives/Button/index.tsx'), MINI_BUTTON],
    [srcFile(MINI_STORIES), BUTTON_STORIES_HEADER],
    [srcFile(CARD_INDEX), cardIndex],
    [srcFile(CARD_STORIES), cardStoriesSource(stories, meta)],
  ])
  return computeStateCoverage({ componentDirs: CARD_DIRS, filesByPath, manifest })
}
const cardEntry = (exportName, record, files = [CARD_INDEX_FILE]) =>
  manifestEntry(`src/${CARD_STORIES}`, exportName, record, files)
const mentionsCard = (computed) => JSON.stringify(computed.matrices.Button).includes('Card')

// ---- B1: a tracked primitive written in a story file credits nothing; only the manifest's mounts do ----

for (const [name, story, mounts] of [
  [
    'JSX under an args key the render never passes',
    `export const ZzArgsKey = { args: { action: <Button variant="ghost" size="lg" href="/x" disabled>Go</Button> }, render: () => <div>nothing</div> }\n`,
    [],
  ],
  [
    'href with disabled (the browser renders an enabled link, so the instance has no disabled element)',
    `export const ZzHrefDisabled = { render: () => <Button variant="ghost" size="lg" href="/x" disabled>Go</Button> }\n`,
    [placedInstance('Button', 'ghost', 'lg', [])],
  ],
  [
    'a tag in a branch that is never reached',
    `export const ZzUnreached = { render: () => <div>{false && <Button variant="ghost" size="lg" disabled>Go</Button>}</div> }\n`,
    [],
  ],
  [
    'a literal loading',
    `export const ZzLoading = { args: { action: <Button variant="ghost" size="lg" loading>Go</Button> }, render: () => <div>nothing</div> }\n`,
    [],
  ],
  [
    'the Rest column of the same call site',
    `export const ZzRest = { render: () => <div>{false && <Button variant="primary" size="lg">Go</Button>}</div> }\n`,
    [],
  ],
]) {
  test(`B1 plant: ${name} credits no cell of Button's matrix`, () => {
    const exportName = story.match(/export const (\w+)/)[1]
    const computed = cardRun({
      stories: story,
      manifest: { 'zz-b1': cardEntry(exportName, { mounts }) },
    })
    assert.equal(mentionsCard(computed), false, JSON.stringify(computed.matrices.Button))
    assert.deepEqual(computed.manifestProblems, [])
  })
}

test('B1 contrast: a design-system component call site keeps its Rest credit and gives no Disabled credit, literal disabled and literal loading both', () => {
  const cardIndex = `export function Card() {
  return (
    <div>
      <Button variant="ghost" size="lg" disabled>A</Button>
      <Button variant="primary" size="lg" loading>B</Button>
      <Button variant="secondary" size="md">C</Button>
    </div>
  )
}
`
  const computed = cardRun({ cardIndex, stories: '', manifest: {} })
  const row = (key) => computed.matrices.Button.find((r) => r.variantSize === key)
  assert.deepEqual(row('ghost|lg').rest, [`composites/Card (${CARD_INDEX_FILE}:4)`])
  assert.deepEqual(row('ghost|lg').disabled, ['none'])
  assert.deepEqual(row('primary|lg').rest, [`composites/Card (${CARD_INDEX_FILE}:5)`])
  assert.deepEqual(row('primary|lg').disabled, ['none'])
  assert.deepEqual(row('secondary|md').rest, [`composites/Card (${CARD_INDEX_FILE}:6)`])
  assert.deepEqual(row('secondary|md').disabled, ['none'])
})

// A component file no story renders, with a Button written disabled in one branch and loading in the
// other: nothing the browser rendered, so no Disabled credit (the Disabled column is the manifest's).
test('B1 plant: a call site in a component file no story renders, written disabled or loading, credits no Disabled cell; contrast: a manifest mount with a disabled element does', () => {
  const pending = `export function Pending({ pending }) {
  return pending ? (
    <Button variant="destructive" size="md" disabled>Saving</Button>
  ) : (
    <Button variant="destructive" size="md" href="/x" loading>Save</Button>
  )
}
`
  const run = (manifest) =>
    computeStateCoverage({
      componentDirs: CARD_DIRS,
      filesByPath: new Map([
        [srcFile('primitives/Button/index.tsx'), MINI_BUTTON],
        [srcFile(MINI_STORIES), BUTTON_STORIES_HEADER],
        [srcFile(CARD_INDEX), 'export function Card() { return <div /> }\n'],
        [srcFile('composites/Card/Pending.tsx'), pending],
        [
          srcFile(CARD_STORIES),
          cardStoriesSource('export const ZzRenders = { render: () => <Card /> }\n'),
        ],
      ]),
      manifest,
    })
  const row = (computed) => computed.matrices.Button.find((r) => r.variantSize === 'destructive|md')
  const none = run({ 'zz-renders': cardEntry('ZzRenders', { mounts: [] }) })
  assert.deepEqual(row(none).disabled, ['none'])
  assert.equal(row(none).rest.length, 2, 'both call sites still credit Rest')
  const mounted = run({
    'zz-renders': cardEntry('ZzRenders', {
      mounts: [placedInstance('Button', 'destructive', 'md', [MINI_BUTTON_STAMP])],
    }),
  })
  assert.deepEqual(row(mounted).disabled, ['Card:ZzRenders'])
})

test('B1 contrast: the same primitive mounted disabled in a story is credited through the manifest mount', () => {
  const computed = cardRun({
    stories: `export const ZzMounted = { render: () => <Button variant="ghost" size="lg" disabled>Go</Button> }\n`,
    manifest: {
      'zz-mounted': cardEntry('ZzMounted', {
        mounts: [placedInstance('Button', 'ghost', 'lg', [MINI_BUTTON_STAMP])],
      }),
    },
  })
  assert.deepEqual(creditsOf(computed, 'ZzMounted'), ['Button|ghost|lg|disabled'])
})

test('B1 contrast (real tree): ErrorState:RetryInProgress credits Button secondary|md Disabled through its mounts, and its story-file call site no longer does', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest: readManifest().manifest,
  })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'secondary|md')
  assert.deepEqual(row.disabled, ['ErrorState:RetryInProgress'])
  assert.equal(JSON.stringify(computed.matrices).includes('.stories.tsx:'), false)
})

// ---- B2: a story that declares a visualCaptureClip gives no mount credit ----------------------------

const CLIP = `{ parts: [{ role: 'checkbox' }] }`
const disabledMount = placedInstance('Button', 'secondary', 'md', [MINI_BUTTON_STAMP])

test('B2 plant: a clipped own-story mounting a disabled Button credits neither Disabled nor Rest; contrast: the same story unclipped credits both', () => {
  const run = (parameters) =>
    miniRun(`export const ZzClip = { args: { disabled: true }${parameters} }\n`, {
      'zz-clip': miniEntry('ZzClip', miniRecord([disabledMount])),
    })
  assert.deepEqual(creditsOf(run(`, parameters: { visualCaptureClip: ${CLIP} }`), 'ZzClip'), [])
  assert.deepEqual(creditsOf(run(''), 'ZzClip'), [
    'Button|secondary|md|disabled',
    'Button|secondary|md|rest',
  ])
})

test('B2 plant: a clipped story composing a disabled Button (AccountErasurePanel:AcknowledgementCheckboxFocusVisible’s shape) credits no Disabled cell; contrast: unclipped credits it', () => {
  const story = (parameters) =>
    `export const ZzComposed = { render: () => <Button disabled>Go</Button>${parameters} }\n`
  const run = (parameters) =>
    cardRun({
      stories: story(parameters),
      manifest: { 'zz-composed': cardEntry('ZzComposed', { mounts: [disabledMount] }) },
    })
  assert.deepEqual(creditsOf(run(`, parameters: { visualCaptureClip: ${CLIP} }`), 'ZzComposed'), [])
  assert.deepEqual(creditsOf(run(''), 'ZzComposed'), ['Button|secondary|md|disabled'])
})

test('B2 siblings: a clip on the default export, and a parameters object this pass cannot read in full, are clips too', () => {
  const run = (meta, story) =>
    cardRun({
      meta,
      stories: story,
      manifest: { 'zz-sib': cardEntry('ZzSib', { mounts: [disabledMount] }) },
    })
  const plain = `export const ZzSib = { render: () => <Button disabled>Go</Button> }\n`
  assert.deepEqual(
    creditsOf(
      run(`{ component: Card, parameters: { visualCaptureClip: ${CLIP} } }`, plain),
      'ZzSib',
    ),
    [],
  )
  assert.deepEqual(
    creditsOf(
      run(
        `{ component: Card }`,
        `const shared = {}\nexport const ZzSib = { parameters: { ...shared }, render: () => <Button disabled>Go</Button> }\n`,
      ),
      'ZzSib',
    ),
    [],
  )
  assert.deepEqual(creditsOf(run(`{ component: Card, parameters: {} }`, plain), 'ZzSib'), [
    'Button|secondary|md|disabled',
  ])
})

test('B2: a clipped forced story keeps its forced credit and gives no Disabled or Rest from its mounts', () => {
  const placed = placedInstance('Button', 'ghost', 'md')
  const run = (parameters) =>
    cardRun({
      stories: `export const ZzForced = { render: () => <Button>Go</Button>, parameters: { visualForceState: { state: 'hover', role: 'button' }${parameters} } }\n`,
      manifest: {
        'zz-forced': cardEntry('ZzForced', {
          mounts: [placed, disabledMount],
          force: { count: 1, stamp: MINI_BUTTON_STAMP, placedBy: placed },
        }),
      },
    })
  const forcedOnly = ['Button|ghost|md|hover', `record1|${MINI_BUTTON_STAMP}|hover`]
  assert.deepEqual(creditsOf(run(`, visualCaptureClip: ${CLIP}`), 'ZzForced'), forcedOnly)
  assert.deepEqual(creditsOf(run(''), 'ZzForced'), [
    'Button|ghost|md|hover',
    'Button|secondary|md|disabled',
    `record1|${MINI_BUTTON_STAMP}|hover`,
  ])
})

const TABS_DIRS = [{ segment: 'primitives', name: 'Tabs' }]
const TABS_INDEX = `export function Tabs({ disabled }) {
  return <button type="button" disabled={disabled} className="hover:bg-surface-sunken" />
}
`
function tabsRun(storyBody, meta = '{ component: Tabs }') {
  return computeStateCoverage({
    componentDirs: TABS_DIRS,
    filesByPath: new Map([
      [srcFile('primitives/Tabs/index.tsx'), TABS_INDEX],
      [
        srcFile('primitives/Tabs/Tabs.stories.tsx'),
        `import { Tabs } from './index'\nconst meta = ${meta}\nexport default meta\n${storyBody}`,
      ],
    ]),
    manifest: {
      'zz-tabs': manifestEntry(
        'src/primitives/Tabs/Tabs.stories.tsx',
        'ZzDisabledArgs',
        {
          mounts: [],
        },
        [`${STAMP_ROOT}primitives/Tabs/index.tsx`],
      ),
    },
  })
}

test('B2 (record 1) plant: a `disabled: true` in a story’s args — top-level or nested in items — credits no element-matrix Disabled cell, clipped or not', () => {
  const clip = `, parameters: { visualCaptureClip: ${CLIP} }`
  for (const args of [`{ disabled: true }`, `{ items: [{ disabled: true }] }`]) {
    for (const parameters of ['', clip]) {
      const computed = tabsRun(`export const ZzDisabledArgs = { args: ${args}${parameters} }\n`)
      assert.deepEqual(computed.matrices.Tabs[0].disabled, ['none'], `${args}${parameters}`)
    }
  }
})

// A file that places an element in `position: fixed`, rendered by a story captured as its root box.
const PANEL_INDEX = 'composites/Panel/index.tsx'
const PANEL_FILE = `${STAMP_ROOT}${PANEL_INDEX}`
function overlayRun({ panel, tags = '' }) {
  const filesByPath = new Map([
    [srcFile('primitives/Button/index.tsx'), MINI_BUTTON],
    [srcFile(MINI_STORIES), BUTTON_STORIES_HEADER],
    [srcFile(CARD_INDEX), 'export function Card() { return <div /> }\n'],
    [srcFile(PANEL_INDEX), panel],
    [
      srcFile(CARD_STORIES),
      cardStoriesSource(
        `export const ZzOverlay = { ${tags} render: () => <Button disabled>Go</Button> }\n`,
      ),
    ],
  ])
  return computeStateCoverage({
    componentDirs: [...CARD_DIRS, { segment: 'composites', name: 'Panel' }],
    filesByPath,
    manifest: {
      'zz-overlay': cardEntry('ZzOverlay', { mounts: [disabledMount] }, [
        CARD_INDEX_FILE,
        PANEL_FILE,
      ]),
    },
  })
}

test('B2 sibling: a root-box story that rendered a position: fixed file gives no mount credit; tagged visual-full-page, or with only a prefixed fixed, it does', () => {
  const fixedPanel = `export function Panel() { return <div className="fixed inset-0" /> }\n`
  assert.deepEqual(creditsOf(overlayRun({ panel: fixedPanel }), 'ZzOverlay'), [])
  assert.deepEqual(
    creditsOf(overlayRun({ panel: fixedPanel, tags: `tags: ['visual-full-page'],` }), 'ZzOverlay'),
    ['Button|secondary|md|disabled'],
  )
  const prefixed = `export function Panel() { return <div className="focus:fixed top-0" /> }\n`
  assert.deepEqual(creditsOf(overlayRun({ panel: prefixed }), 'ZzOverlay'), [
    'Button|secondary|md|disabled',
  ])
})

// ---- B3: a forced state on a disabled target is refused, whatever the state ---------------------------

for (const state of ['hover', 'focus-visible', 'active']) {
  test(`B3 plant: a forced ${state} on a Button the browser reports disabled is refused at record 1 and record 3, its Disabled credit kept`, () => {
    const name = `ZzDisabled${state.replace(/-/g, '')}`
    const computed = miniRun(
      `export const ${name} = { args: { disabled: true }, parameters: { visualForceState: { state: '${state}', role: 'button' } } }\n`,
      {
        'zz-disabled': miniEntry(
          name,
          miniRecord([disabledMount], {
            count: 1,
            stamp: MINI_BUTTON_STAMP,
            placedBy: disabledMount,
          }),
        ),
      },
    )
    assert.deepEqual(stateCreditsOf(computed, name), [])
    assert.deepEqual(creditsOf(computed, name), ['Button|secondary|md|disabled'])
    assert.match(
      refusalOf(computed, 'primitives/Button', name).refusal,
      /^the located element's stamp .*:3 is in its placing Button's disabledAt \(the browser reports it disabled, native or aria-disabled\)/,
    )
  })
}

test('B3 contrast: a forced hover on an enabled Button next to a disabled sibling credits the enabled one', () => {
  const enabled = placedInstance('Button', 'ghost', 'md', [])
  const computed = miniRun(
    `export const ZzBeside = { parameters: { visualForceState: { state: 'hover', role: 'button', name: 'Ghost' } } }\n`,
    {
      'zz-beside': miniEntry(
        'ZzBeside',
        miniRecord([enabled, disabledMount], {
          count: 1,
          stamp: MINI_BUTTON_STAMP,
          placedBy: enabled,
        }),
      ),
    },
  )
  assert.deepEqual(creditsOf(computed, 'ZzBeside'), [
    'Button|ghost|md|hover',
    'Button|secondary|md|disabled',
    `record1|${MINI_BUTTON_STAMP}|hover`,
  ])
})

test('B3: a stamp disabled at one width only is refused too, and disabledAt is read from the DOM as :disabled or aria-disabled="true"', () => {
  const at = (disabledAt) => ({
    mounts: [],
    force: {
      count: 1,
      stamp: MINI_BUTTON_STAMP,
      placedBy: placedInstance('Button', 'ghost', 'md', disabledAt),
    },
  })
  const verdict = resolveRuntimeForce(
    { widths: { 375: at([]), 768: at([MINI_BUTTON_STAMP]), 1280: at([]) } },
    { recordOneKeys: new Set([MINI_BUTTON_STAMP]) },
  )
  assert.ok(verdict.refusal, 'refused')
  assert.equal(verdict.stamp, undefined)
  const reader = readFileSync(
    path.resolve(REPO_SRC_DIR, '..', '..', '..', 'tests', 'visual', 'state-coverage-runtime.ts'),
    'utf8',
  )
  assert.match(
    reader,
    /el\.matches\(':disabled'\) \|\| el\.getAttribute\('aria-disabled'\) === 'true'/,
  )
})

test('B3 residual: an element no tracked primitive placed is credited without knowing whether it renders disabled — the manifest records disabled elements only among a tracked primitive’s own', () => {
  const cardIndex = `export function Card({ disabled }) {
  return (
    <button type="button" disabled={disabled} className="hover:bg-surface-sunken">
      Go
    </button>
  )
}
`
  const stamp = `${CARD_INDEX_FILE}:3`
  const computed = cardRun({
    cardIndex,
    stories: `export const ZzRawHover = { args: { disabled: true }, parameters: { visualForceState: { state: 'hover', role: 'button' } } }\n`,
    manifest: {
      'zz-raw': cardEntry('ZzRawHover', {
        mounts: [],
        force: { count: 1, stamp, placedBy: null },
      }),
    },
  })
  assert.deepEqual(creditsOf(computed, 'ZzRawHover'), [`record1|${stamp}|hover`])
  assert.match(
    REGION_LEGEND,
    /no tracked primitive placed \(a record-1 element of\nanother component\) is credited without knowing whether it renders disabled/,
  )
})

// ---- M1: a manifest entry's shape is checked, and a malformed one fails the check -----------------------

const wellFormedForce = {
  count: 1,
  stamp: MINI_BUTTON_STAMP,
  placedBy: placedInstance('Button', 'secondary', 'md'),
}
const withForce = (force) => ({ widths: atEveryWidth({ mounts: [], force }) })
const MALFORMED_ENTRIES = {
  'a count that is missing': withForce({
    stamp: MINI_BUTTON_STAMP,
    placedBy: wellFormedForce.placedBy,
  }),
  'a null count': withForce({ ...wellFormedForce, count: null }),
  'a string count': withForce({ ...wellFormedForce, count: '1' }),
  'a fractional count': withForce({ ...wellFormedForce, count: 1.5 }),
  'a width missing': {
    widths: Object.fromEntries(
      WIDTHS.slice(1).map((w) => [w, { mounts: [], force: wellFormedForce }]),
    ),
  },
  'an extra width': {
    widths: { ...withForce(wellFormedForce).widths, 1920: { mounts: [], force: wellFormedForce } },
  },
  'empty widths': { widths: {} },
  // The shapes a record's own fields can take (second remediation): each used to credit, or throw.
  'a width record that is null': {
    widths: { ...withForce(wellFormedForce).widths, 768: null },
  },
  'a width record that is not an object': {
    widths: { ...withForce(wellFormedForce).widths, 768: [] },
  },
  'mounts missing': {
    widths: atEveryWidth({ force: wellFormedForce }),
  },
  'mounts that is not an array': {
    widths: atEveryWidth({ mounts: { length: 0 }, force: wellFormedForce }),
  },
  'a mount that is null': {
    widths: atEveryWidth({ mounts: [null], force: wellFormedForce }),
  },
  'a mount with no disabledAt': {
    widths: atEveryWidth({
      mounts: [{ component: 'Button', variant: 'primary', size: 'lg' }],
      force: wellFormedForce,
    }),
  },
  'a mount whose disabledAt is not an array': {
    widths: atEveryWidth({
      mounts: [{ ...placedInstance('Button', 'primary', 'lg'), disabledAt: 3 }],
      force: wellFormedForce,
    }),
  },
  'a mount whose disabledAt holds a non-string': {
    widths: atEveryWidth({
      mounts: [placedInstance('Button', 'primary', 'lg', [3])],
      force: wellFormedForce,
    }),
  },
  'a mount whose variant is not a string': {
    widths: atEveryWidth({
      mounts: [placedInstance('Button', 7, 'lg')],
      force: wellFormedForce,
    }),
  },
  'a mount whose size is missing': {
    widths: atEveryWidth({
      mounts: [{ component: 'Button', variant: 'primary', disabledAt: [] }],
      force: wellFormedForce,
    }),
  },
  'a force at count 1 with no stamp': withForce({ count: 1, placedBy: wellFormedForce.placedBy }),
  'a force at count 1 whose stamp is a number': withForce({ ...wellFormedForce, stamp: 213 }),
  'a placedBy that is a string': withForce({ ...wellFormedForce, placedBy: 'Button' }),
  'a placedBy that is an array': withForce({ ...wellFormedForce, placedBy: [] }),
  'a placedBy with no disabledAt': withForce({
    ...wellFormedForce,
    placedBy: { component: 'Button', variant: 'primary', size: 'lg' },
  }),
  'a placedBy whose disabledAt is not an array of strings': withForce({
    ...wellFormedForce,
    placedBy: { ...placedInstance('Button', 'primary', 'lg'), disabledAt: 'x' },
  }),
  'a placedBy whose variant is not a string': withForce({
    ...wellFormedForce,
    placedBy: placedInstance('Button', { value: 'primary' }, 'lg'),
  }),
  'a placedBy whose size is missing': withForce({
    ...wellFormedForce,
    placedBy: { component: 'Button', variant: 'primary', disabledAt: [] },
  }),
  'a focus record that is not an object': {
    widths: atEveryWidth({ mounts: [], focus: 'x', force: wellFormedForce }),
  },
  'a focus placedBy with a disabledAt that is not an array': {
    widths: atEveryWidth({
      mounts: [],
      focus: {
        stamp: null,
        placedBy: { ...placedInstance('Button', 'primary', 'lg'), disabledAt: 1 },
      },
      force: wellFormedForce,
    }),
  },
}

for (const [name, entry] of Object.entries(MALFORMED_ENTRIES)) {
  test(`M1 plant: ${name} is a malformed entry, not a credit and not a silent refusal`, () => {
    const verdict = resolveRuntimeForce(entry, { recordOneKeys: new Set([MINI_BUTTON_STAMP]) })
    assert.equal(typeof verdict.malformed, 'string', JSON.stringify(verdict))
    assert.equal(verdict.stamp, undefined)
    assert.equal(verdict.refusal, undefined)
    const computed = miniRun(
      `export const ZzShape = { parameters: { visualForceState: { state: 'hover', role: 'button' } } }\n`,
      {
        'zz-shape': {
          ...entry,
          importPath: `./src/${MINI_STORIES}`,
          exportName: 'ZzShape',
          files: [BUTTON_FILE],
        },
      },
    )
    assert.deepEqual(
      computed.manifestProblems.map((p) => [p.kind, p.location]),
      [['malformed-entry', 'src/primitives/Button/Button.stories.tsx:ZzShape']],
    )
    assert.match(computed.manifestProblems[0].detail, /story ZzShape of /)
    assert.ok(computed.manifestProblems[0].detail.includes(REWRITE_COMMAND))
    assert.deepEqual(creditsOf(computed, 'ZzShape'), [])
  })
}

test('M1: the widths an entry must record are the capture’s own, from review-widths, never a copy', () => {
  assert.deepEqual(WIDTHS, REVIEW_WIDTHS.map(String))
  const source = readFileSync(
    path.join(REPO_SRC_DIR, '..', '..', '..', 'scripts', 'checks', 'state-coverage.mjs'),
    'utf8',
  )
  assert.match(source, /from '\.\.\/visual\/review-widths\.mjs'/)
  assert.doesNotMatch(source, /\b375\b/)
})

test('M1: a width missing from a story that forces nothing is malformed too', () => {
  const computed = miniRun(`export const ZzMounts = {}\n`, {
    'zz-mounts': {
      importPath: `./src/${MINI_STORIES}`,
      exportName: 'ZzMounts',
      files: [BUTTON_FILE],
      widths: { 375: { mounts: [placedInstance('Button', 'primary', 'lg')] } },
    },
  })
  assert.deepEqual(
    computed.manifestProblems.map((p) => p.kind),
    ['malformed-entry'],
  )
  assert.deepEqual(creditsOf(computed, 'ZzMounts'), [])
})

test('M1 contrast: a well-formed entry credits', () => {
  const verdict = resolveRuntimeForce(withForce(wellFormedForce), {
    recordOneKeys: new Set([MINI_BUTTON_STAMP]),
  })
  assert.equal(verdict.malformed, undefined)
  assert.equal(verdict.refusal, undefined)
  assert.equal(verdict.stamp, MINI_BUTTON_STAMP)
})

// ---- M4: a fixture is a story with the fixture tag, wherever it sits -----------------------------------

const FIXTURE_FORCE = `parameters: { visualForceState: { state: 'hover', role: 'button' } }`
const fixtureRun = ({ meta, story }) =>
  cardRun({
    meta,
    stories: story,
    manifest: {
      'zz-fixture': cardEntry('ZzTagged', {
        mounts: [placedInstance('Button', 'ghost', 'md')],
        force: {
          count: 1,
          stamp: MINI_BUTTON_STAMP,
          placedBy: placedInstance('Button', 'ghost', 'md'),
        },
      }),
    },
  })

test('M4 plant: a tagged story under packages/design-system/src credits nothing, whether the tag is on the default export or on the story', () => {
  for (const [meta, story] of [
    [
      `{ component: Card, tags: ['state-coverage-fixture', '!dev'] }`,
      `export const ZzTagged = { ${FIXTURE_FORCE} }\n`,
    ],
    [
      `{ component: Card }`,
      `export const ZzTagged = { tags: ['state-coverage-fixture'], ${FIXTURE_FORCE} }\n`,
    ],
    [
      `{ title: 'Zz' , tags: ['state-coverage-fixture'] }`,
      `export const ZzTagged = { ${FIXTURE_FORCE} }\n`,
    ],
  ]) {
    const computed = fixtureRun({ meta, story })
    assert.deepEqual(creditsOf(computed, 'ZzTagged'), [], meta)
    assert.deepEqual(computed.unaccountedForceStates.missing, [], meta)
    assert.deepEqual(computed.manifestProblems, [], meta)
  }
})

test('M4 contrast: the same story untagged, or with the tag removed by !, is credited', () => {
  const credited = ['Button|ghost|md|hover', `record1|${MINI_BUTTON_STAMP}|hover`]
  const story = `export const ZzTagged = { ${FIXTURE_FORCE} }\n`
  assert.deepEqual(
    creditsOf(fixtureRun({ meta: `{ component: Card }`, story }), 'ZzTagged'),
    credited,
  )
  assert.deepEqual(
    creditsOf(
      fixtureRun({
        meta: `{ component: Card, tags: ['state-coverage-fixture'] }`,
        story: `export const ZzTagged = { tags: ['!state-coverage-fixture'], ${FIXTURE_FORCE} }\n`,
      }),
      'ZzTagged',
    ),
    credited,
  )
})

test('M4: a tags this pass cannot read as string literals fails the check, naming the story', () => {
  const computed = fixtureRun({
    meta: `{ component: Card }`,
    story: `const tags = ['x']\nexport const ZzTagged = { tags, ${FIXTURE_FORCE} }\n`,
  })
  assert.deepEqual(
    computed.manifestProblems.map((p) => [p.kind, p.location]),
    [['unreadable-tags', 'src/composites/Card/Card.stories.tsx:ZzTagged']],
  )
})

// ---- M2: the legend names exactly the credits that stay static ----------------------------------------

test('M2: the region legend names each static credit, builds its list from them and lists no other', async () => {
  const { STATIC_CREDITS } = await import('./state-coverage.mjs')
  assert.deepEqual(
    STATIC_CREDITS.map((c) => c.id),
    ['call-site-rest', 'play-click', 'play-focus', 'ancestor-inheritance'],
  )
  const listed = REGION_LEGEND.split('**Still static, and read from source:**')[1]
    .split('**Residual gaps')[0]
    .split('\n')
    .filter((line) => line.startsWith('- '))
  assert.deepEqual(
    listed,
    STATIC_CREDITS.map((c) => `- ${c.legend}`),
  )
  // The Disabled column has no static credit, and the legend says so in the place it names the source.
  assert.doesNotMatch(listed.join('\n'), /disabled/i)
  assert.match(
    REGION_LEGEND,
    /The Disabled column of every matrix, and a primitive's own stories' Rest column, come from\nthe primitive instances a story mounts, as rendered, and from nothing else: a `disabled` or `loading`\nwritten at a call site, and a `disabled: true` in a story's `args`, credit no Disabled cell\./,
  )
})

test('M2: the credits that stay static are still given — Rest’s call sites in component files — and the two deleted Disabled paths are gone from the real tree', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    manifest: readManifest().manifest,
  })
  const row = computed.matrices.Button.find((r) => r.variantSize === 'primary|lg')
  assert.ok(row.rest.some((entry) => /\/index\.tsx:\d+\)$/.test(entry)))
  const mjs = readFileSync(
    path.join(REPO_SRC_DIR, '..', '..', '..', 'scripts', 'checks', 'state-coverage.mjs'),
    'utf8',
  )
  assert.doesNotMatch(mjs, /argsHasDisabledTrue|argsObjectHasDisabledTrue|call-site-disabled/)
})

// ---- Second remediation: cut claims. Each plant below credited (or threw) before; each has a contrast ----

// A `Button` whose own source exports the union types the pass reads the known rows from. The types
// follow the component so every stamp in `MINI_BUTTON` keeps its line.
const TYPED_BUTTON = `${MINI_BUTTON}export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
export type ButtonSize = 'md' | 'lg'
`

test('M1 plant: an instance at a row the primitive does not have (placedBy or mount) is malformed and opens no row; contrast: a known row is credited', () => {
  const run = (placed, mounts) =>
    computeStateCoverage({
      componentDirs: [{ segment: 'primitives', name: 'Button' }],
      filesByPath: new Map([
        [srcFile('primitives/Button/index.tsx'), TYPED_BUTTON],
        [
          srcFile(MINI_STORIES),
          `${BUTTON_STORIES_HEADER}export const ZzRow = { parameters: { visualForceState: { state: 'hover', role: 'button' } } }\n`,
        ],
      ]),
      manifest: {
        'zz-row': miniEntry(
          'ZzRow',
          miniRecord(mounts, { count: 1, stamp: MINI_BUTTON_STAMP, placedBy: placed }),
        ),
      },
    })
  const unknown = placedInstance('Button', 'zz-invented', 'md')
  for (const [name, computed] of [
    ['placedBy', run(unknown, [])],
    [
      'mount',
      run(placedInstance('Button', 'ghost', 'md'), [placedInstance('Button', 'ghost', 'xl')]),
    ],
  ]) {
    assert.deepEqual(
      computed.manifestProblems.map((p) => [p.kind, p.location]),
      [['malformed-entry', 'src/primitives/Button/Button.stories.tsx:ZzRow']],
      name,
    )
    assert.match(computed.manifestProblems[0].detail, /which is none of Button's own/, name)
    assert.equal(JSON.stringify(computed.matrices.Button).includes('zz-invented'), false, name)
    assert.equal(JSON.stringify(computed.matrices.Button).includes('xl'), false, name)
    assert.deepEqual(creditsOf(computed, 'ZzRow'), [], name)
  }
  const ok = run(placedInstance('Button', 'destructive', 'lg'), [])
  assert.deepEqual(ok.manifestProblems, [])
  assert.deepEqual(creditsOf(ok, 'ZzRow'), [
    'Button|destructive|lg|hover',
    `record1|${MINI_BUTTON_STAMP}|hover`,
  ])
})

test('M1 contrast: a force whose stamp is the explicit null of an element no file stamped, and a placedBy of null, are well-formed', () => {
  const entry = withForce({ count: 1, stamp: null, placedBy: null })
  assert.equal(entryShapeProblem(entry, { forced: true }), null)
  assert.match(
    resolveRuntimeForce(entry, { recordOneKeys: new Set() }).refusal,
    /carries no source stamp/,
  )
  // Menu rendered with no variant is a recorded `null`, a note and no row — not a malformed entry.
  const menu = withForce({ count: 1, stamp: null, placedBy: placedInstance('Menu', null, null) })
  assert.equal(entryShapeProblem(menu, { forced: true }), null)
})

test('M1 contrast: every entry of the committed manifest is well-formed, and each primitive’s axis values are read from its own types', () => {
  const { componentDirs, filesByPath, storyFilesByPath } = readAllSourceFiles()
  const manifest = readManifest().manifest
  const known = {}
  for (const name of PRIMITIVE_NAMES) {
    const [file, text] = [...filesByPath].find(([f]) =>
      f.endsWith(`${path.sep}primitives${path.sep}${name}${path.sep}index.tsx`),
    )
    known[name] = readAxisValues(parseTsx(file, text), name)
    for (const axis of PRIMITIVE_AXES[name]) {
      assert.ok(known[name][axis]?.size > 0, `${name}'s ${axis} type is read`)
    }
  }
  assert.deepEqual([...known.Button.variant].sort(), [
    'destructive',
    'ghost',
    'primary',
    'secondary',
  ])
  const problems = Object.entries(manifest).flatMap(([id, entry]) => {
    const problem = entryShapeProblem(entry, { forced: true, knownAxisValues: known })
    return problem ? [`${id}: ${problem}`] : []
  })
  assert.deepEqual(problems, [])
  const computed = computeStateCoverage({ componentDirs, filesByPath, storyFilesByPath, manifest })
  assert.deepEqual(
    computed.manifestProblems.filter((p) => p.kind === 'malformed-entry'),
    [],
  )
})

// ---- A spread in the owner object: its clip and its tags cannot be read ----

const SPREAD_CLIP = `{ parameters: { visualCaptureClip: ${CLIP} } }`
const spreadProblems = (computed) =>
  computed.manifestProblems.map((p) => [p.kind, p.location.split(':').pop()])

test('B2 plant: a story object that spreads a clipped story gets no mount credit and unreadable tags; contrast: no spread and no clip credits its mounts', () => {
  const run = (stories) =>
    cardRun({
      stories,
      manifest: {
        'zz-a': cardEntry('ZzA', { mounts: [disabledMount] }),
        'zz-b': cardEntry('ZzB', { mounts: [disabledMount] }),
      },
    })
  const spread = run(
    `export const ZzA = { parameters: { visualCaptureClip: ${CLIP} }, render: () => <Button disabled>Go</Button> }\nexport const ZzB = { ...ZzA }\n`,
  )
  assert.deepEqual(creditsOf(spread, 'ZzB'), [])
  assert.deepEqual(spreadProblems(spread), [['unreadable-tags', 'ZzB']])
  const plain = run(
    `export const ZzA = { render: () => <Button disabled>Go</Button> }\nexport const ZzB = { render: () => <Button disabled>Go</Button> }\n`,
  )
  assert.deepEqual(creditsOf(plain, 'ZzB'), ['Button|secondary|md|disabled'])
  assert.deepEqual(plain.manifestProblems, [])
})

test('B2 plant: a default export that spreads a clipped object gets no mount credit and unreadable tags, and a tag arriving by that spread is not read as absent', () => {
  const run = (stories, name = 'ZzSib') =>
    cardRun({
      meta: `{ ...BASE, component: Card }`,
      stories,
      manifest: { 'zz-sib': cardEntry(name, { mounts: [disabledMount] }) },
    })
  const clipped = run(
    `const BASE = ${SPREAD_CLIP}\nexport const ZzSib = { render: () => <Button disabled>Go</Button> }\n`,
  )
  assert.deepEqual(creditsOf(clipped, 'ZzSib'), [])
  assert.deepEqual(spreadProblems(clipped), [['unreadable-tags', 'ZzSib']])
  const tagged = run(
    `const BASE = { tags: ['state-coverage-fixture'] }\nexport const ZzTagged = { ${FIXTURE_FORCE} }\n`,
    'ZzTagged',
  )
  assert.deepEqual(spreadProblems(tagged), [['unreadable-tags', 'ZzTagged']])
})

test('B2 contrast: a default export with no spread, whatever else it carries, credits its stories’ mounts', () => {
  const computed = cardRun({
    meta: `{ component: Card, tags: ['autodocs'], args: {} }`,
    stories: `export const ZzSib = { render: () => <Button disabled>Go</Button> }\n`,
    manifest: { 'zz-sib': cardEntry('ZzSib', { mounts: [disabledMount] }) },
  })
  assert.deepEqual(creditsOf(computed, 'ZzSib'), ['Button|secondary|md|disabled'])
  assert.deepEqual(computed.manifestProblems, [])
})

// ---- Mutation gaps: each guard has a test that fails without it ----

const OTHER_DISABLED_STAMP = `${BUTTON_FILE}:99`
const forcedRun = ({ placed, parameters = '', mounts = [placed] }) =>
  cardRun({
    stories: `export const ZzForced = { render: () => <Button>Go</Button>, parameters: { visualForceState: { state: 'hover', role: 'button' }${parameters} } }\n`,
    manifest: {
      'zz-forced': cardEntry('ZzForced', {
        mounts,
        force: { count: 1, stamp: MINI_BUTTON_STAMP, placedBy: placed },
      }),
    },
  })

test('B2: a clipped forced story whose placing instance itself has a disabled element credits no Disabled; unclipped it does', () => {
  const placed = placedInstance('Button', 'ghost', 'md', [OTHER_DISABLED_STAMP])
  const forcedOnly = ['Button|ghost|md|hover', `record1|${MINI_BUTTON_STAMP}|hover`]
  assert.deepEqual(
    creditsOf(forcedRun({ placed, parameters: `, visualCaptureClip: ${CLIP}` }), 'ZzForced'),
    forcedOnly,
  )
  assert.deepEqual(creditsOf(forcedRun({ placed }), 'ZzForced'), [
    'Button|ghost|md|disabled',
    ...forcedOnly,
  ])
})

test('B3 contrast: a forced enabled element is still credited when its placing instance has a disabled element at another stamp — the refusal is by stamp, not by instance', () => {
  const placed = placedInstance('Button', 'ghost', 'md', [OTHER_DISABLED_STAMP])
  const computed = forcedRun({ placed })
  assert.equal(refusalOf(computed, 'composites/Card', 'ZzForced'), undefined)
  assert.deepEqual(stateCreditsOf(computed, 'ZzForced'), [
    'Button|ghost|md|hover',
    `record1|${MINI_BUTTON_STAMP}|hover`,
  ])
})

test('B2: a meta whose parameters is not an object literal is a clip this pass cannot read; contrast: an object literal without a clip is not', () => {
  const run = (meta) =>
    cardRun({
      meta,
      stories: `const shared = {}\nexport const ZzSib = { render: () => <Button disabled>Go</Button> }\n`,
      manifest: { 'zz-sib': cardEntry('ZzSib', { mounts: [disabledMount] }) },
    })
  assert.deepEqual(creditsOf(run(`{ component: Card, parameters: shared }`), 'ZzSib'), [])
  assert.deepEqual(
    creditsOf(run(`{ component: Card, parameters: { layout: 'padded' } }`), 'ZzSib'),
    ['Button|secondary|md|disabled'],
  )
})

test('the Rest label counts credits, not call sites, and the legend names the gaps that remain in their exact shapes', () => {
  const computed = miniRun(
    `export const ZzOne = {}\nexport const ZzTwo = {}\nexport const ZzThree = {}\nexport const ZzFour = {}\n`,
    Object.fromEntries(
      ['ZzOne', 'ZzTwo', 'ZzThree', 'ZzFour'].map((name) => [
        name,
        miniEntry(name, miniRecord([placedInstance('Button', 'secondary', 'md')])),
      ]),
    ),
  )
  const region = renderGeneratedRegion(computed)
  assert.match(region, /\| 4 credits /)
  assert.doesNotMatch(region, /call sites \|/)
  for (const phrase of [
    /a mounted instance the page does not\nshow \(`hidden`, `sr-only`, `opacity-0`, a closed `details`\) is credited as mounted/,
    /reads only a string literal of a non-story, non-test design-system file\nwhose whitespace-separated tokens include exactly `fixed`, so a `fixed` behind a variant prefix\n\(`focus:fixed`, `md:fixed`, `max-md:fixed`\)/,
    /a `fixed` element the story file itself positions/,
    /a disabled instance behind its scrim is credited though the scrim covers it/,
    /fails a forced story whose state frame differs from its rest frame by no more than its comparison\nthreshold inside the captured frame, and it does not check that the forced target lies inside the\nclip/,
  ]) {
    assert.match(REGION_LEGEND, phrase)
  }
  assert.doesNotMatch(REGION_LEGEND, /backs/)
})
