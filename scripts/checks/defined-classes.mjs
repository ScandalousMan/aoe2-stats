#!/usr/bin/env node
// T743: fails when the design system's component source names a class its own stylesheet does not
// define. `text-secondary` was the ink of an unknown or neutral fact in four places (three in
// MatchRow, one in MatchDetailPanel). Tailwind emits nothing for it — the colour role's utility is
// `text-text-secondary` — so the text silently took whatever ink surrounded it, and the unit tests
// could not see it: each asserted `toContain('text-secondary')`, which `text-text-secondary` also
// satisfies. token-scale.mjs refuses raw values and never asks whether a class exists; this check
// asks exactly that and nothing else.
//
// Source set: every `.ts`/`.tsx` under `packages/design-system/src/` except `*.test.ts(x)` and
// `*.stories.tsx` — the component source. A test or story file is evidence about the source, not
// the source (the same boundary token-scale.mjs draws), and a test legitimately names classes the
// stylesheet lacks when it asserts a component does not carry them.
//
// Extraction. The file is parsed with the TypeScript compiler API and every StringLiteral,
// NoSubstitutionTemplateLiteral and template head/middle/tail is split on whitespace. Scanning
// every string, rather than tracing what reaches `className` or `cx()`, is token-scale.mjs's own
// reasoning: class fragments live in JSX attributes, `cx()` arguments and module-scope constants
// (`Record<…, string>` tone maps among them), and a regex cannot trace the last shape.
//
// "Is it a class, and is it defined" is not answered by this script: it is answered by Tailwind's
// own design system, loaded from `packages/design-system/tokens/tailwind.css` — the stylesheet the
// build compiles, so the answer is the build's answer, with no second vocabulary to drift.
//   - `parseCandidate(token)` returns `[]` for what Tailwind cannot read at all ('Unknown',
//     'group/row-link', but also a typo: 'focus-visble:outline-2'). Two rules, nothing wider,
//     tell the typos from the prose; every other `[]` is prose and skipped.
//       A. Unknown variant. The token contains `:`, parses as nothing, and the part after its LAST
//          `:` either parses as a non-bare candidate or compiles to CSS (a bare root with a
//          default, `rounded`, `border`, `shadow`, compiles though it is bare): `focus-visble:outline-2`,
//          `hovr:underline`, `group-hovr/row-link:underline`, `focus-visble:rounded`. Prose such as
//          `Note: to` stays prose, because `to` neither is a non-bare candidate nor compiles. `https://example.com` and `12:30` stay prose, because
//          what follows their last colon is not a candidate.
//       B. Misspelt custom utility. The part after the last `:` (or the whole token) starts with
//          the first `-`-segment of an `@utility` the stylesheet declares (`type-`, `icon-`,
//          read from the loaded files, see loadTailwindDesignSystem) and parses as nothing:
//          `type-numerc`, `icon-smm`.
//     Remaining gap, stated rather than closed: an unknown ROOT with no colon and no custom
//     prefix (`txt-secondary`) is indistinguishable from prose and is not reported.
//   - `candidatesToCss([token])[0]` is `null` when Tailwind would emit nothing — a hit.
//   `__unstable__loadDesignSystem` is an unstable export. If a Tailwind upgrade removes it the
//   check exits 1 loudly; a check that passes because its oracle vanished is the failure this file
//   exists to prevent.
//
// Two kinds of string that parse as a candidate and compile to nothing are not defects, and are
// excluded by shape, never by an exception list (a list of names is a claim this repository
// refuses to keep true). Measured on component source with every other rule active: the first
// skip alone removes 108 hits (15 distinct words), the second alone removes 8 (`block-start` and
// `block-end`), 18 more are removed by either, and with both off the scan reports 134.
//   1. A prose word that parses as a bare functional root — `kind === 'functional'` with neither a
//      value nor a modifier: `to`, `from`, `text`, `h`, `p`, `order`, `contain`, `accent`,
//      `start`, `end`. A bare root with a default (`rounded`, `shadow`, `border`, `ring`)
//      compiles and is checked as defined before this skip applies; one whose default the theme
//      removed would be skipped with the prose, a gap this check does not close.
//   2. A string that is a member of a closed set of string literals, not a free class string:
//      `Tooltip`'s `'block-start' | 'block-end'` placement enum parses as `block` + named value
//      `start`/`end`. It is recognised by position — a literal type (`type P = 'block-start'`) —
//      or by the contextual type the compiler gives it: a string-literal type, or a union whose
//      string part is only literals (the `undefined` an optional prop adds is ignored, and so is
//      the updater function of React's `SetStateAction<P>`, which cannot accept a string). The set
//      is an enum only when NO literal in it compiles to CSS: `'text-text-primary' |
//      'text-secondary'` is a class vocabulary, every member of which is checked. (A union whose
//      members are all undefined classes is indistinguishable from an enum and stays exempt.) An
//      operand of `===`/`!==`/`==`/`!=` and a `case` label are exempt without that test: a
//      compared string styles nothing. A literal whose contextual type is `string`, `any`, or
//      absent IS checked, and that is what keeps the defect visible: `MatchRow`'s
//      `Record<…, string>` map value `unknown: 'text-secondary'` has contextual type `string`.
//
// Usage:  node scripts/checks/defined-classes.mjs [source-root]
//         (with no argument it scans packages/design-system/src with that package's tsconfig.json;
//         the argument exists so the tests can point it at fixtures)
// Exit:   0 if every checked class is defined, 1 otherwise. Needs no build.
import { existsSync, readdirSync, readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const dsDir = path.join(rootDir, 'packages', 'design-system')
const defaultSrcDir = path.join(dsDir, 'src')
const cssPath = path.join(dsDir, 'tokens', 'tailwind.css')

// `typescript` and `tailwindcss` are the design-system package's own dependencies, not the
// workspace root's; resolving them from its package.json uses the versions that package builds with.
const dsRequire = createRequire(path.join(dsDir, 'package.json'))

export function isComponentSource(file) {
  if (/\.d\.ts$/.test(file)) return false
  if (!/\.tsx?$/.test(file)) return false
  return !/\.test\.tsx?$/.test(file) && !/\.stories\.tsx$/.test(file)
}

export function listComponentSource(dir) {
  const out = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...listComponentSource(full))
    else if (isComponentSource(full)) out.push(full)
  }
  return out.sort()
}

