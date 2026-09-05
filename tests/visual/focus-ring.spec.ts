// T096 defect 2 regression (visual review): every interactive primitive in this package composes
// `outline-none` (hide the default browser outline at rest) with `focus-visible:outline-2
// focus-visible:outline-offset-2 focus-visible:outline-focus-ring` — DS-4's one documented ring.
// Tailwind's `outline-none` sets the shared `--tw-outline-style` custom property to `none`
// unconditionally (`.outline-none{--tw-outline-style:none;outline-style:none}`), and `outline-2`
// only *reads* that property (`outline-style:var(--tw-outline-style)`) rather than resetting it —
// so the ring never painted under `:focus-visible`, on any of them, in either theme:
// `getComputedStyle(activeEl).outlineStyle === 'none'` even while `el.matches(':focus-visible')`
// was true. This is an interaction test, not a screenshot: no story in the static suite ever
// renders a focused control, which is exactly why the bug shipped unnoticed, and a screenshot
// proves nothing here unless something actually focuses the element via the keyboard first.
//
// T506 extends this from five representative controls to every focus-ring declaration the package
// ships. The enumeration method: `grep -rn "outline-focus-ring" packages/design-system/src
// --include="*.tsx"` against non-story, non-test source turns up every independent place a
// component attaches this treatment to a rendered element — 14 call sites as of this change. Each
// site is one control below unless a second, structurally identical instance in the same file
// sits on the same background and would only re-run the same assertion (documented inline where
// that happens); a site whose *only* two renderings differ in element type, background, or
// keyboard reach (Button's `<button>` vs its `href` `<a>`; SiteHeader's ordinary `NavItem` anchor
// vs its `sr-only`-until-focus skip link; Menu's outward-ring trigger vs its two inward/outward
// item buttons reached only by opening the menu) gets one control per rendering. That yields the
// 16 controls below, each run in both themes — 32 cases.
//
// T506 also adds the assertion this file never had: the ring must clear WCAG 1.4.11's non-text
// contrast floor (3:1) against the surface it is actually painted on, not an assumed one. See the
// `relativeLuminance`/`contrastRatio` pair below for the formula and why it is a second, small
// implementation rather than a shared import.
//
// That assertion finds a real defect on two of the sixteen controls: `Button` `primary` and
// `DataExportPanel`'s download link both fill with `accent` and ring with `focus-ring` — the same
// pair in both themes, since `focus-ring` was derived only against page surfaces
// (`surface`/`background`, 5.78-6.82:1 there) and never against the accent-filled controls it also
// paints on. Measured: light `focus-ring` `#2f5f73` on `accent` `#916626` = 1.38:1; dark
// `focus-ring` `#6fa8c0` on `accent` `#d9a94b` = 1.21:1 — both under the 3:1 floor. Fixing it here
// (changing `focus-ring`) would repaint every visual baseline while T505's phase-1 byte-identity
// proof is running, and the token-derivation work belongs to phase 2 regardless: T521 re-derives
// `color.json` so every semantic role declares the surfaces it may be painted on, and T526
// re-measures the contrast table so every pair a component actually paints gets a row (see
// `packages/design-system/specs/README.md`, gap DS-10). Until then these four cases (the two
// accent-filled controls x two themes) are `test.fail()` — a strict expected failure, never a
// `test.skip()` — driven off `knownContrastFailure` on the `Control` entry below: every assertion
// in the test body still runs, and the moment T521/T526 land, the pair passing turns this an
// "unexpected pass" that fails the suite rather than a silently stale marker.
import { test, expect, type Locator, type Page } from '@playwright/test'

interface Control {
  /** A free-form label, not a closed enum: the set below is derived from source (see the header
   * comment's enumeration method), not hand-picked, so a literal union would just be restating the
   * array. */
  level: string
  storyId: string
  locate: (page: Page) => Locator
  /** Overrides the default plain-Tab reach for a control whose only path to keyboard focus is
   * through the component's own keyboard handling (opening a menu) rather than sequential Tab —
   * still a genuine keyboard interaction, never a programmatic `.focus()` call. Must leave the
   * target focused and ready for `:focus-visible`/style assertions when it resolves. */
  reach?: (page: Page, target: Locator) => Promise<void>
  /** Present only on the two controls known to fail the WCAG 1.4.11 non-text contrast floor (gap
   * DS-10, `packages/design-system/specs/README.md`): `focus-ring` measured against `accent`,
   * the fill both controls actually paint on focus, one ratio per theme. Drives `test.fail()`
   * below so the marker lives on the data, not on a hand-branch keyed off `level`/`theme` in the
   * test body. T521 re-derives the token; T526 owns removing this field once the pair clears 3:1. */
  knownContrastFailure?: Readonly<{ light: number; dark: number }>
}

