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
// Two layers. The in-page reader (`inspect`, with `describeElement` and `describeMounts` as typed
// wrappers) is self-contained — it is serialised into the page by Playwright, so it references nothing
// outside its own body — and works on plain objects, so `state-coverage-runtime-probe.spec.ts` drives
// it with synthetic fibers, no browser. `probeStory` below is the Playwright side that settles a story
// and calls it.
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
//   - the page's stamp attribute is `STAMP_ATTRIBUTE`, imported from the transform that writes it and
//     handed to the page as an argument — the one definition.
//
// An instance is an object, `{ component, variant, size, disabledAt }` in that key order, so the
// manifest's reader (`scripts/checks/state-coverage.mjs`, T694) decodes it in Node without reading
// `preview.tsx`. `variant` and `size` are the prop the caller passed merged over the primitive's own
// default, `null` when the primitive has no such axis (`Field` has no variant, `Link` no size) or
// when none was passed and there is no default (`Menu`'s variant). `disabledAt` is read from the DOM,
// never from props: the sorted unique stamps of the host elements that instance's own file — or its
// `cloneElement` call — placed and that the browser reports disabled (native `:disabled`, or
// `aria-disabled="true"`). Empty means nothing disabled renders; a `<Button href disabled>` renders an
// enabled `<a>`, so it is empty, which is the point of reading the DOM.
import type { Locator, Page } from '@playwright/test'
import { STAMP_ATTRIBUTE } from '../../packages/design-system/.storybook/source-stamp.mjs'
import { gotoAndWaitForStorySettled, locateTarget, readForceState } from './story-render'
import type { VisualForceState } from './story-render'

export { STAMP_ATTRIBUTE }

// One tracked primitive, as `.storybook/preview.tsx` registers it. An axis maps to its default, or to
// `null` when it has none.
export interface TrackedPrimitive {
  component: unknown
  directory: string
  axes: Record<string, string | null>
}
export type TrackedRegistry = Record<string, TrackedPrimitive>

// One tracked primitive instance, as rendered.
export interface Instance {
  component: string
  variant: string | null
  size: string | null
  disabledAt: string[]
}

// What the forced element, or the focused one, turned out to be. `stamp` is null for an element no
// design-system source file wrote (a story's own raw element); `placedBy` is the tracked primitive
// instance whose own file, or `cloneElement` call, placed it — null when none did.
export interface ElementRecord {
  stamp: string | null
  placedBy: Instance | null
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
  mounts: Instance[]
}

export interface InspectOptions {
  mode: 'element' | 'mounts'
  stampAttribute: string
  // Defaults to the page's own (`window.__DS_TRACKED_PRIMITIVES__`); tests pass a synthetic one.
  registry?: TrackedRegistry
}

