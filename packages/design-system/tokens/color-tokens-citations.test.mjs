// Guards the line citations of `specs/color-tokens.md`: §11.6's table and backtick `file:N` forms
// (T732) and the prose `line N` / `lines N–M` anywhere in the file (T733). Nothing else reads them:
// `scripts/checks/state-coverage.mjs --check-citations` only parses the README's row 8 region, so
// T731 had to repoint all seven by hand. The line number lives in the spec and only there; this
// file holds a substring of each cited line, which must sit on that line and nowhere else in the
// file, so a cited line that moves by one in either direction fails. A range's last line is the
// exception: it is often a lone `}`, so it need only be on neither neighbouring line.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const specPath = 'packages/design-system/specs/color-tokens.md'
const specText = readFileSync(path.join(repoRoot, specPath), 'utf8')
const readSource = (relPath) => {
  try {
    return readFileSync(path.join(repoRoot, relPath), 'utf8')
  } catch {
    return null
  }
}

// Keyed by subject: the cited path for prose, the table row's first cell without its `(:N)` for a
// row. One substring per cited line, in citation order. No line numbers, on purpose.
const pins = {
  'packages/design-system/src/screens/PrivacyNotice/index.tsx': ['controllerContact.contactRoute'],
  '`PrivacyNotice` `ContactBlock`': ['controllerContact.contactRoute'],
  '`PrivacyNotice` inline links': ['function InlineLink('],
  '`PrivacyNotice` `Contents`': ['flex min-h-11 items-center py-3 font-sans text-md text-link'],
  '`ThirdPartyObjectionForm`': ['<Link href={privacyNoticeHref}>'],
  '`AccountErasurePanel`': ['<Link href={homeHref}'],
  '`Footer`': ['<Link href={privacyNoticeHref}', '<Link href={objectionHref}'],
}

// The prose citations, in citation order. A prose citation does not name its file beside the
// number, so the file is held here and the paragraph holding the citation must name it. One
// substring per cited line; a range holds its first and last. No line numbers, on purpose.
const prosePins = [
  { file: 'packages/design-system/tokens/build-tokens.mjs', pins: ['function readJson(', '}'] },
  {
    file: 'packages/design-system/tokens/build-tokens.mjs',
    pins: ['Object.entries(color[theme])'],
  },
  {
    file: 'tests/visual/focus-ring.spec.ts',
    pins: ['const backgroundColor = await target.evaluate(', '})'],
  },
]

const componentRoots = ['primitives', 'composites', 'screens']

// Checks one cited line against its substring and returns the problems. `unique` is the rule for
// a single line and a range's first line: the substring occurs once in the whole file, so a line
// that moved by one cannot be satisfied by its neighbour. A range's last line cannot be unique (a
// lone `}`), so it instead must be on neither neighbouring line.
function checkCitedLine({ label, file, text, n, substring, rangeEnd = false }) {
  const fileLines = text.split('\n')
  if (n > fileLines.length) {
    return [`${label}: ${file}:${n} is past the end (file has ${fileLines.length} lines)`]
  }
  const problems = []
  if (!fileLines[n - 1].includes(substring)) {
    problems.push(
      `${label}: ${file}:${n} should contain ${JSON.stringify(substring)} but is ${JSON.stringify(fileLines[n - 1])}`,
    )
  }
  if (rangeEnd) {
    for (const neighbour of [n - 1, n + 1]) {
      if (fileLines[neighbour - 1]?.includes(substring)) {
        problems.push(
          `${label}: ${file}:${n} range end ${JSON.stringify(substring)} is also on neighbouring line ${neighbour}, so a range end that moved by one would pass`,
        )
      }
    }
    return problems
  }
  const occurrences = text.split(substring).length - 1
  if (occurrences > 1) {
    problems.push(
      `${label}: ${JSON.stringify(substring)} occurs ${occurrences} times in ${file}; it must be unique so a moved line fails`,
    )
  }
  return problems
}

