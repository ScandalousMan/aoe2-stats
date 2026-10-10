// The runtime pass (T693, feature 005): settles stories in the built Storybook and records, per
// review width, what a real browser does with each, settled in both themes the capture runs: the clip
// from either theme (T706), the mounts and the focus both themes show, the force when the two agree on
// it and the files of either (T710). Every settle starts with cleared cookies and storages (T708). See
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
  // Whether the built index tags the story `visual-full-page` (`isFullPageEntry`): the capture's own source.
  fullPage: boolean
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
const CLIP_PLANT = 'state-coverage-fixture-clip-plants--'
const CLIP_META_PLANT = 'state-coverage-fixture-clip-meta-decorator--'
const THEME_PLANT = 'state-coverage-fixture-theme-plants--'

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
    expect(r.files).toEqual(['packages/design-system/src/primitives/Field/index.tsx'])
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

  // A heading written through a tag variable: stamped, and placed by no tracked primitive.
  [`${PLANT}forced-callout-heading`]: (r) => {
    expect(r.files).toEqual(['packages/design-system/src/primitives/Callout/index.tsx'])
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Callout'))
    expect(r.force?.placedBy).toBeNull()
    expect(r.mounts).toEqual([])
  },
  [`${PLANT}play-focus-callout-heading`]: (r) => {
    expect(r.force).toBeUndefined()
    expect(r.focus?.stamp).toMatch(stampIn('Callout'))
    expect(r.focus?.placedBy).toBeNull()
  },

  // T687, T689: a story's own element inside a primitive; a raw button picked by name.
  [`${PLANT}slider-inside-button`]: (r) => {
    // Recorded as the browser answered: the story's `<span role="slider">` is one match, carries no
    // stamp (a story is never stamped), and the `Button` around it did not place it.
    expect(r.force).toEqual({ count: 1, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${PLANT}raw-button-picked-by-name`]: (r) => {
    expect(r.force).toEqual({ count: 1, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('primary', 'lg')])
  },

  // T710: `active` presses the forced control with the real mouse; the record exists, and credits the
  // element as any other force does, whether or not releasing the mouse would navigate.
  [`${PLANT}active-on-leaving-link`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Link'))
    expect(r.force?.placedBy).toEqual(inst('Link', 'inline', null))
    expect(r.mounts).toEqual([inst('Link', 'inline', null)])
  },
  [`${PLANT}active-on-submit-button`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toEqual(button('primary', 'md'))
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${PLANT}active-on-plain-button`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.placedBy).toEqual(button('primary', 'md'))
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${PLANT}hover-on-leaving-link`]: (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.placedBy).toEqual(inst('Link', 'inline', null))
    expect(r.mounts).toEqual([inst('Link', 'inline', null)])
  },

  // T691: a guard that reads a spread.
  [`${PLANT}button-href-via-spread-constant`]: (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    expect(r.mounts).toEqual([button('secondary', 'md')])
  },
}

// T703: what the browser must record for the capture frame of each clip plant. The shapes in the first
// group put a clip on the settled `story.parameters` without writing it in an object literal of the
// story; `clip: true` is the record `scripts/checks/state-coverage.mjs` refuses a mount credit from.
// The contrasts record the other halves: no clip, and a full-page tag read from the built index.
const CLIPPED = (r: WidthRecord) => {
  expect(r.clip).toBe(true)
  expect(r.fullPage).toBe(false)
  expect(r.mounts).toEqual([button('primary', 'md')])
}
Object.assign(PLANTS, {
  [`${CLIP_PLANT}no-clip`]: (r: WidthRecord) => {
    expect(r.clip).toBe(false)
    expect(r.fullPage).toBe(false)
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${CLIP_PLANT}full-page-tagged`]: (r: WidthRecord) => {
    expect(r.clip).toBe(false)
    expect(r.fullPage).toBe(true)
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${CLIP_PLANT}clip-from-play`]: CLIPPED,
  [`${CLIP_PLANT}clip-from-loader`]: CLIPPED,
  [`${CLIP_PLANT}clip-from-decorator`]: CLIPPED,
  [`${CLIP_PLANT}clip-from-story-annotation`]: CLIPPED,
  [`${CLIP_PLANT}clip-from-proto`]: CLIPPED,
  // The same key one level down never reaches the capture: Storybook's merge of the parameters copies
  // own keys only, so the record says no clip.
  [`${CLIP_PLANT}proto-inside-parameters-no-clip`]: (r: WidthRecord) => {
    expect(r.clip).toBe(false)
    expect(r.fullPage).toBe(false)
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${CLIP_PLANT}clip-from-object-prototype`]: CLIPPED,
  // T706: `clip` is the disjunction over the two themes the capture runs. The two dark-only shapes are
  // recorded `clip: false` by a light-only probe; the light-only decorator is the contrast, `true` too.
  [`${CLIP_PLANT}clip-only-in-dark`]: CLIPPED,
  [`${CLIP_PLANT}clip-literal-deleted-unless-dark`]: CLIPPED,
  [`${CLIP_PLANT}clip-only-in-light`]: CLIPPED,
  // T708: the dark clip depends on a storage flag the light settle writes; every settle starts with
  // cleared cookies and storages, as a capture unit's fresh context does, so the flag is absent.
  [`${CLIP_PLANT}clip-only-in-dark-while-storage-flag-absent`]: CLIPPED,
  [`${CLIP_META_PLANT}clip-from-meta-decorator`]: CLIPPED,
  // T710: the force is applied before the clip is read, as the capture does, so a clip the force's own
  // handler writes is recorded.
  [`${CLIP_PLANT}clip-from-force-handler`]: CLIPPED,
})

