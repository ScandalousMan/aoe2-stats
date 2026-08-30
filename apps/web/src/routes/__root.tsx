import type { QueryClient } from '@tanstack/react-query'
import { Outlet, createRootRouteWithContext } from '@tanstack/react-router'
import { Footer } from 'design-system'
import { type MeResponse, meQueryOptions } from '../lib/api'

// The web shell (T017). Two responsibilities live here and nowhere else:
//
// 1. Session bootstrap through `GET /api/me`, done once in `beforeLoad` and handed down as
//    router context — `session` — so every route below reads it from `Route.useRouteContext()`
//    instead of firing its own request. T036 (sign-in) and T037 (dashboard) key their redirects
//    off `context.session.authenticated` rather than re-deriving it.
// 2. The site chrome that is not any one route's business. The footer with the Microsoft
//    disclaimer is mounted here by T098a (constitution X), on every route, linking to the two
//    routes US5 built for a person's rights over their own data: `/privacy-notice` and `/object`.
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

function RootLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <div className="flex-1">
        <Outlet />
      </div>
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
