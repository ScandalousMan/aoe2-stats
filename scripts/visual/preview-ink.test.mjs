// T710: the Storybook preview's decorator wrapped every story in `text-text-primary`, so a component
// whose text carried no token of its own rendered correctly in every story and every baseline, and in
// the browser's default black wherever the application supplied no ink (neither `RootLayout` nor
// `Page` sets a text colour). The decorator now supplies a surface and no ink. This reads the real
// preview and fails if its decorator markup carries a text colour again; the colour utilities are
// derived from the `--color-*` names in the generated preset, never a hand-kept list, so `text-sm`
// passes and any `text-<colour role>` fails. Each red case below runs on a scratch copy of the real
// source, never on the tree.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const read = (rel) => readFileSync(path.join(rootDir, rel), 'utf8')

const PREVIEW = 'packages/design-system/.storybook/preview.tsx'
const PRESET = 'packages/design-system/tokens/generated/preset.css'

/** The colour roles the preset declares: every `--color-<role>` name, once. */
export function colourRoles(presetCss) {
  return [...new Set([...presetCss.matchAll(/--color-([a-z0-9-]+)\s*:/g)].map((m) => m[1]))]
}

/** The source of the `withThemeAndSurface` decorator, from its declaration to its closing brace. */
export function decoratorSource(previewSource) {
  const start = previewSource.indexOf('const withThemeAndSurface')
  assert.notEqual(start, -1, 'the preview declares withThemeAndSurface')
  const end = previewSource.indexOf('\n}\n', start)
  assert.notEqual(end, -1, 'the decorator ends at a column-zero brace')
  return previewSource.slice(start, end + 2)
}

/** Every text-colour utility the decorator's markup writes: `text-<role>` (with any variant prefix
 * and opacity suffix), an arbitrary `text-[...]`, or an inline `color`. Empty when it supplies none. */
export function inkInDecorator(previewSource, roles) {
  const body = decoratorSource(previewSource)
  const found = []
  for (const attribute of body.matchAll(/className\s*=\s*(?:"([^"]*)"|\{([^}]*)\})/g)) {
    const text = attribute[1] ?? attribute[2]
    for (const token of text.split(/[\s'"`,()]+/)) {
      const utility = token.split(':').pop() ?? ''
      const [name] = utility.split('/')
      if (name.startsWith('text-[')) found.push(token)
      else if (name.startsWith('text-') && roles.includes(name.slice('text-'.length))) {
        found.push(token)
      }
    }
  }
  if (/style\s*=\s*\{\{[^}]*\bcolor\s*:/.test(body)) found.push('style color')
  return found
}

const roles = colourRoles(read(PRESET))
const preview = read(PREVIEW)

test('the preset declares the colour roles the guard derives its utilities from', () => {
  assert.ok(roles.length > 20, `read ${roles.length} colour roles`)
  assert.ok(roles.includes('text-primary') && roles.includes('text-secondary'))
  assert.ok(!roles.includes('sm'), 'a type-scale step is not a colour role')
})

test('the real preview’s decorator supplies a surface and no ink', () => {
  assert.match(decoratorSource(preview), /bg-background/, 'the decorator still paints the surface')
  assert.deepEqual(inkInDecorator(preview, roles), [])
})

test('red: text-text-primary on the decorator’s wrapper is reported', () => {
  const scratch = preview.replace(
    'className="bg-background min-h-24 p-6"',
    'className="bg-background text-text-primary min-h-24 p-6"',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, roles), ['text-text-primary'])
})

test('red: any other colour role, a variant-prefixed one, an opacity one and an arbitrary one are reported', () => {
  for (const ink of [
    'text-accent',
    'dark:text-text-secondary',
    'text-danger/80',
    'text-[var(--x)]',
  ]) {
    const scratch = preview.replace(
      'className="bg-background min-h-24 p-6"',
      `className="bg-background ${ink} min-h-24 p-6"`,
    )
    assert.notEqual(scratch, preview, `the scratch edit applied for ${ink}`)
    assert.equal(inkInDecorator(scratch, roles).length, 1, ink)
  }
})

test('red: an inline colour on the decorator’s wrapper is reported', () => {
  const scratch = preview.replace(
    '<div className="bg-background min-h-24 p-6">',
    '<div className="bg-background min-h-24 p-6" style={{ color: "black" }}>',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, roles), ['style color'])
})

test('contrast: a size, a weight and a surface utility are not ink', () => {
  const scratch = preview.replace(
    'className="bg-background min-h-24 p-6"',
    'className="bg-background text-sm text-center font-semibold bg-surface min-h-24 p-6"',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, roles), [])
})
