# Feature Specification: Player Search, Favourites and On-Demand Match Analysis

**Feature Branch**: `003-player-search-match-analysis`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "as a user, I want to have the ability to search for other players, mark them as favorite, list my favorite player, access a player's profile where I can see its leaderbord, match history. When clicking on a match (for my user or for another user), I should see match data which don't require the recorded file. I should have 2 main CTAs there : the ability to download the recorded file, from each player's point of view, and the ability to analyze the game by parsing the recorded file. The game analysis should be done once by streaming the recorded game, but I'm not sure this requires a nightly cron to store saved games on blob storage. Challenge the functional impact of this requirement."

## Context

Feature 001 makes the service useful to the person signed in: their profile, their ratings, their
matches, their replays archived before the ~31-day window closes. Everything it presents is about
one person, and everything it captures belongs to that person.

This feature opens the product to **everyone else**. A player looks up an opponent, a rival or a
well-known name, follows them, reads their matches, and — the two things 001 deliberately deferred —
gets the recorded game, and gets the game analysed.

Two facts from `docs/data-sources.md` shape every requirement below, and they pull in opposite
directions:

- The replay endpoint has **no ownership check**. Any `(gameId, profileId)` pair that is a real
  participant pair answers `200`. Anyone's recorded game, from anyone's point of view, is public
  while it exists.
- It exists for approximately **31 days**. After that it answers `404` for everyone, forever.

