// T693: the in-page readers of `state-coverage-runtime.ts` against synthetic fibers — no browser, no
// build, no story. Every `test()` takes no argument (never `{ page }`), so Playwright never starts a
// browser context for it, the idiom `story-render.spec.ts` uses for the same reason. What the real
// pages answer is `state-coverage-runtime.spec.ts`'s job (the plants); this proves the reading rules
// themselves, with a contrast case beside each.
import { expect, test } from '@playwright/test'
import { STAMP_ATTRIBUTE } from '../../packages/design-system/.storybook/source-stamp-attribute.cjs'
import {
  checkPlantCoverage,
  clearBrowserState,
  combineThemeRecords,
  describeElement,
  describeFiles,
  describeMounts,
  probeSettledStory,
} from './state-coverage-runtime'
import { stubStoryPage } from './fixtures/story-page-stub'
import type { Instance, TrackedRegistry, WidthRecord } from './state-coverage-runtime'

function Button() {}
function Field() {}
function Menu() {}
function Callout() {}
function Row() {}

const registry: TrackedRegistry = {
  Button: {
    component: Button,
    directory: 'packages/design-system/src/primitives/Button/',
    axes: { variant: 'secondary', size: 'md' },
  },
  Field: {
    component: Field,
    directory: 'packages/design-system/src/primitives/Field/',
    axes: { size: 'md' },
  },
  Menu: {
    component: Menu,
    directory: 'packages/design-system/src/primitives/Menu/',
    axes: { variant: null },
  },
}

interface FakeFiber {
  type?: unknown
  stateNode?: unknown
  memoizedProps?: Record<string, unknown>
  return?: FakeFiber | null
  child?: FakeFiber | null
  sibling?: FakeFiber | null
}

interface DomState {
  /** `:disabled` matches: a native form control with the `disabled` attribute. */
  disabled?: boolean
  ariaDisabled?: boolean
}

// An element-like object: carries a React fiber under the `__reactFiber$` key, as a DOM node does,
// and answers the three questions the reader asks of a real element.
function fakeElement(
  fiber: FakeFiber | null,
  attrs: Record<string, string> = {},
  dom: DomState = {},
) {
  const all: Record<string, string> = {
    ...attrs,
    ...(dom.ariaDisabled ? { 'aria-disabled': 'true' } : {}),
  }
  const el: Record<string, unknown> = {
    getAttribute: (name: string) => all[name] ?? null,
    matches: (selector: string) => selector === ':disabled' && Boolean(dom.disabled),
  }
  if (fiber) {
    el['__reactFiber$abc'] = fiber
    fiber.stateNode = el
  }
  return el as unknown as Element
}

// Links `children` under `parent` the way React does (`child`, `sibling`, `return`).
function link(parent: FakeFiber, ...children: FakeFiber[]): FakeFiber {
  parent.child = children[0] ?? null
  children.forEach((c, i) => {
    c.return = parent
    c.sibling = children[i + 1] ?? null
  })
  return parent
}

// A host fiber for an element carrying `stamp` (or none), with its DOM state.
function host(tag: string, stamp: string | null, dom: DomState = {}): FakeFiber {
  const fiber: FakeFiber = { type: tag }
  fakeElement(fiber, stamp ? { [STAMP_ATTRIBUTE]: stamp } : {}, dom)
  return fiber
}

const opts = { registry, stampAttribute: STAMP_ATTRIBUTE }
const inst = (
  component: string,
  variant: string | null,
  size: string | null,
  disabledAt: string[] = [],
): Instance => ({ component, variant, size, disabledAt })

const BUTTON_FILE = 'packages/design-system/src/primitives/Button/index.tsx:213'
const BUTTON_ANCHOR = 'packages/design-system/src/primitives/Button/index.tsx:200'
const FIELD_CLONE = 'packages/design-system/src/primitives/Field/index.tsx:122'
const MENU_TRIGGER = 'packages/design-system/src/primitives/Menu/index.tsx:149'
const MENU_ITEM = 'packages/design-system/src/primitives/Menu/index.tsx:361'
const ROW_BUTTON = 'packages/design-system/src/composites/Row/index.tsx:30'

// The tree root a story mounts under: `describeMounts` starts from the first rendered element.
function rootOf(top: FakeFiber): Element {
  // The first rendered element only has to reach `top` through `return`; it is not part of the tree
  // the walk visits.
  const first = host('div', null)
  first.return = top
  return { firstElementChild: first.stateNode } as unknown as Element
}