// Genuine keyboard focus, not a programmatic `.focus()` call — Chromium's `:focus-visible`
// heuristic is about *how* focus arrived, and the remediation brief asks for a control "focused
// via keyboard" specifically.
async function focusViaKeyboard(page: Page, target: Locator): Promise<void> {
  await target.waitFor({ state: 'visible' })
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  for (let attempt = 0; attempt < 50; attempt += 1) {
    await page.keyboard.press('Tab')
    const isTarget = await target.evaluate((el) => el === document.activeElement).catch(() => false)
    if (isTarget) return
  }
  throw new Error('could not reach the target control by pressing Tab')
}

// Every "open" story in Menu.stories.tsx opens its surface with a `play` function that clicks the
// trigger on mount (that file's own reasoning: the popover only exists once open, so its baseline
// has to show one). By the time this test's page loads, the menu is already open and whatever item
// the mount effect focused got there via that mouse click — not the keyboard reach this file
// exists to test. This closes that pre-opened surface with Escape (itself keyboard-driven, and
// exercised the same way a real keyboard user would dismiss it), then reopens it with Enter on the
// trigger, which is a genuine open transition and lets `MenuItemRow`'s roving-tabindex effect
// re-focus the active item as a direct, synchronous consequence of that keypress.
async function openMenuViaKeyboard(page: Page, triggerName: string): Promise<void> {
  const trigger = page.getByRole('button', { name: triggerName })
  await trigger.waitFor({ state: 'visible' })
  const menu = page.getByRole('menu')
  await menu.waitFor({ state: 'visible', timeout: 5000 }).catch(() => undefined)
  if (await menu.count()) {
    await page.keyboard.press('Escape')
    await menu.waitFor({ state: 'detached', timeout: 5000 }).catch(() => undefined)
  }
  await focusViaKeyboard(page, trigger)
  await page.keyboard.press('Enter')
  await menu.waitFor({ state: 'visible' })
}

