// Generated per run by `scripts/visual/run.mjs`, which decides *which* stories to test (all of
// them, or only the diff-affected ones) and expands each into one capture unit per {theme, width}
// pair — {light, dark} x {375, 768, 1280}, T504, FR-060/FR-061/SC-006. Each unit names its story
// id, its theme, its width and whether its subject escapes the story root (a `position: fixed`
// element, or a popover that overflows its trigger's layout box — see run.mjs for why that
// happens). This file stays dumb on purpose: it never re-derives scope or which axes apply to
// which story, it only renders what it is told to.
//
// The units travel as JSON in a file, named by `VISUAL_STORIES_FILE`, not inline in an env var
// (`VISUAL_STORIES`, retired): Linux caps a single argv/envp string at `MAX_ARG_STRLEN` (128 KiB),
// and the full, unscoped matrix's JSON is ~166 KB — comfortably over that ceiling on its own — so
// `run.mjs`'s `spawnSync` failed with `E2BIG` before Playwright ever started (confirmed on CI, run
// 33971176171). A path is a few dozen bytes regardless of how many units it names, which removes
// the ceiling entirely rather than working around it (chunking, as `.github/workflows/
// baselines.yml` used to, before this same file transport replaced its batching too).
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Locator, type Page, type Route } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
// `.cjs`, not `.mjs` — see that file's header comment. An `.mjs` sibling imported from here used to
// crash on CI (never locally): Playwright transpiles this spec to CommonJS, and a transpiled `.mjs`
// import is ambiguous to Node's loader in a way a `.cjs` import — unambiguously CommonJS by
// extension alone — cannot be.
import {
  componentFromTitle,
  isAllowed,
  recordScanned,
  recordViolation,
} from '../../scripts/visual/a11y-scan.cjs'

// Playwright loads this file as CommonJS unless the nearest package.json sets `"type": "module"`
// (playwright.config.ts's own comment) — `__dirname` is what stays valid either way.
const rootDir = path.resolve(__dirname, '..', '..')

// T507 (FR-057, FR-058, SC-007): each unit (below) carries only its story id, not its Storybook
// `title`, and the axe allowlist keys its entries by a human-readable component name
// derived from that title (see `componentFromTitle`) rather than by the raw id — so this reads the
// same built Storybook index `scripts/visual/run.mjs` already reads, purely to recover `title` for
// each id. This is a one-time lookup at module load, not part of the render loop below.
const storybookIndexPath = path.join(rootDir, 'packages/design-system/storybook-static/index.json')
const titleById = new Map<string, string>()
if (existsSync(storybookIndexPath)) {
  const index = JSON.parse(readFileSync(storybookIndexPath, 'utf8')) as {
    entries?: Record<string, { id: string; title: string }>
    stories?: Record<string, { id: string; title: string }>
  }
  for (const entry of Object.values(index.entries ?? index.stories ?? {})) {
    titleById.set(entry.id, entry.title)
  }
}

// The axe scan is a DOM/semantics question, not a rendering one: the same story in the same theme
// answers it identically at 375, 768 and 1280, so it runs once per story-theme pair rather than
// once per capture unit. 1280 is the designated width — fixed and named here, not "whichever unit
// happens to run first" (units run in parallel across workers with no defined order) — because it
// is the width every pre-existing baseline was captured at before T504 added the width axis, so it
// renders every story's full, uncollapsed structure rather than whatever a narrower breakpoint's
// structural swap (FR-019) produces.
const AXE_SCAN_WIDTH = 1280

// `player-avatar.md` §9 "the visual baseline must not depend on Steam": `PlayerAvatar` builds
// `https://avatars.steamstatic.com/<hash>_full.jpg` itself (that spec §2b), so any story that
// composes a loaded avatar fires a real request to that host unless it is fulfilled here from a
// local fixture. Applied unconditionally to every story in the loop below rather than only to the
// ones known to carry an avatar — this file stays "dumb" (see the header comment above) and never
// has to learn which story ids need which stub. Harmless for a story that never hits the host.
const STEAM_AVATAR_FIXTURE = readFileSync(
  path.join(rootDir, 'tests/visual/fixtures/steam-avatar.jpg'),
)

