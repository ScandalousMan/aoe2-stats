# Quickstart: validating this feature end to end

How to prove the feature works. Not a test plan — the scenarios a test plan has to make pass, in the
order that finds problems soonest.

The ordering is deliberate: scenario 1 needs no external source at all, and scenario 9 is the one
that costs a permanent retention. Running them out of order means discovering a page-render bug by
spending a recording on it.

## Prerequisites

Everything [001's quickstart](../001-steam-link-replay-ingestion/quickstart.md) asks for, plus:

- a **second** AoE2 profile id that is not yours and has played publicly within the last week — an
  opponent from one of your own recent matches is the easiest one to get, and it is the only kind
  this feature can honestly be tested against;
- one match id from **more than 31 days ago**, to exercise every expired path. `docs/data-sources.md`
  §2 lists real ones with their measured outcomes, which is faster than waiting a month;
- `.env` extended from `.env.example` with this feature's keys — the favourites bound, the search
  TTL and rate limit, the analysis request limit, budget and lease, the retention cap, and the
  raw-size ceiling above which a recording is refused before it is parsed.

```bash
uv sync --all-packages --dev
pnpm install
uv run alembic upgrade head
```

## Running it

The API and the front end as 001 describes them. The analysis entry point is a separate function, so
locally it is reached through `vercel dev` rather than through uvicorn — which is exactly the
distinction it exists to make, and running only uvicorn is how a reviewer concludes the isolation
works when it has not been exercised:

```bash
vercel dev
```

```bash
curl -X POST localhost:3000/api/analyze -H "Cookie: session_id=..." -d '{"game_id": 500546441}'
```

## Scenario 1 — Search degrades honestly

Do this first, with the search source deliberately unreachable (block the host, or point its base URL
at a dead address).

1. Search a name. Expect results anyway, from locally-observed profiles, with `degraded: true` and a
   visible statement in the interface that the answer is reduced.
2. Confirm every other route still works: a profile opened by id, the favourites list, a match page,
   both CTAs (SC-002a).
3. Restore the source. Search a partial, wrongly-cased fragment — `vipe` for `Vipechester`. Expect a
   match, most-played first (FR-004a).
4. Search something that matches nothing. Expect an empty result that is **visibly not** the degraded
   state (FR-003). If the two look the same in the interface, this scenario has failed even though
   both requests succeeded.
5. Search the same term twice and check `provider_calls`. Expect one row, not two (FR-004e).
6. Search repeatedly past the per-user limit. Expect `rate_limited` with `retry_after` (FR-005).

## Scenario 2 — Nothing about a search result leaks an account link

1. Capture the raw response from the search source for a well-known player. Confirm by inspection
   that it carries `steamId`, `shared` and `sharedHistory` (`docs/data-sources.md` §3).
2. Search the same player through this service. Grep the response, the database and the logs for that
   `steamId`. **Expect nothing, anywhere** (FR-004b, 001 FR-045).
3. Confirm `profile_search_cache.results` holds only the five contract fields — not the raw body.

If this scenario fails it fails silently in production, which is why it comes second.

## Scenario 3 — A hidden profile stays hidden, including when the source is down

1. Find a profile the source marks hidden. Search for it. Expect absence, and `404` on its profile
   page (FR-004c).
2. Take the source down and search again. **Expect absence still** — this is the case the
   `hidden_observed_at` column exists for, and the one a fallback written without it gets wrong.

## Scenario 4 — Any player's profile and history

1. Open the second profile id by URL. Expect ratings, rank, wins and losses per ladder, matching the
   official leaderboard (US1 independent test).
2. Open its match history. Expect newest first with opponent, map, civilisation, result, rating change
   and duration.
3. Open a profile that has never played ranked. Expect a valid, explained profile — not an error and
   not a blank page (US1 scenario 5).
4. Sign out and request the same URLs. Expect `401`, not a page (FR-010).
5. Check the response headers on all of the above for `X-Robots-Tag: noindex, nofollow`, and
   `robots.txt` for the client routes.

## Scenario 5 — The match page is complete at any age

1. Open the >31-day-old match. Expect every participant with team, civilisation, result and rating
   change, plus map, ladder, version, start time and duration — **all of it**, with nothing blank
   (SC-003).
2. Confirm both CTAs are shown as unavailable with their reason and their date, and that neither is
   clickable (US2 independent test, FR-025, FR-034).
3. Open the same match from two different participants' histories. Expect the identical page, and one
   `matches` row (FR-021).
4. Open a match carrying a civilisation or map id the reference data cannot name. Expect the raw
   identifier, never a guess (FR-020).

## Scenario 6 — Downloads, per point of view

1. Open a recent third-party match. Expect one download per participant, each with its state and, for
   the obtainable ones, the date it stops being obtainable (FR-023, FR-024).
2. Download two different participants' points of view. Open both in the game and confirm each shows
   the match from the expected player's side (US3 independent test).
3. Check the object store and `retained_recordings`. **Expect zero new bytes and zero new rows**
   (FR-027, SC-009). This is the assertion that separates downloading from analysing, and it is easy
   to lose to a helpful cache.
4. Take a match you played whose replay this service archived and which is beyond the window. Expect
   your own point of view offered from the archive, the others shown as expired, and the difference
   explained (US3 scenario 4). Confirm a `replay_access_log` row for the archived one (FR-029).

## Scenario 7 — The analysis runs once, and says what it found

Use a recent third-party match.

1. Request the analysis. Expect progress rather than a frozen screen, and confirm you can navigate
   away and return to it (FR-035).
2. When it publishes, check the output against the game itself for one player: the build order, the
   training order, the technologies, the age-up commands, the units and counts, and the APM (FR-043
   as narrowed by [research.md](./research.md) R1).
3. Confirm the age-up times are labelled as **ordered**, not reached (R5), and that a two-player game
   reports two feudal age-ups rather than four (the double-click).
4. Confirm the analysis carries no ranking, grade, score, benchmark or advice (FR-043).
5. Open the same match as a different user. Expect the analysis immediately, and **one** row in
   `provider_calls` for that recording across both requests (FR-031, SC-006).
6. Confirm `match_analyses` records the point of view and the parser version (FR-032), and that
   `retained_recordings` holds exactly one row with a checksum (FR-033).

## Scenario 8 — Everything that can go wrong with an analysis

1. **Concurrency.** Two users request the same match within the same second. Expect one row, one
   fetch, one parse, and both users shown the same progress (FR-038).
2. **Interruption.** Kill the function mid-parse. Expect no row stuck in an unclaimable state; expect
   the *next person to open that match* to resume it, and expect **nothing on a timer** to (FR-037,
   FR-044).
3. **Unparsable.** Analyse a deliberately corrupted recording. Expect a recorded failure with its
   reason, a plain statement to the user, and a match that is **not** presented as analysed (FR-036).
4. **Too big.** Analyse an eight-player game. This is R3's memory bound and it may legitimately fail;
   what must not happen is a silent truncation or a partial analysis presented as complete.
5. **Expired.** Request an analysis of the >31-day-old match. Expect permanent unavailability with a
   reason, and no button (FR-034).
6. **Isolation.** While a parse is failing, confirm the API answers normally and the ingester's next
   run is unaffected (FR-042, SC-013).

## Scenario 9 — Capture always wins

The scenario this feature is most likely to fail in production, and the one that matters most.

1. Queue a backlog of captures near their deadline. Request an analysis. **Expect the analysis to
   wait** and the captures to proceed (FR-039, US4 scenario 6).
2. Run search, browsing and analysis continuously for a period covering at least two ingest cycles.
   Confirm `expired_total` stays at 0 (SC-008, constitution I).
3. Fill the retention cap. Expect new analyses refused with a clear reason, an
   `analysis_cap_reached` alert, and capture entirely unaffected (FR-047, US4 scenario 8).
4. Confirm total retained bytes never exceed the declared cap (SC-009).

## Scenario 10 — Recomputation without the source

The proof that FR-033 bought what it was meant to buy.

1. Take a published analysis of a match whose recordings the source no longer serves — the
   >31-day-old one.
2. Change the parser version. Confirm the match-detail response now reports `stale: true` for that
   analysis, and recompute by asking for it the same way a first analysis is asked for — `POST
   /api/analyze`. Confirm nothing on a timer did it first (FR-044).
3. Expect it to succeed from this service's own retained bytes, with the checksum verified, and
   **zero** calls to the source in `provider_calls` (FR-041, SC-009a).

If this fails, the retention decision the constitution was amended for has bought nothing.

## Scenario 11 — Favourites, and what they must not cause

1. Favourite two players. Sign out, sign in. Expect both listed with current standing, each reachable
   in one click (US5 independent test).
2. Unfavourite one. Expect it gone and nothing else about that player changed.
3. Confirm no capture, ingestion or archival happened for either (FR-012, US5 scenario 4).
4. Favourite past the bound. Expect `favourites_limit_reached` (FR-016).
5. Favourite while signed out. Expect a sign-in prompt that returns you where you were (US5 scenario 5).
6. Confirm nothing anywhere can answer "who favourited this player" (FR-015).

## Scenario 12 — Data rights cover what this feature added

**001's US5 (T090–T092) lands before US4 of this feature ships** — decided 2026-08-23, see
[research.md](./research.md) R14. So this scenario is walked *before* the first third-party recording
is ever retained, not after. It is part of this feature's definition of done, not someone else's.

1. Export. Expect favourites and the analyses this user requested (FR-017, SC-012).
2. Erase. Expect favourites gone, `requested_by_user_id` cleared on analyses the user asked for, the
   analyses themselves still standing, and **the retained recordings still present** — they are
   derived from public match records, shown to everyone, and must stay recomputable
   (`data-model.md`'s erasure rule for `retained_recordings`).
3. Object as a third party appearing in a retained recording. Expect the recording removed and the
   analyses derived from it withdrawn with it (FR-046).
4. Confirm `docs/privacy/processing-register.md` carries retention of analysed third-party recordings
   as its own activity, with its own legal basis (FR-045). This one is checkable **today** and should
   not wait.

## Automated coverage

Everything above except scenarios 4.2, 6.2, 7.2 and 12 is automatable, and the ones that are not are
not for the same reason 001's were not: they need a human to look at the real game.

- Scenario 4.2 needs the official leaderboard read by a person.
- Scenario 6.2 needs two files opened in AoE2 II:DE.
- Scenario 7.2 needs a person who can tell whether the build order is the one that was played. This
  is the only check that the analysis is *right* rather than merely produced, and no fixture
  substitutes for it — the golden fixture proves the extraction is *stable*, which is a different
  claim.
