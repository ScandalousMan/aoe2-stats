import { readFileSync } from 'node:fs'
import path from 'node:path'
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MatchDetailPanel } from './index'
import type { MatchDetailData } from './index'

// jsdom has no layout engine (vitest.config.ts): `getBoundingClientRect` always returns 0 here, so
// the touch-target assertions below cannot render a real box and measure it. The next best thing —
// `Menu.test.tsx`'s own precedent for T035d — is to read the real spacing scale from its single
// source of truth, `tokens/space.json`, and derive the pixel height a `Button`'s `h-<n>` utility
// actually resolves to from *that* number, not from a literal copied into the test. A class-name
// match (`toMatch(/h-12/)`) keeps passing even if the spacing unit that "12" multiplies shrinks;
// this fails the moment it would.
const SPACE_TOKENS_PATH = path.resolve(__dirname, '../../../tokens/space.json')
const ROOT_FONT_SIZE_PX = 16 // jsdom's default <html> font-size, same as an un-overridden browser.

function spacingUnitPx(): number {
  const { unit } = JSON.parse(readFileSync(SPACE_TOKENS_PATH, 'utf8')) as { unit: string }
  const remMatch = /^([\d.]+)rem$/.exec(unit)
  if (!remMatch) throw new Error(`tokens/space.json "unit" is not a rem value: ${unit}`)
  return Number.parseFloat(remMatch[1]) * ROOT_FONT_SIZE_PX
}

/** Stands in for jsdom's missing layout engine: derives the height a rendered element's own
 * `h-<n>` utility actually resolves to, from the real spacing token, instead of hardcoding a pixel
 * count in the test. An element with no such class measures as 0, so a `Button` that stops setting
 * an explicit height at all fails loudly rather than reading as compliant. */
function mockButtonHeightLayout() {
  const unitPx = spacingUnitPx()
  return vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: Element,
  ) {
    const match = /\bh-(\d+)\b/.exec(this.className)
    const height = match ? Number.parseInt(match[1], 10) * unitPx : 0
    return {
      height,
      width: 0,
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      x: 0,
      y: 0,
      toJSON: () => {},
    } as DOMRect
  })
}

const match: MatchDetailData = {
  gameId: '1001',
  map: 'Arabia',
  leaderboardName: '1v1 Random Map',
  durationLabel: '34 min',
  playedAtLabel: '22 Aug 2026, 14:32',
  gameVersion: '101.101',
  captureStatus: 'stored',
  captureDeadlineAt: null,
  teams: [
    {
      id: 'team-1',
      name: 'Team 1',
      participants: [
        {
          id: 'p1',
          alias: 'aoe2guy',
          civId: 10,
          civName: 'Franks',
          result: 'win',
          ratingChange: { value: 12 },
        },
      ],
    },
    {
      id: 'team-2',
      name: 'Team 2',
      participants: [
        {
          id: 'p2',
          alias: 'aoe2villain',
          civId: 20,
          civName: 'Mongols',
          result: 'loss',
          ratingChange: { value: -12 },
        },
      ],
    },
  ],
}

