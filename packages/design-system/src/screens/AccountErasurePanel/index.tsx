import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../../primitives/Button'
import { Callout } from '../../primitives/Callout'
import { Dialog } from '../../primitives/Dialog'
import { Link } from '../../primitives/Link'

// packages/design-system/specs/privacy-data-rights.md#AccountErasurePanel

export type ErasureUiState =
  | 'idle'
  | 'minting' // GET in flight — `EraseButton` busy before the dialog first opens, or, once it has,
  // a re-mint with `ConfirmAction` busy (`dialogHasOpened` tells the two apart, below)
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
 * `POST`. On the `POST`'s 403 (token expiry) the next confirm press re-mints, then erases, as one
 * in-flight run (T751). Owns its own dialog lifecycle; `initialState` exists only for stories. */
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
  // §5's `minting` covers two moments: the very first mint, fired by `EraseButton` before the
  // dialog has ever opened, and the re-mint §4.4 describes, fired from inside the open dialog
  // after a stale token expired. This flag tells them apart without a second state value;
  // `initialState === 'minting'` (the `Minting` story) starts it `false`, the pre-dialog case, as
  // no story needs the re-mint frame, which only exists inside a real `handleConfirm` retry.
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

  // T751 (§9): the run is the in-dialog re-mint plus the erase after it, `ConfirmAction` `loading`
  // through it. The checkbox and "Keep my account" are `disabled`, so neither may keep focus:
  // Safari leaves it there, Chromium drops it to `body`. Both are moved; a live control stays.
  const sectionRef = useRef<HTMLElement>(null)
  const running = state === 'erasing' || (state === 'minting' && dialogHasOpened)
  useLayoutEffect(() => {
    const dialog = sectionRef.current?.querySelector<HTMLElement>('[role="dialog"]')
    const held = document.activeElement
    if (!running || !dialog || (held && dialog.contains(held) && !held.matches(':disabled'))) return
    dialog.querySelector<HTMLElement>('[aria-busy]')?.focus()
  }, [running])
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

    // A 403 means the token aged out (`_ERASURE_CONFIRMATION_TTL`): the next `ConfirmAction`
    // press re-mints and at once retries the erase — one press, both steps (§4.4).
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
      ref={sectionRef}
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
        {/* §5 "loading": `minting` shows the EraseButton busy while the token is fetched — only
         * the very first mint, before the dialog has opened. "Always live" names the *disabled*
         * state, which `loading` is not. No loading label is specified for this frame, so
         * `Button`'s rule for an omitted one applies: the resting label stays, with the spinner. */}
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
            disabled: !acknowledged,
            loading: running,
            loadingLabel: 'Erasing your account…',
            onClick: handleConfirm,
          }}
          secondaryAction={{
            label: 'Keep my account',
            variant: 'secondary',
            disabled: running,
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
              disabled={running}
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
        {/* T674: was a local `<a>` copying `Link`'s `inline` recipe by hand — it stands alone in
            this paragraph, so it takes `standalone` (`specs/README.md`, "Minimum interactive
            footprint"), gaining that variant's block padding and a moved baseline, and carries
            the `data-variant` marker the touch-footprint route sweep reads. */}
        <Link href={homeHref} variant="standalone">
          Read the privacy notice
        </Link>
      </p>
    </section>
  )
}
