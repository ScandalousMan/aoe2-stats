# ReplayAvailabilityList

**Component**: `src/components/ReplayAvailabilityList/` (internal anatomy piece: `ReplayAvailabilityRow`
— not a separate export, the same relationship `ParticipantRow` has to `MatchDetailPanel` in
[`match-history.md`](./match-history.md))
**Feature**: 003, US3 — consumed by `apps/web/src/features/replays/` (T341), on the same match page
`MatchDetailPanel` renders (`apps/web/src/routes/matches.$gameId.tsx`)
**Requirements**: FR-023, FR-024, FR-025, FR-026, FR-027, FR-028, FR-029. SC-004, SC-005.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Badge` (the four tone variants
[`capture-state-badge.md`](./capture-state-badge.md) §5 already added, plus `neutral`, reused as-is —
no fifth tone is introduced), `Button`, `Callout`, `Skeleton`.
[`capture-state-badge.md`](./capture-state-badge.md) — `countdown.ts`'s remaining-time derivation,
reused rather than reimplemented (§6).

## 1. Purpose

State, per participant, whether their recorded game can be had right now — and never let an
unobtainable one be rendered as a button that then fails (FR-025). This is **not**
`MatchDetailPanel`'s `ParticipantsTable` grown a column: `match-history.md` §11.1 point 2 names this
component explicitly as the separate one FR-023's "one download per participant point of view" needs,
because a download is an action with its own failure modes (rate limits, a boundary race, a stream)
that a table cell showing team/civilisation/result/rating-change has no business carrying.

## 2. Anatomy

```
ReplayAvailabilityList                                one per match, one row per participant
├─ Heading                    h3, "Recorded games" — present even when every row is unobtainable
└─ ReplayAvailabilityRow ×n   same participant order as ParticipantsTable (match-history.md §2):
   │                          grouped by team, so a reader can correlate a name to its download
   │                          status without re-scanning against the table above it
   ├─ ParticipantLabel        alias, text-primary
   ├─ AvailabilityBadge       Badge — one of four label/tone pairs, §3, never chosen by the caller
   ├─ SecondaryLine           countdown (obtainable, when obtainable_until is known) or a one-sentence
   │                          reason (expired / never_recorded) — never present for archived, see §3
   └─ DownloadAction          Button/secondary, "Download" — present only for archived and obtainable
                              (§3); absent, never disabled, for expired and never_recorded, the same
                              "absent, not disabled" rule match-history.md §5 already states for its
                              own DownloadAction and capture-state-badge.md §6 states for its badge
