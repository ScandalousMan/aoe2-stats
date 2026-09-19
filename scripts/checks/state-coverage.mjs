#!/usr/bin/env node
// T594 (amended 2026-09-13, remediated after the orchestrator's review of this task's own second
// hand-back): extracts records 1 and 3 of packages/design-system/specs/README.md's "Contrast-signal
// and duplicate-baseline gap register" row 8 (H5) mechanically, from source and stories, never from a
// line grep and never from call sites alone.
//
// Three defects the orchestrator's review found and this version fixes:
//
//   1. Consistency mode used to diff a JSON snapshot embedded in the README against a fresh run —
//      which only ever proves the snapshot itself hasn't drifted, never that the *prose a reader
//      sees* agrees with it. This version renders record 1 and every primitive matrix as markdown
//      tables directly between `<!-- state-coverage:begin -->`/`<!-- state-coverage:end -->` markers
//      in row 8 (`--write` regenerates them); check mode fails when that region differs from a fresh
//      render. There is no second copy of the data — the rendered tables *are* the record.
//   2. A coverage cell used to default to `'none'` whether the script had *confirmed* no story
//      depicts a state or had merely *failed to resolve* which of several candidates a force-state
//      targets — a false gap in the machine record, indistinguishable from a real one. This version
//      renders `unresolved: <reason>` for the second case and resolves most of what used to fall into
//      it: a story's own `args` (merged with the component's default meta `args`) supplies the
//      literal label/children/`triggerLabel`/nested-object text a `visualForceState`'s own `name`
//      matches when the rendering JSX itself carries no literal text (`Dialog`'s
//      `{primaryAction.label}`); `aria-hidden` elements are excluded from every role-based candidate
//      pool, the same way Playwright's own `getByRole` treats them (`FavouriteToggle`'s decoy);
//      `nth` is resolved against the *inline* candidates of a shared role, sorted by source position,
//      once elements defined inside a reusable local helper function (whose own use sites this static
//      pass cannot enumerate) are excluded from that ordering.
//   3. Record 2 (the handoff tally) was re-read for 6 of 29 spec files. This task's own remediation
//      re-reads all 29.
//
// What this file computes, pure functions (no filesystem access below computeStateCoverage) so
// state-coverage.test.mjs can prove every rule against a small fixture — Record 1: every interactive
// element a component renders locally, with its hover/focus-visible/active classes and which story
// (or `none`, confirmed, or `unresolved`, with a reason) depicts each state. Record 3: every Button,
// Link, Field and Menu instance in source and in stories, resolved against the primitive's own
// defaults when a prop is omitted, and the primitive's own variant/size (or structural-element)
// matrix.
//
// Records 2 (handoff prose) and 4 (false self-claims) stay read by a person against this file's
// output — sentences in specs/*.md and in a story's own comment or rendered text, not a structural
// fact a parser can lift.
//
// Usage:
//   node scripts/checks/state-coverage.mjs            check mode: exit 0 when row 8's generated
//                                                      region matches a fresh render, 1 otherwise
//                                                      (prints a line-level diff, `diffLines`).
//   node scripts/checks/state-coverage.mjs --write     regenerates the region in place, formatted
//                                                      through prettier so check mode never sees a
//                                                      prettier-only difference.
import { readFileSync, readdirSync, statSync, writeFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { execFileSync } from 'node:child_process'
import { listComponentDirs } from './story-docs.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const dsDir = path.join(rootDir, 'packages', 'design-system')
const srcDir = path.join(dsDir, 'src')
const readmePath = path.join(dsDir, 'specs', 'README.md')
const prettierBin = path.join(rootDir, 'node_modules', '.bin', 'prettier')

// `typescript` is a direct devDependency of packages/design-system, not of the workspace root —
// resolved through that package's own node_modules rather than adding a second copy at the root.
const dsRequire = createRequire(path.join(dsDir, 'package.json'))
const ts = dsRequire('typescript')

function log(message) {
  console.log(`state-coverage: ${message}`)
}
function fail(message) {
  console.error(`state-coverage: ${message}`)
  process.exitCode = 1
}

// --- Parsing -----------------------------------------------------------------------------------

export function parseTsx(fileName, code) {
  return ts.createSourceFile(fileName, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
}

function isJsxTag(node) {
  return ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)
}

function openingOf(node) {
  return ts.isJsxElement(node) ? node.openingElement : node
}

function tagNameOf(node) {
  return openingOf(node).tagName.getText()
}

// --- Same-file string/class resolution ------------------------------------------------------

export function resolveClassParts(expr, constMap, unresolved = []) {
  if (!expr) return []
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) {
    return [expr.text]
  }
  if (ts.isTemplateExpression(expr)) {
    const parts = [expr.head.text]
    for (const span of expr.templateSpans) {
      unresolved.push('<template-expression>')
      parts.push(span.literal.text)
    }
    return parts
  }
  if (ts.isParenthesizedExpression(expr)) {
    return resolveClassParts(expr.expression, constMap, unresolved)
  }
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    return [
      ...resolveClassParts(expr.left, constMap, unresolved),
      ...resolveClassParts(expr.right, constMap, unresolved),
    ]
  }
  if (
    ts.isBinaryExpression(expr) &&
    (expr.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken ||
      expr.operatorToken.kind === ts.SyntaxKind.BarBarToken ||
      expr.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken)
  ) {
    return [
      ...resolveClassParts(expr.left, constMap, unresolved),
      ...resolveClassParts(expr.right, constMap, unresolved),
    ]
  }
  if (ts.isConditionalExpression(expr)) {
    return [
      ...resolveClassParts(expr.whenTrue, constMap, unresolved),
      ...resolveClassParts(expr.whenFalse, constMap, unresolved),
    ]
  }
  if (ts.isArrayLiteralExpression(expr)) {
    return expr.elements.flatMap((el) => resolveClassParts(el, constMap, unresolved))
  }
  if (ts.isCallExpression(expr)) {
    const callee = expr.expression.getText()
    if (callee === 'cx' || callee === 'clsx') {
      return expr.arguments.flatMap((arg) => resolveClassParts(arg, constMap, unresolved))
    }
    unresolved.push(`<call:${callee}>`)
    return []
  }
  if (ts.isIdentifier(expr)) {
    if (constMap.has(expr.text)) return constMap.get(expr.text)
    unresolved.push(expr.text)
    return []
  }
  if (ts.isJsxExpression(expr) && expr.expression) {
    return resolveClassParts(expr.expression, constMap, unresolved)
  }
  unresolved.push(`<${ts.SyntaxKind[expr.kind] ?? 'expr'}>`)
  return []
}

export function buildConstStringMap(sourceFile) {
  const constMap = new Map()
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || !decl.initializer) continue
      const parts = resolveClassParts(decl.initializer, constMap, [])
      if (parts.length > 0) constMap.set(decl.name.text, parts)
    }
  }
  return constMap
}

// `focus` (real `:focus`, painted whenever the element takes focus by any means — pointer or
// keyboard) is captured alongside the three state pseudo-classes rather than folded into
// `focus-visible` at extraction time: `SiteHeader`'s skip link (`focus:not-sr-only focus:fixed …
// focus:border-border-strong focus:bg-surface-raised`) paints entirely through this prefix and none
// of it was visible to record 1 before (finding 10) — the regex requires the colon immediately
// after the prefix, so `focus:` never matches inside `focus-visible:`.
const PSEUDO_PREFIXES = ['hover', 'focus-visible', 'active', 'focus']

export function extractPseudoClasses(parts) {
  const text = parts.join(' ')
  const result = {}
  for (const prefix of PSEUDO_PREFIXES) {
    const re = new RegExp(`(?:^|\\s)(${prefix}:[^\\s]+)`, 'g')
    const found = [...text.matchAll(re)].map((m) => m[1])
    result[prefix] = found.length > 0 ? found.join(' ') : null
  }
  return result
}

// --- JSX attribute helpers --------------------------------------------------------------------

function getAttr(openingElement, name) {
  for (const attr of openingElement.attributes.properties) {
    if (ts.isJsxAttribute(attr) && attr.name.getText() === name) return attr
  }
  return undefined
}

function hasSpreadAttr(openingElement) {
  return openingElement.attributes.properties.some((a) => ts.isJsxSpreadAttribute(a))
}

function attrLiteral(attr) {
  if (!attr) return { present: false, literal: false, value: undefined }
  if (!attr.initializer) return { present: true, literal: true, value: true }
  let expr = attr.initializer
  if (ts.isJsxExpression(expr)) expr = expr.expression
  if (!expr) return { present: true, literal: false, value: undefined }
  if (ts.isStringLiteral(expr)) return { present: true, literal: true, value: expr.text }
  if (ts.isNumericLiteral(expr)) return { present: true, literal: true, value: Number(expr.text) }
  if (
    ts.isPrefixUnaryExpression(expr) &&
    expr.operator === ts.SyntaxKind.MinusToken &&
    ts.isNumericLiteral(expr.operand)
  ) {
    return { present: true, literal: true, value: -Number(expr.operand.text) }
  }
  if (expr.kind === ts.SyntaxKind.TrueKeyword) return { present: true, literal: true, value: true }
  if (expr.kind === ts.SyntaxKind.FalseKeyword)
    return { present: true, literal: true, value: false }
  return { present: true, literal: false, value: undefined }
}

// True when this element is invisible to Playwright's `getByRole` — the same accessibility-tree
// exclusion Chromium's own accessible-name computation applies, which is why `FavouriteToggle`'s
// `tabIndex={-1} aria-hidden` decoy `Button/ghost` can never be what a `role: 'button'` force-state
// targets, and is never offered as a match candidate.
function isAriaHidden(opening) {
  // React (and this tree's own usage, `FavouriteToggle`'s decoy) accepts `aria-hidden` as a bare
  // boolean prop *or* the string `"true"` — the DOM attribute is always a string, so both compile to
  // the same rendered markup, and both are read here.
  const value = attrLiteral(getAttr(opening, 'aria-hidden')).value
  return value === true || value === 'true'
}

function lineOf(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
}

// An element's own literal `aria-label` — a real accessible-name source `resolveNameMatch` must
// see the same way it sees JSX text, since a `visualForceState`'s own `name` names the accessible
// name, not specifically the rendered children (T594's REJECT on #80, item 3). `aria-labelledby`
// is not read here: its own value is an id reference, not display text — the name it supplies, if
// literal, is resolved instead through the referenced element's own text via the sole-candidate
// argsLiterals path (`Table`'s own `region`/caption shape).
function ariaLabelText(opening) {
  const lit = attrLiteral(getAttr(opening, 'aria-label'))
  return lit.literal && typeof lit.value === 'string' ? lit.value : ''
}

function literalTextOf(node) {
  if (!ts.isJsxElement(node)) return ''
  return node.children
    .map((child) => {
      if (ts.isJsxText(child)) return child.text
      if (ts.isJsxExpression(child) && child.expression && ts.isStringLiteral(child.expression)) {
        return child.expression.text
      }
      return ''
    })
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
}

const INTERACTIVE_TAGS = new Set(['a', 'button', 'input', 'select', 'textarea', 'summary'])
// A `label` only counts as a local interactive element where it *wraps* a control — nests one as
// a JSX descendant — never for the far more common `htmlFor`/sibling-`input` association
// (`SearchBox`, `ThirdPartyObjectionForm` and `Field` all associate this way, painting no state of
// their own on the label itself). `AccountErasurePanel`'s acknowledgement checkbox is the one real
// case in this tree, its `<input type="checkbox" />` a direct JSX child of the `<label>`.
const LABEL_CONTROL_TAGS = new Set(['input', 'select', 'textarea', 'button'])
function labelWrapsControl(node) {
  let found = false
  function visit(n) {
    if (found) return
    if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n)) {
      if (LABEL_CONTROL_TAGS.has(tagNameOf(n))) {
        found = true
        return
      }
    }
    ts.forEachChild(n, visit)
  }
  ts.forEachChild(node, visit)
  return found
}
// T595 (row 8, H5, the `noImpliedRoleReason` family): every tag below carries exactly one ARIA
// role regardless of its own attributes — the same property that makes a bare per-tag constant
// honest here, unlike `<input>` (handled separately through `INPUT_TYPE_ROLE`/`deriveStructuralRole`
// because its role depends on `type`). `h1`-`h6` are always `heading` (`aria-level` follows the
// number, immaterial to matching a `role`). The table family is extended past the one tag the
// sweep actually found a local element for (`tr`, `Table`'s own row) to its whole fixed-role
// group — `table`, `thead`/`tbody`/`tfoot` (`rowgroup`) and `td` (`cell`) — so the next component
// that puts a hover class on a `<td>` does not reopen this map one tag at a time. `th` is
// deliberately absent: its own role is `columnheader` or `rowheader` depending on its `scope`
// attribute (`col`/`colgroup` vs `row`/`rowgroup`) or, lacking one, its position in the table — the
// same shape as `<input>`'s `type`-dependent role, not a constant this map can hold honestly, and no
// `th` in this tree carries a pseudo-class today for a `deriveStructuralRole` entry to be written
// and tested against.
const INTRINSIC_ROLE = {
  a: 'link',
  button: 'button',
  input: 'textbox',
  select: 'combobox',
  textarea: 'textbox',
  summary: 'button',
  main: 'main',
  h1: 'heading',
  h2: 'heading',
  h3: 'heading',
  h4: 'heading',
  h5: 'heading',
  h6: 'heading',
  table: 'table',
  thead: 'rowgroup',
  tbody: 'rowgroup',
  tfoot: 'rowgroup',
  tr: 'row',
  td: 'cell',
}

// `<input>`'s accessible role depends on its own `type`, not a fixed intrinsic mapping — an
// unlisted or dynamic `type` falls back to `INTRINSIC_ROLE.input` (`'textbox'`) downstream, the
// same behaviour every input already had before this map existed.
const INPUT_TYPE_ROLE = {
  search: 'searchbox',
  checkbox: 'checkbox',
  radio: 'radio',
  range: 'slider',
  button: 'button',
  submit: 'button',
  reset: 'button',
}

// A role this pass can derive from structure rather than from an explicit `role` attribute —
// `<input type="search">`'s `searchbox` (`SearchBox`'s own input), `<nav>`'s `navigation`, and a
// `<section>` given an accessible name (`aria-label`/`aria-labelledby`) its own `region`. Returns
// `null` when nothing beyond the tag's own `INTRINSIC_ROLE` entry (or none at all) applies — the
// caller's existing fallback chain is unchanged for every other tag.
function deriveStructuralRole(tagName, opening) {
  if (tagName === 'input') {
    const typeAttr = attrLiteral(getAttr(opening, 'type'))
    if (typeAttr.literal && INPUT_TYPE_ROLE[typeAttr.value]) return INPUT_TYPE_ROLE[typeAttr.value]
    return null
  }
  if (tagName === 'nav') return 'navigation'
  if (tagName === 'section') {
    if (getAttr(opening, 'aria-label') || getAttr(opening, 'aria-labelledby')) return 'region'
    return null
  }
  return null
}

// --- Shared JSX walk: tracks the enclosing named-function context, the *reachability guards* an
// early return or a conditional/`&&` puts between the file's own top and a given JSX node, and the
// local `const` bindings in scope at that point — everything `findLocalElements`,
// `findPrimitiveInstances` and the dynamic-props resolver below need, so none of them duplicate
// this tracking three different ways. -------------------------------------------------------------

// A `{ expr, truthy }` pair: for the JSX this guards to be reached, `expr` (evaluated against a
// caller's own props/args, `evaluateExpr` below) must equal `truthy`. Collected from three shapes:
//   - `if (cond) { return X }` with no `else` — `X` is guarded `{cond, true}`; every *sibling*
//     statement after this `if` (this function's own remaining body) is guarded `{cond, false}`,
//     because reaching them at all means the early return did not fire (`FavouriteToggle`'s own
//     `if (!authenticated) return <SignedOutControl .../>`).
//   - `if (cond) { A } else { B }` — `A` guarded `{cond, true}`, `B` guarded `{cond, false}`.
//   - `cond ? A : B` / `cond && A` — the same two shapes as expressions, not statements.
function blockAlwaysExits(statements) {
  if (statements.length === 0) return false
  const last = statements[statements.length - 1]
  return ts.isReturnStatement(last) || ts.isThrowStatement(last)
}

function statementsOf(stmtOrBlock) {
  return ts.isBlock(stmtOrBlock) ? stmtOrBlock.statements : [stmtOrBlock]
}

function walkJsxWithContext(sourceFile, visitJsx) {
  function visitBlockStatements(statements, ctx) {
    let guards = ctx.guards
    // A local `const` declared earlier in the same function body (`FavouriteToggle`'s own `const
    // bounded = atLimit && !favourited`) is not a prop and not in scope for a later story-args
    // evaluation unless its own initializer travels with the candidate — threaded the same way
    // `guards` already is, reset at the same function boundaries (`visit` below), so a candidate's
    // own `localConsts` map always reflects exactly what is declared and in scope at its own JSX
    // position, in source order.
    let localConsts = ctx.localConsts
    for (const stmt of statements) {
      if (ts.isVariableStatement(stmt)) {
        for (const decl of stmt.declarationList.declarations) {
          if (ts.isIdentifier(decl.name) && decl.initializer) {
            visit(decl.initializer, { ...ctx, guards, localConsts })
            localConsts = new Map(localConsts)
            localConsts.set(decl.name.text, decl.initializer)
          }
        }
      } else if (ts.isIfStatement(stmt)) {
        const cond = stmt.expression
        const thenStmts = statementsOf(stmt.thenStatement)
        visitBlockStatements(thenStmts, {
          ...ctx,
          guards: [...guards, { expr: cond, truthy: true }],
          localConsts,
        })
        if (stmt.elseStatement) {
          const elseStmts = ts.isIfStatement(stmt.elseStatement)
            ? [stmt.elseStatement]
            : statementsOf(stmt.elseStatement)
          visitBlockStatements(elseStmts, {
            ...ctx,
            guards: [...guards, { expr: cond, truthy: false }],
            localConsts,
          })
        } else if (blockAlwaysExits(thenStmts)) {
          guards = [...guards, { expr: cond, truthy: false }]
        }
      } else if (ts.isReturnStatement(stmt)) {
        if (stmt.expression) visit(stmt.expression, { ...ctx, guards, localConsts })
        return
      } else {
        visit(stmt, { ...ctx, guards, localConsts })
      }
    }
  }

  function visit(node, ctx) {
    if (isJsxTag(node)) {
      visitJsx(node, ctx)
      ts.forEachChild(node, (child) => visit(child, ctx))
      return
    }
    if (ts.isConditionalExpression(node)) {
      visit(node.condition, ctx)
      visit(node.whenTrue, {
        ...ctx,
        guards: [...ctx.guards, { expr: node.condition, truthy: true }],
      })
      visit(node.whenFalse, {
        ...ctx,
        guards: [...ctx.guards, { expr: node.condition, truthy: false }],
      })
      return
    }
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
    ) {
      visit(node.left, ctx)
      visit(node.right, { ...ctx, guards: [...ctx.guards, { expr: node.left, truthy: true }] })
      return
    }
    if (ts.isBlock(node)) {
      visitBlockStatements(node.statements, ctx)
      return
    }
    let nextCtx = ctx
    if (ts.isFunctionDeclaration(node) && node.name) {
      nextCtx = { ...ctx, fnName: node.name.text, guards: [], localConsts: new Map() }
    } else if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.initializer &&
      (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer))
    ) {
      // The name lives on the declaration; the fresh function scope starts at the initializer
      // itself (visited next via forEachChild), which is where `guards`/`localConsts` should
      // reset — done by threading the reset through this same `nextCtx`, since forEachChild's next
      // call is exactly that initializer.
      nextCtx = { ...ctx, fnName: node.name.text, guards: [], localConsts: new Map() }
    }
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      (node.expression.name.text === 'map' || node.expression.name.text === 'flatMap')
    ) {
      // The iteration's own variable name and array source (`entries.map((entry) => ...)`) — a
      // selector-targeted local element inside a single-entry story (`FavouritesList`'s own
      // `entries: [rated]`) resolves its dynamic attribute (`entry.href`) against the sole array
      // element this way; `null` when the callback's own first parameter isn't a plain identifier
      // (a destructuring pattern), left unresolved rather than guessed further.
      const callback = node.arguments[0]
      let iterationVar = null
      if (
        callback &&
        (ts.isArrowFunction(callback) || ts.isFunctionExpression(callback)) &&
        callback.parameters.length > 0 &&
        ts.isIdentifier(callback.parameters[0].name)
      ) {
        iterationVar = callback.parameters[0].name.text
      }
      nextCtx = {
        ...nextCtx,
        inIteration: true,
        iterationVar,
        iterationArrayExpr: node.expression.expression,
      }
    }
    ts.forEachChild(node, (child) => visit(child, nextCtx))
  }
  visit(sourceFile, {
    fnName: null,
    inIteration: false,
    iterationVar: null,
    iterationArrayExpr: null,
    guards: [],
    localConsts: new Map(),
  })
}

// Every locally-declared helper *component* (a capitalised, non-primitive JSX tag invoked
// somewhere in this file, `<SignedOutControl .../>`) mapped to the guards at its own call site —
// `FavouriteToggle`'s `if (!authenticated) { return <SignedOutControl .../> } ... return button`
// nests the *real* button structurally inside `FavouriteToggle`'s own body (guarded there), but
// `SignedOutControl`'s own button sits inside a *separate* function declaration, invoked only
// conditionally — its own reachability guards live at the call site, not inside its declaration,
// so a plain structural walk of `SignedOutControl`'s body alone would never see them. Only a helper
// invoked from exactly one call site can be attributed guards this way; more than one (with
// differing guards) is `null` — unknown, not guessed.
// A guard list's own identity, by AST position rather than by value — an AST node carries a
// circular `.parent` pointer (`ts.createSourceFile`'s own `setParentNodes: true`), so comparing
// guard lists with `JSON.stringify` throws; comparing each guard's `expr.pos`/`expr.end` instead
// is cheap and exact; for the same parsed file, the same source span always means the same guard.
function guardsKey(guards) {
  return guards.map((g) => `${g.expr.pos}:${g.expr.end}:${g.truthy}`).join('|')
}

export function findHelperInvocationGuards(sourceFile) {
  const map = new Map()
  walkJsxWithContext(sourceFile, (node, context) => {
    const tagName = tagNameOf(node)
    if (!/^[A-Z]/.test(tagName) || PRIMITIVE_NAMES.includes(tagName)) return
    if (!map.has(tagName)) {
      map.set(tagName, context.guards)
    } else {
      const existing = map.get(tagName)
      if (existing !== null && guardsKey(existing) !== guardsKey(context.guards)) {
        map.set(tagName, null)
      }
    }
  })
  return map
}

