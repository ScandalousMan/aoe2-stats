import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SiteHeader, type SiteHeaderNavItem } from './index'

// site-header.md §11: what a static story capture cannot see — Tab order, aria-current, the
// current-route rule and the click/modified-click contract — asserted here instead.

const items: SiteHeaderNavItem[] = [
  { id: 'dashboard', label: 'Dashboard', href: '/dashboard' },
  { id: 'matches', label: 'Matches', href: '/matches' },
  { id: 'search', label: 'Search', href: '/search' },
  { id: 'favourites', label: 'Favourites', href: '/favourites' },
  { id: 'my-data', label: 'My data', href: '/privacy' },
]

describe('SiteHeader — anatomy (§2)', () => {
  it('always renders the wordmark, as text, and the skip link', () => {
    render(<SiteHeader items={[]} />)
    expect(screen.getByText('aoe2-stats')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute(
      'href',
      '#main-content',
    )
  })

  it('carries no image of any kind — text and rules only (§Asset origin)', () => {
    render(<SiteHeader items={items} currentPath="/dashboard" />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(document.querySelector('svg')).not.toBeInTheDocument()
  })

  it('renders a banner landmark and a labelled Primary nav', () => {
    render(<SiteHeader items={items} />)
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument()
  })
})

describe('SiteHeader — empty (§5)', () => {
  it('items={[]} renders no <nav> at all, not an empty one', () => {
    render(<SiteHeader items={[]} />)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('omits an item with a blank label or a blank href rather than rendering a dead link', () => {
    render(
      <SiteHeader
        items={[
          { id: 'dashboard', label: 'Dashboard', href: '/dashboard' },
          { id: 'blank-label', label: '   ', href: '/blank-label' },
          { id: 'blank-href', label: 'Blank href', href: '' },
        ]}
      />,
    )
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Blank href' })).not.toBeInTheDocument()
    // Skip link + Brand + the one real item — the two blank-item entries render nothing at all.
    expect(screen.getAllByRole('link')).toHaveLength(3)
  })
})

describe('SiteHeader — current-route indication (§4)', () => {
  it('marks exactly one item current, with aria-current="page" and no other', () => {
    render(<SiteHeader items={items} currentPath="/dashboard" />)
    const current = screen.getAllByRole('link').filter((link) => link.getAttribute('aria-current'))
    expect(current).toHaveLength(1)
    expect(current[0]).toHaveAttribute('aria-current', 'page')
    expect(current[0]).toHaveTextContent('Dashboard')
  })

  it('a nested route still marks its section — /matches/12345 marks Matches', () => {
    render(<SiteHeader items={items} currentPath="/matches/12345" />)
    expect(screen.getByRole('link', { name: 'Matches' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current')
  })

  it('a non-matching path marks nothing — no default to the first item', () => {
    render(<SiteHeader items={items} currentPath="/players/1807091" />)
    for (const item of items) {
      expect(screen.getByRole('link', { name: item.label })).not.toHaveAttribute('aria-current')
    }
  })

  it('no currentPath at all marks nothing', () => {
    render(<SiteHeader items={items} />)
    for (const item of items) {
      expect(screen.getByRole('link', { name: item.label })).not.toHaveAttribute('aria-current')
    }
  })

  it('an href of exactly "/" matches only exactly, never by prefix', () => {
    const rootItems: SiteHeaderNavItem[] = [
      { id: 'home', label: 'Home', href: '/' },
      { id: 'dashboard', label: 'Dashboard', href: '/dashboard' },
    ]
    render(<SiteHeader items={rootItems} currentPath="/dashboard" />)
    expect(screen.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
  })
})

describe('SiteHeader — keyboard order (§9)', () => {
  it('Tab reaches SkipLink first, then Brand, then every item in DOM order', async () => {
    const user = userEvent.setup()
    render(<SiteHeader items={items} currentPath="/dashboard" />)

    await user.tab()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveFocus()

    await user.tab()
    expect(screen.getByRole('link', { name: 'aoe2-stats' })).toHaveFocus()

    for (const item of items) {
      await user.tab()
      expect(screen.getByRole('link', { name: item.label })).toHaveFocus()
    }
  })
})

describe('SiteHeader — navigation seam (§2b)', () => {
  it('a plain left click calls onNavigate for an item', () => {
    const onNavigate = vi.fn()
    render(<SiteHeader items={items} onNavigate={onNavigate} />)
    fireEvent.click(screen.getByRole('link', { name: 'Matches' }))
    expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/matches')
  })

  it('a modified click (new tab) falls through to native handling, never calling onNavigate', () => {
    const onNavigate = vi.fn()
    render(<SiteHeader items={items} onNavigate={onNavigate} />)
    fireEvent.click(screen.getByRole('link', { name: 'Matches' }), { ctrlKey: true })
    expect(onNavigate).not.toHaveBeenCalled()
  })

  it('a plain left click on the wordmark calls onNavigate with brandHref', () => {
    const onNavigate = vi.fn()
    render(<SiteHeader items={[]} onNavigate={onNavigate} brandHref="/dashboard" />)
    fireEvent.click(screen.getByRole('link', { name: 'aoe2-stats' }))
    expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/dashboard')
  })

  it('stays a real link with its href regardless of onNavigate', () => {
    render(<SiteHeader items={items} onNavigate={() => {}} />)
    expect(screen.getByRole('link', { name: 'Matches' })).toHaveAttribute('href', '/matches')
  })
})

describe('SiteHeader — hover and focus class contract (§5, §11)', () => {
  it('every item carries the documented focus-visible ring', () => {
    render(<SiteHeader items={items} currentPath="/dashboard" />)
    for (const item of items) {
      expect(screen.getByRole('link', { name: item.label }).className).toMatch(
        /focus-visible:outline-focus-ring/,
      )
    }
  })

  it('every item carries the hover fill and hover label colour', () => {
    render(<SiteHeader items={items} currentPath="/dashboard" />)
    for (const item of items) {
      const className = screen.getByRole('link', { name: item.label }).className
      expect(className).toMatch(/hover:bg-surface-sunken/)
      expect(className).toMatch(/hover:text-text-primary/)
    }
  })

  it('SkipLink and Brand also carry the documented focus-visible ring', () => {
    render(<SiteHeader items={[]} />)
    expect(screen.getByRole('link', { name: 'Skip to content' }).className).toMatch(
      /focus-visible:outline-focus-ring/,
    )
    expect(screen.getByRole('link', { name: 'aoe2-stats' }).className).toMatch(
      /focus-visible:outline-focus-ring/,
    )
  })

  it('the current item is semibold and text-primary; a resting item is medium and text-secondary', () => {
    render(<SiteHeader items={items} currentPath="/dashboard" />)
    const current = screen.getByRole('link', { name: 'Dashboard' })
    expect(current.className).toMatch(/font-semibold/)
    expect(current.className).toMatch(/text-text-primary/)

    const rest = screen.getByRole('link', { name: 'Matches' })
    expect(rest.className).toMatch(/font-medium/)
    expect(rest.className).toMatch(/text-text-secondary/)
  })

  it('marking an item current changes no other item’s class contract', () => {
    const { rerender } = render(<SiteHeader items={items} currentPath="/players/1807091" />)
    const restingClassName = screen.getByRole('link', { name: 'Matches' }).className

    rerender(<SiteHeader items={items} currentPath="/dashboard" />)
    expect(screen.getByRole('link', { name: 'Matches' }).className).toBe(restingClassName)
  })
})