```

**IP note**: no player portrait, no clan crest, no in-game icon anywhere in the row — the alias is set
as text in this system's own typeface, matching every other roster listing in this product.
Constitution X.

## 3. The four states (FR-025, mandatory — do not re-derive)

Each of R8's four `availability` values gets its own label and its own `Badge` tone — **not**
collapsed the way `capture-state-badge.md` §3 collapses seven raw statuses into four labels. FR-025's
"distinguish and display" is stronger here: `expired` and `never_recorded` are both permanently
unobtainable, and folding them into one "Lost" label the way that badge folds three raw statuses would
recreate exactly the failure `capture-state-badge.md` §3 was written to prevent for a different pair
— sending two people with different facts to the same dead end. So the four states never share a
label, and **two of the four never share a tone either**, which is what makes the difference visible
rather than merely readable in small print:

| `availability`   | Badge label        | Tone      | `SecondaryLine`                                                                               | `DownloadAction` |
| ---------------- | ------------------ | --------- | --------------------------------------------------------------------------------------------- | ---------------- |
| `archived`       | **In our archive** | `success` | none — available regardless of the match's age (FR-026), so there is nothing to count down to | present          |
| `obtainable`     | **Obtainable**     | `info`    | countdown to `obtainable_until`, when known — §6; nothing when it is `null` (§3.2)            | present          |
| `expired`        | **Expired**        | `danger`  | "This recording is no longer available from the game." (§3.1)                                 | absent           |
| `never_recorded` | **Never recorded** | `neutral` | "The game did not record this point of view." (§3.1)                                          | absent           |

**Why `expired` and `never_recorded` differ in tone, not only in label.** `danger` on `expired` reads
as a loss — something existed and is now gone, which is exactly what happened. `neutral` (`Badge`'s
own base variant, `shared-primitives.md` §"Badge" — `surface-sunken` fill, `text-secondary` label,
`border` boundary) on `never_recorded` reads as a plain fact with no loss attached — nothing this
service or the source ever had was taken away, because there was never anything to take. A reader
who converts the frame to greyscale still tells them apart from the label alone (§11's own
acceptance criterion), and a reader who does not loses the tone difference too — belt and braces, not
one carrier standing in for the other (README's "colour is never the only carrier of meaning").

**Why `archived` and `obtainable` also differ, though both are actionable.** `success` on `archived`
signals a settled, permanent fact — this service holds the bytes, the match's age cannot change that
(FR-026). `info` on `obtainable` signals a fact that is true **now** and has a horizon — the source
still has it, until it does not. Sharing one tone across both would blur the one distinction US3's
independent test exists to prove: that a third party's recording inside the window and the caller's
own archived recording are not the same kind of "yes" (spec.md US3 acceptance scenario 4 — "the
difference is visible and explained").

### 3.1 `SecondaryLine` copy is normative

The two sentences above (`expired`, `never_recorded`) are exact strings, not placeholders — the same
discipline [`archival-control.md`](./archival-control.md) §4 states for its own normative copy. Two
reasons, not one:

1. **Neither implies fault or invites an upload.** `capture-state-badge.md` §3's equivalent copy for
   the caller's own lost replay ("if you still have the file, you can upload it") does not transfer
   here: FR-027 forbids this service from storing a recording obtained solely to serve a download, so
   there is no "upload it here" affordance for a third party's point of view to invite, and inviting
   one anyway would promise a feature this component does not have.
2. **Neither promises the fact could ever have been otherwise.** "No longer available" states a
   closed door without assigning blame to the user, the source, or this service; "did not record"
   states an absence at the source, plainly, matching `capture-state-badge.md` §3's own reading of the
   equivalent raw status ("the source itself has nothing").

### 3.2 `obtainable_until` can be `null` on an `obtainable` row (FR-024, amended 2026-08-29)

Research R8 records that the retention window's length is, as of this writing, unresolved, and FR-024
therefore requires `obtainable_until` to be `null` while the question is open rather than derived from
a superseded reading. `ReplayAvailabilityList` treats this as an ordinary, expected shape — not a
degraded or error rendering of the row: the **badge and tone still read `Obtainable`/`info`** exactly
as when a date is present (the fact that the recording is obtainable right now is not in question,
only the date it stops being so), and `SecondaryLine` is simply absent, the same "nothing invented"
discipline `capture-state-badge.md` §6's empty state already states for a missing
`capture_deadline_at`. **The countdown formatting logic (§6) is never handed a `null` and asked to
degrade gracefully on its own** — the caller checks for `null` before calling it, the same contract
`describeCaptureCountdown` already has with its own component.

### 3.3 At most one row is ever `archived`, and it is always the caller's own

R8 and FR-026 together mean `archived` can only ever describe the signed-in caller's own captured
point of view — a `retained_recordings` row never produces this state (R8: "a retained recording is
not an archive for this purpose"), so no third party's row can read `archived` no matter how the
match's own archival went. This makes `ReplayAvailabilityList` genuinely viewer-dependent — the same
match page, opened by two different signed-in users, can render a different row as `archived` (or none
at all) for each of them. **This is not the "marked as you" pattern `match-history.md` §11.1 point 1
forbids for `ParticipantsTable`.** That rule exists because a caller-relative highlight on a table of
facts (team, civilisation, result, rating change) would be a second, divergent presentation of the
same match depending on who opened it — exactly what FR-021 forbids. Here the caller-dependence is not
a highlight layered on top of an otherwise-fixed fact; it **is** the fact FR-022 and FR-026
specifically require this service to show ("the archival state of their own replay"), and it renders
identically for every other viewer of that same row (they see `obtainable`/`expired`/`never_recorded`,
never a placeholder implying something is being hidden from them). No `own` flag or styling beyond the
`archived` state itself is needed or added — the state already carries the fact.

## 4. Variants and sizes

No variant axis. `ReplayAvailabilityList` takes its entire content from the participants and their
`availability` (§3); sizing is responsive, not independent (§9). `AvailabilityBadge` is `Badge`'s one
size (`space-5` tall), matching `CaptureStateBadge`'s own rule that the pill never grows a size of its
own.

## 5. States

The interaction-state vocabulary applies to the whole component and, separately, to each row's
`DownloadAction` — not to be confused with the four **availability** states tabled in §3, which are
not this vocabulary's `error` or `empty`.

- **default** — as tabled in §3.
- **hover / focus-visible / active** — `AvailabilityBadge`: none, per `Badge`'s own rule
  (`shared-primitives.md`: "a badge is not interactive"). `DownloadAction`: per `Button`.
- **disabled** — `DownloadAction` has no disabled form, the same rule `match-history.md` §5 states for
  its own: for `expired` and `never_recorded` it is **absent**, not disabled. The badge and
  `SecondaryLine` already say why nothing can be done here; a greyed-out button repeating that next to
  them is noise `match-history.md` §5 already rejects for the same reason.
- **loading**:
  - Before the match detail response arrives: `Heading` renders, one `Skeleton/block` row per the
    smallest known participant count (2, matching `match-history.md` §5's identical rule for
    `ParticipantsTable`) at the row's own footprint. No `0`, no `–`, no partial row.
  - `DownloadAction`, while the stream or the signed URL is being requested: `Button`'s own `loading`
    state, label "Preparing your download…" — the identical label `match-history.md` §5 already uses
    for the caller's own `DownloadAction`, because it is the identical wait for the identical reason.
- **error** — two distinct causes, never merged into one message:
  - **The request could not be started at all** (a network failure, or FR-028's rate limit): the row
    returns to `default` and `DownloadAction` is pressable again (`Button`'s own rule: "the button
    returns to default and to being pressable" — never a state that makes retrying unreachable). A
    `Callout/danger` (`role="alert"`, `shared-primitives.md`'s tone-to-role mapping) renders beneath
    the row: "We could not start that download. Try again." — or, when the cause is FR-028's rate
    limit, "You are downloading too quickly. Try again in `<retry_after>`." with the exact seconds the
    response carries, never a rounded or invented figure.
  - **The boundary race** (`code: "expired_since_page_load"`, `contracts/http-api.md`): a row rendered
    `obtainable` whose download 404s at fetch time. The row transitions **in place** — no page reload —
    to the `expired` badge and tone (§3), `DownloadAction` is removed, and `SecondaryLine` reads "This
    recording expired while you were viewing this page." **This sentence is distinct from both §3.1
    strings**: it is not the static "no longer available" reason a row that loaded already-`expired`
    carries, and it must never be confused with `never_recorded`'s wording — the recording existed
    a moment ago, which `never_recorded`'s copy would misstate. This is the one place `SecondaryLine`
    for an `expired`-tone row differs from §3's table, and it differs for exactly one page load, on
    exactly the row the race touched; a reload of the page shows the plain `expired` copy from then on,
    because the server records the outcome on that same request (FR-025, `contracts/http-api.md`
    §"boundary race").

    **Amended 2026-08-29 — how this row actually reaches that state.** As first written, §5 and §10
    contradicted each other: §10 requires `DownloadAction` to be a real button triggering a same-tab
    navigation, archived and obtainable alike, and a navigation returns nothing a script can observe,
    so no client code could ever detect the 404 that this transition is a reaction to. Written that
    way, the state was reachable from Storybook and from nowhere else — a specified behaviour with no
    path to it in production, which is the shape of gap this repository keeps writing tasks to close.

    §10 wins, and the transition is obtained from the server instead of from the click. `apps/web`
    refetches `GET /api/matches/{game_id}` after a point-of-view download click; T337 has by then
    written the `replay_fetch_misses` row, so the affected row comes back `never_recorded` with a null
    `download_path` and the dead action disappears on its own. That is `contracts/http-api.md`'s own
    sentence — "records the outcome, so the page is right the next time" — delivered literally rather
    than approximated in the client.

    **What that costs, stated rather than hidden**: the wording above is the one thing not delivered.
    The row self-corrects to `never_recorded`'s copy, not to "This recording expired while you were
    viewing this page." The distinction the paragraph above argues for — the recording existed a
    moment ago — is real, and it is preserved in the API (`expired_since_page_load` is a distinct code
    and stays one), but it is not currently shown to the user. Recovering it needs the download to be
    something a script can observe, which §10 refuses for good reasons (CORS on the archived signed-URL
    redirect; a doubled rate-limit unit and a doubled `replay_access_log` row on the obtainable path).
    The states remain in the component and in its stories, unreached by this wiring: they are what a
    later transport would render, not decoration.
- **empty** — a match with no participants is not a case this component receives; `MatchDetailPanel`
  never renders with zero rows (`match-history.md` FR-011). What _is_ a real empty case: **every row
  is `expired`/`never_recorded`** (a match old enough, or unlucky enough, that nothing is obtainable
  from anyone). `Heading` still renders — "Recorded games" is true of the section's subject even when
  its answer is uniformly no — followed by every row exactly as tabled in §3, never collapsed into a
  single "nothing available" callout that would hide which participant is which and why (spec.md US3
  acceptance scenario 2: "not as a button that fails", not as a summary that erases the per-participant
  answer FR-023 requires either).

## 6. The countdown (`SecondaryLine` for `obtainable`)

**Reused, not reinvented.** `capture-state-badge.md` §7 and its `countdown.ts` module already solve
"how much time is left, in the coarsest honest unit, correctly pluralised" — `ReplayAvailabilityList`
calls the same exported function, `describeCaptureCountdown(obtainableUntil, now, 'compact')`, rather
than re-deriving days/hours/minutes, the floor-not-round rule, or the pluralisation a second time.
T340 wires this call; this spec fixes what it must and must not do with the result:

- **Only the `'compact'` context is ever used here.** `describeCaptureCountdown`'s `'detail'` context
  renders "Captures automatically within `<N>` `<unit>`." — a sentence that names _capture_, a process
  this component has nothing to do with (a source-side retention window closing is not this service
  archiving anything). Calling it with `'detail'` would borrow correct arithmetic wrapped in a false
  cause. The `'compact'` output, `"<N> <unit> left"` (e.g. "6 days left", "3 hours left", "42 minutes
  left"), is generic time-remaining phrasing that carries no such claim and is used exactly as that
  function renders it — no local rewording, so the two components can never drift on how a "left"
  sentence reads.
- **Unit selection, flooring and pluralisation are `describeCaptureCountdown`'s own rules,
  unchanged**: days while ≥ 1 full day remains, then hours, then minutes; floored, never rounded;
  correct singular/plural. A story seeded a few hours from `obtainable_until` (T340's own requirement)
  exercises the same hours branch `capture-state-badge.md`'s stories already exercise for
  `capture_deadline_at` — one code path, two callers.
- **Recomputed on an interval no coarser than once per minute** while the row is mounted, matching
  `capture-state-badge.md` §7's own cadence — a text update, no transition, no ticking seconds
  (README's "Numbers before atmosphere").
- **When `describeCaptureCountdown` would return its "window closing" sentence** (`remainingMs <= 0`,
  i.e. `obtainable_until` has passed while the row still reads `obtainable` — the same brief,
  documented race §5's boundary-race case names), `ReplayAvailabilityList` does **not** render that
  sentence. `"Capture window closing"` / `"This capture is due any moment."` both name capture, which
  is doubly wrong here — not only the process, but the fact: a passed `obtainable_until` on this
  component means the row's _displayed_ state has gone stale, not that a countdown is approaching
  zero the way a capture deadline does. The row renders no `SecondaryLine` at all for that one interval
  until the next fetch or the click-time race (§5) resolves it — never a negative number, and never a
  borrowed sentence about a different process.

## 7. Tokens used

Colour: `surface-sunken` (`neutral` badge fill, per `shared-primitives.md`'s `Badge`), `surface-raised`
(the three tone-variant badge fills, `capture-state-badge.md` §5), `success`, `info`, `danger` (badge
labels, per the tones in §3 — `warning` is not used by this component), `text-secondary` (`neutral`
badge label, `SecondaryLine`), `text-primary` (`ParticipantLabel`), `border` (`neutral` badge
boundary), `border-transparent` (the three tone-variant badge boundaries), `border-strong`
(`DownloadAction`'s boundary, per `Button/secondary`), `focus-ring`. No new colour token and no new
pair: every one of these is already measured in the `specs/README.md` contrast table and already
asserted in `tokens/build-tokens.test.mjs` via `Badge`'s and `Button`'s own use.

Typography: `sans` throughout. Sizes: `xs` `semibold` `tracking-wide` for the badge label (`Badge`'s
own, unchanged), `sm` for `ParticipantLabel` and `SecondaryLine`, matching `match-history.md`'s row
text size. Radius: `full` (badge pill), `md` (`DownloadAction`, per `Button`). Motion:
`duration.fast` + `easing.standard` on `DownloadAction`'s own states (per `Button`); the countdown text
update itself carries no transition (§6). Elevation `none` — this is a list of facts and a button, not
a card.

Gaps in play: none. Every token this component needs is already in use by `Badge`, `Button` or
`Callout` elsewhere in this system.

## 8. Spacing

| Between                                                                  | Step                                                                                                                                                                                                  |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Heading` to first row                                                   | `space-4`                                                                                                                                                                                             |
| Between rows                                                             | `space-3`                                                                                                                                                                                             |
| `ParticipantLabel` to `AvailabilityBadge` (inline, ≥ `md`)               | `space-3`                                                                                                                                                                                             |
| `AvailabilityBadge` to `SecondaryLine` (stacked, `<md`)                  | `space-1`                                                                                                                                                                                             |
| Row content to `DownloadAction`                                          | `space-4`                                                                                                                                                                                             |
| `DownloadAction` to its own error `Callout`                              | `space-2`                                                                                                                                                                                             |
| `ReplayAvailabilityList` (whole section) to `ParticipantsTable` above it | `space-8` — the same wide gap `archival-control.md` §7 uses between its own two distinct subjects, because a download action and a table of facts are two different kinds of content on the same page |

