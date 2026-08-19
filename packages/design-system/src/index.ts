// No component is exported yet — the first component and its story land in T035. See
// `.claude/skills/design-system/SKILL.md` for the eight-point checklist every component added
// here must satisfy before it exists.
//
// Tokens (T016) are exported for the rare consumer that isn't a Tailwind utility class (canvas,
// chart libraries, inline style). Every Tailwind class a component needs — `bg-accent`,
// `shadow-raised`, `p-3` — comes from `tokens/tailwind.css` instead, which every consumer of this
// package must import once (apps/web's global stylesheet, this package's own Storybook preview).
export * from '../tokens/generated/tokens'
