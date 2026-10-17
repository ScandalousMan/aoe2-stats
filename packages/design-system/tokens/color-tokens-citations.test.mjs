// Guards the line citations of `specs/color-tokens.md` §11.6 (T732). Nothing else reads them:
// `scripts/checks/state-coverage.mjs --check-citations` only parses the README's row 8 region, so
// T731 had to repoint all seven by hand. The line number lives in the spec and only there; this
// file holds a substring of each cited line, which must sit on that line and nowhere else in the
// file, so a cited line that moves by one in either direction fails.
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

const componentRoots = ['primitives', 'composites', 'screens']

// Parses §11.6 into { subject, file, lines } citations and returns every problem found; an empty
// list means the section and the sources agree, and `citations` lets a test see what was parsed.
// `readSource(repoRelativePath)` returns the file's text or null, the only seam a fixture needs.
function parseAndCheck({ specText, readSource, pins }) {
  const problems = []
  const citations = []
  const specLines = specText.split('\n')
  const start = specLines.findIndex((line) => /^### 11\.6\s/.test(line))
  if (start === -1)
    return { problems: ['section "### 11.6" not found in color-tokens.md'], citations }
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
    const fileLines = text.split('\n')
    lines.forEach((n, i) => {
      const substring = substrings[i]
      if (n > fileLines.length) {
        problems.push(
          `${subject}: ${file}:${n} is past the end (file has ${fileLines.length} lines)`,
        )
        return
      }
      if (!fileLines[n - 1].includes(substring)) {
        problems.push(
          `${subject}: ${file}:${n} should contain ${JSON.stringify(substring)} but is ${JSON.stringify(fileLines[n - 1])}`,
        )
      }
      const occurrences = text.split(substring).length - 1
      if (occurrences > 1) {
        problems.push(
          `${subject}: ${JSON.stringify(substring)} occurs ${occurrences} times in ${file}; it must be unique so a moved line fails`,
        )
      }
    })
  }
  return { problems, citations }
}

const run = (overrides = {}) => parseAndCheck({ specText, readSource, pins, ...overrides })
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

test('§11.6 line citations name the lines their substrings sit on', () => {
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
