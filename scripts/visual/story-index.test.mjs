// T693 piece 5: every reader of the built index that means "the stories this package publishes"
// skips a `state-coverage-fixture` story by tag, and only the runtime pass asks for fixtures. Each
// test plants a tagged entry in an index and shows what the reader does with it.
//
// How each reader is proved:
//   - `listStories` (the one function the readers share) and `fixtureStoryFiles`: called directly.
//   - the state-signal sweep's reader (`indexedStories`, `buildStateSignalWork`): real functions,
//     called directly on an index carrying a plant.
//   - `.github/workflows/baselines.yml`'s inline unit list: the script is extracted from the workflow
//     and run against a planted index, since it cannot import a module.
//   - `scripts/visual/run.mjs` (capture units and the accessibility scan they carry) and
//     `scripts/checks/story-baselines.mjs`: scripts with side effects on a fixed index path, so what
//     is asserted is that each takes its stories from `listStories` and carries no filter of its own
//     that could forget the tag. The runtime pass itself is the one caller of `includeFixtures`.
//   - the generated region of row 8 of `packages/design-system/specs/README.md`
//     (`scripts/checks/state-coverage.mjs`) reads no index today: it will read the runtime manifest
//     (T694), whose fixture entries it skips by the same tag — that task's test.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { buildStateSignalWork, indexedStories } from './state-signal-model.mjs'
import {
  FIXTURE_TAG,
  FULL_PAGE_TAG,
  fixtureStoryFiles,
  isFullPageEntry,
  listStories,
} from './story-index.mjs'

const require = createRequire(import.meta.url)
const ts = require('typescript')

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

const PLANT = {
  type: 'story',
  id: 'state-coverage-fixture-plants--planted',
  importPath: './.storybook/fixtures/Plants.stories.tsx',
  exportName: 'Planted',
  tags: ['test', FIXTURE_TAG],
}
const REAL = {
  type: 'story',
  id: 'primitives-button--primary',
  importPath: './src/primitives/Button/Button.stories.tsx',
  exportName: 'Primary',
  tags: ['dev', 'autodocs'],
}
const DOCS = {
  type: 'docs',
  id: 'primitives-button--docs',
  importPath: './src/primitives/Button/Button.stories.tsx',
  tags: ['autodocs'],
}
const index = { v: 5, entries: { [REAL.id]: REAL, [PLANT.id]: PLANT, [DOCS.id]: DOCS } }

test('listStories skips a fixture by tag and a docs entry by type; includeFixtures is the runtime pass', () => {
  assert.deepEqual(
    listStories(index).map((e) => e.id),
    [REAL.id],
  )
  assert.deepEqual(
    listStories(index, { includeFixtures: true })
      .map((e) => e.id)
      .sort(),
    [PLANT.id, REAL.id].sort(),
  )
})

test('listStories reads the older `stories` key too, and an entry with no `type`', () => {
  const old = { stories: { a: { id: 'a', tags: [FIXTURE_TAG] }, b: { id: 'b' } } }
  assert.deepEqual(
    listStories(old).map((e) => e.id),
    ['b'],
  )
})

test('fixtureStoryFiles names the files that hold fixtures, relative to the package', () => {
  assert.deepEqual([...fixtureStoryFiles(index)], ['.storybook/fixtures/Plants.stories.tsx'])
})

test('the state-signal sweep neither indexes a fixture nor reports its file as unindexed', () => {
  assert.deepEqual(
    indexedStories(index).map((s) => s.id),
    [REAL.id],
  )
  const work = buildStateSignalWork({
    index,
    readSource: () => 'export default {}\nexport const Primary = {}\n',
    // The fixture file is on disk (the walker reaches `.storybook/fixtures`) and in the index with
    // no published story: it must not surface as "a story file the index lists nothing for".
    diskFiles: [
      '.storybook/fixtures/Plants.stories.tsx',
      'src/primitives/Button/Button.stories.tsx',
    ],
  })
  assert.deepEqual(
    work.discoveryGaps.filter((g) => g.kind === 'story-file-not-indexed'),
    [],
  )
  assert.equal(work.indexedStoryCount, 1)
})