So third-party recorded games are freely readable *and* permanently perishable, and this service
archives none of them. That is not an oversight — it is what constitution IX ("we capture only the
consenting user's point of view") and principle I (capture budget belongs to consenting users)
require. The consequence is the central design fact of this feature: **for the signed-in user's own
matches these two CTAs work forever; for everyone else's they work for about a month and then
disappear.** Every requirement below either follows from that or exists to make it honest to the
user rather than a broken button.

## Challenging the requirement: does on-demand analysis need a nightly cron and blob storage?

The user asked for this to be challenged rather than assumed. The short answer is **no cron — and
the question couples two things that are not connected.** "Nightly cron" and "blob storage" are one
phrase in the requirement and two entirely separate decisions underneath it. The first is settled
below and the answer is no. The second turned out to be the real question, and it was decided the
other way (Q2, session 2026-08-23).

**1. The nightly cron and the object store are not analysis infrastructure.** They exist in 001 to
beat the ~31-day purge for consenting users, mandated by constitution principle I. They are already
built, they are not up for removal, and this feature neither needs nor extends them. The real
question is not "does analysis need them" but "does analysis need **more** of them". For the cron,
the answer is a flat no: **this feature adds no scheduled job at all.** Nothing is fetched on a
timer, in bulk, or in anticipation of someone asking. Every recording this feature touches is
touched because a person clicked.

**2. Streaming on demand is the right trigger, and for own matches nothing is streamed at all.**
Analysing a recorded game means reading it once and deriving facts from it. For a match the
signed-in user played, the bytes are already in this service's own archive — analysis reads what 001
captured, and can be re-run at any time, for years. For anyone else's match, the bytes are fetched
from the source at the moment the user asks. So the user's instinct is right: **no anticipatory
sweep is needed, because the demand itself tells the system which matches matter.** That is what the
cron would have been for, and it is why there isn't one.

**3. What "streaming" does not settle is what happens to the bytes afterwards, and that is where the
whole cost sits.** Discarding them after the parse looks free and is not. Because this service
archives no third-party recording under 001, discarding would mean:

- The analyse CTA on a third-party match works for ~31 days after that match, and then never again —
  acceptable, and honestly displayable.
- **An analysis published from a discarded stream can never be re-derived.** If the parser later
  improves, or is found wrong, that result can be deleted but not corrected. Every viewer of that
  match sees a conclusion that nothing can check. Constitution IV forbids exactly this: a derived
  artifact must be fully recomputable from its raw. This is not a tension to note and move past — it
  is a principle violation, and it is what Q2 had to resolve.

**4. Archiving third-party recordings has three real costs, and they were accepted anyway.** The
alternative was weighed and taken (Q2, session 2026-08-23): a recording that is analysed **is**
retained. The reason is principle IV. The analysis is shown to every viewer of that match, and a
published conclusion that can never be checked or corrected is not a conclusion this project may
publish — and after ~31 days there is nothing left to check it against. The three costs do not
disappear because the decision went the other way; each becomes something the requirements must
control:

- **Privacy.** Constitution IX was amended for this (2.0.0, 2026-08-23). It now separates *automatic
  capture* — still the consenting user's own point of view, still never a side effect of browsing —
  from *user-initiated retention of an already-public recording*. What that costs is a new category
  of personal data, so FR-045 puts it in the processing register with its own legal basis, and
  FR-046 puts it inside the third-party objection route and erasure.
- **Growth driven by clicking rather than by playing.** Real, and now constitutionally required to be
  bounded: FR-047 caps it and rate-limits it. Storage volume must remain a function of deliberate
  human requests, never of traffic.
- **Competition with capture.** Unchanged and non-negotiable. FR-039 keeps principle I's ordering:
  where analysis and capture want the same budget, capture proceeds and analysis waits.

**Conclusion carried into the requirements**: analysis is on demand, computed at most once per match,
and it retains both its derived result and the recording it was derived from. It adds **no scheduled
job and no background sweep** — which was the actual question, and the answer to it is unchanged by
Q2. What grows is storage, bounded and on request; what does not grow is the cron table. Recordings
are still never fetched speculatively, and 001's archive still holds only consenting users' own
points of view. What this feature must also add is **honesty**: a recording that will stop being
fetchable must say so, with its date, before the user relies on it — FR-024, FR-025 and FR-034 exist
for that and for nothing else.

## Clarifications

### Session 2026-08-23

- **Q: How deep must the analysis output go?** A: a factual timeline only — build and training order,
  age-up times, resources and villager count at each age, technologies, units, and actions per
  minute, per participant. No judgment, no coaching, no benchmark comparison. A richer analysis is a
  later feature with its own spec; this one exists to prove the pipeline end to end and to put real
  facts on the page. Resolves FR-043.

  > **Amended 2026-08-23, after planning measured the artifact.** Resources and villager count are
  > **not in the recording** and were never readable: it is a command log, not a state log. They are
  > reconstructible from the command stream, and that reconstruction is now a **separate feature,
  > specified and built after this one** — it depends on this feature's extraction, on the recordings
  > FR-033 retains, and on a way to verify a derived number against the game itself. Recomputing the
  > analyses published in the meantime costs nothing and reaches no source, which is exactly what
  > FR-033 and FR-041 were decided for. Age-up times were also narrowed to age-up *commands*, for the
  > same reason. FR-043 is rewritten accordingly and FR-043b and FR-043c record the two rulings.
  > `specs/003-player-search-match-analysis/research.md` R1 and R5 carry the measurements.
  >
  > One question is left open for that feature to measure first: the parser knows an `Achievements`
  > post-game block, and the reference recording does not carry one. If current-patch ranked
  > recordings ever do, part of this is a read rather than a reconstruction.

- **Q: May a streamed third-party recording be persisted, given that constitution IV demands
  recomputability and IX limited capture to the consenting user?** A: yes — persist it, and amend the
  constitution. IV wins because the analysis is *published*: every viewer of that match sees it, and
  the source destroys the evidence after ~31 days, so not keeping the recording means standing behind
  a conclusion nobody can ever re-derive. Constitution IX was amended to 2.0.0 to draw the line in
  the right place: automatic capture stays consenting-user-only, while retention of an
  already-public recording is permitted when a human deliberately asks for that match to be
  analysed — bounded by requests, never by traffic. Resolves FR-033, and creates FR-045 to FR-047.

- **Q: Can player-name search use `aoe-api.worldsedgelink.com/game/account/FindProfiles`?** A: no,
  and this was measured rather than assumed (`docs/data-sources.md` §1, 2026-08-23). The route exists
  — it answers `401` where an invented `/game/` path answers `404` — but it sits behind a game-client
  session this project has no lawful way to obtain. No public name search exists on the primary
  source at all: two candidate `/community/` endpoints are `404`, and `getLeaderBoard2`'s
  `searchPlayer` parameter is silently ignored, returning the top of the ladder while reporting
  success.

- **Q: So which route does name search take?** A: `data.aoe2companion.com`, measured viable on
  2026-08-23 and recorded in `docs/data-sources.md` §3 — case-insensitive substring matching, ordered
  by games played, paginated, and 12 of 12 requests answered from a residential connection. It is
  chosen knowing it is the degradable source, because the alternatives are worse: a ladder-walked
  index needs a bulk read of the primary source and a refresh job, which is the cron this feature
  exists to avoid, and it still covers only ranked players. Two things make the risk acceptable —
  FR-004d gives search a fallback that needs no external source at all, and nothing else in the
  feature depends on search. Two things make it safe — FR-004b strips the account-linking fields the
  response carries, which would otherwise breach 001's FR-045 silently, and FR-004c honours a
  profile's hidden flag. Resolves FR-004.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find any player and see where they stand (Priority: P1)

A user types a player's name, picks them from the results, and lands on that player's profile: who
they are, and their current rating, rank and record on each ladder they play. Nothing else in this
feature is reachable without this.

**Why this priority**: it is the front door. Every other story in this feature starts from a profile
that is not the user's own, and there is no way to reach one today. On its own it already replaces
looking an opponent up on the official leaderboard site.

**Independent Test**: search for a known active player by name, open the top result, and confirm the
ratings shown match the official leaderboard for that player.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they search a player name that exists, **Then** matching
   players are listed with enough to tell them apart — name, country, and current standing.
2. **Given** a search that matches nothing, **When** the results come back, **Then** the user gets a
   clear empty state that distinguishes "no such player" from "search is unavailable".
3. **Given** any player's profile, **When** it is opened, **Then** their current rating, rank, wins
   and losses are shown for each ladder they have played.
4. **Given** the player-name search source is unavailable, **When** a user searches, **Then** they
   are told search is temporarily degraded and are still offered the routes that do not depend on it.
5. **Given** a searched player who has never played a ranked ladder, **When** their profile opens,
   **Then** it is a valid, explained profile rather than an error or a blank page.

---

### User Story 2 - Read any match without needing the recorded game (Priority: P2)

From a profile the user opens the match history — newest first, with the essentials — and clicks
into any match. The match page shows everything the service already knows about that game: every
participant, teams, civilisations, map, ladder, duration, result, rating change. None of it requires
the recorded game, so it works for matches of any age, including matches whose replay has long
expired.

**Why this priority**: it is what makes a profile worth visiting, and it is the page both CTAs live
on. It is also the part that never breaks with age, so it is what remains when everything else about
an old match is gone.

**Independent Test**: open a match from a third party's history that is older than the retention
window and confirm the page is complete and correct, with both CTAs correctly shown as unavailable.

**Acceptance Scenarios**:

1. **Given** any player's profile, **When** the user opens their match history, **Then** matches
   appear newest first with opponent, map, civilisation, result, rating change and duration.
2. **Given** any match in that history, **When** the user opens it, **Then** every participant is
   shown with their team, civilisation, result and rating change.
3. **Given** a match the signed-in user played themselves, **When** they open it, **Then** they see
   the same page, plus the archival state of their own replay.
4. **Given** a match whose identifiers this service cannot yet name — an unmapped civilisation, an
   unknown map — **When** it is displayed, **Then** the raw identifier is shown rather than a
   guessed name.
5. **Given** a player with no matches, **When** their history is opened, **Then** a clear empty
   state is shown.
6. **Given** the same match reachable from two different players' histories, **When** it is opened
   from either, **Then** it is the same match, presented identically.

---

### User Story 3 - Get the recorded game, from any player's point of view (Priority: P3)

On a match page, the user can download the recorded game. Because a recording exists once per
participant and each shows the game through that player's eyes, the page offers one per
participant — and states plainly which are still obtainable and until when.

**Why this priority**: it is immediately valuable, it is cheap, and it is the escape hatch that makes
the absence of analysis survivable — a user who can hold the file can always watch it in the game.

**Independent Test**: open a recent third-party match, download two different participants' points
of view, and confirm both files open in the game and show the game from the expected player's side.

**Acceptance Scenarios**:

1. **Given** a match inside the retention window, **When** the user opens it, **Then** a download is
   offered for each participant's point of view.
2. **Given** a match beyond the retention window, **When** the user opens it, **Then** the downloads
   are shown as no longer obtainable, with the reason and the date they stopped being available —
   not as a button that fails.
3. **Given** a match the signed-in user played and whose replay this service archived, **When** they
   download their own point of view, **Then** it is served from the archive and works regardless of
   the match's age.
4. **Given** a match the user played whose own point of view is archived but which is beyond the
   window, **When** they open it, **Then** their own point of view is offered and the other
   participants' are shown as expired — the difference is visible and explained.
5. **Given** a participant's recording that the source does not have, **When** the user requests it,
   **Then** they are told it was not obtainable, distinctly from "it expired".
6. **Given** a match still inside the window, **When** the user views it, **Then** the remaining time
   before its recordings stop being obtainable is shown.

---

### User Story 4 - Analyse a game, once (Priority: P4)

On the same match page, the user asks for the game to be analysed. The service reads the recorded
game once, derives what happened inside it, and shows it. Anyone who opens that match afterwards
sees the same analysis without it being computed again.

**Why this priority**: it is the feature with the most value and the most cost, it depends on the
match page existing, and — unlike everything above it — it is the one that can be delivered late
without the rest of the product feeling incomplete.

**Independent Test**: analyse a recent match, confirm the result appears; open the same match as a
different user and confirm the analysis is shown immediately and was not recomputed.

**Acceptance Scenarios**:

1. **Given** a match whose recording is obtainable and which has never been analysed, **When** the
   user asks for analysis, **Then** the analysis is produced and displayed for every participant.
2. **Given** a match that has already been analysed, **When** any user opens it, **Then** the
   existing analysis is shown immediately and nothing is fetched or parsed again.
3. **Given** an analysis that takes longer than a page load, **When** the user asks for it, **Then**
   they are shown its progress and can leave and come back rather than waiting on a frozen screen.
4. **Given** a match whose recordings have expired and which was never analysed, **When** the user
   opens it, **Then** analysis is shown as permanently unavailable with the reason, and is not
   offered as an action.
5. **Given** a recording that cannot be parsed, **When** analysis is attempted, **Then** the failure
   is recorded with its reason, the user is told plainly, and the match is not left claiming to be
   analysed.
6. **Given** many users asking for analyses at once, **When** the capture process needs the same
   resources, **Then** capture wins and analysis waits.
7. **Given** any analysis this service has published, **When** the parser is upgraded or found
   defective, **Then** that analysis can be recomputed from the recording kept alongside it, without
   fetching anything, however old the match is.
8. **Given** the cap on retained recordings has been reached, **When** a user requests a new
   analysis, **Then** they are refused with a clear reason, and capture is unaffected.

---

### User Story 5 - Keep the players I care about close (Priority: P5)

The user marks any player as a favourite and finds them again from one list, without searching.

**Why this priority**: pure convenience on top of US1, nothing depends on it, and it is the cheapest
thing in this feature. It ranks last on cost-to-value, not on desirability.

**Independent Test**: favourite two players, sign out and back in, and confirm both are listed with
their current standing and reachable in one click.

**Acceptance Scenarios**:

1. **Given** a signed-in user on any player's profile, **When** they mark that player as favourite,
   **Then** the player appears in their favourites list.
2. **Given** a favourited player, **When** the user unmarks them, **Then** they are removed and
   nothing else about that player changes.
3. **Given** a user with favourites, **When** they open their favourites list, **Then** each entry
   shows the player and their current standing and links to their profile.
4. **Given** a user who favourites a player, **When** anything about that player's recorded games is
   considered, **Then** nothing of theirs is captured or archived as a result of being favourited.
5. **Given** a visitor who is not signed in, **When** they try to favourite a player, **Then** they
   are asked to sign in and are returned to where they were.

---

### Edge Cases

- Two players share a display name, or a name differs only by case, accent or invisible characters.
- A searched player has since changed their in-game alias: the service holds the last one it
  observed and results may be stale.
- A user favourites a player who later disappears from the source entirely.
- A user favourites a profile that is one of their own linked profiles.
- A user favourites so many players that the favourites list itself becomes a bulk query against the
  source.
- A match page is opened for a match in which none of this service's users participated.
- A match is opened whose participants include a person who has exercised the third-party objection
  route from 001 (FR-039).
- A match sits within hours of the retention boundary: the CTA is offered, and by the time the user
  clicks it the source answers 404.
- A recorded game is published for some participants but not others.
- Two users ask for the same match to be analysed at the same instant.
- A user asks for analysis of a match already queued for analysis by someone else.
- An analysis is interrupted part-way — the platform's execution budget is exhausted, or the process
  dies mid-parse.
- The recorded game is well-formed but its contents are not what the parser expects (a new game
  version, a scenario, a restored game).
- A single match is very long or has many players, making its recorded game far larger than typical.
- The parser is upgraded and every existing analysis becomes stale at once.
- Search is used as a scraping tool: many distinct names queried in quick succession.
- The analyse CTA is used as a way to make this service hammer the replay source.
- A user with no linked profile at all — or not signed in — reaches a match page directly by URL.

## Requirements *(mandatory)*

### Functional Requirements

**Finding players**

- **FR-001**: Users MUST be able to find a player by their display name and reach that player's
  profile without knowing any numeric identifier.
- **FR-002**: System MUST present enough alongside each search result to distinguish players who
  share or nearly share a name — at minimum country and current standing.
- **FR-003**: System MUST distinguish, in the interface, "this search found nothing" from "search is
  currently unavailable", and MUST NOT present the second as the first.
- **FR-004**: System MUST continue to function when the player-name search source is unavailable:
  profiles, favourites, match pages and both CTAs MUST remain reachable by every route that does not
  begin with a name search. No public name search exists on the primary source
  (`docs/data-sources.md` §1), so search rests on a source the architecture requires to be optional;
  everything else in this feature MUST therefore stand without it.
- **FR-004a**: Name search MUST match case-insensitively and on partial strings, so that a user who
  remembers part of a name finds the player, and MUST order results so that the most-played matching
  player appears first.
- **FR-004b**: System MUST discard, at the point the search source is read, every field asserting a
  relationship between a player's accounts — and MUST NOT store, display or act on a third party's
  Steam identifier obtained this way. These fields exist in the response and carrying them further
  would breach 001's FR-045 by accident rather than by decision.
- **FR-004c**: System MUST honour a source-side signal that a profile is hidden, and MUST NOT present
  such a profile in results. Someone who has asked not to be listed has asked this service too.
- **FR-004d**: When the search source is unavailable, System MUST fall back to searching the profiles
  it has already observed — users, favourites, and participants of match histories it already holds
  (FR-011) — and MUST label those results as reduced rather than presenting them as complete. This
  fallback introduces no new source and no new request.
- **FR-004e**: System MUST cache search results, so that repeated and common queries do not become
  repeated calls against a source that is degradable by design.
- **FR-005**: System MUST rate-limit search per user, so that search cannot be used to enumerate the
  source at volume through this service.

**Any player's profile**

- **FR-006**: System MUST show, for any player, their current rating, rank, wins and losses on each
  ladder they have played.
- **FR-007**: System MUST show, for any player, their matches newest first, with opponents, map,
  civilisation, result, rating change and duration.
- **FR-008**: System MUST present a third party's profile using the same information and the same
  shapes as a user's own profile, so that one presentation serves both. This feature generalises
  001's FR-008, FR-010 and FR-011 from "the signed-in user's profile" to "any profile"; it MUST NOT
  create a second, divergent presentation of the same facts.
- **FR-008a**: This feature **supersedes 001's FR-038** and narrows it to what constitution IX
  actually requires. 001 read it as "no endpoint returns the history of a profile the caller does not
  own", which made a third party's profile unreachable even to a signed-in user; the constitution
  forbids third parties being *publicly indexed*, which is a different line. Any signed-in,
  allowlisted user MAY read any player's profile and history, and the four properties that replace
  001's rule MUST hold: no anonymous access to any route added here; no indexing, by response header
  and by `robots.txt`; no disclosure of a relationship between a player's accounts (FR-009); and
  ownership still deciding access to a user's own archived replay (FR-026). 001's cross-route test of
  the old reading MUST be rewritten against these four, never deleted — it is the only executable
  statement of a constitutional property, and a decision that retires a rule has to leave the reason
  where the next reader will find it.
- **FR-009**: System MUST NOT expose, on any player's profile, anything that reveals a relationship
  between that player's profile and any other profile that the owner has not proven by signing in
  (001 FR-045).
- **FR-010**: System MUST NOT allow a third party's profile page or search results to be publicly
  indexed (constitution IX).
- **FR-011**: System MUST preserve verbatim any source response it obtains that
  `docs/data-sources.md` classifies as irrecoverable — third-party match history above all — exactly
  as it does for a user's own (constitution III, 001 FR-012). Viewing a third party's history is
  therefore an act that permanently records their matches, and the third-party objection route (001
  FR-039) MUST cover data recorded this way.
- **FR-012**: System MUST NOT begin capturing, archiving or ingesting a third party's recorded games
  as a consequence of that player being searched, viewed, favourited or analysed. Capture remains
  what 001 defines it as: the consenting user's own point of view, and nothing else.

**Favourites**

- **FR-013**: Users MUST be able to mark any player as a favourite and to unmark them.
- **FR-014**: Users MUST be able to list their favourites and reach each one's profile in one step,
  with current standing shown per entry.
- **FR-015**: System MUST keep favourites private to the user who set them, and MUST NOT reveal to
  any player that they have been favourited, or by whom.
- **FR-016**: System MUST bound the number of favourites per user, so that rendering the list cannot
  become an unbounded query against an external source.
- **FR-017**: System MUST include favourites in the user's data export and erasure (001 FR-036,
  FR-037).

