import { type ReactNode, useId } from 'react'
import { cx } from '../../lib/cx'
import { createRowLinkClickHandler } from '../../lib/rowLink'
import { Skeleton } from '../Skeleton'

// packages/design-system/specs/structural-tier.md §10 (T546, FR-026, FR-019, SC-009).
// contracts/005-design-system-foundations/structural-tier.md: `Table` owns column semantics,
// numeric-column alignment, its one overflow rule and its surface class — the caller never writes
// a `<table>` element, a `<th>` or a `<td>` directly. This file is the whole of that ownership.
//
// The overflow rule, decided once here rather than by each caller: when the table is wider than
// its container, the table's own scroll region scrolls horizontally and the page never does. The
// region is clipped at its own `rounded-panel` frame with no gradient or fade cue (any of those is
// a texture across the numbers in the last column, which README rule 1 forbids), and it is a
// labelled, focusable `role="region"` so a keyboard user can reach and operate the scroll — the
// only reason a non-interactive box may take focus. Columns are ordered identity-first by the
// caller (`columns[0]` is always the row's `<th scope="row">`), so the column that gets clipped at
// a narrow width is always the least identifying one, never the row's name.
//
// Numeric columns render through `type-numeric`, which carries `font-variant-numeric:
// tabular-nums` on the role itself rather than inheriting it from the font family being
// coincidentally monospaced — alignment survives a change of `font.family.mono` (SC-009).

export type TableDensity = 'dense' | 'prose'

/** A two-value vocabulary, deliberately closed (structural-tier.md §10 "Variants and sizes"): an
 * alignment a caller could invent is an alignment two tables would disagree about. `numeric`
 * right-aligns the column, header included, and renders its cells through `type-numeric`. */
export type TableColumnAlign = 'text' | 'numeric'

/** The eight-entry state vocabulary collapses to four distinct renderings for `Table`
 * (structural-tier.md §10 "States"): `hover`, `focus-visible` and `active` are row-link states
 * decided by CSS and the browser, never a prop, and `disabled` never applies to a table (a
 * greyed table is unreadable and still on screen — staleness is a `Callout` above it, not a
 * `Table` state). What remains is a prop: the rows are showing, arriving, failed to arrive, or
 * came back with nothing in them. */
export type TableStatus = 'default' | 'loading' | 'error' | 'empty'

export interface TableColumn<Row> {
  /** Stable key: the React key for this column's cells and part of its accessible id. Never
   * derived from `header`, which may change independently (e.g. a localised label). */
  key: string
  header: ReactNode
  /** `text` (default) or `numeric`. See `TableColumnAlign`. */
  align?: TableColumnAlign
  /** Renders one row's value for this column. `columns[0]`'s `render` fills the row's
   * `<th scope="row">` identity cell; every other column fills a `<td>`. */
  render: (row: Row) => ReactNode
}

export interface TableProps<Row> {
  /** Always rendered — a `<table>` with no name is a table a screen-reader user cannot ask about
   * (structural-tier.md §10 anatomy: "required"). Hide it visually with `captionHidden` when a
   * heading above the table already names it; there is no third option. */
  caption: ReactNode
  captionHidden?: boolean
  /** `dense` (default), a data-comparison surface, or `prose`, a table inside continuous reading
   * content (README "Surface density", structural-tier.md §3). Row padding and body typography
   * follow from this one prop; a caller may not set either directly. */
  density?: TableDensity
  /** Identity-first: the first column is the row's `<th scope="row">` (structural-tier.md §10
   * "Columns are ordered identity-first"). At least one column is required. */
  columns: [TableColumn<Row>, ...TableColumn<Row>[]]
  /** Ignored while `status` is `loading`, `error` or `empty`. */
  rows: Row[]
  getRowKey: (row: Row) => string | number
  /** Present only for a row that is a real, whole-row link (structural-tier.md §10 "hover"): the
   * identity cell's content is wrapped in a stretched `<a href>` covering the row, and the row
   * highlights on hover and on press. A row with no href here never highlights at rest — a
   * highlight that leads nowhere invites a click that does nothing. Return `undefined` for a row
   * that is not a link while others in the same table are. */
  getRowHref?: (row: Row) => string | undefined
  /** Wired to the caller's own router, mirroring `MatchRow`'s `onNavigate` seam (`lib/rowLink.ts`)
   * — the row stays a real anchor with no dependency on any particular router, and a plain click
   * is the only one this component ever intercepts; every modified click falls through to native
   * anchor handling. */
  onNavigate?: (href: string) => void
  status?: TableStatus
  /** `loading` only. Skeleton rows matching the footprint of the rows about to arrive, at a
   * caller-supplied count (structural-tier.md §10 "loading"). Defaults to 5. */
  skeletonRowCount?: number
  /** `error` only: the caption and the column headers are retained and this fills one cell
   * spanning every column (structural-tier.md §10 "error") — typically one `ErrorState` with a
   * retry. `Table` does not import `ErrorState` itself: the words a failure should use are a fact
   * only the caller has, the same reason `StatValue` never invents its own empty-reason text. */
  errorContent?: ReactNode
  /** `empty` only: the caption and the column headers are retained and this fills one cell
   * spanning every column (structural-tier.md §10 "empty") — typically one `EmptyState` with its
   * sentence. Never a bare header over nothing. */
  emptyContent?: ReactNode
  /** Optional `<tfoot>` row — a totals or summary row, spanning every column. */
  footer?: ReactNode
  className?: string
}

const focusRing =
  'outline-none focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

