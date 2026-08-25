import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import { SearchBox } from 'design-system'
import type { SearchBoxState } from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { searchPlayers } from './api'
import { toPlayerSearchResults } from './mappers'

// Wires `SearchBox` (packages/design-system) to `GET /api/players/search` (T319), the same
// discipline `DashboardContainer.tsx` and `MatchHistoryContainer.tsx` established: every visual
// state lives in the component, this module owns the data and the handlers. `SearchBox` itself
// never fetches (its own module docstring) — it dispatches one `onSearch` per settled, non-empty
// query and this container turns the outcome into its `state` prop.

const DEFAULT_RETRY_AFTER_SECONDS = 60

export function SearchContainer() {
  const navigate = useNavigate()
  const meQuery = useQuery(meQueryOptions)
  const session = meQuery.data

  // Mirrors `DashboardContainer.tsx`'s own effect: a cookie can expire while this page is already
  // open, so a live session check runs here too, not only the route's `beforeLoad` gate.
  useEffect(() => {
    if (session && !session.authenticated) {
      void navigate({ to: '/sign-in' })
    }
  }, [session, navigate])

  const [value, setValue] = useState('')
  const [state, setState] = useState<SearchBoxState>({ status: 'idle' })

  // The query a response answers, and a monotonic guard against an earlier, slower request's
  // response landing after a later one's — a response only applies if it is still current.
  const lastQueryRef = useRef('')
  const requestIdRef = useRef(0)

  const runSearch = useCallback(
    async (query: string) => {
      lastQueryRef.current = query
      const requestId = ++requestIdRef.current
      setState({ status: 'loading' })
      try {
        const response = await searchPlayers(query)
        if (requestIdRef.current !== requestId) return
        setState({
          status: 'answered',
          query,
          results: toPlayerSearchResults(response.results),
          degraded: response.degraded,
        })
      } catch (error) {
        if (requestIdRef.current !== requestId) return
        if (isApiErrorCode(error, 'not_authenticated')) {
          void navigate({ to: '/sign-in' })
          return
        }
        if (isApiErrorCode(error, 'rate_limited')) {
          const detail = error.detail as { retry_after?: number } | undefined
          setState({
            status: 'rate-limited',
            retryAfterSeconds: detail?.retry_after ?? DEFAULT_RETRY_AFTER_SECONDS,
          })
          return
        }
        setState({ status: 'failed' })
      }
    },
    [navigate],
  )

  return (
    <main className="min-h-svh bg-background px-4 py-6 md:px-6">
      <div className="mx-auto max-w-2xl">
        <SearchBox
          value={value}
          onValueChange={setValue}
          onSearch={(query) => void runSearch(query)}
          state={state}
          onRetry={() => void runSearch(lastQueryRef.current)}
          // T388: `PlayerResultRow` renders a real `<a href>` so it degrades gracefully, but a
          // plain click routes through here instead of forcing a full document reload — the same
          // discipline every other navigation in this container already follows.
          onNavigate={(href) => void navigate({ to: href })}
        />
      </div>
    </main>
  )
}