**Match page without the recorded game**

- **FR-018**: System MUST provide a match page reachable from any player's history that presents
  every participant with their team, civilisation, result and rating change, plus map, ladder, game
  version, start time and duration.
- **FR-019**: System MUST render the match page entirely from data that does not require the
  recorded game, so that it is complete for matches of any age, including matches whose recordings
  expired long ago.
- **FR-020**: System MUST show a raw identifier rather than a guessed name whenever its reference
  data cannot name one (002 FR-001 onward).
- **FR-021**: System MUST present the same match identically whichever player's history it was
  reached from, and MUST NOT create a second match record for it.
- **FR-022**: System MUST show, on a match the signed-in user took part in, the archival state of
  their own replay as 001 FR-027 defines it.

**Downloading the recorded game**

- **FR-023**: System MUST offer, per match, one download per participant point of view, since each
  recording shows the game from one participant's perspective.
- **FR-024**: System MUST show, for each offered point of view, whether it is currently obtainable,
  and for those that are, the date after which it will stop being — derived from the source's
  measured retention window in `docs/data-sources.md`, not from a value restated here.
- **FR-025**: System MUST distinguish and display, per point of view: obtainable now, held in this
  service's own archive, never recorded by the game, and expired beyond the source's retention
  window. It MUST NOT present an unobtainable download as an action that then fails.
