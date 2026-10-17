import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Link } from './index'

describe('Link', () => {
  it('renders a real <a href>', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    const link = screen.getByRole('link', { name: 'View profile' })
    expect(link.tagName).toBe('A')
    expect(link).toHaveAttribute('href', '/players/1807091')
  })

  it('is permanently underlined at rest, in the link ink, greyscale-identifiable', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    const link = screen.getByRole('link')
    expect(link).toHaveClass('underline')
    expect(link).toHaveClass('decoration-1')
    expect(link).toHaveClass('text-link')
  })

  it('thickens the underline and changes ink on hover — two signals, not one (FR-037)', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    const link = screen.getByRole('link')
    expect(link).toHaveClass('hover:text-link-hover')
    expect(link).toHaveClass('hover:decoration-2')
  })

  it('applies the same hover paint on :active, reaching a keyboard Enter with no pointer hover', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    const link = screen.getByRole('link')
    expect(link).toHaveClass('active:text-link-hover')
    expect(link).toHaveClass('active:decoration-2')
  })

  it('carries the visited role, unable to be observed in a real render but present in the class list', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    expect(screen.getByRole('link')).toHaveClass('visited:text-link-visited')
  })

  it('shows the standard focus ring around the whole link box', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    const link = screen.getByRole('link')
    expect(link).toHaveClass('focus-visible:outline-ring')
    expect(link).toHaveClass('focus-visible:outline-offset-ring')
    expect(link).toHaveClass('focus-visible:outline-focus-ring')
  })

  it('inline variant carries no fill on active and no explicit typography classes', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    const link = screen.getByRole('link')
    expect(link).not.toHaveClass('active:bg-surface-sunken')
    expect(link).not.toHaveClass('type-body')
  })

  it('standalone variant is type-body at text-md, reaches a 44px hit area via space-3 padding, and paints a fill on press', () => {
    render(
      <Link href="/players/1807091" variant="standalone">
        View profile
      </Link>,
    )
    const link = screen.getByRole('link')
    expect(link).toHaveClass('type-body')
    expect(link).toHaveClass('text-md')
    expect(link).toHaveClass('py-3')
    expect(link).toHaveClass('active:bg-surface-sunken')
  })

  // Sixth-pass review remediation (M1), row 2 of `specs/README.md`'s contrast-signal gap
  // register: the fill above used to be `standalone`'s only press signal — a colour change, not
  // the non-colour half FR-037's "more than colour" asks for. `ring` (box-shadow) is a different
  // CSS property from the `outline` the focus ring uses, so both a real `:active:focus-visible`
  // combination and this class-level assertion coexist without either masking the other.
  it('standalone variant carries a non-colour press signal — a ring — never relying on active:outline alone (FR-037)', () => {
    render(
      <Link href="/players/1807091" variant="standalone">
        View profile
      </Link>,
    )
    const link = screen.getByRole('link')
    expect(link).toHaveClass('active:ring-2')
    expect(link).toHaveClass('active:ring-border-strong')
    expect(Array.from(link.classList).filter((c) => /(^|:)active:outline/.test(c))).toEqual([])
  })

  // `inline` keeps its own non-colour signal (the underline-offset drop, asserted above) and must
  // not gain the ring: this pins the boundary rather than asserting "every link rings".
  it('inline variant never carries the standalone ring', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    const link = screen.getByRole('link')
    expect(link).not.toHaveClass('active:ring-2')
    expect(link).not.toHaveClass('active:ring-border-strong')
  })

  // T674: the touch-footprint route sweep exempts an `inline` link inside running prose from the
  // 44×44 floor by reading this marker off the DOM — never a layout heuristic (`specs/README.md`,
  // "Minimum interactive footprint").
  it('renders its variant as a data attribute, the only marker the touch-footprint sweep reads', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    expect(screen.getByRole('link')).toHaveAttribute('data-variant', 'inline')
  })

  it('renders the standalone variant in the same data attribute', () => {
    render(
      <Link href="/players/1807091" variant="standalone">
        View profile
      </Link>,
    )
    expect(screen.getByRole('link')).toHaveAttribute('data-variant', 'standalone')
  })

  // Low-severity remediation, PR #102: `{...rest}` used to spread *after* `data-variant`, so a
  // caller's own `data-variant` — never a prop `LinkProps` declares, but TypeScript exempts every
  // `data-*`/`aria-*` attribute from excess-property checking on any JSX element, the same way it
  // already lets `aria-label` etc. through — silently overrode this primitive's own real marker:
  // `<Link variant="standalone" data-variant="inline" />` compiled and rendered
  // `data-variant="inline"`, exempting a `standalone` link from the touch-footprint sweep's own
  // 44px floor. `data-variant` is ordered after `{...rest}` now, so the real `variant` always wins.
  it("renders its own variant in `data-variant`, never a caller's own override of that attribute", () => {
    render(
      <Link href="/players/1807091" variant="standalone" data-variant="inline">
        View profile
      </Link>,
    )
    expect(screen.getByRole('link')).toHaveAttribute('data-variant', 'standalone')
  })

  it('a link is never disabled — there is no disabled prop', () => {
    render(<Link href="/players/1807091">View profile</Link>)
    expect(screen.getByRole('link')).not.toHaveAttribute('disabled')
    expect(screen.getByRole('link')).not.toHaveAttribute('aria-disabled')
  })

  it('renders nothing with no text — an icon-only link is forbidden', () => {
    const { container } = render(<Link href="/players/1807091">{''}</Link>)
    expect(container).toBeEmptyDOMElement()
  })

  describe('external', () => {
    it('opens in a new tab with noopener noreferrer', () => {
      render(
        <Link href="https://store.steampowered.com" external>
          Steam
        </Link>,
      )
      const link = screen.getByRole('link', { name: /Steam/ })
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    })

    it('renders the mark after the label with aria-hidden, and real hidden text stating it opens in a new tab', () => {
      render(
        <Link href="https://store.steampowered.com" external>
          Steam
        </Link>,
      )
      const link = screen.getByRole('link', { name: /Steam.*opens in a new tab/i })
      const svg = link.querySelector('svg')
      expect(svg).toHaveAttribute('aria-hidden', 'true')
      expect(link.textContent).toMatch(/Steam.*opens in a new tab/)
    })

    it('never carries target or rel when not external', () => {
      render(<Link href="/players/1807091">View profile</Link>)
      const link = screen.getByRole('link')
      expect(link).not.toHaveAttribute('target')
      expect(link).not.toHaveAttribute('rel')
    })

    it('wraps an external inline link so the mark cannot strand on its own line', () => {
      render(
        <Link href="https://store.steampowered.com" external>
          Steam
        </Link>,
      )
      expect(screen.getByRole('link')).toHaveClass('inline-flex')
    })

    it('does not add the inline wrapper class to a plain (non-external) inline link', () => {
      render(<Link href="/players/1807091">View profile</Link>)
      expect(screen.getByRole('link')).not.toHaveClass('inline-flex')
    })
  })
})
