# CaptureStateBadge

**Component**: `src/components/CaptureStateBadge/`
**Feature**: 001, US3 — consumed by `MatchRow` and `MatchDetailPanel`
([`match-history.md`](./match-history.md)), themselves consumed by
`apps/web/src/routes/matches.index.tsx` (T075) and `apps/web/src/routes/matches.$gameId.tsx` (T076)
**Requirements**: FR-019, FR-026, FR-027. SC-010.
**Tier**: composite (`src/composites/`).
**Surface class**: neither `dense` nor `prose` — a pill and an optional line of text, not a surface
with a density of its own to classify.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Badge` (grows four tone variants
here, see §3), `Skeleton`.

## 1. Purpose

Tell the user, per match, what will happen to their replay — in one word they can read at a glance,
plus at most one further sentence, a countdown or a reason (§2). `replay_captures.status`
carries **eight** raw values (`data-model.md`'s seven and `withdrawn`); this badge alone maps a
status and `archivalObjected` to a reading, so two call sites given the same inputs agree (§4).

## 2. Anatomy

```
CaptureStateBadge
├─ Badge              the pill: shared-primitives.md's Badge, one of four tone variants or neutral
└─ SecondaryLine       optional — a countdown or a reason, never both, never invented text
```

Two elements, never more. No icon: per shared-primitives.md's rule for `Badge`, "never communicated
by colour or shape alone" — the label is the carrier, the tone is reinforcement, and an icon here
would be a third channel repeating the same word with the added cost of one more asset to justify
under constitution X (see `shared-primitives.md`'s IP note).

## 3. The five-state collapse (FR-019, FR-026, mandatory — do not re-derive)

| `replay_captures.status`           | Badge label         | Tone      |
| ---------------------------------- | ------------------- | --------- |
| `stored`                           | **Archived**        | `success` |
| `pending`, `downloading`           | **Still catchable** | `warning` |
| `unavailable`, `expired`, `failed` | **Lost**            | `danger`  |
| `quarantined`                      | **Needs review**    | `info`    |
| `withdrawn`                        | **Not archived**    | `neutral` |

**The user-facing label for `stored` is "Archived", not "safe".** `data-model.md`'s own
one-word-per-side rule states this directly: "'Archived' is the user-facing label for the same
state and appears only in component specs and copy" — this file and its consumers are exactly that
readership. SC-010's prose ("whether its replay is safe, still catchable, or lost") is describing
the _idea_ of the four-way split for a requirements reader, not naming a UI string; `spec.md` and
T065's docstring use "archived" for the rendered label for the same reason. **"Archived" is the only
spelling that may appear on screen, in copy, in Storybook story names and in visual acceptance
criteria for this state — never "safe".**

**`downloading` is not a state of its own.** A run holds the row and resolves it to `stored` or
`quarantined` within seconds; without `archivalObjected`, a mid-cycle load reads "Still catchable".

**The collapse is in the badge only.** `GET /api/matches` and `GET /api/matches/{game_id}` return
the raw `capture_status` value untouched (`test_matches_list.py`, `test_capture_visibility.py`) —
this component is where the eight values become five, and nowhere else. The three statuses behind
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

**`withdrawn` is a fifth state, not a fourth "Lost" status (T721).** The write that sets it takes a
row inside a lead before its capture deadline, or past it, and reads ownership as it runs: at that
instant the profile had no active link whose user had not objected. The status says nothing more,
so the copy claims nothing about the deadline, the source, what the row holds or what to do next.
`danger` on every such match of an objector's history is the red banner `archival-control.md` §4.3
rules out, a right turned into a penalty; hence `Badge`'s existing `neutral` variant, no new token
or pair (§8), and the label "Not archived", true of any row that is not `stored`. `SecondaryLine`,
`detail` only: "Automatic capture ended for this match while archival was not running for this
profile." `compact` shows the pill alone: one sentence repeated down an objector's list is that
banner in small print. **No upload, no `MatchDetailPanel` `DownloadAction`**: it is `stored`'s alone
(`match-history.md` §2), and `manual-upload.md` §2's gate stays the three "Lost" statuses, as the
row may hold an object and the match response does not say which rows do (T727).

**An objecting owner reads "Not archived" on a `pending` or `downloading` row (T724).** The claim
refuses that owner's `pending` row and stale `downloading` row, so a countdown would promise a
capture it will not start. With `archivalObjected` (§4) both statuses read "Not archived" in
`neutral`, the pill alone in `compact`; `detail` adds "Archival is off for your account." No upload
or download is offered. A `downloading` row claimed before the objection can still end `stored`.

## 4. Variants and sizes

**Tone** — one of `success`, `warning`, `danger`, `info` or `neutral`, set by §3, never chosen by
the caller. The data inputs are `captureStatus`, `captureDeadlineAt` (ISO 8601 or `null`) and
`archivalObjected` (boolean, default `false`); the badge derives tone, label and `SecondaryLine`
itself, so two call sites given the same inputs agree. `MatchDetailPanel` passes `GET /api/me`'s
`archival_objected` for every match; one no linked profile of the caller played has a `null` status,
so nothing renders. `MatchList` withholds it for `subject="other"` (`match-history.md` §11.3).

**Variant** — `compact` (inside `MatchRow`: pill and `SecondaryLine` may sit on one line or wrap to
two, whichever the row's own width forces) and `detail` (inside `MatchDetailPanel`: they always
stack, and `SecondaryLine` is a full sentence, not §7's shortened form). Both share every token,
tone and label; `SecondaryLine` differs in phrasing, layout and, for "Not archived", presence (§3).
The prop was `context` until T557 (FR-032, FR-066): `GOVERNANCE.md`'s Record has the rename.

**Sizes** — none of its own; the pill is `Badge`'s one size (`space-5` tall) in both variants.

## 5. Badge tone variants (new, added to `shared-primitives.md`'s `Badge`)

Four variants join `neutral` and `accent`, following the same construction: a neutral fill and a
tone-coloured label, never a tone-coloured fill. This reuses contrast headroom rather than inventing
it: the README's measured contrast table already asserts `success`, `warning`, `danger` and `info`
against `surface-raised` at the 4.5:1 normal-text floor in both themes
(`tokens/build-tokens.test.mjs`, "warning clears the 4.5:1 ... floor" and "info, success and danger
clear the 4.5:1 floor"), because `Callout` already renders the identical pair for its heading. A
tone-tinted **fill** would be a new, unmeasured pair, a value this spec is not licensed to invent
(README: "a spec never publishes a raw value for a component to copy").

| Variant   | Fill             | Label colour | Boundary             |
| --------- | ---------------- | ------------ | -------------------- |
| `success` | `surface-raised` | `success`    | `border-transparent` |
| `warning` | `surface-raised` | `warning`    | `border-transparent` |
| `danger`  | `surface-raised` | `danger`     | `border-transparent` |
| `info`    | `surface-raised` | `info`       | `border-transparent` |

Unlike `accent` (which substitutes `accent-active` for light theme text because plain `accent` on
`surface-raised` does not clear AA there), none of these four needs a per-theme substitution: the
README table shows each clears 4.5:1 against `surface-raised` in **both** themes with the same
token, so the class is a single `text-{tone}` with no `dark:` override, as `neutral`'s is.

## 6. States

The interaction-state vocabulary (default / hover / focus-visible / active / disabled / loading /
error / empty) applies to the whole component, not to be confused with §3's five _capture_ states.

- **default** — as tabled in §3/§5.
- **hover / focus-visible / active** — none. `Badge`'s own rule holds here unchanged: "a badge is
  not interactive and must never be the control that changes the state it names." Nothing about a
  match's capture state is decided by clicking its badge.
- **disabled** — not applicable, for the same reason.
- **loading** — while the owning row has not yet received `capture_status`, the caller renders a
  `Skeleton/text` sized to the pill's footprint (`space-5` tall, `~90px` wide) in place of
  `CaptureStateBadge` — never a placeholder tone and never an empty pill. Matches `Badge`'s own rule
  that a state change is a `Skeleton`, not a flicker through a wrong colour.
- **error** — `capture_status` is present but is not one of the eight known `CaptureStatus` values
  (a forward-compatibility guard, not an expected case today): render `Badge/neutral` with the raw
  string as the label, and no `SecondaryLine`. Never render nothing, never guess a tone, and never
  let a known status reach this fallback: `withdrawn` reads "Not archived", never its raw word (§3).
- **empty** — no `ReplayCapture` row exists yet for this match (`capture_status` absent/`null` in the
  API response — `test_matches_list.py`'s own note that this can happen before discovery inserts one,
  T053). Render nothing: an absent badge on a just-discovered match is honest; a badge guessing
  "Still catchable" ahead of the row that would justify it is not. Additionally, if `captureStatus`
  is `pending`/`downloading` but `captureDeadlineAt` is `null` (ruled out by `data-model.md`, never
  trusted): render the pill with no countdown, never one built from a missing value (§7).
- **selection** — not applicable; a capture-state pill is not a set member.
- **expansion** — not applicable; the pill never reveals a second surface. The full sentence in
  `detail`'s `SecondaryLine` is a variant choice (§4), not a disclosure the reader triggers.

## 7. The countdown (`SecondaryLine` for "Still catchable")

`compact` variant: `"<N> <unit> left"` — `"6 days left"`, `"18 hours left"`, `"42 minutes left"`.
`detail` variant: `"Captures automatically within <N> <unit>."`.

- Unit is **days** while at least 1 full day remains to `capture_deadline_at` (floor, not round —
  "6 days left" never means less than 144 hours remain); **hours** below that while at least 1 full
  hour remains; **minutes** below that. Never seconds — a 21-day budget has no use for them.
- Correct pluralisation (`"1 day left"`, not `"1 days left"`).
- Recomputed on an interval no coarser than once per minute while mounted: a text update with no
  transition — §"Numbers before atmosphere" (`README.md`) rules out a second-by-second countdown.
- If `capture_deadline_at` has already passed while `capture_status` still reads `pending` or
  `downloading` — a brief, expected read-time race against the daily sweep that has not yet flipped
  the row — render `"Capture window closing"` (`compact`) / `"This capture is due any moment."`
  (`detail`). **Never a negative number, never `"-1 days left"`.**
- With `archivalObjected` (§3) none of this renders, whatever the deadline, and no interval runs.

## 8. Tokens used

Colour: `surface-raised`, `border-transparent` (tone pill fill and boundary), `success`, `warning`,
`danger`, `info` (label, per §5); `surface-sunken`, `border` (the `neutral` pill of "Not archived");
`text-secondary` (that pill's label, and `SecondaryLine`). Radius `full` (pill). Font: `sans`, size
`xs` throughout; label weight `semibold`, tracking `wide`; `SecondaryLine` weight `normal`.

Gaps in play: none. The four tone pairs are measured and asserted in `tokens/build-tokens.test.mjs`
(§5); `neutral`'s pair is a row of the README table in both themes. No new token, no new pair.

## 9. Spacing

| Between                                                                  | Step      |
| ------------------------------------------------------------------------ | --------- |
| Pill to `SecondaryLine` (stacked, `detail`)                              | `space-1` |
| Pill to `SecondaryLine` (inline, `compact`, when the row is wide enough) | `space-2` |

## 10. Responsive

`compact` wraps `SecondaryLine` onto its own line below 640px-equivalent row width rather than
truncating: a countdown or a reason is never ellipsised (`profile-summary.md`'s "Figures never
ellipsise at any viewport", extended to a sentence). `detail` always stacks, at every viewport.

## 11. Accessibility

- The label is real text in document order, immediately followed by `SecondaryLine` when present —
  never colour alone, never an `aria-label` standing in for visible text.
- `SecondaryLine`, when it states a reason (`unavailable`/`expired`/`failed`/`quarantined`, and
  "Not archived" in `detail`), is programmatically linked to the pill (e.g. `aria-describedby`)
  so a screen-reader user reaches the reason right after the label, not only by reading on.
- The `error` fallback (§6) never omits text: a status this component cannot classify still reads as
  a word, not as a blank pill a screen reader skips silently.
- Contrast per the README table (§5, §8): all four tones clear 4.5:1 on `surface-raised`, and
  `neutral`'s `text-secondary` clears it on `surface-sunken`, in both themes.

## 12. Visual acceptance criteria

- [ ] All four tones (`success`/`warning`/`danger`/`info`) are visually distinct from each other and
      from `Badge`'s existing `neutral`/`accent`, in both themes, in the same screenshot.
- [ ] The `stored` story's pill reads "Archived" — never "Safe" — in every place it appears across
      `capture-state-badge.md`, `match-history.md` and their stories.
- [ ] The three "Lost" stories (`unavailable`, `expired`, `failed`) show the identical "Lost" pill
      and three visibly different `SecondaryLine` sentences in the same screenshot set.
- [ ] The `withdrawn` stories, and the archival-off stories (`pending` six days from its deadline,
      `archivalObjected`), show a "Not archived" pill in `Badge`'s `neutral` paint (sunken fill,
      visible border) — never `danger` or `warning` ink, never the word "withdrawn", never a
      countdown — alone in `compact`, and above its own sentence of §3 in `detail`.
- [ ] The "Still catchable" story shows a countdown in the correct unit for its seeded
      `capture_deadline_at` (days / hours / minutes fixtures each get their own story).
- [ ] In `MatchDetailPanel`'s combined story, "Not archived" and "Needs review" show no download
      affordance (`match-history.md` §10); the upload is gated by `manual-upload.md` §2, not here.
- [ ] Converting any state story to greyscale still leaves the five states distinguishable by label
      text alone.
- [ ] Loading story: a `Skeleton` matches the pill's footprint, no reflow against the loaded story.
- [ ] Empty story (no capture row yet): nothing renders where the badge would sit — confirmed by
      overlaying the empty and loaded screenshots and seeing no leftover placeholder.
- [ ] The pill's label (`xs`, `semibold`, `wide` tracking) reads as legibly as the row's other text
      at the same size, not fainter — a token-correct pill painted in a low-emphasis tone that still
      cleared 4.5:1 could still read as an afterthought beside a `text-primary` alias, and a story
      placing the pill beside a name must show both at equal first-glance legibility (FR-063).
