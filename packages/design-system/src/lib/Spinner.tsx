import { cx } from './cx'

// Internal loading glyph shared by Button and Menu's item loading state (shared-primitives.md).
// Not exported from the package: it is not one of the six specified primitives, only a detail of
// how two of them render their own `loading` state, so it carries no spec or story of its own.
//
// T528: closes the icon half of gap DS-7 (already closed system-wide, feature 004/T517) for this
// call site specifically. `icon.json`'s seven steps have no entry meaning "inherit the surrounding
// text's own size" — every step is a fixed value — so there is no exact token for a glyph that
// used to ride `1em` beside `Button`'s label (`text-sm` at 14px on `md`, `text-md` at 16px on
// `lg`). That absence is itself the finding: `icon-sm` (16px) is the nearest reasonable step,
// exact for `Button`'s `lg` size and 2px over on `md`. Rotation now reads the real `animate-spin`
// utility (`motion.json`'s `animation.spin` group, T516/T512) instead of an arbitrary bracket
// reading the duration variable by hand; `motion-safe:` still gates it so it stops on its resting
// frame under `prefers-reduced-motion` per the README's reduced-motion rule.
export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      className={cx('icon-sm motion-safe:animate-spin', className)}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