const controls: readonly Control[] = [
  // --- The original five (T096 defect 2) ---
  {
    // `bg-accent` at rest (Button/index.tsx's `primary` variant) — gap DS-10, see the header
    // comment: the ring fails the 3:1 floor against its own fill in both themes.
    level: 'Button',
    storyId: 'primitives-button--primary',
    locate: (page) => page.getByRole('button', { name: 'Continue with Steam' }),
    knownContrastFailure: { light: 1.38, dark: 1.21 },
  },
  {
    level: 'Input',
    storyId: 'composite-searchbox--idle',
    locate: (page) => page.getByLabel('Search a player'),
  },
  {
    level: 'checkbox',
    storyId: 'screens-accounterasurepanel--confirming',
    locate: (page) => page.getByRole('checkbox', { name: 'I understand this cannot be undone.' }),
  },
  {
    level: 'link',
    storyId: 'screens-privacynotice--default',
    locate: (page) => page.getByRole('link', { name: 'Object to archival' }),
  },
  {
    level: 'NavItem',
    storyId: 'chrome-siteheader--signed-in',
    locate: (page) => page.getByRole('link', { name: 'Matches' }),
  },

  // --- T506 additions, one per remaining `outline-focus-ring` call site (see header comment) ---
  {
    // Button/index.tsx:54 — same declaration as `Button` above, applied to the `<a href>` render
    // path instead of `<button>`. Different element, same class string; worth its own case since
    // the two paths could diverge independently.
    level: 'Button (href variant)',
    storyId: 'primitives-button--as-link',
    locate: (page) => page.getByRole('link', { name: 'Read the privacy notice' }),
  },
  {
    // SiteHeader/index.tsx:34's `focusRing` constant also styles the skip link — the one element
    // in this package that is `sr-only` until it is focused, so the ring's own visibility depends
    // on that reveal firing correctly first. The ordinary nav anchor and the brand wordmark share
    // this exact constant and background (`bg-surface`, already the `NavItem` control's surface),
    // so they are not repeated here.
    level: 'SkipLink',
    storyId: 'chrome-siteheader--signed-in',
    locate: (page) => page.getByRole('link', { name: 'Skip to content' }),
  },
  {
    // Tooltip/index.tsx:272 — the trigger button is `bg-transparent` at rest, so its ring's
    // contrast has to resolve against whatever ancestor actually paints behind it, exercising the
    // walk-up-the-tree half of the contrast assertion below.
    level: 'Tooltip trigger',
    storyId: 'primitives-tooltip--default',
    locate: (page) => page.getByRole('button', { name: 'France' }),
  },
  {
    // Menu/index.tsx:142 — the trigger, reached by plain Tab; it does not need `openMenuViaKeyboard`
    // itself; it IS what that helper tabs to before opening the surface.
    level: 'Menu trigger',
    storyId: 'primitives-menu--profile-switcher',
    locate: (page) => page.getByRole('button', { name: 'aoe2guy — profile ▾' }),
  },
  {
    // Menu/index.tsx:257 — an inward-offset ring (`-outline-offset-2`), the opposite of every other
    // control in this file, on the item that opening the menu makes active by default (the checked
    // one, "aoe2guy").
    level: 'Menu item',
    storyId: 'primitives-menu--profile-switcher',
    locate: (page) => page.getByRole('menuitemradio', { name: /aoe2guy/ }),
    reach: (page) => openMenuViaKeyboard(page, 'aoe2guy — profile ▾'),
  },
  {
    // Menu/index.tsx:206 — the footer item's ring is outward-offset again (unlike the items above
    // it), reached by opening the menu and then pressing `End`, the same roving-tabindex navigation
    // a keyboard user would use to reach the last row.
    level: 'Menu footer item',
    storyId: 'primitives-menu--profile-switcher',
    locate: (page) => page.getByRole('menuitem', { name: 'Link another Steam account' }),
    reach: async (page, target) => {
      await openMenuViaKeyboard(page, 'aoe2guy — profile ▾')
      await page.keyboard.press('End')
      await target.waitFor({ state: 'visible' })
    },
  },
  {
    // MatchRow/index.tsx:101 — the whole card is one link; located by its known `href` rather than
    // an accessible name, since the row's name is an unstyled concatenation of everything inside it
    // (outcome, rating, map, civilisation, participants).
    level: 'MatchRow link',
    storyId: 'composite-matchrow--win',
    locate: (page) => page.locator('a[href="/matches/1001"]'),
  },
  {
    // FavouritesList/index.tsx:235 — inward-offset, and `bg-transparent` on the row `<li>` itself at
    // this viewport's `md` breakpoint, so its ring's contrast resolves against an ancestor further
    // up than the row — another real ancestor-walk case, not a contrived one.
    level: 'FavouritesList link',
    storyId: 'composite-favouriteslist--default',
    locate: (page) => page.locator('a[href="/players/1"]'),
  },
  {
    // PlayerResultRow/index.tsx:41 — same inward-offset/`md:bg-transparent` shape as FavouritesList
    // above, in an unrelated component; independent regression surface.
    level: 'PlayerResultRow link',
    storyId: 'composite-playerresultrow--source-backed',
    locate: (page) => page.locator('a[href="/players/12345"]'),
  },
  {
    // ThirdPartyObjectionForm/index.tsx:27 — a second, independent text `<input>` (SearchBox is the
    // first); the same constant also styles this screen's inline link, already covered in kind by
    // the `link` control above, so it is not repeated here.
    level: 'ThirdPartyObjectionForm input',
    storyId: 'screens-thirdpartyobjectionform--idle',
    locate: (page) => page.getByLabel('Your Age of Empires II profile id'),
  },
  {
    // DataExportPanel/index.tsx:156 — a download `<a>` styled as a filled button (`bg-accent` on
    // itself, inside a success `Callout`'s own surface): its ring's contrast resolves against its
    // own background rather than an ancestor's, the other end of the walk-up-the-tree logic below.
    // Also gap DS-10, the same `focus-ring`-on-`accent` pair as `Button` `primary` above.
    level: 'DataExportPanel download link',
    storyId: 'screens-dataexportpanel--ready',
    locate: (page) => page.getByRole('link', { name: 'Download the archive' }),
    knownContrastFailure: { light: 1.38, dark: 1.21 },
  },
]

const themes = ['light', 'dark'] as const

// --- WCAG 2.2 relative luminance / contrast ratio. The same formula
// `packages/design-system/tokens/build-tokens.test.mjs` computes from token hex strings — but that
// function takes `#rrggbb` straight out of `color.json`, and everything available here is a
// `getComputedStyle` `rgb(...)`/`rgba(...)` string read out of a live, rendered page. Reusing the
// hex-based helper would mean converting one string format into the other just to call it, so this
// is a second, small implementation of the same public formula (WCAG 2.2 §1.4.11 references the
// same relative luminance definition as §1.4.3), not a duplicated measurement — no number here is
// copied from that file; both compute the same thing from different inputs.
function srgbToLinear(channel: number): number {
  const c = channel / 255
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function relativeLuminance({ r, g, b }: { r: number; g: number; b: number }): number {
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b)
}

function contrastRatio(
  a: { r: number; g: number; b: number },
  b: { r: number; g: number; b: number },
): number {
  const lA = relativeLuminance(a)
  const lB = relativeLuminance(b)
  const lighter = Math.max(lA, lB)
  const darker = Math.min(lA, lB)
  return (lighter + 0.05) / (darker + 0.05)
}

function parseRgb(color: string): { r: number; g: number; b: number } {
  const match = color.match(/rgba?\(([^)]+)\)/)
  if (!match) throw new Error(`unparseable colour from getComputedStyle: "${color}"`)
  const [r, g, b] = match[1].split(',').map((part) => parseFloat(part.trim()))
  return { r, g, b }
}

