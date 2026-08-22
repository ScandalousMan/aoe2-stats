import { tanstackRouter } from '@tanstack/router-plugin/vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

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
  ],
})
