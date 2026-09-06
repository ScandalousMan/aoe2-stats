import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Section } from './index'

describe('Section', () => {
  it('renders a labelled <section> with an <h2> at the top level', () => {
    render(<Section heading="Recent matches">content</Section>)
    const region = screen.getByRole('region', { name: 'Recent matches' })
    expect(region.tagName).toBe('SECTION')
    expect(screen.getByRole('heading', { level: 2, name: 'Recent matches' })).toBeInTheDocument()
  })

  it('renders an <h3> one level below a nested Section, never skipping a level', () => {
    render(
      <Section heading="Outer">
        <Section heading="Inner">nested content</Section>
      </Section>,
    )
    expect(screen.getByRole('heading', { level: 2, name: 'Outer' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Inner' })).toBeInTheDocument()
  })

  it('throws rendering a third level of nesting', () => {
    // Swallow the expected React error-boundary console noise this deliberately triggers.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() =>
      render(
        <Section heading="Level 0">
          <Section heading="Level 1">
            <Section heading="Level 2">too deep</Section>
          </Section>
        </Section>,
      ),
    ).toThrow(/second level of nesting is forbidden/)
    consoleError.mockRestore()
  })

  it('headingHidden keeps the heading in the accessibility tree and hides it visually', () => {
    render(
      <Section heading="Recent matches" headingHidden>
        content
      </Section>,
    )
    const heading = screen.getByRole('heading', { level: 2, name: 'Recent matches' })
    expect(heading).toBeInTheDocument()
    expect(heading.className).toMatch(/sr-only/)
  })

  it('renders an optional description under the heading', () => {
    render(
      <Section heading="Recent matches" description="Three matches this week.">
        content
      </Section>,
    )
    expect(screen.getByText('Three matches this week.')).toBeInTheDocument()
  })

  it('renders an optional action row', () => {
    render(
      <Section heading="Recent matches" actions={<button type="button">Export</button>}>
        content
      </Section>,
    )
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument()
  })

  it('renders its children in the body', () => {
    render(
      <Section heading="Recent matches">
        <p>Three matches this week.</p>
      </Section>,
    )
    expect(screen.getByText('Three matches this week.')).toBeInTheDocument()
  })

  it('loading sets aria-busy once on the body, never on the heading', () => {
    const { container } = render(
      <Section heading="Recent matches" loading>
        <p>arriving</p>
      </Section>,
    )
    const busyRegions = container.querySelectorAll('[aria-busy="true"]')
    expect(busyRegions).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 2 })).not.toHaveAttribute('aria-busy')
  })

  it('carries no aria-busy attribute when not loading', () => {
    const { container } = render(<Section heading="Recent matches">content</Section>)
    expect(container.querySelectorAll('[aria-busy]')).toHaveLength(0)
  })
})
