// T693: the in-page readers of `state-coverage-runtime.ts` against synthetic fibers — no browser, no
// build, no story. Every `test()` takes no argument (never `{ page }`), so Playwright never starts a
// browser context for it, the idiom `story-render.spec.ts` uses for the same reason. What the real
// pages answer is `state-coverage-runtime.spec.ts`'s job (the plants); this proves the reading rules
// themselves, with a contrast case beside each.
import { expect, test } from '@playwright/test'
import { STAMP_ATTRIBUTE } from '../../packages/design-system/.storybook/source-stamp-attribute.cjs'
import {
  checkPlantCoverage,
  describeElement,
  describeFiles,
  describeMounts,
} from './state-coverage-runtime'
import type { Instance, TrackedRegistry } from './state-coverage-runtime'

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
