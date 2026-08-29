import { describe, expect, it } from 'vitest'
import { validateSignInSearch } from './sign-in'

// `validateSignInSearch` feeds TanStack Router's `validateSearch`, and the router serialises
// every *defined* search value back onto the URL. `link` must therefore resolve to `undefined`
// rather than `false` when the parameter is absent — T110 closes the regression where an absent
// `link` became `false` and every ordinary first visit picked up `?link=false` in the address bar.

describe('validateSignInSearch', () => {
  it('leaves link undefined when the parameter is absent (T110 regression)', () => {
    expect(validateSignInSearch({}).link).toBeUndefined()
  })

  it("resolves link to true for the string '1'", () => {
    expect(validateSignInSearch({ link: '1' }).link).toBe(true)
  })

  it('resolves link to true for the boolean true', () => {
    expect(validateSignInSearch({ link: true }).link).toBe(true)
  })

  it.each(['0', 'false'])('does not resolve link to true for %s', (value) => {
    expect(validateSignInSearch({ link: value }).link).toBeUndefined()
  })
})

// US5 scenario 5, `features/auth/returnLocation.ts` — `return` carries the caller's place across
// the sign-in prompt (`FavouriteToggle`/`FavouritesList`'s own `signInHref`).
describe('validateSignInSearch — return', () => {
  it('leaves return undefined when the parameter is absent', () => {
    expect(validateSignInSearch({}).return).toBeUndefined()
  })

  it('carries a safe, relative return path through', () => {
    expect(validateSignInSearch({ return: '/players/12345' }).return).toBe('/players/12345')
  })

  it('drops a protocol-relative return value (an off-site redirect)', () => {
    expect(validateSignInSearch({ return: '//evil.example' }).return).toBeUndefined()
  })

  it('drops a non-string return value', () => {
    expect(validateSignInSearch({ return: 123 }).return).toBeUndefined()
  })
})
