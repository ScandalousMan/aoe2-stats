import axe from 'axe-core'
import { expect } from 'vitest'

// T579 (`specs/README.md`'s "Accessibility mechanism gap register", row 1). This is the one
// generic assertion the register's fix asks for, replacing the hand-written
// `landmark-unique` guards `Panel.test.tsx` and `MatchDetailPanel.test.tsx` carried before this
// task: a hidden caption or heading that repeats an ancestor landmark's accessible name produces
// two landmarks axe cannot tell apart, and this defect class has shipped three times in this
// phase, caught only by `tests/visual/stories.spec.ts` (a built Storybook, a real browser, CI
// only), never at the point a component is authored.
//
// Scoped to `landmark-unique` alone, on purpose, not axe's full default rule set: jsdom has no
// layout engine and no real CSSOM (`MatchDetailPanel.test.tsx`'s own `mockButtonHeightLayout`
// comment documents the same fact about `getBoundingClientRect`), so `color-contrast` and every
// other rendering-dependent rule would give false results here — confirmed by axe-core's own
// `color-contrast` implementation, which reads computed background/foreground colour through
// `getComputedStyle` and falls back to guessing when the element has no real layout box, exactly
// what jsdom cannot provide. `landmark-unique` needs only the accessible-name computation (roles,
// `aria-label`/`aria-labelledby`, text content), which jsdom's DOM/ARIA support is sufficient for
// — the real browser in `tests/visual/stories.spec.ts` remains the one place the rest of axe's
// rule set runs, and this helper does not attempt to replace it.
const RULES = ['landmark-unique'] as const

function formatViolations(violations: axe.Result[]): string {
  if (violations.length === 0) return 'no landmark-unique violations'
  return violations
    .map((violation) => {
      const nodes = violation.nodes
        .map((node) => `      target: ${node.target.join(' ')}\n      html: ${node.html}`)
        .join('\n')
      return `  [${violation.id}] ${violation.help}\n${nodes}`
    })
    .join('\n')
}

/** Runs axe-core's `landmark-unique` rule (only) over a rendered DOM subtree. Exported
 * separately from {@link expectNoLandmarkUniqueViolations} so a caller that wants the raw
 * results (a fixture asserting a specific node, `axe.test.tsx`'s own contrast cases) does not
 * have to catch a thrown assertion to get them. */
export async function scanForLandmarkUniqueViolations(container: Element): Promise<axe.Result[]> {
  const results = await axe.run(container, {
    runOnly: { type: 'rule', values: [...RULES] },
  })
  return results.violations
}

/** Fails the current test if the rendered subtree rooted at `container` carries a
 * `landmark-unique` violation — the shared assertion `packages/design-system/specs/README.md`'s
 * accessibility mechanism gap register (row 1, T579) calls for, reused by every component test
 * file instead of a hand-written per-composition guard. */
export async function expectNoLandmarkUniqueViolations(container: Element): Promise<void> {
  const violations = await scanForLandmarkUniqueViolations(container)
  expect(violations, formatViolations(violations)).toHaveLength(0)
}
