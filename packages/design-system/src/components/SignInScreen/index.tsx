import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/sign-in-screen.md

export type SignInScreenVariant = 'sign-in' | 'link'

// The spec tables "sign-in", "link" and "returning" together as one variant axis (§3), but
// "returning" is exactly the loading phase described again in §4 — the callback being verified.
// Splitting copy (`variant`) from phase keeps the two concerns independent instead of forcing a
// `returning` copy variant to exist for both `sign-in` and `link`.
export type SignInScreenPhase = 'default' | 'leaving' | 'returning' | 'unavailable'

export type SignInOutcome =
  | 'no_aoe2_profile'
  | 'not_allowlisted'
  | 'steam_assertion_invalid'
  | 'unreachable'
  | 'profile_already_linked'

export interface SignInScreenProps {
  variant?: SignInScreenVariant
  phase?: SignInScreenPhase
  /** One of the four failures, or `profile_already_linked` (`link` variant only). `null`/`undefined`
   * is the ordinary first visit: `OutcomeRegion` renders nothing. */
  outcome?: SignInOutcome | null
  onContinueWithSteam: () => void
  onTryAgain?: () => void
  onUseDifferentAccount?: () => void
  onStartOver?: () => void
  onCancel?: () => void
  onTryDifferentAccount?: () => void
  /** "Request access" renders only when this is set — a dead button is worse than no button
   * (spec, `not_allowlisted` row). */
  requestAccessHref?: string
  /** Copy shown in place of the beta note when `phase` is `unavailable`. */
  unavailableMessage?: ReactNode
  /** Microsoft Game Content Usage Rules disclaimer — rendered by the route (constitution X), only
   * reserved here so the panel is not vertically centred against a footer that shifts it later. */
  footerSlot?: ReactNode
  className?: string
}

const identityNote =
  'Your Steam account is the only key to this account. There is no password, no password reset and no account recovery — if you lose access to Steam, you lose access here.'

const betaNote = 'aoe2-stats is currently in a closed beta.'

const noAdminLine = 'No identifier to type. Steam confirms who you are; we never see a password.'

