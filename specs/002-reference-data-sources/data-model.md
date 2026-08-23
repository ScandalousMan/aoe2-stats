# Data Model: Community Reference Data Sources

**Feature**: 002 | **Date**: 2026-08-23 | **Plan**: [plan.md](./plan.md)

## No schema change

This feature adds no table, alters no column, and ships no migration. It reads what feature 001
already stores and writes nothing back. `uv run alembic check` must report no drift after it lands;
if it reports any, something in this feature went wrong rather than something in the schema.

That is worth stating rather than leaving as an absence, because a `data-model.md` that exists but
describes nothing invites a reader to assume the file was simply not filled in.

## What the check reads

One aggregate over one table.

| Source          | Column   | Used for                                                                |
| --------------- | -------- | ----------------------------------------------------------------------- |
| `match_players` | `civ_id` | the identifier whose coverage is being checked                          |
| `match_players` | —        | a count of rows per distinct `civ_id`, to say how much data is affected |

Read as: the distinct set of `civ_id` values present, each with the number of rows carrying it,
restricted to non-null values. Nothing else is selected. In particular `profile_id`, `game_id` and
`match_players`'s remaining columns are deliberately **not** read — see the contract, where that
restriction is a requirement rather than an omission (constitution IX).

`civ_id` is nullable in the schema, and a null means the source did not report a civilisation for
that participant. A null is not an unnamed identifier and is not reported: there is nothing to name,
and nothing a maintainer could do about it.

## What the check compares against

The civilisation mapping in `apps/api/src/aoe2stats_api/civilizations.py`, read through its public
lookup rather than by reaching into its table, so that the check depends on the module's behaviour
and not on the shape of its literal. That module remains the single home of the mapping (FR-009);
this feature neither moves nor copies it.

## Entities

These are conceptual — they describe what the feature reasons about, and none of them is a database
table.

- **Reference source**: a third-party repository consulted when the game changes. Carries what it
  holds, its licence, the date that licence was checked, the ruling that follows (vendorable, or
  readable only), and its standing relative to captured evidence. Recorded in
  `docs/reference-data.md`; no code represents it.

- **Derived mapping**: the correspondence between a numeric civilisation identifier and a displayed
  name. Lives in exactly one module. Carries, per entry, whether it rests on measurement, on the
  ordering rule, or on transcription — a distinction feature 001 established at T070h after
  discovering that a table can be two-thirds unverified while reading as verified.

- **Coverage gap**: a civilisation identifier present in stored match data that the mapping cannot
  name. Produced by the check, not stored. Attributes: the identifier, and how many rows carry it.
  It is a statement about the data as it stands at the moment of the run, never a record that
  persists or that a person closes by hand — extend the mapping and the next run is silent.

- **Deliberate exclusion**: an identifier recorded as never nameable, so it stops being reported.
  Ships empty. Distinct from _unknown_: ids 56 and 57 are absent from every source consulted and are
  emphatically **not** excluded, because a match arriving with one is exactly the evidence that would
  make it nameable.

## State transitions

A coverage gap has no lifecycle. It is true or it is not, recomputed from scratch each run. This is
deliberate and is the difference between a check and a ticket queue: there is no acknowledged state
to drift out of date, and no way for a gap to be marked resolved while remaining real.
