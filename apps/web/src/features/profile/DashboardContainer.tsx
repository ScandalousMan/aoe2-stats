import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { ArchivalControl, Button, Callout, ProfileSummary } from 'design-system'
import type { ProfileSummaryStatus } from 'design-system'
import { isApiErrorCode, meQueryOptions, signOut } from '../../lib/api'
import {
  type ArchivedReplaysPreview,
  confirmUnlink,
  previewUnlink,
  profilesQueryOptions,
  setArchivalObjection,
  setPrimaryProfile,
} from './api'
import { formatFreshness, formatObjectedAt } from './format'
import {
  latestCapturedAt,
  toLinkedProfileOptions,
  toRatingEntries,
  toViewedProfile,
} from './mappers'
import { archivalControlStateFromSession } from './session'
import { UnlinkDialog } from './UnlinkDialog'

// Wires `ProfileSummary` and `ArchivalControl` (T035, packages/design-system) to this feature's
// real effects and to nothing else — the same discipline `SignInContainer.tsx` (T036)
// established. Every visual state lives in those components; this module owns the data and the
// handlers.

export function DashboardContainer() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const meQuery = useQuery(meQueryOptions)
  const profilesQuery = useQuery(profilesQueryOptions)
  const session = meQuery.data

  // `__root.tsx`'s `beforeLoad` and `dashboard.tsx`'s own gate both check `session.authenticated`
  // once, at navigation time. A cookie can still expire while this page is already open — every
  // mutation below also watches for `not_authenticated` and lands here too, so a session that
  // dies mid-visit sends the visitor back to `/sign-in` rather than showing broken partial state.
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

  // --- Sign out (T036b): `signOut` (lib/api.ts) is the client half of `POST /api/auth/signout`
  // (T029) — implemented and tested from the day it shipped, but unreachable from the product
  // until this handler existed, which is why quickstart.md's scenario 1 could not be walked
  // through the UI. Mirrors the other mutations here: invalidate the session on success, redirect
  // on a server-confirmed sign-out or on discovering the session was already dead either way.
  const [signOutPending, setSignOutPending] = useState(false)
  const [signOutError, setSignOutError] = useState<string | null>(null)

  async function handleSignOut() {
    setSignOutPending(true)
    setSignOutError(null)
    try {
      await signOut()
      await queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
      void navigate({ to: '/sign-in' })
    } catch (error) {
      if (!redirectIfSessionExpired(error)) {
        setSignOutError('We could not sign you out. Try again.')
      }
    } finally {
      setSignOutPending(false)
    }
  }

  // FR-043: "viewing" is a session-level selection that writes nothing. `null` means "no explicit
  // selection yet" — the primary profile is what shows until the switcher is used, and it is what
  // shows again once the explicitly viewed profile stops existing (unlinked).
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

  // --- Unlink (FR-004): preview, then a real confirmation, never in one step -------------------

  const [unlinkTarget, setUnlinkTarget] = useState<{ profileId: number; alias: string } | null>(
    null,
  )
  const [unlinkPreview, setUnlinkPreview] = useState<ArchivedReplaysPreview | null>(null)
  const [unlinkPreviewPending, setUnlinkPreviewPending] = useState(false)
  const [unlinkPreviewError, setUnlinkPreviewError] = useState<string | null>(null)
  const [unlinkConfirmPending, setUnlinkConfirmPending] = useState(false)
  const [unlinkConfirmError, setUnlinkConfirmError] = useState<string | null>(null)

  async function handleStartUnlink() {
    if (!viewedProfile) return
    setUnlinkPreviewPending(true)
    setUnlinkPreviewError(null)
    try {
      const preview = await previewUnlink(viewedProfile.profile_id)
      setUnlinkTarget({ profileId: viewedProfile.profile_id, alias: viewedProfile.alias })
      setUnlinkPreview(preview.archived_replays)
    } catch (error) {
      if (!redirectIfSessionExpired(error)) {
        setUnlinkPreviewError('We could not check what unlinking would do. Try again.')
      }
    } finally {
      setUnlinkPreviewPending(false)
    }
  }

  async function handleConfirmUnlink() {
    if (!unlinkTarget) return
    setUnlinkConfirmPending(true)
    setUnlinkConfirmError(null)
    try {
      await confirmUnlink(unlinkTarget.profileId)
      if (viewedProfileId === unlinkTarget.profileId) {
        setViewedProfileId(null)
      }
      setUnlinkTarget(null)
      setUnlinkPreview(null)
      await queryClient.invalidateQueries({ queryKey: profilesQueryOptions.queryKey })
      void queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
    } catch (error) {
      if (!redirectIfSessionExpired(error)) {
        setUnlinkConfirmError('Your choice was not recorded, so nothing has changed.')
      }
    } finally {
      setUnlinkConfirmPending(false)
    }
  }

  function handleCancelUnlink() {
    setUnlinkTarget(null)
    setUnlinkPreview(null)
    setUnlinkConfirmError(null)
  }

  // --- Archival objection (FR-034 / FR-035, constitution IX 4.0.0): `ArchivalControl` is wired
  // here; the privacy route (T095) is the other consumer archival-control.md anticipates, for the
  // account's notice and export/erasure surface rather than for this in-line summary ------------

  const [archivalSubmitting, setArchivalSubmitting] = useState(false)
  const [archivalWriteFailed, setArchivalWriteFailed] = useState(false)
  // Set for the rest of this session immediately after a successful `onResume` write, so the
  // person who just pressed the button sees an acknowledgement (archival-control.md §3) before it
  // collapses back to the plain steady state on the next reload — there is no server-side
  // timestamp for a resumption to reconstruct it from.
  const [justResumed, setJustResumed] = useState(false)

  // T405/T406: `GET /api/me` reports the state that is true *now* (`archival_objected`,
  // `archival_objected_at`) — an objection or a resumption is visible on the very next request, so
  // a page reload never loses it. `archivalControlStateFromSession` (`session.ts`) is the one
  // place this is derived; no session-local override is held here any more.
  const archivalState =
    session && session.authenticated ? archivalControlStateFromSession(session) : 'archiving'

  async function submitArchivalObjection(objected: boolean) {
    setArchivalSubmitting(true)
    setArchivalWriteFailed(false)
    try {
      await setArchivalObjection(objected)
      // Awaited, not fired-and-forgotten: `archivalState` is derived straight from `session`
      // above, so the new state (and, when objecting, the recorded timestamp) only appears once
      // this refetch has actually landed.
      await queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
      setJustResumed(!objected)
    } catch (error) {
      if (!redirectIfSessionExpired(error)) {
        setArchivalWriteFailed(true)
      }
    } finally {
      setArchivalSubmitting(false)
    }
  }

  // --- ProfileSummary status (profile-summary.md §5) -------------------------------------------

  const profilesLoading = profilesQuery.isPending
  const profilesHaveData = profilesQuery.data !== undefined
  let status: ProfileSummaryStatus = 'default'
  if (profilesLoading) {
    status = 'loading'
  } else if (profilesQuery.isError) {
    status = profilesHaveData ? 'stale' : 'error'
  } else if (viewedProfile && viewedProfile.ratings.length === 0) {
    status = 'empty'
  }

  const showEmptyAccount = !profilesLoading && !profilesQuery.isError && profiles.length === 0

  return (
    <main className="min-h-svh bg-background">
      {authenticated && (
        <div className="flex justify-between px-4 pt-4 md:px-6">
          {/* T383: the one entry point to `/search` (T322) a signed-in visitor reaches without
           * typing the URL — without this, `/search` existed and Phase 3's checkpoint ("a user
           * can find any player by name") did not. Plain `navigate()`, matching every other
           * cross-page action in this container (`onLinkAnotherAccount` below), not `Button`'s
           * `href` — that renders a raw `<a>` and forces a full document reload in this SPA. */}
          <Button variant="ghost" onClick={() => void navigate({ to: '/search' })}>
            Search players
          </Button>
          <Button
            variant="ghost"
            onClick={() => void handleSignOut()}
            loading={signOutPending}
            loadingLabel="Signing out…"
          >
            Sign out
          </Button>
        </div>
      )}

      {signOutError && (
        <div className="px-4 md:px-6">
          <Callout tone="danger" heading="We could not sign you out" headingLevel={3}>
            {signOutError}
          </Callout>
        </div>
      )}

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
            Link a Steam account to see your ratings and match history.
          </Callout>
        </div>
      ) : (
        <ProfileSummary
          authenticated={authenticated}
          viewedProfile={viewedProfile ? toViewedProfile(viewedProfile) : undefined}
          linkedProfiles={toLinkedProfileOptions(profiles)}
          entries={viewedProfile ? toRatingEntries(viewedProfile) : []}
          status={status}
          freshnessLine={
            viewedProfile ? formatFreshness(latestCapturedAt(viewedProfile)) : undefined
          }
          primaryChangeInFlight={primaryChangeInFlight}
          unlinkInFlight={unlinkPreviewPending || unlinkConfirmPending}
          manageError={unlinkPreviewError ?? undefined}
          onSelectProfile={(id) => setViewedProfileId(Number(id))}
          onMakePrimary={(id) => void handleMakePrimary(id)}
          onLinkAnotherAccount={() => void navigate({ to: '/sign-in', search: { link: true } })}
          onUnlink={() => void handleStartUnlink()}
          onBackToPrimary={() => setViewedProfileId(primaryProfile?.profile_id ?? null)}
          onRetry={() => void profilesQuery.refetch()}
        />
      )}

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

      {authenticated && (
        <div className="mt-8 px-4 pb-8 md:px-6">
          <ArchivalControl
            state={archivalState}
            objectedAt={
              session && session.authenticated && session.archival_objected_at
                ? formatObjectedAt(session.archival_objected_at)
                : undefined
            }
            justResumed={justResumed}
            submitting={archivalSubmitting}
            writeFailed={archivalWriteFailed}
            onObject={() => void submitArchivalObjection(true)}
            onResume={() => void submitArchivalObjection(false)}
          />
        </div>
      )}

      {unlinkTarget && unlinkPreview && (
        <UnlinkDialog
          alias={unlinkTarget.alias}
          archivedReplayCount={unlinkPreview.count}
          consequenceMessage={unlinkPreview.message}
          pending={unlinkConfirmPending}
          error={unlinkConfirmError ?? undefined}
          onConfirm={() => void handleConfirmUnlink()}
          onCancel={handleCancelUnlink}
        />
      )}
    </main>
  )
}
