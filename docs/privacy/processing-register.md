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

| # | Purpose | Data subjects | Categories of data | Legal basis | Source | Retention | Recipients |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Account and authentication | registered users | OpenID claimed identifier, steamid64, Relic profile_id, opaque session identifier | contract performance (Art. 6-1-b) | the user, via Steam OpenID | until account deletion | none |
| 2 | Displaying stats and match history | registered users | Relic profile_id, alias, country, per-leaderboard rating / rank / W-L / streak, match metadata | contract performance (Art. 6-1-b) | Relic API | until account deletion | none |
| 3 | Replay archival | registered users | the `.aoe2record` recording of their own matches, containing their actions, alias and in-game chat | explicit consent (Art. 6-1-a), collected separately from account creation | aoe.ms | indefinite, until erasure is requested | none |
| 4 | Third-party players appearing in a user's matches | other AoE2 players | Relic profile_id, public alias, country, civilisation, result, rating; and, inside archived replays, their in-game actions and chat | legitimate interest (Art. 6-1-f) — the data is already public through the official leaderboards and stats page, and capture is limited to matches the consenting user played in | Relic API, aoe.ms | same as the replay it belongs to | none |

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

## Technical and organisational measures

- All compute and storage regions are in the EU (constitution principle IX).
- Encryption in transit and at rest; object storage is private, never publicly readable.
- Secrets only in environment variables; never in the repository or in logs.
- Full export and erasure endpoints, covering database rows **and** object-storage blobs.
- Access to archived replays is logged.

## Open items before public launch

- [ ] Publish the privacy policy page and link it from the footer.
- [ ] Publish the third-party objection form and document its handling procedure.
- [ ] Record controller identity and contact details above.
- [ ] Define and document the breach-notification procedure.
