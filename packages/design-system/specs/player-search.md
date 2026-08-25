# SearchBox and PlayerResultRow

**Components**: `src/components/SearchBox/`, `src/components/PlayerResultRow/`
**Feature**: 003, US1 — consumed by `apps/web/src/routes/search.tsx` (T322)
**Requirements**: FR-001, FR-002, FR-003, FR-004a, FR-004b, FR-004d, FR-004e, FR-005, FR-009. SC-001,
SC-002, SC-002a.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Callout`, `Skeleton`, `Button`.
[`profile-summary.md`](./profile-summary.md) — `CountryLabel`'s own convention (text, optional
non-carrying flag glyph) is reused rather than reinvented.

## 1. Purpose

`SearchBox`: let a user find any player by a partial, wrongly-cased name and reach their profile
without ever knowing a numeric identifier (FR-001), while never presenting a reduced answer as a
complete one (FR-003). `PlayerResultRow`: let two players who share or nearly share a name be told
apart at a glance (FR-002).

## 2. Anatomy

```
SearchBox                                                one instance per search route
├─ Label                Label text, visually associated with Input — "Search a player"
├─ Input                type="search", debounced, clearable — the query source for every state below
└─ ResultsRegion        role="region", aria-live="polite" — exactly one of the six states in §5 renders
   ├─ IdlePrompt         no query has been submitted yet — plain text, not a Callout
   ├─ ResultsSkeleton    a query is in flight
   ├─ ResultsList        DegradedBanner? then PlayerResultRow × n — a query answered, with or without rows
   ├─ NotFoundState      Callout/info — a query answered, degraded: false, zero rows
   └─ FailureState       Callout/warning (rate_limited) or Callout/danger (request failed), with retry

PlayerResultRow                                          one per result, the whole row is a link
├─ Alias                display name, text-primary
├─ Clan                 optional — "[TAG]" bracketed, text-secondary, beside Alias
├─ CountryLabel         country name in text, optional flag glyph — never absent when country is known
├─ Standing             games played, formatted "<N> games" — present only when known (see §4)
└─ UnverifiedSteamClaim optional — "Unverified Steam ID: <id>", its own line — present only when
                        unverified_steam_id is not null, and carrying no affordance (see §4a)
