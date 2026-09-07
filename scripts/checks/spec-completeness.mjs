#!/usr/bin/env node
// T571: FR-035, SC-013 — the mechanical check a ten-entry state vocabulary across 41 components
// (T569) can only stay answered by, because nobody re-reads 27 files on every pull request. It
// fails a spec under `packages/design-system/specs/` for any of three reasons:
//   1. It omits one of the nine mandated sections (README.md, "Every spec has nine sections").
//   2. It leaves an entry in the closed state vocabulary unanswered (README.md, same section).
//   3. It declares no tier or no surface class for a component `README.md`'s Index table maps to
//      it — checked **per component**: a file the index maps to more than one component (four of
//      them today: `shared-primitives.md` six, `match-history.md`/`player-search.md`/
//      `privacy-data-rights.md` two each) owes one declaration per component, in a table, because
//      a tier and a surface class are each a property of a component, not of a file (T570).
// A fourth shape is really the same rule read backwards: a component directory under
// `packages/design-system/src/` that no Index row names at all fails too — the index is this
// check's *complete* list of what to verify, so a component missing from it is invisible to
// everything above, which is worse than a component present but incomplete.
//
// Three facts this check reads from `README.md` rather than hard-coding, because a fact written in
// two files goes stale in one of them (CLAUDE.md's law, the reason this whole feature exists):
//   - The nine section names ("Every spec has nine sections").
//   - The ten-entry state vocabulary ("The state vocabulary is closed: ...").
//   - The two surface classes ("Surface density: `dense` and `prose`").
//   - The Index table itself: which spec file covers which component directory, hence which tier
//     (the directory's own top-level segment — `primitives`/`composites`/`screens` — is the tier,
//     per data-model.md §2: "Lives in: the directory a component's source is in... not a manifest,
//     not a frontmatter field"). This check never invents a second vocabulary for tier names; the
//     word a component's spec owes is derived from the very directory the Index row already names.
//
// Exemption. `game-asset-tokens.md` is exempt **by name**, with the reason beside it below: it
// specifies tokens, not a component (its own Index row already says as much — "no component;
// `tokens/`" — which is also why it contributes zero parsed components on its own, see
// `parseComponentCell`; the explicit name below is required by the task regardless, so the
// exemption reads in the source rather than depending on that side effect). `color-tokens.md`,
// `typography-tokens.md` and `GOVERNANCE.md` need no exemption at all: none of the three has an
// Index row, so the index-driven loop below never visits them — deriving "is this a component
// spec?" from the Index, per the task, rather than accumulating a hand-maintained list for every
// non-component file this directory happens to hold (the idiom `story-baselines.mjs` set with its
// derived `loadAppRouteBaselineNames`, rather than a second hardcoded name list growing beside it).
//
// Section and state detection is a lexical scan, matching this repository's other checks
// (token-scale.mjs's own header explains the reasoning: the shapes are lexical, not structural).
// Two conventions both ship today for declaring a section or a state, and both are matched:
//   - A `#`-`######` heading whose text names the section (`## 5. States`, numbering and trailing
//     qualifiers ignored). Matching is by whole word, not substring: `## 3. The four-state
//     collapse` is genuinely not a match for "States" (the hyphenated compound `four-state` is one
//     token, and no token in it equals or starts with the keyword `state`), while `## 6. Tokens
//     used` is a match for "Tokens used" (the token `tokens` starts with the keyword `token`).
//   - A bold label at the very start of a (trimmed) line, optionally bulleted (`**Purpose** —
//     ...`, `- **default** — ...`) — the compressed shape `shared-primitives.md`,
//     `structural-tier.md` and several screen specs already use per component instead of numbered
//     headings.
// A state is "answered" once its bold label appears this way, even combined with siblings on one
// line (`- **hover / focus-visible / active** — none.`) — presence of the label is the proxy for
// "answered", exactly as FR-035 allows: "specifying its appearance and behaviour or recording why
// it does not apply" both start with the state's name written down.
//
// The state vocabulary is checked **per component**, not per file, for the same reason tier and
// surface class already are (T570: "a tier is a property of a component and a file covering six
// cannot declare one"). A multi-component file that also uses one `##` heading per component
// (`shared-primitives.md`, `structural-tier.md` — see `findComponentSection`) is scoped to that
// heading's own body before the ten-entry scan runs, so a state answered for one component no
// longer silently covers a sibling that never answered it. A multi-component file with no such
// heading boundary (`match-history.md`, `player-search.md`, `privacy-data-rights.md` — one shared
// numbered "States" section naming each component inline, e.g. "`MatchRow`: ...; `DownloadAction`:
// ...") has no boundary to scope to and is checked whole-document, exactly as before: that shape
// already answers each component by name inside the one section, which the per-component heading
// scope cannot see and does not need to. The nine other sections stay file-scoped everywhere: the
// compressed per-component shape already restates all nine section labels inside every component's
// own heading block (`shared-primitives.md`'s `## Button` carries its own `**Purpose**` through
// `**Acceptance**`), so the equivalent hole does not exist for sections today.
//
// Usage:  node scripts/checks/spec-completeness.mjs
// Exit:   0 if every Index-mapped spec answers all nine sections, every component it covers
//         answers all ten states, declares a tier and a surface class, and no component directory
//         on disk is missing from the Index — 1 otherwise, naming the file, the component and the
//         exact missing thing for every finding.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const designSystemDir = path.join(rootDir, 'packages', 'design-system')
const specsDir = path.join(designSystemDir, 'specs')
const srcDir = path.join(designSystemDir, 'src')
const readmePath = path.join(specsDir, 'README.md')

