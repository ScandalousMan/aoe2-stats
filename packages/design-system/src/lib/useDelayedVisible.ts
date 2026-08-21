import { useEffect, useState } from 'react'

// Shared by `Skeleton` and anything that shows one (`StatValue`, `SignInScreen`'s `returning`
// variant, `ProfileSummary`). "Do not render before 200 ms (`motion.duration.normal`) — a
// skeleton that flashes is worse than a brief blank" (shared-primitives.md, §Skeleton).
const DELAY_MS = 200

/** Starts `false` and flips to `true` after `motion.duration.normal`, so a loading state that
 * resolves faster than a person can register never paints a pulse at all. */
export function useDelayedVisible(delayMs = DELAY_MS): boolean {
  const [visible, setVisible] = useState(delayMs === 0)

  useEffect(() => {
    if (delayMs === 0) return
    const timer = window.setTimeout(() => setVisible(true), delayMs)
    return () => window.clearTimeout(timer)
  }, [delayMs])

  return visible
}
