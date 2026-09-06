import type { Decorator, Preview } from '@storybook/react-vite'
import { useEffect } from 'react'
// The one stylesheet every consumer imports (see tokens/tailwind.css) — Storybook renders
// components exactly the way apps/web does, tokens included, never a second copy of Tailwind.
import '../tokens/tailwind.css'

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
