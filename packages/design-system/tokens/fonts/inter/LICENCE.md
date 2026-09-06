# Licence record — Inter (design-system `sans` family)

- **Source**: `rsms/inter`, the upstream project. Copied from the pre-built Latin-subset variable web
  font distributed in npm package `@fontsource-variable/inter@5.3.0`, file
  `files/inter-latin-wght-normal.woff2` (upright, weight axis, Latin subset), renamed on copy-in to
  `inter-variable-latin.woff2`. Not re-encoded, not subset further, not modified in any way.
- **Licence**: SIL Open Font License 1.1. The upstream repository's root `LICENSE.txt` (© The Inter
  Project Authors, <https://github.com/rsms/inter>) covers the font files themselves with no
  carve-out — unlike a game-assets pack, there is no `img/README`-style notice narrowing it — and the
  distribution package carries the same text. Both were read before this pack was copied in.
- **Permitted usage**: OFL 1.1 terms — use, study, embed, modify and redistribute the font, including
  as part of a commercial product, on three conditions: it is not sold on its own, any modified
  version is not distributed under the Reserved Font Name, and this licence notice travels with it.
  This project redistributes the file unmodified, under its original name, served from its own
  origin, inside a non-commercial application. No Reserved Font Name is triggered and no condition is
  in tension with anything this project does.
- **Ruling**: **COPY IN**. OFL 1.1 grants this directly. Microsoft's "Game Content Usage Rules"
  reasoning does not apply and must not be read into this pack: a typeface is not game content and
  constitution X's asset permission does not reach it. The pack carries this record because
  `scripts/checks/asset_packs.py` walks every directory under every declared assets root regardless of
  why a given pack is lawful. Self-hosting rather than linking a font service is fixed by
  constitution III (no outbound connection from `apps/*`) and IX (no reader's address handed to a
  non-EU host), not by this ruling.
- **Checked**: 2026-09-05
