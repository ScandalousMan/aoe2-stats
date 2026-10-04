// T693 (third remediation of #114): the tracked primitives default their axes in their own
// destructuring (`Button`'s `variant` and `size`, `Field`'s `size`, `Link`'s `variant`), and the
// runtime pass merges what a caller passed over the exported `<X>_AXIS_DEFAULTS` constant. If a
// destructuring default became a literal, or `Menu` gained a default for `variant`, or the preview's
// registry listed another axis, the pass would record an axis the browser does not render. This reads
// the real sources and fails on any of those; each case below is shown red on a scratch copy of the
// real source (never on the tree).
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { TRACKED_PRIMITIVES, findAxisDrift } from './tracked-axes.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const read = (rel) => readFileSync(path.join(rootDir, rel), 'utf8')
const sources = () => ({
  files: Object.fromEntries(
    TRACKED_PRIMITIVES.map((name) => [
      name,
      read(`packages/design-system/src/primitives/${name}/index.tsx`),
    ]),
  ),
  preview: read('packages/design-system/.storybook/preview.tsx'),
})

test('the tracked primitives are the four the preview registers', () => {
  assert.deepEqual([...TRACKED_PRIMITIVES].sort(), ['Button', 'Field', 'Link', 'Menu'])
  const preview = read('packages/design-system/.storybook/preview.tsx')
  const registered = [...preview.matchAll(/^ {2}(\w+): \{\s*component: \w+,/gm)].map((m) => m[1])
  assert.deepEqual(registered.sort(), [...TRACKED_PRIMITIVES].sort())
})

test('the real sources agree: every destructured axis default is <X>_AXIS_DEFAULTS.<axis>, Menu has none, the registry lists the same axes', () => {
  assert.deepEqual(findAxisDrift(sources()), [])
})

test('red: Button’s default reverted to a literal in a scratch copy is reported', () => {
  const s = sources()
  const scratch = s.files.Button.replace(
    'variant = BUTTON_AXIS_DEFAULTS.variant',
    "variant = 'secondary'",
  )
  assert.notEqual(scratch, s.files.Button, 'the scratch edit applied')
  const problems = findAxisDrift({ ...s, files: { ...s.files, Button: scratch } })
  assert.equal(problems.length, 1)
  assert.match(problems[0], /Button.*variant.*BUTTON_AXIS_DEFAULTS\.variant/)
})

test('red: a size default that reads another primitive’s constant, or none at all, is reported', () => {
  const s = sources()
  const wrongConstant = s.files.Button.replace(
    'BUTTON_AXIS_DEFAULTS.size',
    'FIELD_AXIS_DEFAULTS.size',
  )
  assert.match(
    findAxisDrift({ ...s, files: { ...s.files, Button: wrongConstant } }).join('\n'),
    /Button.*size/,
  )
  const noDefault = s.files.Button.replace('size = BUTTON_AXIS_DEFAULTS.size,', 'size,')
  assert.match(
    findAxisDrift({ ...s, files: { ...s.files, Button: noDefault } }).join('\n'),
    /Button.*size/,
  )
})

test('red: Menu gaining a default for variant is reported', () => {
  const s = sources()
  const scratch = s.files.Menu.replace(/^ {2}variant,$/m, "  variant = 'actions',")
  assert.notEqual(scratch, s.files.Menu, 'the scratch edit applied')
  assert.match(
    findAxisDrift({ ...s, files: { ...s.files, Menu: scratch } }).join('\n'),
    /Menu.*variant/,
  )
})

test('red: a registry axis the primitive does not destructure, and a destructured axis the registry lacks, are reported', () => {
  const s = sources()
  const extra = s.preview.replace('axes: { variant: null }', 'axes: { variant: null, size: null }')
  assert.notEqual(extra, s.preview)
  assert.match(findAxisDrift({ ...s, preview: extra }).join('\n'), /Menu.*size/)
  const missing = s.preview.replace('axes: { variant: null }', 'axes: {}')
  assert.match(findAxisDrift({ ...s, preview: missing }).join('\n'), /Menu.*variant/)
  const swapped = s.preview.replace('axes: BUTTON_AXIS_DEFAULTS', 'axes: LINK_AXIS_DEFAULTS')
  assert.match(findAxisDrift({ ...s, preview: swapped }).join('\n'), /Button/)
})

test('red: a primitive the registry does not list, and one it lists that is not tracked here, are reported', () => {
  const s = sources()
  const dropped = s.preview.replace(/ {2}Link: \{[\s\S]*?\n {2}\},\n/, '')
  assert.notEqual(dropped, s.preview)
  assert.match(findAxisDrift({ ...s, preview: dropped }).join('\n'), /Link/)
})
