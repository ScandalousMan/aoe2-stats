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

| #   | Purpose                                                                           | Data subjects                                                                                                                                                                                                                                                                                        | Categories of data                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Legal basis                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Source                                                                                                                                                                                  | Retention                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Recipients                                                                                                                                                                                                                                                                          |
| --- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Account and authentication                                                        | registered users                                                                                                                                                                                                                                                                                     | steamid64 (extracted from the Steam OpenID claimed identifier, which is verified but never itself stored — constitution III), Relic profile_id, opaque session identifier, sign-in timestamps, beta allowlist admission timestamp                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | contract performance (Art. 6-1-b)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | the user, via Steam OpenID                                                                                                                                                              | until account deletion                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | none                                                                                                                                                                                                                                                                                |
| 2   | Displaying stats and match history                                                | registered users                                                                                                                                                                                                                                                                                     | Relic profile_id, alias, country, per-leaderboard rating / rank / wins / losses / streak / highest rating, daily rating-history snapshots enabling a rating curve (FR-009), match metadata                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | contract performance (Art. 6-1-b)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Relic API                                                                                                                                                                               | until account deletion (rating snapshots are append-only history, never overwritten, until then)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | none                                                                                                                                                                                                                                                                                |
| 3   | Replay archival                                                                   | registered users                                                                                                                                                                                                                                                                                     | the `.aoe2record` recording of their own matches, containing their actions, alias and in-game chat; the timestamp an objection to archival was made, if one was                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | legitimate interest (Art. 6-1-f) — see the balancing test below. Changed from explicit consent (Art. 6-1-a) by constitution IX 4.0.0, 2026-08-25                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | aoe.ms; the user, for the objection timestamp                                                                                                                                           | indefinite, until erasure is requested                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | none                                                                                                                                                                                                                                                                                |
| 4   | Third-party players appearing in a user's matches                                 | other AoE2 players                                                                                                                                                                                                                                                                                   | Relic profile_id, public alias, country, civilisation, team and colour choice, match result, rating and rating change; and, inside a replay this service holds or fetches, their in-game actions and chat                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | legitimate interest (Art. 6-1-f) — the data is already public through the official leaderboards and stats page. **Amended 2026-08-29, feature 003 US3**: archival (activity 3) still captures only the linked user's own point of view, so a third party's actions and chat enter this service's own storage only inside a match the linked user played in — that half of this sentence is unchanged. It no longer describes the whole of this activity: `GET /api/matches/{game_id}/replay/{profile_id}`'s `obtainable` state (003 FR-023, FR-025–FR-028) fetches any participant's point of view of any match this service holds and streams it to the requesting signed-in user, whether or not that caller played in it, without storing it (FR-027). See the balancing test's 2026-08-29 amendment below. | Relic API, aoe.ms                                                                                                                                                                       | same as the replay it belongs to, for a point of view this service stores. A point of view fetched only to stream through is retained nowhere — FR-027 forbids storing it; the request leaves only a `provider_calls` row (endpoint, status, timing — no `game_id`, `profile_id` or requester) and, on a 404, a `replay_fetch_misses` row naming the pair but not the requester (activity 8)                                                                                                                                                                                                                                                                                        | none, for a replay this service stores. **Amended 2026-08-29**: not `none` for a point of view fetched live and streamed through without storage — the recipient is the requesting signed-in user (`obtainable` state above), the one exception to every other `none` in this table |
| 5   | Logging access to archived replay files (FR-040)                                  | registered users (the archive's owner; a replay is only ever opened by the user who owns the capture, per the download endpoint's ownership check)                                                                                                                                                   | which archived replay was accessed, by whom, when, and for what purpose (currently: download)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | legitimate interest (Art. 6-1-f) — see the balancing test below                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | generated by the system itself, at request time                                                                                                                                         | same as the replay it describes; deleted with the capture, including on erasure                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | none                                                                                                                                                                                                                                                                                |
| 6   | Handling data-subject rights requests (export, erasure, third-party objection)    | registered users, and non-user third parties who submit an objection                                                                                                                                                                                                                                 | request kind, the account or profile the request concerns, when it was requested, when and how it was resolved                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | legal obligation (Art. 6-1-c) — GDPR Articles 15-21                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | the requester, via the export / erasure / objection endpoints                                                                                                                           | indefinite — the row is the accountability record for the request and survives an erasure it may document; only `subject_user_id` is cleared, not the row (SC-008)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | none                                                                                                                                                                                                                                                                                |
| 7   | Player-name search, including a player who appears in nobody's match              | any AoE2 player whose name is searched — not only the opponents and teammates a linked user has played, which is the class activity 4's necessity argument is built around and does not cover here                                                                                                   | Relic profile_id, alias, country, clan, games played — and the source's `steamId` claim as a sixth field. Constitution IX 3.0.0 (2026-08-24) retired FR-004b's strip and 003's T396 to T399 landed it: **this activity processes the field today** — the row described a decided change until then and describes a running one now. It is named `unverified_steam_id`, is shown to the user as an assertion this service has **not** verified, and is never used to link or merge profiles (001 FR-045). The identifier itself is rendered beside that label, so a viewer can read the claimed value and not only that a claim exists. `shared`, `sharedHistory` and `hidden` are not carried, for the reasons `specs/003-player-search-match-analysis/contracts/providers.md` gives; the normalised query text itself, which is `profile_search_cache`'s primary key and is typically a searched player's name; the degraded fallback (FR-004d) returns the same shape read from `aoe_profiles`, already covered by activity 4 and adds no category of its own | legitimate interest (Art. 6-1-f) — see the balancing test below                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | `data.aoe2companion.com`'s public search endpoint (`GET /api/profiles?search=`, `docs/data-sources.md` §3); the degraded fallback is a read of `aoe_profiles`, sourced under activity 4 | `profile_search_cache`: a row is _served_ only while younger than `PLAYER_SEARCH_CACHE_TTL_SECONDS` (`.env.example`); it is _physically deleted_ opportunistically on the next successful cache write — any query's, not necessarily its own — never on a schedule (FR-044); see `data-model.md`'s `profile_search_cache` section for the mechanism. The TTL bounds what is served, not what is stored: a row can outlive it if no later search succeeds. Degraded answers (FR-004d) are cached too, under a separate short TTL fixed in code (`_FALLBACK_CACHE_TTL_SECONDS`) rather than the configured one, so writes — and therefore pruning — continue while the source is down | none                                                                                                                                                                                                                                                                                |
| 8   | Recording that the source has no recording for one exact point of view (003 T337) | any AoE2 player whose point of view of a match was asked for and the source answered 404 — most often another participant, but a linked user's own not-yet-archived point of view can land here too, since `GET /api/matches/{game_id}/replay/{profile_id}` does not distinguish caller from subject | `game_id`, `profile_id` and the timestamp the 404 was observed — no gameplay content, since none was ever returned; not the identity of the requester, which this row does not carry at all                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | legitimate interest (Art. 6-1-f) — see the balancing test below                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | the source's own 404 response (`aoe.ms`), observed by this service itself at fetch time                                                                                                 | indefinite; never swept — `specs/003-player-search-match-analysis/spec.md` FR-044 forbids a scheduled sweep, and R8 in that feature's `research.md` gives the reason: unlike a computed `obtainable`/`expired` label, "the source has no recording for this pair" does not become false with the passage of time                                                                                                                                                                                                                                                                                                                                                                    | none — read only by this service's own availability derivation, never served to a caller as a row; a caller sees the derived `never_recorded` state, not this table                                                                                                                 |

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
  a profile _in order to_ have their replays archived, so the "choice" was a formality attached to
  the one action the product exists for. Worse, the gate as implemented withheld the public match and
  rating metadata too, so declining a question about _recordings_ silently disabled the rest of the
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
  caller must have played against the profile) widened _who inside the service_ may view this row to
  any signed-in, allowlisted user, without widening what is collected or from where; the impact
  finding above does not depend on which signed-in user is looking, because the source is already
  public. A `profile_id` this service has never itself observed still answers `404` — that boundary
  is what keeps this widening inside activity 4 rather than reaching the wider class activity 7
  covers.

