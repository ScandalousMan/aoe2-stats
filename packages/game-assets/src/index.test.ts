// Resolver tests against contracts/asset-pack.md's "Resolution contract". Written test-first
// (T408), when `src/index.ts` was still the T409 placeholder (`export {}`) and every test calling
// `civilisationIcon` / `mapThumbnail` / `countryFlag` was expected to FAIL — wrapped in vitest's
// `test.fails(...)`, the equivalent of the Python side's `xfail(strict=True)` for the green-tree
// gate (`scripts/hooks/gate-implementer.sh`), which refuses a hand-back on a red `pnpm test`. That
// wrapping meant the assertion body stayed unchanged while T408 alone was green, and would itself
// start failing the moment an implementation made the wrapped assertion pass — forcing `.fails` off
// instead of silently hiding a regression. T409 has since landed the real implementation, so those
// wrappers are gone and every test below is a plain `test(...)`, including the three signature-shape
// assertions that already passed at runtime under T408 (`expectTypeOf` is a compile-time construct,
// not a runtime check).
//
// Fixtures are chosen for confidence rather than for exact pack inventory, since the civilisation,
// map and flag packs are assembled by concurrent sibling tasks (T404/T405/T406) and may be partial
// or absent while this file is written:
//
// - "Britons" is one of the AoE2:DE base-game civilisations (canonical name from
//   `apps/api/src/aoe2stats_api/civilizations.py:100`) and keys, per research.md D3's measured
//   transform (`name.lower().replace(' ', '_')`), to `britons` — trivial (no space), and one of the
//   original 59/59 civs the pack was measured against.
// - "Arabia" and "Black Forest" are the two most canonical 1v1 land maps in the game's history;
//   research.md D3 measured aoe2cm2's 435-file pack keys by `map_name.lower().replace(' ', '-')`,
//   so "Arabia" -> `arabia` (no space) and "Black Forest" -> `black-forest` (the space case).
// - "fr" is an ISO 3166-1 alpha-2 code carried by `lipis/flag-icons` (MIT), which files its SVGs by
//   lower-case two-letter code (`fr.svg`).
//
// The punctuation case is deliberately not a claim that a specific punctuated map name is in the
// pack — contracts/asset-pack.md only requires that such a name "resolves or misses cleanly", which
// is where a naive string transform quietly stops matching (an untransformed apostrophe or
// parenthesis surviving into the key). The assertion below holds regardless of whether the pack
// happens to contain a matching file.
import { describe, expect, expectTypeOf, test } from 'vitest'

import { civilisationIcon, countryFlag, mapDisplayName, mapThumbnail } from './index.js'

describe('civilisationIcon', () => {
  test('a known civilisation name resolves to a URL under /game-assets/', () => {
    const result = civilisationIcon('Britons')

    expect(result).toBe('/game-assets/civilisations/britons.webp')
  })

  test('an unknown civilisation name misses cleanly', () => {
    const result = civilisationIcon('Not A Real Civilisation')

    // Value: the absent case is `undefined`, never a placeholder path.
    expect(result).toBeUndefined()

    // Type: the contract's return type is `string | undefined`, never `string | null` or a
    // sentinel string, so this must hold at the type level and not only at runtime.
    expectTypeOf(result).toEqualTypeOf<string | undefined>()
  })

  test('the exported function signature matches the contract', () => {
    expectTypeOf(civilisationIcon).toBeFunction()
    expectTypeOf(civilisationIcon).parameter(0).toEqualTypeOf<string>()
    expectTypeOf(civilisationIcon).returns.toEqualTypeOf<string | undefined>()
  })
})

