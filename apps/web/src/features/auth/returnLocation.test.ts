import { afterEach, describe, expect, it } from 'vitest'
import {
  buildSignInHref,
  isSafeReturnPath,
  savePendingReturnLocation,
  takePendingReturnLocation,
} from './returnLocation'

describe('isSafeReturnPath', () => {
  it('accepts an ordinary relative path', () => {
    expect(isSafeReturnPath('/players/12345')).toBe(true)
  })

  it('accepts a relative path carrying a query string', () => {
    expect(isSafeReturnPath('/favourites?tab=all')).toBe(true)
  })

  it('rejects a path that does not start with a slash', () => {
    expect(isSafeReturnPath('players/12345')).toBe(false)
  })

  it('rejects a protocol-relative address (an off-site redirect)', () => {
    expect(isSafeReturnPath('//evil.example')).toBe(false)
  })

  it('rejects a full URL', () => {
    expect(isSafeReturnPath('https://evil.example/players/1')).toBe(false)
  })
})

describe('buildSignInHref', () => {
  it('carries the return path as an encoded ?return= query parameter', () => {
    expect(buildSignInHref('/players/12345')).toBe('/sign-in?return=%2Fplayers%2F12345')
  })
})

describe('savePendingReturnLocation / takePendingReturnLocation', () => {
  afterEach(() => {
    window.sessionStorage.clear()
  })

  it('round-trips a safe path across the two calls', () => {
    savePendingReturnLocation('/players/12345')
    expect(takePendingReturnLocation()).toBe('/players/12345')
  })

  it('consumes the value — a second read sees nothing (US5 scenario 5)', () => {
    savePendingReturnLocation('/favourites')
    takePendingReturnLocation()
    expect(takePendingReturnLocation()).toBeNull()
  })

  it('returns null when nothing is pending', () => {
    expect(takePendingReturnLocation()).toBeNull()
  })

  it('never stores an unsafe path', () => {
    savePendingReturnLocation('//evil.example')
    expect(takePendingReturnLocation()).toBeNull()
  })
})
