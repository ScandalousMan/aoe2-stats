# AnalysisTimeline

**Component**: `src/components/AnalysisTimeline/` (internal anatomy pieces: `ParticipantTimelineColumn`,
`AnalysisProgress`, `AnalysisFailureNotice` — not separate exports, the same relationship
`ReplayAvailabilityRow` has to `ReplayAvailabilityList` in
[`replay-availability.md`](./replay-availability.md))
**Feature**: 003, US4 — consumed by `apps/web/src/features/analysis/` (T372), on the same match page
`MatchDetailPanel` (`match-history.md`) and `ReplayAvailabilityList` (`replay-availability.md`) render
**Requirements**: FR-030, FR-031, FR-032, FR-034, FR-035, FR-036, FR-037, FR-038, FR-041, FR-042,
FR-043, FR-043a, FR-043b, FR-043c, FR-044. SC-006, SC-007, SC-009a, SC-011, SC-013. US4 acceptance
scenarios 1, 2, 3, 4, 5, 7, 8.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Button`, `Callout`, `Badge`,
`Skeleton`, `StatValue`. [`match-history.md`](./match-history.md) §11.2 — the `UnresolvedIdentifier`
treatment (label prefix, `type-identifier` — mono family and `text-secondary` by the role's own
contract, T531/research D7), reused verbatim for a technology, unit or
building id this component's own reference data cannot name (FR-043a), never reinvented for this
component's own three identifier kinds. [`match-history.md`](./match-history.md) §2 — team grouping
order, reused for `ParticipantTimelineColumn` ordering so this component reads as one more section of
the same match page rather than a second, differently-ordered roster.

## 1. Purpose

Show, per participant, the factual account FR-043 requires — what they built, trained, researched and
ordered, and when — once a person has asked for that match to be analysed (FR-030), and let every
subsequent viewer read the identical, already-computed result without waiting (FR-031). Report progress
honestly while the analysis is still running, so a wait of up to a few minutes never reads as a frozen
page (SC-007), and state plainly, per failure shape, why a result cannot be shown, without ever
presenting a permanent limit as a button that fails (FR-034, FR-036).

**What this component does not render.** The entry point that exists before any analysis has ever been
requested — a plain "Request analysis" primary `Button`, wired directly in
`apps/web/src/features/analysis/` (T372) — is not part of this component's anatomy or its state
vocabulary. `AnalysisTimeline` renders once `state` is anything other than `absent`; a bare, unstyled
`Button` firing `POST /api/analyze` has no bespoke states beyond `Button`'s own and earns no spec of its
own, the same reasoning `match-history.md`'s own anatomy note gives for leaving `UploadControl` out of
`MatchDetailPanel`'s anatomy. The six states this component does own — `published`, `published` +
`stale`, `queued`/`running`, `failed`, `unavailable`, `refused` — are exactly the six stories T371
builds.

## 2. Anatomy

```
AnalysisTimeline                                        one per match, rendered from the match-detail
│                                                        response's `analysis` object (contracts/http-api.md)
├─ Heading                    h3, "Match analysis" — present in every state below
├─ StaleRecomputeNotice       present only when state="published" and stale=true — §3.4
├─ EngineProvenance           text-secondary, xs — "Analysed with <engine> <version> on <date>."
│                             present only when state="published" (constitution IV traceability)
└─ (state-dependent body, exactly one of:)
   ├─ AnalysisProgress                              state="queued" | "running" — §3, §5
   ├─ ParticipantTimelineColumn ×n                  state="published" — the factual account, §2.1
   └─ AnalysisFailureNotice                         state="failed" | "unavailable" | "refused" — §3