// The one hash `PlayerAvatar.stories.tsx` and `ProfileSummary.stories.tsx` both call
// `FIXTURE_HASH` / `FIXTURE_AVATAR_HASH` — a "Loaded" story is only real if it is genuinely a
// loaded image, so this is the only path the stub answers with the fixture above. Everything else
// under this host (`PlayerAvatar`'s `FailedHash` story deliberately builds a URL from a hash the
// CDN would never serve) is answered with a 404, so `onError` still fires and `FailedHash` stays
// pixel-identical to the empty-hash story — the one identity `player-avatar.md` §9 exists to
// prove. A stub that fulfilled every request on this host indiscriminately would make that story
// indistinguishable from `Loaded` and quietly retire the assertion it stands for.
const STEAM_AVATAR_FIXTURE_PATH = '/0123456789abcdef0123456789abcdef01234567_full.jpg'

type Theme = 'light' | 'dark'

interface VisualStory {
  id: string
  theme: Theme
  width: number
  fullPage: boolean
}

// Remediation of T565's blocking finding: a story's own `parameters.visualForceState` names a real
// CSS pseudo-class to drive from here, in a real browser, rather than inside the story's own
// `play()` — `userEvent.hover()`/`userEvent.tab()`/`userEvent.pointer()` dispatch synthetic
// (`isTrusted: false`) DOM events, which every JS event listener still receives (a component's own
// `onMouseEnter`/`onFocus` handler fires, which is why a structural reveal like `Tooltip`'s or
// `Menu`'s popover opening from `play()` is genuine) but which Chromium's `:hover`, `:active` and
// `:focus-visible` pseudo-classes never match — those are driven by the browser's real input
// pipeline alone. Measured empirically (not assumed) against a fresh Storybook iframe navigation,
// the same shape every capture unit below already is:
//   - `hover`: only `locator.hover()` (real, CDP-driven mouse move) moves the pointer in a way
//     `:hover` matches. A prior real `page.mouse` click elsewhere on the same page would also affect
//     this, but no capture unit before this one ever runs in the same page (each unit gets its own
//     `page.goto` above), so that never arises here.
//   - `active`: needs a genuine mouse button down, which only `page.mouse.down()` (after a real
//     `.hover()` onto the target) provides — `userEvent.pointer({ keys: '[MouseLeft>]' })` dispatches
//     a `pointerdown`/`mousedown` event, which every JS listener sees but which does not set
//     Chromium's own `:active` flag, itself tied to the platform's real button state.
//   - `focus-visible`: a plain script `element.focus()` call — even one this file makes directly,
//     not routed through any keyboard event at all — reliably matches `:focus-visible` in Chromium,
//     *provided nothing on this page has yet triggered a real, trusted pointer/mouse interaction*.
//     Confirmed by direct experiment: on a fresh page, `el.focus()` alone matches; the same call
//     after a real (CDP) `page.mouse` click anywhere on the page does not; a synthetic, untrusted
//     click (exactly what a story's own `play()` uses to open a menu or a popover) does *not* poison
//     it either, which is why a `play()` that opens a surface via `userEvent.click` and this file's
//     own subsequent `.focus()` on an item inside it coexist safely. A real, trusted keyboard `Tab`
//     (`page.keyboard.press('Tab')`) matches equally well and was verified as a second, independent
//     route — either is "real"; `.focus()` is used uniformly below because it does not depend on tab
//     order, which several of these components (`Table`'s scroll region, `Menu`'s roving items) would
//     otherwise make fragile.
// T568 (FR-047): none of the three routes above waits on the clock, on randomness or on the network
// — `hover()`/`mouse.down()`/`.focus()` are synchronous with respect to Playwright's own action
// waiting, so this adds no new source of flake.
interface VisualForceState {
  state: 'hover' | 'active' | 'focus-visible'
  // Exactly one of `selector` or `role` locates the element, scoped within `#storybook-root` (never
  // the whole page — a story's subject, even a `visual-full-page` one, is still that root's own DOM
  // descendant per this file's existing `#storybook-root` axe-scan comment above). `role` is paired
  // with `name` (Playwright's accessible-name matcher, substring by default) when more than one
  // element on the page shares that role; `nth` (0-based) breaks a tie no `name` can when several
  // elements share both role and accessible name (e.g. `Footer`'s first link, which has no name of
  // its own worth asserting on).
  selector?: string
  role?: string
  name?: string
  nth?: number
}

