# PrivacyNotice

**Component**: `src/components/PrivacyNotice/`
**Feature**: 001, US5 — built by T095, composed by `apps/web/src/routes/privacy-notice.tsx`, linked
from `ArchivalControl`'s `PrivacyNoticeLink` and from the footer (T098a)
**Requirements**: FR-041 (the notice itself), and it discloses FR-006, FR-016, FR-034 to FR-040,
FR-042, FR-045; 003's FR-004b, FR-010, FR-017, FR-027 to FR-029. Constitution IX and X.
**Depends on**: [`shared-primitives.md`](./shared-primitives.md) — `Callout`, `Button`.
**Sources of truth this copy is derived from, and must not contradict**:
`docs/privacy/processing-register.md` (categories, bases, retention, recipients, the balancing
tests), `apps/api/src/aoe2stats_api/routers/privacy.py` (what the export, erasure and objection
routes actually do), `packages/storage/src/aoe2stats_storage/models.py` (what columns exist and what
cascades on erasure), `docs/data-sources.md` (the outside services and the source retention window),
`docs/adr/0002-hosting.md` (the processors).

**Path note.** T095's text says `packages/design-system/src/PrivacyNotice/`. Every other component
in this package lives under `src/components/`, and `packages/design-system/specs/README.md`'s index
column is written against that layout. This spec specifies `src/components/PrivacyNotice/`; the
divergence is a slip in the task text, not a decision, and building it anywhere else makes this the
one component the package's own barrel and story glob do not reach the same way as the rest.

**Why a design-system component and not page markup.** T093's own reasoning: constitution VI admits
no unstoried component, and this notice and the footer disclaimer are the only two pieces of copy in
the product carrying a legal obligation. A legal text that no story renders is a legal text no
visual review ever looks at, and the failure mode — a paragraph silently lost in a route refactor —
leaves no test red.

**This component states the law of the product, so it is normative in a stronger sense than any
other spec here.** §4 is not a suggested wording. A change to §4 is a change to what this service
claims about itself, and it may only be made together with the change to
`docs/privacy/processing-register.md` that makes it true — in the same PR, in that order of
reasoning: the register describes the processing, this file describes the register, the component
renders this file. A copy edit that reaches this file first has inverted the chain.

## 1. Purpose

Tell a person — user or not — everything this service holds about them, where it came from, on what
legal basis it is held, for how long, and the exact control that stops, exports or erases it, in one
page that is readable without a lawyer and without a click.

## 2. Anatomy

```
PrivacyNotice                       <article aria-labelledby>
├─ Header
│  ├─ Title                         h1 — "Privacy notice"
│  ├─ LastUpdatedLine               the date this text last changed
│  └─ Lede                          three sentences; the whole notice in brief, never a substitute
├─ ChangeNote           ×0..1       Callout/info — what changed since the previous version
├─ Contents                         <nav> + ordered list, one entry per Section, in-page links
├─ Section              ×9          each an h2 with a stable id
│  ├─ 1 Who we are and what this is
│  ├─ 2 What we collect
│  │  └─ CategoryEntry  ×8          h3 + DefinitionList (Where it comes from / Why we have it /
│  │                                Legal basis / How long we keep it)
│  ├─ 3 Cookies
│  ├─ 4 Where it is stored, and who else touches it
│  │  ├─ ProcessorList              one line per processor: name, role, where
│  │  └─ OutwardCallList            one line per outside service we send something to
│  ├─ 5 How long we keep it
│  ├─ 6 Your rights, and the control that exercises each one
│  │  └─ RightsItem     ×6          h3 + what it does + what it does not do + the control
│  ├─ 7 If you are not a user of this service
│  │  └─ ObjectionCallToAction      Button/secondary → the objection route, outside the session
│  ├─ 8 What we do not do
│  └─ 9 How to reach us
│     └─ ContactBlock | ContactUnpublished        the empty state, §5
└─ RegisterLink         ×0..1       link to the public processing register, when a href is supplied
```

**`CategoryEntry` is a definition list, not a table**, and this is a decision rather than a
convenience. Five columns of prose cannot be read at 375px without either horizontal scrolling or
truncation, and both are forbidden here: a retention period a reader has to scroll sideways to find
is a retention period that was not disclosed. One DOM at every viewport — an `h3` and a four-term
`<dl>` — means there is no second, hidden copy of the legal text for a screen reader to double-read
or for a find-in-page to miss. §8 says how the `<dl>` gains table-like alignment from `md` up
without becoming a table.

`Contents` is not decoration. This page is long by obligation, and the one question a reader arrives
with — "how do I get my data out" or "how do I make it stop" — must be reachable in one click from
the top of the frame.

## 3. Variants, sizes and props