describe('mapThumbnail', () => {
  test('a known map name with no space resolves to a URL under /game-assets/', () => {
    const result = mapThumbnail('Arabia')

    expect(result).toBe('/game-assets/maps/arabia.webp')
  })

  test('a known map name containing a space resolves to a URL under /game-assets/', () => {
    const result = mapThumbnail('Black Forest')

    expect(result).toBe('/game-assets/maps/black-forest.webp')
  })

  test('an unknown map name misses cleanly', () => {
    const result = mapThumbnail('Not A Real Map Alpha Nine Thousand')

    expect(result).toBeUndefined()
    expectTypeOf(result).toEqualTypeOf<string | undefined>()
  })

  test('a map name containing punctuation resolves cleanly or misses cleanly', () => {
    // Not asserted as a pack hit — see the file header. What matters is that an apostrophe
    // surviving a naive lower-case + space-to-dash transform does not throw, does not produce a
    // URL that would 404, and never yields a placeholder.
    const result = mapThumbnail("Ghost Lake's Cove")

    expectTypeOf(result).toEqualTypeOf<string | undefined>()
    if (result === undefined) {
      expect(result).toBeUndefined()
    } else {
      expect(result).toMatch(/^\/game-assets\/maps\/[^/]+\.webp$/)
    }
  })

  test('the exported function signature matches the contract', () => {
    expectTypeOf(mapThumbnail).toBeFunction()
    expectTypeOf(mapThumbnail).parameter(0).toEqualTypeOf<string>()
    expectTypeOf(mapThumbnail).returns.toEqualTypeOf<string | undefined>()
  })

  // T449: `Match.map_name` in production carries Relic's raw internal name (`Yucatan.rms`,
  // `CoastalForest.rms`), not the clean fixture form the tests above use — the resolver must
  // normalise (strip the `.rms`/`.rmsN` extension, split camelCase/underscore boundaries, then
  // Title-Case) before keying the pack, exactly the way `mapDisplayName` below does, so the two
  // stay in lockstep.
  test('a raw internal name with the .rms extension resolves through the normalised slug', () => {
    const result = mapThumbnail('Yucatan.rms')

    expect(result).toBe('/game-assets/maps/yucatan.webp')
  })

  test('a camelCase raw internal name resolves through the normalised slug', () => {
    const result = mapThumbnail('CoastalForest.rms')

    expect(result).toBe('/game-assets/maps/coastal-forest.webp')
  })

  test('an uncovered raw internal name misses cleanly, never a broken image', () => {
    const result = mapThumbnail('SomeCustomMap.rms')

    expect(result).toBeUndefined()
    expectTypeOf(result).toEqualTypeOf<string | undefined>()
  })
})

// T449: `mapDisplayName` is the FR-010 degrade path's own label — a raw internal `map_name` not
// covered by the pack still shows this cleaned, readable name, never the raw `.rms` string.
describe('mapDisplayName', () => {
  test('strips the raw internal .rms extension', () => {
    expect(mapDisplayName('Yucatan.rms')).toBe('Yucatan')
  })

  test('strips a numbered .rmsN extension case-insensitively', () => {
    expect(mapDisplayName('Yucatan.RMS2')).toBe('Yucatan')
  })

  test('splits a camelCase raw internal name into title-cased words', () => {
    expect(mapDisplayName('CoastalForest.rms')).toBe('Coastal Forest')
  })

  test('splits underscores into title-cased words', () => {
    expect(mapDisplayName('golden_pit')).toBe('Golden Pit')
  })

  test('an uncovered raw internal name still yields a cleaned, readable label', () => {
    expect(mapDisplayName('SomeCustomMap.rms')).toBe('Some Custom Map')
  })

  test('leaves the existing clean fixture form unchanged', () => {
    expect(mapDisplayName('Arabia')).toBe('Arabia')
  })

  test('the exported function signature matches the contract', () => {
    expectTypeOf(mapDisplayName).toBeFunction()
    expectTypeOf(mapDisplayName).parameter(0).toEqualTypeOf<string>()
    expectTypeOf(mapDisplayName).returns.toEqualTypeOf<string>()
  })
})

describe('countryFlag', () => {
  test('a known ISO 3166-1 alpha-2 code resolves to a URL under /game-assets/', () => {
    const result = countryFlag('fr')

    expect(result).toBe('/game-assets/flags/fr.svg')
  })

  test('an unknown / unassigned country code misses cleanly', () => {
    // "zz" is not an assigned ISO 3166-1 alpha-2 code, so no flag pack can legitimately carry it.
    const result = countryFlag('zz')

    expect(result).toBeUndefined()
    expectTypeOf(result).toEqualTypeOf<string | undefined>()
  })

  test('the exported function signature matches the contract', () => {
    expectTypeOf(countryFlag).toBeFunction()
    expectTypeOf(countryFlag).parameter(0).toEqualTypeOf<string>()
    expectTypeOf(countryFlag).returns.toEqualTypeOf<string | undefined>()
  })
})
