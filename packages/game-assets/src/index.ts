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

// T449: `Match.map_name` in production carries Relic's raw internal map name
// (`Yucatan.rms`, `CoastalForest.rms`), not the clean fixture form ("Yucatan", "Coastal Forest")
// used above. A trailing map-file extension (`.rms`, `.rms2`, any `.rmsN`) is stripped
// case-insensitively; the remainder is a deterministic string transform, not a lookup table
// sourced externally (that decision — plan.md, T449 — settled against a hand-maintained mapping,
// the way feature 002's civ-name mapping is owned elsewhere and this is not that).
const MAP_FILE_EXTENSION = /\.rms\d*$/i

function stripMapFileExtension(rawMapName: string): string {
  return rawMapName.replace(MAP_FILE_EXTENSION, '')
}

/** Splits a name on camelCase boundaries and underscores into words — `"CoastalForest"` ->
 * `["Coastal", "Forest"]`, `"golden_pit"` -> `["golden", "pit"]`, `"Yucatan"` -> `["Yucatan"]`
 * (no boundary, passes through as one word). */
function splitIntoWords(name: string): string[] {
  return name
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .split(/\s+/)
    .filter((word) => word.length > 0)
}

function titleCaseWord(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
}

/**
 * Derives a clean, readable map display name from a raw `map_name` — production's Relic-supplied
 * raw internal name (`"Yucatan.rms"`, `"CoastalForest.rms"`) or the already-clean fixture form
 * (`"Arabia"`, which passes through unchanged). This is FR-010's degrade label too: a name the
 * pack does not cover still renders this cleaned text, never the raw `.rms` string.
 */
export function mapDisplayName(rawMapName: string): string {
  return splitIntoWords(stripMapFileExtension(rawMapName)).map(titleCaseWord).join(' ')
}

function mapSlug(rawMapName: string): string {
  return mapDisplayName(rawMapName).toLowerCase().replace(/ /g, '-')
}

/**
 * Resolves a map name onto a URL under `/game-assets/maps/`, or `undefined` when the pack does
 * not cover it. Keyed on the same normalised slug `mapDisplayName` derives its words from, so a
 * raw internal name (`"Yucatan.rms"`) resolves exactly like its clean form (`"Yucatan"`).
 */
export function mapThumbnail(mapName: string): string | undefined {
  const key = mapSlug(mapName)
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
