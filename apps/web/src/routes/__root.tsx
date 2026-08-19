import { Outlet, createRootRoute } from '@tanstack/react-router'

// Scaffold only (T003). The real shell — session bootstrap through `GET /api/me`, the
// query client, the footer with its Microsoft disclaimer — is built by T017 and T098a.
export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  return <Outlet />
}