test('describeElement: the stamped element is attributed to the nearest tracked instance whose own file placed it, axes merged over the defaults', () => {
  const instance: FakeFiber = { type: Button, memoizedProps: { variant: 'primary' }, return: null }
  const el = host('button', BUTTON_FILE)
  link(instance, link({ type: 'span' }, el))
  expect(describeElement(el.stateNode as Element, opts)).toEqual({
    stamp: BUTTON_FILE,
    placedBy: inst('Button', 'primary', 'md'),
  })
})

test('describeElement: a bare instance is recorded at its own defaults; an axis the primitive lacks is null; loading is not read from props', () => {
  const bare: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const el = host('button', BUTTON_FILE)
  link(bare, el)
  expect(describeElement(el.stateNode as Element, opts).placedBy).toEqual(
    inst('Button', 'secondary', 'md'),
  )
  // Field has a size and no variant; Menu has a variant with no default.
  const field: FakeFiber = { type: Field, memoizedProps: { size: 'lg' }, return: null }
  const control = host('input', FIELD_CLONE)
  link(field, control)
  expect(describeElement(control.stateNode as Element, opts).placedBy).toEqual(
    inst('Field', null, 'lg'),
  )
  const unnamed: FakeFiber = { type: Menu, memoizedProps: {}, return: null }
  const trigger = host('button', MENU_TRIGGER)
  link(unnamed, trigger)
  expect(describeElement(trigger.stateNode as Element, opts).placedBy).toEqual(
    inst('Menu', null, null),
  )
  const named: FakeFiber = { type: Menu, memoizedProps: { variant: 'selection' }, return: null }
  const trigger2 = host('button', MENU_TRIGGER)
  link(named, trigger2)
  expect(describeElement(trigger2.stateNode as Element, opts).placedBy).toEqual(
    inst('Menu', 'selection', null),
  )
  // `loading` is a prop: only the DOM says whether anything renders disabled.
  const loading: FakeFiber = { type: Button, memoizedProps: { loading: true }, return: null }
  const loadingEl = host('button', BUTTON_FILE)
  link(loading, loadingEl)
  expect(describeElement(loadingEl.stateNode as Element, opts).placedBy?.disabledAt).toEqual([])
})

test('describeElement: an element with no stamp was written by a story, and no instance placed it', () => {
  const instance: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const el = host('div', null)
  link(instance, el)
  expect(describeElement(el.stateNode as Element, opts)).toEqual({ stamp: null, placedBy: null })
})

test('describeElement: a stamp outside every tracked primitive, even under one, is placed by none', () => {
  const instance: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const callout: FakeFiber = { type: Callout }
  const stamp = 'packages/design-system/src/primitives/Callout/index.tsx:59'
  const el = host('div', stamp)
  link(instance, link(callout, el))
  expect(describeElement(el.stateNode as Element, opts)).toEqual({ stamp, placedBy: null })
})

test("describeElement: a stamp in a primitive's file with no instance of it above is placed by none (a function of the same name that is not the tracked one does not count)", () => {
  function OtherButton() {}
  const impostor: FakeFiber = { type: OtherButton, memoizedProps: {}, return: null }
  const el = host('button', BUTTON_FILE)
  link(impostor, el)
  expect(describeElement(el.stateNode as Element, opts)).toEqual({
    stamp: BUTTON_FILE,
    placedBy: null,
  })
})

test('describeElement: the nearest instance wins when the same primitive nests, and a disabled element belongs to the inner one alone', () => {
  const outer: FakeFiber = { type: Button, memoizedProps: { variant: 'ghost' }, return: null }
  const inner: FakeFiber = { type: Button, memoizedProps: { variant: 'primary' } }
  const el = host('button', BUTTON_FILE, { disabled: true })
  link(outer, link(inner, el))
  expect(describeElement(el.stateNode as Element, opts).placedBy).toEqual(
    inst('Button', 'primary', 'md', [BUTTON_FILE]),
  )
  // The outer instance placed nothing disabled of its own.
  const mounts = describeMounts(rootOf(outer), opts)
  expect(mounts).toEqual([
    inst('Button', 'ghost', 'md'),
    inst('Button', 'primary', 'md', [BUTTON_FILE]),
  ])
})