## 9. Responsive

- **375** — each row is a stacked card: `ParticipantLabel` and `AvailabilityBadge` on the first line,
  `SecondaryLine` on its own line beneath (never truncated — `profile-summary.md`'s "figures never
  ellipsise" extended to a countdown or a reason, the same rule `capture-state-badge.md` §10 already
  applies to its own `SecondaryLine`), `DownloadAction` full-width beneath, when present.
- **768** — `ParticipantLabel`, `AvailabilityBadge` and `SecondaryLine` sit on one row where the badge
  and secondary text fit without wrapping; `DownloadAction` becomes intrinsic-width, right-aligned.
- **1280** — unchanged from 768 beyond the column's own width; this is a short list (at most eight
  rows, one per participant), not a table, and does not gain a `<table>` layout the way `MatchRow`
  does — a table implies sortable/comparable columns, and there is exactly one comparison a reader
  makes here (is this one obtainable), already legible from the badge alone.

**Do not render both layouts and hide one** — the same rule `match-history.md` §8 and
`profile-summary.md` §8 both state for their own breakpoint changes.

## 10. Accessibility

- `ReplayAvailabilityList` is a `<section aria-labelledby>` headed by `Heading` (`<h3>`); each row is a
  `<li>` inside a `<ul>` — a list of participants and their own facts, matching the semantics
  `player-search.md` uses for its own result rows.
