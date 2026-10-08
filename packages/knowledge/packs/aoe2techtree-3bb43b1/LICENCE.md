# Licence record — aoe2techtree-3bb43b1 knowledge pack

- **Source**: `SiegeEngineers/aoe2techtree`, commit `3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f`
  (2026-09-11) — `data/data.json` (units, buildings, technologies, their costs, training,
  construction and research times, age requirements and prerequisites, and per-civilisation
  unit/building/tech membership), `data/trees/*.json` (one file per civilisation, 56 files), and
  `data/locales/en/strings.json` (the English strings, including civilisation bonus prose), renamed
  on copy-in to the flat `data.json`, `trees/`, `strings.en.json` layout `plan.md`'s Project
  Structure names. Not re-encoded, not filtered, not modified in any way beyond the path rename.
- **Licence**: MIT. The repository root's `LICENSE` (© 2018 HSZemi) covers the code and the data
  files copied here — unlike `img/Civs/` (the directory `packages/game-assets/civilisations/` was
  vendored from), there is no carve-out narrowing the grant over `data/`: no sibling `README` in
  that directory asserts a third-party copyright the way `img/README` does for the icons, so MIT
  applies to these files directly. Re-read at this commit: the root `LICENSE` is unchanged since
  the first pack's commit and `data/` still carries no `README`.
- **Permitted usage**: MIT terms — use, copy, modify, merge, publish, distribute, sublicense and
  sell, with no restriction beyond keeping the copyright and permission notice, which this record
  and the copy of `LICENSE` cited above satisfy.
- **Ruling**: **COPY IN**. MIT grants this directly; no Game Content Usage Rules reasoning applies
  to this ruling, because the files themselves carry an open licence rather than a Microsoft
  game-content notice. The residual risk this ruling accepts is not the flags pack's position: the
  values in these files were produced upstream by reading the game's own data file, which the
  publisher's usage rules do not authorise, even though the resulting file is MIT. This repository
  has already weighed that for this exact source — `docs/data-sources.md` §1 rules this pack's data
  MIT, and the risk register's `docs/risks.md` R7 records the residual — so this record cites both
  and restates neither.
- **Checked**: 2026-10-08