// Loads Tailwind's design system over the stylesheet the build compiles, and reads from the very
// files it loaded (`tokens/tailwind.css` and everything it imports, `tokens/generated/preset.css`
// among them) the prefixes of the stylesheet's own `@utility` families — `type-`, `icon-` — so the
// misspelt-utility rule below names no family itself. A family counts as the stylesheet's own only
// when Tailwind's stock design system cannot parse its name (`type-numeric`, `icon-sm`): that
// leaves out `border-hairline`, `outline-ring` and `max-h-sheet`, which extend a built-in root and
// are already judged by Tailwind's own `border-*`/`outline-*`/`max-h-*` parsing.
export async function loadTailwindDesignSystem() {
  const tailwind = (await import(dsRequire.resolve('tailwindcss'))).default
  if (typeof tailwind?.__unstable__loadDesignSystem !== 'function') {
    throw new Error(
      'tailwindcss no longer exports __unstable__loadDesignSystem, the oracle this check asks ' +
        'whether a class exists. Refusing to pass without it: port the check to the new API.',
    )
  }
  const loaded = []
  const load = (css, base, record) =>
    tailwind.__unstable__loadDesignSystem(css, {
      base,
      loadStylesheet: async (id, from) => {
        const p =
          id === 'tailwindcss' ? dsRequire.resolve('tailwindcss/index.css') : path.resolve(from, id)
        const content = readFileSync(p, 'utf8')
        if (record) loaded.push(content)
        return { path: p, base: path.dirname(p), content }
      },
    })
  const rootCss = readFileSync(cssPath, 'utf8')
  loaded.push(rootCss)
  const design = await load(rootCss, path.dirname(cssPath), true)
  const stock = await load('@import "tailwindcss";', dsDir, false)

  const customPrefixes = new Set()
  for (const css of loaded) {
    const code = css.replace(/\/\*[\s\S]*?\*\//g, '')
    for (const m of code.matchAll(/^\s*@utility\s+([^\s{]+)/gm)) {
      const name = m[1]
      if (name.includes('-') && stock.parseCandidate(name).length === 0) {
        customPrefixes.add(`${name.slice(0, name.indexOf('-'))}-`)
      }
    }
  }
  return { design, customPrefixes: [...customPrefixes].sort() }
}

function compilerOptionsFor(ts, srcDir) {
  if (srcDir === defaultSrcDir) {
    const tsconfig = path.join(dsDir, 'tsconfig.json')
    const read = ts.readConfigFile(tsconfig, ts.sys.readFile)
    return ts.parseJsonConfigFileContent(read.config, ts.sys, dsDir, undefined, tsconfig).options
  }
  return {
    target: ts.ScriptTarget.ES2023,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    jsx: ts.JsxEmit.ReactJSX,
    strict: true,
    noEmit: true,
    skipLibCheck: true,
    types: [],
  }
}

// The string-literal members a contextual type could take, when its string-typed part is only
// string-literal types, else null. `undefined`/`null` are ignored (an optional prop adds one), and
// so are object/function members: they cannot accept a string, and React's `SetStateAction<P>` is
// `P | ((prev: P) => P)`, so `setPlacement('block-end')` has contextual type
// `'block-start' | 'block-end' | ((prev) => …)`. `string`, `any`, `unknown`, a type parameter or a
// template-literal type among the members makes it a free class string (null).
function closedStringLiteralSet(ts, type) {
  if (!type) return null
  const members = type.isUnion() ? type.types : [type]
  const real = members.filter((t) => !(t.flags & (ts.TypeFlags.Undefined | ts.TypeFlags.Null)))
  const literals = real.filter((t) => t.isStringLiteral())
  const others = real.filter((t) => !t.isStringLiteral())
  if (literals.length === 0 || !others.every((t) => t.flags & ts.TypeFlags.Object)) return null
  return literals.map((t) => t.value)
}

// The string-literal members of the union type node a literal type sits in (parentheses and
// nested unions looked through): `type P = 'block-start' | 'block-end'` gives both, a lone
// `type Q = 'x'` gives one.
function literalTypeSiblings(ts, literalType) {
  let top = literalType
  while (ts.isUnionTypeNode(top.parent) || ts.isParenthesizedTypeNode(top.parent)) top = top.parent
  const out = []
  const collect = (t) => {
    if (ts.isUnionTypeNode(t)) t.types.forEach(collect)
    else if (ts.isParenthesizedTypeNode(t)) collect(t.type)
    else if (ts.isLiteralTypeNode(t) && ts.isStringLiteralLike(t.literal)) out.push(t.literal.text)
  }
  collect(top)
  return out
}

const EQUALITY = (ts) =>
  new Set([
    ts.SyntaxKind.EqualsEqualsEqualsToken,
    ts.SyntaxKind.ExclamationEqualsEqualsToken,
    ts.SyntaxKind.EqualsEqualsToken,
    ts.SyntaxKind.ExclamationEqualsToken,
  ])

// `compiles(text)` says whether Tailwind emits CSS for the string. A closed set of literals is an
// enum — exempt — only when NO member compiles: `'block-start' | 'block-end'` styles nothing, while
// `'text-text-primary' | 'text-secondary'` is a class vocabulary whose every member must be
// defined. A compared string (`===`, `case`) styles nothing whatever its spelling, so those
// positions stay exempt without the test.
function isEnumMemberPosition(ts, node, checker, equality, compiles) {
  const parent = node.parent
  if (ts.isBinaryExpression(parent) && equality.has(parent.operatorToken.kind)) return true
  if (ts.isCaseClause(parent) && parent.expression === node) return true
  if (ts.isLiteralTypeNode(parent)) return !literalTypeSiblings(ts, parent).some(compiles)
  // Template heads/middles/tails belong to a template with substitutions, which is always a free
  // class string; only a substitution-free template can stand for a member of a closed set.
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    const members = closedStringLiteralSet(ts, checker.getContextualType(node))
    return members !== null && !members.some(compiles)
  }
  return false
}

const isBareFunctionalRoot = (c) =>
  c.kind === 'functional' && c.value === null && c.modifier === null

/**
 * @returns {Promise<{ hits: {file: string, line: number, cls: string}[], files: number, candidates: number }>}
 */
export async function checkDefinedClasses(srcDir = defaultSrcDir) {
  const ts = (await import(dsRequire.resolve('typescript'))).default
  const { design, customPrefixes } = await loadTailwindDesignSystem()
  const files = listComponentSource(srcDir)
  const program = ts.createProgram({ rootNames: files, options: compilerOptionsFor(ts, srcDir) })
  const checker = program.getTypeChecker()
  const equality = EQUALITY(ts)

  const compiles = (text) => {
    const parsed = design.parseCandidate(text)
    return parsed.length > 0 && design.candidatesToCss([text])[0] != null
  }
  const isNonBareCandidate = (text) => {
    const parsed = design.parseCandidate(text)
    return parsed.length > 0 && !parsed.every(isBareFunctionalRoot)
  }

  const verdicts = new Map() // token -> 'defined' | 'skip' | 'undefined' | 'not-a-class'
  function verdict(token) {
    let v = verdicts.get(token)
    if (v) return v
    const parsed = design.parseCandidate(token)
    if (parsed.length === 0) {
      // Prose, unless it is a typo of something the stylesheet defines (header, rules A and B).
      const tail = token.slice(token.lastIndexOf(':') + 1)
      if (token.includes(':') && (isNonBareCandidate(tail) || compiles(tail))) v = 'undefined'
      else if (customPrefixes.some((prefix) => tail.startsWith(prefix))) v = 'undefined'
      else v = 'not-a-class'
    } else if (design.candidatesToCss([token])[0] != null) v = 'defined'
    else if (parsed.every(isBareFunctionalRoot)) v = 'skip'
    else v = 'undefined'
    verdicts.set(token, v)
    return v
  }

  const hits = []
  let candidates = 0
  const rel = (f) => {
    const r = path.relative(rootDir, f)
    return r.startsWith('..') ? f : r
  }

  for (const file of files) {
    const sf = program.getSourceFile(file)
    if (!sf) throw new Error(`defined-classes: ${file} is not in the program`)
    const visit = (node) => {
      const isText =
        ts.isStringLiteral(node) ||
        ts.isNoSubstitutionTemplateLiteral(node) ||
        ts.isTemplateHead(node) ||
        ts.isTemplateMiddle(node) ||
        ts.isTemplateTail(node)
      if (isText && !isEnumMemberPosition(ts, node, checker, equality, compiles)) {
        const text = node.text
        const startLine = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
        for (const m of text.matchAll(/\S+/g)) {
          const v = verdict(m[0])
          if (v === 'not-a-class' || v === 'skip') continue
          candidates += 1
          if (v === 'undefined') {
            const line = startLine + (text.slice(0, m.index).match(/\n/g)?.length ?? 0)
            hits.push({ file: rel(file), line, cls: m[0] })
          }
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
  }
  return { hits, files: files.length, candidates }
}

async function main() {
  const srcDir = process.argv[2] ? path.resolve(process.argv[2]) : defaultSrcDir
  if (!existsSync(srcDir)) {
    console.error(`defined-classes: ${srcDir} does not exist`)
    process.exit(1)
  }
  let result
  try {
    result = await checkDefinedClasses(srcDir)
  } catch (err) {
    console.error(`defined-classes: ${err instanceof Error ? err.message : err}`)
    process.exit(1)
  }
  for (const h of result.hits) console.error(`defined-classes: ${h.file}:${h.line} ${h.cls}`)
  if (result.hits.length > 0) {
    console.error(
      `defined-classes: ${result.hits.length} class${result.hits.length === 1 ? '' : 'es'} the ` +
        `stylesheet does not define, across ${result.files} files under ${path.relative(rootDir, srcDir) || srcDir}.`,
    )
    process.exit(1)
  }
  console.log(
    `defined-classes: ${result.files} files, ${result.candidates} class candidates checked, all defined.`,
  )
}

// Only run when invoked directly — defined-classes.test.mjs imports the functions above.
if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main()
}
