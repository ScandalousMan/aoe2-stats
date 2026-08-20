# Feature Specification: Steam Account Linking and Automatic Replay Ingestion

**Feature Branch**: `001-steam-link-replay-ingestion`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Steam account linking to an AoE2 profile, plus automatic replay ingestion. A user creates an account, links it to their Steam identity, and the system resolves their AoE2 profile. From then on the system automatically discovers their new matches and archives the replay file of each one before it is purged from the official servers (~31 day window). The user can see their linked profile, their rating per leaderboard, their match history, a match detail view, and the archival status of each replay. Manual replay upload is the fallback when automatic capture failed. Includes GDPR consent, export and erasure."

## Context

Replay files for Age of Empires II: Definitive Edition are removed from the publisher's servers
after approximately **31 days** (measured 2026-08-19; see `docs/data-sources.md`). Once removed they
cannot be recovered by anyone. Every day a player's replays go uncaptured is a day of their history
permanently destroyed.

This feature exists to stop that loss. It is deliberately scoped to **capture and presentation only**:
analysing what is inside a replay is a separate, later feature. That ordering is mandated by
constitution principle I.

## Clarifications

### Session 2026-08-19

- **Q: Is Steam sign-in the sole credential, or is there also an email-and-password account?**
  A: Steam sign-in is the sole credential. No password is ever stored, and password reset, email
  verification and account recovery are out of scope — Valve owns recovery. The reasoning is that a
  user's AoE2 identity *is* their Steam account: losing Steam means losing the game profile anyway,
  so a separate local account would survive only as an empty shell. Resolves FR-006.

- **Q: A player can hold several AoE2 profiles. One profile or several?**
  A: Capture all of them, present one. Ingestion covers every profile the user has linked; the
  interface shows a single primary profile chosen by the user. This follows constitution principle
  I: a second profile's replays face the same ~31-day window, so not capturing them destroys them
  permanently, whereas presenting them is a display problem solvable at any later date.
  Resolves FR-007.

- **Correction, same session — how "several profiles" actually works.** The original wording assumed
  one Steam account could hold several AoE2 profiles. Measurement says otherwise: **one Steam account
  maps to exactly one AoE2 profile.** What players call a second profile is a second *Steam account*.
  A well-known player was observed with four profiles across four distinct Steam accounts.
  Consequently, supporting several profiles means letting a user **link several Steam accounts to one
  aoe2-stats account**, each proven by its own sign-in. It cannot be done by discovery.

  Third-party services publish a community-curated mapping between a player's accounts. We
  deliberately do **not** use it, for two reasons: it is an unverifiable claim about someone's
  identity, and acting on it would silently reveal that one account is an alternate of another —
  something players frequently take pains to keep separate. Only a completed sign-in proves
  ownership. Reflected in FR-007, FR-042 and FR-045.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Link my Steam account and see who I am (Priority: P1)

A player arrives, signs in with their Steam account, and the system identifies their Age of Empires
II profile. They immediately see their profile name, country, and current rating and rank on each
leaderboard they play. Nothing else in this feature is reachable until this works.

**Why this priority**: Every other story depends on knowing which AoE2 profile belongs to the user.
On its own it already replaces the chore of looking oneself up on the official leaderboard.

**Independent Test**: Sign in with a Steam account belonging to a player who has played ranked games,
and confirm the correct profile and current ratings appear without any manual entry.

**Acceptance Scenarios**:

1. **Given** a visitor who has never signed in, **When** they complete Steam sign-in, **Then** an
   account is created, their AoE2 profile is resolved automatically, and their ratings are displayed.
2. **Given** a signed-in user, **When** they return later, **Then** they are recognised and see their
   ratings refreshed to the current values.
3. **Given** a Steam account whose owner has never played AoE2 II:DE online, **When** they sign in,
   **Then** the system explains clearly that no AoE2 profile could be found and offers to retry
   rather than leaving them on an empty screen.
