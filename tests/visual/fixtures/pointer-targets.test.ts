// T676: the pointer-only touch sweep, shown failing on pages carrying the defect it names. Each
// planted page is a target a finger can tap and a keyboard cannot reach (so `walkTabOrder` never
// measures it), 30px where the floor is 44, found by one of the sweep's two signals — a pointer
// cursor or an interactive role — with controls beside them that must NOT be reported.
import { expect, test } from '@playwright/test'
import {
  assertPointerTargetFootprint,
  collectPointerOnlyTargets,
  INTERACTIVE_ROLES,
} from './pointer-targets'

const BOX = 'box-sizing: border-box; padding: 0; border: 0; margin: 0;'

test.describe('pointer-only touch sweep, planted pages', () => {
  test('a 30px clickable div (cursor: pointer, no role, no tabindex) fails, naming it', async ({
    page,
  }) => {
    await page.setContent(
      `<div id="tap" style="${BOX} cursor: pointer; width: 30px; height: 30px;">Tap me</div>`,
    )

    await expect(assertPointerTargetFootprint(page, 'planted')).rejects.toThrow(
      /1 pointer-only target\(s\) are under 44×44 — <div> "Tap me" is 30\.0×30\.0 \(cursor: pointer/,
    )
  })

  test('a 40px div with an interactive role but no pointer cursor fails (the role signal alone)', async ({
    page,
  }) => {
    await page.setContent(
      `<div role="menuitem" style="${BOX} width: 200px; height: 40px;">Row action</div>`,
    )

    await expect(assertPointerTargetFootprint(page, 'planted')).rejects.toThrow(
      /<div role="menuitem"> "Row action" is 200\.0×40\.0/,
    )
  })

  test('a pointer-cursor row whose child inherits the cursor is one target, not two', async ({
    page,
  }) => {
    await page.setContent(`
      <div style="${BOX} cursor: pointer; width: 300px; height: 48px;">
        <span style="${BOX} display: inline-block; width: 20px; height: 20px;">icon</span>
      </div>`)

    const targets = await collectPointerOnlyTargets(page)
    expect(targets.map((target) => target.tag)).toEqual(['div'])
    await assertPointerTargetFootprint(page, 'planted')
  })

  test('control: a 44×44 clickable div passes', async ({ page }) => {
    await page.setContent(
      `<div style="${BOX} cursor: pointer; width: 44px; height: 44px;">Tap me</div>`,
    )

    const targets = await assertPointerTargetFootprint(page, 'planted')
    expect(targets).toHaveLength(1)
  })

  test('a Tab stop is not this sweep’s: a 30px button is left to walkTabOrder', async ({
    page,
  }) => {
    // The two sweeps partition the targets. A focusable element is measured by `walkTabOrder`, with
    // the label-box and inline-link rules; counting it here too would double-report it.
    await page.setContent(
      `<button style="${BOX} cursor: pointer; width: 30px; height: 30px;">Small</button>`,
    )

    expect(await collectPointerOnlyTargets(page)).toEqual([])
  })

  test('a hidden pointer-cursor element is no target', async ({ page }) => {
    await page.setContent(
      `<div style="${BOX} display: none; cursor: pointer; width: 10px; height: 10px;">Hidden</div>`,
    )

    expect(await collectPointerOnlyTargets(page)).toEqual([])
  })

  test('a landmark or container role is not an interactive role', async ({ page }) => {
    await page.setContent(`<div role="dialog" style="${BOX} width: 20px; height: 20px;">x</div>`)

    expect(INTERACTIVE_ROLES).not.toContain('dialog')
    expect(await collectPointerOnlyTargets(page)).toEqual([])
  })
})
