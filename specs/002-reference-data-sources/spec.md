# Feature Specification: Community Reference Data Sources

**Feature Branch**: `002-reference-data-sources`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "Document that aoe2techtree, aoc-reference-data and aoe2-apis contain a
lot of reference data, it may be helpful in the future when new civilizations are added or if they
change (e.g. Indian treatment)."

## Context

Feature 001 needed a civilisation id-to-name mapping. The first attempt asserted thirteen names from
an assumed ordering and every one of them was wrong; the product labelled an Aztecs game "Britons".
The correction came from three community repositories and from this repository's own frozen
fixtures, and it took two further rounds to arrive at a table that is both right and checked.

None of that is written down. The next person to face the same problem — and the game guarantees
there will be one, because civilisations are added and renamed — starts from nothing, with the same
plausible-looking wrong answer available to them.

This feature writes down what those sources are, what each may legally be used for, and how the
mapping is re-derived and verified. It adds no runtime behaviour: nothing here is fetched by the
running system, now or ever (constitution III).

## User Scenarios & Testing _(mandatory)_

The actor throughout is a **maintainer** of this repository, not an end user. The value is that
knowledge which currently exists only in one conversation survives into the next one.

### User Story 1 - A new civilisation appears and shows as a number (Priority: P1)

An expansion adds civilisations. Players pick them, and the product shows "Civilisation 61" where a
name belongs, because the id is outside the table. The maintainer needs to know where to look, which
source may be copied and which may only be read, and how to prove the addition is right rather than
plausible.

**Why this priority**: it is the case that recurs on every expansion, it is user-visible, and it is
the one where a confident guess does real harm — a wrong name is worse than a bare id, because it
carries no hint of doubt. This story alone justifies the feature.

**Independent Test**: hand the documentation to someone who did not work on feature 001, give them a
civilisation id the table does not name, and confirm they can add it and demonstrate it is correct
without consulting the author.

**Acceptance Scenarios**:

1. **Given** an id the table does not name, **When** the maintainer follows the documented
   procedure, **Then** they reach a name and a verification step without asking anyone.
2. **Given** a source that carries no licence, **When** the maintainer wants its data, **Then** the
   documentation tells them plainly that it may be read and transcribed but not copied into the tree.
3. **Given** an id absent from every source, **When** the maintainer reaches it, **Then** the
   documented answer is to leave it on the fallback rather than to infer it from its neighbours.

---

### User Story 2 - A civilisation is renamed and nothing may be renumbered (Priority: P2)

The game renames a civilisation, as it did when Indians became Hindustanis. The displayed name
changes; the numeric id does not, and it keeps the position the _original_ spelling sorted into. A
maintainer who re-derives the ordering from current names alone silently shifts several ids and
mislabels every match played by the affected civilisations.

**Why this priority**: rarer than an addition, and far more dangerous, because it breaks entries that
were previously correct and it looks like a tidy-up. It is also the trap that is invisible without
having been told.

**Independent Test**: describe a hypothetical rename to a maintainer and confirm they change the
displayed label without changing any id or sort position.

**Acceptance Scenarios**:

1. **Given** a renamed civilisation, **When** the maintainer updates the mapping, **Then** the id
   and its derivation position are unchanged and only the displayed name moves.
2. **Given** the existing Hindustanis entry, **When** a maintainer reads the documentation, **Then**
   they understand why it sorts under a name the game no longer shows, and do not "fix" it.

---

### User Story 3 - Two sources disagree (Priority: P3)

A community source spells a civilisation differently from the game — the reference dataset writes
"Maya" where the game writes "Mayans". A maintainer must know which wins without relitigating it.

**Why this priority**: cosmetic rather than harmful, but unresolved it produces churn, and each
round of churn risks touching an id.

**Independent Test**: present a maintainer with a naming conflict and confirm they resolve it from
the documented precedence rule alone.

**Acceptance Scenarios**:

1. **Given** two sources disagreeing on a name, **When** the maintainer applies the documented
   precedence, **Then** the name the game itself displays wins.
2. **Given** a deliberate divergence already in the table, **When** a maintainer reads it, **Then**
   it is marked as checked rather than looking like an oversight.

---

### Edge Cases

- A source is deleted, archived, or stops being maintained. The documentation must still say what it
  held and what was taken from it, so a broken link does not erase the provenance.
- A source changes its licence, in either direction. What was permissible when the data was taken is
  a fact about a moment, so the check is recorded with its date rather than implied to be permanent.
