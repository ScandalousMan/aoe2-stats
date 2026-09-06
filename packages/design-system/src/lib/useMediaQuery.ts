import { useEffect, useState } from 'react'
import { breakpointTokens } from '../../tokens/generated/tokens'

// Closes DS-5 (T513, research D4): the breakpoint numbers live in `tokens/breakpoint.json` and
// are generated into `breakpointTokens` alongside Tailwind's own `--breakpoint-*` mapping in
// `preset.css`, so this hook's structural decision and the stylesheet's `md:`/`lg:`/`xl:` variants
// derive from the one source and cannot disagree. This hook lets a component switch its DOM shape
// — never its styling alone — at one of those named breakpoints, for the one rule that cannot be
// expressed in CSS: "only one layout in the DOM at a time" (ProfileSummary's ratings table/cards).
// `sm` exists in the token family for Tailwind's `sm:` variant call sites; this hook does not need
// it because none of them change DOM shape.
export type Breakpoint = Exclude<keyof typeof breakpointTokens, 'sm'>

/** True once the viewport is at or above the named breakpoint. Defaults to `false` (the mobile,
 * card-first shape) until the first effect runs, so server-rendered and first-paint markup never
 * disagrees with a media query it hasn't evaluated yet. */
export function useBreakpoint(breakpoint: Breakpoint): boolean {
  const query = `(min-width: ${breakpointTokens[breakpoint]}px)`
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