4. **Given** a user who already has one linked account, **When** they sign in with a second Steam
   account, **Then** it is added to the same aoe2-stats account, both profiles begin being archived,
   and the user picks which one the interface shows.
5. **Given** a user with several linked profiles, **When** anyone other than that user views
   anything the service exposes, **Then** nothing reveals that those profiles belong to the same
   person.
6. **Given** a signed-in user, **When** they choose to unlink a profile, **Then** automatic ingestion
   stops for it and they are told plainly what happens to the replays already archived.
7. **Given** a visitor about to consent, **When** they are shown what the service does, **Then** they
   are told before consenting that access depends entirely on their Steam account and cannot be
   recovered by any other means.

---

### User Story 2 - Never lose another replay (Priority: P2)

Once the user has consented, the system watches for their new matches and archives each replay
automatically, well inside the ~31-day window. When they link their account it also sweeps backwards
and rescues everything still available from the preceding 31 days. The user does nothing.

**Why this priority**: This is the irreplaceable part of the product. Presentation features can be
built at any time; a replay not captured this month is gone forever. Constitution principle I places
this above everything except the linking that enables it.

**Independent Test**: Link an account belonging to an active player, wait for the ingestion cycle,
and confirm that every match they played in the preceding 31 days that is still available has been
archived and can be downloaded back byte-for-byte identical to the original.

**Acceptance Scenarios**:

1. **Given** a user who has just consented and linked their profile, **When** the first ingestion
   cycle completes, **Then** every one of their matches from the preceding 31 days whose replay is
   still available has been archived, across **all** of their profiles and not only the primary one.
2. **Given** a linked user who plays a new match, **When** the next ingestion cycle runs, **Then**
   that match's replay is archived, and in no case later than 21 days after the match ended.
3. **Given** a replay that has already been archived, **When** ingestion runs again, **Then** no
   duplicate is created and the stored file is not rewritten.
4. **Given** a match whose replay was never recorded by the game, **When** ingestion attempts it,
   **Then** it is recorded as unavailable with a reason, and is not retried indefinitely.
5. **Given** an archived replay, **When** it is retrieved, **Then** its checksum matches the one
   recorded at capture time.
6. **Given** an ingestion cycle interrupted part-way, **When** the next cycle runs, **Then** it
   resumes cleanly with no match left in an in-progress state and nothing lost.
7. **Given** a user who has not consented to replay ingestion, **When** ingestion runs, **Then**
   nothing of theirs is downloaded or stored.

---

### User Story 3 - Browse my match history (Priority: P3)

The user sees a reverse-chronological list of their matches with the essentials at a glance —
opponent, map, civilisation, result, rating change, duration — and can open any match for detail.
Each row shows whether its replay is safely archived, still pending, or lost, and how long remains
before the capture window closes.

**Why this priority**: This is what makes the product feel useful day to day, but every match it
displays can be re-fetched at any time. It carries no risk of permanent loss, so it ranks below
capture.

**Independent Test**: With a linked account, open the history and confirm the last matches match
what the official stats page shows, and that each row's archival state reflects reality.

**Acceptance Scenarios**:

1. **Given** a linked user, **When** they open their match history, **Then** their matches appear
   newest first with opponent, map, civilisation, result, rating change and duration.
2. **Given** a match in the list, **When** the user opens it, **Then** they see every participant,
   their team, civilisation, result and rating change.
3. **Given** a match whose replay is archived, **When** the user views it, **Then** they can download
   the original replay file.
4. **Given** a match whose replay is not yet archived, **When** the user views it, **Then** they see
   the current state and the remaining time before the capture window closes.
5. **Given** a user with no matches at all, **When** they open their history, **Then** they get a
   clear empty state, not a broken or blank page.

---

### User Story 4 - Rescue a replay the system could not get (Priority: P4)

When automatic capture failed — the window closed during an outage, or the match was never recorded
server-side — the user can upload the replay file from their own machine and have it archived
alongside the rest.

**Why this priority**: A safety net for a minority of cases. Valuable precisely because the
alternative is permanent loss, but it only matters once automatic capture is working.

