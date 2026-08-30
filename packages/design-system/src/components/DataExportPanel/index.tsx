import { useEffect, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/privacy-data-rights.md#DataExportPanel

export type ExportStatus = { status: 'queued' } | { status: 'completed'; downloadUrl: string }

export type ExportUiState = 'idle' | 'requesting' | 'preparing' | 'ready' | 'failed'

export interface DataExportPanelProps {
  /** POST /api/privacy/export. Resolves to the job id the panel then polls. */
  onRequestExport: () => Promise<{ id: string }>
  /** GET /api/privacy/export/{id}. Called on an interval while status is "queued". */
  onPollExport: (id: string) => Promise<ExportStatus>
  /** Injected only by stories to render a fixed state; the route never sets it. */
  initialState?: ExportUiState
  className?: string
}

// Interaction timing, not a design token (same category as SearchBox's `debounceMs`): how often
// this panel re-polls `GET /api/privacy/export/{id}` while a job reads "queued".
const POLL_INTERVAL_MS = 2_000
// Skeleton's own 10s ceiling (shared-primitives.md): after this long still "preparing", the panel
// treats it as a failure rather than pulsing forever.
const PREPARING_TIMEOUT_MS = 10_000

/** FR-036: request a complete export archive and, once it is ready, download it. Owns its own
 * request/poll lifecycle — `initialState` exists only so a story can render one fixed frame
 * without driving real promises. No "past exports" list: the API exposes no such endpoint (§3), so
 * a reload always returns this panel to `idle`. */
export function DataExportPanel({
  onRequestExport,
  onPollExport,
  initialState = 'idle',
  className,
}: DataExportPanelProps) {
  const [state, setState] = useState<ExportUiState>(initialState)
  // Story-only placeholder: production never sets `initialState`, so this fallback href is never
  // seen outside Storybook — the real flow always sets a real signed URL from `onPollExport`.
  const [downloadUrl, setDownloadUrl] = useState<string | undefined>(
    initialState === 'ready' ? '#' : undefined,
  )

  const pollTimeoutRef = useRef<number | undefined>(undefined)
  const preparingDeadlineRef = useRef<number | undefined>(undefined)
  const generationRef = useRef(0)

  useEffect(
    () => () => {
      if (pollTimeoutRef.current !== undefined) window.clearTimeout(pollTimeoutRef.current)
    },
    [],
  )

  function pollOnce(jobId: string, generation: number) {
    onPollExport(jobId)
      .then((status) => {
        if (generation !== generationRef.current) return
        if (status.status === 'completed') {
          setDownloadUrl(status.downloadUrl)
          setState('ready')
          return
        }
        if (Date.now() >= (preparingDeadlineRef.current ?? 0)) {
          setState('failed')
          return
        }
        pollTimeoutRef.current = window.setTimeout(
          () => pollOnce(jobId, generation),
          POLL_INTERVAL_MS,
        )
      })
      .catch(() => {
        if (generation !== generationRef.current) return
        setState('failed')
      })
  }

  function handleRequestExport() {
    generationRef.current += 1
    const generation = generationRef.current
    if (pollTimeoutRef.current !== undefined) window.clearTimeout(pollTimeoutRef.current)

    setState('requesting')
    onRequestExport()
      .then(({ id }) => {
        if (generation !== generationRef.current) return
        setState('preparing')
        preparingDeadlineRef.current = Date.now() + PREPARING_TIMEOUT_MS
        pollOnce(id, generation)
      })
      .catch(() => {
        if (generation !== generationRef.current) return
        setState('failed')
      })
  }

  const requestPending = state === 'requesting' || state === 'preparing'

  return (
    <section aria-labelledby="data-export-panel-heading" className={cx('max-w-prose', className)}>
      <h2
        id="data-export-panel-heading"
        className="font-display text-xl font-semibold text-text-primary"
      >
        Get a copy of your data
      </h2>

      <p className="mt-3 font-sans text-md text-text-primary">
        We build a single archive containing your account record, every Steam sign-in you have made,
        every profile you have ever linked, the match records and per-player rows for those
        profiles, your archived recordings as their original files, your favourites, and the matches
        you asked us to analyse. It does not include cached search results, which are keyed to
        nobody, and it does not include the internal counters that rate-limit the API.
      </p>

      <div className="mt-6">
        <Button
          variant="secondary"
          size="lg"
          disabled={requestPending}
          loading={requestPending}
          loadingLabel="Preparing your export…"
          onClick={handleRequestExport}
        >
          Export my data
        </Button>
      </div>

      {state === 'preparing' && (
        <div className="mt-6">
          <Callout tone="info" heading="Your export is being prepared.">
            <p>
              This usually takes a moment. Keep this tab open until the download link appears — the
              link is not saved, so leaving this page means starting a new export.
            </p>
            <Skeleton variant="block" className="h-10 w-48" />
          </Callout>
        </div>
      )}

      {state === 'ready' && downloadUrl && (
        <div className="mt-6">
          <Callout tone="success" heading="Your export is ready.">
            <div className="flex flex-col gap-2">
              <a
                href={downloadUrl}
                download
                className={cx(
                  'inline-flex min-h-11 w-fit items-center justify-center rounded-md bg-accent px-6 font-sans text-md font-semibold text-accent-contrast',
                  'transition-colors duration-120 ease-standard motion-reduce:duration-0',
                  'hover:bg-accent-hover active:bg-accent-active',
                  'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                )}
              >
                Download the archive
              </a>
              <p className="font-sans text-sm text-text-secondary">
                This link stops working after a short while. If it has expired, start a new export
                above.
              </p>
            </div>
          </Callout>
        </div>
      )}

      {state === 'failed' && (
        <div className="mt-6">
          <Callout
            tone="danger"
            heading="We could not build your export"
            actions={
              <Button variant="secondary" onClick={handleRequestExport}>
                Try again
              </Button>
            }
          >
            Nothing was changed. Try again when you are ready.
          </Callout>
        </div>
      )}
    </section>
  )
}