// A helper component invoked from exactly one call site *inside* a `.map()`/`.flatMap()`
// callback, one of whose own props passes that callback's own iteration variable through
// literally (`FavouritesList`'s own `entry={entry}`, passed to the sibling `FavouriteRow`) — one
// indirection past the inline shape `MatchRow`/`PlayerResultRow` render their own row link in,
// where the local element sits directly inside the `.map()` callback rather than behind a second,
// separately-declared component. Only a bare identifier prop value equal to the call site's own
// iteration variable qualifies; a transform, a spread, more than one candidate prop at the same
// call site, or more than one call site with a different answer all leave the helper unmapped —
// found, never guessed. The mapped `iterationVar` is the *prop name* at the call site
// (`FavouriteRow`'s own `entry`), not the caller's local name, since evaluating a dynamic
// attribute inside the helper's body reads whatever identifier its own destructuring bound —
// ordinarily the same name, by convention, but never assumed so: a helper that renamed its own
// destructured binding simply fails to resolve further (`evaluateExpr` finds no such identifier
// in scope), the same "unresolved, not guessed" default as every other static gap in this file.
export function findHelperInvocationIterationContext(sourceFile) {
  const map = new Map()
  function entrySignature(entry) {
    return entry
      ? `${entry.propName}:${entry.iterationArrayExpr.pos}:${entry.iterationArrayExpr.end}`
      : 'none'
  }
  walkJsxWithContext(sourceFile, (node, context) => {
    const tagName = tagNameOf(node)
    if (!/^[A-Z]/.test(tagName) || PRIMITIVE_NAMES.includes(tagName)) return
    let entry = null
    if (context.iterationVar) {
      const opening = openingOf(node)
      const candidates = []
      for (const attr of opening.attributes.properties) {
        if (!ts.isJsxAttribute(attr) || !attr.initializer) continue
        const expr = ts.isJsxExpression(attr.initializer) ? attr.initializer.expression : null
        if (expr && ts.isIdentifier(expr) && expr.text === context.iterationVar) {
          candidates.push(attr.name.getText())
        }
      }
      if (candidates.length === 1) {
        entry = {
          propName: candidates[0],
          iterationArrayExpr: context.iterationArrayExpr,
        }
      }
    }
    if (!map.has(tagName)) {
      map.set(tagName, entry)
    } else {
      const existing = map.get(tagName)
      if (existing === 'ambiguous') return
      if (entrySignature(existing) !== entrySignature(entry)) {
        map.set(tagName, 'ambiguous')
      }
    }
  })
  const result = new Map()
  for (const [name, entry] of map) {
    if (entry && entry !== 'ambiguous') {
      result.set(name, {
        iterationVar: entry.propName,
        iterationArrayExpr: entry.iterationArrayExpr,
      })
    }
  }
  return result
}

// --- Record 1: local interactive elements -------------------------------------------------------

// `mainComponentName`: the directory's own component name (`PrivacyNotice`) — an element whose
// nearest enclosing named function is anything *else* (`InlineLink`, `SectionHeading`) is a reusable
// local helper invoked from more than one place this static pass cannot enumerate, so its recorded
// line is a declaration site, not a real render position (`isHelper: true`, excluded from `nth`
// resolution below, never from Record 1's own listing).
export function findLocalElements(
  sourceFile,
  filePath,
  constMap,
  mainComponentName = null,
  helperIterationContext = new Map(),
) {
  const found = []
  walkJsxWithContext(sourceFile, (node, context) => {
    const tagName = tagNameOf(node)
    if (!/^[a-z]/.test(tagName)) return
    const opening = openingOf(node)
    const roleAttr = attrLiteral(getAttr(opening, 'role'))
    const tabIndexAttr = attrLiteral(getAttr(opening, 'tabIndex'))
    const classAttr = getAttr(opening, 'className')
    const unresolved = []
    const parts = classAttr
      ? resolveClassParts(
          classAttr.initializer && ts.isJsxExpression(classAttr.initializer)
            ? classAttr.initializer.expression
            : classAttr.initializer,
          constMap,
          unresolved,
        )
      : []
    const pseudo = extractPseudoClasses(parts)
    const hasPseudo = pseudo.hover || pseudo['focus-visible'] || pseudo.active || pseudo.focus
    const isIntrinsicInteractive =
      tagName === 'label' ? labelWrapsControl(node) : INTERACTIVE_TAGS.has(tagName)
    const isRoleInteractive =
      roleAttr.literal && (roleAttr.value === 'button' || roleAttr.value === 'link')
    const isTabIndexed = tabIndexAttr.present
    if (!(isIntrinsicInteractive || isRoleInteractive || isTabIndexed || hasPseudo)) return
    // Whether this element carries *any* disabled-capable attribute at all (`disabled` or
    // `aria-disabled`, literal or dynamic) — an element with neither can never render disabled, a
    // confirmed `'none'`; one that does needs a story's own data checked before the disabled cell
    // may say either `'none'` or name a story (T594's REJECT on #80, item 4).
    const hasDisabledAttr = Boolean(
      getAttr(opening, 'disabled') || getAttr(opening, 'aria-disabled'),
    )
    // Every attribute's own value, literal or not — the generic sibling of the named
    // role/tabIndex/disabled reads above, read once so a `visualForceState: { selector:
    // 'a[href="..."]' }` can resolve *any* attribute name a real selector in this tree names, not
    // only the ones this file already has a dedicated reader for.
    const attrExprs = new Map()
    for (const attr of opening.attributes.properties) {
      if (!ts.isJsxAttribute(attr)) continue
      const attrName = attr.name.getText()
      const lit = attrLiteral(attr)
      let expr = null
      if (attr.initializer && ts.isJsxExpression(attr.initializer))
        expr = attr.initializer.expression
      attrExprs.set(attrName, { literal: lit.present && lit.literal, value: lit.value, expr })
    }
    // A candidate lexically inside a helper component that has no iteration context of its own
    // (a fresh function declaration, not directly nested in a `.map()`/`.flatMap()` callback) may
    // still be *invoked* from one, one call site, through a prop passed literally —
    // `findHelperInvocationIterationContext`'s own map, keyed by the helper's name.
    const inheritedIteration =
      !context.iterationVar && context.fnName ? helperIterationContext.get(context.fnName) : null
    found.push({
      file: filePath,
      line: lineOf(sourceFile, node),
      tag: tagName,
      role: roleAttr.literal
        ? roleAttr.value
        : roleAttr.present
          ? 'unresolved'
          : deriveStructuralRole(tagName, opening),
      tabIndex: tabIndexAttr.present
        ? tabIndexAttr.literal
          ? tabIndexAttr.value
          : 'unresolved'
        : null,
      hover: pseudo.hover,
      focusVisible: pseudo['focus-visible'],
      active: pseudo.active,
      focus: pseudo.focus,
      classUnresolvedRefs: unresolved,
      text: literalTextOf(node) || ariaLabelText(opening),
      hasDisabledAttr,
      attrExprs,
      // Every local `const` in scope at this exact JSX position (`MenuItemRow`'s own `const role =
      // variant === 'selection' ? 'menuitemradio' : 'menuitem'`) — the same read
      // `findPrimitiveInstances` already keeps for a dynamic `disabled`/`loading` expression, needed
      // here so a dynamic `role={role}` attribute (`attrExprs.get('role').expr`, below) can be
      // resolved against a specific story's own scope (T595, `noImpliedRoleReason`'s "dynamic role").
      localConsts: context.localConsts,
      ariaHidden: isAriaHidden(opening),
      isHelper: context.fnName != null && context.fnName !== mainComponentName,
      isInsideIteration: context.inIteration || Boolean(inheritedIteration),
      iterationVar: context.iterationVar ?? inheritedIteration?.iterationVar ?? null,
      iterationArrayExpr:
        context.iterationArrayExpr ?? inheritedIteration?.iterationArrayExpr ?? null,
      guards: context.guards,
      // Character offsets of this element's own JSX node — used only to tell whether one local
      // element's rendered range structurally contains another's (`buildElementMatrix`'s "ancestor
      // of a forced descendant" reason, `Table`'s own `<tr>` around its row link). Not meaningful
      // across two different files.
      nodeStart: node.getStart(sourceFile),
      nodeEnd: node.getEnd(),
    })
  })
  return found
}

// --- Record 3: primitive instances --------------------------------------------------------------

export const PRIMITIVE_NAMES = ['Button', 'Link', 'Field', 'Menu']

// `Button` (`primitives/Button/index.tsx`: `disabled={disabled || loading}`) and `Field`
// (`primitives/Field/index.tsx`: `const isDisabled = disabled || loading`) both render their own
// `loading` prop through the exact same rendered-disabled state their `disabled` prop reaches —
// `Link` and `Menu` carry no such fold. A call site that only ever sets `loading` (`FavouriteToggle`'s
// own `AddingInFlight`/`RemovingInFlight`, never a literal `disabled`) is real, positive disabled
// coverage this file must not miss (T594's row 8 sweep, item 1).
const PRIMITIVES_WHERE_LOADING_DISABLES = new Set(['Button', 'Field'])

// The role a composed primitive instance actually renders as — never a single constant per
// primitive name (`INTRINSIC_ROLE[primitive.toLowerCase()]` gave `null` for `Link`/`Field`/`Menu`,
// so `Link` only ever pooled on a literal `role: 'button'` force-state, and that same universal
// `'button'` wildcard let a button-role story be wrongly credited to a `Link`/`Field`/`Menu`
// instance sitting in the same component — T594's REJECT on #80, item 5). `Button` renders `<a
// href>` once `href` is supplied (own `index.tsx`); `Link` is always `<a>`; `Menu`'s own trigger is
// always `<button>`. `Field` wraps a caller-supplied control under no single fixed role of its own
// — `null`, matched by nothing, rather than guessed.
export function impliedRoleForPrimitiveInstance(primitive, candidate) {
  if (primitive === 'Button') return candidate?.hasHref ? 'link' : 'button'
  if (primitive === 'Link') return 'link'
  if (primitive === 'Menu') return 'button'
  return null
}

export function findVariantSizeDefaults(sourceFile) {
  let variantDefault = null
  let sizeDefault = null
  function visit(node) {
    if (ts.isObjectBindingPattern(node)) {
      for (const el of node.elements) {
        if (!ts.isBindingElement(el) || !ts.isIdentifier(el.name)) continue
        const propName = el.propertyName ? el.propertyName.getText() : el.name.text
        if (!el.initializer) continue
        if (propName === 'variant' && ts.isStringLiteral(el.initializer)) {
          variantDefault = el.initializer.text
        }
        if (propName === 'size' && ts.isStringLiteral(el.initializer)) {
          sizeDefault = el.initializer.text
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return { variant: variantDefault, size: sizeDefault }
}

// The raw expression an attribute's `{...}` container wraps (never unwrapped through a literal) —
// used to evaluate a *dynamic* `variant`/`size` (`Dialog`'s `primaryAction.variant ?? 'destructive'`)
// against a specific story's own scope later, rather than discarding it the moment it fails to be a
// literal.
function attrExprOf(attr) {
  if (!attr || !attr.initializer) return null
  return ts.isJsxExpression(attr.initializer) ? attr.initializer.expression : null
}

export function findPrimitiveInstances(
  sourceFile,
  filePath,
  defaultsByPrimitive,
  skipPrimitives = [],
  helperGuards = new Map(),
) {
  const found = []
  walkJsxWithContext(sourceFile, (node, context) => {
    const tagName = tagNameOf(node)
    if (!PRIMITIVE_NAMES.includes(tagName) || skipPrimitives.includes(tagName)) return
    // A candidate declared inside a helper *component* invoked from exactly one, known call site
    // inherits that call site's own guards, prepended — the mechanism that excludes
    // `SignedOutControl`'s own button when a story's `authenticated: true` arg means
    // `FavouriteToggle` never even calls it.
    const inheritedGuards =
      context.fnName && helperGuards.has(context.fnName)
        ? (helperGuards.get(context.fnName) ?? [])
        : []
    const effectiveGuards = [...inheritedGuards, ...context.guards]
    const opening = openingOf(node)
    const defaults = defaultsByPrimitive[tagName] ?? {}
    const spread = hasSpreadAttr(opening)
    const resolveProp = (propName) => {
      const attr = getAttr(opening, propName)
      const lit = attrLiteral(attr)
      if (lit.present && lit.literal) return { value: lit.value, resolved: 'explicit' }
      if (lit.present && !lit.literal)
        return { value: null, resolved: 'unresolved', expr: attrExprOf(attr) }
      if (spread) return { value: null, resolved: 'unresolved' }
      if (Object.prototype.hasOwnProperty.call(defaults, propName) && defaults[propName] != null) {
        return { value: defaults[propName], resolved: 'default' }
      }
      return { value: null, resolved: 'unresolved' }
    }
    // `disabled`'s own literal/dynamic split, the same reading `resolveProp` already gives
    // `variant`/`size` — a literal `disabled`/`disabled={true}` is real, story-independent
    // knowledge (kept in `disabled` below, unconditionally true); a *dynamic* expression
    // (`FavouriteToggle`'s own `disabled={bounded}`, `Dialog`'s own `disabled={primaryAction.disabled}`)
    // is not resolvable here at all — it carries no story's own args yet — so it is kept as
    // `disabledExpr` for a later pass to evaluate against each of this component's own stories
    // (T594's row 8 sweep, item 1: this used to be silently dropped, reading a confirmed `'none'`
    // no comparison had actually made). `loadingExpr` is the same reading of a `loading` attribute,
    // captured only for the primitives whose own rendering folds `loading` into `disabled` too.
    const disabledAttr = getAttr(opening, 'disabled')
    const disabledLit = attrLiteral(disabledAttr)
    const loadingAttr = PRIMITIVES_WHERE_LOADING_DISABLES.has(tagName)
      ? getAttr(opening, 'loading')
      : undefined
    const loadingLit = attrLiteral(loadingAttr)
    found.push({
      primitive: tagName,
      file: filePath,
      line: lineOf(sourceFile, node),
      variant:
        defaults.variant != null || getAttr(opening, 'variant')
          ? resolveProp('variant')
          : { value: null, resolved: 'n/a' },
      size:
        defaults.size != null || getAttr(opening, 'size')
          ? resolveProp('size')
          : { value: null, resolved: 'n/a' },
      disabled:
        (disabledLit.literal && disabledLit.value === true) ||
        (loadingLit.literal && loadingLit.value === true),
      disabledExpr: disabledLit.present && !disabledLit.literal ? attrExprOf(disabledAttr) : null,
      loadingExpr: loadingLit.present && !loadingLit.literal ? attrExprOf(loadingAttr) : null,
      // Every local `const` in scope at this exact JSX position (`FavouriteToggle`'s own `const
      // bounded = atLimit && !favourited`) — `disabledExpr`/`loadingExpr` above are frequently a
      // bare reference to one of these, never resolvable against a story's own args without it.
      localConsts: context.localConsts,
      // `Button` renders `<a href>` rather than `<button>` once `href` is supplied (its own
      // `index.tsx`) — its own implied role follows that, not a fixed per-primitive constant
      // (T594's REJECT on #80, item 5).
      hasHref: Boolean(getAttr(opening, 'href')),
      text: literalTextOf(node) || ariaLabelText(opening),
      childrenExpr: !literalTextOf(node) && ts.isJsxElement(node) ? node.children : null,
      ariaHidden: isAriaHidden(opening),
      isHelper: context.fnName != null,
      isInsideIteration: context.inIteration,
      guards: effectiveGuards,
      fnName: context.fnName,
    })
  })
  return found
}

// --- Static evaluation: resolves a dynamic expression (a guard's condition, a `variant`/`size`
// attribute, a `{label}` child) against a scope built from a story's own args and a component's own
// prop defaults — the mechanism `Dialog`'s `{ primaryAction: { label: 'Turn it off' } }` and
// `FavouriteToggle`'s `if (!authenticated) return <SignedOutControl />` both need, once args are
// substituted in. Never a full interpreter: only literals, `??`/`&&`/`||`, `!`, `===`/`!==`,
// property access, ternaries and object/array literals are evaluated; anything else (a function
// call, a value truly outside the story's own data) stays unresolved rather than guessed. -------

// A sentinel distinguishing "resolved to `undefined`" from "could not be resolved at all" inside a
// nested object value, so a later property access on an unresolved nested value stays unresolved
// too instead of silently reading as `undefined`.
const UNRESOLVED_VALUE = Symbol('unresolved')
const UNRESOLVED = { resolved: false, value: undefined }

export function evaluateExpr(node, scope) {
  if (!node) return UNRESOLVED
  if (ts.isParenthesizedExpression(node)) return evaluateExpr(node.expression, scope)
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    return { resolved: true, value: node.text }
  }
  if (ts.isNumericLiteral(node)) return { resolved: true, value: Number(node.text) }
  if (node.kind === ts.SyntaxKind.TrueKeyword) return { resolved: true, value: true }
  if (node.kind === ts.SyntaxKind.FalseKeyword) return { resolved: true, value: false }
  if (node.kind === ts.SyntaxKind.NullKeyword) return { resolved: true, value: null }
  if (ts.isIdentifier(node)) {
    if (node.text === 'undefined') return { resolved: true, value: undefined }
    if (scope.has(node.text)) return scope.get(node.text)
    return UNRESOLVED
  }
  if (ts.isPropertyAccessExpression(node)) {
    const obj = evaluateExpr(node.expression, scope)
    if (!obj.resolved) return UNRESOLVED
    if (obj.value == null || typeof obj.value !== 'object')
      return { resolved: true, value: undefined }
    const val = obj.value[node.name.text]
    if (val === UNRESOLVED_VALUE) return UNRESOLVED
    return { resolved: true, value: val }
  }
  if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.ExclamationToken) {
    const v = evaluateExpr(node.operand, scope)
    return v.resolved ? { resolved: true, value: !v.value } : UNRESOLVED
  }
  if (
    ts.isPrefixUnaryExpression(node) &&
    node.operator === ts.SyntaxKind.MinusToken &&
    ts.isNumericLiteral(node.operand)
  ) {
    return { resolved: true, value: -Number(node.operand.text) }
  }
  if (ts.isBinaryExpression(node)) {
    const op = node.operatorToken.kind
    if (op === ts.SyntaxKind.QuestionQuestionToken) {
      const l = evaluateExpr(node.left, scope)
      if (l.resolved && l.value != null) return l
      if (l.resolved) return evaluateExpr(node.right, scope)
      return UNRESOLVED
    }
    if (op === ts.SyntaxKind.AmpersandAmpersandToken) {
      const l = evaluateExpr(node.left, scope)
      if (!l.resolved) return UNRESOLVED
      return l.value ? evaluateExpr(node.right, scope) : l
    }
    if (op === ts.SyntaxKind.BarBarToken) {
      const l = evaluateExpr(node.left, scope)
      if (!l.resolved) return UNRESOLVED
      return l.value ? l : evaluateExpr(node.right, scope)
    }
    if (op === ts.SyntaxKind.EqualsEqualsEqualsToken || op === ts.SyntaxKind.EqualsEqualsToken) {
      const l = evaluateExpr(node.left, scope)
      const r = evaluateExpr(node.right, scope)
      return l.resolved && r.resolved ? { resolved: true, value: l.value === r.value } : UNRESOLVED
    }
    if (
      op === ts.SyntaxKind.ExclamationEqualsEqualsToken ||
      op === ts.SyntaxKind.ExclamationEqualsToken
    ) {
      const l = evaluateExpr(node.left, scope)
      const r = evaluateExpr(node.right, scope)
      return l.resolved && r.resolved ? { resolved: true, value: l.value !== r.value } : UNRESOLVED
    }
    return UNRESOLVED
  }
  if (ts.isConditionalExpression(node)) {
    const cond = evaluateExpr(node.condition, scope)
    if (!cond.resolved) return UNRESOLVED
    return evaluateExpr(cond.value ? node.whenTrue : node.whenFalse, scope)
  }
  if (ts.isObjectLiteralExpression(node)) {
    const obj = {}
    for (const prop of node.properties) {
      if (ts.isPropertyAssignment(prop)) {
        const key = prop.name.getText()
        const v = evaluateExpr(prop.initializer, scope)
        obj[key] = v.resolved ? v.value : UNRESOLVED_VALUE
      } else if (ts.isShorthandPropertyAssignment(prop)) {
        const key = prop.name.text
        const v = scope.has(key) ? scope.get(key) : UNRESOLVED
        obj[key] = v.resolved ? v.value : UNRESOLVED_VALUE
      }
      // A spread property is not resolved into `obj` — best effort, never guessed.
    }
    return { resolved: true, value: obj }
  }
  if (ts.isArrayLiteralExpression(node)) {
    return {
      resolved: true,
      value: node.elements.map((el) => {
        const v = evaluateExpr(el, scope)
        return v.resolved ? v.value : UNRESOLVED_VALUE
      }),
    }
  }
  if (ts.isJsxExpression(node) && node.expression) return evaluateExpr(node.expression, scope)
  return UNRESOLVED
}

// Every top-level `const NAME = <expr>`, evaluated in declaration order against the growing scope
// so a later const may reference an earlier one — the general-valued sibling of
// `buildConstStringMap`, used to resolve a story's own shorthand `args` property
// (`SiteHeader.stories.tsx`'s `args: { items, currentPath }`) back to its declaration's real value.
export function buildFileValueScope(sourceFile) {
  const scope = new Map()
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (ts.isIdentifier(decl.name) && decl.initializer) {
        scope.set(decl.name.text, evaluateExpr(decl.initializer, scope))
      }
    }
  }
  return scope
}

// A component's own destructured prop names, each mapped to its default-value expression (or
// `null` when the prop has none) — read from the same parameter-destructuring or in-body
// `const { ... } = props` shape `findVariantSizeDefaults` already reads two ways.
export function getComponentPropDefaults(sourceFile, componentName) {
  const result = new Map()
  function visit(node) {
    if (
      ts.isObjectBindingPattern(node) &&
      (ts.isParameter(node.parent) || ts.isVariableDeclaration(node.parent))
    ) {
      for (const el of node.elements) {
        if (!ts.isBindingElement(el) || !ts.isIdentifier(el.name)) continue
        const propName = el.propertyName ? el.propertyName.getText() : el.name.text
        result.set(propName, el.initializer ?? null)
      }
    }
    ts.forEachChild(node, visit)
  }
  for (const statement of sourceFile.statements) {
    if (
      ts.isFunctionDeclaration(statement) &&
      statement.name?.text === componentName &&
      statement.body
    ) {
      visit(statement)
    }
  }
  return result
}

// The merged `{ ...meta.args, ...story.args }` object, evaluated with `fileScope` as its own base
// scope (so a shorthand property resolves against a top-level const) — Storybook's own merge order,
// the story's own value winning.
export function evaluateMergedArgsObject(metaObj, storyObj, fileScope) {
  const metaArgs = getProp(metaObj, 'args')
  const storyArgs = getProp(storyObj, 'args')
  const metaVal = evaluateExpr(metaArgs, fileScope)
  const storyVal = evaluateExpr(storyArgs, fileScope)
  return {
    resolved: true,
    value: {
      ...(metaVal.resolved ? metaVal.value : {}),
      ...(storyVal.resolved ? storyVal.value : {}),
    },
  }
}

// The scope a candidate's own guards/attribute expressions are evaluated against for one specific
// story: the component's own prop defaults, overridden by whichever of those same names the
// story's merged args actually supplies.
export function buildStoryPropsScope(componentPropDefaults, mergedArgsObject, fileScope) {
  const scope = new Map(fileScope)
  for (const [name, defaultExpr] of componentPropDefaults) {
    scope.set(name, defaultExpr ? evaluateExpr(defaultExpr, fileScope) : UNRESOLVED)
  }
  if (mergedArgsObject.resolved) {
    for (const [key, value] of Object.entries(mergedArgsObject.value)) {
      scope.set(key, value === UNRESOLVED_VALUE ? UNRESOLVED : { resolved: true, value })
    }
  }
  return scope
}

// Evaluates every guard a candidate carries against `scope` — `'reached'` (every guard held),
// `'unreached'` (at least one guard's condition resolved to the *wrong* boolean — a different,
// sibling branch is what this story actually renders) or `'unresolved'` (a guard's own condition
// could not be evaluated from this story's own data at all).
export function evaluateGuards(guards, scope) {
  for (const guard of guards) {
    const result = evaluateExpr(guard.expr, scope)
    if (!result.resolved) return 'unresolved'
    if (Boolean(result.value) !== guard.truthy) return 'unreached'
  }
  return 'reached'
}

