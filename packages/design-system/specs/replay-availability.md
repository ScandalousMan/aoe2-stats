# ReplayAvailabilityList

**Component**: `src/components/ReplayAvailabilityList/` (internal anatomy piece: `ReplayAvailabilityRow`
— not a separate export, the same relationship `ParticipantRow` has to `MatchDetailPanel` in
[`match-history.md`](./match-history.md))
**Feature**: 003, US3 — consumed by `apps/web/src/features/replays/` (T341), on the same match page
`MatchDetailPanel` renders (`apps/web/src/routes/matches.$gameId.tsx`)
**Requirements**: FR-023, FR-024, FR-025, FR-026, FR-027, FR-028, FR-029. SC-004, SC-005.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Badge` (the four tone variants
[`capture-state-badge.md`](./capture-state-badge.md) §5 already added, plus `neutral`, reused as-is —
no new tone is introduced; `beyond_window` reuses `warning`, §5.1), `Button`, `Callout`, `Skeleton`.
[`capture-state-badge.md`](./capture-state-badge.md) — `countdown.ts`'s remaining-time derivation,
reused rather than reimplemented (§6).

**Tier**: composite (`src/composites/`).
**Surface class**: `dense` (README's "Surface density" section) — `space-3` between rows (§8), the
same tight rhythm `AnalysisTimeline`'s event list uses.

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
   ├─ AvailabilityBadge       Badge — one of five label/tone pairs, §3, never chosen by the caller
   ├─ SecondaryLine           countdown (obtainable, when obtainable_until is known) or a one-sentence
   │                          reason (beyond_window / expired / never_recorded) — never for archived
   └─ DownloadAction          Button/secondary, "Download" (archived, obtainable) or "Try to download"
                              (beyond_window), §3; absent, never disabled, for expired and never_recorded
                              — match-history.md §5's "absent, not disabled" rule, and capture-state-badge.md §6's
```

**IP note**: no player portrait, no clan crest, no in-game icon anywhere in the row — the alias is set
as text in this system's own typeface, matching every other roster listing in this product.
Constitution X.

## 3. The five states (FR-025, mandatory — do not re-derive)

Each of R8's five `availability` values gets its own label and its own `Badge` tone — **not**
collapsed the way `capture-state-badge.md` §3 collapses eight raw statuses into five labels. FR-025's
"distinguish and display" is stronger here: `expired` and `never_recorded` are both permanently
unobtainable, and folding them into one "Lost" label the way that badge folds three raw statuses would
recreate exactly the failure `capture-state-badge.md` §3 was written to prevent for a different pair
— sending two people with different facts to the same dead end. So the five states never share a
label and never share a tone (**amended 2026-11-10, T842**: five, not four), which is what makes each
difference visible rather than merely readable in small print:

| `availability`   | Badge label                | Tone      | `SecondaryLine`                                                                                                             | `DownloadAction`                  |
| ---------------- | -------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `archived`       | **In our archive**         | `success` | none — available regardless of the match's age (FR-026), so there is nothing to count down to                               | present, "Download"               |
| `obtainable`     | **Obtainable**             | `info`    | countdown to `obtainable_until`, when known — §6; nothing when it is `null` (§3.2)                                          | present, "Download"               |
| `beyond_window`  | **Outside capture window** | `warning` | "This match is outside our capture window; trying asks the game for this recording now, and it may no longer be available." | present, "Try to download" (§5.1) |
| `expired`        | **Expired**                | `danger`  | "This recording is no longer available from the game." (§3.1)                                                               | absent                            |
| `never_recorded` | **Never recorded**         | `neutral` | "The game did not record this point of view." (§3.1)                                                                        | absent                            |

