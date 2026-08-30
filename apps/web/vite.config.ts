import { tanstackRouter } from '@tanstack/router-plugin/vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { viteStaticCopy } from 'vite-plugin-static-copy'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // Must run before @vitejs/plugin-react: it generates routeTree.gen.ts from
    // src/routes/* on every dev/build, which the react plugin then compiles.
    // Generator options shared with the standalone `tsr generate` step in package.json (e.g.
    // routeFileIgnorePattern) live in tsr.config.json, not here: that CLI resolves its own
    // config and never sees these inline options.
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
    tailwindcss(),
    // Serves packages/game-assets at the exact same /game-assets/ prefix Storybook mounts via
    // `staticDirs` (packages/design-system/.storybook/main.ts, T401): a component's `src` prop is
    // the same string in the app and in a story only if both consumers agree on the prefix. This
    // is a build-time copy (dev server + `vite build`), never a runtime fetch of the pack — the
    // pack ships in the repository (constitution III, plan.md Technical Context).
    viteStaticCopy({
      targets: [
        {
          src: '../../packages/game-assets/civilisations/*',
          dest: 'game-assets/civilisations',
          rename: (name, extension) => `${name}.${extension}`,
        },
        {
          src: '../../packages/game-assets/maps/*',
          dest: 'game-assets/maps',
          rename: (name, extension) => `${name}.${extension}`,
        },
        {
          src: '../../packages/game-assets/flags/*',
          dest: 'game-assets/flags',
          rename: (name, extension) => `${name}.${extension}`,
        },
      ],
    }),
  ],
})