// --- Story parsing: exported story objects, args, visualForceState, play()-focus ----------------

export function findExportedStoryObjects(sourceFile) {
  let defaultExportName = null
  for (const statement of sourceFile.statements) {
    if (
      ts.isExportAssignment(statement) &&
      !statement.isExportEquals &&
      ts.isIdentifier(statement.expression)
    ) {
      defaultExportName = statement.expression.text
    }
  }
  const stories = []
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    const isExported = statement.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
    if (!isExported) continue
    for (const decl of statement.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || decl.name.text === defaultExportName) continue
      let init = decl.initializer
      if (init && ts.isSatisfiesExpression(init)) init = init.expression
      if (init && ts.isAsExpression(init)) init = init.expression
      if (init && ts.isObjectLiteralExpression(init)) {
        stories.push({ exportName: decl.name.text, node: init })
      }
    }
  }
  return stories
}

export function findMeta(sourceFile) {
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (
        ts.isIdentifier(decl.name) &&
        decl.initializer &&
        ts.isObjectLiteralExpression(decl.initializer)
      ) {
        const hasComponent = decl.initializer.properties.some(
          (p) => ts.isPropertyAssignment(p) && p.name.getText() === 'component',
        )
        if (hasComponent) return decl.initializer
      }
    }
  }
  return null
}

function getProp(objLiteral, name) {
  if (!objLiteral) return undefined
  for (const prop of objLiteral.properties) {
    if (ts.isPropertyAssignment(prop) && prop.name.getText() === name) return prop.initializer
    if (ts.isShorthandPropertyAssignment(prop) && prop.name.getText() === name) return prop.name
  }
  return undefined
}

function literalOf(expr) {
  if (!expr) return { present: false }
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) {
    return { present: true, literal: true, value: expr.text }
  }
  if (ts.isNumericLiteral(expr)) return { present: true, literal: true, value: Number(expr.text) }
  if (expr.kind === ts.SyntaxKind.TrueKeyword) return { present: true, literal: true, value: true }
  if (expr.kind === ts.SyntaxKind.FalseKeyword)
    return { present: true, literal: true, value: false }
  if (ts.isRegularExpressionLiteral(expr)) return { present: true, literal: true, value: expr.text }
  return { present: true, literal: false }
}

export function metaComponentName(metaObj) {
  const expr = getProp(metaObj, 'component')
  return expr && ts.isIdentifier(expr) ? expr.text : null
}

export function resolveStoryAxisValues(metaObj, storyObj, defaults) {
  const metaArgs = getProp(metaObj, 'args')
  const storyArgs = getProp(storyObj, 'args')
  const resolve = (propName) => {
    const storyLit = literalOf(getProp(storyArgs, propName))
    if (storyLit.present)
      return storyLit.literal
        ? { value: storyLit.value, resolved: 'explicit' }
        : { value: null, resolved: 'unresolved' }
    const metaLit = literalOf(getProp(metaArgs, propName))
    if (metaLit.present)
      return metaLit.literal
        ? { value: metaLit.value, resolved: 'explicit' }
        : { value: null, resolved: 'unresolved' }
    if (Object.prototype.hasOwnProperty.call(defaults, propName) && defaults[propName] != null) {
      return { value: defaults[propName], resolved: 'default' }
    }
    return { value: null, resolved: 'unresolved' }
  }
  const result = {}
  if (defaults.variant != null || getProp(storyArgs, 'variant') || getProp(metaArgs, 'variant')) {
    result.variant = resolve('variant')
  }
  if (defaults.size != null || getProp(storyArgs, 'size') || getProp(metaArgs, 'size')) {
    result.size = resolve('size')
  }
  return result
}

// A primitive's *own* story file can render its own JSX literally inside a `render:` function
// instead of composing purely from `args` (`Button.stories.tsx`'s `Disabled`, `AllVariants`,
// `RealisticPageActions`) — `resolveStoryAxisValues` above only ever reads `args`, so every one of
// those stories silently fell back to the primitive's *default* row (T594's REJECT on #80, item
// 4). This parses `render`'s own JSX exactly as `findPrimitiveInstances` parses a real call site,
// and returns one entry per instance found (`AllVariants` renders four) — `null`, never `[]`, for
// a story with no `render` or no matching JSX in it, so the caller can tell "parse this" from
// "nothing to parse, fall back to the args-only axis".
export function findOwnStoryRenderInstances(storyObj, primitiveName, defaults, metaObj = null) {
  const renderExpr = getProp(storyObj, 'render')
  if (!renderExpr) return null
  let body = renderExpr
  if (ts.isArrowFunction(renderExpr) || ts.isFunctionExpression(renderExpr)) body = renderExpr.body
  const found = []
  // A spread (`<Field {...args}>`) carries a prop's value through the story's own `args`, never a
  // literal JSX attribute — falling straight to the primitive's *default* whenever a spread is
  // present, as this function used to, silently drops every story whose custom `render` overrides
  // `variant`/`size` only through `args` (`Field.stories.tsx`'s own `SizeLg`, `size: 'lg'` in
  // `args`, no literal `size=` attribute anywhere in its `render`). Resolved lazily, at most once
  // per story, through the same args-reading path `resolveStoryAxisValues` already uses for the
  // no-`render` case, so a spread's value is read from the data that actually supplies it rather
  // than guessed from the default.
  let argsAxis = null
  function resolveViaArgs(propName) {
    if (!metaObj) return null
    if (argsAxis === null) argsAxis = resolveStoryAxisValues(metaObj, storyObj, defaults)
    return argsAxis[propName] ?? null
  }
  function resolveProp(opening, propName) {
    const attr = getAttr(opening, propName)
    const lit = attrLiteral(attr)
    if (lit.present && lit.literal) return { value: lit.value, resolved: 'explicit' }
    if (lit.present && !lit.literal) return { value: null, resolved: 'unresolved' }
    if (hasSpreadAttr(opening)) {
      const viaArgs = resolveViaArgs(propName)
      if (viaArgs) return viaArgs
      return { value: null, resolved: 'unresolved' }
    }
    if (Object.prototype.hasOwnProperty.call(defaults, propName) && defaults[propName] != null) {
      return { value: defaults[propName], resolved: 'default' }
    }
    return { value: null, resolved: 'unresolved' }
  }
  function visit(node) {
    if (isJsxTag(node) && tagNameOf(node) === primitiveName) {
      const opening = openingOf(node)
      found.push({
        variant:
          defaults.variant != null || getAttr(opening, 'variant')
            ? resolveProp(opening, 'variant')
            : { value: null, resolved: 'n/a' },
        size:
          defaults.size != null || getAttr(opening, 'size')
            ? resolveProp(opening, 'size')
            : { value: null, resolved: 'n/a' },
        disabled: attrLiteral(getAttr(opening, 'disabled')).value === true,
        text: literalTextOf(node),
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(body)
  return found.length > 0 ? found : null
}

// A story's own merged `args` (meta's default `args` plus the story's own) can render a primitive
// *instance's own sub-item* disabled without any literal `disabled` attribute on the primitive's
// own JSX at all — `Menu.stories.tsx`'s `ActionsWithDisabledItem`/`LoadingItem`, whose `items`
// array carries `disabled: true` on one entry, rendered through `MenuItemRow`, a local element
// this static pass does not trace back to one specific array element (T594's REJECT on #80, item
// 4). Positive at the *story* grain: "this story's own args, however nested, admit a `disabled:
// true`" — never at the specific-item grain, which this pass cannot resolve without a fuller
// object-shape trace than the fixed set of literals the rest of this file already stops short of.
export function argsObjectHasDisabledTrue(...exprs) {
  function visit(node) {
    if (!node) return false
    if (ts.isObjectLiteralExpression(node)) {
      for (const prop of node.properties) {
        if (!ts.isPropertyAssignment(prop)) continue
        if (prop.name.getText() === 'disabled') {
          const lit = literalOf(prop.initializer)
          if (lit.present && lit.literal && lit.value === true) return true
        }
        if (visit(prop.initializer)) return true
      }
      return false
    }
    if (ts.isArrayLiteralExpression(node)) return node.elements.some(visit)
    if (ts.isJsxExpression(node) && node.expression) return visit(node.expression)
    return false
  }
  return exprs.some(visit)
}

export function extractVisualForceState(storyObj) {
  const params = getProp(storyObj, 'parameters')
  const forced = getProp(params, 'visualForceState')
  if (!forced || !ts.isObjectLiteralExpression(forced)) return null
  const state = literalOf(getProp(forced, 'state'))
  if (!state.present || !state.literal) return null
  const role = literalOf(getProp(forced, 'role'))
  const name = literalOf(getProp(forced, 'name'))
  const selector = literalOf(getProp(forced, 'selector'))
  const nth = literalOf(getProp(forced, 'nth'))
  return {
    state: state.value,
    role: role.present && role.literal ? role.value : null,
    name: name.present && name.literal ? name.value : null,
    selector: selector.present && selector.literal ? selector.value : null,
    nth: nth.present && nth.literal ? nth.value : null,
  }
}

// Every string literal reachable at any depth inside an object/array literal — a story's own `args`
// merged with its meta's `args`, read this way so a nested literal (`primaryAction: { label: 'Turn
// it off' }`, an `items` array of `{ label: '...' }` objects) supplies a name a `visualForceState`
// can match even when the JSX itself only ever renders `{primaryAction.label}` or `{item.label}` —
// never resolvable from the JSX alone.
// `constNodeMap` resolves a bare identifier (a shorthand `{ items, currentPath }` referencing a
// top-level `const items = [...]` declared elsewhere in the same story file, `SiteHeader.stories.tsx`'s
// own shape) back to its own initializer — `seen` stops a self-referential or mutually-referential
// pair from recursing forever, which no real fixture in this tree does but a future one might.
export function extractStringLiteralsDeep(
  node,
  out = new Set(),
  constNodeMap = null,
  seen = new Set(),
) {
  if (!node) return out
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    out.add(node.text)
    return out
  }
  if (ts.isObjectLiteralExpression(node)) {
    for (const prop of node.properties) {
      if (ts.isPropertyAssignment(prop)) {
        extractStringLiteralsDeep(prop.initializer, out, constNodeMap, seen)
      } else if (ts.isShorthandPropertyAssignment(prop) && constNodeMap) {
        const name = prop.name.text
        if (!seen.has(name) && constNodeMap.has(name)) {
          seen.add(name)
          extractStringLiteralsDeep(constNodeMap.get(name), out, constNodeMap, seen)
        }
      }
    }
    return out
  }
  if (ts.isArrayLiteralExpression(node)) {
    for (const el of node.elements) extractStringLiteralsDeep(el, out, constNodeMap, seen)
    return out
  }
  if (ts.isJsxExpression(node) && node.expression) {
    return extractStringLiteralsDeep(node.expression, out, constNodeMap, seen)
  }
  if (
    ts.isIdentifier(node) &&
    constNodeMap &&
    constNodeMap.has(node.text) &&
    !seen.has(node.text)
  ) {
    seen.add(node.text)
    return extractStringLiteralsDeep(constNodeMap.get(node.text), out, constNodeMap, seen)
  }
  return out
}

// Every top-level `const NAME = <expr>` in a file, unresolved — the general-purpose sibling of
// `buildConstStringMap` (which only keeps the ones that resolve to a class string). Used to chase a
// story's own shorthand `args` property back to its declaration.
export function buildTopLevelConstNodeMap(sourceFile) {
  const map = new Map()
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (ts.isIdentifier(decl.name) && decl.initializer) {
        map.set(decl.name.text, decl.initializer)
      }
    }
  }
  return map
}

export function storyArgsStringLiterals(metaObj, storyObj, constNodeMap = null) {
  const set = new Set()
  extractStringLiteralsDeep(getProp(metaObj, 'args'), set, constNodeMap)
  extractStringLiteralsDeep(getProp(storyObj, 'args'), set, constNodeMap)
  return set
}

function resolvePlayBody(storyObj, sourceFile) {
  const playExpr = getProp(storyObj, 'play')
  if (!playExpr) return null
  if (ts.isArrowFunction(playExpr) || ts.isFunctionExpression(playExpr)) return playExpr.body
  if (ts.isIdentifier(playExpr)) {
    let found = null
    for (const statement of sourceFile.statements) {
      if (
        ts.isFunctionDeclaration(statement) &&
        statement.name?.text === playExpr.text &&
        statement.body
      ) {
        found = statement.body
      }
      if (ts.isVariableStatement(statement)) {
        for (const decl of statement.declarationList.declarations) {
          if (
            ts.isIdentifier(decl.name) &&
            decl.name.text === playExpr.text &&
            decl.initializer &&
            (ts.isArrowFunction(decl.initializer) || ts.isFunctionExpression(decl.initializer))
          ) {
            found = decl.initializer.body
          }
        }
      }
    }
    return found
  }
  return null
}

// The explicit JSX props a story's own `render: () => <ComponentName prop={x} />` passes to the
// component under test — `MatchRow.stories.tsx`'s `render: () => <MatchRow match={base} />`
// shape, none of it visible to `resolveStoryAxisValues`/`buildStoryPropsScope`, which only ever
// read `args`. Only the *first* JSX element named `componentName` found in `render`'s own body is
// read — every real story in this tree renders its subject exactly once.
export function findRenderJsxProps(storyObj, componentName) {
  const renderExpr = getProp(storyObj, 'render')
  if (!renderExpr) return new Map()
  let body = renderExpr
  if (ts.isArrowFunction(renderExpr) || ts.isFunctionExpression(renderExpr)) body = renderExpr.body
  let found = null
  function visit(node) {
    if (found) return
    if (isJsxTag(node) && tagNameOf(node) === componentName) {
      found = node
      return
    }
    ts.forEachChild(node, visit)
  }
  visit(body)
  const props = new Map()
  if (!found) return props
  const opening = openingOf(found)
  for (const attr of opening.attributes.properties) {
    if (!ts.isJsxAttribute(attr)) continue
    let expr = attr.initializer
    if (expr && ts.isJsxExpression(expr)) expr = expr.expression
    if (expr) props.set(attr.name.getText(), expr)
  }
  return props
}

// A `visualForceState: { selector }` (no `role`) targets a specific CSS selector directly rather
// than an accessible role — `MatchRow`/`FavouritesList`/`PlayerResultRow`'s own row link
// (`a[href="/matches/1001"]`). Only the exact `tag[attr="literal"]` shape every real selector in
// this tree uses is parsed; anything else is `null`, resolved by the caller as unresolved rather
// than guessed.
export function parseSelector(selector) {
  const m = /^([a-zA-Z][a-zA-Z0-9]*)\[([a-zA-Z-]+)="([^"]*)"\]$/.exec(selector)
  if (!m) return null
  return { tag: m[1], attr: m[2], value: m[3] }
}

// Every string value reachable inside a story's own resolved scope (`buildStoryPropsScope`'s
// output, extended with a `render`'s own explicit props) — the general-valued sibling of
// `storyArgsStringLiterals`, which only ever reads `args`. `Table`'s own `caption="Recent matches"`
// carries no `args` at all, so a `visualForceState`'s `name` needs this to be found at all.
export function collectScopeStringLiterals(scope) {
  const out = new Set()
  function visit(value) {
    if (typeof value === 'string') out.add(value)
    else if (Array.isArray(value)) value.forEach(visit)
    else if (value && typeof value === 'object') {
      for (const v of Object.values(value)) visit(v)
    }
  }
  for (const entry of scope.values()) {
    if (entry && entry.resolved) visit(entry.value)
  }
  return out
}

// `'match'`/`'reject'`/`'ambiguous'`, the same three-way contract as `resolveNameMatch` — resolves
// `candidate`'s own value for `selector`'s attribute either from a literal in its own JSX or, once
// `scope` supplies it (a story's own render-passed props, `MatchRow`'s `match={base}` resolved
// through `evaluateExpr`), from a dynamic expression (`match.href`). A tag mismatch is a positive
// `'reject'`; an attribute this pass cannot read at all, from either source, is `'ambiguous'` —
// never a silent `'none'` (T594's REJECT on #80, item 1).
export function resolveSelectorMatch({ selector, candidate, pool: _pool, scope }) {
  const parsed = parseSelector(selector)
  if (!parsed) return 'ambiguous'
  if (candidate.tag !== parsed.tag) return 'reject'
  const attrInfo = candidate.attrExprs?.get(parsed.attr)
  if (!attrInfo) return 'ambiguous'
  let resolved
  if (attrInfo.literal) {
    resolved = { resolved: true, value: attrInfo.value }
  } else if (attrInfo.expr && scope) {
    resolved = evaluateExpr(attrInfo.expr, scope)
    // A dynamic attribute referencing the candidate's own iteration variable (`entry.href`,
    // `FavouritesList`'s row link) is not in `scope` directly — only its own array source is
    // (`entries`). A story whose merged args resolve that array to exactly one element removes the
    // only real ambiguity (which element the story renders); more than one stays unresolved rather
    // than guessed at an index this static pass has no way to pick.
    if (!resolved.resolved && candidate.iterationVar && candidate.iterationArrayExpr) {
      const arr = evaluateExpr(candidate.iterationArrayExpr, scope)
      if (arr.resolved && Array.isArray(arr.value) && arr.value.length === 1) {
        const item = arr.value[0]
        const extendedScope = new Map(scope)
        extendedScope.set(candidate.iterationVar, {
          resolved: item !== UNRESOLVED_VALUE,
          value: item === UNRESOLVED_VALUE ? undefined : item,
        })
        resolved = evaluateExpr(attrInfo.expr, extendedScope)
      }
    }
  } else {
    resolved = { resolved: false }
  }
  if (!resolved.resolved) return 'ambiguous'
  return resolved.value === parsed.value ? 'match' : 'reject'
}

function focusCallShape(expr) {
  if (!expr) return null
  let call = expr
  if (ts.isAwaitExpression(call)) call = call.expression
  if (!ts.isCallExpression(call)) return null
  const callee = call.expression
  if (ts.isPropertyAccessExpression(callee) && callee.name.text === 'focus') {
    return { kind: 'focus', targetExpr: callee.expression }
  }
  if (
    ts.isPropertyAccessExpression(callee) &&
    callee.name.text === 'toHaveFocus' &&
    ts.isCallExpression(callee.expression) &&
    ts.isIdentifier(callee.expression.expression) &&
    callee.expression.expression.text === 'expect'
  ) {
    return { kind: 'toHaveFocus', targetExpr: callee.expression.arguments[0] }
  }
  return null
}

function roleCallTarget(expr) {
  let call = expr
  if (call && ts.isAwaitExpression(call)) call = call.expression
  if (!call || !ts.isCallExpression(call)) return null
  const callee = call.expression
  if (!ts.isPropertyAccessExpression(callee)) return null
  if (callee.name.text !== 'getByRole' && callee.name.text !== 'findByRole') return null
  const roleLit = literalOf(call.arguments[0])
  const opts = call.arguments[1]
  const nameLit = literalOf(
    getProp(opts && ts.isObjectLiteralExpression(opts) ? opts : null, 'name'),
  )
  return {
    role: roleLit.present && roleLit.literal ? roleLit.value : 'unresolved',
    name: nameLit.present && nameLit.literal ? nameLit.value : null,
  }
}

export function findPlayFocusTarget(body) {
  if (!body) return null
  const flat = ts.isBlock(body) ? body.statements : []
  const varMap = new Map()
  let last = null
  function consider(expr) {
    const shape = focusCallShape(expr)
    if (!shape) return
    let target = shape.targetExpr
    let resolved = roleCallTarget(target)
    if (!resolved && target && ts.isIdentifier(target) && varMap.has(target.text)) {
      resolved = varMap.get(target.text)
    }
    last = resolved ?? { role: 'unresolved', name: null, raw: target?.getText?.() ?? '<expr>' }
  }
  for (const statement of flat) {
    if (ts.isVariableStatement(statement)) {
      for (const decl of statement.declarationList.declarations) {
        if (ts.isIdentifier(decl.name) && decl.initializer) {
          const roleTarget = roleCallTarget(decl.initializer)
          if (roleTarget) varMap.set(decl.name.text, roleTarget)
        }
      }
    }
    if (ts.isExpressionStatement(statement)) consider(statement.expression)
  }
  return last
}

// --- Shared candidate-resolution: does `forced`/`playFocus` target `candidate` among `pool`? ------
//
// Returns `'match'` (this candidate, and only this one, is the target), `'reject'` (a *different*
// candidate is clearly the target, or the force-state's role does not even apply here — never an
// "attempt" against this candidate) or `'ambiguous'` (the state genuinely could not be resolved to
// one candidate — printed as `unresolved`, never silently guessed and never silently dropped as
// `none`). `pool` is every candidate in the component sharing the same implied role as `candidate`
// (aria-hidden ones already excluded by the caller, mirroring Playwright's own `getByRole`).
export function resolveNameMatch({ candidate, pool, name, nth, argsLiterals }) {
  if (name) {
    // Every pool member whose own text literally carries the name, not just this candidate's own
    // — checked before deciding anything, so two candidates that both carry it are caught as one
    // ambiguity rather than each independently returning `'match'` (T594's REJECT on #80, item 5:
    // `resolveComposedStoryMatches`'s own caller took whichever of the two a plain `for` loop
    // visited last, silently crediting one frame to both elements — zero live occurrences today,
    // the one ambiguity shape B1's own fixture sweep never covers).
    const directTextMatches = pool.filter((c) => c.text && c.text.includes(name))
    if (directTextMatches.length > 1) return 'ambiguous'
    if (directTextMatches.length === 1)
      return directTextMatches[0] === candidate ? 'match' : 'reject'
    if (argsLiterals) {
      let inArgs = false
      for (const lit of argsLiterals) {
        if (lit.includes(name)) {
          inArgs = true
          break
        }
      }
      if (inArgs) {
        // The name is real (it's in this story's own data) but no candidate's JSX carries it
        // literally. A sole candidate for this role needs no further disambiguation (`Menu`'s
        // footer item, the only `role="menuitem"` element outside `MenuItemRow`'s own dynamic
        // role, matched against `footerItem: { label: 'Link another Steam account' }`); with more
        // than one, prefer a candidate rendered from a `.map()`/`.flatMap()` over a literal array
        // (`NavItem`, one of several `items`), the shape a repeated, data-driven label takes — a
        // helper function invoked once by name (`InlineLink`) is not that shape.
        if (pool.length === 1) return 'match'
        const iterationCandidates = pool.filter((c) => c.isInsideIteration)
        if (iterationCandidates.length === 1) {
          return iterationCandidates[0] === candidate ? 'match' : 'reject'
        }
        return 'ambiguous'
      }
    }
    // Neither this candidate's own JSX text, another candidate's JSX text, nor this story's own
    // args positively account for `name` — `'none'` must be positive knowledge (T594's amendment,
    // the orchestrator's REJECT on #80), so an unaccounted-for name is `'ambiguous'` (rendered
    // `unresolved: <reason>`), never silently `'reject'`ed into a false `'none'`. `'reject'` is
    // reserved for the case a *different* candidate positively carries the name.
    return 'ambiguous'
  }
  if (nth != null) {
    // The candidate itself is a reusable helper's declaration site (`PrivacyNotice`'s own
    // `InlineLink`, invoked from several call sites this static pass does not enumerate) — its
    // real render position relative to the orderable candidates below is unknown, so this pass can
    // neither place it at `nth` nor rule it out. `'reject'` would be a confirmed exclusion this
    // pass never actually established (T594 part A); `'ambiguous'` is what it actually knows.
    if (candidate.isHelper) return 'ambiguous'
    // A real DOM-render-order position. Only the candidates whose own recorded line *is* a render
    // position (not a reusable helper's declaration site, invoked from elsewhere this static pass
    // cannot enumerate) can be ordered this way.
    const orderable = pool.filter((c) => !c.isHelper).sort((a, b) => a.line - b.line)
    if (orderable.length > nth) {
      return orderable[nth] === candidate ? 'match' : 'reject'
    }
    return 'ambiguous'
  }
  // No name, no nth: safe only when this candidate is the pool's sole member.
  return pool.length === 1 ? 'match' : 'ambiguous'
}