export function SignInScreen({
  variant = 'sign-in',
  phase = 'default',
  outcome = null,
  onContinueWithSteam,
  onTryAgain,
  onUseDifferentAccount,
  onStartOver,
  onCancel,
  onTryDifferentAccount,
  requestAccessHref,
  unavailableMessage,
  footerSlot,
  className,
}: SignInScreenProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const hasFocusedOutcome = useRef(false)
  // §4, `returning`: "after 10s, fall through to the unreachable outcome below with a retry."
  const [returningTimedOut, setReturningTimedOut] = useState(false)

  useEffect(() => {
    if (phase !== 'returning') {
      setReturningTimedOut(false)
      return
    }
    const timer = window.setTimeout(() => setReturningTimedOut(true), 10_000)
    return () => window.clearTimeout(timer)
  }, [phase])

  const effectiveOutcome = phase === 'returning' && returningTimedOut ? 'unreachable' : outcome

  useEffect(() => {
    // "Do this once, on mount, and never steal focus again afterwards."
    if (effectiveOutcome && !hasFocusedOutcome.current) {
      hasFocusedOutcome.current = true
      headingRef.current?.focus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const isReturning = phase === 'returning' && !returningTimedOut
  const title =
    variant === 'link'
      ? 'Link another Steam account'
      : 'Sign in to see your Age of Empires II stats'
  const valueLine =
    variant === 'link'
      ? 'Each Steam account has its own Age of Empires II profile. Linking a second one archives its replays too.'
      : 'See your ratings, matches and win rate — nothing to type, no password to remember.'

  return (
    <main className="flex min-h-screen flex-col items-center bg-background px-4 pt-8 md:px-6 md:pt-0 lg:px-8">
      <section
        aria-labelledby="sign-in-screen-title"
        className={cx(
          'mt-8 w-full max-w-md rounded-panel border border-border bg-surface p-6 shadow-raised md:mt-12 md:p-8',
          className,
        )}
      >
        <div
          aria-hidden="true"
          className="mx-auto mb-5 h-10 w-10 rounded-full border-2 border-accent"
        />
        <h1
          id="sign-in-screen-title"
          className="text-center font-display text-2xl font-bold tracking-tight text-text-primary md:text-3xl"
        >
          {title}
        </h1>

        {isReturning ? (
          <ReturningState />
        ) : (
          <>
            <p className="mt-3 text-left font-sans text-md text-text-primary">{valueLine}</p>

            <div className="mt-6">
              {effectiveOutcome && (
                <Callout
                  tone={outcomeTone[effectiveOutcome]}
                  heading={outcomeHeading[effectiveOutcome]}
                  headingRef={headingRef}
                  actions={renderOutcomeActions(effectiveOutcome, {
                    onTryAgain,
                    onUseDifferentAccount,
                    onStartOver,
                    onCancel,
                    onTryDifferentAccount,
                    requestAccessHref,
                  })}
                >
                  {outcomeBody[effectiveOutcome]}
                </Callout>
              )}
            </div>

            <div
              className={cx('flex flex-col gap-3 md:flex-row', effectiveOutcome ? 'mt-6' : 'mt-6')}
            >
              <Button
                variant="primary"
                size="lg"
                loading={phase === 'leaving'}
                loadingLabel="Taking you to Steam…"
                disabled={phase === 'unavailable'}
                onClick={onContinueWithSteam}
                className="w-full md:w-auto"
              >
                Continue with Steam
              </Button>
              {variant === 'link' && (
                <Button
                  variant="secondary"
                  size="lg"
                  onClick={onCancel}
                  className="w-full md:w-auto"
                >
                  Cancel
                </Button>
              )}
            </div>

            <p className="mt-4 font-sans text-sm text-text-secondary">{noAdminLine}</p>
            <p className="mt-3 font-sans text-sm text-text-primary">{identityNote}</p>
            {phase === 'unavailable' ? (
              <div className="mt-2">
                <Callout tone="info" heading="Sign-in is unavailable">
                  {unavailableMessage}
                </Callout>
              </div>
            ) : (
              <p className="mt-2 font-sans text-sm text-text-secondary">{betaNote}</p>
            )}
          </>
        )}
      </section>
      {footerSlot && <div className="mt-8 w-full max-w-md">{footerSlot}</div>}
    </main>
  )
}

// T532 (FR-054): one region for both skeletons below, announced once via this div's own
// `aria-busy` rather than per `Skeleton` (each stays `aria-hidden`, its own contract).
function ReturningState() {
  return (
    <div className="mt-6 flex flex-col gap-3" aria-busy="true">
      <Skeleton variant="text" lines={3} />
      <Skeleton variant="block" className="h-12 w-full" />
      <p className="font-sans text-sm text-text-secondary">Checking that with Steam…</p>
    </div>
  )
}

const outcomeTone: Record<SignInOutcome, 'info' | 'danger' | 'warning'> = {
  no_aoe2_profile: 'info',
  not_allowlisted: 'info',
  steam_assertion_invalid: 'danger',
  unreachable: 'danger',
  profile_already_linked: 'warning',
}

const outcomeHeading: Record<SignInOutcome, string> = {
  no_aoe2_profile: 'This Steam account has no Age of Empires II profile yet',
  not_allowlisted: 'aoe2-stats is in closed beta',
  steam_assertion_invalid: 'We could not verify that sign-in with Steam',
  unreachable: 'Steam did not answer',
  profile_already_linked: 'That Steam account is already linked elsewhere',
}

const outcomeBody: Record<SignInOutcome, string> = {
  no_aoe2_profile:
    'Your sign-in worked. The game creates a profile the first time you play a match online — single-player games do not create one. If you have played online very recently, it can take a little while to appear.',
  not_allowlisted:
    'Your sign-in worked. This Steam account is not on the beta list, so no account was created.',
  steam_assertion_invalid:
    'Steam did not confirm the response we received, so we did not sign you in. This usually means the sign-in link was reused or has expired. Start again from the beginning.',
  unreachable:
    'We could not reach Steam just now. Nothing about you was changed. This is almost always temporary.',
  profile_already_linked:
    'This Steam account is linked to a different aoe2-stats account. Unlink it there first, or link a different one.',
}

interface OutcomeHandlers {
  onTryAgain?: () => void
  onUseDifferentAccount?: () => void
  onStartOver?: () => void
  onCancel?: () => void
  onTryDifferentAccount?: () => void
  requestAccessHref?: string
}

function renderOutcomeActions(outcome: SignInOutcome, handlers: OutcomeHandlers): ReactNode {
  switch (outcome) {
    case 'no_aoe2_profile':
      return (
        <>
          <Button variant="primary" onClick={handlers.onTryAgain}>
            Try again
          </Button>
          <Button variant="secondary" onClick={handlers.onUseDifferentAccount}>
            Use a different Steam account
          </Button>
        </>
      )
    case 'not_allowlisted':
      return (
        <>
          {handlers.requestAccessHref && (
            <Button variant="primary" href={handlers.requestAccessHref}>
              Request access
            </Button>
          )}
          <Button variant="secondary" onClick={handlers.onTryAgain}>
            Try again
          </Button>
        </>
      )
    case 'steam_assertion_invalid':
      return (
        <Button variant="primary" onClick={handlers.onStartOver}>
          Start over
        </Button>
      )
    case 'unreachable':
      return (
        <Button variant="primary" onClick={handlers.onTryAgain}>
          Try again
        </Button>
      )
    case 'profile_already_linked':
      return (
        <>
          <Button variant="primary" onClick={handlers.onTryDifferentAccount}>
            Try a different account
          </Button>
          <Button variant="secondary" onClick={handlers.onCancel}>
            Cancel
          </Button>
        </>
      )
  }
}
