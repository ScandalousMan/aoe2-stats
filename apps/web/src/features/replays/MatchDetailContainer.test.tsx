import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    // The redirect-driven tests below (`?replay_error=...`) navigate this file's shared jsdom
    // `window` with the real `history` API rather than stubbing `location` — reset it so one
    // test's query string never leaks into the next.
    window.history.replaceState(null, '', '/')
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

  // 2026-08-29 remediation: a same-tab navigation to the download route that fails cannot be
  // observed by this component at all (`api.ts`'s own note — `triggerReplayPointOfViewDownload`
  // carries no completion signal), so a previous fix that deferred a client-side refetch never
  // actually worked: a plain JSON failure response *navigates the browser away from this page*,
  // destroying the pending timeout before it could ever fire. `routers/replays.py` now answers a
  // same-origin `303` back to this exact page instead
  // (`_match_page_redirect_for_download_failure`), carrying the failure as query parameters
  // (`downloadFailure.ts`) this component reads once, on load — real navigation and reload, no
  // fetch mock involved in the mechanism this test exercises, only in what the reloaded page's
  // own `GET /api/matches/{game_id}` answers with.

  it('renders the boundary-race sentence for the row the redirect names, from the URL alone (FR-025)', async () => {
    // The server already wrote the boundary-race evidence before issuing the redirect
    // (`_record_fetch_miss`), so the freshly-fetched detail this reload receives reports the
    // affected profile `never_recorded` — the override below is what still shows the real
    // boundary-race sentence for this one page load, not `never_recorded`'s own copy.
    window.history.pushState(
      {},
      '',
      '/matches/700800900?replay_error=expired_since_page_load&replay_error_profile_id=11',
    )
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
        ),
    })

    renderMatch()

    // Both rows read `Expired` — profile 11 via the redirect-carried override, profile 22
    // because `baseDetail()`'s own fixture already seeds it that way — so this asserts the count
    // rather than a single match.
    expect(await screen.findAllByText('Expired')).toHaveLength(2)
    expect(
      screen.getByText('This recording expired while you were viewing this page.'),
    ).toBeInTheDocument()
    // The row that lost its recording no longer offers a dead `DownloadAction` (FR-025) — the
    // one button left, if any, would be the other row's, which was already `expired` and never
    // had one to begin with, so there must be none at all.
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()

    // `replay-availability.md` §5's "distinct for exactly one page load": the parameter is
    // cleared immediately so a refresh does not resurrect the alert.
    await waitFor(() => expect(window.location.search).toBe(''))
  })

  it('renders the rate-limit alert with the exact retry_after the redirect carried (FR-028)', async () => {
    window.history.pushState(
      {},
      '',
      '/matches/700800900?replay_error=rate_limited&replay_error_profile_id=11&replay_error_retry_after=42',
    )
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })

    renderMatch()

    expect(
      await screen.findByText('You are downloading too quickly. Try again in 42 seconds.'),
    ).toBeInTheDocument()
    // The row itself is unchanged and still pressable (`replay-availability.md` §5: "never a row
    // that looks like it gave up") — `baseDetail()`'s profile 11 is `obtainable`.
    expect(screen.getAllByRole('button', { name: 'Download' })).toHaveLength(1)
    await waitFor(() => expect(window.location.search).toBe(''))
  })

  it('renders the generic failed-request alert for any other redirect-carried code', async () => {
    window.history.pushState(
      {},
      '',
      '/matches/700800900?replay_error=never_recorded&replay_error_profile_id=22',
    )
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })

    renderMatch()

    await screen.findByText('Expired')
    expect(
      await screen.findByText('We could not start that download. Try again.'),
    ).toBeInTheDocument()
    await waitFor(() => expect(window.location.search).toBe(''))
  })

  // H3 remediation (2026-08-29): a redirect-carried failure used to be held in `useState` for the
  // component's whole lifetime, unconditionally overriding `downloadStates[id]` — a retry of the
  // failing row never showed its own `loading` state, and a successful retry (a `200` that never
  // navigates) left the stale `Callout` on screen forever. `MatchDetailContainer.tsx`'s
  // `handlePointOfViewDownload` now clears the failure for exactly the row being retried, the
  // moment the retry starts.

  it('clicking the failing row again shows its own loading state, not the stale failure', async () => {
    // `vi.stubGlobal('location', ...)` below replaces `window.location` with a plain object
    // spread at call time — `pushState` must run first, or the stub's own `search` is frozen to
    // whatever the URL was *before* this test's own navigation, and `MatchDetailContainer`'s
    // mount-time `parseReplayDownloadFailure(window.location.search)` reads nothing.
    window.history.pushState(
      {},
      '',
      '/matches/700800900?replay_error=not_found&replay_error_profile_id=11',
    )
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })

    renderMatch()

    expect(
      await screen.findByText('We could not start that download. Try again.'),
    ).toBeInTheDocument()

    const downloadButton = await screen.findByRole('button', { name: 'Download' })
    fireEvent.click(downloadButton)

    expect(
      screen.queryByText('We could not start that download. Try again.'),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preparing your download…' })).toBeInTheDocument()
  })

  it('a successful retry — a stream that never navigates — returns the row to default with no alert', async () => {
    vi.useFakeTimers()
    try {
      // Same ordering note as the previous test: `pushState` first, then the `location` stub.
      window.history.pushState(
        {},
        '',
        '/matches/700800900?replay_error=not_found&replay_error_profile_id=11',
      )
      const assign = vi.fn()
      vi.stubGlobal('location', { ...window.location, assign })
      installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })

      renderMatch()

      await vi.waitFor(() =>
        expect(
          screen.getByText('We could not start that download. Try again.'),
        ).toBeInTheDocument(),
      )

      const downloadButton = screen.getByRole('button', { name: 'Download' })
      fireEvent.click(downloadButton)

      // The `303`-carried failure never returns here again — this row's own `200` stream is
      // in-place, so nothing else touches this component's state until the reset timeout below,
      // the same one `handleDownload`'s own note describes for the header's `DownloadAction`.
      // Wrapped in `act`: the reset fires from a `setTimeout` callback, outside any event RTL
      // wraps on its own, and React 19 will not flush the resulting state update to the DOM
      // before the next assertion otherwise.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })

      expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
      expect(
        screen.queryByText('We could not start that download. Try again.'),
      ).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('a failure on one row does not affect another row’s state, in either direction', async () => {
    // Same ordering note as above: `pushState` first, then the `location` stub.
    window.history.pushState(
      {},
      '',
      '/matches/700800900?replay_error=not_found&replay_error_profile_id=11',
    )
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
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
                profile_id: 33,
                alias: 'third_party',
                team_id: 2,
                civ_id: 9,
                civ_name: 'Turks',
                color_id: 2,
                result: 'loss',
                rating: 1750,
                rating_diff: -12,
                replay: {
                  profile_id: 33,
                  availability: 'obtainable',
                  obtainable_until: null,
                  download_path: '/api/matches/700800900/replay/33',
                },
              },
            ],
          }),
        ),
    })

    renderMatch()

    expect(
      await screen.findByText('We could not start that download. Try again.'),
    ).toBeInTheDocument()

    const [, otherRowButton] = await screen.findAllByRole('button', { name: 'Download' })
    fireEvent.click(otherRowButton!)

    // Row 33's own click must not touch row 11's failure — the alert is still row 11's, and row
    // 33 shows its own `loading` state rather than inheriting row 11's `error`.
    expect(screen.getByText('We could not start that download. Try again.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preparing your download…' })).toBeInTheDocument()
    expect(assign).toHaveBeenCalledExactlyOnceWith('/api/matches/700800900/replay/33')
  })

  // L15 remediation (2026-08-29): `replay_error` is read straight off the URL, unauthenticated —
  // a forged or stale code outside the fixed set `download_replay_point_of_view` can actually
  // raise must be ignored, not rendered as if the server had sent it.

  it('ignores a crafted/unknown replay_error value rather than rendering it', async () => {
    window.history.pushState(
      {},
      '',
      '/matches/700800900?replay_error=totally_bogus&replay_error_profile_id=11',
    )
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })

    renderMatch()

    await screen.findByText('Obtainable')
    expect(
      screen.queryByText('We could not start that download. Try again.'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('This recording expired while you were viewing this page.'),
    ).not.toBeInTheDocument()
    // The row is unaffected: still pressable, not stuck in any failure-derived state.
    expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
  })

  // M7 remediation (2026-08-29): `history.replaceState(null, ...)` used to wipe
  // `window.history.state` for this entry along with the URL — `@tanstack/react-router`'s history
  // layer owns that object. The redirect-driven tests above only ever assert `location.search`;
  // this one pushes a real (non-empty) state object first, the way the router's own navigation
  // does, and asserts the cleanup preserves it rather than replacing it with `null`.

  it('preserves window.history.state when clearing the redirect-carried query parameters', async () => {
    const routerState = { key: 'abc123', idx: 3 }
    window.history.pushState(
      routerState,
      '',
      '/matches/700800900?replay_error=not_found&replay_error_profile_id=11',
    )
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })

    renderMatch()

    await screen.findByText('We could not start that download. Try again.')
    await waitFor(() => expect(window.location.search).toBe(''))
    expect(window.history.state).toEqual(routerState)
  })

  it('renders no alert at all for an ordinary visit carrying no replay_error', async () => {
    installFakeApi({ profiles: [], detail: () => jsonResponse(baseDetail()) })

    renderMatch()

    await screen.findByText('Obtainable')
    expect(
      screen.queryByText('We could not start that download. Try again.'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('This recording expired while you were viewing this page.'),
    ).not.toBeInTheDocument()
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
