import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import {
  AccountErasurePanel,
  ArchivalControl,
  Callout,
  DataExportPanel,
  ErasedScreen,
} from 'design-system'
import { isApiErrorCode, meQueryOptions } from '../../lib/api'
import { formatObjectedAt } from '../profile/format'
import { setArchivalObjection } from '../profile/api'
import { archivalControlStateFromSession } from '../profile/session'
import {
  eraseAccount,
  pollExport,
  requestErasureConfirmation,
  startExport,
  type ExportStatusResponse,
} from './api'

// T095: the signed-in privacy route, composing (top to bottom, per privacy-data-rights.md's own
// composition order) `ArchivalControl` — consumed exactly as it is on the profile page, not
// respanned — then `DataExportPanel`, then `AccountErasurePanel` last, because erasure ends the
// session and nothing a user might still want sits below it. At most one `Button/primary` across
// the whole route (`ArchivalControl`'s "Resume archival", in one state only).

export function PrivacyContainer() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const meQuery = useQuery(meQueryOptions)
  const session = meQuery.data
  const authenticated = session?.authenticated ?? false

  function redirectIfSessionExpired(error: unknown): boolean {
    if (isApiErrorCode(error, 'not_authenticated')) {
      void navigate({ to: '/sign-in' })
      return true
    }
    return false
  }

  // --- Archival objection (FR-034/FR-035) — the same wiring `DashboardContainer.tsx` gives
  // `ArchivalControl`, reused here rather than rebuilt: this route is the second, anticipated
  // consumer `archival-control.md`'s own header names -------------------------------------------

  const [archivalSubmitting, setArchivalSubmitting] = useState(false)
  const [archivalWriteFailed, setArchivalWriteFailed] = useState(false)
  const [justResumed, setJustResumed] = useState(false)

  const archivalState =
    session && session.authenticated ? archivalControlStateFromSession(session) : 'archiving'

  async function submitArchivalObjection(objected: boolean) {
    setArchivalSubmitting(true)
    setArchivalWriteFailed(false)
    try {
      await setArchivalObjection(objected)
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

  // --- Export (FR-036) — `DataExportPanel` owns its own request/poll lifecycle; this container
  // only adapts the wire shapes (`features/privacy/api.ts`, snake_case) to what it expects -------

  async function handleRequestExport(): Promise<{ id: string }> {
    const response = await startExport()
    return { id: response.id }
  }

  async function handlePollExport(
    jobId: string,
  ): Promise<{ status: 'queued' } | { status: 'completed'; downloadUrl: string }> {
    const response: ExportStatusResponse = await pollExport(jobId)
    if (response.status === 'completed') {
      return { status: 'completed', downloadUrl: response.download_url }
    }
    return { status: 'queued' }
  }

  // --- Erasure (FR-037) — `AccountErasurePanel` owns its own dialog lifecycle; `erased` swaps
  // the whole route to the terminal screen, since every other panel here needs the session that
  // no longer exists once this resolves --------------------------------------------------------

  const [erased, setErased] = useState(false)

  async function handleRequestConfirmation(): Promise<{ confirmationToken: string }> {
    const response = await requestErasureConfirmation()
    return { confirmationToken: response.confirmation_token }
  }

  async function handleErase(confirmationToken: string): Promise<void> {
    await eraseAccount(confirmationToken)
  }

  if (erased) {
    return (
      <main className="min-h-svh bg-background px-4 py-6 md:px-6 md:py-8">
        <ErasedScreen homeHref="/privacy-notice" />
      </main>
    )
  }

  return (
    <main className="min-h-svh bg-background px-4 py-6 md:px-6 md:py-8">
      {meQuery.isPending ? (
        <p className="font-sans text-text-secondary">Loading…</p>
      ) : !authenticated ? (
        <Callout tone="info" heading="Sign in to manage your data">
          You need to be signed in to export or erase your data.
        </Callout>
      ) : (
        <div className="flex flex-col gap-12">
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
            privacyNoticeHref="/privacy-notice"
          />

          <DataExportPanel onRequestExport={handleRequestExport} onPollExport={handlePollExport} />

          <AccountErasurePanel
            onRequestConfirmation={handleRequestConfirmation}
            onErase={handleErase}
            onErased={() => setErased(true)}
          />
        </div>
      )}
    </main>
  )
}
