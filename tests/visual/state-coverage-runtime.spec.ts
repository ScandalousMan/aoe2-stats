// The runtime pass (T693, feature 005): settles stories in the built Storybook and records, per
// review width in the light theme, what a real browser does with each — see
// `tests/visual/state-coverage-runtime.ts` for what is recorded and why.
//
// Never run by hand and never part of `pnpm test:visual`: `scripts/visual/state-coverage-runtime.mjs`
// selects the stories (all, `--changed`, or the plants alone), writes the work list to the file named
// by `VISUAL_RUNTIME_FILE` — `{ stories: [{ id, widths }], fixtureIds }`, the widths coming from
// `scripts/visual/review-widths.mjs` so this file carries no second copy of them, `fixtureIds` every
// fixture story the built index lists whatever the selection — and reads back what this spec writes, one JSON file per
// story, into `VISUAL_RUNTIME_OUT_DIR`. With neither set the file declares no test.
//
// A story that is a plant (`packages/design-system/.storybook/fixtures/Plants.stories.tsx`) is also
// asserted against what its own comment says the browser must do — the plants are the pass's proof
// that it reads each shape the static check guessed wrong: no match, two matches, a stamp outside the
// primitive, no placing instance, the axis the runtime renders. The plants fail closed: a fixture
// story with no assertion fails, and so does an assertion with no fixture story (set equality with
// `fixtureIds`, `checkPlantCoverage`).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import { installSteamAvatarStub } from './fixtures/avatar-stub'
import { checkPlantCoverage, probeStory } from './state-coverage-runtime'
import type { Instance, WidthRecord } from './state-coverage-runtime'

interface WorkItem {
  id: string
  widths: number[]
}
// What the driver hands over: the stories to run, and every fixture story the built index lists —
// whatever the selection — so the plants can be held to set equality with their assertions.
interface Work {
  stories: WorkItem[]
  fixtureIds: string[]
}

const workPath = process.env.VISUAL_RUNTIME_FILE
const outDir = process.env.VISUAL_RUNTIME_OUT_DIR
const work: Work = workPath
  ? (JSON.parse(readFileSync(workPath, 'utf8')) as Work)
  : { stories: [], fixtureIds: [] }

const DIR = 'packages/design-system/src/primitives'
const stampIn = (component: string) => new RegExp(`^${DIR}/${component}/index\\.tsx:\\d+$`)
const PLANT = 'state-coverage-fixture-plants--'

const inst = (
  component: string,
  variant: string | null,
  size: string | null,
  disabledAt: string[] = [],
): Instance => ({ component, variant, size, disabledAt })
const button = (variant: string, size: string, disabledAt: string[] = []) =>
  inst('Button', variant, size, disabledAt)

