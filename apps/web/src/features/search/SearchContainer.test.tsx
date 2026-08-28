import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
  archival_objected: false,
  archival_objected_at: null,
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

// Regression (B3): `onSearch={(query) => void runSearch(query)}` in `SearchContainer.tsx` is a
// fresh closure on every render, and `runSearch` itself calls `setState` — first to `loading`,
// then to `answered` — which is exactly the re-render `SearchBox`'s debounce effect must not treat
// as a reason to fire again. Counting `fetch` calls to the search endpoint, rather than only
// asserting the final rendered state, is the point: the tests above pass identically whether the
// request fired once or in a runaway loop, because they only ever look at the last frame.
function countSearchCalls(fetchMock: ReturnType<typeof installFakeApi>) {
  return fetchMock.mock.calls.filter(([input]) => String(input).startsWith('/api/players/search'))
    .length
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

  // T388: both regression tests below used to drive the query through `userEvent.type` and then
  // wait on the wall clock — a real 900ms `setTimeout` in the first, and up to 4s of real
  // `findByText` polling in the second — making them the two slowest tests in the web suite for a
  // property ("no extra timer fires") that a fake clock proves exactly as well, instantly.
  // `fireEvent.change` + `act(() => vi.advanceTimersByTime(...))` is `SearchBox.test.tsx`'s own
  // established idiom (packages/design-system) for driving this exact debounce under a fake clock;
  // mirrored here rather than reaching for `userEvent`, whose internal delays fight fake timers.
  it('fires exactly one search request for one settled query, even after the response resolves and the box re-renders (B3 regression)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = installFakeApi(() =>
        jsonResponse({ results: [], degraded: false, reason: null }),
      )
      renderSearch()

      fireEvent.change(screen.getByLabelText('Search a player'), { target: { value: 'viper' } })
      // `SearchBox`'s own debounce (default 300ms), then let the stubbed fetch's response and the
      // resulting re-render settle.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })

      expect(screen.getByText('No player matches “viper”.')).toBeInTheDocument()
      expect(countSearchCalls(fetchMock)).toBe(1)

      // Give a re-armed debounce timer every chance to fire the same, already-settled query
      // again — this is the regression itself: a stable `onSearch` closure would make this
      // unnecessary, but T388 (SearchContainer.tsx's own comment) is exactly why it cannot be.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(900)
      })
      expect(countSearchCalls(fetchMock)).toBe(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not re-fire the search while the rate-limited countdown ticks once a second (B3 regression: the countdown itself is a re-render)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = installFakeApi(() =>
        jsonResponse(
          {
            error: {
              code: 'rate_limited',
              message: 'Too many searches.',
              detail: { retry_after: 3 },
            },
          },
          429,
        ),
      )
      renderSearch()

      fireEvent.change(screen.getByLabelText('Search a player'), { target: { value: 'viper' } })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })

      expect(screen.getByText("You're searching too quickly. Try again in 3s.")).toBeInTheDocument()
      expect(countSearchCalls(fetchMock)).toBe(1)

      // The countdown ticks every second for 3s, each tick a `setState` in `SearchBox` itself —
      // let it run out and settle, then confirm no further request landed in the meantime. Once
      // it reaches zero the sentence itself changes (T388, SearchBox's own fix) rather than
      // sitting on "Try again in 0s." forever.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000)
      })
      expect(screen.getByText('You can search again now.')).toBeInTheDocument()
      expect(countSearchCalls(fetchMock)).toBe(1)
    } finally {
      vi.useRealTimers()
    }
  })
})
