import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/archival-control.md

export type ArchivalControlState = 'archiving' | 'objected'

export interface ArchivalControlProps {
  /** The only two facts `archival_objected_at` can mean. There is no "unanswered" state: a linked
   * user who has never touched the switch renders identically to one who objected and later
   * resumed, because the API records no timestamp for a resumption (archival-control.md §3). */
  state?: ArchivalControlState
  /** Required whenever `state="objected"` — the API always returns a timestamp for that state. */
  objectedAt?: ReactNode
  /** True immediately after the caller's own `onResume` write resolves, in this session only.
   * Nothing is persisted that would let a later page load reconstruct this — see §3. */
  justResumed?: boolean
  /** True while `/api/me` has not resolved yet. Only `StatusRegion` skeletons; the identity and
   * basis statements are static copy, available at first paint. */
  loading?: boolean
  /** True while the switch write is in flight; the one visible button disables. */
  submitting?: boolean
  /** The write failed: renders the danger callout and never shows the attempted action as if it
   * had taken effect. `state` stays exactly what it was before the attempt. */
  writeFailed?: boolean
  /** The route is unreachable: the switch disables, an info callout explains nothing has changed. */
  unavailable?: boolean
  /** `state="archiving"` only. */
  onObject?: () => void
  /** `state="objected"` only. */
  onResume?: () => void
  privacyNoticeHref?: string
  className?: string
}

// §4.1 — normative, banned-phrase-checked copy. Never behind a disclosure, never de-emphasised.
// Unchanged by the 4.0.0 amendment.
const statements = [
  'Your Steam account is the only key to this account. There is no password.',
  'If you lose access to your Steam account, you lose access here. We cannot let you back in.',
  'There is no password reset, no email verification and no account recovery — not through support, not by proving who you are, not by any other route.',
  'Getting a Steam account back is between you and Valve. We are not part of that.',
]

const rationaleLine =
  'We never store a password, so there is nothing here to steal and nothing to reset. That is the trade.'

// §4.2 — mechanism (1-6), then the objection boundary (7), both directions stated.
const basisParagraphs = [
  'This runs on our legitimate interest in saving your matches before Microsoft deletes them, not on your consent (GDPR Art. 6-1-f). Nothing is asked of you before it starts.',
  'Age of Empires II deletes your replay files about 31 days after the match. After that nobody can get them back — not you, not us, not Microsoft.',
  'We download the recording of each of your matches from your own point of view and keep the original file, unchanged.',
  'We only ever take your own point of view, never another player’s.',
  'This runs by itself. You never have to remember to do anything.',
  'It covers every Steam account you have linked, so no linked profile quietly expires.',
  'You can object at any time (GDPR Art. 21). Objecting stops future captures immediately; it does not touch your match history, your ratings, or replays already archived — and does not go back and capture what was missed while you had objected, either.',
]

/** GDPR-by-design objection control (constitution IX 4.0.0): states that archival is running, on
 * what basis, and offers the one switch — object, or resume — that changes it. Replaces
 * `ConsentStep`, whose `onboarding` ask-before-archiving variant was the retired consent gate in
 * visual form. */
export function ArchivalControl({
  state = 'archiving',
  objectedAt,
  justResumed = false,
  loading = false,
  submitting = false,
  writeFailed = false,
  unavailable = false,
  onObject,
  onResume,
  privacyNoticeHref,
  className,
}: ArchivalControlProps) {
  const switchDisabled = submitting || unavailable

  return (
    <section aria-labelledby="archival-control-heading" className={cx('max-w-measure', className)}>
      <h2
        id="archival-control-heading"
        className="font-display text-xl font-semibold text-text-primary"
      >
        Replay archival
      </h2>

      <div className="mt-6 rounded-panel bg-surface-raised p-5">
        <h3 className="font-sans text-md font-semibold text-text-primary">
          Before you decide: how you get back in
        </h3>
        <ul className="mt-3 flex flex-col gap-3">
          {statements.map((statement) => (
            <li key={statement} className="font-sans text-md font-medium text-text-primary">
              {statement}
            </li>
          ))}
        </ul>
        <p className="mt-4 font-sans text-md font-medium text-text-primary">{rationaleLine}</p>
      </div>

      <h3 className="mt-8 font-sans text-md font-semibold text-text-primary">
        What we archive, and why
      </h3>
      <div className="mt-3 flex flex-col gap-3">
        {basisParagraphs.map((paragraph) => (
          <p key={paragraph} className="font-sans text-md text-text-primary">
            {paragraph}
          </p>
        ))}
      </div>

      <div className="mt-8">
        {loading ? (
          <div className="flex flex-col gap-2">
            <Skeleton variant="text" lines={1} className="w-1/2" />
            <Skeleton variant="block" className="h-10 w-48" />
          </div>
        ) : (
          <StatusRegion
            state={state}
            objectedAt={objectedAt}
            justResumed={justResumed}
            switchDisabled={switchDisabled}
            submitting={submitting}
            onObject={onObject}
            onResume={onResume}
          />
        )}
      </div>

      {privacyNoticeHref && (
        <p className="mt-4 font-sans text-sm">
          <a href={privacyNoticeHref} className="text-text-secondary underline">
            Read the privacy notice
          </a>
        </p>
      )}

      <FailureRegion writeFailed={writeFailed} unavailable={unavailable} />
    </section>
  )
}

function StatusRegion({
  state,
  objectedAt,
  justResumed,
  switchDisabled,
  submitting,
  onObject,
  onResume,
}: {
  state: ArchivalControlState
  objectedAt?: ReactNode
  justResumed: boolean
  switchDisabled: boolean
  submitting: boolean
  onObject?: () => void
  onResume?: () => void
}) {
  if (state === 'objected') {
    return (
      <Callout
        tone="info"
        heading={objectedAt ? <>Archival is off. You objected {objectedAt}.</> : 'Archival is off.'}
        actions={
          <Button
            variant="primary"
            disabled={switchDisabled}
            loading={submitting}
            loadingLabel="Saving your choice…"
            onClick={onResume}
          >
            Resume archival
          </Button>
        }
      >
        Your match history and ratings still update. Nothing new is being downloaded or stored from
        your replays.
      </Callout>
    )
  }

  return (
    <Callout
      tone="success"
      heading={justResumed ? 'Archival resumed.' : 'Archival is on.'}
      actions={
        <Button
          variant="secondary"
          disabled={switchDisabled}
          loading={submitting}
          loadingLabel="Saving your choice…"
          onClick={onObject}
        >
          Object to archival
        </Button>
      }
    >
      {justResumed
        ? 'Future matches are captured again. Matches from while you had objected are not recovered — see above.'
        : 'New matches are picked up automatically.'}
    </Callout>
  )
}

function FailureRegion({
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
          Your choice was not recorded, so nothing has changed. Try again when you are ready.
        </Callout>
      </div>
    )
  }
  if (unavailable) {
    return (
      <div className="mt-6">
        <Callout tone="info" heading="We can’t save your choice right now">
          Nothing has changed while this is unavailable.
        </Callout>
      </div>
    )
  }
  return null
}
