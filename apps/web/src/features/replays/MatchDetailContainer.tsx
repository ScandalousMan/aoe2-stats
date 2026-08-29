import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import {
  Button,
  Callout,
  MatchDetailPanel,
  ProfileSummary,
  ReplayAvailabilityList,
} from 'design-system'
import type {
  DownloadActionState,
  MatchDetailStatus,
  ProfileSummaryStatus,
  ReplayDownloadState,
} from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { matchDetailQueryOptions } from '../matches/api'
import { toMatchDetailData } from '../matches/mappers'
import { profilesQueryOptions, setPrimaryProfile } from '../profile/api'
import { formatFreshness } from '../profile/format'
import {
  latestCapturedAt,
  toLinkedProfileOptions,
  toRatingEntries,
  toViewedProfile,
} from '../profile/mappers'
import { triggerReplayDownload, triggerReplayPointOfViewDownload } from './api'
import { toReplayAvailabilityRows } from './availability'
import { parseGameId } from './gameId'

// Wires `MatchDetailPanel` and `ProfileSummary/compact` (packages/design-system) to this
// feature's real effects, the same discipline `MatchHistoryContainer.tsx` (T075) established for
// the match list — deliberately its own, near-identical header wiring rather than a shared hook:
// `DashboardContainer.tsx` and `MatchHistoryContainer.tsx` already each own their copy of this
// same composition instead of extracting one, and a third copy here follows that precedent rather
// than inventing a new shared module for it.
//
// match-history.md §1's dependency note: "the page header above both routes is a `ProfileSummary`
// `compact` variant" — this route's data does not depend on *which* profile is viewed (`GET
// /api/matches/{game_id}` is reachable through any of the caller's own linked profiles at once,
// FR-043), only the header's own ratings display does, exactly as it does not on the list route
// either.

export interface MatchDetailContainerProps {
  gameId: string
}

