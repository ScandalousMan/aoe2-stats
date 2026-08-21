import { describe, expect, it } from 'vitest'
import { leaderboardName, leaderboardSortKey } from './leaderboards'

describe('leaderboardName', () => {
  it('names a known leaderboard id', () => {
    expect(leaderboardName(3)).toBe('1v1 Random Map')
  })

  it('falls back to "Leaderboard <id>" for an id it does not recognise, never a guess', () => {
    expect(leaderboardName(999)).toBe('Leaderboard 999')
  })
})

describe('leaderboardSortKey', () => {
  it('orders 1v1 Random Map before Team Random Map', () => {
    expect(leaderboardSortKey(3)).toBeLessThan(leaderboardSortKey(4))
  })

  it('orders every listed leaderboard before an unlisted one', () => {
    expect(leaderboardSortKey(14)).toBeLessThan(leaderboardSortKey(999))
  })

  it('orders unlisted leaderboards ascending by id, so row order stays stable across reloads', () => {
    expect(leaderboardSortKey(998)).toBeLessThan(leaderboardSortKey(999))
  })
})
