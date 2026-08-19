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