**Amended 2026-08-29, feature 003 US3 (`GET /api/matches/{game_id}/replay/{profile_id}`'s
`obtainable` state).** This route widens who may see the recording itself, not only who may see the
row describing it — a bigger step than FR-008a's widening above, and stated separately rather than
folded into it.

- **Necessity**: the source (`aoe.ms`) already serves the identical bytes, unauthenticated, to
  anyone who supplies a real `(gameId, profileId)` pair — `docs/data-sources.md` §2 measured "no
  ownership check" at the source itself. This route adds a Steam-verified sign-in, a per-user rate
  limit (003 FR-028) and never stores what it fetches (003 FR-027), three constraints the source
  does not impose on the same bytes today.
- **Impact on the data subject**: a real widening, stated plainly rather than minimised. Chat and
  actions — the categories this activity's own Impact finding above calls "the most sensitive
  element" — are now disclosed to a caller who need not have played the match, which the previous
  reading of this activity did not cover. It is bounded rather than open-ended: the caller must
  already be a signed-in, allowlisted user of this service, not the public the source already
  exposes the same bytes to; the `(game_id, profile_id)` pair must name a match this service already
  holds a record of, so this route cannot be used to enumerate arbitrary pairs against the source the
  way a caller already could directly; and nothing fetched this way is retained, indexed or displayed
  anywhere in this service beyond the single response (FR-027) — this service keeps no copy for a
  later, unaccountable read to reach.