- **FR-026**: System MUST serve the signed-in user's own point of view from this service's archive
  when it holds one, so that it remains available regardless of the match's age (001 FR-028).
- **FR-027**: System MUST NOT store a recorded game obtained solely to serve a download. Downloading
  is not analysing: retention under constitution IX is permitted only where a user deliberately asks
  for a match to be analysed (FR-033), and a download request is not that act.
- **FR-028**: System MUST rate-limit recorded-game requests per user, and MUST stop and raise an
  alert if the source signals throttling or refusal (001 FR-021).
- **FR-029**: System MUST log access to recorded games it serves from its own archive (001 FR-040).

**Analysing the game**

- **FR-030**: Users MUST be able to request the analysis of a match whose recorded game is
  obtainable, and MUST see the result for every participant.
- **FR-031**: System MUST analyse a given match at most once, and MUST serve the stored result to
  every subsequent viewer without fetching or parsing again.
- **FR-032**: System MUST record which point of view an analysis was derived from, and the version
  of the parser that produced it (constitution IV).
- **FR-033**: System MUST retain the recorded game it analysed, byte-for-byte with a checksum
  recorded at the time and verifiable on retrieval, for every analysis it publishes — third-party
  matches included. A published analysis that cannot be recomputed from its raw is forbidden by
  constitution IV, and the source destroys the raw after ~31 days, so the choice is between keeping
  the recording and publishing an unfalsifiable conclusion. Retained recordings are never modified, and are
  deleted only on an erasure or objection by a person **appearing in** the recording (FR-046).
  Erasing the user who *requested* the analysis clears who asked and keeps the bytes: a published
  analysis must stay recomputable (constitution IV), and the requester is not the subject of a third
  party's recording.
