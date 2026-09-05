import type { ReactNode } from 'react'
import { useId } from 'react'
import { cx } from '../../lib/cx'
import { createRowLinkClickHandler } from '../../lib/rowLink'
import { useBreakpoint } from '../../lib/useMediaQuery'
import { Button } from '../Button'
import { Callout } from '../Callout'
import { FavouriteToggle } from '../FavouriteToggle'
import { Skeleton } from '../Skeleton'
import type { StatValueDelta, StatValueStatus } from '../StatValue'
import { StatValue } from '../StatValue'

// packages/design-system/specs/favourites-list.md

export interface FavouriteStandingData {
  /** `'empty'` for a favourite who has never played a ranked ladder (§4). A stale-but-known
   * standing (the source could not be refreshed) stays `'default'` with `secondaryLine` stating
   * when it was measured and that the refresh failed — `StatValue`'s own rule, restated in §4,
   * never a fourth rendering of the number. */
  status?: StatValueStatus
  label: ReactNode
  value?: ReactNode
  /** The rank (`"#3"`), a **figure**, not a unit label — `FavouriteRow` composes it into
   * `StatValue`'s own `value` slot rather than its `unit` slot (§10 bullet 2, §6 "mono for
   * Standing's figures"), because `StatValue.unit` renders `font-sans text-secondary`
   * (`shared-primitives.md#StatValue`), right for a genuine unit and wrong for a number that must
   * align digit-for-digit with the rating above it. */
  unit?: ReactNode
  delta?: StatValueDelta
  secondaryLine?: ReactNode
}

export interface FavouriteEntryData {
  /** React list key and the id `onRemove` is called with — never rendered. */
  profileId: string
  /** The profile route. `FavouritesList` never invents this path (§2), the same discipline
   * `PlayerResultRowData.href` and `MatchRowData.href` already carry. */
  href: string
  alias: string
  /** Bracketed beside the alias when present, absent — never blank-filled — otherwise (§4). */
  clan?: string | null
  /** Absent — never blank-filled — when unknown (§4). */
  country?: string | null
  standing: FavouriteStandingData
  /** True while this entry's own `DELETE` is in flight (`FavouriteToggle`'s own `loading`, §5). */
  removing?: boolean
}

export interface FavouritesListProps {
  /** Whether a session exists. `false` replaces the whole list with a sign-in prompt that
   * preserves the caller's place (§5a, FR-015) — favourites are private, and there are none to
   * show without a session. Defaults to `true`: the ordinary case is a signed-in visitor. */
  authenticated?: boolean
  /** The real sign-in destination, carrying `/favourites` as the return location (§5a). Required
   * whenever `authenticated` is `false`. */
  signInHref?: string
  /** Wires the profile links and the sign-in link into the caller's own router (T388's pattern),
   * the identical seam `PlayerResultRow.onNavigate` and `MatchRow.onNavigate` already offer. */
  onNavigate?: (href: string) => void
  /** Before `GET /api/favourites` has answered. Takes priority over `error` and `entries`. */
  loading?: boolean
  /** How many `Skeleton` rows to show while `loading` — the last known count, or `3` when none is
   * known yet (§5). */
  loadingRowCount?: number
  /** `GET /api/favourites` failed while signed in — distinct from the signed-out `401` above
   * (§5). Takes priority over `entries`. */
  error?: boolean
  onRetry?: () => void
  entries?: FavouriteEntryData[]
  /** Issues `DELETE /api/favourites/{profile_id}` for one entry (FR-013, US5 scenario 2). */
  onRemove?: (profileId: string) => void
  className?: string
}

const EMPTY_ENTRIES: FavouriteEntryData[] = []

// §10 bullet 2, §6: "shows the rating and rank in `type-numeric`, aligning digit-for-digit down
// the column." Composing the rank inside `StatValue`'s own `value` slot — instead of its `unit`
// slot — lets it inherit that slot's `type-numeric font-semibold tracking-tight`
// (`shared-primitives.md#StatValue`) from its ancestor span; `type-numeric` is repeated explicitly
// on the rank's own span too, so the treatment holds even if `StatValue`'s value markup changes
// later, and so it is a directly assertable class rather than an inherited one. Only colour is
// overridden (`text-secondary`), the same distinction `unit` used to carry, now without giving up
// the `tabular-nums` alignment `StatValue`'s own figures depend on (research D7, FR-007): the rank
// is a measured figure compared down the column, not a unit label, so it takes `numeric`, never
// `machine` or `identifier`.
function renderStandingValue(standing: FavouriteStandingData): ReactNode {
  if (!standing.unit) return standing.value
  return (
    <>
      {standing.value}
      <span className="ml-2 type-numeric text-text-secondary">{standing.unit}</span>
    </>
  )
}

/** One place to find the players a signed-in user cares about again, without searching — each
 * entry showing its current standing and reaching the profile in one step (FR-014), with a remove
 * control right there too (FR-013). See `packages/design-system/specs/favourites-list.md`. */
