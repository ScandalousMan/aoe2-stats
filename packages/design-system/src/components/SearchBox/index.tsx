import { useEffect, useId, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { PlayerResultRow } from '../PlayerResultRow'
import type { PlayerSearchResultData } from '../PlayerResultRow'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/player-search.md

/** The six states `ResultsRegion` renders — exactly one at a time, never combined (§5).
 * `'answered'` further branches into found / not-found / degraded from `results` and `degraded`
 * themselves, the same three-way split the API response carries (contracts/http-api.md), so the
 * component never has to invent a fourth flag the response does not send. */
export type SearchBoxState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'answered'; query: string; results: PlayerSearchResultData[]; degraded: boolean }
  | { status: 'rate-limited'; retryAfterSeconds: number }
  | { status: 'failed' }

export interface SearchBoxProps {
  /** The live, controlled query text (§2) — updated on every keystroke via `onValueChange`,
   * independent of `state.query`, which is the query the current `state` actually answers. */
  value: string
  onValueChange: (value: string) => void
  /** Fired `debounceMs` after the last keystroke with the trimmed, non-empty value. The caller
   * owns fetching and reports the outcome back through `state` — this component never fetches. */
  onSearch: (value: string) => void
  /** Not a token (§6): interaction-timing default, not a CSS duration. */
  debounceMs?: number
  state: SearchBoxState
  /** Only called from the `failed` state's "Try again" action (§5). The `rate-limited` state needs
   * no retry callback: `Input` re-enables itself the instant the countdown reaches zero. */
  onRetry?: () => void
  label?: string
  className?: string
}

const inputFocusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring'

const DEFAULT_DEBOUNCE_MS = 300
// §5 "loading": never fewer skeleton rows than the previous result count already on screen.
const MIN_SKELETON_ROWS = 5

/** Lets a player be found by a partial, wrongly-cased name without ever knowing a numeric
 * identifier (FR-001), while never presenting a reduced answer as a complete one (FR-003). Purely
 * presentational: fetching, debouncing the actual request beyond the keystroke-to-dispatch delay
 * below, and computing `state` from a response are the caller's job (T322). */