export function MatchDetailContainer({ gameId }: MatchDetailContainerProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const meQuery = useQuery(meQueryOptions)
  const profilesQuery = useQuery(profilesQueryOptions)
  const session = meQuery.data

  // Mirrors `MatchHistoryContainer.tsx`'s own effect: a cookie can expire while this page is
  // already open, so every query below also watches for `not_authenticated` and lands here too.
  useEffect(() => {
    if (session && !session.authenticated) {
      void navigate({ to: '/sign-in' })
    }
  }, [session, navigate])

  function redirectIfSessionExpired(error: unknown): boolean {
    if (isApiErrorCode(error, 'not_authenticated')) {
      void navigate({ to: '/sign-in' })
      return true
    }
    return false
  }

  const authenticated = session?.authenticated ?? false
  const profiles = profilesQuery.data?.profiles ?? []

  // FR-043: "viewing" is a session-level selection that writes nothing — same rule
  // `MatchHistoryContainer.tsx` follows. It only changes the header's own ratings, never which
  // match this route shows.
  const [viewedProfileId, setViewedProfileId] = useState<number | null>(null)
  const primaryProfile = profiles.find((profile) => profile.is_primary)
  const viewedProfile =
    profiles.find((profile) => profile.profile_id === viewedProfileId) ?? primaryProfile

  const [primaryChangeInFlight, setPrimaryChangeInFlight] = useState(false)
  const [makePrimaryError, setMakePrimaryError] = useState<string | null>(null)

  async function handleMakePrimary(id: string) {
    const profileId = Number(id)
    setPrimaryChangeInFlight(true)
    setMakePrimaryError(null)
    try {
      await setPrimaryProfile(profileId)
      setViewedProfileId(profileId)
      await queryClient.invalidateQueries({ queryKey: profilesQueryOptions.queryKey })
      void queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
    } catch (error) {
      if (!redirectIfSessionExpired(error)) {
        setMakePrimaryError('We could not change your primary profile. Try again.')
      }
    } finally {
      setPrimaryChangeInFlight(false)
    }
  }

  // --- ProfileSummary status (profile-summary.md §5), identical derivation to
  // `MatchHistoryContainer.tsx` / `DashboardContainer.tsx` -----------------------------------------

  const profilesLoading = profilesQuery.isPending
  const profilesHaveData = profilesQuery.data !== undefined
  let profileSummaryStatus: ProfileSummaryStatus = 'default'
  if (profilesLoading) {
    profileSummaryStatus = 'loading'
  } else if (profilesQuery.isError) {
    profileSummaryStatus = profilesHaveData ? 'stale' : 'error'
  } else if (viewedProfile && viewedProfile.ratings.length === 0) {
    profileSummaryStatus = 'empty'
  }

  const showEmptyAccount = !profilesLoading && !profilesQuery.isError && profiles.length === 0

  // --- Match detail (FR-011) -----------------------------------------------------------------

  const numericGameId = parseGameId(gameId)
  const matchQuery = useQuery(matchDetailQueryOptions(numericGameId ?? -1))

  useEffect(() => {
    if (isApiErrorCode(matchQuery.error, 'not_authenticated')) {
      void navigate({ to: '/sign-in' })
    }
  }, [matchQuery.error, navigate])

  let matchStatus: MatchDetailStatus = 'default'
  if (numericGameId === null || isApiErrorCode(matchQuery.error, 'not_found')) {
    // A `gameId` that is not even a number and one the API answers `not_found` for reach the
    // identical panel state — FR-045's "no field distinguishes the two causes" (match-history.md
    // §5's own empty-state bullet), never a different message for being caught locally.
    matchStatus = 'not-found'
  } else if (matchQuery.isPending) {
    matchStatus = 'loading'
  } else if (matchQuery.isError) {
    matchStatus = 'error'
  }

  const matchDetail = matchQuery.data ? toMatchDetailData(matchQuery.data) : undefined

  // --- Replay download (FR-028) ---------------------------------------------------------------
  //
  // `MatchDetailPanel` renders `DownloadAction` exactly when `matchDetail.captureStatus ===
  // 'stored'` (T070e: `toMatchDetailData` now carries the real value off the wire).
  const [downloadState, setDownloadState] = useState<DownloadActionState>('idle')
  const downloadResetTimeout = useRef<number | undefined>(undefined)

  useEffect(() => {
    return () => {
      if (downloadResetTimeout.current !== undefined) {
        window.clearTimeout(downloadResetTimeout.current)
      }
    }
  }, [])

  function handleDownload() {
    if (numericGameId === null) {
      return
    }
    setDownloadState('loading')
    triggerReplayDownload(numericGameId)
    // `api.ts`'s own note: a full-page navigation gives no completion signal to observe, so the
    // button returns to `idle` after a short window rather than staying in `loading` forever —
    // `shared-primitives.md`'s own "the button returns to default and to being pressable" rule,
    // applied to the one path here that cannot detect success or failure directly.
    downloadResetTimeout.current = window.setTimeout(() => setDownloadState('idle'), 1500)
  }

  // --- Recorded games, per point of view (T338, T341, FR-023..FR-029) ------------------------
  //
  // A second, separate download surface from `handleDownload` above: that one is the caller's
  // *own* one-click shortcut (`MatchDetailPanel`'s header `DownloadAction`, unchanged by this
  // task); this is `ReplayAvailabilityList`'s per-participant row, offering every point of view
  // this match carries, one per row (FR-023) — including a third party's, and including the
  // caller's own again when it renders `archived` (replay-availability.md §3.3).
  const rawParticipants = matchQuery.data?.participants ?? []
  const [pointOfViewDownloadStates, setPointOfViewDownloadStates] = useState<
    Record<string, ReplayDownloadState>
  >({})
  // One reset timeout per row, keyed the same way the state map above is — a second click on a
  // different row must not cancel the first row's own reset (`downloadResetTimeout` above only
  // ever needs one, since `MatchDetailPanel` offers exactly one `DownloadAction`).
  const pointOfViewResetTimeouts = useRef<Map<string, number>>(new Map())

  useEffect(() => {
    const timeouts = pointOfViewResetTimeouts.current
    return () => {
      timeouts.forEach((timeoutId) => window.clearTimeout(timeoutId))
    }
  }, [])

  function handlePointOfViewDownload(rowId: string) {
    const participant = rawParticipants.find((row) => String(row.profile_id) === rowId)
    const downloadPath = participant?.replay.download_path
    // `download_path` is `null` for `expired`/`never_recorded` (FR-025's whole point: an
    // unobtainable download must not be renderable as a button that then fails) —
    // `ReplayAvailabilityList` never offers `DownloadAction` for either state, so this only
    // guards against a row this component does not itself know about.
    if (!downloadPath) {
      return
    }
    setPointOfViewDownloadStates((previous) => ({ ...previous, [rowId]: 'loading' }))
    triggerReplayPointOfViewDownload(downloadPath)
    const existingTimeout = pointOfViewResetTimeouts.current.get(rowId)
    if (existingTimeout !== undefined) {
      window.clearTimeout(existingTimeout)
    }
    // Mirrors `handleDownload`'s own note: a same-tab navigation carries no completion signal
    // (`api.ts`'s `triggerReplayPointOfViewDownload`), so this row returns to `idle` after the
    // same short window `handleDownload` already uses, rather than staying `loading` forever.
    //
    // replay-availability.md §5's "boundary race" (`code: "expired_since_page_load"`) and §10's
    // "a real `<button>` triggering a same-tab navigation... no failure is script-observable" are
    // in tension: a navigation carries no response this component can read, so it cannot render
    // the in-place transition §5 describes from a fetch it never makes. The resolution is
    // `contracts/http-api.md`'s own sentence on that race: the download route "also records the
    // outcome, so the page is right the next time" — `T337`'s `replay_fetch_misses` write,
    // `derive_availability`'s read of it. Refetching `GET /api/matches/{game_id}` after a click
    // makes this page *be* "the next time": a row that just 404'd server-side comes back
    // `never_recorded` with `download_path: null` (FR-025), and `ReplayAvailabilityList`
    // re-renders it with no `DownloadAction` — self-correcting without ever needing to observe
    // the download response directly.
    //
    // Fired from this same 1500ms timeout, not synchronously with the click: a refetch issued the
    // instant the navigation starts would race the download route's own write of
    // `replay_fetch_misses`, which only happens server-side inside *that* request's handler —
    // two independent requests starting together have no ordering guarantee between them. This
    // timeout already exists to give the browser's own unobservable navigation attempt time to
    // resolve before resetting the button's `loading` state (the note above); reusing that same
    // window for the refetch, rather than inventing a second arbitrary delay, means the refetch
    // fires only once the download request has had the same amount of time to complete server-side
    // as the UI already assumes it needs. A successful download refetches identical state — one
    // extra `GET /api/matches/{game_id}`, not a call to the download route itself, so it never
    // consumes a `replay_download` rate-limit unit (FR-028) — which is an acceptable, deliberate
    // cost for the case this exists to correct.
    const timeoutId = window.setTimeout(() => {
      setPointOfViewDownloadStates((previous) => ({ ...previous, [rowId]: 'idle' }))
      pointOfViewResetTimeouts.current.delete(rowId)
      void matchQuery.refetch()
    }, 1500)
    pointOfViewResetTimeouts.current.set(rowId, timeoutId)
  }

  // Rendered while loading (the skeleton) and once data has arrived — never for `not-found` or
  // `error`, the two `matchStatus` values `MatchDetailPanel` itself already turns into its own
  // single unified message; there is no match to offer recordings for in either case.
  const showReplayAvailability = matchStatus === 'loading' || matchStatus === 'default'

  return (
    <main className="min-h-svh bg-background">
      {/* T327/T331: `GET /api/matches/{game_id}` carries no ownership scope any more — a caller
       * with no linked Steam profile at all can still open any match this service holds
       * (spec.md §11.4: "a match page with no consenting participant still renders in full"), so
       * this banner is informational only and never replaces `MatchDetailPanel` below it, unlike
       * `MatchHistoryContainer.tsx`'s identical-looking gate for the caller's *own* history, which
       * has nothing to show without a linked profile. */}
      {showEmptyAccount ? (
        <div className="px-4 py-6 md:px-6">
          <Callout
            tone="info"
            heading="No Steam account is linked yet"
            actions={
              <Button
                variant="primary"
                onClick={() => void navigate({ to: '/sign-in', search: { link: true } })}
              >
                Link a Steam account
              </Button>
            }
          >
            Link a Steam account to see your own replay archive on the matches you play.
          </Callout>
        </div>
      ) : (
        <>
          <ProfileSummary
            variant="compact"
            authenticated={authenticated}
            viewedProfile={viewedProfile ? toViewedProfile(viewedProfile) : undefined}
            linkedProfiles={toLinkedProfileOptions(profiles)}
            entries={viewedProfile ? toRatingEntries(viewedProfile) : []}
            status={profileSummaryStatus}
            freshnessLine={
              viewedProfile ? formatFreshness(latestCapturedAt(viewedProfile)) : undefined
            }
            primaryChangeInFlight={primaryChangeInFlight}
            onSelectProfile={(id) => setViewedProfileId(Number(id))}
            onMakePrimary={(id) => void handleMakePrimary(id)}
            onLinkAnotherAccount={() => void navigate({ to: '/sign-in', search: { link: true } })}
            onBackToPrimary={() => setViewedProfileId(primaryProfile?.profile_id ?? null)}
            onRetry={() => void profilesQuery.refetch()}
          />

          {makePrimaryError && (
            <div className="px-4 md:px-6">
              <Callout
                tone="danger"
                heading="We could not change your primary profile"
                headingLevel={3}
              >
                {makePrimaryError}
              </Callout>
            </div>
          )}
        </>
      )}

      {/* match-history.md §7: page header to the panel below it shares the list route's own
       * `space-6`; no dedicated figure exists for the detail route. Rendered unconditionally
       * (T331): the match itself never depends on the caller having a linked profile, only the
       * header above it does. */}
      <div className="mt-6 px-4 pb-8 md:px-6">
        <MatchDetailPanel
          status={matchStatus}
          match={matchDetail}
          downloadState={downloadState}
          onDownload={handleDownload}
          onRetry={() => void matchQuery.refetch()}
        />

        {/* replay-availability.md §8: `space-8` between this section and `ParticipantsTable`
         * above it (inside `MatchDetailPanel`) — "a download action and a table of facts are two
         * different kinds of content on the same page". */}
        {showReplayAvailability && (
          <div className="mt-8">
            <ReplayAvailabilityList
              loading={matchStatus === 'loading'}
              rows={toReplayAvailabilityRows(rawParticipants, pointOfViewDownloadStates)}
              onDownload={handlePointOfViewDownload}
            />
          </div>
        )}
      </div>
    </main>
  )
}
