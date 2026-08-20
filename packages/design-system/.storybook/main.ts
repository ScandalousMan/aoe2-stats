import tailwindcss from '@tailwindcss/vite'
import type { StorybookConfig } from '@storybook/react-vite'

// Storybook configuration (T016). No stories exist yet — the first component and its story land
// in T035 — so `stories` names the pattern every future `*.stories.tsx` under src/ will match,
// not any file that exists today.
const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(ts|tsx)'],
  addons: [
    // Accessibility checks against every story, for checklist point 5 in the design-system skill.
    '@storybook/addon-a11y',
  ],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  core: {
    disableTelemetry: true,
  },
  staticDirs: [],
  // `@storybook/react-vite` gives us a Vite build but not Tailwind: without this plugin the
  // `@import`/`@theme`/`@custom-variant` at-rules in tokens/tailwind.css pass through unprocessed
  // and every utility class in a story silently resolves to nothing. Same plugin apps/web uses
  // (apps/web/vite.config.ts), so Storybook renders components exactly as the app will.
  viteFinal: async (viteConfig) => {
    viteConfig.plugins ??= []
    viteConfig.plugins.push(tailwindcss())
    return viteConfig
  },
}

export default config
