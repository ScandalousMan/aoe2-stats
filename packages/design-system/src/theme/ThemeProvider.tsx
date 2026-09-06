import { createContext, useCallback, useEffect, useState, type ReactNode } from 'react'

// research.md D11, spec.md FR-014. `apps/web/index.html` (T533) runs an inline, synchronous
// script before the stylesheet that resolves the initial theme — stored override, then system
// preference, then `light` — and paints it onto `document.documentElement.dataset.theme` before
// React ever mounts. This provider owns everything after that first paint: it reads that same
// attribute rather than re-deriving it (re-deriving risks disagreeing with what is already on
// screen), and it owns the `matchMedia` subscription that keeps a reader who has never overridden
// following their system live.
//
// The override is a preference in the reader's own browser only: it is never sent over the
// network, never attached to a profile or session, and readable by nobody but the reader
// (constitution IX). A cookie was rejected for exactly that reason (research D11) — this key
// lives in `localStorage` and nowhere else.
export type Theme = 'light' | 'dark'

/** The `localStorage` key `apps/web/index.html`'s inline script and this provider both read and
 * write. Fixed by T533; changing it here without changing it there reintroduces the flash this
 * feature exists to remove. */
export const THEME_STORAGE_KEY = 'ds-theme-override'

const DARK_QUERY = '(prefers-color-scheme: dark)'

export interface ThemeContextValue {
  /** The theme currently painted. */
  theme: Theme
  /** The reader's stored override, or `null` while following the system preference. A three-state
   * control (system, light, dark — T535) reads this to know which of its three states is active;
   * `theme` alone cannot tell "light because the system says so" from "light because the reader
   * chose it". */
  override: Theme | null
  /** Sets an explicit override: persists it to `localStorage` and paints it onto
   * `document.documentElement.dataset.theme` synchronously, so a toggle never flashes. Storage
   * writes are wrapped — a browser blocking site data must not crash the reader's session, it
   * just means the override does not survive a reload. */
  setOverride: (theme: Theme) => void
  /** Clears the override and returns to following the system preference, resolved immediately. */
  clearOverride: () => void
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function readStoredOverride(): Theme | null {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return stored === 'light' || stored === 'dark' ? stored : null
  } catch {
    // Storage blocked (constitution IX has no basis to route around that): the reader has no
    // override as far as this session is concerned.
    return null
  }
}

function readSystemTheme(): Theme {
  try {
    return window.matchMedia(DARK_QUERY).matches ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

/** The theme already painted by `apps/web/index.html`'s inline script. Read, never re-derived: it
 * has already applied the same fail-closed fallback order this module would otherwise repeat. */
function readPaintedTheme(): Theme {
  if (typeof document === 'undefined') return 'light'
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

function paint(theme: Theme): void {
  document.documentElement.dataset.theme = theme
}

export interface ThemeProviderProps {
  children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps): ReactNode {
  const [theme, setTheme] = useState<Theme>(readPaintedTheme)
  const [override, setOverrideState] = useState<Theme | null>(readStoredOverride)

  // Honours a system change live, but only for a reader who has not overridden (FR-014). A
  // reader who has set light or dark is not moved by a system change until they clear it.
  useEffect(() => {
    if (override !== null) return
    let list: MediaQueryList
    try {
      list = window.matchMedia(DARK_QUERY)
    } catch {
      return
    }
    const onChange = (event: MediaQueryListEvent) => {
      const next: Theme = event.matches ? 'dark' : 'light'
      setTheme(next)
      paint(next)
    }
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }, [override])

  const setOverride = useCallback((next: Theme) => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // Blocked storage: the override still applies for the rest of this page's life, it just
      // will not survive a reload. There is nowhere else this preference is allowed to live.
    }
    setOverrideState(next)
    setTheme(next)
    paint(next)
  }, [])

  const clearOverride = useCallback(() => {
    try {
      localStorage.removeItem(THEME_STORAGE_KEY)
    } catch {
      // As above: nothing to fall back to but continuing without a stored override.
    }
    const system = readSystemTheme()
    setOverrideState(null)
    setTheme(system)
    paint(system)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, override, setOverride, clearOverride }}>
      {children}
    </ThemeContext.Provider>
  )
}