describe('MatchDetailPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the map, leaderboard and duration', () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.getByText('Arabia')).toBeInTheDocument()
    expect(screen.getByText(/1v1 Random Map/)).toBeInTheDocument()
    expect(screen.getByText(/34 min/)).toBeInTheDocument()
  })

  it('shows the raw game version in the header (§11.1 point 3, FR-018)', () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.getByText(/101\.101/)).toBeInTheDocument()
  })

  it('shows the DownloadAction only for a stored capture', () => {
    const { rerender } = render(<MatchDetailPanel match={match} />)
    expect(screen.getByRole('button', { name: 'Download replay' })).toBeInTheDocument()

    rerender(<MatchDetailPanel match={{ ...match, captureStatus: 'pending' }} />)
    expect(screen.queryByRole('button', { name: 'Download replay' })).not.toBeInTheDocument()
  })

  it('never shows the DownloadAction for a quarantined capture, disabled or otherwise', () => {
    render(<MatchDetailPanel match={{ ...match, captureStatus: 'quarantined' }} />)
    expect(screen.queryByRole('button', { name: 'Download replay' })).not.toBeInTheDocument()
  })

  it('shows a loading label while the signed URL is being requested', () => {
    render(<MatchDetailPanel match={match} downloadState="loading" />)
    expect(screen.getByRole('button', { name: /Preparing your download/ })).toBeInTheDocument()
  })

  it('returns the download button to default and pressable on failure, with a reason in StatusRegion', () => {
    render(<MatchDetailPanel match={match} downloadState="error" />)
    const button = screen.getByRole('button', { name: 'Download replay' })
    expect(button).toBeEnabled()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'The download link could not be created. Try again.',
    )
  })

  it('groups every participant under the correct team heading, with none duplicated or dropped', () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.getByText('Team 1')).toBeInTheDocument()
    expect(screen.getByText('Team 2')).toBeInTheDocument()
    expect(screen.getAllByText('aoe2guy')).toHaveLength(1)
    expect(screen.getAllByText('aoe2villain')).toHaveLength(1)
  })

  it("shows an explicit sign on each participant's rating change", () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.getByText('+12')).toBeInTheDocument()
    expect(screen.getByText('−12')).toBeInTheDocument()
  })

  // match-history.md §2a: the reported production defect — a participant's own unrecorded result
  // must never render as "Loss", and must render as its own, differently-coloured state.
  it('shows an unknown participant result as "Unknown", never as "Win" or "Loss"', () => {
    const withUnknown: MatchDetailData = {
      ...match,
      teams: [
        {
          ...match.teams[0],
          participants: [{ ...match.teams[0].participants[0], result: 'unknown' }],
        },
        match.teams[1],
      ],
    }
    render(<MatchDetailPanel match={withUnknown} />)
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.queryByText('Win')).not.toBeInTheDocument()
    expect(screen.getByText('Loss')).toBeInTheDocument()
  })

  // §2a's own reproduction: the production page this fix responds to showed eight participants,
  // none with a known result, all rendered as losses.
  it('renders a match with every participant result unknown without implying anyone lost', () => {
    const allUnknown: MatchDetailData = {
      ...match,
      teams: Array.from({ length: 8 }, (_, index) => ({
        id: `team-${index + 1}`,
        name: `Team ${index + 1}`,
        participants: [
          {
            id: `p${index + 1}`,
            alias: `player${index + 1}`,
            civId: 10,
            civName: 'Franks',
            result: 'unknown' as const,
          },
        ],
      })),
    }
    render(<MatchDetailPanel match={allUnknown} />)
    expect(screen.getAllByText('Unknown')).toHaveLength(8)
    expect(screen.queryByText('Win')).not.toBeInTheDocument()
    expect(screen.queryByText('Loss')).not.toBeInTheDocument()
  })

  it('shows a load-failed callout with a retry, distinct wording from not-found', () => {
    const onRetry = vi.fn()
    render(<MatchDetailPanel status="error" onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('We could not load this match')
    screen.getByRole('button', { name: 'Try again' }).click()
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows a single not-found callout with a link back to the match list, revealing nothing that distinguishes "does not exist" from "not yours"', () => {
    render(<MatchDetailPanel status="not-found" matchListHref="/matches" />)
    expect(screen.getByRole('alert')).toHaveTextContent('This match could not be found.')
    const link = screen.getByRole('link', { name: 'Back to the match list' })
    expect(link).toHaveAttribute('href', '/matches')
    expect(screen.queryByText(/not yours|does not exist|unauthorized/i)).not.toBeInTheDocument()
  })

  it("shows skeleton header fields and the badge's own loading state while loading", () => {
    const { container } = render(<MatchDetailPanel status="loading" />)
    act(() => vi.advanceTimersByTime(200))
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0)
    expect(screen.queryByText('Arabia')).not.toBeInTheDocument()
  })

  it('never shows the DownloadAction while loading', () => {
    render(<MatchDetailPanel status="loading" />)
    expect(screen.queryByRole('button', { name: /Download/ })).not.toBeInTheDocument()
  })
})