**One variant. There is deliberately no `summary` or `short` variant.** A condensed second version
of a legal text is a second version that will disagree with the first, and there is no test that can
catch the disagreement. Where a shorter statement is needed at the point of decision, the component
that owns that decision carries its own normative copy and links here — `ArchivalControl` §4.2 is
exactly that, and it is not a subset of this file, it is the block FR-034 requires at linking time.

**One size.** The notice renders at body size everywhere; there is no compact form. See §8 for what
changes with viewport, which is layout only, never which paragraphs exist.

```ts
interface PrivacyNoticeProps {
  /** ISO date (YYYY-MM-DD) this text last changed. Build-time constant, never fetched. */
  lastUpdated: string
  /** Where each right is exercised. `objectionForm` is required: FR-039's "a way to object". */
  hrefs: {
    archivalControl: string // the profile page carrying ArchivalControl's switch
    privacyRoute: string // the route with the export and erasure controls
    objectionForm: string // the route outside the session (T095's /object)
    processingRegister?: string // optional; renders RegisterLink when present
  }
  /** Non-empty. Who processes the data on our behalf, and where. Defaults to PHASE_1_PROCESSORS. */
  processors?: readonly [Processor, ...Processor[]]
  /** Absent today. Its absence is a rendered state, not a hidden section — see §5, empty. */
  controllerContact?: { name: string; postalAddress?: string; contactRoute: string }
  /** Renders the analysis-retention CategoryEntry and the erasure caveat that goes with it. */
  showsAnalysisRetention?: boolean // default true
  /** What changed since the previous version, when there is a previous version. */
  changeNote?: { heading: string; body: string; date: string }
}

interface Processor {
  name: string
  role: string // "runs the website and the API", "stores the database", ...
  location: string // must be an EU location; constitution IX
}
```

There is no `loading` prop, no `error` prop and no data-fetching prop of any kind. §5 says why that
is a requirement and not an omission.