test('baselines.yml expands no capture unit for a fixture (its inline script, run against a planted index)', () => {
  const workflow = readFileSync(path.join(rootDir, '.github', 'workflows', 'baselines.yml'), 'utf8')
  const match = workflow.match(
    /cat <<'JS' > "\$RUNNER_TEMP\/visual-stories\.mjs"\n([\s\S]*?)\n\s*JS\n/,
  )
  assert.ok(match, 'the inline unit-list script is no longer found in baselines.yml')
  // The heredoc is indented as YAML; strip that indent so the script is plain JS.
  const lines = match[1].split('\n')
  const indent = Math.min(...lines.filter((l) => l.trim()).map((l) => l.match(/^ */)[0].length))
  const script = lines.map((l) => l.slice(indent)).join('\n')

  const dir = mkdtempSync(path.join(tmpdir(), 'baselines-units-'))
  try {
    const indexDir = path.join(dir, 'packages', 'design-system', 'storybook-static')
    mkdirSync(indexDir, { recursive: true })
    writeFileSync(path.join(indexDir, 'index.json'), JSON.stringify(index))
    writeFileSync(path.join(dir, 'units.mjs'), script)
    const result = spawnSync('node', ['units.mjs'], {
      cwd: dir,
      encoding: 'utf8',
      env: { ...process.env, STORIES_DIR: dir },
    })
    assert.equal(result.status, 0, result.stderr)
    const units = JSON.parse(readFileSync(path.join(dir, 'visual-stories.json'), 'utf8'))
    assert.ok(units.length > 0)
    assert.ok(
      units.every((u) => u.id === REAL.id),
      'a fixture story got capture units',
    )
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('run.mjs and story-baselines.mjs take their stories from listStories, with no filter of their own', () => {
  for (const file of ['scripts/visual/run.mjs', 'scripts/checks/story-baselines.mjs']) {
    const source = readFileSync(path.join(rootDir, file), 'utf8')
    assert.match(
      source,
      /listStories\(index\)/,
      `${file} does not read stories through listStories`,
    )
    assert.doesNotMatch(source, /entry\.type === 'story'/, `${file} filters index entries itself`)
  }
})

test('only the runtime pass asks for fixtures', () => {
  const callers = []
  for (const file of [
    'scripts/visual/run.mjs',
    'scripts/visual/state-signal-model.mjs',
    'scripts/checks/story-baselines.mjs',
    'scripts/visual/state-coverage-runtime.mjs',
    'scripts/visual/state-coverage-runtime-model.mjs',
  ]) {
    if (/includeFixtures:\s*true/.test(readFileSync(path.join(rootDir, file), 'utf8'))) {
      callers.push(file)
    }
  }
  assert.deepEqual(callers.sort(), [
    'scripts/visual/state-coverage-runtime-model.mjs',
    'scripts/visual/state-coverage-runtime.mjs',
  ])
})

// T703: the capture's full-page rule has one definition, which `run.mjs` builds its capture units with and
// the runtime pass records the frame with.
test('isFullPageEntry reads the built index tag and nothing else, and run.mjs builds its units with it', () => {
  assert.equal(FULL_PAGE_TAG, 'visual-full-page')
  assert.equal(isFullPageEntry({ tags: ['test', FULL_PAGE_TAG] }), true)
  assert.equal(isFullPageEntry({ tags: ['test'] }), false)
  assert.equal(isFullPageEntry({}), false)
  const runSource = readFileSync(path.join(rootDir, 'scripts/visual/run.mjs'), 'utf8')
  assert.match(runSource, /fullPage: isFullPageEntry\(entry\)/)
  assert.equal(runSource.includes("'visual-full-page'"), false)
})

// T710 (L5), T711, T712: the tag is written once. Every reader that can import the constant does, so a
// literal of it in a harness file is a second definition that a rename of the tag would leave behind.
// The files read are the capture and sweep specs and helpers (`tests/visual/*.ts(x)` and
// `tests/visual/fixtures/*.ts(x)`) and the Node scripts of `scripts/visual/` other than the definition and
// the tests; a single-quoted, double-quoted or template literal of the tag is a hit. The inline script
// of `.github/workflows/baselines.yml` cannot import, and a comment above its unit list says so.
//
// A file is read with its comments removed (`withoutComments`), not line by line: a line that starts with
// a comment marker can carry code after the comment, and a skipped line hides it. Comments name the tag in
// backticks, and a message that spells it between escaped backticks is not a literal of it.
//
// What a comment is, is decided by the TypeScript parser the repository already resolves (a root
// devDependency), not by a character loop: a regular expression literal, a template literal and JSX text
// are tokens of the parse, so a `//` or a quote inside one starts no comment and opens no string. A file
// of this harness is valid source; the parser would read an invalid one as best it can, and nothing here
// asserts what it would make of it.
function withoutComments(text, fileName) {
  const kind = fileName.endsWith('.tsx')
    ? ts.ScriptKind.TSX
    : fileName.endsWith('.ts')
      ? ts.ScriptKind.TS
      : ts.ScriptKind.JS
  const source = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, kind)
  const ranges = new Map()
  const collect = (pos) => {
    for (const range of [
      ...(ts.getLeadingCommentRanges(text, pos) ?? []),
      ...(ts.getTrailingCommentRanges(text, pos) ?? []),
    ]) {
      ranges.set(range.pos, range.end)
    }
  }
  const visit = (node) => {
    // A documentation comment is trivia, and the parser also returns it among a node's children: its
    // leaves sit inside the comment, where a `//` after a tag would be read as a line comment that runs
    // past the end of the block.
    if (ts.isJSDoc(node)) return
    const children = node.getChildren(source)
    // The text of a JSX element is not trivia: a `//` in it is text.
    if (children.length === 0 && node.kind !== ts.SyntaxKind.JsxText) collect(node.getFullStart())
    for (const child of children) visit(child)
  }
  visit(source)
  let out = ''
  let at = 0
  for (const [pos, end] of [...ranges].sort((a, b) => a[0] - b[0])) {
    // Two comments cannot overlap in a valid source. If they do, the scan no longer knows what a comment
    // is, and it must stop rather than return text.
    if (pos < at) throw new Error(`${fileName}: comment ranges overlap at ${pos}`)
    out += text.slice(at, pos) + ' '
    at = end
  }
  return out + text.slice(at)
}

function scanHarnessForTagLiteral(root) {
  const sourceIn = (dir) =>
    readdirSync(path.join(root, dir), { withFileTypes: true })
      .filter((entry) => entry.isFile() && /\.tsx?$/.test(entry.name))
      .map((entry) => `${dir}/${entry.name}`)
  const testFiles = [...sourceIn('tests/visual'), ...sourceIn('tests/visual/fixtures')]
  const scriptFiles = readdirSync(path.join(root, 'scripts/visual'))
    .filter(
      (name) =>
        /\.(mjs|cjs)$/.test(name) && !name.endsWith('.test.mjs') && name !== 'story-index.mjs',
    )
    .map((name) => `scripts/visual/${name}`)
  const literal = new RegExp(`['"\`]${FULL_PAGE_TAG}['"\`]`)
  const offenders = [...testFiles, ...scriptFiles].filter((file) =>
    literal.test(withoutComments(readFileSync(path.join(root, file), 'utf8'), file)),
  )
  return { testFiles, scriptFiles, offenders, literal }
}

test('no harness file writes the full-page tag as a string literal', () => {
  const { testFiles, scriptFiles, offenders, literal } = scanHarnessForTagLiteral(rootDir)
  // Each of the two sets is found on its own: either half alone is more than a handful of files, so a
  // glob that lost the other half still passes a total.
  assert.ok(testFiles.length > 5, 'the scan found the specs and helpers under tests/visual')
  assert.ok(
    testFiles.some((file) => file.startsWith('tests/visual/fixtures/')),
    'the scan found tests/visual/fixtures',
  )
  assert.ok(scriptFiles.length > 5, 'the scan found the Node scripts of scripts/visual')
  assert.deepEqual(offenders, [])
  // The contrast: the definition itself holds the literal, which is what the scan is looking for.
  assert.match(readFileSync(path.join(rootDir, 'scripts/visual/story-index.mjs'), 'utf8'), literal)
})

test('the full-page tag scan flags a quoted, double-quoted and template literal in the specs, the fixtures and the scripts, and an empty directory finds no files', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-scan-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    // The contrast: the tag named in a comment or between escaped backticks is not a literal of it.
    put(
      'tests/visual/prose.ts',
      `// the \`${FULL_PAGE_TAG}\` tag\n/*\n * \`${FULL_PAGE_TAG}\`\n */\nconst m = \`says \\\`${FULL_PAGE_TAG}\\\` here\`\n`,
    )
    assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [])
    for (const [file, text] of [
      ['tests/visual/single.ts', `const t = '${FULL_PAGE_TAG}'\n`],
      ['tests/visual/double.ts', `const t = "${FULL_PAGE_TAG}"\n`],
      ['tests/visual/template.ts', `const t = \`${FULL_PAGE_TAG}\`\n`],
      ['tests/visual/fixtures/template.ts', `const t = \`${FULL_PAGE_TAG}\`\n`],
      ['scripts/visual/template.mjs', `const t = \`${FULL_PAGE_TAG}\`\n`],
    ]) {
      put(file, text)
      assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [file], file)
      rmSync(path.join(scratch, file))
    }
    // A set with no file is empty, which the real scan's per-set assertions would refuse.
    rmSync(path.join(scratch, 'tests/visual/fixtures/clean.ts'))
    assert.deepEqual(scanHarnessForTagLiteral(scratch).testFiles, [
      'tests/visual/clean.ts',
      'tests/visual/prose.ts',
    ])
    assert.equal(
      scanHarnessForTagLiteral(scratch).testFiles.some((f) =>
        f.startsWith('tests/visual/fixtures/'),
      ),
      false,
    )
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

// T712 (13): a comment marker at the start of a line does not make the rest of the line a comment, and a
// `.tsx` file is code too.
test('T712 (13) plant: a literal after a block comment on the same line is a hit, a block comment’s own text is not, and a .tsx file is read', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-comment-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    for (const [file, text] of [
      // The literal follows a block comment that opens the line.
      ['tests/visual/after-block.ts', `/* note */ const t = '${FULL_PAGE_TAG}'\n`],
      ['tests/visual/after-block-multi.ts', `/*\n * note\n */ const t = '${FULL_PAGE_TAG}'\n`],
      ['tests/visual/after-star.ts', `const u = 1\n/* a */ /* b */ const t = "${FULL_PAGE_TAG}"\n`],
      // A `.tsx` file under the specs or the fixtures.
      ['tests/visual/view.tsx', `const t = '${FULL_PAGE_TAG}'\n`],
      ['tests/visual/fixtures/view.tsx', `const t = \`${FULL_PAGE_TAG}\`\n`],
    ]) {
      put(file, text)
      assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [file], file)
      rmSync(path.join(scratch, file))
    }
    // The contrast: the tag named inside comments of every kind, on lines that also carry code, is no hit,
    // and a `//` inside a string does not start a comment that would hide a literal after it.
    put(
      'tests/visual/comments.ts',
      [
        `const a = 1 // the '${FULL_PAGE_TAG}' tag`,
        `/* the '${FULL_PAGE_TAG}' tag */ const b = 2`,
        `/*`,
        ` * the "${FULL_PAGE_TAG}" tag`,
        ` */`,
        `const c = 3 /* "${FULL_PAGE_TAG}" */ + 4`,
        '',
      ].join('\n'),
    )
    assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [])
    put('tests/visual/url.ts', `const u = 'http://x/y'; const t = '${FULL_PAGE_TAG}'\n`)
    assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, ['tests/visual/url.ts'])
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