// --- Directory / file plumbing --------------------------------------------------------------

const TIER_SEGMENTS = ['primitives', 'composites', 'screens']

function walkAllTsxFiles(rootSrcDir) {
  const files = []
  function walk(dir) {
    for (const entry of readdirSync(dir)) {
      const full = path.join(dir, entry)
      const st = statSync(full)
      if (st.isDirectory()) walk(full)
      else if (entry.endsWith('.tsx') && !entry.endsWith('.test.tsx')) files.push(full)
    }
  }
  for (const segment of TIER_SEGMENTS) {
    const segmentDir = path.join(rootSrcDir, segment)
    try {
      walk(segmentDir)
    } catch {
      // segment absent — nothing to walk
    }
  }
  return files.sort()
}

function componentKeyForFile(rootSrcDir, filePath) {
  const rel = path.relative(rootSrcDir, filePath).split(path.sep)
  return `${rel[0]}/${rel[1]}`
}

function relPath(filePath) {
  return path.relative(rootDir, filePath)
}

// --- Orchestration -------------------------------------------------------------------------

export function computeStateCoverage({ componentDirs, filesByPath }) {
  const allFiles = [...filesByPath.keys()].sort()
  const sourceFiles = new Map(allFiles.map((f) => [f, parseTsx(f, filesByPath.get(f))]))

  const defaultsByPrimitive = {}
  for (const name of PRIMITIVE_NAMES) {
    const dir = componentDirs.find((d) => d.name === name)
    if (!dir) continue
    const indexPath = allFiles.find(
      (f) =>
        componentKeyForFile(srcDir, f) === `${dir.segment}/${dir.name}` &&
        path.basename(f) === 'index.tsx',
    )
    if (!indexPath) continue
    defaultsByPrimitive[name] = findVariantSizeDefaults(sourceFiles.get(indexPath))
  }
  if (defaultsByPrimitive.Menu) defaultsByPrimitive.Menu = { variant: null }
  else if (componentDirs.some((d) => d.name === 'Menu'))
    defaultsByPrimitive.Menu = { variant: null }

  // Every component's own prop defaults and file-level const scope, read once from its own
  // `index.tsx` — the static-evaluation half of resolving a dynamic `variant`/`size`/guard
  // (`Dialog`'s `primaryAction.variant ?? 'destructive'`, `FavouriteToggle`'s `!authenticated`)
  // against a specific story's own args later.
  const componentPropDefaultsByKey = new Map()
  const componentFileScopeByKey = new Map()
  for (const { segment, name } of componentDirs) {
    const key = `${segment}/${name}`
    const indexPath = allFiles.find(
      (f) => componentKeyForFile(srcDir, f) === key && path.basename(f) === 'index.tsx',
    )
    if (!indexPath) continue
    const indexSourceFile = sourceFiles.get(indexPath)
    componentPropDefaultsByKey.set(key, getComponentPropDefaults(indexSourceFile, name))
    componentFileScopeByKey.set(key, buildFileValueScope(indexSourceFile))
  }

  const localElementsByComponent = new Map()
  const instancesByPrimitive = new Map(PRIMITIVE_NAMES.map((p) => [p, []]))
  const storyStatesByComponent = new Map()
  const pendingComposedMatches = []
  // One entry per story of a *non-primitive-owning* component (composite or screen), forced or
  // not — `resolveDisabledFromStories` needs every one of them, since a story that resolves a
  // `Button`/`Link`/`Field`/`Menu` call site's own `disabled`/`loading` prop true through its own
  // `args` (`FavouriteToggle`'s own `Bounded`, `AddingInFlight`) never sets `visualForceState` at
  // all — only `pendingComposedMatches` above is forced-only, for the role-based state matching
  // that genuinely needs a forced pseudo-class to mean anything.
  const pendingDisabledChecks = []

  for (const filePath of allFiles) {
    const isStory = filePath.endsWith('.stories.tsx')
    const isTest = filePath.endsWith('.test.tsx')
    if (isTest) continue
    const sourceFile = sourceFiles.get(filePath)
    const constMap = buildConstStringMap(sourceFile)
    const componentKey = componentKeyForFile(srcDir, filePath)
    const componentDirName = componentKey.split('/')[1]

    if (!isStory) {
      const helperIterationContext = findHelperInvocationIterationContext(sourceFile)
      const locals = findLocalElements(
        sourceFile,
        relPath(filePath),
        constMap,
        componentDirName,
        helperIterationContext,
      )
      if (locals.length > 0) {
        localElementsByComponent.set(componentKey, [
          ...(localElementsByComponent.get(componentKey) ?? []),
          ...locals,
        ])
      }
    }

    const metaObj = isStory ? findMeta(sourceFile) : null
    const ownPrimitive = metaObj ? metaComponentName(metaObj) : null
    const skip = ownPrimitive && PRIMITIVE_NAMES.includes(ownPrimitive) ? [ownPrimitive] : []
    const helperGuards = !isStory ? findHelperInvocationGuards(sourceFile) : new Map()
    const jsxInstances = findPrimitiveInstances(
      sourceFile,
      relPath(filePath),
      defaultsByPrimitive,
      skip,
      helperGuards,
    )
    for (const inst of jsxInstances) {
      instancesByPrimitive.get(inst.primitive).push({ ...inst, kind: 'jsx', componentKey })
    }

    const storyObjs = isStory ? findExportedStoryObjects(sourceFile) : []
    const storyConstNodeMap = isStory ? buildTopLevelConstNodeMap(sourceFile) : null

    if (isStory) {
      const storyFileScopeForLocals = buildFileValueScope(sourceFile)
      const entries = storyObjs.map(({ exportName, node }) => {
        const forced = extractVisualForceState(node)
        const playBody = resolvePlayBody(node, sourceFile)
        const playFocus = forced ? null : findPlayFocusTarget(playBody)
        const argsHasDisabledTrue = argsObjectHasDisabledTrue(
          getProp(metaObj, 'args'),
          getProp(node, 'args'),
        )
        // The scope a selector-targeted local element's own dynamic attribute (`match.href`) is
        // resolved against for *this* story: the component's own prop defaults, overridden by its
        // merged `args`, further overridden by whatever `render: () => <Component prop={x} />`
        // passes explicitly — the most specific signal a story can give (`MatchRow`'s own
        // `match={base}` shape, invisible to `args` entirely).
        const mergedArgs = evaluateMergedArgsObject(metaObj, node, storyFileScopeForLocals)
        const scope = buildStoryPropsScope(
          componentPropDefaultsByKey.get(componentKey) ?? new Map(),
          mergedArgs,
          componentFileScopeByKey.get(componentKey) ?? storyFileScopeForLocals,
        )
        for (const [propName, exprNode] of findRenderJsxProps(node, componentDirName)) {
          scope.set(propName, evaluateExpr(exprNode, storyFileScopeForLocals))
        }
        // A name a `visualForceState` targets can come from a literal render prop rather than args
        // (`Table`'s own `caption="Recent matches"`, no `args` at all) — folded into the same
        // literal set `resolveNameMatch` already checks, never a separate resolution path.
        const argsLiterals = new Set([
          ...storyArgsStringLiterals(metaObj, node, storyConstNodeMap),
          ...collectScopeStringLiterals(scope),
        ])
        return { exportName, forced, playFocus, argsLiterals, argsHasDisabledTrue, scope }
      })
      storyStatesByComponent.set(componentKey, [
        ...(storyStatesByComponent.get(componentKey) ?? []),
        ...entries,
      ])
    }

    if (isStory && ownPrimitive && PRIMITIVE_NAMES.includes(ownPrimitive)) {
      const defaults = defaultsByPrimitive[ownPrimitive] ?? {}
      for (const { exportName, node } of storyObjs) {
        const forced = extractVisualForceState(node)
        const playBody = resolvePlayBody(node, sourceFile)
        const playFocus = forced ? null : findPlayFocusTarget(playBody)
        // A story's own args admitting a nested `disabled: true` (`Menu.stories.tsx`'s
        // `ActionsWithDisabledItem`/`LoadingItem`) credits this story's row at the story grain —
        // real, positive knowledge ("this story's own data renders something disabled"), never at
        // the specific sub-item grain this static pass does not trace back that far.
        const argsDisabled = argsObjectHasDisabledTrue(
          getProp(metaObj, 'args'),
          getProp(node, 'args'),
        )
        const renderInstances = findOwnStoryRenderInstances(node, ownPrimitive, defaults, metaObj)
        if (renderInstances) {
          for (const ri of renderInstances) {
            instancesByPrimitive.get(ownPrimitive).push({
              primitive: ownPrimitive,
              kind: 'own-story',
              componentKey,
              file: relPath(filePath),
              storyName: exportName,
              variant: ri.variant,
              size: ri.size,
              disabled: ri.disabled || argsDisabled,
              forced,
              playFocus,
            })
          }
        } else {
          const axis = resolveStoryAxisValues(metaObj, node, defaults)
          instancesByPrimitive.get(ownPrimitive).push({
            primitive: ownPrimitive,
            kind: 'own-story',
            componentKey,
            file: relPath(filePath),
            storyName: exportName,
            variant: axis.variant ?? { value: null, resolved: 'n/a' },
            size: axis.size ?? { value: null, resolved: 'n/a' },
            disabled: argsDisabled,
            forced,
            playFocus,
          })
        }
      }
    } else if (isStory) {
      const storyFileScope = buildFileValueScope(sourceFile)
      for (const { exportName, node } of storyObjs) {
        const forced = extractVisualForceState(node)
        const mergedArgs = evaluateMergedArgsObject(metaObj, node, storyFileScope)
        const propsScope = buildStoryPropsScope(
          componentPropDefaultsByKey.get(componentKey) ?? new Map(),
          mergedArgs,
          componentFileScopeByKey.get(componentKey) ?? storyFileScope,
        )
        // A `render: () => <Component prop="literal" />` story (`Table`'s own `caption` shape)
        // carries no `args` at all, so a name a literal render prop supplies (rather than the
        // component's own JSX text) is invisible to `storyArgsStringLiterals` — merged in here from
        // the same render-prop scope local-element selector matching already builds.
        for (const [propName, exprNode] of findRenderJsxProps(node, componentDirName)) {
          propsScope.set(propName, evaluateExpr(exprNode, storyFileScope))
        }
        // Every story — forced or not — can resolve a local `Button`/`Link`/`Field`/`Menu`
        // instance's own dynamic `disabled`/`loading` prop through its own `args` alone
        // (`FavouriteToggle`'s `Bounded`, `AddingInFlight`; `Dialog`'s `PrimaryPending`), so this
        // runs unconditionally rather than gated on `forced` the way role-based matching is below.
        pendingDisabledChecks.push({
          componentKey,
          file: relPath(filePath),
          exportName,
          propsScope,
        })
        if (!forced) continue
        const storyStartLine =
          sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
        const storyEndLine = sourceFile.getLineAndCharacterOfPosition(node.getEnd()).line + 1
        const argsLiterals = new Set([
          ...storyArgsStringLiterals(metaObj, node, storyConstNodeMap),
          ...collectScopeStringLiterals(propsScope),
        ])
        pendingComposedMatches.push({
          componentKey,
          file: relPath(filePath),
          exportName,
          forced,
          storyLineRange: [storyStartLine, storyEndLine],
          argsLiterals,
          propsScope,
        })
      }
    }
  }

  resolveComposedStoryMatches(pendingComposedMatches, instancesByPrimitive)
  resolveDisabledFromStories(pendingDisabledChecks, instancesByPrimitive)

  // One line per component directory, the ones with nothing to report included, so Record 1 can be
  // counted against `story-docs.mjs`'s own directory count (T594's own text) — previously only the
  // 19 of 41 directories that happened to have a local element at all ever appeared (REJECT on #80).
  const localElements = componentDirs
    .map((d) => `${d.segment}/${d.name}`)
    .sort((a, b) => a.localeCompare(b))
    .map((componentKey) => {
      const elements = localElementsByComponent.get(componentKey) ?? []
      const sorted = elements.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line)
      const storyStates = storyStatesByComponent.get(componentKey) ?? []
      const coverageRows = buildElementMatrix(sorted, storyStates)
      return {
        componentKey,
        elements: sorted.map((el, i) => ({
          ...el,
          coveredBy: {
            hover: coverageRows[i].hover,
            focusVisible: coverageRows[i].focusVisible,
            active: coverageRows[i].active,
          },
        })),
      }
    })

  const matrices = buildAllMatrices(
    componentDirs,
    localElementsByComponent,
    instancesByPrimitive,
    storyStatesByComponent,
  )

  return {
    componentDirCount: componentDirs.length,
    localElements,
    matrices,
    ambiguitySummary: summarizeAmbiguities(instancesByPrimitive, matrices),
  }
}

// The kept/dropped split the Method's own ambiguity-precedence paragraph describes in prose
// (`cellFor`'s own precedence, above): every `composed-story-ambiguous-variant` push taints one
// (primitive, row, state) cell, and that cell's own rendered text either still carries the
// ambiguity note (`'kept'` — nothing else covers that exact state on that exact row) or a real,
// unambiguous match elsewhere on the same row displaced it (`'dropped'`). Counted from the built
// `matrices` themselves, never re-derived by hand — the exact defect item 2 of the row 8 sweep
// found (a hand-typed "six ambiguities... only Menu's actions keeps the note" that measured 13
// tainted cells, not six, and got the keep/drop split backwards under the story-name reading).
function summarizeAmbiguities(instancesByPrimitive, matrices) {
  let instances = 0
  let events = 0
  const storyNames = new Set()
  const taintedCells = new Map()
  for (const primitive of PRIMITIVE_NAMES) {
    for (const inst of instancesByPrimitive.get(primitive) ?? []) {
      if (inst.kind === 'composed-story-unresolved') {
        events++
        storyNames.add(inst.storyName)
      } else if (inst.kind === 'composed-story-ambiguous-variant') {
        instances++
        storyNames.add(inst.storyName)
        const cellKey = `${primitive}|${axisKey(inst)}|${inst.forced.state}`
        if (!taintedCells.has(cellKey)) {
          taintedCells.set(cellKey, { primitive, key: axisKey(inst), state: inst.forced.state })
        }
      }
    }
  }
  let kept = 0
  let dropped = 0
  for (const { primitive, key, state } of taintedCells.values()) {
    const cellProp = state === 'focus-visible' ? 'focusVisible' : state
    const row = (matrices[primitive] ?? []).find((r) => r.variantSize === key)
    const cell = row ? row[cellProp] : null
    const stillNoted =
      Array.isArray(cell) &&
      cell.length === 1 &&
      typeof cell[0] === 'string' &&
      cell[0].includes('none uniquely resolved')
    if (stillNoted) kept++
    else dropped++
  }
  return {
    instances,
    events,
    taintedCells: taintedCells.size,
    kept,
    dropped,
    storyNames: storyNames.size,
  }
}

export function resolveComposedStoryMatches(pending, instancesByPrimitive) {
  for (const {
    componentKey,
    file,
    exportName,
    forced,
    storyLineRange,
    argsLiterals,
    propsScope,
  } of pending) {
    // A `selector`-targeted force-state (`FavouritesList`'s own `Hover`/`FocusVisible`/`Active`,
    // `selector: 'a[href="/players/1"]'`) names no `role` at all — it targets a specific CSS
    // selector, never a primitive by its accessible role, and is not a candidate for this
    // role-based matching regardless of how many `Button`/`Link`/`Field`/`Menu` instances the
    // component happens to render. Every real `role`-based force-state in this tree names its role
    // explicitly; treating an absent `role` as a wildcard (this check's own earlier shape) is what
    // made `FavouritesList`'s two, individually unambiguous (name-matched) `Button`s look like an
    // unresolved pair instead of two force-states this primitive was never the target of at all.
    if (!forced.role) continue
    for (const primitive of PRIMITIVE_NAMES) {
      let candidates = instancesByPrimitive
        .get(primitive)
        .filter((i) => i.kind === 'jsx' && i.componentKey === componentKey && !i.ariaHidden)
      if (storyLineRange && candidates.some((c) => c.file === file)) {
        const inRange = candidates.filter(
          (c) => c.file === file && c.line >= storyLineRange[0] && c.line <= storyLineRange[1],
        )
        if (inRange.length > 0) candidates = inRange
      }
      // A candidate whose own guards evaluate `'unreached'` against this story's own props/args
      // scope is not a sibling this story could possibly render — excluded outright, not merely
      // deprioritised (`FavouriteToggle`'s `SignedOutControl` button, guarded `!authenticated`,
      // excluded once a story's own `authenticated: true` arg resolves that guard false). A guard
      // this scope cannot evaluate at all keeps the candidate in the pool, `unresolvedGuard: true`.
      candidates = candidates
        .map((c) => ({ c, reach: evaluateGuards(c.guards ?? [], propsScope) }))
        .filter(({ reach }) => reach !== 'unreached')
        .map(({ c, reach }) => ({ ...c, unresolvedGuard: reach === 'unresolved' }))
      const roleMatches = candidates.filter(
        (c) => forced.role === impliedRoleForPrimitiveInstance(primitive, c),
      )
      if (roleMatches.length === 0) continue
      // Each candidate's own text, resolved for *this* story: the literal JSX text when it has
      // one, else its dynamic children (`{primaryAction.label}`) evaluated against this story's
      // own scope (`Dialog`'s own `args.primaryAction.label`, substituted in) — `null` when
      // neither resolves, which `resolveNameMatch` treats the same as "no literal text" already.
      const resolvedPool = roleMatches.map((c) => ({
        ...c,
        text: c.text || resolveDynamicChildrenText(c.childrenExpr, propsScope) || c.text,
      }))
      let matchedCandidate = null
      let ambiguous = false
      const ambiguousCandidates = []
      for (const candidate of resolvedPool) {
        const verdict = resolveNameMatch({
          candidate,
          pool: resolvedPool,
          name: forced.name,
          nth: forced.nth,
          argsLiterals,
        })
        if (verdict === 'match') matchedCandidate = candidate
        if (verdict === 'ambiguous') {
          ambiguous = true
          ambiguousCandidates.push(candidate)
        }
      }
      if (matchedCandidate) {
        instancesByPrimitive.get(primitive).push({
          primitive,
          kind: 'composed-story',
          componentKey,
          file,
          storyName: exportName,
          variant: resolveDynamicAxisValue(matchedCandidate.variant, propsScope),
          size: resolveDynamicAxisValue(matchedCandidate.size, propsScope),
          forced,
          playFocus: null,
          sourceLine: matchedCandidate.line,
          // `file` above is the *story* file this match was resolved against — `buildAxisMatrix`'s
          // own fold-back (item 2) needs the JSX candidate's own source file to key against its
          // `rest` entry, which lives in a different file entirely (`FavouriteToggle/index.tsx` vs.
          // `FavouriteToggle.stories.tsx`).
          sourceFile: matchedCandidate.file,
        })
      } else if (ambiguous) {
        const reason = `state ${JSON.stringify(forced.state)}: ${roleMatches.length} ${primitive} instances in ${componentKey} match role ${JSON.stringify(forced.role)}${forced.name ? ` / name ${JSON.stringify(forced.name)}` : ''}${forced.nth != null ? ` / nth ${forced.nth}` : ''}, none uniquely resolved${roleMatches.some((c) => c.unresolvedGuard) ? " (at least one candidate's own guard could not be evaluated from this story's args)" : ''}`
        instancesByPrimitive.get(primitive).push({
          primitive,
          kind: 'composed-story-unresolved',
          componentKey,
          file,
          storyName: exportName,
          forced,
          reason,
        })
        // Positive-knowledge rule (T594 B1, REJECT on #80): an ambiguous match is not a confirmed
        // absence over the variant/size rows it was ambiguous *between* either — Record 1's own
        // `buildElementCells` already applies this (every candidate sharing the role gets its own
        // `unresolved` entry); Record 3 previously only recorded the pseudo-row above and let the
        // real variant rows fall through to a `'none'` that no comparison actually confirmed
        // (`Menu`'s `actions` row against `ProfileSummary`'s `BoardFlagHoverRevealed`, live at
        // `README.md:1902`/`:2305`). Every candidate the ambiguity was between renders `unresolved`
        // on its own row for this state too, alongside the pseudo-row that keeps the detail.
        for (const candidate of ambiguousCandidates) {
          instancesByPrimitive.get(primitive).push({
            primitive,
            kind: 'composed-story-ambiguous-variant',
            componentKey,
            file,
            storyName: exportName,
            variant: resolveDynamicAxisValue(candidate.variant, propsScope),
            size: resolveDynamicAxisValue(candidate.size, propsScope),
            forced,
            reason,
          })
        }
      }
    }
  }
}

// `variant`/`size` already get evaluated against a specific story's own merged args (`resolveProp`
// falling to `resolveDynamicAxisValue` above) — `disabled` (and, on `Button`/`Field`, `loading`,
// which reaches the same rendered state, `PRIMITIVES_WHERE_LOADING_DISABLES`) never did: a dynamic
// expression on a `Button`/`Link`/`Field`/`Menu` call site (`FavouriteToggle`'s own `disabled=
// {bounded}`, `Dialog`'s own `disabled={primaryAction.disabled}`/`loading={primaryAction.loading}`)
// used to leave every row's `disabled` cell reading a bare `'none'` no comparison had ever actually
// made — four such cells, found live in this tree (T594's row 8 sweep, item 1). This runs once per
// `(candidate, story)` pair, for *every* story of the owning component — never only the force-state
// ones `resolveComposedStoryMatches` reads, since `Bounded`/`AddingInFlight` force nothing at all,
// they only ever set `args`. A candidate whose own guards resolve `'unreached'` for a given story
// (`FavouriteToggle`'s decoy `SignedOutControl` button when `authenticated: true`) is skipped
// outright — that story could not possibly render it — the same exclusion role-based matching
// already applies.
// Extends `baseScope` with a candidate's own `localConsts` (`walkJsxWithContext`'s own map,
// declaration order preserved by `Map`) — each evaluated against the *growing* scope in turn, the
// same fold `buildFileValueScope` already does for top-level file consts, so a later local const
// may itself reference an earlier one. Returns `baseScope` unchanged when there are none, the
// common case, rather than copying a `Map` for every candidate with nothing local to add.
function scopeWithLocalConsts(baseScope, localConsts) {
  if (!localConsts || localConsts.size === 0) return baseScope
  const scope = new Map(baseScope)
  for (const [name, exprNode] of localConsts) {
    scope.set(name, evaluateExpr(exprNode, scope))
  }
  return scope
}

