import { useEffect, useState } from 'react'

// Gap DS-5: no breakpoint tokens exist, so the specs name Tailwind's own defaults verbatim
// (`packages/design-system/specs/README.md`). This hook lets a component switch its DOM shape —
// never its styling alone — at one of those named breakpoints, for the one rule that cannot be
// expressed in CSS: "only one layout in the DOM at a time" (ProfileSummary's ratings table/cards).
const BREAKPOINTS = {
  md: 768,
  lg: 1024,
  xl: 1280,
} as const

export type Breakpoint = keyof typeof BREAKPOINTS

/** True once the viewport is at or above the named breakpoint. Defaults to `false` (the mobile,
 * card-first shape) until the first effect runs, so server-rendered and first-paint markup never
 * disagrees with a media query it hasn't evaluated yet. */
export function useBreakpoint(breakpoint: Breakpoint): boolean {
  const query = `(min-width: ${BREAKPOINTS[breakpoint]}px)`
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )

  useEffect(() => {
    const list = window.matchMedia(query)
    const onChange = () => setMatches(list.matches)
    onChange()
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }, [query])

  return matches
}
