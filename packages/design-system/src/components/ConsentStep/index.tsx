import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { Dialog } from '../Dialog'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/consent-step.md

export type ConsentStepVariant = 'onboarding' | 'settings' | 'withdraw-confirm'
export type ConsentDecision = 'accepted' | 'declined' | 'unanswered'

export interface ConsentStepProps {
  variant?: ConsentStepVariant
  decision?: ConsentDecision
  /** When the current decision was recorded (`settings`/accepted state). */
  recordedAt?: ReactNode
  /** True while `/api/me` has not resolved yet (`settings` variant only). The identity statement
   * is never skeletoned — it is static copy, available at first paint. */
  loadingCurrentState?: boolean
  /** True while a decision is being written; both buttons disable together. */
  submitting?: boolean
  /** Which button is in flight, for the loading label. */
  submittingChoice?: 'accept' | 'decline'
  /** The write failed: renders the danger callout and never shows the attempted decision as if it
   * had taken effect. */
  writeFailed?: boolean
  /** Consent cannot be recorded at all (route unavailable): both buttons disable, an info callout
   * explains nothing is archived meanwhile. */
  unavailable?: boolean
  onAccept?: () => void
  onDecline?: () => void
  onTurnOnArchival?: () => void
  privacyNoticeHref?: string
  className?: string
}

// §4.1 — normative, banned-phrase-checked copy. Never behind a disclosure, never de-emphasised.
const statements = [
  'Your Steam account is the only key to this account. There is no password.',
  'If you lose access to your Steam account, you lose access here. We cannot let you back in.',
  'There is no password reset, no email verification and no account recovery — not through support, not by proving who you are, not by any other route.',
  'Getting a Steam account back is between you and Valve. We are not part of that.',
]

const rationaleLine =
  'We never store a password, so there is nothing here to steal and nothing to reset. That is the trade.'

const explanationParagraphs = [
  'Age of Empires II deletes your replay files about 31 days after the match. After that nobody can get them back — not you, not us, not Microsoft.',
  'If you turn this on, we download the recording of each of your matches from your own point of view and keep the original file, unchanged.',
  'We only ever take your own point of view, never another player’s.',
  'This runs by itself. You never have to remember to do anything.',
  'It covers every Steam account you have linked, so no linked profile quietly expires.',
]

const consequenceLine =
  'While this is off, nothing of yours is downloaded or stored. Matches you play meanwhile will expire on Microsoft’s servers, and the only copy left will be the one on your own machine, if you still have it.'

const withdrawalLine =
  'You can change this whenever you like. Turning it off stops future captures; replays already archived stay until you delete them, and you can export or erase everything at any time.'

export function ConsentStep({
  variant = 'onboarding',
  decision = 'unanswered',
  recordedAt,
  loadingCurrentState = false,
  submitting = false,
  submittingChoice,
  writeFailed = false,
  unavailable = false,
  onAccept,
  onDecline,
  onTurnOnArchival,
  privacyNoticeHref,
  className,
}: ConsentStepProps) {
  if (variant === 'withdraw-confirm') {
    return <WithdrawConfirmDialog onTurnOff={onAccept} onKeepOn={onDecline} className={className} />
  }

  const short = variant === 'settings'
  const bothDisabled = submitting || unavailable

  return (
    <section aria-labelledby="consent-step-heading" className={cx('max-w-prose', className)}>
      <h2
        id="consent-step-heading"
        className="font-display text-xl font-semibold text-text-primary"
      >
        Replay archival
      </h2>

      <div className="mt-6 rounded-lg bg-surface-raised p-5">
        <h3 className="font-sans text-md font-semibold text-text-primary">
          Before you decide: how you get back in
        </h3>
        <ul className="mt-3 flex flex-col gap-3">
          {(short ? statements.slice(0, 2) : statements).map((statement) => (
            <li key={statement} className="font-sans text-md font-medium text-text-primary">
              {statement}
            </li>
          ))}
        </ul>
        {/* `settings` renders the short form — heading plus statements 1 and 2 only — and drops
         * the rationale line, which belongs to the full explanation. */}
        {!short && (
          <p className="mt-4 font-sans text-md font-medium text-text-primary">{rationaleLine}</p>
        )}
      </div>

      {short ? (
        <SettingsBody
          decision={decision}
          recordedAt={recordedAt}
          loading={loadingCurrentState}
          bothDisabled={bothDisabled}
          submitting={submitting}
          submittingChoice={submittingChoice}
          writeFailed={writeFailed}
          unavailable={unavailable}
          onAccept={onAccept}
          onDecline={onDecline}
          onTurnOnArchival={onTurnOnArchival}
        />
      ) : (
        <OnboardingBody
          bothDisabled={bothDisabled}
          submitting={submitting}
          submittingChoice={submittingChoice}
          writeFailed={writeFailed}
          unavailable={unavailable}
          decision={decision}
          onAccept={onAccept}
          onDecline={onDecline}
        />
      )}

      {privacyNoticeHref && (
        <p className="mt-4 font-sans text-sm">
          <a href={privacyNoticeHref} className="text-text-secondary underline">
            Read the privacy notice
          </a>
        </p>
      )}
    </section>
  )
}

