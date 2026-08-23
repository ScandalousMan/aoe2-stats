# CaptureStateBadge

**Component**: `src/components/CaptureStateBadge/`
**Feature**: 001, US3 — consumed by `MatchRow` and `MatchDetailPanel`
([`match-history.md`](./match-history.md)), themselves consumed by
`apps/web/src/routes/matches.index.tsx` (T075) and `apps/web/src/routes/matches.$gameId.tsx` (T076)
**Requirements**: FR-019, FR-026, FR-027. SC-010.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Badge` (grows four tone variants
here, see §3), `Skeleton`.

## 1. Purpose

Tell the user, per match, what will happen to their replay — in one word they can read at a glance,
plus the one further sentence that decides whether they have anything to do about it. `replay_captures.status`
carries **seven** raw values (`data-model.md`); this badge is the single place their collapse into a
user-facing state is decided, so no two call sites invent a different mapping.

## 2. Anatomy

```
CaptureStateBadge
├─ Badge              the coloured pill: shared-primitives.md's Badge, one of four new tone variants
└─ SecondaryLine       optional — a countdown or a reason, never both, never invented text
```

Two elements, never more. No icon: per shared-primitives.md's rule for `Badge`, "never communicated
by colour or shape alone" — the label is the carrier, the tone is reinforcement, and an icon here
would be a third channel repeating the same word with the added cost of one more asset to justify
under constitution X (see `shared-primitives.md`'s IP note).

## 3. The four-state collapse (FR-019, FR-026, mandatory — do not re-derive)

| `replay_captures.status`           | Badge label         | Tone      |
| ---------------------------------- | ------------------- | --------- |
| `stored`                           | **Archived**        | `success` |
| `pending`, `downloading`           | **Still catchable** | `warning` |
| `unavailable`, `expired`, `failed` | **Lost**            | `danger`  |
| `quarantined`                      | **Needs review**    | `info`    |

**The user-facing label for `stored` is "Archived", not "safe".** `data-model.md`'s own
one-word-per-side rule states this directly: "'Archived' is the user-facing label for the same
state and appears only in component specs and copy" — this file and its consumers are exactly that
readership. SC-010's prose ("whether its replay is safe, still catchable, or lost") is describing
the _idea_ of the four-way split for a requirements reader, not naming a UI string; `spec.md` and
T065's docstring use "archived" for the rendered label for the same reason. **"Archived" is the only
spelling that may appear on screen, in copy, in Storybook story names and in visual acceptance
criteria for this state — never "safe".**

**`downloading` is not a fifth state.** It means a run holds this row right now; it resolves to
`stored` or `quarantined` within seconds. A user who loads the page mid-cycle sees "Still catchable"
exactly as they would a second before or after — never a fourth label they would have to look up.

**The collapse is in the badge only.** `GET /api/matches` and `GET /api/matches/{game_id}` return
the raw `capture_status` value untouched (`test_matches_list.py`, `test_capture_visibility.py`) —
this component is where the seven values become four, and nowhere else. The three statuses behind
"Lost" travel to this component intact, and it renders the **reason** as `SecondaryLine`, because
they differ in the one way that matters to the reader:

| Raw status    | `SecondaryLine` copy                                                                                       | Why this wording                                                                                                                             |
| ------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `unavailable` | "The game never recorded this match. Your own saved games folder is probably empty too."                   | The source itself has nothing (`data-model.md`: "the source says this replay was never recorded"); a manual upload is very unlikely to help. |
| `expired`     | "The replay existed, but we did not capture it in time. If you still have the file, you can upload it."    | Ours to own — `expired_total` is expected to be permanently zero (`spec.md` FR-025) — and the user's local copy is very likely still there.  |
| `failed`      | "We could not capture this replay after repeated attempts. If you still have the file, you can upload it." | Same recourse as `expired`: the replay existed at the source, capture failed on our side.                                                    |

A badge reading only "Lost" for all three sends both a user with an empty saved-games folder and a
user with the exact file sitting on their disk to the same dead end; this table is why the API keeps
the three statuses separate in the first place (FR-019).

`quarantined`'s `SecondaryLine`: "We have a copy, but it failed validation. It is kept for review —
there is nothing further for you to do." FR-026: the bytes are durably stored and checksummed, only
unreadable; per FR-028's literal "archived" scope, `CaptureStateBadge` and `MatchDetailPanel`
(`match-history.md` §5) do **not** offer a download for this state — the row is evidence for
operators, not a file the product hands the user as their archive.

## 4. Variants and sizes

**Tone** — one of `success`, `warning`, `danger`, `info`, set by the table in §3, never chosen by the
caller. `CaptureStateBadge` takes `captureStatus` (one of the seven raw values) and
`captureDeadlineAt` (ISO 8601 or `null`) as its only inputs and derives the tone, the label and the
`SecondaryLine` itself — a call site never passes a label or a tone directly, which is what keeps
every match row and the detail panel from ever disagreeing about what a given status means.

**Context** — `compact` (inside `MatchRow`: pill and `SecondaryLine` may sit on one line or wrap to
two, whichever the row's own width forces) and `detail` (inside `MatchDetailPanel`: pill and
`SecondaryLine` always stack, `SecondaryLine` renders as a full sentence rather than the shortened
countdown form — see §3's copy versus the countdown format below). Both contexts share every token,
every tone and every label; only the `SecondaryLine`'s phrasing and layout differ.

**Sizes** — none of its own; the pill is `Badge`'s one size (`space-5` tall) in both contexts.

## 5. Badge tone variants (new, added to `shared-primitives.md`'s `Badge`)

Four variants join `neutral` and `accent`, following the same construction: a neutral fill and a
tone-coloured label, never a tone-coloured fill. This is deliberate and reuses, rather than invents,
contrast headroom — the README's measured contrast table already asserts `success`, `warning`,
`danger` and `info` against `surface-raised` at the 4.5:1 normal-text floor in both themes
(`tokens/build-tokens.test.mjs`, "warning clears the 4.5:1 ... floor" and "info, success and danger
clear the 4.5:1 floor", both against `surface-raised`) because `Callout` already renders the
identical pair for its heading. A tone-tinted **fill** would be a new, unmeasured pair and is exactly
the kind of value this spec is not licensed to invent (README: "a spec never publishes a raw value
for a component to copy"); reusing the neutral-fill-plus-coloured-label shape `accent` already
established keeps every pair this badge needs inside what is already measured and already asserted
in the build.

| Variant   | Fill             | Label colour | Boundary             |
| --------- | ---------------- | ------------ | -------------------- |
| `success` | `surface-raised` | `success`    | `border-transparent` |
| `warning` | `surface-raised` | `warning`    | `border-transparent` |
| `danger`  | `surface-raised` | `danger`     | `border-transparent` |
| `info`    | `surface-raised` | `info`       | `border-transparent` |

Unlike `accent` (which substitutes `accent-active` for light theme text because plain `accent` on
`surface-raised` does not clear AA there), none of these four need a per-theme substitution: the
README table shows `success`, `warning`, `danger` and `info` each clear 4.5:1 against `surface-raised`
in **both** themes using the same token in each, so the Tailwind class is a single `text-{tone}`,
with no `dark:` override, mirroring `Badge`'s existing `neutral` variant rather than its `accent`
one.

## 6. States

The interaction-state vocabulary (default / hover / focus-visible / active / disabled / loading /
error / empty) applies to the whole component, not to be confused with the four _capture_ states in
§3.

- **default** — as tabled in §3/§5.
- **hover / focus-visible / active** — none. `Badge`'s own rule holds here unchanged: "a badge is
  not interactive and must never be the control that changes the state it names." Nothing about a
  match's capture state is decided by clicking its badge.
- **disabled** — not applicable, for the same reason.
- **loading** — while the owning row has not yet received `capture_status`, the caller renders a
  `Skeleton/text` sized to the pill's footprint (`space-5` tall, `~90px` wide) in place of
  `CaptureStateBadge` — never a placeholder tone and never an empty pill. Matches `Badge`'s own rule
  that a state change is a `Skeleton`, not a flicker through a wrong colour.
- **error** — `capture_status` is present but is not one of the seven known `CaptureStatus` values
  (a forward-compatibility guard, not an expected case today): render `Badge/neutral` with the raw
  string as the label, and no `SecondaryLine`. Never render nothing, and never guess a tone for a
  value this component cannot honestly classify.
- **empty** — no `ReplayCapture` row exists yet for this match (`capture_status` absent/`null` in the
  API response — `test_matches_list.py`'s own note that this can happen before discovery inserts one,
  T053). Render nothing: an absent badge on a just-discovered match is honest; a badge guessing
  "Still catchable" ahead of the row that would justify it is not. Additionally, if `captureStatus`
  is `pending`/`downloading` but `captureDeadlineAt` is `null` (should not happen per `data-model.md`
  — "every discovered match acquires one at discovery time" — but never trusted blindly): render the
  "Still catchable" pill with no `SecondaryLine`, never a countdown built from a missing value.

## 7. The countdown (`SecondaryLine` for "Still catchable")

`compact` context: `"<N> <unit> left"` — `"6 days left"`, `"18 hours left"`, `"42 minutes left"`.
`detail` context: `"Captures automatically within <N> <unit>."`.

- Unit is **days** while at least 1 full day remains to `capture_deadline_at` (floor, not round —
  "6 days left" never means less than 144 hours remain); **hours** below that while at least 1 full
  hour remains; **minutes** below that. Never seconds — a 21-day budget has no use for second-level
  precision and it would recompute needlessly.
- Correct pluralisation (`"1 day left"`, not `"1 days left"`).
- Recomputed on an interval no coarser than once per minute while the component is mounted; this is
  a text update, not an animation, and carries no transition — §"Numbers before atmosphere"
  (`README.md`) rules out a ticking, second-by-second countdown as motion competing with the number.
- If `capture_deadline_at` has already passed while `capture_status` still reads `pending` or
  `downloading` — a brief, expected read-time race against the daily sweep that has not yet flipped
  the row — render `"Capture window closing"` (`compact`) / `"This capture is due any moment."`
  (`detail`). **Never a negative number, never `"-1 days left"`.**

## 8. Tokens used

Colour: `surface-raised` (pill fill), `success`, `warning`, `danger`, `info` (label, per §5),
`text-secondary` (`SecondaryLine`), `border-transparent` (pill boundary, all four new variants).
Radius `full` (pill). Font: `sans`, size `xs`, weight `semibold`, tracking `wide` for the label
(unchanged from `Badge`); `sans`, size `xs`, weight `normal` for `SecondaryLine`.

Gaps in play: none. Every pair this component needs is already measured and asserted in
`tokens/build-tokens.test.mjs` (§5); no new token or new pair is introduced.

## 9. Spacing

| Between                                                                  | Step      |
| ------------------------------------------------------------------------ | --------- |
| Pill to `SecondaryLine` (stacked, `detail`)                              | `space-1` |
| Pill to `SecondaryLine` (inline, `compact`, when the row is wide enough) | `space-2` |

## 10. Responsive

`compact` context wraps `SecondaryLine` onto its own line below 640px-equivalent row width rather
than truncating — a countdown or a reason is exactly the text this product refuses to ellipsise
(`profile-summary.md`'s "Figures never ellipsise at any viewport" extends here: this is the same
discipline applied to the sentence explaining a figure's absence). `detail` context always stacks,
at every viewport.

## 11. Accessibility

- The label is real text in document order, immediately followed by `SecondaryLine` when present —
  never colour alone, never an `aria-label` standing in for visible text.
- `SecondaryLine`, when it states a reason for `unavailable`/`expired`/`failed`/`quarantined`, is
  programmatically associated with the pill (e.g. `aria-describedby`) so a screen-reader user
  reaches the reason immediately after the label, not only by continuing to read the row.
- The `error` fallback (§6) never omits text: a status this component cannot classify still reads as
  a word, not as a blank pill a screen reader skips silently.
- Contrast per `shared-primitives.md`'s README table, §5 above: all four tones clear 4.5:1 on
  `surface-raised` in both themes.

## 12. Visual acceptance criteria

- [ ] All four tones (`success`/`warning`/`danger`/`info`) are visually distinct from each other and
      from `Badge`'s existing `neutral`/`accent`, in both themes, in the same screenshot.
- [ ] The `stored` story's pill reads "Archived" — never "Safe" — in every place it appears across
      `capture-state-badge.md`, `match-history.md` and their stories.
- [ ] The three "Lost" stories (`unavailable`, `expired`, `failed`) show the identical "Lost" pill
      and three visibly different `SecondaryLine` sentences in the same screenshot set.
- [ ] The "Still catchable" story shows a countdown in the correct unit for its seeded
      `capture_deadline_at` (days / hours / minutes fixtures each get their own story).
- [ ] The "Needs review" story never shows a download affordance in the `MatchDetailPanel` combined
      story (cross-checked against `match-history.md`'s own acceptance criteria).
- [ ] Converting any tone story to greyscale still leaves the four states distinguishable by label
      text alone.
- [ ] Loading story: a `Skeleton` matches the pill's footprint, no reflow against the loaded story.
- [ ] Empty story (no capture row yet): nothing renders where the badge would sit — confirmed by
      overlaying the empty and loaded screenshots and seeing no leftover placeholder.
