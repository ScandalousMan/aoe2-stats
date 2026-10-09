import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiAnalysisDocument } from './api'

const { AnalysisContainer } = await import('./AnalysisContainer')

// Mirrors `MatchDetailContainer.test.tsx`'s own discipline: a small fake behind the real `fetch`
// global, so this file proves the container against the real request/response contract
// (`lib/api.ts`'s `apiRequest`) rather than a mocked `api` module.

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

interface FakeMatchDetail {
  game_id: number
  started_at: string | null
  completed_at: string
  map_name: string | null
  leaderboard_id: number
  leaderboard_name: string
  duration_seconds: number | null
  patch: string | null
  participants: unknown[]
  capture_status: string | null
  capture_deadline_at: string | null
  analysis: {
    state: string
    parser_version: string | null
    stale: boolean
    point_of_view_profile_id: number | null
    result_path: string
    reason: string | null
    error_class: string | null
  }
}

function baseParticipants() {
  return [
    {
      profile_id: 196_240,
      alias: 'GL.TheViper',
      team_id: 1,
      civ_id: 5,
      civ_name: 'Britons',
      color_id: 1,
      result: 'win',
      rating: 1900,
      rating_diff: 12,
      replay: {
        profile_id: 196_240,
        availability: 'expired',
        obtainable_until: null,
        download_path: null,
      },
    },
    {
      profile_id: 87_654,
      alias: 'Hera',
      team_id: 2,
      civ_id: 9,
      civ_name: 'Mayans',
      color_id: 2,
      result: 'loss',
      rating: 1850,
      rating_diff: -12,
      replay: {
        profile_id: 87_654,
        availability: 'expired',
        obtainable_until: null,
        download_path: null,
      },
    },
  ]
}

function baseDetail(overrides: Partial<FakeMatchDetail['analysis']> = {}): FakeMatchDetail {
  return {
    game_id: 500_546_441,
    started_at: '2026-08-22T10:00:00Z',
    completed_at: '2026-08-22T10:34:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2040,
    patch: '101.101',
    participants: baseParticipants(),
    capture_status: null,
    capture_deadline_at: null,
    analysis: {
      state: 'absent',
      parser_version: null,
      stale: false,
      point_of_view_profile_id: null,
      result_path: '/api/matches/500546441/analysis',
      reason: null,
      error_class: null,
      ...overrides,
    },
  }
}

function baseDocument(): ApiAnalysisDocument {
  return {
    schema_version: 1,
    game_id: 500_546_441,
    point_of_view_profile_id: 196_240,
    engine: { name: 'aoe2rec-py', version: '0.1.21', deps: {} },
    source_recording: {
      object_key: 'retained-recordings/500546441/196240.zip',
      sha256: 'a'.repeat(64),
    },
    extracted_at: '2026-08-23T10:00:00Z',
    participants: [
      {
        profile_id: 196_240,
        player_number: 1,
        civ_id: 5,
        resolved_team_id: 1,
        builds: [],
        trainings: [],
        researches: [],
        age_up_commands: { '101': 401_000 },
        villagers_ordered: 68,
        actions: 3821,
        actions_per_minute: 142.7,
        resigned_at_ms: null,
      },
      {
        profile_id: 87_654,
        player_number: 2,
        civ_id: 9,
        resolved_team_id: 2,
        builds: [],
        trainings: [],
        researches: [],
        age_up_commands: {},
        villagers_ordered: 61,
        actions: 3010,
        actions_per_minute: 118.3,
        resigned_at_ms: null,
      },
    ],
  }
}