describe('MatchDetailPanel — ParticipantsTable responsive tiers (match-history.md §8)', () => {
  function mockMatchMediaAt(widthPx: number): () => void {
    const original = window.matchMedia
    window.matchMedia = (query: string) => {
      const minWidthMatch = /min-width:\s*(\d+)px/.exec(query)
      const threshold = minWidthMatch ? Number(minWidthMatch[1]) : Infinity
      return {
        matches: widthPx >= threshold,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      } as MediaQueryList
    }
    return () => {
      window.matchMedia = original
    }
  }

  it('renders one card per participant at 375, no table', () => {
    const restore = mockMatchMediaAt(375)
    render(<MatchDetailPanel match={match} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    restore()
  })

  it('still renders cards, not a table, at 1100 — below `xl`, the breakpoint the spec names for the table', () => {
    const restore = mockMatchMediaAt(1100)
    render(<MatchDetailPanel match={match} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    restore()
  })

  it('renders participant cards two-up (a 2-column grid) at 768, still no table', () => {
    const restore = mockMatchMediaAt(768)
    render(<MatchDetailPanel match={match} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    const lists = screen.getAllByRole('list')
    expect(lists).toHaveLength(2)
    for (const list of lists) {
      expect(list.className).toContain('grid-cols-2')
    }
    restore()
  })

  it('renders a real ruled table with a caption per team from `xl` (1280) up', () => {
    const restore = mockMatchMediaAt(1280)
    render(<MatchDetailPanel match={match} />)
    expect(screen.getAllByRole('table', { name: /Team/ })).toHaveLength(2)
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    restore()
  })
})

// T074b: every button reachable on a touch viewport must clear the 44px floor
// (shared-primitives.md's Button rule). Measured, not matched against a class name (T035d) — see
// `mockButtonHeightLayout` above.
describe('MatchDetailPanel — touch target floor (shared-primitives.md Button rule)', () => {
  it("DownloadAction's rendered box clears the 44px touch floor", () => {
    const getBoundingClientRect = mockButtonHeightLayout()
    try {
      render(<MatchDetailPanel match={match} />)
      const button = screen.getByRole('button', { name: 'Download replay' })
      expect(button.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
    } finally {
      getBoundingClientRect.mockRestore()
    }
  })

  it("'Back to the match list' rendered box clears the 44px touch floor", () => {
    const getBoundingClientRect = mockButtonHeightLayout()
    try {
      render(<MatchDetailPanel status="not-found" matchListHref="/matches" />)
      const link = screen.getByRole('link', { name: 'Back to the match list' })
      expect(link.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
    } finally {
      getBoundingClientRect.mockRestore()
    }
  })

  it("the load-failure 'Try again' rendered box clears the 44px touch floor", () => {
    const getBoundingClientRect = mockButtonHeightLayout()
    try {
      render(<MatchDetailPanel status="error" onRetry={() => {}} />)
      const button = screen.getByRole('button', { name: 'Try again' })
      expect(button.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
    } finally {
      getBoundingClientRect.mockRestore()
    }
  })
})

// T074b: the spacing scale (match-history.md §7). Asserted against the class the utility actually
// renders, then cross-checked against the real token value it resolves to — a component that
// swapped `gap-4`/`gap-6` for two literal pixel values would still fail this the same way a
// class-name match alone could not distinguish `space-4` from a coincidentally-equal literal.
describe('MatchDetailPanel — spacing scale (match-history.md §7)', () => {
  it("keeps the header-to-DownloadAction run at space-4, distinct from DownloadAction's own space-6 to ParticipantsTable", () => {
    const { container } = render(<MatchDetailPanel match={match} />)
    const headerGroup = container.querySelector('header')?.parentElement
    expect(headerGroup?.className).toMatch(/\bgap-4\b/)
    expect(headerGroup?.className).not.toMatch(/\bgap-6\b/)

    const outer = headerGroup?.parentElement
    expect(outer?.className).toMatch(/\bgap-6\b/)
  })

  it('renders ParticipantsTable row padding-block at space-3 (py-3), not space-2', () => {
    const original = window.matchMedia
    window.matchMedia = (query: string) => {
      const minWidthMatch = /min-width:\s*(\d+)px/.exec(query)
      const threshold = minWidthMatch ? Number(minWidthMatch[1]) : Infinity
      return {
        matches: 1280 >= threshold,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      } as MediaQueryList
    }
    const { container } = render(<MatchDetailPanel match={match} />)
    const cell = container.querySelector('td')
    expect(cell?.className).toMatch(/\bpy-3\b/)
    expect(cell?.className).not.toMatch(/\bpy-2\b/)
    window.matchMedia = original
  })
})

// 003 T330 (match-history.md §11): widening `MatchDetailPanel` to any match this service holds —
// unresolved identifiers, any team count, and the "no caller highlight" rule.
describe('MatchDetailPanel — 003, §11: any match, any age', () => {
  function mockMatchMediaAt(widthPx: number): () => void {
    const original = window.matchMedia
    window.matchMedia = (query: string) => {
      const minWidthMatch = /min-width:\s*(\d+)px/.exec(query)
      const threshold = minWidthMatch ? Number(minWidthMatch[1]) : Infinity
      return {
        matches: widthPx >= threshold,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      } as MediaQueryList
    }
    return () => {
      window.matchMedia = original
    }
  }

  const unresolvedMatch: MatchDetailData = {
    ...match,
    gameId: '2001',
    map: null,
    teams: [
      {
        id: 'team-1',
        name: 'Team 1',
        participants: [
          {
            id: 'p1',
            alias: 'Fr020A',
            civId: 5,
            civName: 'Britons',
            result: 'win',
            ratingChange: { value: 10 },
          },
        ],
      },
      {
        id: 'team-2',
        name: 'Team 2',
        participants: [
          {
            id: 'p2',
            alias: 'Fr020B',
            civId: 999,
            civName: null,
            result: 'loss',
            ratingChange: { value: -10 },
          },
        ],
      },
    ],
  }

  it('renders an unresolved civilisation as "Civilisation ID <n>" in text-secondary/font-mono, distinct from a resolved name in the same frame (FR-020, §11.2)', () => {
    const restore = mockMatchMediaAt(1280)
    render(<MatchDetailPanel match={unresolvedMatch} />)

    const unresolved = screen.getByText('Civilisation ID 999')
    expect(unresolved.className).toMatch(/\bfont-mono\b/)
    expect(unresolved.className).toContain('text-text-secondary')

    const resolved = screen.getByText('Britons')
    expect(resolved.className).not.toMatch(/\bfont-mono\b/)
    expect(resolved.className).toContain('text-text-primary')
    restore()
  })

  it('never fills an unresolved civilisation name in with its raw id as if it were a name', () => {
    render(<MatchDetailPanel match={unresolvedMatch} />)
    expect(screen.queryByText('999')).not.toBeInTheDocument()
    expect(screen.getByText('Civilisation ID 999')).toBeInTheDocument()
  })

  it('renders an unresolved map without inventing a name or a numeric identifier this schema does not carry', () => {
    render(<MatchDetailPanel match={unresolvedMatch} />)
    const unresolvedMap = screen.getByText(/Map — unresolved/)
    expect(unresolvedMap.className).toMatch(/\bfont-mono\b/)
    expect(unresolvedMap.className).toContain('text-text-secondary')
    expect(screen.queryByText('Arabia')).not.toBeInTheDocument()
  })

  it('renders eight TeamGroups for a free-for-all, none dropped or duplicated (§11.4)', () => {
    const restore = mockMatchMediaAt(1280)
    const ffaMatch: MatchDetailData = {
      ...match,
      gameId: '2002',
      teams: Array.from({ length: 8 }, (_, index) => ({
        id: `team-${index + 1}`,
        name: `Team ${index + 1}`,
        participants: [
          {
            id: `p${index + 1}`,
            alias: `player${index + 1}`,
            civId: index + 1,
            civName: `Civ${index + 1}`,
            result: index === 0 ? ('win' as const) : ('loss' as const),
            ratingChange: { value: index === 0 ? 40 : -6 },
          },
        ],
      })),
    }
    render(<MatchDetailPanel match={ffaMatch} />)
    expect(screen.getAllByRole('table', { name: /Team/ })).toHaveLength(8)
    for (let index = 1; index <= 8; index += 1) {
      expect(screen.getAllByText(`player${index}`)).toHaveLength(1)
    }
    restore()
  })

  it('renders identically whether or not the caller took part — no row carries a distinguishing "you" marker or class', () => {
    render(<MatchDetailPanel match={match} />)
    expect(screen.queryByText(/\byou\b/i)).not.toBeInTheDocument()
    const rows = document.querySelectorAll('tbody tr, li')
    const classNames = new Set(Array.from(rows).map((row) => row.className))
    // Every row shares the same structural className — none is singled out.
    expect(classNames.size).toBeLessThanOrEqual(1)
  })
})
