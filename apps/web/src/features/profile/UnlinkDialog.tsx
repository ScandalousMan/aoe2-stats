import { Callout, Dialog } from 'design-system'

// FR-004's confirming half: the preview call already happened (`api.ts`'s `previewUnlink`,
// wired in `DashboardContainer.tsx`) and its consequence for archived replays is what this dialog
// shows *before* the confirming `DELETE …?confirm=true` is ever issued — never in the same step.
// Built on `design-system`'s `Dialog` primitive (T035b), which replaced the copy of `ConsentStep`'s
// `WithdrawConfirmDialog` chrome — focus trap, Escape handling, backdrop and boxed-surface classes
// — this module used to carry directly.

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
  return (
    <Dialog
      heading={`Unlink ${alias}?`}
      primaryAction={{
        label: 'Unlink this profile',
        onClick: onConfirm,
        disabled: pending,
        loading: pending,
        loadingLabel: 'Unlinking…',
      }}
      secondaryAction={{ label: 'Keep it linked', onClick: onCancel, disabled: pending }}
    >
      {archivedReplayCount > 0 &&
        `You have ${archivedReplayCount} replay${archivedReplayCount === 1 ? '' : 's'} archived from this profile. `}
      {consequenceMessage}
      {error && (
        <div className="mt-4">
          <Callout tone="danger" heading="We could not unlink this profile" headingLevel={3}>
            {error}
          </Callout>
        </div>
      )}
    </Dialog>
  )
}
