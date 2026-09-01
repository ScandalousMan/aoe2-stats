import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiMatchListRow } from '../matches/api'
import type { ApiPlayerProfile } from './api'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — mirrors
// `PlayerProfileContainer.test.tsx` and `MatchDetailContainer.test.tsx`'s identical setup.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { PlayerMatchHistoryContainer } = await import('./PlayerMatchHistoryContainer')

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

// `archival_objected: false` here is the translation of the retired `ingest_consent: true` — a
// user whose ingestion runs, which constitution IX 4.0.0 made the default rather than something
// consented to (session.ts, DashboardContainer.test.tsx's `baseSession`).
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
    avatar_hash: null,
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

function baseRow(overrides: Partial<ApiMatchListRow> = {}): ApiMatchListRow {
  return {
    game_id: 1001,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
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
    opponents: [{ profile_id: 99, alias: 'someone_else', civ_id: 3, civ_name: 'Celts' }],
    participants: [
      {
        profile_id: 87654321,
        alias: 'rival_ace',
        country: 'de',
        team_id: 1,
        civ_id: 7,
        civ_name: 'Japanese',
        color_id: 4,
        result: 'win',
        rating: 934,
        rating_diff: 12,
      },
      {
        profile_id: 99,
        alias: 'someone_else',
        country: null,
        team_id: 2,
        civ_id: 3,
        civ_name: 'Celts',
        color_id: 2,
        result: 'loss',
        rating: 1500,
        rating_diff: -12,
      },
    ],
    capture_status: 'stored',
    capture_deadline_at: null,
    ...overrides,
  }
}

function installFakeApi(options: {
  profileHandler?: () => Response
  matchesHandler?: () => Response
}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(authenticatedSession)
    }
    if (/^\/api\/players\/\d+\/matches(\?.*)?$/.test(path) && method === 'GET') {
      return options.matchesHandler
        ? options.matchesHandler()
        : jsonResponse({ matches: [baseRow()], next_cursor: null })
    }
    if (/^\/api\/players\/\d+$/.test(path) && method === 'GET') {
      return options.profileHandler ? options.profileHandler() : jsonResponse(baseProfile())
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderHistory(profileId = 87654321) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<PlayerMatchHistoryContainer profileId={profileId} />, { wrapper })
}

describe('PlayerMatchHistoryContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it('renders the third party header and their match history once both queries resolve', async () => {
    installFakeApi({})
    renderHistory()

    // "rival_ace" appears twice once the row loads — the page header, and their own name among
    // the match row's Participants (§12.3, both are the same person's alias, legitimately) — so
    // this waits for at least one occurrence rather than asserting a single match.
    expect((await screen.findAllByText('rival_ace')).length).toBeGreaterThan(0)
    expect(screen.getByText('someone_else')).toBeInTheDocument()
  })

  // match-history.md §11.3: the third-party caption, never the first-person "Your recent matches"
  // this same `MatchList` renders on `matches.index.tsx`.
  it('names the viewed player in the list caption, never "Your recent matches" (§11.3)', async () => {
    installFakeApi({})
    renderHistory()

    await screen.findAllByText('rival_ace')
    expect(screen.getByRole('list', { name: "rival_ace's recent matches" })).toBeInTheDocument()
    expect(screen.queryByText('Your recent matches')).not.toBeInTheDocument()
  })

  it('shows the third-party empty-state sentence for a player with no matches', async () => {
    installFakeApi({ matchesHandler: () => jsonResponse({ matches: [], next_cursor: null }) })
    renderHistory()

    expect(
      await screen.findByText('rival_ace has no matches in their history yet.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('No matches yet')).not.toBeInTheDocument()
  })

  it('renders a valid, explained profile for a never-ranked player (US1 scenario 5)', async () => {
    installFakeApi({ profileHandler: () => jsonResponse(baseProfile({ ratings: [] })) })
    renderHistory()

    expect((await screen.findAllByText('rival_ace')).length).toBeGreaterThan(0)
    expect(screen.getByText('No ratings yet')).toBeInTheDocument()
  })

  it('collapses to the not-found callout, with no duplicate match-list state below it', async () => {
    installFakeApi({
      profileHandler: () =>
        jsonResponse({ error: { code: 'not_found', message: 'Never observed.' } }, 404),
    })
    renderHistory()

    expect(await screen.findByText('This player could not be found.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('clicking "Back to profile" navigates to the player\'s own profile route', async () => {
    installFakeApi({})
    const user = userEvent.setup()
    renderHistory(87654321)

    await screen.findAllByText('rival_ace')
    await user.click(screen.getByRole('button', { name: 'Back to profile' }))

    expect(navigateMock).toHaveBeenCalledWith({
      to: '/players/$profileId',
      params: { profileId: '87654321' },
    })
  })

  it('redirects to sign-in when the session has expired mid-visit', async () => {
    installFakeApi({
      matchesHandler: () =>
        jsonResponse(
          { error: { code: 'not_authenticated', message: 'Your session has expired.' } },
          401,
        ),
    })
    renderHistory()

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith({ to: '/sign-in' }))
  })
})
