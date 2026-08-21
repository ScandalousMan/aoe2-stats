import { useCallback, useState } from 'react'
import { SignInScreen, type SignInScreenPhase } from 'design-system'
import { resolveOutcome } from './outcome'
import { buildSteamStartUrl } from './steamStart'

export interface SignInContainerProps {
  /** `true` only for an already-signed-in caller adding a second Steam account (FR-007) — the
   * route gates this before it ever reaches here (`sign-in.tsx`'s `beforeLoad`). */
  linkMode: boolean
  /** The `?error=` query parameter, verbatim from the URL. */
  errorCode: string | undefined
  /** Client-side navigation back to the app, for `Cancel` (`link` variant) and the outcome that
   * shares it, `profile_already_linked`. Never a `window.location` assignment: unlike "Continue
   * with Steam" this never leaves the SPA. */
  onNavigateHome: () => void
}

/**
 * Wires `SignInScreen` (T035, packages/design-system/src/components/SignInScreen/) to this
 * feature's two real effects — a full-page navigation to Steam, and a client-side navigation back
 * into the app — and to nothing else. Every visual state lives in the component; this module owns
 * none of its own.
 */
export function SignInContainer({ linkMode, errorCode, onNavigateHome }: SignInContainerProps) {
  const [phase, setPhase] = useState<SignInScreenPhase>('default')
  const outcome = resolveOutcome(errorCode)

  const continueWithSteam = useCallback(() => {
    setPhase('leaving')
    // `window.location.assign` unloads this SPA (module docstring, steamStart.ts) — deferred one
    // tick so React commits the `leaving` phase's "Taking you to Steam…" label before that
    // happens, rather than racing the navigation against the paint.
    window.setTimeout(() => {
      window.location.assign(buildSteamStartUrl(linkMode))
    }, 0)
  }, [linkMode])

  return (
    <SignInScreen
      variant={linkMode ? 'link' : 'sign-in'}
      phase={phase}
      outcome={outcome}
      onContinueWithSteam={continueWithSteam}
      // Every outcome's retry action is the same real effect: a fresh, unconsumed
      // `/api/auth/steam/start` round trip. Steam's own page is what decides whether the visitor
      // can pick a different account (`no_aoe2_profile`, `profile_already_linked`) — this app has
      // no mechanism of its own to force that chooser.
      onTryAgain={continueWithSteam}
      onUseDifferentAccount={continueWithSteam}
      onStartOver={continueWithSteam}
      onTryDifferentAccount={continueWithSteam}
      onCancel={onNavigateHome}
      // `requestAccessHref` deliberately left unset: no request-access route exists yet, and the
      // spec is explicit that a dead button is worse than no button (sign-in-screen.md,
      // `not_allowlisted` row).
    />
  )
}
