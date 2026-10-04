// What a real browser does with a story, recorded (T693, feature 005).
//
// `scripts/checks/state-coverage.mjs` reads source to guess which element a forced story
// (`parameters.visualForceState`) lands on and which primitive's matrix cell that credits; each
// adversarial review of #112 found another guess wrong (guards, spreads, unrendered branches,
// `aria-hidden` ancestors, children a primitive never places). The capture harness does not guess: it
// locates the forced element with Playwright in the built Storybook (`applyForceState`,
// `story-render.ts`). This module asks the same question through the same locator and records the
// answer, with enough about *who placed the element* that a coverage claim can be checked against it.
//
// Two layers. The in-page functions (`describeElement`, `describeMounts`) are self-contained — they
// are serialised into the page by Playwright, so they reference nothing outside their own body — and
// work on plain objects, so `state-coverage-runtime-probe.spec.ts` drives them with synthetic fibers,
// no browser. `probeStory` below is the Playwright side that settles a story and calls them.
//
// What is read, and from where:
//   - which element the force selects: `locateTarget` (`story-render.ts`), the locator `applyForceState`
//     and the clip resolver share. The match count is how many elements it finds.
//   - where an element was written: `data-ds-src`, the `file:line` stamp the Storybook build adds to
//     every intrinsic element of a design-system source file (`packages/design-system/.storybook/
//     source-stamp.mjs`). An element a story wrote carries none.
//   - which tracked primitive placed it: React's fiber, walked up from the element, for a fiber whose
//     component is a tracked primitive (`window.__DS_TRACKED_PRIMITIVES__`, exposed by
//     `.storybook/preview.tsx`) and whose own directory the stamp falls under. The fiber carries only
//     the props the caller passed, so each axis is that prop merged over the primitive's own exported
//     defaults.
//
// An instance is written as one short string, `Button:primary|lg`, `Link:standalone`, `Field:md`,
// `Menu:selection|start`, with `:disabled` appended when it renders disabled (`disabled` or, for the
// two primitives that have it, `loading`). The manifest stays readable and diffable that way.
import type { Locator, Page } from '@playwright/test'
import { gotoAndWaitForStorySettled, locateTarget, readForceState } from './story-render'
import type { VisualForceState } from './story-render'

export const STAMP_ATTRIBUTE = 'data-ds-src'

// One tracked primitive, as `.storybook/preview.tsx` registers it.
export interface TrackedPrimitive {
  component: unknown
  directory: string
  axes: Record<string, string>
}
export type TrackedRegistry = Record<string, TrackedPrimitive>

// What the forced element, or the focused one, turned out to be. `stamp` is null for an element no
// design-system source file wrote (a story's own raw element); `placedBy` is the tracked primitive
// instance whose own file, or `cloneElement` call, placed it — null when none did.
export interface ElementRecord {
  stamp: string | null
  placedBy: string | null
}

export interface ForceRecord extends ElementRecord {
  count: number
}

// One width's record of one story. `force` is present only for a story that carries a
// `visualForceState`; `focus` only for a story with a `play()` function, `null` when nothing but the
// document body holds focus once it has settled.
export interface WidthRecord {
  force?: ForceRecord
  focus?: ElementRecord | null
  mounts: string[]
}

// Reads the element's own stamp and the tracked primitive instance that placed it. Self-contained
// (serialised into the page): no reference to anything outside this function's body. `registry`
// defaults to the page's own; tests pass a synthetic one.
export function describeElement(
  el: Element,
  registryArg?: TrackedRegistry,
  stampAttribute = 'data-ds-src',
): ElementRecord {
  const registry: TrackedRegistry =
    registryArg ??
    (window as unknown as { __DS_TRACKED_PRIMITIVES__?: TrackedRegistry })
      .__DS_TRACKED_PRIMITIVES__ ??
    {}
  const stamp = el.getAttribute(stampAttribute)

  const fiberOf = (node: object): Record<string, unknown> | null => {
    for (const key of Object.keys(node)) {
      if (key.startsWith('__reactFiber$')) {
        return (node as Record<string, Record<string, unknown>>)[key]
      }
    }
    return null
  }
  const describeInstance = (name: string, props: Record<string, unknown>): string => {
    const axes = registry[name].axes
    const values = Object.keys(axes).map((key) => String(props[key] ?? axes[key]))
    const disabled = Boolean(props.disabled || props.loading)
    return `${name}:${values.join('|')}${disabled ? ':disabled' : ''}`
  }

  if (!stamp) return { stamp: null, placedBy: null }
  const file = stamp.slice(0, stamp.lastIndexOf(':'))
  let fiber = fiberOf(el) as { type?: unknown; return?: unknown; memoizedProps?: unknown } | null
  while (fiber) {
    for (const name of Object.keys(registry)) {
      const tracked = registry[name]
      if (fiber.type === tracked.component && file.startsWith(tracked.directory)) {
        return {
          stamp,
          placedBy: describeInstance(name, (fiber.memoizedProps ?? {}) as Record<string, unknown>),
        }
      }
    }
    fiber = fiber.return as typeof fiber
  }
  return { stamp, placedBy: null }
}

