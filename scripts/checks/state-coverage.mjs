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
//                                                      (printing a diff).
//   node scripts/checks/state-coverage.mjs --write     regenerates the region in place, formatted
//                                                      through prettier so check mode never sees a
//                                                      prettier-only difference.
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
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

const PSEUDO_PREFIXES = ['hover', 'focus-visible', 'active']

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

const INTERACTIVE_TAGS = new Set(['a', 'button', 'input', 'select', 'textarea', 'summary', 'label'])
const INTRINSIC_ROLE = {
  a: 'link',
  button: 'button',
  input: 'textbox',
  select: 'combobox',
  textarea: 'textbox',
  summary: 'button',
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
//
// `locals`: `[name, initializerExprNode][]` in declaration order, for evaluating a JSX attribute or
// guard expression that references a local (`Dialog`'s own `bounded`, if it had one) rather than a
// prop directly — resolved against the same scope the guards are.
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
    let locals = ctx.locals
    for (const stmt of statements) {
      if (ts.isVariableStatement(stmt)) {
        const newLocals = []
        for (const decl of stmt.declarationList.declarations) {
          if (ts.isIdentifier(decl.name) && decl.initializer) {
            newLocals.push([decl.name.text, decl.initializer])
            visit(decl.initializer, { ...ctx, guards, locals })
          }
        }
        locals = [...locals, ...newLocals]
      } else if (ts.isIfStatement(stmt)) {
        const cond = stmt.expression
        const thenStmts = statementsOf(stmt.thenStatement)
        visitBlockStatements(thenStmts, {
          ...ctx,
          guards: [...guards, { expr: cond, truthy: true }],
          locals,
        })
        if (stmt.elseStatement) {
          const elseStmts = ts.isIfStatement(stmt.elseStatement)
            ? [stmt.elseStatement]
            : statementsOf(stmt.elseStatement)
          visitBlockStatements(elseStmts, {
            ...ctx,
            guards: [...guards, { expr: cond, truthy: false }],
            locals,
          })
        } else if (blockAlwaysExits(thenStmts)) {
          guards = [...guards, { expr: cond, truthy: false }]
        }
      } else if (ts.isReturnStatement(stmt)) {
        if (stmt.expression) visit(stmt.expression, { ...ctx, guards, locals })
        return
      } else {
        visit(stmt, { ...ctx, guards, locals })
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
      nextCtx = { ...ctx, fnName: node.name.text, guards: [], locals: [] }
    } else if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.initializer &&
      (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer))
    ) {
      // The name lives on the declaration; the fresh function scope starts at the initializer
      // itself (visited next via forEachChild), which is where `guards`/`locals` should reset —
      // done by threading the reset through this same `nextCtx`, since forEachChild's next call is
      // exactly that initializer.
      nextCtx = { ...ctx, fnName: node.name.text, guards: [], locals: [] }
    }
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      (node.expression.name.text === 'map' || node.expression.name.text === 'flatMap')
    ) {
      nextCtx = { ...nextCtx, inIteration: true }
    }
    ts.forEachChild(node, (child) => visit(child, nextCtx))
  }
  visit(sourceFile, { fnName: null, inIteration: false, guards: [], locals: [] })
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

// --- Record 1: local interactive elements -------------------------------------------------------

// `mainComponentName`: the directory's own component name (`PrivacyNotice`) — an element whose
// nearest enclosing named function is anything *else* (`InlineLink`, `SectionHeading`) is a reusable
// local helper invoked from more than one place this static pass cannot enumerate, so its recorded
// line is a declaration site, not a real render position (`isHelper: true`, excluded from `nth`
// resolution below, never from Record 1's own listing).
export function findLocalElements(sourceFile, filePath, constMap, mainComponentName = null) {
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
    const hasPseudo = pseudo.hover || pseudo['focus-visible'] || pseudo.active
    const isIntrinsicInteractive = INTERACTIVE_TAGS.has(tagName)
    const isRoleInteractive =
      roleAttr.literal && (roleAttr.value === 'button' || roleAttr.value === 'link')
    const isTabIndexed = tabIndexAttr.present
    if (!(isIntrinsicInteractive || isRoleInteractive || isTabIndexed || hasPseudo)) return
    found.push({
      file: filePath,
      line: lineOf(sourceFile, node),
      tag: tagName,
      role: roleAttr.literal ? roleAttr.value : roleAttr.present ? 'unresolved' : null,
      tabIndex: tabIndexAttr.present
        ? tabIndexAttr.literal
          ? tabIndexAttr.value
          : 'unresolved'
        : null,
      hover: pseudo.hover,
      focusVisible: pseudo['focus-visible'],
      active: pseudo.active,
      classUnresolvedRefs: unresolved,
      text: literalTextOf(node),
      ariaHidden: isAriaHidden(opening),
      isHelper: context.fnName != null && context.fnName !== mainComponentName,
      isInsideIteration: context.inIteration,
      guards: context.guards,
      locals: context.locals,
    })
  })
  return found
}

