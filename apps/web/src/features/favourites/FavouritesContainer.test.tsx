import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — mirrors
// `SearchContainer.test.tsx` and `PlayerProfileContainer.test.tsx`'s identical setup.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { FavouritesContainer } = await import('./FavouritesContainer')

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

const authenticatedSession = {
  authenticated: true,
  user_id: 'user-1',
  allowlisted: true,
  archival_objected: false,
  archival_objected_at: null,
  profiles: [],
}

const unauthenticatedSession = { authenticated: false }

function oneFavourite(overrides: Record<string, unknown> = {}) {
  return {
    profile_id: 87654321,
    alias: 'rival_ace',
    country: 'Germany',
    ratings: [
      {
        leaderboard_id: 3,
        leaderboard_name: '1v1 Random Map',
        rating: 1842,
        rank: 214,
        wins: 142,
        losses: 118,
        streak: 3,
        highest_rating: 1901,
        captured_at: '2026-08-22T10:00:00Z',
      },
    ],
    ...overrides,
  }
}

function installFakeApi({
  session = authenticatedSession,
  favouritesHandler,
  deleteHandler,
}: {
  session?: typeof authenticatedSession | typeof unauthenticatedSession
  favouritesHandler?: () => Response
  deleteHandler?: (profileId: string) => Response
}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(session)
    }
    if (path === '/api/favourites' && method === 'GET') {
      return favouritesHandler ? favouritesHandler() : jsonResponse({ favourites: [] })
    }
    const deleteMatch = /^\/api\/favourites\/(\d+)$/.exec(path)
    if (deleteMatch && method === 'DELETE' && deleteMatch[1]) {
      return deleteHandler
        ? deleteHandler(deleteMatch[1])
        : jsonResponse({ profile_id: Number(deleteMatch[1]), favourited: false })
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderFavourites() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<FavouritesContainer />, { wrapper })
}

describe('FavouritesContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it("renders the caller's favourites with their current standing (FR-014)", async () => {
    installFakeApi({ favouritesHandler: () => jsonResponse({ favourites: [oneFavourite()] }) })
    renderFavourites()

    expect(await screen.findByText('rival_ace')).toBeInTheDocument()
    expect(screen.getByText('1,842')).toBeInTheDocument()
  })

  it('shows the empty state when the caller has no favourites yet', async () => {
    installFakeApi({ favouritesHandler: () => jsonResponse({ favourites: [] }) })
    renderFavourites()

    expect(await screen.findByText('You have not added any favourites yet.')).toBeInTheDocument()
  })

  it('shows the signed-out prompt, carrying /favourites as the return place (US5 scenario 5)', async () => {
    installFakeApi({ session: unauthenticatedSession })
    renderFavourites()

    const signIn = await screen.findByRole('link', { name: 'Sign in' })
    expect(signIn).toHaveAttribute('href', '/sign-in?return=%2Ffavourites')
  })

  it('removes a favourite and refreshes the list (FR-013, US5 scenario 2)', async () => {
    let deleted = false
    const fetchMock = installFakeApi({
      favouritesHandler: () => jsonResponse({ favourites: deleted ? [] : [oneFavourite()] }),
      deleteHandler: (profileId) => {
        deleted = true
        return jsonResponse({ profile_id: Number(profileId), favourited: false })
      },
    })
    const user = userEvent.setup()
    renderFavourites()

    await screen.findByText('rival_ace')
    await user.click(screen.getByRole('button', { name: 'Remove from favourites' }))

    await waitFor(() =>
      expect(screen.getByText('You have not added any favourites yet.')).toBeInTheDocument(),
    )
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          String(input) === '/api/favourites/87654321' && init?.method === 'DELETE',
      ),
    ).toBe(true)
  })

  it('shows a danger callout when a removal fails, without touching the list (FR-013)', async () => {
    installFakeApi({
      favouritesHandler: () => jsonResponse({ favourites: [oneFavourite()] }),
      deleteHandler: () => jsonResponse({ error: { code: 'unknown_error', message: 'boom' } }, 500),
    })
    const user = userEvent.setup()
    renderFavourites()

    await screen.findByText('rival_ace')
    await user.click(screen.getByRole('button', { name: 'Remove from favourites' }))

    expect(await screen.findByText('We could not update your favourites')).toBeInTheDocument()
    // The row itself is untouched — still there, still removable.
    expect(screen.getByText('rival_ace')).toBeInTheDocument()
  })

  it('shows the load-failed state distinctly from the empty state when GET fails', async () => {
    installFakeApi({
      favouritesHandler: () =>
        jsonResponse({ error: { code: 'unknown_error', message: 'boom' } }, 500),
    })
    renderFavourites()

    expect(
      await screen.findByText('We could not load your favourites. Try again.'),
    ).toBeInTheDocument()
  })
})