- **FR-034**: System MUST present analysis as permanently unavailable, with the reason, for a match
  whose recordings have expired and which was never analysed — never as an action that fails.
- **FR-035**: System MUST report progress for an analysis that outlasts a page load, and MUST let the
  user leave and return to it.
- **FR-036**: System MUST record a failed analysis with its reason, MUST tell the user plainly, and
  MUST NOT leave the match presented as analysed. A recording that cannot be parsed goes to the
  `failed` state with its full error class and message recorded (constitution V), never a silent
  failure. It needs no quarantine of its own: 001's `QUARANTINED` holds aside bytes that must survive
  for inspection, and here FR-033 already keeps them, so the evidence is preserved by construction.
- **FR-037**: System MUST resume cleanly from an analysis interrupted at any point, leaving no match
  stuck in an in-progress state.
- **FR-038**: System MUST treat concurrent requests to analyse the same match as one piece of work.
- **FR-039**: System MUST NOT let analysis consume the request budget, the quota or the execution
  window that replay capture depends on. Where the two compete, capture proceeds and analysis waits
  (constitution I).
- **FR-040**: System MUST rate-limit analysis requests per user, so that the CTA cannot be used to
  drive volume at the replay source through this service.
- **FR-041**: System MUST be able to recompute any analysis it has published, when the parser version
  changes or a parser defect is found, without re-fetching anything from the source. FR-033 is what
  makes this possible for matches whose recordings the source no longer has. The recompute is
  requested the same way a first analysis is, by a person opening that match; there is no sweep and no
  scheduled re-derivation (FR-044). Staleness is the comparison between a stored analysis's parser
  version and the running engine, computed on read.
