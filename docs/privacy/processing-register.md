# Processing register

Constitution principle IX requires that any PR introducing a new category of personal data updates
this file in the same change. A PR that adds personal data without a row here is rejected.

Controller: the project owner. Contact and DPO details go here before the first real user is
onboarded.

This register is wrong in **both** directions, and both matter: a category collected without a row
here is a breach, and a row for a category that is not collected misdescribes the processing to
whoever reads it, with no way for them to tell. So a row is removed as carefully as it is added.

A verified Steam sign-in is the sole credential. There is no password and no email address anywhere
in the system, which is why neither appears in the table below.

## Processing activities

| #   | Purpose                                                                        | Data subjects                                                                                                                                      | Categories of data                                                                                                                                                                                                                | Legal basis                                                                                                                                                                     | Source                                                        | Retention                                                                                                                                                          | Recipients |
| --- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| 1   | Account and authentication                                                     | registered users                                                                                                                                   | steamid64 (extracted from the Steam OpenID claimed identifier, which is verified but never itself stored — constitution III), Relic profile_id, opaque session identifier, sign-in timestamps, beta allowlist admission timestamp | contract performance (Art. 6-1-b)                                                                                                                                               | the user, via Steam OpenID                                    | until account deletion                                                                                                                                             | none       |
| 2   | Displaying stats and match history                                             | registered users                                                                                                                                   | Relic profile_id, alias, country, per-leaderboard rating / rank / wins / losses / streak / highest rating, daily rating-history snapshots enabling a rating curve (FR-009), match metadata                                        | contract performance (Art. 6-1-b)                                                                                                                                               | Relic API                                                     | until account deletion (rating snapshots are append-only history, never overwritten, until then)                                                                   | none       |
| 3   | Replay archival                                                                | registered users                                                                                                                                   | the `.aoe2record` recording of their own matches, containing their actions, alias and in-game chat; the timestamp an objection to archival was made, if one was                                                       | legitimate interest (Art. 6-1-f) — see the balancing test below. Changed from explicit consent (Art. 6-1-a) by constitution IX 4.0.0, 2026-08-25                                                                                                       | aoe.ms; the user, for the objection timestamp                   | indefinite, until erasure is requested                                                                                                                             | none       |
| 4   | Third-party players appearing in a user's matches                              | other AoE2 players                                                                                                                                 | Relic profile_id, public alias, country, civilisation, team and colour choice, match result, rating and rating change; and, inside archived replays, their in-game actions and chat                                               | legitimate interest (Art. 6-1-f) — the data is already public through the official leaderboards and stats page, and capture is limited to matches the linked user played in | Relic API, aoe.ms                                             | same as the replay it belongs to                                                                                                                                   | none       |
| 5   | Logging access to archived replay files (FR-040)                               | registered users (the archive's owner; a replay is only ever opened by the user who owns the capture, per the download endpoint's ownership check) | which archived replay was accessed, by whom, when, and for what purpose (currently: download)                                                                                                                                     | legitimate interest (Art. 6-1-f) — see the balancing test below                                                                                                                 | generated by the system itself, at request time               | same as the replay it describes; deleted with the capture, including on erasure                                                                                    | none       |
| 6   | Handling data-subject rights requests (export, erasure, third-party objection) | registered users, and non-user third parties who submit an objection                                                                               | request kind, the account or profile the request concerns, when it was requested, when and how it was resolved                                                                                                                    | legal obligation (Art. 6-1-c) — GDPR Articles 15-21                                                                                                                             | the requester, via the export / erasure / objection endpoints | indefinite — the row is the accountability record for the request and survives an erasure it may document; only `subject_user_id` is cleared, not the row (SC-008) | none       |
| 7   | Player-name search, including a player who appears in nobody's match          | any AoE2 player whose name is searched — not only the opponents and teammates a linked user has played, which is the class activity 4's necessity argument is built around and does not cover here | Relic profile_id, alias, country, clan, games played — and the source's `steamId` claim as a sixth field. Constitution IX 3.0.0 (2026-08-24) retired FR-004b's strip and 003's T396 to T399 landed it: **this activity processes the field today** — the row described a decided change until then and describes a running one now. It is named `unverified_steam_id`, is shown to the user as an assertion this service has **not** verified, and is never used to link or merge profiles (001 FR-045). The identifier itself is rendered beside that label, so a viewer can read the claimed value and not only that a claim exists. `shared`, `sharedHistory` and `hidden` are not carried, for the reasons `specs/003-player-search-match-analysis/contracts/providers.md` gives; the normalised query text itself, which is `profile_search_cache`'s primary key and is typically a searched player's name; the degraded fallback (FR-004d) returns the same shape read from `aoe_profiles`, already covered by activity 4 and adds no category of its own | legitimate interest (Art. 6-1-f) — see the balancing test below                                                                                                                 | `data.aoe2companion.com`'s public search endpoint (`GET /api/profiles?search=`, `docs/data-sources.md` §3); the degraded fallback is a read of `aoe_profiles`, sourced under activity 4 | `profile_search_cache`: a row is *served* only while younger than `PLAYER_SEARCH_CACHE_TTL_SECONDS` (`.env.example`); it is *physically deleted* opportunistically on the next successful cache write — any query's, not necessarily its own — never on a schedule (FR-044); see `data-model.md`'s `profile_search_cache` section for the mechanism. The TTL bounds what is served, not what is stored: a row can outlive it if no later search succeeds. Degraded answers (FR-004d) are cached too, under a separate short TTL fixed in code (`_FALLBACK_CACHE_TTL_SECONDS`) rather than the configured one, so writes — and therefore pruning — continue while the source is down | none       |

