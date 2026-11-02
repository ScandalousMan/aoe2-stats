import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { AnalysisTimeline, Button, Callout } from 'design-system'
import { ApiRequestError, isApiErrorCode } from '../../lib/api'
import { matchDetailQueryOptions } from '../matches/api'
import { formatPlayedAtAbsolute } from '../matches/format'
import { parseGameId } from '../replays/gameId'
import {
  analysisDocumentQueryOptions,
  extractAnalysisSummary,
  requestAnalysis,
  type ApiAnalysisSummary,
} from './api'
import { toAnalysisTeamGroups } from './mappers'

// T372, US4: wires `AnalysisTimeline` (packages/design-system) onto the match page, from the
// `analysis` object `GET /api/matches/{game_id}` already carries (T368) and, once `published`, the
// full document `GET /api/matches/{game_id}/analysis` serves (FR-030). Rendered as its own section,
// mounted by `routes/matches.$gameId.tsx` as `MatchDetailContainer.tsx`'s (`features/replays/`)
// trailing child (T558) rather than as a route-level sibling — the two share exactly one `Page`,
// one main landmark and one width/padding/rhythm, none of which this component declares itself
// (`analysis-timeline.md` §1's own note: "wired directly in `apps/web/src/features/analysis/`").
// It stays a second, independent container rather than a component `MatchDetailContainer` imports
// directly, for the reason the next paragraph gives.
//
// `matchDetailQueryOptions` (`features/matches/api.ts`) is imported, not restated: this container
// shares that exact query key with `MatchDetailContainer`, so the two ever issue one request for
// `GET /api/matches/{game_id}`, not two — `api.ts`'s own module docstring explains why the
// `analysis` object itself is still read and validated independently here rather than through
// `ApiMatchDetail`, which does not declare that field.

/** `analysis-timeline.md` §5: "this component polls `GET /api/matches/{game_id}` every 5 seconds"
 * while `state` is `queued` or `running` — the concrete mechanism behind FR-035's "let the user
 * leave and come back": leaving means navigating away and returning to find the right state
 * already showing, not necessarily watching this page the whole time. */
const POLL_INTERVAL_MS = 5000

export interface AnalysisContainerProps {
  gameId: string
}

/** What the page says when the automatic `POST /api/analyze` on a `queued` analysis is refused. */
const TAKEOVER_FALLBACK_MESSAGE = "We could not ask for this match's analysis to continue."

/** The API's own sentence for a refusal it authored (an admission gate, a sign-in), which is
 * written for the person reading it; a request that never reached the server, or an answer with no
 * envelope, has no sentence worth showing and gets the fixed one. */
function takeoverRefusalMessage(error: unknown): string {
  if (
    error instanceof ApiRequestError &&
    error.code !== 'network_error' &&
    error.code !== 'unknown_error'
  ) {
    return error.message
  }
  return TAKEOVER_FALLBACK_MESSAGE
}

/** Safely reads `extractAnalysisSummary` off a `query.state.data` value inside `refetchInterval`
 * (called by `@tanstack/react-query` outside this component's own render, on data it has not
 * necessarily validated yet) — `undefined` for anything that is not yet a valid summary, which
 * reads as "not polling" below rather than throwing out of the query's own internal scheduler. */
function safeAnalysisState(data: unknown): ApiAnalysisSummary['state'] | undefined {
  if (!data) {
    return undefined
  }
  try {
    return extractAnalysisSummary(data).state
  } catch {
    return undefined
  }
}

