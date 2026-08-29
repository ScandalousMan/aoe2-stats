<!--
Sync Impact Report — 2026-08-28

Version change: 4.0.0 -> 4.1.0

4.1.0 (MINOR: materially expanded guidance, no principle removed or redefined) — principle I stops
asserting a retention figure and gains a ratchet.

The trigger is a defect this constitution created for itself. Principle I carried "approximately 31
days (measured 2026-08-19)" as a statement of fact. `docs/data-sources.md` recorded on 2026-08-28
that a second, larger sample (78 captures, profile 2322168) puts an equally sharp boundary six
months back rather than 31 days, with the replay endpoint having moved between the two measurements
and the question unresolved. The constitution therefore asserted as settled something `docs/` marks
as contradicted — and `CLAUDE.md` names this exact failure mode: a measurement written in two homes
goes stale in one of them. The measured window is a property of the outside world, so it belongs in
`docs/data-sources.md` and only there; principle I now points at it instead of restating it.

What the amendment adds beyond the deletion, and why it is MINOR rather than PATCH: a new normative
rule that new retention evidence may tighten the capture budget at any time but may only widen it
once `docs/data-sources.md` records the question as settled with corroboration across more than one
profile and more than one date. The unresolved reading is longer than the old one, which makes the
comfortable inference — replays are safe for months, capture can relax — the one this principle must
forbid explicitly. It also names the budget's mechanism (`CAPTURE_BUDGET_DAYS`, configured) rather
than its value, so a re-measurement changes a setting and not this document.

Unchanged and deliberate: the ordering itself ("any trade-off ... resolves in favour of capture"),
the no-degradation rule, and the `expired_total` corollary. The 21-day budget is unchanged; it is
conservative under either reading.

Modified principles:
- I. Capture Outranks Analysis — retention figure removed in favour of a pointer to
  `docs/data-sources.md`; budget-ratchet rule added.

Added sections: none. Removed sections: none.

Formatting: rewrapped principle IV's recomputability sentence, which sat on one ~135-char line.

Follow-up TODOs — none deferred in this file. Two dependent artifacts named by the 4.0.0 report are
still not in line, and this amendment does not touch them either (scope: constitution only):
- `specs/001-steam-link-replay-ingestion/quickstart.md` scenario 2, still titled "Nothing happens
  without consent" and still instructing the reader to decline consent. Under 4.0.0 there is nothing
  to decline; the scenario inverts to an objection that stops capture.
- `specs/003-player-search-match-analysis/spec.md`, which quotes principle IX as "we capture only
  the consenting user's point of view" (~l.31) and reasons from "consenting users" at l.46, l.92 and
  l.108. The point-of-view limit it relies on survives 4.0.0; the word "consenting" does not.

Everything else on that list landed: 001 FR-034/FR-035, the register's activities 3 and 4 and its
balancing test, and `discover.py`'s gate — now `archival_objected_at`, excluded rather than
required. Neither remaining item is caused by this amendment, and both predate it.

Prior report — 2026-08-25

Version change: 3.0.1 -> 4.0.0

4.0.0 (MAJOR: principle redefinition, backward incompatible) — principle IX's consent gate is
retired. Opt-in consent (Art. 6-1-a) is replaced by legitimate interest (Art. 6-1-f) for both the
ingestion of public match and rating metadata and the archival of a linked user's own recorded
games. Archival is ON by default for a linked profile; a mandatory right to object (Art. 21)
replaces the gate, reversing the default rather than renaming it.

Two faults forced this. **The principle contradicted a rule the same constitution blesses**: IX
said "Nothing is ingested ... as a side effect of someone browsing" while 003's FR-011 states that
viewing a third party's history "is therefore an act that permanently records their matches" — with
no consent from that person at all. **And the implementation over-applied the gate**: DiscoverStage's
`_consenting_profile_ids()` is the only place that module decides whose profiles exist for a cycle,
so a non-consenting user got no match discovery and no rating refresh, not merely no replay capture.
001's FR-013 ("MUST discover the linked user's new matches automatically, without user action")
carries no consent condition, and FR-034/FR-035 gate consent on "replay ingestion" and "no further
replays of theirs are captured". The gate was never specified that broadly. The result was backwards:
this service permanently recorded a stranger's matches because somebody browsed, and refused to
record the signed-in user's own. Project owner's decision, 2026-08-25.

What survives the edit, deliberately and verbatim: everything 3.0.0 and 3.0.1 established about
retained recordings, the public-field treatment rule, the no-hiding / no-circumvention rule, and the
carriage-versus-action split for unverified source claims. The **point-of-view limit** survives and
is now this principle's real constraint: only the linked user's own recording is ever captured, never
another participant's (001 FR-016, 003 FR-012, both unchanged).