- `AvailabilityBadge`'s label is real text in document order, immediately followed by `SecondaryLine`
  when present — never colour alone, matching `capture-state-badge.md` §11's identical rule for its
  own badge.
- `SecondaryLine`, when present, is programmatically associated with its row's badge (`aria-describedby`)
  — `capture-state-badge.md` §11's rule, restated here because the same failure (a screen-reader user
  reaching the label but not the reason next to it) is possible in this component too.
- `DownloadAction` is a real `<button>` triggering a same-tab navigation to the download endpoint —
  never a bare `<a href>` to an unsigned URL, matching `match-history.md` §9's identical rule; the URL
  is minted per click so FR-029's access-log write happens server-side on that request, on every click,
  archived and obtainable alike.
- The row-level error `Callout` (§5) uses `Callout`'s own tone-to-role mapping — `role="alert"` for the
  rate-limit/failed-request case, and the same for the `expired_since_page_load` transition, since both
  are events the user did not expect and must be told about immediately, not stumbled on.
- Touch target ≥ 44px on every `DownloadAction`.
- Contrast per `specs/README.md`'s measured table: `success`/`info`/`danger` badge labels on
  `surface-raised` and `neutral`'s `text-secondary` on `surface-sunken`, both already asserted in
  `tokens/build-tokens.test.mjs`.
