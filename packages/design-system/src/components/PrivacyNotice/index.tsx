import type { MouseEvent, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { Callout } from '../Callout'

// packages/design-system/specs/privacy-notice.md

export interface Processor {
  name: string
  role: string
  /** Must be an EU location; constitution IX. */
  location: string
}

export interface PrivacyNoticeHrefs {
  /** The profile page carrying ArchivalControl's switch. */
  archivalControl: string
  /** The route with the export and erasure controls. */
  privacyRoute: string
  /** The route outside the session (T095's /object). Required — FR-039's "a way to object". */
  objectionForm: string
  /** Optional; renders RegisterLink when present. */
  processingRegister?: string
}

export interface PrivacyNoticeControllerContact {
  name: string
  postalAddress?: string
  contactRoute: string
}

export interface PrivacyNoticeChangeNote {
  heading: string
  body: string
  date: string
}

export interface PrivacyNoticeProps {
  /** ISO date (YYYY-MM-DD) this text last changed. Build-time constant, never fetched. */
  lastUpdated: string
  hrefs: PrivacyNoticeHrefs
  /** Non-empty. Defaults to PHASE_1_PROCESSORS. */
  processors?: readonly [Processor, ...Processor[]]
  /** Absent today. Its absence is a rendered state (ContactUnpublished), not a hidden section. */
  controllerContact?: PrivacyNoticeControllerContact
  /** Renders the analysis-retention CategoryEntry and the erasure caveat that goes with it. */
  showsAnalysisRetention?: boolean
  changeNote?: PrivacyNoticeChangeNote
  className?: string
}

// §4.4 — phase-1 default processors.
export const PHASE_1_PROCESSORS: readonly [Processor, ...Processor[]] = [
  { name: 'Vercel', role: 'runs the website and the API', location: 'Paris, France' },
  { name: 'Neon', role: 'stores the database', location: 'European Union' },
  { name: 'Cloudflare', role: 'stores the recordings (R2)', location: 'European Union' },
]

interface OutwardCall {
  service: string
  what: string
  why: string
}

// §4.4 — fixed body text, not a prop: what we send out never varies by deployment the way the
// processor list can.
const OUTWARD_CALLS: readonly OutwardCall[] = [
  {
    service: "The game's official API (worldsedgelink.com)",
    what: 'your profile id, or your Steam id',
    why: 'your profile, ratings and match history',
  },
  {
    service: "The game's replay service (aoe.ms)",
    what: 'a match id and a profile id',
    why: 'to download a recording',
  },
  {
    service: 'data.aoe2companion.com',
    what: 'the name text you typed in a search',
    why: 'to find a player by name',
  },
]

interface CategoryEntryData {
  id: string
  heading: string
  from: string
  why: string
  basis: string
  howLong: string
  body: string
}

// §4.2 — normative, banned-phrase-checked copy for the eight collection categories.
const CATEGORY_ENTRIES: readonly CategoryEntryData[] = [
  {
    id: 'category-account',
    heading: 'Your sign-in and your account',
    from: 'your Steam sign-in.',
    why: 'to know that this account is yours, and to keep you signed in.',
    basis: 'performing the service you asked us for (GDPR Art. 6-1-b).',
    howLong: 'until you erase your account.',
    body: 'We keep your Steam account number, taken from the identifier Steam verifies for us — we check that identifier and never store it. With it: your Age of Empires II profile id, an opaque session identifier, the dates you signed in, and the date you were let into the closed beta. There is no password and no email address here. We never asked you for either, so there is neither to store, to leak, or to reset.',
  },
  {
    id: 'category-matches',
    heading: 'Your matches and your ratings',
    from: "the game's official API.",
    why: 'to show you your stats and your match history.',
    basis: 'performing the service you asked us for (GDPR Art. 6-1-b).',
    howLong: 'until you erase your account.',
    body: 'Your profile id, alias, country, and — per leaderboard — your rating, rank, wins, losses, streak and highest rating. One rating snapshot a day, so a rating curve can be drawn; snapshots are only ever added, never rewritten. And the details of each match: map, civilisation, team, colour, result, rating change, duration, and when it started and ended.',
  },
  {
    id: 'category-recordings',
    heading: 'Your recorded games',
    from: "the game's own replay service.",
    why: 'the game deletes them, and then they are gone for everyone.',
    basis:
      'our legitimate interest in saving them before that happens (GDPR Art. 6-1-f). You can object at any time — see "Your rights".',
    howLong: 'until you erase your account. There is no other expiry.',
    body: 'Age of Empires II deletes your replay files about 31 days after the match. After that nobody can get them back — not you, not us, not Microsoft. So we download the recording of each of your matches, from your own point of view, and keep the original file unchanged. A recording contains your actions, your alias, and whatever was typed in the in-game chat during that match. We only ever take your own point of view, never another player’s. If you object to this, we also keep the date you objected.',
  },
  {
    id: 'category-other-players',
    heading: 'Other players who appear in your matches',
    from: "the game's official API, and the recordings we hold.",
    why: 'a match cannot be split per player, and neither can a recording.',
    basis: 'our legitimate interest, over data the game already publishes (GDPR Art. 6-1-f).',
    howLong: 'as long as the match or the recording it belongs to.',
    body: 'For everyone in a match you played: profile id, alias, country, civilisation, team, colour, result, rating and rating change — all of it already published by the game on its own public leaderboards. Inside a recording we hold, their in-game actions and chat are in the file too, because a recording cannot be separated per player. We never capture another player’s own point of view, and we never put a profile page or a search result into a public listing or a search engine. If a signed-in user asks to watch one specific point of view of a match we know about, we fetch it from the game’s service and pass it straight through without keeping a copy.',
  },
  {
    id: 'category-search',
    heading: 'Searching for a player by name',
    from: 'you type the name; a third-party public search service answers.',
    why: 'nothing we hold is indexed by name for a player we have never seen in a match.',
    basis: 'our legitimate interest (GDPR Art. 6-1-f).',
    howLong:
      'a cached answer goes stale quickly and is deleted when a later search overwrites it. There is no scheduled clean-up, so a row can outlive its staleness if no later search happens.',
    body: 'The text you type is sent to data.aoe2companion.com, a public search service we do not run. What comes back is cached under the text of the query and never under who typed it, so this cache cannot answer "who searched for this player". A result carries a Steam account number that the source itself publishes beside a profile; we show it exactly as an unverified claim by that source, and we never use it to link, merge or treat two profiles as the same person. Only a completed Steam sign-in does that. Neither erasing an account nor objecting reaches this cache — it is keyed to nobody, and we are saying so rather than implying it is covered.',
  },
  {
    id: 'category-access-log',
    heading: 'Opening a recording we hold',
    from: 'generated here, when the file is opened.',
    why: 'these files contain other people’s gameplay and chat, so who opened one is worth keeping.',
    basis:
      'our legitimate interest in being able to show that access is limited and auditable (GDPR Art. 6-1-f).',
    howLong:
      'deleted together with the recording it describes, including when you erase your account.',
    body: 'Which recording was opened, by whom, when, and what for. A point of view we fetch and pass straight through without storing is not logged this way, because there is no stored file for a later, unrecorded read to reach.',
  },
  {
    id: 'category-requests',
    heading: 'The requests you make under this notice',
    from: 'you, through the export, erasure and objection controls.',
    why: 'it is the proof that your request was carried out.',
    basis: 'our legal obligation under GDPR Articles 15 to 21 (Art. 6-1-c).',
    howLong:
      'indefinitely, on purpose — including after an erasure it documents. The link to your account is removed; the record that the request was made and resolved stays.',
    body: 'What kind of request it was, which account or profile it concerned, when it was asked for, and when and how it was resolved. This is the one thing an erasure deliberately leaves behind, and it exists so that the erasure can still be shown to have happened.',
  },
]

const ANALYSIS_CATEGORY_ENTRY: CategoryEntryData = {
  id: 'category-analysis',
  heading: 'Matches you ask us to analyse',
  from: "the game's replay service, when you ask for that match to be analysed.",
  why: 'an analysis published to everyone who opens that match has to stay checkable.',
  basis:
    'our legitimate interest, over a recording already public at its source (GDPR Art. 6-1-f).',
  howLong:
    'indefinitely. This one is not deleted by erasing your account, and not by a third-party objection.',
  body: 'If you ask us to analyse a match, we keep the recording the analysis was computed from. The game deletes its own copy after about a month, so throwing ours away would mean publishing a conclusion nobody could ever check or correct again. Erasing your account removes the record that you were the one who asked; it does not delete the recording, and the recording is never modified, because modifying it would break both its checksum and the reason for keeping it. We are stating this as the decision it is, not claiming the file stops being about anyone.',
}

const SECTIONS_TOC: readonly { id: string; label: string }[] = [
  { id: 'who-we-are', label: 'Who we are and what this is' },
  { id: 'what-we-collect', label: 'What we collect' },
  { id: 'cookies', label: 'Cookies' },
  { id: 'where-stored', label: 'Where it is stored, and who else touches it' },
  { id: 'how-long', label: 'How long we keep it' },
  { id: 'your-rights', label: 'Your rights, and the control that exercises each one' },
  { id: 'non-user', label: 'If you are not a user of this service' },
  { id: 'what-we-do-not-do', label: 'What we do not do' },
  { id: 'how-to-reach-us', label: 'How to reach us' },
]

const NOT_DO_ITEMS: readonly string[] = [
  'We do not sell your data, and we do not share it with anyone outside the three providers named above.',
  'We do not show advertising and we make no money from this service at all.',
  'We do not publish or index profile pages or search results. Nothing here is meant to be found by a search engine looking for a person.',
  'We do not store a password or an email address, and there is no password reset, no email verification and no account recovery. Your Steam account is the only way in.',
  'We do not offer a way to hide your matches inside this service. Every field the game’s own APIs serve is public, and we keep it that way rather than pretending we can make it private.',
  'Where the game itself withholds data — a player who has switched off its "Shared History" setting — we do not go around it by another route. We also do not treat that setting as a request addressed to us, because it is not one.',
  'We do not treat an unverified Steam account number published beside a profile as proof that two profiles are the same person, and no feature acts on it.',
]

const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring'

const inlineLinkClasses = cx(
  'text-link underline transition-colors duration-120 ease-standard motion-reduce:duration-0',
  'hover:text-link-hover active:text-link-hover visited:text-link-visited',
  focusRing,
)

function scrollAndFocus(id: string) {
  return (event: MouseEvent<HTMLAnchorElement>) => {
    const target = document.getElementById(id)
    if (!target) return
    event.preventDefault()
    const reduceMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
    target.focus()
  }
}

function InlineLink({ href, id, children }: { href: string; id?: string; children: ReactNode }) {
  const inPage = id !== undefined
  return (
    <a href={href} onClick={inPage ? scrollAndFocus(id) : undefined} className={inlineLinkClasses}>
      {children}
    </a>
  )
}

function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2
      id={id}
      tabIndex={-1}
      className="font-display text-xl font-semibold text-text-primary outline-none"
    >
      {children}
    </h2>
  )
}

