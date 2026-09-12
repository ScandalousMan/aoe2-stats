import { useEffect, useRef, useState } from 'react'
import { cx } from '../../lib/cx'
import { Button } from '../../primitives/Button'
import { Callout } from '../../primitives/Callout'
import { Skeleton } from '../../primitives/Skeleton'

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
    <section aria-labelledby="data-export-panel-heading" className={cx('max-w-measure', className)}>
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
                  'inline-flex min-h-11 w-fit items-center justify-center rounded-control bg-accent px-6 font-sans text-md font-semibold text-accent-contrast',
                  'transition-colors duration-120 ease-standard motion-reduce:duration-0',
                  // Fifth-pass review remediation (M2), corrected sixth-pass: `hover`/`active`
                  // used to be a pure fill swap (`accent-hover` / `accent-active`, the same
                  // three-rung ramp `Button`'s `primary` variant already carries) with no shape
                  // signal on top. The fifth-pass fix reached for `active:outline-2
                  // active:outline-offset-2`, an outward ring meant to sit clear of the inward
                  // focus ring below at the opposite offset — but it never painted: this anchor
                  // composes `outline-none` too, and `tailwind.css`'s restoration of
                  // `--tw-outline-style` fires only under `:focus-visible`, so the `:active` rule
                  // resolved to `outline-style: none` at runtime (`Button/index.tsx`'s own comment
                  // records the trap this repeats). Corrected the same way as `Button`'s bordered
                  // variants: `active:ring-2 active:ring-offset-2 active:ring-offset-transparent
                  // active:ring-accent-contrast` — Tailwind's box-shadow-backed `ring` utility,
                  // which never reads `--tw-outline-style`. `ring-offset-transparent` keeps the
                  // 2px gap see-through rather than painting a solid colour into it, so this anchor
                  // never has to know what surface (`Callout`'s `surface-raised`, here) sits behind
                  // it. `box-shadow`, like `outline`, never participates in layout, so this stays
                  // reflow-free regardless of the surrounding `Callout`'s own layout — and because
                  // it paints through a different CSS property than the focus ring's `outline`
                  // below, a keyboard press (`:active` and `:focus-visible` matching at once) can
                  // now actually show both at once, which two rules on the same `outline` property
                  // never could.
                  'hover:bg-accent-hover active:bg-accent-active active:ring-2 active:ring-offset-2 active:ring-offset-transparent active:ring-accent-contrast',
                  // Inward ring, in `accent-contrast` — this link fills with `accent`, and
                  // `focus-ring` cannot clear 3:1 against both the page and an accent fill at
                  // once (packages/design-system/specs/color-tokens.md §5, DS-10).
                  //
                  // T586: `-outline-offset-2` on this 2px-wide ring painted exactly the outermost
                  // two pixels of the border box — flush with the edge, so its outer side sat on
                  // the page at 1.00-1.42:1, the same invisible-on-the-page defect §5 exists to
                  // prevent. The inward `outline-offset-ring-inset` (`-4px`, `border.json`'s
                  // `ring-offset-inset`, admitted in GOVERNANCE.md's token admission Record after
                  // this offset shipped as a bare `-outline-offset-4` literal — the same rendered
                  // value, now named) leaves a 2px band of `accent` fill between the ring and the
                  // edge on every side. Checked against this link's own smallest rendered size
                  // (`min-h-11 px-6`): the ring's inner edge sits 4px inside the border box, far
                  // short of the 24px horizontal padding around the label, so it never comes near
                  // the text. Guarded by tokens/accent-contrast-ring.test.mjs.
                  'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring-inset focus-visible:outline-accent-contrast',
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
              // T561 (FR-018/FR-019): reachable at 375, `size="lg"` not the `md` default.
              <Button variant="secondary" size="lg" onClick={handleRequestExport}>
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