**Independent Test**: Take a match marked lost, upload the corresponding file from the game's saved
games folder, and confirm it is archived and attached to the right match.

**Acceptance Scenarios**:

1. **Given** a match with no archived replay, **When** the user uploads a valid replay file for it,
   **Then** it is archived and the match shows as archived, flagged as manually supplied.
2. **Given** a match that already has an archived replay, **When** the user uploads another file,
   **Then** the existing archive is not overwritten and the user is told why.
3. **Given** a file that is not a valid replay, **When** the user uploads it, **Then** it is rejected
   with a clear reason and nothing is stored.
4. **Given** a valid replay file for a match the user did not take part in, **When** they upload it,
   **Then** it is rejected.

---

### User Story 5 - Control my data (Priority: P5)

The user can see exactly what is held about them, download all of it including their archived
replays, and delete everything permanently.

**Why this priority**: Legally required before the service is offered to anyone beyond the author,
and cheap to build once the data model exists. It is last only because nothing else depends on it.

**Independent Test**: Request an export and confirm it contains the account, the profile link, the
match records and the archived replays; then request erasure and confirm nothing remains, in the
records or in storage.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they request an export, **Then** they receive all their
   personal data, their match records and their archived replay files.
2. **Given** a signed-in user, **When** they request erasure and confirm it, **Then** their account,
   profile link, match records and archived replay files are permanently deleted, storage included.
3. **Given** a user creating an account, **When** they are asked to consent to replay ingestion,
   **Then** that consent is a separate, explicit choice they can decline while still using the rest,
   and can withdraw later.
4. **Given** a person who is not a user but appears in archived matches, **When** they object,
   **Then** their identifiers are pseudonymised without destroying the integrity of the match
   records, and the outcome is recorded.

---

### Edge Cases

- A user links a Steam account that owns AoE2 but has only ever played single-player: no online
  profile exists.
- A player has changed their in-game alias: the stored alias is the last one observed, not a
  history.
- A player plays on a second Steam account. Only a completed sign-in on that account can reveal it
  (FR-007, FR-045); nothing discovers it, and the cost of not linking it — permanent loss — must be
  stated where the user would see it.
- A user links a second Steam account that is already linked to a different aoe2-stats account.
- A user loses access to their Steam account: by design there is no recovery path, and they were
  told so before consenting.
- The match discovery source is unreachable for several days: capture must catch up automatically,
  and the 21-day budget must absorb the outage without loss.
- The replay source starts refusing requests: the system must back off and raise an alert rather
  than hammering it.
- A match ends but its replay is not yet published: the first attempt must not mark it lost.
- A match is older than the retention window when discovered: it must be recorded as expired,
  distinctly from "we failed to fetch it", so the two never blur in the metrics.
- Two matches finish while an ingestion cycle is already running.
- An ingestion cycle exhausts its time budget mid-queue.
- The same match appears twice from the discovery source, or under two of the user's profiles.
- A user withdraws ingestion consent while captures are queued.
- A user unlinks their profile and later relinks the same one.
- The archived file is not a well-formed replay (truncated, empty, or unexpected contents).
- Two users are in the same match: the match record is shared, but each user's own replay is not.
- Storage rejects a write mid-capture: no match may ever be marked archived without its file.

## Requirements *(mandatory)*

### Functional Requirements

**Identity and profile linking**

- **FR-001**: System MUST let a person sign in using their Steam account and MUST verify that
  sign-in with Steam itself before trusting it.
- **FR-002**: System MUST resolve the signed-in Steam identity to the corresponding AoE2 player
  profile automatically, with no manual identifier entry by the user.
- **FR-003**: System MUST handle the case where no AoE2 profile exists for a Steam identity, with an
  explanatory outcome rather than an error state.
- **FR-004**: System MUST let a user unlink their profile, and MUST state clearly what becomes of
  already-archived replays before the user confirms.
- **FR-005**: System MUST restrict account creation to an allowlist during the closed beta, and MUST
  tell a non-allowlisted visitor why they cannot proceed.