interface BodyCommon {
  bothDisabled: boolean
  submitting: boolean
  submittingChoice?: 'accept' | 'decline'
  writeFailed: boolean
  unavailable: boolean
  decision: ConsentDecision
  onAccept?: () => void
  onDecline?: () => void
}

function OnboardingBody({
  bothDisabled,
  submitting,
  submittingChoice,
  writeFailed,
  unavailable,
  onAccept,
  onDecline,
}: BodyCommon) {
  return (
    <>
      <h3 className="mt-8 font-sans text-md font-semibold text-text-primary">
        What we would archive
      </h3>
      <div className="mt-3 flex flex-col gap-3">
        {explanationParagraphs.map((paragraph) => (
          <p key={paragraph} className="font-sans text-md text-text-primary">
            {paragraph}
          </p>
        ))}
      </div>

      <div className="mt-8 flex flex-col gap-3 md:flex-row">
        <Button
          variant="primary"
          size="lg"
          disabled={bothDisabled}
          loading={submitting && submittingChoice === 'accept'}
          loadingLabel="Saving your choice…"
          onClick={onAccept}
          className="w-full md:w-auto"
        >
          Archive my replays
        </Button>
        <Button
          variant="secondary"
          size="lg"
          disabled={bothDisabled}
          loading={submitting && submittingChoice === 'decline'}
          loadingLabel="Saving your choice…"
          onClick={onDecline}
          className="w-full md:w-auto"
        >
          Not now
        </Button>
      </div>

      <p className="mt-4 font-sans text-sm text-text-secondary">{consequenceLine}</p>
      <p className="mt-2 font-sans text-sm text-text-secondary">{withdrawalLine}</p>

      <StatusRegion writeFailed={writeFailed} unavailable={unavailable} />
    </>
  )
}

function SettingsBody({
  decision,
  recordedAt,
  loading,
  bothDisabled,
  submitting,
  submittingChoice,
  writeFailed,
  unavailable,
  onAccept,
  onDecline,
  onTurnOnArchival,
}: BodyCommon & {
  recordedAt?: ReactNode
  loading: boolean
  onTurnOnArchival?: () => void
}) {
  if (loading) {
    return (
      <div className="mt-8 flex flex-col gap-2">
        <Skeleton variant="text" lines={1} className="w-1/2" />
        <Skeleton variant="block" className="h-10 w-40" />
      </div>
    )
  }

  if (decision === 'unanswered') {
    return (
      <>
        <p className="mt-8 font-sans text-md text-text-primary">You have not answered this yet.</p>
        <OnboardingBody
          bothDisabled={bothDisabled}
          submitting={submitting}
          submittingChoice={submittingChoice}
          writeFailed={writeFailed}
          unavailable={unavailable}
          decision={decision}
          onAccept={onAccept}
          onDecline={onDecline}
        />
      </>
    )
  }

  if (decision === 'accepted') {
    return (
      <div className="mt-8">
        <Callout tone="success" heading="Archival is on.">
          {recordedAt
            ? `Recorded ${recordedAt}. We started with the last 31 days. New matches are picked up automatically.`
            : 'Nothing has been archived yet. The first sweep runs within a day.'}
        </Callout>
        <p className="mt-4 font-sans text-sm text-text-secondary">{withdrawalLine}</p>
        <StatusRegion writeFailed={writeFailed} unavailable={unavailable} />
      </div>
    )
  }

  return (
    <div className="mt-8">
      <Callout
        tone="info"
        heading="Archival is off."
        actions={
          <Button variant="primary" disabled={bothDisabled} onClick={onTurnOnArchival}>
            Turn on archival
          </Button>
        }
      >
        Your profile, ratings and match history still work. Nothing of yours is being downloaded or
        stored.
      </Callout>
      <StatusRegion writeFailed={writeFailed} unavailable={unavailable} />
    </div>
  )
}

function StatusRegion({
  writeFailed,
  unavailable,
}: {
  writeFailed: boolean
  unavailable: boolean
}) {
  if (writeFailed) {
    return (
      <div className="mt-6">
        <Callout tone="danger" heading="We could not save that choice">
          Your choice was not recorded, so nothing has changed. Nothing of yours is being archived.
        </Callout>
      </div>
    )
  }
  if (unavailable) {
    return (
      <div className="mt-6">
        <Callout tone="info" heading="We can’t save your choice right now">
          Nothing of yours is being archived while this is unavailable.
        </Callout>
      </div>
    )
  }
  return null
}

function WithdrawConfirmDialog({
  onTurnOff,
  onKeepOn,
  className,
}: {
  onTurnOff?: () => void
  onKeepOn?: () => void
  className?: string
}) {
  return (
    <Dialog
      heading="Turn off replay archival?"
      primaryAction={{ label: 'Turn it off', onClick: onTurnOff }}
      secondaryAction={{ label: 'Keep it on', onClick: onKeepOn }}
      className={className}
    >
      {consequenceLine}
    </Dialog>
  )
}
