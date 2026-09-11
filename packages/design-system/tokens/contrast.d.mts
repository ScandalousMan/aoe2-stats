// Declaration for `./contrast.mjs`'s two exports. TypeScript pairs a `.d.mts` with the `.mjs`
// module of the same name automatically; this exists only so a `.ts`/`.tsx` importer (today,
// `.storybook/foundations/Colour.stories.tsx`) gets a real type instead of an implicit `any`
// (TS7016) — the same pattern `scripts/visual/review-widths.d.mts` already uses for its own `.mjs`.
// `contrast.mjs`'s own header comment is the source of truth for why each entry point exists; this
// file only has to match its real shape, not restate the reasoning.
export interface Rgb {
  r: number
  g: number
  b: number
}

export declare function contrastRatioRgb(a: Rgb, b: Rgb): number
export declare function contrastRatioHex(hexA: string, hexB: string): number
