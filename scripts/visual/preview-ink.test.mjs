// 006 T710: the Storybook preview's decorator wrapped every story in `text-text-primary`, so a
// component whose text carried no token of its own rendered correctly in every story and every
// baseline, and in the browser's default black wherever the application supplied no ink (neither
// `RootLayout` nor `Page` sets a text colour). The decorator now supplies a surface and no ink.
//
// What this checks, exactly: the class strings and the inline `style` of the markup of
// `withThemeAndSurface` in the real `preview.tsx`. Any `text-*` utility written there is ink unless it
// is a font size (the `--text-<size>` names of the generated preset) or a Tailwind `text-` keyword that
// is not a colour (alignment, wrapping, overflow). The rule is inverted on purpose: Tailwind's default
// palette is not reset in the preset, so `text-black`, `text-zinc-900`, `text-current` and
// `text-inherit` generate CSS though no `--color-*` name carries them. It does not check how ink could
// enter a story any other way (a global stylesheet, a `body` rule, another decorator, a story's own
// markup, a class that comes from a variable). Each red case below runs on a scratch copy of the real
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

/** Tailwind `text-` utilities that set no colour: alignment, wrapping and overflow. */
export const NON_COLOUR_KEYWORDS = [
  'left',
  'center',
  'right',
  'justify',
  'start',
  'end',
  'wrap',
  'nowrap',
  'balance',
  'pretty',
  'ellipsis',
  'clip',
]

/** The font sizes the preset declares: every `--text-<size>` name, once. The preset emits each size
 * with a sibling `--text-<size>--line-height`, which is not a size of its own. */
export function fontSizes(presetCss) {
  const names = [...presetCss.matchAll(/(?<![\w-])--text-([a-z0-9-]+)\s*:/g)].map((m) => m[1])
  return [...new Set(names.filter((name) => !name.includes('--')))]
}

/** The source of the `withThemeAndSurface` decorator, from its declaration to its closing brace. */
export function decoratorSource(previewSource) {
  const start = previewSource.indexOf('const withThemeAndSurface')
  assert.notEqual(start, -1, 'the preview declares withThemeAndSurface')
  const end = previewSource.indexOf('\n}\n', start)
  assert.notEqual(end, -1, 'the decorator ends at a column-zero brace')
  return previewSource.slice(start, end + 2)
}

/** The text of every `className` the markup writes: a quoted attribute value, or the whole
 * brace-balanced expression of `className={...}` (a template literal with interpolations included). */