ParticipantTimelineColumn                             one per participant, team-grouped in the same
│                                                      order ParticipantsTable uses (match-history.md §2)
├─ ParticipantHeading         alias, civilisation name (or UnresolvedIdentifier, §3.2)
├─ SummaryStats               ApmStat + ActionsStat + VillagersOrderedStat — StatValue/compact, §2.1
├─ AgeUpList                  one row per age ordered so far — §3.1, the wording requirement
├─ BuildOrderList             chronological, one row per BuildEvent
├─ TrainingOrderList          chronological, one row per TrainingEvent, with its trained count
├─ ResearchList               chronological, one row per ResearchEvent — excludes the three age-up
│                             technology ids, which appear only in AgeUpList (§2.1)
└─ ResignedLine               present only when resigned_at_ms is not null — §2.1
```

**IP note**: every name rendered — civilisation, technology, unit, building — is factual text in this
system's own typeface. No civilisation emblem, no technology icon, no unit portrait, no building
thumbnail anywhere in this component. Constitution X.

### 2.1 What each row says, and what it deliberately does not invent

The data this component is fed is `MatchTimeline` (`contracts/analysis.md`), and every field name on
the wire is load-bearing there for a reason this component must not undo by choosing a friendlier
label that erases the distinction the contract drew:

- **`AgeUpList`** — see §3.1. This is the one place FR-043c's wording rule applies, and it is the
  reason this component has its own spec section for wording rather than leaving it to whoever writes
  the JSX.
- **`BuildOrderList` / `TrainingOrderList`** — two separate chronological lists, not one merged feed.
  `MatchTimeline` carries `builds` and `trainings` as two separate sequences and this component renders
  them as given; merging them into one interleaved list would require inventing a total order across
  two arrays the contract does not itself merge, which is exactly the kind of derived quantity FR-043b
  forbids for a different field on the same artifact. `TrainingOrderList` shows each `TrainingEvent`'s
  `amount` beside the unit — "3× `<Unit>`" — because a `DeQueue` command can queue more than one at a
  time; it is a command count, the same discipline `VillagersOrderedStat` states below for the whole
  match.
- **`ResearchList`** excludes technology ids 101, 102 and 103 (the three age-up commands) even though
  `ResearchEvent`'s own shape (`technology_id` + `world_time_ms`, first occurrence only) could carry
  them. An age-up command already has its own row, in `AgeUpList`, worded under FR-043c's rule; showing
  it a second time in a plain "researched" list — worded only as a technology, with no "ordered"
  qualifier — would put the same fact on the page twice under two different framings, and the second one
  is exactly the "reached" misreading FR-043c exists to prevent. One fact, one row, one wording.
- **`VillagersOrderedStat`** is labelled **"Villagers ordered"**, never "Villagers trained" and never
  "Villagers" — FR-043b's own naming rule, restated here because this component is where a shorter,
  friendlier label would otherwise get invented at review time. It always carries a secondary line,
  `text-secondary` `xs`, **"Training commands, net of cancelled orders — not a population count."** —
  present in every rendering, not only the first one a reader sees, because `contracts/analysis.md`
  documents this as "one refactor away at all times" and a label that is only sometimes accompanied by
  its own caveat is a label a later edit silently strips.
- **`ApmStat` / `ActionsStat`** — `StatValue/compact`, "Actions per minute" (rounded to the nearest
  whole number — an activity rate, not a countdown, so the floor-only discipline `describeCaptureCountdown`
  uses for a deadline does not apply here) and "Actions" (the whole-match count, unrounded). Neither
  carries a delta; there is nothing to compare against inside this feature's scope (spec.md's own
  "no benchmark, no comparison" boundary).
- **`ResignedLine`** renders only `resigned_at_ms`, worded **"Resigned at `<mm:ss>`"**, and is entirely
  absent — never a placeholder, never "Still playing" — for a participant who did not resign.
  **`MatchTimeline` carries no separate "defeated" signal** (`contracts/analysis.md`'s dataclass has
  `resigned_at_ms` and nothing else describing how the match ended for a participant), though FR-043's
  own prose names "defeated or resigned" together. This component does not paper over that gap with an
  invented "Defeated" label for a participant who simply has no `resigned_at_ms` — that would be exactly
  the guess-dressed-as-a-fact FR-020/FR-043a forbid for a name, applied here to an outcome instead. A
  participant with no `ResignedLine` is presented with nothing on that subject, which is the honest
  reading of what the artifact actually contains.
- Every time value across every list (`AgeUpList` excepted, worded per §3.1) renders as `m:ss` — minutes
  unpadded, seconds zero-padded, floored from `world_time_ms` (never rounded up, so a row never claims
  an order happened before it did).

## 3. The six states this component renders

Six of the seven values `contracts/http-api.md`'s `analysis` object carries reach this component
(`absent` does not — §1). `queued` and `running` share one rendering, `AnalysisProgress`; `published`
carries a second, independent axis (`stale`) that changes what sits _beside_ the timeline, never what
replaces it.

| `state`                     | Heading region                | Body                                           | Action offered                               |
| --------------------------- | ----------------------------- | ---------------------------------------------- | -------------------------------------------- |
| `queued`                    | plain                         | `AnalysisProgress`, "Waiting to start…"        | none — leave and come back (FR-035)          |
| `running`                   | plain                         | `AnalysisProgress`, "Analysing this match…"    | none — leave and come back (FR-035)          |
| `published`, `stale: false` | plain                         | full `ParticipantTimelineColumn ×n`            | none — there is nothing to do                |
| `published`, `stale: true`  | `StaleRecomputeNotice` — §3.4 | full `ParticipantTimelineColumn ×n`, unchanged | `Button/secondary` "Recompute"               |
| `failed`                    | none                          | `AnalysisFailureNotice`, `danger` — §3.5       | none — a parse is deterministic              |
| `unavailable`               | none                          | `AnalysisFailureNotice`, `danger` — §3.5       | none — permanent (FR-034)                    |
| `refused`                   | none                          | `AnalysisFailureNotice`, `warning` — §3.5      | `Button/secondary` "Try requesting analysis" |

`queued` and `running` render identically apart from that one line of copy — neither carries a
percentage or an ETA, because nothing in `contracts/analysis.md` or `contracts/http-api.md` produces one
(the state column is the only signal), and inventing a progress bar with no real numerator would be the
same fabricated-precision failure `describeCaptureCountdown` was written to avoid for a deadline.

### 3.1 An age-up time is worded as ordered, never as reached (FR-043c) — normative copy

Every `AgeUpList` row reads, exactly:

> **`<Age name>` ordered — `<m:ss>`**

Never "Reached `<Age name>` at `<time>`", never "`<Age name>` at `<time>`" with the verb dropped, and
never a past-tense construction that could be misread as the age having arrived. The reason is stated in
`contracts/analysis.md`: `age_up_commands` is a mapping from a research **command**, not from a
completion event, and the two differ by the age's own research duration — a fact that varies by
civilisation and game speed and that no reference data in this repository holds. "Ordered Feudal Age at
6:41" is true of the recording; "Reached Feudal Age at 6:41" would be false by roughly the research
duration, in the direction that flatters the player, and this component must never say it.

`<Age name>` resolves technology ids 101, 102 and 103 to Feudal Age, Castle Age and Imperial Age
respectively (the order `contracts/analysis.md`'s own comment gives) through the same reference-data
lookup every other technology name in this component uses — this component does not hardcode the three
names itself, and if the lookup ever returns nothing for one of the three, §3.2's `UnresolvedIdentifier`
treatment applies to that row exactly as it would to any other technology id, still worded "`ordered`"
around it: **"Technology ID 101 ordered — 6:41."**

Rows appear only for an age actually ordered — `age_up_commands` carries no zero or placeholder entry
for an age nobody reached, and this component renders nothing for it: never "Feudal Age — not ordered",
which would assert a negative fact about a game state this artifact cannot see (a match that ended before
Feudal, or a participant defeated before ordering it, look identical to "never asked", and inventing a
distinction between them is not something this data supports). Rows are ordered chronologically, oldest
first, matching every other list in this component.

`age_up_commands` is already deduplicated against a double-click before it reaches this component
(`contracts/analysis.md`: "first occurrence only" / "collapse a command repeated by a double-click to
one event", FR-043c's own second clause) — this component renders the map exactly as given and performs
no deduplication of its own, so there is exactly one place in the whole pipeline responsible for that
rule, not two that could drift.

### 3.2 An unnamed technology, unit or building identifier (FR-043a)

Wherever this component's own reference data cannot name a `technology_id`, `unit_id` or `building_id` —
a new game version, ahead of this service's own naming table — the field renders as an
`UnresolvedIdentifier`, reusing `match-history.md` §11.2's treatment unchanged, generalised from
"Civilisation ID" / "Map ID" to this component's own three kinds:

- **"Technology ID `<n>`"**, **"Unit ID `<n>`"**, **"Building ID `<n>`"** — the label prefix names what
  the number is an id _of_, never the bare number and never the field's own label with nothing marking
  it unresolved.
- `type-identifier` (research D7, FR-007) — `text-secondary`, never `text-primary`, by the role's own
  contract: one step down the same hierarchy a resolved name sits at, exactly as `match-history.md`
  §11.2 states for `Civilisation`/`Map`. The role also carries the mono family: an id is data, a name
  is prose, and this component does not blur the two typefaces any more than `match-history.md` does
  for its own pair.

No icon, no additional colour token, no fourth signal — three (wording, colour step, typeface) already
clear constitution VI's "never colour alone" rule, the identical reasoning `match-history.md` §11.2
states for its own two fields. This treatment reaches every list in §2 that names a technology, unit or
building: `BuildOrderList`, `TrainingOrderList`, `ResearchList`, and `AgeUpList` per §3.1's own note.

### 3.3 `stale` is a fact about the published analysis, not about this component's confidence in it

`stale: true` means the stored `parser_version` differs from the engine currently running
(`contracts/http-api.md`) — it says nothing about whether the numbers on the page are wrong, only that a
newer engine exists and could, in principle, produce a different reading. `StaleRecomputeNotice` (§3.4)
is worded to match that: it never says "This analysis may be inaccurate," which would assert a doubt this
component has no basis for.

### 3.4 A stale published analysis: the facts stay, the recompute sits beside them (FR-041)

**The whole of §2's `ParticipantTimelineColumn ×n` renders exactly as it would if `stale` were `false` —
same rows, same order, same wording, no dimming, no strikethrough, no reduced opacity.** `StaleRecomputeNotice`
is a single inline row, placed between `Heading` and `EngineProvenance` (§2's anatomy), never a `Callout`
and never anything that pushes the timeline below the fold or visually separates it from the rest of the
page as "in question":

```
StaleRecomputeNotice
├─ Badge/info    "Newer analysis engine available"
└─ Button/secondary   "Recompute"
```

This is the concrete answer to FR-041's own prohibition: "never a warning that hides the result." A
`Callout` — this system's own component for "explain an outcome the user did not ask for" — is
deliberately **not** used here, even at `info` tone, because every `Callout` in this system is a full-
width block with its own heading and body that visually announces "something to read before the content
below," and a stale analysis is not that: the content below is exactly as good as it was a moment ago,
and nothing about it needs to be read first. A single `Badge` plus a single `Button`, sitting on one line
above facts that render unchanged, says "an upgrade exists" without implying the facts beneath it are in
doubt.

**Recompute is the identical action a first request or a `refused` retry is** — `Button`'s click fires
`POST /api/analyze` on this match, which re-claims the row and re-derives it from the retained recording,
reaching no source (FR-041, SC-009a, `contracts/http-api.md`). Clicking it does not clear or hide the
current `ParticipantTimelineColumn`s while the recompute runs: the page keeps showing the last published
result, `StaleRecomputeNotice`'s `Button` moves to `Button`'s own `loading` state (label "Recomputing…"),
and the whole component swaps to the new published result only once the recompute itself publishes — at
no point does a reader see less than they saw before clicking.

### 3.5 The three failure shapes, and why they read differently (FR-034, FR-036, FR-047)

None of the three shares the "distinguish and display" reasoning `replay-availability.md` §3 already
states for a different pair — different label, and tone chosen for the same reason that file gives:
`danger` where the door is genuinely and permanently closed, a third tone where it is not.

| `state`       | Heading                                    | Body (exact copy)                                                                                                      | Tone      | Action                    |
| ------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | --------- | ------------------------- |
| `failed`      | "This match could not be analysed"         | "The recorded game could not be parsed." + secondary line `text-secondary`/`type-machine`: "Error: `<error_class>`"    | `danger`  | none                      |
| `unavailable` | "Analysis is not available for this match" | "This match's recorded game is no longer available, and it was never analysed. It cannot be analysed now."             | `danger`  | none                      |
| `refused`     | "Analysis is temporarily unavailable"      | "This service has reached its limit for the number of recordings it can keep for analysis right now. Try again later." | `warning` | "Try requesting analysis" |

**Why `failed` and `unavailable` share `danger` and offer nothing.** Both are closed doors for a reason
that trying again cannot fix right now: `failed` because a parse is deterministic and a second attempt on
the same bytes is a second identical failure that costs another fetch (`contracts/analysis.md`,
FR-036) — this component offers no "Try again" for exactly that reason, not because retrying is
forbidden by policy but because it is known in advance to fail identically; `unavailable` because the
source's own recording is gone and FR-034 explicitly forbids presenting that as "an action that fails."
They differ in heading and body text alone — no icon, no second colour — and a reader converting either
screenshot to greyscale still tells them apart from the words alone, the same acceptance discipline
`replay-availability.md` §11 states for its own pair of permanent states.

**Why `refused` is the one warning, and the one with a button.** `contracts/http-api.md` and
`data-model.md` both say the same thing about this state alone: "it may be asked for again later." That
is a real, structural difference from the other two — the cap is a volume constraint that changes as
other recordings age out or as the operator raises it, not a fact about this match's bytes — and it is
why `refused` gets `warning` rather than `danger` (README's own reading: "something will go wrong if
nothing changes" fits a constraint that can lift; `danger`'s "something failed, or is about to be
irreversible" does not) and the one retry button among the three. Clicking it fires the identical
`POST /api/analyze` §3.4 describes; a still-full cap simply answers `refused` again, and the component
shows the same notice, not a different one for "refused again."

`failed`'s `error_class` is the failure class `apps/analyzer` recorded (constitution V, FR-036), never
the traceback — the same boundary `contracts/http-api.md`'s `analysis_failed` code states for the API
response this component reads.

## 4. Variants and sizes

No variant axis. `AnalysisTimeline` takes its entire shape from the `analysis` object and, once
`published`, from `MatchTimeline`'s own content (§2, §3). Sizing is responsive, not independent (§8).

## 5. States

The closed interaction-state vocabulary (README) applies to `AnalysisTimeline` as a whole and,
separately, to `StaleRecomputeNotice`'s and `AnalysisFailureNotice`'s own `Button`s — distinct from the
six domain states tabled in §3, which this vocabulary's `loading`/`error`/`empty` are not.

- **default** — as tabled in §3, for whichever `state` the match-detail response carries.
- **hover / focus-visible / active** — none on `Heading`, `EngineProvenance`, or any list row; all are
  static text. `Button`s (`Recompute`, "Try requesting analysis") follow `Button`'s own states.
- **disabled** — neither `Button` has a disabled form. `Recompute` is offered only while `stale: true`
  (never rendered and disabled otherwise — the same "absent, not disabled" rule
  `replay-availability.md` §5 states for its own `DownloadAction`); "Try requesting analysis" is never
  disabled while shown, because a `refused` state that still forbids asking again would need a reason
  this component has no field for.
- **loading** — before the match-detail response carries an `analysis` object at all: `Heading` renders,
  then one `Skeleton/block` per the smallest known participant count (2, matching
  `replay-availability.md` §5's identical rule), at `ParticipantTimelineColumn`'s own footprint. This is
  the ordinary "the page has not loaded yet" case, and it is not to be confused with the `queued`/`running`
  domain state (§3), which is reached only once the response is known and says `state: "queued"` or
  `"running"` — a real fact about the analysis, not an unloaded page.
- **`AnalysisProgress`'s own refresh** — while `state` is `queued` or `running`, this component polls
  `GET /api/matches/{game_id}` every 5 seconds and re-renders from the response, so the page moves itself
  from progress to a published, failed, unavailable or refused result without a manual reload — the
  concrete mechanism behind FR-035's "let the user leave and come back": leaving means navigating away
  and returning to find the right state already showing, not necessarily watching this page the whole
  time. Polling stops the instant `state` is anything other than `queued`/`running`, and stops entirely
  when the component unmounts. Requesting or recomputing an analysis (§3.4) does not wait on its own
  `POST /api/analyze` response to update this component: the click fires the request and this component
  immediately shows `AnalysisProgress`, relying on the very next poll (or the eventual page it lands on)
  to read the outcome — this is what keeps SC-007's "never a frozen screen" true even though a single
  analysis run may take up to the platform's 300 s budget, because no `Button` is ever left spinning for
  more than the instant it takes to fire the request.
- **error** — a network failure loading the match-detail response itself (not any of §3's domain states,
  which are not errors): `Callout/danger` in place of this whole section, "We could not load this
  match's analysis. Try again." with a retry — matching `match-history.md`'s and
  `replay-availability.md`'s identical shape for their own load failures. A poll (above) that fails
  once is retried silently at the next interval rather than surfacing this Callout, so a single dropped
  request during a multi-minute wait never interrupts `AnalysisProgress` with an alarming message; only
  a load failure on the page's own first fetch shows this state.
- **empty** — not applicable in the sense this vocabulary usually means it: there is no participant list
  that can be legitimately empty once `state` is `published` (`contracts/analysis.md`'s
  `MatchTimeline.participants` is never empty for a real match), and the `absent` state that would
  otherwise be "nothing here yet" is out of this component's scope (§1).

## 6. Tokens used

Colour: `surface` (page), `surface-sunken` (`Skeleton` fill, `neutral` `Badge` fill via that component),
`surface-raised` (`Callout` fill, tone-variant `Badge` fill, via those components), `text-primary`
(aliases, resolved names, list values), `text-secondary` (labels, `EngineProvenance`, "Analysing this
match…"/"Waiting to start…", `VillagersOrderedStat`'s caveat line, `UnresolvedIdentifier`'s id text,
§2.1), `info` (`StaleRecomputeNotice`'s `Badge`, via that component), `warning` (`refused`'s `Callout`
heading, via that component), `danger` (`failed`/`unavailable`'s `Callout` heading, via that component),
`border-strong` (`Button/secondary`'s boundary), `focus-ring`. No new colour token and no new pair: every
one is already measured in `specs/README.md`'s contrast table and already asserted in
`tokens/build-tokens.test.mjs` via `Badge`'s, `Callout`'s and `Button`'s own use.

Typography (T531, research D7): `type-numeric` for every time value (`m:ss`) and every count
(`StatValue`'s figures) — the mono family with `tabular-nums`, so alignment does not ride on the
family happening to be monospaced; `type-identifier` for every `UnresolvedIdentifier`'s number — the
same reasoning every raw identifier in this system gives, now the mono family and `text-secondary` by
the role's own contract rather than DS-8's shared, undifferentiated `font-mono`; `sans` for every
name, label and sentence. Sizes: `Heading` `xl`
(matching `MatchDetailPanel`'s own panel heading, `match-history.md` §6); participant heading `lg`
`semibold`; list rows and `EngineProvenance` `sm`/`xs`; `StatValue/compact` per that component's own
sizing. Weights `semibold` on aliases, participant headings and figures; `normal` elsewhere.

Radius: `lg` (`Callout`, `ParticipantTimelineColumn` card at 375), `full` (`Badge`), `md` (`Button`).
Elevation `none` throughout — `profile-summary.md`'s reasoning against shadowed cards in a fast-read list
applies identically here. Motion: `duration.fast` + `easing.standard` on `Button`'s own states; **no
motion on any figure or list row** (`StatValue`'s own rule, README rule 1) — nothing counts up, nothing
fades in as it is read, including the moment a poll (§5) turns `running` into `published`. `Skeleton`'s
own pulse, `duration.slow`, stops on its resting frame under `prefers-reduced-motion: reduce`.

Gaps in play: none. **DS-8 closed** (T531) — every time value and count now carries `type-numeric`,
whose `tabular-nums` keeps alignment independent of the mono family.

## 7. Spacing

| Between                                                                       | Step                                                                                                              |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `ReplayAvailabilityList` (above) to `AnalysisTimeline`                        | `space-8` — the same wide gap `replay-availability.md` §8 uses between its own two distinct subjects on this page |
| `Heading` to `StaleRecomputeNotice` (when present)                            | `space-3`                                                                                                         |
| `Heading`/`StaleRecomputeNotice` to `EngineProvenance`                        | `space-1`                                                                                                         |
| `EngineProvenance` to body (progress / timeline / failure)                    | `space-4`                                                                                                         |
| Between `ParticipantTimelineColumn`s                                          | `space-6`                                                                                                         |
| `ParticipantHeading` to `SummaryStats`                                        | `space-2`                                                                                                         |
| `SummaryStats` to `AgeUpList`                                                 | `space-4`                                                                                                         |
| Between `AgeUpList` / `BuildOrderList` / `TrainingOrderList` / `ResearchList` | `space-4`                                                                                                         |
| Last list to `ResignedLine` (when present)                                    | `space-3`                                                                                                         |
| `StaleRecomputeNotice`'s `Badge` to its `Button`                              | `space-3`                                                                                                         |
| `AnalysisFailureNotice`'s body to its `Button` (`refused` only)               | `space-4`                                                                                                         |

## 8. Responsive

- **375** — each `ParticipantTimelineColumn` is a stacked full-width card: `ParticipantHeading`,
  `SummaryStats` wrapping onto its own line, then each list stacked beneath with its own heading. No
  field truncates or ellipsises — `profile-summary.md`'s figure rule extended to a technology, unit or
  building name, the same discipline `favourites-list.md` §8 already states for its own rows.
- **768** — two `ParticipantTimelineColumn`s from the same `TeamGroup` sit side by side, matching
  `match-history.md` §8's identical rule for `ParticipantsTable` at this width; `SummaryStats` sits on
  one line beside `ParticipantHeading`.
- **1280** — columns widen with the page; still one card per participant, never a `<table>` — the lists
  inside a column are prose-shaped (a build order, a research order), not a comparable grid of figures
  the way `ParticipantsTable` or `MatchRow` are, so this component does not gain a table layout at any
  width, the same reasoning `favourites-list.md` §8 and `replay-availability.md` §9 give for keeping one
  shape.

**Do not render both layouts and hide one** — one DOM, restructured at the breakpoint, the rule every
other spec in this directory states identically.

`AnalysisProgress`'s skeleton footprint (§5) matches the loaded `ParticipantTimelineColumn` footprint at
the same viewport, so a poll that turns `running` into `published` shows no reflow.

## 9. Accessibility

- `AnalysisTimeline` is a `<section aria-labelledby>` headed by `Heading` (`<h3>`, matching
  `ReplayAvailabilityList`'s own heading level on the same page).
- Each `ParticipantTimelineColumn` is headed by its own `<h4>` (`ParticipantHeading`'s alias); each list
  (`AgeUpList`, `BuildOrderList`, `TrainingOrderList`, `ResearchList`) is an `<ol>` — order is the fact
  being shown, and an unordered list would misstate that a build order and a research order are sequences.
- `UnresolvedIdentifier` (§3.2) carries `match-history.md` §11.5's own rule: the visible label prefix
  ("Technology ID," "Unit ID," "Building ID") is real text inside the row, needing no additional
  `aria-label` because the words already say what the number is.
- `StaleRecomputeNotice`'s `Badge` label is real text, immediately followed by its `Button` in document
  order — never colour alone (constitution VI), matching `capture-state-badge.md` §11's identical rule
  for its own badge-plus-context pairing.
- `AnalysisFailureNotice` uses `Callout`'s own tone-to-role mapping (`shared-primitives.md`'s `Callout`
  accessibility rule): `role="alert"` for `danger` (`failed`, `unavailable`) and `role="status"` for
  `warning` (`refused`). `refused` is a state the user can act on rather than an error thrown at them —
  it carries a "Try requesting analysis" button — so `status` (polite) is the correct live-region
  politeness for it, not `alert` (assertive). The component follows this real mapping.
- The poll (§5) that refreshes a `queued`/`running` page carries no `aria-live` region of its own: the
  transition from progress to a result is a full re-render of this section, not a status line that
  updates in place, so there is nothing here that would double-announce the way `shared-primitives.md`
  warns a first-paint `Callout` with `aria-live` would.
- `Recompute` and "Try requesting analysis" are real `<button>`s, never a `<div>` with a click handler;
  touch target ≥ 44px on both, per `Button`.
- Every figure and every name is selectable text, never an image or canvas — `profile-summary.md`'s rule
  extended here.
- Contrast per `specs/README.md`'s measured table, entirely through `Badge`, `Callout`, `Button` and
  `StatValue`.
- Usable at 200% zoom and 320px logical width without horizontal scrolling; no list item truncates at any
  viewport (§8).

## 10. Visual acceptance criteria

- [ ] The `published`, not-stale story shows every `ParticipantTimelineColumn` from §2's anatomy with no
      `StaleRecomputeNotice` present anywhere in the frame.
- [ ] The `published`-and-`stale` story shows the identical `ParticipantTimelineColumn` content as the
      not-stale story, placed side by side to confirm the two are pixel-identical below the notice — plus
      a `Badge`/`Button` pair above it and nothing dimmed, struck through, or collapsed.
- [ ] An `AgeUpList` row in any `published` story reads "`<Age name>` ordered — `<m:ss>`" — never
      "Reached," never a bare time with no verb — confirmed against a second story that seeds an
      unresolved age-up technology id and shows "Technology ID `<n>` ordered — `<m:ss>`" with the same
      verb.
- [ ] A story seeded with an unresolved technology, unit and building id each renders that field's
      `UnresolvedIdentifier` form (§3.2) in `type-identifier`, visibly distinct from a resolved
      name in the same story's other rows, placed in one frame.
- [ ] The `VillagersOrderedStat` in every `published` story shows both "Villagers ordered" and its
      secondary caveat line in the same frame — never the label alone.
- [ ] The `running` (progress) story shows `AnalysisProgress`'s skeleton at the same footprint as the
      loaded `published` story's first column, at the same viewport, so the two can be compared for
      reflow.
- [ ] `failed`, `unavailable` and `refused` each render a distinct heading and body string with no two
      sharing wording, and `failed`/`unavailable` (both `danger`) are still distinguishable from each
      other by heading text alone when the frame is converted to greyscale.
- [ ] `refused` is the only one of the three failure stories showing a `Button`; `failed` and
      `unavailable` show none — cross-checked in one combined frame against
      `replay-availability.md`'s equivalent "action present only where it can succeed" criterion.
- [ ] Converting the `refused` story to greyscale still distinguishes it from `failed`/`unavailable` by
      wording and by the presence of the button alone, not by tone (constitution VI).
- [ ] No civilisation, technology, unit or building icon, portrait or thumbnail appears in any frame —
      only text, in this system's own typeface.
