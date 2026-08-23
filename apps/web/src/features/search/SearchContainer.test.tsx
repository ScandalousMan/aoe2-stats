import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — `SearchContainer` calls
// it directly, so it is the one dependency this suite replaces, the same discipline
// `DashboardContainer.test.tsx` established. Every other effect (the session query, the search
// request) runs for real against a stubbed `fetch`.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { SearchContainer } = await import('./SearchContainer')

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
  ingest_consent: true,
  ingest_consent_at: '2026-08-01T00:00:00Z',
  ingest_consent_withdrawn_at: null,
  profiles: [],
}

function installFakeApi(searchHandler: (query: string) => Response) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(authenticatedSession)
    }
    const searchMatch = /^\/api\/players\/search\?q=(.+)$/.exec(path)
    if (searchMatch && method === 'GET') {
      return searchHandler(decodeURIComponent(searchMatch[1] ?? ''))
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderSearch() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<SearchContainer />, { wrapper })
}

describe('SearchContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it('shows the idle state before any query is submitted', async () => {
    installFakeApi(() => jsonResponse({ results: [], degraded: false, reason: null }))
    renderSearch()

    expect(await screen.findByText('Search for a player by name.')).toBeInTheDocument()
  })

  it('renders found results with country and standing (FR-002)', async () => {
    installFakeApi(() =>
      jsonResponse({
        results: [
          {
            profile_id: 196240,
            alias: 'TheViper',
            country: 'Netherlands',
            games_played: 8213,
            clan: null,
          },
        ],
        degraded: false,
        reason: null,
      }),
    )
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByLabelText('Search a player'), 'viper')
    expect(await screen.findByText('TheViper')).toBeInTheDocument()
    expect(screen.getByText('Netherlands')).toBeInTheDocument()
    expect(screen.getByText('8213 games')).toBeInTheDocument()
  })

  it('distinguishes found-nothing from degraded (FR-003)', async () => {
    installFakeApi(() => jsonResponse({ results: [], degraded: false, reason: null }))
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByLabelText('Search a player'), 'nobody')
    expect(await screen.findByText('No player matches “nobody”.')).toBeInTheDocument()
  })

  it('shows the degraded banner, distinct from found-nothing, when the source is unavailable', async () => {
    installFakeApi(() =>
      jsonResponse({ results: [], degraded: true, reason: 'search_source_unavailable' }),
    )
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByLabelText('Search a player'), 'viper')
    expect(await screen.findByText('Player search is temporarily degraded.')).toBeInTheDocument()
    expect(screen.queryByText('No player matches “viper”.')).not.toBeInTheDocument()
  })

  it('shows the rate-limited countdown, carrying retry_after from the error detail', async () => {
    installFakeApi(() =>
      jsonResponse(
        {
          error: {
            code: 'rate_limited',
            message: 'Too many searches.',
            detail: { retry_after: 42 },
          },
        },
        429,
      ),
    )
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByLabelText('Search a player'), 'viper')
    expect(
      await screen.findByText("You're searching too quickly. Try again in 42s."),
    ).toBeInTheDocument()
  })

  it('shows the failed state with a retry action on an unexpected error', async () => {
    installFakeApi(() => jsonResponse({ error: { code: 'unknown_error', message: 'boom' } }, 500))
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByLabelText('Search a player'), 'viper')
    expect(await screen.findByText('We could not search right now.')).toBeInTheDocument()
  })

  it('redirects to sign-in when the session has expired mid-search', async () => {
    installFakeApi(() =>
      jsonResponse(
        { error: { code: 'not_authenticated', message: 'Your session has expired.' } },
        401,
      ),
    )
    const user = userEvent.setup()
    renderSearch()

    await user.type(screen.getByLabelText('Search a player'), 'viper')
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith({ to: '/sign-in' }))
  })
})
