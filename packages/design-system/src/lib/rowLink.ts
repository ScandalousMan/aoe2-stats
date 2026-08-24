import type { MouseEvent } from 'react'

// Shared by `PlayerResultRow` and `MatchRow` (T388): both render their whole row as a single
// `<a href>` — a real link, so it keeps working with no JavaScript at all, is reachable by
// keyboard, and supports every native anchor gesture (open in new tab, copy link, middle-click).
// Neither component knows about this app's router (packages/design-system has no dependency on
// one, and is exercised standalone in Storybook), so instead of forcing a full document reload on
// every plain click inside a TanStack Router SPA, the row accepts an optional `onNavigate` callback
// that the caller wires to its own router. This mirrors every other seam in this design system
// (`onSelectProfile`, `onRetry`, `onSearch`, …) rather than inventing a router-specific prop.

/** True only for the click this component may safely turn into a client-side navigation: the
 * primary mouse button, no modifier held, and nothing upstream already called
 * `preventDefault()` on it. Every other click — a modified click (new tab/window), a
 * middle-click, or a nested control that has already handled the event — is left entirely to the
 * browser's native `<a href>` handling. */
export function isPlainLeftClick(event: MouseEvent): boolean {
  return (
    !event.defaultPrevented &&
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  )
}

/** Builds the `onClick` handler for a row's own `<a href>`: intercepts a plain left click into
 * `onNavigate`, and does nothing at all — letting the anchor's native `href` handle it — for
 * every other click or when the caller supplied no `onNavigate`. */
export function createRowLinkClickHandler(
  href: string,
  onNavigate: ((href: string) => void) | undefined,
) {
  return (event: MouseEvent<HTMLAnchorElement>) => {
    if (!onNavigate || !isPlainLeftClick(event)) return
    event.preventDefault()
    onNavigate(href)
  }
}