- **Safeguards**: the per-user rate limit (FR-028); the boundary-race fetch-miss record (activity 8)
  so a repeat request reads a stored fact instead of probing the source a second time; the route
  never overrides what `derive_availability` already decided from rows and a clock
  (`specs/003-player-search-match-analysis/research.md` R8) — it only carries out the state's own
  action, never a stranger's.
- **What this amendment does not claim**: unlike the `archived` state above, this state writes no
  `replay_access_log` row (`specs/003-player-search-match-analysis/contracts/http-api.md`) — FR-029's
  own text scopes that duty to "a recorded game this service **holds**", and a streamed point of view
  is, by FR-027, never held. Activity 5's balancing test states why that omission is judged
  acceptable rather than restating it here.

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

**Amended 2026-08-29, feature 003 US3 — scope stated plainly rather than left to imply more than it
covers.** The Interest-pursued bullet above is written against "an archived replay" — a recording
this service itself holds — and that scope is now load-bearing rather than incidental.
`GET /api/matches/{game_id}/replay/{profile_id}`'s `obtainable` state (activity 4's own 2026-08-29
amendment) fetches a third party's recording from the source and streams it to any signed-in caller,
with no ownership check, and writes **no** row here.

Two ways of making the register honest about that gap were weighed, per this remediation's own
instruction to pick one rather than leave it ambiguous. Extending this log to the `obtainable` state
was rejected: the accountability this log buys is that a persisted copy inside this service's own
infrastructure — one that could otherwise be opened repeatedly, silently, by anyone with access to
the database or the object store, with no trace left anywhere — was opened only by the person
entitled to it. FR-029's own text draws that boundary deliberately: it requires a log for "a recorded
game this service **holds**", both served and merely read, and a streamed point of view is, by
FR-027, never held — there is no persisted copy inside this service for a later, unaccountable read
to reach, because nothing survives past the single request/response cycle that already names the
recipient in every application log of the request itself. Logging it here would record a fact this
log's own necessity argument does not need recorded — an access trail exists so that a _later_ look
at something already at rest can be found; a stream that is fetched once and immediately discarded
does not create the thing this log audits.

