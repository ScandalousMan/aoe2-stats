// T693 piece 1: the source-stamp transform (`packages/design-system/.storybook/source-stamp.mjs`)
// and the guarantee that none of it reaches `apps/web`. No browser, no build: the transform is a pure
// function of source text, and "absent from `apps/web`" is proved at two honest levels — the app's own
// Vite config never names the plugin (source level), and `scripts/checks/stamp-absent.mjs`, which CI
// runs over the output of `pnpm --filter web build`, fails on a planted stamp and passes on a clean
// directory (built-output level; the scan is exercised here on planted directories, the real build is
// the CI step's).
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import {
  cpSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  STAMP_ATTRIBUTE,
  isStampedFile,
  sourceStampPlugin,
  stampSource,
} from '../../packages/design-system/.storybook/source-stamp.mjs'
import { findStampedFiles } from '../checks/stamp-absent.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const FILE = 'packages/design-system/src/primitives/Widget/index.tsx'

test('stamps an intrinsic element with its repository-rooted file:line, on the line its tag starts', () => {
  const code = [
    'export function Widget() {',
    '  return (',
    '    <div className="x">',
    '      <button',
    '        type="button"',
    '      >',
    '        go',
    '      </button>',
    '      <input />',
    '    </div>',
    '  )',
    '}',
  ].join('\n')
  const out = stampSource(code, FILE)
  assert.ok(out)
  assert.match(out, new RegExp(`<div ${STAMP_ATTRIBUTE}="${FILE}:3" className="x">`))
  assert.match(out, new RegExp(`<button ${STAMP_ATTRIBUTE}="${FILE}:4"\\n`))
  assert.match(out, new RegExp(`<input ${STAMP_ATTRIBUTE}="${FILE}:9" />`))
  // No line moves: the transform only adds characters on the line it stamps.
  assert.equal(out.split('\n').length, code.split('\n').length)
})

test('does not stamp a component tag, a member expression or a fragment', () => {
  const code = 'const a = <><Button /><Foo.Bar /></>'
  assert.equal(stampSource(code, FILE), null)
})

test('stamps the props an element is cloned with, keyed to the call, in each argument shape', () => {
  const code = [
    "import { cloneElement } from 'react'",
    'export const a = (c) => cloneElement(c, { id: 1 })',
    'export const b = (c, p) => cloneElement(c, p)',
    'export const c2 = (c) => cloneElement(c)',
    'export const d = (c) => React.cloneElement(c, {})',
  ].join('\n')
  const out = stampSource(code, 'packages/design-system/src/primitives/Widget/clone.ts')
  assert.ok(out)
  const key = (line) =>
    `'${STAMP_ATTRIBUTE}': 'packages/design-system/src/primitives/Widget/clone.ts:${line}'`
  assert.ok(out.includes(`cloneElement(c, { ${key(2)}, id: 1 })`), out)
  assert.ok(out.includes(`cloneElement(c, { ${key(3)}, ...(p) })`), out)
  assert.ok(out.includes(`cloneElement(c, { ${key(4)} })`), out)
  assert.ok(out.includes(`React.cloneElement(c, { ${key(5)},})`), out)
})

test('the transformed source still parses and cloneElement stamps evaluate to the attribute', async () => {
  const out = stampSource(
    'export const f = (c, p) => cloneElement(c, p)',
    'packages/design-system/src/x.ts',
  )
  const calls = []
  const fn = new Function('cloneElement', `${out.replace('export const f =', 'return')}`)((c, p) =>
    calls.push(p),
  )
  fn('el', { id: 'x' })
  assert.deepEqual(calls[0], { [STAMP_ATTRIBUTE]: 'packages/design-system/src/x.ts:1', id: 'x' })
})

test('isStampedFile: design-system source only, never a story, a test or another package', () => {
  assert.equal(isStampedFile(FILE), true)
  assert.equal(isStampedFile('packages/design-system/src/lib/Spinner.tsx'), true)
  assert.equal(
    isStampedFile('packages/design-system/src/primitives/Button/Button.stories.tsx'),
    false,
  )
  assert.equal(isStampedFile('packages/design-system/src/primitives/Button/Button.test.tsx'), false)
  assert.equal(isStampedFile('packages/design-system/.storybook/fixtures/X.stories.tsx'), false)
  assert.equal(isStampedFile('apps/web/src/main.tsx'), false)
  assert.equal(isStampedFile('packages/design-system/src/index.css'), false)
})

test('the plugin stamps a design-system file and passes everything else through untouched', () => {
  const plugin = sourceStampPlugin({ rootDir })
  assert.equal(plugin.enforce, 'pre')
  const code = 'export const A = () => <span />'
  const abs = path.join(rootDir, FILE)
  const hit = plugin.transform(code, `${abs}?v=1`)
  assert.match(hit.code, new RegExp(`<span ${STAMP_ATTRIBUTE}="${FILE}:1" />`))
  assert.equal(plugin.transform(code, path.join(rootDir, 'apps/web/src/main.tsx')), null)
  assert.equal(
    plugin.transform(code, path.join(rootDir, 'packages/design-system/src/a.stories.tsx')),
    null,
  )
  assert.equal(plugin.transform(code, '\0virtual:thing'), null)
})

test('apps/web never wires the stamp: its Vite config does not name the plugin or its module', () => {
  const viteConfig = readFileSync(path.join(rootDir, 'apps/web/vite.config.ts'), 'utf8')
  assert.doesNotMatch(viteConfig, /source-stamp|sourceStampPlugin|ds-source-stamp/)
  const main = readFileSync(path.join(rootDir, 'packages/design-system/.storybook/main.ts'), 'utf8')
  assert.match(main, /sourceStampPlugin/, 'Storybook is the one place the plugin is wired')
})

