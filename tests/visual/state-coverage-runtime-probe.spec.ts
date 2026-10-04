// T693: the in-page readers of `state-coverage-runtime.ts` against synthetic fibers — no browser, no
// build, no story. Every `test()` takes no argument (never `{ page }`), so Playwright never starts a
// browser context for it, the idiom `story-render.spec.ts` uses for the same reason. What the real
// pages answer is `state-coverage-runtime.spec.ts`'s job (the plants); this proves the reading rules
// themselves, with a contrast case beside each.
import { expect, test } from '@playwright/test'
import { describeElement, describeMounts } from './state-coverage-runtime'
import type { TrackedRegistry } from './state-coverage-runtime'

function Button() {}
function Field() {}
function Callout() {}

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
}

interface FakeFiber {
  type?: unknown
  memoizedProps?: Record<string, unknown>
  return?: FakeFiber | null
  child?: FakeFiber | null
  sibling?: FakeFiber | null
}

// An element-like object: carries a React fiber under the `__reactFiber$` key, as a DOM node does.
function fakeElement(fiber: FakeFiber | null, attrs: Record<string, string> = {}, extra = {}) {
  const el: Record<string, unknown> = {
    getAttribute: (name: string) => attrs[name] ?? null,
    ...extra,
  }
  if (fiber) el['__reactFiber$abc'] = fiber
  return el as unknown as Element
}

const BUTTON_FILE = 'packages/design-system/src/primitives/Button/index.tsx:213'

test('describeElement: the stamped element is attributed to the nearest tracked instance whose own file placed it, axes merged over the defaults', () => {
  const instance: FakeFiber = { type: Button, memoizedProps: { variant: 'primary' }, return: null }
  const host: FakeFiber = { type: 'button', return: { type: 'span', return: instance } }
  const el = fakeElement(host, { 'data-ds-src': BUTTON_FILE })
  expect(describeElement(el, registry)).toEqual({
    stamp: BUTTON_FILE,
    placedBy: 'Button:primary|md',
  })
})

test('describeElement: a bare instance is recorded at its own defaults, and disabled or loading is appended', () => {
  const bare: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const loading: FakeFiber = {
    type: Button,
    memoizedProps: { loading: true, size: 'lg' },
    return: null,
  }
  const stamped = { 'data-ds-src': BUTTON_FILE }
  expect(
    describeElement(fakeElement({ type: 'button', return: bare }, stamped), registry).placedBy,
  ).toBe('Button:secondary|md')
  expect(
    describeElement(fakeElement({ type: 'button', return: loading }, stamped), registry).placedBy,
  ).toBe('Button:secondary|lg:disabled')
})

test('describeElement: an element with no stamp was written by a story, and no instance placed it', () => {
  const instance: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const el = fakeElement({ type: 'div', return: instance })
  expect(describeElement(el, registry)).toEqual({ stamp: null, placedBy: null })
})

test('describeElement: a stamp outside every tracked primitive, even under one, is placed by none', () => {
  const instance: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const callout: FakeFiber = { type: Callout, return: instance }
  const stamp = 'packages/design-system/src/primitives/Callout/index.tsx:59'
  const el = fakeElement({ type: 'div', return: callout }, { 'data-ds-src': stamp })
  expect(describeElement(el, registry)).toEqual({ stamp, placedBy: null })
})

test("describeElement: a stamp in a primitive's file with no instance of it above is placed by none (a function of the same name that is not the tracked one does not count)", () => {
  function OtherButton() {}
  const impostor: FakeFiber = { type: OtherButton, memoizedProps: {}, return: null }
  const el = fakeElement({ type: 'button', return: impostor }, { 'data-ds-src': BUTTON_FILE })
  expect(describeElement(el, registry)).toEqual({ stamp: BUTTON_FILE, placedBy: null })
})

test('describeElement: the nearest instance wins when the same primitive nests', () => {
  const outer: FakeFiber = { type: Button, memoizedProps: { variant: 'ghost' }, return: null }
  const inner: FakeFiber = { type: Button, memoizedProps: { variant: 'primary' }, return: outer }
  const el = fakeElement({ type: 'button', return: inner }, { 'data-ds-src': BUTTON_FILE })
  expect(describeElement(el, registry).placedBy).toBe('Button:primary|md')
})

test('describeElement: a stamp that names no tracked primitive reads its own file, never a prefix of another name', () => {
  // `ButtonGroup/` shares the `Button` prefix but is not `Button/`: the directory carries its slash.
  const instance: FakeFiber = { type: Button, memoizedProps: {}, return: null }
  const stamp = 'packages/design-system/src/primitives/ButtonGroup/index.tsx:9'
  const el = fakeElement({ type: 'div', return: instance }, { 'data-ds-src': stamp })
  expect(describeElement(el, registry).placedBy).toBeNull()
})

test('describeMounts lists every tracked instance from the top of the tree, in order, with the same encoding', () => {
  const second: FakeFiber = { type: Field, memoizedProps: { size: 'lg', disabled: true } }
  const first: FakeFiber = {
    type: Button,
    memoizedProps: { variant: 'destructive' },
    sibling: second,
  }
  const wrapper: FakeFiber = { type: 'div', child: first }
  const top: FakeFiber = { type: 'root', child: { type: Callout, child: wrapper } }
  first.return = wrapper
  second.return = wrapper
  wrapper.return = top.child
  top.child!.return = top
  const first_el = fakeElement(wrapper)
  const root = { firstElementChild: first_el } as unknown as Element
  expect(describeMounts(root, registry)).toEqual(['Button:destructive|md', 'Field:lg:disabled'])
})

test('describeMounts: an empty story root mounts nothing', () => {
  expect(describeMounts({ firstElementChild: null } as unknown as Element, registry)).toEqual([])
})