test('describeElement: a stamp that names no tracked primitive reads its own file, never a prefix of another name', () => {
  // `ButtonGroup/` shares the `Button` prefix but is not `Button/`: the directory carries its slash.
  const instance: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const stamp = 'packages/design-system/src/primitives/ButtonGroup/index.tsx:9'
  const el = host('div', stamp)
  link(instance, el)
  expect(describeElement(el.stateNode as Element, opts).placedBy).toBeNull()
})

test('the stamp attribute is the one passed in, never a literal of the reader’s own', () => {
  const instance: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const fiber: FakeFiber = { type: 'button' }
  const el = fakeElement(fiber, { 'data-other-stamp': BUTTON_FILE })
  link(instance, fiber)
  expect(
    describeElement(el, { registry, stampAttribute: 'data-other-stamp' }).placedBy?.component,
  ).toBe('Button')
  // The default attribute name finds nothing on that element.
  expect(describeElement(el, opts)).toEqual({ stamp: null, placedBy: null })
})

test('describeMounts lists every tracked instance from the top of the tree, in order, as structured objects', () => {
  const first: FakeFiber = { type: Button, memoizedProps: { variant: 'destructive' } }
  const second: FakeFiber = { type: Field, memoizedProps: { size: 'lg', disabled: true } }
  const wrapper = link({ type: 'div' }, first, second)
  const callout = link({ type: Callout }, wrapper)
  expect(describeMounts(rootOf(callout), opts)).toEqual([
    inst('Button', 'destructive', 'md'),
    inst('Field', null, 'lg'),
  ])
})

test('describeMounts keeps multiplicity: two instances are two entries, in tree order', () => {
  const a: FakeFiber = { type: Button, memoizedProps: { variant: 'primary' } }
  const b: FakeFiber = { type: Button, memoizedProps: { variant: 'primary' } }
  expect(describeMounts(rootOf(link({ type: 'div' }, a, b)), opts)).toEqual([
    inst('Button', 'primary', 'md'),
    inst('Button', 'primary', 'md'),
  ])
})

test('describeMounts: an empty story root mounts nothing', () => {
  expect(describeMounts({ firstElementChild: null } as unknown as Element, opts)).toEqual([])
})

// ---- disabled, as the DOM renders it -------------------------------------------------------------

test('disabledAt: <Button disabled> is its button stamp, read from the DOM', () => {
  const button: FakeFiber = { type: Button, memoizedProps: { disabled: true } }
  const el = host('button', BUTTON_FILE, { disabled: true })
  link(button, el)
  expect(describeMounts(rootOf(button), opts)).toEqual([
    inst('Button', 'secondary', 'md', [BUTTON_FILE]),
  ])
  expect(describeElement(el.stateNode as Element, opts).placedBy?.disabledAt).toEqual([BUTTON_FILE])
})

test('disabledAt: <Button href="/x" disabled> is whatever the DOM says — an <a> is never :disabled, so []', () => {
  const button: FakeFiber = { type: Button, memoizedProps: { href: '/x', disabled: true } }
  const anchor = host('a', BUTTON_ANCHOR, { disabled: false })
  link(button, anchor)
  expect(describeMounts(rootOf(button), opts)).toEqual([inst('Button', 'secondary', 'md')])
  expect(describeElement(anchor.stateNode as Element, opts).placedBy?.disabledAt).toEqual([])
})

test('disabledAt: <Field><input disabled/></Field> is the Field cloneElement stamp', () => {
  const field: FakeFiber = { type: Field, memoizedProps: {} }
  const input = host('input', FIELD_CLONE, { disabled: true })
  const label = host('label', 'packages/design-system/src/primitives/Field/index.tsx:130')
  link(field, label, input)
  expect(describeMounts(rootOf(field), opts)).toEqual([inst('Field', null, 'md', [FIELD_CLONE])])
})

test('disabledAt: a Menu with a disabled item is the item stamp; aria-disabled counts, and so does an empty menu’s trigger', () => {
  const menu: FakeFiber = { type: Menu, memoizedProps: { variant: 'actions' } }
  const trigger = host('button', MENU_TRIGGER)
  const enabledItem = host('button', MENU_ITEM)
  const disabledItem = host('button', MENU_ITEM, { ariaDisabled: true })
  link(menu, trigger, link({ type: 'div' }, enabledItem, disabledItem))
  expect(describeMounts(rootOf(menu), opts)).toEqual([inst('Menu', 'actions', null, [MENU_ITEM])])

  const empty: FakeFiber = { type: Menu, memoizedProps: { variant: 'selection', items: [] } }
  link(empty, host('button', MENU_TRIGGER, { ariaDisabled: true }))
  expect(describeMounts(rootOf(empty), opts)).toEqual([
    inst('Menu', 'selection', null, [MENU_TRIGGER]),
  ])
})

