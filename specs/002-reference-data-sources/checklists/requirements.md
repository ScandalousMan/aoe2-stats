# Specification Quality Checklist: Community Reference Data Sources

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

Two items were judged rather than waved through, and the reasoning is recorded so a reviewer can
disagree with it rather than have to reconstruct it.

**"Written for non-technical stakeholders."** The actor in every story is a maintainer of this
repository, so the reader is technical by definition — this feature has no end user and inventing
one would have made the spec dishonest. The item is read as "free of jargon that only the author of
feature 001 would understand", and against that reading it passes: the stories describe what goes
wrong for a player when the mapping is stale, and the requirements say what must be written down
rather than how.

**"No implementation details."** The requirements themselves name no file and no module: FR-004 and
FR-009 say the mapping lives in one place and is pointed at, FR-010 says the judgment lives where an
agent loads it on demand, and FR-013 to FR-016 describe what the check must notice rather than how it
is built. The three homes are named once, in the Clarifications section, because the user settled
that question on 2026-08-22 and a decision log records decisions — that is what the section is for.
Planning still owns how each file is structured; it no longer owns which file.

**On success criteria.** SC-001, SC-004 and SC-005 are stated as what a maintainer unfamiliar with
feature 001 can do unaided. That is a real test, and it is the only honest one for documentation:
whether it works is a fact about a reader, not about the text. SC-002, SC-003 and SC-006 are
inspectable directly.

**Scope note carried forward to planning.** The spec assumes feature 001's civilisation table is
correct and does not revisit it. If planning discovers otherwise, that is a defect in 001 and belongs
in 001's remediation, not here.

**Re-validated after clarification (2026-08-22).** All 16 items still pass; none regressed. The third
clarification widened the feature from documentation alone to documentation plus one check, so User
Story 4, FR-013 to FR-016, SC-007, SC-008 and two edge cases were added, and the Context paragraph
was corrected — it had claimed the feature adds no runtime behaviour, which the clarification made
false. That correction matters more than its size: a spec whose overview contradicts its own
requirements is the defect this project keeps finding, and it would have been introduced by the very
step meant to remove ambiguity.