**Conclusion**: this activity's safeguard is accurate for the `archived` state and does not extend to
the `obtainable` state — the register now says so rather than implying one audit trail covers both.
The disclosure itself — that any signed-in caller, not only a participant, now sees a third party's
chat and actions at all — is a real and separate widening, and it is weighed on its own terms in
activity 4's 2026-08-29 amendment, not smuggled into this log's absence.

## Handling procedure for activity 6's third-party objection (FR-039)

Activity 6 above is a legal obligation (Art. 6-1-c), not legitimate interest, so it carries no
balancing test — this section is the launch-item commitment the "Open items" list below names,
written once implementation existed to describe rather than promised in advance of it.

**Where an objection lands.** `POST /api/privacy/object`
(`apps/api/src/aoe2stats_api/routers/privacy.py`, T092) is the one unauthenticated write in this
system — the person objecting is, by definition, not a user and carries no session. The call
records one `data_requests` row (`kind = third_party_objection`, `subject_profile_id` set to the
profile named, `subject_user_id` null, `requested_at` set, `completed_at` null) and acts on
nothing else. It is rate limited — counted against `data_requests` itself, in a single window
shared by every caller, rather than per caller, since there is no caller identity here to key a
limit to the way every other write in this API can (`privacy.py`'s own module docstring) — closing
the denial-of-service surface an unthrottled anonymous write would otherwise open.

**Who resolves it, and within what delay.** The controller (the project owner, named at the top
of this file) — there is no second role or admin console to name at this stage of the project, and
inventing one here would describe a process that does not exist. Resolution is due within 30 days
of `requested_at`, the same period GDPR Article 12(3) gives a controller to act on a data-subject
rights request generally: this row is the one deferred request in the feature (export and erasure
both act synchronously, inside their own `POST`), so it is the one that needs a delay stated at
all.

**The mechanism, named rather than left implied.** `resolve_third_party_objection`
(`apps/api/src/aoe2stats_api/routers/privacy.py`) is the instrument: a plain function, not a
route, that the controller calls directly — from a one-off script or a database shell against the
production database, naming the unresolved `data_requests.id` — never through any unauthenticated
path, which is the exact vector the rate limit above exists to close. It looks the row up,
pseudonymises `subject_profile_id` through `_pseudonymise_profile_id`, the identical mechanism
`POST /api/privacy/erase` (T091) already calls over a departing user's own linked profiles
(`specs/001-steam-link-replay-ingestion/data-model.md`'s own phrase: "the same mechanism FR-039
gives third parties"), and then sets `completed_at` and `outcome` on the same row — the row is
this procedure's own trace, readable afterwards without needing to trust that anything happened.
Recording an objection is not pseudonymising one; this is the sentence that used to be missing,
naming the actor, the delay and the instrument together rather than leaving a human the first two
with no way to carry out the third.

**What this procedure does not yet cover.** No route or script surfaces the _list_ of unresolved
`data_requests` rows of this kind to the controller — today that means a direct query against
`data_requests WHERE kind = 'third_party_objection' AND completed_at IS NULL`. A dashboard for
this is a legitimate future improvement, not a gap in the obligation itself: the row exists, the
instrument to resolve it exists, and the delay is stated, which is what this launch item asked
for. Publishing a form a non-user can actually reach — the front end this JSON endpoint is not by
itself, per the "Open items" list below — is T095's, not this procedure's.

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
  finding rests on capture being limited to matches the linked user played in — true of archival
  (activity 3) and, per activity 4's 2026-08-29 amendment, not true of the streamed `obtainable`
  fetch, which still requires the match to be one this service already holds a record of. Neither
  constraint applies here: a subject here may never have played against the searching user, or against
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
`profile_search_cache` is keyed to a user, so a _searching_ user's own export or erasure never touches
it (`data-model.md`'s `profile_search_cache` section). For the _subject_ of a cached row — the player
who was searched — neither the export/erasure endpoints (activity 6) nor 001's third-party objection
route reach it either: FR-039 scopes that route to "a non-user appearing in archived matches," and a
cached search result does not describe an archived match. Nothing in this system removes a subject's
row on request, and nothing removes it on a schedule either: the TTL only stops a stale row from being
_served_, per the retention column above; the row is _deleted_ only opportunistically, on a later
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

## Balancing test for activity 8

Added 2026-08-29, feature 003 US3, T337 — remediating a review finding that this table (`replay_fetch_misses`) shipped without a row here, alongside the `obtainable` streaming
operation activity 4 gained the same day.

- **Interest pursued**: getting the download route's own displayed state right, and not repeating a
  fetch the source has already answered "no" to. FR-025 forbids presenting an unobtainable download
  as an action that then fails; without this table, the second click on the same point of view would
  either lie about the state or repeat the exact fetch that already disclosed the recording once
  (activity 4) for no gain.
- **Necessity**: the fact — "the source has no recording for this exact pair" — can only be learned
  by asking the source, and it can only be learned once profitably; asking again would be a second,
  needless disclosure attempt of the same third party's data with the identical, already-known
  answer. Storing the one bit that avoids repeating it is the least intrusive way to keep the page
  honest.
- **Impact on the data subject**: negligible. The two identifiers this row carries (`game_id`,
  `profile_id`) are already processed for the same match under activity 4; this row adds no new
  category and states only that a recording does not exist, which is already learnable by anyone who
  makes the identical unauthenticated request against `aoe.ms` directly (`docs/data-sources.md` §2).
  It carries no gameplay content, because none was ever returned.
- **Safeguards**: insert-only, `ON CONFLICT DO NOTHING` (data-model.md), so no caller can overwrite
  or infer anything about a concurrent request; read only by this route's own availability derivation
  (`derive_availability`, R8), never returned to a caller as a row — a caller sees the derived
  `never_recorded` state, not this table; carries no requester identifier at all, so it cannot answer
  "who asked" any more than it answers "who is this player" beyond what activity 4 already processes.
- **Outcome**: the interest is not overridden. The category is already governed and low-impact under
  activity 4, the row adds no new one, and indefinite retention without a sweep (FR-044) is justified
  by the fact recorded never becoming false with time — unlike a cached availability label, which
  would (`research.md` R8).

## Technical and organisational measures

- All compute and storage regions are in the EU (constitution principle IX).
- Encryption in transit and at rest; object storage is private, never publicly readable.
- Secrets only in environment variables; never in the repository or in logs.
- Full export and erasure endpoints, covering database rows **and** object-storage blobs — with the
  single exception constitution IX 3.0.0 creates: a recording retained under its public-recording
  basis is not deleted by erasure or objection. Those routes reach every identifier held about a
  person appearing in it, and pseudonymise them.
- Access to a recording this service holds is logged (activity 5). **Amended 2026-08-29**: a point
  of view fetched live from the source and streamed through without storage is not — activity 5's
  2026-08-29 amendment states why that is judged acceptable rather than a gap in this line.

## Open items before public launch

Every item below names the task that delivers it, or says it is out of scope and why. This list is
a set of commitments rather than a description, and an unowned commitment is how three of them came
to be promised here and built nowhere. `scripts/checks/spec_lint.py` enforces the convention.

- [ ] Publish the privacy policy page and link it from the footer — T093, T095, T098a.
- [ ] Publish the third-party objection form and document its handling procedure — T092 writes the
      procedure and the endpoint, T094 specifies the form, T095 builds it on a route outside the
      session. The endpoint alone would not be a way for a non-user to object. **T092 done**: the
      endpoint (`POST /api/privacy/object`) and the handling procedure above (who resolves it,
      within what delay, and the `resolve_third_party_objection` instrument that carries out the
      pseudonymisation) both exist now. This item stays open for T094 and T095: an unauthenticated
      JSON endpoint is not, by itself, a way for the person it exists for — who has no reason to
      know it exists — to object.
- [ ] Publish a dashboard over unresolved third-party objections — out of scope for any task in
      feature 001; today's procedure above names the direct `data_requests` query in its place. A
      legitimate future improvement, not a gap in the obligation itself: the row, the delay and
      the resolving instrument all already exist.
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
