import type { FormEvent } from 'react'
import { useId, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../../primitives/Button'
import { Callout } from '../../primitives/Callout'
import { Page } from '../../primitives/Page'

// packages/design-system/specs/third-party-objection.md

export type ObjectionUiState =
  | 'idle' // explanation + empty field
  | 'submitting' // POST in flight
  | 'recorded' // 202; RecordedConfirmation shown
  | 'rate-limited' // 429; FormFailure/warning, with the retry hint
  | 'failed' // network or 5xx; FormFailure/danger, retryable

export interface ThirdPartyObjectionFormProps {
  /** POST /api/privacy/object. Resolves on 202; rejects with a typed reason otherwise. */
  onSubmit: (profileId: number) => Promise<void>
  /** Full privacy notice route, for the inline link in the explanation. Required. */
  privacyNoticeHref: string
  /** Injected only by stories to render a fixed state; the route never sets it. */
  initialState?: ObjectionUiState
  className?: string
}

// T589: `outline-offset-ring` (`border.json`'s `ring-offset`, 2px) names the offset this ring
// shipped as a bare `outline-offset-2` literal — same rendered offset, now a named token.
const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

// Fourth-pass review remediation (FR-037): hover and active shared `link-hover` with no other
// signal, so a press was not distinguishable from a hover in a still image.
// `active:underline-offset-4` gives press its own frame without a fill — the same fix now shared
// with `Link`'s `inline` variant, `Footer`, `PrivacyNotice` and `AccountErasurePanel`'s own copies
// of this pattern.
const inlineLinkClasses = cx(
  'text-link underline transition-colors duration-120 ease-standard motion-reduce:duration-0',
  'hover:text-link-hover active:text-link-hover active:underline-offset-4',
  focusRing,
)

// The visible heading and the hidden `Page` title below share this string (structural-tier.md
// §5): `Page` owns the route's only `<h1>`, so `Explanation`'s own heading is downgraded to
// `<h2>` rather than duplicated at the same level.
const pageTitle = 'Object to what is held about you'

/** FR-039: the one screen in the product addressed to someone who is not a user and has no
 * session. Self-contained — no signed-in chrome, no fetch that requires a cookie — and it explains
 * what is held and why *before* the field that asks for anything (FR-039's ordering). Records an
 * objection for a person to resolve later; it never claims the data has already changed. */
export function ThirdPartyObjectionForm({
  onSubmit,
  privacyNoticeHref,
  initialState = 'idle',
  className,
}: ThirdPartyObjectionFormProps) {
  const [state, setState] = useState<ObjectionUiState>(initialState)
  const [value, setValue] = useState('')
  const [fieldError, setFieldError] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const inputId = useId()
  const helpId = useId()
  const errorId = useId()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    // Validation happens on submit, never by disabling the button (§5's "disabled" rule) — a
    // stranger meeting this form once must never face a dead control with no explanation.
    const trimmed = value.trim()
    const profileId = Number(trimmed)
    if (trimmed === '' || !Number.isFinite(profileId) || !Number.isInteger(profileId)) {
      setFieldError(true)
      inputRef.current?.focus()
      return
    }

    setFieldError(false)
    setState('submitting')
    onSubmit(profileId)
      .then(() => {
        setState('recorded')
      })
      .catch((error: unknown) => {
        const status = (error as { status?: number } | undefined)?.status
        setState(status === 429 ? 'rate-limited' : 'failed')
      })
  }

  // The single main landmark, the content width and the page padding are `Page`'s (FR-021,
  // FR-022, structural-tier.md §5) — this form is always the sole thing `/object` renders, so it
  // composes `Page` itself rather than leaving that to its container. `width="measure"` keeps
  // the exact reading width this form already used (`tokens/size.json`'s `measure`, unchanged).
  if (state === 'recorded') {
    return (
      <Page title={pageTitle} titleHidden width="measure">
        <div className={className}>
          <Explanation privacyNoticeHref={privacyNoticeHref} />
          <div className="mt-8">
            <Callout tone="success" heading="Your objection has been recorded.">
              A person will act on it within 30 days, replacing your profile id in our match records
              with a pseudonymous one. Nothing has been changed yet, and there is no account here to
              sign in to — this is the whole of what happens, and we would rather say so than send a
              confirmation we have no address for.
            </Callout>
          </div>
        </div>
      </Page>
    )
  }

  return (
    <Page title={pageTitle} titleHidden width="measure">
      <div className={className}>
        <Explanation privacyNoticeHref={privacyNoticeHref} />

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <label htmlFor={inputId} className="font-sans text-md font-semibold text-text-primary">
              Your Age of Empires II profile id
            </label>
            <input
              ref={inputRef}
              id={inputId}
              inputMode="numeric"
              readOnly={state === 'submitting'}
              aria-describedby={fieldError ? `${helpId} ${errorId}` : helpId}
              aria-invalid={fieldError || undefined}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className={cx(
                'h-12 w-full max-w-xs rounded-control border bg-surface px-4 font-sans text-md text-text-primary',
                'transition-colors duration-120 ease-standard motion-reduce:duration-0',
                fieldError ? 'border-danger' : 'border-border-strong',
                focusRing,
              )}
            />
            <p id={helpId} className="font-sans text-sm text-text-secondary">
              This is the number Age of Empires II and its public leaderboards use to identify a
              player. It is the number in the address of a player's profile page. It is the only
              thing this form asks for.
            </p>
            {fieldError && (
              <p id={errorId} className="font-sans text-sm text-danger">
                Enter your numeric profile id — just the number.
              </p>
            )}
          </div>

          <div>
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={state === 'submitting'}
              loadingLabel="Recording your objection…"
            >
              Record my objection
            </Button>
          </div>
        </form>

        {state === 'rate-limited' && (
          <div className="mt-6">
            <Callout tone="warning" heading="Too many objections right now.">
              This form is busy. Please try again shortly.
            </Callout>
          </div>
        )}
        {state === 'failed' && (
          <div className="mt-6">
            <Callout tone="danger" heading="We could not record your objection.">
              Nothing was recorded. Try again when you are ready.
            </Callout>
          </div>
        )}
      </div>
    </Page>
  )
}

