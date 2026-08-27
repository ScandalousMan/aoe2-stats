import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiProfile } from './api'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — `DashboardContainer`
// calls it directly (not through `Route.useRouteContext()`), so it is the one dependency this
// suite replaces. Every other effect (the two TanStack Query hooks, the mutation calls) runs for
// real against a stubbed `fetch`, which is what actually proves the wiring in the container
// rather than the mock.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { DashboardContainer } = await import('./DashboardContainer')

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

interface FakeSession {
  authenticated: true
  user_id: string
  allowlisted: boolean
  archival_objected: boolean
  archival_objected_at: string | null
  profiles: unknown[]
}

// `false` / `null` is deliberately the default here, not a placeholder: constitution IX 4.0.0
// inverted the rule, and this is the fixture shape of "a linked user who has never answered any
// question" — the exact case the amendment says is archiving, not awaiting an answer.
function baseSession(overrides: Partial<FakeSession> = {}): FakeSession {
  return {
    authenticated: true,
    user_id: 'user-1',
    allowlisted: true,
    archival_objected: false,
    archival_objected_at: null,
    profiles: [],
    ...overrides,
  }
}

function baseProfile(overrides: Partial<ApiProfile> = {}): ApiProfile {
  return {
    profile_id: 1,
    alias: 'ArchonQueen',
    country: 'FR',
    is_primary: true,
    linked_at: '2026-08-01T00:00:00Z',
    ratings: [
      {
        leaderboard_id: 3,
        leaderboard_name: '1v1 Random Map',
        rating: 1500,
        rank: 200,
        wins: 10,
        losses: 5,
        streak: 2,
        highest_rating: 1600,
        captured_at: '2026-08-01T00:00:00Z',
      },
    ],
    ...overrides,
  }
}

/** A small fake backend behind the real `fetch` global: every call this app makes goes through
 * `apps/web/src/lib/api.ts`'s real `apiRequest`, so this proves the container against the actual
 * request/response contract rather than against a mocked `api` module. */
function installFakeApi(initial: { session: FakeSession; profiles: ApiProfile[] }) {
  let session = initial.session
  let profiles = initial.profiles

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(session)
    }
    if (path === '/api/profiles' && method === 'GET') {
      return jsonResponse({ profiles })
    }
    const primaryMatch = /^\/api\/profiles\/(\d+)\/primary$/.exec(path)
    if (primaryMatch && method === 'POST') {
      const id = Number(primaryMatch[1])
      profiles = profiles.map((profile) => ({ ...profile, is_primary: profile.profile_id === id }))
      return jsonResponse({ profile_id: id, is_primary: true })
    }
    const unlinkMatch = /^\/api\/profiles\/(\d+)(\?confirm=true)?$/.exec(path)
    if (unlinkMatch && method === 'DELETE') {
      const id = Number(unlinkMatch[1])
      const confirmed = Boolean(unlinkMatch[2])
      const archivedReplays = { retained: true, count: 2, message: 'Archived replays are kept.' }
      if (!confirmed) {
        return jsonResponse({ confirmed: false, archived_replays: archivedReplays })
      }
      profiles = profiles.filter((profile) => profile.profile_id !== id)
      return jsonResponse({
        confirmed: true,
        unlinked_at: '2026-08-20T00:00:00Z',
        archived_replays: archivedReplays,
      })
    }
    if (path === '/api/auth/signout' && method === 'POST') {
      return jsonResponse(null)
    }
    if (path === '/api/privacy/archival-objection' && method === 'POST') {
      const body = JSON.parse(String(init?.body)) as { objected: boolean }
      const recordedAt = '2026-08-10T00:00:00Z'
      // Mirrors the real router (T405): objecting records a fresh timestamp, resuming clears it
      // back to null — the same shape a user who never objected reads as.
      session = {
        ...session,
        archival_objected: body.objected,
        archival_objected_at: body.objected ? recordedAt : null,
      }
      return jsonResponse({
        archival_objected: session.archival_objected,
        archival_objected_at: session.archival_objected_at,
      })
    }

    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })

  vi.stubGlobal('fetch', fetchMock)
  return {
    fetchMock,
    expireSession() {
      // Simulates a cookie dying mid-visit: every subsequent call answers the documented
      // `not_authenticated` envelope (contracts/http-api.md), which is exactly what
      // `redirectIfSessionExpired` in `DashboardContainer.tsx` watches for.
      session = baseSession()
      fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === '/api/me' && (init?.method ?? 'GET') === 'GET') {
          return jsonResponse(session)
        }
        return jsonResponse(
          { error: { code: 'not_authenticated', message: 'Your session has expired.' } },
          401,
        )
      })
    },
  }
}

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<DashboardContainer />, { wrapper })
}