// The one hand-maintained exemption the task requires by name — see the file header for why
// nothing else needs one.
export const EXEMPT_SPEC_FILES = new Map([
  [
    'game-asset-tokens.md',
    'specifies tokens, not a component (its own Index row: "no component; `tokens/`")',
  ],
])

function log(message) {
  console.log(`spec-completeness: ${message}`)
}

function fail(message) {
  console.error(`spec-completeness: ${message}`)
  process.exitCode = 1
}

// --- Derived from README.md: sections, vocabulary, surface classes --------------------------

const SECTIONS_HEADING = '## Every spec has nine sections'
const SECTIONS_HEADING_RE = /^## Every spec has (\w+) sections$/m

// English number words this check needs to cross-check a count against, small and closed rather
// than pulled from a library — README never counts past "ten" today.
const COUNT_WORDS = {
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
}

function parseCountWord(word, contextLabel) {
  const number = COUNT_WORDS[word.toLowerCase()]
  if (number === undefined) {
    throw new Error(`README.md's "${contextLabel}" names an unrecognised count word "${word}"`)
  }
  return number
}

// The first sentence of the "Every spec has nine sections" paragraph is the nine-item list itself
// (`README.md`'s own text: "Purpose, Anatomy, ... Visual acceptance criteria. A spec missing one is
// incomplete..."). Read structurally rather than restated, so a future edit to the sentence's
// wording is the only place that ever needs to change.
//
// The heading's own count word ("nine") is cross-checked against how many names the sentence below
// it actually lists, rather than trusted on its own — a heading is a promise, the list beneath it
// is the delivery, and a bare `=== 9` here would only ever notice the list side of that promise
// breaking, never the heading itself drifting out of step with a list that still has nine names
// but a heading now claiming eight. See C2 in the T571 remediation this guards against.
export function deriveNineSections(readmeSource) {
  // Matched by pattern, not by the literal "nine" text, so a heading whose count word has drifted
  // is still found here — the mismatch is caught below by comparison, not by failing to locate the
  // heading at all (which would misreport a drifted count as "the heading is missing").
  const headingMatch = readmeSource.match(SECTIONS_HEADING_RE)
  if (!headingMatch) {
    throw new Error(`README.md is missing the "${SECTIONS_HEADING}" heading this check reads from`)
  }
  const expectedCount = parseCountWord(headingMatch[1], headingMatch[0])

  const body = readmeSource.slice(headingMatch.index + headingMatch[0].length)
  const periodIdx = body.indexOf('. ')
  if (periodIdx === -1) {
    throw new Error('could not find the end of the nine-sections sentence in README.md')
  }
  const sections = body
    .slice(0, periodIdx)
    .replace(/\n/g, ' ')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

  if (sections.length !== expectedCount) {
    throw new Error(
      `README.md's "${headingMatch[0]}" heading says "${headingMatch[1]}" (${expectedCount}) ` +
        `but the sentence beneath it names ${sections.length} section${sections.length === 1 ? '' : 's'} ` +
        `(${sections.join(', ')}) — the two halves disagree.`,
    )
  }
  return sections
}

const VOCABULARY_COUNT_SENTENCE_RE = /Every spec answers all (\w+)/i

// The closed, ten-entry state vocabulary, bolded in README.md right after "The state vocabulary is
// closed:". Lower-cased: every state name in this system is already lower-case prose.
//
// Cross-checked the same way as `deriveNineSections`, against the count word in README's own
// "Every spec answers all ten..." sentence a few words later — the two are two independent halves
// of the same paragraph, and only comparing them catches either one drifting without the other
// (shrink the bolded list to nine and this throws even though nothing here hard-codes "10").
export function deriveVocabulary(readmeSource) {
  const match = readmeSource.match(/state vocabulary is closed:\s*\*\*([^*]+)\*\*/)
  if (!match) {
    throw new Error('README.md is missing the "state vocabulary is closed: **...**" sentence')
  }
  const countMatch = readmeSource.match(VOCABULARY_COUNT_SENTENCE_RE)
  if (!countMatch) {
    throw new Error(
      'README.md is missing the "Every spec answers all ten..." sentence this check cross-checks the vocabulary count against',
    )
  }
  const expectedCount = parseCountWord(countMatch[1], countMatch[0])

  const vocabulary = match[1]
    .replace(/\n/g, ' ')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)

  if (vocabulary.length !== expectedCount) {
    throw new Error(
      `README.md says "${countMatch[0]}" (${expectedCount}) but the closed state vocabulary lists ` +
        `${vocabulary.length} entr${vocabulary.length === 1 ? 'y' : 'ies'} (${vocabulary.join(', ')}) ` +
        '— the two halves disagree.',
    )
  }
  return vocabulary
}

// The two surface classes, named in the "## Surface density: `dense` and `prose`" heading itself
// rather than restated from its body.
export function deriveSurfaceClasses(readmeSource) {
  const headingMatch = readmeSource.match(/^## Surface density:.*$/m)
  if (!headingMatch) {
    throw new Error(
      'README.md is missing the "## Surface density: ..." heading this check reads from',
    )
  }
  const classes = [...headingMatch[0].matchAll(/`([a-z]+)`/g)].map((m) => m[1])
  if (classes.length === 0) {
    throw new Error('found the "Surface density" heading but no `class` names inside it')
  }
  return classes
}

// A small, generic stoplist for deriving a single discriminative keyword from a canonical section
// name — "and", "used" and "criteria" are English glue words, not part of what makes a section
// itself, and "sizes" is skipped so "Variants and sizes" and shared-primitives.md's split
// "**Variants**" / "**Sizes**" labels both satisfy it on the "variant" half alone. Not a second
// vocabulary: it is applied to whatever `deriveNineSections` returns, never a hardcoded list of the
// nine names themselves.
const KEYWORD_STOPWORDS = new Set(['and', 'used', 'criteria', 'visual'])

export function sectionKeyword(sectionName) {
  const words = sectionName
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => !KEYWORD_STOPWORDS.has(w))
  const word = words[0] ?? sectionName.toLowerCase()
  return word.replace(/s$/, '')
}

