import type { ChangeEvent, DragEvent, FormEvent } from 'react'
import { useEffect, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../Button'
import type { CalloutTone } from '../Callout'
import { Callout } from '../Callout'

// packages/design-system/specs/manual-upload.md

export type UploadUiState =
  | 'idle' // no file chosen — the resting/empty state
  | 'file-chosen' // a file is selected, not yet sent; SubmitButton live
  | 'uploading' // multipart POST in flight, then server-side validation
  | 'succeeded' // 200; OutcomeRegion/success, control collapses to the confirmation
  | 'invalid-replay' // 422 invalid_replay; OutcomeRegion/danger, retryable
  | 'wrong-match' // 404 not_found; OutcomeRegion/danger, retryable
  | 'already-archived' // 409 already_archived; OutcomeRegion/info, no retry — refresh instead
  | 'failed' // network or 5xx; OutcomeRegion/danger, retryable

// The states that render `OutcomeRegion` — every one of them the result of a settled attempt, not
// a resting phase of the picker itself (§5).
const outcomeStates = new Set<UploadUiState>([
  'succeeded',
  'invalid-replay',
  'wrong-match',
  'already-archived',
  'failed',
])

/** The endpoint's error envelope carries `code`, never a `message` to branch on (http-api.md's
 * error-envelope rule, restated in manual-upload.md's header). A `code` this component does not
 * recognise — including no code at all, a network failure or a 5xx — falls to `failed`. */
export interface UploadFailure {
  code?: 'invalid_replay' | 'not_found' | 'already_archived' | string
}

export interface UploadControlProps {
  /** The match this upload is filed under. Goes in the endpoint path; never trusted from the
   * file. Used here only to key this section's ids — the multipart request itself is `onUpload`'s
   * job, wired by the route (T084). */
  gameId: number
  /** POST /api/replays/{gameId}/upload, multipart. Resolves on 200; rejects with a typed reason
   * carrying the endpoint's `code` so the caller maps it to the right OutcomeRegion. */
  onUpload: (file: File) => Promise<void>
  /** Injected only by stories to pin a fixed state; the route never sets it. */
  initialState?: UploadUiState
  /** Delay before the loading label switches from "Uploading…" to "Checking the file…"
   * (`VALIDATING_LABEL_DELAY_MS` by default). Injected only by the `UploadingValidating` story,
   * set to `0` there so the switched label renders deterministically instead of racing the
   * visual harness's two-consecutive-frames screenshot trigger, which fires well inside the
   * production 1200 ms window. Production never sets this. */
  validatingLabelDelayMs?: number
  className?: string
}

// Interaction timing, not a design token (same category as `DataExportPanel`'s
// `POLL_INTERVAL_MS`): `onUpload` exposes no real transfer-progress signal, only a single
// `Promise<void>` spanning both the multipart send and the server's validation. §5 ("loading")
// asks for the label to switch once the bytes are believed sent, on to server-side validation —
// this is that switch, not a fake determinate progress bar pretending to know a duration it does
// not (§5's own words).
const VALIDATING_LABEL_DELAY_MS = 1_200

// The four codes `routers/replays.py` answers with, mapped to the state each drives (§3).
function stateForFailure(failure: unknown): UploadUiState {
  const code = (failure as UploadFailure | undefined)?.code
  if (code === 'invalid_replay') return 'invalid-replay'
  if (code === 'not_found') return 'wrong-match'
  if (code === 'already_archived') return 'already-archived'
  return 'failed'
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unitIndex]}`
}

// §4.4, normative. Copied verbatim; a change to what an outcome means changes here first.
const outcomeCopy: Partial<
  Record<UploadUiState, { tone: CalloutTone; heading: string; body: string }>
> = {
  succeeded: {
    tone: 'success',
    heading: 'Archived from your upload.',
    body: "This match's replay is stored now and marked as supplied by you. Nothing else about the match changed.",
  },
  'invalid-replay': {
    tone: 'danger',
    heading: 'That file is not a replay we can read.',
    body: 'Nothing was stored. Check it is the .aoe2record file for this match, taken straight from your saved games folder, then try again.',
  },
  'wrong-match': {
    tone: 'danger',
    heading: 'This file could not be filed to this match.',
    body: "Nothing was stored. Make sure it is this match's own recording and try again.",
  },
  'already-archived': {
    tone: 'info',
    heading: 'This match already has an archived replay.',
    body: 'Your file was not stored, and nothing was overwritten — the copy we already hold is untouched.',
  },
  failed: {
    tone: 'danger',
    heading: 'The upload did not go through.',
    body: 'Nothing was stored. This was a problem on our side or with the connection, not with your file. Try again when you are ready.',
  },
}

/** FR-029..FR-033: rescue a match whose automatic capture never got the replay, by adding the
 * file from the user's own machine. Presentational only — it takes `onUpload` and renders
 * whatever it resolves or rejects with; it never calls the API itself (T084's job). Rendered only
 * where no archive exists (manual-upload.md §2): mutually exclusive with `DownloadAction`. */
export function UploadControl({
  gameId,
  onUpload,
  initialState = 'idle',
  validatingLabelDelayMs = VALIDATING_LABEL_DELAY_MS,
  className,
}: UploadControlProps) {
  const [state, setState] = useState<UploadUiState>(initialState)
  // Story-only placeholder (same idiom as `DataExportPanel`'s seeded `downloadUrl`): `initialState`
  // pins a fixed frame without driving a real selection, but every state past `idle` presupposes a
  // file was already chosen, and the normative interface (§3) carries no `initialFile` prop.
  // Production never sets `initialState`, so this file is never seen outside Storybook.
  const [file, setFile] = useState<File | null>(() =>
    initialState === 'idle'
      ? null
      : new File(
          [new Uint8Array(2_150_000)],
          'MP Replay v101.103 @2026.08.30 091542 (4).aoe2record',
          { type: 'application/octet-stream' },
        ),
  )
  const [isDragOver, setIsDragOver] = useState(false)
  const [validating, setValidating] = useState(false)

  const inputRef = useRef<HTMLInputElement>(null)
  const outcomeHeadingRef = useRef<HTMLHeadingElement>(null)
  const prevStateRef = useRef(state)
  const validatingTimeoutRef = useRef<number | undefined>(undefined)
  const generationRef = useRef(0)

  const headingId = `upload-control-${gameId}-heading`

  useEffect(
    () => () => {
      if (validatingTimeoutRef.current !== undefined) {
        window.clearTimeout(validatingTimeoutRef.current)
      }
    },
    [],
  )

  // §9: "after a rejection, focus moves to the OutcomeRegion... so a keyboard or screen-reader
  // user learns the result and can act." Only on a live transition, never on first paint — a
  // story pinning `initialState` to an outcome must not steal focus the moment it mounts.
  useEffect(() => {
    if (state !== prevStateRef.current && outcomeStates.has(state)) {
      outcomeHeadingRef.current?.focus()
    }
    prevStateRef.current = state
  }, [state])

  function selectFile(next: File | null) {
    setFile(next)
    setState(next ? 'file-chosen' : 'idle')
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0] ?? null)
    // Allows choosing the same file again after a `Remove`.
    event.target.value = ''
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    if (state === 'uploading') return
    setIsDragOver(true)
  }

  function handleDragLeave() {
    setIsDragOver(false)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragOver(false)
    if (state === 'uploading') return
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) selectFile(dropped)
  }

  function handleRemove() {
    selectFile(null)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file || state === 'uploading') return

    generationRef.current += 1
    const generation = generationRef.current
    setState('uploading')
    setValidating(false)
    validatingTimeoutRef.current = window.setTimeout(() => {
      if (generation === generationRef.current) setValidating(true)
    }, validatingLabelDelayMs)

    onUpload(file)
      .then(() => {
        if (generation !== generationRef.current) return
        setState('succeeded')
      })
      .catch((error: unknown) => {
        if (generation !== generationRef.current) return
        setState(stateForFailure(error))
      })
      .finally(() => {
        if (validatingTimeoutRef.current !== undefined) {
          window.clearTimeout(validatingTimeoutRef.current)
        }
      })
  }

  function handleRefresh() {
    // §4.4 "already-archived": "reloads the match so `DownloadAction`... replaces this control."
    // The normative props (`gameId`, `onUpload`, `initialState`) carry no refresh callback, so a
    // full reload is the literal, self-contained way this presentational component delivers on
    // the copy it shows — the re-read the route performs afterwards is `DownloadAction`'s slot.
    window.location.reload()
  }

  const hasFile = file !== null
  const isUploading = state === 'uploading'
  // §5 "succeeded" and "already-archived" (info, "not a retry"): the picker collapses rather than
  // returning to a shape a user could act on again — there is nothing left to submit either way.
  const showPicker = state !== 'succeeded' && state !== 'already-archived'
  const outcome = outcomeCopy[state]

  return (
    <section aria-labelledby={headingId} className={cx('p-5 md:p-6', className)}>
      <h3 id={headingId} className="font-sans text-md font-semibold text-text-primary">
        Add the replay yourself
      </h3>
      <p className="mt-2 font-sans text-md text-text-primary">
        If you still have this match's file, add it and we will keep it exactly as it is, marked as
        one you supplied by hand.
      </p>
      <p className="mt-1 font-sans text-sm text-text-secondary">
        Look in your Age of Empires II saved games folder for the file whose name ends .aoe2record.
      </p>

      {showPicker && (
        <form onSubmit={handleSubmit} aria-busy={isUploading || undefined} className="mt-4">
          <div
            onDragOver={hasFile ? undefined : handleDragOver}
            onDragLeave={hasFile ? undefined : handleDragLeave}
            onDrop={hasFile ? undefined : handleDrop}
            className={cx(
              'flex flex-col items-center gap-3 rounded-lg border-2 border-dashed p-6 text-center',
              'transition-colors duration-120 ease-standard motion-reduce:duration-0',
              isDragOver && !hasFile
                ? 'border-focus-ring bg-surface-sunken'
                : 'border-border-strong bg-surface',
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".aoe2record"
              hidden
              tabIndex={-1}
              disabled={isUploading}
              onChange={handleInputChange}
            />

            {hasFile && file ? (
              <FileChip file={file} disabled={isUploading} onRemove={handleRemove} />
            ) : (
              <>
                <p className="font-sans text-md text-text-primary">
                  Drop the .aoe2record file here, or
                </p>
                <Button
                  type="button"
                  variant="secondary"
                  size="lg"
                  onClick={() => inputRef.current?.click()}
                >
                  Choose file
                </Button>
              </>
            )}
          </div>

          {hasFile && (
            <div className="mt-4">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={isUploading}
                loadingLabel={validating ? 'Checking the file…' : 'Uploading…'}
              >
                Upload and archive
              </Button>
            </div>
          )}
        </form>
      )}

      {outcome && (
        <div className="mt-4">
          <Callout
            tone={outcome.tone}
            heading={outcome.heading}
            headingLevel={4}
            headingRef={outcomeHeadingRef}
            actions={
              state === 'already-archived' ? (
                <Button variant="secondary" size="lg" onClick={handleRefresh}>
                  Refresh
                </Button>
              ) : undefined
            }
          >
            {outcome.body}
          </Callout>
        </div>
      )}
    </section>
  )
}

function FileChip({
  file,
  disabled,
  onRemove,
}: {
  file: File
  disabled: boolean
  onRemove: () => void
}) {
  return (
    <div className="flex w-full items-center justify-between gap-3 rounded-md border border-border bg-surface p-3">
      <div className="min-w-0 flex-1 text-left">
        {/* manual-upload.md §8: a long name wraps or middle-truncates, never cut without
         * recourse. `break-words` alone still overflows a name with no natural break point
         * (a long run of digits/dots with no space), so `[overflow-wrap:anywhere]` forces a
         * break inside such a run too — the name always stays within the chip's width. */}
        <p
          title={file.name}
          className="whitespace-normal break-words font-mono text-sm text-text-primary [overflow-wrap:anywhere]"
        >
          {file.name}
        </p>
        <p className="mt-2 font-sans text-sm text-text-secondary">{formatFileSize(file.size)}</p>
      </div>
      <Button type="button" variant="secondary" size="lg" disabled={disabled} onClick={onRemove}>
        Remove
      </Button>
    </div>
  )
}