export function AnalysisContainer({ gameId }: AnalysisContainerProps) {
  const numericGameId = parseGameId(gameId)

  // FR-041, `analysis-timeline.md` §5: a click shows `AnalysisProgress` at once, and what the
  // match reads is trusted only after the click's own `POST /api/analyze` settles (T831). The server
  // claims the row some seconds into the request, so a poll that reads `absent` before then says
  // nothing. Keyed to the match so a settle after a navigation to another cannot touch it.
  const queryClient = useQueryClient()
  // T832: `from` is the state the click came from. A click from `absent` pins `running` (progress);
  // Recompute (`published`) and the refused retry keep their own frame and show `requesting`.
  const [pendingRequest, setPendingRequest] = useState<{
    gameId: number
    from: 'absent' | 'published' | 'refused'
  } | null>(null)
  const activeRequest = pendingRequest?.gameId === numericGameId ? pendingRequest : null
  const optimisticRunning = activeRequest !== null

  // T706a: set when the page's automatic `POST /api/analyze` on a `queued` analysis is refused
  // (an admission gate's 409, a 401, a network failure). A refused request takes nothing over, so
  // the row is still `queued` as far as this page can tell and polling on would show "Waiting to
  // start" for as long as the tab is open: while the state is `queued`, polling stops and the
  // refusal is shown instead. That is all the refusal holds back (T706b): the row can leave
  // `queued` without this page's help - another viewer takes it over, or a refetch (a window
  // focus) reads it differently - and from then on the state is polled as usual. The refusal stays
  // recorded, and is shown again if the row returns to `queued`, because this page view sends no
  // second automatic request. Keyed to the match so it cannot outlive a navigation to another.
  const [takeoverRefusal, setTakeoverRefusal] = useState<{
    gameId: number
    message: string
  } | null>(null)
  const refusedTakeover = takeoverRefusal?.gameId === numericGameId ? takeoverRefusal : null

  const matchQuery = useQuery({
    ...matchDetailQueryOptions(numericGameId ?? -1),
    refetchInterval: (query) => {
      const state = safeAnalysisState(query.state.data)
      // Stops only for the state the refusal is about (`queued`): a row that has since become
      // `running` (taken over elsewhere) or anything else is polled by the rules below.
      if (refusedTakeover && state === 'queued') {
        return false
      }
      return optimisticRunning || state === 'queued' || state === 'running'
        ? POLL_INTERVAL_MS
        : false
    },
  })

  let summary: ApiAnalysisSummary | undefined
  let summaryShapeError = false
  if (matchQuery.data) {
    try {
      summary = extractAnalysisSummary(matchQuery.data)
    } catch {
      summaryShapeError = true
    }
  }

  const effectiveState: ApiAnalysisSummary['state'] | undefined = activeRequest
    ? activeRequest.from === 'absent'
      ? 'running'
      : activeRequest.from
    : summary?.state

  // T706: a `queued` analysis is one nobody holds - the server serves a `running` row whose lease
  // expired as `queued` - and nothing else will take it, so the page asks once. One `POST
  // /api/analyze` per page view and per match, never one per poll, and never while `running`
  // (a live lease is held by someone else). The same ref records the click's own POST, so a poll
  // that still reads `queued` while that request is in flight does not send a second one. A
  // rejection is not read back through the polls - a refused request changes nothing on the row,
  // so a poll cannot tell - so it is kept and shown while the row reads `queued`, polling stops
  // there, and only the person's "Try again" sends it again.
  const requestedForGameIdRef = useRef<number | null>(null)
  const serverState = summary?.state

  const takeOver = useCallback((gameIdToTake: number) => {
    void requestAnalysis(gameIdToTake).catch((error: unknown) => {
      setTakeoverRefusal({ gameId: gameIdToTake, message: takeoverRefusalMessage(error) })
    })
  }, [])

  useEffect(() => {
    if (numericGameId === null || serverState !== 'queued') {
      return
    }
    if (requestedForGameIdRef.current === numericGameId) {
      return
    }
    requestedForGameIdRef.current = numericGameId
    takeOver(numericGameId)
  }, [numericGameId, serverState, takeOver])

  const documentQuery = useQuery({
    ...analysisDocumentQueryOptions(numericGameId ?? -1),
    enabled: numericGameId !== null && effectiveState === 'published',
  })

  function handleRequestAnalysis() {
    if (numericGameId === null) {
      return
    }
    const from =
      summary?.state === 'published' || summary?.state === 'refused' ? summary.state : 'absent'
    const requestedGameId = numericGameId
    requestedForGameIdRef.current = requestedGameId
    setPendingRequest({ gameId: requestedGameId, from })
    // Settled either way (a rejection, such as a rate limit or the cap, is not shown): the match is
    // read once, and progress ends only when that read has answered, so the cached pre-claim read
    // is never shown in between.
    void requestAnalysis(requestedGameId)
      .catch(() => {})
      .then(() =>
        // The document's key extends the match's, so this refetch also fetches a Recompute's new
        // document (T832) before the pinned frame is released.
        queryClient.refetchQueries({
          queryKey: matchDetailQueryOptions(requestedGameId).queryKey,
        }),
      )
      .catch(() => {})
      .finally(() => {
        setPendingRequest((current) => (current?.gameId === requestedGameId ? null : current))
      })
  }

  // Mirrors `MatchDetailContainer.tsx`'s own `showReplayAvailability` gate: nothing to analyse for
  // a `gameId` that is not even a number, or a `game_id` this service does not hold at all —
  // `MatchDetailPanel`'s own not-found callout already covers that case in full.
  if (numericGameId === null || isApiErrorCode(matchQuery.error, 'not_found')) {
    return null
  }

  // `analysis-timeline.md` §7's `space-8` between `ReplayAvailabilityList` and this section is no
  // longer this container's to express: `matches.$gameId.tsx` renders this component as a child of
  // `MatchDetailContainer`'s own `Page` (T558) rather than as a route-level sibling next to it, so
  // the between-sections rhythm and the page's width and padding all come from that one `Page`
  // (FR-021) — this container writes no layout class of its own.

  if (matchQuery.isPending) {
    return <AnalysisTimeline loading />
  }

  if (matchQuery.isError || summaryShapeError || !summary) {
    return <AnalysisTimeline error onRetryLoad={() => void matchQuery.refetch()} />
  }

  if (refusedTakeover && effectiveState === 'queued') {
    // No new design-system state: the refusal is the API's own sentence in a `Callout`, with the
    // same "Try again" the load-error variant of `AnalysisTimeline` offers (T706a).
    return (
      <Callout
        tone="warning"
        headingLevel={3}
        heading={refusedTakeover.message}
        actions={
          <Button
            variant="primary"
            size="lg"
            onClick={() => {
              setTakeoverRefusal(null)
              takeOver(refusedTakeover.gameId)
            }}
          >
            Try again
          </Button>
        }
      />
    )
  }

  if (effectiveState === 'absent') {
    // `analysis-timeline.md` §1: "a plain 'Request analysis' primary `Button`... is not part of
    // this component's anatomy" — `AnalysisTimeline` renders once `state` is anything other than
    // `absent`. Rendered bare: `Page`'s own children column already spaces this from its
    // neighbours (T558).
    return (
      <Button variant="primary" size="lg" onClick={handleRequestAnalysis}>
        Request analysis
      </Button>
    )
  }

  if (effectiveState === 'published') {
    if (documentQuery.isPending) {
      return <AnalysisTimeline loading />
    }
    if (documentQuery.isError) {
      return <AnalysisTimeline error onRetryLoad={() => void documentQuery.refetch()} />
    }
    return (
      <AnalysisTimeline
        state="published"
        // A pinned Recompute keeps its notice (and loading button) even if a read says otherwise.
        stale={activeRequest ? true : summary.stale}
        requesting={activeRequest !== null}
        engineName={documentQuery.data.engine.name}
        engineVersion={documentQuery.data.engine.version}
        analysedAtLabel={formatPlayedAtAbsolute(documentQuery.data.extracted_at)}
        teams={toAnalysisTeamGroups(documentQuery.data, matchQuery.data.participants)}
        // FR-041: offered only while `stale` — `AnalysisTimeline` itself already renders
        // `StaleRecomputeNotice` exactly when `stale` is true and never otherwise, so this handler
        // is passed unconditionally and simply goes unused when `stale` is `false`.
        onRequestAnalysis={handleRequestAnalysis}
      />
    )
  }

  // `queued` | `running` | `failed` | `unavailable` | `refused` — `AnalysisTimeline`'s remaining
  // five states. `onRequestAnalysis` is read only by `refused` (`analysis-timeline.md` §3.5); the
  // other four render no button, so passing it unconditionally is exactly as inert as it is above.
  // `errorClass` is read only by `failed` (`analysis-timeline.md` §3.5), where it words the notice
  // and is shown; the server sends `null` in every other state, so it is passed through as it is.
  return (
    <AnalysisTimeline
      state={effectiveState}
      errorClass={summary.error_class ?? undefined}
      requesting={activeRequest !== null}
      onRequestAnalysis={handleRequestAnalysis}
    />
  )
}