// --- Derived from README.md: the Index table --------------------------------------------------

const INDEX_ROW_RE = /^\|\s*\[`([^`]+)`\]\([^)]*\)\s*\|(.*)\|(.*)\|\s*$/

// A component directory cell names zero or more `src/<tier>/Name/` paths, one per component, with
// a `{A,B,C}` brace group standing for several components sharing one tier directory
// (`shared-primitives.md`'s six). A cell with no `src/...` backtick at all (game-asset-tokens.md's
// "no component; `tokens/`") yields zero components, which is exactly right — see the file header.
export function parseComponentCell(cell) {
  const components = []
  for (const m of cell.matchAll(/`([^`]+)`/g)) {
    const content = m[1]
    const braceMatch = content.match(/^src\/(primitives|composites|screens)\/\{([^}]+)\}\/?$/)
    if (braceMatch) {
      const [, segment, names] = braceMatch
      for (const name of names.split(',').map((n) => n.trim())) {
        components.push({ name, segment })
      }
      continue
    }
    const singleMatch = content.match(/^src\/(primitives|composites|screens)\/([A-Za-z0-9_]+)\/?$/)
    if (singleMatch) {
      const [, segment, name] = singleMatch
      components.push({ name, segment })
    }
  }
  return components
}

// The tier a component's own directory names it (data-model.md §2: the directory *is* the tier,
// never a second, hand-written field).
export function tierWordForSegment(segment) {
  return { primitives: 'primitive', composites: 'composite', screens: 'screen' }[segment]
}

// One row per Index entry: the spec file, and every component it covers (name, source directory
// segment, and the tier word that segment owes).
export function parseIndexTable(readmeSource) {
  const indexHeadingIdx = readmeSource.indexOf('## Index')
  if (indexHeadingIdx === -1) throw new Error('README.md is missing its "## Index" heading')
  const nextHeadingIdx = readmeSource.indexOf('\n## ', indexHeadingIdx + 1)
  const indexBody = readmeSource.slice(
    indexHeadingIdx,
    nextHeadingIdx === -1 ? undefined : nextHeadingIdx,
  )

  const rows = []
  for (const line of indexBody.split('\n')) {
    const match = INDEX_ROW_RE.exec(line)
    if (!match) continue
    const [, specFile, componentCell] = match
    const components = parseComponentCell(componentCell).map(({ name, segment }) => ({
      name,
      segment,
      tierWord: tierWordForSegment(segment),
    }))
    rows.push({ specFile, components })
  }
  return rows
}

// --- Section and state detection (spec source) --------------------------------------------------

