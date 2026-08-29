import { readFileSync } from 'node:fs'
import path from 'node:path'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AnalysisTeamGroupData } from './index'
import { AnalysisTimeline } from './index'

// jsdom has no layout engine (vitest.config.ts): `getBoundingClientRect` always returns 0 here, so
// the touch-target assertions below cannot render a real box and measure it. Same precedent as
// `MatchDetailPanel.test.tsx` / `Menu.test.tsx` (T035d): derive the pixel height a `Button`'s
// `h-<n>` utility actually resolves to from `tokens/space.json`, the single source of truth,
// rather than a literal copied into the test.
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

const teams: AnalysisTeamGroupData[] = [
  {
    id: 'team-1',
    participants: [
      {
        id: 'p1',
        alias: 'GL.TheViper',
        civId: 5,
        civName: 'Britons',
        apm: 142.7,
        actions: 3821,
        villagersOrdered: 68,
        ageUps: [{ id: 'a1', technologyId: 101, ageName: 'Feudal Age', timeMs: 401_000 }],
        builds: [{ id: 'b1', buildingId: 70, buildingName: 'House', timeMs: 15_000 }],
        trainings: [{ id: 't1', unitId: 83, unitName: 'Villager', amount: 3, timeMs: 42_000 }],
        researches: [{ id: 'r1', technologyId: 22, technologyName: 'Loom', timeMs: 20_000 }],
        resignedAtMs: null,
      },
      {
        id: 'p2',
        alias: 'Hera',
        civId: 9,
        civName: 'Mayans',
        apm: 118.3,
        actions: 3010,
        villagersOrdered: 61,
        ageUps: [],
        builds: [],
        trainings: [],
        researches: [],
        resignedAtMs: 1_680_000,
      },
    ],
  },
]