export function resolveDisabledFromStories(pendingStoryScopes, instancesByPrimitive) {
  for (const { componentKey, file, exportName, propsScope } of pendingStoryScopes) {
    const label = `${path.basename(file, '.stories.tsx')}:${exportName}`
    for (const primitive of PRIMITIVE_NAMES) {
      const candidates = instancesByPrimitive
        .get(primitive)
        .filter((i) => i.kind === 'jsx' && i.componentKey === componentKey && !i.ariaHidden)
      for (const candidate of candidates) {
        const exprs = [candidate.disabledExpr, candidate.loadingExpr].filter(Boolean)
        if (exprs.length === 0) continue // no dynamic disabled-capable attribute at all: nothing to resolve, and nothing to add — a genuine 'none' stands on its own weight elsewhere
        const reach = evaluateGuards(candidate.guards ?? [], propsScope)
        if (reach === 'unreached') continue
        const scope = scopeWithLocalConsts(propsScope, candidate.localConsts)
        let anyTrue = false
        let anyUnresolved = reach === 'unresolved'
        for (const expr of exprs) {
          const v = evaluateExpr(expr, scope)
          if (!v.resolved) anyUnresolved = true
          else if (v.value) anyTrue = true
        }
        const variant = resolveDynamicAxisValue(candidate.variant, scope)
        const size = resolveDynamicAxisValue(candidate.size, scope)
        if (anyTrue) {
          instancesByPrimitive.get(primitive).push({
            primitive,
            kind: 'jsx-disabled-resolved',
            componentKey,
            file,
            storyName: exportName,
            variant,
            size,
            label,
          })
        } else if (anyUnresolved) {
          instancesByPrimitive.get(primitive).push({
            primitive,
            kind: 'jsx-disabled-unresolved',
            componentKey,
            file,
            storyName: exportName,
            variant,
            size,
            reason: `disabled not statically resolvable (${label})`,
          })
        }
        // Resolved, and false on every dynamic attribute this story carries: real negative
        // knowledge for this one story, nothing to add — the row still falls to a confirmed
        // `'none'` only once *no* story anywhere resolved it true or left it unresolved either.
      }
    }
  }
}

// The children of a JSX element, evaluated as text against `scope` — literal `JsxText` runs plus
// any `{expr}` child resolved through `evaluateExpr` (`Dialog`'s own `{primaryAction.label}`).
// `null` when any part cannot be resolved, so the caller falls back to whatever static text (if
// any) it already had rather than assembling a partial, misleading string.
function resolveDynamicChildrenText(childrenExpr, scope) {
  if (!childrenExpr) return null
  const parts = []
  for (const child of childrenExpr) {
    if (ts.isJsxText(child)) {
      parts.push(child.text)
    } else if (ts.isJsxExpression(child) && child.expression) {
      const v = evaluateExpr(child.expression, scope)
      if (!v.resolved) return null
      if (v.value != null) parts.push(String(v.value))
    } else {
      return null
    }
  }
  const text = parts.join('').replace(/\s+/g, ' ').trim()
  return text || null
}

// Upgrades a `resolved: 'unresolved'` `variant`/`size` field that carries its own dynamic
// expression (`Dialog`'s `primaryAction.variant ?? 'destructive'`) to a concrete value once a
// specific story's own props/args scope can evaluate it — `resolved: 'resolved-from-story'`, kept
// distinct from `'explicit'`/`'default'` so a reader can tell a story-specific resolution from a
// source-wide one.
function resolveDynamicAxisValue(axisField, scope) {
  if (!axisField || axisField.resolved !== 'unresolved' || !axisField.expr) return axisField
  const v = evaluateExpr(axisField.expr, scope)
  if (v.resolved && typeof v.value === 'string') {
    return { value: v.value, resolved: 'resolved-from-story' }
  }
  return axisField
}

// --- Matrix building -------------------------------------------------------------------------

function axisKey(inst) {
  const v = inst.variant?.resolved === 'n/a' ? null : (inst.variant?.value ?? 'unresolved')
  const s = inst.size?.resolved === 'n/a' ? null : (inst.size?.value ?? 'unresolved')
  return [v, s].filter((x) => x !== null).join('|') || '(no axis)'
}

function cellName(inst) {
  if (inst.kind === 'own-story' || inst.kind === 'composed-story')
    return `${path.basename(inst.file, '.stories.tsx')}:${inst.storyName}`
  return `${inst.componentKey}`
}

export function buildAxisMatrix(primitiveName, instances) {
  const rows = new Map()
  const unresolvedReasons = []
  function rowFor(key) {
    if (!rows.has(key)) {
      rows.set(key, {
        key,
        rest: [],
        restInstances: [],
        hover: [],
        'focus-visible': [],
        active: [],
        disabled: [],
        forcedRoles: [],
        // One unresolved-reason list per force-state, parallel to `hover`/`focus-visible`/`active`
        // above. Two shapes land here: a play-driven focus-visible match (never provably a real
        // frame, T594's amendment) and, since B1, an ambiguous composed-story match — the
        // positive-knowledge rule Record 1's own `buildElementCells` already applies, extended to
        // Record 3 so an ambiguity never renders a confirmed `'none'` over a comparison that
        // produced an ambiguity.
        //
        // **Precedence, stated rather than left implied (T594's REJECT on #80, item 4 — the
        // comment this replaced claimed an ambiguity renders `unresolved` on *every* row it was
        // ambiguous between; `cellFor` below only ever reads this list when the same row's own
        // `hover`/`focus-visible`/`active` match list is empty, so a row that *also* carries a real,
        // unambiguous match for that exact state from elsewhere — another story, another candidate
        // — shows that match and drops the ambiguity note entirely; `Menu`'s own `actions` row is
        // one of the cells this leaves with nothing else to show, so it keeps the note — the exact
        // kept/dropped split, over every ambiguity live in this tree today, is `summarizeAmbiguities`'
        // own printed line below, never hand-counted here again (a hand count was wrong twice, T594's
        // row 8 sweep, item 2).**
        //
        // A real match anywhere for this row's own state is positive knowledge in its own right — a
        // cell covered by one story and merely ambiguous against a second force-state is still
        // covered — and outranks noting that a *different* comparison could not be settled; the
        // ambiguity note is not lost, it simply never has to carry a row whose state is already
        // known some other way.
        // `disabled` carries its own reason list the same way (T594's row 8 sweep, item 1): a
        // dynamic `disabled`/`loading` expression this pass could not evaluate against a specific
        // story's own args is `unresolved: <reason>`, never folded into the same confirmed `'none'`
        // a control that carries no disabled-capable attribute at all genuinely earns.
        unresolvedByState: { hover: [], 'focus-visible': [], active: [], disabled: [] },
      })
    }
    return rows.get(key)
  }
  // T594's REJECT on #80, item 2: a JSX candidate's own state can resolve, through a specific
  // story, to a row keyed *differently* from the row its own static (often dynamic-unresolved)
  // variant/size key files its `rest` entry under — `FavouriteToggle`'s real button (`ghost`
  // variant, a dynamic `size` prop no story literal resolves) files `rest` at `ghost|unresolved`,
  // but `FavouriteToggle:Hover`'s own args default that same `size` to `'md'` and land the *match*
  // at `ghost|md` instead; `Dialog`'s two `Button` instances the same way, `unresolved|lg` vs.
  // `destructive|lg`. The same source line lands in two rows, and the row that kept `rest` read a
  // confirmed `'none'` over a comparison that actually found a match elsewhere — positive knowledge
  // this pass has, filed under a different key. Recorded once, up front, from every already-matched
  // `composed-story` instance's own source position, so the row a `rest` line stays on can point at
  // wherever its own state actually resolved instead of falling to `'none'`.
  const storyResolvedBySourceLine = new Map()
  for (const inst of instances) {
    if (inst.kind !== 'composed-story' || inst.sourceLine == null || !inst.sourceFile) continue
    const lineKey = `${inst.componentKey}|${inst.sourceFile}|${inst.sourceLine}`
    if (!storyResolvedBySourceLine.has(lineKey)) storyResolvedBySourceLine.set(lineKey, new Map())
    storyResolvedBySourceLine.get(lineKey).set(inst.forced.state, axisKey(inst))
  }
  for (const inst of instances) {
    if (inst.kind === 'composed-story-unresolved') {
      // No variant/size to key a row on — that is exactly what was unresolved — so this is not
      // attributed to any one row; it is its own pseudo-row below instead, printed rather than
      // silently dropped (`FavouriteToggle`'s two `Button/ghost` instances before `aria-hidden`
      // exclusion narrowed the pool to one, kept here as a worked example of the shape this row
      // still catches when a *different* component leaves two real, equally-named candidates).
      unresolvedReasons.push(
        `${inst.componentKey}/${path.basename(inst.file)}:${inst.storyName} — ${inst.reason}`,
      )
      continue
    }
    const key = axisKey(inst)
    const row = rowFor(key)
    if (inst.kind === 'jsx') {
      row.rest.push(`${inst.componentKey} (${inst.file}:${inst.line})`)
      row.restInstances.push(inst)
      if (inst.disabled) row.disabled.push(`${inst.componentKey} (${inst.file}:${inst.line})`)
      continue
    }
    if (inst.kind === 'composed-story-ambiguous-variant') {
      const stateKey = inst.forced.state
      row.unresolvedByState[stateKey].push(
        `${inst.componentKey}/${path.basename(inst.file)}:${inst.storyName} — ${inst.reason}`,
      )
      continue
    }
    // A `disabled`/`loading` expression `resolveDisabledFromStories` evaluated against one specific
    // story's own merged args — real, positive knowledge that this exact row renders disabled under
    // that story, or a reason it could not tell (T594's row 8 sweep, item 1). Filed on the row the
    // *story* resolved variant/size to, the same redirect `composed-story` already gets, not the
    // JSX candidate's own possibly-different static row.
    if (inst.kind === 'jsx-disabled-resolved') {
      row.disabled.push(inst.label)
      continue
    }
    if (inst.kind === 'jsx-disabled-unresolved') {
      row.unresolvedByState.disabled.push(inst.reason)
      continue
    }
    const label = cellName(inst)
    // An own-story or composed-story instance can carry a positively-resolved `disabled` too
    // (a literal `disabled` attribute in the story's own render JSX, or a nested `disabled: true`
    // admitted by the story's own args) — credited independently of which state, if any, the same
    // story also forces.
    if (inst.disabled) row.disabled.push(label)
    if (inst.forced) {
      const stateKey = inst.forced.state
      if (row[stateKey]) row[stateKey].push(label)
      row.forcedRoles.push({
        state: inst.forced.state,
        role: inst.forced.role,
        name: inst.forced.name,
        story: label,
      })
    } else if (inst.playFocus) {
      // A play() script can leave a real `:focus-visible` on a fresh page, or the same frame a
      // preceding story already captured — the script cannot tell which, statically, so this is
      // never a confirmed cover (T594's amendment, REJECT on #80: 'none' — and a covered cell — is
      // positive knowledge or neither is claimed).
      row.unresolvedByState['focus-visible'].push(
        `${label} (play-driven; frame not provable statically)`,
      )
      row.forcedRoles.push({
        state: 'focus-visible',
        role: inst.playFocus.role,
        name: inst.playFocus.name ?? null,
        story: `${label} (play-driven)`,
      })
    } else {
      row.rest.push(label)
    }
  }
  const builtRows = [...rows.values()]
    .sort((a, b) => a.key.localeCompare(b.key))
    .map((row) => {
      // Before this row's own cell falls all the way to a confirmed `'none'`, check whether one of
      // its own `rest` lines resolved this exact state to a *different* row through a story — if
      // so, point there instead of claiming an absence this pass never actually confirmed.
      const redirectFor = (state) => {
        for (const inst of row.restInstances) {
          const lineKey = `${inst.componentKey}|${inst.file}|${inst.line}`
          const target = storyResolvedBySourceLine.get(lineKey)?.get(state)
          if (target && target !== row.key) return target
        }
        return null
      }
      const cellFor = (stateList, unresolvedList, state) => {
        if (stateList.length) return [...new Set(stateList)]
        if (unresolvedList.length) return [`unresolved: ${[...new Set(unresolvedList)].join('; ')}`]
        const redirect = redirectFor(state)
        if (redirect) return [`unresolved: axis resolved only per story (→ ${redirect})`]
        return ['none']
      }
      return {
        variantSize: row.key,
        rest: row.rest.length ? [...new Set(row.rest)] : ['none'],
        hover: cellFor(row.hover, row.unresolvedByState.hover, 'hover'),
        focusVisible: cellFor(
          row['focus-visible'],
          row.unresolvedByState['focus-visible'],
          'focus-visible',
        ),
        active: cellFor(row.active, row.unresolvedByState.active, 'active'),
        disabled: cellFor(row.disabled, row.unresolvedByState.disabled, 'disabled'),
        forcedRoles: row.forcedRoles.sort(
          (a, b) => a.state.localeCompare(b.state) || String(a.role).localeCompare(String(b.role)),
        ),
      }
    })
  if (unresolvedReasons.length > 0) {
    builtRows.push({
      variantSize: '(unresolved matches — no row, printed rather than dropped)',
      rest: ['N/A'],
      hover: [`unresolved: ${[...new Set(unresolvedReasons)].join(' | ')}`],
      focusVisible: ['N/A'],
      active: ['N/A'],
      disabled: ['N/A'],
      forcedRoles: [],
    })
  }
  return builtRows
}

// The 13 primitives with no `variant`/`size` axis of their own get one row per distinct local
// element `findLocalElements` found in their own index.tsx, cross-referenced against that
// component's own stories.tsx for a `visualForceState`/play-focus match on the same role. A cell is
// `'none'` only when *no* force-state of that state shares the element's implied role anywhere in
// the component's stories; when one does but `resolveNameMatch` cannot settle it on one candidate,
// the cell is `'unresolved: <reason>'` — never silently folded into `'none'`.
// A `role` attribute that is *present but dynamic* (`MenuItemRow`'s own
// `role={variant === 'selection' ? 'menuitemradio' : 'menuitem'}`) overrides the tag's intrinsic
// role at render time, whatever it resolves to — falling back to the intrinsic role here would
// wrongly pool a `<button role={...}>` whose real role is never `'button'` with elements that
// really do render as plain buttons (`Menu`'s own trigger), inventing an ambiguity between two
// elements that can never actually share a role. `null` excludes it from every implied-role pool
// instead — the caller's own `cellFor` no longer reads that `null` as `'none'` (below): a genuine
// gap in role resolution is not comparable knowledge either way.
function impliedRoleOf(el) {
  return el.role === 'unresolved' ? null : el.role || (INTRINSIC_ROLE[el.tag] ?? null)
}

// One element's own role-based and selector-based cells/ambiguous-reasons, against every other
// element in the same component (`elements`) — factored out of `buildElementMatrix` so a second
// pass can read one element's results while computing another's own `'unresolved'` reason (the
// ancestor case below), without re-deriving them.
function buildElementCells(el, elements, storyObjectsWithMeta) {
  const impliedRole = impliedRoleOf(el)
  const pool = elements.filter((o) => impliedRoleOf(o) === impliedRole && !o.ariaHidden)
  const cells = { hover: [], 'focus-visible': [], active: [] }
  const ambiguousReasons = { hover: [], 'focus-visible': [], active: [] }
  if (!el.ariaHidden && impliedRole) {
    for (const { exportName, forced, playFocus, argsLiterals } of storyObjectsWithMeta) {
      // A `selector`-targeted force-state names no `role` — never a candidate for a local
      // element matched by role (the same fix `resolveComposedStoryMatches` carries, and its own
      // comment explains: `FavouritesList`'s row link itself is `selector`-targeted, and must not
      // be treated as a wildcard match against every role-bearing element in the component).
      if (forced && forced.role && forced.role === impliedRole) {
        const verdict = resolveNameMatch({
          candidate: el,
          pool,
          name: forced.name,
          nth: forced.nth,
          argsLiterals,
        })
        if (verdict === 'match') cells[forced.state].push(exportName)
        else if (verdict === 'ambiguous') {
          ambiguousReasons[forced.state].push(
            `${exportName}: ${pool.length} candidates share role ${JSON.stringify(impliedRole)}${forced.name ? `, name ${JSON.stringify(forced.name)} not literally resolvable` : forced.nth != null ? `, nth ${forced.nth} not orderable` : ''}`,
          )
        }
      } else if (
        !forced &&
        playFocus &&
        (playFocus.role === impliedRole || playFocus.role === 'unresolved')
      ) {
        const verdict = resolveNameMatch({
          candidate: el,
          pool,
          name: playFocus.name,
          nth: null,
          argsLiterals,
        })
        // A play() script can leave a real `:focus-visible` on a fresh page, or the same frame a
        // preceding story already captured (`Page.stories.tsx`'s own `play()` `.focus()` shares
        // its frame with `Default` — `tests/visual/stories.spec.ts:92-119`). The script cannot
        // tell which case a given story is, so a resolved candidate is `unresolved`, never
        // `'match'` — covered only by a real `visualForceState` (T594's amendment, REJECT on #80).
        if (verdict === 'match') {
          ambiguousReasons['focus-visible'].push(
            `${exportName} (play-driven; frame not provable statically)`,
          )
        } else if (verdict === 'ambiguous') {
          ambiguousReasons['focus-visible'].push(
            `${exportName} (play-driven): ${pool.length} candidates share role ${JSON.stringify(impliedRole)}`,
          )
        }
      }
    }
  }
  // T595 (row 8, H5, `noImpliedRoleReason`'s "dynamic role" family): a `role` attribute that is
  // *present but dynamic* (`el.role === 'unresolved'`, `MenuItemRow`'s own `role={role}`, `role =
  // variant === 'selection' ? 'menuitemradio' : 'menuitem'`) has no place in the static pool above
  // — `impliedRoleOf` returns `null` for it on purpose (the comment on that function explains why:
  // falling back to the tag's own intrinsic role would wrongly pool this element with ones that
  // really do render that role). But the expression is frequently resolvable *per story*, the same
  // fold `resolveDisabledFromStories` already applies to a dynamic `disabled`/`loading` prop:
  // evaluated against that one story's own props/args scope, extended by the element's own local
  // `const`s in scope (`scopeWithLocalConsts`, below — reused, not a second evaluator). A story
  // whose own data settles the expression is real, positive knowledge for that story alone, never a
  // claim about the element's role in general; a story whose data cannot settle it is simply
  // skipped here (not a negative), the same way a story whose disabled expression cannot be
  // evaluated is skipped rather than counted as a confirmed absence.
  if (!el.ariaHidden && el.role === 'unresolved') {
    const roleExpr = el.attrExprs?.get('role')?.expr ?? null
    if (roleExpr) {
      // A story-specific pool: every other element in the component whose own role, *for this same
      // story*, is also the resolved role — either a plain static role that matches outright, or
      // another dynamic-role element that resolves to the same string for this same story (none in
      // this tree today; kept general rather than assuming exactly one dynamic-role element per
      // component).
      const roleForStory = (candidate, scope) => {
        if (candidate.role !== 'unresolved') return impliedRoleOf(candidate)
        const candidateExpr = candidate.attrExprs?.get('role')?.expr ?? null
        if (!candidateExpr) return null
        const v = evaluateExpr(candidateExpr, scopeWithLocalConsts(scope, candidate.localConsts))
        return v.resolved && typeof v.value === 'string' ? v.value : null
      }
      for (const { exportName, forced, playFocus, argsLiterals, scope } of storyObjectsWithMeta) {
        if (!scope) continue
        if (evaluateGuards(el.guards ?? [], scope) === 'unreached') continue
        const resolved = evaluateExpr(roleExpr, scopeWithLocalConsts(scope, el.localConsts))
        if (!resolved.resolved || typeof resolved.value !== 'string') continue
        const resolvedRole = resolved.value
        const poolForStory = elements.filter(
          (o) => !o.ariaHidden && (o === el || roleForStory(o, scope) === resolvedRole),
        )
        if (forced && forced.role && forced.role === resolvedRole) {
          const verdict = resolveNameMatch({
            candidate: el,
            pool: poolForStory,
            name: forced.name,
            nth: forced.nth,
            argsLiterals,
          })
          if (verdict === 'match') cells[forced.state].push(exportName)
          else if (verdict === 'ambiguous') {
            ambiguousReasons[forced.state].push(
              `${exportName}: ${poolForStory.length} candidates share role ${JSON.stringify(resolvedRole)} (resolved for this story)${forced.name ? `, name ${JSON.stringify(forced.name)} not literally resolvable` : forced.nth != null ? `, nth ${forced.nth} not orderable` : ''}`,
            )
          }
        } else if (
          !forced &&
          playFocus &&
          (playFocus.role === resolvedRole || playFocus.role === 'unresolved')
        ) {
          const verdict = resolveNameMatch({
            candidate: el,
            pool: poolForStory,
            name: playFocus.name,
            nth: null,
            argsLiterals,
          })
          if (verdict === 'match') {
            ambiguousReasons['focus-visible'].push(
              `${exportName} (play-driven; frame not provable statically)`,
            )
          } else if (verdict === 'ambiguous') {
            ambiguousReasons['focus-visible'].push(
              `${exportName} (play-driven): ${poolForStory.length} candidates share role ${JSON.stringify(resolvedRole)} (resolved for this story)`,
            )
          }
        }
      }
    }
  }
  // A `visualForceState: { selector }` targets an element by its own attribute value directly,
  // never by role — so it applies whether or not this element even has an implied role at all
  // (`MatchRow`/`FavouritesList`/`PlayerResultRow`'s own row link, `a[href="..."]`), and is
  // matched against every element sharing the selector's own tag rather than `impliedRole`'s pool
  // (T594's REJECT on #80, item 1 — previously dropped outright, `forced.role` required).
  if (!el.ariaHidden) {
    for (const { exportName, forced, scope } of storyObjectsWithMeta) {
      if (!forced || forced.role || !forced.selector) continue
      const parsed = parseSelector(forced.selector)
      if (!parsed) continue
      const tagPool = elements.filter((o) => o.tag === parsed.tag && !o.ariaHidden)
      if (el.tag !== parsed.tag) continue
      const verdict = resolveSelectorMatch({
        selector: forced.selector,
        candidate: el,
        pool: tagPool,
        scope,
      })
      if (verdict === 'match') cells[forced.state].push(exportName)
      else if (verdict === 'ambiguous') {
        ambiguousReasons[forced.state].push(
          `${exportName}: selector ${JSON.stringify(forced.selector)} not resolvable against this element's own ${JSON.stringify(parsed.attr)}`,
        )
      }
    }
  }
  return { el, impliedRole, cells, ambiguousReasons }
}