test('disabledAt is the sorted unique stamps: two disabled elements from one line are one entry', () => {
  const menu: FakeFiber = { type: Menu, memoizedProps: { variant: 'actions' } }
  const kids = [
    host('button', MENU_ITEM, { ariaDisabled: true }),
    host('button', MENU_TRIGGER, { ariaDisabled: true }),
    host('button', MENU_ITEM, { ariaDisabled: true }),
  ]
  link(menu, ...kids)
  expect(describeMounts(rootOf(menu), opts)[0].disabledAt).toEqual([MENU_TRIGGER, MENU_ITEM])
})

test('disabledAt contrast: an enabled Button, and disabled={false}, are []', () => {
  const plain: FakeFiber = { type: Button, memoizedProps: {} }
  link(plain, host('button', BUTTON_FILE))
  const off: FakeFiber = { type: Button, memoizedProps: { disabled: false } }
  link(off, host('button', BUTTON_FILE))
  const mounts = describeMounts(rootOf(link({ type: 'div' }, plain, off)), opts)
  expect(mounts.map((m) => m.disabledAt)).toEqual([[], []])
})

test('disabledAt contrast: a disabled raw <button> a composite placed, beside an enabled Button, leaves the Button’s disabledAt []', () => {
  const button: FakeFiber = { type: Button, memoizedProps: {} }
  link(button, host('button', BUTTON_FILE))
  const raw = host('button', ROW_BUTTON, { disabled: true })
  const row = link({ type: Row }, button, raw)
  expect(describeMounts(rootOf(row), opts)).toEqual([inst('Button', 'secondary', 'md')])
  expect(describeElement(raw.stateNode as Element, opts)).toEqual({
    stamp: ROW_BUTTON,
    placedBy: null,
  })
})

test('describeElement and describeMounts agree: the placing instance is the matching mount, disabledAt included', () => {
  const menu: FakeFiber = { type: Menu, memoizedProps: { variant: 'actions' } }
  const item = host('button', MENU_ITEM, { ariaDisabled: true })
  link(menu, host('button', MENU_TRIGGER), item)
  const mounts = describeMounts(rootOf(menu), opts)
  expect(describeElement(item.stateNode as Element, opts).placedBy).toEqual(mounts[0])
})

// ---- plants fail closed ---------------------------------------------------------------------------

test('checkPlantCoverage: a fixture story with no assertion fails, an assertion with no fixture story fails, equal sets pass', () => {
  expect(checkPlantCoverage(['a', 'b'], ['a', 'b'])).toEqual([])
  expect(checkPlantCoverage(['a'], ['a', 'b'])).toEqual([expect.stringContaining('b')])
  expect(checkPlantCoverage(['a'], ['a', 'b'])[0]).toMatch(/fixture story .*no assertion/)
  expect(checkPlantCoverage(['a', 'gone'], ['a'])[0]).toMatch(/assertion .*no fixture story/)
  expect(checkPlantCoverage(['a', 'gone'], ['a'])).toHaveLength(1)
  expect(checkPlantCoverage([], [])).toEqual([])
})

// ---- files: every stamped source file that rendered an element ------------------------------------

// A document-like object whose `querySelectorAll` answers `[attr]` with elements carrying the stamps.
function fakeDocumentRoot(stamps: (string | null)[]): Element {
  const found = stamps.map((stamp) => ({ getAttribute: () => stamp }))
  const ownerDocument = {
    querySelectorAll: (selector: string) => (selector === `[${STAMP_ATTRIBUTE}]` ? found : []),
  }
  return { ownerDocument } as unknown as Element
}

test('describeFiles: the file part of every stamp in the document, sorted and unique', () => {
  const root = fakeDocumentRoot([
    BUTTON_FILE,
    BUTTON_ANCHOR,
    ROW_BUTTON,
    FIELD_CLONE,
    'packages/design-system/src/lib/Spinner.tsx:5',
  ])
  expect(describeFiles(root, opts)).toEqual([
    'packages/design-system/src/composites/Row/index.tsx',
    'packages/design-system/src/lib/Spinner.tsx',
    'packages/design-system/src/primitives/Button/index.tsx',
    'packages/design-system/src/primitives/Field/index.tsx',
  ])
})