// Reads the settled story's own `parameters.visualForceState`, the same
// `window.__STORYBOOK_PREVIEW__.storyRenders` this file already reads (immediately below) to learn
// a story's render `phase` — not a second mechanism, the same one asked one more question. Returns
// `null` for every story that carries none, which is nearly all of them.
async function readForceState(page: Page, storyId: string): Promise<VisualForceState | null> {
  return page.evaluate((id: string) => {
    const preview = (
      window as unknown as {
        __STORYBOOK_PREVIEW__?: {
          storyRenders?: { id: string; story?: { parameters?: Record<string, unknown> } }[]
        }
      }
    ).__STORYBOOK_PREVIEW__
    const render = preview?.storyRenders?.find((r) => r.id === id)
    const forced = render?.story?.parameters?.visualForceState
    return (forced ?? null) as VisualForceState | null
  }, storyId)
}

// T591 (FR-037's verification half): a story that names a state whose signal is smaller than
// roughly 1% of its own frame — a 2px inline-start rule or a 1px boundary on a component sized in
// the hundreds of pixels — is structurally invisible to `story-baselines-duplicates.mjs`'s own
// tolerance regardless of whether the underlying CSS is correct. `visualCaptureClip`, a sibling
// parameter to `visualForceState` above and read the same way, names the part(s) of the story worth
// capturing instead of the whole `#storybook-root` box or the whole page, so the signal the story
// exists to prove occupies enough of the frame for the comparator to see it. `pad` is a spacing-
// scale step *name* (`space.json`'s own `scale` keys — '2' is `space.2`, 8px), resolved below from
// the page's own `--ds-space-*` custom property rather than a hand-picked px literal, the same rule
// every component source in this package already follows for a spacing value.
interface VisualCaptureClipPart {
  // Exactly one of `selector` or `role` locates the element, scoped within `#storybook-root` — see
  // `VisualForceState`'s own comment above for why `role`/`name`/`nth` share that shape here too.
  selector?: string
  role?: string
  name?: string
  nth?: number
}

interface VisualCaptureClip {
  // The clip rect is the union of every part's own `getBoundingClientRect()`, in page coordinates —
  // more than one part lets a story clip to, say, a trigger button AND the popover it opens, which
  // do not share a common ancestor smaller than the story root.
  parts: VisualCaptureClipPart[]
  // A `space.json` `scale` key, e.g. '2'. Defaults to '2' (`space.2`, 8px) when omitted.
  pad?: string
}

// Reads the settled story's own `parameters.visualCaptureClip` — the same
// `window.__STORYBOOK_PREVIEW__.storyRenders` lookup `readForceState` above already performs, asked
// one more question. Returns `null` for every story that carries none, which is nearly all of them.
async function readCaptureClip(page: Page, storyId: string): Promise<VisualCaptureClip | null> {
  return page.evaluate((id: string) => {
    const preview = (
      window as unknown as {
        __STORYBOOK_PREVIEW__?: {
          storyRenders?: { id: string; story?: { parameters?: Record<string, unknown> } }[]
        }
      }
    ).__STORYBOOK_PREVIEW__
    const render = preview?.storyRenders?.find((r) => r.id === id)
    const clip = render?.story?.parameters?.visualCaptureClip
    return (clip ?? null) as VisualCaptureClip | null
  }, storyId)
}

// One part's own box, located the same way `VisualForceState`'s `target` is located above — a
// selector or a role(+name), scoped to `root`, with `nth` breaking a tie. Throws (never returns a
// shrunken or empty clip) when the part matches zero or more-than-one element with no `nth` to
// disambiguate: a silently wrong clip would hide the very signal this parameter exists to surface,
// worse than the axe/render errors this file already lets propagate as a thrown test failure.
async function locateClipPart(root: Locator, storyId: string, part: VisualCaptureClipPart) {
  const role = part.role as Parameters<typeof root.getByRole>[0]
  const located = part.selector
    ? root.locator(part.selector)
    : root.getByRole(role, part.name !== undefined ? { name: part.name } : undefined)
  const scoped = typeof part.nth === 'number' ? located.nth(part.nth) : located
  const count = await scoped.count()
  if (count !== 1) {
    throw new Error(
      `visualCaptureClip: part ${JSON.stringify(part)} of story "${storyId}" matched ${count} ` +
        'element(s) — expected exactly 1 (add "nth" to disambiguate a part that matches more than one).',
    )
  }
  return scoped
}

