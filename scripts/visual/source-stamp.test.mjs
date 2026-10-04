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
  readdirSync,
  rmSync,
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
  const code = "import { Button, Foo } from './x'\nconst a = <><Button /><Foo.Bar /></>"
  assert.equal(stampSource(code, FILE), null)
})

test('stamps the props an element is cloned with, keyed to the call, in each argument shape', () => {
  const code = [
    "import React, { cloneElement } from 'react'",
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
    "import { cloneElement } from 'react'\nexport const f = (c, p) => cloneElement(c, p)",
    'packages/design-system/src/x.ts',
  )
  const calls = []
  const body = out.split('\n').slice(1).join('\n') // the import line is not evaluable here
  const fn = new Function('cloneElement', `${body.replace('export const f =', 'return')}`)((c, p) =>
    calls.push(p),
  )
  fn('el', { id: 'x' })
  assert.deepEqual(calls[0], { [STAMP_ATTRIBUTE]: 'packages/design-system/src/x.ts:2', id: 'x' })
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
      () =>
        stampSource(
          `import { cloneElement } from 'react'\nexport const a = (c, args, rest, kids) =>\n  ${call}`,
          file,
        ),
      (error) => error.message.includes(`${file}:3`) && /spread/.test(error.message),
      call,
    )
  }
  // The three shapes handled today still pass: an object literal, a props variable, no props.
  const imp = "import { cloneElement } from 'react'\n"
  assert.ok(stampSource(`${imp}export const a = (c) => cloneElement(c, { id: 1 })`, file))
  assert.ok(stampSource(`${imp}export const a = (c, p) => cloneElement(c, p)`, file))
  assert.ok(stampSource(`${imp}export const a = (c) => cloneElement(c)`, file))
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
    // The script and the one module it imports, copied to a path that needs URL-encoding.
    mkdirSync(path.join(dir, 'scripts', 'checks'), { recursive: true })
    cpSync(stampAbsent, path.join(dir, 'scripts', 'checks', 'stamp-absent.mjs'))
    mkdirSync(path.join(dir, 'packages', 'design-system', '.storybook'), { recursive: true })
    cpSync(
      path.join(rootDir, 'packages/design-system/.storybook/source-stamp-attribute.cjs'),
      path.join(dir, 'packages', 'design-system', '.storybook', 'source-stamp-attribute.cjs'),
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

// ---- the stamp's attribute name: one definition both a Playwright spec and Vite can load ----------

// Playwright transpiles a spec to CommonJS, and a transpiled `.mjs` that uses `import.meta` (or
// `createRequire(import.meta.url)`, as `source-stamp.mjs` does) cannot be loaded from there: it died
// on CI's Node 20.20 with `exports is not defined in ES module scope` and fails the same way on
// Node 20.13 and 24 locally, while passing on 20.19.0 — which is why it was not caught before. The
// precedent is `scripts/visual/a11y-scan.cjs`: a `.cjs` is CommonJS by extension alone. So the
// attribute name lives in a `.cjs` file, and no TypeScript file under `tests/visual/` may import an
// `.mjs` that reaches `import.meta`.
function relativeImports(text) {
  return [...text.matchAll(/(?:from|import)\s*\(?\s*['"](\.[^'"]+)['"]/g)].map((m) => m[1])
}

test('no tests/visual TypeScript file imports an .mjs that uses import.meta, directly or through another .mjs', () => {
  const visualDir = path.join(rootDir, 'tests', 'visual')
  const offenders = []
  const seen = new Set()
  const scan = (file, via) => {
    if (seen.has(file)) return
    seen.add(file)
    const text = readFileSync(file, 'utf8')
    if (file.endsWith('.mjs') && /import\.meta/.test(text)) {
      offenders.push(`${path.relative(rootDir, file)} (reached from ${via})`)
    }
    for (const spec of relativeImports(text)) {
      if (!spec.endsWith('.mjs')) continue
      scan(path.resolve(path.dirname(file), spec), via)
    }
  }
  for (const name of readdirSync(visualDir)) {
    if (!name.endsWith('.ts')) continue
    const file = path.join(visualDir, name)
    for (const spec of relativeImports(readFileSync(file, 'utf8'))) {
      if (spec.endsWith('.mjs')) scan(path.resolve(visualDir, spec), name)
    }
  }
  assert.deepEqual(offenders, [])
})

test('the stamp attribute has one definition, a .cjs, and source-stamp.mjs re-exports it', async () => {
  const { createRequire } = await import('node:module')
  const cjs = createRequire(import.meta.url)(
    '../../packages/design-system/.storybook/source-stamp-attribute.cjs',
  )
  assert.equal(typeof cjs.STAMP_ATTRIBUTE, 'string')
  assert.equal(STAMP_ATTRIBUTE, cjs.STAMP_ATTRIBUTE)
  const stamp = readFileSync(
    path.join(rootDir, 'packages/design-system/.storybook/source-stamp.mjs'),
    'utf8',
  )
  assert.doesNotMatch(stamp, /=\s*['"]data-ds-src['"]/, 'the literal is defined once, in the .cjs')
})

// ---- a capitalised tag that is not a component: `const Heading = `h${level}`` ----------------------

const DYN = 'packages/design-system/src/primitives/Widget/dynamic.tsx'

test('a template-literal tag variable is stamped at the line its `<` is on', () => {
  const code = [
    'export function Widget({ level }) {',
    '  const Heading = `h${level}`',
    '  return (',
    '    <div>',
    '      <Heading',
    '        id="x"',
    '      >',
    '        go',
    '      </Heading>',
    '    </div>',
    '  )',
    '}',
  ].join('\n')
  const out = stampSource(code, DYN)
  assert.ok(out)
  assert.match(out, new RegExp(`<Heading ${STAMP_ATTRIBUTE}="${DYN}:5"\\n`))
  // The closing tag is not an element of its own.
  assert.equal(out.match(new RegExp(STAMP_ATTRIBUTE, 'g')).length, 2)
  assert.equal(out.split('\n').length, code.split('\n').length)
})

test('a string-literal tag, an `as const as` wrapper, a satisfies, a parenthesised and a conditional of strings are all stamped', () => {
  const shapes = {
    string: "const Tag = 'section'",
    wrapper: "const Tag = `h${level}` as const as 'h2' | 'h3' | 'h4'",
    union: "const Tag = level as 'h2' | 'h3'",
    satisfies: "const Tag = 'h2' satisfies string",
    parenthesised: "const Tag = ('h2')",
    conditional: "const Tag = level ? 'section' : 'div'",
    nested: "const Tag = level === 0 ? 'h2' : level === 1 ? 'h3' : `h${level}`",
    conditionalOfCasts: "const Tag = level ? (x as 'a' | 'b') : 'div'",
  }
  for (const [name, declaration] of Object.entries(shapes)) {
    const out = stampSource(
      `export function W({ level, x }) {\n  ${declaration}\n  return <Tag id="a" />\n}`,
      DYN,
    )
    assert.ok(out, name)
    assert.ok(out.includes(`<Tag ${STAMP_ATTRIBUTE}="${DYN}:3" id="a" />`), `${name}: ${out}`)
  }
})

test('a tag that is a component is never stamped: imported, function, class, arrow, forwardRef, memo, a member expression', () => {
  const shapes = [
    "import { Foo } from './Foo'\nexport const A = () => <Foo />",
    "import Foo from './Foo'\nexport const A = () => <Foo />",
    "import * as Foo from './Foo'\nexport const A = () => <Foo />",
    'function Foo() { return null }\nexport const A = () => <Foo />',
    'class Foo {}\nexport const A = () => <Foo />',
    'const Foo = () => null\nexport const A = () => <Foo />',
    'const Foo = function () { return null }\nexport const A = () => <Foo />',
    "import { forwardRef } from 'react'\nconst Foo = forwardRef((p, r) => null)\nexport const A = () => <Foo />",
    "import * as React from 'react'\nconst Foo = React.memo(() => null)\nexport const A = () => <Foo />",
    "import { memo } from 'react'\nconst Foo = memo(function Foo() { return null }) as never\nexport const A = () => <Foo />",
    "import * as Foo from './Foo'\nexport const A = () => <Foo.Bar />",
    'export const A = () => <><this.Foo /></>',
  ]
  for (const code of shapes) assert.equal(stampSource(code, DYN), null, code)
})

test('the nearest declaration decides: an inner string variable shadows an outer import, and an inner component an outer string', () => {
  const shadow = [
    "import { Heading } from './Heading'",
    'export function A() {',
    "  const Heading = 'h2'",
    '  return <Heading />',
    '}',
    'export const B = () => <Heading />',
  ].join('\n')
  const out = stampSource(shadow, DYN)
  assert.ok(out)
  assert.ok(out.includes(`<Heading ${STAMP_ATTRIBUTE}="${DYN}:4" />`), out)
  assert.ok(out.includes('<Heading />'), 'the outer, imported one is untouched')
  const inner = [
    "const Tag = 'h2'",
    'export function A() {',
    '  const Tag = () => null',
    '  return <Tag />',
    '}',
  ].join('\n')
  assert.equal(stampSource(inner, DYN), null)
})

test('a capitalised local tag the transform cannot classify throws, naming file:line, instead of being skipped', () => {
  const cases = {
    'a destructured `as: Tag` prop': 'export function A({ as: Tag }) {\n  return <Tag />\n}',
    'a parameter used as a tag': 'export function A(Tag) {\n  return <Tag />\n}',
    'a destructured binding':
      'export function A(props) {\n  const { Tag } = props\n  return <Tag />\n}',
    'a member read': 'export function A(props) {\n  const Tag = props.as\n  return <Tag />\n}',
    'a cast to ElementType':
      "export function A({ as }) {\n  const Tag = (as ?? 'p') as ElementType\n  return <Tag />\n}",
    'a conditional with a component branch':
      "export function A(p) {\n  const Tag = p ? 'a' : Other\n  return <Tag />\n}",
    'a name declared nowhere': 'export function A() {\n  return <Mystery />\n}',
  }
  for (const [name, code] of Object.entries(cases)) {
    const line = code.split('\n').findIndex((l) => /<(Tag|Mystery)/.test(l)) + 1
    assert.throws(
      () => stampSource(code, DYN),
      (error) =>
        error.message.includes(`${DYN}:${line}`) && /cannot (tell|classify)/.test(error.message),
      name,
    )
  }
})

test('every capitalised JSX tag under packages/design-system/src classifies: the real tree transforms without throwing', async () => {
  const { readdirSync: ls, readFileSync: read } = await import('node:fs')
  const walk = (dir) =>
    ls(dir, { withFileTypes: true }).flatMap((e) =>
      e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)],
    )
  const files = walk(path.join(rootDir, 'packages/design-system/src'))
    .map((f) => path.relative(rootDir, f).split(path.sep).join('/'))
    .filter(isStampedFile)
  assert.ok(files.length > 20, `only ${files.length} files found`)
  for (const file of files) stampSource(read(path.join(rootDir, file), 'utf8'), file)
})

test('the real dynamic-tag elements are stamped: Callout, EmptyState, ErrorState, Panel, Section and Text', () => {
  const read = (rel) => readFileSync(path.join(rootDir, rel), 'utf8')
  for (const [rel, tag] of [
    ['primitives/Callout/index.tsx', 'Heading'],
    ['primitives/EmptyState/index.tsx', 'Heading'],
    ['primitives/ErrorState/index.tsx', 'Heading'],
    ['primitives/Panel/index.tsx', 'Tag'],
    ['primitives/Section/index.tsx', 'HeadingTag'],
    ['primitives/Text/index.tsx', 'Tag'],
  ]) {
    const file = `packages/design-system/src/${rel}`
    const out = stampSource(read(file), file)
    assert.match(out, new RegExp(`<${tag}\\s+${STAMP_ATTRIBUTE}="${file}:\\d+"`), file)
  }
})

// ---- cloneElement is React's, resolved by import, never matched by bare name ----------------------

const CLONE = 'packages/design-system/src/primitives/Widget/clone2.ts'

test('cloneElement: a call that does not resolve to React is not stamped', () => {
  const unstamped = {
    'an alias imported from a non-React module':
      "import { cloneElement as ce } from './mine'\nexport const a = (c) => ce(c, { id: 1 })",
    'the plain name imported from a non-React module':
      "import { cloneElement } from 'preact'\nexport const a = (c) => cloneElement(c, { id: 1 })",
    'the plain name with no import at all': 'export const a = (c) => cloneElement(c, { id: 1 })',
    'a method on a non-React object':
      "import React from 'react'\nexport const a = (x, c) => x.cloneElement(c, { id: 1 })",
    'a method on an object with no import':
      'export const a = (x, c) => x.cloneElement(c, { id: 1 })',
    'a default import of another module':
      "import React from 'preact'\nexport const a = (c) => React.cloneElement(c, { id: 1 })",
    'another named React export':
      "import { cloneElement as ce, useId } from 'react'\nexport const a = (c) => useId(c)",
  }
  for (const [name, code] of Object.entries(unstamped)) {
    assert.equal(stampSource(code, CLONE), null, name)
  }
})

test('cloneElement: a named import (aliased or not), a default import and a namespace import of react are stamped', () => {
  const stamped = {
    named:
      "import { cloneElement } from 'react'\nexport const a = (c) => cloneElement(c, { id: 1 })",
    aliased: "import { cloneElement as ce } from 'react'\nexport const a = (c) => ce(c, { id: 1 })",
    default: "import React from 'react'\nexport const a = (c) => React.cloneElement(c, { id: 1 })",
    namespace: "import * as R from 'react'\nexport const a = (c) => R.cloneElement(c, { id: 1 })",
    'default and named together':
      "import React, { cloneElement } from 'react'\nexport const a = (c) => React.cloneElement(c, { id: 1 })",
  }
  for (const [name, code] of Object.entries(stamped)) {
    const out = stampSource(code, CLONE)
    assert.ok(out?.includes(`'${STAMP_ATTRIBUTE}': '${CLONE}:2', id: 1`), `${name}: ${out}`)
  }
})

test('cloneElement: redeclaring the imported name anywhere in the file throws, naming file:line', () => {
  // [source, the line the redeclaration is on]
  const redeclared = {
    'a parameter': [
      "import { cloneElement } from 'react'\nexport function f(c, cloneElement) {\n  return cloneElement(c)\n}",
      2,
    ],
    'a nested const': [
      "import { cloneElement } from 'react'\nexport function f(c) {\n  const cloneElement = (x) => x\n  return cloneElement(c)\n}",
      3,
    ],
    'a function declaration': [
      "import { cloneElement as ce } from 'react'\nfunction ce(c) { return c }\nexport const a = (c) => ce(c)",
      2,
    ],
    'a shadowed namespace': [
      "import * as R from 'react'\nexport function f(c) {\n  const R = { cloneElement: (x) => x }\n  return R.cloneElement(c)\n}",
      3,
    ],
    'a destructured binding': [
      "import React from 'react'\nexport function f(props) {\n  const { React } = props\n  return React.cloneElement(1)\n}",
      3,
    ],
  }
  for (const [name, [code, line]] of Object.entries(redeclared)) {
    assert.throws(
      () => stampSource(code, CLONE),
      (error) => error.message.includes(`${CLONE}:${line}`) && /redeclar/.test(error.message),
      name,
    )
  }
})

test('cloneElement: Field’s real call is still stamped, at the line it has always been', () => {
  const file = 'packages/design-system/src/primitives/Field/index.tsx'
  const text = readFileSync(path.join(rootDir, file), 'utf8')
  const callLine = text.split('\n').findIndex((l) => /cloneElement\(children/.test(l)) + 1
  assert.equal(callLine, 122)
  assert.ok(stampSource(text, file).includes(`'${STAMP_ATTRIBUTE}': '${file}:122'`))
})