// Every tracked primitive instance mounted under `root`, in the fiber tree's own depth-first order,
// each written the way `describeElement` writes `placedBy`. Self-contained (serialised into the page).
export function describeMounts(root: Element, registryArg?: TrackedRegistry): string[] {
  const registry: TrackedRegistry =
    registryArg ??
    (window as unknown as { __DS_TRACKED_PRIMITIVES__?: TrackedRegistry })
      .__DS_TRACKED_PRIMITIVES__ ??
    {}
  type Fiber = {
    type?: unknown
    child?: Fiber | null
    sibling?: Fiber | null
    return?: Fiber | null
    memoizedProps?: unknown
  }
  const fiberOf = (node: object): Fiber | null => {
    for (const key of Object.keys(node)) {
      if (key.startsWith('__reactFiber$')) return (node as Record<string, Fiber>)[key]
    }
    return null
  }
  // The story root is the container React was mounted into, not an element React rendered, so it
  // has no fiber of its own: start from its first rendered child and climb to the top of the tree
  // (the preview mounts decorators and the story in one root; no tracked primitive sits outside the
  // story), then walk down.
  const first = root.firstElementChild
  if (!first) return []
  let top = fiberOf(first)
  if (!top) return []
  while (top.return) top = top.return

  const mounts: string[] = []
  // Iterative pre-order walk over `child`/`sibling`, so a deep tree cannot overflow the stack.
  const stack: Fiber[] = [top]
  while (stack.length > 0) {
    const node = stack.pop() as Fiber
    for (const name of Object.keys(registry)) {
      if (node.type === registry[name].component) {
        const props = (node.memoizedProps ?? {}) as Record<string, unknown>
        const axes = registry[name].axes
        const values = Object.keys(axes).map((key) => String(props[key] ?? axes[key]))
        const disabled = Boolean(props.disabled || props.loading)
        mounts.push(`${name}:${values.join('|')}${disabled ? ':disabled' : ''}`)
      }
    }
    if (node.sibling) stack.push(node.sibling)
    if (node.child) stack.push(node.child)
  }
  return mounts
}

// Whether the preview's own record of this story has a `play()` function — `parameters` cannot say.
async function storyHasPlay(page: Page, storyId: string): Promise<boolean> {
  return page.evaluate((id: string) => {
    const preview = (
      window as unknown as {
        __STORYBOOK_PREVIEW__?: {
          storyRenders?: { id: string; story?: { playFunction?: unknown } }[]
        }
      }
    ).__STORYBOOK_PREVIEW__
    const render = preview?.storyRenders?.find((r) => r.id === id)
    return typeof render?.story?.playFunction === 'function'
  }, storyId)
}

// Fails loudly on a Storybook build that predates the registry rather than recording a build with
// nothing tracked in it as "no instance placed anything".
async function assertRegistryPresent(page: Page): Promise<void> {
  const present = await page.evaluate(
    () => !!(window as unknown as { __DS_TRACKED_PRIMITIVES__?: object }).__DS_TRACKED_PRIMITIVES__,
  )
  if (!present) {
    throw new Error(
      'window.__DS_TRACKED_PRIMITIVES__ is missing — the built Storybook predates T693 (or its ' +
        'preview no longer registers the tracked primitives). Rebuild: ' +
        '`pnpm --filter design-system build-storybook`.',
    )
  }
}

// One story at one width, already settled (`gotoAndWaitForStorySettled`): what a forced target
// selects, what holds focus after `play()`, and every tracked primitive instance mounted. The force
// is located, never applied — hover, press and focus change paint, not which element a role, a name
// and an `nth` select nor which component placed it.
export async function probeSettledStory(
  page: Page,
  root: Locator,
  storyId: string,
  forceState: VisualForceState | null,
): Promise<WidthRecord> {
  await assertRegistryPresent(page)
  const record: WidthRecord = { mounts: await root.evaluate(describeMounts) }

  if (forceState) {
    const target = locateTarget(root, forceState)
    const count = await target.count()
    record.force =
      count === 1
        ? { count, ...(await target.evaluate(describeElement)) }
        : { count, stamp: null, placedBy: null }
  }

  if (await storyHasPlay(page, storyId)) {
    const focused = page.locator(':focus')
    const holders = await focused.count()
    // `:focus` matches the body when nothing is focused only if the body is itself focusable; an
    // element that holds focus is exactly one, and one that is not the document body.
    const isBody = holders === 1 && (await focused.evaluate((el) => el === document.body))
    record.focus = holders === 1 && !isBody ? await focused.evaluate(describeElement) : null
  }
  return record
}

// Navigates to a story at one width in the light theme — the only theme the pass records: a theme
// changes paint, never which element a role, a name and an `nth` select nor which component placed
// it, and the capture suite still drives both themes through the same locator — settles it the way
// `stories.spec.ts` does, and probes it.
export async function probeStory(page: Page, storyId: string, width: number): Promise<WidthRecord> {
  // The same height rule `stories.spec.ts` applies per unit (see the comment there).
  const height = width === 375 ? 900 : 720
  const root = await gotoAndWaitForStorySettled(page, storyId, 'light', width, height)
  const forceState = await readForceState(page, storyId)
  return probeSettledStory(page, root, storyId, forceState)
}