// What the browser must record for each plant, at every width.
const PLANTS: Record<string, (record: WidthRecord) => void> = {
  [`${PLANT}no-match`]: (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    // An empty `Menu` does not open, and its trigger is `aria-disabled`: the DOM says so.
    expect(r.mounts).toHaveLength(1)
    expect(r.mounts[0]).toMatchObject({ component: 'Menu', variant: 'selection', size: null })
    expect(r.mounts[0].disabledAt).toEqual([expect.stringMatching(stampIn('Menu'))])
  },
  [`${PLANT}two-matches`]: (r) => {
    expect(r.force).toEqual({ count: 2, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('primary', 'lg')])
  },
  [`${PLANT}stamp-outside-the-primitive`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Callout'))
    expect(r.force?.placedBy).toBeNull()
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${PLANT}no-placing-instance`]: (r) => {
    expect(r.force).toEqual({ count: 1, stamp: null, placedBy: null })
    expect(r.mounts).toHaveLength(1)
    expect(r.mounts[0]).toMatchObject({ component: 'Menu', variant: 'selection', size: null })
  },
  [`${PLANT}spread-wins-over-literal`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toEqual(button('destructive', 'md'))
    expect(r.mounts).toEqual([button('destructive', 'md')])
  },
  [`${PLANT}bare-button`]: (r) => {
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toEqual(button('secondary', 'md'))
    expect(r.mounts).toEqual([button('secondary', 'md')])
  },
  [`${PLANT}cloned-control`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Field'))
    expect(r.force?.placedBy).toEqual(inst('Field', null, 'md'))
    expect(r.mounts).toEqual([inst('Field', null, 'md')])
  },
  [`${PLANT}hidden-ancestor`]: (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('primary', 'lg')])
  },
  [`${PLANT}play-focus`]: (r) => {
    expect(r.force).toBeUndefined()
    expect(r.focus?.stamp).toMatch(stampIn('Button'))
    expect(r.focus?.placedBy).toEqual(button('ghost', 'md'))
    expect(r.mounts).toEqual([button('ghost', 'md')])
  },

  // T689: args a render never passes, and what the DOM says is disabled.
  [`${PLANT}args-disabled-ignored`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.placedBy).toEqual(button('destructive', 'md'))
    expect(r.mounts).toEqual([button('destructive', 'md')])
  },
  [`${PLANT}args-disabled-spread`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toEqual(button('secondary', 'md', [r.force?.stamp as string]))
    expect(r.mounts).toEqual([button('secondary', 'md', [r.force?.stamp as string])])
  },
  [`${PLANT}args-href-ignored`]: (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('secondary', 'md')])
  },
  [`${PLANT}href-and-disabled`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    // An `<a>` is never `:disabled`: nothing disabled renders.
    expect(r.force?.placedBy).toEqual(button('secondary', 'md'))
    expect(r.mounts).toEqual([button('secondary', 'md')])
  },
  [`${PLANT}disabled-control-in-field`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Field'))
    expect(r.force?.placedBy).toEqual(inst('Field', null, 'md', [r.force?.stamp as string]))
    expect(r.mounts).toEqual([inst('Field', null, 'md', [r.force?.stamp as string])])
  },

  // T688: which element a force names, and who placed it.
  [`${PLANT}raw-anchor-beside-link`]: (r) => {
    expect(r.force).toEqual({ count: 2, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([inst('Link', 'inline', null)])
  },
  [`${PLANT}raw-anchor-picked-by-name`]: (r) => {
    expect(r.force).toEqual({ count: 1, stamp: null, placedBy: null })
    // The `Link` beside it passes no variant: recorded at the default.
    expect(r.mounts).toEqual([inst('Link', 'inline', null)])
  },
  [`${PLANT}name-selects-one-of-two`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toEqual(button('ghost', 'lg'))
    expect(r.mounts).toEqual([button('primary', 'md'), button('ghost', 'lg')])
  },
  [`${PLANT}nth-past-the-last`]: (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('primary', 'md'), button('ghost', 'lg')])
  },

  // T690: a tag that never renders; an axis never passed.
  [`${PLANT}guarded-menu-beside-raw`]: (r) => {
    expect(r.force).toEqual({ count: 1, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([])
  },
  [`${PLANT}menu-without-variant`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Menu'))
    expect(r.force?.placedBy).toEqual(inst('Menu', null, null))
    expect(r.mounts).toEqual([inst('Menu', null, null)])
  },
  [`${PLANT}menu-spread-with-variant`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.placedBy).toEqual(inst('Menu', 'selection', null))
    expect(r.mounts).toEqual([inst('Menu', 'selection', null)])
  },

  // T691: a guard that reads a spread.
  [`${PLANT}button-href-via-spread-constant`]: (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('secondary', 'md')])
  },
}

// The plants fail closed: a fixture story and its assertion exist together or the pass fails. Never
// part of a run that has no work (the file declares no test then).
if (workPath) {
  test('every fixture story has an assertion and every assertion a fixture story', () => {
    expect(checkPlantCoverage(Object.keys(PLANTS), work.fixtureIds)).toEqual([])
  })
}

for (const { id, widths } of work.stories) {
  test(`${id} runtime record`, async ({ page }) => {
    await installSteamAvatarStub(page)
    const outFile = outDir ? path.join(outDir, `${id}.json`) : null
    if (outDir) mkdirSync(outDir, { recursive: true })
    try {
      // A fixture story with no assertion is an error of its own, not a record nothing checked.
      const isFixture = work.fixtureIds.includes(id)
      const assertion = Object.hasOwn(PLANTS, id) ? PLANTS[id] : undefined
      if (isFixture && !assertion) {
        throw new Error(`fixture story ${id} has no assertion in PLANTS`)
      }
      const records: Record<string, WidthRecord> = {}
      for (const width of widths) {
        records[String(width)] = await probeStory(page, id, width)
        assertion?.(records[String(width)])
      }
      if (outFile) writeFileSync(outFile, JSON.stringify({ id, widths: records }))
    } catch (error) {
      if (outFile) writeFileSync(outFile, JSON.stringify({ id, error: String(error) }))
      throw error
    }
  })
}
