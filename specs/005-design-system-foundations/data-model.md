# Phase 1 — Data Model: Design System Foundations

**Feature**: `005-design-system-foundations` | **Date**: 2026-09-05

This feature adds no database table, no column and no migration. Its entities are the design
system's own structural facts — the things a component, a spec and the verification suite are
checked against. Each is listed with where it lives, what makes it valid, and which mechanical check
holds it true, because an entity nothing asserts is documentation rather than a model.

## 1. Token family

A named group of design decisions of one kind, serving both themes under one set of names.

**Lives in**: one JSON file per family under `packages/design-system/tokens`, generated into CSS
custom properties, Tailwind theme namespaces, custom utilities and TypeScript accessors by
`build-tokens.mjs`.

**Fields**: family name; per-token key and value; for a themed family, a value per theme under the
same key; a `$comment` carrying the rationale and the regeneration instruction.

**Validity**:

- Every token expresses a reusable design decision. One call site is not a justification (FR-004).
- Every token is reachable through the ordinary utility vocabulary. A family whose values can only
  be read as a hand-written `var(--ds-*)` is incomplete, which is what made the icon family a defect
  rather than a feature.
- A themed family carries the same key set in both themes. A key present in one theme only is a
  component that will break when the reader switches.
- Every colour role declares the surfaces it may be painted on (FR-005).

**Families after this feature** — nine, up from seven:

| Family       | Themed | Utility vocabulary                              | Status                          |
| ------------ | ------ | ------------------------------------------------ | ------------------------------- |
| `color`      | yes    | `bg-*`, `text-*`, `border-*`, `outline-*`       | re-derived; gains link roles    |
| `space`      | no     | every numeric utility, via Tailwind's multiplier | gains the rhythm rule           |
| `font`       | no     | `font-*`, `text-*`, plus one utility per role   | re-derived; gains a role group  |
| `radius`     | no     | `rounded-*`                                      | gains role assignment           |
| `elevation`  | yes    | `shadow-*`                                       | gains per-level meaning         |
| `motion`     | no     | `duration-*`, `ease-*`, `animate-*`             | gains an animation group        |
| `icon`       | no     | `icon-*` custom utilities                        | values unchanged, now reachable |
| `breakpoint` | no     | responsive variants, plus a generated TS record | **new**                         |
| `border`     | no     | `border-*`, `outline-*` widths and offsets      | **new**                         |
| `size`       | no     | `max-w-*` via Tailwind's container namespace     | **new**                         |

**Asserted by**: `packages/design-system/tokens/build-tokens.test.mjs` (contrast floors, key-set symmetry across themes)
and `scripts/checks/token-scale.mjs` (nothing off the scale reaches a component).

## 2. Component tier

Where a component sits, what it may depend on, and what kind of specification it owes.

**Lives in**: the directory a component's source is in, which is the tier. Not a manifest, not a
frontmatter field — one fact in one place.

| Tier             | Directory                              | Carries domain knowledge | May depend on              |
| ---------------- | -------------------------------------- | ------------------------ | -------------------------- |
| Primitive        | `packages/design-system/src/primitives` | never                    | tokens, other primitives   |
| Domain composite | `packages/design-system/src/composites` | yes                      | primitives, composites     |
| Screen           | `packages/design-system/src/screens`    | yes                      | primitives, composites     |

**Validity**: a primitive never imports a composite or a screen; nothing in the package imports from
`apps/`; every component is in exactly one tier directory.

**Asserted by**: `scripts/checks/tier-deps.mjs`, run in the web job.

**Migration note**: the assignment already exists in Storybook story id prefixes and is carried over
component by component rather than re-derived. `chrome` collapses into composites — see
[research.md](./research.md) D13.

## 3. Component specification

The nine-section contract, one per component.

**Lives in**: `packages/design-system/specs/<component>.md`, indexed by that directory's `README.md`.

**Sections**: Purpose, Anatomy, Variants and sizes, States, Tokens used, Spacing, Responsive,
Accessibility, Visual acceptance criteria. Unchanged; extended rather than replaced.

**Validity after this feature**:

- Every state in the closed vocabulary is answered — specified, or recorded as inapplicable with
  what happens instead (FR-035). An unanswered state fails a check, not a review.
- The component declares its tier and its surface class.
- Every visual acceptance criterion is decidable from a still image plus the spec, with no source
  reading and no taste judgement (FR-059).
- At least one criterion concerns hierarchy, rhythm or legibility — something a token-correct but
  visually poor implementation would fail (FR-063).

**Asserted by**: a section-and-state completeness check over the specs directory, run in the web job.

## 4. State vocabulary

Closed. Every component spec answers every entry.

**Today (eight)**: default, hover, focus-visible, active, disabled, loading, error, empty.

**After this feature (ten)**: the eight above plus **selection** and **expansion**, which several
components already implement and none names (FR-034).

**Validity**: a state is answered, never merely implemented because the list contains it (FR-036).
Two states of one component are distinguishable by more than colour and in a still image (FR-037).

