// Tokens (T016) are exported for the rare consumer that isn't a Tailwind utility class (canvas,
// chart libraries, inline style). Every Tailwind class a component needs — `bg-accent`,
// `shadow-raised`, `p-3` — comes from `tokens/tailwind.css` instead, which every consumer of this
// package must import once (apps/web's global stylesheet, this package's own Storybook preview).
export * from '../tokens/generated/tokens'

// Shared primitives (T035, packages/design-system/specs/shared-primitives.md).
export * from './primitives/Button'
export * from './primitives/Callout'
export * from './primitives/Badge'
export * from './primitives/Skeleton'
export * from './primitives/Menu'
export * from './primitives/StatValue'
export * from './primitives/Dialog'
export * from './composites/CaptureStateBadge'
export * from './composites/MatchRow'
export * from './composites/MatchDetailPanel'

// Player search (T320, packages/design-system/specs/player-search.md).
export * from './composites/SearchBox'
export * from './composites/PlayerResultRow'

// Replay availability (T340, packages/design-system/specs/replay-availability.md).
export * from './composites/ReplayAvailabilityList'

// Favourites (T348, packages/design-system/specs/{favourite-toggle,favourites-list}.md).
export * from './composites/FavouriteToggle'
export * from './composites/FavouritesList'

// Analysis (T371, packages/design-system/specs/analysis-timeline.md).
export * from './composites/AnalysisTimeline'

// Screens (T035, packages/design-system/specs/{sign-in-screen,archival-control,profile-summary}.md).
// T036/T037 build the routes that mount these; this package builds what they compose.
// `ArchivalControl` was `ConsentStep` until T406 (constitution IX 4.0.0): the opt-in gate it drew
// is retired, and archival-control.md's amendment note records the rename and why.
export * from './screens/SignInScreen'
export * from './screens/ArchivalControl'
export * from './screens/ProfileSummary'

// Data rights (T095, packages/design-system/specs/{privacy-notice,privacy-data-rights,
// third-party-objection}.md). `apps/web/src/routes/{privacy,privacy-notice,object}.tsx` compose
// these; `object.tsx` sits outside the session (FR-039).
export * from './screens/PrivacyNotice'
export * from './screens/DataExportPanel'
export * from './screens/AccountErasurePanel'
export * from './screens/ThirdPartyObjectionForm'

// Manual upload (T083, packages/design-system/specs/manual-upload.md). Rendered by T084 inside
// `MatchDetailPanel`'s route, only where no archive exists — mutually exclusive with
// `DownloadAction`.
export * from './composites/UploadControl'

// Site chrome (T098, packages/design-system/specs/footer.md). Carries the Microsoft Game Content
// Usage Rules disclaimer (constitution X); mounted once in `apps/web/src/routes/__root.tsx` by
// T098a, so it renders on every route.
export * from './composites/Footer'

// Site chrome (T441, packages/design-system/specs/site-header.md). Primary navigation, present on
// every route; mounted beside `Footer` in `apps/web/src/routes/__root.tsx` by T442.
export * from './composites/SiteHeader'

// Theme (T534, research D11). `ThemeProvider` owns the stored override and the live
// system-preference subscription; `apps/web` mounts it once near the app root so `useTheme` is
// reachable everywhere, including `SiteHeader`'s three-state toggle (T535). The `localStorage`
// key it reads and writes is fixed by `apps/web/index.html`'s inline theme-resolution script
// (T533) and must not be renamed independently of it.
export * from './theme'

// Visual parity (T429, packages/design-system/specs/{civilisation-icon,map-thumbnail,
// player-colour-swatch}.md). Take an image URL as a prop; never import `packages/game-assets`.
// Consumed by `MatchRow`/`MatchDetailPanel` in T430/T431.
export * from './composites/CivilisationIcon'
export * from './composites/MapThumbnail'
export * from './composites/PlayerColourSwatch'