- Zoom to 200% and 320px logical width without horizontal scrolling — no cell truncates because there
  is no table at this component's one breakpoint shape (§9).

## 11. Visual acceptance criteria

- [ ] All four states (`archived`/`obtainable`/`expired`/`never_recorded`) appear in one combined
      story and are each identifiable by label text alone, with no two sharing a label.
- [ ] `expired` and `never_recorded` are visually distinct from each other in the same screenshot —
      different badge tone (`danger` vs `neutral`) and different `SecondaryLine` sentence — not merely
      distinguishable by reading two different strings side by side. Converting the frame to greyscale
      still leaves them distinguishable from the badge label and the sentence alone (README's "colour
      is never the only carrier").
- [ ] `archived` and `obtainable` are visually distinct from each other (`success` vs `info`) in the
      same screenshot, even though both show a `DownloadAction`.
- [ ] The `obtainable` story with a seeded `obtainable_until` shows a countdown in the correct unit;
      a second `obtainable` story with `obtainable_until: null` shows the identical badge and tone
      with no `SecondaryLine` and no invented date — placed in the same frame as the dated story to
      confirm the only difference is the countdown's presence.
- [ ] A story seeded a few hours before `obtainable_until` (T340's own requirement) shows the hours
      unit, not days rounded up and not minutes — confirmed against `capture-state-badge.md`'s
      equivalent hours-unit story, same wording shape.
- [ ] `DownloadAction` is present in exactly the `archived` and `obtainable` stories and absent — never
      disabled — in the `expired` and `never_recorded` stories, cross-checked against
      `match-history.md`'s equivalent criterion for its own `DownloadAction`.
- [ ] The `expired_since_page_load` story shows the row transitioning from `obtainable` to the
      `expired` badge with the boundary-race sentence from §5, visibly different from a story seeded
      already-`expired` with §3.1's plain sentence, in the same frame.
- [ ] The rate-limited story shows the row unchanged (`DownloadAction` still present and pressable) with
      a danger callout beneath it naming the retry time — never a row that looks like it gave up.
- [ ] Loading story: skeleton row count matches the loaded story's row count at the same viewport, no
      reflow between the two.
- [ ] A story with every row `expired`/`never_recorded` still shows the section heading and one row per
      participant — never a single collapsed "nothing available" message.