- **FR-042**: System MUST run analysis in isolation from the API and the ingester, such that a parser
  failure degrades neither (constitution V).
- **FR-043**: The analysis MUST produce, per participant, a factual account of what that player did,
  and no judgment about it: the order in which they built and trained, with the time of each; the
  time at which they **ordered** each age-up; the technologies they researched, with times; the units
  they trained, with counts — and, of those, the count of villager training orders net of the
  cancellations the log itself carries, published under a name that says it counts commands and not a
  population (FR-043b); their actions per minute over the course of the game; and when they were
  defeated or resigned. It MUST NOT rank, grade, score, advise or compare players — those are a later
  feature with its own specification, and stating a judgment this feature cannot justify would be
  worse than stating nothing.
- **FR-043a**: System MUST show a raw identifier rather than a guessed name for anything the analysis
  surfaces that its reference data cannot name (002, FR-020). A new game version introducing unknown
  units or technologies MUST degrade to identifiers, never to invented names.
- **FR-043b**: The analysis MUST publish only what is read from the recording, and MUST NOT publish a
  quantity it reconstructed. A `.aoe2record` is a log of what each player **ordered**, never of what
  the game did in response, so resources and villager count are absent from it and are recoverable
  only by partial re-simulation. That derivation is deferred to its own feature (see the amendment
  note in Clarifications), because it needs training durations that vary by civilisation, cancellation
  handling, and a stated accuracy claim for the one thing the log can never carry — what combat
  destroyed. Publishing a reconstruction without that claim, to every viewer of a match, is the
  unfalsifiable conclusion Q2 was resolved to prevent.