function Explanation({ privacyNoticeHref }: { privacyNoticeHref: string }) {
  return (
    <>
      <h2 className="font-display text-xl font-semibold text-text-primary md:text-2xl">
        {pageTitle}
      </h2>
      <div className="mt-4 flex flex-col gap-4 font-sans text-md text-text-primary">
        <p>
          You can appear in this service without ever having signed in to it. You played a match
          against someone who uses it, and Age of Empires II publishes that match. This page is for
          you, and it does not need an account.
        </p>
        <p>
          What we hold about you is the public part of that match — your profile id, alias, country,
          civilisation, team, colour, result, rating and rating change, all of it already published
          by the game on its own leaderboards. Inside the recording that other player's own game
          produced, your in-game actions and whatever was typed in chat are in the file too, because
          a recording cannot be split apart per player. We never capture your own point of view of a
          match.
        </p>
        <p>
          We hold it on the basis of our legitimate interest in saving these matches before the game
          deletes them (GDPR Art. 6-1-f), not on your consent. This form is how you object to that.
        </p>
        <p>
          When you object, we record it with the date. A person reads it and acts within 30 days,
          replacing your profile id in our match records with a pseudonymous one, so what remains no
          longer names you.
        </p>
        <p>
          Objecting does not delete the matches, which are other players' records too, and it does
          not delete or alter a recording. This is pseudonymisation, not anonymisation — the record
          still describes a game somebody played. To read the whole of what is held and why, see the{' '}
          <a href={privacyNoticeHref} className={inlineLinkClasses}>
            privacy notice
          </a>
          .
        </p>
      </div>
    </>
  )
}