`showsAnalysisRetention` exists because the retention of an analysed recording is live code in
`apps/analyzer` while `docs/privacy/processing-register.md` still carries no activity row for it
(003's T369, open at the time of writing). The flag is not a licence to hide the paragraph: it
defaults to `true`, the copy in §4.2 is written as a conditional ("if you ask us to analyse a
match…") so it is true whether or not any recording has yet been retained, and setting it to `false`
is only correct for a deployment where match analysis does not exist at all. Whoever closes T369
deletes this prop and makes the entry unconditional; that is the intended end state.

## 4. Copy

Normative. The implementer copies these strings. A change happens in this file first, and only
alongside the register change that makes it true.

**The one measured number in this copy** is the source's replay retention window, in §4.2's "Your
recorded games". It is the same sentence `archival-control.md` §4.2 ¶2 already carries, and both
derive from `docs/data-sources.md` §2. If that measurement changes, both copy blocks change in the
same PR. No other number from `docs/` is restated anywhere in this file.

**Banned throughout §4**, each checkable in review:

- Reassurance in place of fact: "we take your privacy seriously", "your privacy is important to us",
  "rest assured", "industry-standard security", "military-grade encryption", "we've got you
  covered".
- "Anonymous", "anonymised", "anonymisation" for anything this service does. It pseudonymises, and
  constitution IX says in terms that the pseudonym is re-identifiable. Using the wrong word here is
  a legal claim, not a synonym.
- "We may share your data with trusted partners", or any sentence whose subject is a partner this
  notice cannot name.
- Any promise of a route that does not exist: "email us", "contact support", "we'll get back to
  you", "reset your password", "verify your email". There is no email address anywhere in this
  system.
- Hedged retention: "for as long as necessary", "for a reasonable period", "in accordance with our
  retention policy". Every entry in §4.2 states an actual end condition.
- Cookie-banner vocabulary: "we use cookies to improve your experience", "accept all", "manage
  preferences". Two strictly necessary cookies do not get a consent theatre.
- A shield, lock, tick or padlock icon anywhere in the component. An icon that reads as a safety
  badge reframes a disclosure as a reassurance.

### 4.1 Header

`Title`: **Privacy notice**

`LastUpdatedLine`: _Last updated {lastUpdated}._ Rendered unambiguously — "30 August 2026", never
`30/08/2026` and never `08/30/2026`.

`Lede`, three sentences, always visible above the contents:

> This service keeps your Age of Empires II profile, your match history and the recordings of your
> own games, so that they still exist after the game deletes them. It has no password and no email
> address for you, and it never sells or shares any of this. Everything below says what is held, why
> we are allowed to hold it, for how long, and the button that stops or removes it.

### 4.2 Section 2 — What we collect

`SectionHeading`: **What we collect**

Lead-in: _Eight kinds of thing, each with where it came from, why we have it, what allows us to hold
it, and when it goes._

Each `CategoryEntry` below gives the four terms in this order: **Where it comes from**, **Why we
have it**, **Legal basis**, **How long we keep it**. No entry may render with a missing or blank
term.

**1. Your sign-in and your account**

- Where it comes from: your Steam sign-in.
- Why we have it: to know that this account is yours, and to keep you signed in.
- Legal basis: performing the service you asked us for (GDPR Art. 6-1-b).
- How long we keep it: until you erase your account.
- Body: _We keep your Steam account number, taken from the identifier Steam verifies for us — we
  check that identifier and never store it. With it: your Age of Empires II profile id, an opaque
  session identifier, the dates you signed in, and the date you were let into the closed beta. There
  is no password and no email address here. We never asked you for either, so there is neither to
  store, to leak, or to reset._

**2. Your matches and your ratings**

- Where it comes from: the game's official API.
- Why we have it: to show you your stats and your match history.
- Legal basis: performing the service you asked us for (GDPR Art. 6-1-b).
- How long we keep it: until you erase your account.
- Body: _Your profile id, alias, country, and — per leaderboard — your rating, rank, wins, losses,
  streak and highest rating. One rating snapshot a day, so a rating curve can be drawn; snapshots
  are only ever added, never rewritten. And the details of each match: map, civilisation, team,
  colour, result, rating change, duration, and when it started and ended._

**3. Your recorded games**

- Where it comes from: the game's own replay service.
- Why we have it: the game deletes them, and then they are gone for everyone.
- Legal basis: our legitimate interest in saving them before that happens (GDPR Art. 6-1-f). You can
  object at any time — see "Your rights".
- How long we keep it: until you erase your account. There is no other expiry.
- Body: _Age of Empires II deletes your replay files about 31 days after the match. After that
  nobody can get them back — not you, not us, not Microsoft. So we download the recording of each of
  your matches, from your own point of view, and keep the original file unchanged. A recording
  contains your actions, your alias, and whatever was typed in the in-game chat during that match.
  We only ever take your own point of view, never another player's. If you object to this, we also
  keep the date you objected._

**4. Other players who appear in your matches**

- Where it comes from: the game's official API, and the recordings we hold.
- Why we have it: a match cannot be split per player, and neither can a recording.
- Legal basis: our legitimate interest, over data the game already publishes (GDPR Art. 6-1-f).
- How long we keep it: as long as the match or the recording it belongs to.
- Body: _For everyone in a match you played: profile id, alias, country, civilisation, team, colour,
  result, rating and rating change — all of it already published by the game on its own public
  leaderboards. Inside a recording we hold, their in-game actions and chat are in the file too,
  because a recording cannot be separated per player. We never capture another player's own point of
  view, and we never put a profile page or a search result into a public listing or a search engine.
  If a signed-in user asks to watch one specific point of view of a match we know about, we fetch it
  from the game's service and pass it straight through without keeping a copy._

**5. Searching for a player by name**

- Where it comes from: you type the name; a third-party public search service answers.
- Why we have it: nothing we hold is indexed by name for a player we have never seen in a match.
- Legal basis: our legitimate interest (GDPR Art. 6-1-f).
- How long we keep it: a cached answer goes stale quickly and is deleted when a later search
  overwrites it. There is no scheduled clean-up, so a row can outlive its staleness if no later
  search happens.
- Body: _The text you type is sent to `data.aoe2companion.com`, a public search service we do not
  run. What comes back is cached under the text of the query and never under who typed it, so this
  cache cannot answer "who searched for this player". A result carries a Steam account number that
  the source itself publishes beside a profile; we show it exactly as an unverified claim by that
  source, and we never use it to link, merge or treat two profiles as the same person. Only a
  completed Steam sign-in does that. Neither erasing an account nor objecting reaches this cache —
  it is keyed to nobody, and we are saying so rather than implying it is covered._

**6. Opening a recording we hold**

- Where it comes from: generated here, when the file is opened.
- Why we have it: these files contain other people's gameplay and chat, so who opened one is worth
  keeping.
- Legal basis: our legitimate interest in being able to show that access is limited and auditable
  (GDPR Art. 6-1-f).
- How long we keep it: deleted together with the recording it describes, including when you erase
  your account.
- Body: _Which recording was opened, by whom, when, and what for. A point of view we fetch and pass
  straight through without storing is not logged this way, because there is no stored file for a
  later, unrecorded read to reach._

**7. The requests you make under this notice**

- Where it comes from: you, through the export, erasure and objection controls.
- Why we have it: it is the proof that your request was carried out.
- Legal basis: our legal obligation under GDPR Articles 15 to 21 (Art. 6-1-c).
- How long we keep it: indefinitely, on purpose — including after an erasure it documents. The link
  to your account is removed; the record that the request was made and resolved stays.
- Body: _What kind of request it was, which account or profile it concerned, when it was asked for,
  and when and how it was resolved. This is the one thing an erasure deliberately leaves behind, and
  it exists so that the erasure can still be shown to have happened._

**8. Matches you ask us to analyse** — rendered when `showsAnalysisRetention` is true.

- Where it comes from: the game's replay service, when you ask for that match to be analysed.
- Why we have it: an analysis published to everyone who opens that match has to stay checkable.
- Legal basis: our legitimate interest, over a recording already public at its source (GDPR
  Art. 6-1-f).
- How long we keep it: indefinitely. **This one is not deleted by erasing your account, and not by a
  third-party objection.**
- Body: _If you ask us to analyse a match, we keep the recording the analysis was computed from. The
  game deletes its own copy after about a month, so throwing ours away would mean publishing a
  conclusion nobody could ever check or correct again. Erasing your account removes the record that
  you were the one who asked; it does not delete the recording, and the recording is never modified,
  because modifying it would break both its checksum and the reason for keeping it. We are stating
  this as the decision it is, not claiming the file stops being about anyone._

### 4.3 Section 3 — Cookies

`SectionHeading`: **Cookies**

> Two, both strictly necessary, neither of which asks you anything. One keeps you signed in. The
> other lives for a few minutes during sign-in and exists only to make sure the trip to Steam and
> back is really yours. There is no advertising cookie, no analytics cookie and no third-party
> tracker on this site, which is why there is no cookie banner to dismiss.

**Before this paragraph ships, and on every later change to `apps/web`**, the last sentence must be
verified rather than assumed: no analytics, error-reporting or tag-manager script in
`apps/web/index.html` or its dependencies. If one is ever added, this paragraph changes in the same
PR, and so does the register.

### 4.4 Section 4 — Where it is stored, and who else touches it

`SectionHeading`: **Where it is stored, and who else touches it**

> Everything is stored in the European Union, and nothing here is sold, shared or handed to anyone
> for their own purposes. Three companies handle it on our behalf, because we do not own servers:

`ProcessorList` — one line each, from the `processors` prop. The phase-1 default:

| Provider   | Role                         | Where          |
| ---------- | ---------------------------- | -------------- |
| Vercel     | runs the website and the API | Paris, France  |
| Neon       | stores the database          | European Union |
| Cloudflare | stores the recordings (R2)   | European Union |

> They act on our instructions and for nothing else. If we ever move this service to different
> hosting, this list changes here first.

`OutwardCallList` lead-in: _We also send requests out to three services that we do not run, and this
is everything we send them:_

| Service                                        | What we send                        | Why                                     |
| ---------------------------------------------- | ----------------------------------- | --------------------------------------- |
| The game's official API (`worldsedgelink.com`) | your profile id, or your Steam id   | your profile, ratings and match history |
| The game's replay service (`aoe.ms`)           | a match id and a profile id         | to download a recording                 |
| `data.aoe2companion.com`                       | the name text you typed in a search | to find a player by name                |

> Your Steam sign-in itself happens at Steam, not here: we send you there and Steam tells us which
> account came back. We never see your Steam password.

### 4.5 Section 5 — How long we keep it

`SectionHeading`: **How long we keep it**

> Each entry above states its own end condition, and this is the summary of them. Almost everything
> we hold about you ends when you erase your account: the account itself, the sign-in records, the
> profile links, your favourites, the match records that name you, and every recording of yours we
> have stored, including the files themselves in storage.
>
> Three things deliberately outlive that, and each one is named above rather than buried here. The
> matches themselves survive, with your profile id replaced by a pseudonymous one, because they are
> other players' match records too. The record of your erasure request survives, without the link to
> your account, because it is the proof the erasure happened. And a recording kept for an analysis
> you asked to be published survives, because the analysis it produced has to stay checkable.
>
> We do not delete anything on a timer. Nothing here expires quietly on its own, except a cached
> search result, which is overwritten by a later search.

### 4.6 Section 6 — Your rights, and the control that exercises each one

`SectionHeading`: **Your rights, and the control that exercises each one**

Lead-in: _Each of these is a control in this product, not a request form. Where a right has a limit,
the limit is written under the right and not somewhere else._

Each `RightsItem` renders a heading, **What it does**, **What it does not do**, and the control.

**Stop us archiving your recordings** (GDPR Art. 21)

- What it does: stops every future capture of your recordings, from the moment you press it, and
  records the date you objected.
- What it does not do: it does not touch your match history or your ratings, which keep updating; it
  does not delete recordings already archived; and it does not go back and capture what was missed
  once you resume.
- Control: **Object to archival**, on your profile page. You can resume at any time, with one press.

**Get a copy of everything** (GDPR Art. 15 and Art. 20)

- What it does: builds a single archive containing your account record, your Steam identities, every
  profile link you have ever held, the match records and per-player rows for those profiles, your
  archived recordings as the original files, your favourites, and the analyses you asked for.
- What it does not do: it does not include the cached search results described above, which are
  keyed to nobody, and it does not include the internal counters that rate-limit the API.
- Control: **Export my data**, on the privacy page. When it is ready you get a download link, which
  stops working after a short while — start a new export if it does.

**Erase your account and everything attached to it** (GDPR Art. 17)

- What it does: deletes your account, your Steam identities, your sessions, your profile links, your
  favourites, your archived recordings — the files in storage, not just the rows pointing at them —
  and the access records for them. Your session stops working on the very next request.
- What it does not do: it does not delete the matches themselves. Your profile id in them is
  replaced by a pseudonymous one, so the other players' records stay correct. That is
  pseudonymisation, not anonymisation: we are not claiming the result stops being about anyone. It
  also leaves the record that you asked for the erasure, and any recording kept for an analysis you
  asked to be published.
- Control: **Erase my account**, on the privacy page. It asks you to confirm, and then it is done.
  **There is no undo, and no backup we can restore you from.**

**Correct something that is wrong** (GDPR Art. 16)

- What it does: nothing on our side, and this is the honest answer. Your alias, country, rating and
  match results are not written by us — we read them from the game's own services. Correcting them
  there is what changes them here, on the next update.
- What it does not do: we will not edit a match record, a rating or a recording to say something
  different from what the game reported. A stats tool that lets its numbers be edited is not one.
- Control: none here, by design.

**Restrict processing, or anything else in Articles 15 to 22**

- What it does: the controls above cover getting a copy, stopping the archiving and erasing
  everything, which is the whole of what this service can do to your data. Anything else goes to
  the controller.
- What it does not do: it does not go through an automated route, because there is not one.
- Control: see "How to reach us" at the end of this notice.

**Complain about how we handle this**

- What it does: you can complain to your national data protection authority. That right does not
  depend on us, and using it does not require asking us first.
- What it does not do: it does not replace the controls above, which are faster.
- Control: your own supervisory authority.

Closing line of the section: _Nothing here makes an automated decision about you that has a legal
effect or anything similar. We compute statistics from your matches; we do not rank, score or judge
you with a consequence attached._

### 4.7 Section 7 — If you are not a user of this service

`SectionHeading`: **If you are not a user of this service**

> You may appear here without ever having signed in: you played a match against someone who did, and
> the game publishes that match. What we hold about you is the public part of that match — profile
> id, alias, country, civilisation, team, colour, result, rating and rating change — and, inside the
> recording that user's own game produced, your in-game actions and chat.
>
> You can object. The form asks for the profile id you want acted on and nothing else: no account,
> no sign-in, no email address, because we have no way to ask you for one and no way to answer you.
>
> What happens then: your objection is recorded with its date. A person reads it and acts on it
> within 30 days, replacing your profile id in our match records with a pseudonymous one, so that
> what remains no longer names you.
>
> What it does not do: it does not delete the matches, which are other players' records too, and it
> does not delete or alter a recording. It does not reach a cached search result, for the reason
> given above. And, again, this is pseudonymisation and not anonymisation — the record still
> describes a game somebody played.

`ObjectionCallToAction`: a `Button/secondary` labelled **Object to what is held about me**, linking
to `hrefs.objectionForm`. This control is on the page whether or not anyone is signed in.

### 4.8 Section 8 — What we do not do

`SectionHeading`: **What we do not do**

A list, each item one line:

1. We do not sell your data, and we do not share it with anyone outside the three providers named
   above.
2. We do not show advertising and we make no money from this service at all.
3. We do not publish or index profile pages or search results. Nothing here is meant to be found by
   a search engine looking for a person.
4. We do not store a password or an email address, and there is no password reset, no email
   verification and no account recovery. Your Steam account is the only way in. The consequences of
   that are stated in full where you link a profile, and they are not softened here.
5. We do not offer a way to hide your matches inside this service. Every field the game's own APIs
   serve is public, and we keep it that way rather than pretending we can make it private.
6. Where the game itself withholds data — a player who has switched off its "Shared History"
   setting — we do not go around it by another route. We also do not treat that setting as a request
   addressed to us, because it is not one.
7. We do not treat an unverified Steam account number published beside a profile as proof that two
   profiles are the same person, and no feature acts on it.

Item 4 states the data fact and stops. The full FR-006 statement — that access cannot be restored by
any route — has exactly one normative home, `archival-control.md` §4.1, and is shown where a user
links a profile. Restating it in full here would create a second copy of a banned-phrase-checked
block, which is how one of the two comes to be edited alone.

### 4.9 Section 9 — How to reach us, and its empty state

`SectionHeading`: **How to reach us**

**With a published contact** (`controllerContact` present):

> The controller for everything described here is {name}. {postalAddress}. To reach us about
> anything this notice does not have a button for, use {contactRoute}.

**Without one** (`controllerContact` absent — the state today):

> **We have not published a contact address yet.** This service is in closed beta and is not open to
> the public. Contact details for the controller will be published in this section before it opens,
> and that is a condition of it opening, not a task left for later.
>
> Until then the controls above are the whole of what is available: object to archival and export or
> erase your data from inside the product, or object through the form above if you are not a user.
> If you want something those do not cover, there is no route here yet, and we would rather say so
> than print an address that reaches nobody.

This block is **never** omitted, collapsed or replaced by silence. A privacy notice whose contact
section is absent reads as an oversight; one that says the address is not published yet, and why, is
a disclosure. It is also the visible trace of an open commitment in
`docs/privacy/processing-register.md` ("Record controller identity and contact details"), which is
where it gets closed.

### 4.10 Change note

`ChangeNote` (`Callout/info`), rendered only when `changeNote` is supplied: heading names what
changed, body says what it means for the reader, and the date is the date of that change.

> _We have no email address for you, so we cannot tell you when this notice changes. The date at the
> top is the date it last did, and a change worth noticing appears here._

That sentence sits in the header, under `LastUpdatedLine`, whether or not a `ChangeNote` is present.

## 5. States

**default** — the whole notice as anatomised, every section rendered, nothing collapsed. No
accordion, no "read more", no truncation with an expander anywhere in this component at any
viewport. The page is allowed to be long.

**hover** — inline links and `Contents` entries only: the link colour moves to `accent-hover` and
the underline stays (it was never absent). `ObjectionCallToAction` hovers as `Button/secondary`. No
other part of this component responds to a pointer.

**focus-visible** — the standard ring (`outline-2 outline-offset-2` in `focus-ring`, gap DS-4) on
every link and on the objection button. Following a `Contents` entry moves focus to the target
`<h2>`, which carries `tabindex="-1"` for that purpose — a jump that moves the viewport without
moving focus leaves a keyboard user at the top of a nine-section document.

**active** — links render in `accent-active` while pressed. Nothing translates or scales.

**disabled** — **nothing in this component is ever disabled.** A right that is described and then
greyed out has been withdrawn without saying so. If a target route is unavailable, the link is still
a link and the text still states the right; the failure belongs to the route the user lands on,
which has its own error state, not to the sentence that promised the right. `hrefs.objectionForm` is
required rather than optional for the same reason: a build in which FR-039's route has no address is
a build that should not compile, not one that renders a dead paragraph.

**loading** — **none, and this is a requirement.** The component takes no data-fetching prop, renders
no `Skeleton`, and must be fully readable at first paint before any network call resolves. A privacy
notice that waits on an API is a privacy notice that can fail to exist, and the one screenshot that
would catch it is the one nobody takes on a slow connection. `lastUpdated` is a build-time constant
for exactly this reason.

**error** — none of its own; there is nothing here that can fail. The two error surfaces a reader
might expect belong elsewhere: an export or erasure that fails renders its error on the privacy
route, and a failed objection renders on the objection form. This component keeps stating what the
rights are while either of those is broken, which is correct — the right exists even when the button
is having a bad day.

**empty** — one, and it is real: `controllerContact` absent renders `ContactUnpublished` per §4.9.
`changeNote` absent renders nothing at all, per `Callout`'s own empty rule — an empty bordered box
at the top of a legal document reads as a paragraph that failed to load. `processors` is required
and non-empty in the type: an empty list is a call-site defect, not a state, and the component must
not paper over it by silently substituting a default it was not given — a storage section that
renders with no processors would be claiming nobody touches the data.

## 6. Tokens used

Colour: `surface` (the document), `surface-raised` (`ChangeNote`, `ContactBlock` and
`ContactUnpublished`), `border` (section separators, list rules), `text-primary` (all body copy,
every heading, every `<dd>` value), `text-secondary` (`LastUpdatedLine`, the `<dt>` labels in a
`CategoryEntry`, table column headers), `accent` (inline and `Contents` links, on `surface` only —
see the DS-9 note below), `accent-hover`, `accent-active`, `info` (`ChangeNote` stripe and heading,
via `Callout`), `focus-ring`. No `danger`, no `warning`: nothing in this notice is an alarm, and
colouring the erasure paragraph red would make a right look like a hazard.

Typography: family `sans` throughout; `display` for the `h1` only. Sizes — `h1` `3xl` (`2xl` below
`md`); section `h2` `xl`; `CategoryEntry` and `RightsItem` `h3` `lg`; body, `<dd>` values and list
items `md`; `<dt>` labels `sm`; `LastUpdatedLine` and the register link `sm`. Weights — `semibold`
on every heading and on every `<dt>` label, `medium` on the bolded lead phrase of a `RightsItem`
("What it does", "What it does not do"), `normal` on body. Tracking `normal` everywhere; nothing in
this component is a number that needs `tight`.

Radius `lg` on `ChangeNote` and the contact block, `md` on the objection button. Elevation `none`
throughout — this is a document, not a stack of cards, and a shadow around a section reads as a
widget the reader can dismiss.

Motion: `duration.fast` + `easing.standard` on link colour and on the objection button only. In-page
navigation from `Contents` scrolls with the browser's own smooth behaviour and falls back to an
instant jump under `prefers-reduced-motion: reduce`, where every transition here becomes
`duration.instant`. **No entrance animation anywhere.** Text that fades in is text that can be
scrolled past before it exists.

Gaps in play: **DS-4** (focus ring width and offset), **DS-6** (reading measure — this is the
longest prose in the product and needs one), **DS-5** (breakpoints), and **DS-9**, added by this
spec to the README's gap register: there is no link colour role, and `accent` on `surface-raised` is
not in the measured contrast table. Until DS-9 closes, this component paints **no link on
`surface-raised`** — the contact block and the change note contain no inline links, and the contact
route in `ContactBlock` renders as `text-primary` with a permanent underline rather than as `accent`.

## 7. Spacing

| Between                                          | Step                                                                             |
| ------------------------------------------------ | -------------------------------------------------------------------------------- |
| Document padding                                 | `space-6` below `md`, `space-8` from `md`                                        |
| `h1` to `LastUpdatedLine`                        | `space-2`                                                                        |
| `LastUpdatedLine` to `Lede`                      | `space-4`                                                                        |
| `Lede` to `ChangeNote` (or to `Contents`)        | `space-6`                                                                        |
| `ChangeNote` to `Contents`                       | `space-6`                                                                        |
| `Contents` to the first `Section`                | `space-8`                                                                        |
| Between `Section`s                               | `space-12` — the widest gap in the document; a reader must feel a subject change |
| Section `h2` to its lead-in                      | `space-3`                                                                        |
| Between paragraphs inside a `Section`            | `space-4`                                                                        |
| Between `CategoryEntry` blocks                   | `space-8`                                                                        |
| `CategoryEntry` `h3` to its `<dl>`               | `space-3`                                                                        |
| Between `<dl>` term/value rows                   | `space-2`                                                                        |
| `<dl>` to the entry's body paragraph             | `space-4`                                                                        |
| Between `RightsItem` blocks                      | `space-8`                                                                        |
| `RightsItem` `h3` to its first line              | `space-3`                                                                        |
| Between the three lines of a `RightsItem`        | `space-3`                                                                        |
| Between `ProcessorList` / `OutwardCallList` rows | `space-3`                                                                        |
| Between numbered items in "What we do not do"    | `space-3`                                                                        |
| Contact block padding                            | `space-5`                                                                        |
| Last `Section` to `RegisterLink`                 | `space-8`                                                                        |
| `Contents` entry padding-block                   | `space-3` — with the `md` line-height this clears the 44px touch minimum         |

## 8. Responsive

- **375** — one column, full width less the document padding. Every `CategoryEntry` `<dl>` stacks:
  label above value, both left-aligned. `ProcessorList` and `OutwardCallList` stack the same way,
  one labelled block per row. **No horizontal scrolling anywhere, at any width, ever** — a retention
  period reachable only by scrolling sideways has not been disclosed. `Contents` is a full-width
  list of tap targets. `ObjectionCallToAction` is full width.
- **768** — text column capped at a 60 to 75 character measure (gap DS-6), left-aligned, not
  centred as a narrow ribbon in a wide frame. `CategoryEntry` `<dl>` switches to a two-column grid,
  labels in a fixed-width first column and values in the second, so the four terms line up down the
  page across all eight entries — the alignment a table would have given, without a table's
  overflow. `ProcessorList` and `OutwardCallList` gain their column headings.
  `ObjectionCallToAction` is intrinsic width, left-aligned with the text.
- **1280** — identical to 768. The measure does not widen, and no second column, sidebar or sticky
  rail appears. `Contents` stays inline at the top of the document rather than moving into a margin:
  a table of contents parked in a sidebar is furniture, and it disappears entirely at the one
  viewport where the document is hardest to navigate.

At every viewport, the set of paragraphs rendered is identical. Layout changes; content never does.

## 9. Accessibility

- Root is `<article aria-labelledby="privacy-notice-title">` with the `<h1>`. The route composing it
  renders no second `<h1>`. Sections are `<section aria-labelledby>` with `<h2>`; `CategoryEntry`
  and `RightsItem` headings are `<h3>`. Heading levels never skip.
- `Contents` is a `<nav aria-labelledby>` containing an `<ol>` of same-page links, in document order,
  one per section. Activating one moves focus to the target `<h2>` (`tabindex="-1"`), not only the
  viewport.
- Each `CategoryEntry` is a `<dl>` of four `<dt>`/`<dd>` pairs. A screen reader announcing "Legal
  basis: our legitimate interest…" is exactly the association this content needs, and it is the
  reason this is not a table.
- `ProcessorList` and `OutwardCallList` are real `<table>`s with `<th scope="col">`, small enough
  (three columns, three rows) to fit the measure at every viewport without overflow. They are the
  only tables in the component.
- Inline links are `<a>` with a permanent underline, never colour alone (README rule 4).
  `ObjectionCallToAction` is a `Button` rendered as `<a>`, because it navigates.
- Touch targets: every `Contents` entry and the objection button clear 44px. Inline links inside a
  running sentence take WCAG 2.5.8's inline exception and are not padded to 44px — doing so would
  break the line rhythm of a long document, and every one of them has a standalone equivalent in
  `Contents` or in a `RightsItem` control.
- Contrast per the README table, in both themes: body `text-primary` on `surface`; `<dt>` labels
  `text-secondary` on `surface` (6.2 light / 7.8 dark); links `accent` on `surface` (4.9 light /
  7.7 dark — passing normal text in both, which is why DS-9 permits `accent` here and only on this
  background). `ChangeNote` follows `Callout`'s own rule: `info` heading, `text-primary` body, on
  `surface-raised`.
- Reading order equals visual order equals DOM order, verified with CSS disabled. With stylesheets
  off, the notice must still read as a complete, ordered document — this is the state a text browser
  and a "reader mode" both produce, and it is a plausible way a regulator reads it.
- Zoom to 200%, and 320px logical width, with no horizontal scrolling and no truncated cell.
- The document is selectable, copyable and printable text. No part of this notice is an image, a
  canvas, an embedded PDF or a downloaded file.

## 10. Visual acceptance criteria

**The document exists and is whole**

- [ ] All nine section headings are present in a full-page screenshot at 375, 768 and 1280.
- [ ] All eight `CategoryEntry` headings are present when `showsAnalysisRetention` is true; seven
      when it is false, and the missing one is the analysis entry and no other.
- [ ] Every `CategoryEntry` shows all four labels — Where it comes from, Why we have it, Legal
      basis, How long we keep it — each with a non-empty value. No blank, no em dash, no "—".
- [ ] No section is collapsed, truncated, behind a "Read more", or inside a scrollable sub-region.
- [ ] The notice renders identically with JavaScript data loading blocked: no skeleton block and no
      spinner appears anywhere in any frame.

**The legally load-bearing phrases are on screen**

- [ ] "legitimate interest" appears in the recorded-games entry, together with "Art. 6-1-f".
- [ ] "Art. 21" and the word "object" appear in the rights section.
- [ ] The erasure item contains the words "There is no undo".
- [ ] The words "pseudonymous" or "pseudonymisation" appear where erasure and third-party objection
      are described, and the words "anonymous" and "anonymised" appear **nowhere in the frame**.
- [ ] The words "no password" and "no email address" both appear.
- [ ] "30 days" appears in the non-user section.
- [ ] The three processors and the three outward services are each named in full, with a location
      that is in the EU.

**The empty state**

- [ ] With `controllerContact` absent, the "How to reach us" section is present and visibly states
      that no contact address is published yet, plus why. The section is never absent and never
      blank.
- [ ] With `controllerContact` present, no "not published yet" wording remains in the frame.
- [ ] With no `changeNote`, no empty bordered callout appears between the lede and the contents.

**Tone and prohibitions**

- [ ] No shield, lock, padlock or tick icon anywhere in the frame.
- [ ] No phrase from the banned list in §4 appears — spot-check "we take your privacy seriously",
      "trusted partners", "as long as necessary", "contact support", "accept all cookies".
- [ ] Nothing in the frame is coloured `danger` or `warning`. The erasure and objection paragraphs
      are the same text colour as the rest of the document.
- [ ] No game artwork, logo, portrait or in-game font in the frame.

**Craft and layout**

- [ ] At 375 the page has no horizontal scrollbar and no clipped or side-scrolling row, in any
      section, including both tables.
- [ ] At 768 and 1280 the text column holds roughly 60 to 75 characters per line and does not span
      the viewport; the measure is the same at both.
- [ ] At 768 and above, the four `<dt>` labels align vertically down the page across every
      `CategoryEntry`.
- [ ] The contents list is visible without scrolling at 1280 in the top frame, and every entry is at
      least 44px tall at 375.
- [ ] The focus ring is visible and unclipped on the first contents link, on an inline link in the
      middle of a paragraph, and on the objection button, in both themes.
- [ ] The objection button is present in the non-user section in every story, including those
      rendered as if signed in.
- [ ] At 200% zoom, no text overlaps and no line is cut off.
