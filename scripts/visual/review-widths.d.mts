// Declaration for `./review-widths.mjs`'s own single export. TypeScript pairs a `.d.mts` with the
// `.mjs` module of the same name automatically; this exists only so a `.ts`/`.tsx` importer (today,
// `packages/design-system/.storybook/preview.tsx`) gets a real type instead of an implicit `any`
// (TS7016). `review-widths.mjs`'s own comment is the source of truth for why this literal exists —
// this file only has to match its shape, not restate the reasoning.
export declare const REVIEW_WIDTHS: number[]