- **FR-043c**: Where the analysis states a time derived from a research command, it MUST say that the
  action was **ordered** and MUST NOT claim the age was reached. The two differ by the research
  duration, which varies by game speed and civilisation and which no reference data in this
  repository holds. It MUST also collapse a command repeated by a double-click to one event.
- **FR-044**: System MUST add no scheduled job and no background sweep. Analysis is initiated by a
  person, on one match. Nothing is fetched speculatively, and no process walks matches nobody asked
  about — this is what keeps FR-039 satisfiable and is unchanged by FR-033.

**Obligations created by retaining third-party recordings (constitution IX, 2.0.0)**

- **FR-045**: System MUST record the retention of analysed third-party recordings in the processing
  register as its own processing purpose, with its own legal basis, retention and safeguards, in the
  same change that implements it.
- **FR-046**: System MUST make a retained recording reachable by the third-party objection route and
  by erasure (001 FR-037, FR-039), such that a person appearing in one can have it removed, and the
  analyses derived from it withdrawn with it.
- **FR-047**: System MUST cap the volume retained this way and MUST rate-limit the requests that
  cause retention, per user and in total, so that stored volume remains a function of deliberate
  human requests and never of traffic. On reaching the cap the system MUST refuse new analyses with
  a clear reason rather than degrade capture or grow without bound.
- **FR-048**: System MUST keep recordings retained under FR-033 distinguishable from replays captured
  under 001, so that the two never blur: they have different legal bases, different consent, and
  different points of view, and a report that counts them together would misstate both.

### Key Entities

- **Player profile**: as 001 defines it. This feature adds no attribute; it makes profiles of people
  who are not users reachable and presentable.
- **Favourite**: one user's private mark on one player profile, and when it was set. Carries no
  consequence for capture.
- **Match**: as 001 defines it. Shared by every participant, never duplicated per viewer.
- **Recorded game availability**: what is known about one participant's point of view of one match —
  whether it is obtainable from the source, held in this service's archive, never recorded, or
  expired, and the date it stops being obtainable. This is a *view* over what 001's replay capture
  and the measured retention window already establish, not a second record of the same truth.
- **Match analysis**: the derived result of parsing one match's recorded game once — which point of
  view it came from, which parser version produced it, when it ran, its state, and its outcome or
  its failure reason. Derived and disposable, because the recording it came from is kept.
- **Retained recording**: a recorded game kept because it was analysed — which match and point of
  view it is, where it is stored, its size and checksum, when and at whose request it was retained.
  Distinct from 001's replay capture in legal basis, consent and point of view, and never counted
  together with it (FR-048).
- **Analysis request**: the intent to analyse one match, so that concurrent askers share one piece of
  work and an interrupted run can be resumed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user goes from typing a player's name to reading that player's ratings in under 15
  seconds, without knowing any numeric identifier.
- **SC-002**: 95% of searches for a player who exists return that player among the top results, with
  a partial, wrongly-cased fragment of the name accepted as readily as the exact name.
- **SC-002a**: When the search source is unavailable, every route that does not begin with a name
  search still works, search itself still returns locally-known players, and the user is told the
  results are reduced — verified by exercising the feature with the source disabled.
- **SC-003**: A match page renders completely for 100% of matches present in a profile's history,
  including matches whose recordings expired, with no field left blank or wrong.
- **SC-004**: For 100% of matches shown, the availability stated for every point of view matches what
  the source actually answers at that moment; a download offered as available succeeds, and one
  offered as expired is not clickable.
- **SC-005**: A user can obtain any participant's point of view of a match inside the retention
  window in at most two actions from the match page.
- **SC-006**: A match is parsed at most once: for any match, the number of times its recorded game is
  fetched and parsed is 1, however many users view or request its analysis — except after a parser
  version change, where it is 1 again.
- **SC-007**: 90% of analyses of a typical ranked 1v1 complete within 60 seconds of being requested,
  and the user is never shown a frozen screen while one runs.
- **SC-008**: Zero replays are lost as a result of this feature: across any 30-day period, the number
  of consenting users' matches whose replay expired unarchived remains 0 (001 SC-001) while search,
  browsing and analysis are in use.
- **SC-009**: Storage attributable to this feature grows only with analyses actually requested by a
  person: searching, browsing a profile, opening a match and downloading a recording add 0 bytes, and
  total retained volume never exceeds the declared cap.
- **SC-009a**: 100% of published analyses can be recomputed from a recording this service holds,
  including analyses of matches whose recordings the source no longer serves, verified by
  recomputing a sample after a parser version change.