test('describeFiles: no stamped element is no file, and the attribute named is the one passed in', () => {
  expect(describeFiles(fakeDocumentRoot([]), opts)).toEqual([])
  expect(
    describeFiles(fakeDocumentRoot([BUTTON_FILE]), { ...opts, stampAttribute: 'data-x' }),
  ).toEqual([])
})

// ---- T710: the two themes' records joined, and the storage clear ----------------------------------

const btn = (variant: string, size: string, disabledAt: string[] = []): Instance => ({
  component: 'Button',
  variant,
  size,
  disabledAt,
})
const themed = (overrides: Partial<WidthRecord> = {}): WidthRecord => ({
  clip: false,
  fullPage: false,
  mounts: [],
  files: [],
  ...overrides,
})

test('combineThemeRecords: a mount only the light theme renders is not credited, a mount both render is', () => {
  const both = btn('primary', 'md')
  const lightOnly = btn('ghost', 'sm', [`${BUTTON_FILE}`])
  expect(
    combineThemeRecords(themed({ mounts: [both, lightOnly] }), themed({ mounts: [both] })).mounts,
  ).toEqual([both])
  // Dark-only is not credited either, and the contrast: identical renders keep every mount.
  expect(
    combineThemeRecords(themed({ mounts: [both] }), themed({ mounts: [both, lightOnly] })).mounts,
  ).toEqual([both])
  expect(
    combineThemeRecords(
      themed({ mounts: [both, lightOnly] }),
      themed({ mounts: [both, lightOnly] }),
    ).mounts,
  ).toEqual([both, lightOnly])
})

test('combineThemeRecords: an instance is the same only with the same axes and disabledAt, and counts once per time both render it', () => {
  const rest = btn('primary', 'md')
  const off = btn('primary', 'md', [BUTTON_FILE])
  expect(combineThemeRecords(themed({ mounts: [off] }), themed({ mounts: [rest] })).mounts).toEqual(
    [],
  )
  expect(
    combineThemeRecords(themed({ mounts: [rest, rest] }), themed({ mounts: [rest] })).mounts,
  ).toEqual([rest])
})

test('combineThemeRecords: clip is the disjunction, files the union, fullPage the index tag', () => {
  const joined = combineThemeRecords(
    themed({ clip: false, fullPage: true, files: ['b.tsx', 'a.tsx'] }),
    themed({ clip: true, fullPage: true, files: ['c.tsx', 'a.tsx'] }),
  )
  expect(joined).toMatchObject({ clip: true, fullPage: true, files: ['a.tsx', 'b.tsx', 'c.tsx'] })
  expect(combineThemeRecords(themed(), themed()).clip).toBe(false)
})

test('combineThemeRecords: a file exactly one theme rendered is in files and in oneThemeFiles, in either direction; a file both render is in files alone', () => {
  const lightOnly = combineThemeRecords(
    themed({ files: ['both.tsx', 'light.tsx'] }),
    themed({ files: ['both.tsx'] }),
  )
  expect(lightOnly).toMatchObject({
    files: ['both.tsx', 'light.tsx'],
    oneThemeFiles: ['light.tsx'],
  })
  const darkOnly = combineThemeRecords(
    themed({ files: ['both.tsx'] }),
    themed({ files: ['both.tsx', 'dark.tsx'] }),
  )
  expect(darkOnly).toMatchObject({ files: ['both.tsx', 'dark.tsx'], oneThemeFiles: ['dark.tsx'] })
  const each = combineThemeRecords(
    themed({ files: ['b.tsx', 'a.tsx'] }),
    themed({ files: ['c.tsx', 'a.tsx'] }),
  )
  expect(each.oneThemeFiles).toEqual(['b.tsx', 'c.tsx'])
  // The contrast: the same files in both themes write no such key, so a story both render alike is
  // unchanged in the manifest.
  const alike = combineThemeRecords(
    themed({ files: ['a.tsx', 'b.tsx'] }),
    themed({ files: ['a.tsx', 'b.tsx'] }),
  )
  expect(alike).not.toHaveProperty('oneThemeFiles')
  expect(combineThemeRecords(themed(), themed())).not.toHaveProperty('oneThemeFiles')
})

