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
| 3   | Replay archival                                                                | registered users                                                                                                                                   | the `.aoe2record` recording of their own matches, containing their actions, alias and in-game chat; the timestamp ingestion consent was given and, if applicable, withdrawn                                                       | explicit consent (Art. 6-1-a), collected separately from account creation                                                                                                       | aoe.ms; the user, for the consent timestamp                   | indefinite, until erasure is requested                                                                                                                             | none       |
| 4   | Third-party players appearing in a user's matches                              | other AoE2 players                                                                                                                                 | Relic profile_id, public alias, country, civilisation, team and colour choice, match result, rating and rating change; and, inside archived replays, their in-game actions and chat                                               | legitimate interest (Art. 6-1-f) — the data is already public through the official leaderboards and stats page, and capture is limited to matches the consenting user played in | Relic API, aoe.ms                                             | same as the replay it belongs to                                                                                                                                   | none       |
| 5   | Logging access to archived replay files (FR-040)                               | registered users (the archive's owner; a replay is only ever opened by the user who owns the capture, per the download endpoint's ownership check) | which archived replay was accessed, by whom, when, and for what purpose (currently: download)                                                                                                                                     | legitimate interest (Art. 6-1-f) — see the balancing test below                                                                                                                 | generated by the system itself, at request time               | same as the replay it describes; deleted with the capture, including on erasure                                                                                    | none       |
| 6   | Handling data-subject rights requests (export, erasure, third-party objection) | registered users, and non-user third parties who submit an objection                                                                               | request kind, the account or profile the request concerns, when it was requested, when and how it was resolved                                                                                                                    | legal obligation (Art. 6-1-c) — GDPR Articles 15-21                                                                                                                             | the requester, via the export / erasure / objection endpoints | indefinite — the row is the accountability record for the request and survives an erasure it may document; only `subject_user_id` is cleared, not the row (SC-008) | none       |

## Balancing test for activity 4

- **Interest pursued**: letting a player analyse their own matches, which inherently involve
  opponents and teammates.
- **Necessity**: a replay cannot be split per player. Analysing one's own game requires the file
  that contains everyone in it. No less intrusive means exists.
- **Impact on the data subject**: low. The identifiers and results are already published by the game
  publisher on a public leaderboard and stats site. In-game chat is the most sensitive element and is
  never displayed or indexed publicly.
- **Safeguards**: only the consenting user's point of view is captured, never the opponents' own
  replay files; no public indexing of third-party profiles; no cross-user aggregation of a
  third-party's behaviour beyond what the official leaderboards already show; an objection form
  pseudonymises a third party's `profile_id` on request without breaking match integrity; access to
  stored replays is logged.

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

## Technical and organisational measures

- All compute and storage regions are in the EU (constitution principle IX).
- Encryption in transit and at rest; object storage is private, never publicly readable.
- Secrets only in environment variables; never in the repository or in logs.
- Full export and erasure endpoints, covering database rows **and** object-storage blobs.
- Access to archived replays is logged.

## Open items before public launch

Every item below names the task that delivers it, or says it is out of scope and why. This list is
a set of commitments rather than a description, and an unowned commitment is how three of them came
to be promised here and built nowhere. `scripts/checks/spec_lint.py` enforces the convention.

- [ ] Publish the privacy policy page and link it from the footer — T093, T095, T098a.
- [ ] Publish the third-party objection form and document its handling procedure — T092 writes the
      procedure and the endpoint, T094 specifies the form, T095 builds it on a route outside the
      session. The endpoint alone would not be a way for a non-user to object.
- [ ] Record controller identity and contact details above — out of scope for any task: an act of
      the controller, not of the code. Blocks public launch, not implementation.
- [ ] Define and document the breach-notification procedure — out of scope: nothing in feature 001
      defines one, and inventing it in passing would be worse than leaving it visibly open.
