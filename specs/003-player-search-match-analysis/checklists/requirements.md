# Specification Quality Checklist: Player Search, Favourites and On-Demand Match Analysis

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-23
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

**Validation round 2 — 2026-08-23, after the clarification session.**

Two of the three markers are resolved and recorded in the spec's Clarifications section:

- **FR-043** — resolved. The analysis is a factual timeline only, with FR-043 now naming each
  element it must produce and forbidding ranking, grading or advice. FR-043a was added so that an
  unknown unit or technology degrades to an identifier rather than an invented name.
- **FR-033** — resolved, in the direction opposite to the spec's first draft. Analysed recordings are
  retained. This required amending constitution IX (1.1.0 → **2.0.0**, a principle redefinition) and
  created FR-045 to FR-048, SC-009a and a new key entity. The challenge section was rewritten: its
  first draft argued against retention, and leaving that argument standing next to the decision would
  have made the document contradict itself.

- **FR-004** — resolved. The originally proposed endpoint was probed and does not work:
  `/game/account/FindProfiles` answers `401` for every parameter shape while an invented `/game/`
  path answers `404`, so the route exists but is behind a game-client session. No public name search
  exists on the primary source at all; `getLeaderBoard2`'s `searchPlayer` is silently ignored.
  Search therefore rests on `data.aoe2companion.com`, measured viable, with FR-004d as a fallback
  that needs no external source. Both measurements are recorded in `docs/data-sources.md` §1 and §3
  rather than in this spec, per the repository's documentation rule.

  Probing that source produced a requirement that would not have been written otherwise: its search
  records carry `steamId`, `shared` and `sharedHistory` — the community account-linking claim that
  001's FR-045 forbids acting on. Consuming the response naively would have breached FR-045 silently.
  **FR-004b** now strips those fields at the provider boundary, and **FR-004c** honours the
  source's `hidden` flag. Both exist because the source was measured rather than assumed.

**All markers are now resolved.** One open risk is carried in Assumptions rather than as a marker:
whether the search source answers from the production platform's egress is unverified, and
`docs/data-sources.md` §3 records it as such. It is not a marker because it does not change what is
specified — FR-004d already defines the behaviour if the answer is no.

**Checked and deliberately kept as they are:**

- SC-009, SC-009a and SC-010 name "storage", "cap" and "cron entries". These are infrastructure
  nouns in a document that should avoid them, and they stay: the user's question was precisely
  whether this feature adds a cron and blob storage, and criteria that cannot be checked against
  those two things would not answer it. All three remain verifiable by inspection.
- No measured number — retention window, replay size, execution budget — is restated as a
  requirement. Each is referenced to `docs/`.
- FR-008 and FR-021 were checked for duplication against 001's FR-008/FR-010/FR-011: this feature
  generalises them rather than restating them, and says so.
