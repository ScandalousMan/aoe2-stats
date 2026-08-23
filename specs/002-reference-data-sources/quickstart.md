# Quickstart: Community Reference Data Sources

**Feature**: 002 | **Date**: 2026-08-23 | **Plan**: [plan.md](./plan.md)

Five scenarios. The first four are the check, and each is runnable against a throwaway database. The
fifth is the documentation, and it is walked by a person because that is the only honest way to test
whether writing works.

## Prerequisites

A local Postgres, as `tests/db.py` already provisions per session, and the workspace installed:

```bash
uv sync
```

Scenarios 1 to 4 run through the check's own test module. To drive them by hand instead, point
`DATABASE_URL` at a scratch database and seed it as the tests do.

---

## Scenario 1 — A civilisation the mapping cannot name is reported

Covers FR-013, SC-007.

1. Seed `match_players` rows carrying a `civ_id` outside the mapping — 61 is safe today, being past
   the highest named id.
2. Run the check.

**Expected**: exit status `1`. The output names identifier 61 and the number of rows carrying it.

**Also expected, and worth asserting rather than eyeballing**: the output contains no `profile_id`,
no alias and no `game_id`, per the contract. Assert their absence, because this is the requirement a
later well-meaning change is most likely to erode.

---

## Scenario 2 — A fully covered database is silent

Covers FR-013, SC-008.

1. Seed `match_players` rows whose `civ_id` values are all inside the mapping.
2. Run the check.

**Expected**: exit status `0`, and no identifier reported. A report that appears when nothing is
wrong is a report that stops being read, so silence here is the feature, not the absence of one.

---

## Scenario 3 — Examining nothing is a failure, and says which failure

Covers FR-015, and the distinction the contract requires.

1. Point the check at a database with no `match_players` rows at all.
2. Run the check.

**Expected**: exit status `1`, with a message saying plainly that nothing was examined — distinct
from the message scenario 1 produces.

This is the scenario most likely to be skipped as trivial, and it is the one that matters: a check
that reports success over an unexamined region is the failure this repository has already met at
T015a, T038b and T070h. Assert the two failure messages differ, not merely that both exit non-zero.

---

## Scenario 4 — An excluded identifier stays quiet, an unknown one does not

Covers FR-016.

1. Seed a row carrying an identifier recorded in the deliberate-exclusion collection.
2. Run the check. **Expected**: it is not reported.
3. Seed a row carrying id 56 — absent from every source, but _unknown_ rather than unnameable.
4. Run the check. **Expected**: it **is** reported.

Step 4 is the point of the scenario. The exclusion mechanism ships empty and must not quietly grow to
cover ids that are simply unnamed yet: an arriving civilisation 56 is precisely the evidence that it
exists, and silencing it would throw away the signal.

---

## Scenario 5 — A maintainer extends the mapping using only the documentation

Covers FR-001 to FR-012, SC-001, SC-002, SC-004, SC-005. Walked by a person, once, before the
feature is called done.

Give someone who did not work on feature 001 a civilisation identifier the mapping does not name, and
`docs/reference-data.md`. Without further help, they should be able to:

1. Decide which of the three sources answers the question, and why the other two do not.
2. See at a glance which sources may be copied into the repository and which may only be read, and
   the date each licence was checked.
3. Follow the procedure to a name.
4. Verify the result against captured responses rather than trusting it, and know that a
   verification recovering nothing is a failure.
5. State what happens if two sources disagree, without reopening the question.
6. Say why an identifier absent from every source is left on the fallback instead of inferred.

Then ask them the trap question, which is the one feature 001 got wrong twice: _a civilisation has
been renamed in-game — what changes?_ The documentation has done its job only if the answer is "the
displayed name, and no id and no sort position".

Record the outcome in the pull request. If the reader stalls at any step, that step is a defect in
the writing, not in the reader — this is the only test documentation has.