// Why a given `state` cell cannot be a confirmed `'none'` for an element `impliedRoleOf` returns
// `null` for — this pass never even attempted to compare a force-state against `el` (the whole
// loop in `buildElementCells` is gated on a truthy `impliedRole`), so `'none'` would be reporting
// an absence this pass never checked for (T594's amendment: `'none'` is positive knowledge or it
// is not printed). `buildElementCells` already resolves a dynamic `role={…}` per story where a
// story's own data settles it (T595) — this function is reached only once that path has already
// run and found nothing for this `el`/`state`, i.e. `el.role === 'unresolved'` genuinely means "no
// story's own data resolved this element's role", never "this pass didn't try". Likewise,
// `buildElementMatrix` already credits `hover`/`active` (never `focus-visible`, which does not
// cascade — see that credit's own comment) from a confirmed descendant match before this function
// is ever called, so the descendant branch below is reached only for a descendant whose own match
// was merely *ambiguous* (never a confirmed one, already credited) — still genuinely unresolved,
// not a confirmed absence and not a confirmed cover either. Two shapes, in order:
//   - `el.role === 'unresolved'`: a dynamic `role={…}` (`MenuItemRow`'s own `role={role}`) whose
//     real rendered role no story's own data settles.
//   - `el` itself carries a real `hover:`/`active:`/`focus-visible:` class for this `state` and a
//     descendant of `el` (by JSX nesting, `nodeStart`/`nodeEnd` containment within the same file)
//     was left ambiguous for this same `state` — genuinely unresolved rather than a guess either
//     way; nothing to credit when `el` carries no such class at all (nothing paints regardless of
//     what a descendant does), which falls to the last case below instead.
//   - neither of the above, *and `el` carries a class for this `state`*: the tag simply carries no
//     role this pass can derive at all. Nothing in this tree reaches this third case today — every
//     `impliedRole == null` element that carries a class either resolves its role dynamically
//     (`MenuItemRow`) or is credited by the ancestor-cascade pass above — but a future one might.
// When `el` carries **no** class for this `state` at all (`AccountErasurePanel`'s own `<label>`,
// which ARIA gives no role of its own to begin with — `INTRINSIC_ROLE` deliberately has no entry
// for it, never guessed — and whose own `className` paints no `hover:`/`focus-visible:`/`active:`
// utility of any kind, confirmed the same way `disabledCell` already confirms a control that carries
// no disabled-capable attribute at all is a real `'none'`), the caller (`cellFor`, below) never
// reaches this function in the first place: nothing exists for any story to depict differently,
// regardless of role, so that comparison needs no role and no story reading to settle — real,
// positive knowledge of a structural absence, not a claim about a comparison this pass declined.
// `labelWrapsControl` (used only as this label's own capture gate, above) independently confirms
// the same shape from the other direction: this specific label wraps its own control directly
// rather than standing in for a state of its own, consistent with — not the source of — the
// class-absence fact this rule actually rests on.
function ownPseudoClass(el, state) {
  return state === 'hover' ? el.hover : state === 'active' ? el.active : el.focusVisible
}
function noImpliedRoleReason(el, state, perElement) {
  if (el.role === 'unresolved') return 'dynamic role'
  const ownClass = ownPseudoClass(el, state)
  const descendant = ownClass
    ? perElement.find(
        ({ el: other, cells, ambiguousReasons }) =>
          other !== el &&
          other.file === el.file &&
          el.nodeStart != null &&
          other.nodeStart != null &&
          el.nodeStart <= other.nodeStart &&
          el.nodeEnd >= other.nodeEnd &&
          (cells[state].length > 0 || ambiguousReasons[state].length > 0),
      )
    : null
  if (descendant) {
    const signal =
      descendant.cells[state].length > 0
        ? [...new Set(descendant.cells[state])].join('; ')
        : [...new Set(descendant.ambiguousReasons[state])].join('; ')
    return `ancestor of a forced descendant (${descendant.el.tag}@${descendant.el.file}:${descendant.el.line}, ${state}: ${signal})`
  }
  return 'no implied role'
}

// The 13 primitives with no `variant`/`size` axis of their own get one row per distinct local
// element `findLocalElements` found in their own index.tsx, cross-referenced against that
// component's own stories.tsx for a `visualForceState`/play-focus match on the same role. A cell is
// `'none'` only when *no* force-state of that state shares the element's implied role anywhere in
// the component's stories; when one does but `resolveNameMatch` cannot settle it on one candidate,
// the cell is `'unresolved: <reason>'` — never silently folded into `'none'`.
export function buildElementMatrix(elements, storyObjectsWithMeta) {
  if (elements.length === 0) {
    return [
      {
        variantSize: '(no local interactive element)',
        rest: ['N/A'],
        hover: ['N/A'],
        focusVisible: ['N/A'],
        active: ['N/A'],
        disabled: ['N/A'],
      },
    ]
  }
  const perElement = elements.map((el) => buildElementCells(el, elements, storyObjectsWithMeta))
  // T595 (row 8, H5, `noImpliedRoleReason`'s "ancestor of a forced descendant" family): `hover` and
  // `active` are driven in the visual harness by a real, CDP-backed pointer move and mouse-down
  // (`tests/visual/stories.spec.ts`'s own `VisualForceState` comment — `locator.hover()`, then
  // `page.mouse.down()`), never a role-scoped pseudo-class toggle, so a real capture of either state
  // also matches `:hover`/`:active` on every ancestor whose own box contains the forced descendant —
  // the same fact `Table`'s own `<tr>` around its row `<a>` used to carry only as hand-written prose
  // (row 8's F17). Credited here, directly into `cells`, before `cellFor` below ever runs, so a
  // credited element's own cell reads the descendant's story name(s) exactly like a direct match —
  // never a special-cased "inherited" value, because the capture the reader opens shows no
  // difference between the two. `focus-visible` is excluded on purpose: a story drives it with a
  // plain `element.focus()` targeting one specific element, which does not move a pointer and does
  // not cascade the way a real hover/press does (row 8's own F17 makes the same distinction). Two
  // guards keep this from over-crediting: `el` must carry a real `hover:`/`active:` class of its own
  // for that state (nothing to credit when nothing paints), and only a *confirmed* descendant match
  // counts — an ambiguous descendant credits nothing, and still falls through to
  // `noImpliedRoleReason`'s own ancestor wording below for an element with no implied role of its
  // own, unresolved rather than guessed either way.
  for (const { el, cells } of perElement) {
    for (const state of ['hover', 'active']) {
      if (cells[state].length > 0) continue
      const ownClass = state === 'hover' ? el.hover : el.active
      if (!ownClass) continue
      const descendant = perElement.find(
        ({ el: other, cells: otherCells }) =>
          other !== el &&
          other.file === el.file &&
          el.nodeStart != null &&
          other.nodeStart != null &&
          el.nodeStart <= other.nodeStart &&
          el.nodeEnd >= other.nodeEnd &&
          otherCells[state].length > 0,
      )
      if (descendant) cells[state] = [...new Set(descendant.cells[state])]
    }
  }
  return perElement.map(({ el, impliedRole, cells, ambiguousReasons }) => {
    // T595: an `impliedRole == null` element that carries no class for this specific `state` at all
    // (`ownPseudoClass`, shared with `noImpliedRoleReason` above) needs no role and no story
    // resolved to know its cell — a real, positive `'none'`, never routed through
    // `noImpliedRoleReason` at all (see that function's own comment for the reasoning this rests
    // on).
    const cellFor = (state) =>
      cells[state].length > 0
        ? [...new Set(cells[state])]
        : ambiguousReasons[state].length > 0
          ? [`unresolved: ${ambiguousReasons[state].join('; ')}`]
          : impliedRole == null && ownPseudoClass(el, state)
            ? [`unresolved: ${noImpliedRoleReason(el, state, perElement)}`]
            : ['none']
    // `'none'` is confirmed only when this element carries no disabled-capable attribute at all —
    // it structurally can never render disabled. When it does (`aria-disabled={item.disabled ||
    // ...}`, `MenuItemRow`'s own shape), credit every story whose own args admit a nested
    // `disabled: true` anywhere; that is real, positive knowledge at the *story* grain (T594's
    // REJECT on #80, item 4) even though this static pass cannot trace it to one specific
    // rendered instance among several in an iteration.
    const disabledCell = !el.hasDisabledAttr
      ? ['none']
      : (() => {
          const covering = [
            ...new Set(
              storyObjectsWithMeta.filter((s) => s.argsHasDisabledTrue).map((s) => s.exportName),
            ),
          ]
          return covering.length > 0 ? covering : ['none']
        })()
    return {
      variantSize: `${el.tag}${el.role ? `[role=${el.role}]` : ''}${el.ariaHidden ? '[aria-hidden]' : ''} @ ${el.file}:${el.line}`,
      rest: [`${el.file}:${el.line}`],
      hover: cellFor('hover'),
      focusVisible: cellFor('focus-visible'),
      active: cellFor('active'),
      disabled: disabledCell,
    }
  })
}

function buildAllMatrices(
  componentDirs,
  localElementsByComponent,
  instancesByPrimitive,
  storyStatesByComponent,
) {
  const matrices = {}
  const primitiveDirs = componentDirs.filter((d) => d.segment === 'primitives')
  for (const { name } of primitiveDirs) {
    if (PRIMITIVE_NAMES.includes(name)) {
      matrices[name] = buildAxisMatrix(name, instancesByPrimitive.get(name))
    } else {
      const elements = localElementsByComponent.get(`primitives/${name}`) ?? []
      const storyStates = storyStatesByComponent.get(`primitives/${name}`) ?? []
      matrices[name] = buildElementMatrix(elements, storyStates)
    }
  }
  return matrices
}

// --- Rendering: record 1 and every primitive matrix as markdown tables --------------------------

function esc(text) {
  return String(text).replace(/\|/g, '\\|').replace(/\n/g, ' ')
}

function table(headers, rows) {
  const head = `| ${headers.join(' | ')} |`
  const sep = `| ${headers.map(() => '---').join(' | ')} |`
  const body = rows.map((r) => `| ${r.map(esc).join(' | ')} |`).join('\n')
  return [head, sep, body].filter(Boolean).join('\n')
}

// `classResolved`: `false` only when `resolveClassParts` hit something it could not read at all
// (a call to an unknown function, a spread, an out-of-scope identifier) — in that case a `null`
// `classText` is not confirmed knowledge that no pseudo-class utility exists, so it must not print
// as `'none'` (T594's amendment, the orchestrator's REJECT on #80: `'none'` is positive knowledge
// or it is not printed at all).
function stateCell(classText, coverageList, classResolved) {
  const cls = classText ?? (classResolved ? 'none' : 'unresolved: className not fully resolved')
  const coverage = coverageList.join('; ')
  return `${cls} → ${coverage}`
}

// The real `focus:` classes an element paints (`SiteHeader`'s skip link, finding 10) alongside
// whatever `focus-visible:` classes it also carries — both answer the same closed-vocabulary
// "focus-visible" state, from two different pseudo-classes, so both belong on the one column a
// reader checks for it rather than one of them staying invisible to record 1.
function combineFocusClassText(focusText, focusVisibleText) {
  if (focusText && focusVisibleText) return `${focusText} ${focusVisibleText}`
  return focusText ?? focusVisibleText
}

export function renderRecord1(computed) {
  const rows = []
  for (const { componentKey, elements } of computed.localElements) {
    if (elements.length === 0) {
      rows.push([componentKey, '(no local interactive element)', 'N/A', 'N/A', 'N/A', 'N/A'])
      continue
    }
    for (const el of elements) {
      const classResolved = (el.classUnresolvedRefs ?? []).length === 0
      rows.push([
        componentKey,
        `${el.tag}${el.role ? `[role=${el.role}]` : ''}${el.tabIndex !== null ? `[tabIndex=${el.tabIndex}]` : ''}${el.ariaHidden ? '[aria-hidden]' : ''}`,
        `${el.file}:${el.line}`,
        stateCell(el.hover, el.coveredBy.hover, classResolved),
        stateCell(
          combineFocusClassText(el.focus, el.focusVisible),
          el.coveredBy.focusVisible,
          classResolved,
        ),
        stateCell(el.active, el.coveredBy.active, classResolved),
      ])
    }
  }
  return table(
    [
      'Component',
      'Element',
      'File:Line',
      'Hover (class → story)',
      'Focus-visible (class → story)',
      'Active (class → story)',
    ],
    rows,
  )
}

export function renderMatrices(computed) {
  const sections = []
  for (const name of Object.keys(computed.matrices).sort()) {
    const rows = computed.matrices[name].map((row) => [
      row.variantSize,
      row.rest.length > 3 ? `${row.rest.length} real call sites` : row.rest.join('; '),
      row.hover.join('; '),
      row.focusVisible.join('; '),
      row.active.join('; '),
      row.disabled.join('; '),
    ])
    sections.push(
      `#### \`${name}\`\n\n${table(['Row', 'Rest', 'Hover', 'Focus-visible', 'Press (active)', 'Disabled'], rows)}`,
    )
  }
  return sections.join('\n\n')
}

export function renderGeneratedRegion(computed) {
  return [
    `<!-- state-coverage:begin -->`,
    `_Generated by \`scripts/checks/state-coverage.mjs --write\`. Do not hand-edit between these markers — run the script instead._`,
    '',
    `**Record 1 — every local interactive element (${computed.componentDirCount} component directories scanned).**`,
    '',
    renderRecord1(computed),
    '',
    '**Record 3 — every primitive matrix.**',
    '',
    renderMatrices(computed),
    `<!-- state-coverage:end -->`,
  ].join('\n')
}

const BEGIN_MARKER = '<!-- state-coverage:begin -->'
const END_MARKER = '<!-- state-coverage:end -->'

export function extractGeneratedRegion(readmeText) {
  const start = readmeText.indexOf(BEGIN_MARKER)
  const end = readmeText.indexOf(END_MARKER)
  if (start === -1 || end === -1 || end < start) return null
  return readmeText.slice(start, end + END_MARKER.length)
}

export function replaceGeneratedRegion(readmeText, newRegion) {
  const start = readmeText.indexOf(BEGIN_MARKER)
  const end = readmeText.indexOf(END_MARKER)
  if (start === -1 || end === -1 || end < start) {
    throw new Error(`${BEGIN_MARKER}/${END_MARKER} not found in README text`)
  }
  return readmeText.slice(0, start) + newRegion + readmeText.slice(end + END_MARKER.length)
}

// Formats `text` (a full README.md's worth of markdown) through the repository's own prettier
// binary via stdin, exactly the formatting `pnpm exec prettier --write` would apply — so check mode
// never reports a difference that is only prettier's own table-padding choice, and `--write` leaves
// the file exactly as `prettier --check` expects it.
export function formatWithPrettier(text) {
  return execFileSync(prettierBin, ['--stdin-filepath', 'README.md'], {
    input: text,
    cwd: rootDir,
    encoding: 'utf8',
    maxBuffer: 1024 * 1024 * 64,
  })
}

// A minimal line-level diff between two strings — the usage comment above promises check mode
// prints one; before this it only ever named the two commands to run, never showed what actually
// differed. A parallel line-index comparison, not a true LCS diff: good enough for this region,
// whose content is one markdown table row per line, and worth more than the comment it replaces.
export function diffLines(before, after) {
  const beforeLines = before.split('\n')
  const afterLines = after.split('\n')
  const max = Math.max(beforeLines.length, afterLines.length)
  const out = []
  for (let i = 0; i < max; i++) {
    const b = beforeLines[i]
    const a = afterLines[i]
    if (b === a) continue
    if (b !== undefined) out.push(`- ${b}`)
    if (a !== undefined) out.push(`+ ${a}`)
  }
  return out.length > 0 ? out.join('\n') : '(no line-level difference — whitespace only)'
}

// --- Citation checking (`reviewer`'s third REJECT on PR #80) ------------------------------------
//
// Every citation in row 8's own prose (8c, 8c-bis, 8d's no-owner list, 8e's findings) names a
// `file:line` and quotes what is there — the shape three review passes found wrong line numbers
// and misquotes in, and could not verify twelve of at all. This is the reader nobody should have
// to be, run as its own gate.
//
// **What a citation is.** A backtick span ``` `location:line` ``` or ``` `location:line-line2` ```
// — a comma joins several line numbers/ranges under one `location` (`structural-tier.md:549,551`,
// a citation claiming its quote spans both, not that each repeats it independently) — immediately
// followed by its own quote: a straight double-quoted string, or, failing that within the same
// short gap, the next inline-code span. "Immediately" allows only whitespace and one optional
// `(` between the citation's closing backtick and the quote's opening mark — the same gap the
// best-formed citations on this page already leave (`` `sign-in-screen.md:69` ("owned entirely by
// `Button`") ``). A backtick `location:line` with nothing adjacent to it is not a citation under
// this definition: read as a structural pointer into source ("`index.tsx:127,138`, `variant={…}`
// … "), not a claim this checker can hold to particular prose — deliberately out of scope, not a
// silently accepted one. Every span that *does* carry an adjacent quote is parsed and must resolve
// and match, or the run fails and names it.
//
// **`location`.** A bare `*.md` filename resolves under `packages/design-system/specs/`. Inside
// 8c's own table, a citation may omit `location` entirely (`` `:39` ``) — resolved against that
// table row's own first cell, the file the row is filed under; inside 8c-bis's table, the same
// bare shorthand resolves against that row's own component, as `<Component>.stories.tsx`. Outside
// a table (8d, 8e), `location` is never omitted — any other value (a bare `*.stories.tsx`
// filename, a `segment/Component/index.tsx`-shaped relative path, or a path rooted at
// `packages/design-system/`) is resolved by an exact or unique-suffix match against every file
// this package's own source tree carries; a location this checker cannot resolve to exactly one
// file fails, rather than matching the first thing that looks close.
//
// **Matching.** The cited line(s) are read from the resolved file, concatenated with a single
// space (so a quote split across `:550-551` is one string to search), and whitespace-collapsed.
// An ellipsis (`…`, U+2026) inside a quote elides a run of text: the quote is split there into an
// ordered sequence of parts, each required to appear, in that order, in the target text — an
// unelided quote is one part, matched as a literal (whitespace-collapsed) substring.
// T594's REJECT on #80, item 7: this used to stop at `**Cell counts` — the paragraph that follows
// row 8's own tally rule — which left roughly the last hundred lines of row 8 (the "Six cells
// moved again" paragraph, the re-derivation of F10/F10a/F12/F17 against them, the Owners
// paragraph, and the closing "Also recorded" note) entirely outside this checker's reach: eight
// `index.tsx:N` citations in that span were never mechanically verified (a reviewer hand-checked
// them; all correct), and a ninth, the closing note's own `Link.stories.tsx:47-60`, had gone stale
// (the rename it promised already landed) with nothing to catch it. Row 8 is the last thing in
// this file (`packages/design-system/specs/README.md`'s own "Contrast-signal and duplicate-
// baseline gap register" carries no ninth row and no section after it), so the scope now runs to
// the end of the document rather than to an interior heading that happens to name a real boundary
// for only *part* of the row.
export function extractCitationScope(readmeText) {
  const start = readmeText.indexOf('**8c. Record 2')
  if (start === -1) return null
  return readmeText.slice(start)
}

// The double-quoted alternative allows a backslash-escaped `\"` inside it — several citations on
// this page quote a spec sentence that itself contains a nested literal quote (`analysis-
// timeline.md:288`'s `"Try requesting analysis"` button label) and escape it to keep the outer
// quote closing where it should; `unescapeQuote` below undoes that before matching.
//
// **The gap, three shapes** (widened by `reviewer`'s fourth REJECT on PR #80 — the plain form
// alone admitted only whitespace and one optional `(`, which made ten citations carrying a real
// adjacent quote invisible to this parser, several of them wrong line numbers a check that never
// parsed them could not catch): the plain form itself (`` `sign-in-screen.md:69` ("owned entirely
// by `Button`") ``, quote either double-quoted or a bare code span); a possessive annotation — an
// apostrophe-`s`, an optional `own`, and up to three lowercase words, with an optional trailing `(`
// (`` `:138`'s focus-visible bullet ("...") ``, `` `privacy-notice.md:523`'s own claim ("...") ``);
// and a bold parenthetical aside ending in an em dash (`` `favourites-list.md:110-111`
// (**corrected …**) — "..." ``). The latter two admit only a double-quoted string as the quote,
// never the bare-code-span alternative: the annotation words themselves are prose that can end in
// an unrelated inline-code reference (`` '...`ArchivalControl`'s own comment...' ``), and crediting
// that as *this* citation's quote is worse than declining to parse it at all. A gap outside all
// three shapes is not a citation under this definition — never silently accepted, caught instead by
// `findUnparsedQuoteAdjacentCitations` below, which fails the run when a quote sits just past one.
const CITATION_RE = new RegExp(
  '`([\\w./-]*):(\\d+(?:-\\d+)?(?:,\\d+(?:-\\d+)?)*)`' +
    '(?:' +
    '\\s*\\(?\\s*(?:"((?:[^"\\\\]|\\\\.)*)"|`([^`]*)`)' +
    '|' +
    "(?:\\s*'s\\s*(?:own\\s+)?(?:[a-z][a-z-]*\\s+){0,3}\\(?\\s*|" +
    '\\s*\\(\\*\\*[\\s\\S]*?\\*\\*\\)\\s*—\\s*)"((?:[^"\\\\]|\\\\.)*)"' +
    ')',
  'g',
)

// Every `` `location:line` `` shaped span in scope, not already parsed above as a citation, that
// is followed — within a short distance, stopping at a table-cell boundary or at a *citation-shaped*
// backtick span (`` `foo:123` ``, the next citation's own location marker) so an unrelated later
// quote or another citation's own text is never mistaken for this one's — by a real double-quoted
// string. Anything this finds is a citation whose own gap the widened parser above still does not
// recognise: a malformed or misplaced citation, not a structural pointer (the same fourth-REJECT
// instruction: "a citation outside the recognised format must fail, not be skipped"). Only a plain
// `"` counts as the quote here, deliberately narrower than the parser's own quote grammar.
//
// A plain inline-code span in the gap (`` `Button.stories.tsx` ``, `` `destructive` `` — no
// `:digit` inside) is **not** a stop condition: it is prose, not another citation, and stopping
// there is exactly how F20's own defect escaped this check (T594 B2, REJECT #5 on #80/#79) — the
// gap between `:122-124` and its real quote crosses `` `destructive` `` at offset 20 of 40, and the
// old scan bailed there before ever reaching the quote, so a citation whose quote matched neither
// cited location was never even flagged as malformed. A backtick with no matching close before the
// budget (or past it) still bails — genuinely ambiguous, the same as before.
const LOCATION_ONLY_RE = /`([\w./-]*):(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)`/g
const CITATION_SHAPED_SPAN_RE = /^[\w./-]*:\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$/
export const UNPARSED_QUOTE_DISTANCE = 40

export function findUnparsedQuoteAdjacentCitations(scopeText) {
  const flat = scopeText.replace(/\n/g, ' ')
  const parsedSpans = []
  CITATION_RE.lastIndex = 0
  let pm
  while ((pm = CITATION_RE.exec(flat))) parsedSpans.push([pm.index, pm.index + pm[0].length])
  const isParsed = (pos) => parsedSpans.some(([s, e]) => pos >= s && pos < e)

  const results = []
  LOCATION_ONLY_RE.lastIndex = 0
  let lm
  while ((lm = LOCATION_ONLY_RE.exec(flat))) {
    if (isParsed(lm.index)) continue
    const spanEnd = lm.index + lm[0].length
    const budget = spanEnd + UNPARSED_QUOTE_DISTANCE
    let pos = spanEnd
    let quoteAt = -1
    while (pos < budget && pos < flat.length) {
      const ch = flat[pos]
      if (ch === '`') {
        const closeIdx = flat.indexOf('`', pos + 1)
        if (closeIdx === -1 || closeIdx >= budget) break // unmatched within the gap: bail, ambiguous
        const inner = flat.slice(pos + 1, closeIdx)
        if (CITATION_SHAPED_SPAN_RE.test(inner)) break // the *next* citation's own location marker
        pos = closeIdx + 1
        continue
      }
      if (ch === '"') {
        quoteAt = pos
        break
      }
      if (ch === '|') break
      pos++
    }
    if (quoteAt === -1) continue
    const lineIndex = scopeText.slice(0, lm.index).split('\n').length - 1
    results.push({ raw: lm[0], line: lineIndex + 1, gap: flat.slice(spanEnd, quoteAt) })
  }
  return results
}