// structural-tier.md §10 "The header row is quieter than the data": `type-body` at `text-sm`,
// weight `normal`, in `text-secondary` — fixed regardless of `density`, because the relationship
// this rule protects (the data draws the first fixation, not its label) does not change with how
// tightly the rows are packed.
const headerCellBase = 'type-body px-4 py-3 text-sm font-normal text-text-secondary'

// structural-tier.md §3 "Density applied": cell block padding `space-3` (`py-3`) at `dense`,
// `space-4` (`py-4`) at `prose`; cell inline padding `space-4` (`px-4`) between columns and from
// the frame on both edges, at every density.
const bodyCellClassByDensity: Record<TableDensity, string> = {
  dense: 'type-body px-4 py-3 text-sm text-text-primary',
  prose: 'type-body px-4 py-4 text-md text-text-primary',
}

const numericCellClassByDensity: Record<TableDensity, string> = {
  dense: 'type-numeric px-4 py-3 text-right text-sm text-text-primary',
  prose: 'type-numeric px-4 py-4 text-right text-md text-text-primary',
}

// A loading skeleton row must be the same height as a real one (structural-tier.md §10's own
// acceptance criterion — "overlay the two and the header does not move"): `h-5` (1.25rem/20px)
// matches `text-sm`'s own line-height at `dense`, `h-6` (1.5rem/24px) matches `text-md`'s at
// `prose` (`tokens/font.json` `size.sm`/`size.md`).
const skeletonHeightByDensity: Record<TableDensity, string> = {
  dense: 'h-5',
  prose: 'h-6',
}

const skeletonCellPaddingByDensity: Record<TableDensity, string> = {
  dense: 'px-4 py-3',
  prose: 'px-4 py-4',
}

export function Table<Row>({
  caption,
  captionHidden = false,
  density = 'dense',
  columns,
  rows,
  getRowKey,
  getRowHref,
  onNavigate,
  status = 'default',
  skeletonRowCount = 5,
  errorContent,
  emptyContent,
  footer,
  className,
}: TableProps<Row>) {
  const captionId = useId()
  const [identityColumn, ...restColumns] = columns
  const columnCount = columns.length

  return (
    <div
      role="region"
      aria-labelledby={captionId}
      aria-busy={status === 'loading' || undefined}
      tabIndex={0}
      className={cx(
        'overflow-auto rounded-panel border border-border bg-surface',
        focusRing,
        className,
      )}
    >
      <table className="w-full border-collapse">
        <caption
          id={captionId}
          className={cx(
            'type-body px-4 py-3 text-left text-sm text-text-secondary',
            captionHidden && 'sr-only',
          )}
        >
          {caption}
        </caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cx(
                  headerCellBase,
                  column.align === 'numeric' ? 'text-right' : 'text-left',
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>

        {status === 'loading' && (
          <tbody>
            {Array.from({ length: skeletonRowCount }, (_, index) => (
              <tr key={index} className="border-b border-border">
                {columns.map((column) => (
                  <td key={column.key} className={skeletonCellPaddingByDensity[density]}>
                    <Skeleton
                      variant="block"
                      className={cx(skeletonHeightByDensity[density], 'w-full')}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        )}

        {status === 'error' && (
          <tbody>
            <tr>
              {/* No `py` here: `errorContent` is `ErrorState` (structural-tier.md §10), which
               * already carries its own vertical rhythm (`py-6`) — stacking Table's own on top of
               * it would be a second, uncoordinated padding decision for the same edge. */}
              <td colSpan={columnCount} className="px-4">
                {errorContent}
              </td>
            </tr>
          </tbody>
        )}

        {status === 'empty' && (
          <tbody>
            <tr>
              {/* Same reasoning: `emptyContent` is `EmptyState`, already `py-8`. */}
              <td colSpan={columnCount} className="px-4">
                {emptyContent}
              </td>
            </tr>
          </tbody>
        )}

        {status === 'default' && (
          <tbody>
            {rows.map((row) => {
              const href = getRowHref?.(row)
              return (
                <tr
                  key={getRowKey(row)}
                  className={cx(
                    'relative border-b border-border',
                    href && 'hover:bg-surface-sunken active:bg-surface-sunken',
                  )}
                >
                  <th
                    scope="row"
                    className={cx(bodyCellClassByDensity[density], 'text-left font-normal')}
                  >
                    {href ? (
                      // structural-tier.md §10 "hover"/"active": the row's single link lives in
                      // its identity cell and is stretched over the whole row with
                      // `after:absolute after:inset-0` against the row's own `relative` — the
                      // standard "one link, whole row clickable" technique this design system
                      // already ships in `MatchRow`, kept exactly one focus stop per row.
                      <a
                        href={href}
                        onClick={createRowLinkClickHandler(href, onNavigate)}
                        className={cx('static after:absolute after:inset-0', focusRing)}
                      >
                        {identityColumn.render(row)}
                      </a>
                    ) : (
                      identityColumn.render(row)
                    )}
                  </th>
                  {restColumns.map((column) => (
                    <td
                      key={column.key}
                      className={
                        column.align === 'numeric'
                          ? numericCellClassByDensity[density]
                          : bodyCellClassByDensity[density]
                      }
                    >
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        )}

        {footer && (
          <tfoot>
            <tr className="border-t border-border">
              <td
                colSpan={columnCount}
                className={cx(
                  density === 'prose' ? 'type-supporting' : 'type-body',
                  'px-4 py-3 text-sm text-text-secondary',
                )}
              >
                {footer}
              </td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
