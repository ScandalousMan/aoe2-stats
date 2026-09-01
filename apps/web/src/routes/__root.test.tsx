import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { affiliationNote, disclaimer } from 'design-system'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// T442: `RootLayout` mounts `SiteHeader` beside the already-mounted `Footer`, so both render on
// every route. This test never builds a `RouterProvider` — apps/web's vitest config deliberately
// omits the router plugin and the generated route tree (vite.config.ts's own comment) — so the
// three hooks `RootLayout` reads from `@tanstack/react-router` (`useRouteContext`, `useRouterState`,
// `useNavigate`) are replaced the same way `DashboardContainer.test.tsx` replaces `useNavigate`
// alone. `Outlet` is replaced too: rendering the real one with no mounted router throws, and this
// suite is about the shell around it, not about routing itself.
let sessionFixture: { authenticated: boolean } = { authenticated: false }
let currentPathFixture = '/'
const navigateMock = vi.fn()

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useRouterState: () => currentPathFixture,
    useRouteContext: () => ({ session: sessionFixture }),
    Outlet: () => <div data-testid="route-outlet">outlet content</div>,
  }
})

const { RootLayout } = await import('./__root')

describe('RootLayout (T442)', () => {
  beforeEach(() => {
    navigateMock.mockClear()
    sessionFixture = { authenticated: false }
    currentPathFixture = '/'
  })

  it('mounts SiteHeader with the signed-in nav items and marks the current route (§3a, §4)', () => {
    sessionFixture = { authenticated: true }
    currentPathFixture = '/matches/12345'
    render(<RootLayout />)

    const nav = screen.getByRole('navigation', { name: 'Primary' })
    ;['Dashboard', 'Matches', 'Search', 'Favourites', 'My data'].forEach((label) => {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    })
    // /matches/12345 is a nested route under /matches — Matches is the item marked current.
    expect(within(nav).getByRole('link', { name: 'Matches' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current')
  })

  it('passes items={[]} when signed out, so SiteHeader renders no <nav> (§5 empty)', () => {
    sessionFixture = { authenticated: false }
    render(<RootLayout />)

    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument()
    // The wordmark and skip link are never conditional (§2, §5).
    expect(screen.getByRole('link', { name: 'aoe2-stats' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toBeInTheDocument()
  })

  it('leaves the footer, and its Game Content Usage Rules disclaimer, exactly as it is (FR-009, FR-012)', () => {
    sessionFixture = { authenticated: true }
    render(<RootLayout />)

    expect(screen.getByText(disclaimer)).toBeInTheDocument()
    expect(screen.getByText(affiliationNote)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Read the privacy notice' })).toHaveAttribute(
      'href',
      '/privacy-notice',
    )
    expect(screen.getByRole('link', { name: 'Object to what is held about me' })).toHaveAttribute(
      'href',
      '/object',
    )
  })

  it('renders the route outlet inside <main id="main-content" tabIndex={-1}>, the skip link target (§9)', () => {
    sessionFixture = { authenticated: true }
    render(<RootLayout />)

    const outlet = screen.getByTestId('route-outlet')
    const main = outlet.closest('main')
    expect(main).not.toBeNull()
    expect(main).toHaveAttribute('id', 'main-content')
    expect(main).toHaveAttribute('tabindex', '-1')
  })

  it('renders header before main before footer, so the banner landmark leads the page (§9)', () => {
    sessionFixture = { authenticated: true }
    const { container } = render(<RootLayout />)

    const landmarks = Array.from(container.querySelectorAll('header, main, footer')).map(
      (el) => el.tagName,
    )
    expect(landmarks).toEqual(['HEADER', 'MAIN', 'FOOTER'])
  })

  it('wires SiteHeader navigation through TanStack Router: a plain left click calls navigate (§2b)', async () => {
    sessionFixture = { authenticated: true }
    currentPathFixture = '/dashboard'
    render(<RootLayout />)

    await userEvent.click(screen.getByRole('link', { name: 'Search' }))

    expect(navigateMock).toHaveBeenCalledWith({ to: '/search' })
  })
})