// T594 M2/M3, REJECT #5 on #80/#79: a `` `file:line` `` citation followed by a `"..."`-quoted
// string is verified by `checkCitations` above; one followed by an *inline-code* span (single
// backtick, no surrounding double quotes) never was — `CITATION_RE`'s own backtick-quote
// alternative only fires when the code span sits immediately adjacent, and about half the
// inline-code spans in row 8's own F1-F20/8d/8e prose sit a few words further off (`F19`'s own
// `FavouritesList/index.tsx:293\` gives \`RemoveControl\` (\`FavouriteToggle\`) \`size="lg"\``:
// two bare-identifier spans intervene before the real claim). Both real defects this task found
// (F17's `focusRing` string one line off, F19's `size="lg"` five lines off) were inline-code claims
// exactly this shape, sitting unverified.
//
// The distinction this exports, deliberately: a bare identifier span (`` `Button` ``, `` `Menu` ``,
// `` `RemoveControl` ``, `` `FavouriteToggle` `` — a single word, no source punctuation) is a
// *reference* to a component, not a claim about what a specific cited line contains, and is never
// treated as one — skipped over on the way to the real claim, the same way a bare component name in
// a table's own citation column is not itself verified against file content. A span carrying real
// source punctuation (`=`, `(`, `)`, `{`, `}`, `<`, `>` — a prop assignment, a call, a class list,
// a tag) *is* a claim about the nearest preceding cited line, and is verified the same way a
// double-quoted citation already is: `matchQuoteAgainstText` against that line's own text.
const CODE_SHAPED_SPAN_RE = /[="(){}<>]/
export const INLINE_CLAIM_DISTANCE = 150

export function findInlineCodeClaims(scopeText) {
  const flat = scopeText.replace(/\n/g, ' ')
  const parsedSpans = []
  CITATION_RE.lastIndex = 0
  let pm
  while ((pm = CITATION_RE.exec(flat))) parsedSpans.push([pm.index, pm.index + pm[0].length])
  const isParsed = (pos) => parsedSpans.some(([s, e]) => pos >= s && pos < e)

  const results = []
  LOCATION_ONLY_RE.lastIndex = 0
  let lm
  while ((lm = LOCATION_ONLY_RE.exec(flat))) {
    // Already a real citation (a `"..."` or immediately-adjacent `` `...` `` quote follows it
    // directly) — verified by `checkCitations` itself, never double-claimed here.
    if (isParsed(lm.index)) continue
    const [, location, lineSpec] = lm
    const spanEnd = lm.index + lm[0].length
    const budget = spanEnd + INLINE_CLAIM_DISTANCE
    let pos = spanEnd
    let claim = null
    while (pos < budget && pos < flat.length) {
      const ch = flat[pos]
      if (ch === '"' || ch === '|') break // a real quote or a table boundary: a different citation's own domain
      if (ch === '`') {
        const closeIdx = flat.indexOf('`', pos + 1)
        if (closeIdx === -1 || closeIdx >= budget) break // unmatched within the budget: bail, ambiguous
        const inner = flat.slice(pos + 1, closeIdx)
        if (CITATION_SHAPED_SPAN_RE.test(inner)) break // the *next* citation's own location marker
        if (CODE_SHAPED_SPAN_RE.test(inner)) {
          claim = inner
          break
        }
        // A bare identifier immediately followed by a possessive `'s` reassigns the subject —
        // `` `EscapeReturnsFocusToTrigger`'s `play()` `` is a claim about *that* identifier, never
        // about whatever citation preceded it (`Menu`'s own `index.tsx:144`, three sentences
        // earlier) — bail rather than let the next code-shaped span downstream be misattributed.
        if (flat.slice(closeIdx + 1, closeIdx + 3) === "'s") break
        pos = closeIdx + 1 // a bare identifier span: a reference, not a claim — skip past it
        continue
      }
      pos++
    }
    if (claim === null) continue
    const lineIndex = scopeText.slice(0, lm.index).split('\n').length - 1
    results.push({ raw: lm[0], location, lineSpec, line: lineIndex + 1, claim })
  }
  return results
}

function unescapeQuote(text) {
  return text.replace(/\\(.)/g, '$1')
}

// Every citation found in `scopeText`, line by line so a bare (location-less) citation can be
// resolved against the markdown table row it sits in — 8c's own file column, or 8c-bis's own
// component column. `tableContext` carries forward across consecutive `|`-prefixed lines only,
// the same rule that keeps prose after a table from inheriting its last row's file by accident.
export function parseCitations(scopeText) {
  // Table-row context (8c's own File column, 8c-bis's own Component column) is a per-*physical*-
  // line fact — computed against the real lines first, forward-filled the same way a reader's eye
  // carries a table's own file down its rows, reset the moment a line stops being one.
  const lines = scopeText.split('\n')
  const contextByLine = []
  let tableContext = null
  for (const line of lines) {
    const trimmed = line.trimStart()
    if (trimmed.startsWith('|')) {
      const rowMatch = trimmed.match(/^\|\s*`([^`]+)`\s*\|/)
      if (rowMatch) {
        const cell = rowMatch[1]
        tableContext = cell.endsWith('.md')
          ? { kind: 'md', name: cell }
          : { kind: 'stories', name: cell }
      }
    } else {
      tableContext = null
    }
    contextByLine.push(tableContext)
  }

  // Prose (8d, 8e) is prettier-wrapped — a citation's own quote can carry a hard line break
  // between the words either side of it, invisible to a reader and meaningless to what the quote
  // claims. Newlines are flattened to spaces before matching (`\n` and `' '` are both one
  // character, so every match offset below still lands on the same *character* of `scopeText`,
  // and the line it started on is still recoverable by counting the newlines before it) — a
  // citation is never invisible to this parser only because prettier chose to wrap it.
  const flat = scopeText.replace(/\n/g, ' ')
  const citations = []
  CITATION_RE.lastIndex = 0
  let m
  while ((m = CITATION_RE.exec(flat))) {
    const [raw, location, lineSpec, plainDoubleQuote, codeQuote, annotatedDoubleQuote] = m
    const doubleQuote = plainDoubleQuote ?? annotatedDoubleQuote
    const quote = doubleQuote !== undefined ? unescapeQuote(doubleQuote) : codeQuote
    const lineIndex = scopeText.slice(0, m.index).split('\n').length - 1
    citations.push({
      raw,
      location: location || null,
      lineSpec,
      quote,
      tableContext: location ? null : contextByLine[lineIndex],
    })
  }
  return citations
}

// Parses `1`, `1-2`, `1,5-7` into `[[1, 1], [5, 7]]`. Malformed input (the citation regex already
// guarantees digits and dashes only, so this is a belt) returns `null`.
export function parseLineSpec(lineSpec) {
  const ranges = []
  for (const part of lineSpec.split(',')) {
    const m = part.match(/^(\d+)(?:-(\d+))?$/)
    if (!m) return null
    ranges.push([Number(m[1]), m[2] ? Number(m[2]) : Number(m[1])])
  }
  return ranges
}

// Resolves a citation's own `location` (or its table context) to one file under this repository,
// or `null` when it cannot be resolved to exactly one — ambiguity is a failure, not a guess.
export function resolveCitationLocation(
  { location, tableContext },
  { specsDir: specs, allSrcFiles },
) {
  // 8c-bis's own table context is a bare component name (`AnalysisTimeline`, its first cell),
  // never a filename — resolved against that component's own `<Name>.stories.tsx`, the same file
  // an explicit `AnalysisTimeline.stories.tsx:176` in prose would resolve to.
  const name = location ?? (tableContext ? tableContext.name : null)
  if (!name) return null
  if (tableContext && tableContext.kind === 'stories' && !location) {
    return resolveCitationLocation(
      { location: `${name}.stories.tsx`, tableContext: null },
      { specsDir: specs, allSrcFiles },
    )
  }
  if (name.endsWith('.md')) {
    const direct = path.isAbsolute(name) ? name : path.join(rootDir, name)
    if (existsSync(direct) && statSync(direct).isFile()) return direct
    const p = path.join(specs, path.basename(name))
    return existsSync(p) ? p : null
  }
  // A story-file table context (8c-bis) is always a bare `<Component>.stories.tsx` — resolved the
  // same suffix-unique way as an explicit one in prose.
  const direct = path.join(srcDir, name)
  if (existsSync(direct) && statSync(direct).isFile()) return direct
  const base = name.split('/').slice(-2).join('/') // "Component/index.tsx" style suffix
  const suffixMatches = allSrcFiles.filter(
    (f) => f.endsWith(`/${name}`) || f.endsWith(`/${base}`) || path.basename(f) === name,
  )
  const unique = [...new Set(suffixMatches)]
  return unique.length === 1 ? unique[0] : null
}

// A bare filename shared by every component (`index.tsx`, `index.tsx:426`) cannot resolve uniquely
// through `resolveCitationLocation` above — the whole reason a bullet names its subject component
// once, in **bold** or in its own opening clause, rather than repeating the directory on every
// citation inside it. T594 M2/M3's own inline-code-claim check hits this directly: a claim's own
// citation is routinely a bare `index.tsx:N` inside a bullet whose subject was already named a
// sentence earlier (`Dialog`, `PrivacyNotice`, `ProfileSummary`…). Resolved here the same way a
// reader resolves it — the *first* backtick-quoted `PascalCase` word in the bullet's own text
// (the list item this line sits in, from its own `- **` start to the next one) that names a real
// component directory, never the nearest preceding one: a bullet routinely mentions a second
// component's name (`Button`, `Menu`) after its own subject, and the nearest-preceding rule would
// misattribute a citation about the subject's own file to that second component's directory instead
// (`Dialog`'s own two `Button` instances — `Button` sits between `Dialog` and the citation).
function bulletBlockAround(scopeText, lineNum) {
  const lines = scopeText.split('\n')
  let start = lineNum - 1
  while (start > 0 && !/^-\s+\*\*/.test(lines[start])) start--
  let end = lineNum
  while (end < lines.length && !/^-\s+\*\*/.test(lines[end])) end++
  return lines.slice(start, end).join('\n')
}

// Every backtick-quoted `PascalCase` word in `blockText` that names a real component directory,
// in the order it appears, each tagged with whether it is immediately followed by a possessive
// `'s` — the one grammatical signal this prose actually uses to mark a bullet's own subject
// ("`Dialog`'s own two `Button` instances": `Dialog` is possessive, the subject; `Button` is the
// object of that sentence, never marked that way). Returns `{ name, dir, possessive }` per match,
// `dir` already resolved to the real directory `PRIMITIVE_NAMES`/`TIER_SEGMENTS` gives it.
function namedDirectoriesInBlock(blockText, allSrcFiles) {
  // The *whole* backtick span, from an opening backtick immediately followed by an uppercase
  // letter (never `` `<Button` ``, a JSX tag quoted for its own sake, the same exclusion the
  // pre-fix version got by accident from a narrower regex) to its own closing backtick — captures
  // only the leading `PascalCase` run (`` `Dialog.stories.tsx` `` still names `Dialog`), so the
  // possessive check below can look at what follows the *closing* backtick regardless of how much
  // of the span's own text sits after the captured name.
  const spanRe = /`([A-Z][A-Za-z0-9]*)[^`]*`/g
  const found = []
  let m
  while ((m = spanRe.exec(blockText))) {
    const name = m[1]
    const dirRe = new RegExp(`/(?:primitives|composites|screens)/${name}/`)
    const match = allSrcFiles.find((f) => dirRe.test(f))
    if (!match) continue
    const dir = match.slice(0, match.indexOf(match.match(dirRe)[0]) + match.match(dirRe)[0].length)
    const possessive = /^'s\b/.test(blockText.slice(m.index + m[0].length))
    found.push({ name, dir, possessive })
  }
  return found
}

// Every *fully qualified* citation in the block for this exact `bareLocation` basename
// (`` `AccountErasurePanel/index.tsx:224` `` when `bareLocation` is `index.tsx`) — the strongest
// signal available: the prose itself already disambiguates this exact file elsewhere in the same
// bullet, so a bare citation for the same basename resolves against it before any weaker heuristic
// runs at all. Distinct directories returned, in no particular order — the caller fails outright
// when there is more than one, a genuine internal contradiction rather than something to guess past.
function selfQualifiedDirs(blockText, bareLocation, allSrcFiles) {
  const escaped = bareLocation.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp('`([A-Z][A-Za-z0-9]*)/' + escaped + '(?::|`)', 'g')
  const dirs = new Set()
  let m
  while ((m = re.exec(blockText))) {
    const dirRe = new RegExp(`/(?:primitives|composites|screens)/${m[1]}/`)
    const match = allSrcFiles.find((f) => dirRe.test(f))
    if (match)
      dirs.add(match.slice(0, match.indexOf(match.match(dirRe)[0]) + match.match(dirRe)[0].length))
  }
  return [...dirs]
}

// Resolves a bare filename (`index.tsx`, no leading path) against the *one* component directory
// this bullet is genuinely about — never merely the first real-directory name the block happens to
// mention, which silently picks the wrong file once a bullet's own subject is named after some
// other real component it discusses along the way (T594's row 8 sweep, item 5; documented before
// this fix as a known risk, worked around per-citation by qualifying the path in full rather than
// closed at the source — `selfQualifiedDirs` above is that same workaround, read back out of the
// prose instead of trusted by construction). Three signals, in order of how much they actually
// commit to an answer: (1) a fully qualified citation for this exact basename elsewhere in the
// block — unambiguous, and a *second*, disagreeing one is a real contradiction, failed outright;
// (2) the directory named with a possessive `'s` — this prose's own grammatical marker for "this is
// what the sentence is about" (`` `Dialog`'s own two `Button` instances ``: `Dialog` is possessive,
// the subject; `Button` is the object of that sentence, never marked that way) — more than one
// distinct directory marked this way is the same kind of contradiction; (3) the first real-directory
// name in the block, whether marked or not — the pre-fix rule, kept as the last resort so a citation
// that predates this fix and never needed disambiguating still resolves exactly as it always did.
export function resolveBareLocationFromBullet(scopeText, lineNum, bareLocation, allSrcFiles) {
  const blockText = bulletBlockAround(scopeText, lineNum)
  const tryDir = (dir) => {
    const candidate = path.join(dir, bareLocation)
    return existsSync(candidate) && statSync(candidate).isFile() ? candidate : null
  }
  const qualified = selfQualifiedDirs(blockText, bareLocation, allSrcFiles)
  if (qualified.length > 1) return null // the block itself qualifies this basename two ways — contradiction, not a guess to make
  if (qualified.length === 1) {
    const resolved = tryDir(qualified[0])
    if (resolved) return resolved
  }
  const named = namedDirectoriesInBlock(blockText, allSrcFiles)
  const possessiveDirs = [...new Set(named.filter((n) => n.possessive).map((n) => n.dir))]
  if (possessiveDirs.length > 1) return null // genuine subject ambiguity — fail, never guess
  if (possessiveDirs.length === 1) {
    const resolved = tryDir(possessiveDirs[0])
    if (resolved) return resolved
    // The marked subject's own directory carries no file at this bare name — fall through to the
    // first-named rule below rather than fail outright, the same tolerance the pre-fix version had.
  }
  for (const { dir } of named) {
    const resolved = tryDir(dir)
    if (resolved) return resolved
  }
  return null
}

// Whether `quote` (an ellipsis-elided sequence or a plain string) appears, in order, in the text
// spanned by `ranges` (1-indexed, inclusive) of `fileText`'s own lines.
export function matchQuoteAgainstText(quote, fileText, ranges) {
  const lines = fileText.split('\n')
  const spanned = ranges
    .map(([start, end]) => lines.slice(start - 1, end).join(' '))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
  let cursor = 0
  for (const rawPart of quote.split('…')) {
    const part = rawPart.replace(/\s+/g, ' ').trim()
    if (part === '') continue
    const idx = spanned.indexOf(part, cursor)
    if (idx === -1) return false
    cursor = idx + part.length
  }
  return true
}

// Parses and verifies every citation in row 8's own 8c/8c-bis/8d/8e prose (`extractCitationScope`)
// against the live tree.
export function checkCitations({ readmeText }) {
  const scopeText = extractCitationScope(readmeText)
  if (scopeText === null) {
    return {
      parsedCount: 0,
      failures: [
        { raw: '(scope)', reason: '8c/8c-bis/8d/8e scope markers not found in README.md' },
      ],
    }
  }
  const allSrcFiles = walkAllTsxFiles(srcDir).map((f) => f.split(path.sep).join('/'))
  const citations = parseCitations(scopeText)
  const failures = []
  for (const citation of citations) {
    if (citation.location === null && citation.tableContext === null) {
      failures.push({
        raw: citation.raw,
        reason: 'bare `:line` citation outside a recognised table row',
      })
      continue
    }
    const ranges = parseLineSpec(citation.lineSpec)
    if (!ranges) {
      failures.push({
        raw: citation.raw,
        reason: `malformed line spec ${JSON.stringify(citation.lineSpec)}`,
      })
      continue
    }
    const resolved = resolveCitationLocation(citation, {
      specsDir: path.join(dsDir, 'specs'),
      allSrcFiles,
    })
    if (!resolved) {
      const name = citation.location ?? citation.tableContext?.name
      failures.push({
        raw: citation.raw,
        reason: `location ${JSON.stringify(name)} did not resolve to exactly one file`,
      })
      continue
    }
    const maxLine = Math.max(...ranges.map(([, end]) => end))
    const fileText = readFileSync(resolved, 'utf8')
    const lineCount = fileText.split('\n').length
    if (maxLine > lineCount) {
      failures.push({
        raw: citation.raw,
        reason: `${relPath(resolved)} has ${lineCount} lines, cited up to :${maxLine}`,
      })
      continue
    }
    if (!matchQuoteAgainstText(citation.quote, fileText, ranges)) {
      failures.push({
        raw: citation.raw,
        reason: `quote not found at ${relPath(resolved)}:${citation.lineSpec}`,
      })
    }
  }
  const unparsed = findUnparsedQuoteAdjacentCitations(scopeText)
  for (const u of unparsed) {
    failures.push({
      raw: u.raw,
      reason:
        `at row 8's own region, README.md line ${u.line}: a quote follows within ` +
        `${UNPARSED_QUOTE_DISTANCE} characters (gap ${JSON.stringify(u.gap)}) but this span's own ` +
        'gap does not parse as a citation — fix the citation (or its quote) rather than widen the ' +
        'gap rule again for one more shape',
    })
  }
  // T594 M2/M3: an inline-code span next to a `file:line` is a claim about that line, verified the
  // same way a double-quoted citation is — never merely skipped because it carries a backtick
  // instead of a `"`.
  const inlineClaims = findInlineCodeClaims(scopeText)
  let inlineClaimVerifiedCount = 0
  let inlineClaimFailureCount = 0
  let inlineClaimUnresolvableCount = 0
  let inlineClaimOutOfRangeCount = 0
  let inlineClaimMalformedLineSpecCount = 0
  for (const claim of inlineClaims) {
    // `LOCATION_ONLY_RE`'s own `location` group (`[\w./-]*`) matches empty, so a genuinely bare
    // `` `:96` `` (no filename at all — F17's own opening parenthetical, "`:96` is the `const
    // focusRing =` declaration itself") parses with `claim.location === ''`, falsy exactly like a
    // real absence. `if (!claim.location) continue` (T594's REJECT on #80, item 1) treated the two
    // the same and dropped every bare-location claim unverified — five of the ten claims on this
    // page at the time of that REJECT, every one of them an M2/M3 citation correction. A bare
    // location means "this bullet's own subject component's `index.tsx`", the exact shape
    // `resolveBareLocationFromBullet` already resolves for a *named* bare filename (`index.tsx`
    // with no leading path) below — routed through the same function with that default name rather
    // than skipped.
    const bareLocation = claim.location || 'index.tsx'
    let resolved = claim.location
      ? resolveCitationLocation(
          { location: claim.location, tableContext: null },
          { specsDir: path.join(dsDir, 'specs'), allSrcFiles },
        )
      : null
    // A bare filename every component shares (`index.tsx`) never resolves uniquely on its own —
    // fall back to the bullet's own named subject component (see `resolveBareLocationFromBullet`).
    if (!resolved && !bareLocation.includes('/')) {
      resolved = resolveBareLocationFromBullet(scopeText, claim.line, bareLocation, allSrcFiles)
    }
    if (!resolved) {
      inlineClaimUnresolvableCount++
      failures.push({
        raw: claim.raw,
        reason: `inline-code claim ${JSON.stringify(claim.claim)}: location ${JSON.stringify(claim.location)} did not resolve to exactly one file`,
      })
      continue
    }
    const ranges = parseLineSpec(claim.lineSpec)
    // A hole T595 closes: this used to be a bare `continue`, the same silent-drop shape as the
    // out-of-range branch below — a malformed line spec was dropped from the tally with the run
    // still exiting 0. It is a failure now, with its own counter, so the sum assertion after this
    // loop can hold. `claim.lineSpec` is always `LOCATION_ONLY_RE`'s own capture group, built from
    // exactly the atoms `parseLineSpec`'s per-part regex accepts (see that function's own comment
    // on its citation-level twin above, `parseCitations`'s `!ranges` branch: "the citation regex
    // already guarantees digits and dashes only, so this is a belt") — so `!ranges` cannot be
    // reached through any real `readmeText` today. It stays a real, counted failure rather than a
    // silent `continue` anyway, so a future widening of that regex cannot reopen this hole unnoticed.
    if (!ranges) {
      inlineClaimMalformedLineSpecCount++
      failures.push({
        raw: claim.raw,
        reason: `inline-code claim ${JSON.stringify(claim.claim)}: malformed line spec ${JSON.stringify(claim.lineSpec)}`,
      })
      continue
    }
    const fileText = readFileSync(resolved, 'utf8')
    const maxLine = Math.max(...ranges.map(([, end]) => end))
    const lineCount = fileText.split('\n').length
    // The hole T595 was written to close: `findInlineCodeClaims` skips every span `CITATION_RE`
    // already parsed, so `checkCitations`'s own out-of-range branch above (the one for
    // double-quoted citations) never sees this claim — it has to be caught here or nowhere. It
    // used to be a bare `continue`, dropped from every count with the run still exiting 0; it is a
    // failure now, with its own counter, mirroring the double-quoted branch's own reason text.
    if (maxLine > lineCount) {
      inlineClaimOutOfRangeCount++
      failures.push({
        raw: claim.raw,
        reason: `inline-code claim ${JSON.stringify(claim.claim)}: ${relPath(resolved)} has ${lineCount} lines, cited up to :${maxLine}`,
      })
      continue
    }
    if (!matchQuoteAgainstText(claim.claim, fileText, ranges)) {
      inlineClaimFailureCount++
      failures.push({
        raw: claim.raw,
        reason: `inline-code claim ${JSON.stringify(claim.claim)} not found at ${relPath(resolved)}:${claim.lineSpec}`,
      })
      continue
    }
    inlineClaimVerifiedCount++
  }
  // Every branch of the loop above increments exactly one of these five counters before its
  // `continue` (or falls through to `inlineClaimVerifiedCount++`), so their sum must equal
  // `inlineClaims.length`. This is not restating that arithmetic for its own sake: it is the
  // guard against the next silent `continue`. Both branches T595 closed here were a `continue`
  // added to this loop with no counter and no failure behind it, and the run kept exiting 0 —
  // this assertion is what makes that shape fail the moment it is written again, instead of
  // waiting for someone to notice the claim went missing from every count.
  const inlineClaimCountSum =
    inlineClaimVerifiedCount +
    inlineClaimFailureCount +
    inlineClaimUnresolvableCount +
    inlineClaimOutOfRangeCount +
    inlineClaimMalformedLineSpecCount
  if (inlineClaimCountSum !== inlineClaims.length) {
    failures.push({
      raw: '(inline-claim count)',
      reason:
        `inline-code claim counts (${inlineClaimVerifiedCount} verified + ` +
        `${inlineClaimFailureCount} mismatch + ${inlineClaimUnresolvableCount} unresolvable + ` +
        `${inlineClaimOutOfRangeCount} out of range + ${inlineClaimMalformedLineSpecCount} ` +
        `malformed line spec = ${inlineClaimCountSum}) do not sum to the ${inlineClaims.length} ` +
        'claims `findInlineCodeClaims` found — some branch of the loop dropped a claim without ' +
        'counting it',
    })
  }
  return {
    parsedCount: citations.length,
    unparsedQuoteCarryingCount: unparsed.length,
    inlineClaimCount: inlineClaims.length,
    inlineClaimVerifiedCount,
    inlineClaimUnresolvableCount,
    inlineClaimFailureCount,
    inlineClaimOutOfRangeCount,
    inlineClaimMalformedLineSpecCount,
    failures,
  }
}

// Item 2 of the row-8 sweep's own remediation: "have the checker assert each row's count equals
// the number of quoted citations in that row." 8c's own table is the only place `Handoffs` is a
// number a reader could compare against something — one row per spec file, its own citations
// never repeated table-scoped in 8d/8e (which cite the *same* line again in full-path form to
// stand alone, `structural-tier.md:441` rather than bare `:441`, so they don't re-inflate a table
// row's own count here). Fails per file when the printed number and the parsed count disagree, and
// once more when their sum disagrees with the `**Total: N handoffs**` line.
export function checkHandoffTally(readmeText) {
  const scopeText = extractCitationScope(readmeText)
  if (scopeText === null)
    return { failures: [{ reason: '8c/8c-bis/8d/8e scope markers not found' }] }
  const citations = parseCitations(scopeText)
  const perFile = new Map()
  for (const c of citations) {
    if (c.location === null && c.tableContext && c.tableContext.kind === 'md') {
      perFile.set(c.tableContext.name, (perFile.get(c.tableContext.name) ?? 0) + 1)
    }
  }
  const failures = []
  const rowRe = /^\|\s*`([\w-]+\.md)`\s*\|\s*(\d+)\s*\|/gm
  let rowMatch
  let printedSum = 0
  const seenFiles = new Set()
  while ((rowMatch = rowRe.exec(scopeText))) {
    const [, file, printedStr] = rowMatch
    const printed = Number(printedStr)
    printedSum += printed
    seenFiles.add(file)
    const parsed = perFile.get(file) ?? 0
    if (printed !== parsed) {
      failures.push({
        reason: `${file}'s own Handoffs cell reads ${printed} but ${parsed} quoted citation(s) were found for it in 8c's table`,
      })
    }
  }
  for (const file of perFile.keys()) {
    if (!seenFiles.has(file)) {
      failures.push({ reason: `${file} has quoted citations but no row in 8c's own table` })
    }
  }
  const totalMatch = scopeText.match(/\*\*Total:\s*(\d+)\s*handoffs/)
  if (!totalMatch) {
    failures.push({ reason: 'no "**Total: N handoffs**" line found to check the sum against' })
  } else if (Number(totalMatch[1]) !== printedSum) {
    failures.push({
      reason: `"**Total: ${totalMatch[1]} handoffs**" disagrees with the table's own row sum, ${printedSum}`,
    })
  }
  return { failures }
}

// --- 8c-bis vocabulary sweep (item 3 of the row-8 sweep's own remediation) ---------------------
//
// 8c-bis's own closing claim — "no component outside this list carries any deferral language in
// its own `*.stories.tsx`" — was false three times over before this pass (`Section`, `Callout`,
// `Text`). Read, by hand, is exactly the shape that keeps failing; this greps every
// `*.stories.tsx` under this package's own three tiers for the vocabulary 8c-bis itself names, and
// fails when a hit's component is neither a row in 8c-bis's own table nor named in its own
// exclusion paragraph — so the next hit is a build failure, not a fifth review pass.
//
// Widened by `reviewer`'s fourth REJECT on PR #80, which found ordinary deferral wording the
// original list missed entirely: `owned entirely by` (an intervening word breaks the plain `owned
// by` phrase — `SignInScreen.stories.tsx:79`, `FavouriteToggle.stories.tsx:103`) and a possessive
// attribution, `` are `X`'s `` (`ProfileSummary.stories.tsx:496`'s own "are `Menu`'s stories",
// already quoted and judged false by row 8 itself — the sweep just never independently found it).
// Four more shapes carry no live instance today but are named because the class of phrasing is the
// point, not today's inventory: `` live in `X`'s own ``, `deferred to `X` ``, `` `X`'s stories for
// ``, `` inherits `X`'s ``.
//
// Widened again (T594 B3, REJECT #5 on #80/#79): `owns`/`owned` had no bare alternative — only
// `owned by` — so "The enclosing row's own link owns the hover fill." (`PlayerColourSwatch`,
// `CivilisationIcon`, `MapThumbnail` — the identical sentence filed on the spec side in 8c but
// never carried to the story side) went uncaught. `\bowns?\b`/`\bowned\b` close that. The singular
// `` is `X`'s `` joins the plural `` are `X`'s `` already above (`SiteHeader.stories.tsx:198`'s own
// "that state is `Menu`'s to answer").
export const DEFERRAL_VOCABULARY_RE =
  /per `[A-Za-z]+`|owned (?:entirely )?by|\bowns\b|\bowned\b|belongs? to|covered by|already covered|follows? .{0,20}states|carr(?:y|ies) (?:its|their) own|(?:are|is) `[A-Za-z]+`'s\b|live in `[A-Za-z]+`'s own|deferred to `[A-Za-z]+`|`[A-Za-z]+`'s stories for|inherits `[A-Za-z]+`'s/g

// A file's own "prose blocks" — maximal runs of non-blank lines — so a phrase this vocabulary
// crosses a line boundary is never invisible only because prettier wrapped a comment or a rendered
// `<p>`'s own text run split it (`reviewer`'s fourth REJECT, item 2: "make it latent-proof by
// matching across a comment block or joining continuation lines"). No wrapped instance exists in
// this tree today; this is what keeps the next one from being a fifth review pass. These blocks
// also give `checkDeferralVocabularyCoverage` below the unit it excuses a hit at — a table
// citation commonly quotes one clause of a longer comment-and-rendered-text claim (`AccountErasurePanel`'s
// own privacy-data-rights.md paragraph, 101-135, cites only `:106`/`:123-124`), so matching at the
// bare physical line the old, component-level check never had to distinguish would fail most of
// this package's own existing, honest deferral prose.
function splitIntoProseBlocks(text) {
  const lines = text.split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    if (lines[i].trim() === '') {
      i++
      continue
    }
    const startLine = i
    let end = i
    while (end + 1 < lines.length && lines[end + 1].trim() !== '') end++
    blocks.push({
      startLine: startLine + 1,
      endLine: end + 1,
      text: lines.slice(startLine, end + 1),
    })
    i = end + 1
  }
  return blocks
}

export function findDeferralHitsInStories(allSrcFiles) {
  const hits = []
  for (const file of allSrcFiles) {
    if (!file.endsWith('.stories.tsx')) continue
    const segMatch = file.match(/\/src\/(primitives|composites|screens)\/([A-Za-z0-9]+)\//)
    if (!segMatch) continue
    const component = segMatch[2]
    const text = readFileSync(file, 'utf8')
    for (const block of splitIntoProseBlocks(text)) {
      // Joined with real `\n`s first, then flattened to spaces for the regex — `parseCitations`'
      // own idiom (`:2559` above) — so a match's character offset still recovers its own physical
      // line by counting the newlines the *joined* text carries before it.
      const joined = block.text.join('\n')
      const flat = joined.replace(/\n/g, ' ')
      DEFERRAL_VOCABULARY_RE.lastIndex = 0
      let m
      while ((m = DEFERRAL_VOCABULARY_RE.exec(flat))) {
        const lineOffset = joined.slice(0, m.index).split('\n').length - 1
        const physicalLine = block.startLine + lineOffset
        hits.push({
          component,
          file,
          line: physicalLine,
          blockStart: block.startLine,
          blockEnd: block.endLine,
          text: (block.text[lineOffset] ?? flat).trim(),
        })
      }
    }
  }
  return hits
}

export function checkDeferralVocabularyCoverage(
  readmeText,
  { allSrcFiles: injectedSrcFiles } = {},
) {
  const start = readmeText.indexOf('**8c-bis.')
  const end = readmeText.indexOf('**8d.')
  if (start === -1 || end === -1 || end < start) {
    return { failures: [{ reason: '8c-bis section markers not found' }] }
  }
  const sectionText = readmeText.slice(start, end)
  const citations = parseCitations(sectionText)
  // Every line either the table's own row for a component, or the exclusion paragraph after it,
  // cites for that component — table and exclusion citations feed the same per-component line
  // set, since either one is an equally real accounting of the hit.
  //
  // **Block membership plus a citation window, never block membership alone (T594 M4, REJECT #5 on
  // #80/#79; heading corrected in the row 8 sweep's own item 6 — it used to read "genuinely quote
  // level, not block level", the exact framing `README.md`'s own paragraph above retracts, while
  // this body already stated the real rule below it)**: this comment used
  // to claim "quote level, not component level" while the excuse condition below only ever checked
  // *block* membership — a whole prose block, and some of this package's own blocks run 30+ lines
  // (`AccountErasurePanel.stories.tsx` 101-135, `DataExportPanel.stories.tsx` 126-157). One
  // citation anywhere in a block that size excused every hit in it, including one a later edit adds
  // far from the citation that was supposed to account for it. A hit is now excused only when one
  // of that component's own cited lines is *both* in the hit's own block (never crossing a blank
  // line — a component's own comment routinely spans several blocks a single table citation cannot
  // each name on its own, `Text`'s own `disabled`-vocabulary block a second, separate block from
  // its table row's own citations) *and* within `DEFERRAL_CITATION_WINDOW` physical lines of the
  // hit itself — close enough that the citation is plausibly accounting for *this* clause, not
  // merely present somewhere in the same multi-paragraph comment.
  const DEFERRAL_CITATION_WINDOW = 15
  const citedLinesByComponent = new Map()
  const addCitedLines = (component, lineSpec) => {
    const ranges = parseLineSpec(lineSpec) ?? []
    const lines = citedLinesByComponent.get(component) ?? new Set()
    for (const [startLine, endLine] of ranges) {
      for (let l = startLine; l <= endLine; l++) lines.add(l)
    }
    citedLinesByComponent.set(component, lines)
  }
  for (const c of citations) {
    if (c.location === null && c.tableContext && c.tableContext.kind === 'stories') {
      addCitedLines(c.tableContext.name.replace(/\.stories\.tsx$/, ''), c.lineSpec)
    } else if (c.location && c.location.endsWith('.stories.tsx')) {
      addCitedLines(path.basename(c.location, '.stories.tsx'), c.lineSpec)
    }
  }
  const allSrcFiles =
    injectedSrcFiles ?? walkAllTsxFiles(srcDir).map((f) => f.split(path.sep).join('/'))
  const hits = findDeferralHitsInStories(allSrcFiles)
  const failures = []
  for (const hit of hits) {
    const citedLines = citedLinesByComponent.get(hit.component)
    const quoteCited =
      citedLines &&
      Array.from(citedLines).some(
        (l) =>
          l >= hit.blockStart &&
          l <= hit.blockEnd &&
          Math.abs(l - hit.line) <= DEFERRAL_CITATION_WINDOW,
      )
    if (quoteCited) continue
    failures.push({
      reason:
        `${hit.component}.stories.tsx:${hit.line} carries deferral vocabulary ` +
        `(${JSON.stringify(hit.text.slice(0, 80))}) but is neither within a cited line's own ` +
        "prose block in 8c-bis's own table nor named in its own exclusion paragraph",
    })
  }
  // T594's row 8 sweep, item 7: `README.md`'s own prose used to hand-type "Eighteen components
  // carry at least one" with no tripwire of its own — correct the day it was written, silently
  // wrong the next time a row was added or dropped. Printed instead: the 8c-bis table's own row
  // count, one `| \`Component\` | ... |` line per real, judged citation — never the wider set of
  // every distinct `hit.component` this pass finds, which also includes components named only in
  // the exclusion paragraph below the table (`Badge`, `SiteHeader`'s `expansion` hit, `Menu`'s
  // `selection` hit and others) and were never meant to be part of this count.
  const tableRowCount = (sectionText.match(/^\|\s*`[A-Z][A-Za-z0-9]*`\s*\|/gm) ?? []).length
  return { failures, hitCount: hits.length, tableRowCount }
}

// --- Cell-count tallies (item 4 of the row-8 sweep's own remediation) --------------------------
//
// Row 8's own prose used to restate Record 1's and Record 3's cell counts by hand (T594's Amended
// text bans exactly this: "Counts the script prints are cited, never restated in prose"), and
// every restated triple this branch has carried was wrong at least once. This prints the count
// instead, computed the same way both times a cell is rendered — from `el.coveredBy`
// (Record 1) and each matrix row's own `hover`/`focusVisible`/`active`/`disabled`/`rest` fields
// (Record 3) — so there is exactly one place a cell's classification is decided.
//
// A cell counts as the value it renders — `'none'` only for the literal `['none']`, `'unresolved'`
// for any `'unresolved: <reason>'` whatever the reason, `'covered'` otherwise. This used to fold
// every non-`play-driven` `unresolved` into `'none'`, on the reasoning that both state "no proof of
// any frame for this state." The orchestrator rejected that: `'none'` is a confirmed absence, a gap
// T595 must close; `'unresolved'` is this script declining to decide, and no finding may claim a
// gap from it — the distinction row 8's own Method section exists to defend, and this tally is not
// the one place allowed to erase it again. Count what the region actually renders; a reader who
// wants "how many gaps and how many undecided" reads two numbers, not one merged into the other.
function classifyCoverage(list) {
  if (Array.isArray(list) && list.length === 1 && list[0] === 'none') return 'none'
  const joined = Array.isArray(list) ? list.join('; ') : String(list)
  if (joined.includes('unresolved:')) return 'unresolved'
  return 'covered'
}

// Record 1's own left half — `stateCell`'s own `cls`, whether resolving the element's `className`
// found a pseudo-class utility, found none, or could not resolve the expression at all — classified
// the identical three ways, mirroring `stateCell`'s own rule (`classText ?? (classResolved ? 'none'
// : 'unresolved: …')`) rather than re-deriving it, so the two can never drift apart.
function classifyClassHalf(classText, classResolved) {
  if (classText != null) return 'covered'
  return classResolved ? 'none' : 'unresolved'
}

// Record 1: every local element's own hover/focus-visible/active cell (never `rest`, which
// Record 1 does not track — "8c" above: "Record 1 tracks hover/focus-visible/active only"). A cell
// renders two halves, `class → story`, and both are counted — not `el.coveredBy` alone, which the
// orchestrator's fifth REJECT (row 8's own recount, this pass) found undercounted `unresolved`:
// eight cells render `unresolved: className not fully resolved` on their own left half while their
// right half (`el.coveredBy`) independently reads `none` (five) or a real story (three) — the
// element's own class expression was never resolved, so neither reading is knowledge this pass
// actually has. A cell whose class half is `unresolved` is an `unresolved` cell regardless of what
// its story half says; otherwise the story half alone decides, exactly as before.
export function countRecord1Cells(computed) {
  const counts = { none: 0, unresolved: 0, covered: 0 }
  for (const { elements } of computed.localElements) {
    for (const el of elements) {
      const classResolved = (el.classUnresolvedRefs ?? []).length === 0
      const pairs = [
        [el.hover, el.coveredBy.hover],
        [combineFocusClassText(el.focus, el.focusVisible), el.coveredBy.focusVisible],
        [el.active, el.coveredBy.active],
      ]
      for (const [classText, coverageList] of pairs) {
        const classHalf = classifyClassHalf(classText, classResolved)
        counts[classHalf === 'unresolved' ? 'unresolved' : classifyCoverage(coverageList)]++
      }
    }
  }
  return counts
}

// Record 3: every primitive matrix's own real row (excluding the `(no local interactive
// element)` placeholder and the `(unresolved matches — no row, printed rather than dropped)`
// information row, neither of which is a variant/size combination FR-042 asks a cell of) across
// all five of its own states — `rest`, `hover`, `focus-visible`, `press` (`active`) and
// `disabled` — the matrix's full FR-042 vocabulary, not Record 1's narrower three.
export function countRecord3Cells(computed) {
  const counts = { none: 0, unresolved: 0, covered: 0 }
  for (const rows of Object.values(computed.matrices)) {
    for (const row of rows) {
      if (row.variantSize === '(no local interactive element)') continue
      if (row.variantSize.startsWith('(unresolved matches')) continue
      counts[classifyCoverage(row.rest)]++
      counts[classifyCoverage(row.hover)]++
      counts[classifyCoverage(row.focusVisible)]++
      counts[classifyCoverage(row.active)]++
      counts[classifyCoverage(row.disabled)]++
    }
  }
  return counts
}

function formatCounts(counts) {
  const total = counts.none + counts.unresolved + counts.covered
  return `${counts.none} none / ${counts.unresolved} unresolved / ${counts.covered} covered (${total} cells)`
}

// Names the axes and the row unit each total is built from, so a reader can reproduce the count
// without inferring the convention from the two numbers alone — the omission that let a prior
// version fold `unresolved` into `none` silently.
export function logCellCounts(computed, logFn = log) {
  const r1 = countRecord1Cells(computed)
  const r3 = countRecord3Cells(computed)
  logFn(
    `record 1 cell counts (hover/focus-visible/active, one cell per state per local interactive ` +
      `element): ${formatCounts(r1)}`,
  )
  logFn(
    `record 3 cell counts (rest/hover/focus-visible/press/disabled, one cell per state per real ` +
      `primitive-matrix row — the "(no local interactive element)" and "(unresolved matches…)" ` +
      `rows excluded): ${formatCounts(r3)}`,
  )
  const amb = computed.ambiguitySummary
  logFn(
    `record 3 ambiguity tally (composed-story-ambiguous-variant): ${amb.instances} instances, ` +
      `${amb.events} distinct ambiguity events, ${amb.taintedCells} tainted (row, state) cells ` +
      `across ${amb.storyNames} distinct story names, of which ${amb.kept} keep the note and ` +
      `${amb.dropped} drop it (a real match elsewhere on the same row covers that state instead)`,
  )
  return { record1: r1, record3: r3, ambiguity: amb }
}

// --- main --------------------------------------------------------------------------------------

function readAllSourceFiles() {
  const componentDirs = listComponentDirs(srcDir)
  const filesByPath = new Map()
  for (const filePath of walkAllTsxFiles(srcDir)) {
    filesByPath.set(filePath, readFileSync(filePath, 'utf8'))
  }
  return { componentDirs, filesByPath }
}

function main() {
  const write = process.argv.includes('--write')
  const { componentDirs, filesByPath } = readAllSourceFiles()
  const computed = computeStateCoverage({ componentDirs, filesByPath })
  const freshRegion = renderGeneratedRegion(computed)

  let readmeText
  try {
    readmeText = readFileSync(readmePath, 'utf8')
  } catch {
    fail(`could not read ${relPath(readmePath)}.`)
    return
  }

  let candidateText
  try {
    candidateText = replaceGeneratedRegion(readmeText, freshRegion)
  } catch (err) {
    fail(err.message)
    return
  }
  const formatted = formatWithPrettier(candidateText)
  const formattedRegion = extractGeneratedRegion(formatted)

  if (write) {
    writeFileSync(readmePath, formatted)
    log(`wrote the generated region for ${computed.componentDirCount} component directories.`)
    logCellCounts(computed)
    return
  }

  const currentRegion = extractGeneratedRegion(readmeText)
  if (currentRegion === null) {
    fail(
      `${relPath(readmePath)} carries no ${BEGIN_MARKER}/${END_MARKER} region for row 8 (H5) to ` +
        'check against. Run with --write to create it.',
    )
    return
  }
  if (currentRegion !== formattedRegion) {
    fail(
      `row 8 (H5)'s generated region disagrees with a fresh render — run ` +
        '`node scripts/checks/state-coverage.mjs --write` and commit the result.',
    )
    console.error(diffLines(currentRegion, formattedRegion))
    return
  }

  log(
    `${computed.componentDirCount} component directories; row 8's generated region matches a fresh ` +
      'render — no drift.',
  )
  logCellCounts(computed)
}

function runCitationCheck() {
  let readmeText
  try {
    readmeText = readFileSync(readmePath, 'utf8')
  } catch {
    fail(`could not read ${relPath(readmePath)}.`)
    return
  }
  const result = checkCitations({ readmeText })
  for (const failure of result.failures) {
    console.error(`state-coverage: citation ${JSON.stringify(failure.raw)} — ${failure.reason}`)
  }
  const tally = checkHandoffTally(readmeText)
  for (const failure of tally.failures) {
    console.error(`state-coverage: handoff tally — ${failure.reason}`)
  }
  const vocab = checkDeferralVocabularyCoverage(readmeText)
  for (const failure of vocab.failures) {
    console.error(`state-coverage: 8c-bis vocabulary — ${failure.reason}`)
  }
  // Printed on every run, pass or fail, so silence can never pass for scope: how many
  // `` `location:line` `` spans in row 8's own citation prose actually parsed as citations, and how
  // many more, outside that recognised format, still carry a quote close enough to need one.
  log(
    `${result.parsedCount} \`file:line\` spans parsed as citations; ` +
      `${result.unparsedQuoteCarryingCount} more, outside the recognised citation format, still ` +
      'carry a nearby quote (each of those is also a failure above, not merely a count).',
  )
  // T594's REJECT on #80, item 1: this used to print "found and verified" for every claim
  // `findInlineCodeClaims` returned, whether or not this loop actually checked it — a bare
  // location silently skipped the whole comparison and still reported as verified. Five numbers
  // now, none folded into another: `found` is what the extractor returned, `verified` is what this
  // pass actually confirmed matches its own cited line, `unresolvable` is a location this pass
  // could not resolve to one file at all, `out of range` is a cited line past the end of its file
  // (T595) and `malformed line spec` is a line spec that did not parse at all (T595) — the four
  // failing kinds are kept apart only so a reader can tell "wrong place" from "wrong text" from
  // "past the end" from "unparseable", and `checkCitations` itself asserts the five sum to `found`.
  log(
    `${result.inlineClaimCount} inline-code claims next to a \`file:line\` found (T594 M2/M3); ` +
      `${result.inlineClaimVerifiedCount} verified, ${result.inlineClaimUnresolvableCount} ` +
      `unresolvable, ${result.inlineClaimFailureCount} content mismatch, ` +
      `${result.inlineClaimOutOfRangeCount} out of range, ` +
      `${result.inlineClaimMalformedLineSpecCount} malformed line spec (unresolvable, mismatch, ` +
      'out of range and malformed line spec are each also a failure above, not merely a count).',
  )
  if (result.failures.length > 0 || tally.failures.length > 0 || vocab.failures.length > 0) {
    fail(
      `${result.failures.length} of ${result.parsedCount} row-8 citations failed verification, ` +
        `${tally.failures.length} handoff-tally mismatch(es), ${vocab.failures.length} ` +
        'uncovered 8c-bis deferral hit(s) (see above).',
    )
    return
  }
  log(`${result.parsedCount} row-8 citations parsed and verified against their own file:line.`)
  log("8c's own per-file Handoffs counts and total agree with its own quoted citations.")
  log(
    `${vocab.hitCount} deferral-vocabulary hits across every *.stories.tsx; every one is either a ` +
      "row in 8c-bis's own table (currently " +
      `${vocab.tableRowCount} rows, one per component) or named in its own exclusion paragraph.`,
  )
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (process.argv.includes('--check-citations')) {
    runCitationCheck()
  } else {
    main()
  }
}
