// GENERATED FILE — do not hand-edit.
// Source: packages/design-system/tokens/*.json
// Regenerate with `pnpm --filter design-system tokens:build`.
// Every value below is a CSS var() reference, not a literal — the resolved value depends on the
// active theme (light by default, dark under [data-theme='dark']). See tokens/generated/tokens.css.

export const colorTokens = {
  'background': 'var(--ds-color-background)',
  'surface': 'var(--ds-color-surface)',
  'surface-raised': 'var(--ds-color-surface-raised)',
  'surface-sunken': 'var(--ds-color-surface-sunken)',
  'border': 'var(--ds-color-border)',
  'border-strong': 'var(--ds-color-border-strong)',
  'text-primary': 'var(--ds-color-text-primary)',
  'text-secondary': 'var(--ds-color-text-secondary)',
  'text-disabled': 'var(--ds-color-text-disabled)',
  'text-inverse': 'var(--ds-color-text-inverse)',
  'accent': 'var(--ds-color-accent)',
  'accent-hover': 'var(--ds-color-accent-hover)',
  'accent-active': 'var(--ds-color-accent-active)',
  'accent-contrast': 'var(--ds-color-accent-contrast)',
  'success': 'var(--ds-color-success)',
  'success-contrast': 'var(--ds-color-success-contrast)',
  'warning': 'var(--ds-color-warning)',
  'warning-contrast': 'var(--ds-color-warning-contrast)',
  'danger': 'var(--ds-color-danger)',
  'danger-contrast': 'var(--ds-color-danger-contrast)',
  'info': 'var(--ds-color-info)',
  'info-contrast': 'var(--ds-color-info-contrast)',
  'focus-ring': 'var(--ds-color-focus-ring)',
  'overlay': 'var(--ds-color-overlay)',
} as const
export type ColorToken = keyof typeof colorTokens

export const spaceTokens = {
  '0': 'var(--ds-space-0)',
  '1': 'var(--ds-space-1)',
  '2': 'var(--ds-space-2)',
  '3': 'var(--ds-space-3)',
  '4': 'var(--ds-space-4)',
  '5': 'var(--ds-space-5)',
  '6': 'var(--ds-space-6)',
  '8': 'var(--ds-space-8)',
  '10': 'var(--ds-space-10)',
  '12': 'var(--ds-space-12)',
  '16': 'var(--ds-space-16)',
  '20': 'var(--ds-space-20)',
  '24': 'var(--ds-space-24)',
  '32': 'var(--ds-space-32)',
  'unit': 'var(--ds-space-unit)',
  'px': 'var(--ds-space-px)',
} as const
export type SpaceToken = keyof typeof spaceTokens

export const radiusTokens = {
  'none': 'var(--ds-radius-none)',
  'sm': 'var(--ds-radius-sm)',
  'md': 'var(--ds-radius-md)',
  'lg': 'var(--ds-radius-lg)',
  'xl': 'var(--ds-radius-xl)',
  '2xl': 'var(--ds-radius-2xl)',
  'full': 'var(--ds-radius-full)',
} as const
export type RadiusToken = keyof typeof radiusTokens

export const elevationTokens = {
  'none': 'var(--ds-elevation-none)',
  'raised': 'var(--ds-elevation-raised)',
  'overlay': 'var(--ds-elevation-overlay)',
  'modal': 'var(--ds-elevation-modal)',
} as const
export type ElevationToken = keyof typeof elevationTokens

export const fontTokens = {
  family: {
    'sans': 'var(--ds-font-family-sans)',
    'display': 'var(--ds-font-family-display)',
    'mono': 'var(--ds-font-family-mono)',
  },
  size: {
    'xs': 'var(--ds-font-size-xs)',
    'sm': 'var(--ds-font-size-sm)',
    'md': 'var(--ds-font-size-md)',
    'lg': 'var(--ds-font-size-lg)',
    'xl': 'var(--ds-font-size-xl)',
    '2xl': 'var(--ds-font-size-2xl)',
    '3xl': 'var(--ds-font-size-3xl)',
    '4xl': 'var(--ds-font-size-4xl)',
  },
  weight: {
    'normal': 'var(--ds-font-weight-normal)',
    'medium': 'var(--ds-font-weight-medium)',
    'semibold': 'var(--ds-font-weight-semibold)',
    'bold': 'var(--ds-font-weight-bold)',
  },
  tracking: {
    'tight': 'var(--ds-font-tracking-tight)',
    'normal': 'var(--ds-font-tracking-normal)',
    'wide': 'var(--ds-font-tracking-wide)',
  },
} as const

export const motionTokens = {
  duration: {
    'instant': 'var(--ds-motion-duration-instant)',
    'fast': 'var(--ds-motion-duration-fast)',
    'normal': 'var(--ds-motion-duration-normal)',
    'slow': 'var(--ds-motion-duration-slow)',
  },
  easing: {
    'standard': 'var(--ds-motion-easing-standard)',
    'decelerate': 'var(--ds-motion-easing-decelerate)',
    'accelerate': 'var(--ds-motion-easing-accelerate)',
  },
} as const
