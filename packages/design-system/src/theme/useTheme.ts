import { useContext } from 'react'
import { ThemeContext, type ThemeContextValue } from './ThemeProvider'

/** The resolved theme, whether it is a reader-chosen override or the live system preference, and
 * the setter/clearer `SiteHeader`'s three-state control (T535) calls. Must be used within a
 * `ThemeProvider` — thrown loudly rather than silently defaulting, since a silent default here
 * would hide a missing provider until a theme toggle mysteriously did nothing. */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