// Every `#`-`######` heading's text, numbering (`1.`, `3a.`) stripped, plus every bold label at the
// very start of a (trimmed) line — see the file header for why both shapes are read.
export function extractHeadingsAndLabels(specSource) {
  const items = []
  for (const m of specSource.matchAll(/^#{1,6}\s+(.*)$/gm)) {
    items.push(m[1].replace(/^\d+[a-z]?\.\s*/i, '').trim())
  }
  for (const m of specSource.matchAll(/^\s*\*\*([A-Za-z][A-Za-z ]{1,40})\*\*/gm)) {
    items.push(m[1].trim())
  }
  return items
}

// Whole letter/hyphen runs, so a hyphenated compound (`four-state`) is one token rather than two —
// splitting on the hyphen too would let `state` re-match inside it, exactly the false match this
// tokenisation exists to prevent (see the file header, and C3 of the T571 remediation: `## 3. The
// four-state collapse` must genuinely not match "States").
function tokenise(text) {
  return text.match(/[a-z][a-z-]*/g) ?? []
}

function haystackTextMatchesKeyword(text, keyword) {
  return tokenise(text).some((token) => token.startsWith(keyword))
}

export function checkNineSections(specSource, sections) {
  const haystack = extractHeadingsAndLabels(specSource).map((s) => s.toLowerCase())
  return sections.filter((name) => {
    const keyword = sectionKeyword(name)
    return !haystack.some((text) => haystackTextMatchesKeyword(text, keyword))
  })
}

// True when the bold span starting at `matchIndex` opens a new clause rather than sitting mid-
// sentence: the nearest non-whitespace character before it (skipping one optional `-`/`*` bullet
// marker) is the start of the string, a newline, a sentence-ending mark (`.`, `!`, `?`, `:`, `;`) or
// an em/en dash. This is the boundary a "line-leading" bold span (`- **default** — ...`) already
// satisfies, generalised to also admit a *sentence*-leading one on a shared line — the inline,
// run-on-paragraph shape `shared-primitives.md`'s `Callout`, `Badge`, `Skeleton` and `Dialog` write
// their States section in (`**States** — **default** as above. **hover / active** — none; ...`),
// discovered when C1 of the T571 remediation scoped the vocabulary scan to each component's own
// section and found this shape had never been exercised on its own before (previously it only ever
// had to share a file with a sibling component using the bulleted form, which supplied the match).
function isClauseLeadingBoldSpan(text, matchIndex) {
  let i = matchIndex - 1
  while (i >= 0 && (text[i] === ' ' || text[i] === '\t')) i -= 1
  if (i < 0) return true
  if (text[i] === '\n') return true
  if ('.!?:;'.includes(text[i]) || text[i] === '—' || text[i] === '–') return true
  if (text[i] === '-' || text[i] === '*') {
    let j = i - 1
    while (j >= 0 && (text[j] === ' ' || text[j] === '\t')) j -= 1
    return j < 0 || text[j] === '\n'
  }
  return false
}

// Every clause-leading bold span (see `isClauseLeadingBoldSpan`) — line-leading, optionally bulleted
// (`- **default** — ...`, bare `**default** — ...`), and sentence-leading within a shared line
// (`**States** — **default** as above. **hover** — ...`) all ship today; see the file header. Raw
// content, not yet split on the `/`-combined shape (`hover / focus-visible / active`) a single
// bullet or clause may answer several states with at once.
//
// A bold span's own content never crosses a line in this repository's specs — every real label is
// a short word or two, and prose that follows one wraps, the label itself does not — so the pair is
// matched within one line (`[^*\n]+`), never across one. This is load-bearing, not cosmetic: an
// unrelated single, unpaired `*` elsewhere in the file (a glob like `--ds-icon-*` inside its own,
// unrelated bold phrase) is real prose this repository's specs already contain, and letting bold
// content cross lines lets that one stray `*` re-pair every `**` for the rest of the document,
// silently losing real labels far away from it (found while implementing C1 of the T571
// remediation) — confined to one line, the same stray `*` only ever breaks the one bold phrase it
// sits inside, exactly as it did before this function existed.
export function extractLineLeadingBoldSpans(specSource) {
  const items = []
  for (const m of specSource.matchAll(/\*\*([^*\n]+)\*\*/g)) {
    if (isClauseLeadingBoldSpan(specSource, m.index)) items.push(m[1])
  }
  return items
}

// Reduces one split-out token to the state name it leads with, discarding anything that follows
// (a trailing parenthetical is real and ships today — `tooltip.md`'s own "**default (closed)**",
// "**active (open, pinned)**" — so this takes the leading run of letters/hyphens rather than
// stripping non-letters everywhere, which would otherwise glue "default" and "(closed)" into one
// unmatched word).
function normaliseStateToken(token) {
  const trimmed = token
    .trim()
    .toLowerCase()
    .replace(/^and\s+/, '')
  const match = trimmed.match(/^[a-z-]+/)
  return match ? match[0].replace(/-+$/, '') : ''
}

export function checkVocabulary(specSource, vocabulary) {
  const answered = new Set()
  for (const raw of extractLineLeadingBoldSpans(specSource)) {
    for (const token of raw.split(/[/,]/)) {
      const normalised = normaliseStateToken(token)
      if (normalised) answered.add(normalised)
    }
  }
  return vocabulary.filter((word) => !answered.has(word))
}

// --- Per-component vocabulary scoping (C1) -------------------------------------------------------

// Every `#`-`######` heading's exact position and level, alongside the same numbering-stripped text
// `extractHeadingsAndLabels` already computes — kept separate because this rule needs the position
// in the source, not only the text.
function extractHeadingPositions(specSource) {
  const headings = []
  for (const m of specSource.matchAll(/^(#{1,6})\s+(.*)$/gm)) {
    headings.push({
      level: m[1].length,
      text: m[2].replace(/^\d+[a-z]?\.\s*/i, '').trim(),
      start: m.index,
      end: m.index + m[0].length,
    })
  }
  return headings
}

// A heading names a component when its (numbering-stripped) text is exactly the component's name,
// bare or backtick-fenced (`## Button`, `` ## 5. `Page` `` — both shapes `shared-primitives.md` and
// `structural-tier.md` already ship). Deliberately exact, not `.includes`: a heading like `` ## 4.
// `Opponent` for team matches `` (match-history.md) names a sub-concept, not the component itself,
// and must not be mistaken for one.
function headingNamesComponent(headingText, componentName) {
  const bare = headingText.replace(/^`([^`]+)`$/, '$1').trim()
  return bare === componentName
}

// The slice of `specSource` between a component's own heading (matched by `headingNamesComponent`)
// and the next heading at the same level or shallower — or `null` when the file has no such heading
// at all, or names it more than once (either way, there is no unambiguous boundary to scope to, and
// the caller falls back to the whole document). This is the per-component analogue of
// `findComponentRow`'s table-row lookup, for files whose per-component boundary is a `##` heading
// rather than a declarations-table row (`shared-primitives.md`'s `## Button`, `structural-tier.md`'s
// `` ## 5. `Page` ``) — see the file header for why a third shape (one shared section naming every
// component inline, `match-history.md`'s own "States") has no heading boundary and is intentionally
// left unscoped.
export function findComponentSection(specSource, componentName) {
  const headings = extractHeadingPositions(specSource)
  const matches = headings.filter((h) => headingNamesComponent(h.text, componentName))
  if (matches.length !== 1) return null
  const [heading] = matches
  const next = headings.find((h) => h.start > heading.start && h.level <= heading.level)
  return specSource.slice(heading.end, next ? next.start : specSource.length)
}

// One entry per component with at least one state left unanswered: `{ component, missing }`. A
// single-component file is already that component's own section in full, so no heading lookup is
// needed for it. A multi-component file scopes each component to `findComponentSection` when the
// file draws that boundary; when it does not (see the file header), that component is checked
// against the whole document, unchanged from before this rule existed.
export function checkComponentVocabulary(specSource, components, vocabulary) {
  if (components.length === 1) {
    const missing = checkVocabulary(specSource, vocabulary)
    return missing.length > 0 ? [{ component: components[0].name, missing }] : []
  }
  const findings = []
  for (const component of components) {
    const section = findComponentSection(specSource, component.name)
    const missing = checkVocabulary(section ?? specSource, vocabulary)
    if (missing.length > 0) findings.push({ component: component.name, missing })
  }
  return findings
}

// --- Per-component tier / surface-class declarations --------------------------------------------

function splitTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim())
}

function isSeparatorRow(line) {
  return /^\s*\|?[\s:|-]+\|?\s*$/.test(line)
}

// Every contiguous block of `|`-lines in the document, as `{ header, rows }`. Not scoped to "near
// the top" on purpose: a table naming components, tiers and surface classes is recognised by its
// header cells (below), wherever in the file it sits.
export function extractMarkdownTables(specSource) {
  const lines = specSource.split('\n')
  const blocks = []
  let current = []
  for (const line of lines) {
    if (/^\s*\|.*\|\s*$/.test(line)) {
      current.push(line)
    } else if (current.length > 0) {
      blocks.push(current)
      current = []
    }
  }
  if (current.length > 0) blocks.push(current)

  return blocks
    .filter((block) => block.length > 1)
    .map((block) => ({
      header: splitTableRow(block[0]),
      rows: block
        .slice(1)
        .filter((l) => !isSeparatorRow(l))
        .map(splitTableRow),
    }))
}

// A table is a "declarations table" once its header names all three columns this check needs — a
// component, a tier and a surface class (or "surface density", README's own heading spelling).
export function annotateDeclarationsTable(table) {
  const componentIdx = table.header.findIndex((h) => /component/i.test(h))
  const tierIdx = table.header.findIndex((h) => /\btier\b/i.test(h))
  const surfaceIdx = table.header.findIndex((h) => /surface|density/i.test(h))
  if (componentIdx === -1 || tierIdx === -1 || surfaceIdx === -1) return null
  return { ...table, componentIdx, tierIdx, surfaceIdx }
}

function findComponentRow(declarationsTables, componentName) {
  for (const table of declarationsTables) {
    for (const row of table.rows) {
      const cell = (row[table.componentIdx] ?? '').replace(/`/g, '').trim()
      if (cell === componentName) {
        return { tierCell: row[table.tierIdx] ?? '', surfaceCell: row[table.surfaceIdx] ?? '' }
      }
    }
  }
  return null
}

// A single-component file's own bold-label declaration, outside any table — the meta-header shape
// `structural-tier.md` and `tooltip.md` already use (`**Tier**: all nine are **primitives**.`).
// Returns the rest of that line, or `null` if no such label exists at all.
export function findLabelledValue(specSource, labelNames) {
  const lowerNames = labelNames.map((n) => n.toLowerCase())
  for (const m of specSource.matchAll(/^\*\*([A-Za-z ]+)\*\*\s*[:—-]?\s*(.*)$/gm)) {
    if (lowerNames.includes(m[1].trim().toLowerCase())) return m[2]
  }
  return null
}

function escapeRegExp(literal) {
  return literal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// A single class name, optionally backtick-fenced, matched as a whole word — `\b` on both sides so
// "prose" never matches inside "condensed" and a fenced "`dense`" still matches with the backticks
// consumed literally.
function classNamePattern(className) {
  return '`?\\b' + escapeRegExp(className) + '\\b`?'
}

// Every ordering of `surfaceClasses` — small and closed (README names two today, "neither `A`, `B`
// nor `Z`" if it ever grows), so a plain permutation is cheap and exact rather than approximated.
function permutations(items) {
  if (items.length <= 1) return [items]
  const result = []
  for (let i = 0; i < items.length; i += 1) {
    const rest = [...items.slice(0, i), ...items.slice(i + 1)]
    for (const tail of permutations(rest)) result.push([items[i], ...tail])
  }
  return result
}

// The "A, B, ..., joinWord Z" middle of both sanctioned multi-class forms below, for one fixed
// ordering of `orderedClasses`.
function classListBodyForOrder(orderedClasses, joinWord) {
  const [last, ...rest] = [...orderedClasses].reverse()
  const allButLast = rest.reverse().map(classNamePattern).join('\\s*,\\s*')
  return `${allButLast}\\s*,?\\s*${joinWord}\\s+${classNamePattern(last)}`
}

// The same "A, B, ..., joinWord Z" middle, but matching the class *set* regardless of which order
// the spec names them in — every permutation of `surfaceClasses`, alternated. Order-tolerance is
// the point (C4 of the T571 remediation): "`prose` or `dense`, by its own `density` prop" is the
// same semantic claim as "`dense` or `prose`, ..." with the two names swapped, and a spec arguing
// what a component is *not* reasonably leads with either name first.
function classListBodyAnySet(surfaceClasses, joinWord) {
  return permutations(surfaceClasses)
    .map((order) => classListBodyForOrder(order, joinWord))
    .join('|')
}

// The sanctioned negation's own head — "neither `A` nor `Z`" for two classes, "neither `A`, `B` nor
// `Z`" if the vocabulary ever grows past two, in any order the two names may appear. Not anchored
// to the start of the string (C4): "Not applicable: neither `dense` nor `prose` — ..." carries a
// prefix before "neither" and is exactly as sanctioned as the bare form.
function negationHeadPattern(surfaceClasses) {
  return new RegExp(`neither\\s+(?:${classListBodyAnySet(surfaceClasses, 'nor')})`, 'i')
}

// The sanctioned prop-selection form's own head — "`A` or `Z`" in either order — data-model.md §5's
// other admission-test exit besides "two components": "a prop, decided by the admission test."
// `structural-tier.md`'s own shape: "`dense` or `prose`, by its own `density` prop (§3) — the
// caller picks exactly one." This is not the same claim as naming both classes outright: the
// component itself never draws both densities at once, a caller-supplied prop picks one per
// instance, which is exactly what makes it "a prop" rather than "two components" in that sentence.
// Not anchored to the start of the string, for the same reason as the negation head above.
function classSelectionHeadPattern(surfaceClasses) {
  return new RegExp(`(?:${classListBodyAnySet(surfaceClasses, 'or')})`, 'i')
}

// A prop-selection claim must name the actual prop, not merely use the word "prop(s)" somewhere in
// the sentence — "by its own `density` prop" names one; "whichever the parent Panel props supply"
// does not (`Panel` is never backtick-fenced, "props" is plural and belongs to a *different*
// component, and nothing here is the caller's own prop). A named prop is a backtick-fenced
// identifier immediately followed by the singular word "prop".
const NAMED_PROP_RE = /`[^`]+`\s*prop\b/i

// Cue words that negate the class mention immediately preceding them, within the same clause —
// "never", "not", "no", "isn't"/"is not" all ship in this repository's specs, which habitually argue
// what a decision is *not* (C4's own example: "`prose`. Never `dense`: rows here are paragraphs,
// not data." is a correct, single-class claim naming the class it is not, not a conflict).
const NEGATION_CUE_RE = /\b(?:never|not|no|isn['’]t|is\s+not)\s*$/i

// The start of the clause containing `matchIndex` — the char after the nearest clause-ending
// punctuation (`.`, `;`, `:`, an em/en dash, or a newline) at or before it, or the start of the
// string when there is none. A negation only counts within its own clause, so an earlier negation
// elsewhere in the sentence never reaches across a period into an unrelated claim.
function clauseStartBefore(text, index) {
  const boundaries = ['.', ';', ':', '—', '–', '\n'].map((ch) => text.lastIndexOf(ch, index - 1))
  return Math.max(-1, ...boundaries) + 1
}

function isNegatedOccurrence(text, matchIndex) {
  const prefix = text.slice(clauseStartBefore(text, matchIndex), matchIndex)
  return NEGATION_CUE_RE.test(prefix.trim())
}

// For each of `surfaceClasses`, whether `text` names it as a positive claim (an occurrence not
// immediately preceded, in its own clause, by a negation cue) and/or negates it (an occurrence that
// is). A class mentioned only ever negated is not a claim — "Never `dense`" beside a positive claim
// of `prose` is how this repository's specs name the class a component is *not*, and must not read
// as if both had been claimed.
function classifyOccurrences(text, surfaceClasses) {
  return surfaceClasses.map((className) => {
    const pattern = new RegExp(classNamePattern(className), 'gi')
    let positive = false
    let negated = false
    for (const m of text.matchAll(pattern)) {
      if (isNegatedOccurrence(text, m.index)) negated = true
      else positive = true
    }
    return { className, positive, negated }
  })
}

// Classifies one surface-class declaration cell/value against the vocabulary `surfaceClasses`
// (`deriveSurfaceClasses`, never hardcoded). Every accepted shape (C4 of the T571 remediation
// documents each one so the next spec author does not have to discover it by running the check):
//   - exactly one class named as a claim (`` `dense` ``) — `{ valid: true, kind: 'declared' }`.
//   - the sanctioned negation, either order, with a non-empty reason after it that does not itself
//     name a class as a claim (`` neither `dense` nor `prose` — a control, not a surface with a
//     density of its own. ``, `` Not applicable: neither `prose` nor `dense` — ... ``) —
//     `{ valid: true, kind: 'inapplicable' }`.
//   - the sanctioned prop-selection form, either order, naming both classes joined by "or" and one
//     backtick-fenced, singular `prop` (`` `dense` or `prose`, by its own `density` prop — the
//     caller picks exactly one. ``) — `{ valid: true, kind: 'prop-selected' }` — data-model.md §5's
//     "or a prop" exit.
//   - a positive claim naming one class while explicitly negating the other, in either order
//     (`` `prose`. Never `dense`: rows here are paragraphs, not data. ``) — `{ valid: true, kind:
//     'declared' }`, exactly as a bare single-class claim is: this repository's specs routinely
//     argue what a decision is not, and a negated mention of the other class is not a second claim.
// Ways to fail:
//   - nothing recognisable at all (empty, `null`, bare "N/A") — `{ valid: false, kind: 'missing' }`.
//   - the negation's head with no reason after it (a bare "neither `dense` nor `prose`") —
//     `{ valid: false, kind: 'bare-negation' }` — FR-036 requires the "what happens instead" clause,
//     exactly as it does for a state.
//   - the negation's reason itself makes a positive claim of a class (`` neither `dense` nor
//     `prose` — it is `dense`. ``, contradicting the "neither" it just made) —
//     `{ valid: false, kind: 'contradiction' }`.
//   - the "A or B" head present with no named prop after it (`` `dense` or `prose`, depending on
//     mood ``, `` `dense` or `prose`, whichever the parent Panel props supply ``) falls through to
//     the next rule, where naming both classes as positive claims is a conflict.
//   - more than one class named as a positive claim that is neither the negation nor the
//     prop-selection form — `{ valid: false, kind: 'conflict' }` — data-model.md §5: "every
//     component declares exactly one class. A component that would need both is two components or
//     a prop, decided by the admission test."
export function classifySurfaceClassDeclaration(rawText, surfaceClasses) {
  if (rawText === null) return { valid: false, kind: 'missing' }
  const text = rawText.trim()
  if (text.length === 0) return { valid: false, kind: 'missing' }

  const negationMatch = text.match(negationHeadPattern(surfaceClasses))
  if (negationMatch) {
    const reason = text
      .slice(negationMatch.index + negationMatch[0].length)
      .replace(/^\s*[—–-]\s*/, '')
      .trim()
    // Trailing punctuation with no actual words (a bare "." closing the sentence, or nothing at
    // all) is not a reason — FR-036's "what happens instead" clause has to say something.
    if (!/[A-Za-z]/.test(reason)) return { valid: false, kind: 'bare-negation' }
    // A reason that itself claims a surface class contradicts the "neither ... nor ..." it just
    // made (C4's fifth row: "neither `dense` nor `prose` — it is `dense`.").
    if (classifyOccurrences(reason, surfaceClasses).some((o) => o.positive)) {
      return { valid: false, kind: 'contradiction' }
    }
    return { valid: true, kind: 'inapplicable' }
  }

  const selectionMatch = text.match(classSelectionHeadPattern(surfaceClasses))
  if (selectionMatch && NAMED_PROP_RE.test(text)) {
    return { valid: true, kind: 'prop-selected' }
  }

  const occurrences = classifyOccurrences(text, surfaceClasses)
  const positiveClasses = occurrences.filter((o) => o.positive)
  if (positiveClasses.length === 0) return { valid: false, kind: 'missing' }
  if (positiveClasses.length > 1) return { valid: false, kind: 'conflict' }
  return { valid: true, kind: 'declared' }
}

// One finding per missing or malformed declaration: `{ component, kind: 'tier' | 'surface-class' |
// 'surface-class-conflict' | 'surface-class-bare-negation' | 'surface-class-contradiction' |
// 'no-row', detail }`. `kind: 'no-row'` only happens for a multi-component file (see the file
// header): a component sharing a file with siblings has nowhere else a declaration could be
// attributed to it.
export function checkComponentDeclarations(specSource, components, surfaceClasses) {
  const declarationsTables = extractMarkdownTables(specSource)
    .map(annotateDeclarationsTable)
    .filter(Boolean)
  const multi = components.length > 1
  const findings = []

  const pushSurfaceFinding = (componentName, detail) => {
    const result = classifySurfaceClassDeclaration(detail, surfaceClasses)
    if (result.valid) return
    if (result.kind === 'conflict') {
      findings.push({ component: componentName, kind: 'surface-class-conflict', detail })
    } else if (result.kind === 'bare-negation') {
      findings.push({ component: componentName, kind: 'surface-class-bare-negation', detail })
    } else if (result.kind === 'contradiction') {
      findings.push({ component: componentName, kind: 'surface-class-contradiction', detail })
    } else {
      findings.push({ component: componentName, kind: 'surface-class', detail })
    }
  }

  for (const component of components) {
    const row = findComponentRow(declarationsTables, component.name)
    if (row) {
      if (!row.tierCell.toLowerCase().includes(component.tierWord)) {
        findings.push({ component: component.name, kind: 'tier', detail: row.tierCell })
      }
      pushSurfaceFinding(component.name, row.surfaceCell)
      continue
    }
    if (multi) {
      findings.push({ component: component.name, kind: 'no-row' })
      continue
    }
    const tierText = findLabelledValue(specSource, ['tier'])
    if (tierText === null || !tierText.toLowerCase().includes(component.tierWord)) {
      findings.push({ component: component.name, kind: 'tier', detail: tierText })
    }
    const surfaceText = findLabelledValue(specSource, ['surface class', 'surface density'])
    pushSurfaceFinding(component.name, surfaceText)
  }
  return findings
}

// --- Component directories with no Index row at all ---------------------------------------------

const TIER_SEGMENTS = ['primitives', 'composites', 'screens']

// Every immediate component directory under `src/{primitives,composites,screens}/`, as
// `<segment>/<Name>` — the same shape `parseIndexTable`'s components carry.
export function listComponentDirs(rootSrcDir) {
  const dirs = []
  for (const segment of TIER_SEGMENTS) {
    const segmentDir = path.join(rootSrcDir, segment)
    let entries
    try {
      entries = readdirSync(segmentDir)
    } catch {
      continue
    }
    for (const entry of entries) {
      if (statSync(path.join(segmentDir, entry)).isDirectory()) {
        dirs.push(`${segment}/${entry}`)
      }
    }
  }
  return dirs.sort()
}

export function findUnindexedComponentDirs(componentDirsOnDisk, indexedDirs) {
  return componentDirsOnDisk.filter((d) => !indexedDirs.has(d)).sort()
}

// --- Orchestration ------------------------------------------------------------------------------

// Runs every rule above over an in-memory model of the specs directory (README already parsed into
// its three derived vocabularies plus the Index rows, every spec file's source keyed by filename,
// and the on-disk component directory list) and returns one formatted finding string per problem —
// see the file header for the message shapes. Pure: no filesystem access, so
// spec-completeness.test.mjs can prove every rule fails on a small fixture without touching the
// real (currently incomplete — T570 in flight) specs directory.
export function evaluateSpecsDirectory({
  sections,
  vocabulary,
  surfaceClasses,
  indexRows,
  specSources,
  exemptFiles,
  componentDirsOnDisk,
}) {
  const findings = []
  const indexedDirs = new Set()

  for (const { specFile, components } of indexRows) {
    for (const { segment, name } of components) indexedDirs.add(`${segment}/${name}`)

    if (exemptFiles.has(specFile)) continue

    const source = specSources.get(specFile)
    if (source === undefined) {
      findings.push(
        `README.md's Index names \`${specFile}\`, but packages/design-system/specs/${specFile} ` +
          'does not exist.',
      )
      continue
    }

    for (const missingSection of checkNineSections(source, sections)) {
      findings.push(
        `packages/design-system/specs/${specFile}: missing section "${missingSection}" — no ` +
          `heading or bold label found naming it (README.md, "Every spec has nine sections").`,
      )
    }

    if (components.length === 0) {
      for (const missingState of checkVocabulary(source, vocabulary)) {
        findings.push(
          `packages/design-system/specs/${specFile}: state "${missingState}" is not answered — no ` +
            `"**${missingState}**" declaration found (FR-035: specify it, or record why it does not ` +
            'apply and what happens instead).',
        )
      }
      continue
    }

    for (const { component, missing } of checkComponentVocabulary(source, components, vocabulary)) {
      for (const missingState of missing) {
        findings.push(
          `packages/design-system/specs/${specFile}: component \`${component}\` — state ` +
            `"${missingState}" is not answered — no "**${missingState}**" declaration found within ` +
            `its own section (FR-035: specify it, or record why it does not apply and what happens ` +
            'instead).',
        )
      }
    }

    for (const finding of checkComponentDeclarations(source, components, surfaceClasses)) {
      if (finding.kind === 'no-row') {
        findings.push(
          `packages/design-system/specs/${specFile}: component \`${finding.component}\` has no ` +
            'declarations-table row — this file covers more than one component, so tier and ' +
            'surface class are owed one row each in a table (T570).',
        )
      } else if (finding.kind === 'tier') {
        const componentDef = components.find((c) => c.name === finding.component)
        findings.push(
          `packages/design-system/specs/${specFile}: component \`${finding.component}\` declares ` +
            `no tier — expected something naming "${componentDef.tierWord}" ` +
            `(its directory: src/${componentDef.segment}/${finding.component}/)` +
            (finding.detail ? `, found "${finding.detail.trim()}" instead.` : ', found nothing.'),
        )
      } else if (finding.kind === 'surface-class-conflict') {
        findings.push(
          `packages/design-system/specs/${specFile}: component \`${finding.component}\` declares ` +
            `more than one surface class as a claim (found "${finding.detail.trim()}") — ` +
            `data-model.md §5: "every component declares exactly one class. A component that would ` +
            'need both is two components or a prop, decided by the admission test."',
        )
      } else if (finding.kind === 'surface-class-bare-negation') {
        findings.push(
          `packages/design-system/specs/${specFile}: component \`${finding.component}\` records ` +
            `neither surface class applies (found "${finding.detail.trim()}") but gives no reason — ` +
            'FR-036 requires "what happens instead" for a declared-inapplicable answer, exactly as ' +
            'it does for a state.',
        )
      } else if (finding.kind === 'surface-class-contradiction') {
        findings.push(
          `packages/design-system/specs/${specFile}: component \`${finding.component}\` records ` +
            `neither surface class applies, but its own reason claims one (found ` +
            `"${finding.detail.trim()}") — the "what happens instead" clause must not name the ` +
            'class the negation just ruled out.',
        )
      } else {
        findings.push(
          `packages/design-system/specs/${specFile}: component \`${finding.component}\` declares ` +
            `no surface class — expected one of ${surfaceClasses.map((c) => `"${c}"`).join(' / ')}, ` +
            'or the sanctioned negation ("neither ... nor ... — <what it is instead>")' +
            (finding.detail ? `, found "${finding.detail.trim()}" instead.` : ', found nothing.'),
        )
      }
    }
  }

  for (const dir of findUnindexedComponentDirs(componentDirsOnDisk, indexedDirs)) {
    findings.push(
      `packages/design-system/src/${dir} has no row in README.md's Index table naming it — add ` +
        'one (or extend an existing brace group) so this check can verify its spec.',
    )
  }

  return findings
}

function main() {
  const readmeSource = readFileSync(readmePath, 'utf8')
  const sections = deriveNineSections(readmeSource)
  const vocabulary = deriveVocabulary(readmeSource)
  const surfaceClasses = deriveSurfaceClasses(readmeSource)
  const indexRows = parseIndexTable(readmeSource)

  const specSources = new Map()
  for (const entry of readdirSync(specsDir)) {
    if (entry.endsWith('.md') && entry !== 'README.md') {
      specSources.set(entry, readFileSync(path.join(specsDir, entry), 'utf8'))
    }
  }

  const componentDirsOnDisk = listComponentDirs(srcDir)

  const findings = evaluateSpecsDirectory({
    sections,
    vocabulary,
    surfaceClasses,
    indexRows,
    specSources,
    exemptFiles: EXEMPT_SPEC_FILES,
    componentDirsOnDisk,
  })

  if (findings.length > 0) {
    for (const finding of findings) fail(finding)
    fail(
      `${findings.length} finding${findings.length === 1 ? '' : 's'} across ` +
        `${indexRows.length} Index row${indexRows.length === 1 ? '' : 's'} and ` +
        `${componentDirsOnDisk.length} component director${componentDirsOnDisk.length === 1 ? 'y' : 'ies'}.`,
    )
    return
  }

  log(
    `${indexRows.length} Index rows and ${componentDirsOnDisk.length} component directories agree: ` +
      `every mapped spec answers all ${sections.length} sections and all ${vocabulary.length} ` +
      'states, and declares a tier and a surface class for every component it covers.',
  )
}

// Only run when invoked directly (`node scripts/checks/spec-completeness.mjs`) —
// spec-completeness.test.mjs imports the functions above without triggering the scan or the
// process exit code, the same guard token-scale.mjs and story-baselines.mjs use.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