// T713 (a): the scan knows what a regular expression literal and JSX text are, because it reads the file
// with the TypeScript parser, not with a character loop. Each of the three shapes below hid a literal from
// the loop that T712 wrote and was caught by the line scan it replaced.
test('T713 (a) plant: a literal after a regular expression holding two slashes, after a quote inside a regular expression, and after an apostrophe in JSX text is a hit', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-regex-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    for (const [file, text] of [
      // The real line of `story-selection.mjs`, with a literal appended: `\//` is not a comment.
      [
        'scripts/visual/regex-slashes.mjs',
        `const importPath = (entry.importPath ?? '').replace(/^\\.\\//, ''); const t = '${FULL_PAGE_TAG}'\n`,
      ],
      // A quote inside a regular expression is not the start of a string.
      [
        'tests/visual/regex-quote.ts',
        `const r = /'/\nconst u = 'http://x/y'; const t = '${FULL_PAGE_TAG}'\n`,
      ],
      [
        'tests/visual/regex-dquote.ts',
        `const r = /"/\nconst u = "http://x/y"; const t = "${FULL_PAGE_TAG}"\n`,
      ],
      // An apostrophe in JSX text is not the start of a string.
      [
        'tests/visual/jsx-apostrophe.tsx',
        `export const A = () => <p>don't</p>\nconst u = 'http://x/y'; const t = '${FULL_PAGE_TAG}'\n`,
      ],
      [
        'tests/visual/fixtures/jsx-apostrophe.tsx',
        `export const A = () => <p>don't</p>\nconst u = 'http://x/y'; const t = \`${FULL_PAGE_TAG}\`\n`,
      ],
    ]) {
      put(file, text)
      assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [file], file)
      rmSync(path.join(scratch, file))
    }
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

