# Specification Quality Checklist: Steam Account Linking and Automatic Replay Ingestion

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-19
**Last validated**: 2026-08-19, after the clarification session
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

## Validation notes

Both open questions were resolved in the clarification session of 2026-08-19 and are recorded in the
spec's Clarifications section.

- **FR-006 — identity model.** Steam sign-in is the sole credential. No stored passwords, no reset
  flow, no email verification, no account recovery. This removes an entire class of attack surface,
  and the trade is honest: a user's AoE2 identity is their Steam account, so a local account would
  outlive the thing it identifies. FR-006 now requires that the absence of recovery be stated to the
  user *before* they consent to archival.
- **FR-007 — one profile or several.** All discovered profiles are ingested; one is presented. Driven
  by constitution principle I rather than by convenience: a second profile's replays face the same
  ~31-day window, so declining to capture them destroys them, while declining to display them costs
  nothing that cannot be recovered later. Added FR-042 (ingest all), FR-043 (designate and present a
  primary, without hiding the others) and FR-044 (quota per user, not per profile).

### Deliberate departures worth recording

- The spec names the ~31-day retention window, the 21-day capture budget and `docs/data-sources.md`.
  These are measured properties of the problem domain, not implementation choices, and the feature is
  meaningless without them. They stay.
- "Steam" appears throughout. It is the product requirement, not a technical choice — the feature is
  literally about linking a Steam account. No protocol, endpoint or library is named anywhere.
- SC-001 is expressed as an absolute zero rather than a percentage. Intentional, and follows
  constitution principle I: a lost replay is unrecoverable, so any non-zero rate is a failure of the
  feature rather than an acceptable error budget.

**Ready for `/speckit-plan`.**
