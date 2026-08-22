// Tokens (T016) are exported for the rare consumer that isn't a Tailwind utility class (canvas,
// chart libraries, inline style). Every Tailwind class a component needs — `bg-accent`,
// `shadow-raised`, `p-3` — comes from `tokens/tailwind.css` instead, which every consumer of this
// package must import once (apps/web's global stylesheet, this package's own Storybook preview).
export * from '../tokens/generated/tokens'

// Shared primitives (T035, packages/design-system/specs/shared-primitives.md).
export * from './components/Button'
export * from './components/Callout'
export * from './components/Badge'
export * from './components/Skeleton'
export * from './components/Menu'
export * from './components/StatValue'
export * from './components/Dialog'
export * from './components/CaptureStateBadge'
export * from './components/MatchRow'
export * from './components/MatchDetailPanel'

// Screens (T035, packages/design-system/specs/{sign-in-screen,consent-step,profile-summary}.md).
// T036/T037 build the routes that mount these; this package builds what they compose.
export * from './components/SignInScreen'
export * from './components/ConsentStep'
export * from './components/ProfileSummary'