// T710: what the browser must record for a story whose render depends on the theme. The capture shows
// both themes, so a mount, a focus or a force only one of them has is not credited.
Object.assign(PLANTS, {
  // The light theme alone mounts a disabled Button: the intersection holds the Button both mount, and
  // no instance whose `disabledAt` names an element.
  [`${THEME_PLANT}disabled-button-in-light-only`]: (r: WidthRecord) => {
    expect(r.clip).toBe(false)
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  // The contrast: the disabled Button both themes mount is credited with its `disabledAt`.
  [`${THEME_PLANT}disabled-button-in-both-themes`]: (r: WidthRecord) => {
    expect(r.mounts).toHaveLength(2)
    expect(r.mounts[0]).toEqual(button('primary', 'md'))
    expect(r.mounts[1]).toMatchObject({ component: 'Button', variant: 'ghost', size: 'lg' })
    expect(r.mounts[1].disabledAt).toEqual([expect.stringMatching(stampIn('Button'))])
  },
  // One element in light, two in dark: the record carries the light answer and refuses it.
  [`${THEME_PLANT}force-count-differs-in-dark`]: (r: WidthRecord) => {
    expect(r.force).toMatchObject({ count: 1, differsByTheme: true })
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  // One element in each theme, a different one: the counts agree, the stamp and the placing instance
  // differ, and the force carries the flag all the same.
  [`${THEME_PLANT}force-element-differs-in-dark`]: (r: WidthRecord) => {
    expect(r.force).toMatchObject({ count: 1, differsByTheme: true })
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.mounts).toEqual([])
  },
  // The contrast: the same answer in both themes is the ordinary record, with no flag.
  [`${THEME_PLANT}force-same-in-both-themes`]: (r: WidthRecord) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toEqual(button('primary', 'md'))
    expect(r.force).not.toHaveProperty('differsByTheme')
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  // The focus is held in the light theme only: no focus in the record, and the flag the checker answers
  // by withholding the Rest credit of the story's own mounts.
  [`${THEME_PLANT}focus-in-light-only`]: (r: WidthRecord) => {
    expect(r.focus).toBeNull()
    expect(r.focusDiffersByTheme).toBe(true)
    expect(r.mounts).toEqual([button('primary', 'md')])
  },
  [`${THEME_PLANT}focus-in-both-themes`]: (r: WidthRecord) => {
    expect(r.focus?.stamp).toMatch(stampIn('Button'))
    expect(r.focus?.placedBy).toEqual(button('primary', 'md'))
    expect(r).not.toHaveProperty('focusDiffersByTheme')
  },
})

// The plants fail closed: a fixture story and its assertion exist together or the pass fails. Never
// part of a run that has no work (the file declares no test then).
if (workPath) {
  test('every fixture story has an assertion and every assertion a fixture story', () => {
    expect(checkPlantCoverage(Object.keys(PLANTS), work.fixtureIds)).toEqual([])
  })
}

for (const { id, widths, fullPage } of work.stories) {
  test(`${id} runtime record`, async ({ page }) => {
    // The budget is a rule, not a measurement: 30 s per settle (the per-unit default of
    // `stories.spec.ts`, which `playwright.config.ts` does not override) times the settles, which are
    // two per width, one per theme. A settle of the probe does what one capture unit does short of the
    // screenshot and the axe scan, in the same page: the navigation, the in-page readers, and the
    // force applied when the target is one element (T710, so the clip is read where the capture reads
    // it); the dark settle is probed exactly as the light one is, so the budget is 2 x 30 s per width
    // as it was when the dark settle only read the clip. Two measurements, 2026-10-08, of the same six
    // stories (the four foundations overviews, two PrivacyNotice stories) before the force was applied
    // and the dark settle probed: in a full pass with four workers in contention all six timed out at
    // the 30 s default once the dark settle doubled the navigations; rerun alone with four workers they
    // take 7.7 to 18.7 s with both settles. Those figures predate T710 and are not re-measured here;
    // the lead's full pass is.
    test.setTimeout(widths.length * 2 * 30_000)
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
        records[String(width)] = await probeStory(page, id, width, fullPage)
        assertion?.(records[String(width)])
        // Every fixture story outside the two clip plant files is a story with no clip.
        if (isFixture && !id.startsWith(CLIP_PLANT) && !id.startsWith(CLIP_META_PLANT)) {
          expect(records[String(width)].clip).toBe(false)
        }
      }
      if (outFile) writeFileSync(outFile, JSON.stringify({ id, widths: records }))
    } catch (error) {
      if (outFile) writeFileSync(outFile, JSON.stringify({ id, error: String(error) }))
      throw error
    }
  })
}
