# apps/web

The aoe2-stats front end: Vite + React 19 + TypeScript, TanStack Router (file-based) and Query,
Tailwind CSS. See the repository root `README.md` and `CLAUDE.md` for the project overview and
`.specify/memory/constitution.md` for the rules this app must follow — tokens only, no business
logic here (the API owns it), every component ships with a Storybook story in
`packages/design-system`.

This is a scaffold (T003 in `specs/001-steam-link-replay-ingestion/tasks.md`). The real shell —
router, query client, session bootstrap through `GET /api/me`, the API client — lands in T017.

## Commands

Run from the repository root, or with `--filter web` dropped from inside this directory.

```bash
pnpm --filter web dev         # dev server
pnpm --filter web build       # generate routes, typecheck, production build
pnpm --filter web typecheck   # generate routes, typecheck only
pnpm --filter web lint        # oxlint
```

## Routing

File-based, via `@tanstack/router-plugin`: files under `src/routes/` map to routes, `__root.tsx` is
the pathless root layout. `src/routeTree.gen.ts` is generated on every dev/build run and is not
committed — never edit it by hand.
