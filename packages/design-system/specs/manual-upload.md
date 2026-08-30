# UploadControl

**Component**: `src/components/UploadControl/`
**Feature**: 001, US4 — "Rescue a replay the system could not get." Built by T083, wired into
`MatchDetailPanel`'s route by T084, and rendered there **only where no archive exists**
([`match-history.md`](./match-history.md) §2: "an upload affordance for a `lost` capture is not part
of `MatchDetailPanel`'s anatomy — it is `UploadControl`, specified separately (T082, US4)").
**Requirements**: FR-029 (upload a replay for one of your own matches that has none), FR-030 (reject a
file that is not a well-formed replay, storing nothing), FR-031 (reject an upload for a match the
caller did not play), FR-032 (never overwrite an existing archive), FR-033 (record that a replay was
manually supplied). US4 acceptance scenarios 1–4; quickstart scenario 8, all four points.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`. It defines its
own file field inline, exactly as `SearchBox` ([`player-search.md`](./player-search.md) §2) and
`ThirdPartyObjectionForm` ([`third-party-objection.md`](./third-party-objection.md) §2) define theirs:
there is no shared form-field primitive, and a file input is not the input either of those two is.
**Sources of truth this behaviour and copy are derived from, and must not contradict**:

- `apps/api/tests/test_manual_upload.py` and `contracts/http-api.md`'s `POST
/api/replays/{game_id}/upload` — the multipart endpoint. Its four outcomes are the four this
  component branches on, by `code`, never by `message` (http-api.md's error-envelope rule):
  - **success** — `200`, body `{"status": "stored", "source": "manual"}` (`CaptureStatus.STORED` /
    `CaptureSource.MANUAL`, FR-033).
  - **`422 invalid_replay`** — the file is not a well-formed replay (FR-030). **Nothing is stored — not
    even `quarantined`**: quarantine is for a capture that validated once and later failed a check, not
    for an upload that never validated at all (`test_manual_upload.py`).
  - **`404 not_found`** — the caller did not play this match (FR-031). This is the **same code**
    `routers/replays.py` already answers for "no such match" and "not yet archived" — deliberately
    indistinguishable causes (FR-045). The copy below respects that: it states the outcome, it does not
    diagnose which indistinguishable cause applied.
  - **`409 already_archived`** — an archive already exists for this `game_id` (FR-032); `stored` is
    terminal and is never overwritten (`data-model.md`).
- [`capture-state-badge.md`](./capture-state-badge.md) §3 owns the **reason** a match is lost and the
  one-line recourse ("If you still have the file, you can upload it." for `expired`/`failed`; "very
  unlikely to help" for `unavailable`). This component renders the **action**, not the reason, and must
  not restate or contradict that line — see §2.

## 1. Purpose

Let a user rescue a match whose replay automatic capture never got, by adding the file from their own
machine, and have it archived and marked as manually supplied — the only route left once the ~31-day
window has closed.

## 2. Anatomy

```
UploadControl                               <section aria-labelledby>; inside MatchDetailPanel
├─ Heading                    h3 — "Add the replay yourself"
├─ Explanation                one short paragraph: what it does, that it is kept unchanged and
│                             marked as supplied by you, and where the file lives (§4.2)
├─ DropZone                   the drop target + file picker; the empty state lives here
│  ├─ DropPrompt             "Drop the .aoe2record file here, or Choose file"
│  ├─ FileInput              <input type="file" accept=".aoe2record"> — visually the Choose file
│  │                         control; the always-present keyboard/click path (drag-drop is extra)
│  └─ FileChip   ×0..1       chosen file: name (font-mono) + size (text-secondary) + Remove button
├─ SubmitButton  ×0..1       Button/primary "Upload and archive" — present only once a file is chosen
└─ OutcomeRegion ×0..1       Callout — the one result of the last attempt (§4.4)
```

`UploadControl` is **not** rendered when the match has a `stored` archive — `DownloadAction` is there
instead ([`match-history.md`](./match-history.md) §2). It is rendered for a match with **no** archive.
The recommended gate for T084 is the three terminal-failure statuses `capture-state-badge.md` groups as
"Lost" — `unavailable`, `expired`, `failed` — and **not** `pending`/`downloading` (capture may still
succeed on its own; offering an upload there invites a needless one that will race the automatic
capture) nor `quarantined` (bytes are already stored; an upload would be the overwrite FR-032 forbids).

**The reason line is not repeated here.** `CaptureStateBadge`'s `SecondaryLine` already tells the user
_why_ this match is lost and whether a local copy is likely to exist. `UploadControl`'s `Heading` and
`Explanation` speak only to the _action_ of adding the file, so the panel never says the same thing
twice, and never says two different things about the same fact.

## 3. Variants, sizes and props

One instance, no variant axis, one size: the full width of the detail panel's content column at every
viewport (§8). No dialog — it is inline panel content, like everything else in `MatchDetailPanel`.

```ts
interface UploadControlProps {
  /** The match this upload is filed under. Goes in the endpoint path; never trusted from the file. */
  gameId: number
  /** POST /api/replays/{gameId}/upload, multipart. Resolves on 200; rejects with a typed reason
   *  carrying the endpoint's `code` so the caller maps it to the right OutcomeRegion. */
  onUpload: (file: File) => Promise<void>
  /** Injected only by stories to pin a fixed state; the route never sets it. */
  initialState?: UploadUiState
}

type UploadUiState =
  | 'idle' // no file chosen — the resting/empty state
  | 'file-chosen' // a file is selected, not yet sent; SubmitButton live
  | 'uploading' // multipart POST in flight, then server-side validation
  | 'succeeded' // 200; OutcomeRegion/success, control collapses to the confirmation
  | 'invalid-replay' // 422 invalid_replay; OutcomeRegion/danger, retryable
  | 'wrong-match' // 404 not_found; OutcomeRegion/danger, retryable
  | 'already-archived' // 409 already_archived; OutcomeRegion/info, no retry — refresh instead
  | 'failed' // network or 5xx; OutcomeRegion/danger, retryable
```

`onUpload` **rejects with a typed reason**, and the caller maps `code → state` exactly:
`invalid_replay → invalid-replay`, `not_found → wrong-match`, `already_archived → already-archived`,
anything else (network, `5xx`, an unrecognised code) `→ failed`. Branching on the `message` string is
forbidden by http-api.md; a new code the front end does not recognise falls to `failed`, never crashes.

## 4. Copy

Normative. The implementer copies these strings; they are not placeholders. A change to what an
outcome means changes here first, and must stay true to `test_manual_upload.py`.

**Banned throughout, each checkable in review:**

- Any claim a file was stored when the endpoint rejected it: "uploaded", "saved", "archived", "done"
  anywhere in a `422`/`404`/`409`/failure frame. The rejection frames say **nothing was stored**, which
  is the literal contract (FR-030's "storing nothing").
- Any suggestion the existing archive was or could be replaced: "overwritten", "replaced", "updated".
  FR-032 is that it is **never** overwritten, and the copy states that, not the opposite.
- The word "safe" for a stored replay — `capture-state-badge.md` §3's rule, carried here: the state is
  **archived**, a fact, not **safe**, a reassurance.
- Reassurance in place of fact: "don't worry", "rest assured", "we've got you covered".
- A shield, lock, padlock or tick icon anywhere in the component. A drop target needs a boundary and a
  prompt, not a safety badge; a badge reframes a data action as a security promise.

### 4.1 Heading

`Heading` (`h3`): **Add the replay yourself**

### 4.2 Explanation

`Explanation`:

> If you still have this match's file, add it and we will keep it exactly as it is, marked as one you
> supplied by hand. Look in your Age of Empires II saved games folder for the file whose name ends
> `.aoe2record`.

### 4.3 The drop zone and the file

`DropPrompt` (empty `DropZone`): **Drop the `.aoe2record` file here, or** — with **Choose file** the
labelled control that opens the picker.

`FileChip` renders the selected file's name in `font-mono` (so a name full of digits reads cleanly, gap
DS-8) and its size in `text-secondary`, with a **Remove** button that returns the control to `idle`.

`SubmitButton`: **Upload and archive** (`Button/primary`). Loading label while the bytes are in flight:
**Uploading…**; once the request is accepted and the server is validating: **Checking the file…**.

### 4.4 Outcomes

`OutcomeRegion`, one at a time, the result of the last attempt:

- **`succeeded`** (`Callout/success`): **Archived from your upload.** _This match's replay is stored now
  and marked as supplied by you. Nothing else about the match changed._ On this state the picker
  collapses; the download this rescue exists to enable appears when the panel next reads the match — see
  §5, **succeeded**.
- **`invalid-replay`** (`422`, `Callout/danger`): **That file is not a replay we can read.** _Nothing
  was stored. Check it is the `.aoe2record` file for this match, taken straight from your saved games
  folder, then try again._
- **`wrong-match`** (`404`, `Callout/danger`): **This file could not be filed to this match.** _Nothing
  was stored. Make sure it is this match's own recording and try again._ — deliberately does not assert
  _why_ (the `404` code is shared with "no such match"; see the header). It states the outcome and the
  one thing the user can act on, and claims nothing it cannot know.
- **`already-archived`** (`409`, `Callout/info`): **This match already has an archived replay.** _Your
  file was not stored, and nothing was overwritten — the copy we already hold is untouched._ Action:
  **Refresh** (`Button/secondary`) — reloads the match so `DownloadAction` (the archive that now exists)
  replaces this control. Info, not danger: the match is fine, the upload was simply unnecessary.
- **`failed`** (network or `5xx`, `Callout/danger`): **The upload did not go through.** _Nothing was
  stored. This was a problem on our side or with the connection, not with your file. Try again when you
  are ready._

## 5. States

The closed vocabulary, all eight, plus the `succeeded` outcome §4.4 names.

**default** — `idle`: `Heading`, `Explanation`, an empty `DropZone` showing `DropPrompt` and the
`Choose file` control. No `SubmitButton` yet (nothing to submit), no `OutcomeRegion`.

**hover** — the `Choose file` control and `SubmitButton` per `Button`; the `DropZone` shows a distinct
drag-over boundary/fill while a file is dragged over it (a `focus-ring`-toned inset). No numeric value
sits behind that fill — there is none in this component.

**focus-visible** — the standard ring (`focus-ring`, `outline-2 outline-offset-2`, gap DS-4) on the
`Choose file` control, the `Remove` button, `SubmitButton` and the `Refresh` button, in both themes.
The ring is never clipped by the `DropZone` boundary.

**active** — pressed states per `Button`; the `DropZone` on a valid drag-over shows its active boundary
tone. Nothing scales.

**disabled** — there is **no resting disabled control**. `SubmitButton` does not exist until a file is
chosen, so it is never rendered as a dead grey button waiting for one (the reasoning
`third-party-objection.md` §5 gives, applied to a control that simply withholds itself rather than
disabling). The only disable is transient: during `uploading`, the `Choose file` control, `Remove` and
`SubmitButton` all disable so the file cannot change under an in-flight request.

**loading** — `uploading`: the form is `aria-busy`, `SubmitButton` shows its loading label (§4.3) and
busy state at its resting width, and the two phases (transfer, then server validation) are announced by
the label switching from **Uploading…** to **Checking the file…**. If a determinate transfer
percentage is available it renders as a `role="progressbar"`; if not, the busy button is the whole
indication — no fake indeterminate bar pretending to know a duration it does not. There is **no
page-load skeleton**: this control fetches nothing to render and is fully present at first paint.

**error** — three distinct rejections and one failure, all recoverable, none ever claiming a partial
success: `invalid-replay` (`422`, danger), `wrong-match` (`404`, danger), `failed` (network/`5xx`,
danger), each returning the control to `file-chosen` with the same file still selected so a retry is one
press away; and `already-archived` (`409`, info), which offers **Refresh** rather than a retry, because
retrying a `409` can only fail the same way. Every one of the four states **nothing was stored**.

**empty** — the `idle` `DropZone` **is** the empty state, and it is a real rendered state: the prompt,
the `Choose file` control and the drag target are all present with no file chosen. There is no
collection here to be otherwise empty, and no "nothing yet" beyond "no file picked", which `idle`
already is.

**succeeded** (outcome) — `OutcomeRegion/success` per §4.4; the picker and `SubmitButton` collapse. The
control does **not** synthesise a download link itself: on success the caller re-reads the match, its
`capture_status` is now `stored`, and `MatchDetailPanel` renders `DownloadAction` in the slot this
control occupied ([`match-history.md`](./match-history.md) §2). The success callout may remain until
that re-render; it never turns into a download button, which is a different component's job.

## 6. Tokens used

Colour: `surface` (the section, on the panel's own background, and the `DropZone` fill), `surface-raised`
(all `Callout` fills — `Callout` is unconditionally raised), `border-strong` (the `DropZone` boundary and
`Button/secondary` boundaries — the 3:1 non-text floor a control owes), `border` (the `FileChip`
separator, decorative only), `text-primary` (heading, explanation, prompt, callout bodies, file name),
`text-secondary` (file size, the saved-games hint), `accent` family via `Button/primary`, `danger`
(`invalid-replay`/`wrong-match`/`failed` callouts), `info` (`already-archived` callout), `success`
(`succeeded` callout), `focus-ring` (rings, and the drag-over boundary/fill). No game-derived mark and
no `warning`/`accent`-only signal carries meaning without its own text.

**Interactive boundary and tone pairs, per the README measured table (both themes, AA / non-text 3:1):**
`border-strong` on `surface` (the `DropZone` and secondary buttons: 3.5 light / 3.8 dark, clears 3:1);
`focus-ring` on `surface` (6.7 / 6.3); `accent-contrast` on the `accent` family for `SubmitButton` (4.9
light / 8.2 dark); `danger` on `surface-raised` (6.2 / 4.6), `info` on `surface-raised` (6.3 / 5.7),
`success` on `surface-raised` (5.6 / 5.8) — every callout heading, both themes. Bodies are `text-primary`
on `surface-raised` (14.5 / 12.0, AAA). Referenced by pair, per the README convention; numbers not
restated as the source of truth.

Typography: family `sans` throughout, except the chosen file **name** in `font-mono` (DS-8). Sizes —
`Heading` `md`; `Explanation`, `DropPrompt` and callout bodies `md`; file name `sm` mono; file size and
saved-games hint `sm`; callout headings `md` weight `semibold`. Weights — `semibold` on the heading and
the bolded lead phrases of each outcome, `normal` elsewhere. No number animates on entry (README rule 1).

Radius `lg` on the `DropZone` and the callouts, `md` on the buttons and the `FileChip`.
Elevation `none` throughout — the `DropZone` is a well defined by its boundary, not a floating card, and
must not compete with the panel's real content for depth.
Motion: `duration.fast` + `easing.standard` on button and drag-over boundary changes; `duration.normal`

- `easing.decelerate` for an `OutcomeRegion` callout appearing; a determinate `progressbar`, when shown,
  advances with no easing curve of its own. Under `prefers-reduced-motion: reduce` every transition is
  `duration.instant` and the progress bar, if present, stops animating and shows its value statically.

Gaps in play: **DS-4** (focus ring), **DS-7** (no icon is required; if a plain, in-house upload glyph is
ever added it sizes from the adjacent font-size and records its origin — an in-house glyph, not a game
asset, and if it ever became one it would still need the recorded licence README §3 requires),
**DS-8** (mono for the file name). **No file-size ceiling is hard-coded**: client-side pre-checks are
limited to the `accept=".aoe2record"` filter, and well-formedness is the server's `invalid_replay` call
alone. A size limit, if wanted, comes from configuration, not a literal in this component — flagged here,
not invented.

## 7. Spacing

| Between                                   | Step                                                            |
| ----------------------------------------- | --------------------------------------------------------------- |
| Section padding (within the panel column) | `space-5` below `md`, `space-6` from `md`                       |
| `Heading` to `Explanation`                | `space-2`                                                       |
| `Explanation` to `DropZone`               | `space-4`                                                       |
| `DropZone` inner padding                  | `space-6` — the target must be comfortably larger than a button |
| `DropPrompt` to `Choose file` control     | `space-3`                                                       |
| `FileChip` inner padding                  | `space-3`                                                       |
| File name to size                         | `space-2`                                                       |
| `DropZone` to `SubmitButton`              | `space-4`                                                       |
| Control to `OutcomeRegion`                | `space-4`                                                       |

## 8. Responsive

- **375** — one column, full width less the panel padding. The `DropZone` spans the column and stays a
  large tap target; `Choose file`, `SubmitButton` and `Refresh` are full width and stack. No horizontal
  scroll. A long file name in the `FileChip` wraps or middle-truncates with the full name in `title` and
  as accessible text — it is never cut without recourse.
- **768** — the `DropZone` holds the column width; `SubmitButton` and `Refresh` take their intrinsic
  width, left-aligned under the zone. The explanation reads as a plain short paragraph within the panel's
  own measure.
- **1280** — identical to 768; the control does not widen beyond the panel column and grows no second
  column or sidebar. The upload path is the same shape at every viewport — a lost replay is rescued the
  same way on a phone as on a desktop.

## 9. Accessibility

- Root is a `<section aria-labelledby>` whose label is the `<h3>` `Heading`; the level sits under
  `MatchDetailPanel`'s own heading and never skips a level.
- The file field is a real `<input type="file" accept=".aoe2record">` with a programmatic `<label>`
  (`for`/`id`); the visible `Choose file` is that label (or a `<button>` that forwards to the input),
  reachable by Tab and activated by Enter/Space. **Drag-and-drop is an enhancement only** — the
  click/keyboard path through the input always works, so the control is never drag-only (WCAG 2.5.7).
- `Remove`, `SubmitButton` (`type="submit"`) and `Refresh` are real `<button>`s inside a `<form>`;
  Enter from the control submits. None is a `<div>` with a handler.
- `OutcomeRegion` announces: `role="status"` for `succeeded` and `already-archived` (success/info),
  `role="alert"` for the three danger rejections, via `Callout`'s tone-to-role mapping. After a
  rejection, focus moves to the `OutcomeRegion` (or back to `Choose file`) so a keyboard or
  screen-reader user learns the result and can act; focus is not left on a control whose meaning just
  changed underneath it.
- During `uploading` the form is `aria-busy="true"`; a determinate transfer, when available, is a
  `role="progressbar"` with `aria-valuemin/max/now`, otherwise the busy `SubmitButton` label carries the
  state and is announced.
- Touch targets ≥ 44px: `Choose file`, `Remove`, `SubmitButton` and `Refresh` each clear 44px in every
  state; the `DropZone` itself is far larger.
- Contrast per the README table, both themes: body/heading/prompt/file-name `text-primary`; file size
  and saved-games hint `text-secondary`; the `DropZone` and secondary-button boundaries `border-strong`
  (3:1 non-text floor); callout headings `danger`/`info`/`success` on `surface-raised`, bodies
  `text-primary`. Colour is never the only signal — every callout leads with a bold text phrase.
- Reading order equals visual order equals DOM order, verified with CSS disabled: heading, explanation,
  drop zone, submit, outcome.
- Zoom to 200% and 320px logical width with no horizontal scroll and no clipped drop zone or file name.

## 10. Visual acceptance criteria

**The control and its resting shape**

- [ ] In the `idle` frame at 375, 768 and 1280, there is a labelled drop zone with a visible `Choose
  file` control and a "Drop the `.aoe2record` file here" prompt, and **no** submit button.
- [ ] The heading reads "Add the replay yourself"; the explanation names the `.aoe2record` file and the
      saved games folder, and says the file is kept unchanged and marked as supplied by the user.
- [ ] `UploadControl` never appears in the same frame as a `DownloadAction` — the two are mutually
      exclusive for one match (archive absent vs `stored`).
- [ ] The reason a match is lost is **not** restated here — that line belongs to `CaptureStateBadge`; no
      frame shows the reason twice.

**Choosing a file and uploading**

- [ ] The `file-chosen` frame shows the file name (monospaced) and size, a `Remove` control, and an
      enabled "Upload and archive" button.
- [ ] The `uploading` frame shows the button busy at its resting width with an "Uploading…" or "Checking
      the file…" label; the file cannot be changed while it is in flight.

**Outcomes — the four the endpoint returns**

- [ ] `succeeded`: a success callout says the replay is archived and marked as supplied by the user; no
      frame calls it "safe".
- [ ] `invalid-replay`: a danger callout states the file is not a readable replay and that **nothing was
      stored**; the file is still selectable for a retry.
- [ ] `wrong-match`: a danger callout states the file could not be filed to this match and that nothing
      was stored, and does **not** assert the user did or did not play it beyond that.
- [ ] `already-archived`: an **info** (not danger) callout states an archive already exists, nothing was
      stored and nothing was overwritten, with a `Refresh` control; no frame implies the archive was
      replaced.
- [ ] `failed`: a danger callout states the upload did not go through, nothing was stored, and it was
      not the user's file at fault; the button is enabled again.
- [ ] No rejection or failure frame contains the words "uploaded", "saved", "archived" or "done" about
      the file, and none implies an overwrite.

**Craft and prohibitions**

- [ ] No shield, lock, padlock or tick icon anywhere in any frame; no game artwork, logo, portrait or
      in-game font.
- [ ] At 375 there is no horizontal scrollbar; drop zone and buttons are full width and a long file name
      does not overflow the column.
- [ ] The focus ring is visible and unclipped on `Choose file`, `Remove`, the submit button and
      `Refresh`, in both themes.
- [ ] The drop zone and callouts carry no shadow; the drop zone reads as a bordered well, not a floating
      card competing with the panel's match data.