test('combineThemeRecords: a force the themes answer alike is the ordinary record, one they answer differently is flagged, whichever differs', () => {
  const answer = { count: 1, stamp: BUTTON_FILE, placedBy: btn('primary', 'md') }
  const same = combineThemeRecords(themed({ force: answer }), themed({ force: { ...answer } }))
  expect(same.force).toEqual(answer)
  expect(same.force).not.toHaveProperty('differsByTheme')
  const flagged = (dark: object | undefined) =>
    combineThemeRecords(themed({ force: answer }), themed(dark ? { force: dark as never } : {}))
      .force
  // A count, a stamp, a placing instance, and a force only one theme carries.
  expect(flagged({ ...answer, count: 2 })).toEqual({ ...answer, differsByTheme: true })
  expect(flagged({ ...answer, stamp: null, placedBy: null })).toEqual({
    ...answer,
    differsByTheme: true,
  })
  expect(flagged({ ...answer, placedBy: btn('ghost', 'md') })).toEqual({
    ...answer,
    differsByTheme: true,
  })
  expect(flagged(undefined)).toEqual({ ...answer, differsByTheme: true })
  // A story with no force in either theme has none.
  expect(combineThemeRecords(themed(), themed())).not.toHaveProperty('force')
})

// T712 (6): a force target no tracked primitive placed carries no `disabledAt` to compare (that list
// belongs to the placing instance), so the element's own disabled state is read per theme and joined.
test('T712 (6) plant: a force target no tracked primitive placed, disabled in one theme only, is flagged differsByTheme, in either direction, and the per-theme flag is never written', () => {
  const raw = { count: 1, stamp: ROW_BUTTON, placedBy: null }
  for (const [light, dark] of [
    [true, false],
    [false, true],
  ]) {
    const joined = combineThemeRecords(
      themed({ force: { ...raw, disabled: light } }),
      themed({ force: { ...raw, disabled: dark } }),
    )
    expect(joined.force).toEqual({ ...raw, differsByTheme: true })
  }
})

test('T712 (6) plant: the same target disabled in both themes, or in neither, is the ordinary record, and the per-theme disabled flag is not written', () => {
  const raw = { count: 1, stamp: ROW_BUTTON, placedBy: null }
  for (const both of [true, false]) {
    const joined = combineThemeRecords(
      themed({ force: { ...raw, disabled: both } }),
      themed({ force: { ...raw, disabled: both } }),
    )
    expect(joined.force).toEqual(raw)
  }
})

test('T712 (6) contrast: a record with no disabled field is the ordinary record as before, and a placed target is judged by its instance', () => {
  const raw = { count: 1, stamp: ROW_BUTTON, placedBy: null }
  expect(combineThemeRecords(themed({ force: raw }), themed({ force: { ...raw } })).force).toEqual(
    raw,
  )
  const placed = { count: 1, stamp: BUTTON_FILE, placedBy: btn('primary', 'md', [BUTTON_FILE]) }
  expect(
    combineThemeRecords(
      themed({ force: { ...placed } }),
      themed({ force: { ...placed, placedBy: btn('primary', 'md') } }),
    ).force,
  ).toEqual({ ...placed, differsByTheme: true })
})

test('combineThemeRecords: a focus is credited only when both themes agree on it', () => {
  const focus = { stamp: BUTTON_FILE, placedBy: btn('ghost', 'md') }
  expect(combineThemeRecords(themed({ focus }), themed({ focus: { ...focus } })).focus).toEqual(
    focus,
  )
  expect(combineThemeRecords(themed({ focus }), themed({ focus: null })).focus).toBeNull()
  expect(combineThemeRecords(themed({ focus }), themed()).focus).toBeNull()
  expect(combineThemeRecords(themed({ focus: null }), themed({ focus: null })).focus).toBeNull()
  // No `play()` in either theme: no focus key at all.
  expect(combineThemeRecords(themed(), themed())).not.toHaveProperty('focus')
})

test('combineThemeRecords: a focus the themes disagree on writes focusDiffersByTheme, one they agree on (a focus or none) does not', () => {
  const focus = { stamp: BUTTON_FILE, placedBy: btn('ghost', 'md') }
  const other = { stamp: BUTTON_FILE, placedBy: btn('primary', 'md') }
  // Held in one theme only, in either direction, held in different elements, and a `play()` in one theme.
  for (const [light, dark] of [
    [{ focus }, { focus: null }],
    [{ focus: null }, { focus }],
    [{ focus }, { focus: other }],
    [{ focus }, {}],
    [{}, { focus }],
  ] as const) {
    const joined = combineThemeRecords(themed(light), themed(dark))
    expect(joined.focus).toBeNull()
    expect(joined.focusDiffersByTheme).toBe(true)
  }
  // The contrast: both agree on a focus, on no focus, or have no `play()`.
  for (const both of [{ focus }, { focus: null }, {}] as const) {
    expect(combineThemeRecords(themed(both), themed({ ...both }))).not.toHaveProperty(
      'focusDiffersByTheme',
    )
  }
})