// The one reader, serialised into the page by Playwright: no reference to anything outside this
// function's body (so the two modes share their helpers instead of drifting apart). `mode: 'element'`
// answers for one element — its stamp and the tracked instance that placed it; `mode: 'mounts'` for a
// story root — every tracked instance mounted under it. Both build an instance the same way.
//
// Which element an instance placed: a host element whose stamp falls under the directory of the
// nearest enclosing tracked instance of that directory's primitive. It is found walking DOWN the
// fiber tree with the enclosing instances carried along, never by identity across a walk up — React
// leaves `return` pointing at an alternate fiber on occasion, so two walks need not agree on a fiber.
export function inspect(start: Element, options: InspectOptions): ElementRecord | Instance[] {
  const registry: TrackedRegistry =
    options.registry ??
    (window as unknown as { __DS_TRACKED_PRIMITIVES__?: TrackedRegistry })
      .__DS_TRACKED_PRIMITIVES__ ??
    {}
  const attribute = options.stampAttribute
  type Fiber = {
    type?: unknown
    stateNode?: unknown
    child?: Fiber | null
    sibling?: Fiber | null
    return?: Fiber | null
    memoizedProps?: unknown
  }
  type Host = {
    getAttribute: (name: string) => string | null
    matches: (selector: string) => boolean
  }
  type Entry = {
    fiber: Fiber
    name: string
    props: Record<string, unknown>
    disabledAt: Set<string>
  }
  type Chain = { entry: Entry; up: Chain | null }

  const fiberOf = (node: object): Fiber | null => {
    for (const key of Object.keys(node)) {
      if (key.startsWith('__reactFiber$')) return (node as Record<string, Fiber>)[key]
    }
    return null
  }
  const nameOf = (fiber: Fiber): string | undefined =>
    Object.keys(registry).find((name) => fiber.type === registry[name].component)
  const stampFile = (stamp: string) => stamp.slice(0, stamp.lastIndexOf(':'))
  const axisOf = (entry: Entry, axis: string): string | null => {
    const axes = registry[entry.name].axes
    if (!(axis in axes)) return null
    const value = entry.props[axis] ?? axes[axis]
    return value === null || value === undefined ? null : String(value)
  }
  const record = (entry: Entry): Instance => ({
    component: entry.name,
    variant: axisOf(entry, 'variant'),
    size: axisOf(entry, 'size'),
    disabledAt: [...entry.disabledAt].sort(),
  })

  // Pre-order walk of `top`'s subtree (never its siblings): every tracked instance, in order, with
  // the stamps of the disabled host elements it placed.
  const walk = (top: Fiber): Entry[] => {
    const entries: Entry[] = []
    const stack: { fiber: Fiber; chain: Chain | null }[] = [{ fiber: top, chain: null }]
    while (stack.length > 0) {
      const { fiber, chain } = stack.pop() as { fiber: Fiber; chain: Chain | null }
      let here = chain
      const name = nameOf(fiber)
      if (name !== undefined) {
        const entry: Entry = {
          fiber,
          name,
          props: (fiber.memoizedProps ?? {}) as Record<string, unknown>,
          disabledAt: new Set(),
        }
        entries.push(entry)
        here = { entry, up: chain }
      } else if (typeof fiber.type === 'string' && fiber.stateNode) {
        const el = fiber.stateNode as Host
        const stamp = el.getAttribute(attribute)
        if (stamp) {
          const file = stampFile(stamp)
          let link = here
          while (link && !file.startsWith(registry[link.entry.name].directory)) link = link.up
          if (link && (el.matches(':disabled') || el.getAttribute('aria-disabled') === 'true')) {
            link.entry.disabledAt.add(stamp)
          }
        }
      }
      if (fiber !== top && fiber.sibling) stack.push({ fiber: fiber.sibling, chain })
      if (fiber.child) stack.push({ fiber: fiber.child, chain: here })
    }
    return entries
  }

  if (options.mode === 'mounts') {
    // The story root is the container React was mounted into, not an element React rendered, so it
    // has no fiber of its own: start from its first rendered child and climb to the top of the tree
    // (the preview mounts decorators and the story in one root; no tracked primitive sits outside the
    // story), then walk down.
    const first = start.firstElementChild
    if (!first) return []
    let top = fiberOf(first)
    if (!top) return []
    while (top.return) top = top.return
    return walk(top).map(record)
  }

  const stamp = start.getAttribute(attribute)
  if (!stamp) return { stamp: null, placedBy: null }
  const file = stampFile(stamp)
  let fiber = fiberOf(start)
  while (fiber) {
    const name = nameOf(fiber)
    if (name !== undefined && file.startsWith(registry[name].directory)) {
      // The placing instance is the first entry of its own subtree walk.
      return { stamp, placedBy: record(walk(fiber)[0]) }
    }
    fiber = fiber.return ?? null
  }
  return { stamp, placedBy: null }
}

// The two questions as functions of their own, for the unit tests and for readers that want a typed
// result. The page runs `inspect` (Playwright serialises one function, not its wrappers).
export function describeElement(
  el: Element,
  options: { stampAttribute: string; registry?: TrackedRegistry },
): ElementRecord {
  return inspect(el, { ...options, mode: 'element' }) as ElementRecord
}
export function describeMounts(
  root: Element,
  options: { stampAttribute: string; registry?: TrackedRegistry },
): Instance[] {
  return inspect(root, { ...options, mode: 'mounts' }) as Instance[]
}

// Set equality between the plants' assertions (`state-coverage-runtime.spec.ts`) and the fixture
// stories the built index lists: a fixture story with no assertion would be recorded and asserted
// against nothing, and an assertion with no fixture story would never run. One problem per
// disagreement, in id order; empty when the two sets are equal.
export function checkPlantCoverage(assertedIds: string[], fixtureIds: string[]): string[] {
  const asserted = new Set(assertedIds)
  const fixtures = new Set(fixtureIds)
  return [
    ...[...fixtures]
      .filter((id) => !asserted.has(id))
      .sort()
      .map((id) => `fixture story ${id} has no assertion in PLANTS`),
    ...[...asserted]
      .filter((id) => !fixtures.has(id))
      .sort()
      .map(
        (id) =>
          `PLANTS has an assertion for ${id}, but the built index lists no fixture story with that id`,
      ),
  ]
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
  const inspectOptions = (mode: 'element' | 'mounts'): InspectOptions => ({
    mode,
    stampAttribute: STAMP_ATTRIBUTE,
  })
  const record: WidthRecord = {
    mounts: (await root.evaluate(inspect, inspectOptions('mounts'))) as Instance[],
  }

  if (forceState) {
    const target = locateTarget(root, forceState)
    const count = await target.count()
    record.force =
      count === 1
        ? {
            count,
            ...((await target.evaluate(inspect, inspectOptions('element'))) as ElementRecord),
          }
        : { count, stamp: null, placedBy: null }
  }

  if (await storyHasPlay(page, storyId)) {
    const focused = page.locator(':focus')
    const holders = await focused.count()
    // `:focus` matches the body when nothing is focused only if the body is itself focusable; an
    // element that holds focus is exactly one, and one that is not the document body.
    const isBody = holders === 1 && (await focused.evaluate((el) => el === document.body))
    record.focus =
      holders === 1 && !isBody
        ? ((await focused.evaluate(inspect, inspectOptions('element'))) as ElementRecord)
        : null
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
