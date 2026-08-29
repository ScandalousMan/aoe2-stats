import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
  archival_objected: boolean
  archival_objected_at: string | null
  profiles: unknown[]
}

// `false` / `null` is the fixture shape of "never answered any question", which constitution IX
// 4.0.0 makes archiving by default — mirrors `DashboardContainer.test.tsx`'s `baseSession`. This
// container never reads either field (it only branches on `session.authenticated`), so the exact
// value does not drive any assertion below; it exists to keep the fixture honest to the current
// `GET /api/me` contract.
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
        replay: {
          profile_id: 11,
          availability: 'obtainable',
          obtainable_until: null,
          download_path: '/api/matches/700800900/replay/11',
        },
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
        replay: {
          profile_id: 22,
          availability: 'expired',
          obtainable_until: null,
          download_path: null,
        },
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
    // Each alias now appears twice — once in `ParticipantsTable`, once in
    // `ReplayAvailabilityList`'s own row (T341) — so this asserts presence, not a single match.
    expect(screen.getAllByText('aoe2villain').length).toBeGreaterThan(0)
    expect(screen.getAllByText('rival_ace').length).toBeGreaterThan(0)
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
                replay: {
                  profile_id: 11,
                  availability: 'obtainable',
                  obtainable_until: null,
                  download_path: '/api/matches/700800900/replay/11',
                },
              },
            ],
          }),
        ),
    })
    renderMatch()

    expect(await screen.findByText('Civilisation ID 87')).toBeInTheDocument()
  })

  // T341: `ReplayAvailabilityList` wired from `GET /api/matches/{game_id}`'s per-participant
  // `replay` object (T338, FR-023..FR-029).

  it('renders one recorded-game row per participant, each in its own state', async () => {
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })
    renderMatch()

    // `Heading` renders before the match data arrives too (§5's loading skeleton), so waiting on
    // the badge text — only present once real rows replace the skeleton — is what actually
    // proves the data reached the list, not just that the section mounted.
    expect(await screen.findByText('Obtainable')).toBeInTheDocument()
    expect(screen.getByText('Expired')).toBeInTheDocument()
  })

  it('triggers a same-tab navigation to the participant’s own download_path on click (FR-023)', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })
    renderMatch()

    const [downloadButton] = await screen.findAllByRole('button', { name: 'Download' })
    fireEvent.click(downloadButton!)

    expect(assign).toHaveBeenCalledExactlyOnceWith('/api/matches/700800900/replay/11')
  })

  // Follow-up to T341: `packages/design-system/specs/replay-availability.md` §10 mandates a real
  // `<button>` triggering a same-tab navigation (no failure is script-observable), while §5's
  // boundary-race case (`code: "expired_since_page_load"`) reads as if the click were a `fetch`
  // this component could inspect. The resolution (`contracts/http-api.md`'s own sentence — the
  // download route "also records the outcome, so the page is right the next time"): keep the
  // navigation, and refetch `GET /api/matches/{game_id}` after the click so a row the server
  // recorded as having 404'd comes back correct on its own, without ever reading the download
  // response directly.
  //
  // Real timers throughout, deliberately: `screen.findAllByRole` below relies on
  // testing-library's own real-`setTimeout` polling to observe the fetch mock's microtask
  // resolution, the same reason `SearchContainer.test.tsx`'s fake-timer tests (T388) never mix
  // `findBy*` with `vi.useFakeTimers()` — a fake clock that is never advanced past a `findBy`
  // query's own poll interval hangs forever. `MatchDetailContainer.tsx`'s 1500ms reset window
  // costs this test ~1.5s of real wall-clock time instead; acceptable once, for a single test.
  it('refetches match detail after a point-of-view download click, and re-renders a row the server now reports differently (boundary race, FR-025)', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })

    let detailCallCount = 0
    const fetchMock = installFakeApi({
      profiles: [],
      detail: () => {
        detailCallCount += 1
        if (detailCallCount === 1) {
          // Rendered `obtainable`, offering a `DownloadAction` for profile 11.
          return jsonResponse(baseDetail())
        }
        // The server's own answer to the download request 404'd at fetch time and recorded the
        // outcome (`replay_fetch_misses`, T337) — `derive_availability` now reports this same
        // profile `never_recorded`, `download_path: null` (FR-025), before this component ever
        // reads the download route's own response.
        return jsonResponse(
          baseDetail({
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
                replay: {
                  profile_id: 11,
                  availability: 'never_recorded',
                  obtainable_until: null,
                  download_path: null,
                },
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
                replay: {
                  profile_id: 22,
                  availability: 'expired',
                  obtainable_until: null,
                  download_path: null,
                },
              },
            ],
          }),
        )
      },
    })

    renderMatch()

    const [downloadButton] = await screen.findAllByRole('button', { name: 'Download' })
    fireEvent.click(downloadButton!)

    expect(assign).toHaveBeenCalledExactlyOnceWith('/api/matches/700800900/replay/11')

    const countDetailCalls = () =>
      fetchMock.mock.calls.filter(([input]) => /^\/api\/matches\/\d+$/.test(String(input))).length

    // No second request yet — a refetch fired the instant `location.assign` runs would race the
    // download route's own server-side write of the outcome it is trying to read (this
    // component's own comment on the timing choice).
    expect(countDetailCalls()).toBe(1)

    // The refetch is deliberately deferred to the same 1500ms window
    // `MatchDetailContainer.tsx`'s own comment explains — so this assertion only becomes true
    // after that window elapses, on the real clock this test runs on.
    await waitFor(() => expect(countDetailCalls()).toBe(2), { timeout: 3000 })
    await waitFor(() => expect(screen.getByText('Never recorded')).toBeInTheDocument())
    // The row that lost its recording no longer offers a dead `DownloadAction` (FR-025) — the
    // one button left is the other row's, which was already `expired` and never had one to
    // begin with, so there must be none at all now.
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()
  })

  it('offers no download for an unobtainable point of view — absent, never a button that fails (FR-025)', async () => {
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })
    renderMatch()

    await screen.findByText('Expired')
    // Exactly one participant is `obtainable` in `baseDetail()`'s fixture; the other is
    // `expired` and must not contribute a second `DownloadAction`.
    expect(screen.getAllByRole('button', { name: 'Download' })).toHaveLength(1)
  })

  it('does not render the recorded-games section for a match this service does not hold', async () => {
    installFakeApi({
      profiles: [],
      detail: () => jsonResponse({ error: { code: 'not_found', message: 'No such match.' } }, 404),
    })
    renderMatch()

    await screen.findByText('This match could not be found.')
    expect(screen.queryByText('Recorded games')).not.toBeInTheDocument()
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
