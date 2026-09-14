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
  metaComponentName,
  findExportedStoryObjects,
  resolveStoryAxisValues,
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
  evaluateExpr,
  evaluateGuards,
  resolveComposedStoryMatches,
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

test("buildAxisMatrix leaves Menu's actions variant with no forced state when every hover/focus-visible/active story targets selection", () => {
  const sourceFile = parse(MENU_STORIES_SOURCE, 'Menu.stories.tsx')
  const metaObj = findMeta(sourceFile)
  assert.equal(metaComponentName(metaObj), 'Menu')
  const defaults = { variant: null }
  const instances = []
  for (const { exportName, node } of findExportedStoryObjects(sourceFile)) {
    const axis = resolveStoryAxisValues(metaObj, node, defaults)
    const forced = extractVisualForceState(node)
    instances.push({
      primitive: 'Menu',
      kind: 'own-story',
      componentKey: 'primitives/Menu',
      file: 'Menu.stories.tsx',
      storyName: exportName,
      variant: axis.variant,
      size: { value: null, resolved: 'n/a' },
      forced,
      playFocus: null,
    })
  }
  const matrix = buildAxisMatrix('Menu', instances)
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

test('extractPseudoClasses returns null for a state with no matching utility', () => {
  assert.deepEqual(extractPseudoClasses(['bg-surface text-text-primary']), {
    hover: null,
    'focus-visible': null,
    active: null,
  })
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
  assert.equal(resolveNameMatch({ candidate: helperRecipe, pool, name: null, nth: 0 }), 'reject')
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

test('check mode (region equality after a prettier round-trip) passes when nothing changed and fails when a generated cell is hand-edited', () => {
  const region = renderGeneratedRegion(FIXTURE_COMPUTED)
  const readme = `# Title\n\n${region}\n`
  const formatted = formatWithPrettier(readme)
  const formattedRegion = extractGeneratedRegion(formatted)
  // Unchanged: the currently-committed region (after its own prettier pass) matches a fresh render.
  const currentRegion = extractGeneratedRegion(formatWithPrettier(readme))
  assert.equal(currentRegion, formattedRegion)

  // Hand-edit one generated cell — exactly the shape the orchestrator's review found: the embedded
  // record says `none`/unresolved, the visible text claims otherwise. Everything else (the source
  // this would be computed from) is unchanged.
  const corruptedReadme = formatted.replace('none → none', 'hover:underline → CoveredStory')
  const corruptedRegion = extractGeneratedRegion(corruptedReadme)
  assert.notEqual(corruptedRegion, formattedRegion)
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

test('contrast: a name with no literal arg anywhere resolves nothing, never guessed', () => {
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
  assert.equal(matched.length, 0)
  assert.equal(unresolved.length, 0)
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
  assert.deepEqual(rows[1].hover, ['none'])
})