describe('AnalysisTimeline', () => {
  describe('loading (§5)', () => {
    it('shows the "Match analysis" heading and no participant content', () => {
      render(<AnalysisTimeline loading />)
      expect(screen.getByRole('heading', { name: 'Match analysis' })).toBeInTheDocument()
      expect(screen.queryByText('GL.TheViper')).not.toBeInTheDocument()
    })

    it('is the default rendering when no state is given yet', () => {
      render(<AnalysisTimeline />)
      expect(screen.getByRole('heading', { name: 'Match analysis' })).toBeInTheDocument()
    })
  })

  describe('error (§5)', () => {
    it('shows a danger callout distinct from every domain state, with a retry', () => {
      render(<AnalysisTimeline error onRetryLoad={vi.fn()} />)
      expect(
        screen.getByText("We could not load this match's analysis. Try again."),
      ).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('calls onRetryLoad when the retry action is activated', async () => {
      const onRetryLoad = vi.fn()
      const user = userEvent.setup()
      render(<AnalysisTimeline error onRetryLoad={onRetryLoad} />)

      await user.click(screen.getByRole('button', { name: 'Try again' }))

      expect(onRetryLoad).toHaveBeenCalledOnce()
    })
  })

  describe('queued / running (§3, §5)', () => {
    it('renders "Waiting to start…" for queued, with no action offered', () => {
      render(<AnalysisTimeline state="queued" />)
      expect(screen.getByRole('heading', { name: 'Match analysis' })).toBeInTheDocument()
      expect(screen.getByText('Waiting to start…')).toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })

    it('renders "Analysing this match…" for running, with no action offered', () => {
      render(<AnalysisTimeline state="running" />)
      expect(screen.getByText('Analysing this match…')).toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('published, not stale', () => {
    it('shows the heading, engine provenance, and no StaleRecomputeNotice', () => {
      render(
        <AnalysisTimeline
          state="published"
          teams={teams}
          engineName="aoe2rec-py"
          engineVersion="0.1.21"
          analysedAtLabel="23 Aug 2026"
        />,
      )
      expect(screen.getByRole('heading', { name: 'Match analysis' })).toBeInTheDocument()
      expect(
        screen.getByText('Analysed with aoe2rec-py 0.1.21 on 23 Aug 2026.'),
      ).toBeInTheDocument()
      expect(screen.queryByText('Newer analysis engine available')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Recompute' })).not.toBeInTheDocument()
    })

    it('renders one column per participant with alias and civilisation', () => {
      render(<AnalysisTimeline state="published" teams={teams} />)
      expect(screen.getByRole('heading', { name: 'GL.TheViper' })).toBeInTheDocument()
      expect(screen.getByText('Britons')).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Hera' })).toBeInTheDocument()
      expect(screen.getByText('Mayans')).toBeInTheDocument()
    })

    it('worded an age-up as ordered, never reached (FR-043c)', () => {
      render(<AnalysisTimeline state="published" teams={teams} />)
      const viperColumn = screen.getByRole('heading', { name: 'GL.TheViper' }).closest('article')!
      expect(
        within(viperColumn).getByText(
          (_, node) => node?.tagName === 'LI' && node.textContent === 'Feudal Age ordered — 6:41',
        ),
      ).toBeInTheDocument()
      expect(within(viperColumn).queryByText(/[Rr]eached/)).not.toBeInTheDocument()
    })

    it('shows a training amount as "N× Unit"', () => {
      render(<AnalysisTimeline state="published" teams={teams} />)
      const viperColumn = screen.getByRole('heading', { name: 'GL.TheViper' }).closest('article')!
      expect(within(viperColumn).getByText('3×')).toBeInTheDocument()
      expect(within(viperColumn).getByText('Villager')).toBeInTheDocument()
    })

    it('always shows the "Villagers ordered" label with its caveat, never "Villagers"', () => {
      render(<AnalysisTimeline state="published" teams={teams} />)
      const labels = screen.getAllByText('Villagers ordered')
      expect(labels.length).toBeGreaterThan(0)
      expect(
        screen.getAllByText('Training commands, net of cancelled orders — not a population count.')
          .length,
      ).toBe(labels.length)
      expect(screen.queryByText('Villagers trained')).not.toBeInTheDocument()
    })

    it('rounds actions per minute to the nearest whole number', () => {
      render(<AnalysisTimeline state="published" teams={teams} />)
      expect(screen.getByText('143')).toBeInTheDocument()
    })

    it('shows a ResignedLine only for a participant who resigned', () => {
      render(<AnalysisTimeline state="published" teams={teams} />)
      expect(
        screen.getByText(
          (_, node) => node?.tagName === 'P' && node.textContent === 'Resigned at 28:00',
        ),
      ).toBeInTheDocument()
      expect(
        screen.queryAllByText(
          (_, node) => node?.tagName === 'P' && /^Resigned at/.test(node.textContent ?? ''),
        ),
      ).toHaveLength(1)
    })

    it('renders an unresolved technology, unit and building id distinctly from a resolved name', () => {
      render(
        <AnalysisTimeline
          state="published"
          teams={[
            {
              id: 'team-1',
              participants: [
                {
                  id: 'p1',
                  alias: 'DauT',
                  civId: 5,
                  civName: 'Britons',
                  apm: 100,
                  actions: 100,
                  villagersOrdered: 10,
                  ageUps: [{ id: 'a1', technologyId: 101, ageName: null, timeMs: 401_000 }],
                  builds: [{ id: 'b1', buildingId: 9999, buildingName: null, timeMs: 1_000 }],
                  trainings: [{ id: 't1', unitId: 9998, unitName: null, amount: 1, timeMs: 1_000 }],
                  researches: [
                    { id: 'r1', technologyId: 9997, technologyName: null, timeMs: 1_000 },
                  ],
                  resignedAtMs: null,
                },
              ],
            },
          ]}
        />,
      )
      const unresolvedAge = screen.getByText('Technology ID 101')
      const unresolvedBuilding = screen.getByText('Building ID 9999')
      const unresolvedUnit = screen.getByText('Unit ID 9998')
      const unresolvedResearch = screen.getByText('Technology ID 9997')
      expect(unresolvedAge).toHaveClass('text-text-secondary')
      expect(unresolvedAge).toHaveClass('font-mono')
      expect(unresolvedBuilding).toHaveClass('text-text-secondary')
      expect(unresolvedUnit).toHaveClass('text-text-secondary')
      expect(unresolvedResearch).toHaveClass('text-text-secondary')
    })
  })

  describe('published, stale (§3.4, FR-041)', () => {
    it('keeps the participant content unchanged and offers Recompute beside it, never a Callout', () => {
      render(<AnalysisTimeline state="published" stale teams={teams} />)
      expect(screen.getByText('Newer analysis engine available')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Recompute' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'GL.TheViper' })).toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('fires onRequestAnalysis when Recompute is activated', async () => {
      const onRequestAnalysis = vi.fn()
      const user = userEvent.setup()
      render(
        <AnalysisTimeline
          state="published"
          stale
          teams={teams}
          onRequestAnalysis={onRequestAnalysis}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'Recompute' }))

      expect(onRequestAnalysis).toHaveBeenCalledOnce()
    })
  })

  describe('failed (§3.5, FR-036)', () => {
    it('shows a danger notice with the error class, and no retry button', () => {
      render(<AnalysisTimeline state="failed" errorClass="MalformedArchiveError" />)
      expect(screen.getByText('This match could not be analysed')).toBeInTheDocument()
      expect(screen.getByText('The recorded game could not be parsed.')).toBeInTheDocument()
      expect(screen.getByText('Error: MalformedArchiveError')).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('unavailable (§3.5, FR-034)', () => {
    it('shows a danger notice with no retry button, distinct wording from failed', () => {
      render(<AnalysisTimeline state="unavailable" />)
      expect(screen.getByText('Analysis is not available for this match')).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
      expect(screen.queryByText('This match could not be analysed')).not.toBeInTheDocument()
    })
  })

  describe('refused (§3.5)', () => {
    // `Callout`'s own tone-to-role mapping (`shared-primitives.md`, asserted in
    // `Callout.test.tsx`) is `role="status"` for `warning` and `role="alert"` for `danger` only —
    // the same mapping every other spec in this directory cites. `refused` uses `warning`.
    it('is the only failure shape with a retry action, in a warning tone', () => {
      render(<AnalysisTimeline state="refused" />)
      expect(screen.getByText('Analysis is temporarily unavailable')).toBeInTheDocument()
      expect(screen.getByRole('status')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Try requesting analysis' })).toBeInTheDocument()
    })

    it('fires onRequestAnalysis when the retry action is activated', async () => {
      const onRequestAnalysis = vi.fn()
      const user = userEvent.setup()
      render(<AnalysisTimeline state="refused" onRequestAnalysis={onRequestAnalysis} />)

      await user.click(screen.getByRole('button', { name: 'Try requesting analysis' }))

      expect(onRequestAnalysis).toHaveBeenCalledOnce()
    })
  })

  // shared-primitives.md's Button rule: any button reachable on a touch viewport clears the 44px
  // floor. Measured, not matched against a class name (T035d) — see `mockButtonHeightLayout` above.
  describe('touch target floor (shared-primitives.md Button rule)', () => {
    it("the stale-notice 'Recompute' rendered box clears the 44px touch floor", () => {
      const getBoundingClientRect = mockButtonHeightLayout()
      try {
        render(<AnalysisTimeline state="published" stale teams={teams} />)
        const button = screen.getByRole('button', { name: 'Recompute' })
        expect(button.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
      } finally {
        getBoundingClientRect.mockRestore()
      }
    })

    it("the refused-state 'Try requesting analysis' rendered box clears the 44px touch floor", () => {
      const getBoundingClientRect = mockButtonHeightLayout()
      try {
        render(<AnalysisTimeline state="refused" />)
        const button = screen.getByRole('button', { name: 'Try requesting analysis' })
        expect(button.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
      } finally {
        getBoundingClientRect.mockRestore()
      }
    })
  })
})