## Balancing test for activity 3

Added 2026-08-25, when constitution IX 4.0.0 moved this activity from explicit consent (Art. 6-1-a)
to legitimate interest (Art. 6-1-f). A basis under Art. 6-1-f requires this test; the previous basis
did not, which is why the section did not exist before.

- **Interest pursued**: archiving a player's own recorded games before the publisher deletes them.
  The source purges a recording after about 31 days, so the interest is time-limited and the loss it
  prevents is permanent.
- **Necessity**: the recording cannot be obtained again once the window closes, and no less intrusive
  means exists — there is no partial or summarised form the source offers instead. Only the linked
  user's own point of view is fetched, which is the smallest unit the source serves.
- **Impact on the data subject**: low, and lower than under the retired basis in one respect worth
  stating plainly: the subject here is the linked user themselves, who obtained an account precisely
  to have this done. The recording is their own game, already published by the game publisher for
  about 31 days, and this service neither indexes it publicly nor serves it to anyone but a
  participant. In-game chat is the most sensitive element and is never displayed or indexed publicly.
- **Why consent was the wrong basis**: it was not freely given in any meaningful sense — a user links
  a profile *in order to* have their replays archived, so the "choice" was a formality attached to
  the one action the product exists for. Worse, the gate as implemented withheld the public match and
  rating metadata too, so declining a question about *recordings* silently disabled the rest of the
  service. Art. 6-1-f with a real objection route gives the user the same control without pretending
  the decision was optional.
- **Safeguards**: archival is limited to the linked user's own point of view, never another
  participant's (001 FR-016, constitution IX); a standing objection (Art. 21) stops all further
  capture and is recorded with its timestamp; export and erasure reach the stored objects
  (001 FR-036, FR-037); access to stored replays is logged. An objection stops capture only — public
  match and rating metadata continues under activities 1 and 4, which do not depend on this basis.
- **Outcome**: the interest is not overridden. The data subject is the account holder, the data is
  their own already-public game, the retention prevents an irreversible loss, and the objection route
  gives them a one-action way out that the retired consent gate did not improve upon.

## Balancing test for activity 4

- **Interest pursued**: letting a player analyse their own matches, which inherently involve
  opponents and teammates.
- **Necessity**: a replay cannot be split per player. Analysing one's own game requires the file
  that contains everyone in it. No less intrusive means exists.
