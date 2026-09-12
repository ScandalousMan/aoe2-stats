import { cleanup, render } from '@testing-library/react'
import { composeStories, setProjectAnnotations } from '@storybook/react'
import type { ReactRenderer } from '@storybook/react'
import type { ReactElement } from 'react'
import type { Store_CSFExports } from 'storybook/internal/types'
import { afterEach, describe, expect, it } from 'vitest'
import preview from '../../.storybook/preview'
import { scanForLandmarkUniqueViolations } from './axe'

// T579 (`specs/README.md`'s "Accessibility mechanism gap register", row 1): "one vitest file that
// renders EVERY story of every component ... and runs the helper on each, so a new component or
// story is covered with no one having to opt in." This is that file. It reuses Storybook's own
// project annotations (`.storybook/preview.tsx` — the theme/surface decorator, viewport globals)
// through the portable-stories API (`composeStories`), so a story renders here exactly as it does
// inside Storybook, with no second, hand-maintained render path to drift from the first.
setProjectAnnotations([preview])

// A story's `play` function (hover-opening a Tooltip, opening a Menu popover) is not invoked
// here. This sweep answers a narrower question than "does this story's fully-interacted state
// carry a landmark-unique violation" — it answers "does the DOM this story mounts, before any
// interaction, carry one." That is deliberately the same DOM axe scans first in
// `tests/visual/stories.spec.ts` too (its own scan runs once per story-theme pair against the
// settled render, not gated on a story's `play` step). The defect class this task closes — a
// hidden caption repeating an ancestor landmark's name — lives in a component's static
// composition (`Panel` + `Table`, `MatchDetailPanel`'s `TeamGroup` + `Table`), never behind an
// interaction, so this is not a gap the defect class has actually used.
// `composeStories`'s own accepted input type (review remediation, 2026-09-11) — the CSF exports
// shape Storybook itself exports from `storybook/internal/types`, `{ default: <a Meta>, ... }` —
// rather than a looser `Record<string, unknown>` that happened to satisfy `composeStories`'
// pre-existing `as` cast at the call site without actually matching what it declares it accepts.
type StoryModule = Store_CSFExports<ReactRenderer>

const storyModules = import.meta.glob<StoryModule>('../**/*.stories.tsx', { eager: true })

// Independent of the glob above, on purpose (review remediation, 2026-09-11): a coverage guard
// derived from the same glob it is meant to catch failing would fail the same way — silently. If
// `../**/*.stories.tsx` ever matched nothing (a file moves, a Vite config change alters glob
// resolution), the sweep loop below would generate zero tests and the suite would still report
// green: nothing failed because nothing ran. This is the independent source of truth the coverage
// check below compares the swept set against — every component directory, from its own
// `index.tsx`, the same shape `story-docs.mjs` already uses to require that every one of them
// carries a story file.
const componentIndexModules = import.meta.glob<Record<string, unknown>>(
  '../{primitives,composites,screens}/*/index.tsx',
  { eager: true },
)

/** A glob key is a path like `../primitives/Panel/Panel.stories.tsx` or
 * `../primitives/Panel/index.tsx` — the component directory is always the second-to-last
 * segment, regardless of the file's own name, so this reads the same for both globs above. */
function componentDirFromPath(path: string): string {
  const segments = path.split('/')
  return segments[segments.length - 2]
}

interface ComposedStory {
  (): ReactElement
  storyName?: string
}

/** Every story `composeStories` finds in a module, by export name. Factored out as its own pure
 * function (review remediation, 2026-09-11) so the story-level coverage guard — "this module
 * composed at least one story" — is provable against a fixture module directly, not only by
 * inference from the real sweep going red. */
function composedStoryNames(module: StoryModule): string[] {
  return Object.keys(composeStories(module) as Record<string, ComposedStory>)
}

const sortedStoryPaths = Object.keys(storyModules).sort()

// Module-level coverage guard. Equality, not "at least one": `story-docs.mjs` already requires
// every component directory under `src/{primitives,composites,screens}/` to carry a story file,
// so the correct claim here is that the swept set and the existing set are the same set — a
// component directory with no swept story file fails this, by name, and so does a swept path that
// somehow names a directory with no `index.tsx` (a stale or misplaced story file).
const sweptComponentDirs = new Set(sortedStoryPaths.map(componentDirFromPath))
const existingComponentDirs = new Set(Object.keys(componentIndexModules).map(componentDirFromPath))

describe('landmark-unique sweep — coverage', () => {
  it('sweeps every component directory that exists, and only those', () => {
    expect([...sweptComponentDirs].sort()).toEqual([...existingComponentDirs].sort())
  })
})