function TermRow({ term, value }: { term: string; value: ReactNode }) {
  return (
    <div className="flex flex-col md:flex-row md:gap-x-6">
      <dt className="font-sans text-sm font-semibold text-text-secondary md:w-56 md:shrink-0">
        {term}
      </dt>
      <dd className="font-sans text-md text-text-primary">{value}</dd>
    </div>
  )
}

function CategoryEntry({ entry }: { entry: CategoryEntryData }) {
  return (
    <div>
      <h3 className="font-sans text-lg font-semibold text-text-primary">{entry.heading}</h3>
      <dl className="mt-3 flex flex-col gap-2">
        <TermRow term="Where it comes from" value={entry.from} />
        <TermRow term="Why we have it" value={entry.why} />
        <TermRow term="Legal basis" value={entry.basis} />
        <TermRow term="How long we keep it" value={entry.howLong} />
      </dl>
      <p className="mt-4 font-sans text-md text-text-primary">{entry.body}</p>
    </div>
  )
}

function InfoTable({
  caption,
  columns,
  rows,
}: {
  caption: string
  columns: readonly string[]
  rows: readonly (readonly ReactNode[])[]
}) {
  return (
    <table className="mt-3 w-full border-collapse text-left font-sans text-md text-text-primary">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          {columns.map((column) => (
            <th
              key={column}
              scope="col"
              className="border-b border-border py-2 pr-4 font-sans text-sm font-semibold text-text-secondary"
            >
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          // eslint-disable-next-line react/no-array-index-key
          <tr key={index} className="border-b border-border">
            {row.map((cell, cellIndex) => (
              // eslint-disable-next-line react/no-array-index-key
              <td key={cellIndex} className="py-2 pr-4 align-top">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function StackedRow({
  columns,
  values,
}: {
  columns: readonly string[]
  values: readonly ReactNode[]
}) {
  return (
    <dl className="flex flex-col gap-2 border-b border-border pb-3 last:border-b-0 last:pb-0">
      {columns.map((column, index) => (
        <TermRow key={column} term={column} value={values[index]} />
      ))}
    </dl>
  )
}

// §8 — below `md` `ProcessorList` and `OutwardCallList` stack as one labelled block per row, the
// same `<dl>` pattern `CategoryEntry` uses: three columns of prose cannot be read at 375px without
// either horizontal scrolling or truncation, and §10 forbids both, in any section, including these
// two tables. At `md` and up they render as the real `<table>`s §9 describes. Both representations
// are in the DOM; only one is ever visible. `display: none` (Tailwind's `hidden`), unlike
// `visibility: hidden` or clipping, removes the inactive one from the accessibility tree and from
// find-in-page, so there is never a second, hidden copy of this legal text for a screen reader to
// double-read.
function ResponsiveInfoTable({
  caption,
  columns,
  rows,
}: {
  caption: string
  columns: readonly string[]
  rows: readonly (readonly ReactNode[])[]
}) {
  return (
    <>
      <div className="mt-3 flex flex-col gap-3 md:hidden">
        {rows.map((row, index) => (
          // eslint-disable-next-line react/no-array-index-key
          <StackedRow key={index} columns={columns} values={row} />
        ))}
      </div>
      <div className="hidden md:block">
        <InfoTable caption={caption} columns={columns} rows={rows} />
      </div>
    </>
  )
}

function RightsItem({
  heading,
  what,
  whatNot,
  control,
}: {
  heading: string
  what: ReactNode
  whatNot: ReactNode
  control: ReactNode
}) {
  return (
    <div>
      <h3 className="font-sans text-lg font-semibold text-text-primary">{heading}</h3>
      <div className="mt-3 flex flex-col gap-3 font-sans text-md text-text-primary">
        <p>
          <span className="font-medium">What it does:</span> {what}
        </p>
        <p>
          <span className="font-medium">What it does not do:</span> {whatNot}
        </p>
        <p>{control}</p>
      </div>
    </div>
  )
}

/** FR-041: what this service holds, on what basis, for how long, and the control that stops,
 * exports or erases it — one page, readable without a lawyer and without a click. Normative in the
 * stronger sense §4 of the spec describes: this file states the law of the product. No
 * `loading`/`error` prop of any kind — the notice must be complete at first paint (§5). */
export function PrivacyNotice({
  lastUpdated,
  hrefs,
  processors = PHASE_1_PROCESSORS,
  controllerContact,
  showsAnalysisRetention = true,
  changeNote,
  className,
}: PrivacyNoticeProps) {
  const categoryEntries = showsAnalysisRetention
    ? [...CATEGORY_ENTRIES, ANALYSIS_CATEGORY_ENTRY]
    : CATEGORY_ENTRIES

  return (
    <article
      aria-labelledby="privacy-notice-title"
      className={cx('mx-auto max-w-measure px-6 py-6 md:px-0 md:py-8', className)}
    >
      <header>
        <h1
          id="privacy-notice-title"
          className="font-display text-2xl font-semibold text-text-primary md:text-3xl"
        >
          Privacy notice
        </h1>
        <p className="mt-2 font-sans text-sm text-text-secondary">
          Last updated {formatLastUpdated(lastUpdated)}.
        </p>
        <p className="mt-1 font-sans text-sm text-text-secondary">
          We have no email address for you, so we cannot tell you when this notice changes. The date
          at the top is the date it last did, and a change worth noticing appears here.
        </p>
        <p className="mt-4 font-sans text-md text-text-primary">
          This service keeps your Age of Empires II profile, your match history and the recordings
          of your own games, so that they still exist after the game deletes them. It has no
          password and no email address for you, and it never sells or shares any of this.
          Everything below says what is held, why we are allowed to hold it, for how long, and the
          button that stops or removes it.
        </p>
      </header>

      {changeNote && (
        <div className="mt-6">
          <Callout tone="info" heading={changeNote.heading} headingLevel={3}>
            <p>{changeNote.body}</p>
            <p className="text-sm text-text-secondary">{changeNote.date}</p>
          </Callout>
        </div>
      )}

      <nav aria-labelledby="privacy-notice-contents-heading" className="mt-6">
        <h2
          id="privacy-notice-contents-heading"
          className="font-sans text-sm font-semibold text-text-secondary"
        >
          Contents
        </h2>
        <ol className="mt-3 flex flex-col gap-1">
          {SECTIONS_TOC.map((section, index) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                onClick={scrollAndFocus(section.id)}
                className={cx(
                  'flex min-h-11 items-center py-3 font-sans text-md text-link underline',
                  'transition-colors duration-120 ease-standard motion-reduce:duration-0',
                  'hover:text-link-hover active:text-link-hover visited:text-link-visited',
                  focusRing,
                )}
              >
                {index + 1}. {section.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      {/* Section 1 */}
      <section aria-labelledby="who-we-are" className="mt-8">
        <SectionHeading id="who-we-are">Who we are and what this is</SectionHeading>
        <div className="mt-3 flex flex-col gap-4 font-sans text-md text-text-primary">
          <p>
            aoe2-stats keeps Age of Empires II: Definitive Edition stats, match history and replay
            recordings for players who choose to link their Steam account. It is a closed-beta,
            hobby service — not affiliated with Microsoft or Relic Entertainment.
          </p>
        </div>
      </section>

      {/* Section 2 */}
      <section aria-labelledby="what-we-collect" className="mt-12">
        <SectionHeading id="what-we-collect">What we collect</SectionHeading>
        <p className="mt-3 font-sans text-md text-text-primary">
          Eight kinds of thing, each with where it came from, why we have it, what allows us to hold
          it, and when it goes.
        </p>
        <div className="mt-8 flex flex-col gap-8">
          {categoryEntries.map((entry) => (
            <CategoryEntry key={entry.id} entry={entry} />
          ))}
        </div>
      </section>

      {/* Section 3 */}
      <section aria-labelledby="cookies" className="mt-12">
        <SectionHeading id="cookies">Cookies</SectionHeading>
        <p className="mt-3 font-sans text-md text-text-primary">
          Two, both strictly necessary, neither of which asks you anything. One keeps you signed in.
          The other lives for a few minutes during sign-in and exists only to make sure the trip to
          Steam and back is really yours. There is no advertising cookie, no analytics cookie and no
          third-party tracker on this site, which is why there is no cookie banner to dismiss.
        </p>
      </section>

      {/* Section 4 */}
      <section aria-labelledby="where-stored" className="mt-12">
        <SectionHeading id="where-stored">
          Where it is stored, and who else touches it
        </SectionHeading>
        <p className="mt-3 font-sans text-md text-text-primary">
          Everything is stored in the European Union, and nothing here is sold, shared or handed to
          anyone for their own purposes. Three companies handle it on our behalf, because we do not
          own servers:
        </p>
        <ResponsiveInfoTable
          caption="Processors handling data on our behalf"
          columns={['Provider', 'Role', 'Where']}
          rows={processors.map((processor) => [processor.name, processor.role, processor.location])}
        />
        <p className="mt-4 font-sans text-md text-text-primary">
          They act on our instructions and for nothing else. If we ever move this service to
          different hosting, this list changes here first.
        </p>
        <p className="mt-4 font-sans text-md text-text-primary">
          We also send requests out to three services that we do not run, and this is everything we
          send them:
        </p>
        <ResponsiveInfoTable
          caption="Outside services we send requests to"
          columns={['Service', 'What we send', 'Why']}
          rows={OUTWARD_CALLS.map((call) => [call.service, call.what, call.why])}
        />
        <p className="mt-4 font-sans text-md text-text-primary">
          Your Steam sign-in itself happens at Steam, not here: we send you there and Steam tells us
          which account came back. We never see your Steam password.
        </p>
      </section>

      {/* Section 5 */}
      <section aria-labelledby="how-long" className="mt-12">
        <SectionHeading id="how-long">How long we keep it</SectionHeading>
        <div className="mt-3 flex flex-col gap-4 font-sans text-md text-text-primary">
          <p>
            Each entry above states its own end condition, and this is the summary of them. Almost
            everything we hold about you ends when you erase your account: the account itself, the
            sign-in records, the profile links, your favourites, the match records that name you,
            and every recording of yours we have stored, including the files themselves in storage.
          </p>
          <p>
            Three things deliberately outlive that, and each one is named above rather than buried
            here. The matches themselves survive, with your profile id replaced by a pseudonymous
            one, because they are other players’ match records too. The record of your erasure
            request survives, without the link to your account, because it is the proof the erasure
            happened. And a recording kept for an analysis you asked to be published survives,
            because the analysis it produced has to stay checkable.
          </p>
          <p>
            We do not delete anything on a timer. Nothing here expires quietly on its own, except a
            cached search result, which is overwritten by a later search.
          </p>
        </div>
      </section>

      {/* Section 6 */}
      <section aria-labelledby="your-rights" className="mt-12">
        <SectionHeading id="your-rights">
          Your rights, and the control that exercises each one
        </SectionHeading>
        <p className="mt-3 font-sans text-md text-text-primary">
          Each of these is a control in this product, not a request form. Where a right has a limit,
          the limit is written under the right and not somewhere else.
        </p>
        <div className="mt-8 flex flex-col gap-8">
          <RightsItem
            heading="Stop us archiving your recordings (GDPR Art. 21)"
            what="stops every future capture of your recordings, from the moment you press it, and records the date you objected."
            whatNot="it does not touch your match history or your ratings, which keep updating; it does not delete recordings already archived; and it does not go back and capture what was missed once you resume."
            control={
              <>
                <InlineLink href={hrefs.archivalControl}>Object to archival</InlineLink>, on your
                profile page. You can resume at any time, with one press.
              </>
            }
          />
          <RightsItem
            heading="Get a copy of everything (GDPR Art. 15 and Art. 20)"
            what="builds a single archive containing your account record, your Steam identities, every profile link you have ever held, the match records and per-player rows for those profiles, your archived recordings as the original files, your favourites, and the analyses you asked for."
            whatNot="it does not include the cached search results described above, which are keyed to nobody, and it does not include the internal counters that rate-limit the API."
            control={
              <>
                <InlineLink href={hrefs.privacyRoute}>Export my data</InlineLink>, on the privacy
                page. When it is ready you get a download link, which stops working after a short
                while — start a new export if it does.
              </>
            }
          />
          <RightsItem
            heading="Erase your account and everything attached to it (GDPR Art. 17)"
            what="deletes your account, your Steam identities, your sessions, your profile links, your favourites, your archived recordings — the files in storage, not just the rows pointing at them — and the access records for them. Your session stops working on the very next request."
            whatNot="it does not delete the matches themselves. Your profile id in them is replaced by a pseudonymous one, so the other players' records stay correct. That is pseudonymisation, not anonymisation: we are not claiming the result stops being about anyone. It also leaves the record that you asked for the erasure, and any recording kept for an analysis you asked to be published."
            control={
              <>
                <InlineLink href={hrefs.privacyRoute}>Erase my account</InlineLink>, on the privacy
                page. It asks you to confirm, and then it is done.{' '}
                <span className="font-medium">
                  There is no undo, and no backup we can restore you from.
                </span>
              </>
            }
          />
          <RightsItem
            heading="Correct something that is wrong (GDPR Art. 16)"
            what="nothing on our side, and this is the honest answer. Your alias, country, rating and match results are not written by us — we read them from the game's own services. Correcting them there is what changes them here, on the next update."
            whatNot="we will not edit a match record, a rating or a recording to say something different from what the game reported. A stats tool that lets its numbers be edited is not one."
            control="none here, by design."
          />
          <RightsItem
            heading="Restrict processing, or anything else in Articles 15 to 22"
            what="the controls above cover getting a copy, stopping the archiving and erasing everything, which is the whole of what this service can do to your data. Anything else goes to the controller."
            whatNot="it does not go through an automated route, because there is not one."
            control={
              <>
                see{' '}
                <InlineLink href="#how-to-reach-us" id="how-to-reach-us">
                  How to reach us
                </InlineLink>{' '}
                at the end of this notice.
              </>
            }
          />
          <RightsItem
            heading="Complain about how we handle this"
            what="you can complain to your national data protection authority. That right does not depend on us, and using it does not require asking us first."
            whatNot="it does not replace the controls above, which are faster."
            control="your own supervisory authority."
          />
        </div>
        <p className="mt-8 font-sans text-md text-text-primary">
          Nothing here makes an automated decision about you that has a legal effect or anything
          similar. We compute statistics from your matches; we do not rank, score or judge you with
          a consequence attached.
        </p>
      </section>

      {/* Section 7 */}
      <section aria-labelledby="non-user" className="mt-12">
        <SectionHeading id="non-user">If you are not a user of this service</SectionHeading>
        <div className="mt-3 flex flex-col gap-4 font-sans text-md text-text-primary">
          <p>
            You may appear here without ever having signed in: you played a match against someone
            who did, and the game publishes that match. What we hold about you is the public part of
            that match — profile id, alias, country, civilisation, team, colour, result, rating and
            rating change — and, inside the recording that user’s own game produced, your in-game
            actions and chat.
          </p>
          <p>
            You can object. The form asks for the profile id you want acted on and nothing else: no
            account, no sign-in, no email address, because we have no way to ask you for one and no
            way to answer you.
          </p>
          <p>
            What happens then: your objection is recorded with its date. A person reads it and acts
            on it within 30 days, replacing your profile id in our match records with a pseudonymous
            one, so that what remains no longer names you.
          </p>
          <p>
            What it does not do: it does not delete the matches, which are other players’ records
            too, and it does not delete or alter a recording. It does not reach a cached search
            result, for the reason given above. And, again, this is pseudonymisation and not
            anonymisation — the record still describes a game somebody played.
          </p>
        </div>
        <div className="mt-6">
          <a
            href={hrefs.objectionForm}
            className={cx(
              'inline-flex min-h-11 w-full items-center justify-center rounded-control border border-border-strong bg-surface px-6 font-sans text-md font-semibold text-text-primary md:w-auto',
              'transition-colors duration-120 ease-standard motion-reduce:duration-0',
              'hover:bg-surface-sunken active:bg-surface-sunken',
              focusRing,
            )}
          >
            Object to what is held about me
          </a>
        </div>
      </section>

      {/* Section 8 */}
      <section aria-labelledby="what-we-do-not-do" className="mt-12">
        <SectionHeading id="what-we-do-not-do">What we do not do</SectionHeading>
        <ol className="mt-3 flex flex-col gap-3 font-sans text-md text-text-primary">
          {NOT_DO_ITEMS.map((item, index) => (
            <li key={item} className="flex gap-2">
              <span className="text-text-secondary">{index + 1}.</span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      </section>

      {/* Section 9 */}
      <section aria-labelledby="how-to-reach-us" className="mt-12">
        <SectionHeading id="how-to-reach-us">How to reach us</SectionHeading>
        <div className="mt-3 rounded-panel bg-surface-raised p-5 font-sans text-md text-text-primary">
          {controllerContact ? (
            <p>
              The controller for everything described here is {controllerContact.name}.{' '}
              {controllerContact.postalAddress && `${controllerContact.postalAddress}. `}To reach us
              about anything this notice does not have a button for, use{' '}
              <a href={controllerContact.contactRoute} className="text-link underline">
                this contact route
              </a>
              .
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              <p className="font-medium">
                We have not published a contact address yet. This service is in closed beta and is
                not open to the public. Contact details for the controller will be published in this
                section before it opens, and that is a condition of it opening, not a task left for
                later.
              </p>
              <p>
                Until then the controls above are the whole of what is available: object to archival
                and export or erase your data from inside the product, or object through the form
                above if you are not a user. If you want something those do not cover, there is no
                route here yet, and we would rather say so than print an address that reaches
                nobody.
              </p>
            </div>
          )}
        </div>
      </section>

      {hrefs.processingRegister && (
        <p className="mt-8 font-sans text-sm text-text-secondary">
          <InlineLink href={hrefs.processingRegister}>
            Read the public processing register
          </InlineLink>
        </p>
      )}
    </article>
  )
}

// `en-GB`, not `en`: `Intl.DateTimeFormat('en', { dateStyle: 'long' })` renders "August 30, 2026",
// the exact MM/DD ordering §4.1 bans in numeric form and would still read ambiguously as prose.
// `en-GB`'s day-month-year prose ("30 August 2026") matches the spec's own worked example.
const lastUpdatedFormat = new Intl.DateTimeFormat('en-GB', { dateStyle: 'long' })

/** `lastUpdated` is a plain `YYYY-MM-DD` build-time constant (§3) — rendered unambiguously, never
 * `30/08/2026` and never `08/30/2026` (§4.1). */
function formatLastUpdated(iso: string): string {
  return lastUpdatedFormat.format(new Date(`${iso}T00:00:00Z`))
}
