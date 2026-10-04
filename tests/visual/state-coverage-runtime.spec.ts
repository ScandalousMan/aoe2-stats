// The runtime pass (T693, feature 005): settles stories in the built Storybook and records, per
// review width in the light theme, what a real browser does with each — see
// `tests/visual/state-coverage-runtime.ts` for what is recorded and why.
//
// Never run by hand and never part of `pnpm test:visual`: `scripts/visual/state-coverage-runtime.mjs`
// selects the stories (all, `--changed`, or the plants alone), writes the work list to the file named
// by `VISUAL_RUNTIME_FILE` — `[{ id, widths }]`, the widths coming from `scripts/visual/review-widths.mjs`
// so this file carries no second copy of them — and reads back what this spec writes, one JSON file per
// story, into `VISUAL_RUNTIME_OUT_DIR`. With neither set the file declares no test.
//
// A story that is a plant (`packages/design-system/.storybook/fixtures/Plants.stories.tsx`) is also
// asserted against what its own comment says the browser must do — the plants are the pass's proof
// that it reads each shape the static check guessed wrong: no match, two matches, a stamp outside the
// primitive, no placing instance, the axis the runtime renders.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import { installSteamAvatarStub } from './fixtures/avatar-stub'
import { probeStory } from './state-coverage-runtime'
import type { WidthRecord } from './state-coverage-runtime'

interface WorkItem {
  id: string
  widths: number[]
}

const workPath = process.env.VISUAL_RUNTIME_FILE
const outDir = process.env.VISUAL_RUNTIME_OUT_DIR
const work: WorkItem[] = workPath ? (JSON.parse(readFileSync(workPath, 'utf8')) as WorkItem[]) : []

const DIR = 'packages/design-system/src/primitives'
const stampIn = (component: string) => new RegExp(`^${DIR}/${component}/index\\.tsx:\\d+$`)

// What the browser must record for each plant, at every width.
const PLANTS: Record<string, (record: WidthRecord) => void> = {
  'state-coverage-fixture-plants--no-match': (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    expect(r.mounts).toEqual(['Menu:selection|start'])
  },
  'state-coverage-fixture-plants--two-matches': (r) => {
    expect(r.force).toEqual({ count: 2, stamp: null, placedBy: null })
    expect(r.mounts).toEqual(['Button:primary|lg'])
  },
  'state-coverage-fixture-plants--stamp-outside-the-primitive': (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Callout'))
    expect(r.force?.placedBy).toBeNull()
    expect(r.mounts).toEqual(['Button:primary|md'])
  },
  'state-coverage-fixture-plants--no-placing-instance': (r) => {
    expect(r.force).toEqual({ count: 1, stamp: null, placedBy: null })
    expect(r.mounts).toEqual(['Menu:selection|start'])
  },
  'state-coverage-fixture-plants--spread-wins-over-literal': (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toBe('Button:destructive|md')
    expect(r.mounts).toEqual(['Button:destructive|md'])
  },
  'state-coverage-fixture-plants--bare-button': (r) => {
    expect(r.force?.stamp).toMatch(stampIn('Button'))
    expect(r.force?.placedBy).toBe('Button:secondary|md')
    expect(r.mounts).toEqual(['Button:secondary|md'])
  },
  'state-coverage-fixture-plants--cloned-control': (r) => {
    expect(r.force?.count).toBe(1)
    expect(r.force?.stamp).toMatch(stampIn('Field'))
    expect(r.force?.placedBy).toBe('Field:md')
    expect(r.mounts).toEqual(['Field:md'])
  },
  'state-coverage-fixture-plants--hidden-ancestor': (r) => {
    expect(r.force).toEqual({ count: 0, stamp: null, placedBy: null })
    expect(r.mounts).toEqual(['Button:primary|lg'])
  },
  'state-coverage-fixture-plants--play-focus': (r) => {
    expect(r.force).toBeUndefined()
    expect(r.focus?.stamp).toMatch(stampIn('Button'))
    expect(r.focus?.placedBy).toBe('Button:ghost|md')
    expect(r.mounts).toEqual(['Button:ghost|md'])
  },
}

for (const { id, widths } of work) {
  test(`${id} runtime record`, async ({ page }) => {
    await installSteamAvatarStub(page)
    const outFile = outDir ? path.join(outDir, `${id}.json`) : null
    if (outDir) mkdirSync(outDir, { recursive: true })
    try {
      const records: Record<string, WidthRecord> = {}
      for (const width of widths) {
        records[String(width)] = await probeStory(page, id, width)
        PLANTS[id]?.(records[String(width)])
      }
      if (outFile) writeFileSync(outFile, JSON.stringify({ id, widths: records }))
    } catch (error) {
      if (outFile) writeFileSync(outFile, JSON.stringify({ id, error: String(error) }))
      throw error
    }
  })
}