// Parses every prose `line N` / `lines N–M` of the spec, §11.6 included. A paragraph is the
// unit, joined with spaces, so a citation wrapped across a line break still parses. Exactly two
// shapes are accepted; anything the pattern captured in another shape, or a line word still
// followed by a digit after the accepted ones are consumed, is reported rather than skipped.
function parseProse(specLines) {
  const citations = []
  const problems = []
  const paragraphs = []
  let current = null
  specLines.forEach((line, i) => {
    if (line.trim() === '') {
      current = null
      return
    }
    if (current === null) {
      current = { startLine: i + 1, lines: [] }
      paragraphs.push(current)
    }
    current.lines.push(line)
  })
  for (const { startLine, lines } of paragraphs) {
    const paragraph = lines.join(' ')
    const consumed = paragraph.replace(
      /\blines?\s+(\d+(?:\s*(?:[–—-]|,|and|to|&)\s*\d+)*)/gi,
      (match, numbers) => {
        const found = numbers.match(/\d+/g).map(Number)
        const plural = /^lines/i.test(match)
        if (!plural && found.length === 1) {
          citations.push({ lines: found, paragraph, startLine })
        } else if (
          plural &&
          found.length === 2 &&
          /^\s*[–-]\s*$/.test(numbers.replace(/\d+/g, '')) &&
          found[0] < found[1]
        ) {
          citations.push({ lines: found, paragraph, startLine })
        } else {
          problems.push(`unparsed line citation at spec line ${startLine}: "${match}"`)
        }
        return ' '
      },
    )
    // A `:` between the word and the digit is the `:N` shapes' business, not this one's.
    for (const leftover of consumed.match(/.{0,20}\blines?\b[^\w:]{0,6}\d.{0,20}/gi) ?? []) {
      problems.push(`unparsed line citation at spec line ${startLine}: …${leftover}…`)
    }
  }
  return { citations, problems }
}

