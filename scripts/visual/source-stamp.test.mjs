// T693 piece 1: the source-stamp transform (`packages/design-system/.storybook/source-stamp.mjs`)
// and the guarantee that none of it reaches `apps/web`. No browser, no build: the transform is a pure
// function of source text, and "absent from `apps/web`" is proved at two honest levels — the app's own
// Vite config never names the plugin (source level), and `scripts/checks/stamp-absent.mjs`, which CI
// runs over the output of `pnpm --filter web build`, fails on a planted stamp and passes on a clean
// directory (built-output level; the scan is exercised here on planted directories, the real build is
// the CI step's).
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
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
