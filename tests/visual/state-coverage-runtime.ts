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
//   - the page's stamp attribute is `STAMP_ATTRIBUTE`, imported from `source-stamp-attribute.cjs`, the one definition the
//     transform that writes it re-exports, and handed to the page as an argument.
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
import { STAMP_ATTRIBUTE } from '../../packages/design-system/.storybook/source-stamp-attribute.cjs'
import {
  gotoAndWaitForStorySettled,
  locateTarget,
  readCaptureClip,
  readForceState,
} from './story-render'
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
//
// `clip` and `fullPage` are the two facts about the capture frame the credit for a story's mounts
// rests on (T703). `clip` is whether a `visualCaptureClip` applied in EITHER theme at this width
// (T706, the disjunction of the two themes the capture runs): `readCaptureClip` (`story-render.ts`),
// the reader `stories.spec.ts` captures through, run on the SETTLED story (after the loaders, the
// decorators and the `play()` that may write to `parameters`) and read through the same
// `story.parameters` object, its prototype chain included — so a clip that no object literal spells
// reaches this record. `mounts`, `files`, `force` and `focus` are recorded from the light render
// only: an element only the dark render mounts is not credited, and an element only the light render
// mounts is credited though the dark capture does not show it (a decorator branching on
// `context.globals.theme` can do either), an over-credit T710 records as open. Cookies, `localStorage`
// and `sessionStorage` are cleared before each settle; IndexedDB, Cache Storage and `window.name` are
// not, and nothing in the design system uses them. A capture unit starts in a fresh browser context
// (`stories.spec.ts`), which clears all of them. `fullPage` is whether
// the capture takes the whole page when no clip applies, from the built index's tags, the one place the
// capture reads it (`isFullPageEntry`, `story-index.mjs`). A clip wins over the tag, as it does in the
// capture.
export interface WidthRecord {
  clip: boolean
  fullPage: boolean
  force?: ForceRecord
  focus?: ElementRecord | null
  mounts: Instance[]
  // The sorted unique repository-rooted source files that rendered a stamped element in the story's
  // document at this width. `buildEntry` (`scripts/visual/state-coverage-runtime-model.mjs`) unions it
  // across widths into the entry's own `files` and keeps it out of the per-width record.
  files: string[]
}

