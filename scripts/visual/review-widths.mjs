// The three widths this system reviews and captures against — mobile, tablet, desktop.
//
// `packages/design-system/specs/README.md` standing rule 7 is the prose home for what these
// numbers mean and why 375 has no breakpoint counterpart (closes DS-5, T529). This module is the
// one place the literal exists in code — T529's own design was "one home in prose, one consumer in
// code, the number written once," and a second review remediation found `375` had drifted into two
// consumers anyway (`scripts/visual/run.mjs`'s `WIDTHS` and
// `packages/design-system/.storybook/preview.tsx`'s `reviewWidthNarrow` viewport). Both now import
// this array instead of each writing the number again.
export const REVIEW_WIDTHS = [375, 768, 1280]