// Exclusions: a label this sweep does not generate a test for, with the reason it cannot render
// here — never a silent gap. Checked against the actual composed set below, so an exclusion that
// stops applying (the story is renamed, or the reason stops holding) fails loudly instead of
// quietly excluding nothing.
const EXCLUDED_STORIES: Record<string, string> = {}

function componentLabelFromPath(path: string): string {
  const match = /\/([^/]+)\.stories\.tsx$/.exec(path)
  return match ? match[1] : path
}

const seenExclusionLabels = new Set<string>()

for (const path of sortedStoryPaths) {
  const module = storyModules[path]
  const componentLabel = componentLabelFromPath(path)
  const composed = composeStories(module) as Record<string, ComposedStory>

  describe(`landmark-unique sweep — ${componentLabel}`, () => {
    afterEach(() => {
      cleanup()
    })

    // Story-level coverage guard: a module composing zero stories (a `default`-only export, a CSF
    // shape `composeStories` stops recognising) contributes no test to the loop below and would
    // otherwise pass by contributing nothing to fail. `composedStoryNames` is proven against a
    // fixture with exactly this shape further down this file.
    it(`${componentLabel} composes at least one story`, () => {
      expect(composedStoryNames(module).length).toBeGreaterThan(0)
    })

    for (const [exportName, Story] of Object.entries(composed)) {
      const label = `${componentLabel} > ${Story.storyName ?? exportName}`
      const exclusionReason = EXCLUDED_STORIES[label]

      if (exclusionReason !== undefined) {
        seenExclusionLabels.add(label)
        // Not silently skipped: the reason is the test's own name, so it shows in every run.
        it.skip(`${label} — excluded: ${exclusionReason}`, () => {})
        continue
      }

      it(`${label} carries no landmark-unique violation`, async () => {
        // `baseElement` (`document.body`), not `container` (review remediation, 2026-09-11): no
        // component here uses a portal (`ReactDOM.createPortal`, confirmed absent from
        // `packages/design-system/src`) today, so the two are equivalent for every story this
        // sweep composes — but a story that renders outside its own `container` via a portal
        // would otherwise never be scanned at all, silently. `cleanup()` above runs after every
        // test, so `document.body` holds only the current story's render, never a previous one's.
        const { baseElement } = render(<Story />)
        const violations = await scanForLandmarkUniqueViolations(baseElement)
        expect(
          violations,
          violations
            .map(
              (violation) =>
                `[${violation.id}] ${violation.help}\n` +
                violation.nodes
                  .map((node) => `  target: ${node.target.join(' ')}\n  html: ${node.html}`)
                  .join('\n'),
            )
            .join('\n'),
        ).toHaveLength(0)
      })
    }
  })
}

// Guards the exclusion list itself against going stale: an entry naming a story that no longer
// exists (renamed, removed) would otherwise exclude nothing and nobody would notice.
describe('landmark-unique sweep — exclusion list', () => {
  it('names only stories the sweep actually composed', () => {
    expect(Object.keys(EXCLUDED_STORIES).sort()).toEqual([...seenExclusionLabels].sort())
  })
})

// Fixture proof for the story-level coverage guard above (review remediation, 2026-09-11):
// `composedStoryNames` is a pure function of a module object, so it is checked directly against a
// module shaped the way a broken story file would be — a `default` export and no story exports —
// without needing a real file on disk to reproduce the failure.
describe('landmark-unique sweep — story-level coverage guard (fixture proof)', () => {
  function FixtureComponent() {
    return null
  }

  it('finds zero stories in a module whose default export carries no story exports', () => {
    const emptyModule: StoryModule = {
      default: { title: 'Fixture', component: FixtureComponent },
    }
    expect(composedStoryNames(emptyModule)).toHaveLength(0)
    // The guard itself, applied to that module, fails — exactly what a real swept module in this
    // shape would do inside the loop above, rather than silently contributing no test.
    expect(() => {
      expect(composedStoryNames(emptyModule).length).toBeGreaterThan(0)
    }).toThrow()
  })

  it('finds at least one story in a module carrying a story export', () => {
    // No `: StoryModule` annotation here, on purpose: `Store_CSFExports` (the type
    // `composeStories` actually declares it accepts) names only `default` — a real CSF module's
    // story exports (`Default` here) exist structurally beyond it, not as a literal property of
    // the type itself, so annotating this fresh object literal directly would trip TypeScript's
    // excess-property check on `Default`. Left to infer its own literal type, `fixtureModule` is a
    // plain value by the time it reaches `composedStoryNames` below, and only structural
    // assignability — not literal freshness — applies to a value passed by reference.
    const fixtureModule = {
      default: { title: 'Fixture', component: FixtureComponent },
      Default: {},
    }
    expect(composedStoryNames(fixtureModule).length).toBeGreaterThan(0)
  })
})