// Resolves a `pad` step name to its px value from the page's own generated `--ds-space-*` custom
// property, never a literal duplicated from `space.json` — the same var Tailwind's own utilities
// (`p-3`, `gap-4`, ...) already resolve through. `space.json`'s `unit` is `rem`-based, so the
// returned string can be `rem` or already `px` depending on the step; both are handled without
// assuming which.
async function resolvePadPx(page: Page, step: string): Promise<number> {
  return page.evaluate((s: string) => {
    const raw = getComputedStyle(document.documentElement)
      .getPropertyValue(`--ds-space-${s}`)
      .trim()
    if (!raw)
      throw new Error(
        `visualCaptureClip: unknown spacing token step "${s}" (--ds-space-${s} is unset).`,
      )
    const value = Number.parseFloat(raw)
    if (Number.isNaN(value)) {
      throw new Error(
        `visualCaptureClip: could not parse "--ds-space-${s}" value "${raw}" as a number.`,
      )
    }
    return raw.trim().endsWith('rem') ? value * 16 : value
  }, step)
}

// The clip rect `expect(page).toHaveScreenshot` takes: the union of every part's own box (page
// coordinates, via `getBoundingClientRect()` + the page's own scroll offsets), inflated by `padPx`
// on every side, clamped to the page's own scrollable extent so the inflation can never request a
// rect outside what Playwright can actually capture.
async function resolveCaptureClip(
  page: Page,
  root: Locator,
  storyId: string,
  clip: VisualCaptureClip,
): Promise<{ x: number; y: number; width: number; height: number }> {
  const padPx = await resolvePadPx(page, clip.pad ?? '2')

  let union: { left: number; top: number; right: number; bottom: number } | null = null
  for (const part of clip.parts) {
    const located = await locateClipPart(root, storyId, part)
    const box = await located.evaluate((el) => {
      const rect = el.getBoundingClientRect()
      return {
        left: rect.left + window.scrollX,
        top: rect.top + window.scrollY,
        right: rect.right + window.scrollX,
        bottom: rect.bottom + window.scrollY,
      }
    })
    union = union
      ? {
          left: Math.min(union.left, box.left),
          top: Math.min(union.top, box.top),
          right: Math.max(union.right, box.right),
          bottom: Math.max(union.bottom, box.bottom),
        }
      : box
  }
  if (!union) {
    throw new Error(`visualCaptureClip: story "${storyId}" names no parts.`)
  }

  const pageExtent = await page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight,
  }))

  const left = Math.max(0, union.left - padPx)
  const top = Math.max(0, union.top - padPx)
  const right = Math.min(pageExtent.width, union.right + padPx)
  const bottom = Math.min(pageExtent.height, union.bottom + padPx)

  return { x: left, y: top, width: right - left, height: bottom - top }
}

// `run.mjs` always sets `VISUAL_STORIES_FILE`; `tests/visual/app-routes.spec.ts` is Playwright's
// other spec under this same config and takes no units at all, so an unset var here (any run that
// selects `stories.spec.ts` at all comes from `run.mjs` or `baselines.yml`, both of which set it)
// falls back to an empty list rather than throwing.
const storiesFilePath = process.env.VISUAL_STORIES_FILE
const stories: VisualStory[] = storiesFilePath
  ? (JSON.parse(readFileSync(storiesFilePath, 'utf8')) as VisualStory[])
  : []

