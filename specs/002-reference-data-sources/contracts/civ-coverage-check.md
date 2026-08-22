# Contract: civilisation coverage check

**Feature**: 002 | **Date**: 2026-08-23 | **Implements**: FR-013, FR-014, FR-015, FR-016

`scripts/checks/civ_coverage.py`, run nightly. Reports every civilisation identifier present in
stored match data that the mapping cannot name.

## Invocation

```text
uv run scripts/checks/civ_coverage.py
```

No arguments. Configuration comes from the environment, as with the three sibling checks —
`DATABASE_URL` and nothing else new. Matching `cron_liveness.py`, the entry point returns an integer
status and the module raises `SystemExit(main())`.

## Exit status

The nightly workflow reads the exit status and nothing else; the text is for the human who opens the
issue.

| Status | Meaning                                                                    | When                                                         |
| ------ | -------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `0`    | Every identifier present in the data is named.                             | At least one row was examined and no gap was found.          |
| `1`    | At least one identifier cannot be named, **or** nothing could be examined. | A coverage gap exists, or the query returned no rows at all. |

The two `1` cases must be **distinguishable in the message**, never only in the status. "The mapping
does not name civilisation 61" and "no match data was examined" send a maintainer to entirely
different places, and collapsing them into one line is the same fault T061b corrected in
`cron_liveness.py`, where "the cron stopped firing" and "the cron fires and every run dies" had to
be told apart.

An empty examination is a failure and not a pass (FR-015). A database carrying no `match_players`
rows is already a red `cron_liveness` for a more urgent reason, so this does not introduce a new
false alarm; it refuses to report success over an unexamined region.

## Output

Written to standard output. Human-readable, in the shape the sibling checks already use.

Per reported identifier, exactly two facts:

- the civilisation identifier
- the number of `match_players` rows carrying it

### What the output must never contain

A hard requirement, not a style preference (constitution IX). The report ends up in a GitHub issue
that is public by default.

- No `profile_id`, no alias, no Steam identifier.
- No `game_id` or any other match identifier.
- No connection string, credential, or any part of one.

The diagnostic these would provide — who was affected, in which match — is genuinely tempting and
buys nothing: the remedy for every gap this check can report is to name the civilisation, which needs
the identifier alone. A future change that makes the report "more useful" by adding an example match
has to argue with this paragraph first.

## Deliberate exclusions

The module carries an explicit, reviewable collection of identifiers that are never to be reported,
each with its reason recorded inline. It ships **empty**.

An entry belongs there only when an identifier can never be named by any source — a modded value, a
test artefact. An identifier that is merely absent from the sources consulted so far does **not**
belong there: ids 56 and 57 are unknown rather than unnameable, and a match arriving with one is the
evidence that would make it nameable. Pre-silencing them would discard the signal this check exists
to produce.

## What the check must not do

- It must open no network connection and must never fetch a reference source (FR-014). The three
  repositories are consulted by a human.
- It must not write to the database, the object store, or any file.
- It must not import the replay engine, or anything that transitively loads it (constitution V).

## Verification

Covered by `scripts/checks/tests/test_civ_coverage.py`, inside the `python` job's path filter since
T061a. The tests must include the empty-data case explicitly: a check that cannot be shown to fail
when there is nothing to examine has not been shown to implement FR-015.