- **SC-010**: No scheduled job is added: the number of cron entries after this feature equals the
  number before it, and no process fetches a recording nobody asked for.
- **SC-011**: A user can tell, for any match they open, whether it can still be analysed and until
  when, without contacting support.
- **SC-012**: An erasure request removes the user's favourites along with everything else, verified
  by inspection (001 SC-008).
- **SC-013**: A parser failure on one match leaves the API and the ingestion process unaffected, and
  the match is visibly marked as failed rather than analysed.

## Assumptions

- **A recorded game from any one point of view contains the whole match.** The format is a
  deterministic command log covering every player, so one parse yields facts about all participants
  and analysis is per **match**, not per point of view. This halves nothing if it is false — it
  multiplies the work by the number of players — so it is recorded here as the assumption it is,
  to be verified against a real capture before planning commits to it. FR-032 records which point of
  view was used precisely so that a later correction is traceable.
- Third-party recorded games are public while they exist: the source applies no ownership check, only
  a real-participant check (`docs/data-sources.md` §2, measured 2026-08-19). Offering them surfaces
  already-public data; retaining one that a person asked to have analysed is permitted by constitution
  IX as amended to 2.0.0 on 2026-08-23, and by nothing before that version.
- Retention under FR-033 is bounded by human requests, so its volume is a product design question
  before it is a capacity question. At the measured sizes — ~0.87 MB for a ranked 1v1, ~2.5 MB for an
  eight-player game — the cap in FR-047 is what decides the bill, not the traffic.
- The ~31-day retention window and its consequences are as recorded in `docs/data-sources.md`. This
  spec deliberately restates no measured number; where a date or a deadline is shown to the user it
  is derived from that file.
- Whether the search source answers from the production platform's egress addresses is **not yet
  verified** — `docs/data-sources.md` §3 records it as open, alongside observed intermittent 403s
  from datacentre addresses. This is why FR-004d exists: if the answer turns out to be no, search
  degrades to locally-observed profiles and the feature still stands. It must be checked before
  search is presented as the primary route, not after.
- **That the search source signals a hidden profile at all is not yet verified.**
  `docs/data-sources.md` §3's measured record carries no such field. FR-004c, the
  `hidden_observed_at` column and the local fallback's honouring of it all depend on one, so it is
  measured (T301a) before Phase 3 rather than discovered during it. If the signal does not exist,
  FR-004c is re-decided, not implemented around.
- Search, favourites and browsing are available to signed-in users. Whether any of it is reachable
  without signing in is deferred: the beta allowlist (001 FR-005) makes the question moot for now.
- A third party's match history is read from the source on demand and is no deeper than the source
  provides. There is no backfill of other people's history.
- Reference data for naming maps, civilisations and ladders comes from what 002 establishes. Where it
  cannot name an identifier, the identifier is shown — this feature adds no naming of its own.
- Analysis is initiated by a person on one match. There is no queue that analyses matches nobody
  asked for, and no sweep. This is what keeps FR-039 satisfiable, and it is unchanged by the decision
  to retain what is analysed.
- The platform's per-execution budget is 300 s (`docs/adr/0002-hosting.md`). A single ranked replay
  is ~0.87 MB compressed, ~6.9 MB raw. Analysis of one match is expected to fit; a match that does
  not fit must fail visibly (FR-036) rather than silently truncate. **Measured during planning: it is
  memory and not time that binds.** The reference 1v1 parses in 0.58 s and peaks near 631 MB against
  a 2 GB ceiling, because every operation is materialised; an eight-player game carries roughly three
  times the operations. FR-036's visible failure is therefore a path that will run in production, not
  a formality.
- Comparing a player's analysis against a benchmark bracket is out of scope, as is any grading,
  scoring or advice. The historical corpus that would make a comparison meaningful has been empty
  since 2026-02 (`docs/data-sources.md` §4) and is recorded there as a V2 concern. A richer analysis
  is expected to be specified as its own feature; FR-043 is deliberately the floor, chosen so that
  the pipeline is proven end to end before anything is built on top of it.
- **The data-rights routes this feature leans on are not built yet.** FR-017 and FR-046 point at
  001's export, erasure and third-party objection (001 FR-036, FR-037, FR-039), which are that
  feature's US5 and are still open. FR-033 creates a new category of personal data, and constitution
  IX requires export and erasure from the MVP, so **001's US5 lands before this feature retains its
  first third-party recording.** Everything here that retains nothing — search, profiles, match pages,
  downloads and favourites — is unaffected and may proceed in parallel. Decided 2026-08-23.
- Nothing in this feature is commercial, and no game asset is redistributed (constitution X). The
  recorded game is the player's own game data, served from or pointed at the publisher's own source.