for (const { id, theme, width, fullPage } of stories) {
  test(`${id} matches its visual baseline (${theme}, ${width})`, async ({ page }) => {
    await page.route('https://avatars.steamstatic.com/**', (route: Route) => {
      const requestUrl = new URL(route.request().url())
      if (requestUrl.pathname === STEAM_AVATAR_FIXTURE_PATH) {
        return route.fulfill({ status: 200, contentType: 'image/jpeg', body: STEAM_AVATAR_FIXTURE })
      }
      return route.fulfill({ status: 404 })
    })
    // Width is what collapses a table to a stacked layout at the `md` breakpoint; height's only
    // job here is to stay identical to what every pre-existing baseline was already captured at,
    // because a `fullPage: false` (element-clipped) screenshot is height-independent but a
    // `fullPage: true` one (a fixed dialog, a popover) is not: a fixed-position dialog centers
    // against the viewport, so a taller viewport measurably shifts its content (confirmed: T505's
    // first attempt used height 900 unconditionally and moved 44 pre-existing baselines, four of
    // them `AccountErasePanel` dialogs, by a real 15-20% pixel diff, not a tolerance artifact).
    // Before T504, only the ten `visual-mobile`-tagged stories called `setViewportSize` at all, at
    // {375, 900}; every other capture had no explicit call and rendered at Playwright's
    // `devices['Desktop Chrome']` preset default, {1280, 720}. T504 made every width call this
    // unconditionally (correctly — the loop needs one shape for every unit, matching this file's
    // "stays dumb" rule above) but collapsed the height to one constant, which broke that
    // inherited identity for every 1280-wide capture. So: 375 keeps its pre-existing 900, and
    // every other width — including the new 768, which has no pre-existing baseline to match —
    // uses the desktop default of 720, so 768 and 1280 share one convention instead of inventing a
    // third with no history behind it. Do not simplify this back to one constant.
    const height = width === 375 ? 900 : 720
    await page.setViewportSize({ width, height })
    // Mirrors `tests/visual/focus-ring.spec.ts`'s exact URL pattern for driving the theme global.
    await page.goto(`/iframe.html?id=${id}&viewMode=story&globals=theme:${theme}`)
    // Storybook mounts every story under this id; waiting for it removes the render race that
    // would otherwise make the very first screenshot after a baseline change flaky.
    const root = page.locator('#storybook-root')
    await root.waitFor({ state: 'visible' })
    // `waitFor({ state: 'visible' })` only proves the root element exists — it says nothing about
    // whether the story is still mutating the DOM. Playwright's own screenshot stability polling
    // (retinting until two consecutive frames match) only kicks in once a baseline already exists;
    // the very first capture of a story — which is exactly the state a new baseline is taken from —
    // fires immediately with no such polling. A story with a `play()` (Tooltip's hover/focus-reveal
    // stories among them) is still running its interaction, and possibly a CSS transition it
    // triggered, well after the root is visible, so that first screenshot can bake in a pre-play or
    // mid-transition frame.
    //
    // Storybook 10.5.9 exposes the render driving this story as an entry in
    // `window.__STORYBOOK_PREVIEW__.storyRenders` (confirmed by reading the installed
    // `storybook/dist/preview/runtime.js`'s `StoryRender` class, not assumed from an API guess).
    // Its `.phase` advances `preparing -> loading -> rendering -> playing -> played -> completing
    // -> completed -> afterEach -> finished` for a story that renders cleanly, and short-circuits
    // to `errored` (still followed by `finished`) if the story or its `play()` throws. `completing`
    // is where Storybook itself awaits any CSS transition or Web Animation the story's own render
    // started (its `waitForAnimations`) — the exact class of thing `duration-120` fade-ins like
    // Tooltip's reveal are — so `played` alone is not enough: it fires *before* that wait. Waiting
    // past it, for `completed` (or `finished`/`errored`, reached by a story with no `play()` at all
    // or one whose `play()` failed), is therefore what a story with a play function AND a story
    // without one both eventually reach — no per-story branching, no knowledge here of which
    // stories carry a `play()`, matching this file's "stays dumb" rule above.
    await page.waitForFunction(
      (storyId: string) => {
        const preview = (
          window as unknown as {
            __STORYBOOK_PREVIEW__?: { storyRenders?: { id: string; phase?: string }[] }
          }
        ).__STORYBOOK_PREVIEW__
        const render = preview?.storyRenders?.find((r) => r.id === storyId)
        return !!render && ['completed', 'finished', 'errored'].includes(render.phase ?? '')
      },
      id,
      { timeout: 5_000 },
    )
    // typography-tokens.md §10: with `font-display: swap` a story can be screenshotted in the
    // fallback face if the capture beats the font — the DOM has rendered, but the render has not
    // finished, the same class of wait as the `completing`-state one directly above. Waited here,
    // after the story-settled wait and before the axe scan and the screenshot, so neither ever
    // runs against a mid-swap frame.
    await page.evaluate(() => document.fonts.ready)

    // Remediation of T565's blocking finding (see `VisualForceState`'s own comment above): drives
    // the real CSS pseudo-class a vocabulary-state story names, in this real browser, after the
    // story has settled and before anything reads or captures it — a real `:hover`/`:active` must
    // still be showing at the moment of the screenshot below, and the axe scan just after this block
    // runs against the same forced DOM state a reader would actually see.
    const forceState = await readForceState(page, id)
    let releaseMouseAfterCapture = false
    if (forceState) {
      // Several of these pseudo-classes paint through a token-driven CSS transition
      // (`transition-colors duration-120` on `Button`, for one) rather than an instant swap.
      // `.hover()`/`page.mouse.down()`/`.focus()` below resolve as soon as the input itself has
      // been dispatched, not once the transition it triggers has finished animating — confirmed
      // empirically: without this, `Button`'s own `Hover` story captured byte-identical to its
      // resting state, the transition's very first (unchanged) frame. Disabling every transition
      // and animation for the page removes the race outright rather than papering over it with a
      // fixed wait, which is also what FR-047 asks for ("no dependence on ... an unsettled
      // animation") — the forced state now paints in the same frame it is applied, deterministically,
      // instead of racing a clock.
      await page.addStyleTag({
        content:
          '*, *::before, *::after { transition: none !important; animation: none !important; }',
      })
      const target = (() => {
        // `role` travels as a plain string from a story's own `parameters`, not as Playwright's
        // `AriaRole` union, hence the cast — the string itself still reaches a real ARIA role query.
        const role = forceState.role as Parameters<typeof root.getByRole>[0]
        const located = forceState.selector
          ? root.locator(forceState.selector)
          : root.getByRole(
              role,
              forceState.name !== undefined ? { name: forceState.name } : undefined,
            )
        return typeof forceState.nth === 'number' ? located.nth(forceState.nth) : located
      })()
      if (!fullPage && (forceState.state === 'hover' || forceState.state === 'active')) {
        // `:hover`/`:active` are anchored to the mouse's actual viewport position, not to the
        // element — a root taller than the viewport (every `screens/*` composition at 375) needs
        // Playwright to scroll during `.hover()` to bring the target into view, and needs to scroll
        // again while stitching a full-element screenshot taller than one viewport. The pointer
        // itself never moves during that second scroll, so whatever now sits under its fixed
        // viewport coordinate — not the element we hovered — is what ends up `:hover`ed by the time
        // the capture actually happens. Confirmed empirically: `ThirdPartyObjectionForm`'s `Hover`
        // story (a root 1596px tall, well past the 900px viewport at 375) captured byte-identical to
        // its own resting state even though `getComputedStyle` read the correct hovered colour
        // immediately after `.hover()` — the scroll that followed, internal to the screenshot call,
        // silently lost it. Growing the viewport to the full content height before hovering removes
        // the second scroll entirely, so nothing can move under the pointer between the hover and
        // the capture.
        //
        // Only for `!fullPage`: the comment above `setViewportSize` a few lines up is the reason —
        // a `fullPage: true` subject (a `position: fixed` dialog, an absolutely positioned popover)
        // is height-*dependent*, a fixed dialog centers against the viewport and a taller one
        // measurably shifts its content (T505's own finding, moved 44 baselines). None of this
        // suite's `fullPage: true` + hover/active stories are taller than their starting viewport in
        // practice (confirmed: `Menu`'s `Hover`/`Active` already capture correctly without this), so
        // the height this branch would otherwise grow never needs to move for them, and this stays
        // narrowly scoped to the case that does.
        const contentHeight = await root.evaluate((el) => el.scrollHeight)
        if (contentHeight > height) {
          await page.setViewportSize({ width, height: contentHeight })
        }
      }
      if (forceState.state === 'hover') {
        await target.hover()
      } else if (forceState.state === 'active') {
        await target.hover()
        await page.mouse.down()
        releaseMouseAfterCapture = true
      } else if (forceState.state === 'focus-visible') {
        await target.evaluate((el: HTMLElement) => el.focus())
      }
    }

    // T507 (FR-057, FR-058, SC-007): runs here, on the same settled DOM the screenshot below is
    // about to capture — "at the point the screenshot is taken" — but *before* that assertion
    // rather than after: `toHaveScreenshot` throws on the first pixel mismatch, and a real (or
    // locally-rendered, research D3) diff must never silently skip the accessibility check for a
    // story that would otherwise have been scanned this run. Only once per story-theme pair, at
    // the designated width (see `AXE_SCAN_WIDTH` above), not once per capture unit, and reusing
    // this loop's scoping and theme mechanism rather than a second harness (research D12).
    if (width === AXE_SCAN_WIDTH) {
      const component = componentFromTitle(titleById.get(id) ?? id)
      // Scoped to `#storybook-root` — the story's own wrapper — rather than the whole page.
      // Confirmed empirically (not assumed): scanning the whole `iframe.html` document reports
      // `landmark-one-main` and `page-has-heading-one` on *every single story*, because axe's
      // page-level rules run against `document` the moment the include selector is not scoped —
      // and a component preview correctly has neither; only a full application page owns a main
      // landmark and a heading. Those are Storybook's chrome, not the design system's, exactly the
      // failure mode this comment is here to explain. Scoping to the root removes them entirely and
      // still catches every element-level rule (color-contrast, aria-*, button-name, and so on).
      // A `visual-full-page` story's subject (a fixed dialog, an open popover) still gets scanned
      // even though its *screenshot* goes full-page: none of these components use a portal
      // (`ReactDOM.createPortal`, confirmed absent from `packages/design-system/src`), so a
      // `position: fixed` element stays a DOM descendant of `#storybook-root` — only its painted
      // position escapes the root's layout box, which is a screenshot-clipping concern, not a DOM
      // membership one, and axe's `include` scopes by the latter.
      const axeResults = await new AxeBuilder({ page }).include('#storybook-root').analyze()

      // Recorded whether or not the rule below turns out to be allowlisted, and even when this
      // story has no violation at all — `checkStaleness` (in `run.mjs`, after the whole suite
      // finishes) needs every component this run actually scanned, not only the ones that failed,
      // to tell "the fix already happened" (stale) apart from "this run never looked" (silent).
      recordScanned(component, theme)
      for (const violation of axeResults.violations) {
        recordViolation(component, theme, violation.id)
      }

      const unallowed = axeResults.violations.filter(
        (violation) => !isAllowed(component, violation.id),
      )
      if (unallowed.length > 0) {
        const details = unallowed
          .map((violation) => {
            const nodes = violation.nodes
              .map((node) => `      ${node.target.join(' ')}\n      ${node.html}`)
              .join('\n')
            return `  [${violation.impact ?? 'unknown'}] ${violation.id} — ${violation.help}\n${nodes}`
          })
          .join('\n')
        throw new Error(
          `axe-core found ${unallowed.length} accessibility violation(s) in "${component}" ` +
            `(${theme} theme, story ${id}) not covered by scripts/visual/a11y-allowlist.json:\n${details}`,
        )
      }
    }

    const baselineName = `${id}-${theme}-${width}.png`
    // `visualCaptureClip` takes precedence over `fullPage` (T591): a story that carries both would
    // mean its own `visual-full-page` tag was never removed when the clip was added — the clip is
    // still the more specific, more correct capture, so it wins rather than the two silently racing.
    const captureClip = await readCaptureClip(page, id)
    if (captureClip) {
      const clip = await resolveCaptureClip(page, root, id, captureClip)
      await expect(page).toHaveScreenshot(baselineName, { fullPage: true, clip })
    } else if (fullPage) {
      // The story's own subject (a fixed dialog, an open popover) paints outside the root
      // element's layout box, so a screenshot clipped to that element never shows it — this
      // captures the whole page instead.
      await expect(page).toHaveScreenshot(baselineName)
    } else {
      await expect(root).toHaveScreenshot(baselineName)
    }

    // Releases the real mouse-down `active` above started — harmless to skip (the page closes with
    // the test either way), done anyway so a future addition after this block never inherits a
    // button Playwright still believes is held down.
    if (releaseMouseAfterCapture) {
      await page.mouse.up()
    }
  })
}
