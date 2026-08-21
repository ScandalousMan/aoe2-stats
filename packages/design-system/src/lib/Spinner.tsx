import { cx } from './cx'

// Internal loading glyph shared by Button and Menu's item loading state (shared-primitives.md).
// Not exported from the package: it is not one of the six specified primitives, only a detail of
// how two of them render their own `loading` state, so it carries no spec or story of its own.
//
// Sizing rides on gap DS-7 (no icon-size token): the interim there is "size from the adjacent
// font-size token (1em)", so the glyph is `1em` square and inherits whatever text size surrounds
// it. Rotation duration has no token either — closest named motion duration is `duration.slow`
// (320ms) — so the keyframe reads the CSS custom property directly instead of a literal, the same
// way every generated token does, and stops under `prefers-reduced-motion` per the README's
// reduced-motion rule.
export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      className={cx(
        'h-[1em] w-[1em] motion-safe:animate-[spin_var(--ds-motion-duration-slow)_linear_infinite]',
        className,
      )}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
