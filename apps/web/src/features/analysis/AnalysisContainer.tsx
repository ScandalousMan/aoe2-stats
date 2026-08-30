import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { AnalysisTimeline, Button } from 'design-system'
import { isApiErrorCode } from '../../lib/api'
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
// full document `GET /api/matches/{game_id}/analysis` serves (FR-030). Rendered as its own section
// beside `MatchDetailContainer.tsx`'s (`features/replays/`) — a second, independent container on
// the same route, `routes/matches.$gameId.tsx`, the same relationship `ReplayAvailabilityList`
// already has to `MatchDetailPanel` inside that other container, except this one owns its own
// section rather than nesting inside it (`analysis-timeline.md` §1's own note: "wired directly in
// `apps/web/src/features/analysis/`").
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

  // FR-041, `analysis-timeline.md` §5: "does not wait on its own `POST /api/analyze` response...
  // the click fires the request and this component immediately shows `AnalysisProgress`" — this is
  // that immediate, optimistic switch, cleared the moment a real fetch lands after the click
  // (below), whatever state it turns out to carry.
  const [optimisticRunning, setOptimisticRunning] = useState(false)
  const clickedAtRef = useRef<number | null>(null)

  const matchQuery = useQuery({
    ...matchDetailQueryOptions(numericGameId ?? -1),
    refetchInterval: (query) => {
      const state = safeAnalysisState(query.state.data)
      return optimisticRunning || state === 'queued' || state === 'running'
        ? POLL_INTERVAL_MS
        : false
    },
  })

  useEffect(() => {
    if (!optimisticRunning || clickedAtRef.current === null) {
      return
    }
    if (matchQuery.dataUpdatedAt > clickedAtRef.current) {
      setOptimisticRunning(false)
      clickedAtRef.current = null
    }
  }, [optimisticRunning, matchQuery.dataUpdatedAt])

  let summary: ApiAnalysisSummary | undefined
  let summaryShapeError = false
  if (matchQuery.data) {
    try {
      summary = extractAnalysisSummary(matchQuery.data)
    } catch {
      summaryShapeError = true
    }
  }

  const effectiveState: ApiAnalysisSummary['state'] | undefined = optimisticRunning
    ? 'running'
    : summary?.state

  const documentQuery = useQuery({
    ...analysisDocumentQueryOptions(numericGameId ?? -1),
    enabled: numericGameId !== null && effectiveState === 'published',
  })

  function handleRequestAnalysis() {
    if (numericGameId === null) {
      return
    }
    clickedAtRef.current = Date.now()
    setOptimisticRunning(true)
    // Fire-and-forget (this function's own docstring, `api.ts`) — a rejection here (a rate limit,
    // the cap) is read back through the next poll, never through this promise.
    void requestAnalysis(numericGameId).catch(() => {})
  }

  // Mirrors `MatchDetailContainer.tsx`'s own `showReplayAvailability` gate: nothing to analyse for
  // a `gameId` that is not even a number, or a `game_id` this service does not hold at all —
  // `MatchDetailPanel`'s own not-found callout already covers that case in full.
  if (numericGameId === null || isApiErrorCode(matchQuery.error, 'not_found')) {
    return null
  }

  // `analysis-timeline.md` §7: `space-8` between `ReplayAvailabilityList` (above, inside
  // `MatchDetailContainer`) and this section — reapplied here since this section is this route's
  // own sibling, not nested inside that container's already-padded column.
  const sectionClassName = 'mt-8 px-4 pb-8 md:px-6'

  if (matchQuery.isPending) {
    return <AnalysisTimeline loading className={sectionClassName} />
  }

  if (matchQuery.isError || summaryShapeError || !summary) {
    return (
      <AnalysisTimeline
        error
        onRetryLoad={() => void matchQuery.refetch()}
        className={sectionClassName}
      />
    )
  }

  if (effectiveState === 'absent') {
    return (
      <div className={sectionClassName}>
        {/* `analysis-timeline.md` §1: "a plain 'Request analysis' primary `Button`... is not part
         * of this component's anatomy" — `AnalysisTimeline` renders once `state` is anything other
         * than `absent`. */}
        <Button variant="primary" size="lg" onClick={handleRequestAnalysis}>
          Request analysis
        </Button>
      </div>
    )
  }

  if (effectiveState === 'published') {
    if (documentQuery.isPending) {
      return <AnalysisTimeline loading className={sectionClassName} />
    }
    if (documentQuery.isError) {
      return (
        <AnalysisTimeline
          error
          onRetryLoad={() => void documentQuery.refetch()}
          className={sectionClassName}
        />
      )
    }
    return (
      <AnalysisTimeline
        state="published"
        stale={summary.stale}
        engineName={documentQuery.data.engine.name}
        engineVersion={documentQuery.data.engine.version}
        analysedAtLabel={formatPlayedAtAbsolute(documentQuery.data.extracted_at)}
        teams={toAnalysisTeamGroups(documentQuery.data, matchQuery.data.participants)}
        // FR-041: offered only while `stale` — `AnalysisTimeline` itself already renders
        // `StaleRecomputeNotice` exactly when `stale` is true and never otherwise, so this handler
        // is passed unconditionally and simply goes unused when `stale` is `false`.
        onRequestAnalysis={handleRequestAnalysis}
        className={sectionClassName}
      />
    )
  }

  // `queued` | `running` | `failed` | `unavailable` | `refused` — `AnalysisTimeline`'s remaining
  // five states. `onRequestAnalysis` is read only by `refused` (`analysis-timeline.md` §3.5); the
  // other four render no button, so passing it unconditionally is exactly as inert as it is above.
  return (
    <AnalysisTimeline
      state={effectiveState}
      onRequestAnalysis={handleRequestAnalysis}
      className={sectionClassName}
    />
  )
}
