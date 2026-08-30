/// <reference types="vite/client" />

// T409 implements civilisationIcon(civName), mapThumbnail(mapName) and countryFlag(countryCode)
// here, resolving a name onto a URL under the /game-assets/ prefix that packages/design-system's
// .storybook/main.ts and apps/web/vite.config.ts both mount (T401).
//
// The coverage set is generated from the directory listing at build via Vite's `import.meta.glob`,
// never a hand-maintained list of the 59/435/249 names: `import.meta.glob` is statically analysed
// and expanded by Vite — and by vitest, which transforms source through Vite — into the exact set
// of files matching the pattern at build/transform time, so a file added to or removed from a pack
// changes what resolves here without anyone editing this file. The glob is left non-eager: the
// resolver only ever needs the matched *paths*, never the file contents, so nothing is imported.

function keysFrom(glob: Record<string, unknown>, extension: string): ReadonlySet<string> {
  const keys = new Set<string>()
  for (const path of Object.keys(glob)) {
    const filename = path.slice(path.lastIndexOf('/') + 1)
    if (filename.endsWith(extension)) {
      keys.add(filename.slice(0, -extension.length))
    }
  }
  return keys
}

const civilisationKeys = keysFrom(import.meta.glob('../civilisations/*.webp'), '.webp')
const mapKeys = keysFrom(import.meta.glob('../maps/*.webp'), '.webp')
const flagKeys = keysFrom(import.meta.glob('../flags/*.svg'), '.svg')

/**
 * Resolves a civilisation NAME (never the id — feature 002 owns `civ_id -> name`) onto a URL
 * under `/game-assets/civilisations/`, or `undefined` when the pack does not cover it.
 */
export function civilisationIcon(civName: string): string | undefined {
  const key = civName.toLowerCase().replace(/ /g, '_')
  return civilisationKeys.has(key) ? `/game-assets/civilisations/${key}.webp` : undefined
}

/**
 * Resolves a map name onto a URL under `/game-assets/maps/`, or `undefined` when the pack does
 * not cover it.
 */
export function mapThumbnail(mapName: string): string | undefined {
  const key = mapName.toLowerCase().replace(/ /g, '-')
  return mapKeys.has(key) ? `/game-assets/maps/${key}.webp` : undefined
}

/**
 * Resolves an ISO 3166-1 alpha-2 country code onto a URL under `/game-assets/flags/`, or
 * `undefined` when the pack does not cover it.
 */
export function countryFlag(countryCode: string): string | undefined {
  const key = countryCode.toLowerCase()
  return flagKeys.has(key) ? `/game-assets/flags/${key}.svg` : undefined
}
