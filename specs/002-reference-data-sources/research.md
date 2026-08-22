# Research: Community Reference Data Sources

**Feature**: 002 | **Date**: 2026-08-23 | **Plan**: [plan.md](./plan.md)

Six decisions. The measured inventory of what each source holds is deliberately **not** repeated
here — it is the deliverable, and it lives in `docs/reference-data.md` once built. What appears below
is only the part of each fact that drives a decision, which is the one kind of repetition
`CLAUDE.md` permits: a constraint stated where it governs a choice.

---

## 1. Where the source facts live

**Decision**: a new `docs/reference-data.md`, with `docs/data-sources.md` linking to it.

**Rationale**: `data-sources.md` records the sources the providers call at runtime, each with
measured properties the nightly contract tests keep honest. These three are consulted by a human on
the occasions the game changes and are never called by anything. Filing them together would put
material that is never invoked in front of a reader skimming for endpoints, which is what FR-012
asks to prevent. `data-sources.md` is also already long, and the civilisation note added in feature
001 sits inside its Relic section, where a reader looking for reference material would not think to
look.

**Alternatives considered**: a new section inside `data-sources.md` — one fewer file and one place to
look, rejected because it mixes the two kinds; an ADR under `docs/adr/` — rejected on lifetime, since
an ADR is a decision frozen at its date and this content must stay true as licences and rosters
change, which is the `docs/` contract instead.

**Settled by**: the user, 2026-08-22, recorded in the spec's Clarifications.

---

## 2. Where the judgment lives

**Decision**: the `aoe2-data-sources` skill gains a short section on when to consult these sources
and what not to do, pointing at `docs/reference-data.md` for every specific.

**Rationale**: `CLAUDE.md`'s three-homes rule assigns judgment — the rules, the traps, what not to do
— to skills, kept short and loaded on demand, referencing `docs/` for every number. The traps here
are real and cost a full round of rework in feature 001: that a rename does not renumber, that a
confident wrong name is worse than a placeholder, and that a source with no licence may be read but
not copied. An agent about to extend the mapping needs those three sentences in context; it does not
need the inventory.

**Alternatives considered**: putting the traps in `docs/reference-data.md` alone — rejected because
an agent does not read `docs/` unprompted, and the failure mode this addresses is an agent
confidently inventing an ordering; duplicating the traps in both — rejected outright, that is the
documentation defect this project cares most about.

---

## 3. How the check reports

**Decision**: a nightly script in `scripts/checks/`, non-zero exit on finding an unnamed identifier,
wired into `.github/workflows/nightly.yml` **and into the `report` job's `needs:` list**.

**Rationale**: this project already has exactly one pull-based mechanism for turning a fact about
stored data into something a human sees, and FR-013 asks for that one rather than a new one.
`cron_liveness.py`, `capture_audit.py` and `alert_audit.py` are its members; a fourth is a job
definition and a `needs:` entry.

The `needs:` entry is not a detail. T061 recorded that a job absent from `report`'s `needs:` list
fails in silence, and T100 is still open with the same requirement attached. For this feature that
failure would be self-referential: a check built to stop a gap going unnoticed, itself going
unnoticed.

**Alternatives considered**: `raise_alert` into the `alerts` table — the runtime mechanism, carrying
`ingest_run_id` and audited by `alert_audit.py`. Rejected because this is not a runtime event: it
belongs to no run, so the column that gives an alert its context would be null, and T059c is a whole
task about how bad null `ingest_run_id` values are for the reader. Also rejected: a check inside the
ingestion cycle, which would put a naming concern on the capture path that constitution I keeps
clear.

---

## 4. What the check reads

**Decision**: `match_players.civ_id` from the live database, aggregated to distinct identifiers with
row counts.

**Rationale**: staleness is a property of the data arriving now. The frozen fixtures under
`packages/providers/fixtures/` are a snapshot of three matches from before this feature existed and
cannot contain a civilisation added next year — a check reading them would be permanently green and
permanently useless. `capture_audit.py` already reads the live database from the nightly job and is
the pattern to copy, including how it obtains its connection string.

**Alternatives considered**: reading the fixtures — rejected as above, though the fixtures remain the
right input for the _table's own_ correctness test, which is a different question already answered by
`apps/api/tests/test_civilizations.py`; scanning `matches.raw_payload` — rejected as redundant, since
`match_players` is the parsed projection of exactly that field and is indexed.

---

## 5. Marking an identifier deliberately unnameable

**Decision**: an explicit, reviewable collection in the check module, shipping **empty**, each future
entry carrying its reason inline.

**Rationale**: FR-016 exists so a value no source will ever name — a mod, a test artefact — cannot
become a standing alarm that trains its reader to ignore it. That is a real risk once the report is
an issue somebody has to triage.

The critical judgment is what does **not** go in it today. Ids 56 and 57 are absent from every source
consulted so far, which makes them _unknown_, not _unnameable_. If a match ever arrives carrying
civilisation 56, that arrival is the evidence that it exists and needs a name; pre-silencing it would
discard the only signal this feature was built to produce. The mechanism therefore exists and is
empty, with that reasoning written beside it, because the next reader's instinct will be to
"complete" it.

**Alternatives considered**: an environment variable — rejected, since a suppression is a decision
that belongs in review with its reason attached, not in a deploy configuration where it is invisible;
suppressing anything absent from the sources — rejected as the exact inversion of the feature's
purpose.

---

## 6. What an empty examination means

**Decision**: examining nothing is a failure, reported distinctly from "everything is named".

**Rationale**: FR-015. This repository has met the empty-pass failure at least three times — T015a's
tests that skipped rather than ran, T038b's baselines that photographed a closed menu, T070h's rule
test that covered a fifth of its table while reading as verified. Each reported success over an
unexamined region. A coverage check that passes because there was no data to check would be the same
error in the tool built to catch errors.

It adds no false-alarm mode: a production database with zero `match_players` rows already fails
`cron_liveness.py` for a louder and more urgent reason, so this check going red alongside it tells a
consistent story rather than a new one.

**Alternatives considered**: passing with a warning — rejected, it is forbidden by FR-015 and a
warning in a green run is a thing nobody reads; treating zero rows as unreachable and asserting it
cannot happen — rejected, an assertion about the world that the world can falsify.

---

## 7. What the check may print

**Decision**: distinct civilisation identifiers and a count of rows carrying each. Never a
`profile_id`, an alias, or a `game_id`.

**Rationale**: constitution IX, and it is a live constraint rather than a formality. The obvious
diagnostic — which players are affected, in which matches — would be genuinely useful to a
maintainer and would place personal data into a GitHub issue that is public by default. The
identifier and its frequency are sufficient for every action the report leads to: naming the
civilisation. This is recorded in the contract so that a later "make the report more useful" change
has to argue with something.

**Alternatives considered**: including one example `game_id` for reproduction — rejected, a match
identifier plus a public issue is a link to the players in it, and nothing in the remedy needs it.
