import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiMatchListRow } from './api'
import type { ApiProfile } from '../profile/api'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — the same setup
// `PlayerMatchHistoryContainer.test.tsx` and `MatchDetailContainer.test.tsx` use.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { MatchHistoryContainer } = await import('./MatchHistoryContainer')

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

function session(archivalObjected: boolean) {
  return {
    authenticated: true,
    user_id: 'user-1',
    allowlisted: true,
    archival_objected: archivalObjected,
    archival_objected_at: archivalObjected ? '2026-10-01T00:00:00Z' : null,
    profiles: [],
  }
}

const ownProfile: ApiProfile = {
  profile_id: 1807091,
  alias: 'my_own_account',
  country: 'FR',
  avatar_hash: null,
  is_primary: true,
  linked_at: '2026-08-01T00:00:00Z',
  ratings: [],
}

const SIX_DAYS_MS = 6 * 24 * 60 * 60_000

function pendingRow(overrides: Partial<ApiMatchListRow> = {}): ApiMatchListRow {
  return {
    game_id: 1001,
    started_at: '2026-10-12T10:00:00Z',
    completed_at: '2026-10-12T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2040,
    civilisation: 7,
    civilisation_name: 'Japanese',
    result: 'win',
    rating: 934,
    rating_diff: 12,
    team_id: 1,
    color_id: 4,
    opponents: [],
    participants: [],
    capture_status: 'pending',
    capture_deadline_at: new Date(Date.now() + SIX_DAYS_MS + 60_000).toISOString(),
    ...overrides,
  }
}

function installFakeApi(options: { archivalObjected: boolean; rows: ApiMatchListRow[] }) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(session(options.archivalObjected))
    }
    if (path === '/api/profiles' && method === 'GET') {
      return jsonResponse({ profiles: [ownProfile] })
    }
    if (/^\/api\/matches\?/.test(path) && method === 'GET') {
      return jsonResponse({ matches: options.rows, next_cursor: null })
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderHistory() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<MatchHistoryContainer />, { wrapper })
}

describe('MatchHistoryContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  // T724 (capture-state-badge.md §4): the caller's own list passes `GET /api/me`'s
  // `archival_objected`, so an objecting owner's `pending` row promises no capture.
  it('reads "Not archived", with no countdown, for a pending row when the session has objected', async () => {
    installFakeApi({ archivalObjected: true, rows: [pendingRow()] })
    const { container } = renderHistory()

    expect(await screen.findByText('Not archived')).toBeInTheDocument()
    expect(screen.queryByText('Still catchable')).not.toBeInTheDocument()
    expect(container).not.toHaveTextContent(/left|window closing/i)
  })

  it('contrast: reads "Still catchable" with its countdown when the session has not objected', async () => {
    installFakeApi({ archivalObjected: false, rows: [pendingRow()] })
    renderHistory()

    expect(await screen.findByText('Still catchable')).toBeInTheDocument()
    expect(screen.getByText(/days left/)).toBeInTheDocument()
    expect(screen.queryByText('Not archived')).not.toBeInTheDocument()
  })

  it('an objecting session leaves a stored row as "Archived"', async () => {
    installFakeApi({
      archivalObjected: true,
      rows: [pendingRow({ capture_status: 'stored', capture_deadline_at: null })],
    })
    renderHistory()

    expect(await screen.findByText('Archived')).toBeInTheDocument()
    expect(screen.queryByText('Not archived')).not.toBeInTheDocument()
  })
})