- **FR-006**: System MUST treat the verified Steam sign-in as the sole credential. It MUST NOT store
  passwords, and MUST NOT offer password reset, email verification or account recovery: a user who
  loses access to their Steam account loses access here, and this MUST be stated plainly before they
  consent to anything being archived.
- **FR-007**: System MUST let a user link more than one Steam account to their single aoe2-stats
  account, each proven by its own completed sign-in, since one Steam account corresponds to exactly
  one AoE2 profile.
- **FR-042**: System MUST ingest replays for **all** of the user's linked profiles, so that no
  linked profile's matches expire uncaptured.
- **FR-045**: System MUST NOT infer, suggest or act upon any relationship between AoE2 profiles that
  the user has not proven by signing in. Third-party mappings between a player's accounts MUST NOT be
  used to link, merge or display profiles together: they are unverifiable, and surfacing them would
  expose alternate accounts their owners keep separate on purpose.
- **FR-043**: System MUST let the user designate one discovered profile as primary, and MUST present
  ratings and match history for that profile. Where a user has more than one profile, the interface
  MUST make the others reachable rather than hiding that they exist and are being archived.
- **FR-044**: System MUST apply its ingestion quota per user, aggregated across all their profiles,
  never per profile. The quota MUST NOT apply to a capture whose deadline is nearer than the
  quota-exempt horizon: a fairness cap that delays an expiring replay in order to serve a fresh one
  inverts the priority the whole system is built on. The quota exists for fairness between users,
  not for politeness toward the source — rate limiting handles that.

**Ratings and match data**

- **FR-008**: System MUST display the user's current rating, rank and win/loss record for each
  leaderboard they have played.
- **FR-009**: System MUST record a rating snapshot over time so rating history can be shown.
- **FR-010**: System MUST present the user's matches newest first, showing opponents, map,
  civilisation, result, rating change and duration.
- **FR-011**: System MUST provide a match detail view listing every participant with their team,
  civilisation, result and rating change.
- **FR-012**: System MUST preserve, unmodified, the exact response received from any external source
  whose response is irrecoverable — match records above all — so that a later change in
  interpretation can be re-derived without re-fetching. Sources that can be re-queried at any time,
  such as current ratings, are exempt: a second verbatim copy of something still available is a
  second thing to keep honest, for no gain.

**Replay capture**

- **FR-013**: System MUST discover the linked user's new matches automatically, without user action.
- **FR-014**: System MUST archive the replay of each discovered match no later than **21 days** after
  the match ended, leaving margin against the ~31-day source retention window.
- **FR-015**: System MUST, upon linking, immediately attempt every match from the preceding 31 days.
- **FR-016**: System MUST capture only the recording from the consenting user's own point of view,
  never that of other participants.
- **FR-017**: System MUST store each replay exactly as received, unmodified, with a checksum recorded
  at capture time and verifiable on retrieval.
- **FR-018**: System MUST never store two copies of the same replay for the same user and match.
- **FR-019**: System MUST distinguish, and report separately, these outcomes per match: not yet
  attempted, archived, never recorded by the game, expired beyond the retention window, failed
  after repeated attempts, and captured but unreadable (FR-026).
  "Never recorded by the game" MUST NOT be concluded from the first attempt on a recent match. A
  replay is not always published the instant a match ends, and the source answers an identical 404
  for "not yet" and "never". Until the match is older than the publication grace, a 404 leaves the
  capture awaiting a further attempt rather than closing it, and "never recorded" MUST NOT be
  concluded from fewer than two attempts whatever the age: at a daily cadence a single poll can fall
  on either side of the grace, so age alone would let one unlucky 404 close a capture that the next
  poll would have caught. The grace itself MUST be at least twice the discovery cadence for the same
  reason. Concluding otherwise turns a
  publication delay into a permanent loss, which is the one outcome this system exists to prevent.
- **FR-020**: System MUST retry a failed capture with increasing delay, and MUST stop after a bounded
  number of attempts rather than retrying forever.
