// Declaration for `./source-stamp.mjs`, so `./main.ts` gets real types instead of an implicit `any`
// (TS7016) — the same pairing `scripts/visual/review-widths.d.mts` has for its `.mjs`.
import type { Plugin } from 'vite'

export declare const STAMP_ATTRIBUTE: string
export declare function isStampedFile(repoRelativePath: string): boolean
export declare function stampSource(code: string, repoRelativePath: string): string | null
export declare function sourceStampPlugin(options: { rootDir: string }): Plugin