// The files of this contrast are not green on both sides: the loop of T712 reads each as a hit (run
// against that loop, both files report the tag), so this is red before T713 in the safe direction, a
// comment read as code, a false hit.
test('T713 (a) contrast: a literal inside a real line comment or block comment is no hit, whatever precedes it on the line', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-regex-comment-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    put(
      'scripts/visual/after-regex.mjs',
      [
        `const p = (entry.importPath ?? '').replace(/^\\.\\//, '') // the '${FULL_PAGE_TAG}' tag`,
        `const q = /'/ /* the "${FULL_PAGE_TAG}" tag */`,
        `// don't`,
        `const half = 4 / 2 // 'visual-full-page'`,
        '',
      ].join('\n'),
    )
    put(
      'tests/visual/jsx.tsx',
      [
        `export const A = () => <p>don't // not a comment</p> // the '${FULL_PAGE_TAG}' tag`,
        `export const B = () => <p>{/* the '${FULL_PAGE_TAG}' tag */ 'x'}</p>`,
        '',
      ].join('\n'),
    )
    assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [])
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

// The two real files the review named: the regular expression line of the selection script keeps the
// rest of its line, and a comment of the open-surface test, which the loop of T712 read as code, is gone.
test('T713 (a) the real tree: the rest of the line after the regular expression of story-selection.mjs is kept, and the comment of open-surface.test.ts is removed', () => {
  const selection = withoutComments(
    readFileSync(path.join(rootDir, 'scripts/visual/story-selection.mjs'), 'utf8'),
    'story-selection.mjs',
  )
  assert.ok(selection.includes(`.replace(/^\\.\\//, '')`))
  assert.equal(selection.includes('// '), false, 'no line comment survives in the selection script')
  const surface = withoutComments(
    readFileSync(path.join(rootDir, 'tests/visual/fixtures/open-surface.test.ts'), 'utf8'),
    'open-surface.test.ts',
  )
  assert.equal(surface.includes('whole point of'), false)
  assert.ok(surface.includes('distinctSurfaceStops(walk)'))
})