// Parses §11.6 into { subject, file, lines } citations and the rest of the file into prose
// citations, and returns every problem found; an empty list means the spec and the sources agree,
// and `citations` / `proseCitations` let a test see what was parsed. `readSource(repoRelativePath)`
// returns the file's text or null, the only seam a fixture needs.
function parseAndCheck({ specText, readSource, pins, prosePins }) {
  const problems = []
  const citations = []
  const proseCitations = []
  const specLines = specText.split('\n')
  const start = specLines.findIndex((line) => /^### 11\.6\s/.test(line))
  if (start === -1)
    return {
      problems: ['section "### 11.6" not found in color-tokens.md'],
      citations,
      proseCitations,
    }
  const end = specLines.findIndex((line, i) => i > start && line.startsWith('### '))
  const section = specLines.slice(start, end === -1 ? undefined : end)

  const unconsumed = []
  for (const line of section) {
    let rest = line
    if (line.startsWith('|')) {
      const firstCell = line.split('|')[1] ?? ''
      const match = firstCell.match(/\((:\d+(?:,\s*:\d+)*)\)/)
      if (match) {
        const name = firstCell.match(/`([A-Z][A-Za-z0-9]*)`/)?.[1]
        const candidates = componentRoots
          .map((root) => `packages/design-system/src/${root}/${name}/index.tsx`)
          .filter((candidate) => readSource(candidate) !== null)
        const subject = firstCell.replace(match[0], '').trim()
        if (candidates.length === 1) {
          citations.push({
            subject,
            file: candidates[0],
            lines: match[1].match(/\d+/g).map(Number),
          })
        } else {
          problems.push(`${subject}: ${candidates.length} files match component "${name}"`)
        }
        // Only the parenthetical is consumed; a stray `:N` elsewhere in the cell stays visible.
        rest = line.replace(match[0], ' ')
      }
    } else {
      rest = line.replace(/`([\w./-]+):(\d+)`/g, (_, file, n) => {
        citations.push({ subject: file, file, lines: [Number(n)] })
        return ' '
      })
    }
    unconsumed.push(...(rest.match(/.{0,20}:\d.{0,20}/g) ?? []))
  }
  for (const text of unconsumed) problems.push(`unparsed ":N" in §11.6: …${text}…`)

  const cited = new Set(citations.map((citation) => citation.subject))
  for (const subject of Object.keys(pins)) {
    if (!cited.has(subject)) problems.push(`${subject}: pinned but no longer cited`)
  }

  for (const { subject, file, lines } of citations) {
    const substrings = pins[subject]
    if (!substrings) {
      problems.push(`${subject}: cited at ${file} with no pin`)
      continue
    }
    if (substrings.length !== lines.length) {
      problems.push(`${subject}: cites ${lines.length} line(s) but has ${substrings.length} pin(s)`)
      continue
    }
    const text = readSource(file)
    if (text === null) {
      problems.push(`${subject}: ${file} does not exist`)
      continue
    }
    lines.forEach((n, i) => {
      problems.push(...checkCitedLine({ label: subject, file, text, n, substring: substrings[i] }))
    })
  }

  // Outside §11.6 a `:N` form is not a citation this guard reads, so it must not appear at all.
  specLines.forEach((line, i) => {
    if (i >= start && (end === -1 || i < end)) return
    for (const match of line.match(/.{0,20}(?:`[\w./-]+:\d+`|\(:\d).{0,20}/g) ?? []) {
      problems.push(`unparsed ":N" outside §11.6 at spec line ${i + 1}: …${match}…`)
    }
  })

  const prose = parseProse(specLines)
  problems.push(...prose.problems)
  proseCitations.push(...prose.citations)
  if (proseCitations.length !== prosePins.length) {
    const extra =
      proseCitations.length > prosePins.length
        ? `${proseCitations.length - prosePins.length} citation(s) with no pin`
        : `${prosePins.length - proseCitations.length} pin(s) whose citation is gone`
    problems.push(
      `prose citations: found ${proseCitations.length} but ${prosePins.length} pinned (${extra})`,
    )
    return { problems, citations, proseCitations }
  }
  proseCitations.forEach((citation, i) => {
    const { file, pins: substrings } = prosePins[i]
    citation.file = file
    const label = `prose citation ${i + 1} (spec line ${citation.startLine})`
    if (!citation.paragraph.includes(path.basename(file))) {
      problems.push(`${label}: its paragraph does not name ${path.basename(file)}`)
    }
    if (substrings.length !== citation.lines.length) {
      problems.push(
        `${label}: cites ${citation.lines.length} line(s) but has ${substrings.length} pin(s)`,
      )
      return
    }
    const text = readSource(file)
    if (text === null) {
      problems.push(`${label}: ${file} does not exist`)
      return
    }
    const isRange = citation.lines.length === 2
    citation.lines.forEach((n, j) => {
      const rangeEnd = isRange && j === 1
      problems.push(...checkCitedLine({ label, file, text, n, substring: substrings[j], rangeEnd }))
    })
  })
  return { problems, citations, proseCitations }
}

const run = (overrides = {}) =>
  parseAndCheck({ specText, readSource, pins, prosePins, ...overrides })
const check = (overrides) => run(overrides).problems

// A readSource that serves `transform(text)` for one file and the real text for the rest.
const withEdited = (file, transform) => (relPath) => {
  const text = readSource(relPath)
  return relPath === file && text !== null ? transform(text) : text
}

const pinnedFiles = [
  'packages/design-system/src/screens/PrivacyNotice/index.tsx',
  'packages/design-system/src/screens/ThirdPartyObjectionForm/index.tsx',
  'packages/design-system/src/screens/AccountErasurePanel/index.tsx',
  'packages/design-system/src/composites/Footer/index.tsx',
]

test('every line citation of the spec names the lines its substrings sit on', () => {
  assert.deepEqual(check(), [])
})

test('the parser finds 7 citations over 8 lines, so an empty parse cannot pass', () => {
  const { citations } = run()
  assert.equal(citations.length, 7)
  assert.equal(citations.flatMap((citation) => citation.lines).length, 8)
})

test('a source line moved down by one fails', () => {
  for (const file of pinnedFiles) {
    const problems = check({ readSource: withEdited(file, (text) => `// inserted\n${text}`) })
    assert.ok(
      problems.some((p) => p.includes(file) && p.includes('should contain')),
      file,
    )
  }
})

test('a source line moved up by one fails', () => {
  for (const file of pinnedFiles) {
    const problems = check({
      readSource: withEdited(file, (text) => text.split('\n').slice(1).join('\n')),
    })
    assert.ok(
      problems.some((p) => p.includes(file) && p.includes('should contain')),
      file,
    )
  }
})

test('a citation number changed in the spec fails', () => {
  const problems = check({ specText: specText.replace('index.tsx:795', 'index.tsx:796') })
  assert.ok(problems.some((p) => p.includes(':796') && p.includes('should contain')))
  const row = check({ specText: specText.replace('(:45, :50)', '(:46, :50)') })
  assert.ok(row.some((p) => p.includes('`Footer`') && p.includes(':46')))
})

test('a table row without a pin fails', () => {
  const row = '| `ThirdPartyObjectionForm` (:214)'
  const added = specText.replace(row, `| \`Footer\` extra (:45) | x | y |\n${row}`)
  assert.notEqual(added, specText)
  assert.ok(
    check({ specText: added }).some((p) => p.includes('`Footer` extra') && p.includes('no pin')),
  )
})

test('a pin whose citation was removed fails', () => {
  const kept = specText.split('\n').filter((line) => !line.startsWith('| `AccountErasurePanel` (:'))
  assert.equal(kept.length, specText.split('\n').length - 1)
  const problems = check({ specText: kept.join('\n') })
  assert.ok(problems.some((p) => p.includes('`AccountErasurePanel`') && p.includes('pinned but')))
})

test('a ":N" shape the parser does not consume fails', () => {
  const prose = specText.replace(
    '### 11.6 What',
    'Also see index.tsx line :12 below.\n\n### 11.6 What',
  )
  assert.deepEqual(check({ specText: prose }), [])
  const inside = specText.replace('The concrete consequence', 'The concrete (line:12) consequence')
  assert.ok(check({ specText: inside }).some((p) => p.includes('unparsed')))
  const cell = specText.replace('| `Footer` (:45, :50)', '| `Footer` :51 (:45, :50)')
  assert.notEqual(cell, specText)
  assert.ok(check({ specText: cell }).some((p) => p.includes('unparsed') && p.includes(':51')))
})

test('a substring that also occurs on a neighbouring line fails', () => {
  for (const file of pinnedFiles) {
    const problems = check({
      readSource: withEdited(file, (text) => {
        const lines = text.split('\n')
        const substring = Object.values(pins)
          .flat()
          .find((s) => lines.some((line) => line.includes(s)))
        const at = lines.findIndex((line) => line.includes(substring))
        lines.splice(at + 1, 0, lines[at])
        return lines.join('\n')
      }),
    })
    assert.ok(
      problems.some((p) => p.includes(file) && p.includes('must be unique')),
      file,
    )
  }
})

test('a missing section, source file or line past the end fails', () => {
  assert.deepEqual(check({ specText: specText.replace('### 11.6', '### 11.66') }), [
    'section "### 11.6" not found in color-tokens.md',
  ])
  const gone = check({ readSource: (p) => (p.includes('/Footer/') ? null : readSource(p)) })
  assert.ok(gone.some((p) => p.includes('`Footer`') && p.includes('0 files match')))
  const short = check({ readSource: withEdited(pinnedFiles[3], () => 'one line\n') })
  assert.ok(short.some((p) => p.includes('past the end') && p.includes('file has 2 lines')))
})

test('the parser finds 3 prose citations over 5 lines, so an empty parse cannot pass', () => {
  const { proseCitations } = run()
  assert.equal(proseCitations.length, 3)
  assert.equal(proseCitations.flatMap((citation) => citation.lines).length, 5)
})

test('a line inserted above, or removed at, any cited line fails', () => {
  const { citations, proseCitations } = run()
  const everyCitation = [...citations, ...proseCitations]
  assert.equal(everyCitation.flatMap((citation) => citation.lines).length, 13)
  for (const { file, lines } of everyCitation) {
    for (const n of lines) {
      const insert = (text) => {
        const split = text.split('\n')
        split.splice(n - 1, 0, '// inserted')
        return split.join('\n')
      }
      const remove = (text) => {
        const split = text.split('\n')
        split.splice(n - 1, 1)
        return split.join('\n')
      }
      for (const [what, transform] of [
        ['inserted above', insert],
        ['removed at', remove],
      ]) {
        const problems = check({ readSource: withEdited(file, transform) })
        assert.ok(
          problems.some((p) => p.includes(`${file}:${n}`)),
          `${what} ${file}:${n}`,
        )
      }
    }
  }
})

test('a prose citation number changed in the spec fails', () => {
  const buildTokens = 'packages/design-system/tokens/build-tokens.mjs'
  const focusRing = 'tests/visual/focus-ring.spec.ts'
  for (const [from, to, file, n] of [
    ['lines 42–45', 'lines 42–46', buildTokens, 46],
    ['line 92', 'line 91', buildTokens, 91],
    ['lines 314–327', 'lines 315–327', focusRing, 315],
  ]) {
    const edited = specText.replace(from, to)
    assert.notEqual(edited, specText, from)
    assert.ok(
      check({ specText: edited }).some((p) => p.includes(`${file}:${n}`)),
      to,
    )
  }
})

test('a range end that is also on a neighbouring line fails; the same text elsewhere does not', () => {
  const file = 'packages/design-system/tokens/build-tokens.mjs'
  const doubled = check({
    readSource: withEdited(file, (text) => {
      const lines = text.split('\n')
      lines.splice(45, 0, lines[44])
      return lines.join('\n')
    }),
  })
  assert.ok(doubled.some((p) => p.includes(`${file}:45`) && p.includes('neighbouring')))
  assert.deepEqual(check({ readSource: withEdited(file, (text) => `${text}\n}\n`) }), [])
})

test('a line citation in a shape the parser does not accept fails', () => {
  for (const [from, to] of [
    ['lines 42–45', 'lines 42, 45'],
    ['lines 42–45', 'line 42–45'],
    ['lines 42–45', 'lines 42'],
    ['lines 42–45', 'lines 42–44–45'],
    ['lines 42–45', 'lines 42 and 45'],
    ['lines 42–45', 'lines 45–42'],
    ['### 11.6 What', 'See `build-tokens.mjs:42` here.\n\n### 11.6 What'],
    ['### 11.6 What', 'See (:42) here.\n\n### 11.6 What'],
  ]) {
    const edited = specText.replace(from, to)
    assert.notEqual(edited, specText, to)
    assert.ok(
      check({ specText: edited }).some((p) => p.includes('unparsed')),
      to,
    )
  }
  const wrapped = specText.replace('lines 42–45', 'lines\n42–45')
  assert.notEqual(wrapped, specText)
  assert.deepEqual(check({ specText: wrapped }), [])
})

test('a prose citation without a pin, or a pin without a citation, fails', () => {
  const added = check({ specText: `${specText}\nSee line 12 of build-tokens.mjs.\n` })
  assert.ok(added.some((p) => p.includes('found 4 but 3 pinned') && p.includes('no pin')))
  const removedSpec = specText.replace(' (line 92)', '')
  assert.notEqual(removedSpec, specText)
  const removed = check({ specText: removedSpec })
  assert.ok(
    removed.some((p) => p.includes('found 2 but 3 pinned') && p.includes('citation is gone')),
  )
})

test('a paragraph that no longer names its file fails', () => {
  const paragraph = specText.split(/\n\s*\n/).find((p) => p.includes('lines 42–45'))
  assert.ok(paragraph)
  const edited = specText.replace(paragraph, paragraph.replaceAll('build-tokens.mjs', 'other.mjs'))
  assert.notEqual(edited, specText)
  const problems = check({ specText: edited })
  assert.ok(problems.some((p) => p.includes('does not name build-tokens.mjs')))
})