export interface InspectOptions {
  mode: 'element' | 'mounts' | 'files'
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
// fiber tree with the enclosing instances carried along.
//
// Which tree: the COMMITTED one. React writes `__reactFiber$` on a DOM node once, when it creates it;
// after updates that fiber may be either of the node's current/alternate pair, and a `return` pointer
// may lead to the alternate parent as well (a subtree an update never reached keeps the `return` it
// had). Climbing `return` from a node can therefore end at the alternate HostRoot, whose children are
// the PREVIOUS render's — stale variants, sizes, mounts and disabled elements. So `return` is used
// for one thing only, reaching the HostRoot (every chain ends at the same FiberRoot, whichever of the
// pair it passes through); from there everything is read in `root.stateNode.current`, and an
// element's ancestors are the path found DESCENDING to it, never a climb. `tests/…` of the fiber
// reader against real React are `packages/design-system/src/test/state-coverage-fiber.test.tsx`.
export function inspect(
  start: Element,
  options: InspectOptions,
): ElementRecord | Instance[] | string[] {
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

  // The committed tree's root fiber, reached from any fiber of the tree. A fiber with no `return` is a
  // HostRoot, whose `stateNode` is the FiberRoot and whose `current` is the committed HostRoot. The
  // synthetic fibers of `state-coverage-runtime-probe.spec.ts` have no FiberRoot: their top is the root.
  const committedRoot = (from: Fiber): Fiber => {
    let top = from
    while (top.return) top = top.return
    const fiberRoot = top.stateNode as { current?: Fiber } | null | undefined
    return fiberRoot && typeof fiberRoot === 'object' && fiberRoot.current ? fiberRoot.current : top
  }

  if (options.mode === 'files') {
    // Every stamped element of the document, not only of the story root: a menu or a dialog renders
    // in a portal on `document.body`, and the preview shows one story per page, so whatever carries
    // a stamp there belongs to this story. Only the file part is kept — a line shift is not a change
    // of what a story depends on.
    const files = new Set<string>()
    for (const el of Array.from(start.ownerDocument.querySelectorAll(`[${attribute}]`))) {
      const stamp = el.getAttribute(attribute)
      if (stamp) files.add(stampFile(stamp))
    }
    return [...files].sort()
  }

  if (options.mode === 'mounts') {
    // The story root is the container React was mounted into, not an element React rendered, so it
    // has no fiber of its own: start from its first rendered child, reach the committed root (the
    // preview mounts decorators and the story in one root; no tracked primitive sits outside the
    // story), then walk down.
    const first = start.firstElementChild
    if (!first) return []
    const seed = fiberOf(first)
    if (!seed) return []
    return walk(committedRoot(seed)).map(record)
  }

  const stamp = start.getAttribute(attribute)
  if (!stamp) return { stamp: null, placedBy: null }
  const file = stampFile(stamp)
  const seed = fiberOf(start)
  if (!seed) return { stamp, placedBy: null }

  // The path from the committed root to the fiber whose `stateNode` is the element, found by
  // descending (`child`, `sibling`), so every ancestor on it is in the committed tree.
  const path: Fiber[] = []
  const descend = (fiber: Fiber | null | undefined): boolean => {
    for (let node = fiber; node; node = node.sibling) {
      path.push(node)
      if (node.stateNode === start) return true
      if (descend(node.child)) return true
      path.pop()
    }
    return false
  }
  const root = committedRoot(seed)
  // An element that is not in the committed tree (unmounted since) was placed by nobody.
  if (root.stateNode !== start && !descend(root.child)) return { stamp, placedBy: null }
  path.unshift(root)
  for (let i = path.length - 1; i >= 0; i -= 1) {
    const fiber = path[i]
    const name = nameOf(fiber)
    if (name !== undefined && file.startsWith(registry[name].directory)) {
      // The placing instance is the first entry of its own subtree walk.
      return { stamp, placedBy: record(walk(fiber)[0]) }
    }
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
export function describeFiles(
  root: Element,
  options: { stampAttribute: string; registry?: TrackedRegistry },
): string[] {
  return inspect(root, { ...options, mode: 'files' }) as string[]
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
  fullPage: boolean,
): Promise<WidthRecord> {
  await assertRegistryPresent(page)
  const inspectOptions = (mode: 'element' | 'mounts' | 'files'): InspectOptions => ({
    mode,
    stampAttribute: STAMP_ATTRIBUTE,
  })
  const record: WidthRecord = {
    // The capture's own test: `if (captureClip)`, so a falsy clip is no clip.
    clip: Boolean(await readCaptureClip(page, storyId)),
    fullPage,
    mounts: (await root.evaluate(inspect, inspectOptions('mounts'))) as Instance[],
    files: (await root.evaluate(inspect, inspectOptions('files'))) as string[],
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

// Clears what a previous settle of this page may have left for the next one: the context's cookies and
// the `localStorage` and `sessionStorage` of the origin the page is on. IndexedDB, Cache Storage and
// `window.name` are not cleared, and nothing in the design system uses them. `stories.spec.ts` gives
// every capture unit a fresh browser context, which clears all of them, while this spec reuses one page
// for every theme and width, so without this a decorator or loader that writes a flag in the light
// settle (the design system's own `ThemeProvider` writes `localStorage`) would show it to the dark
// settle the capture never sees it in.
// Storage can only be cleared from a page on the right origin: a page that has not navigated yet is on
// `about:blank`, where reading `localStorage` throws, and where nothing of this page's was written.
async function clearBrowserState(page: Page): Promise<void> {
  await page.context().clearCookies()
  try {
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  } catch {
    // `about:blank` or an opaque origin: no storage of ours to clear.
  }
}

// Navigates to a story at one width and settles it the way `stories.spec.ts` does, in both themes the
// capture runs, each settle starting from cleared cookies, `localStorage` and `sessionStorage`
// (`clearBrowserState`, T708; a capture unit's fresh context clears more). What is recorded per theme (T706, T708): `mounts`, `files`,
// `force` and `focus` are recorded from the LIGHT render only, and `clip` from both. A render that
// depends on the theme (a decorator, a loader or a `play()` branching on `context.globals.theme`) is
// credited from the light render only: an element the dark render alone mounts is not credited, and an
// element the light render alone mounts is credited though the dark capture does not show it, which
// T710 records as an open over-credit. `clip` is the exception because the capture
// reads it at each theme: the story is settled a second time at the same width in the DARK theme,
// through the same `gotoAndWaitForStorySettled`, and `clip` is recorded true when either theme applied
// one. `fullPage` comes from the built index and does not depend on the theme.
export async function probeStory(
  page: Page,
  storyId: string,
  width: number,
  fullPage: boolean,
): Promise<WidthRecord> {
  // The same height rule `stories.spec.ts` applies per unit (see the comment there).
  const height = width === 375 ? 900 : 720
  await clearBrowserState(page)
  const root = await gotoAndWaitForStorySettled(page, storyId, 'light', width, height)
  const forceState = await readForceState(page, storyId)
  const record = await probeSettledStory(page, root, storyId, forceState, fullPage)
  await clearBrowserState(page)
  await gotoAndWaitForStorySettled(page, storyId, 'dark', width, height)
  // The capture's own test, `if (captureClip)`: a falsy clip is no clip.
  const darkClip = Boolean(await readCaptureClip(page, storyId))
  return { ...record, clip: record.clip || darkClip }
}
