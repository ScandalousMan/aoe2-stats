<!--
Sync Impact Report — compact changelog. Full rationale for each entry is in git history.

5.0.0 (2026-08-30, MAJOR) — Principle X: retire the ban on copying game assets into the repo. Asset
packs needed to display game content MAY now be copied in and served, conditional on the two surviving
anchors (non-commercial + the README/footer disclaimer) plus a per-pack licence record (feature 002's
discipline). The ban was stricter than Microsoft's Game Content Usage Rules require for non-commercial
fan use and gave up no protection those anchors don't already provide, while leaving the product
poorer than every peer. Backward-incompatible: specs and the design-system "evoke without reusing"
approach were written against it. Modified: X.

4.1.0 (2026-08-28, MINOR) — Principle I: drop the hard-coded retention figure (a measurement lives
only in docs/data-sources.md; the 31-day reading was contradicted on 2026-08-28 by a boundary six
months back, unresolved). Add the budget ratchet: new evidence MAY tighten CAPTURE_BUDGET_DAYS at any
time, may only widen it once docs/data-sources.md records the question settled across >1 profile and
>1 date. Modified: I.

4.0.0 (2026-08-25, MAJOR) — Principle IX: retire the consent gate; ingestion and archival move to
legitimate interest (Art. 6-1-f) with a mandatory Art. 21 right to object, archival on by default. The
gate had forbidden what 003 FR-011 does by design and had stopped capture of the signed-in user's own
matches while recording strangers'. IV's erasure exception rewritten "consenting" → "linked" user.
Modified: IX, IV.

3.0.1 (2026-08-24, PATCH) — Principle IV: erasure exception rewritten against the legal basis, not the
file, so it no longer covers a recording IX retains. Found by /speckit-analyze (D1).

3.0.0 (2026-08-24, MAJOR) — Principle IX: a retained already-public recording is never deleted or
modified; erasure/objection reach the person↔recording link, not the artifact. Adds the public-field
rule, the no-hiding/no-circumvention rule, and the carriage-vs-action split for unverified claims.
Modified: IX.

Open follow-ups (dependent artifacts not yet in line):
- specs/001-steam-link-replay-ingestion/quickstart.md scenario 2 — still titled "Nothing happens
  without consent"; must invert to an objection that stops capture (4.0.0).
- specs/003-player-search-match-analysis/spec.md — several "consenting user" phrasings; the
  point-of-view limit survives, the word "consenting" does not (4.0.0).
- design-system guidance / spec text prescribing "evoke the visual language without reusing it" now
  describes a retired rule (5.0.0).
- Older follow-ups from the 3.0.x amendments: see git history; this compaction did not re-verify their
  status.
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

Strictly non-commercial — monetizing would breach both Microsoft's "Game Content Usage Rules" and
Vercel's Hobby terms, so it is the condition under which the rest is lawful. The Microsoft "Game
Content Usage Rules" disclaimer MUST appear in the README and the site footer. On those two anchors,
game assets needed to display game content (map, civilisation, unit, building and resource icons,
flags, player colours) MAY be copied into the repository and served, as non-Microsoft fan sites do;
remove either anchor and the permission lapses. Every pack copied in MUST record its source and
permitted usage (feature 002's discipline); a pack whose licence is not recorded MUST NOT be added.

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

**Version**: 5.0.0 | **Ratified**: 2026-08-19 | **Last Amended**: 2026-08-30
