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
  // Mounts packages/game-assets at /game-assets/ — the same prefix apps/web/vite.config.ts serves
  // it under (T401) — so a story's image URL and the app's image URL are the same string, and
  // visual regression runs against the real licenced packs instead of missing images (research.md
  // D5; constitution VII). The second entry mounts the three self-hosted typeface packs the same
  // way, at /fonts/ (typography-tokens.md §8.3, feature 005 T523) — the prefix `font.json`'s
  // `face.*.src` names, so a story renders in the real Inter/Fraunces/JetBrains Mono instead of
  // the fallback stack, exactly as apps/web does.
  staticDirs: [
    { from: '../../game-assets', to: '/game-assets' },
    { from: '../tokens/fonts', to: '/fonts' },
  ],
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
