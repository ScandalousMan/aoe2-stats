import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'

// packages/design-system/specs/shared-primitives.md#Badge

export type BadgeVariant = 'neutral' | 'accent'

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
}

/** A badge with no label renders nothing — it is never the only difference between two rows. */
export function Badge({ variant = 'neutral', children, className }: BadgeProps) {
  if (!children) return null

  return (
    <span
      className={cx(
        'inline-flex h-5 items-center rounded-full px-2 font-sans text-xs font-semibold tracking-wide',
        variantClasses[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