- **FR-021**: System MUST limit its request rate to external sources and MUST stop and raise an alert
  if a source signals throttling or refusal, rather than continuing.
- **FR-022**: System MUST resume cleanly after an interrupted cycle, leaving no match stuck in an
  in-progress state.
- **FR-023**: System MUST never mark a replay archived unless its file is durably stored.
- **FR-024**: System MUST record, for every cycle, when it ran, what it attempted, what it achieved
  and what remains outstanding, so that a cycle failing to run at all is detectable from the outside.
- **FR-025**: System MUST raise an alert when any replay passes its capture deadline unarchived. This
  count is expected to be permanently zero. This alert fires at the **capture deadline** (day 21),
  not at expiry (day ~31). By the time a capture is expired the replay is already gone and the alert
  is a post-mortem; at the deadline there are still ~10 days in which a human can act.
- **FR-026**: System MUST verify that a captured file is a well-formed replay and MUST record the
  outcome of that verification. A file that fails verification MUST still be stored, and MUST be
  marked for review rather than discarded or retried into oblivion: once the retention window has
  closed the source holds no replacement, so a malformed capture is evidence, not garbage. A capture
  in this state counts as neither archived nor lost.
- **FR-027**: System MUST show the user, per match, the archival state and the time remaining before
  the capture window closes. "Time remaining" means time to the **capture deadline** (the 21-day
  internal budget), not to the source's ~31-day retention: the user is shown the deadline the system
  commits to, not the one it refuses to rely on.
- **FR-028**: Users MUST be able to download any of their archived replays.

**Manual upload**

- **FR-029**: Users MUST be able to upload a replay file for one of their own matches that has none.
- **FR-030**: System MUST validate an uploaded file is a well-formed replay and reject it otherwise,
  storing nothing.
- **FR-031**: System MUST reject an upload for a match the user did not participate in.
- **FR-032**: System MUST never let an upload overwrite an existing archived replay.
- **FR-033**: System MUST record that a replay was manually supplied rather than captured.

**Consent, privacy and data rights**

- **FR-034**: System MUST obtain explicit consent for replay ingestion, separately from account
  creation, and MUST record when it was given.
- **FR-035**: Users MUST be able to withdraw ingestion consent, after which no further replays of
  theirs are captured.
- **FR-036**: Users MUST be able to export all their personal data, match records and archived
  replays.
- **FR-037**: Users MUST be able to permanently erase their account and everything attached to it,
  stored files included, with an explicit confirmation step.
- **FR-038**: System MUST NOT publicly expose or index the profiles of people who are not users.
- **FR-039**: System MUST provide a way for a non-user appearing in archived matches to object, and
  MUST pseudonymise their identifiers on request without corrupting match records.
- **FR-040**: System MUST log access to archived replay files.
- **FR-041**: System MUST publish a privacy notice describing what is collected, on what basis, for
  how long, and how to exercise these rights.

### Key Entities

- **User**: someone with an account. Holds their consent decisions and their allowlist status.
- **Steam identity**: a Steam account whose ownership the user has proven by signing in. A user may
  hold several; each maps to exactly one AoE2 profile.
- **Player profile**: an AoE2 player as the game knows them — identifier, alias, country. Exists for
  users and for third parties alike; only users' profiles are linked to an account.
- **Profile link**: the association between a user and one of their player profiles, whether it is
  the primary one for display, and when it was linked and unlinked. A user may hold several; all
  are ingested, one is presented. Ingestion consent is **not** here: it is held once on the user,
  because it is a decision about the person and not about one of their accounts, and because a
  per-link consent would make FR-044's per-user quota ambiguous.
- **Match**: one game — when it started and ended, map, leaderboard, game version, duration, plus the
  unaltered source record it came from.
- **Match participant**: one player's part in one match — team, civilisation, result, rating before
  and change.
- **Rating snapshot**: a profile's standing on one leaderboard at one moment.
- **Replay capture**: the intent to archive one match's replay from one profile's point of view. Its
  state, attempt count, capture deadline, where the file is stored, its size and its checksum. This
  is the record the whole feature turns on.
