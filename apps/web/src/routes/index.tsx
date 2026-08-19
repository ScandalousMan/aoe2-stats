import { createFileRoute } from '@tanstack/react-router'

// Placeholder landing route. Replaced by the sign-in / dashboard flow in T036 and T037.
export const Route = createFileRoute('/')({
  component: Index,
})

function Index() {
  return (
    <main className="flex min-h-svh items-center justify-center">
      <p>aoe2-stats</p>
    </main>
  )
}
