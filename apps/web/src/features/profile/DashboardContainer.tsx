import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Button, Callout, ConsentStep, ProfileSummary } from 'design-system'
import type { ProfileSummaryStatus } from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import {
  type ArchivedReplaysPreview,
  confirmUnlink,
  previewUnlink,
  profilesQueryOptions,
  setConsent,
  setPrimaryProfile,
} from './api'
import { formatFreshness, formatRecordedAt } from './format'
import {
  latestCapturedAt,
  toLinkedProfileOptions,
  toRatingEntries,
  toViewedProfile,
} from './mappers'
import { type ConsentDecision, consentDecisionFromSession } from './session'
import { UnlinkDialog } from './UnlinkDialog'

// Wires `ProfileSummary` and `ConsentStep` (T035, packages/design-system) to this feature's real
// effects and to nothing else — the same discipline `SignInContainer.tsx` (T036) established.
// Every visual state lives in those components; this module owns the data and the handlers.

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

  // --- Consent (FR-034 / FR-035): `onboarding` and `settings` are wired here; the privacy route
  // (T095) is the other consumer consent-step.md's variant split anticipates, for the account's
  // notice and export/erasure surface rather than for this in-line summary ---------------------

  const [consentSubmitting, setConsentSubmitting] = useState(false)
  const [consentSubmittingChoice, setConsentSubmittingChoice] = useState<
    'accept' | 'decline' | undefined
  >(undefined)
  const [consentWriteFailed, setConsentWriteFailed] = useState(false)
  // `withdraw-confirm` (consent-step.md §3): a real dialog asked for before turning archival off,
  // never before turning it on — the settings/accepted `onTurnOffArchival` control opens it rather
  // than withdrawing directly, so the "Turn off archival" button T032a added is not a dead control.
  const [withdrawConfirmOpen, setWithdrawConfirmOpen] = useState(false)

  // T037a: `GET /api/me` now reports the consent state that is true *now* (`ingest_consent`,
  // `ingest_consent_at`) — a withdrawal is visible on the very next request, so a page reload no
  // longer loses it. `consentDecisionFromSession` (`session.ts`) is the one place this is derived;
  // no session-local override is held here any more.
  const effectiveConsentDecision: ConsentDecision =
    session && session.authenticated ? consentDecisionFromSession(session) : 'unanswered'

  async function handleConfirmWithdraw() {
    setWithdrawConfirmOpen(false)
    await submitConsent(false)
  }

  async function submitConsent(granted: boolean) {
    setConsentSubmitting(true)
    setConsentSubmittingChoice(granted ? 'accept' : 'decline')
    setConsentWriteFailed(false)
    try {
      await setConsent(granted)
      // Awaited, not fired-and-forgotten: `effectiveConsentDecision` is derived straight from
      // `session` above, so the new decision (and, for "settings", the recorded-at timestamp)
      // only appears once this refetch has actually landed.
      await queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
    } catch (error) {
      if (!redirectIfSessionExpired(error)) {
        setConsentWriteFailed(true)
      }
    } finally {
      setConsentSubmitting(false)
      setConsentSubmittingChoice(undefined)
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
          {effectiveConsentDecision === 'unanswered' ? (
            <ConsentStep
              variant="onboarding"
              submitting={consentSubmitting}
              submittingChoice={consentSubmittingChoice}
              writeFailed={consentWriteFailed}
              onAccept={() => void submitConsent(true)}
              onDecline={() => void submitConsent(false)}
            />
          ) : (
            <ConsentStep
              variant="settings"
              decision={effectiveConsentDecision}
              recordedAt={
                session && session.authenticated && session.ingest_consent_at
                  ? formatRecordedAt(session.ingest_consent_at)
                  : undefined
              }
              submitting={consentSubmitting}
              submittingChoice={consentSubmittingChoice}
              writeFailed={consentWriteFailed}
              onTurnOnArchival={() => void submitConsent(true)}
              onTurnOffArchival={() => setWithdrawConfirmOpen(true)}
            />
          )}
        </div>
      )}

      {withdrawConfirmOpen && (
        <ConsentStep
          variant="withdraw-confirm"
          onConfirmWithdraw={() => void handleConfirmWithdraw()}
          onCancelWithdraw={() => setWithdrawConfirmOpen(false)}
        />
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