export function FavouritesList({
  authenticated = true,
  signInHref,
  onNavigate,
  loading = false,
  loadingRowCount = 3,
  error = false,
  onRetry,
  entries = EMPTY_ENTRIES,
  onRemove,
  className,
}: FavouritesListProps) {
  const headingId = useId()

  return (
    <section aria-labelledby={headingId} className={cx('flex flex-col', className)}>
      <h1 id={headingId} className="font-sans text-2xl font-semibold text-text-primary">
        Favourites
      </h1>

      <div className="mt-6">
        {!authenticated ? (
          <SignedOutState signInHref={signInHref} onNavigate={onNavigate} />
        ) : loading ? (
          <LoadingState count={loadingRowCount} />
        ) : error ? (
          <ErrorState onRetry={onRetry} />
        ) : entries.length === 0 ? (
          <EmptyState />
        ) : (
          <ul className="flex flex-col gap-3 md:gap-0">
            {entries.map((entry) => (
              <FavouriteRow
                key={entry.profileId}
                entry={entry}
                onNavigate={onNavigate}
                onRemove={onRemove}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

// §5a — favourites are private (FR-015): no favourited state and no player render before a
// session exists. Mirrors `favourite-toggle.md` §5a's own signed-out behaviour.
function SignedOutState({
  signInHref,
  onNavigate,
}: {
  signInHref?: string
  onNavigate?: (href: string) => void
}) {
  const href = signInHref ?? '#'
  return (
    <Callout
      tone="info"
      heading="Sign in to see the players you've favourited."
      actions={
        <Button variant="primary" href={href} onClick={createRowLinkClickHandler(href, onNavigate)}>
          Sign in
        </Button>
      }
    />
  )
}

// §5 "loading" — footprint matches `FavouriteRow`'s own, so loading-to-loaded shows no reflow.
function LoadingState({ count }: { count: number }) {
  const rowCount = Math.max(count, 0)
  return (
    <ul className="flex flex-col gap-3 md:gap-4">
      {Array.from({ length: rowCount }, (_, index) => (
        <li key={index}>
          <Skeleton variant="block" className="h-20 w-full rounded-panel md:h-14" />
        </li>
      ))}
    </ul>
  )
}

// §5 "error" — distinct from the empty state below in both tone and copy, and from the signed-out
// state above: this is a signed-in visitor whose request failed, not one who has none yet.
function ErrorState({ onRetry }: { onRetry?: () => void }) {
  return (
    <Callout
      tone="danger"
      heading="We could not load your favourites. Try again."
      actions={
        <Button variant="primary" onClick={onRetry}>
          Try again
        </Button>
      }
    />
  )
}

// §5 "empty" — nothing went wrong; the copy points at the exact route to fill the list.
function EmptyState() {
  return (
    <Callout tone="info" heading="You have not added any favourites yet.">
      Open any player's profile and choose &ldquo;Add to favourites&rdquo;.
    </Callout>
  )
}

function FavouriteRow({
  entry,
  onNavigate,
  onRemove,
}: {
  entry: FavouriteEntryData
  onNavigate?: (href: string) => void
  onRemove?: (profileId: string) => void
}) {
  // §8: 375 is a stacked full-width card with the remove control at touch size beneath; from 768
  // the row sits on one line with the remove control intrinsic-width, right-aligned. One DOM
  // shape throughout — restructured at the breakpoint, never two shapes with one hidden.
  const isMd = useBreakpoint('md')

  return (
    <li
      className={cx(
        'flex flex-col gap-4 rounded-panel border border-border bg-surface p-4',
        isMd &&
          'flex-row items-center justify-between gap-4 rounded-none border-x-0 border-t-0 border-b bg-transparent px-0 py-3',
      )}
    >
      <a
        href={entry.href}
        onClick={createRowLinkClickHandler(entry.href, onNavigate)}
        className={cx(
          'flex flex-1 flex-col gap-1 rounded-control',
          'md:flex-row md:items-center md:justify-between md:gap-4',
          'transition-colors duration-120 ease-standard hover:bg-surface-sunken',
          'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring',
        )}
      >
        <span className="flex flex-wrap items-baseline gap-2">
          <span className="font-sans text-sm font-semibold text-text-primary">{entry.alias}</span>
          {entry.clan && (
            <span className="font-sans text-xs text-text-secondary">[{entry.clan}]</span>
          )}
          {entry.country && (
            <span className="font-sans text-xs text-text-secondary">{entry.country}</span>
          )}
        </span>
        <StatValue
          variant="compact"
          label={entry.standing.label}
          status={entry.standing.status}
          value={renderStandingValue(entry.standing)}
          delta={entry.standing.delta}
          secondaryLine={entry.standing.secondaryLine}
        />
      </a>
      <div className={cx(isMd && 'shrink-0')}>
        <FavouriteToggle
          favourited
          authenticated
          loading={entry.removing}
          size="lg"
          onRemove={() => onRemove?.(entry.profileId)}
          className={cx(!isMd && 'w-full')}
        />
      </div>
    </li>
  )
}
