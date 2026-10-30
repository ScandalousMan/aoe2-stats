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

**Tier and surface class, per component**:

| Component             | Tier                                        | Surface class                                                                                                                     |
| --------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `DataExportPanel`     | screen (`src/screens/DataExportPanel/`)     | `prose` (README's "Surface density" section) — the contents statement is continuous reading text, `space-3`/`space-6` rhythm (§7) |
| `AccountErasurePanel` | screen (`src/screens/AccountErasurePanel/`) | `prose` — the two consequence groups are read as paragraphs, not scanned as table rows                                            |

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
  | 'minting' // GET in flight — `EraseButton` busy before the dialog first opens, or, once it has,
  // a re-mint with `ConfirmAction` busy (`dialogHasOpened` tells the two apart, `AccountErasurePanel/index.tsx`)
  | 'confirming' // dialog open, token held, waiting for the acknowledged confirm
  | 'erasing' // POST in flight
  | 'confirmation-expired' // 403 from POST: the token aged out; dialog says so
  | 'failed' // POST failed for another reason, or a mint GET failed (§10); dialog says so
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
checked). Loading label, for the re-mint and the erase alike: **Erasing your account…**

`CancelAction`: **Keep my account** (`Button/secondary`; this is `Dialog`'s Escape target — the
accidental key never takes the destructive path, per `Dialog`'s own rule).

`DialogFailure` inside the body:

- Token expired (`confirmation-expired`, the `POST`'s `403`): **Your confirmation expired.** _For your
  safety a confirmation is only good for a few minutes. Confirm again to erase your account._ — the
  next `ConfirmAction` press re-mints (`onRequestConfirmation`) and then erases: one press, no extra
  step and no extra copy; the button reads **Erasing your account…** through both (§5, §9, T751).
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

**hover / focus-visible / active** — owned by the `Button`s, the `DownloadLink`, the `ErasedScreen`'s
privacy-notice link, the `Dialog`'s actions and the `Acknowledgement` checkbox; the sections
themselves are not interactive. The standard
ring (`focus-ring`, `outline-2 outline-offset-2`, gap DS-4) on every one, in both themes, **except
`DownloadLink`**: it is `Button/primary` rendered as an anchor, so it rings inward in
`accent-contrast` at `-outline-offset-4` instead (DS-10, `color-tokens.md` §5, the same override
`Button`'s own `primary` variant carries, T586) — a band of the `accent` fill separates the ring
from the link's own edge on every side, so it reads against that fill (6.07:1 light / 8.07:1 dark),
never against `ReadyRegion`'s `Callout` behind it, which its geometry keeps it from ever touching.

**`DownloadLink`'s own hover and press are not colour alone (T588, README's gap register rows
5/H2 and 6/H3).** Like `Button`'s `primary` variant, `DownloadLink` used to distinguish rest, hover
and press by fill luminance alone (`accent` → `accent-hover` → `accent-active`, 1.26:1/1.28:1 light,
1.25:1/1.57:1 dark) and pressed with an outward `active:ring-2 active:ring-offset-2
active:ring-offset-transparent active:ring-accent-contrast` — but that ring rendered inside
`ReadyRegion`'s `bg-surface-raised` `Callout`, where `accent-contrast` **is** `surface-raised` in
the light theme: the ring measured 1.00:1 there and 1.24:1 in the dark theme, invisible on the
surface it actually sat on, and no story drove `:active` to catch it. An `accent`-filled control
may not distinguish rest, hover and press by fill alone: measured, the accent ramp's steps are
1.25–1.57:1, a difference no still image carries. It also may not ring outward for press — DS-10's
proof (`color-tokens.md` §5) applies to any ring whose adjacencies are the page and an accent fill,
whatever its colour. Its non-colour signal is therefore drawn inside the fill in `accent-contrast`
and clear of the inward focus ring's edge band: the label's underline appears on hover
(`decoration-2`, `underline-offset-2`) and drops to `underline-offset-4` on press, thickness for
hover and position for press, the same two axes `Link` uses (`structural-tier.md` §9). The outward
ring is deleted rather than repositioned — the same class of defect governs every colour it could
have used. Every `accent`-filled control added later follows this, and its press state is captured
as its own component-scoped story so the signal is larger than the comparator's tolerance.

**The `ErasedScreen`'s privacy-notice link is the `Link` primitive at `variant="standalone"`**
(`structural-tier.md` §9; README's gap register row 7/H4; T674, 2026-09-28). It stands alone in its
own paragraph — a navigation link on its own line, not a run of words inside prose — so `standalone`
is the variant its placement calls for, not `inline`: before T674 it was a local anchor in
`AccountErasurePanel`'s source copying `inline`'s ink and underline recipe by hand, which is why it
fell short of the 44×44 touch floor (README's "Minimum interactive footprint") until it became a
real `Link` instance. It does not carry `visited` ink (`Link` never omits it; a one-way terminal
screen simply has no return trip to have visited before). Rest is `link` with a permanent
`decoration-1` underline at `underline-offset-2`, `type-body` at `text-md`, and `standalone`'s own
`py-3` block padding around it (the baseline moved when this landed); hover is `link-hover` and a
`decoration-2` underline at the same offset; press is `link-hover`, `decoration-2`, a
`surface-sunken` fill and a `border-strong` box-shadow ring (`active:ring-2
active:ring-border-strong`) — `standalone`'s own non-colour press signal, not `inline`'s
underline-offset drop, so hover and press are two distinct still frames told apart by the ring
rather than by colour or position; focus-visible is the standard ring above. It sits on `surface`
(§6, DS-9); the press ring's `border-strong` clears the 3:1 non-text floor there (README's contrast
table). `AccountErasurePanel.stories.tsx`'s `ErasedScreenHover`, `ErasedScreenFocusVisible` and
`ErasedScreenActive` capture those three states clipped to the link, and they are judged against
this paragraph.

**disabled** — `DataExportPanel`: none — while a request is in flight or a job is preparing, the
`RequestButton` is in `Button`'s `loading` state: it keeps focus, and a second export cannot start.
`AccountErasurePanel`: `ConfirmAction` is `disabled` while `Acknowledgement` is unchecked — sanctioned
because the act is irreversible and the checkbox beside it _is_ the visible reason `Button` requires —
and for no other reason: a request in flight (the re-mint, the `POST`) makes it `loading`, never
`disabled`. `CancelAction` and `Acknowledgement` are `disabled` only while that request runs (§9);
nothing else ever is: the `EraseButton` is always live, and a right greyed out is withdrawn unspoken.

**loading** — `DataExportPanel`: `requesting` shows the `RequestButton` in its loading state;
`preparing` shows `ProgressRegion` with a `Skeleton` block at the download link's footprint (honouring
`Skeleton`'s 200 ms floor and 10 s ceiling — after 10 s the panel replaces the skeleton with the
`FailureRegion` and a retry, per `Skeleton`'s own rule). `AccountErasurePanel`: `minting` shows the
`EraseButton` busy while the token is fetched; a re-mint inside the open dialog, then `erasing`, show
`ConfirmAction` `loading` as one run, **Erasing your account…**, focus kept, its siblings disabled (§9).

**error** — `DataExportPanel`: `failed` renders `FailureRegion` (`Callout/danger`) with a retry; the
button returns to enabled. `AccountErasurePanel`: `DialogFailure` renders inside the open dialog per
§4.4 — the dialog **stays open** on failure (closing it would lose the message and, worse, leave the
user unsure whether the erasure went through), `ConfirmAction` returns to enabled with the box still
ticked, and nothing was erased. A failed first mint opens it in `failed`, box unticked (§10, T779).

**empty** — `DataExportPanel`: the `idle` state **is** the empty state — no export has been requested
yet — and it is a real rendered state (the contents statement plus the button), never a blank panel;
there is deliberately no "your past exports" list to be empty, because the API has none (§3).
`AccountErasurePanel`: not applicable — it is a single irreversible action, not a collection; there is
no "nothing yet" fact for an empty state to represent, and this is stated rather than omitted.

**selection** — not applicable to either component; neither has a set of items for one to be marked
current within.

**expansion** — not applicable to either component's own page content: the contents statement and
both consequence groups are always fully rendered (§2, §4), never behind a disclosure.
`ConfirmDialog` is a modal (`Dialog`'s own contract, `shared-primitives.md`), not a disclosure that
reveals a surface beside its trigger — it blocks the rest of the page, which `Dialog`'s own spec
already distinguishes from the vocabulary's expansion state.

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
the `ErasedScreen`, which sits on `surface` in `link` with a permanent underline — the pair measured in
[the README's contrast table](./README.md) (`link` on `surface`). `DataExportPanel` renders no inline
link: its one anchor is the `DownloadLink`, a filled control (§5). Neither panel
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
  Escape follows `Dialog`'s own rule (`shared-primitives.md` §Dialog) with `CancelAction` as its
  secondary action — in no state does the accidental key reach `ConfirmAction`.
- **Focus while a confirm is in flight (T751).** A press of `ConfirmAction` leaves focus on it until
  the request settles, on each of two paths: a first confirm, from `confirming` with the token minted
  when the dialog opened, goes straight to `erasing`; a confirm from `confirmation-expired` re-mints
  first (`minting` with `dialogHasOpened`), then goes to `erasing`. For the whole run `ConfirmAction`
  is `Button`'s `loading` (`aria-busy` and `aria-disabled`, never the `disabled` attribute) with
  `loadingLabel` **Erasing your account…**: one frame for both steps, because the press asked for one
  thing, the erasure — a separate "Confirming…" label would flip mid-press and name a step the user
  never chose. Focus is never on `body` or behind the backdrop, and the dialog does not close or
  remount across the step. `CancelAction` is `disabled` and Escape calls nothing for the whole run,
  exactly as during `erasing`: the `POST` follows the `GET` with no further input, so a Cancel live
  during the re-mint would race a `POST` the user already confirmed, and would go live then dead
  under the pointer within one press. The `DialogFailure` callout clears on the press, as on any
  retry. When the run settles in `failed` or another `confirmation-expired`, `ConfirmAction` is
  enabled again with focus still on it; on success the route swaps in `ErasedScreen`.
- **`Acknowledgement` during the run (T751).** The checkbox takes the native `disabled` attribute for
  the whole run, on both paths, and stays ticked; when the run settles in `failed` or
  `confirmation-expired` it is enabled again, still ticked. An untick cannot stop an erasure the
  press already committed, for the reason `CancelAction` is disabled: the `POST` follows the `GET`
  with no further input. A live checkbox would either be ignored — a control misstating its own
  effect, since unticking during the re-mint would still erase — or abort only while the `GET` is
  pending and lapse silently once the `POST` is sent, a meaning that changes under the user's hand
  within one press. Its visible reason is `CancelAction`'s: the busy **Erasing your account…** beside
  it. Its label stays `text-primary`, because the statement the user ticked still stands. No control
  the run disables may keep focus: if, when the run starts, focus is on `Acknowledgement` or
  `CancelAction` (an activation that does not move focus) or has left the dialog (Chromium drops it
  to `body` the moment it disables the focused control), it moves to `ConfirmAction`.
- `Acknowledgement` is a real `<input type="checkbox">` with a `<label>`. While it is unchecked,
  `ConfirmAction` carries the native `disabled` attribute and no `aria-disabled`; during a run its
  `aria-disabled` comes from `Button`'s `loading`, not from the checkbox. The checkbox and its
  44px-min hit area clear the touch minimum.
- `DownloadLink` is an `<a href download>`, not a `<button>`, because it navigates to a file; it is
  never the only carrier of the "ready" meaning — the `ReadyRegion` heading states it in text too.
- The export `ProgressRegion` and `ReadyRegion` announce via `Callout`'s own `role="status"`; the
  `FailureRegion` and `DialogFailure` via `role="alert"`. A `Callout` present at first paint is never
  given `aria-live` (it would double-announce).
- Touch targets: every button, the download link, `ErasedScreen`'s privacy-notice link (`Link`
  `variant="standalone"` since T674 — it stands alone in its own paragraph, not running prose) and
  the acknowledgement checkbox clear 44px. An inline link inside running prose takes WCAG 2.5.5's
  inline exception instead, but neither of these two components renders one.
- Contrast per the README table, both themes: body `text-primary` on `surface`; callout bodies
  `text-primary` on `surface-raised`; callout headings `info` / `success` / `danger` on
  `surface-raised`; the destructive buttons' `danger` label and boundary on `surface`; the
  privacy-notice link `link` on `surface`.
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
- [ ] The heading is visibly heavier than the contents statement beneath it — a token-correct panel
      that gave the paragraph the heading's own weight would leave a reader unsure where the section
      starts, and fails this criterion (FR-063).

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
- [ ] In the token-expired dialog frame — the `ConfirmationExpired` story and
      `/privacy (erasure confirmation expired)`; entered only from a `403` on the `POST` at the end
      of a run, so the box is ticked when it appears (§9) — the copy says the confirmation expired
      and offers to confirm again; the acknowledgement checkbox is ticked and enabled; the confirm
      button is enabled, not in the greyed `surface-sunken` fill and `text-disabled` label it
      carries in the `confirming` frame; nothing claims the account was erased.
- [ ] In the failure dialog frame — the `Failed` story and `/privacy (erasure failed)`; entered from
      a confirmed press, when the `POST` fails other than with a `403` or the re-mint after an
      expiry fails, both leaving the box ticked (§9) — the dialog is still open, the message is
      present, the acknowledgement checkbox is ticked and enabled, and the confirm button is enabled
      again, not greyed as in the `confirming` frame.
- [ ] In the first-mint failure frame — `/privacy (erasure confirmation minting failed)`: the `GET`
      behind "Erase my account" failed, so the dialog opens for the first time already in `failed`,
      before the box could be ticked — the dialog is open, "We could not erase your account." is
      present, the acknowledgement checkbox is unticked and enabled, and the confirm button is
      visibly disabled until it is ticked. No story depicts this frame (T779): its failure callout
      is the `Failed` story's and its gated confirm is the `Confirming` story's; that route
      scenario's unticked-acknowledgement mark and the `initialState` criterion below guard it.
- [ ] In the re-mint frame (`/privacy (erasure re-mint in flight)`: confirm pressed from the
      token-expired dialog, the `GET` still pending), the dialog is open; the confirm button shows a
      spinner and reads "Erasing your account…", the same label as the erasing frame; "Keep my
      account" is visibly disabled; the acknowledgement checkbox is still ticked; the "Your
      confirmation expired." callout is gone; and the focus ring, if shown, is on the confirm button
      — nowhere else, and not absent because focus fell to the page.
- [ ] Keyboard, falsifiable in a unit test (T751), on both paths — a first confirm from the
      `confirming` dialog, and a confirm from the token-expired dialog: with focus on the confirm
      button, Enter leaves `document.activeElement` on that same button while the request is
      pending, after a re-mint resolves into `erasing`, and after the run settles in `failed` or
      token-expired — never `body`. Throughout the run the button has no `disabled` attribute and
      carries `aria-busy="true"` and `aria-disabled="true"`; Escape pressed during it calls neither
      action and the dialog stays open.
- [ ] The checkbox during the run, falsifiable in a unit test (T751): from the token-expired dialog
      with the box ticked, a confirm press leaves the checkbox `disabled` and checked while the
      re-mint is pending; a click on the checkbox or on its label text leaves it checked; when the
      re-mint resolves, `onErase` is called with the new token. After the run settles in `failed`,
      the checkbox is enabled and still checked. With focus on the checkbox, a click on the confirm
      button that does not itself move focus leaves `document.activeElement` on the confirm button,
      never `body`.
- [ ] With the box unchecked, the confirm button carries the `disabled` attribute and no
      `aria-disabled`.
- [ ] The frame each `initialState` opens on, falsifiable in a unit test (T779): `failed` and
      `confirmation-expired` open with the acknowledgement checkbox checked and enabled, and the
      confirm button carrying none of `disabled`, `aria-disabled` and `aria-busy`; `erasing` opens
      with it checked and `disabled`; `confirming` opens with it unchecked and enabled and the
      confirm button `disabled`; `idle` and `minting` open no dialog. The rule names a story's entry
      frame, not a property of `failed`: from `idle`, a first mint that rejects opens the dialog in
      `failed` with the checkbox unchecked and enabled and the confirm button `disabled`.
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
- [ ] Focus ring visible and unclipped on the erase button, on the acknowledgement checkbox, and on
      the confirm and cancel actions, in both themes — each clears 3:1 against the page surface
      behind it (`focus-ring`, README's measured-contrast table). On the download link, the ring is
      `accent-contrast`, inward of the link's own edge with a band of `accent` fill on either side
      of it (`-outline-offset-4`, T586, `color-tokens.md` §5) — visible against that fill (6.07:1
      light / 8.07:1 dark), never against the page surface, which the ring never touches.
- [ ] No game artwork, logo, portrait or in-game font in any frame.
- [ ] "There is no undo" (`medium`) is visibly heavier than the sentence around it (`normal`) — a
      token-correct lede that gave the whole sentence one weight would let the one clause that must
      not be missed blend into the rest, and fails this criterion (FR-063).
