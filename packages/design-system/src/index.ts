// The package's deliberate public surface (FR-027, T542): everything intended for use is
// reachable from here, and everything unreachable is intended to be — not "everything a
// component happens to use is exported". Organised by tier (`primitives/`, `composites/`,
// `screens/`, T540) so a new primitive from `structural-tier.md` (T543-T548) has an obvious
// section to join.

// Tokens (T016) are exported for the rare consumer that isn't a Tailwind utility class (canvas,
// chart libraries, inline style). Every Tailwind class a component needs — `bg-accent`,
// `shadow-raised`, `p-3` — comes from `tokens/tailwind.css` instead, which every consumer of this
// package must import once (apps/web's global stylesheet, this package's own Storybook preview).
export * from '../tokens/generated/tokens'

// ---------------------------------------------------------------------------------------------
// Primitives (packages/design-system/src/primitives/)
// ---------------------------------------------------------------------------------------------

// Shared primitives (T035, packages/design-system/specs/shared-primitives.md).
export * from './primitives/Button'
export * from './primitives/Callout'
export * from './primitives/Badge'
export * from './primitives/Skeleton'
export * from './primitives/Menu'
export * from './primitives/StatValue'
export * from './primitives/Dialog'

// Tooltip (T456, packages/design-system/specs/tooltip.md). Built as `CountryFlag`'s hover-reveal
// mechanism but general-purpose — README's rule 4 names it the one sanctioned way any component
// carries a fact that is not permanently painted beside it — and it was never added here when it
// shipped (T542 resolution): a finished, spec'd, tested primitive with no consumer yet is
// unreachable by omission, not by decision, and the omission is fixed. Published.
export * from './primitives/Tooltip'

// The structural tier (T543-T548, packages/design-system/specs/structural-tier.md). `Page` is the
// first of the nine: the single main landmark, the content width and the page padding a route must
// not declare for itself (FR-020, FR-021).
export * from './primitives/Page'

// ---------------------------------------------------------------------------------------------
// Composites (packages/design-system/src/composites/)
// ---------------------------------------------------------------------------------------------

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

// Visual parity (T429, packages/design-system/specs/{civilisation-icon,map-thumbnail,
// player-colour-swatch}.md). Take an image URL as a prop; never import `packages/game-assets`.
// Consumed by `MatchRow`/`MatchDetailPanel` in T430/T431.
export * from './composites/CivilisationIcon'
export * from './composites/MapThumbnail'
export * from './composites/PlayerColourSwatch'

// Player identity (T436, packages/design-system/specs/{country-flag,player-avatar}.md). Built
// for `ProfileSummary` and, until now, reachable only through it — the same omission as
// `Tooltip`'s above, and the same T542 resolution: both are finished, spec'd, tested composites
// in the same family as the visual-parity trio directly above (an image with a documented
// fallback, no consumer outside the design system yet), so the same call applies. Published.
export * from './composites/CountryFlag'
export * from './composites/PlayerAvatar'

// ---------------------------------------------------------------------------------------------
// Screens (packages/design-system/src/screens/)
// ---------------------------------------------------------------------------------------------

// T035, packages/design-system/specs/{sign-in-screen,archival-control,profile-summary}.md.
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

// ---------------------------------------------------------------------------------------------
// Theme (packages/design-system/src/theme/)
// ---------------------------------------------------------------------------------------------

// T534, research D11. `ThemeProvider` owns the stored override and the live system-preference
// subscription; `apps/web` mounts it once near the app root so `useTheme` is reachable
// everywhere, including `SiteHeader`'s three-state toggle (T535). The `localStorage` key it
// reads and writes is fixed by `apps/web/index.html`'s inline theme-resolution script (T533) and
// must not be renamed independently of it.
export * from './theme'