test('stamp-absent: a built directory carrying the attribute is reported, a clean one is not', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'stamp-absent-'))
  try {
    mkdirSync(path.join(dir, 'assets'), { recursive: true })
    writeFileSync(path.join(dir, 'index.html'), '<div id="root"></div>')
    writeFileSync(path.join(dir, 'assets', 'app.js'), 'createElement("div",{className:"x"})')
    assert.deepEqual(findStampedFiles(dir), [])
    writeFileSync(
      path.join(dir, 'assets', 'leaked.js'),
      `createElement("div",{"${STAMP_ATTRIBUTE}":"a:1"})`,
    )
    assert.deepEqual(findStampedFiles(dir), [path.join('assets', 'leaked.js')])
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('an aliased cloneElement import is stamped like the plain name; an unrelated local of the same shape is not', () => {
  const file = 'packages/design-system/src/primitives/Widget/alias.ts'
  const aliased = stampSource(
    [
      "import { cloneElement as ce } from 'react'",
      'export const a = (c) => ce(c, { id: 1 })',
      'export const b = (c) => ce(c)',
    ].join('\n'),
    file,
  )
  assert.ok(aliased)
  assert.ok(aliased.includes(`ce(c, { '${STAMP_ATTRIBUTE}': '${file}:2', id: 1 })`), aliased)
  assert.ok(aliased.includes(`ce(c, { '${STAMP_ATTRIBUTE}': '${file}:3' })`), aliased)
  // `ce` here is the author's own function, not an alias of React's: nothing to stamp.
  assert.equal(
    stampSource('const ce = (c, p) => c\nexport const a = (c) => ce(c, { id: 1 })', file),
    null,
  )
})

test('a cloneElement call with a spread argument throws at transform time naming file:line, instead of stamping a child', () => {
  const file = 'packages/design-system/src/primitives/Widget/spread.ts'
  for (const call of [
    'cloneElement(...args)',
    'cloneElement(c, ...rest)',
    'cloneElement(c, {}, ...kids)',
  ]) {
    assert.throws(
      () => stampSource(`export const a = (c, args, rest, kids) =>\n  ${call}`, file),
      (error) => error.message.includes(`${file}:2`) && /spread/.test(error.message),
      call,
    )
  }
  // The three shapes handled today still pass: an object literal, a props variable, no props.
  assert.ok(stampSource('export const a = (c) => cloneElement(c, { id: 1 })', file))
  assert.ok(stampSource('export const a = (c, p) => cloneElement(c, p)', file))
  assert.ok(stampSource('export const a = (c) => cloneElement(c)', file))
})

// ---- stamp-absent: a scan that found nothing to scan is a failure ---------------------------------

const stampAbsent = path.join(rootDir, 'scripts/checks/stamp-absent.mjs')
const runStampAbsent = (dir, script = stampAbsent) =>
  spawnSync(process.execPath, [script, dir], { encoding: 'utf8' })

test('stamp-absent: an empty directory, a missing one and one holding only empty directories fail; a clean one passes; a stamped one fails', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'stamp-absent-cli-'))
  try {
    const empty = path.join(dir, 'empty')
    mkdirSync(empty)
    const emptyResult = runStampAbsent(empty)
    assert.equal(emptyResult.status, 1, emptyResult.stdout)
    assert.match(emptyResult.stdout, /no file|nothing to scan|empty/i)

    const nested = path.join(dir, 'nested')
    mkdirSync(path.join(nested, 'assets'), { recursive: true })
    assert.equal(runStampAbsent(nested).status, 1, 'only empty directories: zero files scanned')

    const missingResult = runStampAbsent(path.join(dir, 'missing'))
    assert.equal(missingResult.status, 1)
    assert.match(missingResult.stdout, /does not exist/)

    const clean = path.join(dir, 'clean')
    mkdirSync(clean)
    writeFileSync(path.join(clean, 'index.html'), '<div id="root"></div>')
    const cleanResult = runStampAbsent(clean)
    assert.equal(cleanResult.status, 0, cleanResult.stdout)
    assert.match(cleanResult.stdout, /1 file/)

    const stamped = path.join(dir, 'stamped')
    mkdirSync(stamped)
    writeFileSync(path.join(stamped, 'app.js'), `x("${STAMP_ATTRIBUTE}")`)
    assert.equal(runStampAbsent(stamped).status, 1)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('stamp-absent: the script runs as the main module from a path that needs URL-encoding', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'stamp absent é-'))
  try {
    // The script and what it imports, copied beside a `node_modules` that resolves `typescript`.
    mkdirSync(path.join(dir, 'scripts', 'checks'), { recursive: true })
    cpSync(stampAbsent, path.join(dir, 'scripts', 'checks', 'stamp-absent.mjs'))
    mkdirSync(path.join(dir, 'packages', 'design-system', '.storybook'), { recursive: true })
    cpSync(
      path.join(rootDir, 'packages/design-system/.storybook/source-stamp.mjs'),
      path.join(dir, 'packages', 'design-system', '.storybook', 'source-stamp.mjs'),
    )
    symlinkSync(
      path.join(rootDir, 'packages/design-system/node_modules'),
      path.join(dir, 'packages', 'design-system', 'node_modules'),
    )
    const built = path.join(dir, 'built')
    mkdirSync(built)
    writeFileSync(path.join(built, 'app.js'), `x("${STAMP_ATTRIBUTE}")`)
    const result = runStampAbsent(built, path.join(dir, 'scripts', 'checks', 'stamp-absent.mjs'))
    assert.equal(result.status, 1, `main did not run: ${result.stdout}${result.stderr}`)
    assert.match(result.stdout, /carry/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
