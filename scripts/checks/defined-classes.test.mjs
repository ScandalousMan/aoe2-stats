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
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
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