function stubPage(url: string, evaluate: () => Promise<void>) {
  const calls: string[] = []
  const page = {
    context: () => ({ clearCookies: async () => void calls.push('cookies') }),
    url: () => url,
    evaluate: async () => {
      calls.push('storage')
      await evaluate()
    },
  }
  return { page: page as unknown as Parameters<typeof clearBrowserState>[0], calls }
}

test('clearBrowserState: about:blank is skipped after the cookies, any other storage error throws', async () => {
  const blank = stubPage('about:blank', async () => {
    throw new Error('SecurityError: localStorage is not available')
  })
  await clearBrowserState(blank.page)
  expect(blank.calls).toEqual(['cookies'])

  const failing = stubPage('http://localhost:6006/iframe.html', async () => {
    throw new Error('SecurityError: the document is sandboxed')
  })
  await expect(clearBrowserState(failing.page)).rejects.toThrow('the document is sandboxed')

  // The contrast: a page on the origin is cleared, cookies first.
  const healthy = stubPage('http://localhost:6006/iframe.html', async () => {})
  await clearBrowserState(healthy.page)
  expect(healthy.calls).toEqual(['cookies', 'storage'])
})

// ---- T712: the order the probe drives a settled page in, against a stub page (no browser) --------------
//
// `stubStoryPage` runs the readers of `story-render.ts` against a `window` it owns and answers
// `inspect`'s questions from what the test says the page holds when the harness asks, so a handler the
// force triggers shows up in what is read, and in when.

const FORCE = { state: 'hover', role: 'button' }
const noElement = () => ({ stamp: null, placedBy: null })
const FRAME = { width: 400, height: 300 }
// Reads one width of one theme the way `probeStory` does, with the force in the story's parameters.
function probeWith(
  state: Parameters<typeof stubStoryPage>[1],
  force: Record<string, unknown> | null = FORCE,
) {
  const stub = stubStoryPage('test--story', state)
  if (force) stub.parameters.visualForceState = force
  return { stub, probed: () => probeSettledStory(stub.page, stub.root, 'test--story', true, FRAME) }
}

test('T712 (2) plant: the mounts and the files are read after the force is applied, so a handler that mounts on hover is in the record the frame shows', async () => {
  let hovered = false
  const extra = btn('ghost', 'sm')
  const { probed } = probeWith({
    mounts: () => (hovered ? [btn('primary', 'md'), extra] : [btn('primary', 'md')]),
    files: () => (hovered ? ['a.tsx', 'b.tsx'] : ['a.tsx']),
    element: noElement,
    onHover: () => {
      hovered = true
    },
  })
  const record = await probed()
  expect(record.mounts).toEqual([btn('primary', 'md'), extra])
  expect(record.files).toEqual(['a.tsx', 'b.tsx'])
})

test('T712 (2) plant: a handler that UNMOUNTS on hover or press is gone from the record, as it is from the frame', async () => {
  let pressed = false
  const { probed } = probeWith(
    {
      mounts: () => (pressed ? [] : [btn('primary', 'md')]),
      files: () => (pressed ? [] : ['a.tsx']),
      element: noElement,
      onMouseDown: () => {
        pressed = true
      },
    },
    { state: 'active', role: 'button' },
  )
  const record = await probed()
  expect(record.mounts).toEqual([])
  expect(record.files).toEqual([])
})

test('T712 (2) contrast: a story with no force reads its mounts and files once, and a handler-free force records what the page holds', async () => {
  const { probed } = probeWith(
    { mounts: () => [btn('primary', 'md')], files: () => ['a.tsx'], element: noElement },
    null,
  )
  expect(await probed()).toMatchObject({ mounts: [btn('primary', 'md')], files: ['a.tsx'] })
  const forced = probeWith({
    mounts: () => [btn('primary', 'md')],
    files: () => ['a.tsx'],
    element: noElement,
  })
  expect(await forced.probed()).toMatchObject({ mounts: [btn('primary', 'md')], files: ['a.tsx'] })
})