// --- Record 3: primitive instances --------------------------------------------------------------

export const PRIMITIVE_NAMES = ['Button', 'Link', 'Field', 'Menu']

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
      disabled: attrLiteral(getAttr(opening, 'disabled')).value === true,
      text: literalTextOf(node),
      childrenExpr: !literalTextOf(node) && ts.isJsxElement(node) ? node.children : null,
      ariaHidden: isAriaHidden(opening),
      isHelper: context.fnName != null,
      isInsideIteration: context.inIteration,
      guards: effectiveGuards,
      locals: context.locals,
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
    if (candidate.text && candidate.text.includes(name)) return 'match'
    const directTextMatches = pool.filter((c) => c.text && c.text.includes(name))
    if (directTextMatches.length > 0) return 'reject'
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
    return 'reject'
  }
  if (nth != null) {
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

  for (const filePath of allFiles) {
    const isStory = filePath.endsWith('.stories.tsx')
    const isTest = filePath.endsWith('.test.tsx')
    if (isTest) continue
    const sourceFile = sourceFiles.get(filePath)
    const constMap = buildConstStringMap(sourceFile)
    const componentKey = componentKeyForFile(srcDir, filePath)
    const componentDirName = componentKey.split('/')[1]

    if (!isStory) {
      const locals = findLocalElements(sourceFile, relPath(filePath), constMap, componentDirName)
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
      const entries = storyObjs.map(({ exportName, node }) => {
        const forced = extractVisualForceState(node)
        const playBody = resolvePlayBody(node, sourceFile)
        const playFocus = forced ? null : findPlayFocusTarget(playBody)
        const argsLiterals = storyArgsStringLiterals(metaObj, node, storyConstNodeMap)
        return { exportName, forced, playFocus, argsLiterals }
      })
      storyStatesByComponent.set(componentKey, [
        ...(storyStatesByComponent.get(componentKey) ?? []),
        ...entries,
      ])
    }

    if (isStory && ownPrimitive && PRIMITIVE_NAMES.includes(ownPrimitive)) {
      const defaults = defaultsByPrimitive[ownPrimitive] ?? {}
      for (const { exportName, node } of storyObjs) {
        const axis = resolveStoryAxisValues(metaObj, node, defaults)
        const forced = extractVisualForceState(node)
        const playBody = resolvePlayBody(node, sourceFile)
        const playFocus = forced ? null : findPlayFocusTarget(playBody)
        instancesByPrimitive.get(ownPrimitive).push({
          primitive: ownPrimitive,
          kind: 'own-story',
          componentKey,
          file: relPath(filePath),
          storyName: exportName,
          variant: axis.variant ?? { value: null, resolved: 'n/a' },
          size: axis.size ?? { value: null, resolved: 'n/a' },
          forced,
          playFocus,
        })
      }
    } else if (isStory) {
      const storyFileScope = buildFileValueScope(sourceFile)
      for (const { exportName, node } of storyObjs) {
        const forced = extractVisualForceState(node)
        if (!forced) continue
        const storyStartLine =
          sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
        const storyEndLine = sourceFile.getLineAndCharacterOfPosition(node.getEnd()).line + 1
        const argsLiterals = storyArgsStringLiterals(metaObj, node, storyConstNodeMap)
        const mergedArgs = evaluateMergedArgsObject(metaObj, node, storyFileScope)
        const propsScope = buildStoryPropsScope(
          componentPropDefaultsByKey.get(componentKey) ?? new Map(),
          mergedArgs,
          componentFileScopeByKey.get(componentKey) ?? storyFileScope,
        )
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

  const localElements = [...localElementsByComponent.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([componentKey, elements]) => {
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

  return { componentDirCount: componentDirs.length, localElements, matrices }
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
      const implied = INTRINSIC_ROLE[primitive.toLowerCase()] ?? null
      const roleMatches = candidates.filter(
        (c) => forced.role === 'button' || forced.role === implied,
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
      for (const candidate of resolvedPool) {
        const verdict = resolveNameMatch({
          candidate,
          pool: resolvedPool,
          name: forced.name,
          nth: forced.nth,
          argsLiterals,
        })
        if (verdict === 'match') matchedCandidate = candidate
        if (verdict === 'ambiguous') ambiguous = true
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
        })
      } else if (ambiguous) {
        instancesByPrimitive.get(primitive).push({
          primitive,
          kind: 'composed-story-unresolved',
          componentKey,
          file,
          storyName: exportName,
          forced,
          reason: `state ${JSON.stringify(forced.state)}: ${roleMatches.length} ${primitive} instances in ${componentKey} match role ${JSON.stringify(forced.role)}${forced.name ? ` / name ${JSON.stringify(forced.name)}` : ''}${forced.nth != null ? ` / nth ${forced.nth}` : ''}, none uniquely resolved${roleMatches.some((c) => c.unresolvedGuard) ? " (at least one candidate's own guard could not be evaluated from this story's args)" : ''}`,
        })
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
        hover: [],
        'focus-visible': [],
        active: [],
        disabled: [],
        forcedRoles: [],
      })
    }
    return rows.get(key)
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
      if (inst.disabled) row.disabled.push(`${inst.componentKey} (${inst.file}:${inst.line})`)
      continue
    }
    const label = cellName(inst)
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
      row['focus-visible'].push(`${label} (play-driven: ${JSON.stringify(inst.playFocus)})`)
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
    .map((row) => ({
      variantSize: row.key,
      rest: row.rest.length ? [...new Set(row.rest)] : ['none'],
      hover: row.hover.length ? [...new Set(row.hover)] : ['none'],
      focusVisible: row['focus-visible'].length ? [...new Set(row['focus-visible'])] : ['none'],
      active: row.active.length ? [...new Set(row.active)] : ['none'],
      disabled: row.disabled.length ? [...new Set(row.disabled)] : ['none'],
      forcedRoles: row.forcedRoles.sort(
        (a, b) => a.state.localeCompare(b.state) || String(a.role).localeCompare(String(b.role)),
      ),
    }))
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
  // A `role` attribute that is *present but dynamic* (`MenuItemRow`'s own
  // `role={variant === 'selection' ? 'menuitemradio' : 'menuitem'}`) overrides the tag's intrinsic
  // role at render time, whatever it resolves to — falling back to the intrinsic role here would
  // wrongly pool a `<button role={...}>` whose real role is never `'button'` with elements that
  // really do render as plain buttons (`Menu`'s own trigger), inventing an ambiguity between two
  // elements that can never actually share a role. `null` excludes it from every implied-role pool
  // instead — correct, and harmless here: a dynamic-role element's own coverage is read from the
  // primitive's own variant matrix (`forcedRoles`), which is not blind to it, this record-1 view.
  const impliedRoleOf = (el) =>
    el.role === 'unresolved' ? null : el.role || (INTRINSIC_ROLE[el.tag] ?? null)
  return elements.map((el) => {
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
          if (verdict === 'match') cells['focus-visible'].push(`${exportName} (play-driven)`)
          else if (verdict === 'ambiguous') {
            ambiguousReasons['focus-visible'].push(
              `${exportName} (play-driven): ${pool.length} candidates share role ${JSON.stringify(impliedRole)}`,
            )
          }
        }
      }
    }
    const cellFor = (state) =>
      cells[state].length > 0
        ? [...new Set(cells[state])]
        : ambiguousReasons[state].length > 0
          ? [`unresolved: ${ambiguousReasons[state].join('; ')}`]
          : ['none']
    return {
      variantSize: `${el.tag}${el.role ? `[role=${el.role}]` : ''}${el.ariaHidden ? '[aria-hidden]' : ''} @ ${el.file}:${el.line}`,
      rest: [`${el.file}:${el.line}`],
      hover: cellFor('hover'),
      focusVisible: cellFor('focus-visible'),
      active: cellFor('active'),
      disabled: ['none'],
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

function stateCell(classText, coverageList) {
  const cls = classText ?? 'none'
  const coverage = coverageList.join('; ')
  return `${cls} → ${coverage}`
}

export function renderRecord1(computed) {
  const rows = []
  for (const { componentKey, elements } of computed.localElements) {
    for (const el of elements) {
      rows.push([
        componentKey,
        `${el.tag}${el.role ? `[role=${el.role}]` : ''}${el.tabIndex !== null ? `[tabIndex=${el.tabIndex}]` : ''}${el.ariaHidden ? '[aria-hidden]' : ''}`,
        `${el.file}:${el.line}`,
        stateCell(el.hover, el.coveredBy.hover),
        stateCell(el.focusVisible, el.coveredBy.focusVisible),
        stateCell(el.active, el.coveredBy.active),
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
    return
  }

  log(
    `${computed.componentDirCount} component directories; row 8's generated region matches a fresh ` +
      'render — no drift.',
  )
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
