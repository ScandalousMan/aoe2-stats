import { describe, expect, it } from 'vitest'
import { parseGameId } from './gameId'

describe('parseGameId', () => {
  it('accepts a plain positive integer string', () => {
    expect(parseGameId('700800900')).toBe(700_800_900)
  })

  it('accepts a single digit', () => {
    expect(parseGameId('1')).toBe(1)
  })

  it('rejects zero — a game_id is always positive', () => {
    expect(parseGameId('0')).toBeNull()
  })

  it('rejects a negative number', () => {
    expect(parseGameId('-5')).toBeNull()
  })

  it('rejects a decimal', () => {
    expect(parseGameId('1.5')).toBeNull()
  })

  it('rejects non-numeric text', () => {
    expect(parseGameId('abc')).toBeNull()
  })

  it('rejects a numeric string with trailing garbage', () => {
    expect(parseGameId('123abc')).toBeNull()
  })

  it('rejects an empty string', () => {
    expect(parseGameId('')).toBeNull()
  })

  it('rejects whitespace', () => {
    expect(parseGameId('  ')).toBeNull()
  })

  it('rejects a value beyond safe integer range', () => {
    expect(parseGameId('99999999999999999999')).toBeNull()
  })
})