Modified principles:
- IX. GDPR by Design — consent retired in favour of legitimate interest plus a right to object.
- IV. Raw Is Sacred — its erasure exception was written against "the consenting user's own basis",
  a basis that no longer exists. Rewritten to "the linked user's own basis"; the distinction it
  draws against IX's public-recording basis is untouched.

Dependent artifacts still to be brought in line — NOT edited by this amendment:
- 001 spec FR-034, FR-035 and acceptance scenario 7 ("a user who has not consented ... nothing of
  theirs is downloaded or stored"), plus the Assumptions and Edge cases wording on withdrawal
- 003 spec's several "consenting user" phrasings
- docs/privacy/processing-register.md activities 3 and 4, and its balancing test — activity 3 moves
  from Art. 6-1-a to Art. 6-1-f with the objection route named; activity 4's necessity argument rests
  on "capture is limited to matches the consenting user played in", which becomes "the linked user"
- apps/ingester/src/aoe2stats_ingester/discover.py's `_consenting_profile_ids` gate, the code that
  still enforces the retired rule

Prior report — 2026-08-24

Version change: 2.0.0 -> 3.0.0 -> 3.0.1

3.0.0 (MAJOR: principle redefinition, backward incompatible) — principle IX, below.
3.0.1 (PATCH: clarification, no behaviour change) — principle IV's deletion exception was written
against the file ("the original replay zip ... except on a GDPR erasure request") and so covered a
retained recording too, permitting exactly what 3.0.0's IX forbids. The constitution contradicted
itself for the duration. The exception is now written against the *basis*: a capture held under the
consenting user's own basis is deleted on erasure; a recording retained under IX's public-recording
basis is not. Found by /speckit-analyze, 2026-08-24 (finding D1).

Modified principles:
- IX. GDPR by Design — retention of an already-public recording no longer carries a deletion
  obligation. Erasure and the third-party objection route now reach the identifiers this service
  holds about a person appearing in a recording, and leave the recording itself intact. Adds the
  public-field treatment rule, the no-hiding / no-circumvention rule, and the carriage-versus-action
  split for unverified source claims.

Unchanged: principle IV. The amendment satisfies IV rather than overriding it — the recording
survives, so every published analysis stays recomputable. IV's own erasure exception still governs
001's consented captures.

Added sections: none. Removed sections: none.

Formatting: restored the missing blank line before "All compute and storage regions are EU.", which
had been glued to the preceding paragraph.

Follow-up TODOs — none deferred in this file. Dependent artifacts still to be brought in line, each
already recorded in specs/003-player-search-match-analysis/spec.md session 2026-08-24:
- 001 FR-045 carve-out (carriage is not action)
- 003 FR-004b, FR-033, FR-046 (written, struck-pending; the struck text comes out now)
- docs/privacy/processing-register.md balancing test and retention activity
- docs/data-sources.md §3 "Trap" note on steamId
- specs/003 quickstart scenario 2, which inverts
- the provider-boundary strip and the tests asserting steamId absence
-->

# aoe2-stats Constitution

## Core Principles

### I. Capture Outranks Analysis (NON-NEGOTIABLE)

The source destroys recordings on a schedule this project neither controls nor reliably predicts. An
uncaptured replay is gone forever. Any trade-off between shipping an analysis feature and hardening
capture resolves in favour of capture. No PR may degrade the ingestion pipeline to serve a display
feature. Corollary: `expired_total` must stay at zero; any non-zero value is a severity-1 incident.

**This principle states no retention figure.** The measured window is a property of the outside
world and lives in `docs/data-sources.md` alone. A number written down twice goes stale in one of
the two copies, and that is not hypothetical here: the 31-day reading this principle carried from
2026-08-19 was contradicted on 2026-08-28 by an equally sharp boundary sitting six months back,
measured after the replay endpoint had moved. The contradiction is unresolved, and this document
does not get to decide it.

**Capture runs against a budget strictly shorter than the shortest credible window**, configured
(`CAPTURE_BUDGET_DAYS`) and never hard-coded, so a re-measurement changes a setting, not code.

**A longer or unresolved reading never widens that budget.** New evidence MAY tighten it at any
time. Widening it requires `docs/data-sources.md` to record the question as settled, corroborated
across more than one profile and more than one date. Until then the ambiguity argues for capturing
sooner, not later: an unexplained boundary may be a fixed epoch rather than a rolling window, and an
epoch can be emptied wholesale with no notice. A PR that relaxes capture on the strength of an
uncorroborated measurement is rejected.

### II. Python Backend

FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, uv. Parsing and data analysis are Python. The front
end holds no business logic; it consumes the API.

### III. All External Data Goes Through a DataProvider

`apps/*` and `packages/core` never open an outbound connection. Every external source is a provider
in `packages/providers` with: explicit timeout, retry/backoff, rate limiting, a `provider_calls`
record of every call, and real fixtures for tests. Unit tests never touch the network; only nightly
contract tests do.

Verbatim persistence of the raw response is owed to every source of **irrecoverable data** — data
whose value cannot be obtained again once that source's window closes. A source that can be
re-queried at any time is exempt: a second copy of something still available is a second thing to
keep honest, for no gain. An authentication exchange is not a data source; what it proves is
recorded, its wire form is not. Which sources are irrecoverable is a measured fact and lives in
`docs/data-sources.md`. When it is unclear, the source is irrecoverable — principle I decides ties.

### IV. Raw Is Sacred, Derived Is Disposable

The original replay zip and its HTTP response are stored byte-for-byte with a checksum, never
modified, and never deleted. One exception, and one only: a replay captured under the linked
user's own basis is deleted on that user's GDPR erasure request. A recording retained under
principle IX's public-recording basis is not — IX carries that rule and this principle does not
override it. The two are different objects with different legal bases even when they are the same
match, so the exception is written against the basis and not against the file.

Every derived artifact records the version of the tool that produced it and must be fully
recomputable from the raw. No migration may ever be required to re-parse history.

### V. Parsing Runs in an Isolated, Pluggable Engine

The parser runs with its own pinned dependencies and no direct write access to application tables
outside its own. An unparsable replay goes to quarantine with the full error, never a silent
failure. A parser crash affects neither the API nor the ingester.
`aoe2rec-py` is primary, `aoc-mgz` secondary, both behind one interface. Being able to swap parsers
is a requirement, not an accident: the primary parser has changed once already.

### VI. Tokens First

No hard-coded colour, spacing, radius, typography or elevation value in a component. Everything
comes from `packages/design-system/tokens`. A component without a Storybook story does not exist.

### VII. Visual Tests Are Mandatory

Every UI component created or modified passes visual-reviewer locally, then Playwright visual
regression on its stories. CI is a court, not a factory: it tests only the stories the diff affects;
full coverage runs nightly.

### VIII. No Secrets in the Clear

Nothing sensitive in the repository, ever. Environment variables, `.env.example` without values,
GitHub Actions secrets and Vercel project environment variables only. No secret in logs, no key in a
URL. Cron endpoints are authenticated by a secret and are never publicly invocable.

### IX. GDPR by Design

**Amended 2026-08-25 — ingestion rests on legitimate interest, not consent.** Every field the AoE2
DE APIs serve is public (the public-field rule below), and the recorded game of a public match is
public at its source on the same footing. This service therefore ingests a linked profile's public
match and rating metadata, and archives that user's own recorded games, under GDPR Art. 6-1-f.
Archival is **on by default** for a linked profile. No opt-in is required, and none may be
reintroduced as a precondition for ingestion: a linked profile whose user has not answered any
question is ingested in full. The previous rule — automatic capture limited to the _consenting_
user, nothing ingested as a side effect of browsing — is retired, having forbidden in one sentence
what 003's FR-011 does by design and having stopped this service from recording the signed-in user's
own public matches while it permanently recorded strangers'.

**A right to object replaces consent, and is mandatory.** Art. 21 attaches to legitimate interest,
so a linked user MUST be able to switch archival off, that objection MUST stop all further capture
of their recordings, and it MUST be recorded with its timestamp and honoured for as long as it
stands. This is an opt-out that reverses the previous default; it is not the retired gate under a
new name, and an implementation that declines to ingest until the user has decided has reinstated
the gate.

**The point-of-view limit survives and is now this principle's real constraint.** Only the linked
user's own point of view is ever captured automatically, never another participant's. No third
party's recorded game is captured as a consequence of that player being searched, viewed, favourited
or analysed, and nothing is captured speculatively. Recording a third party's public _match
metadata_ because somebody browsed is permitted and always was (003 FR-011); capturing their
_recording_ is not (001 FR-016, 003 FR-012). Ingestion on this basis MUST be recorded in the
processing register with its balancing test.

A recording that is **already public at its source** may additionally be retained when a user
deliberately asks for that match to be analysed. The reason is principle IV, not convenience: the
resulting analysis is shown to everyone who opens that match, and a derived artifact that cannot be
recomputed from its raw is one this project may not publish. The source purges the recording after
about 31 days, so declining to keep it means publishing a conclusion that can never again be
checked or corrected. Retention on this basis is bounded by explicit human requests and never by
traffic; it MUST be rate-limited and capped, and MUST be recorded in the processing register with
its own legal basis.

**Amended 2026-08-24 — a retained recording is never deleted and never modified.** Erasure and the
third-party objection route reach the _link_ between a recording and a person — who requested the
analysis, and the identifiers this service holds — never the artifact. A recorded game is the record
of a public match. The precedent is one level up in this same codebase: erasure pseudonymises the
departing `profile_id` in `matches` and `match_players` in place rather than deleting the match. The
one difference is stated rather than engineered around — a `.aoe2record` cannot be pseudonymised
without being modified, and modifying it destroys both its checksum and the recomputability
principle IV requires, so it is kept whole and untouched. This orders principle IV above the
deletion half of this principle, deliberately. The processing register MUST carry that ordering in
its balancing test rather than leave it implied, and MUST state it as the product decision it is
rather than as a claim that the data is anonymous — the pseudonym is re-identifiable, and
`docs/data-sources.md` §3 measured the public search projection serving `steamId` beside
`profileId`.

**This project treats every field the AoE2 DE APIs serve as public and keeps it so.** This service
offers players no way to hide their matches within it. Where the source itself withholds data — a
player who has switched off the source's own "Shared History" setting — **nothing is done to obtain
it by another route**. The preference is neither honoured as a signal nor circumvented.

A field the source serves MAY be carried and shown as the source reports it, marked as a claim this
project has **not** verified. It MUST NOT be used to infer, suggest or act upon a relationship
between profiles that the user has not proven by signing in: no linking, no merging, no feature
treating two profiles as one person on that basis. A verified Steam sign-in is the only account link
this project vouches for, and presenting an unchecked third-party assertion beside it without the
distinction is an accuracy fault regardless of how the data is classified.

Third-party players are processed only on the basis of already-public data and are never publicly
indexed. Replay ingestion carries no consent step; the objection route above is what gives a linked
user control over their own recordings. Full export and erasure are available from the MVP, storage
objects included — with the single exception the 2026-08-24 amendment creates, stated above and
nowhere else. Any new personal data is added to the processing register in the same PR, and any
change of legal basis is recorded there with its balancing test.

**All compute and storage regions are EU.** Vercel functions run in `cdg1`, the database in an EU
region, the object store under EU jurisdiction. A PR that moves a region outside the EU is rejected.

### X. Intellectual Property

Strictly non-commercial. No game asset (icons, civilisation portraits, fonts, sounds, screenshots)
is copied into the repository: the design system evokes the visual language without reusing it. The
Microsoft "Game Content Usage Rules" disclaimer appears in the README and in the site footer.
The hosting plan carries the same constraint: monetizing this project would breach both Microsoft's
rules and Vercel's Hobby terms simultaneously.

### XI. Documentation Is in English

Repository, specs, ADRs, agent and skill definitions, code comments and commit messages are English.

### XII. Portable by Construction

The application must run unchanged on the phase-1 serverless stack and on a phase-2 VPS. Concretely:
all configuration comes from environment variables; no local filesystem state; object storage is
reached only through the S3 API behind `packages/storage`; the database is reached only through
`DATABASE_URL`; and the ingester is a library exposing `run_once(budget_seconds)` with a thin cron
handler and a thin worker loop as its only two entrypoints. Any code that can only run on Vercel, or
only on a VPS, is rejected.

## Technology Constraints

- Backend: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, uv workspace.
- Front end: Vite + React 19 + TypeScript + TanStack Router/Query + Tailwind, Storybook, Playwright.
- Parsing: `aoe2rec-py` (primary), `aoc-mgz` (secondary).
- Phase 1 hosting: Vercel Hobby (region `cdg1`) + Neon (EU) + Cloudflare R2 (EU jurisdiction).
- Phase 2 hosting: OVH VPS + Docker Compose + OVH Object Storage.
- Data sources: Relic `aoe-api.worldsedgelink.com` (primary), `aoe.ms` (replays), aoe2companion
  (enrichment only, degradable), aoestats (V2 historical corpus only).

## Development Workflow

Spec-Driven Development with Spec-Kit: `speckit-specify` -> `speckit-clarify` -> `speckit-plan` ->
`speckit-tasks` -> `speckit-analyze` -> `speckit-implement`. One task in `tasks.md` is one unit of
work for the `implementer` agent. The `reviewer` agent runs before every merge and rejects any
non-compliant change regardless of technical quality.

## Governance

This constitution outranks every other convention in the repository. Amendments go through a
dedicated PR carrying their rationale, and bump the version below using semantic versioning:
MAJOR for removing or redefining a principle, MINOR for adding one or materially expanding guidance,
PATCH for clarifications that change no behaviour.

**Version**: 4.1.0 | **Ratified**: 2026-08-19 | **Last Amended**: 2026-08-28