test('T712 (9) plant: a hover handler that navigates fails the probe, naming the story, not a record of a page the capture would not show', async () => {
  const { stub, probed } = probeWith({
    mounts: () => [btn('primary', 'md')],
    files: () => ['a.tsx'],
    element: noElement,
    onHover: (page) => page.navigate('http://stub/elsewhere.html'),
  })
  await expect(probed()).rejects.toThrow(/test--story.*left the story/)
  // T713 (b): the check runs before any read, so it is the named failure and not the timeout of a read
  // through a story root the new page does not hold (the stub rejects that read as a locator would).
  expect(stub.calls).not.toContain('read mounts')
})

test('T713 (b) plant: a handler that leaves for a page with no story root fails with the named failure, not the timeout of a read through the root', async () => {
  const { probed } = probeWith(
    {
      mounts: () => [],
      files: () => [],
      element: noElement,
      onMouseDown: (page) => page.navigate('http://stub/not-a-story.html'),
    },
    { state: 'active', role: 'button' },
  )
  const error = await probed().then(
    () => null,
    (thrown: unknown) => thrown as Error,
  )
  expect(error?.message).toMatch(/test--story.*left the story/)
  expect(error?.message).not.toMatch(/Timeout/)
})

test('T713 (b) plant: a handler that reloads the story page, which holds a root again, fails with the named failure', async () => {
  const { probed } = probeWith({
    mounts: () => [btn('primary', 'md')],
    files: () => ['a.tsx'],
    element: noElement,
    onHover: (page) => page.navigate('http://stub/iframe.html?reloaded'),
  })
  await expect(probed()).rejects.toThrow(/test--story.*left the story/)
})

// T714 (c): the two document checks tell different navigations apart. `onHover` above navigates as the
// force is applied, which the first check (before any read) catches whether or not the second exists.
// This one navigates DURING the reads, to a page that has a root, so the reads succeed and only the
// second check, after the clip, sees that the document is another one.
test('T714 (c) plant: a navigation during the reads, to a page that holds a root, fails with the named failure, which only the check after the last read can give', async () => {
  let leave: () => void = () => {}
  const { stub, probed } = probeWith({
    mounts: () => {
      leave()
      return [btn('primary', 'md')]
    },
    files: () => ['a.tsx'],
    element: noElement,
  })
  leave = () => stub.navigate('http://stub/iframe.html?reloaded')
  await expect(probed()).rejects.toThrow(/test--story.*left the story/)
  // The reads went through, so the failure did not come from the first check or from a read.
  expect(stub.calls).toContain('read files')
  expect(stub.calls).toContain('read clip')
})

test('T712 (9) plant: a control whose mousedown navigates fails the probe, and the mouse comes up on about:blank, never over the story', async () => {
  const { stub, probed } = probeWith(
    {
      mounts: () => [],
      files: () => [],
      element: noElement,
      onMouseDown: (page) => page.navigate('http://stub/elsewhere.html'),
    },
    { state: 'active', role: 'button' },
  )
  await expect(probed()).rejects.toThrow(/left the story/)
  expect(stub.calls).toContain('mouse.up on about:blank')
  expect(stub.calls).not.toContain('mouse.up on the story')
})

test('T712 (9) contrast: an active force on a control that does not navigate is a record, with the mouse up on about:blank after the reads', async () => {
  const { stub, probed } = probeWith(
    { mounts: () => [btn('primary', 'md')], files: () => ['a.tsx'], element: noElement },
    { state: 'active', role: 'button' },
  )
  expect(await probed()).toMatchObject({ clip: false, mounts: [btn('primary', 'md')] })
  expect(stub.calls.slice(-6)).toEqual([
    'read clip',
    'clear cookies',
    'clear localStorage',
    'clear sessionStorage',
    'goto about:blank',
    'mouse.up on about:blank',
  ])
})

test('T712 (6) the per-theme record carries the forced element’s own disabled state, and a story with no force carries no force record', async () => {
  for (const disabled of [true, false]) {
    const { probed } = probeWith({
      mounts: () => [],
      files: () => [],
      element: () => ({ stamp: ROW_BUTTON, placedBy: null }),
      disabled: () => disabled,
    })
    expect((await probed()).force).toEqual({
      count: 1,
      stamp: ROW_BUTTON,
      placedBy: null,
      disabled,
    })
  }
  const none = probeWith({ mounts: () => [], files: () => [], element: noElement }, null)
  expect(await none.probed()).not.toHaveProperty('force')
})
