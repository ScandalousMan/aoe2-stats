import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { expectNoLandmarkUniqueViolations, scanForLandmarkUniqueViolations } from './axe'

// T579's own fixture cases, minimal reproductions of the defect class rather than a real
// component — the shared helper itself is what every component test file (and the all-stories
// sweep, `story-a11y.test.tsx`) reuses, so it is proven here against the shape the register row
// names before any composition depends on it.
describe('expectNoLandmarkUniqueViolations', () => {
  // (a) the reported shape: a Section/Panel-style landmark whose hidden (sr-only) caption/heading
  // repeats an ancestor landmark's name. `Panel`'s own `<section aria-labelledby>` and a nested
  // `role="region"` scroll area, named from a visually-hidden caption carrying the exact same
  // text as the ancestor's heading — the precise composition `Panel.stories.tsx`'s
  // `RealisticMatchTable` comment (T579's own read) describes as the reproduced defect.
  it('fails, naming landmark-unique, when a hidden caption repeats its ancestor landmark name', async () => {
    const { container } = render(
      <section aria-labelledby="outer-heading">
        <h2 id="outer-heading">Recent matches</h2>
        <div role="region" aria-label="Recent matches" tabIndex={-1}>
          <span className="sr-only">Recent matches</span>
          <table>
            <tbody>
              <tr>
                <td>Arabia</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>,
    )
    const violations = await scanForLandmarkUniqueViolations(container)
    expect(violations.map((violation) => violation.id)).toContain('landmark-unique')
    const violation = violations.find((v) => v.id === 'landmark-unique')
    expect(violation?.nodes.some((node) => node.html.includes('role="region"'))).toBe(true)

    await expect(expectNoLandmarkUniqueViolations(container)).rejects.toThrow(/landmark-unique/)
  })

  // (b) contrast case: two landmarks of the same role with distinct names must pass.
  it('passes when two landmarks of the same role carry distinct accessible names', async () => {
    const { container } = render(
      <div>
        <section aria-label="Recent matches">content one</section>
        <section aria-label="Older matches">content two</section>
      </div>,
    )
    await expect(expectNoLandmarkUniqueViolations(container)).resolves.toBeUndefined()
  })

  // (c) contrast case: a single landmark must pass — nothing to collide with.
  it('passes for a single landmark with no sibling to collide with', async () => {
    const { container } = render(<section aria-label="Recent matches">content</section>)
    await expect(expectNoLandmarkUniqueViolations(container)).resolves.toBeUndefined()
  })
})