describe('DashboardContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it('renders the linked profile and its ratings once both queries resolve', async () => {
    installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    renderDashboard()

    expect(await screen.findByText('ArchonQueen')).toBeInTheDocument()
    expect(screen.getByText('1v1 Random Map')).toBeInTheDocument()
    expect(screen.getByText('1,500')).toBeInTheDocument()
  })

  it('shows the empty-account callout, not the summary, when no profile is linked', async () => {
    installFakeApi({ session: baseSession(), profiles: [] })
    renderDashboard()

    expect(await screen.findByText('No Steam account is linked yet')).toBeInTheDocument()
    expect(screen.queryByText('ArchonQueen')).not.toBeInTheDocument()
  })

  it('archives by default for a linked user who has never answered any question — constitution IX 4.0.0, the inverted default', async () => {
    // `baseSession()`'s default (`archival_objected: false`, `archival_objected_at: null`) is
    // exactly the fixture for "never answered": there is no third state left to render, and no
    // interaction happens before this assertion. An implementation that reintroduced the retired
    // gate would show a question here instead of a running state, which is what every assertion
    // below rules out.
    installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    renderDashboard()

    await screen.findByText('ArchonQueen')
    expect(screen.getByRole('status')).toHaveTextContent('Archival is on.')
    expect(screen.getByRole('button', { name: 'Object to archival' })).toBeInTheDocument()
    // The retired gate does not resurface under any name: no accept/decline pair, no "not now",
    // no checkbox, no question awaiting an answer.
    expect(screen.queryByRole('button', { name: /accept/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /decline/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/archive my replays/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('shows archival off with the recorded date for a user who has objected, and a "Resume archival" switch', async () => {
    installFakeApi({
      session: baseSession({
        archival_objected: true,
        archival_objected_at: '2026-08-01T00:00:00Z',
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    renderDashboard()

    await screen.findByText('ArchonQueen')
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Archival is off.')
    expect(status).toHaveTextContent('2026')
    expect(screen.getByRole('button', { name: 'Resume archival' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Object to archival' })).not.toBeInTheDocument()
  })

  it('objecting posts to /api/privacy/archival-objection and flips the dashboard to the objected state', async () => {
    const fake = installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('ArchonQueen')
    await user.click(screen.getByRole('button', { name: 'Object to archival' }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Archival is off.')
    })
    expect(screen.getByRole('button', { name: 'Resume archival' })).toBeInTheDocument()
    expect(fake.fetchMock).toHaveBeenCalledWith(
      '/api/privacy/archival-objection',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ objected: true }) }),
    )
  })

  it('resuming after an objection shows the "Archival resumed." acknowledgement, not the plain steady-state heading', async () => {
    installFakeApi({
      session: baseSession({
        archival_objected: true,
        archival_objected_at: '2026-08-01T00:00:00Z',
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('ArchonQueen')
    await user.click(screen.getByRole('button', { name: 'Resume archival' }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Archival resumed.')
    })
    expect(screen.queryByText('Archival is on.')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Object to archival' })).toBeInTheDocument()
  })

  it('unlinking previews, then confirms, and the profile disappears afterwards', async () => {
    installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('ArchonQueen')
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    await user.click(screen.getByRole('menuitem', { name: 'Unlink this profile' }))

    const dialog = await screen.findByRole('dialog', { name: 'Unlink ArchonQueen?' })
    expect(within(dialog).getByText(/2 replays archived/)).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Unlink this profile' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    expect(await screen.findByText('No Steam account is linked yet')).toBeInTheDocument()
  })

  it('cancelling the unlink dialog leaves the profile linked and closes without confirming', async () => {
    installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('ArchonQueen')
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    await user.click(screen.getByRole('menuitem', { name: 'Unlink this profile' }))
    const dialog = await screen.findByRole('dialog', { name: 'Unlink ArchonQueen?' })
    await user.click(within(dialog).getByRole('button', { name: 'Keep it linked' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    expect(screen.getByText('ArchonQueen')).toBeInTheDocument()
  })

  it('clicking "Search players" navigates to /search — T383, the entry point to US1', async () => {
    installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('ArchonQueen')
    await user.click(screen.getByRole('button', { name: 'Search players' }))

    expect(navigateMock).toHaveBeenCalledWith({ to: '/search' })
  })

  it('signing out calls POST /api/auth/signout and navigates to /sign-in — quickstart.md scenario 1', async () => {
    const fake = installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('ArchonQueen')
    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({ to: '/sign-in' })
    })
    expect(fake.fetchMock).toHaveBeenCalledWith(
      '/api/auth/signout',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('a session that expires mid-mutation redirects to /sign-in instead of showing broken state', async () => {
    const fake = installFakeApi({
      session: baseSession({
        profiles: [{ profile_id: 1, alias: 'ArchonQueen', country: 'FR', is_primary: true }],
      }),
      profiles: [baseProfile()],
    })
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('ArchonQueen')
    fake.expireSession()

    await user.click(screen.getByRole('button', { name: 'Manage' }))
    await user.click(screen.getByRole('menuitem', { name: 'Unlink this profile' }))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({ to: '/sign-in' })
    })
  })
})