function classNameTexts(body) {
  const texts = []
  for (const attribute of body.matchAll(/className\s*=\s*(["{])/g)) {
    const open = attribute.index + attribute[0].length - 1
    if (attribute[1] === '"') {
      const close = body.indexOf('"', open + 1)
      texts.push(body.slice(open + 1, close === -1 ? undefined : close))
      continue
    }
    let depth = 0
    let end = body.length
    for (let at = open; at < body.length; at += 1) {
      if (body[at] === '{') depth += 1
      else if (body[at] === '}') {
        depth -= 1
        if (depth === 0) {
          end = at
          break
        }
      }
    }
    texts.push(body.slice(open + 1, end))
  }
  return texts
}

/** The utility of a class token: the part after its last top-level `:` (a variant separator outside
 * brackets), without a leading or trailing important marker. */
function utilityOf(token) {
  let depth = 0
  let cut = 0
  for (let at = 0; at < token.length; at += 1) {
    const char = token[at]
    if (char === '[') depth += 1
    else if (char === ']') depth -= 1
    else if (char === ':' && depth === 0) cut = at + 1
  }
  return token.slice(cut).replace(/^!/, '').replace(/!$/, '')
}

/** Every `text-*` class the decorator's markup writes that is not a font size or a non-colour keyword,
 * and an inline `color`. Empty when it supplies none. */
export function inkInDecorator(previewSource, sizes) {
  const body = decoratorSource(previewSource)
  const found = []
  for (const text of classNameTexts(body)) {
    for (const token of text.split(/[\s'"`,]+|\$\{|\}/)) {
      const utility = utilityOf(token)
      if (!utility.startsWith('text-')) continue
      const [name] = utility.slice('text-'.length).split('/')
      if (sizes.includes(name) || NON_COLOUR_KEYWORDS.includes(name)) continue
      found.push(token)
    }
  }
  if (/style\s*=\s*\{\{[^}]*\bcolor\s*:/.test(body)) found.push('style color')
  return found
}

const sizes = fontSizes(read(PRESET))
const preview = read(PREVIEW)

test('the preset declares the font sizes the guard derives its exemptions from', () => {
  assert.ok(sizes.length >= 8, `read ${sizes.length} font sizes`)
  assert.ok(sizes.includes('sm') && sizes.includes('2xl'))
  assert.ok(!sizes.some((name) => name.includes('--')), 'a line-height sibling is not a size')
  assert.ok(!sizes.includes('text-primary'), 'a colour role is not a font size')
})

test('the real preview’s decorator supplies a surface and no ink', () => {
  assert.match(decoratorSource(preview), /bg-background/, 'the decorator still paints the surface')
  assert.deepEqual(inkInDecorator(preview, sizes), [])
})

test('red: text-text-primary on the decorator’s wrapper is reported', () => {
  const scratch = preview.replace(
    'className="bg-background min-h-24 p-6"',
    'className="bg-background text-text-primary min-h-24 p-6"',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, sizes), ['text-text-primary'])
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
    assert.equal(inkInDecorator(scratch, sizes).length, 1, ink)
  }
})

test('red: an inline colour on the decorator’s wrapper is reported', () => {
  const scratch = preview.replace(
    '<div className="bg-background min-h-24 p-6">',
    '<div className="bg-background min-h-24 p-6" style={{ color: "black" }}>',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, sizes), ['style color'])
})

test('contrast: a size, an alignment, a wrapping, a weight and a surface utility are not ink', () => {
  const scratch = preview.replace(
    'className="bg-background min-h-24 p-6"',
    'className="bg-background text-sm text-sm/6 md:text-lg text-center text-balance text-ellipsis font-semibold bg-surface min-h-24 p-6"',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, sizes), [])
})

test('red: a Tailwind default-palette colour, text-current and text-inherit are reported', () => {
  // The preset does not reset Tailwind's default palette, so these generate CSS though no
  // `--color-*` name in the preset carries them.
  for (const ink of ['text-black', 'text-zinc-900', 'text-current', 'text-inherit']) {
    const scratch = preview.replace(
      'className="bg-background min-h-24 p-6"',
      `className="bg-background ${ink} min-h-24 p-6"`,
    )
    assert.notEqual(scratch, preview, `the scratch edit applied for ${ink}`)
    assert.deepEqual(inkInDecorator(scratch, sizes), [ink], ink)
  }
})

test('red: ink after an interpolation in a template-literal className is reported', () => {
  const scratch = preview.replace(
    'className="bg-background min-h-24 p-6"',
    'className={`bg-background ${theme} text-text-primary min-h-24 p-6`}',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, sizes), ['text-text-primary'])
})

test('red: ink behind a variant with an arbitrary selector, or marked important, is reported', () => {
  for (const ink of ['[&:hover]:text-black', '!text-zinc-900', 'text-[color:var(--x)]']) {
    const scratch = preview.replace(
      'className="bg-background min-h-24 p-6"',
      `className="bg-background ${ink} min-h-24 p-6"`,
    )
    assert.notEqual(scratch, preview, `the scratch edit applied for ${ink}`)
    assert.deepEqual(inkInDecorator(scratch, sizes), [ink], ink)
  }
})

test('red: ink inside an interpolated expression of a template-literal className is reported', () => {
  const scratch = preview.replace(
    'className="bg-background min-h-24 p-6"',
    "className={`bg-background ${theme === 'dark' ? 'text-white' : ''} min-h-24 p-6`}",
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, sizes), ['text-white'])
})

test('contrast: an interpolation beside a size is not ink', () => {
  const scratch = preview.replace(
    'className="bg-background min-h-24 p-6"',
    'className={`bg-background ${theme} text-sm min-h-24 p-6`}',
  )
  assert.notEqual(scratch, preview, 'the scratch edit applied')
  assert.deepEqual(inkInDecorator(scratch, sizes), [])
})
