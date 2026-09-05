# Contract: The structural tier

**Feature**: `005-design-system-foundations` | **Date**: 2026-09-05

Nine primitives that assemble a screen, so that the application writes no layout and no spacing.
This file fixes what each one owns and what it forbids its caller. The visual specification —
anatomy, states, tokens, acceptance criteria — is the `product-designer`'s, in
`packages/design-system/specs/structural-tier.md`.

The test this contract exists to pass: a new route is built from these alone, with no layout or
spacing class written in the application, and its rhythm matches the existing routes without
adjustment (SC-004).

## The nine

| Primitive     | Owns                                                          | The caller may not                             |
| ------------- | ------------------------------------------------------------- | ---------------------------------------------- |
| `Page`        | the single main landmark, the content width, the page padding, the skip-link target | declare any of the four |
| `Section`     | the vertical rhythm between sections, and its heading level   | write a margin between sections                |
| `Panel`       | the bounded surface: background, border, radius, elevation, its surface class | choose a radius or an elevation |
| `Text`        | every typography role, and the role-to-element mapping        | write a font utility directly                  |
| `Link`        | the link roles, the permanent underline, external-link semantics | colour a link by hand                       |
| `Table`       | column semantics, numeric column alignment, the overflow rule, its surface class | write a table element directly |
| `Field`       | the label, hint and error associations, and the error's text  | associate a label by hand                      |
| `EmptyState`  | the explanation, and the action that would fill the region    | render a blank region                          |
| `ErrorState`  | what failed in the reader's terms, and the path forward       | leave the failing control permanently unusable |

## The main landmark, concretely

This is the one existing accessibility defect the feature removes, and it is present on every
authenticated route today.

**Now**: `apps/web/src/routes/__root.tsx` renders `<main id="main-content" tabIndex={-1}>`. Ten
descendants render a second one — nine application containers, plus `SignInScreen` and
`ThirdPartyObjectionForm` inside the design system itself, so a route composing either nests three
deep.

**After**: `Page` renders `<main id="main-content" tabIndex={-1}>`. `__root.tsx` renders a plain
`div` and keeps mounting the header and the footer around the outlet. The skip link's target moves
with the landmark, so the header's call-site obligation is satisfied by `Page` rather than by the
root, and no route can satisfy it wrongly because no route declares it at all.

**Verified by**: a check that counts `main` elements in every rendered route and fails on anything
but one. Cheaper and more reliable than reading a screenshot, which is why the defect survived 279
baselines.

## Spacing: the rhythm rule

FR-008 asks the system to say which step expresses which relationship. Today section spacing is
`mt-6` in three places, `mt-8` in three others and `gap-12` in one, with no rule saying which is
right.

Three named relationships, each assigned one step from the space scale by the `product-designer`:

| Relationship         | Expressed by             |
| -------------------- | ------------------------ |
| Within a component   | the component's own gap  |
| Between components   | `Section`'s internal gap |
| Between sections     | `Page`'s section rhythm  |

The application cannot express any of the three, because FR-021 removes its ability to write spacing
at all. That is what makes the rule hold rather than merely exist.

## Density

Two surface classes, `dense` and `prose`, declared per component in its spec and carried as a prop
on `Panel` and `Table`. Not a reader-facing setting — out of scope by the spec's own assumption —
and not a per-component improvisation, which is the drift it prevents.

## Table overflow

`Table` defines what it does when it is wider than its container, once, rather than each caller
deciding. Numeric columns align on their digits through the `numeric` typography role, so alignment
survives a change of the monospace family. A column of numbers is never the thing that makes the
page scroll horizontally: FR-018 forbids horizontal overflow of the page, and the table's own
overflow is contained within the table.

## Public surface

Everything the package exposes for use is reachable from `packages/design-system/src/index.ts`
(FR-027). Three components are currently built and unimportable — `CountryFlag`, `PlayerAvatar` and
`Tooltip` — and each is resolved explicitly: published, or documented as internal with the reason.
The nine primitives above are all published.

## What this contract does not add

No new domain composite, no new screen, no product behaviour change. Every existing component keeps
its current behaviour and its current public props except where FR-032's prop-vocabulary
reconciliation renames one, and any such rename lands together with every consumer it breaks, in one
change (FR-066).
