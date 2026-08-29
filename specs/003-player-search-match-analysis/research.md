# Phase 0 Research: Player Search, Favourites and On-Demand Match Analysis

**Feature**: `003-player-search-match-analysis` | **Date**: 2026-08-23

Everything below was either measured here, or is a measurement recorded in `docs/` that this feature
depends on. Where a number appears twice in this repository one of the copies is wrong, so this file
states no measurement that `docs/data-sources.md` or an ADR already carries — it points at them.

The findings are numbered because [plan.md](./plan.md), [data-model.md](./data-model.md) and
[contracts/analysis.md](./contracts/analysis.md) refer to them by number.

---

## R1 — What the recorded game can actually be asked

**This is the finding that changes the spec.**

### Decision

**003 publishes only what is read directly from the artifact.** Per participant: the build order, the
training order, the technologies researched, the age-up **commands**, the units trained with counts,
actions per minute, and the resignation or defeat.

**Resources and villager count are derivable, and deriving them is a separate feature.** They are not
present in the recording; they are reconstructible from the command stream by partial re-simulation.
That reconstruction has its own rules, its own failure modes and its own verification problem, and it
cannot be a clause inside a requirement about what to display.

### Rationale

Measured 2026-08-23 against `tests/fixtures/replays/AgeIIDE_Replay_500546441.zip`, the committed
reference replay, with the pinned `aoe2rec-py` 0.1.21 the project already ships.

What the parse yields, and what each FR-043 clause maps onto:

| FR-043 asks for                             | In 003                | From                                                                                    |
| ------------------------------------------- | --------------------- | --------------------------------------------------------------------------------------- |
| the order in which they built, with times   | yes, with R4's caveat | `Build` actions, `world_time`                                                           |
| the order in which they trained, with times | yes                   | `DeQueue` actions — the DE train command, carrying `unit_id`, `amount`, `building_type` |
| the time they reached each age              | **command time only** | `Research` with `technology_type` 101/102/103 — see R5                                  |
| resources at each age-up                    | **deferred**          | reconstruction only — see below                                                         |
| villager count at each age-up               | **deferred**          | reconstruction only — see below                                                         |
| technologies researched, with times         | yes, as identifiers   | `Research`, `technology_type` — see R13                                                 |
| units trained, with counts                  | yes, as identifiers   | `DeQueue`, `unit_id` and `amount`                                                       |
| actions per minute                          | yes                   | `Action` operations per `player_id` over the world clock                                |
| when they were defeated or resigned         | yes                   | `Resign` action; the `PostGame` `WorldTime` block ends the clock                        |

A `.aoe2record` is a **command log**, not a state log. It records what each player told the game to
do; the game's response — resources gathered and spent, units lost in combat, buildings destroyed —
exists only in the simulation, which is why every client needs the same deterministic engine to
replay it. Anything about _state_ is therefore a reconstruction, not a reading, and the two must not
be published through the same requirement as if they carried the same confidence.

### What a reconstruction needs, and where it stops

Villager count is the tractable end of the problem and is worth writing out, because it shows the
shape of the whole:

- a `DeQueue` is an _order to train_, not a villager. The villager exists one training duration later,
  and that duration varies by civilisation (Persians' faster town centres, Chinese' extra starting
  villagers, Mayans' cheaper ones) and by game speed;
- an `Unqueue` cancels it. The action vocabulary carries `Unqueue`, `FarmUnqueue` and
  `FishtrapUnqueue` — verified present in the parser's own type table, though absent from this
  particular game — so cancellations are observable;
- a new object id appearing in a later command (`Move`, `Interact`, `Gatherpoint` all carry
  `object_ids`) confirms a unit was really created. It is a confirmation and not a census: a villager
  that walks to the gather point and works without ever being individually commanded issues nothing,
  so absence of an id proves nothing;
- a town centre destroyed while villagers are queued cancels them, and **building destruction is not
  in the command log at all**. Nothing the victim does records it, and nothing the attacker does
  records the outcome.

That last one is the boundary. Everything above it is bookkeeping over the command stream and can be
made exact; combat outcomes cannot, because the log records intent and never effect. A reconstruction
is therefore accurate up to what combat took away from a player, which is precisely the situation
where a viewer most wants the number.

This is why it is its own feature: it needs a stated accuracy claim, a way to verify a derived number
against the game itself, and an honest label for the cases where it is a lower bound rather than a
count. None of that fits inside FR-043, and all of it is invisible if the derivation ships as a
clause in a display requirement.

### One measurement that could shortcut part of it

The parser's type table also carries an **`Achievements`** post-game block, alongside the
`Leaderboards` and `WorldTime` blocks the reference recording actually contains — that recording has
`num_blocks: 2` and 389 serialised bytes, and no achievements section. So the engine knows how to
read such a block; this game does not carry one.

Whether _any_ current-patch ranked DE recording carries it is **unverified and worth one measurement
before the derivation feature commits to simulating anything**, because an achievements block in the
recorded game reports gathered resources and unit counts as facts. If it is ever present, part of
FR-043 is a read rather than a reconstruction, and the two paths have very different costs. This is
the first thing that feature's own Phase 0 should measure, across several recordings and several game
modes — one negative sample proves nothing.

### Consequence for the spec — settled 2026-08-23

`spec.md` is amended. FR-043 loses its two state clauses, FR-043b forbids publishing a reconstructed
quantity at all, and FR-043c fixes the wording of an age-up time (R5). The derivation becomes its own
feature, **specified and built after this one**: it depends on this feature's extraction, on the
recordings FR-033 retains, and on a way to verify a derived number against the game itself. Building
it first would invert that dependency.

Recomputing the analyses published in the meantime costs nothing and reaches no source — FR-033 plus
FR-041 is precisely what makes a later enrichment free, and it is the return on the retention decision
the constitution was amended for.

### Alternatives considered

- **Reconstruct the economy inside 003.** Rejected on scope, not on feasibility. The spec itself says
  FR-043 is "deliberately the floor, chosen so that the pipeline is proven end to end before anything
  is built on top of it"; a re-simulation is the thing built on top.
- **Publish an approximate villager count now and refine it later.** Rejected. An approximation with
  no stated accuracy is the "conclusion nobody can check" the spec's own Q2 argument exists to
  prevent, and it would be published to every viewer of that match.
- **Take resources from a third-party service that publishes them.** Rejected. No such source exists
  for a match this service did not play (`docs/data-sources.md` §4 records the historical corpus empty
  since 2026-02), and it would be an unverifiable claim published as our own fact.

---

## R2 — One point of view is enough for every participant

### Decision

Analysis is per **match**, not per point of view. One recording is fetched, retained and parsed, and
it yields facts about every player. The spec's central assumption holds.

### Rationale

The spec recorded this as an assumption to verify before planning committed to it. Measured on the
reference replay: every `Action` operation carries the `player_id` that issued it, and both players'
commands are present in the single recording — 5 583 actions for player 1 and 5 631 for player 2.
`zheader.game_settings.players` carries each slot's `profile_id`, `name`, `civ_id`, `color_id` and
`resolved_team_id`, which is what joins the parse to `match_players` without guessing.

The recorded game differs between points of view only in what its owner could _see_; the command
stream is the full, shared, deterministic log. This is why one parse is enough, and why FR-031's
"at most once per match" is achievable rather than aspirational.

FR-032 still records which point of view was used, exactly as the spec says: it costs one column and
it is what makes a later correction traceable if this ever turns out to be false on some game mode.

### Alternatives considered

- **Parse one recording per participant.** Rejected: it multiplies fetches, retention and cost by the
  player count for no additional fact, and it would put an eight-player match permanently out of
  reach of FR-047's cap.

---

## R3 — Memory, not time, is what bounds a parse

### Decision

The analyzer treats a parse as memory-bounded work: it reduces the operation stream to the published
analysis and never holds both, it refuses recordings above a configured raw-size ceiling before
parsing them, and a parse that exceeds the platform's memory fails visibly under FR-036 rather than
being retried forever.

### Rationale

Measured 2026-08-23, same fixture, same wheel: **0.58 s of parse, ~631 MB peak resident**, for a
6.9 MB raw 1v1 producing 484 542 operations. Vercel Hobby with Fluid compute gives 2 GB
(`docs/adr/0002-hosting.md`).

The time is a rounding error against a 300 s budget. The memory is not: `parse_rec` materialises
every operation as a Python object, so consumption scales with operation count, and operation count
scales with players × duration. An eight-player game — ~2.5 MB zipped, so roughly 20 MB raw
(`docs/data-sources.md` §2) — is in the region of three times the operations, which puts it close
enough to the ceiling that it must be treated as a real failure mode rather than a theoretical one.

**The number that follows.** 631 MB for 6.9 MB raw is an amplification of ~91×, and the ceiling is
2 GB, which puts the break-even near 22 MB of raw recording. `ANALYSIS_MAX_RAW_BYTES` therefore
defaults to **24 MB**, and the choice is deliberate rather than conservative: an eight-player game at
~20 MB raw lands near 1.8 GB, inside the ceiling and uncomfortably close to it. Refusing it up front
would decide by configuration a case quickstart §8.4 says must be allowed to fail _visibly_;
admitting it keeps FR-036's path real. The key exists to refuse what is certainly impossible before
paying for a fetch, not to guarantee what is merely tight. The existing `_MAX_INNER_BYTES = 200 MB`
in `packages/replay-engine` stays what it is — a zip-bomb guard, about a different threat, and ~9×
too permissive to protect memory.

The spec anticipated this and pointed at the wrong resource: its assumption reads "the platform's
per-execution budget is 300 s ... analysis of one match is expected to fit". It fits in time by two
orders of magnitude and may not fit in memory. FR-036's visible failure is therefore the code path
that will actually run first in production, and it is where the eight-player case will show up.

### Alternatives considered

- **Stream the operations instead of materialising them.** Preferred, and not available: the pinned
  wheel exposes `parse_rec(bytes) -> dict` and no iterator. Recorded as the first thing to ask for if
  a newer wheel ships (ADR-0001 already tracks the wheel lagging the Rust crate).
- **Raise the function memory.** Not available on the free tier, and it would be a Vercel-shaped fix
  to a portable problem (constitution XII).
- **Retry a failed parse on a bigger machine later.** Rejected: there is no later, because FR-044
  forbids the sweep that would run it.

---

## R4 — The `Build` action is not decoded by the pinned wheel

### Decision

`packages/replay-engine` decodes the `Build` payload itself, from the raw bytes the wheel hands back,
and the decoding is covered by a golden test against the committed reference replay.

### Rationale

ADR-0001 recorded 326 `Build` actions in this replay and concluded that "`Build` plus `Research`
plus the `Sync` clock is everything the V2 engine needs". True of the information; not true of the
shape. Measured here: `Research` is fully decoded (`player_id`, `building_id`, `technology_type`),
and `Build` is **not** — it comes back as `{"action_length": 36, "data": [...]}` with no `player_id`
field at all. The player id and the building type are inside `data`, and reading them is this
repository's job.

This is the kind of gap that is cheap to close and expensive to discover late, which is why it is
recorded rather than left to the implementer to find. It is also why the decoder belongs in the
engine adapter and nowhere else: it is knowledge about one engine's output format, and constitution V
says that knowledge lives behind the Protocol so a second engine can be swapped in without a caller
learning about it.

### Alternatives considered

- **Build from the Rust crate with `maturin` to get a newer, fuller decoder.** Rejected for now, and
  kept as ADR-0001's existing fallback: it trades a small decoder for a source build in the deploy
  path, on a platform with a 500 MB bundle limit and no build toolchain guarantee.
- **Infer buildings from something else.** There is nothing else. `Build` is the only signal.

---

## R5 — An age-up time is a command, not an arrival

### Decision

The analysis publishes the time the age-up was **ordered**, labelled as such, and does not claim the
time the age was reached. Duplicate commands are collapsed to the first occurrence per
`(player_id, technology_type)`.

### Rationale

Measured on the reference replay, the age-up commands are:

```
player 1: feudal 401 674 ms, castle 915 577 ms, imperial 2 070 341 ms
player 2: feudal 403 494 ms, castle 1 168 258 ms, imperial 2 042 924 ms
```

Two things are visible in the raw stream and both matter. First, player 2's feudal command appears
**twice**, 208 ms apart, and so do four other commands — a double-click on the age-up button issues
the command twice, and a naive reading reports five age-ups in a two-player game. First occurrence
wins.

Second, a research _command_ is not a research _completion_. The age is reached when the research
finishes, which is the command time plus the technology's research duration, adjusted for game speed
and for any civilisation bonus. This repository holds no technology-duration table: 002 wrote the
re-derivation procedure for civilisations only, deliberately structured so a second identifier can be
added beside it later. Adding technology durations is that second identifier, and it is a separate
piece of work with its own verification.

So the honest statement today is the one the artifact supports. "Ordered Feudal Age at 6:41" is a
fact; "reached Feudal Age at 6:41" is false by roughly two minutes, and it is false in the direction
that flatters the player, which is the worst direction for a number nobody can check. FR-043's own
rule — a raw identifier rather than a guessed name — is the same discipline applied to a time.

### Alternatives considered

- **Hard-code the three age-up durations.** Rejected: they vary by game speed and by civilisation, a
  hard-coded constant would be a measurement living in code with nothing to keep it honest, and
  `CLAUDE.md`'s rule about where measurements live forbids exactly this.
- **Extend 002's reference data with technology durations now.** The right answer eventually, and out
  of scope here — it is a maintainer-facing derivation with its own verification, and this feature
  should not be the thing that decides how it is done.

---

## R6 — Analysis runs without a scheduled job

### Decision

`apps/analyzer` is a library exposing `run_once(budget_seconds)`, driven by a dedicated Vercel
function `api/analyze.py` at `maxDuration: 300` that a signed-in person's click reaches directly.
Work is claimed with a database lease. An invocation that dies leaves an expired lease, and the next
person who opens that match re-claims and restarts it. No cron, no sweep, and the existing daily
ingest cron is not widened.

### Rationale

FR-044 forbids a scheduled job and a background sweep. The platform forbids the other obvious
answer: a serverless function stops executing when its response is returned, so "reply 202 and keep
working" is not available, and the Python runtime has no `waitUntil` equivalent to buy it.

That leaves the request itself as the only thing that can drive work, which is why the entry point
is its own function rather than a route on the API — `api/index.py` is capped at `maxDuration: 10`
in `vercel.json`, and 60 s of analysis (SC-007) does not fit behind it.

A file at `api/analyze.py` is reached before the `/api/(.*)` rewrite, because Vercel resolves a
filesystem match before it consults `rewrites`. This is not assumed: `api/cron/ingest.py` already
depends on it in production today, and `scripts/checks/spa-routing.mjs` encodes the resolution order
as an executable check.

The property this buys, and the reason it is worth stating plainly: `running` in this system means
_someone was working on this recently_, not _work is happening now_. A lease with an expiry is the
only honest representation, and every state transition in [data-model.md](./data-model.md) is written
against that reading. A match that is abandoned mid-parse and that nobody ever opens again stays
unanalysed forever — which is correct, because nobody is waiting for it.

### Alternatives considered

- **Let the existing daily cron collect abandoned analyses.** Rejected. It is a background sweep with
  a cron's paperwork, FR-044 forbids it, and it would put analysis work inside the one execution
  window constitution I reserves for capture.
- **Have the API self-call the analysis function to fan out.** Rejected twice over: constitution III
  forbids `apps/*` opening an outbound connection, and it would be a Vercel-shaped mechanism with no
  meaning on a VPS (constitution XII).
- **A queue broker.** Rejected for the reason 001 rejected it, and more strongly: it would be a new
  moving part serving the lowest-priority story in the product.

---

## R7 — How FR-039 is enforced rather than intended

### Decision

Three independent gates, all inspectable with a SQL query, checked in `apps/analyzer/admission.py`
before an analysis is allowed to fetch anything:

1. **Deadline gate** — no analysis fetch while any `replay_captures` row is unstored and inside its
   deadline danger window. Capture's backlog is the signal; the query is the same one the capture
   audit already uses.
2. **Budget gate** — analysis draws on its own daily allowance of requests to the replay source,
   configured below capture's, counted from `provider_calls`. Exhausting it defers analyses; it never
   touches capture's.
3. **Storage gate** — FR-047's cap, expressed in bytes and set below the free allowance so that
   capture always has headroom it never has to compete for. At the cap, new analyses are refused with
   a clear reason (US4 scenario 8), and capture is unaffected.

### Rationale

Constitution I is a tie-break rule, and a tie-break rule that lives only in prose is decided by
whoever wrote the code last. Each gate is a condition over rows this system already keeps, which
means it can be asserted in a test and read in production without instrumentation — the same property
001 chose the database-as-queue for.

The ordering matters and is the reason there are three rather than one: they fail in different
directions. The deadline gate protects the _window_, the budget gate protects the _source's patience_
and the storage gate protects the _allowance_. Capture can be starved by any of the three
independently.

### Alternatives considered

- **A shared token bucket with priorities.** Rejected: a token bucket lives in process memory, and
  there is no shared process here. It would work on a VPS and silently do nothing on Vercel, which is
  the failure mode constitution XII exists to prevent.

---

## R8 — Availability of a point of view is derived, never probed

### Decision

Whether a participant's recording is obtainable is computed from the match's completion time against
the measured retention window, plus what this service already holds. The source is never asked in
order to render the page. A 404 at click time is the documented boundary race, and it is reported as
what it is.

### Rationale

`docs/data-sources.md` §2 measured this: `HEAD` answers `405` and `Range` is ignored. There is no
cheap existence probe. Asking the source means downloading the whole recording, and doing that for
every participant of every match a user opens would be a bulk read of third-party recordings driven
by browsing — which constitution IX forbids in the same sentence FR-012 restates.

So the four states FR-025 requires are each derived from something this service already knows:

| State                          | Derived from                                                          |
| ------------------------------ | --------------------------------------------------------------------- |
| held in this service's archive | a `replay_captures` row in `stored` — that row only, see below        |
| obtainable now                 | the match completed inside the capture budget (`capture_budget_days`) |
| expired                        | the match completed outside it                                        |
| never recorded by the game     | a prior attempt that answered 404 while inside the window             |

### The retention window is not settled, and this table assumed it was — decided 2026-08-29

The two middle rows read "the retention window" as a **rolling** window of known length. On
2026-08-28 `docs/data-sources.md` recorded a second, larger sample that contradicts that reading: an
equally sharp boundary six months back rather than 31 days, measured after the replay endpoint moved,
with a **fixed epoch** fitting the sample as well as any rolling window. The question is open, and
constitution I 4.1.0 forbids settling it by assumption.

**What is decided, and what is not.** The derivation stays conservative, but it no longer reads the
measured window at all: the `obtainable`/`expired` split now runs against `capture_budget_days`
(`CAPTURE_BUDGET_DAYS`, constitution I), a configured budget deliberately **shorter** than either
contested reading of the window, not a restatement of it. Reading the split as `docs/data-sources.md`'s
own "approximately 31 days" — itself the reading the second sample above contradicts — offered zero
margin: a match at day 30.9 rendered `obtainable` for a recording the source may already have
discarded, which is exactly the failure FR-025 forbids. `capture_budget_days` is strictly shorter than
either reading of the window, so the derivation genuinely under-offers, with margin rather than at
exact equality: it renders `expired` sooner than either reading of the window requires and never
later, so it still never presents an unobtainable download as an action that then fails — the same
guarantee as before, now held by a number this project configures rather than one it measures.

**What changes is the date.** `obtainable_until` is a promise about the future, and under an
unresolved window there is no honest one to make. It is therefore **null while the question is open**,
and FR-024's date appears only once `docs/data-sources.md` records the window as settled. A date
derived from a window that may not exist is worse than no date: the user plans around it.

**The cost is stated rather than hidden.** Under the epoch reading this service tells a user `expired`
for a recording the source would still serve. That is a real defect and it is accepted knowingly, for
one turn of the argument: the alternative is probing, and probing is a full download per participant
per page view (`HEAD` answers `405`), which is the browsing-driven bulk read of third-party recordings
constitution IX forbids and FR-012 restates. There is no cheap third option. **SC-004 cannot be
claimed while this stands** — it measures stated availability against what the source actually
answers, and under the epoch reading it fails by construction, not by implementation error.

This reverses the moment the measurement settles, and what would settle it is written down in
`docs/data-sources.md`: re-measure on a different profile, and again a week later. Until then this
paragraph is the reason a reader does not have to re-derive any of it from the diff.

**A retained recording is not an archive for this purpose** — decided 2026-08-23. Deriving `archived`
from a `retained_recordings` row is tempting: the bytes are right there, and past 31 days they are the
only copy anyone holds. It is refused, and 3.0.0 strengthens the refusal rather than weakening it — the bytes now survive an
erasure, so serving them would redistribute a recording of someone who has asked this service to
forget them. Constitution IX permits retention so that a _published
analysis stays recomputable_; handing those bytes to any signed-in caller is redistribution of a third
party's recording after the source destroyed its own, which is a second processing purpose with no
basis and no register entry. FR-026 says "the signed-in user's **own** point of view", and a retained
recording generally is not one.

So a match whose recording this service holds only because someone analysed it renders as `expired`,
with an analysis available. That is the honest answer, and it is the shape of the whole feature: the
facts survive, the file does not.

The last one is the only state that requires evidence rather than arithmetic, and the evidence
already exists: 001 records exactly this outcome on `replay_captures` for a user's own matches, and
an analysis fetch that 404s inside the window records it for a third party's.

SC-004 asks that the stated availability match what the source answers "at that moment", and the
boundary race in the spec's edge cases is the case where it cannot: a match hours from expiry is
offered, and by the time the user clicks, the source has purged it. The design does not pretend to
close that race — it names it. The countdown FR-024 requires is what makes the risk visible before
the click, and a 404 after it is reported as "it expired while you were reading", distinctly from
"it was never recorded" (FR-025).

### Alternatives considered

- **Probe on page render.** Rejected: it is a full download per participant, it is browsing-driven
  bulk reading of third-party recordings, and it would burn the request budget constitution I
  reserves for capture.
- **Probe lazily on hover or focus.** Same objection, arriving more slowly.

---

## R9 — Retained recordings are a separate table and a separate key prefix

### Decision

A retained recording is a row in its own table and an object under its own key prefix, never a flag
on `replay_captures` and never under 001's key scheme.

### Rationale

FR-048 requires that the two remain distinguishable, and gives the reason: different legal bases,
different points of view. The failure it is guarding against is not confusion in someone's head, it is
a `SELECT count(*)` that quietly answers a question nobody asked — "how many replays do we hold"
meaning one thing to the processing register (activity 3) and another to the free-tier watch (bytes in
the bucket). (**Amended 2026-08-29**: this said the two differ by "different consent", and called
activity 3 "explicit consent". Constitution IX 4.0.0 retired that gate — activity 3 now rests on
legitimate interest with a right to object, and FR-033's retention on IX's public-recording basis. The
distinction survives and its reason narrows to _legal basis and point of view_, exactly as spec.md's
FR-048 already records.)

A separate table makes the ambiguous query impossible to write by accident: there is no column to
forget to filter on. A separate key prefix extends the same property to the bucket, where the
free-tier watch and any future bulk copy both operate by prefix and neither has a database to join
against.

`packages/storage`'s existing `replay_object_key(game_id, profile_id)` is deliberately not reused for
the same reason it was written the way it was — it is idempotent per `(game_id, profile_id)`, and a
retained recording and a captured replay of the _same_ pair are two different things with two
different bases and must not resolve to one object.

### Alternatives considered

- **One table with a `basis` column.** Rejected above. It also makes 001's existing queries wrong the
  moment the column is added, silently, everywhere.
- **One table, one prefix, distinguished by a join at read time.** Strictly worse: it moves the
  distinction from the schema into every reader.

---

## R10 — Per-user rate limiting does not exist in the API yet

### Decision

Add database-backed per-user counters — a fixed-window count per `(user_id, bucket, window)` — and
apply them to search (FR-005), recorded-game requests (FR-028), analysis requests (FR-040) and the
retention those requests cause (FR-047).

### Rationale

The API has no rate limiting today. `packages/providers` has token buckets, but those are
_outbound_ limits protecting a source from this service; four requirements here need an _inbound_
limit protecting this service and its sources from one user. They are different mechanisms and the
existing one cannot be pointed at the new problem.

Database-backed rather than in-memory, for R7's reason: there is no shared process, so an in-memory
counter would be per-invocation, would work on a VPS and would silently count nothing on Vercel.
Fixed-window rather than a sliding log, because the counters are read on every request on a free-tier
database and the precision a sliding window buys is worth nothing against limits chosen to stop
enumeration rather than to shape traffic.

### Alternatives considered

- **A hosted rate-limit service.** Rejected: a new external dependency, on a paid tier, for the
  lowest-priority stories in the product.
- **Rely on the outbound token bucket to absorb it.** Rejected: it would make one user's enumeration
  indistinguishable from capture's own traffic, at exactly the moment constitution I needs them
  separable.

---

## R11 — Search: the route, and what must be stripped from it

### Decision

`GET https://data.aoe2companion.com/api/profiles?search={name}`, through the existing
`CompanionEnrichmentProvider`'s circuit breaker and rate limiter, as a new `PlayerSearchProvider`
method. Results are cached. The account-linking fields are dropped at the provider boundary, before
any Pydantic model that could carry them exists. Nothing is dropped on privacy grounds beyond that:
T301a measured the source's `hidden` field and found it carries nothing, so FR-004c was retired.

### Rationale

The route and its properties are settled and measured — `docs/data-sources.md` §1 and §3, and the
spec's own clarifications — **with one exception, since corrected: the hidden-profile signal was
asserted here and measured nowhere.** T301a measured it on 2026-08-23, found the source's `hidden`
field carries nothing, and FR-004c was retired (`docs/data-sources.md` §3). This paragraph is what
let an unmeasured property into a Phase 0 that opens by claiming everything here is measured; the
correction is worth more than the deletion. What Phase 0 has to settle is where the obligations land
in code, and there is only one defensible answer for the one that remains.

**Superseded 2026-08-24 by constitution IX 3.0.0** as to `steamId`, which is now carried as
`unverified_steam_id`; the boundary reasoning below still governs `shared` and `sharedHistory`, and
the pattern it establishes is why the carried field is a typed attribute rather than a passthrough
dict. FR-004b (strip `steamId`, `shared`, `sharedHistory`) was enforced at the provider boundary because
that is the only place where "it never entered the system" is a property rather than a promise. A field stripped in a router is a field that existed in memory,
in a log line, and in a traceback. The existing provider already demonstrates the pattern: its module
docstring records that `linkedProfiles` "is not read anywhere below, deliberately", and there is
nowhere for it to leak to because the value object has no field for it. The search record gets the
same treatment.

FR-004e's cache and FR-004d's fallback both follow from §3's "unverified from Vercel's egress
addresses". The fallback needs no new source, because `aoe_profiles` already exists and is already
populated by 001's discovery with every participant of every match this service has seen — searching
it is a `LIKE` over rows this repository already holds, which is what makes FR-004d cost nothing and
introduce no dependency.

### Alternatives considered

- **`FindProfiles` on the primary source.** Unavailable, not merely difficult — it needs a game-client
  session this project has no lawful way to obtain (`docs/data-sources.md` §1).
- **`getLeaderBoard2&searchPlayer=`.** It is the documented trap: `200`, `"SUCCESS"`, and the top of
  the ladder regardless of the name.
- **Build a name index by walking the ladder.** Rejected in the spec: it needs a bulk read of the
  primary source and a refresh job, which is the cron this feature exists not to add, and it covers
  only ranked players.

---

## R12 — Two people asking at once is one piece of work

### Decision

One row per match, created by whoever asks first, claimed with `SELECT ... FOR UPDATE SKIP LOCKED`
and a lease. A second asker joins the existing row and is shown its progress. The uniqueness is a
primary key on `game_id`, not application logic.

### Rationale

FR-031 ("at most once") and FR-038 ("concurrent requests are one piece of work") are the same
constraint seen from two sides, and SC-006 makes it measurable: the number of fetches and parses per
match is exactly 1. A primary key is the only mechanism that holds under concurrency without anyone
having to remember it; an `if not exists` check followed by an insert is the classic way to fetch the
same recording twice under a double-click.

The claim mechanism is 001's, deliberately unchanged — `replay_captures` is already claimed this way,
it works identically on Neon and on self-hosted Postgres, and the queue stays inspectable.

### Alternatives considered

- **An advisory lock keyed on the game id.** Equivalent for exclusion, worse for inspection: a lock
  leaves no row to read when someone asks why a match is stuck.

---

## R13 — Technologies and units have no name table, and that is the correct default

### Decision

The analysis publishes technology and unit identifiers. Where a name exists it is shown; where none
does, the identifier is shown as-is, and nothing is guessed.

### Rationale

FR-043a already requires this, and 002 is why it is the default rather than a fallback. That feature
wrote the re-derivation procedure for civilisations only, structured so another identifier can be
added beside it, and it wrote down the reason a guess is worse than a number: a confident wrong name
carries no hint of doubt. 001's first civilisation table asserted thirteen names from an assumed
ordering and every one was wrong.

Technology 101/102/103 are the age-ups and are named here because the analysis is _about_ them. The
remaining identifiers ship as identifiers. Naming them is 002's procedure applied to a second
identifier, and it can happen later without any change to what is stored — which is the property
worth protecting, and the reason the published analysis stores identifiers rather than names.

### Alternatives considered

- **Vendor a technology and unit name table from a community repository.** Rejected on the licence
  grounds 002 established: `aoc-reference-data` carries no licence at all, so its data may be read
  and transcribed by a human, never copied into this tree, and never fetched at build or test time.

---

## R14 — Two requirements here depend on 001 work that is not finished

### Decision — settled 2026-08-23

**001's US5 lands before this feature retains its first third-party recording.** T090, T091 and T092
are a prerequisite of US4 here, and of nothing else: search, profiles, match pages, downloads and
favourites retain nothing and proceed in parallel.

FR-033 creates a new category of personal data, and constitution IX requires export and erasure from
the MVP. Retaining a third party's recording while no erasure route exists is not a sequencing
inconvenience, it is the principle being broken for the duration. FR-017 and FR-046's half is still
built here — every table in [data-model.md](./data-model.md) states what erasure must do to it — so
that the 001 tasks have something to implement against rather than something to remember.

### Rationale amended 2026-08-24, decision unchanged

Constitution IX 3.0.0 removed the deletion half of erasure and objection for retained recordings, so
the sentence above — "retaining a third party's recording while no erasure route exists is the
principle being broken for the duration" — no longer supports the gate on its own terms. **The gate
stands; its reason moved.** What T090 to T092 owe this feature is now: FR-017's export of favourites
and requested analyses (T090), and T092's **pseudonymisation instrument**, which the amended FR-046
promotes from half the remedy to the whole of it. Under 2.0.0 a person appearing in a recording had
two routes and one of them deleted the bytes; under 3.0.0 they have one, and if it does not exist the
obligation is discharged by nothing at all. Recorded rather than left to be re-derived, because a
gate whose written reason is false is a gate the next reader removes.

### Rationale

FR-017 points at 001 FR-036 and FR-037, and FR-046 at 001 FR-037 and FR-039. Those are the export
job, erasure, and the third-party objection endpoint: tasks T090, T091 and T092 in
`specs/001-steam-link-replay-ingestion/tasks.md`, all still open. `apps/api/src/aoe2stats_api/routers/privacy.py`
today implements the archival objection and nothing else. (**Corrected 2026-08-29**: this read "implements
consent", which was true when written and false since T405 renamed the route to
`POST /api/privacy/archival-objection` under constitution IX 4.0.0. The sequencing fact it supports is
unchanged — export, erasure and the third-party objection route are still T090 to T092, still open.)

This is a sequencing fact for `/speckit-tasks`, not a design problem: what this feature owes is that
its new tables are covered when those jobs are written, and the way to owe it without depending on it
is to state the coverage in [data-model.md](./data-model.md) — every new table names whether erasure
deletes it, pseudonymises it, or leaves it — so that the 001 tasks have something to implement
against rather than something to remember.

### Alternatives considered

- **Implement 001's US5 here.** Rejected: it is another feature's scope, and taking it would make
  this feature's own gate depend on work its spec never described.
