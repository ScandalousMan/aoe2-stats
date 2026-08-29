import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiPlayerProfile } from './api'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — mirrors
// `DashboardContainer.test.tsx` and `SearchContainer.test.tsx`'s identical setup.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { PlayerProfileContainer } = await import('./PlayerProfileContainer')

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

function baseProfile(overrides: Partial<ApiPlayerProfile> = {}): ApiPlayerProfile {
  return {
    profile_id: 87654321,
    alias: 'rival_ace',
    country: 'Germany',
    alias_observed_at: '2026-08-12T00:00:00Z',
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

function installFakeApi(
  profileHandler: () => Response,
  {
    favouritesHandler = () => jsonResponse({ favourites: [] }),
    favouriteMutationHandler,
  }: {
    favouritesHandler?: () => Response
    favouriteMutationHandler?: (method: string, profileId: string) => Response
  } = {},
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(authenticatedSession)
    }
    if (/^\/api\/players\/\d+$/.test(path) && method === 'GET') {
      return profileHandler()
    }
    if (path === '/api/favourites' && method === 'GET') {
      return favouritesHandler()
    }
    const favouriteMutationMatch = /^\/api\/favourites\/(\d+)$/.exec(path)
    if (
      favouriteMutationMatch &&
      (method === 'PUT' || method === 'DELETE') &&
      favouriteMutationMatch[1]
    ) {
      const profileId = favouriteMutationMatch[1]
      return favouriteMutationHandler
        ? favouriteMutationHandler(method, profileId)
        : jsonResponse({ profile_id: Number(profileId), favourited: method === 'PUT' })
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderProfile(profileId = 87654321) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<PlayerProfileContainer profileId={profileId} />, { wrapper })
}

describe('PlayerProfileContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it('renders a third party profile and its ratings once the query resolves', async () => {
    installFakeApi(() => jsonResponse(baseProfile()))
    renderProfile()

    expect(await screen.findByText('rival_ace')).toBeInTheDocument()
    expect(screen.getByText('1v1 Random Map')).toBeInTheDocument()
    expect(screen.getByText('1,842')).toBeInTheDocument()
  })

  it('shows the alias freshness note for a third party (003 spec §11.1.4)', async () => {
    installFakeApi(() => jsonResponse(baseProfile()))
    renderProfile()

    expect(await screen.findByText(/Last seen as rival_ace on/)).toBeInTheDocument()
  })

  it('renders a valid, explained profile — not an error — for a never-ranked player (US1 scenario 5)', async () => {
    installFakeApi(() => jsonResponse(baseProfile({ ratings: [] })))
    renderProfile()

    expect(await screen.findByText('rival_ace')).toBeInTheDocument()
    expect(screen.getByText('No ratings yet')).toBeInTheDocument()
  })

  it('collapses to the not-found callout for a profile this service has never observed', async () => {
    installFakeApi(() =>
      jsonResponse(
        { error: { code: 'not_found', message: 'This player has never been observed.' } },
        404,
      ),
    )
    renderProfile()

    expect(await screen.findByText('This player could not be found.')).toBeInTheDocument()
    // `ProfileSummary`'s own not-found callout carries the round trip back to `/search` here —
    // T383's own top-bar link (below, for the resolved case) is suppressed to avoid the two
    // reading as duplicates, so exactly one "Back to search" link, not a button, is present.
    expect(screen.getByRole('link', { name: 'Back to search' })).toHaveAttribute('href', '/search')
    expect(screen.queryByRole('button', { name: 'Back to search' })).not.toBeInTheDocument()
  })

  it('clicking "Back to search" navigates to /search from a resolved profile — T383', async () => {
    installFakeApi(() => jsonResponse(baseProfile()))
    const user = userEvent.setup()
    renderProfile()

    await screen.findByText('rival_ace')
    await user.click(screen.getByRole('button', { name: 'Back to search' }))

    expect(navigateMock).toHaveBeenCalledWith({ to: '/search' })
  })

  // T331: the one link into `players.$profileId.matches.tsx`.
  it('clicking "View match history" navigates to this profile\'s history route', async () => {
    installFakeApi(() => jsonResponse(baseProfile()))
    const user = userEvent.setup()
    renderProfile(87654321)

    await screen.findByText('rival_ace')
    await user.click(screen.getByRole('button', { name: 'View match history' }))

    expect(navigateMock).toHaveBeenCalledWith({
      to: '/players/$profileId/matches',
      params: { profileId: '87654321' },
    })
  })

  it('offers no "View match history" link while the profile has not resolved yet', () => {
    // A `Response` that never resolves keeps `profileQuery` pending forever, the same technique
    // used to assert a loading state has no premature content.
    installFakeApi((() => new Promise<Response>(() => {})) as unknown as () => Response)
    renderProfile()

    expect(screen.queryByRole('button', { name: 'View match history' })).not.toBeInTheDocument()
  })

  it('redirects to sign-in when the session has expired mid-visit', async () => {
    installFakeApi(() =>
      jsonResponse(
        { error: { code: 'not_authenticated', message: 'Your session has expired.' } },
        401,
      ),
    )
    renderProfile()

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith({ to: '/sign-in' }))
  })

  // T349: `FavouriteToggle` (US5), wired into `ProfileSummary`'s own slot.

  it("shows the unmarked toggle for a profile that is not one of the caller's favourites", async () => {
    installFakeApi(() => jsonResponse(baseProfile()))
    renderProfile()

    expect(await screen.findByRole('button', { name: 'Add to favourites' })).toBeInTheDocument()
  })

  it("shows the marked toggle for a profile already in the caller's favourites", async () => {
    installFakeApi(() => jsonResponse(baseProfile()), {
      favouritesHandler: () =>
        jsonResponse({
          favourites: [
            { profile_id: 87654321, alias: 'rival_ace', country: 'Germany', ratings: [] },
          ],
        }),
    })
    renderProfile()

    expect(
      await screen.findByRole('button', { name: 'Remove from favourites' }),
    ).toBeInTheDocument()
  })

  it('marks a profile as favourite (FR-013) and refreshes the toggle from the 200', async () => {
    let added = false
    installFakeApi(() => jsonResponse(baseProfile()), {
      favouritesHandler: () =>
        jsonResponse({
          favourites: added
            ? [{ profile_id: 87654321, alias: 'rival_ace', country: 'Germany', ratings: [] }]
            : [],
        }),
      favouriteMutationHandler: (method, profileId) => {
        added = method === 'PUT'
        return jsonResponse({ profile_id: Number(profileId), favourited: added })
      },
    })
    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByRole('button', { name: 'Add to favourites' }))

    expect(
      await screen.findByRole('button', { name: 'Remove from favourites' }),
    ).toBeInTheDocument()
  })

  it('shows a warning callout on the FR-016 bound race, without a fabricated max', async () => {
    installFakeApi(() => jsonResponse(baseProfile()), {
      favouriteMutationHandler: () =>
        jsonResponse(
          { error: { code: 'favourites_limit_reached', message: 'You have reached the limit.' } },
          409,
        ),
    })
    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByRole('button', { name: 'Add to favourites' }))

    expect(await screen.findByText('You have reached your favourites limit')).toBeInTheDocument()
    // The control itself stays pressable — never stuck disabled (favourite-toggle.md §5, "error").
    expect(screen.getByRole('button', { name: 'Add to favourites' })).toBeEnabled()
  })

  it('shows a danger callout when the PUT fails outright', async () => {
    installFakeApi(() => jsonResponse(baseProfile()), {
      favouriteMutationHandler: () =>
        jsonResponse({ error: { code: 'unknown_error', message: 'boom' } }, 500),
    })
    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByRole('button', { name: 'Add to favourites' }))

    expect(await screen.findByText('We could not update your favourites')).toBeInTheDocument()
  })

  it('redirects to sign-in when the session expires between load and the toggle click', async () => {
    installFakeApi(() => jsonResponse(baseProfile()), {
      favouriteMutationHandler: () =>
        jsonResponse(
          { error: { code: 'sign_in_required', message: 'Sign in to manage your favourites.' } },
          401,
        ),
    })
    const user = userEvent.setup()
    renderProfile()

    await user.click(await screen.findByRole('button', { name: 'Add to favourites' }))

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith({ to: '/sign-in' }))
  })
})