## 5. Surface class

A property of a surface, assigned per component, not a reader-facing setting and not a per-component
improvisation.

| Class   | Row height and padding | Line rhythm | Typography roles       | Example                  |
| ------- | ---------------------- | ----------- | ---------------------- | ------------------------ |
| `dense` | data-table steps       | tight       | numeric, machine, body | match history, standings |
| `prose` | reading steps          | open        | display, body, supporting | the privacy notice     |

**Lives in**: declared in each component's spec; carried as a prop on the `Panel` and `Table`
primitives; never inferred.

**Validity**: every component declares exactly one class. A component that would need both is two
components or a prop, decided by the admission test.

## 6. Review matrix

The set of captures the verification suite takes, and when each subset runs.

**Axes**: story x theme x width. States are already separate stories, so the state axis is carried
by the story axis rather than duplicated.

| Axis   | Values                    | Count |
| ------ | ------------------------- | ----- |
| story  | every published story     | 299   |
| theme  | light, dark               | 2     |
| width  | 375, 768, 1280            | 3     |

**Full matrix**: 1,794 captures. 25 stories have no baseline today and 3 baselines name stories
that no longer exist; phase 1 reconciles both sets before adding an axis, and a set-equality check
keeps them reconciled ([research.md](./research.md) D2a).

| Run          | Story selection          | Axes           |
| ------------ | ------------------------ | -------------- |
| Pull request | the stories the diff affects | the full matrix |
| Nightly      | every story              | the full matrix |

**Validity**: the runner emits the complete axis set for every story it selects, and exposes no flag
that removes an axis (FR-061). Scope is by story, never by axis.

**Lives in**: `scripts/visual/run.mjs` decides selection and emits the matrix; `tests/visual`
renders what it is told and re-derives nothing. That split exists today and is preserved.

**Companion artifacts**: `packages/design-system/__screenshots__` holds the baselines, regenerated
only by the dispatched workflow on Linux ([research.md](./research.md) D3);
`scripts/visual/a11y-allowlist.json` holds accepted accessibility findings, each dated and naming
the fix owed, and is empty by the end of phase 5.

## 7. Gap register

The list of design decisions the system has not yet made.

**Lives in**: `packages/design-system/specs/README.md`, which stays where it is — its subject is the
package it describes, not the outside world ([research.md](./research.md) D17).

**Entry**: id, gap, impact, interim, action owed. An entry is **open**, **closed** (the token was
admitted) or **refused** (a dated decision not to admit it, naming what components use instead).

**Validity after this feature**: no entry is open with only an interim workaround (FR-002, SC-002).
Ids are never renumbered, so the register and the commit history keep lining up with the defects
they describe — the rule the DS-1, DS-2 and DS-7 closures already followed.

**Disposition of the six open entries**:

| Id   | Disposition                                                                 |
| ---- | --------------------------------------------------------------------------- |
| DS-3 | **Refused**, dated 2026-09-05. No opacity family; attenuation is a colour role. |
| DS-4 | **Closed** by a `border` family — not by ratifying Tailwind's unbounded width scale. |
| DS-5 | **Closed** by a `breakpoint` family with one definition and two generated consumers. |
| DS-6 | **Closed** by a `size` family: page, panel, measure.                         |
| DS-8 | **Closed** by typography roles, with `tabular-nums` making alignment a decision. |
| DS-9 | **Closed** by link, link-hover and link-visited roles, measured on all four surfaces. |

## 8. Measured contrast table

Every colour pair a component actually paints, with its ratio and verdict.

**Lives in**: `packages/design-system/specs/README.md`, beside the register, for the same reason.

**Row**: foreground token, the background **the component that carries it actually paints behind
it**, ratio, verdict. The pairing convention is existing law, learned three times, and is kept
verbatim: a row is derived from usage found by reading the component, never from the background
conventionally associated with a token.

**Validity after this feature**: every row is re-measured against the values that ship (FR-001a);
every pair a component draws has a row, including `text-secondary` on dark `background`, which the
register currently names as drawn and unmeasured; every row carrying an accessibility floor is
asserted by a test.

**Asserted by**: `packages/design-system/tokens/build-tokens.test.mjs`.

## 9. Governance procedure

Four mechanical procedures, each a numbered sequence an agent can execute alone from a cold context.

**Lives in**: `packages/design-system/specs/GOVERNANCE.md`.

| Procedure                | Decides                                          | Records                                        |
| ------------------------ | ------------------------------------------------ | ---------------------------------------------- |
| Token admission          | whether a proposed token is admitted             | the decision, or the existing token that serves |
| Component and variant admission | reuse, consistency or interaction complexity | which of the three justified it                |
| Promotion                | a composition seen three times in the application | promoted, or the reason it was not             |
| Deprecation              | retiring a component or a prop name              | the replacement and every consumer             |

**Validity**: no procedure requires a synchronous human decision (FR-067). Each is applied at least
once during this feature, which is production-readiness item 14 and also the only honest test of
whether it is applicable at all.
