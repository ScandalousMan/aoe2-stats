// T750 (remediation): the design system's focus trap (`Dialog`) decides what a Tab press can land
// on with `packages/design-system/src/lib/focusableStops.ts`, which restates the rule the route
// keyboard walk uses (`FOCUSABLE_SELECTOR` plus a `checkVisibility` filter, `./keyboard-walk`)
// because a package may not import from `tests/`. Two statements of one rule drift, so this pins
// them: one page of candidates is rendered in Chromium, the design system's real rule (transpiled
// from its source and injected, never restated here) and the walk's rule are each asked about every
// element, and the answers are compared element by element. The browser itself is the third judge:
// the elements a real Tab walk reaches are asserted to be exactly the design system's.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import ts from 'typescript'
import { FOCUSABLE_SELECTOR } from './keyboard-walk'

const RULE_SOURCE = path.join(
  __dirname,
  '../../../packages/design-system/src/lib/focusableStops.ts',
)

// One element per case, in DOM order (the order a real Tab walk visits them).
const CANDIDATES = `
  <main>
    <button id="enabled-button">Enabled</button>
    <button id="disabled-button" disabled>Disabled</button>
    <fieldset disabled><button id="button-in-disabled-fieldset">In disabled fieldset</button></fieldset>
    <button id="aria-disabled-button" aria-disabled="true">Aria disabled (a loading Button)</button>
    <input id="input-text" type="text" aria-label="Text" />
    <input id="input-hidden" type="hidden" value="x" />
    <input id="input-disabled" type="text" aria-label="Disabled" disabled />
    <select id="select" aria-label="Choice"><option>One</option></select>
    <textarea id="textarea" aria-label="Notes"></textarea>
    <a id="link-with-href" href="#target">Link</a>
    <a id="link-without-href">Anchor</a>
    <div id="tabindex-zero" tabindex="0">Tabindex 0</div>
    <div id="tabindex-minus-one" tabindex="-1">Tabindex -1</div>
    <button id="hidden-attribute-button" hidden>Hidden attribute</button>
    <button id="display-none-button" style="display: none">Display none</button>
    <button id="visibility-hidden-button" style="visibility: hidden">Visibility hidden</button>
    <div inert><button id="button-in-inert">Inert</button></div>
  </main>`

interface Verdict {
  id: string
  walk: boolean
  designSystem: boolean
}

async function installDesignSystemRule(page: Page): Promise<void> {
  const compiled = ts.transpileModule(readFileSync(RULE_SOURCE, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  await page.addScriptTag({
    content: `window.__focusableRule = (() => { const exports = {}; ${compiled}; return exports })()`,
  })
}

async function verdicts(page: Page): Promise<Verdict[]> {
  await page.setContent(CANDIDATES)
  await installDesignSystemRule(page)
  return page.evaluate((walkSelector) => {
    const rule = (
      window as unknown as { __focusableRule: { isFocusableStop(el: HTMLElement): boolean } }
    ).__focusableRule
    return Array.from(document.querySelectorAll<HTMLElement>('main [id]')).map((el) => ({
      id: el.id,
      // `walkTabOrder`'s candidate rule: the selector, then `checkVisibility` with the visibility
      // property (`./keyboard-walk`).
      walk: el.matches(walkSelector) && el.checkVisibility({ visibilityProperty: true }),
      designSystem: rule.isFocusableStop(el),
    }))
  }, FOCUSABLE_SELECTOR)
}

// Where the two rules differ, and why. Both are elements Chromium never focuses, which the design
// system's rule drops and the walk's selector-plus-visibility rule keeps (`button:not([disabled])`
// does not see a disabled `fieldset`, and `checkVisibility` does not see `inert`). The walk is not
// changed here: no route renders either, and a candidate the walk could never reach would surface
// as its own step-count mismatch.
const WALK_ONLY = new Set(['button-in-disabled-fieldset', 'button-in-inert'])

// Everything both rules select.
const BOTH = [
  'enabled-button',
  'aria-disabled-button',
  'input-text',
  'select',
  'textarea',
  'link-with-href',
  'tabindex-zero',
]

test.describe('the focus trap and the keyboard walk agree on what is focusable', () => {
  test('the two rules select the same elements, but for two stated differences', async ({
    page,
  }) => {
    const all = await verdicts(page)
    expect(all.length).toBe(17)

    for (const { id, walk, designSystem } of all) {
      if (WALK_ONLY.has(id)) {
        expect(walk, `${id}: the walk's selector and visibility filter keep it`).toBe(true)
        expect(designSystem, `${id}: the design system's rule drops it`).toBe(false)
      } else {
        expect(designSystem, `${id}: the design system's rule disagrees with the walk's`).toBe(walk)
      }
    }

    expect(
      all.filter((verdict) => verdict.designSystem).map((verdict) => verdict.id),
      'the design system selects exactly these',
    ).toEqual(BOTH)
    expect(
      all.filter((verdict) => verdict.walk).map((verdict) => verdict.id),
      'the walk selects exactly these',
    ).toEqual([...BOTH, ...WALK_ONLY].sort((a, b) => order(all, a) - order(all, b)))
  })

  // The ground truth: the design system's elements are the ones a real Tab press reaches, in order.
  // (The two walk-only elements are never focused by the browser, so the walk's rule is the one
  // that over-counts.)
  test('a real Tab walk reaches exactly the elements the design system selects', async ({
    page,
  }) => {
    const all = await verdicts(page)
    const reached: string[] = []
    for (let press = 0; press < all.length + 2; press += 1) {
      await page.keyboard.press('Tab')
      const id = await page.evaluate(() => document.activeElement?.id ?? '')
      if (id === '' || reached.includes(id)) break
      reached.push(id)
    }
    expect(reached).toEqual(all.filter((verdict) => verdict.designSystem).map((v) => v.id))
  })
})

function order(all: Verdict[], id: string): number {
  return all.findIndex((verdict) => verdict.id === id)
}
