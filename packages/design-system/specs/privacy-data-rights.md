# DataExportPanel and AccountErasurePanel

**Components**: `src/components/DataExportPanel/`, `src/components/AccountErasurePanel/`
**Feature**: 001, US5 — both built by T095, composed by the signed-in privacy route
`apps/web/src/routes/privacy.tsx`
**Requirements**: FR-036 (export), FR-037 (erasure, with its explicit confirmation step). Constitution
IX and X.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Skeleton`,
`Dialog`.
**Sources of truth this behaviour and copy are derived from, and must not contradict**:
`apps/api/src/aoe2stats_api/routers/privacy.py` (what `POST /api/privacy/export`,
`GET /api/privacy/export/{id}`, `GET /api/privacy/erase` and `POST /api/privacy/erase` actually do,
and — in `erase_account`'s own docstring — exactly what erasure deletes, clears and pseudonymises),
`packages/storage/src/aoe2stats_storage/models.py` (the columns and the `ondelete` cascades those
routes rely on), `contracts/http-api.md`'s Privacy table, and
[`privacy-notice.md`](./privacy-notice.md) §4.6 (the normative home of the rights descriptions these
two point-of-action controls must agree with).

**The signed-in privacy route composes three controls, in this order.** `apps/web/src/routes/privacy.tsx`
renders, top to bottom: the archival-objection control ([`archival-control.md`](./archival-control.md),
consumed here exactly as it is on the profile page — this file does **not** respan it), then
`DataExportPanel`, then `AccountErasurePanel` last. Erasure is last because it is the one action on
the page that ends the session, and a control that signs the user out must not sit above controls they
might still want to reach. The route carries **no `Button/primary`**: none of the three actions is the
single recommended thing to do on a data-rights page, and `ArchivalControl`'s "Resume archival" is the
only `primary` any of the three ever renders, in one state only. Two primaries on this route is a
review failure.

**Why two design-system components and not route markup.** The same reason
[`privacy-notice.md`](./privacy-notice.md) gives: constitution VI admits no unstoried component, and
the erasure confirmation wording carries a legal obligation (FR-037's "explicit confirmation step").
Wording that no story renders is wording no visual review ever looks at, and an irreversibility
warning silently softened in a route refactor leaves no test red.

**This spec's erasure copy (§4.4) is normative in the stronger sense.** It is the point-of-action
statement of what erasure does and that it cannot be undone. It must agree with
[`privacy-notice.md`](./privacy-notice.md) §4.6's erasure item and with
[`archival-control.md`](./archival-control.md) §4.1's FR-006 statement; a change to what erasure
destroys or preserves changes all the places that describe it, in one PR, and the register/notice
chain in `privacy-notice.md`'s own header governs the order. This file restates the **operational**
list (what happens to your data) and the irreversibility; it does not restate legal-basis prose, whose
one home is the notice.

---

## 1. Purpose

`DataExportPanel`: let a signed-in user take a complete copy of everything this service holds about
them, in one archive, and download it — FR-036, GDPR Art. 15 and 20.

`AccountErasurePanel`: let a signed-in user permanently destroy their account and everything attached
to it, understanding before they confirm that it cannot be undone and exactly what survives — FR-037,
GDPR Art. 17.

## 2. Anatomy

```
DataExportPanel                                   <section aria-labelledby>
├─ Heading                    h2 — "Get a copy of your data"
├─ ContentsStatement          plain text — what the archive contains (§4.1), always visible
├─ RequestButton              Button/secondary — "Export my data"; the sole action in the idle state
├─ ProgressRegion   ×0..1     Callout/info + Skeleton — a job is preparing (status "queued")
├─ ReadyRegion      ×0..1     Callout/success — a job completed; holds DownloadLink + ExpiryNote
│  ├─ DownloadLink            Button/primary rendered as <a href={download_url} download>
│  └─ ExpiryNote              text-secondary — the link stops working after a short while
└─ FailureRegion    ×0..1     Callout/danger — the request or the status poll failed; holds a retry

