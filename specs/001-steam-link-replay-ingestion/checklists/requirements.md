# Specification Quality Checklist: Steam Account Linking and Automatic Replay Ingestion

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-19
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [ ] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Validation notes

**Two [NEEDS CLARIFICATION] markers remain, both scope-level and both deliberate.**

- **FR-006 — identity model.** Whether Steam sign-in is the sole credential or the user also holds an
  email-and-password account. This is not a detail: the second option adds password storage, reset
  flows, email verification and account-recovery paths to the scope, and the first removes them
  entirely. No reasonable default exists because it hinges on whether the user must remain reachable
  and keep their data if they lose access to Steam.
- **FR-007 — one profile or several.** A player can hold multiple AoE2 profiles under a single Steam
  account (observed in the source data as linked profiles). Supporting several changes the ratings
  view, the match history and the ingestion quota from single-profile to aggregated.

Both must be resolved by `/speckit-clarify` before `/speckit-plan`.

**"All functional requirements have clear acceptance criteria" is marked incomplete** for the same
reason and no other: FR-006 and FR-007 cannot have acceptance criteria until they are decided. Every
other functional requirement is covered by an acceptance scenario in User Stories 1 to 5.

### Deliberate departures worth recording

- The spec names the ~31-day retention window, the 21-day capture budget and `docs/data-sources.md`.
  These are measured properties of the problem domain, not implementation choices, and the whole
  feature is meaningless without them. They stay.
- "Steam" appears throughout. It is the product requirement, not a technical choice — the feature is
  literally about linking a Steam account. No protocol, endpoint or library is named anywhere.
- SC-001 is expressed as an absolute zero rather than a percentage. That is intentional and follows
  constitution principle I: a lost replay is unrecoverable, so any non-zero rate is a failure of the
  feature rather than an acceptable error budget.