- **Ingestion cycle**: one run of the discovery-and-capture process, with what it attempted and
  achieved. Its absence is itself a signal.
- **Data request**: an export, erasure or third-party objection, and how it was resolved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Zero replays are lost.** Across any 30-day period of normal operation, the number of
  a consenting user's matches whose replay expired unarchived while it was still fetchable is 0.
- **SC-002**: 95% of a linked user's new matches are archived within **48 hours** of the match
  ending, and 100% within 21 days. The floor is the daily ingestion cadence: detection lag alone is
  up to ~25 h (`docs/adr/0002-hosting.md`), so anything under 48 h would be a promise the platform
  cannot keep.
- **SC-003**: A newly linked account has its backfill **queued within one ingestion cycle** of
  linking, and every still-available replay from the preceding 31 days archived within **7 days**,
  across all of the user's profiles, nearest deadline first.
- **SC-004**: A user goes from arriving on the site to seeing their own ratings in under 60 seconds
  and without typing any identifier.
- **SC-005**: Every archived replay is retrievable and byte-for-byte identical to what was captured,
  verified by checksum, for 100% of archives.
- **SC-006**: Re-running ingestion over an already-processed period creates no duplicate archive and
  rewrites no stored file.
- **SC-007**: A failure of the ingestion process to run at all is detected and surfaced within 30
  hours, well inside the capture budget.
- **SC-008**: An erasure request leaves no trace of the user in records or in stored files, verified
  by inspection, within the statutory deadline.
- **SC-009**: An interruption of the ingestion process at any point leaves no match in an
  in-progress state and loses no queued work.
- **SC-010**: A user can tell, for any match, whether its replay is safe, still catchable, or lost,
  without contacting support.

## Assumptions

- One Steam account corresponds to exactly one AoE2 profile. Verified against the source, 2026-08-19.
  Multi-profile support therefore means multiple linked Steam accounts, never discovery.
- Steam is the only sign-in route in scope, and the only credential. Players on other platforms are
  out of scope for this feature and this is stated to them explicitly rather than left to fail.
- Because there is no second credential, there is no account recovery. This is a deliberate trade:
  it removes password storage and every flow around it from the attack surface, and a user who has
  lost their Steam account has lost the AoE2 profile the service is about.
- The service is non-commercial and stays within the game publisher's content usage rules. No game
  assets are redistributed.
- The user base during the closed beta is small enough that request volume against external sources
  stays modest; quotas exist to keep it that way.
- Match metadata is read from the source on demand and is not expected to be exhaustive further back
  than the source itself provides.
- The publication grace and SC-002 pull in opposite directions, and the grace wins. A replay that
  answers 404 on its first poll cannot be archived before the next cycle, so a grace wide enough to
  survive a late publication puts those captures beyond SC-002's 48 hours. SC-002 tolerates 5% for
  exactly this, and the trade is not close: a metric tail is a reporting inconvenience, a capture
  closed as "never recorded" because one poll landed early is a permanent loss. Principle I decides
  it, and the decision is recorded here so it is not rediscovered as a contradiction.
- A capture budget of 21 days against an observed ~31-day retention window is deemed sufficient
  margin. If the window is ever observed to shrink, the budget is revised before anything else.
- Only the consenting user's own point-of-view recording is captured. Recordings from other
  participants' perspectives are deliberately out of scope, for volume and for privacy.
- The 7-day backfill figure (SC-003) assumes users link a few at a time. Onboarding the whole beta
  cohort at once exceeds a daily run's throughput for several days; if that is ever planned, stagger
  the invitations rather than discovering it as a backlog.
- Analysing the contents of a replay — build orders, age-up times, recommendations — is explicitly
  out of scope here. This feature must nonetheless leave the archive in a state where such analysis
  is possible later without re-fetching anything.
- The retention window, the source behaviour and the response formats are as recorded in
  `docs/data-sources.md`, measured 2026-08-19. They are not guaranteed by any external contract and
  are monitored for change.
