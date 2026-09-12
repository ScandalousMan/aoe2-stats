import { useEffect, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../../primitives/Button'
import { Callout } from '../../primitives/Callout'
import { Dialog } from '../../primitives/Dialog'

// packages/design-system/specs/privacy-data-rights.md#AccountErasurePanel

export type ErasureUiState =
  | 'idle'
  | 'minting' // GET in flight — `EraseButton` busy before the dialog first opens, or a silent
  // re-mint once it already has (`dialogHasOpened` tells the two apart, below)
  | 'confirming' // dialog open, token held, waiting for the acknowledged confirm
  | 'erasing' // POST in flight
  | 'confirmation-expired' // 403 from POST: the token aged out; dialog says so
  | 'failed' // POST failed for another reason; dialog says so
  | 'erased' // terminal; the route shows ErasedScreen, not this panel

export interface AccountErasurePanelProps {
  /** GET /api/privacy/erase. Mints the confirmation token; changes nothing. */
  onRequestConfirmation: () => Promise<{ confirmationToken: string }>
  /** POST /api/privacy/erase with the token. Resolves when the account is gone. */
  onErase: (confirmationToken: string) => Promise<void>
  /** Called once `onErase` resolves — the caller (route) swaps this panel for `ErasedScreen`. */
  onErased?: () => void
  /** Injected only by stories; the route never sets it. */
  initialState?: ErasureUiState
  className?: string
}

// T589: `outline-offset-ring` (`border.json`'s `ring-offset`, 2px) names the offset this ring
// shipped as a bare `outline-offset-2` literal — same rendered offset, now a named token.
const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

/** FR-037: irreversible account erasure, gated by a real two-step confirmation — a `GET` mints a
 * short-lived token, then a `Dialog` with a required "I understand" checkbox gates the destructive
 * `POST`. On the `POST`'s 403 (token expiry) the panel silently re-mints and retries once the user
 * confirms again. Owns its own dialog lifecycle; `initialState` exists only for stories. */
export function AccountErasurePanel({
  onRequestConfirmation,
  onErase,
  onErased,
  initialState = 'idle',
  className,
}: AccountErasurePanelProps) {
  const [state, setState] = useState<ErasureUiState>(initialState)
  const [confirmationToken, setConfirmationToken] = useState<string | undefined>(undefined)
  const [acknowledged, setAcknowledged] = useState(false)
  // §5's `minting` names two different moments the same state value covers: the very first mint,
  // triggered by `EraseButton` before `ConfirmDialog` has ever opened ("minting shows the
  // `EraseButton` busy while the token is fetched" — before the dialog exists to hold anything
  // busy itself), and the silent re-mint §4.4 describes, fired from inside an already-open dialog
  // when a stale token expired. Both are `state === 'minting'`; this flag is what tells them
  // apart without a second state value the vocabulary does not need. `initialState === 'minting'`
  // (the `Minting` story) starts `false` — the pre-dialog case — deliberately: no story ever needs
  // to open straight into the re-mint frame, which only exists as a transient step inside a
  // real `handleConfirm` retry.
  const [dialogHasOpened, setDialogHasOpened] = useState(false)

  // Guards every `.then()`/`.catch()` below against setting state once this panel has unmounted
  // — the terminal `erased` transition, in particular, can race an unmount the caller (route)
  // triggers from `onErased` itself.
  const mountedRef = useRef(true)
  useEffect(
    () => () => {
      mountedRef.current = false
    },
    [],
  )

  // The dialog is open for `minting` only once it has already opened once this cycle (the
  // in-dialog re-mint above) — the very first `minting`, fired from `EraseButton` on the page
  // itself, renders that button busy instead (below) and does not open `ConfirmDialog` early.
  const dialogOpen =
    (state === 'minting' && dialogHasOpened) ||
    state === 'confirming' ||
    state === 'erasing' ||
    state === 'confirmation-expired' ||
    state === 'failed'

  function openDialog() {
    setState('minting')
    onRequestConfirmation()
      .then(({ confirmationToken: token }) => {
        if (!mountedRef.current) return
        setConfirmationToken(token)
        setDialogHasOpened(true)
        setState('confirming')
      })
      .catch(() => {
        if (!mountedRef.current) return
        // `failed` is also a `dialogOpen` state (unconditionally, above); it must open the
        // dialog here even though this is the very first mint and it never reached `confirming`,
        // because `DialogFailure` (§4.4/§5) is what tells the reader the mint itself failed — the
        // one `failed`/`confirmation-expired` case not reached through an already-open dialog.
        setDialogHasOpened(true)
        setState('failed')
      })
  }

  function closeDialog() {
    setState('idle')
    setConfirmationToken(undefined)
    setAcknowledged(false)
    setDialogHasOpened(false)
  }

  function performErase(token: string) {
    setState('erasing')
    onErase(token)
      .then(() => {
        if (!mountedRef.current) return
        setState('erased')
        onErased?.()
      })
      .catch((error: unknown) => {
        if (!mountedRef.current) return
        const status = (error as { status?: number } | undefined)?.status
        if (status === 403) {
          setConfirmationToken(undefined)
          setState('confirmation-expired')
        } else {
          setState('failed')
        }
      })
  }

  function handleConfirm() {
    if (!acknowledged) return

    // A 403 means the token aged out (module docstring, `_ERASURE_CONFIRMATION_TTL`): the very
    // next `ConfirmAction` press silently re-mints and immediately retries the erase with the
    // fresh token — one press does both steps, so "the user simply confirms once more" (§4.4) is
    // literally true rather than a second, separate mint-only step.
    if (confirmationToken === undefined) {
      setState('minting')
      onRequestConfirmation()
        .then(({ confirmationToken: token }) => {
          if (!mountedRef.current) return
          setConfirmationToken(token)
          performErase(token)
        })
        .catch(() => {
          if (mountedRef.current) setState('failed')
        })
      return
    }

    performErase(confirmationToken)
  }

  if (state === 'erased') return null

  return (
    <section
      aria-labelledby="account-erasure-panel-heading"
      className={cx('max-w-measure', className)}
    >
      <h2
        id="account-erasure-panel-heading"
        className="font-display text-xl font-semibold text-text-primary"
      >
        Erase your account
      </h2>

      <p className="mt-3 font-sans text-md text-text-primary">
        This permanently deletes your account and everything attached to it.{' '}
        <span className="font-medium">
          There is no undo, and no backup we can restore you from.
        </span>{' '}
        Read what stays and what goes before you start.
      </p>

      <div className="mt-6 flex flex-col gap-6 font-sans text-md text-text-primary">
        <div>
          <p className="font-semibold">What is deleted, for good:</p>
          <ul className="mt-3 flex flex-col gap-3">
            <li>Your account, and your Steam sign-ins.</li>
            <li>Your session — you are signed out on your very next request.</li>
            <li>Every profile you linked, and your favourites.</li>
            <li>
              Every recording of yours we have archived — the files in storage, not just the rows
              that point at them — and the records of who opened them.
            </li>
          </ul>
        </div>
        <div>
          <p className="font-semibold">What survives, and why:</p>
          <ul className="mt-3 flex flex-col gap-3">
            <li>
              The matches themselves stay, with your profile id replaced by a pseudonymous one, so
              the other players' records stay correct.{' '}
              <span className="font-medium">That is pseudonymisation, not anonymisation:</span> we
              are not claiming the result stops being about anyone.
            </li>
            <li>
              The record that you asked to be erased stays, without the link to your account,
              because it is the proof the erasure happened.
            </li>
            <li>
              A recording kept for an analysis you asked us to publish stays, because the published
              conclusion has to remain checkable. Erasing your account removes the record that you
              were the one who asked; it does not delete that recording.
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-8">
        {/* §5 "loading — ... minting shows the EraseButton busy while the token is fetched" —
         * only the very first mint, before ConfirmDialog has ever opened (`dialogOpen`'s own
         * comment above); the disabled-state paragraph's "the EraseButton on the page is always
         * live" names the *disabled* state, a different category `Button`'s `loading` does not
         * fall into. No loading label is given for this frame anywhere in §4.3/§4.4's normative
         * copy, so none is supplied — `Button`'s own rule for an omitted one applies: the resting
         * label stays, with the spinner beside it. */}
        <Button
          variant="destructive"
          size="lg"
          onClick={openDialog}
          loading={state === 'minting' && !dialogHasOpened}
        >
          Erase my account
        </Button>
      </div>

      {dialogOpen && (
        <Dialog
          heading="This permanently erases your account"
          primaryAction={{
            label: 'Erase my account permanently',
            variant: 'destructive',
            disabled: !acknowledged || state === 'minting' || state === 'erasing',
            loading: state === 'erasing',
            loadingLabel: 'Erasing your account…',
            onClick: handleConfirm,
          }}
          secondaryAction={{
            label: 'Keep my account',
            variant: 'secondary',
            disabled: state === 'erasing',
            onClick: closeDialog,
          }}
        >
          <p>
            This cannot be undone. When you confirm, your account, your Steam sign-ins, your
            session, your linked profiles, your favourites and your archived recordings — the files
            included — are deleted. Your match records stay, with your profile id replaced by a
            pseudonymous one. There is no undo and no backup.
          </p>

          {state === 'confirmation-expired' && (
            <div className="mt-4">
              <Callout tone="danger" heading="Your confirmation expired." headingLevel={3}>
                For your safety a confirmation is only good for a few minutes. Confirm again to
                erase your account.
              </Callout>
            </div>
          )}
          {state === 'failed' && (
            <div className="mt-4">
              <Callout tone="danger" heading="We could not erase your account." headingLevel={3}>
                Nothing was changed, and your account is still here. Try again when you are ready.
              </Callout>
            </div>
          )}

          <label className="mt-6 flex min-h-11 items-center gap-2 font-sans text-md text-text-primary">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
              className={cx('h-5 w-5 shrink-0', focusRing)}
            />
            <span>I understand this cannot be undone.</span>
          </label>
        </Dialog>
      )}
    </section>
  )
}

/** The terminal state the route swaps in once `onErase` resolves (privacy-data-rights.md §4.4).
 * Attempts no authenticated fetch of any kind — there is no longer an account to fetch. */
export function ErasedScreen({ homeHref }: { homeHref: string }) {
  return (
    <section aria-labelledby="erased-screen-heading" className="max-w-measure">
      <h2
        id="erased-screen-heading"
        className="font-display text-xl font-semibold text-text-primary"
      >
        Your account has been erased.
      </h2>
      <p className="mt-3 font-sans text-md text-text-primary">
        Everything attached to it is gone, and you are signed out.
      </p>
      <p className="mt-4 font-sans text-md text-text-primary">
        Your match records remain with a pseudonymous id in place of yours, and the record that you
        asked to be erased remains without any link to you — both are described in the privacy
        notice. There is nothing left here to sign in to.
      </p>
      <p className="mt-6 font-sans text-md">
        <a
          href={homeHref}
          className={cx(
            'text-link underline transition-colors duration-120 ease-standard motion-reduce:duration-0',
            // Fourth-pass review remediation (FR-037): hover and active shared `link-hover` with
            // no other signal, so a press was not distinguishable from a hover in a still image.
            // `active:underline-offset-4` gives press its own frame without a fill — the same fix
            // now shared with `Link`'s `inline` variant, `Footer`, `PrivacyNotice` and
            // `ThirdPartyObjectionForm`'s own copies of this pattern.
            'hover:text-link-hover active:text-link-hover active:underline-offset-4',
            focusRing,
          )}
        >
          Read the privacy notice
        </a>
      </p>
    </section>
  )
}
