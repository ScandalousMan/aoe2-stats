import type { QueryClient } from '@tanstack/react-query'
import {
  Outlet,
  createRootRouteWithContext,
  useNavigate,
  useRouteContext,
  useRouterState,
} from '@tanstack/react-router'
import { Footer, SiteHeader, type SiteHeaderNavItem } from 'design-system'
import { type MeResponse, meQueryOptions } from '../lib/api'

// The web shell (T017). Three responsibilities live here and nowhere else:
//
// 1. Session bootstrap through `GET /api/me`, done once in `beforeLoad` and handed down as
//    router context — `session` — so every route below reads it from `Route.useRouteContext()`
//    instead of firing its own request. T036 (sign-in) and T037 (dashboard) key their redirects
//    off `context.session.authenticated` rather than re-deriving it.
// 2. The site chrome that is not any one route's business. The footer with the Microsoft
//    disclaimer is mounted here by T098a (constitution X), on every route, linking to the two
//    routes US5 built for a person's rights over their own data: `/privacy-notice` and `/object`.
// 3. `SiteHeader` (T442, packages/design-system/specs/site-header.md), mounted beside the footer
//    so primary navigation is present on every route too. Left of the footer, above `<Outlet>`,
//    never touching either — FR-012's anchor is the footer's disclaimer, unchanged below.
export interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  beforeLoad: async ({ context }): Promise<{ session: MeResponse }> => {
    // `ensureQueryData` reuses a cached, still-fresh session rather than refetching on every
    // navigation — `meQueryOptions.staleTime` is what governs that — and the query cache stays
    // the single source of truth: features that mutate the session (sign-in, sign-out, linking a
    // profile) invalidate `meQueryOptions.queryKey` instead of tracking a second copy.
    const session = await context.queryClient.ensureQueryData(meQueryOptions)
    return { session }
  },
  pendingComponent: RootPending,
  errorComponent: RootError,
  component: RootLayout,
})

// site-header.md §3a's canonical item set for 004, fixed here so the site's primary navigation is
// one decision rather than one per container. Every one of the five routes redirects an
// unauthenticated visitor to `/sign-in` (each route's own `beforeLoad`), so the signed-out call
// below passes `[]` instead of five links that all lead to the same place (§3a).
const NAV_ITEMS: readonly SiteHeaderNavItem[] = [
  { id: 'dashboard', label: 'Dashboard', href: '/dashboard' },
  { id: 'matches', label: 'Matches', href: '/matches' },
  { id: 'search', label: 'Search', href: '/search' },
  { id: 'favourites', label: 'Favourites', href: '/favourites' },
  { id: 'my-data', label: 'My data', href: '/privacy' },
]

// Exported for `__root.test.tsx`, which renders it directly rather than through a mounted
// `RouterProvider` (apps/web's vitest config deliberately omits the router plugin and the
// generated route tree — tests import feature modules and containers directly). `useRouteContext`
// is called directly, with `from: Route.id`, rather than through `Route.useRouteContext()`:
// the two are equivalent (`RouteApi`'s own implementation), and calling the hook this file already
// imports from `@tanstack/react-router` is what lets the test's `vi.mock` of that module reach it —
// `Route.useRouteContext` is bound inside the library's own module graph and a package-level mock
// cannot see it.
export function RootLayout() {
  const { session } = useRouteContext({ from: Route.id })
  const currentPath = useRouterState({ select: (state) => state.location.pathname })
  const navigate = useNavigate()

  return (
    <div className="flex min-h-svh flex-col">
      <SiteHeader
        items={session.authenticated ? NAV_ITEMS : []}
        currentPath={currentPath}
        onNavigate={(href) => void navigate({ to: href })}
      />
      {/* `id="main-content"` + `tabIndex={-1}` is SiteHeader's call-site obligation
       * (site-header.md §9): its skip link targets `#main-content` and moves focus here, not only
       * scroll — a skip link that scrolls without moving focus is the failure it is famous for. */}
      <main id="main-content" tabIndex={-1} className="flex-1">
        <Outlet />
      </main>
      <Footer privacyNoticeHref="/privacy-notice" objectionHref="/object" />
    </div>
  )
}

function RootPending() {
  return (
    <main className="flex min-h-svh items-center justify-center bg-background text-text-secondary">
      <p>Loading…</p>
    </main>
  )
}

function RootError() {
  // `GET /api/me` answers 200 even when signed out (contracts/http-api.md) — reaching this
  // component means the request itself failed (network, or the API being down), not an ordinary
  // signed-out visit. There is no design-system component to reach for yet (T035 has not landed),
  // so this stays plain text rather than inventing markup outside the token system.
  return (
    <main className="flex min-h-svh items-center justify-center bg-background text-text-primary">
      <p>aoe2-stats could not be reached. Please try again shortly.</p>
    </main>
  )
}
