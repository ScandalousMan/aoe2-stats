// Resolver tests against contracts/asset-pack.md's "Resolution contract". Written test-first
// (T408): `src/index.ts` is still the T409 placeholder (`export {}`), so every test that calls
// `civilisationIcon` / `mapThumbnail` / `countryFlag` is expected to FAIL until T409 lands the real
// implementation — do not add a stub implementation here to turn these green; that would defeat the
// point of writing the contract down before the code exists.
//
// The green-tree gate (`scripts/hooks/gate-implementer.sh`) refuses a hand-back on a red `pnpm test`,
// the same constraint the Python side resolves with `xfail(strict=True)`. Vitest's `test.fails(...)`
// is the equivalent for these tests: the assertion body is unchanged, the expected failure is what
// keeps the suite green today, and it flips to a hard failure the moment T409's implementation makes
// the assertion pass — which is what forces `.fails` off instead of silently hiding a regression. The
// three signature-shape assertions below already pass at runtime (`expectTypeOf` is a compile-time
// construct, not a runtime check), so they stay plain `test(...)`.
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

import { civilisationIcon, countryFlag, mapThumbnail } from './index.js'

describe('civilisationIcon', () => {
  test.fails('a known civilisation name resolves to a URL under /game-assets/', () => {
    const result = civilisationIcon('Britons')

    expect(result).toBe('/game-assets/civilisations/britons.webp')
  })

  test.fails('an unknown civilisation name misses cleanly', () => {
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
  test.fails('a known map name with no space resolves to a URL under /game-assets/', () => {
    const result = mapThumbnail('Arabia')

    expect(result).toBe('/game-assets/maps/arabia.webp')
  })

  test.fails('a known map name containing a space resolves to a URL under /game-assets/', () => {
    const result = mapThumbnail('Black Forest')

    expect(result).toBe('/game-assets/maps/black-forest.webp')
  })

  test.fails('an unknown map name misses cleanly', () => {
    const result = mapThumbnail('Not A Real Map Alpha Nine Thousand')

    expect(result).toBeUndefined()
    expectTypeOf(result).toEqualTypeOf<string | undefined>()
  })

  test.fails('a map name containing punctuation resolves cleanly or misses cleanly', () => {
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
})

describe('countryFlag', () => {
  test.fails('a known ISO 3166-1 alpha-2 code resolves to a URL under /game-assets/', () => {
    const result = countryFlag('fr')

    expect(result).toBe('/game-assets/flags/fr.svg')
  })

  test.fails('an unknown / unassigned country code misses cleanly', () => {
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
