import type { Decorator, Preview } from '@storybook/react-vite'
import { useEffect } from 'react'
import { MINIMAL_VIEWPORTS } from 'storybook/viewport'
import { REVIEW_WIDTHS } from '../../../scripts/visual/review-widths.mjs'
import { BUTTON_AXIS_DEFAULTS, Button } from '../src/primitives/Button'
import { FIELD_AXIS_DEFAULTS, Field } from '../src/primitives/Field'
import { LINK_AXIS_DEFAULTS, Link } from '../src/primitives/Link'
import { Menu } from '../src/primitives/Menu'
// The one stylesheet every consumer imports (see tokens/tailwind.css) — Storybook renders
// components exactly the way apps/web does, tokens included, never a second copy of Tailwind.
import '../tokens/tailwind.css'

// A handful of stories pin a viewport to force the narrow shape of a responsive component into
// view in the browsable Storybook (each such story's own comment names why). None of Storybook's
// built-in presets sits at the narrowest width `packages/design-system/specs/README.md` rule 7
// declares for review — `MINIMAL_VIEWPORTS.mobile1` is narrower than that — so it is declared once
// here rather than borrowed from a preset chosen for a different number, and its width comes from
// `REVIEW_WIDTHS` (`scripts/visual/review-widths.mjs`), the one place that literal exists in code.
// This pin is cosmetic only: the visual regression suite's own width axis
// (`scripts/visual/run.mjs`'s `WIDTHS`, the same import) is what actually governs a baseline's
// dimensions, and it overrides whatever this preview sets.
const VIEWPORT_OPTIONS = {
  ...MINIMAL_VIEWPORTS,
  reviewWidthNarrow: {
    name: 'Review width (narrow)',
    styles: { width: `${REVIEW_WIDTHS[0]}px`, height: '667px' },
    type: 'mobile' as const,
  },
}

// The tracked primitives, exposed to the page (T693 piece 2) so the runtime pass
// (`tests/visual/state-coverage-runtime.spec.ts`) can tell, by function identity while walking
// React's fiber up from a located element, which instance placed it and with which props. No
// `data-*` marker is added to production markup for this — the page-level registry is the only
// handle, and it exists in Storybook alone.
//
// `directory` is the repository-rooted directory a primitive's own source lives in: an element whose
// source stamp (`./source-stamp.mjs`) falls under it was placed by the primitive's own code (or, for
// `Field`, by its `cloneElement` call), as opposed to by a story or by another component rendered
// inside it. `axes` is the primitive's own exported axis-defaults constant — the one its destructuring
// reads; the fiber carries only the props a caller passed, so the pass merges those over it. An axis
// with no default is `null` (`Menu`'s `variant` is required). Only `variant` and `size` are recorded,
// and only for a primitive that lists them. Adding a primitive here is how it becomes tracked — and
// `scripts/visual/state-coverage-runtime-model.mjs` carries its directory beside this one.
interface TrackedPrimitive {
  component: unknown
  directory: string
  axes: Record<string, string | null>
}
declare global {
  interface Window {
    __DS_TRACKED_PRIMITIVES__?: Record<string, TrackedPrimitive>
  }
}
window.__DS_TRACKED_PRIMITIVES__ = {
  Button: {
    component: Button,
    directory: 'packages/design-system/src/primitives/Button/',
    axes: BUTTON_AXIS_DEFAULTS,
  },
  Link: {
    component: Link,
    directory: 'packages/design-system/src/primitives/Link/',
    axes: LINK_AXIS_DEFAULTS,
  },
  Field: {
    component: Field,
    directory: 'packages/design-system/src/primitives/Field/',
    axes: FIELD_AXIS_DEFAULTS,
  },
  // `Menu`'s `variant` is required, so it has no default to merge: `null` records it as passed, or
  // as `null` for a story that renders a `Menu` without one. `align` is not a matrix axis.
  Menu: {
    component: Menu,
    directory: 'packages/design-system/src/primitives/Menu/',
    axes: { variant: null },
  },
}

// Every story renders inside this element so it always carries the theme's own background and
// text colour from tokens — never a Storybook default that the token set doesn't own.
const withThemeAndSurface: Decorator = (Story, context) => {
  const theme = context.globals.theme === 'dark' ? 'dark' : 'light'

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  return (
    <div className="bg-background text-text-primary min-h-24 p-6">
      <Story />
    </div>
  )
}

const preview: Preview = {
  // T578 (FR-040, row 1 of `specs/README.md`'s "Storybook documentation gap register"). The
  // autodocs tag has to be set here, on the preview's own project-level annotations, to reach
  // every story by default — setting it in `.storybook/main.ts` instead is silent: that file has
  // no runtime effect on a story's own `tags` array, only `preview.tsx`'s (and each story's own
  // meta) do. Confirmed by building Storybook before and after moving it here: zero `docs`-type
  // entries in `storybook-static/index.json` with it in `main.ts`, 41 with it here — one per
  // component directory, since `@storybook/addon-docs` (registered in `main.ts`) is what turns the
  // tag into an actual autodocs page rather than a no-op. A story may still opt out per file with
  // `tags: ['!autodocs']`; none does today.
  tags: ['autodocs'],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
      },
    },
    // Sidebar order (FR-046, T564). Every story's `title` already carries its tier as the first
    // path segment — `Primitives/…`, `Composites/…`, `Screens/…` — matching the three directories
    // T540 moved every component into (`src/primitives/`, `src/composites/`, `src/screens/`), and
    // its need as the second segment, so a reader who does not know a component's name can still
    // find "I need to show a player's colour" under `Composites/Player identity/`. `Foundations`
    // (T563) documents the token system rather than a component and has no tier, so it is ordered
    // first and kept out of the tier list rather than interleaved alphabetically between
    // `Composites` and `Primitives`, which is where the default alphabetical sort would put it.
    // Everything below the named levels — the foundation pages, the need groups and the components
    // inside them — stays alphabetical, which `storySort` does by default for any level it is not
    // told to order.
    options: {
      storySort: {
        order: [
          'Foundations',
          ['Colour', 'Typography', 'Spacing', 'Radii', 'Elevation', 'Motion', 'Iconography'],
          'Primitives',
          ['Layout & structure', 'Typography', 'Feedback & status', 'Forms'],
          'Composites',
          ['Player identity', 'Match & game data', 'Search & favourites', 'Site chrome', 'Uploads'],
          'Screens',
          ['Account & privacy', 'Profile & capture'],
        ],
      },
    },
    viewport: {
      options: VIEWPORT_OPTIONS,
    },
  },
  globalTypes: {
    theme: {
      name: 'Theme',
      description: 'Light or dark token theme',
      defaultValue: 'light',
      toolbar: {
        icon: 'circlehollow',
        items: [
          { value: 'light', title: 'Light' },
          { value: 'dark', title: 'Dark' },
        ],
      },
    },
  },
  decorators: [withThemeAndSurface],
}

export default preview
