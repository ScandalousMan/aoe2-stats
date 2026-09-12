import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Panel } from './index'
import { Table } from '../Table'
import { expectNoLandmarkUniqueViolations } from '../../test/axe'

describe('Panel', () => {
  it('renders a plain <div> when it has no heading', () => {
    const { container } = render(<Panel density="dense">content</Panel>)
    const panel = container.firstElementChild
    expect(panel?.tagName).toBe('DIV')
    expect(panel).not.toHaveAttribute('aria-labelledby')
  })

  it('renders a labelled <section> when it has a heading', () => {
    render(
      <Panel density="dense" heading="Recent matches">
        content
      </Panel>,
    )
    const region = screen.getByRole('region', { name: 'Recent matches' })
    expect(region.tagName).toBe('SECTION')
    expect(screen.getByRole('heading', { level: 3, name: 'Recent matches' })).toBeInTheDocument()
  })

  it('renders nothing at all when given no children', () => {
    const { container } = render(<Panel density="dense" heading="Recent matches" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('draws surface for the outermost panel and surface-raised nested one level in', () => {
    render(
      <Panel density="dense" heading="Outer">
        <Panel density="dense" heading="Inner">
          nested content
        </Panel>
      </Panel>,
    )
    const outer = screen.getByRole('region', { name: 'Outer' })
    const inner = screen.getByRole('region', { name: 'Inner' })
    expect(outer.className).toMatch(/bg-surface\b/)
    expect(inner.className).toMatch(/bg-surface-raised/)
  })

  it('throws rendering a third level of nesting', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() =>
      render(
        <Panel density="dense" heading="Level 0">
          <Panel density="dense" heading="Level 1">
            <Panel density="dense" heading="Level 2">
              too deep
            </Panel>
          </Panel>
        </Panel>,
      ),
    ).toThrow(/second level of nesting is forbidden/)
    consoleError.mockRestore()
  })

  it('renders an optional description under the heading', () => {
    render(
      <Panel density="dense" heading="Recent matches" description="Three matches this week.">
        content
      </Panel>,
    )
    expect(screen.getByText('Three matches this week.')).toBeInTheDocument()
  })

  it('renders an optional action row', () => {
    render(
      <Panel
        density="dense"
        heading="Recent matches"
        actions={<button type="button">Export</button>}
      >
        content
      </Panel>,
    )
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument()
  })

  it('renders an optional footer', () => {
    render(
      <Panel density="dense" footer={<span>Two profiles</span>}>
        content
      </Panel>,
    )
    expect(screen.getByText('Two profiles')).toBeInTheDocument()
  })

  it('bounds a prose panel to the reading measure and leaves a dense one unbounded', () => {
    const { container: denseContainer } = render(<Panel density="dense">dense content</Panel>)
    const { container: proseContainer } = render(<Panel density="prose">prose content</Panel>)
    expect(denseContainer.querySelector('.max-w-measure')).not.toBeInTheDocument()
    expect(proseContainer.querySelector('.max-w-measure')).toBeInTheDocument()
  })

  it('sets aria-busy once on the panel itself while loading', () => {
    const { container } = render(
      <Panel density="dense" loading>
        arriving
      </Panel>,
    )
    const busyRegions = container.querySelectorAll('[aria-busy="true"]')
    expect(busyRegions).toHaveLength(1)
    expect(container.firstElementChild).toHaveAttribute('aria-busy', 'true')
  })

  it('carries no aria-busy attribute when not loading', () => {
    const { container } = render(<Panel density="dense">content</Panel>)
    expect(container.querySelectorAll('[aria-busy]')).toHaveLength(0)
  })

  it('draws no border-radius or elevation override — always the panel role, always no shadow', () => {
    const { container } = render(<Panel density="dense">content</Panel>)
    const panel = container.firstElementChild
    expect(panel?.className).toMatch(/rounded-panel/)
    expect(panel?.className).not.toMatch(/shadow-/)
  })

  // Regression guard for the `landmark-unique` violation axe found in
  // `Panel.stories.tsx`'s `RealisticMatchTable` (remediated 2026-09-06): `Panel`'s own `<section>`
  // and `Table`'s scroll region (structural-tier.md §10) are two independent landmarks, each
  // correctly labelled on its own, but a caller that gives `Table`'s hidden caption the exact same
  // text as the enclosing `Panel`'s `heading` produces two landmarks with one accessible name.
  // T579 replaces the hand-written DOM-name assertion this guard used to carry with the shared
  // axe scan (`src/test/axe.ts`) every component test file and the all-stories sweep
  // (`src/test/story-a11y.test.tsx`) now reuse, rather than re-deriving the rule by hand per
  // composition here. Neither component is responsible for the other's label; this only proves
  // the composition this test renders keeps the two names apart.
  // `baseElement`, not `container` (review remediation, 2026-09-11): neither component here uses
  // a portal today, so the two are equivalent for this render, but scanning `baseElement`
  // (`document.body`) rather than the render's own wrapper `<div>` is what stays correct if that
  // ever changes.
  it('keeps its own landmark name distinct from a nested Table region named differently', async () => {
    const { baseElement } = render(
      <Panel density="dense" heading="Recent matches">
        <Table
          caption="3 of 47 recent matches"
          captionHidden
          columns={[
            {
              key: 'opponent',
              header: 'Opponent',
              render: (row: { opponent: string }) => row.opponent,
            },
          ]}
          rows={[{ opponent: 'RedBull_Barley' }]}
          getRowKey={(row) => row.opponent}
        />
      </Panel>,
    )
    await expectNoLandmarkUniqueViolations(baseElement)
  })
})