```

**IP note**: no player avatar, no clan crest, no country flag illustration beyond a free-licensed,
`aria-hidden` glyph beside the country name in text — the same rule and the same licensing obligation
`profile-summary.md` §2 states for `CountryLabel`. Constitution X.

## 3. Variants and sizes

Neither component has a variant axis. `SearchBox` is one instance, full width of its column, at every
viewport. `PlayerResultRow` takes its entire variation from the data it is given (§4) and from which
of the six `ResultsRegion` states it is rendered inside (§5); sizing is responsive, not independent
(§7).

## 4. What a result can actually carry, and what the row does about the gap (FR-002, FR-004b, FR-004d)

`PlayerResultRow` is fed `PlayerSearchResult` exactly as
[contracts/providers.md](../../../specs/003-player-search-match-analysis/contracts/providers.md)
defines it: `profile_id`, `alias`, `country: str | None`, `games_played: int | None`,
`clan: str | None`, and `unverified_steam_id: str | None`. **`shared`, `shared_history` and
`linked_profiles` have no field to render, ever** — they stay absent for the reasons
`contracts/providers.md` states (no known meaning, a preference this service neither honours nor
circumvents, and an unread duplicate of the same unverifiable claim at a different shape), and
`PlayerResultRow` has no prop that could carry any of the three. This is the same enforcement
`profile-summary.md` §4 states for the multi-profile switcher: the field the rule forbids has nowhere
to be assigned, not a value hidden by a conditional.

**Amended 2026-08-25.** The paragraph above used to read "there is no `steam_id` … field to render,
ever", true under FR-004b as first written. Constitution IX 3.0.0 (2026-08-24) retired that strip and
FR-004b was rewritten the same day: the source's Steam claim is now carried, as
`unverified_steam_id`, and is no longer withheld at the provider boundary. It is not withheld here
either — it is carried, labelled and bounded by §4a below. The sentence is corrected rather than
deleted so the next reader finds the reason the old rule existed, and the reason it no longer applies,
in the same place.

### 4a. The unverified Steam claim, and the one rule on it (FR-004b, FR-009)

`unverified_steam_id` is the sixth field `PlayerSearchResult` carries
([contracts/providers.md](../../../specs/003-player-search-match-analysis/contracts/providers.md)) and
the sixth `GET /api/players/search?q=` puts on the wire
([contracts/http-api.md](../../../specs/003-player-search-match-analysis/contracts/http-api.md)). It
is the source's own assertion, unverified by this service, and both documents fix its name for the
same reason this section fixes its wording: a field named `steam_id` could be read as a fact by a
consumer who never opened either contract, and `unverified_steam_id` cannot.

**The wording is fixed here, not left to the component.** Whenever `unverified_steam_id` is not null,
`PlayerResultRow` renders, on its own line, exactly:

> Unverified Steam ID: `<value>`

The word "Unverified" is the requirement, not a decoration on it — it MUST prefix the label verbatim
everywhere this field is shown, so no later change can drop the qualifier by omission the way a plain
"Steam ID:" would. When `unverified_steam_id` is null, the whole line is absent — no placeholder, no
em dash, the same "absent, not blank-filled" discipline §4 states for `Standing` and `CountryLabel`.

**No affordance may be built on this field — the whole of the rule that survives 001's FR-045 and
constitution IX 3.0.0 unchanged (spec.md session 2026-08-24).** Concretely, for this component:

- The claim is plain, non-interactive text inside the row's one existing `<a>` (§2, §9). It is never
  itself a link, never a second `<a>`, never a `<button>`, never `role="button"` or any other
  interactive role — the row has exactly one focus stop before this field exists and exactly one
  after.
- It links to nothing — no `href` built from it, no navigation to a Steam profile, no navigation to
  another `PlayerResultRow`'s result.
- No copy anywhere near it may assert, suggest or invite the reading that two profiles are the same
  person: no "same player", no "also known as", no "merge", no comparison against another result on
  the page. The label above is the entire vocabulary this component is permitted to use for the
  field; nothing else describes it.
- `PlayerResultRowProps` carries no prop, today or later, for "this result is also profile X" — there
  is deliberately nothing in the component's own type for such an affordance to be wired to, which is
  the same enforcement §4 states for the three fields that do not exist at all.

This is carriage, not action: the claim may be _shown_, and showing it truthfully labelled is what
FR-004b now requires: presenting an unverified assertion beside a verified fact (001 FR-006's proven
Steam link) without the distinction would itself be the accuracy fault the amendment exists to avoid.
What is forbidden is building anything on top of the showing.

**`games_played` and `clan` are nullable for a structural reason, not an occasional gap.** A
source-backed result carries `games_played`; a result produced by FR-004d's local fallback over
`aoe_profiles` cannot, because that table has no games-played column — it holds only what 001's
discovery observed (`profile_id`, `alias`, `country`, `first_seen_at`, `last_seen_at`). `PlayerSearchResult`'s own type is `int | None` for exactly this reason (`contracts/providers.md`), and the same
shape is reused for both paths so the row never has to know which one answered.

**FR-002 asks for "at minimum country and current standing", and the row honours it exactly at that
minimum, never inventing past it:**

- `CountryLabel` renders whenever `country` is not null. This is the one field both paths can supply
  and is present on essentially every result — the closest thing to a guarantee this component has.
- `Standing` renders `"<N> games"` (`font-mono`, per DS-8, so a stacked column of counts aligns
  digit-for-digit) whenever `games_played` is not null. **When it is null, `Standing` is absent, not a
  placeholder** — no `0`, no em dash standing in for an unmeasured count, following `StatValue`'s own
  rule against a placeholder numeral reading as real.
- `Clan` renders whenever present, and is the row's fallback distinguishing signal on a locally-known
  result that carries neither a games-played count nor anything else beyond alias and country. Two
  players sharing a name, a country and no clan tag are — correctly — indistinguishable from this row
  alone; they are still each one click away from the profile page (`profile-summary.md`), which is
  where a rating and a rank actually live.

**No per-row degraded indicator exists, because the API carries none.** `degraded` is a field on the
_response_, not on a result (`contracts/http-api.md`): a single search can return some source-backed
rows and some locally-known ones. `ResultsList` states degradedness once, above every row it applies
to (§5's `DegradedBanner`), rather than inventing a per-row badge the contract has nothing to feed.

## 5. States

### `SearchBox` / `ResultsRegion` — the three named empty states, and the three that are not empty

FR-003 requires "found nothing" and "search is unavailable" to never look the same, and US1 scenario 2
and 4 both describe an _empty state_ — a state with zero rows — but the interface owes a **third**
one that is not about row count at all: before any query has been asked. `ResultsRegion` renders
exactly one of the six states below; none may combine or stack with another.

**default / idle — no query yet.** Plain text below `Input`, `text-secondary`: _"Search for a player
by name."_ **Deliberately not a `Callout`**: `Callout`'s own purpose (`shared-primitives.md`) is to
"explain an outcome the user did not ask for", and idle is not an outcome — wrapping it in a bordered,
tone-striped region would make the very first thing a user sees look like something went wrong before
they have done anything.

**loading — a query is in flight.** `ResultsSkeleton`: 5 `Skeleton/block` rows at `PlayerResultRow`'s
own footprint, per `Skeleton`'s own 200 ms-before-paint / 10 s-then-error rule
(`shared-primitives.md`). Never fewer than the previous result count if one is already on screen — a
skeleton that shrinks the list while a fresh query runs reads as results disappearing.

**default — found (`degraded: false`, `results` non-empty).** `ResultsList`: `PlayerResultRow` × n,
most-played first (FR-004a), no `DegradedBanner`.

**empty 1 of 3 — found nothing (`degraded: false`, `results: []`).** `NotFoundState`: `Callout/info` —
_"No player matches “<query>”. Check the spelling, or try a shorter part of the name."_ This is an
outcome, not a failure: `info`'s own tone rule (`shared-primitives.md`) — "nothing went wrong" — is
exactly the claim FR-003 needs distinguished from the next state.

**empty 2 of 3 — search degraded (`degraded: true`).** A `Callout/warning` `DegradedBanner` renders
above `ResultsList` **whenever `degraded` is `true`, independently of whether any row is present**:
_"Player search is temporarily degraded. These results are limited to players already known to this
service."_ Its tone is `warning`, not `danger`: nothing has failed for this request — a reduced,
truthful answer was returned — and `warning`'s own definition ("something will go wrong if nothing
changes") undersells it in the other direction less than `danger`'s ("something failed") would.

- If the fallback also found nothing, `DegradedBanner`'s body carries one further sentence rather
  than a second, stacked `Callout`: _"No locally known player matches “<query>” either."_ Two
  callouts answering the same request is noise `Callout`'s own spec (`shared-primitives.md` §
  "empty… ships by accident") exists to keep out; one banner, worded for the case it is in, does not
  need a second region to say so.
- If the fallback found rows, they render in `ResultsList` beneath the banner exactly as any other
  result set — reduced, not absent (FR-004d, US1 scenario 4: "still offered the routes that do not
  depend on it").

**error — the request itself failed, two distinct causes:**

1. _Rate limited_ (`code: "rate_limited"`, FR-005). `FailureState`: `Callout/warning` —
   _"You're searching too quickly. Try again in <N>s."_ — with `Input` disabled and the same sentence
   doubling as the explanatory text `Button`'s own disabled rule requires
   (`shared-primitives.md`). The countdown recomputes once per second (unlike
   `capture-state-badge.md`'s day-scale countdown, a `retry_after` of a few seconds is unreadable at
   coarser granularity) and `Input` re-enables itself the instant it reaches zero — no manual retry
   needed, because the block was never the user's mistake to correct.
2. _Request failed_ (network error, our own API unavailable). `FailureState`: `Callout/danger` —
   _"We could not search right now."_ with a "Try again" action. This is a failure this service owns,
   distinct from FR-003's "search is unavailable", which is a **successful** response carrying
   `degraded: true` — a request that never completed is not the same claim as one that completed with
   a reduced answer, and the two must never share a `Callout` tone or a sentence.

**hover / focus-visible / active** — `Input`: standard text-input interaction, focus ring per DS-4.
`PlayerResultRow`: whole-row hover fill `surface-sunken`, exactly `match-history.md`'s own
`MatchRow` rule (nothing inside the row — including `Standing` — has its own hover); focus ring on the
row's own link wrapper, inset so it never crops `Standing`'s digits, following `profile-summary.md`'s
identical rule for rating figures.

**disabled** — `Input` only, and only during the rate-limited countdown above; there is no other
disabled condition for either component.

## 6. Tokens used

Colour: `background` (page), `surface` (`Input` fill, row/card), `surface-raised` (`Callout` fill, via
that component), `surface-sunken` (row hover, `Skeleton` fill, `Input` disabled fill), `border`
(`Input` boundary at rest, row separators), `border-strong` (`Input` boundary on focus/hover),
`text-primary` (alias, standing figure), `text-secondary` (idle prompt, clan, country label, labels,
`UnverifiedSteamClaim`'s label and value — §4a deliberately never promotes it to `text-primary`, so it
never carries the same visual weight as a verified fact), `text-disabled` (`Input` label while
disabled), `info` / `warning` / `danger` (the three `Callout` tones in §5), `focus-ring`.

Typography: `mono` for `Standing`'s games-played figure and `UnverifiedSteamClaim`'s id value — DS-8,
the same reasoning `profile-summary.md` and `match-history.md` give for any number or numeric-looking
identifier read down a list — `sans` for everything else (alias, clan, country, labels including
`UnverifiedSteamClaim`'s own "Unverified Steam ID:" label, callout copy). Sizes: `Input` text `md`; row
text `sm`; alias `sm` `semibold`; clan, country, standing, `UnverifiedSteamClaim` `xs`. Weights
`semibold` on alias, `normal` elsewhere.

Radius `md` (`Input`), `lg` (row card at 375, `Callout`, via that component). Elevation `none`
throughout — `profile-summary.md`'s own reasoning against shadowed cards in a list applies here
identically. Motion `duration.fast` + `easing.standard` on row hover and `Input`'s focus/border
transition; **no motion on `Standing`'s figure** — no count-up, no entrance fade, `StatValue`'s own
rule.

**Debounce is not a token.** The delay between a keystroke and `SearchBox` issuing its query is an
interaction-timing default, not a CSS duration drawn from the `motion` family — none of `duration`'s
values are scoped to input-handling latency, and treating one as if it were would misuse a token for a
behaviour it was never measured against. It is left as a plain numeric prop with a sensible default,
not specified here.

Gaps in play: **DS-4** (focus ring), **DS-8** (`Standing`'s tabular alignment rides on `font-mono`
being monospaced, same as every other stacked-figure list in this system).

## 7. Spacing

| Between                                              | Step      |
| ---------------------------------------------------- | --------- |
| Label to `Input`                                     | `space-1` |
| `Input` to `ResultsRegion`                           | `space-4` |
| `Input` padding-inline                               | `space-4` |
| `DegradedBanner` to `ResultsList`                    | `space-3` |
| Between `PlayerResultRow` cards (375)                | `space-3` |
| `PlayerResultRow` padding (375 card)                 | `space-4` |
| `PlayerResultRow` row padding-block (from 768)       | `space-3` |
| Alias to clan                                        | `space-2` |
| Alias line to country/standing line                  | `space-1` |
| Country to standing (same line, from 768)            | `space-4` |
| Country/standing line to `UnverifiedSteamClaim` line | `space-1` |

## 8. Responsive

- **375** — `Input` full width. `PlayerResultRow` renders as a stacked full-width card: alias plus
  clan on the first line, country and standing wrapping onto a second line at `text-secondary`/
  `font-mono` respectively. Neither field ever truncates or ellipsises — `profile-summary.md`'s own
  rule for figures extended to every field here, because a half-visible alias is exactly the
  "near-identical names" failure FR-002 exists to prevent.
- **768** — country and standing move onto the alias's own line, right-aligned, still one `<a>` per
  row. `UnverifiedSteamClaim`, when present, stays on its own line beneath — it is never squeezed onto
  the alias line alongside country and standing, so a longer id string never crowds the field FR-002
  actually needs read at a glance.
- **1280** — layout unchanged from 768; a full `<table>` transform (as `profile-summary.md` and
  `match-history.md` adopt at this breakpoint) is not used here — four short fields in a single-column
  list read as fast at this width as a table would, and a second DOM shape would be one more place for
  the two to drift with no legibility gained. `Input` gains a `max-w-*` cap (gap DS-6) rather than
  spanning the full page width.

`ResultsSkeleton`'s row count and footprint match `ResultsList`'s loaded footprint at the same
viewport, so the loading-to-loaded transition shows no reflow — `match-history.md`'s own acceptance
criterion, restated here because it applies identically.

## 9. Accessibility

- `Label` is a real `<label>` programmatically associated with `Input` (`for`/`id`), never a
  placeholder standing in for it.
- `Input` is `type="search"`, with `aria-describedby` pointing at the rate-limit countdown while
  `disabled` is set, so the reason reaches a screen-reader user at the same moment the control stops
  responding.
- `ResultsRegion` is `role="region" aria-live="polite"` with an accessible name ("Search results");
  `ResultsSkeleton`'s blocks carry `aria-hidden` under the region's own `aria-busy`
  (`Skeleton`'s own rule) so the loading state announces once, not per block, and the settled state —
  found, not-found, degraded or failed — is what actually gets read out.
- `PlayerResultRow`'s whole card/row is one `<a>` (never a `<div>` with a click handler), matching
  `match-history.md`'s identical rule for `MatchRow` — everything inside it is non-interactive text,
  so the row has exactly one focus stop.
- The list is a `<ul>`/`<li>` at every viewport (§8 keeps one DOM shape here, unlike
  `profile-summary.md`/`match-history.md`'s table transform).
- `NotFoundState`/`DegradedBanner`/`FailureState` follow `Callout`'s own `role="status"` /
  `role="alert"` split (`shared-primitives.md`).
- Every field (alias, clan, country, standing, `UnverifiedSteamClaim`) is selectable text, never an
  image or canvas.
- `UnverifiedSteamClaim` carries no role of its own — no `role="link"`, no `role="button"`, no
  `tabindex` — precisely because §4a forbids it being a second interactive element; it is read by a
  screen reader as part of the row's one link, in document order, the same as every other field.
- 200% zoom and 320px logical width without horizontal scrolling; no field ellipsises at any
  viewport (§8).

## 10. Visual acceptance criteria

- [ ] The idle screenshot shows the plain-text prompt, no `Callout` border or tone stripe anywhere in
      the frame.
- [ ] The not-found screenshot and the degraded-with-results screenshot are visibly different tones
      (`info` vs `warning`) and different copy, side by side, so FR-003's distinction is provable from
      a single side-by-side comparison.
- [ ] The degraded screenshot shows the `DegradedBanner` above the row list, in the same frame as at
      least one `PlayerResultRow`, proving "reduced" and "some results" are not mutually exclusive.
- [ ] The degraded-and-empty screenshot shows one `Callout`, not two, with both sentences present in
      its body.
- [ ] The rate-limited screenshot shows `Input` visibly disabled with the countdown sentence in the
      same frame — never a bare disabled control with no explanation.
- [ ] A row seeded with `games_played: null` (a locally-known result) renders with no numeral, no `0`
      and no em dash in the `Standing` position — confirmed by overlaying it against a row that does
      carry a count and observing the field is absent, not blank-filled.
- [ ] A row seeded with a `clan` renders the tag beside the alias in every story that sets it, and a
      row without one shows no empty bracket.
- [ ] A row seeded with `unverifiedSteamId` shows "Unverified Steam ID: `<value>`" verbatim, the id in
      `font-mono`, and the row still renders exactly one link in the accessibility tree — confirmed by
      counting focusable elements in that story against a row without the field and finding no
      difference.
- [ ] No screenshot in this file, at any state, shows a second link, a button, or any copy reading
      "same player", "also known as" or "merge" anywhere near `UnverifiedSteamClaim` — the claim reads
      as a labelled fact and nothing else is clickable because of it.
- [ ] Loading screenshot's skeleton row count matches the loaded screenshot's row count at the same
      viewport, with no reflow between the two.
- [ ] Converting any screenshot to greyscale leaves the three `Callout` tones (`info`/`warning`/
      `danger`) still distinguishable by heading text and body copy alone.
- [ ] No avatar, clan crest or flag illustration in any frame — only text and, at most, a free-licensed
      `aria-hidden` country glyph.