// T714 (a): the parser returns the documentation-comment nodes among a node's children. A walk that enters
// one reads a `//` after a tag inside it as a line comment that runs to the end of the line, past the end
// of the block, so a literal after the block on the same line is hidden.
test('T714 (a) plant: a literal after a documentation comment holding a tag and a `//` is a hit, in .ts, .tsx and .mjs, and inside an object literal and a parameter list', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-jsdoc-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    const tag = `'${FULL_PAGE_TAG}'`
    const cases = []
    for (const [name, body] of [
      ['link', '{@link Foo} // see'],
      ['see', '@see // note'],
      ['type', '@type // note'],
      ['param', '@param // note'],
    ]) {
      cases.push(
        [`tests/visual/jsdoc-${name}.ts`, `/** ${body} */ const t = ${tag}\n`],
        [`tests/visual/jsdoc-${name}.tsx`, `/** ${body} */ const t = ${tag}\n`],
        [`scripts/visual/jsdoc-${name}.mjs`, `/** ${body} */ const t = ${tag}\n`],
      )
    }
    cases.push(
      // A documentation comment that opens a property of an object literal.
      ['tests/visual/jsdoc-object.ts', `const o = {\n  /** {@link Foo} // see */ b: ${tag},\n}\n`],
      [
        'tests/visual/jsdoc-params.ts',
        `function f(/** @param // note */ x = ${tag}) { return x }\n`,
      ],
    )
    // Every case is run before the assertion, so a failure names all the shapes that went undetected.
    const missed = []
    for (const [file, text] of cases) {
      put(file, text)
      if (scanHarnessForTagLiteral(scratch).offenders.join() !== file) missed.push(file)
      rmSync(path.join(scratch, file))
    }
    assert.deepEqual(missed, [])
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

test('T714 (a) contrast: a tag named in backticks on a later line of a documentation comment holding `{@link Foo} // more` is no hit', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-jsdoc-multi-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    put(
      'tests/visual/multi.ts',
      [
        '/**',
        ' * See {@link Foo} // more',
        ` * the \`${FULL_PAGE_TAG}\` tag`,
        ' */',
        'export const a = 1',
        '',
      ].join('\n'),
    )
    assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [])
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

test('T714 (a) contrast: a literal named inside a documentation comment with no `//` in it is no hit', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-jsdoc-plain-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    put(
      'tests/visual/plain.ts',
      [
        '/**',
        ` * the \`${FULL_PAGE_TAG}\` tag and '${FULL_PAGE_TAG}'`,
        ' */',
        `/** the "${FULL_PAGE_TAG}" tag */ export const b = 2`,
        '',
      ].join('\n'),
    )
    assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, [])
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

// T714 (a): the only input found that overlaps two ranges after the walk skips documentation comments is
// invalid source (found by generating combinations of comment, JSX and brace fragments): the parser
// recovers from the unclosed expression in the JSX element in a way that puts a comment inside another.
// A valid file of the harness has no such pair, so this pins that the scan stops, naming the file, and
// leaves open whether a later version of the parser recovers the same way.
test('T714 (a) the scan throws, naming the file, when two comment ranges overlap', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-overlap-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    put('tests/visual/overlap.tsx', '<p>{// y/</p>/**// y\n')
    assert.throws(
      () => scanHarnessForTagLiteral(scratch),
      /tests\/visual\/overlap\.tsx: comment ranges overlap/,
    )
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

// T714 (b): the text of a JSX element is not trivia. Without the guard in `withoutComments`, a text that
// starts with `//` is read as a line comment that hides the rest of the line.
test('T714 (b) plant: a literal after JSX text starting with `//` on the same line is a hit', () => {
  const scratch = mkdtempSync(path.join(tmpdir(), 'tag-literal-jsx-text-'))
  try {
    const put = (file, text) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), text)
    }
    put('tests/visual/clean.ts', 'export const a = 1\n')
    put('tests/visual/fixtures/clean.ts', 'export const b = 1\n')
    put('scripts/visual/clean.mjs', 'export const c = 1\n')
    put('tests/visual/jsx-slashes.tsx', `const A = <p>// see</p>; const t = '${FULL_PAGE_TAG}'\n`)
    assert.deepEqual(scanHarnessForTagLiteral(scratch).offenders, ['tests/visual/jsx-slashes.tsx'])
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})