**`never_recorded`, `beyond_window` (and, in §5 below, `downloadState: 'rate_limited'`) are
`snake_case` on purpose (FR-032, T557, README's rule 9).** Every other closed union this package
invents is `kebab-case` — `not-found`, `unknown-result`, `rate-limited` on `SearchBoxState`. These
are not invented: they are the API's own wire spelling, carried straight through with no translation
— `participant.replay.availability` already reads `never_recorded` or `beyond_window` the moment it
leaves `apps/api/src/aoe2stats_api/availability.py`'s `Availability` enum, and `downloadState:
'rate_limited'` is set from the identical `rate_limited` error `code` (`availability.ts`, this
file's own mapper). Translating any of them into this package's own kebab-case convention would buy
nothing and would cost the one property both `availability.ts` and this spec's §5 already lean on:
that the value read here and the value the wire sent are the same string, so a grep for one finds
the other.

**Why `expired` and `never_recorded` differ in tone, not only in label.** Both stand on evidence,
never on arithmetic (**amended 2026-11-10, T842**): `expired` means the source answered "not found"
when asked later than this service's capture budget after the match, which R8 reads as a recording
the game no longer keeps — `danger` reads as that loss. `neutral` (`Badge`'s own base variant,
`shared-primitives.md` §"Badge") on `never_recorded` reads as a plain fact with no loss attached —
there was never anything to take. A reader who converts the frame to greyscale still tells them apart
from the label alone (§11), and the tone difference is a second carrier, not a substitute (README's
"colour is never the only carrier of meaning").

**Why `archived` and `obtainable` also differ, though both are actionable.** `success` on `archived`
signals a settled, permanent fact — this service holds the bytes, the match's age cannot change that
(FR-026). `info` on `obtainable` signals a fact that is true **now** and has a horizon — the source
still has it, until it does not. Sharing one tone across both would blur the one distinction US3's
independent test exists to prove: that a third party's recording inside the window and the caller's
own archived recording are not the same kind of "yes" (spec.md US3 acceptance scenario 4 — "the
difference is visible and explained").

### 3.1 `SecondaryLine` copy is normative

The three sentences above (`beyond_window`, `expired`, `never_recorded`) are exact strings, not
placeholders — the same discipline [`archival-control.md`](./archival-control.md) §4 states for its
own normative copy. Two reasons for the last two, not one (`beyond_window`'s own are in §5.1):

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

Research R8 records why FR-024 requires `obtainable_until` to be `null` in every state (re-derived
2026-10-27): the window belongs to each profile, so no date can be derived that the source will
honour, and the list is never handed one. `ReplayAvailabilityList` treats this as an ordinary, expected shape — not a
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
identically for every other viewer of that same row (they see one of the other four states, never a
placeholder implying something is being hidden from them). No `own` flag or styling beyond the
`archived` state itself is needed or added — the state already carries the fact.

## 4. Variants and sizes

No variant axis. `ReplayAvailabilityList` takes its entire content from the participants and their
`availability` (§3); sizing is responsive, not independent (§9). `AvailabilityBadge` is `Badge`'s one
size (`space-5` tall), matching `CaptureStateBadge`'s own rule that the pill never grows a size of its
own.

## 5. States

The interaction-state vocabulary applies to the whole component and, separately, to each row's
`DownloadAction` — not to be confused with the five **availability** states tabled in §3, which are
not this vocabulary's `error` or `empty`.

- **default** — as tabled in §3.
- **hover / focus-visible / active** — `AvailabilityBadge`: none, per `Badge`'s own rule
  (`shared-primitives.md`: "a badge is not interactive"). `DownloadAction`: per `Button`.
- **disabled** — `DownloadAction` has no disabled form, the same rule `match-history.md` §5 states for
  its own: for `expired` and `never_recorded` it is **absent**, not disabled. The badge and
  `SecondaryLine` already say why nothing can be done here; a greyed-out button repeating that next to
  them is noise `match-history.md` §5 already rejects for the same reason. **Amended 2026-11-10
  (T842)**: on a `beyond_window` row it is present and enabled — never disabled "because it might
  fail". The attempt is the action; §5.1 says why that is not a button that fails.
- **loading**:
  - Before the match detail response arrives: `Heading` renders, one `Skeleton/block` row per the
    smallest known participant count (2, matching `match-history.md` §5's identical rule for
    `ParticipantsTable`) at the row's own footprint. No `0`, no `–`, no partial row.
  - `DownloadAction`, while the stream or the signed URL is being requested: `Button`'s own `loading`
    state, label "Preparing your download…" — the identical label `match-history.md` §5 already uses
    for the caller's own `DownloadAction`, because it is the identical wait for the identical reason.
  - **Added 2026-11-10 (T842)** — `DownloadAction` on a `beyond_window` row, while the source is
    being asked: the same `Button` `loading` state, label "Asking the game for this recording…".
    Not "Preparing your download…": that label promises a file at the end of the wait, and this wait
    may end in "not found" (§5.1). Same mechanism, same same-tab navigation, a different promise.
- **error** — two distinct causes, never merged into one message. **All three of the states below are
  now reachable in production**, through the one `303` redirect mechanism the 2026-08-29 amendment
  below describes: the generic failed-request `Callout`, the rate-limited `Callout` (with a
  `retry_after` where the response carries one), and the boundary race's transition to the `expired`
  badge (via that same reload, not in place — corrected 2026-08-29, below). Every point-of-view
  download failure used to navigate the browser to a raw JSON error page before any of the three could
  render at all — a first attempt at a fix addressed only the boundary race's own wording (retiring it
  to `never_recorded`'s copy, below) and never mentioned that the other two shared the identical root
  cause and were equally unreachable. **Amended 2026-11-10 (T842)**: a `beyond_window` row takes the
  generic failed-request and rate-limited states exactly as an `obtainable` row does — the row keeps
  its `beyond_window` badge, line and pressable "Try to download", with the `Callout` beneath. A
  `replay_error=expired` answer is none of these three: it is the last bullet of this list.
  - **The generic failed-request Callout**: the reload this route's `303` triggers
    (`apps/api/.../routers/replays.py`'s `_match_page_redirect_for_download_failure`) finds the row's
    state has moved since the page loaded — `not_found` (the `archived` branch's own ownership check
    failed a second time, or the caller is not this match's participant), `never_recorded`, the
    `404` codes `download_replay_point_of_view` raises for those states, or
    `source_unavailable` — its own `502`, raised when the replay source itself answers a 5xx, times
    out, or answers a status that is neither `200` nor `404`: the source failing this service, not
    evidence the recording never existed, and folded into this same generic bullet rather than
    `never_recorded`'s because a reader must not conclude from the copy that the game never recorded
    it (**added 2026-08-29**). **Amended 2026-11-10 (T842)**: `expired` has left this list. It used
    to be listed here as a third `404` code; it is now always rendered as the row's answer, with no
    `Callout` at all — see "`replay_error=expired` is an answer, not a failure" below.
    **Narrowed 2026-08-29 — never a _client-side_ network failure**: `DownloadAction` triggers a
    same-tab navigation (`apps/web/src/features/replays/api.ts`'s
    `triggerReplayPointOfViewDownload`), not a `fetch`, so a failure in _this browser's_ connection to
    `apps/api` is not a thing this component can observe or distinguish — there is no script left
    running to catch it. That says nothing about the leg beyond `apps/api`: a _source-side_ failure
    (`source_unavailable`, above) is exactly this service reaching `aoe.ms` and getting a 5xx, a
    timeout or an unrecognised status, and it reaches this row the same way every other 404 above
    does — as a completed `303` response, not a dropped connection. The row returns to `default` and
    `DownloadAction` is pressable again (`Button`'s own rule: "the button returns to default and to
    being pressable" — never a state that makes retrying unreachable). A `Callout/danger`
    (`role="alert"`, `shared-primitives.md`'s tone-to-role mapping) renders beneath the row: "We could
    not start that download. Try again." — the identical copy for all three codes now, since none of
    them is worth a more specific message of its own here
    (`apps/web/src/features/replays/availability.ts`'s own mapping).
  - **FR-028's rate limit** takes its own `rate_limited` `downloadState`
    (`ReplayAvailabilityList`'s own type, `index.tsx`), never this generic bullet. Two distinct causes
    answer the identical `rate_limited` code, and only one of them has a figure to give: this
    service's own per-caller limit (`_apply_replay_download_rate_limit`, FR-028) knows its own
    `retry_after` and carries it through as `<retry_after>`; the replay **source** refusing this
    service's own outbound request (`_source_rate_limited_error`, a 403/429 `aoe.ms` itself returns)
    carries none, because `aoe.ms` gives this service nothing to pass on. The `Callout/danger` reads
    "You are downloading too quickly. Try again in `<retry_after>`." with the exact seconds the
    response carries, never a rounded or invented figure, when one is present, and falls back to the
    identical "We could not start that download. Try again." copy above when it is not
    (`ReplayAvailabilityRowData.retryAfterSeconds`'s own null-check, `index.tsx`).
  - **The boundary race** (`code: "expired_since_page_load"`, `contracts/http-api.md`): a row rendered
    `obtainable` whose download 404s at fetch time. **Corrected 2026-08-29**: this used to say the row
    transitions "in place — no page reload". It does not, and the amendment below this bullet says so
    at length — the row reaches the `expired` badge and tone (§3) through the same-tab `303` reload
    every other case in this section uses, never in place, because no script observes the navigation
    that carries the failure. `DownloadAction` is removed, and `SecondaryLine` reads "This
    recording expired while you were viewing this page." **This sentence is distinct from both §3.1
    strings**: it is not the static "no longer available" reason a row that loaded already-`expired`
    carries, and it must never be confused with `never_recorded`'s wording — the recording existed
    a moment ago, which `never_recorded`'s copy would misstate. This is the one place `SecondaryLine`
    for an `expired`-tone row differs from §3's table, and it differs for exactly one page load, on
    exactly the row the race touched; the server records the outcome on that request only past the
    grace, so a reload reads `never_recorded` then and offers `obtainable` again inside it (FR-025,
    `contracts/http-api.md` §"boundary race"). Unchanged by T842 (2026-11-10): it applies to an
    `obtainable` row only; a `beyond_window` row answers `expired`, the last bullet below.

    **Amended 2026-08-29 — how this row actually reaches that state.** As first written, §5 and §10
    contradicted each other: §10 requires `DownloadAction` to be a real button triggering a same-tab
    navigation, archived and obtainable alike, and a navigation returns nothing a script can observe,
    so no client code could ever detect the 404 that this transition is a reaction to. A first fix
    tried to work around that from the click side — a `setTimeout`-deferred `matchQuery.refetch()` in
    `MatchDetailContainer.tsx`, intending the row to self-correct once `apps/api` had recorded the
    outcome. It did not work: a `200` carrying `content-disposition: attachment` does not navigate
    (nothing to correct), and every failure response was plain JSON with no such header, so the
    browser _did_ navigate on a failure — destroying the SPA, and the pending timeout along with it,
    before the refetch ever ran. A user who hit this state was left looking at a raw JSON error page,
    not at this row transitioning to anything.

    **§10 wins, and the transition is obtained from the server instead of from the click — as a
    redirect, not a refetch.** `GET /api/matches/{game_id}/replay/{profile_id}`
    (`apps/api/.../routers/replays.py`'s `_match_page_redirect_for_download_failure`) answers a
    same-origin `303` back to this exact match page for a browser navigation, carrying the failing
    `code` (and `retry_after`, where the error has one) as query parameters. The browser follows it as an
    ordinary same-tab navigation — the same mechanism §10 already requires, never a script reading a
    response — and the reloaded page reads those parameters once, on load, then clears them
    (`apps/web/src/features/replays/downloadFailure.ts`) so a later refresh does not resurrect a
    stale alert. This costs a page reload on the failure path only, and nothing on the success path;
    an API caller (not a browser navigation) still receives the identical JSON body it always did.

    **The real wording is delivered, not given up.** `T337`'s `replay_fetch_misses` write means the
    freshly-fetched `GET /api/matches/{game_id}` this reload triggers already reports the affected
    profile `never_recorded`, not `expired` — `derive_availability`'s own reading of that evidence,
    unchanged by this fix. `toReplayAvailabilityRows`
    (`apps/web/src/features/replays/availability.ts`) is what reconciles the two: for the one row
    `replay_error_profile_id` names, an
    `expired_since_page_load` code overrides that row's rendered `availability` to `expired` and sets
    `expiredSincePageLoad`, so `ReplayAvailabilityList` shows the real boundary-race sentence for this
    one page load, exactly as tabled above — never `never_recorded`'s copy, which would misstate that
    the recording was never there at all.

  - **`replay_error=expired` is an answer, not a failure (added 2026-11-10, T842).** A "Try to
    download" on a `beyond_window` row that the source answers "not found" comes back through the
    same `303` reload, with `replay_error=expired` for that row. For the one row
    `replay_error_profile_id` names, `toReplayAvailabilityRows` renders `availability: 'expired'`,
    `expiredSincePageLoad` unset, `downloadState: 'idle'`: the `Expired` badge, `danger` tone, §3.1's
    plain sentence "This recording is no longer available from the game.", no `DownloadAction`, and
    **no `Callout` of any kind** — neither the generic failed-request copy nor the boundary-race
    sentence. The row said before the click that the click asks the game (§5.1); "not found" is the
    answer it said it would ask for, so presenting it as "We could not start that download" would
    misstate a delivered answer as a failure to start. The reloaded match detail normally already
    reports the row `expired` (the route records the miss past the capture budget, R8); the override
    makes that rendering hold on this page load whatever the refetch returns. The rule is the code's,
    not the prior state's: an `expired` code renders this way on whichever row it names.
- **empty** — a match with no participants is not a case this component receives; `MatchDetailPanel`
  never renders with zero rows (`match-history.md` FR-011). What _is_ a real empty case: **every row
  is `expired`/`never_recorded`** (a match old enough, or unlucky enough, that nothing is obtainable
  from anyone). `Heading` still renders — "Recorded games" is true of the section's subject even when
  its answer is uniformly no — followed by every row exactly as tabled in §3, never collapsed into a
  single "nothing available" callout that would hide which participant is which and why (spec.md US3
  acceptance scenario 2: "not as a button that fails", not as a summary that erases the per-participant
  answer FR-023 requires either). **Amended 2026-11-10 (T842)**: a match whose rows are all
  `beyond_window` is not this case — each row carries an action — and renders as tabled, one row per
  participant, with no summary either.
- **selection** — not applicable; no row is marked current within the list, and `archived`'s
  caller-dependence (§3.3) is a fact about that row's own data, not a selection state.
- **expansion** — not applicable; every row's fields (§2) either render or are absent, and nothing
  here collapses to be revealed later.

### 5.1 `beyond_window` — an attempt, labelled as one (added 2026-11-10, T842)

**What it means.** The match completed longer ago than this service's capture budget — a capture
setting this project chose, shorter than the source's own retention for many profiles — and nothing
has been observed either way: no capture of this point of view, no "not found" from the source. This
service does not know whether the game still has the recording, and the row says exactly that. The
page asks nothing to render it (R8); the click asks the source, at that moment, for that one
recording — the same request an `obtainable` download makes, under the same rate limit (FR-028), with
the bytes streamed and not stored (FR-027). If the source serves it, the file downloads through the
same same-tab navigation `obtainable` uses; if it answers "not found", the row comes back `expired`
(§5, last error bullet) and is not offered again.

**Why this is not "a button that then fails" (FR-025, as amended 2026-11-10).** Three carriers say
"attempt" before the click — the badge label, `SecondaryLine` and the action's own label — and none of
them says "Download" or "Obtainable". A "not found" after that is the answer the row promised to
fetch, not a broken promise. Dropping any one of the three carriers would weaken that claim; none is
optional.

**Tone: `warning`.** The five tones then read as one ordered scale: `success` (held), `info` (the
source has it now), `warning` (unknown — may or may not), `danger` (gone), `neutral` (never existed).
`warning` already means "not yet settled, still worth acting on" in this system
(`capture-state-badge.md` §3's "Still catchable"), which is this state's meaning, and it carries no
fault. Not `accent`: `accent` is an identity/emphasis marker with no state meaning (`Badge`'s
"Primary"), and would read as "recommended", not "uncertain". No new variant, so GOVERNANCE §2 is not
triggered — an existing variant composes the meaning.

**`SecondaryLine` copy (normative, §3.1):** "This match is outside our capture window; trying asks the
game for this recording now, and it may no longer be available." Three properties, each required:

1. **It does not promise the file exists** — "may no longer be available" leaves both outcomes open,
   and uses the same "available from the game" register as `expired`'s sentence, so the two read as
   the question and its possible answer.
2. **It implies no fault** — "outside our capture window" is a fact about this service's own setting,
   not a failing of the user, the other player, or the source.
3. **It says what the click does** — "trying asks the game … now": the request happens on the click,
   not before, so the reader knows the answer is not already known.

`obtainableUntil` is ignored on this row (FR-024 makes it `null` anyway): no countdown, ever — there
is no horizon to count down to when the row's whole point is that the horizon is unknown.

**Action label: "Try to download"; loading label: "Asking the game for this recording…".** Not
"Download" — that would promise a file. Not "Try anyway" — the visible label is the accessible name
(§10), and in a list of buttons "Try anyway" does not say what is being tried. "Try to download" says
both the action and that it is an attempt, in one self-sufficient phrase. The loading label differs
from "Preparing your download…" for the same reason (§5 loading).

**Distinguishable from `obtainable` without colour**: badge label ("Outside capture window" vs
"Obtainable"), `SecondaryLine` (the caveat sentence vs a countdown or nothing) and action label ("Try
to download" vs "Download") all differ.

## 6. The countdown (`SecondaryLine` for `obtainable`)

**Reused, not reinvented.** `capture-state-badge.md` §7 and its `countdown.ts` module already solve
"how much time is left, in the coarsest honest unit, correctly pluralised" — `ReplayAvailabilityList`
calls the same exported function, `describeCaptureCountdown(obtainableUntil, now, 'compact')`, rather
than re-deriving days/hours/minutes, the floor-not-round rule, or the pluralisation a second time.
T340 wires this call; this spec fixes what it must and must not do with the result:

- **Only the `'compact'` variant is ever used here** (renamed from `context`, FR-032, T557 — see
  `capture-state-badge.md`). `describeCaptureCountdown`'s `'detail'` variant
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
(the four tone-variant badge fills, `capture-state-badge.md` §5), `success`, `info`, `warning`,
`danger` (badge labels, per the tones in §3 — `warning` added 2026-11-10 for `beyond_window`, T842;
`accent` is not used by this component), `text-secondary` (`neutral` badge label, `SecondaryLine`),
`text-primary` (`ParticipantLabel`), `border` (`neutral` badge boundary), `border-transparent` (the
four tone-variant badge boundaries), `border-strong` (`DownloadAction`'s boundary, per
`Button/secondary`), `focus-ring`. No new colour token and no new pair: every one of these is already
measured in the `specs/README.md` contrast table, light and dark, and already asserted in
`tokens/build-tokens.test.mjs` via `Badge`'s and `Button`'s own use — `warning` on `surface-raised`
through `CaptureStateBadge`'s "Still catchable" pill, the identical pair.

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
| `ParticipantLabel` to `AvailabilityBadge` (wrapped beneath it, `<md`)    | `space-1` — the same step as badge to `SecondaryLine`, so a wrapped badge reads as part of the row's text block, not a new row (added 2026-11-10, T842, §9)                                           |
| Row content to `DownloadAction`                                          | `space-4`                                                                                                                                                                                             |
| `DownloadAction` to its own error `Callout`                              | `space-2`                                                                                                                                                                                             |
| `ReplayAvailabilityList` (whole section) to `ParticipantsTable` above it | `space-8` — the same wide gap `archival-control.md` §7 uses between its own two distinct subjects, because a download action and a table of facts are two different kinds of content on the same page |

## 9. Responsive

- **375** — each row is a stacked card: `ParticipantLabel` and `AvailabilityBadge` on the first line,
  `SecondaryLine` on its own line beneath (never truncated — `profile-summary.md`'s "figures never
  ellipsise" extended to a countdown or a reason, the same rule `capture-state-badge.md` §10 already
  applies to its own `SecondaryLine`), `DownloadAction` full-width beneath, when present.
  **Amended 2026-11-10 (T842)**: "Outside capture window" is the longest badge label; when it and the
  alias do not fit on one line, the badge wraps beneath the alias (`space-1`, §8) — never truncated,
  never ellipsised, never shrunk below `Badge`'s one size, and the alias is never truncated to make
  room. `beyond_window`'s two-clause `SecondaryLine` wraps across lines like any other.
- **768** — `ParticipantLabel`, `AvailabilityBadge` and `SecondaryLine` sit on one row where the badge
  and secondary text fit without wrapping; `DownloadAction` becomes intrinsic-width, right-aligned.
  Where they do not fit (routinely the case for `beyond_window`'s sentence), `SecondaryLine` drops to
  its own line beneath, as at 375, and `DownloadAction` stays right-aligned beside the text block.
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
  is minted per click, server-side, on that request. **Corrected 2026-08-29** — this used to claim
  FR-029's `replay_access_log` write happens "on every click, archived and obtainable alike"; it does
  not, and the route (`apps/api/.../routers/replays.py`'s `download_replay_point_of_view`) never
  claimed otherwise — only the `archived` branch writes that row. FR-029 and `contracts/http-api.md`
  scope the logging duty to a recording this service _holds_: `obtainable` is fetched from the source
  and streamed straight through with nothing stored (FR-027), so there is no archive access to log,
  by design (`docs/privacy/processing-register.md`). This spec was the one that was wrong; the route's
  own logging behaviour is unchanged by this correction. `beyond_window` is fetched and streamed the
  same way as `obtainable` (§5.1) and, like it, writes no access-log row (added 2026-11-10, T842).
- **`beyond_window`'s action (added 2026-11-10, T842).** Its accessible name is its visible text,
  "Try to download" — no `aria-label` override, so the spoken name and the visible label are the same
  words (label in name). While loading, the name is the loading label, per `Button`. The button also
  carries `aria-describedby` pointing at the row's `SecondaryLine`, so a screen-reader user who tabs
  straight to the action hears the caveat ("… it may no longer be available") before pressing — the
  badge keeps its own `aria-describedby` to the same line; one element described by two is valid.
- The row-level error `Callout` (§5) uses `Callout`'s own tone-to-role mapping — `role="alert"` for the
  rate-limit/failed-request case, and the same for the `expired_since_page_load` transition, since both
  are events the user did not expect and must be told about immediately, not stumbled on.
- **A `replay_error=expired` row carries no `role="alert"` and no live region (added 2026-11-10,
  T842)** — it is the answer the user asked for, not an unexpected event (§5). Its badge and §3.1
  sentence are in document order with the usual `aria-describedby` association; focus after the
  reload behaves as for every other `303` in §5.
- Touch target ≥ 44px on every `DownloadAction`, "Try to download" included (`Button` `lg`).
- **Loading (T532, FR-054)**: the `<ul>` carries `aria-busy` while `loading`, one announcement for
  the whole list, never once per row's `Skeleton` (each stays `aria-hidden`, its own contract). See
  `shared-primitives.md`'s `StatValue` section for the general rule this follows.
- Contrast per `specs/README.md`'s measured table: `success`/`info`/`warning`/`danger` badge labels on
  `surface-raised` and `neutral`'s `text-secondary` on `surface-sunken`, both themes, all already
  asserted in `tokens/build-tokens.test.mjs`.
- Zoom to 200% and 320px logical width without horizontal scrolling — no cell truncates because there
  is no table at this component's one breakpoint shape (§9).

## 11. Visual acceptance criteria

- [ ] All five states (`archived`/`obtainable`/`beyond_window`/`expired`/`never_recorded`) appear in
      one combined story — `AllFiveStates` (renamed from `AllFourStates`, 2026-11-10, T842; its
      baseline moves either way, since a row is added) — and are each identifiable by label text
      alone, with no two sharing a label and no two sharing a tone.
- [ ] `RealisticMatch` includes at least one `beyond_window` row beside an `obtainable` or `archived`
      row, as a match past the capture budget looks to a caller whose own point of view is archived
      (spec.md US3 acceptance scenario 4, as amended 2026-11-10).
- [ ] The `BeyondWindow` story shows: badge "Outside capture window" in `warning` ink on the
      `surface-raised` pill; `SecondaryLine` reading exactly "This match is outside our capture
      window; trying asks the game for this recording now, and it may no longer be available."; and an
      enabled `secondary` `lg` button reading "Try to download" — no countdown, no `Callout`.
- [ ] The `BeyondWindowAsking` story shows that row's button in `Button`'s loading state reading
      "Asking the game for this recording…" — never "Preparing your download…", which
      `DownloadPreparing` shows for `obtainable`/`archived`.
- [ ] `beyond_window` and `obtainable` are distinct in the same frame (`AllFiveStates`) with the
      frame converted to greyscale: badge label, `SecondaryLine` and button label all differ.
- [ ] At 375, `beyond_window`'s badge is shown whole — wrapped beneath the alias if needed — with no
      ellipsis on the badge, the alias or the sentence (`StackedRowsBelowMd` includes a
      `beyond_window` row).
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
- [ ] `DownloadAction` is present in exactly the `archived`, `obtainable` and `beyond_window` stories
      and absent — never disabled — in the `expired` and `never_recorded` stories, cross-checked
      against `match-history.md`'s equivalent criterion for its own `DownloadAction`.
- [ ] The `expired_since_page_load` story shows the row transitioning from `obtainable` to the
      `expired` badge with the boundary-race sentence from §5, visibly different from a story seeded
      already-`expired` with §3.1's plain sentence, in the same frame.
- [ ] A row answered `replay_error=expired` renders pixel-identical to the `Expired` story — §3.1's
      plain sentence, no `Callout`. This is a mapping rule in `apps/web`
      (`toReplayAvailabilityRows`), not a component state, so it needs no story of its own; it is
      verified by that mapper's test, and this criterion fails if any story shows an `expired` row
      with a `Callout` beneath it.
- [ ] The rate-limited story shows the row unchanged (`DownloadAction` still present and pressable) with
      a danger callout beneath it naming the retry time — never a row that looks like it gave up.
- [ ] Loading story: skeleton row count matches the loaded story's row count at the same viewport, no
      reflow between the two.
- [ ] A story with every row `expired`/`never_recorded` still shows the section heading and one row per
      participant — never a single collapsed "nothing available" message. (`EveryRowUnobtainable`
      stays free of `beyond_window` rows: they are actionable, §5 empty.)
- [ ] The `AvailabilityBadge` (`xs`, `semibold`, `wide` tracking) is at least as legible as
      `ParticipantLabel` (`sm`) in the same row — a token-correct row that let the badge fade against
      the alias would leave the one fact this component exists to state harder to find than the name
      beside it, and fails this criterion (FR-063). This holds for the `warning` pill too.
