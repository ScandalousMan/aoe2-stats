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

// Player search (T320, packages/design-system/specs/player-search.md).
export * from './components/SearchBox'
export * from './components/PlayerResultRow'

// Replay availability (T340, packages/design-system/specs/replay-availability.md).
export * from './components/ReplayAvailabilityList'

// Favourites (T348, packages/design-system/specs/{favourite-toggle,favourites-list}.md).
export * from './components/FavouriteToggle'
export * from './components/FavouritesList'

// Analysis (T371, packages/design-system/specs/analysis-timeline.md).
export * from './components/AnalysisTimeline'

// Screens (T035, packages/design-system/specs/{sign-in-screen,archival-control,profile-summary}.md).
// T036/T037 build the routes that mount these; this package builds what they compose.
// `ArchivalControl` was `ConsentStep` until T406 (constitution IX 4.0.0): the opt-in gate it drew
// is retired, and archival-control.md's amendment note records the rename and why.
export * from './components/SignInScreen'
export * from './components/ArchivalControl'
export * from './components/ProfileSummary'

// Data rights (T095, packages/design-system/specs/{privacy-notice,privacy-data-rights,
// third-party-objection}.md). `apps/web/src/routes/{privacy,privacy-notice,object}.tsx` compose
// these; `object.tsx` sits outside the session (FR-039).
export * from './components/PrivacyNotice'
export * from './components/DataExportPanel'
export * from './components/AccountErasurePanel'
export * from './components/ThirdPartyObjectionForm'