- **Impact on the data subject**: low. The identifiers and results are already published by the game
  publisher on a public leaderboard and stats site. In-game chat is the most sensitive element and is
  never displayed or indexed publicly.
- **Safeguards**: only the linked user's point of view is captured, never the opponents' own
  replay files; no public indexing of third-party profiles; no cross-user aggregation of a
  third-party's behaviour beyond what the official leaderboards already show; an objection form
  pseudonymises a third party's `profile_id` on request without breaking match integrity; access to
  stored replays is logged. `GET /api/players/{profile_id}` (FR-008a, superseding 001's rule that a
  caller must have played against the profile) widened *who inside the service* may view this row to
  any signed-in, allowlisted user, without widening what is collected or from where; the impact
  finding above does not depend on which signed-in user is looking, because the source is already
  public. A `profile_id` this service has never itself observed still answers `404` — that boundary
  is what keeps this widening inside activity 4 rather than reaching the wider class activity 7
  covers.

## Balancing test for activity 5

- **Interest pursued**: being able to demonstrate, to the third parties whose gameplay and chat an
  archived replay contains, that access to it is limited to the match's own participant and is
  auditable — the same accountability the balancing test above leans on as a safeguard for
  activity 4.
- **Necessity**: an access trail cannot be reconstructed after the fact from any other table; it has
  to be written at request time or it does not exist.
- **Impact on the data subject**: low. The subject of this log entry is the registered user
  accessing their own file; the entry records that they looked at something they are already
  entitled to see, not new information about them.
- **Safeguards**: written only by the download endpoint itself, never editable by the user; erased
  together with the capture it describes, including on erasure of the account that owns it.

## Balancing test for activity 7

- **Interest pursued**: letting a user find a player by name without already knowing a numeric
  profile id (FR-001), and see enough alongside each result to tell same-named players apart
  (FR-002).
- **Necessity**: matching by name needs a source indexed on name; nothing this service holds is
  indexed that way for a player it has not itself seen in a match, which is why FR-004 accepts an
  external source for this at all rather than serving it from data already captured under activity 4.
  `GET /api/players/{profile_id}` is not part of this necessity and not part of this activity: see the
  boundary noted in activity 4's own Safeguards, above.
- **Impact on the data subject**: higher than activity 4's, and stating the difference plainly is the
  point of this being a separate row rather than an amendment to that one. Activity 4's low-impact
  finding rests on "capture is limited to matches the linked user played in" — a constraint this
  activity does not have: a subject here may never have played against the searching user, or against
  anyone this service has ever recorded, and is processed anyway, the moment their name is typed. What
  keeps the impact bounded rather than open-ended is the narrowness of the categories (alias, country,
  clan, games played — no chat, no in-match actions, nothing FR-004b strips) and that the same data is
  already returned by the source's own public search endpoint to anyone who queries it directly; this
  activity does not disclose anything the source was not already disclosing.
- **Safeguards**: FR-004b strips every account-linking field the source returns before anything
  reaches storage or the response; no public indexing of a search result or a profile page (FR-010); a
  per-user rate limit (FR-005, bucket `search`) so this service cannot be used to enumerate the source
  at volume; `profile_search_cache` rows are keyed only by the normalised query text, never by the user
  who searched, so this table cannot answer "who searched for this player" any more than it answers
  "who is this player" beyond what the source's own public endpoint already would; what a query is
  served is TTL-bounded, and the table is self-pruning on a later write, per the retention column
  above — the two are not the same guarantee, and the paragraph below states the difference.

