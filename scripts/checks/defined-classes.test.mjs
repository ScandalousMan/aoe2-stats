// Regression tests for T743's check (defined-classes.mjs). Fixture-only for the shape rules —
// small component sources written into a fresh `mkdtempSync` directory per test, the script run as
// a child process so the exit code and the `file:line class` output are the thing under test — plus
// one test that runs the check over the real package's component source.
//
// Plant, red before: `text-secondary` (not a utility; the colour role's is `text-text-secondary`)
// in a `className`, and in the historical shape that carried the defect for real — a tone map
// typed `Record<string, string>`. Contrast, pass: the real utility, a variant-prefixed class, and
// the Tooltip-shaped string-literal enum that parses as a class candidate (`block` + `start`) but
// is a member of a closed set, not a class string.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const script = path.join(scriptDir, 'defined-classes.mjs')

function run(files) {
  const dir = mkdtempSync(path.join(tmpdir(), 'defined-classes-'))
  try {
    for (const [name, content] of Object.entries(files)) {
      const full = path.join(dir, name)
      mkdirSync(path.dirname(full), { recursive: true })
      writeFileSync(full, content)
    }
    const r = spawnSync(process.execPath, [script, dir], { encoding: 'utf8' })
    return { status: r.status, out: r.stdout, err: r.stderr, dir }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

test('plant: text-secondary in a className fails, naming file, line and class', () => {
  const r = run({
    'Widget.tsx': [
      'export function Widget() {',
      '  return <p className="text-sm text-secondary">x</p>',
      '}',
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 1)
  assert.ok(
    r.err.includes(`${path.join(r.dir, 'Widget.tsx')}:2 text-secondary`),
    `expected a hit on line 2, got:\n${r.err}`,
  )
  assert.ok(!r.err.includes(' text-sm\n'), 'a defined class is not reported')
})

test('plant: the historical shape, a Record<string, string> tone map value, fails', () => {
  const r = run({
    'tone.ts': [
      'const tone: Record<string, string> = {',
      "  win: 'text-text-primary',",
      "  unknown: 'text-secondary',",
      '}',
      'export { tone }',
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 1)
  assert.ok(r.err.includes('tone.ts:3 text-secondary'), r.err)
})

test('a class in a multi-line template literal is reported on its own line', () => {
  const r = run({
    'multi.ts': ['export const c = `flex', '  text-secondary', '  gap-2`', ''].join('\n'),
  })
  assert.equal(r.status, 1)
  assert.ok(r.err.includes('multi.ts:2 text-secondary'), r.err)
})

test('contrast: the real utility, a variant-prefixed class and arbitrary values pass', () => {
  const r = run({
    'ok.tsx': [
      'export function Ok() {',
      '  return (',
      '    <a',
      '      className={[',
      "        'text-text-secondary',",
      "        'group-hover/row-link:underline',",
      "        'md:grid-cols-[1fr_auto]',",
      "        'type-numeric icon-sm rounded-panel sr-only flex',",
      "      ].join(' ')}",
      '    >',
      '      Unknown the group/row-link to from text',
      '    </a>',
      '  )',
      '}',
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 0, r.err)
  assert.match(r.out, /all defined/)
})

test('contrast: a Tooltip-shaped closed string-literal set is an enum, not a class string', () => {
  const r = run({
    'placement.tsx': [
      "type P = 'block-start' | 'block-end'",
      "export function pick(initial: P = 'block-start', set: (v: P | ((p: P) => P)) => void) {",
      "  if (initial === 'block-start') {",
      "    set('block-end')",
      "  } else if (initial !== 'block-end') {",
      "    set('block-start')",
      '  }',
      '  switch (initial) {',
      "    case 'block-end':",
      '      return 1',
      '  }',
      '  return 0',
      '}',
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 0, r.err)
})

test('a literal whose contextual type is plain string is still checked, even beside an enum', () => {
  const r = run({
    'mixed.ts': [
      "type P = 'block-start' | 'block-end'",
      "export const p: P = 'block-start'",
      "export const cls: string = 'block-start'",
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 1)
  assert.ok(r.err.includes('mixed.ts:3 block-start'), r.err)
  assert.ok(!r.err.includes('mixed.ts:2'), r.err)
})

// B1 (reviewer, T743): a token Tailwind cannot parse at all was read as prose, so a misspelt
// variant or a misspelt custom utility passed. Two narrow rules close the shapes the stylesheet
// itself can name: an unknown variant in front of a real utility, and a typo of one of the
// stylesheet's own `@utility` families.
for (const typo of [
  'focus-visble:outline-2',
  'hovr:underline',
  'dakr:bg-surface',
  'group-hovr/row-link:underline',
  'type-numerc',
  'icon-smm',
]) {
  test(`plant: the misspelt class ${typo} fails`, () => {
    const r = run({ 'Typo.tsx': `export const c = '${typo}'\n` })
    assert.equal(r.status, 1, `expected exit 1, got ${r.status}:\n${r.out}${r.err}`)
    assert.ok(r.err.includes(`Typo.tsx:1 ${typo}`), r.err)
  })
}

test('contrast: URLs, times and the correctly spelt variants and utilities pass', () => {
  const r = run({
    'Prose.tsx': [
      "export const a = 'https://example.com'",
      "export const b = '12:30'",
      "export const c = 'Note: see https://example.com/a:b at 12:30'",
      "export const d = 'type-numeric focus-visible:outline-2 hover:underline icon-sm'",
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 0, r.err)
})

// B2 (reviewer, T743): the closed-set exemption was meant for an enum like Tooltip's placement,
// not for a union that is itself a class vocabulary. A set is an enum only when no member of it
// compiles to CSS.
test('plant: a class-vocabulary union carrying the defect through a Record value fails', () => {
  const r = run({
    'tone.ts': [
      "type Tone = 'text-text-primary' | 'text-secondary'",
      'export const tone: Record<string, Tone> = {',
      "  unknown: 'text-secondary',",
      '}',
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 1, `${r.out}${r.err}`)
  assert.ok(r.err.includes('tone.ts:1 text-secondary'), r.err)
  assert.ok(r.err.includes('tone.ts:3 text-secondary'), r.err)
})

test('plant: a class-vocabulary union under `satisfies` fails', () => {
  const r = run({
    'ring.ts': [
      "export const ring = { unknown: 'ring-secondary', known: 'ring-focus-ring' } satisfies Record<",
      '  string,',
      "  'ring-secondary' | 'ring-focus-ring'",
      '>',
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 1, `${r.out}${r.err}`)
  assert.ok(r.err.includes('ring.ts:1 ring-secondary'), r.err)
})

test('plant: an optional prop typed by a class-vocabulary union fails (the `| undefined` path)', () => {
  const r = run({
    'paint.ts': [
      "type Ink = 'text-text-primary' | 'text-secondary'",
      'declare function paint(props: { ink?: Ink }): void',
      "paint({ ink: 'text-secondary' })",
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 1, `${r.out}${r.err}`)
  assert.ok(r.err.includes('paint.ts:3 text-secondary'), r.err)
})

test('contrast: a Tooltip-shaped enum passes through an optional prop and a Record value', () => {
  const r = run({
    'tip.ts': [
      "type P = 'block-start' | 'block-end'",
      'declare function place(props: { placement?: P }): void',
      "place({ placement: 'block-end' })",
      'export const flip: Record<P, P> = {',
      "  'block-start': 'block-end',",
      "  'block-end': 'block-start',",
      '}',
      '',
    ].join('\n'),
  })
  assert.equal(r.status, 0, r.err)
})

// N2: `import.meta.url === \`file://${process.argv[1]}\`` is false through a symlink or a path with
// a space, and a script that silently does not run exits 0.
test('plant: the check still runs, and fails, when invoked through a symlink', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'defined-classes link-'))
  try {
    mkdirSync(path.join(dir, 'src'))
    writeFileSync(path.join(dir, 'src', 'Bad.tsx'), "export const c = 'text-secondary'\n")
    const link = path.join(dir, 'run link.mjs')
    symlinkSync(script, link)
    const r = spawnSync(process.execPath, [link, path.join(dir, 'src')], { encoding: 'utf8' })
    assert.equal(r.status, 1, `${r.stdout}${r.stderr}`)
    assert.ok(r.stderr.includes('Bad.tsx:1 text-secondary'), r.stderr)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('test and story files are not component source', () => {
  const r = run({
    'Widget.test.tsx': "export const a = 'text-secondary'\n",
    'Widget.stories.tsx': "export const b = 'text-secondary'\n",
    'Widget.tsx': "export const c = 'text-text-secondary'\n",
  })
  assert.equal(r.status, 0, r.err)
})

test("the real package's component source passes", () => {
  const r = spawnSync(process.execPath, [script], { encoding: 'utf8' })
  assert.equal(r.status, 0, r.stderr)
  assert.match(r.stdout, /class candidates checked, all defined/)
})
