# aoe2-stats

Stats and match analysis for Age of Empires II: Definitive Edition. Link your Steam account to your
AoE2 profile, browse your rating history and matches, and have your replays archived automatically.

## Why automatic archival

Replays are only retained for about **31 days** on the official servers. After that they are gone
permanently. This project captures them while they still exist so that analysis can happen later,
whenever the tooling is ready. That ordering — capture first, analyse later — is the core design
constraint of the whole codebase.

## Status

Early bootstrap. See `.specify/memory/constitution.md` for the project's governing principles and
`docs/` for the data-source research and architecture decisions.

## Development

Requirements: Python 3.13+, `uv`, Node 20+, `pnpm`.

```bash
uv sync
pnpm install
```

## Non-commercial

This project is strictly non-commercial and uses no assets from the game.

> aoe2-stats was created under Microsoft's "Game Content Usage Rules" using assets from
> Age of Empires II: Definitive Edition, (c) Microsoft Corporation.

This project is not affiliated with or endorsed by Microsoft or World's Edge.
