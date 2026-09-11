import tailwindcss from '@tailwindcss/vite'
import type { StorybookConfig } from '@storybook/react-vite'

// Storybook configuration (T016). No stories exist yet — the first component and its story land
// in T035 — so `stories` names the pattern every future `*.stories.tsx` under src/ will match,
// not any file that exists today.
//
// `./foundations/**` (T563, FR-040, FR-041) is the one deliberate exception to "every story lives
// under src/": the foundation pages document the token system itself, not a component, so they
// have no `src/` component directory to sit beside — this file is their only home.
const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(ts|tsx)', './foundations/**/*.stories.@(ts|tsx)'],
  addons: [
    // Accessibility checks against every story, for checklist point 5 in the design-system skill.
    '@storybook/addon-a11y',
    // T578 (FR-040, row 1 of `specs/README.md`'s Storybook documentation gap register): autodocs
    // needs this addon registered to generate a `docs`-type entry at all — `tags: ['autodocs']`
    // below is silent without it (proven while closing this row: the tag alone built 540 `story`
    // entries and zero `docs` ones). Not part of `essentials` in this Storybook major, so it is
    // named explicitly rather than assumed bundled.
    '@storybook/addon-docs',
  ],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  // The `react-vite` framework's own default (`'react-docgen'`) is the Babel-based scanner: it
  // reads prop *shapes* but not a `interface Props` declared in a separate type import, and it
  // carries no per-prop JSDoc description through to the Controls panel. `'react-docgen-typescript'`
  // (`@joshwooding/vite-plugin-react-docgen-typescript`, already a transitive dependency of
  // `@storybook/react-vite` — no new package needed) reads the real TypeScript prop types, so a
  // union like `LinkVariant`'s `'inline' | 'standalone'` renders as that literal union in both the
  // Controls panel and the autodocs prop table, and a prop's own JSDoc comment (e.g. `LinkProps`'s
  // `external`) becomes that prop's description in both places — one source, the component's own
  // types, feeding both surfaces (closes row 2 of the register above).
  typescript: {
    reactDocgen: 'react-docgen-typescript',
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
