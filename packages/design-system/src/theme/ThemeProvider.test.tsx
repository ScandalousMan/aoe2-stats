import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { THEME_STORAGE_KEY, ThemeProvider } from './ThemeProvider'
import { useTheme } from './useTheme'

type ChangeListener = (event: MediaQueryListEvent) => void

/** A controllable `matchMedia` stand-in: `change()` fires the same `change` event a real
 * `prefers-color-scheme` media query fires when the OS setting flips, which the default stub in
 * `src/test/setup.ts` (a no-op `addEventListener`) cannot simulate. */
function installMatchMediaMock(initialMatches: boolean) {
  let matches = initialMatches
  const listeners = new Set<ChangeListener>()
  window.matchMedia = ((query: string) =>
    ({
      get matches() {
        return matches
      },
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: (_type: string, listener: ChangeListener) => listeners.add(listener),
      removeEventListener: (_type: string, listener: ChangeListener) => listeners.delete(listener),
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList) as typeof window.matchMedia

  return {
    change(next: boolean) {
      matches = next
      for (const listener of listeners) {
        listener({ matches: next } as MediaQueryListEvent)
      }
    },
  }
}

describe('ThemeProvider / useTheme', () => {
  const originalMatchMedia = window.matchMedia

  beforeEach(() => {
    localStorage.clear()
    document.documentElement.dataset.theme = 'light'
  })

  afterEach(() => {
    window.matchMedia = originalMatchMedia
    localStorage.clear()
    delete document.documentElement.dataset.theme
  })

  it('reads its initial state from the DOM attribute the inline script already painted, not by re-deriving it', () => {
    // The system says light; the DOM attribute (as if T533's script had resolved a stored
    // override to dark) says dark. The provider must trust the DOM, not the system query.
    installMatchMediaMock(false)
    document.documentElement.dataset.theme = 'dark'

    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })

    expect(result.current.theme).toBe('dark')
  })

  it('honours a live system change when the reader has no stored override (FR-014)', () => {
    const mock = installMatchMediaMock(false)
    document.documentElement.dataset.theme = 'light'

    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.theme).toBe('light')
    expect(result.current.override).toBeNull()

    act(() => mock.change(true))

    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('ignores a system change once the reader has set an override', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
    const mock = installMatchMediaMock(false)
    document.documentElement.dataset.theme = 'light'

    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.override).toBe('light')

    act(() => mock.change(true))

    expect(result.current.theme).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('setOverride persists to localStorage and updates the DOM attribute synchronously', () => {
    installMatchMediaMock(false)

    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })

    act(() => result.current.setOverride('dark'))

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(result.current.theme).toBe('dark')
    expect(result.current.override).toBe('dark')
  })

  it('clearOverride removes the stored key and falls back to the current system preference', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    document.documentElement.dataset.theme = 'dark'
    installMatchMediaMock(false) // system currently prefers light

    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
    expect(result.current.override).toBe('dark')

    act(() => result.current.clearOverride())

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
    expect(result.current.override).toBeNull()
    expect(result.current.theme).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('never crashes when localStorage throws, and still lets an override apply for the session', () => {
    installMatchMediaMock(false)
    const originalGetItem = Storage.prototype.getItem
    const originalSetItem = Storage.prototype.setItem
    const originalRemoveItem = Storage.prototype.removeItem
    Storage.prototype.getItem = () => {
      throw new DOMException('blocked')
    }
    Storage.prototype.setItem = () => {
      throw new DOMException('blocked')
    }
    Storage.prototype.removeItem = () => {
      throw new DOMException('blocked')
    }

    try {
      document.documentElement.dataset.theme = 'light'

      const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })
      expect(result.current.theme).toBe('light')
      expect(result.current.override).toBeNull()

      expect(() => act(() => result.current.setOverride('dark'))).not.toThrow()
      expect(result.current.theme).toBe('dark')
      expect(document.documentElement.dataset.theme).toBe('dark')

      expect(() => act(() => result.current.clearOverride())).not.toThrow()
    } finally {
      Storage.prototype.getItem = originalGetItem
      Storage.prototype.setItem = originalSetItem
      Storage.prototype.removeItem = originalRemoveItem
    }
  })

  it('throws a clear error when used outside a ThemeProvider', () => {
    expect(() => renderHook(() => useTheme())).toThrow(
      'useTheme must be used within a ThemeProvider',
    )
  })
})