**What erasure and objection can reach here, stated plainly rather than left implied.** No row in
`profile_search_cache` is keyed to a user, so a *searching* user's own export or erasure never touches
it (`data-model.md`'s `profile_search_cache` section). For the *subject* of a cached row — the player
who was searched — neither the export/erasure endpoints (activity 6) nor 001's third-party objection
route reach it either: FR-039 scopes that route to "a non-user appearing in archived matches," and a
cached search result does not describe an archived match. Nothing in this system removes a subject's
row on request, and nothing removes it on a schedule either: the TTL only stops a stale row from being
*served*, per the retention column above; the row is *deleted* only opportunistically, on a later
successful cache write, which is not guaranteed to happen at all. That is a genuine limit on this
activity's rights coverage, not a gap this paragraph is smoothing over: a subject who notices
themselves cached has no way to ask for it to be removed sooner, and — absent some later search
succeeding — no guarantee it is ever removed at all.

**Amended 2026-08-24, constitution IX 3.0.0.** This activity now carries an account-link claim it
previously stripped, so the impact finding changes with it and is stated here rather than inherited
from the version above. This service republishes an identifier the source already serves publicly
beside the same profile: it adds no capability that did not exist, it is shown as unverified, and no
route, query or feature acts on it. It is recorded as the product decision it is, and **not** as a
claim that the identifier is not personal data — `docs/data-sources.md` §3 measured the public search
projection serving `steamId` beside `profileId`, which is exactly what makes the pseudonym
re-identifiable. The same amendment removes the deletion half of erasure and objection for recordings
retained under IX's public-recording basis; that ordering of principle IV above deletion belongs to
the retention activity, which does not exist in this register yet and is created by
`specs/003-player-search-match-analysis` T369 in the same change that implements the retention.

## Technical and organisational measures

- All compute and storage regions are in the EU (constitution principle IX).
- Encryption in transit and at rest; object storage is private, never publicly readable.
- Secrets only in environment variables; never in the repository or in logs.
- Full export and erasure endpoints, covering database rows **and** object-storage blobs — with the
  single exception constitution IX 3.0.0 creates: a recording retained under its public-recording
  basis is not deleted by erasure or objection. Those routes reach every identifier held about a
  person appearing in it, and pseudonymise them.
- Access to archived replays is logged.

## Open items before public launch

Every item below names the task that delivers it, or says it is out of scope and why. This list is
a set of commitments rather than a description, and an unowned commitment is how three of them came
to be promised here and built nowhere. `scripts/checks/spec_lint.py` enforces the convention.

- [ ] Publish the privacy policy page and link it from the footer — T093, T095, T098a.
- [ ] Publish the third-party objection form and document its handling procedure — T092 writes the
      procedure and the endpoint, T094 specifies the form, T095 builds it on a route outside the
      session. The endpoint alone would not be a way for a non-user to object. The procedure T092
      writes must name the *instrument* as well as the actor and the delay: recording an objection
      is not pseudonymising one, and no task in feature 001 currently gives whoever resolves it a
      way to carry the act out.
- [ ] Record controller identity and contact details above — out of scope for any task: an act of
      the controller, not of the code. Blocks public launch, not implementation.
- [ ] Define and document the breach-notification procedure — out of scope: nothing in feature 001
      defines one, and inventing it in passing would be worse than leaving it visibly open.
- [ ] Decide whether real players' identifiers committed in `packages/providers/fixtures/companion_profiles_search.json` need scrubbing from git history before public launch — out of scope here: no
      task in this feature closes it, and it is an act on the repository's history, not on running
      code. The fixture holds twenty real players' `profileId`, `name`, `country`, `clan`, `games`,
      `avatarhash`, and, deliberately, the very account-linking fields FR-004b requires stripped at
      the boundary (`steamId`, `shared`, `sharedHistory`), plus a handful of social-media handles.
      The fixture is correct as engineering: T312 asserts those fields are dropped before anything
      downstream sees them, and a fixture that had already stripped them would make that assertion
      pass without exercising the code path it exists to guard. That correctness does not make the
      fixture free of consequence — it sits in the history of a public repository, outside every
      table this register or `apps/api` governs, reachable by no erasure or export endpoint and
      bounded by no TTL, and removing it from history later would not reach a fork or clone already
      taken. FR-004b's prohibition is written against the running service acting on these fields;
      nothing currently extends it to what the repository commits as a fixture, and this item is
      that gap, weighed but not yet closed.