for (const { level, storyId, locate, reach, knownContrastFailure } of controls) {
  for (const theme of themes) {
    test(`${level} paints the focus-visible ring in the ${theme} theme`, async ({ page }) => {
      // Gap DS-10 (`packages/design-system/specs/README.md`): a strict expected failure, not a
      // skip — every assertion below still runs, including the contrast one it is here for. If
      // T521/T526 land and the pair clears 3:1, this reports "unexpected pass" and fails the run,
      // which is the point: the marker cannot outlive the defect unnoticed.
      test.fail(
        knownContrastFailure !== undefined,
        knownContrastFailure &&
          `gap DS-10: focus-ring on accent measures ${knownContrastFailure[theme]}:1 in the ` +
            `${theme} theme (light 1.38:1, dark 1.21:1), below the 3:1 WCAG 1.4.11 floor — ` +
            `focus-ring was derived only against page surfaces, never against the accent-filled ` +
            `controls it also paints on. T521 re-derives color.json's role coverage; T526 adds ` +
            `the contrast-table row for the pairs a component actually paints and owns removing ` +
            `this expected failure.`,
      )

      await page.goto(`/iframe.html?id=${storyId}&viewMode=story&globals=theme:${theme}`)
      const root = page.locator('#storybook-root')
      await root.waitFor({ state: 'visible' })

      // `.storybook/preview.tsx` sets `data-theme` in a `useEffect`, after first paint, and every
      // token-coloured property in `tokens.css` transitions over 120ms — so a read taken right
      // after mount can land mid-transition, between the light and dark value, on whichever
      // control's interaction happens to be fast enough to race it (seen here on `MatchRow` and
      // `DataExportPanel`'s dark-theme cases, both a single Tab press from the page load). Wait for
      // the attribute to land, then clear the transition window, before touching anything the
      // upcoming colour assertions read.
      await page.waitForFunction(
        (expected) => document.documentElement.dataset.theme === expected,
        theme,
      )
      await page.waitForTimeout(200)

      const target = locate(page)
      await target.waitFor({ state: 'visible' })
      await (reach ?? focusViaKeyboard)(page, target)

      const isFocusVisible = await target.evaluate((el) => el.matches(':focus-visible'))
      expect(isFocusVisible).toBe(true)

      // Every one of these components lists `outline-color` itself in `transition-colors` (it
      // transitions "between rest and hover/active" for a border, but the property list is not
      // state-specific) — so the moment `:focus-visible` starts matching, `outline-color` legally
      // animates from whatever it was at rest up to the `focus-ring` token over the same 120ms as
      // every other colour change, and a read taken immediately can land on an interpolated shade
      // partway through, never the resting `Button`/`focus-ring` values a story's CSS declares.
      // Caught here on `Button` (light) reading contrast ratios that varied run to run against the
      // exact same story. Settle past the transition before reading any colour.
      await page.waitForTimeout(200)

      const outline = await target.evaluate((el) => {
        const computed = getComputedStyle(el)
        return {
          style: computed.outlineStyle,
          width: computed.outlineWidth,
          color: computed.outlineColor,
        }
      })

      // The bug: `outlineStyle` resolves to `none` here even though `:focus-visible` matched.
      expect(outline.style).not.toBe('none')
      expect(outline.width).toBe('2px')

      // FR-050 / SC-015's focus half: the ring must also clear the non-text contrast floor (WCAG
      // 1.4.11, 3:1) against the surface it is actually painted on — the element's own background
      // if it has one, otherwise the nearest ancestor that does (the element itself is frequently
      // transparent, e.g. Tooltip's trigger and every `md:bg-transparent` row link above).
      const backgroundColor = await target.evaluate((el) => {
        let node: Element | null = el
        while (node) {
          const bg = getComputedStyle(node).backgroundColor
          const match = bg.match(/rgba?\(([^)]+)\)/)
          const alpha = match ? (match[1].split(',').map(Number)[3] ?? 1) : 1
          if (alpha !== 0) return bg
          node = node.parentElement
        }
        // Every story renders inside `.storybook/preview.tsx`'s `bg-background` decorator, so a
        // real render always terminates the walk above before this — reachable only if that
        // decorator itself were ever removed.
        throw new Error('no ancestor of the focused element paints a non-transparent background')
      })

      const ratio = contrastRatio(parseRgb(outline.color), parseRgb(backgroundColor))
      expect(
        ratio,
        `${level} (${theme}): the focus ring (${outline.color}) is ${ratio.toFixed(2)}:1 against ` +
          `its surface (${backgroundColor}), below the 3:1 WCAG 1.4.11 non-text contrast floor`,
      ).toBeGreaterThanOrEqual(3)
    })
  }
}