function installFakeApi(options: {
  detail: () => Response
  document?: () => Response
  analyze?: () => Response
}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (/^\/api\/matches\/\d+$/.test(path) && method === 'GET') {
      return options.detail()
    }
    if (/^\/api\/matches\/\d+\/analysis$/.test(path) && method === 'GET') {
      return options.document ? options.document() : jsonResponse(baseDocument())
    }
    if (path === '/api/analyze' && method === 'POST') {
      return options.analyze ? options.analyze() : jsonResponse(baseDetail().analysis)
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAnalysis(gameId = '500546441') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return { ...render(<AnalysisContainer gameId={gameId} />, { wrapper }), queryClient }
}

describe('AnalysisContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders a plain "Request analysis" button for "absent" — never the AnalysisTimeline heading', async () => {
    installFakeApi({ detail: () => jsonResponse(baseDetail({ state: 'absent' })) })
    renderAnalysis()

    expect(await screen.findByRole('button', { name: 'Request analysis' })).toBeInTheDocument()
    expect(screen.queryByText('Match analysis')).not.toBeInTheDocument()
  })

  it('renders nothing for a game_id this service does not hold (FR-045-style not-found gate)', async () => {
    installFakeApi({
      detail: () => jsonResponse({ error: { code: 'not_found', message: 'No such match.' } }, 404),
    })
    const { container } = renderAnalysis()

    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it('renders nothing for a gameId that is not a number, without ever calling the API', () => {
    const fetchMock = installFakeApi({ detail: () => jsonResponse(baseDetail()) })
    const { container } = renderAnalysis('not-a-number')

    expect(container).toBeEmptyDOMElement()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows progress for "queued" and "running", with no action offered (FR-035)', async () => {
    installFakeApi({ detail: () => jsonResponse(baseDetail({ state: 'running' })) })
    renderAnalysis()

    expect(await screen.findByText('Analysing this match…')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders the published timeline with no recompute offered when not stale', async () => {
    installFakeApi({
      detail: () => jsonResponse(baseDetail({ state: 'published', parser_version: '0.1.21' })),
      document: () => jsonResponse(baseDocument()),
    })
    renderAnalysis()

    expect(await screen.findByText('Match analysis')).toBeInTheDocument()
    expect(await screen.findByText('GL.TheViper')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Recompute' })).not.toBeInTheDocument()
  })

  it('offers Recompute only while the summary reports stale: true (FR-041)', async () => {
    installFakeApi({
      detail: () =>
        jsonResponse(baseDetail({ state: 'published', stale: true, parser_version: '0.1.0' })),
      document: () => jsonResponse(baseDocument()),
    })
    renderAnalysis()

    expect(await screen.findByRole('button', { name: 'Recompute' })).toBeInTheDocument()
    // The facts stay on the page beside it (analysis-timeline.md §3.4) — never hidden behind the
    // recompute notice.
    expect(screen.getByText('GL.TheViper')).toBeInTheDocument()
  })

  it('renders the failed notice with no action, and never the "Match analysis" heading', async () => {
    installFakeApi({ detail: () => jsonResponse(baseDetail({ state: 'failed' })) })
    renderAnalysis()

    expect(await screen.findByText('This match could not be analysed')).toBeInTheDocument()
    expect(screen.queryByText('Match analysis')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('words an exhausted failure by its error class, claiming no parse (T706b)', async () => {
    installFakeApi({
      detail: () => jsonResponse(baseDetail({ state: 'failed', error_class: 'AttemptsExhausted' })),
    })
    renderAnalysis()

    expect(
      await screen.findByText('The analysis was interrupted several times and is not retried.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/could not be parsed/)).not.toBeInTheDocument()
    expect(screen.getByText('Error: AttemptsExhausted')).toBeInTheDocument()
  })

  it('keeps the parse sentence for a failure of any other class (T706b)', async () => {
    installFakeApi({
      detail: () => jsonResponse(baseDetail({ state: 'failed', error_class: 'EngineParseError' })),
    })
    renderAnalysis()

    expect(await screen.findByText('The recorded game could not be parsed.')).toBeInTheDocument()
    expect(screen.getByText('Error: EngineParseError')).toBeInTheDocument()
  })

  it('renders the unavailable notice with no action offered (FR-034)', async () => {
    installFakeApi({ detail: () => jsonResponse(baseDetail({ state: 'unavailable' })) })
    renderAnalysis()

    expect(await screen.findByText('Analysis is not available for this match')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders the refused notice with a retry action', async () => {
    installFakeApi({ detail: () => jsonResponse(baseDetail({ state: 'refused' })) })
    renderAnalysis()

    expect(await screen.findByText('Analysis is temporarily unavailable')).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Try requesting analysis' }),
    ).toBeInTheDocument()
  })

  it('clicking "Request analysis" fires POST /api/analyze and immediately shows progress (FR-035, FR-041)', async () => {
    const fetchMock = installFakeApi({
      detail: () => jsonResponse(baseDetail({ state: 'absent' })),
    })
    renderAnalysis()

    const button = await screen.findByRole('button', { name: 'Request analysis' })
    fireEvent.click(button)

    // The click switches this section straight to `AnalysisProgress`, without waiting on
    // `POST /api/analyze`'s own response (analysis-timeline.md §5).
    expect(await screen.findByText('Analysing this match…')).toBeInTheDocument()
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/analyze',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('clicking Recompute fires the identical POST /api/analyze action (FR-041)', async () => {
    const fetchMock = installFakeApi({
      detail: () =>
        jsonResponse(baseDetail({ state: 'published', stale: true, parser_version: '0.1.0' })),
      document: () => jsonResponse(baseDocument()),
    })
    renderAnalysis()

    const recompute = await screen.findByRole('button', { name: 'Recompute' })
    fireEvent.click(recompute)

    expect(await screen.findByText('Analysing this match…')).toBeInTheDocument()
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/analyze',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('polls GET /api/matches/{game_id} every 5 seconds while running, and stops once published (FR-035)', async () => {
    vi.useFakeTimers()
    try {
      let call = 0
      const fetchMock = installFakeApi({
        detail: () => {
          call += 1
          return call === 1
            ? jsonResponse(baseDetail({ state: 'running' }))
            : jsonResponse(baseDetail({ state: 'published', parser_version: '0.1.21' }))
        },
        document: () => jsonResponse(baseDocument()),
      })
      renderAnalysis()

      await act(async () => {
        await vi.waitFor(() =>
          expect(screen.getByText('Analysing this match…')).toBeInTheDocument(),
        )
      })
      const matchDetailCallsBefore = fetchMock.mock.calls.filter(
        ([input]) => input === '/api/matches/500546441',
      ).length
      expect(matchDetailCallsBefore).toBe(1)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000)
      })

      await vi.waitFor(() => expect(screen.getByText('Match analysis')).toBeInTheDocument())
      const matchDetailCallsAfter = fetchMock.mock.calls.filter(
        ([input]) => input === '/api/matches/500546441',
      ).length
      expect(matchDetailCallsAfter).toBe(2)

      // Once published, the interval stops — a further 10s must not add another request.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000)
      })
      const matchDetailCallsFinal = fetchMock.mock.calls.filter(
        ([input]) => input === '/api/matches/500546441',
      ).length
      expect(matchDetailCallsFinal).toBe(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('sends exactly one POST /api/analyze across several "queued" polls (T706)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = installFakeApi({
        detail: () => jsonResponse(baseDetail({ state: 'queued' })),
      })
      renderAnalysis()

      await act(async () => {
        await vi.waitFor(() => expect(screen.getByText('Waiting to start…')).toBeInTheDocument())
      })
      for (let poll = 0; poll < 3; poll += 1) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(5000)
        })
      }

      const detailCalls = fetchMock.mock.calls.filter(
        ([input]) => input === '/api/matches/500546441',
      ).length
      const postCalls = fetchMock.mock.calls.filter(
        ([input, init]) => input === '/api/analyze' && init?.method === 'POST',
      )
      expect(detailCalls).toBe(4)
      expect(postCalls).toHaveLength(1)
      expect(postCalls[0]?.[1]?.body).toBe(JSON.stringify({ game_id: 500_546_441 }))
    } finally {
      vi.useRealTimers()
    }
  })

  it('sends no POST /api/analyze while the analysis is "running" (T706)', async () => {
    vi.useFakeTimers()
    try {
      const fetchMock = installFakeApi({
        detail: () => jsonResponse(baseDetail({ state: 'running' })),
      })
      renderAnalysis()

      await act(async () => {
        await vi.waitFor(() =>
          expect(screen.getByText('Analysing this match…')).toBeInTheDocument(),
        )
      })
      for (let poll = 0; poll < 3; poll += 1) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(5000)
        })
      }

      expect(fetchMock.mock.calls.filter(([input]) => input === '/api/analyze')).toHaveLength(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not send a second POST for a "queued" poll after the user already requested it (T706)', async () => {
    vi.useFakeTimers()
    try {
      let call = 0
      const fetchMock = installFakeApi({
        detail: () => {
          call += 1
          return jsonResponse(baseDetail({ state: call === 1 ? 'absent' : 'queued' }))
        },
      })
      renderAnalysis()

      await act(async () => {
        await vi.waitFor(() =>
          expect(screen.getByRole('button', { name: 'Request analysis' })).toBeInTheDocument(),
        )
      })
      fireEvent.click(screen.getByRole('button', { name: 'Request analysis' }))
      for (let poll = 0; poll < 3; poll += 1) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(5000)
        })
      }

      expect(fetchMock.mock.calls.filter(([input]) => input === '/api/analyze')).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('stops polling and shows the API message when the automatic POST on "queued" is refused (T706a)', async () => {
    vi.useFakeTimers()
    try {
      const refusal =
        'Analysis is paused while replay capture has unstored recordings inside their deadline window. Try again shortly.'
      const fetchMock = installFakeApi({
        detail: () => jsonResponse(baseDetail({ state: 'queued' })),
        analyze: () =>
          jsonResponse({ error: { code: 'capture_deadline_contention', message: refusal } }, 409),
      })
      renderAnalysis()

      await act(async () => {
        await vi.waitFor(() => expect(screen.getByText('Waiting to start…')).toBeInTheDocument())
      })
      for (let poll = 0; poll < 3; poll += 1) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(5000)
        })
      }

      expect(screen.getByText(refusal)).toBeInTheDocument()

      expect(
        fetchMock.mock.calls.filter(([input]) => input === '/api/matches/500546441'),
      ).toHaveLength(1)
      expect(fetchMock.mock.calls.filter(([input]) => input === '/api/analyze')).toHaveLength(1)
      expect(screen.queryByText('Waiting to start…')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('polls again once a refused-takeover row is read as "running" - another viewer took it over (T706b)', async () => {
    vi.useFakeTimers()
    try {
      const refusal = 'Analysis is paused. Try again shortly.'
      let state = 'queued'
      const fetchMock = installFakeApi({
        detail: () => jsonResponse(baseDetail({ state })),
        analyze: () =>
          jsonResponse({ error: { code: 'capture_deadline_contention', message: refusal } }, 409),
      })
      const detailCalls = () =>
        fetchMock.mock.calls.filter(([input]) => input === '/api/matches/500546441').length
      const { queryClient } = renderAnalysis()

      await act(async () => {
        await vi.waitFor(() => expect(screen.getByText('Waiting to start…')).toBeInTheDocument())
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(15_000)
      })
      expect(screen.getByText(refusal)).toBeInTheDocument()
      expect(detailCalls()).toBe(1)

      // Not a poll: whatever refetches next (a window focus, here an invalidation) finds the row
      // taken over elsewhere.
      state = 'running'
      await act(async () => {
        void queryClient.invalidateQueries({ queryKey: ['matches', 'detail', 500_546_441] })
        await vi.waitFor(() =>
          expect(screen.getByText('Analysing this match…')).toBeInTheDocument(),
        )
      })
      expect(detailCalls()).toBe(2)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000)
      })
      expect(detailCalls()).toBe(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('shows a fixed message when the automatic POST never reaches the server, and "Try again" sends it once more (T706a)', async () => {
    vi.useFakeTimers()
    try {
      let attempts = 0
      const fetchMock = installFakeApi({
        detail: () => jsonResponse(baseDetail({ state: 'queued' })),
        analyze: () => {
          attempts += 1
          if (attempts === 1) {
            throw new TypeError('Failed to fetch')
          }
          return jsonResponse(baseDetail({ state: 'running' }).analysis)
        },
      })
      renderAnalysis()

      await act(async () => {
        await vi.waitFor(() => expect(screen.getByText('Waiting to start…')).toBeInTheDocument())
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(
        screen.getByText("We could not ask for this match's analysis to continue."),
      ).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000)
      })

      expect(fetchMock.mock.calls.filter(([input]) => input === '/api/analyze')).toHaveLength(2)
      expect(
        screen.queryByText("We could not ask for this match's analysis to continue."),
      ).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('renders the load-error callout on a network failure, with a working retry', async () => {
    let attempt = 0
    const fetchMock = installFakeApi({
      detail: () => {
        attempt += 1
        if (attempt === 1) {
          throw new Error('network down')
        }
        return jsonResponse(baseDetail({ state: 'absent' }))
      },
    })
    renderAnalysis()

    expect(
      await screen.findByText("We could not load this match's analysis. Try again."),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('button', { name: 'Request analysis' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
