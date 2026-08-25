import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiMatchDetail } from '../matches/api'
import type { ApiProfile } from '../profile/api'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — mirrors
// `DashboardContainer.test.tsx` and `PlayerProfileContainer.test.tsx`'s identical setup.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { MatchDetailContainer } = await import('./MatchDetailContainer')

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
  ingest_consent: boolean
  ingest_consent_at: string | null
  ingest_consent_withdrawn_at: string | null
  profiles: unknown[]
}

function baseSession(overrides: Partial<FakeSession> = {}): FakeSession {
  return {
    authenticated: true,
    user_id: 'user-1',
    allowlisted: true,
    ingest_consent: false,
    ingest_consent_at: null,
    ingest_consent_withdrawn_at: null,
    profiles: [],
    ...overrides,
  }
}

function baseDetail(overrides: Partial<ApiMatchDetail> = {}): ApiMatchDetail {
  return {
    game_id: 700_800_900,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2040,
    patch: '101.101',
    participants: [
      {
        profile_id: 11,
        alias: 'aoe2villain',
        team_id: 1,
        civ_id: 3,
        civ_name: 'Celts',
        color_id: 1,
        result: 'win',
        rating: 1800,
        rating_diff: 12,
      },
      {
        profile_id: 22,
        alias: 'rival_ace',
        team_id: 2,
        civ_id: 9,
        civ_name: 'Turks',
        color_id: 2,
        result: 'loss',
        rating: 1750,
        rating_diff: -12,
      },
    ],
    capture_status: null,
    capture_deadline_at: null,
    ...overrides,
  }
}

/** A small fake backend behind the real `fetch` global, the same discipline
 * `DashboardContainer.test.tsx`'s own `installFakeApi` documents: every call goes through
 * `apps/web/src/lib/api.ts`'s real `apiRequest`, proving the container against the actual
 * request/response contract rather than a mocked `api` module. */
function installFakeApi(options: {
  session?: FakeSession
  profiles?: ApiProfile[]
  detail?: () => Response
}) {
  const session = options.session ?? baseSession()
  const profiles = options.profiles ?? []

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(session)
    }
    if (path === '/api/profiles' && method === 'GET') {
      return jsonResponse({ profiles })
    }
    if (/^\/api\/matches\/\d+$/.test(path) && method === 'GET') {
      return options.detail ? options.detail() : jsonResponse(baseDetail())
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderMatch(gameId = '700800900') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<MatchDetailContainer gameId={gameId} />, { wrapper })
}

describe('MatchDetailContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  // T327/T331: the match-detail route no longer assumes the match belongs to the caller — a
  // signed-in caller with zero linked Steam profiles must still see the full match, not the
  // "Link a Steam account" callout `MatchHistoryContainer.tsx` shows in its place instead.
  it('renders the match in full for a caller with no linked Steam profile at all', async () => {
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })
    renderMatch()

    expect(await screen.findByText('Arabia')).toBeInTheDocument()
    expect(screen.getByText('aoe2villain')).toBeInTheDocument()
    expect(screen.getByText('rival_ace')).toBeInTheDocument()
  })

  it('still offers to link a Steam account, non-blocking, above the match content', async () => {
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })
    renderMatch()

    expect(await screen.findByText('Arabia')).toBeInTheDocument()
    expect(screen.getByText('No Steam account is linked yet')).toBeInTheDocument()
  })

  it('renders no row as "you" — a caller absent from the match sees the identical table', async () => {
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })
    renderMatch()

    await screen.findByText('Arabia')
    expect(screen.getByText('Win')).toBeInTheDocument()
    expect(screen.getByText('Loss')).toBeInTheDocument()
  })

  it('shows the game version in the header (FR-018)', async () => {
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail({ patch: '101.101' })) })
    renderMatch()

    expect(await screen.findByText(/101\.101/)).toBeInTheDocument()
  })

  it('renders an unresolved civilisation as its raw id, never a guessed name (FR-020)', async () => {
    installFakeApi({
      profiles: [],
      detail: () =>
        jsonResponse(
          baseDetail({
            participants: [
              {
                profile_id: 11,
                alias: 'aoe2villain',
                team_id: 1,
                civ_id: 87,
                civ_name: null,
                color_id: 1,
                result: 'win',
                rating: 1800,
                rating_diff: 12,
              },
            ],
          }),
        ),
    })
    renderMatch()

    expect(await screen.findByText('Civilisation ID 87')).toBeInTheDocument()
  })

  it('collapses to the not-found callout for a game_id this service does not hold', async () => {
    installFakeApi({
      profiles: [],
      detail: () => jsonResponse({ error: { code: 'not_found', message: 'No such match.' } }, 404),
    })
    renderMatch()

    expect(await screen.findByText('This match could not be found.')).toBeInTheDocument()
  })

  it('redirects to sign-in when the session has expired mid-visit', async () => {
    installFakeApi({
      profiles: [],
      detail: () =>
        jsonResponse(
          { error: { code: 'not_authenticated', message: 'Your session has expired.' } },
          401,
        ),
    })
    renderMatch()

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith({ to: '/sign-in' }))
  })
})
