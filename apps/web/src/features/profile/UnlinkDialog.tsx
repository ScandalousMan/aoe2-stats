import { useEffect, useRef } from 'react'
import { Button, Callout } from 'design-system'

// FR-004's confirming half: the preview call already happened (`api.ts`'s `previewUnlink`,
// wired in `DashboardContainer.tsx`) and its consequence for archived replays is what this dialog
// shows *before* the confirming `DELETE …?confirm=true` is ever issued — never in the same step.
//
// No shared `Dialog` primitive exists in `packages/design-system` yet (`shared-primitives.md` has
// none, and `ConsentStep`'s own `withdraw-confirm` dialog is unexported markup private to that
// component, hardcoded to consent copy). This task's scope forbids editing
// `packages/design-system/`, so this composes `Button` and `Callout` — both already tokened,
// exported primitives — directly, reproducing the exact accessible dialog shell
// `ConsentStep`'s `WithdrawConfirmDialog` already established (same token classes: `bg-overlay`,
// `bg-surface`, `shadow-modal`, the bottom-sheet-below-`md` / centred-dialog-from-`md` split) so
// this doesn't invent a second visual language for the one real dialog this route needs. Reported
// alongside this task: a generic `Dialog` shared primitive would remove this duplication, and
// T095's erasure confirmation is going to want the same shape again.

export interface UnlinkDialogProps {
  alias: string
  archivedReplayCount: number
  consequenceMessage: string
  pending: boolean
  error?: string
  onConfirm: () => void
  onCancel: () => void
}

export function UnlinkDialog({
  alias,
  archivedReplayCount,
  consequenceMessage,
  pending,
  error,
  onConfirm,
  onCancel,
}: UnlinkDialogProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        // Escape cancels, never confirms — the same discipline `ConsentStep`'s
        // `withdraw-confirm` keeps for the same reason (consent-step.md §9): the accidental key
        // must never be the one that takes the destructive path.
        event.preventDefault()
        onCancel()
      }
      if (event.key === 'Tab' && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, a[href], input, [tabindex]:not([tabindex="-1"])',
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onCancel])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-overlay md:items-center">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="unlink-confirm-heading"
        className="w-full max-w-sm rounded-t-xl bg-surface p-6 shadow-modal md:rounded-xl"
      >
        <h2
          id="unlink-confirm-heading"
          ref={headingRef}
          tabIndex={-1}
          className="font-display text-xl font-semibold text-text-primary"
        >
          Unlink {alias}?
        </h2>
        <p className="mt-3 font-sans text-sm text-text-secondary">
          {archivedReplayCount > 0 &&
            `You have ${archivedReplayCount} replay${archivedReplayCount === 1 ? '' : 's'} archived from this profile. `}
          {consequenceMessage}
        </p>

        {error && (
          <div className="mt-4">
            <Callout tone="danger" heading="We could not unlink this profile" headingLevel={3}>
              {error}
            </Callout>
          </div>
        )}

        <div className="mt-6 flex flex-col gap-3 md:flex-row">
          <Button
            variant="destructive"
            size="lg"
            disabled={pending}
            loading={pending}
            loadingLabel="Unlinking…"
            onClick={onConfirm}
            className="w-full md:w-auto"
          >
            Unlink this profile
          </Button>
          <Button
            variant="secondary"
            size="lg"
            disabled={pending}
            onClick={onCancel}
            className="w-full md:w-auto"
          >
            Keep it linked
          </Button>
        </div>
      </div>
    </div>
  )
}
