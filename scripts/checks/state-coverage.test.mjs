// Regression tests for T594's extractor (state-coverage.mjs), including the orchestrator's own
// remediation of this task's second hand-back: consistency mode now renders record 1 and every
// primitive matrix as markdown between `<!-- state-coverage:begin/end -->` markers instead of
// diffing a JSON snapshot against itself, and a coverage cell distinguishes a confirmed `'none'`
// from an `'unresolved: <reason>'` it could not settle. Follows story-docs.test.mjs's own
// `node --test` conventions: real functions, small fixtures, node:assert/strict, no mocking.
import { test } from 'node:test'
import assert from 'node:assert/strict'
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
  renderRecord1,
  findOwnStoryRenderInstances,
  parseSelector,
  resolveSelectorMatch,
  findRenderJsxProps,
  impliedRoleForPrimitiveInstance,
  computeStateCoverage,
} from './state-coverage.mjs'

function parse(code, fileName = 'fixture.tsx') {
  return parseTsx(fileName, code)
}

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

// --- T594 part A: `impliedRoleOf` returns `null` for a dynamic `role={…}` or a tag `INTRINSIC_ROLE`
// does not carry (`h2`, `label`, `tr`) — the whole matching loop used to be skipped and the cell
// fell to a false confirmed `'none'`. Three shapes, one fixture each. --------------------------------

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

test('buildElementMatrix: a tag INTRINSIC_ROLE does not carry reads "unresolved: no implied role" when it has no forced descendant (Dialog\'s h2 shape)', () => {
  const heading = {
    tag: 'h2',
    role: null,
    tabIndex: -1,
    ariaHidden: false,
    isHelper: false,
    text: '',
    file: 'Dialog/index.tsx',
    line: 102,
    nodeStart: 0,
    nodeEnd: 10,
  }
  // A play() ending on `expect(heading).toHaveFocus()` — `findPlayFocusTarget`'s own shape — names
  // role 'heading', which `h2` cannot be compared against because it has no implied role at all;
  // this must still surface as unresolved, not as a confirmed absence.
  const storyStates = [
    {
      exportName: 'KeyboardFocusOrderAndTrap',
      forced: null,
      playFocus: { role: 'heading', name: 'Turn off replay archival?' },
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix([heading], storyStates)
  assert.match(rows[0].hover[0], /^unresolved: no implied role$/)
  assert.match(rows[0].focusVisible[0], /^unresolved: no implied role$/)
  assert.match(rows[0].active[0], /^unresolved: no implied role$/)
})

test('buildElementMatrix: an ancestor of a forced descendant reads "unresolved: ancestor of a forced descendant …", never "none" (Table\'s tr/row-link shape)', () => {
  const row = {
    tag: 'tr',
    role: null,
    tabIndex: null,
    ariaHidden: false,
    isHelper: false,
    text: '',
    file: 'Table/index.tsx',
    line: 237,
    nodeStart: 0,
    nodeEnd: 100,
  }
  const rowLink = {
    tag: 'a',
    role: null,
    tabIndex: null,
    ariaHidden: false,
    isHelper: false,
    text: 'RedBull_Barley',
    file: 'Table/index.tsx',
    line: 281,
    nodeStart: 10,
    nodeEnd: 20,
  }
  const storyStates = [
    {
      exportName: 'RowLinkHover',
      forced: { state: 'hover', role: 'link', name: 'RedBull_Barley', nth: null },
      playFocus: null,
      argsLiterals: new Set(),
    },
  ]
  const rows = buildElementMatrix([row, rowLink], storyStates)
  const trRow = rows.find((r) => r.variantSize.startsWith('tr'))
  const linkRow = rows.find((r) => r.variantSize.startsWith('a'))
  assert.deepEqual(linkRow.hover, ['RowLinkHover'])
  assert.equal(trRow.hover.length, 1)
  assert.match(trRow.hover[0], /^unresolved: ancestor of a forced descendant/)
  assert.match(trRow.hover[0], /a@Table\/index\.tsx:281/)
  assert.match(trRow.hover[0], /RowLinkHover/)
  // `active` carries no force-state at all in this fixture, on either element — a genuine gap
  // ('no implied role'), not an ancestor of anything forced.
  assert.match(trRow.active[0], /^unresolved: no implied role$/)
})