AccountErasurePanel                               <section aria-labelledby>
├─ Heading                    h2 — "Erase your account"
├─ IrreversibleLede           the plain statement that this is permanent (§4.4), always visible
├─ ConsequenceList            what is destroyed vs. what survives pseudonymised (§4.4), always visible
├─ EraseButton                Button/destructive — "Erase my account" — opens ConfirmDialog
├─ ConfirmDialog    ×0..1     Dialog — the explicit confirmation step (FR-037)
│  ├─ DialogHeading           "This permanently erases your account"
│  ├─ DialogBody              the irreversibility restated + the destroyed/surviving list in brief
│  ├─ Acknowledgement         a required checkbox — "I understand this cannot be undone"
│  ├─ DialogFailure ×0..1     Callout/danger inside the body — token expired, or the write failed
│  ├─ ConfirmAction           Button/destructive — "Erase my account permanently" (secondary slot)
│  └─ CancelAction            Button/secondary — "Keep my account" (Dialog's Escape target)
└─ (on success) → the route replaces the whole panel with the terminal ErasedScreen (§4.4, §5)
```

**`ConsequenceList` is not behind the button.** FR-037's confirmation step is the `ConfirmDialog`, but
what erasure does is stated in full on the page _before_ the user opens it — a consequence a user only
discovers inside the confirmation dialog is a consequence disclosed too late to reconsider calmly.
`ConfirmDialog`'s body carries a brief restatement, not the first appearance of the facts.

**`Acknowledgement` is a real checkbox gating `ConfirmAction`, and this is a decision.** FR-037 says
"explicit". Two backend steps already enforce deliberateness (the `GET` that mints a confirmation
token, then the `POST` that spends it — router docstring); the checkbox makes that deliberateness
_visible and un-fat-fingerable_ in the one dialog where a mis-click is unrecoverable. `ConfirmAction`
is `disabled` until the box is checked. This is the one place in the product where a disabled control
is correct rather than a dead end, because the thing it guards has no undo — §5 says so.

## 3. Variants, sizes and props

Neither component has a variant axis; each is one instance, full width of the route's text column, at
every viewport (§8). There is no size split.

```ts
interface DataExportPanelProps {
  /** POST /api/privacy/export. Resolves to the job id the route then polls. */
  onRequestExport: () => Promise<{ id: string }>
  /** GET /api/privacy/export/{id}. Called on an interval while status is "queued". */
  onPollExport: (id: string) => Promise<ExportStatus>
  /** Injected only by stories to render a fixed state; the route never sets it. */
  initialState?: ExportUiState
}

type ExportStatus = { status: 'queued' } | { status: 'completed'; downloadUrl: string }

type ExportUiState = 'idle' | 'requesting' | 'preparing' | 'ready' | 'failed'

interface AccountErasurePanelProps {
  /** GET /api/privacy/erase. Mints the confirmation token; changes nothing. */
  onRequestConfirmation: () => Promise<{ confirmationToken: string }>
  /** POST /api/privacy/erase with the token. Resolves when the account is gone. */
  onErase: (confirmationToken: string) => Promise<void>
  /** Injected only by stories; the route never sets it. */
  initialState?: ErasureUiState
}

type ErasureUiState =
  | 'idle'
  | 'minting' // GET in flight, opening the dialog
  | 'confirming' // dialog open, token held, waiting for the acknowledged confirm
  | 'erasing' // POST in flight
  | 'confirmation-expired' // 403 from POST: the token aged out; dialog says so
  | 'failed' // POST failed for another reason; dialog says so
  | 'erased' // terminal; the route shows ErasedScreen, not this panel
```

**`DataExportPanel` holds the job id in memory for the session only.** The API exposes no "list my
exports" endpoint — only `GET /api/privacy/export/{id}` by a known id (router). So the panel does not,
and cannot, show a history of past exports; a reload returns it to `idle`. This is a real constraint
for T095 to build against, not an omission: do not design a "your previous exports" list the backend
cannot answer.

**Neither panel is optimistic.** `DataExportPanel` shows a download link only when a poll actually
returned `status: "completed"` with a URL; `AccountErasurePanel` shows the terminal `ErasedScreen`
only after `onErase` resolves. An erasure UI that claims success before the `POST` returns would be
claiming an irreversible act happened when it may not have.

## 4. Copy

Normative. The implementer copies these strings. §4.4 changes in this file first, and only alongside
the [`privacy-notice.md`](./privacy-notice.md) §4.6 change that keeps them in agreement.

**Banned throughout, each checkable in review** (the same discipline
[`privacy-notice.md`](./privacy-notice.md) §4 fixes):

- Reassurance in place of fact: "don't worry", "rest assured", "your data is safe with us", "we've got
  you covered".
- "Anonymous", "anonymised", "anonymisation" for anything erasure does. It **pseudonymises**, and
  constitution IX says the pseudonym is re-identifiable. The wrong word here is a legal claim.
- Any promise of a route that does not exist: "email us", "contact support", "we'll send you a
  confirmation email", "restore from backup". There is no email address and no undo anywhere in this
  system.
- Hedged irreversibility: "this may be difficult to reverse", "contact us if you change your mind".
  It cannot be reversed. Say that.
- A shield, lock, tick or padlock icon anywhere in either component. A safety badge reframes a
  disclosure as a reassurance.

### 4.1 Export — contents statement and states

`Heading`: **Get a copy of your data**

`ContentsStatement`, always visible above the button:

> We build a single archive containing your account record, every Steam sign-in you have made, every
> profile you have ever linked, the match records and per-player rows for those profiles, your
> archived recordings as their original files, your favourites, and the matches you asked us to
> analyse. It does not include cached search results, which are keyed to nobody, and it does not
> include the internal counters that rate-limit the API.

`RequestButton`: **Export my data** (`Button/secondary`). Loading label: **Preparing your export…**

`ProgressRegion` (`Callout/info`, status `queued`): **Your export is being prepared.** _This usually
takes a moment. Keep this tab open until the download link appears — the link is not saved, so leaving
this page means starting a new export._

`ReadyRegion` (`Callout/success`, status `completed`):

- Heading: **Your export is ready.**
- `DownloadLink`: **Download the archive** (`Button/primary` as `<a download>`).
- `ExpiryNote` (`text-secondary`): _This link stops working after a short while. If it has expired,
  start a new export above._

`FailureRegion` (`Callout/danger`): heading **We could not build your export**, body _Nothing was
changed. Try again when you are ready._, action **Try again** (`Button/secondary`) which re-runs the
request.

### 4.2 Export — reserved

(Left intentionally: the export panel has no second sub-block. Numbering keeps §4.3/§4.4 aligned with
the erasure component, which is the copy-heavy one.)

### 4.3 Erasure — page statement (always visible, before the dialog)

`Heading`: **Erase your account**

`IrreversibleLede`, first line after the heading, never behind a control:

> This permanently deletes your account and everything attached to it. **There is no undo, and no
> backup we can restore you from.** Read what stays and what goes before you start.

`ConsequenceList` — two labelled groups, both always rendered:

**What is deleted, for good:**

1. Your account, and your Steam sign-ins.
2. Your session — you are signed out on your very next request.
3. Every profile you linked, and your favourites.
4. Every recording of yours we have archived — the files in storage, not just the rows that point at
   them — and the records of who opened them.

**What survives, and why:**

1. The matches themselves stay, with your profile id replaced by a pseudonymous one, so the other
   players' records stay correct. **That is pseudonymisation, not anonymisation:** we are not claiming
   the result stops being about anyone.
2. The record that you asked to be erased stays, without the link to your account, because it is the
   proof the erasure happened.
3. A recording kept for an analysis you asked us to publish stays, because the published conclusion
   has to remain checkable. Erasing your account removes the record that you were the one who asked; it
   does not delete that recording.

### 4.4 Erasure — the confirmation dialog and the terminal screen

`ConfirmDialog` `DialogHeading`: **This permanently erases your account**

`DialogBody`:

> This cannot be undone. When you confirm, your account, your Steam sign-ins, your session, your
> linked profiles, your favourites and your archived recordings — the files included — are deleted.
> Your match records stay, with your profile id replaced by a pseudonymous one. There is no undo and
> no backup.

`Acknowledgement` checkbox label: **I understand this cannot be undone.**

`ConfirmAction`: **Erase my account permanently** (`Button/destructive`; `disabled` until the box is
checked). Loading label: **Erasing your account…**

`CancelAction`: **Keep my account** (`Button/secondary`; this is `Dialog`'s Escape target — the
accidental key never takes the destructive path, per `Dialog`'s own rule).

`DialogFailure` inside the body:

- Token expired (`confirmation-expired`, the `POST`'s `403`): **Your confirmation expired.** _For your
  safety a confirmation is only good for a few minutes. Confirm again to erase your account._ — and the
  panel silently re-mints a token (re-runs `onRequestConfirmation`) the next time `ConfirmAction` is
  pressed, so the user simply confirms once more.
- Other failure (`failed`): **We could not erase your account.** _Nothing was changed, and your account
  is still here. Try again when you are ready._

`ErasedScreen` — the terminal state the route swaps in when `onErase` resolves (the session is now
invalid, so the panel cannot re-render against `/api/me`):

> **Your account has been erased.** Everything attached to it is gone, and you are signed out.
>
> Your match records remain with a pseudonymous id in place of yours, and the record that you asked to
> be erased remains without any link to you — both are described in the privacy notice. There is
> nothing left here to sign in to.

The `ErasedScreen` carries one link, to the public home or the privacy notice, and **no** "sign back
in" affordance — there is no account to return to.

## 5. States

Answered for both components; where one has no meaningful case, it says why.

**default** — `DataExportPanel`: `idle`, the contents statement and the `RequestButton` only, no
progress or ready region. `AccountErasurePanel`: `idle`, the lede and both consequence groups visible,
the `EraseButton` enabled, no dialog.

**hover / focus-visible / active** — owned by the `Button`s, the `DownloadLink`, the `Dialog`'s
actions and the `Acknowledgement` checkbox; the sections themselves are not interactive. The standard
ring (`focus-ring`, `outline-2 outline-offset-2`, gap DS-4) on every one, in both themes.

**disabled** — `DataExportPanel`: the `RequestButton` disables while a request is in flight or a job is
preparing (its loading label says why), so a second export cannot be started over an unfinished one.
`AccountErasurePanel`: `ConfirmAction` is `disabled` until `Acknowledgement` is checked — the one
sanctioned disabled control in these two specs, because the action it guards is irreversible and the
checkbox beside it _is_ the visible reason (satisfying `Button`'s rule that a disabled button carry a
visible explanation). Nothing else is ever disabled: the `EraseButton` on the page is always live, and
a right that is greyed out has been withdrawn without saying so.

**loading** — `DataExportPanel`: `requesting` shows the `RequestButton` in its loading state;
`preparing` shows `ProgressRegion` with a `Skeleton` block at the download link's footprint (honouring
`Skeleton`'s 200 ms floor and 10 s ceiling — after 10 s the panel replaces the skeleton with the
`FailureRegion` and a retry, per `Skeleton`'s own rule). `AccountErasurePanel`: `minting` shows the
`EraseButton` busy while the token is fetched; `erasing` shows `ConfirmAction` busy with `CancelAction`
disabled for the duration.

**error** — `DataExportPanel`: `failed` renders `FailureRegion` (`Callout/danger`) with a retry; the
button returns to enabled. `AccountErasurePanel`: `DialogFailure` renders inside the open dialog per
§4.4 — the dialog **stays open** on failure (closing it would lose the message and, worse, leave the
user unsure whether the erasure went through), `ConfirmAction` returns to enabled, and `state` is
exactly what it was — nothing was erased.

**empty** — `DataExportPanel`: the `idle` state **is** the empty state — no export has been requested
yet — and it is a real rendered state (the contents statement plus the button), never a blank panel;
there is deliberately no "your past exports" list to be empty, because the API has none (§3).
`AccountErasurePanel`: not applicable — it is a single irreversible action, not a collection; there is
no "nothing yet" fact for an empty state to represent, and this is stated rather than omitted.

## 6. Tokens used

Colour: `surface` (both sections, and the page prose the links sit on), `surface-raised`
(`Callout` fills — `ProgressRegion`, `ReadyRegion`, `FailureRegion`, `DialogFailure`), `surface`
(the `Dialog` surface, per `Dialog`'s own tokens), `overlay` (the `Dialog` backdrop), `border`
(section separators), `text-primary` (all body copy, every heading, the consequence lists),
`text-secondary` (`ExpiryNote`, timestamps), `accent` family via `Button` and the `DownloadLink`,
`danger` (the `destructive` erase controls, and `FailureRegion` / `DialogFailure` stripes and
headings), `success` (`ReadyRegion`), `info` (`ProgressRegion`), `focus-ring`. No `warning`: nothing
here is a "something will go wrong if you do not act" — erasure is a chosen action, framed as danger at
the point of confirmation and as neutral fact everywhere else.

Typography: family `sans` throughout; `display` on the two `h2` headings only. Sizes — section `h2`
`xl`; `DialogHeading` `lg`; body, consequence-list items and callout bodies `md`; `ExpiryNote` and the
`text-secondary` notes `sm`. Weights — `semibold` on headings and on the two `ConsequenceList` group
labels ("What is deleted, for good:", "What survives, and why:"), `medium` on the bolded irreversible
phrases ("There is no undo…", "That is pseudonymisation, not anonymisation:"), `normal` on the rest.

Radius `lg` on callouts, `xl` on the `Dialog` (its own token), `md` on buttons. Elevation `none`
throughout the page; the `Dialog` carries `modal` elevation (its own token) and nothing else does — the
two panels are passages of text with controls, not floating cards.

Motion: `duration.fast` + `easing.standard` on every button and link colour change; `duration.normal` +
`easing.decelerate` for a `Callout` or the `Dialog` appearing; `duration.instant` under
`prefers-reduced-motion: reduce`. **No entrance animation on the consequence list or the irreversible
lede** — a warning that fades in can be dismissed before it is read. No skeleton pulse on the erasure
side at all.

Gaps in play: **DS-4** (focus ring), **DS-5** (breakpoints), **DS-6** (reading measure — both panels
are prose), and **DS-9**: the only inline link in these two components is the privacy-notice link in
the `ErasedScreen` and (optionally) in the export contents statement, and both sit on `surface`, where
`accent` with a permanent underline is the one measured pair (4.9 light / 7.7 dark). Neither panel
paints an inline link on `surface-raised`: the callouts and the dialog body contain **no** inline
links — their forward action is always a `Button`, never a link inside coloured-surface prose.

## 7. Spacing

| Between                                             | Step                                                                                           |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Section padding                                     | `space-6` below `md`, `space-8` from `md`                                                      |
| `h2` to its first paragraph                         | `space-3`                                                                                      |
| `ContentsStatement` to `RequestButton`              | `space-6`                                                                                      |
| `RequestButton` to `ProgressRegion` / `ReadyRegion` | `space-6`                                                                                      |
| `DownloadLink` to `ExpiryNote`                      | `space-2`                                                                                      |
| `IrreversibleLede` to `ConsequenceList`             | `space-6`                                                                                      |
| Between the two consequence groups                  | `space-6`                                                                                      |
| Group label to its first item                       | `space-3`                                                                                      |
| Between consequence-list items                      | `space-3`                                                                                      |
| `ConsequenceList` to `EraseButton`                  | `space-8` — the widest page gap; the button is deliberately set apart from the text it acts on |
| Between the two privacy-route panels                | `space-12` (owned by the route; noted so T095 keeps subjects distinct)                         |
| `Dialog` surface padding                            | `space-6` (Dialog's own)                                                                       |
| `DialogBody` to `Acknowledgement`                   | `space-4`                                                                                      |
| `Acknowledgement` to the action row                 | `space-6`                                                                                      |
| Checkbox to its label                               | `space-2`                                                                                      |

## 8. Responsive

- **375** — one column, full width less the section padding. `RequestButton`, `DownloadLink` and the
  `Dialog`'s two actions are full width and stack (recommended-position action first, per `Button`).
  The `ConfirmDialog` presents as a full-width bottom sheet (`Dialog`'s own responsive rule). No
  horizontal scrolling anywhere. The consequence list stacks as a plain list; nothing is truncated or
  put behind a "read more".
- **768** — text column capped at a 60–75 character measure (gap DS-6), left-aligned, not centred as a
  narrow ribbon. Buttons become intrinsic width, left-aligned with the text; the `Dialog` becomes a
  centred boxed dialog with its actions side by side.
- **1280** — identical to 768; the measure does not widen and no second column or sidebar appears. At
  every viewport the set of consequence-list items and the irreversibility wording is identical —
  layout changes, the disclosure never does.

## 9. Accessibility

- Each panel root is a `<section aria-labelledby>` with its `<h2>`; the route renders exactly one
  `<h1>` above the three panels, and heading levels never skip.
- `ConsequenceList`'s two groups are each an `<h3>` (or a `<p>` label) followed by a `<ul>` — a screen
  reader announces "list, four items" over facts, which is accurate.
- `ConfirmDialog` is `Dialog`: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` on
  `DialogHeading`, focus moved to the heading on open, Tab trapped to the dialog's own focusables, and
  **Escape calls `CancelAction`, never `ConfirmAction`** — the accidental key must never erase the
  account.
- `Acknowledgement` is a real `<input type="checkbox">` with a `<label>`; `ConfirmAction` reflects the
  checked state via `disabled` and `aria-disabled`. The checkbox and its 44px-min hit area clear the
  touch minimum.
- `DownloadLink` is an `<a href download>`, not a `<button>`, because it navigates to a file; it is
  never the only carrier of the "ready" meaning — the `ReadyRegion` heading states it in text too.
- The export `ProgressRegion` and `ReadyRegion` announce via `Callout`'s own `role="status"`; the
  `FailureRegion` and `DialogFailure` via `role="alert"`. A `Callout` present at first paint is never
  given `aria-live` (it would double-announce).
- Touch targets: every button, the download link and the acknowledgement checkbox clear 44px. Inline
  links inside running prose take WCAG 2.5.8's inline exception.
- Contrast per the README table, both themes: body `text-primary` on `surface`; callout bodies
  `text-primary` on `surface-raised`; callout headings `info` / `success` / `danger` on
  `surface-raised`; the destructive buttons' `danger` label and boundary on `surface`; the
  privacy-notice link `accent` on `surface` (the only DS-9-permitted background).
- Reading order equals visual order equals DOM order, verified with CSS disabled: on the erasure panel,
  the irreversible lede and both consequence groups must read **before** the erase button in source, so
  a screen-reader user meets the warning before the control.
- Zoom to 200% and 320px logical width with no horizontal scrolling and no clipped dialog.
- The `ErasedScreen` is reachable and readable with no valid session — it must not attempt any
  authenticated fetch, because there is no longer an account to fetch.

## 10. Visual acceptance criteria

**Export**

- [ ] In the `idle` frame the contents statement and the "Export my data" button are both present; no
      progress or download region is shown.
- [ ] The `preparing` frame shows a single info callout with a skeleton at the download link's
      footprint; no `0`, `–` or placeholder download link appears while preparing.
- [ ] The `ready` frame shows a success callout with a real download link **and** the expiry note; the
      expiry note is present in every ready story.
- [ ] The `failed` frame shows a danger callout with a retry action, and the request button is enabled
      again.
- [ ] No "your previous exports" list appears in any frame.

**Erasure — the wording that is the point of the task**

- [ ] The words **"There is no undo"** appear on the page in the default frame, before any dialog is
      opened, at body size or larger and in `text-primary` (not greyed, not behind a control).
- [ ] Both consequence groups — "What is deleted, for good:" and "What survives, and why:" — are
      visible in the default frame, above the erase button.
- [ ] The word **"pseudonymisation"** (or "pseudonymous") appears in the surviving-data group, and the
      words **"anonymous"** and **"anonymised"** appear **nowhere** in any frame.
- [ ] The `ConfirmDialog` restates that it cannot be undone, shows a required "I understand this cannot
      be undone" checkbox, and the "Erase my account permanently" button is visibly disabled until the
      box is checked.
- [ ] In the token-expired dialog frame, the copy says the confirmation expired and offers to confirm
      again; nothing claims the account was erased.
- [ ] In the failure dialog frame, the dialog is still open, the message is present, and the confirm
      button is enabled again.
- [ ] The `ErasedScreen` frame states the account is erased, names what survives, and carries no "sign
      back in" control.

**Tone, prohibitions and craft (both)**

- [ ] No shield, lock, padlock or tick icon anywhere in any frame.
- [ ] Nothing on the erasure page is coloured `danger` except the erase/confirm buttons and any failure
      callout; the consequence lists are the same text colour as the rest of the page.
- [ ] The route shows at most one `Button/primary` across all three composed panels in any frame.
- [ ] At 375 there is no horizontal scrollbar; the confirm dialog is a full-width sheet with both
      actions at least 44px tall.
- [ ] At 768 and 1280 the text column holds roughly 60–75 characters per line and does not span the
      viewport.
- [ ] Focus ring visible and unclipped on the erase button, on the acknowledgement checkbox, on the
      confirm and cancel actions, and on the download link, in both themes.
- [ ] No game artwork, logo, portrait or in-game font in any frame.