export function SearchBox({
  value,
  onValueChange,
  onSearch,
  debounceMs = DEFAULT_DEBOUNCE_MS,
  state,
  onRetry,
  label = 'Search a player',
  className,
}: SearchBoxProps) {
  const inputId = useId()
  const rateLimitId = useId()

  const lastResultCount = useRef(MIN_SKELETON_ROWS)
  if (state.status === 'answered') {
    lastResultCount.current = Math.max(MIN_SKELETON_ROWS, state.results.length)
  }

  // The caller (T322) cannot hand this a stable `onSearch`: it calls `setState` the instant the
  // callback fires, which re-renders the caller and mints a fresh closure every time. Reading
  // `onSearch` through a ref, updated every render but never listed as a dependency, means the
  // debounce effect below only reruns when `value` or `debounceMs` actually change — not on every
  // render `onSearch` itself provokes. Depending on `onSearch`'s identity instead re-arms the timer
  // on each of those renders and redispatches the same, already-settled query forever: an
  // unbounded request loop the client would run against itself, exactly what FR-005's rate limiter
  // exists to stop from the outside (regression, see SearchBox.test.tsx).
  const onSearchRef = useRef(onSearch)
  onSearchRef.current = onSearch

  // Debounce: dispatch `onSearch` once typing has settled. A blank query is never dispatched —
  // clearing the box is not a search, and `idle`'s own definition ("no query has been submitted
  // yet") would otherwise be unreachable once the user has typed anything at all.
  useEffect(() => {
    const trimmed = value.trim()
    if (trimmed === '') return
    const timer = window.setTimeout(() => onSearchRef.current(trimmed), debounceMs)
    return () => window.clearTimeout(timer)
  }, [value, debounceMs])

  // The countdown recomputes once per second (§5) — coarser granularity is unreadable for a
  // `retry_after` of a few seconds.
  const retryAfterSeconds = state.status === 'rate-limited' ? state.retryAfterSeconds : undefined
  const [secondsLeft, setSecondsLeft] = useState(retryAfterSeconds ?? 0)

  useEffect(() => {
    if (retryAfterSeconds === undefined) return
    setSecondsLeft(retryAfterSeconds)
  }, [retryAfterSeconds])

  useEffect(() => {
    if (state.status !== 'rate-limited') return
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => Math.max(0, current - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [state.status])

  // `Input` re-enables itself the instant the countdown reaches zero — no manual retry needed,
  // because the block was never the user's mistake to correct (§5).
  const rateLimited = state.status === 'rate-limited' && secondsLeft > 0

  return (
    <div className={cx('flex w-full flex-col', className)}>
      <div className="flex flex-col gap-1">
        <label htmlFor={inputId} className="font-sans text-sm text-text-secondary">
          {label}
        </label>
        <input
          id={inputId}
          type="search"
          value={value}
          disabled={rateLimited}
          aria-describedby={rateLimited ? rateLimitId : undefined}
          onChange={(event) => onValueChange(event.target.value)}
          className={cx(
            'h-10 w-full rounded-md border border-border bg-surface px-4 font-sans text-md text-text-primary',
            'transition-colors duration-120 ease-standard',
            'hover:border-border-strong focus-visible:border-border-strong',
            'disabled:cursor-default disabled:border-border disabled:bg-surface-sunken disabled:text-text-disabled',
            inputFocusRing,
          )}
        />
      </div>
      <div
        role="region"
        aria-live="polite"
        aria-label="Search results"
        aria-busy={state.status === 'loading' || undefined}
        className="mt-4"
      >
        <ResultsRegionContent
          state={state}
          secondsLeft={secondsLeft}
          rateLimitId={rateLimitId}
          skeletonRows={lastResultCount.current}
          onRetry={onRetry}
        />
      </div>
    </div>
  )
}

function ResultsRegionContent({
  state,
  secondsLeft,
  rateLimitId,
  skeletonRows,
  onRetry,
}: {
  state: SearchBoxState
  secondsLeft: number
  rateLimitId: string
  skeletonRows: number
  onRetry?: () => void
}) {
  switch (state.status) {
    // Deliberately not a `Callout`: idle is not an outcome (§5). Wrapping the very first thing a
    // user sees in a bordered, tone-striped region would make it look like something went wrong
    // before they have done anything.
    case 'idle':
      return <p className="font-sans text-sm text-text-secondary">Search for a player by name.</p>

    case 'loading':
      return (
        <ul className="flex flex-col gap-3">
          {Array.from({ length: skeletonRows }, (_, index) => (
            <li key={index}>
              <Skeleton
                variant="block"
                className="h-20 w-full rounded-lg md:h-12 md:rounded-none"
              />
            </li>
          ))}
        </ul>
      )

    case 'rate-limited':
      return (
        <div id={rateLimitId}>
          <Callout
            tone="warning"
            heading={`You're searching too quickly. Try again in ${secondsLeft}s.`}
          />
        </div>
      )

    case 'failed':
      return (
        <Callout
          tone="danger"
          heading="We could not search right now."
          actions={
            onRetry && (
              <Button variant="primary" size="lg" onClick={onRetry}>
                Try again
              </Button>
            )
          }
        />
      )

    case 'answered': {
      const { query, results, degraded } = state

      // empty 1 of 3 — found nothing, not degraded. `info`: nothing went wrong, exactly the claim
      // FR-003 needs distinguished from `failed` above.
      if (!degraded && results.length === 0) {
        return (
          <Callout tone="info" heading={`No player matches “${query}”.`}>
            Check the spelling, or try a shorter part of the name.
          </Callout>
        )
      }

      return (
        <div className="flex flex-col gap-3">
          {degraded && (
            // empty 2 of 3 (when results is also empty) — one banner, worded for the case it is
            // in, rather than a second stacked `Callout` answering the same request (§5).
            <Callout tone="warning" heading="Player search is temporarily degraded.">
              <p>These results are limited to players already known to this service.</p>
              {results.length === 0 && (
                <p>{`No locally known player matches “${query}” either.`}</p>
              )}
            </Callout>
          )}
          {results.length > 0 && (
            <ul className="flex flex-col gap-3">
              {results.map((result) => (
                <li key={result.profileId}>
                  <PlayerResultRow result={result} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )
    }
  }
}
