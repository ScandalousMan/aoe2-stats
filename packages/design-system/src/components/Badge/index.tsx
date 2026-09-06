import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/shared-primitives.md#Badge

export type BadgeVariant = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info'

export interface BadgeProps {
  variant?: BadgeVariant
  children: ReactNode
  className?: string
}

const variantClasses: Record<BadgeVariant, string> = {
  neutral: 'bg-surface-sunken text-text-secondary border border-border',
  // The README table is why light theme uses `accent-active` as text here rather than `accent`
  // itself: `accent` on `surface-raised` does not clear AA for normal-size text in the light
  // theme, and this is the one place `accent` appears as text at all.
  accent: 'bg-surface-raised text-accent-active dark:text-accent border border-transparent',
  // Tone variants (capture-state-badge.md §5): a neutral fill with a tone-coloured label, the same
  // shape `accent` already established, rather than a tone-tinted fill — which would be a new,
  // unmeasured pair. `success`/`warning`/`danger`/`info` all clear the 4.5:1 normal-text floor
  // against `surface-raised` in *both* themes with the same token (README's measured contrast
  // table), so — unlike `accent` — none of these four need a per-theme substitution.
  success: 'bg-surface-raised text-success border border-transparent',
  warning: 'bg-surface-raised text-warning border border-transparent',
  danger: 'bg-surface-raised text-danger border border-transparent',
  info: 'bg-surface-raised text-info border border-transparent',
}

/** A badge with no label renders nothing — it is never the only difference between two rows. */
export function Badge({ variant = 'neutral', children, className }: BadgeProps) {
  if (!children) return null

  return (
    <span
      className={cx(
        'inline-flex h-5 items-center rounded-pill px-2 font-sans text-xs font-semibold tracking-wide',
        variantClasses[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