- The captured fixtures stop overlapping, so the verification join recovers nothing. A verification
  that silently checks zero things must fail rather than pass.
- An id sits in a gap that no source names, as 56 and 57 do today. The documented answer is to leave
  the gap, not to interpolate across it.
- A source states a fact that contradicts this repository's own captured responses. Captured
  evidence from the live source wins over any third-party restatement of it.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Documentation MUST record, for each of the three reference sources, what it holds and
  what it is useful for, in enough detail that a maintainer can tell which one answers their question
  without opening all three.
- **FR-002**: Documentation MUST record each source's licence status and the consequence that
  follows from it — whether its data may be copied into this repository or only read and transcribed.
- **FR-003**: Documentation MUST record the date on which each licence status was checked, because a
  licence is a fact about a moment and this repository has already been bitten by a source that has
  none.
- **FR-004**: Documentation MUST record the procedure for extending the civilisation mapping when the
  game adds civilisations, including where the mapping lives.
- **FR-005**: Documentation MUST record that a rename does not renumber, and that a re-derivation
  driven by current names alone will shift ids that were previously correct.
- **FR-006**: Documentation MUST record how a derivation is verified against this repository's own
  captured responses rather than trusted, and MUST state that a verification recovering nothing is a
  failure and not a pass.
- **FR-007**: Documentation MUST record the precedence when sources disagree: the name the game
  itself displays wins over any community restatement.
- **FR-008**: Documentation MUST record what remains uncovered, so an absence reads as a decision
  rather than an oversight.
- **FR-009**: Documentation MUST NOT restate the civilisation mapping itself, or any other
  measurement that already lives elsewhere in the repository. It points at the single place each fact
  is recorded.
- **FR-010**: The judgment about when and how to consult these sources MUST live where an agent will
  load it on demand, and MUST point at the recorded facts rather than repeat them.
- **FR-011**: Nothing in this feature may cause the running system, its build, or its tests to fetch
  any of these sources. They are consulted by a human, on the occasions the game changes.
- **FR-012**: Documentation MUST record that these sources are reference material consulted by a
  maintainer, distinguishing them from the runtime data sources the product actually calls, so the
  two are not confused by a reader skimming for endpoints.

### Key Entities

- **Reference source**: a third-party repository consulted when the game changes. Attributes: what it
  holds, its licence and the date that was checked, whether its data may be vendored, and how far it
  can be trusted relative to captured evidence.
- **Derived mapping**: a correspondence between an external identifier and a human-readable name,
  living in exactly one place in this repository, carrying its own record of which entries rest on
  measurement and which on transcription.
- **Verification join**: the procedure that checks a derived mapping against captured responses
  already held in this repository, and that must fail loudly when it can check nothing.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A maintainer who did not work on feature 001 can name a newly added civilisation and
  demonstrate the addition is correct, using only the documentation, without consulting its author.
- **SC-002**: Every reference source named carries a recorded licence status, a check date, and an
  explicit ruling on whether its data may enter this repository — no source is listed without all
  three.
- **SC-003**: No measurement is recorded in two places: every fact the documentation mentions is
  either stated once there or pointed at where it lives, and this is verifiable by inspection.
- **SC-004**: A maintainer presented with a rename changes the displayed name and no id, on the first
  attempt.
- **SC-005**: A maintainer presented with two sources disagreeing on a name resolves it from the
  documentation alone, without reopening the question.
- **SC-006**: The repository's own checks continue to pass with no new network access introduced,
  demonstrating this feature added reference material and no runtime dependency.

## Assumptions

- The three sources remain publicly readable. If one disappears, the documentation still records what
  was taken from it and when, so the provenance survives the link.
- The maintainer has repository access and can run the existing test suite; the verification step is
  something they execute, not something they read about.
- Licence status is recorded as observed on the date of the check and is not assumed to be permanent
  in either direction. Nothing here is legal advice, and a source with no licence is treated as
  reserving its rights.
- The civilisation mapping is the worked example because it is the one this repository has already
  been burned by, but the procedure is written so it reads sensibly for the next identifier that
  needs the same treatment.
- Feature 001's civilisation table is correct as it stands. This feature records how it was obtained
  and how to extend it; it does not revisit its contents.
- Extending the mapping when the game next changes is out of scope. This feature makes that work
  possible and cheap, it does not perform it in advance for civilisations that do not yet exist.
