import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Page } from './index'

describe('Page', () => {
  it('renders exactly one <main id="main-content" tabIndex={-1}>, the skip-link target', () => {
    render(<Page title="Match history">content</Page>)
    const main = screen.getAllByRole('main')
    expect(main).toHaveLength(1)
    expect(main[0]).toHaveAttribute('id', 'main-content')
    expect(main[0]).toHaveAttribute('tabindex', '-1')
  })

  it('renders the title as the page’s only <h1>', () => {
    render(<Page title="Match history">content</Page>)
    const headings = screen.getAllByRole('heading', { level: 1 })
    expect(headings).toHaveLength(1)
    expect(headings[0]).toHaveTextContent('Match history')
  })

  it('titleHidden keeps the <h1> in the accessibility tree and hides it visually', () => {
    render(
      <Page title="Match history" titleHidden>
        content
      </Page>,
    )
    const heading = screen.getByRole('heading', { level: 1, name: 'Match history' })
    expect(heading).toBeInTheDocument()
    expect(heading.className).toMatch(/sr-only/)
  })

  it('renders an optional description under the title', () => {
    render(
      <Page title="Match history" description="Every match this profile has played.">
        content
      </Page>,
    )
    expect(screen.getByText('Every match this profile has played.')).toBeInTheDocument()
  })

  it('renders an optional action row', () => {
    render(
      <Page title="Match history" actions={<button type="button">Export</button>}>
        content
      </Page>,
    )
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument()
  })

  it('defaults to the page width and switches through the closed three-value vocabulary', () => {
    const { container, rerender } = render(<Page title="Match history">content</Page>)
    expect(container.querySelector('.max-w-page')).toBeInTheDocument()

    rerender(
      <Page title="Match history" width="panel">
        content
      </Page>,
    )
    expect(container.querySelector('.max-w-panel')).toBeInTheDocument()

    rerender(
      <Page title="Match history" width="measure">
        content
      </Page>,
    )
    expect(container.querySelector('.max-w-measure')).toBeInTheDocument()
  })

  it('renders its children inside the section stack', () => {
    render(
      <Page title="Match history">
        <p>Three matches this week.</p>
      </Page>,
    )
    expect(screen.getByText('Three matches this week.')).toBeInTheDocument()
  })

  it('loading sets aria-busy once on the section stack, never on the header', () => {
    const { container } = render(
      <Page title="Match history" loading>
        <p>arriving</p>
      </Page>,
    )
    const busyRegions = container.querySelectorAll('[aria-busy="true"]')
    expect(busyRegions).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1 })).not.toHaveAttribute('aria-busy')
  })

  it('carries no aria-busy attribute when not loading', () => {
    const { container } = render(<Page title="Match history">content</Page>)
    expect(container.querySelectorAll('[aria-busy]')).toHaveLength(0)
  })

  it('shows a visible focus-visible outline token on the landmark, not a removed outline', () => {
    render(<Page title="Match history">content</Page>)
    expect(screen.getByRole('main').className).toMatch(/focus-visible:outline-focus-ring/)
  })
})
