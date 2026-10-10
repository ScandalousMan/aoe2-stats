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
// What this file computes — Record 1: every interactive element a component renders locally, with its
// hover/focus-visible/active classes and which story (or `none`, confirmed, or `unresolved`, with a
// reason) depicts each state. Record 3: every Button, Link, Field and Menu instance in source and in
// stories, resolved against the primitive's own defaults when a prop is omitted, and the primitive's
// own variant/size (or structural-element) matrix.
//
// T694 (2026-10-04): which story depicts which state is read from what a real browser rendered, not
// guessed from source. `packages/design-system/specs/state-coverage-runtime.json` (T693) records, per
// story, the element a force located (its source stamp), the tracked primitive instance that placed
// it and the instances the story mounts; `computeStateCoverage` takes that manifest as an input and
// `resolveRuntimeForce` decides each forced story's credit. What stays static is named in
// `REGION_LEGEND`, printed in the region itself.
//
// Records 2 (handoff prose) and 4 (false self-claims) stay read by a person against this file's
// output — sentences in specs/*.md and in a story's own comment or rendered text, not a structural
// fact a parser can lift.
//
// Usage (reads the committed manifest, so it needs no build; a story with no entry fails it):
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
import {
  collectModuleSpecifiers,
  findNonLiteralSpecifiers,
  unwrapExpression,
} from '../visual/module-specifiers.mjs'
import { BUILD_STORYBOOK_COMMAND } from '../visual/missing-index.mjs'
import { REVIEW_WIDTHS } from '../visual/review-widths.mjs'
import { FIXTURE_TAG } from '../visual/story-index.mjs'
import {
  MANIFEST_PATH,
  REWRITE_COMMAND,
  parseManifest,
} from '../visual/state-coverage-runtime-model.mjs'
import {
  parseIndexTable,
  findComponentSection,
  isClauseLeadingBoldSpan,
  normaliseStateToken,
  deriveVocabulary,
} from './spec-completeness.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const dsDir = path.join(rootDir, 'packages', 'design-system')
const srcDir = path.join(dsDir, 'src')
const specsDir = path.join(dsDir, 'specs')
const readmePath = path.join(dsDir, 'specs', 'README.md')
const prettierBin = path.join(rootDir, 'node_modules', '.bin', 'prettier')

// `typescript` is a direct devDependency of packages/design-system, not of the workspace root —
// resolved through that package's own node_modules rather than adding a second copy at the root.
const dsRequire = createRequire(path.join(dsDir, 'package.json'))
const ts = dsRequire('typescript')

// The specifier reader moved to `scripts/visual/module-specifiers.mjs` (T707), shared with the story
// selection; these two keep their old public names here.
export { findNonLiteralSpecifiers, unwrapExpression }

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

// T595 (row 8, H5, the `className not fully resolved` family): `resolveClassParts` used to have
// exactly one namespace to resolve an identifier against — `constMap`, module-top-level `const`s
// only — so a *function-local* `const` a className expression itself references (`Button`'s own
// `const classes = cx(...)`, the JSX attribute's real value) was never even attempted: the bare
// identifier `classes` fell straight to the catch-all, unresolved, and every fragment `classes`
// itself composes (a real, resolvable object-literal lookup and a real, resolvable conditional
// among them) stayed invisible behind it. `scopes` (default `null`, so every pre-T595 call site —
// `buildConstStringMap` below among them — keeps its exact prior behaviour unchanged) threads three
// additional, independent namespaces through every recursive call:
//   - `localConsts`: the function-local `const` bindings in scope at the JSX node's own position
//     (`walkJsxWithContext`'s own map, `context.localConsts` — the same read the dynamic-`role={…}`
//     resolution already relies on). Checked *before* `constMap`, matching real JS lexical scoping
//     (a local declaration shadows an outer one of the same name, never observed in this tree today
//     but the correct order regardless) — resolved by recursing into the local `const`'s own
//     initializer expression, through this same function, with this same identifier removed from
//     the scope handed to that recursive call (self-reference protection; no local `const` in this
//     codebase is self-referential, but a cycle must stay unresolved rather than loop forever).
//   - `defaultScope`: an `evaluateExpr`-shaped scope (`{ resolved, value }` per name) carrying the
//     owning component's own **default** `variant`/`size` value, when it destructures one
//     (`buildVariantSizeDefaultScope`, `findVariantSizeDefaults` reused rather than reinvented —
//     the exact default Record 3 already resolves an *omitted* prop to for its own axis matrix).
//     Consulted by two node shapes below, both only when a real default value settles them: an
//     `ElementAccessExpression` whose key is that prop (`variantClasses[variant]`) and a
//     `ConditionalExpression` whose condition is a real comparison against that prop
//     (`variant === 'primary' ? primaryFocusRing : focusRing`). **The decision this closes, stated
//     once here since both shapes share it**: `variant` is a real axis (record 3's own matrix
//     already carries every value it can take), and record 1 has no room for one — one row per
//     element, not one row per element per variant. Resolving `variantClasses[variant]` by
//     unioning *every* entry the object holds would compile and would be wrong: the combined string
//     is not the classes any single variant actually renders, which is exactly the "flattened,
//     true of none of them" shape this task was warned against. Resolving it against the
//     component's own **default** variant instead is not a guess: it is the one configuration a
//     bare `<Button className="…">` — the exact call this element's own `className` slot exists
//     for — actually renders as, the same "resting configuration" Record 3's own doc comment
//     already names ("resolved against the primitive's own defaults when a prop is omitted").
//     Record 1 documents that resting configuration; Record 3 still carries the full per-variant
//     breakdown for anyone who needs the rest. A component with no default for the prop the
//     expression keys on (`defaultScope` has no entry) leaves both shapes exactly as unresolved as
//     before — never guessed further.
//   - `objectConstMap`: every module-top-level `const NAME = { ... }` object literal, keyed by
//     `NAME` (`buildConstObjectMap`, Button's own `variantClasses`/`sizeClasses`) — the namespace
//     `ElementAccessExpression` resolves its own object against, parallel to how `constMap` already
//     serves a plain identifier.
export function resolveClassParts(expr, constMap, unresolved = [], scopes = null) {
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
    return resolveClassParts(expr.expression, constMap, unresolved, scopes)
  }
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    return [
      ...resolveClassParts(expr.left, constMap, unresolved, scopes),
      ...resolveClassParts(expr.right, constMap, unresolved, scopes),
    ]
  }
  // T595: `cond && 'classes'` — the left operand is a *condition*, never itself a class-string
  // fragment (`Table`'s own `href && 'border-l-2 … hover:bg-surface-sunken …'`). Resolving it as if
  // it might contribute text pushed a bare boolean identifier like `href` into `unresolved` for no
  // reason: this pass cannot know the condition's runtime value, so the right-hand class string is
  // already kept unconditionally (dual-branch-conservative, T594's own rule), and the left side was
  // never going to contribute anything a real capture renders — only ever a false "cannot resolve"
  // signal. `||`/`??` keep the prior dual-branch treatment: unlike `&&`, *either* side can be the
  // real rendered value depending on which one is truthy (`a || b`), so both stay real candidates,
  // the same conservative-superset treatment the ternary below still falls back to.
  if (
    ts.isBinaryExpression(expr) &&
    expr.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
  ) {
    return resolveClassParts(expr.right, constMap, unresolved, scopes)
  }
  if (
    ts.isBinaryExpression(expr) &&
    (expr.operatorToken.kind === ts.SyntaxKind.BarBarToken ||
      expr.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken)
  ) {
    return [
      ...resolveClassParts(expr.left, constMap, unresolved, scopes),
      ...resolveClassParts(expr.right, constMap, unresolved, scopes),
    ]
  }
  if (ts.isConditionalExpression(expr)) {
    // T595: when `scopes.defaultScope` actually settles the condition (`variant === 'primary'`
    // against the component's own default `variant`), only the branch that default really takes is
    // real — see this function's own top comment for why the other branch is not also included.
    if (scopes?.defaultScope) {
      const cond = evaluateExpr(expr.condition, scopes.defaultScope)
      if (cond.resolved) {
        return resolveClassParts(
          cond.value ? expr.whenTrue : expr.whenFalse,
          constMap,
          unresolved,
          scopes,
        )
      }
    }
    return [
      ...resolveClassParts(expr.whenTrue, constMap, unresolved, scopes),
      ...resolveClassParts(expr.whenFalse, constMap, unresolved, scopes),
    ]
  }
  if (ts.isArrayLiteralExpression(expr)) {
    return expr.elements.flatMap((el) => resolveClassParts(el, constMap, unresolved, scopes))
  }
  if (ts.isCallExpression(expr)) {
    const callee = expr.expression.getText()
    if (callee === 'cx' || callee === 'clsx') {
      return expr.arguments.flatMap((arg) => resolveClassParts(arg, constMap, unresolved, scopes))
    }
    unresolved.push(`<call:${callee}>`)
    return []
  }
  // T595: `variantClasses[variant]` — resolved only when the object is a known module-level object
  // literal (`scopes.objectConstMap`) *and* the key resolves against the component's own default
  // (`scopes.defaultScope`, this function's own top comment for the reasoning). Anything else (a
  // computed object, a key with no default to fall back on) stays unresolved, printed as the same
  // `<ElementAccessExpression>` shape the pre-T595 catch-all already produced for it — a shape this
  // pass still cannot reduce, not a guess dressed up as one.
  if (ts.isElementAccessExpression(expr)) {
    const objectName = ts.isIdentifier(expr.expression) ? expr.expression.text : null
    const objectLiteral =
      objectName && scopes?.objectConstMap ? scopes.objectConstMap.get(objectName) : null
    const key =
      objectLiteral && scopes?.defaultScope
        ? evaluateExpr(expr.argumentExpression, scopes.defaultScope)
        : UNRESOLVED
    if (objectLiteral && key.resolved) {
      const propNode = objectLiteral.properties.find(
        (p) => ts.isPropertyAssignment(p) && propertyKeyText(p.name) === key.value,
      )
      if (propNode) {
        return resolveClassParts(propNode.initializer, constMap, unresolved, scopes)
      }
    }
    unresolved.push('<ElementAccessExpression>')
    return []
  }
  if (ts.isIdentifier(expr)) {
    // T595: a function-local `const` in scope at this exact JSX position (`Button`'s own `classes`)
    // — checked before `constMap`, matching real lexical scoping (see this function's own top
    // comment). Resolved by recursing into its own initializer with itself removed from the scope
    // handed onward, so a genuine cycle stays unresolved rather than looping.
    if (scopes?.localConsts?.has(expr.text)) {
      const initializer = scopes.localConsts.get(expr.text)
      const nextLocalConsts = new Map(scopes.localConsts)
      nextLocalConsts.delete(expr.text)
      return resolveClassParts(initializer, constMap, unresolved, {
        ...scopes,
        localConsts: nextLocalConsts,
      })
    }
    if (constMap.has(expr.text)) return constMap.get(expr.text)
    // T595: `className` bare, resolved through neither namespace above, is this design system's
    // own universal "caller extension slot" — every primitive/composite/screen here declares
    // `className?: string` and forwards it as the trailing `cx(…, className)` argument (grepping
    // `className)` across `packages/design-system/src` finds the idiom on 25 of this file's own
    // sibling components, not a one-off). Its contents belong to the caller, never to this
    // component's own source, and record 1 already treated it exactly this way for every element
    // whose *other* fragments supply a real class for a given state (`MatchRow`/`PlayerResultRow`'s
    // own row link: the unresolved `className` was already invisible to `stateCell`'s own
    // classText-first priority). This closes the mirror case honestly: when nothing else this
    // component's own code declares paints a given state either, that is real, positive knowledge
    // of what this component's own source contributes — the caller-controlled remainder is out of
    // this register's own scope by the same convention already applied everywhere else, not a new
    // one invented for this case. Contributes no parts and is never pushed to `unresolved` — the one
    // identifier this branch does not treat as "this pass does not know".
    if (expr.text === 'className') return []
    unresolved.push(expr.text)
    return []
  }
  if (ts.isJsxExpression(expr) && expr.expression) {
    return resolveClassParts(expr.expression, constMap, unresolved, scopes)
  }
  unresolved.push(`<${ts.SyntaxKind[expr.kind] ?? 'expr'}>`)
  return []
}

function propertyKeyText(name) {
  if (ts.isIdentifier(name)) return name.text
  if (ts.isStringLiteral(name)) return name.text
  return null
}

// T595: every module-top-level `const NAME = { ... }` object literal (`Button`'s own
// `variantClasses`/`sizeClasses`), keyed by `NAME` — `resolveClassParts`'s own
// `ElementAccessExpression` branch resolves its object against this map, parallel to how `constMap`
// already serves a plain identifier reference. Kept to *object literals* only (never a computed or
// spread-built object), the same "found, never guessed" bar `buildConstStringMap` already holds
// its own module scan to.
export function buildConstObjectMap(sourceFile) {
  const map = new Map()
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || !decl.initializer) continue
      if (ts.isObjectLiteralExpression(decl.initializer)) {
        map.set(decl.name.text, decl.initializer)
      }
    }
  }
  return map
}

// T595: an `evaluateExpr`-shaped scope (`{ resolved, value }` per name) carrying only the two names
// `findVariantSizeDefaults` already extracts from this file's own component — `resolveClassParts`'s
// own top comment states the reasoning this rests on (record 1 documents the default/resting
// configuration; record 3 still owns the full per-variant/size axis). A component with no default
// for either prop leaves that name absent from the scope, not present with a guessed value.
export function buildVariantSizeDefaultScope(sourceFile) {
  const { variant, size } = findVariantSizeDefaults(sourceFile)
  const scope = new Map()
  if (variant != null) scope.set('variant', { resolved: true, value: variant })
  if (size != null) scope.set('size', { resolved: true, value: size })
  return scope
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

// T675 M2 (reviewer finding): a Tailwind class token is a colon-delimited *chain* of variants
// ending in the utility itself (`enabled:hover:ring-1` — `SearchBox`'s own input, `player-search.md`
// "Hover signals"; `ThirdPartyObjectionForm`'s input carries the identical shape) — the pseudo-class
// this file cares about can sit anywhere in that chain, not only first. Splits on `:` but never
// inside a `[...]` arbitrary-value bracket, so `data-[hover=true]:underline` stays one segment
// (`data-[hover=true]`), not two — the contrast this finding also named: that segment merely *names*
// "hover" inside its own brackets, it is not the `hover:` variant, and must never match.
function splitVariantChain(token) {
  const segments = []
  let depth = 0
  let current = ''
  for (const ch of token) {
    if (ch === '[') depth++
    else if (ch === ']') depth = Math.max(0, depth - 1)
    if (ch === ':' && depth === 0) {
      segments.push(current)
      current = ''
    } else {
      current += ch
    }
  }
  segments.push(current)
  return segments
}

export function extractPseudoClasses(parts) {
  const result = {}
  const tokens = parts.join(' ').split(/\s+/).filter(Boolean)
  for (const prefix of PSEUDO_PREFIXES) {
    const found = []
    for (const token of tokens) {
      const segments = splitVariantChain(token)
      // The last segment is always the utility itself (`ring-1`), never a variant — every segment
      // before it is a modifier in the chain, `enabled`/`aria-expanded`/`motion-safe`/the pseudo-class
      // itself, in whatever order the author wrote them. A bare word with no colon at all
      // (`hoverable`) has exactly one segment, which is the utility, so it is never scanned as a
      // variant here — the other required contrast this finding named.
      const variants = segments.slice(0, -1)
      if (variants.includes(prefix)) found.push(token)
    }
    result[prefix] = found.length > 0 ? found.join(' ') : null
  }
  return result
}

// T675 M2: `group-hover`/`group-hover/<name>` (and `peer-hover`/`peer-hover/<name>`) are a distinct
// Tailwind family — they paint on an ANCESTOR's hover (`group`) or a PRECEDING SIBLING's hover
// (`peer`), never on the element that carries the utility itself, so they are deliberately excluded
// from `extractPseudoClasses`'s own `hover` above (a literal `hover:` segment is the only thing that
// means "this element's own :hover"; folding `group-hover` into it would wrongly make a purely
// decorative descendant — `PlayerResultRow`'s alias `<span>`, `FavouritesList`'s alias `<span>` —
// read as though it had a hover state of its own, and would wrongly pull it into Record 1 as a row
// with no role and no story of its own to credit). Extracted here instead, read only by
// `findLocalElements`'s own group-hover credit pass below, which attributes the paint to the element
// actually hovered — the one carrying `group`/`group/<name>` — never to the descendant.
// `peer-hover` is matched (detected here, never silently dropped) but carries no credit pass of its
// own: a grep of this repository (2026-09-30) found no real `peer-hover`/`peer/<name>` usage
// anywhere, and this file's own standing rule is "found, never guessed" — a sibling-credit pass
// written against nothing real would be untestable against anything real. Extend
// `creditGroupHoverToAncestors` the same way the moment a real `peer-hover` case exists.
const GROUP_OR_PEER_HOVER_RE = /^(group|peer)-hover(?:\/([\w-]+))?$/

export function extractGroupOrPeerHoverClasses(parts) {
  const found = []
  for (const token of parts.join(' ').split(/\s+/).filter(Boolean)) {
    const segments = splitVariantChain(token)
    const variants = segments.slice(0, -1)
    for (const segment of variants) {
      const match = segment.match(GROUP_OR_PEER_HOVER_RE)
      if (match) {
        found.push({ token, kind: match[1], groupName: match[2] ?? null })
        break
      }
    }
  }
  return found
}

// The complementary marker: does this element itself carry the bare `group`/`peer` class, or a
// named `group/<name>`/`peer/<name>` — the class a `group-hover/<name>:`/`peer-hover/<name>:`
// descendant actually pairs with. `group`/`peer` are themselves bare utility class names (no colon,
// no variant chain), so this reads the token list directly rather than reusing
// `splitVariantChain` (nothing to split).
const GROUP_OR_PEER_MARKER_RE = /^(group|peer)(?:\/([\w-]+))?$/

export function extractGroupOrPeerMarkers(parts) {
  const found = []
  for (const token of parts.join(' ').split(/\s+/).filter(Boolean)) {
    const match = token.match(GROUP_OR_PEER_MARKER_RE)
    if (match) found.push({ kind: match[1], groupName: match[2] ?? null })
  }
  return found
}

// T671 (row 8, H5, Cause C — this row's own Method section, "8j" below): a *state-conditional*
// class — a ternary keyed on a component's own persisted boolean state, rather than a literal CSS
// pseudo-class utility — is the shape `Tooltip`'s own press treatment actually takes (tooltip.md §4
// active: "the trigger shows its own pressed treatment ... painted `border-strong` for as long as
// `pinned` is true"; `Tooltip/index.tsx`'s own remediation-B1 comment: "`pinned` is a persisted
// React boolean ... not the CSS `:active` pseudo-class ... so the paint is a plain conditional class
// rather than an `active:` variant"). `extractPseudoClasses` above only ever reads a literal
// `active:`-prefixed utility out of the *flattened* class text — by the time a ternary reaches it,
// `resolveClassParts` has already merged both branches into one bag of strings, deliberately losing
// which branch belongs to which condition (that function's own top comment: the "dual-branch
// conservative" rule). This walks the *raw*, unflattened className expression instead, looking for a
// `ConditionalExpression` whose own condition is exactly one of this state's own known bare
// identifiers.
// **First decision (this task's own brief): scope, Option A vs Option B — recorded in row 8's own
// Method section ("8j"), not restated here.** `STATE_CONDITIONAL_IDENTIFIERS` holds only the one
// real shape found: `pinned` names `active`, and nothing else — widened only once a second real case
// is found, never a general state-shaped-name vocabulary guessed ahead of one.
const STATE_CONDITIONAL_IDENTIFIERS = { active: ['pinned'] }

export function findStateConditionalClass(expr, state) {
  const names = STATE_CONDITIONAL_IDENTIFIERS[state]
  if (!names || !expr) return null
  let found = null
  function visit(node) {
    if (found || !node) return
    if (
      ts.isConditionalExpression(node) &&
      ts.isIdentifier(node.condition) &&
      names.includes(node.condition.text)
    ) {
      found = {
        identifier: node.condition.text,
        whenTrue: node.whenTrue.getText(),
        whenFalse: node.whenFalse.getText(),
      }
      return
    }
    ts.forEachChild(node, visit)
  }
  visit(expr)
  return found
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

// True when an element is inert by construction: it carries the literal HTML `hidden` attribute
// (bare `hidden` or `hidden={true}`, never a dynamic `hidden={someCondition}` — a condition might
// resolve `false` in some story, and an element that can become visible is not safe to treat as
// permanently inert) *and* a literal `tabIndex={-1}` (`UploadControl`'s own hidden file input,
// `composites/UploadControl/index.tsx`). Both together, never either alone: `hidden` is the UA
// stylesheet's own `display: none`, so an element the browser never gives a box to cannot be
// hovered, focused or pressed in any frame a real pointer or keyboard could produce, whatever a
// spec sentence says about it — but `tabIndex={-1}` alone says nothing of the kind (`Page`'s own
// `main` and `Dialog`'s own `h2` are both real script-focus targets, `tabIndex={-1}` and a genuine,
// painted `focus-visible` frame; `tabIndex` never governs hover or press either, so a `tabIndex={-1}`
// element that is not hidden can still be hoverable). T595 (row 8, group 3): this is the structural
// counterpart of bucket (b)'s spec-vocabulary recogniser above — a source-level fact about what the
// DOM can ever render, never a claim resting on a spec sentence, and never a named exception for one
// component's own directory.
function isInertByConstruction(opening) {
  const hiddenAttr = attrLiteral(getAttr(opening, 'hidden'))
  const tabIndexAttr = attrLiteral(getAttr(opening, 'tabIndex'))
  return (
    hiddenAttr.literal &&
    hiddenAttr.value === true &&
    tabIndexAttr.literal &&
    tabIndexAttr.value === -1
  )
}

function lineOf(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
}

// An element's own literal `aria-label` — a real accessible-name source, read the same way
// as JSX text, since a `visualForceState`'s own `name` names the accessible name, not specifically
// the rendered children (T594's REJECT on #80, item 3). Kept as element data (T694: the static name
// matching that read it is retired, and the `play()`-click match still compares by `text`). `aria-labelledby`
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
// T595 (row 8, H5): every tag below carries exactly one ARIA
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

// --- Shared JSX walk: visits every JSX tag of a file with the function-local `const` bindings in
// scope at that point, which `findLocalElements` resolves a className through (`resolveClassParts`'s
// `localConsts` namespace). Statements after a `return` in the same block are not visited. -----------

function statementsOf(stmtOrBlock) {
  return ts.isBlock(stmtOrBlock) ? stmtOrBlock.statements : [stmtOrBlock]
}

function walkJsxWithContext(sourceFile, visitJsx) {
  function visitBlockStatements(statements, ctx) {
    // A local `const` declared earlier in the same function body (`Button`'s own `const classes =
    // cx(...)`) is resolved through its own initializer, which travels with the candidate, reset at
    // the function boundaries (`visit` below), so a candidate's own `localConsts` map always reflects
    // exactly what is declared and in scope at its own JSX position, in source order.
    let localConsts = ctx.localConsts
    for (const stmt of statements) {
      if (ts.isVariableStatement(stmt)) {
        for (const decl of stmt.declarationList.declarations) {
          if (ts.isIdentifier(decl.name) && decl.initializer) {
            visit(decl.initializer, { ...ctx, localConsts })
            localConsts = new Map(localConsts)
            localConsts.set(decl.name.text, decl.initializer)
          }
        }
      } else if (ts.isIfStatement(stmt)) {
        visitBlockStatements(statementsOf(stmt.thenStatement), { ...ctx, localConsts })
        if (stmt.elseStatement) {
          const elseStmts = ts.isIfStatement(stmt.elseStatement)
            ? [stmt.elseStatement]
            : statementsOf(stmt.elseStatement)
          visitBlockStatements(elseStmts, { ...ctx, localConsts })
        }
      } else if (ts.isReturnStatement(stmt)) {
        if (stmt.expression) visit(stmt.expression, { ...ctx, localConsts })
        return
      } else {
        visit(stmt, { ...ctx, localConsts })
      }
    }
  }

  function visit(node, ctx) {
    if (isJsxTag(node)) {
      visitJsx(node, ctx)
      ts.forEachChild(node, (child) => visit(child, ctx))
      return
    }
    if (ts.isBlock(node)) {
      visitBlockStatements(node.statements, ctx)
      return
    }
    let nextCtx = ctx
    if (ts.isFunctionDeclaration(node) && node.name) {
      nextCtx = { ...ctx, localConsts: new Map() }
    } else if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.initializer &&
      (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer))
    ) {
      // The fresh function scope starts at the initializer itself (visited next via forEachChild),
      // which is where `localConsts` should reset, so the reset is threaded through this same
      // `nextCtx`.
      nextCtx = { ...ctx, localConsts: new Map() }
    }
    ts.forEachChild(node, (child) => visit(child, nextCtx))
  }
  visit(sourceFile, { localConsts: new Map() })
}

// --- Record 1: local interactive elements -------------------------------------------------------

export function findLocalElements(sourceFile, filePath, constMap) {
  const found = []
  // T675 M2: every `group`/`group/<name>` marker and every `group-hover`/`group-hover/<name>` match
  // seen anywhere in this file's own JSX, collected across the whole walk (not only from candidates
  // that end up in `found`) — read once, after the walk, by `creditGroupHoverToAncestors` below.
  const groupMarkerCandidates = []
  const groupHoverDescendants = []
  // T595: computed once per file, not per element — `resolveClassParts`'s own top comment states
  // what these two feed and why (an `ElementAccessExpression`'s own object namespace, and the
  // component's default `variant`/`size` two node shapes below resolve against).
  const constObjectMap = buildConstObjectMap(sourceFile)
  const defaultScope = buildVariantSizeDefaultScope(sourceFile)
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
          { localConsts: context.localConsts, defaultScope, objectConstMap: constObjectMap },
        )
      : []
    // T675 M2: captured for *every* lowercase-tag JSX node with a resolved className, independent of
    // the interactive/pseudo gate a few lines below — a `group/<name>` marker or a
    // `group-hover/<name>:` utility must be seen even on a plain, non-interactive `<span>` that will
    // never itself become a Record 1 row (`PlayerResultRow`'s alias, `FavouritesList`'s alias), since
    // the whole point of the credit pass after this walk is to move that fact onto the ancestor that
    // does become a row, never to add a row for the descendant itself.
    const nodeStart = node.getStart(sourceFile)
    const nodeEnd = node.getEnd()
    const ownGroupMarkers = extractGroupOrPeerMarkers(parts).filter((m) => m.kind === 'group')
    if (ownGroupMarkers.length > 0) {
      groupMarkerCandidates.push({
        nodeStart,
        nodeEnd,
        names: ownGroupMarkers.map((m) => m.groupName),
      })
    }
    const ownGroupHoverMatches = extractGroupOrPeerHoverClasses(parts).filter(
      (m) => m.kind === 'group',
    )
    if (ownGroupHoverMatches.length > 0) {
      groupHoverDescendants.push({ nodeStart, nodeEnd, matches: ownGroupHoverMatches })
    }
    const pseudo = extractPseudoClasses(parts)
    // T671: a state-conditional `active` class (`findStateConditionalClass`, above) is read from
    // the *raw* className expression, never `parts` — `parts` is already the flattened,
    // dual-branch-merged bag `resolveClassParts` produces, which is exactly what loses the one fact
    // this needs (which branch belongs to `pinned`). Skipped once a literal `active:` utility
    // already answers the state (`pseudo.active`): a component with both would be a second, still
    // unfound real case, not this one.
    const classExprForState = classAttr
      ? classAttr.initializer && ts.isJsxExpression(classAttr.initializer)
        ? classAttr.initializer.expression
        : classAttr.initializer
      : null
    const stateConditionalActive = pseudo.active
      ? null
      : findStateConditionalClass(classExprForState, 'active')
    const hasPseudo =
      pseudo.hover ||
      pseudo['focus-visible'] ||
      pseudo.active ||
      pseudo.focus ||
      Boolean(stateConditionalActive)
    const isIntrinsicInteractive =
      tagName === 'label' ? labelWrapsControl(node) : INTERACTIVE_TAGS.has(tagName)
    const isRoleInteractive =
      roleAttr.literal && (roleAttr.value === 'button' || roleAttr.value === 'link')
    const isTabIndexed = tabIndexAttr.present
    if (!(isIntrinsicInteractive || isRoleInteractive || isTabIndexed || hasPseudo)) return
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
      // T671: real, positive knowledge from source alone — independent of any story — that this
      // element's own `active` state paints through a conditional class rather than a literal
      // `active:` utility (`findStateConditionalClass`, above); `null` when no such shape was found.
      // Kept separate from `active` (never merged into it) so every existing reader of `active` —
      // the "ancestor of a forced descendant" pass — keeps reading exactly the literal-pseudo-class fact it always has; only
      // `buildElementCells`'s own new play-click branch and `renderRecord1`'s own display column
      // read this field.
      activeStateConditional: stateConditionalActive,
      classUnresolvedRefs: unresolved,
      text: literalTextOf(node) || ariaLabelText(opening),
      ariaHidden: isAriaHidden(opening),
      inertByConstruction: isInertByConstruction(opening),
      // Character offsets of this element's own JSX node — used only to tell whether one local
      // element's rendered range structurally contains another's (`buildElementMatrix`'s "ancestor
      // of a forced descendant" reason, `Table`'s own `<tr>` around its row link). Not meaningful
      // across two different files.
      nodeStart,
      nodeEnd,
    })
  })
  creditGroupHoverToAncestors(found, groupMarkerCandidates, groupHoverDescendants)
  return found
}

// T675 M2: the group-hover credit pass itself, run once per file after the walk above has finished
// (every candidate and every marker must be collected first — a marker later in source order than
// its own descendant, an unusual but legal JSX shape, must still resolve). For each
// `group-hover/<name>:` (or bare `group-hover:`) match found on some descendant, finds every
// `group`/`group/<name>` marker whose own JSX node structurally contains that descendant's
// (`nodeStart`/`nodeEnd` containment — the same technique `buildElementMatrix`'s "ancestor of a
// forced descendant" family already uses) with a matching name (`null` for bare `group`/`group-hover`,
// matched only to `null`, never to a named one — Tailwind itself never pairs a bare `group-hover:`
// with a named `group/<name>`, the contrast this finding named), and picks the *innermost* one
// (smallest containing range) so a nested group does not steal a closer group's own credit. The
// matched utility is appended onto that ancestor's own `hover` field in `found` — never onto the
// descendant, which never gains a `hover` of its own from this. A descendant whose containing
// `group/<name>` element never became its own Record 1 row (not itself interactive, no role, no
// pseudo-class of its own, and not carrying a `group` marker that turned out to matter) has nothing
// in `found` to credit — left uncredited rather than guessed, the same bar every other pass in this
// file holds; not a real case yet (every `group/<name>` marker found in this repository, 2026-09-30,
// sits on the row's own `<a>`, already a Record 1 row for its intrinsic tag alone). A descendant
// reached only through a *separately declared* helper component invoked as a JSX child — `MatchRow`'s
// `OutcomeLabel`, whose own `<span>` and whose caller's `<a href="...group/row-link">` are two
// disjoint JSX trees in the file's own source text, never one nested inside the other — is invisible
// to this containment test and stays uncredited too; a real, known, reported gap, not a silent one
// (T675 M2 remediation report), and not fixed here — resolving a JSX composition boundary this way
// would need call-site substitution this file does not otherwise do anywhere, guessed rather than
// found.
function creditGroupHoverToAncestors(found, groupMarkerCandidates, groupHoverDescendants) {
  for (const descendant of groupHoverDescendants) {
    for (const match of descendant.matches) {
      let bestMarker = null
      for (const marker of groupMarkerCandidates) {
        if (marker.nodeStart > descendant.nodeStart || marker.nodeEnd < descendant.nodeEnd) continue
        if (!marker.names.includes(match.groupName)) continue
        if (
          !bestMarker ||
          marker.nodeEnd - marker.nodeStart < bestMarker.nodeEnd - bestMarker.nodeStart
        ) {
          bestMarker = marker
        }
      }
      if (!bestMarker) continue
      const target = found.find(
        (el) => el.nodeStart === bestMarker.nodeStart && el.nodeEnd === bestMarker.nodeEnd,
      )
      if (!target) continue
      const already = (target.hover ?? '').split(' ').filter(Boolean)
      if (!already.includes(match.token)) {
        target.hover = already.length > 0 ? `${target.hover} ${match.token}` : match.token
      }
    }
  }
}

// --- Record 3: primitive instances --------------------------------------------------------------

export const PRIMITIVE_NAMES = ['Button', 'Link', 'Field', 'Menu']

// A destructuring default's string value: a string literal, or (T693) a member of a top-level
// `const X = { ... } as const` object in the same file — `variant = BUTTON_AXIS_DEFAULTS.variant`,
// where `BUTTON_AXIS_DEFAULTS` is the one constant `Button`'s destructuring and the runtime pass
// (`tests/visual/state-coverage-runtime.spec.ts`) both read. Anything else is `null`, unchanged.
function resolveStringDefault(sourceFile, initializer) {
  if (ts.isStringLiteral(initializer)) return initializer.text
  if (
    !ts.isPropertyAccessExpression(initializer) ||
    !ts.isIdentifier(initializer.expression) ||
    !ts.isIdentifier(initializer.name)
  ) {
    return null
  }
  const objectName = initializer.expression.text
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || decl.name.text !== objectName || !decl.initializer)
        continue
      const object = unwrapExpression(decl.initializer)
      if (!ts.isObjectLiteralExpression(object)) return null
      for (const prop of object.properties) {
        if (
          ts.isPropertyAssignment(prop) &&
          ts.isIdentifier(prop.name) &&
          prop.name.text === initializer.name.text &&
          ts.isStringLiteral(prop.initializer)
        ) {
          return prop.initializer.text
        }
      }
      return null
    }
  }
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
        if (propName === 'variant') {
          variantDefault = resolveStringDefault(sourceFile, el.initializer) ?? variantDefault
        }
        if (propName === 'size') {
          sizeDefault = resolveStringDefault(sourceFile, el.initializer) ?? sizeDefault
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return { variant: variantDefault, size: sizeDefault }
}

// What a call site's `variant` or `size` attribute settles to, the way JSX settles it (T700): the last
// attribute naming the prop is the one that applies, and an axis attribute is settled only when no
// spread attribute follows it in the attribute list (a spread before it is overridden by it). The value
// is a string literal, a no-substitution template literal, or either under `as const`, `as <T>`,
// `satisfies <T>` or parentheses in any nesting (`unwrapExpression`); any other expression, a
// template literal with substitutions, a boolean attribute (`<Button variant />` is `true`), a number
// and `null` included, is not settled by the source: only a string is a value of an axis (T702). `attributePresent` is
// whether the call site names the prop at all, which decides whether a default may fill an omitted axis.
function settleAxisAttr(openingElement, name) {
  const properties = openingElement.attributes.properties
  let index = -1
  properties.forEach((attr, i) => {
    if (ts.isJsxAttribute(attr) && attr.name.getText() === name) index = i
  })
  if (index === -1) return { attributePresent: false, settled: false }
  const spreadFollows = properties.some((attr, i) => i > index && ts.isJsxSpreadAttribute(attr))
  if (spreadFollows) return { attributePresent: true, settled: false }
  const attr = properties[index]
  let expr = attr.initializer
  if (expr && ts.isJsxExpression(expr)) expr = expr.expression
  const inner = unwrapExpression(expr)
  if (inner && (ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner))) {
    return { attributePresent: true, settled: true, value: inner.text }
  }
  return { attributePresent: true, settled: false }
}

// A call site of a tracked primitive in a design-system component file, read statically: its source
// position and the `variant`/`size` it settles to (a literal, or the primitive's own default; a prop
// the source cannot settle is `unresolved` and opens no row, `axisKey`). It fills `Rest` and nothing
// else (T694, T695).
export function findPrimitiveInstances(
  sourceFile,
  filePath,
  defaultsByPrimitive,
  skipPrimitives = [],
) {
  const found = []
  walkJsxWithContext(sourceFile, (node) => {
    const tagName = tagNameOf(node)
    if (!PRIMITIVE_NAMES.includes(tagName) || skipPrimitives.includes(tagName)) return
    const opening = openingOf(node)
    const defaults = defaultsByPrimitive[tagName] ?? {}
    const spread = hasSpreadAttr(opening)
    const resolveProp = (propName) => {
      const settled = settleAxisAttr(opening, propName)
      if (settled.settled) return { value: settled.value, resolved: 'explicit' }
      if (settled.attributePresent) return { value: null, resolved: 'unresolved' }
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

// --- Story parsing: exported story objects, args, visualForceState, play()-focus ----------------

export function findExportedStoryObjects(sourceFile) {
  const defaultExportName = findDefaultExportBindings(sourceFile).values().next().value ?? null
  const stories = []
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    const isExported = statement.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
    if (!isExported) continue
    for (const decl of statement.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || decl.name.text === defaultExportName) continue
      const init = unwrapExpression(decl.initializer)
      if (init && ts.isObjectLiteralExpression(init)) {
        stories.push({ exportName: decl.name.text, node: init })
      }
    }
  }
  return stories
}

function getProp(objLiteral, name) {
  if (!objLiteral) return undefined
  for (const prop of objLiteral.properties) {
    if (ts.isPropertyAssignment(prop) && prop.name.getText() === name) return prop.initializer
    if (ts.isShorthandPropertyAssignment(prop) && prop.name.getText() === name) return prop.name
  }
  return undefined
}

// T699: the name a property key spells, for the keys whose name is known without evaluating anything:
// an identifier, a string or numeric literal, a no-substitution template, or a computed key holding one
// of those. `null` for a computed key this pass cannot evaluate (`[k]`, a template with a substitution).
function spelledPropertyName(nameNode) {
  const computed = ts.isComputedPropertyName(nameNode)
  const key = computed ? unwrapExpression(nameNode.expression) : nameNode
  if (!key) return null
  if (
    ts.isStringLiteral(key) ||
    ts.isNoSubstitutionTemplateLiteral(key) ||
    ts.isNumericLiteral(key)
  )
    return key.text
  // `[k]` is a variable's value, not a name; only a bare key is an identifier's text.
  if (!computed && ts.isIdentifier(key)) return key.text
  return null
}

// T699: what an object literal says about a property, read the way JavaScript reads it. `getProp` takes
// the first identifier-named match, which is not what the engine keeps: a quoted or computed key, an
// accessor or a method is invisible to it, and a property written twice resolves to the LAST one. So
// each property is classified once per object, by the NAME TEXT of its key, and a name is `readable`
// only when exactly one property spells it and that property is a plain `name: value` or a shorthand
// `name` with an identifier key. Anything else that spells it, or a second property that does, is
// `unreadable`. A computed key whose name cannot be evaluated could be any name: `opaque`, and every
// name the caller asks about is then unreadable on this object (over-refusal, the safe direction).
// Spreads are not classified here; they are `hasSpreadElement`'s.
const propertyClassCache = new WeakMap()
function classifyProperties(objLiteral) {
  let classified = propertyClassCache.get(objLiteral)
  if (classified) return classified
  const byName = new Map()
  let opaque = false
  for (const prop of objLiteral.properties) {
    if (ts.isSpreadAssignment(prop) || !prop.name) continue
    const name = spelledPropertyName(prop.name)
    if (name === null) {
      opaque = true
      continue
    }
    const plain =
      (ts.isPropertyAssignment(prop) || ts.isShorthandPropertyAssignment(prop)) &&
      ts.isIdentifier(prop.name)
    if (byName.has(name) || !plain) {
      byName.set(name, 'unreadable')
    } else {
      byName.set(name, { node: ts.isPropertyAssignment(prop) ? prop.initializer : prop.name })
    }
  }
  classified = { byName, opaque }
  propertyClassCache.set(objLiteral, classified)
  return classified
}

// `{ present: false }`, `{ present: true, node }`, or `{ unreadable: true }` for the property `name` of
// an object literal (see `classifyProperties`). `null` or `undefined` object: absent.
function readProp(objLiteral, name) {
  if (!objLiteral) return { present: false }
  const { byName, opaque } = classifyProperties(objLiteral)
  if (opaque) return { unreadable: true }
  const found = byName.get(name)
  if (found === undefined) return { present: false }
  if (found === 'unreadable') return { unreadable: true }
  return { present: true, node: found.node }
}

// T704: what makes a story object or the default export unreadable as a whole, or `null`. An accessor
// (`get name()`, `set name(v)`) runs when Storybook reads the object and can write `this.parameters`; a
// method (`play() {}`) is called with the object as its `this`; a `this` in a function expression binds
// to the object the function is called on, and one in an arrow function inherits the module's, which is
// not this object's either way. None of that is in an object literal this pass reads, so the owner's
// `parameters` and `tags` are unreadable, the run fails for it, and the story gets no mount credit. T705: every `this`
// expression inside the owner is refused, a nested class's included (a `this` type or a `this` parameter
// is not an expression and is not refused), over-refusing being the safe direction. The owner's own
// shape only: an accessor or method of a nested `parameters` object is not this rule's.
const ownerHazardCache = new WeakMap()
function findOwnerHazard(owner) {
  if (!owner) return null
  if (ownerHazardCache.has(owner)) return ownerHazardCache.get(owner)
  let hazard = null
  for (const prop of owner.properties) {
    if (ts.isGetAccessorDeclaration(prop) || ts.isSetAccessorDeclaration(prop)) {
      hazard = `an accessor (\`${prop.name.getText()}\`)`
      break
    }
    if (ts.isMethodDeclaration(prop)) {
      hazard = `a method (\`${prop.name.getText()}\`)`
      break
    }
  }
  if (hazard === null) {
    const visit = (node) => {
      if (hazard !== null) return
      if (node.kind === ts.SyntaxKind.ThisKeyword) {
        hazard = 'a `this`'
        return
      }
      ts.forEachChild(node, visit)
    }
    visit(owner)
  }
  ownerHazardCache.set(owner, hazard)
  return hazard
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

export function extractVisualForceState(storyObj) {
  // A `parameters` that is not an object literal (an identifier, a call) carries no force this pass can
  // read: `null`, never a throw (T696). `computeStateCoverage` names such a story
  // (`hasUnreadableParameters`).
  // A `parameters` or a `visualForceState` this pass cannot read by name (T699) carries no force it can
  // read either, and `hasUnreadableParameters` names the story.
  if (findOwnerHazard(storyObj)) return null
  const parameters = readProp(storyObj, 'parameters')
  if (!parameters.present) return null
  const params = unwrapExpression(parameters.node)
  if (!params || !ts.isObjectLiteralExpression(params)) return null
  const force = readProp(params, 'visualForceState')
  if (!force.present) return null
  const forced = unwrapExpression(force.node)
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

// Whether a story's own `parameters` is present and not an object literal (`parameters: shared`,
// `parameters: make()`, a shorthand `parameters`): what it holds, a `visualForceState` among it, is
// not readable from this object. A literal that spreads another object is not this case: a force it
// hides is named when the manifest records one.
function hasUnreadableParameters(storyObj) {
  if (findOwnerHazard(storyObj)) return true
  const parameters = readProp(storyObj, 'parameters')
  if (parameters.unreadable) return true
  if (!parameters.present) return false
  const object = unwrapExpression(parameters.node)
  return !object || !ts.isObjectLiteralExpression(object) || hasUnreadableAnnotation(object)
}

// T699: the `parameters` of an owner (a story object or the default export) this pass cannot read by name:
// the property itself is quoted, computed, an accessor, a method or written more than once, or the object
// has a computed key whose name cannot be evaluated; or, in a `parameters` object literal, the same holds
// of `visualForceState`. A `parameters` that is not an object literal is the story's own reason
// (`hasUnreadableParameters`). What these rules guard is the reading of `visualForceState` and `tags`
// (the fixture tag): the record carries neither the force's state nor the story's tags, T703 moved the
// clip and the full-page frame to it.
function hasUnreadableNamedParameters(owner) {
  if (!owner) return false
  if (findOwnerHazard(owner)) return true
  const parameters = readProp(owner, 'parameters')
  if (parameters.unreadable) return true
  if (!parameters.present) return false
  const object = unwrapExpression(parameters.node)
  return Boolean(object) && ts.isObjectLiteralExpression(object) && hasUnreadableAnnotation(object)
}

function hasUnreadableAnnotation(parametersObject) {
  return readProp(parametersObject, 'visualForceState').unreadable === true
}

// T697: the rule that replaced T696 (a)'s list of mutation shapes. A story's binding, and the binding
// the default export names, may appear in a story file only in their own top-level declaration and in
// an export (`export default meta`, `export { meta as default }`, `export { X }`). Every other
// identifier reference to either, anywhere in the file, fails the check naming the story: a read or a
// write, at any depth, inside a function, inside the story's own initializer, as an argument, an alias,
// a destructuring or `for…of` target, a spread, a shorthand property, a JSX tag. Storybook reads
// `parameters` and `tags` from the module's exports after such code has run, and this pass reads the
// object literal; no list of the ways code can reach an object converges, so none is kept here.
//
// References are found by identifier, not by text: an identifier in a property-name position
// (`obj.X`, `{ X: … }`, a JSX attribute name, a destructuring key, a label) is not one, nor is one
// inside a type (`typeof meta` is erased and cannot mutate anything). A local of the same name in a
// nested scope (a parameter `meta`, an inner `const ZzA`) is NOT told apart from the binding: it is
// read as a reference, because over-refusing is the safe direction here (the story is named and gets
// no mount credit; nothing is credited that should not be) and resolving scope is not worth the
// risk of crediting a mutation it resolved wrongly.
//
// Not covered, by construction: a reference this pass cannot see because it is in another file is the
// import rule's (`findStoryModuleImports`); a story whose initializer is not an object literal is not
// a story this pass reads at all (`findExportedStoryObjects`).
function isTopLevelDeclarationName(node) {
  const declaration = node.parent
  return (
    ts.isVariableDeclaration(declaration) &&
    declaration.name === node &&
    ts.isVariableDeclarationList(declaration.parent) &&
    ts.isVariableStatement(declaration.parent.parent) &&
    ts.isSourceFile(declaration.parent.parent.parent)
  )
}

function isExportedAsDefaultExpression(node) {
  let current = node
  while (
    current.parent &&
    (ts.isAsExpression(current.parent) ||
      ts.isSatisfiesExpression(current.parent) ||
      ts.isParenthesizedExpression(current.parent) ||
      ts.isNonNullExpression(current.parent))
  ) {
    current = current.parent
  }
  return (
    ts.isExportAssignment(current.parent) &&
    !current.parent.isExportEquals &&
    current.parent.expression === current
  )
}

// Whether an identifier is a reference to a binding at all, rather than a name that merely spells it.
function isBindingReference(node) {
  const parent = node.parent
  if (!parent) return false
  if (ts.isPropertyAccessExpression(parent) && parent.name === node) return false
  if (ts.isQualifiedName(parent) && parent.right === node) return false
  if (
    (ts.isPropertyAssignment(parent) ||
      ts.isPropertySignature(parent) ||
      ts.isPropertyDeclaration(parent) ||
      ts.isMethodDeclaration(parent) ||
      ts.isMethodSignature(parent) ||
      ts.isGetAccessorDeclaration(parent) ||
      ts.isSetAccessorDeclaration(parent) ||
      ts.isEnumMember(parent) ||
      ts.isJsxAttribute(parent)) &&
    parent.name === node
  ) {
    return false
  }
  if (ts.isBindingElement(parent) && parent.propertyName === node) return false
  if (
    (ts.isLabeledStatement(parent) || ts.isBreakOrContinueStatement(parent)) &&
    parent.label === node
  ) {
    return false
  }
  // An import's own local name cannot coexist with the top-level declaration it would spell.
  if (ts.isImportSpecifier(parent) || ts.isImportClause(parent) || ts.isNamespaceImport(parent))
    return false
  // `export { X }`, `export { X as Y }`, `export { X as default }`: exports.
  if (ts.isExportSpecifier(parent)) return false
  if (isExportedAsDefaultExpression(node)) return false
  if (isTopLevelDeclarationName(node)) return false
  // `<meta />`: a lowercase JSX tag is an intrinsic element, not a reference to a binding.
  if (
    (ts.isJsxOpeningElement(parent) ||
      ts.isJsxClosingElement(parent) ||
      ts.isJsxSelfClosingElement(parent)) &&
    parent.tagName === node &&
    /^[a-z]/.test(node.text)
  ) {
    return false
  }
  return true
}

// Whether the walk may enter a node: not a type (a `typeof X` there is erased), except the `extends`
// clause of a class, whose expression runs, and an instantiation expression, which is a value.
function isRuntimeNode(node) {
  if (ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node)) return false
  if (!ts.isTypeNode(node)) return true
  if (!ts.isExpressionWithTypeArguments(node)) return false
  // T701: an `ExpressionWithTypeArguments` outside a heritage clause is an instantiation expression
  // (`meta<0>`), which evaluates `meta`: a value reference, walked. A type query with type arguments
  // (`typeof Table<MatchRow>`) is a `TypeQuery`, not this node, and stays a type.
  if (!ts.isHeritageClause(node.parent)) return true
  return node.parent.token === ts.SyntaxKind.ExtendsKeyword && ts.isClassLike(node.parent.parent)
}

// What a file exports as `default`, read once for every reader of the default export: a list of the
// default exports the file declares, each either `{ expression }` (an `export default <expression>` or
// the identifier of an `export { <identifier> as default }`) or `{ opaque }` (a declaration that has no
// expression to read: a function or class, a re-export from another module, `export * as default`).
// `!`, `as`, `satisfies` and parentheses are not stripped here; `unwrapExpression` strips them, so
// every reader unwraps the same way.
function collectDefaultExports(sourceFile) {
  const found = []
  for (const statement of sourceFile.statements) {
    if (ts.isExportAssignment(statement)) {
      if (!statement.isExportEquals) found.push({ expression: statement.expression })
    } else if (ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement)) {
      const isDefault = statement.modifiers?.some((m) => m.kind === ts.SyntaxKind.DefaultKeyword)
      if (isDefault) {
        found.push({ opaque: ts.isClassDeclaration(statement) ? 'a class' : 'a function' })
      }
    } else if (ts.isExportDeclaration(statement) && statement.exportClause) {
      if (ts.isNamespaceExport(statement.exportClause)) {
        if (statement.exportClause.name.text === 'default') {
          found.push({ opaque: 'a namespace re-exported from another module' })
        }
      } else {
        for (const specifier of statement.exportClause.elements) {
          if (specifier.name.text !== 'default') continue
          if (statement.moduleSpecifier) {
            found.push({ opaque: 're-exported from another module' })
          } else {
            found.push({ expression: specifier.propertyName ?? specifier.name })
          }
        }
      }
    }
  }
  return found
}

// The binding the default export names: `export default meta` and `export { meta as default }`, with
// `!`, `as`, `satisfies` and parentheses unwrapped in any nesting. The set is empty when the default
// export is anything else (an inline object literal, a call, a conditional), and holds the one name
// otherwise: whether that name is also readable is `readDefaultExport`'s.
export function findDefaultExportBindings(sourceFile) {
  const bindings = new Set()
  const defaults = collectDefaultExports(sourceFile)
  if (defaults.length !== 1 || defaults[0].expression === undefined) return bindings
  const expression = unwrapExpression(defaults[0].expression)
  if (expression && ts.isIdentifier(expression)) bindings.add(expression.text)
  return bindings
}

// ---- T701: top-level declarations of a name, and the one readable shape of a default export -----

function declaredNames(bindingName, out = []) {
  if (ts.isIdentifier(bindingName)) {
    out.push(bindingName.text)
    return out
  }
  for (const element of bindingName.elements) {
    if (!ts.isOmittedExpression(element)) declaredNames(element.name, out)
  }
  return out
}

// Every declaration of a name at the top level of a file, whatever it declares (`var`, `let`, `const`,
// a function, a class, an enum, a namespace, an import). A name has more than one only where
// JavaScript or TypeScript lets declarations merge or later ones overwrite earlier ones: which of them
// Storybook receives is not what this pass reads.
export function findTopLevelDeclarations(sourceFile) {
  const byName = new Map()
  const lineOf = (node) =>
    sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
  const add = (name, kind, node) => {
    if (!byName.has(name)) byName.set(name, [])
    byName.get(name).push({ kind, node, line: lineOf(node) })
  }
  for (const statement of sourceFile.statements) {
    if (ts.isVariableStatement(statement)) {
      const flags = statement.declarationList.flags
      const kind = flags & ts.NodeFlags.Const ? 'const' : flags & ts.NodeFlags.Let ? 'let' : 'var'
      for (const decl of statement.declarationList.declarations) {
        for (const name of declaredNames(decl.name)) add(name, kind, decl)
      }
    } else if (ts.isFunctionDeclaration(statement) && statement.name) {
      add(statement.name.text, 'function', statement)
    } else if (ts.isClassDeclaration(statement) && statement.name) {
      add(statement.name.text, 'class', statement)
    } else if (ts.isEnumDeclaration(statement)) {
      add(statement.name.text, 'enum', statement)
    } else if (ts.isModuleDeclaration(statement) && ts.isIdentifier(statement.name)) {
      add(statement.name.text, 'namespace', statement)
    } else if (ts.isImportEqualsDeclaration(statement)) {
      add(statement.name.text, 'import', statement)
    } else if (ts.isImportDeclaration(statement) && statement.importClause) {
      const { name, namedBindings } = statement.importClause
      if (name) add(name.text, 'import', statement)
      if (namedBindings && ts.isNamespaceImport(namedBindings)) {
        add(namedBindings.name.text, 'import', statement)
      } else if (namedBindings) {
        for (const element of namedBindings.elements) add(element.name.text, 'import', statement)
      }
    }
  }
  return byName
}

// What is wrong with a story's or a meta's binding, or `null`: declared more than once (the object
// Storybook receives is the last one assigned, and this pass reads one declaration), or with `var` or
// `let` (which a later assignment may rebind). Only a single `const` is read.
export function bindingDeclarationProblem(declarations, name) {
  const found = declarations.get(name) ?? []
  if (found.length > 1) {
    return {
      kind: 'redeclared-binding',
      reason:
        `is declared ${found.length} times at the top level (${found.map((d) => `${d.kind} at line ${d.line}`).join(', ')}), ` +
        'and this pass reads one declaration where Storybook receives the last value assigned. ' +
        'Declare it once, as a `const`.',
    }
  }
  if (found.length === 1 && (found[0].kind === 'var' || found[0].kind === 'let')) {
    return {
      kind: 'mutable-binding',
      reason:
        `is declared with ${found[0].kind} (line ${found[0].line}), which a later assignment may rebind ` +
        'to an object this pass did not read. Declare it as a `const`.',
    }
  }
  return null
}

// The object literal a file's default export reads as, and the binding it names. Readable only as
// `export default <identifier>` or `export { <identifier> as default }` (with `!`, `as`, `satisfies` and
// parentheses unwrapped, in any nesting) naming a top-level binding declared once, with `const`,
// initialised with an object literal (its own wrappers unwrapped the same way), or as an inline object
// literal `export default { … }`. Anything else is a `problem`: `{ kind, reason }`, and `object` is
// `null`, so no annotation is read from a guessed object. `binding` is the identifier the default
// export names, whether or not the rest is readable, for the reference rule.
export function readDefaultExport(sourceFile) {
  const defaults = collectDefaultExports(sourceFile)
  const unreadable = (reason, binding = null) => ({
    object: null,
    binding,
    problem: { kind: 'unreadable-default-export', reason },
  })
  if (defaults.length === 0) return unreadable('the file has no default export')
  if (defaults.length > 1) return unreadable(`the file has ${defaults.length} default exports`)
  const [only] = defaults
  if (only.opaque !== undefined) return unreadable(`the default export is ${only.opaque}`)
  const expression = unwrapExpression(only.expression)
  if (expression && ts.isObjectLiteralExpression(expression)) {
    return { object: expression, binding: null, problem: null }
  }
  if (!expression || !ts.isIdentifier(expression)) {
    return unreadable(
      'the default export is neither a binding nor an object literal (a call, a conditional, a comma ' +
        'expression, an instantiation expression, …)',
    )
  }
  const name = expression.text
  const declarations = findTopLevelDeclarations(sourceFile)
  const found = declarations.get(name) ?? []
  const declarationProblem = bindingDeclarationProblem(declarations, name)
  if (declarationProblem)
    return { object: null, binding: name, problem: { ...declarationProblem, binding: name } }
  if (found.length === 0) {
    return unreadable(
      `the default export names \`${name}\`, which is not declared at the top level`,
      name,
    )
  }
  const [declaration] = found
  const initializer =
    declaration.kind === 'const' &&
    ts.isVariableDeclaration(declaration.node) &&
    ts.isIdentifier(declaration.node.name)
      ? unwrapExpression(declaration.node.initializer)
      : null
  if (!initializer) {
    return unreadable(
      `the default export names \`${name}\`, which is not a \`const\` identifier initialised in place ` +
        `(it is ${declaration.kind === 'const' ? 'a destructured or uninitialised const' : `a ${declaration.kind}`})`,
      name,
    )
  }
  if (!ts.isObjectLiteralExpression(initializer)) {
    return unreadable(
      `the default export names \`${name}\`, whose initializer (line ${declaration.line}) is not an object ` +
        'literal (an alias, a call, a conditional, …)',
      name,
    )
  }
  return { object: initializer, binding: name, problem: null }
}

// The first line (1-based) of each of `bindingNames` that the file references outside its declaration
// and its exports.
export function findBindingReferences(sourceFile, bindingNames) {
  const referencedAt = new Map()
  const visit = (node) => {
    if (!isRuntimeNode(node)) return
    if (ts.isIdentifier(node) && bindingNames.has(node.text) && isBindingReference(node)) {
      if (!referencedAt.has(node.text)) {
        referencedAt.set(
          node.text,
          sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1,
        )
      }
      return
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return referencedAt
}

// ---- T697: a story module imported from a non-test module --------------------------------------

// A module specifier that names a story module: `….stories`, `….stories.ts`, `….stories.tsx` (and the
// other script extensions a bundler would resolve the same file through; a superset is the safe
// direction). A query or fragment is not part of the module's name.
const STORY_MODULE_SPECIFIER = /\.stories(\.(tsx?|jsx?|mjs|cjs|mts|cts))?$/

export function isStoryModuleSpecifier(specifier) {
  return STORY_MODULE_SPECIFIER.test(specifier.replace(/[?#].*$/, ''))
}

// T705: every identifier `require` in a file that is neither the declared name of a binding nor the
// direct, unparenthesised callee of a call, as `{ line, text }`. A direct callee with any arguments is
// not listed: its specifier is `findNonLiteralSpecifiers`'s when it is not a plain string literal and
// `findStoryModuleImports`'s when it is. Anything else (a parenthesised or cast callee, a comma
// expression, an alias, a member access on it, a value passed along, a shorthand property) can call or
// hand on a `require` whose specifier this pass does not read, so it is listed. A property or key that
// is merely spelled `require` (`x.require`, `{ require: 1 }`, `export { f as require }`), and a
// statement label, are not references to the identifier and are not listed.
function isRequireDeclaredOrNamed(node) {
  const parent = node.parent
  if (!parent) return false
  if (
    (ts.isPropertyAccessExpression(parent) ||
      ts.isQualifiedName(parent) ||
      ts.isPropertyAssignment(parent) ||
      ts.isPropertySignature(parent) ||
      ts.isPropertyDeclaration(parent) ||
      ts.isMethodDeclaration(parent) ||
      ts.isMethodSignature(parent) ||
      ts.isGetAccessorDeclaration(parent) ||
      ts.isSetAccessorDeclaration(parent) ||
      ts.isEnumMember(parent) ||
      ts.isJsxAttribute(parent)) &&
    (parent.name === node || parent.right === node)
  ) {
    return true
  }
  if (ts.isBindingElement(parent) && (parent.name === node || parent.propertyName === node)) {
    return true
  }
  if (
    (ts.isVariableDeclaration(parent) ||
      ts.isParameter(parent) ||
      ts.isFunctionDeclaration(parent) ||
      ts.isFunctionExpression(parent) ||
      ts.isClassDeclaration(parent) ||
      ts.isClassExpression(parent) ||
      ts.isImportClause(parent) ||
      ts.isNamespaceImport(parent) ||
      ts.isImportEqualsDeclaration(parent)) &&
    parent.name === node
  ) {
    return true
  }
  if (ts.isImportSpecifier(parent)) return true
  // `export { f as require }` names an export; `export { require }` references the binding.
  if (ts.isExportSpecifier(parent) && parent.name === node && parent.propertyName) return true
  if (
    (ts.isLabeledStatement(parent) || ts.isBreakOrContinueStatement(parent)) &&
    parent.label === node
  ) {
    return true
  }
  return ts.isCallExpression(parent) && parent.expression === node
}

export function findRequireReferences(sourceFile) {
  const found = []
  const visit = (node) => {
    if (ts.isIdentifier(node) && node.text === 'require' && !isRequireDeclaredOrNamed(node)) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile))
      const context = (node.parent ?? node).getText(sourceFile).replace(/\s+/g, ' ')
      found.push({
        line: line + 1,
        text: context.length > 80 ? `${context.slice(0, 77)}...` : context,
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return found
}

// The story-module specifiers a file imports. A module under `src` or `.storybook` other than a test
// may not: a reference from another file to a story's binding is one the per-file reference rule
// cannot see.
export function findStoryModuleImports(sourceFile) {
  return collectModuleSpecifiers(sourceFile).filter(isStoryModuleSpecifier)
}

// T701, T704: the one test-module predicate, for a file path and for a module specifier alike (a
// specifier may leave the extension off): `….test`, `….test.ts`, `….test.tsx`. A story is never a test
// module, whatever its name: Storybook indexes `Evil.test.stories.tsx` as a story, so it is read as one
// by every reader, and a specifier that names a story module names a story module. A query or fragment
// is not part of the name.
const TEST_MODULE = /\.test(\.[^/\\]+)?$/

export function isTestModule(pathOrSpecifier) {
  const name = pathOrSpecifier.replace(/[?#].*$/, '')
  if (isStoryPath(name) || isStoryModuleSpecifier(name)) return false
  return TEST_MODULE.test(name)
}

// The `*.test.*` module specifiers a file imports. `walkModuleFiles` does not read a test module, so a
// story module a test module imports is one only the test module's own importers could name: a module
// that is not a test may not import one.
export function findTestModuleImports(sourceFile) {
  return collectModuleSpecifiers(sourceFile).filter(isTestModule)
}

// T701: every use of `import.meta.glob` or `import.meta.globEager` in a file, whatever its pattern: the
// text of the access (or of the call that holds it), truncated. A glob names the files it loads by a
// pattern that matches story files without ending in `.stories` (`../src/**/*.stories.@(ts|tsx)`,
// `./*.stories.{ts,tsx}`, `./*`), or one built at run time, so no pattern is told apart from a story's.
// The access is what is found, not the call: `const g = import.meta.glob` is one. An `import.meta`
// indexed by something that is not a string literal could be one too, and is read as one.
export function findImportMetaGlobs(sourceFile) {
  const found = []
  const isImportMeta = (node) =>
    ts.isMetaProperty(node) && node.keywordToken === ts.SyntaxKind.ImportKeyword
  const globNames = new Set(['glob', 'globEager'])
  const visit = (node) => {
    let hit = false
    if (ts.isPropertyAccessExpression(node) && isImportMeta(node.expression)) {
      hit = globNames.has(node.name.text)
    } else if (ts.isElementAccessExpression(node) && isImportMeta(node.expression)) {
      const key = unwrapExpression(node.argumentExpression)
      hit =
        !key ||
        !(ts.isStringLiteral(key) || ts.isNoSubstitutionTemplateLiteral(key)) ||
        globNames.has(key.text)
    }
    if (hit) {
      const holder =
        ts.isCallExpression(node.parent) && node.parent.expression === node ? node.parent : node
      const text = holder.getText(sourceFile).replace(/\s+/g, ' ')
      found.push(text.length > 80 ? `${text.slice(0, 77)}...` : text)
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return found
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
// story's own shorthand `args` property back to its declaration. Stores the *unwrapped* initializer
// (`unwrapExpression`, above) — a `const X = {...} as const` is the common shape every
// `visualCaptureClip` constant not written inline uses (a story's own `args` constants too), and a caller resolving `X` back through this
// map wants the object literal itself, never the `AsExpression` wrapping it.
export function buildTopLevelConstNodeMap(sourceFile) {
  const map = new Map()
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (ts.isIdentifier(decl.name) && decl.initializer) {
        map.set(decl.name.text, unwrapExpression(decl.initializer))
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

// T671: the `userEvent.click(target)` shape `Tooltip.stories.tsx`'s own `pinOpen` (`Pinned`'s
// `play`) uses to drive `handleActivate` for real — the click-half of the two things this task's own
// brief says are owed together, the deliberate opposite number to `focusCallShape` above (`.focus()`
// or `toHaveFocus()`). Unlike a `visualForceState: { state: 'active' }`, which the visual harness
// (`tests/visual/stories.spec.ts`) answers with a real, held `page.mouse.down()` — wrong here, since
// `pinned` outlives the mouse button being held (tooltip.md §4 active) and a forced hover+mousedown
// would re-hover the trigger the `Pinned` story's own `pinOpen` deliberately moves the pointer off
// of — a real `userEvent.click()` is the only honest way to reach this state at all, so this reads it
// out of the play body directly rather than the `visualForceState` object every other credited state
// reads from.
function clickCallShape(expr) {
  if (!expr) return null
  let call = expr
  if (ts.isAwaitExpression(call)) call = call.expression
  if (!ts.isCallExpression(call)) return null
  const callee = call.expression
  if (
    ts.isPropertyAccessExpression(callee) &&
    callee.name.text === 'click' &&
    ts.isIdentifier(callee.expression) &&
    callee.expression.text === 'userEvent'
  ) {
    return { targetExpr: call.arguments[0] }
  }
  return null
}

// The click-half's own `findPlayFocusTarget` counterpart — same shape, same `varMap` (a
// `const trigger = canvas.getByRole('button')` bound earlier in the same play body, `pinOpen`'s own
// shape), same "keep the last one found" rule. **Not folded into `findPlayFocusTarget` itself**: a
// click and a focus/blur assertion answer two different states (`active` vs `focus-visible`) and a
// play body that does both (`pinOpen` clicks, then unhovers and blurs) must credit each to its own
// state, never the last call of either kind found across the whole body.
export function findPlayClickTarget(body) {
  if (!body) return null
  const flat = ts.isBlock(body) ? body.statements : []
  const varMap = new Map()
  let last = null
  function consider(expr) {
    const shape = clickCallShape(expr)
    if (!shape) return
    const target = shape.targetExpr
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

// --- Directory / file plumbing --------------------------------------------------------------

const TIER_SEGMENTS = ['primitives', 'composites', 'screens']

function walkAllTsxFiles(rootSrcDir) {
  const files = []
  function walk(dir) {
    for (const entry of readdirSync(dir)) {
      const full = path.join(dir, entry)
      const st = statSync(full)
      if (st.isDirectory()) walk(full)
      else if (entry.endsWith('.tsx') && !isTestModule(entry)) files.push(full)
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

// Reject anything that is not a real, unambiguous ISO calendar date (`YYYY-MM-DD`) — the identical
// reading `a11y-allowlist.mjs` already gives its own `fixBy`/`date` fields, duplicated rather than
// imported across these two independent checks: `new Date("soon")` parses to `Invalid Date`, and a
// later `<` comparison against it is always false — silently never overdue — so a garbage string
// must fail as malformed here rather than surviving to the expiry comparison and being read as
// never expiring.
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/
function isValidIsoDate(value) {
  if (typeof value !== 'string' || !ISO_DATE_RE.test(value)) return false
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return false
  return parsed.toISOString().slice(0, 10) === value
}

// Every entry here is a real, filed exception with an owner and a deadline — not a suppression —
// the same shape `a11y-allowlist.mjs` already carries for its own file (row 8's own Method section
// cites it: printing "empty — nothing to validate" proves no *known* violation is currently
// hidden), down to the field names (`date`/`fixOwed`/`fixBy`) so the two allowlists read the same
// way. `findUnaccountedForceStates` still fails the run on anything *outside* this list, and now
// also on anything *inside* it that is malformed or past its own `fixBy` — an allowlist with no
// expiry is how a temporary exception becomes permanent, and this project already enforces exactly
// that date shape elsewhere (`a11y-allowlist.mjs`, `story-baselines-duplicates.test.mjs`'s own debt
// entries, T591). Empty today: the one entry this list ever carried (`ProfileSummary`'s own
// `SwitcherFocusVisibleAndOpen`, filed 2026-09-19) is closed (T598,
// row 8's own Method section; the runtime manifest places that frame now, T694) — deleted outright
// here, never left behind as a passing allowlist row, the same discipline `a11y-allowlist.mjs`'s
// own empty-list steady state already models.
export const KNOWN_UNACCOUNTED_FORCE_STATES = []

// --- Reading the region back, by column (T684) -------------------------------------------------
//
// A forced story is accounted for only by a mention in a cell of *its own state's column*: Record
// 1's story part (the text after ` → `) of the Hover / Focus-visible / Active cell, Record 3's Hover
// / Focus-visible / Press (active) column. Every other cell of the region says something else — a
// path (File:Line, Row, Rest), an element tag, class utilities, a disabled credit — and a word
// found there is not a credit of any state: a story named `Tooltip` is spelled in its own
// component's own path, `ZzBoundedHover` is printed in Button's Disabled column,
// and neither says its hover frame exists.
//
// Read from the rendered text, not from the credit record (`coveredBy` / `ambiguousReasons` /
// `unresolvedByState`) it is rendered from, on purpose: the comment on `findUnaccountedForceStates`
// holds that the check must read what a reader opens, and two derivations of one fact are how they
// come apart. The cost of that choice is that the reader must not guess at the text's layout, so
// columns are located by their header text (`RECORD1_HEADERS` / `RECORD3_HEADERS`, the very
// constants the renderers print) and anything unexpected — a missing table, a missing header, a row
// with another cell count, a Record 1 state cell with no ` → ` — throws, never silently reads as
// an empty scope that would then report every story missing, or none.

function splitTableRow(line) {
  const trimmed = line.trim()
  if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) {
    throw new Error(`state-coverage: not a table row: ${JSON.stringify(line.slice(0, 80))}`)
  }
  // `esc` (the renderer) writes a literal pipe inside a cell as `\|`.
  return trimmed
    .slice(1, -1)
    .split(/(?<!\\)\|/)
    .map((cell) => cell.trim().replace(/\\\|/g, '|'))
}

function columnIndex(headerCells, header, tableKind) {
  const index = headerCells.indexOf(header)
  if (index === -1) {
    throw new Error(
      `state-coverage: ${tableKind} table has no ${JSON.stringify(header)} column ` +
        `(found ${JSON.stringify(headerCells)}) — the renderer and the reader of the region disagree`,
    )
  }
  return index
}

const TABLE_SEPARATOR_ROW = /^\|[\s|:-]+\|$/

// The Record 1 `Hover (class → story)` cell, reduced to the story half. `N/A` is how a component
// with no local interactive element prints every state cell.
function record1StoryPart(cell, rowLine) {
  if (cell === 'N/A') return ''
  const arrow = cell.indexOf(' → ')
  if (arrow === -1) {
    throw new Error(
      `state-coverage: Record 1 state cell has no " → " between class and story: ${JSON.stringify(rowLine.slice(0, 80))}`,
    )
  }
  return cell.slice(arrow + ' → '.length)
}

// `{ record1: [{ key, cells }], sections: [{ name, componentKey, rows: [{ label, cells }] }] }`,
// `cells` keyed by state (`hover` / `focus-visible` / `active`), each holding the text of that
// state's column in that row. A Record 3 section is the `#### \`Name\`` heading's own table and ends
// where that table ends — a line after it belongs to no section — and is keyed `primitives/<Name>`,
// the component key every other part of this check uses, so a composite or screen that shares a
// primitive's directory name cannot read the primitive's section. A table that is neither Record 1
// nor a heading's own is not a table this pass renders and is read as nothing.
function parseStateColumns(regionText) {
  const record1 = []
  const sections = []
  const lines = regionText.split('\n')
  let heading = null
  for (let i = 0; i < lines.length; i++) {
    const headingMatch = /^#### `(.+)`$/.exec(lines[i])
    if (headingMatch) {
      heading = headingMatch[1]
      continue
    }
    const startsTable =
      lines[i].startsWith('|') && i + 1 < lines.length && TABLE_SEPARATOR_ROW.test(lines[i + 1])
    if (!startsTable) {
      if (lines[i].trim() !== '') heading = null
      continue
    }
    const header = splitTableRow(lines[i])
    const rowLines = []
    let end = i + 2
    while (end < lines.length && lines[end].startsWith('|')) rowLines.push(lines[end++])
    const rows = rowLines.map((line) => {
      const cells = splitTableRow(line)
      if (cells.length !== header.length) {
        throw new Error(
          `state-coverage: a table row has ${cells.length} cells under a ${header.length}-cell header: ${JSON.stringify(line.slice(0, 80))}`,
        )
      }
      return { cells, line }
    })
    if (heading === null && header[0] === RECORD1_HEADERS[0]) {
      const key = columnIndex(header, RECORD1_HEADERS[0], 'Record 1')
      const states = Object.fromEntries(
        Object.entries(RECORD1_STATE_HEADERS).map(([state, name]) => [
          state,
          columnIndex(header, name, 'Record 1'),
        ]),
      )
      for (const { cells, line } of rows) {
        record1.push({
          key: cells[key],
          cells: Object.fromEntries(
            Object.entries(states).map(([state, at]) => [state, record1StoryPart(cells[at], line)]),
          ),
        })
      }
    } else if (heading !== null) {
      const label = columnIndex(header, RECORD3_HEADERS[0], `Record 3 \`${heading}\``)
      const states = Object.fromEntries(
        Object.entries(RECORD3_STATE_HEADERS).map(([state, name]) => [
          state,
          columnIndex(header, name, `Record 3 \`${heading}\``),
        ]),
      )
      sections.push({
        name: heading,
        componentKey: `primitives/${heading}`,
        rows: rows.map(({ cells }) => ({
          label: cells[label],
          cells: Object.fromEntries(
            Object.entries(states).map(([state, at]) => [state, cells[at]]),
          ),
        })),
      })
    }
    heading = null
    i = end - 1
  }
  if (!lines.some((line) => line.startsWith(`| ${RECORD1_HEADERS[0]} |`))) {
    throw new Error(
      `state-coverage: the region has no Record 1 table (header starting "| ${RECORD1_HEADERS[0]} |")`,
    )
  }
  return { record1, sections }
}

// A story file's label base: the `<base>` of the `<base>:<export>` label every printer below writes
// and the reader (`storyIsCreditedInItsStateColumn`) reads back.
function storyFileLabelBase(storyFile) {
  return storyFile.replace(/\.stories\.tsx?$/, '')
}

// The `<base>:<export>` label of a story, from a story file's path or basename. The one place a
// label is spelled: `cellName`, the story credits of the runtime pass and `qualifyStoryNamesWhereAmbiguous`
// all print through it.
function storyLabel(storyFile, exportName) {
  return `${storyFileLabelBase(path.basename(storyFile))}:${exportName}`
}

// A `<base>:<export>` label names one story only if no two story files share a base: the base
// carries no component, so `composites/Footer/Extra.stories.tsx` and
// `composites/SearchBox/Extra.stories.tsx` would both print `Extra:Hover`. Throws, naming the files
// and the base, when two distinct story files (in two components, or two directories of one) share
// one — the reader cannot tell their labels apart and the printers do not lengthen them.
function assertStoryLabelBasesAreUnique(filePaths) {
  const filesByBase = new Map()
  for (const filePath of filePaths) {
    if (!/\.stories\.tsx?$/.test(filePath)) continue
    const base = storyFileLabelBase(path.basename(filePath))
    filesByBase.set(base, [...(filesByBase.get(base) ?? []), filePath])
  }
  for (const [base, files] of filesByBase) {
    if (files.length < 2) continue
    throw new Error(
      `state-coverage: story files ${files.map((f) => relPath(f)).join(' and ')} share the label ` +
        `base ${JSON.stringify(base)}, so \`${base}:<export>\` would name a story of either — ` +
        `rename one of the files`,
    )
  }
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// The entries of a bare-name cell. A bare story name is only ever printed where an entry *starts*:
// `Hover`, `unresolved: Hover: 2 candidates share role …`, `Hover (play-driven; …)`, joined by
// `; ` — so a name is read at the start of an entry, never as a word inside another story's reason
// text (`share role "button"`, `name "Hover" not literally resolvable`, an ancestor's own
// `hover: RowLinkHover`). A name is followed by `: ` (`Hover: 2 candidates share role …`,
// `Hover: selector …`), ` (` (`Hover (play-driven; …)`, `Hover (play-click-driven): …`) or the end
// of the entry; `Hover:` followed by anything but a space is another story's qualified label
// (`CountryFlag:FlagHoverRevealed` is not an entry of a story exported as `CountryFlag`).
function bareCellEntries(text) {
  return text.split('; ').map((entry) => entry.trim().replace(/^unresolved: /, ''))
}

// Whether the region credits *this* story for the state it forces — by its own identity (component,
// story file, export name) in a cell of that state's column (T684, M1-M3), in exactly these forms:
//   - a qualified `<story file base>:<export>` label (`Footer:Hover`) in the state's column of any
//     row of either record — the form every credit of a story in another component's cell, and
//     every Record 3 axis-matrix credit, is printed in;
//   - the bare export name, only in the story's own component's own rows — Record 1's rows of that
//     component key, or the `primitives/<Name>` element matrix section (a primitive outside
//     `PRIMITIVE_NAMES`; an axis matrix prints every story as a qualified label) — and only when the
//     story's file is the component's only story file (`hasSoleStoryFile`): a bare name cannot say
//     which of two files' `Hover` it credits, and `computeStateCoverage` prints a component with
//     several story files qualified (`qualifyStoryNamesWhereAmbiguous`).
// Never Rest, Row, Element, File:Line, class text or Disabled, never another state's column.
function storyIsCreditedInItsStateColumn(componentKey, entry, columns, hasSoleStoryFile) {
  const { exportName, storyFile, forced } = entry
  const state = forced.state
  if (!Object.hasOwn(RECORD1_STATE_HEADERS, state)) return false
  const labelBase = storyFileLabelBase(storyFile)
  const name = escapeRegExp(exportName)
  const qualified = new RegExp(
    `(?<![\\w$])(?:${escapeRegExp(labelBase)}|${escapeRegExp(`${componentKey}/${storyFile}`)}):${name}(?![\\w$])`,
  )
  const bare = new RegExp(`^${name}(?:: | \\(|$)`)
  const credits = (text, bareAllowed) =>
    qualified.test(text) || (bareAllowed && bareCellEntries(text).some((e) => bare.test(e)))
  for (const row of columns.record1) {
    if (credits(row.cells[state], hasSoleStoryFile && row.key === componentKey)) return true
  }
  for (const section of columns.sections) {
    const ownElementMatrix =
      section.componentKey === componentKey && !PRIMITIVE_NAMES.includes(section.name)
    for (const row of section.rows) {
      if (credits(row.cells[state], hasSoleStoryFile && ownElementMatrix)) return true
    }
  }
  return false
}

// Every real `visualForceState` in every story under this package's three tiers is either credited
// on some cell (a real match) or named in some cell's own `unresolved: <reason>` text — the two
// ways this region ever shows that a force-state was compared against anything at all. A
// force-state that is neither has been silently lost somewhere between the source and the region —
// exactly the shape mechanism 3's own first draft shipped (`ProfileSummary`'s three flag stories,
// traced far enough to reject every wrong candidate in `Button`/`Menu` and credited nowhere at all,
// T595 orchestrator finding on this task's own hand-back: "a real forced frame that appears
// nowhere"). Checked against the region's own rendered text — the same text a reader actually
// opens — rather than re-derived a second, parallel way from `coveredBy`/`ambiguousReasons` that
// could itself drift from what renders (the record is equivalent to the text, which is why either
// would do; the text is read because it is what the comment above `parseStateColumns` says it is,
// and its columns are located by header, so a layout change throws rather than drifts). A story is
// looked up by its own identity in a cell of its own state's column (`storyIsCreditedInItsStateColumn`,
// T684), never by its export name as a bare word anywhere in the region: the region prints
// conventional exports (`Hover`, `FocusVisible`, `Active`) on the cells of many components, so a
// forced `Hover` credited nowhere used to pass because another component's `Hover` was printed, and
// a story named after its own component passed on the component's own path. Every forced story is asked for an accounting (T694): one the manifest
// refuses carries its `refusal` (`resolveRuntimeForce`) and is reported with that reason, whatever it
// mounts. A `synthetic` entry (a credit this pass manufactured on another
// component's behalf, a credit another component's story gives its element) is excluded too: it is not a real
// exported story object anywhere, and the real story it originated from is checked under its own
// name in its own component's own list. Returns three groups, never merged so a genuinely new loss
// can never hide behind an old, filed one: `missing` (unfiled — fails the run), `known` (a
// well-formed, unexpired `KNOWN_UNACCOUNTED_FORCE_STATES` member that is, in fact, still
// unaccounted — reported every run, never fails on its own, so a fix that closes one is never left
// stale on the list by accident), and `expired` (a filed member that is malformed or past its own
// `fixBy` — fails the run exactly like `missing`, because an exception nobody enforces the deadline
// on is not an exception, it is a rename of the original bug).
export function findUnaccountedForceStates(storyStatesByComponent, regionText) {
  const missing = []
  const known = []
  const expired = []
  const today = new Date().toISOString().slice(0, 10)
  const columns = parseStateColumns(regionText)
  for (const [componentKey, entries] of storyStatesByComponent) {
    // A synthetic entry names no story file (it is a label this pass manufactured); every real one
    // does — a fixture that builds one by hand names its own file, never a guessed `<Component>.stories.tsx`.
    const realEntries = entries.filter((e) => !e.synthetic)
    for (const e of realEntries) {
      if (typeof e.storyFile !== 'string' || e.storyFile === '') {
        throw new Error(
          `state-coverage: story ${JSON.stringify(e.exportName)} of ${componentKey} carries no storyFile`,
        )
      }
    }
    const hasSoleStoryFile = new Set(realEntries.map((e) => e.storyFile)).size <= 1
    for (const entry of entries) {
      const { exportName, forced, synthetic } = entry
      if (!forced || synthetic) continue
      if (storyIsCreditedInItsStateColumn(componentKey, entry, columns, hasSoleStoryFile)) continue
      const filed = KNOWN_UNACCOUNTED_FORCE_STATES.find(
        (k) => k.componentKey === componentKey && k.exportName === exportName,
      )
      if (!filed) {
        // `refusal` is why the manifest's record for this story credits no cell (`resolveRuntimeForce`);
        // absent, the story was credited by that record and the region still does not show it.
        missing.push({
          componentKey,
          exportName,
          state: forced.state,
          ...(entry.refusal ? { refusal: entry.refusal } : {}),
        })
        continue
      }
      const malformed = ['date', 'fixOwed', 'fixBy'].filter((field) => {
        const value = filed[field]
        return typeof value !== 'string' || value.trim() === ''
      })
      if (!malformed.includes('fixBy') && !isValidIsoDate(filed.fixBy)) {
        malformed.push('fixBy (not a valid ISO date)')
      }
      if (!malformed.includes('date') && !isValidIsoDate(filed.date)) {
        malformed.push('date (not a valid ISO date)')
      }
      if (malformed.length > 0) {
        expired.push({ componentKey, exportName, state: forced.state, ...filed, malformed })
      } else if (filed.fixBy < today) {
        expired.push({ componentKey, exportName, state: forced.state, ...filed, overdue: today })
      } else {
        known.push({ componentKey, exportName, state: forced.state, ...filed })
      }
    }
  }
  return { missing, known, expired }
}

// --- Orchestration -------------------------------------------------------------------------

// Record 1 and an element matrix print a story by its bare export name, which names one story only
// while the component has one story file. A component with several (`Extra.stories.tsx` beside
// `Component.stories.tsx`, each free to export a `Hover`) prints each qualified — `Extra:Hover`, the
// form `cellName` already gives every Record 3 axis-matrix credit — so the region says which file's
// story it credits, and `findUnaccountedForceStates` can tell a credited story from a namesake
// (T684, M3). `displayName` is only what the cells print; `exportName` stays the story's identity.
function qualifyStoryNamesWhereAmbiguous(storyStatesByComponent) {
  for (const entries of storyStatesByComponent.values()) {
    const real = entries.filter((e) => !e.synthetic && e.storyFile)
    if (new Set(real.map((e) => e.storyFile)).size <= 1) continue
    for (const e of real) e.displayName = storyLabel(e.storyFile, e.exportName)
  }
}

// The story entries as the cells print them: `displayName` (set by `qualifyStoryNamesWhereAmbiguous`)
// standing in for the bare export name. A hand-built fixture carries none and reads unchanged.
function asPrinted(storyObjectsWithMeta) {
  return storyObjectsWithMeta.map((s) => (s.displayName ? { ...s, exportName: s.displayName } : s))
}

// --- T694: the runtime manifest decides what every story credits --------------------------------
//
// What a forced story credits used to be read from source: which element a role, a name and an `nth`
// pick, through guards, spreads, branches that never render, `aria-hidden` ancestors and children a
// primitive never places. Each adversarial review of #112 found another shape that guess got wrong
// (T687–T692). A real browser does not guess: `tests/visual/state-coverage-runtime.spec.ts` locates
// every forced story's target with the capture harness's own locator in the built Storybook and
// records what it found, in `packages/design-system/specs/state-coverage-runtime.json` (T693). This
// section reads that record and nothing else about a force:
//   - a record-1 cell is credited when the browser found exactly one element at every captured width,
//     with one source stamp across them, and that stamp is the `file:line` of a record-1 element;
//   - a record-3 cell when the entry's placing instance is a tracked primitive at the variant and size
//     the browser rendered it at;
//   - the Disabled column (from nothing else) and a primitive's own stories' Rest column from the instances the manifest
//     says the story mounts, as rendered, unless the record says a `visualCaptureClip` applied to the
//     story (T703: observed by the browser, never read from source) or the frame may not show where a
//     rendered file painted (`computeStateCoverage`); a tracked primitive written in a story file
//     credits nothing;
//   - every other forced story credits no cell and is reported with the reason (`resolveRuntimeForce`),
//     among them a force on an element the browser reports disabled.
// The stories considered are the manifest's entries, each joined to its parsed story object by the
// entry's `importPath` and `exportName`, never the story files found under a component directory, so
// where a story file lives decides nothing. A story with no entry fails the check, naming the command
// that refreshes the manifest.
//
// What stays static, and the region's legend says so (`STATIC_CREDITS` lists it and the legend is built
// from that list): the Rest column's call sites in component files, the `play()`-click credit of an
// element that paints its `active` state through a conditional class (`resolveClickMatch`), which
// stories carry `play()` at all, and the hover and active credit an ancestor inherits from a credited
// descendant. No Disabled cell is static.

// The directory, relative to the design-system package, whose stories are the runtime pass's own
// plants (`packages/design-system/.storybook/fixtures/`). Their manifest entries record what the
// browser rendered for each plant; they are not published stories and the region never reads them.
// This path only removes entries from consideration. What makes a story a fixture is its tag
// (`FIXTURE_TAG`, `scripts/visual/story-index.mjs`), as for every other reader of the stories, so a
// tagged story anywhere credits nothing too.
export const FIXTURE_STORY_DIRECTORY = '.storybook/fixtures/'

// The axes each tracked primitive keys its matrix rows on: `variant`, `size`, both, or one. The
// registry `packages/design-system/.storybook/preview.tsx` builds for the browser lists the same;
// `state-coverage.test.mjs` fails when either side drifts.
export const PRIMITIVE_AXES = {
  Button: ['variant', 'size'],
  Link: ['variant'],
  Field: ['size'],
  Menu: ['variant'],
}

// The axes a tracked primitive keys its rows on, or `undefined` for anything else. `PRIMITIVE_AXES` is
// a plain object, so a component named `constructor`, `toString` or `__proto__` would find an
// `Object.prototype` member there, and a non-string (`['Button']` coerces to `Button`) would find a
// real entry: only a string that is an own key is a tracked primitive (T702).
function axesOfPrimitive(component) {
  return typeof component === 'string' && Object.hasOwn(PRIMITIVE_AXES, component)
    ? PRIMITIVE_AXES[component]
    : undefined
}

// A manifest `importPath` as the package-relative path it names (`./src/x.stories.tsx` is
// `src/x.stories.tsx`).
function normaliseImportPath(importPath) {
  return importPath.replace(/^\.\//, '')
}

function isFixtureImportPath(importPath) {
  return normaliseImportPath(importPath).startsWith(FIXTURE_STORY_DIRECTORY)
}

// The component a story file belongs to, as a record key: `<tier>/<Component>` for a story file at
// `src/<tier>/<Component>/...`, and its own directory (relative to the package) for every other file
// the Storybook globs index — `.storybook/foundations`, `src/lib`, `src/primitives` — so a story
// there is accounted for under a key of its own rather than dropped.
function storyHomeKey(filePath) {
  const rel = path.relative(srcDir, filePath).split(path.sep)
  if (rel.length >= 3 && TIER_SEGMENTS.includes(rel[0])) return `${rel[0]}/${rel[1]}`
  return path.relative(dsDir, path.dirname(filePath)).split(path.sep).join('/')
}

function isStoryPath(filePath) {
  return /\.stories\.tsx?$/.test(filePath)
}

function canonicalInstance(instance) {
  return JSON.stringify([
    instance.component,
    instance.variant ?? null,
    instance.size ?? null,
    [...(instance.disabledAt ?? [])].sort(),
  ])
}

// The tracked-primitive instances every captured width mounts: the multiset intersection across
// widths, in the first width's order. An instance one width renders and another does not is not
// what the story shows, so it credits nothing.
export function stableMounts(entry) {
  const perWidth = Object.values(entry?.widths ?? {}).map((record) => record.mounts ?? [])
  if (perWidth.length === 0) return []
  const counts = perWidth.map((mounts) => {
    const byKey = new Map()
    for (const mount of mounts) {
      const key = canonicalInstance(mount)
      byKey.set(key, (byKey.get(key) ?? 0) + 1)
    }
    return byKey
  })
  const allowed = new Map()
  for (const [key, count] of counts[0]) {
    allowed.set(key, Math.min(count, ...counts.map((byKey) => byKey.get(key) ?? 0)))
  }
  const stable = []
  for (const mount of perWidth[0]) {
    const key = canonicalInstance(mount)
    if ((allowed.get(key) ?? 0) > 0) {
      allowed.set(key, allowed.get(key) - 1)
      stable.push(mount)
    }
  }
  return stable
}

// What the browser reports holds focus after a story's `play()` settles, when every captured width
// agrees on it: `{ stamp, placedBy }`, or `null`.
function stableFocus(entry) {
  const records = Object.values(entry?.widths ?? {}).map((record) => record.focus ?? null)
  if (records.length === 0 || records.some((r) => r === null)) return null
  const first = JSON.stringify(records[0])
  return records.every((r) => JSON.stringify(r) === first) ? records[0] : null
}

// The matrix row an instance the browser rendered lands on, as the `{ variant, size }` fields
// `axisKey` reads, or the reason it lands on none: an axis the primitive keys its rows on that the
// browser rendered with no value (`Menu` mounted without a `variant`) has no row in a matrix that
// has none for it, and inventing a `(no axis)` row would only open cells nothing can close.
export function rowAxesOf(instance) {
  const axes = axesOfPrimitive(instance.component)
  if (!axes) return { reason: `${instance.component} is not a tracked primitive` }
  for (const axis of axes) {
    if (instance[axis] == null) {
      return {
        reason: `${instance.component} rendered with no ${axis} (none passed, no default), so no row of its matrix is keyed by it`,
      }
    }
  }
  const field = (axis) =>
    axes.includes(axis)
      ? { value: instance[axis], resolved: 'runtime' }
      : { value: null, resolved: 'n/a' }
  return { variant: field('variant'), size: field('size') }
}

// The widths every story is captured and recorded at, as the manifest's keys.
const CAPTURED_WIDTHS = REVIEW_WIDTHS.map(String)

const isPlainObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
const show = (value) => String(JSON.stringify(value))

// The values each tracked primitive's axes take, from the union type its own `index.tsx` exports
// (`export type ButtonVariant = 'primary' | 'secondary' | ...`, `FieldSize`, `LinkVariant`,
// `MenuVariant`): `{ variant: Set | null, size: Set | null }`, an axis null when the primitive has no
// such axis or its type is not a union of string literals this pass can read. A manifest instance at
// a value outside the set is a manifest the pass did not write (`instanceShapeProblem`).
export function readAxisValues(sourceFile, primitive) {
  const values = { variant: null, size: null }
  for (const axis of axesOfPrimitive(primitive) ?? []) {
    const aliasName = `${primitive}${axis[0].toUpperCase()}${axis.slice(1)}`
    for (const statement of sourceFile.statements) {
      if (!ts.isTypeAliasDeclaration(statement) || statement.name.text !== aliasName) continue
      const members = ts.isUnionTypeNode(statement.type) ? statement.type.types : [statement.type]
      if (
        members.every((m) => ts.isLiteralTypeNode(m) && ts.isStringLiteral(m.literal)) &&
        members.length > 0
      ) {
        values[axis] = new Set(members.map((m) => m.literal.text))
      }
    }
  }
  return values
}

// What is wrong with one tracked-primitive instance a manifest records (a mount, a force's or a
// focus's `placedBy`), or `null`: it is an object; its `disabledAt` is an array of strings; and for
// each axis its primitive keys rows on, the value is `null` (rendered with no value, which lands on no
// row, `rowAxesOf`) or a string, one the primitive's own type lists when this pass could read it. A
// value outside that list would otherwise open a row of the matrix nothing else knows.
function instanceShapeProblem(instance, where, knownAxisValues) {
  if (!isPlainObject(instance)) return `${where} is not an object (${show(instance)})`
  if (
    !Array.isArray(instance.disabledAt) ||
    !instance.disabledAt.every((stamp) => typeof stamp === 'string' && STAMP_FORM.test(stamp))
  ) {
    return `${where} has a disabledAt that is not an array of \`file:line\` stamps (${show(instance.disabledAt)})`
  }
  for (const axis of axesOfPrimitive(instance.component) ?? []) {
    const value = instance[axis]
    if (value === null) continue
    if (typeof value !== 'string') {
      return `${where} has a ${axis} that is neither a string nor null (${show(value)})`
    }
    const known = knownAxisValues?.[instance.component]?.[axis]
    if (known && !known.has(value)) {
      return `${where} has ${axis} ${show(value)}, which is none of ${instance.component}'s own (${[...known].join(', ')})`
    }
  }
  return null
}

// The one form of a non-null stamp: `<repository-rooted path>:<line>`, a positive line. It is what
// `packages/design-system/.storybook/source-stamp.mjs` writes (`keyOf`: the path, a colon, the 1-based
// line of the opening tag) and what `tests/visual/state-coverage-runtime.ts` reads back (`stampFile`
// cuts at the last colon). That capture maps every falsy stamp to `{ stamp: null, placedBy: null }`,
// so an empty string is a stamp it never writes (T698). The path is repository-relative: no
// whitespace anywhere (a space or a newline is a stamp it never writes), no leading `./` or `/`, and
// the line has no leading zero (T702). The same form is each `disabledAt` entry's: the capture writes
// those keys from the same stamp attribute. The check reads only the shape, not whether
// the path names a file: a stamp that names none credits no record-1 element.
const STAMP_FORM = /^(?!\.\/|\/)\S+:[1-9][0-9]*$/

// What is wrong with an element record's `stamp` (a force's or a focus's), or `null`: it is `null`
// (an element no source file stamped) or a non-empty string of the `file:line` form (T698).
function stampProblem(stamp, where) {
  if (stamp === null) return null
  if (typeof stamp !== 'string') {
    return `${where} has a stamp that is neither a string nor null (${show(stamp)})`
  }
  if (!STAMP_FORM.test(stamp)) {
    return `${where} has a stamp that is not of the \`file:line\` form the capture writes (${show(stamp)})`
  }
  return null
}

// What is wrong with an entry's `files`, or `null`: an array of strings, present (T698). It is read
// for the overlay verdict, which credits mounts, so an entry that carries none cannot be told from
// one that renders nothing fixed, and a value that is not an array would throw where it is read.
const isStringArray = (value) =>
  Array.isArray(value) && value.every((item) => typeof item === 'string')

export function filesProblem(entry) {
  const files = entry?.files
  if (isStringArray(files)) return null
  return `its \`files\` is not an array of strings (${show(files)})`
}

// An element record (a force's or a focus's) with a null stamp and a placing instance: the capture
// finds the placing instance by walking up from the element's stamp, so an element no source file
// stamped has none (`tests/visual/state-coverage-runtime.ts` writes `{ stamp: null, placedBy: null }`
// for it). The pair is a manifest the pass did not write, and crediting it would give record 3 a cell
// without the disabled refusal, which keys on the stamp (T696).
function unstampedPlacedProblem(record, where) {
  if (record.stamp !== null || (record.placedBy ?? null) === null) return null
  return (
    `${where} has a null stamp and a placedBy (${show(record.placedBy)}): an element no source file ` +
    'stamped is placed by no tracked primitive, so the capture never writes that pair'
  )
}

// What is wrong with the SHAPE of a manifest entry, or `null`. A malformed entry is not a refusal of
// one story's credit; it is a manifest the pass did not write, so the check fails naming the story:
//   - the entry's widths are not exactly the widths the capture takes (`REVIEW_WIDTHS`: the runtime
//     pass records every story at every one of them, `scripts/visual/state-coverage-runtime.mjs`) — a
//     missing width would let the credit rest on fewer frames than the story is captured at, an extra
//     one on a frame no capture takes, and none at all records nothing;
//   - a width's record that is not an object, whose `mounts` is not an array, or one of whose mounts
//     (`instanceShapeProblem`) is malformed, or whose `focus` is neither null nor an object with a
//     `stamp` that is `null` or a `file:line` string (`stampProblem`) and a null or well-formed
//     `placedBy`, a null `stamp` never with a `placedBy` (`unstampedPlacedProblem`);
//   - for a forced story, a force record whose `count` is not a non-negative integer, and, at count 1,
//     whose `stamp` is neither the explicit `null` of an element no source file stamped (a missing key
//     is not one) nor a `file:line` string (`stampProblem`: an empty string is neither), or whose
//     `placedBy` is neither null nor a well-formed instance, or whose `stamp` is null while its
//     `placedBy` is not; and a force record whose `differsByTheme` (the light and the dark render
//     disagree on the match count, stamp or placing instance, or only one carries the force, T710) is
//     present and not `true`;
//     (An entry's `files` is checked by `filesProblem`, which the story path runs first: it is read
//     outside this function's widths, so a value that is not an array of strings must be named before
//     any of it is read.)
//   - the entry's `oneThemeFiles` (the files exactly one of the two themes rendered, T711) is, when
//     present, an array of strings, and a width's `focusDiffersByTheme` (the two themes disagree on the
//     focus, T711) is, when present, `true`;
// `knownAxisValues` is `readAxisValues` per primitive; absent, an axis value is not checked against it.
export function entryShapeProblem(entry, { forced, knownAxisValues } = {}) {
  const oneTheme = entry?.oneThemeFiles
  if (oneTheme !== undefined && !isStringArray(oneTheme)) {
    return `its \`oneThemeFiles\` is not an array of strings (${show(oneTheme)}); the pass writes it only as one, and only when it is not empty`
  }
  const recorded = Object.keys(entry?.widths ?? {})
  const missing = CAPTURED_WIDTHS.filter((w) => !recorded.includes(w))
  const extra = recorded.filter((w) => !CAPTURED_WIDTHS.includes(w))
  if (recorded.length === 0) {
    return `it records no captured width (the capture takes ${CAPTURED_WIDTHS.map((w) => `${w}px`).join(', ')})`
  }
  if (missing.length > 0 || extra.length > 0) {
    return (
      `its widths (${recorded.map((w) => `${w}px`).join(', ')}) are not the widths the capture takes ` +
      `(${CAPTURED_WIDTHS.map((w) => `${w}px`).join(', ')})` +
      (missing.length > 0 ? `: missing ${missing.map((w) => `${w}px`).join(', ')}` : '') +
      (extra.length > 0 ? `: extra ${extra.map((w) => `${w}px`).join(', ')}` : '')
    )
  }
  for (const w of CAPTURED_WIDTHS) {
    const record = entry.widths[w]
    const at = `its record at ${w}px`
    if (!isPlainObject(record)) return `${at} is not an object (${show(record)})`
    if (!Array.isArray(record.mounts)) {
      return `${at} has \`mounts\` that is not an array (${show(record.mounts)})`
    }
    // The capture frame (T703): booleans the browser pass writes. An entry without them predates the
    // record, and a mount credit read from nothing would be a credit for a frame nobody observed.
    if (record.focusDiffersByTheme !== undefined && record.focusDiffersByTheme !== true) {
      return `${at} has a \`focusDiffersByTheme\` that is not \`true\` (${show(record.focusDiffersByTheme)}); the pass writes it only as \`true\``
    }
    for (const field of ['clip', 'fullPage']) {
      if (typeof record[field] !== 'boolean') {
        return `${at} has \`${field}\` that is not a boolean (${show(record[field])}), so the capture frame it shows is not recorded`
      }
    }
    for (const [i, mount] of record.mounts.entries()) {
      const problem = instanceShapeProblem(mount, `${at}'s mounts[${i}]`, knownAxisValues)
      if (problem) return problem
    }
    const focus = record.focus ?? null
    if (focus !== null) {
      if (!isPlainObject(focus)) return `${at} has a focus that is not an object (${show(focus)})`
      const focusStamp = stampProblem(focus.stamp, `${at}'s focus`)
      if (focusStamp) return focusStamp
      if ((focus.placedBy ?? null) !== null) {
        const problem = instanceShapeProblem(
          focus.placedBy,
          `${at}'s focus placedBy`,
          knownAxisValues,
        )
        if (problem) return problem
      }
      const pair = unstampedPlacedProblem(focus, `${at}'s focus`)
      if (pair) return pair
    }
  }
  if (forced) {
    for (const w of CAPTURED_WIDTHS) {
      const force = entry.widths[w].force
      if (!force) continue
      const at = `its force record at ${w}px`
      if (!(Number.isInteger(force.count) && force.count >= 0)) {
        return `${at} has a count that is not a non-negative integer (${show(force.count)})`
      }
      if (force.differsByTheme !== undefined && force.differsByTheme !== true) {
        return `${at} has a differsByTheme that is not \`true\` (${show(force.differsByTheme)}); the pass writes it only as \`true\``
      }
      if (force.count !== 1) continue
      const forceStamp = stampProblem(force.stamp, at)
      if (forceStamp) return forceStamp
      if ((force.placedBy ?? null) !== null) {
        const problem = instanceShapeProblem(force.placedBy, `${at}'s placedBy`, knownAxisValues)
        if (problem) return problem
      }
      const pair = unstampedPlacedProblem(force, at)
      if (pair) return pair
    }
  }
  return null
}

// What a forced story's manifest entry credits, or why it credits nothing. `recordOneKeys` is the
// set of `file:line` keys of record 1's elements. Returns `{ malformed }` for an entry whose
// shape is wrong (`entryShapeProblem`), `{ refusal }`, or `{ stamp, placedBy, notes }`: `stamp` is
// the record-1 element credited (null when the located element is none), `placedBy` the tracked
// instance (with its `row`) whose matrix cell is credited (null when none), `notes` the reasons a
// half was refused while the other was credited.
//
// A force is credited only when it is the same answer at every captured width: one element
// (Playwright's strict mode refuses two, so no frame of a two-match force can be captured, and none
// of zero), one stamp, one placing instance, and an element the browser does not report disabled. The
// refusal names the true reason — never the one a refusal prints for every cause (`credited on no
// cell`).
export function resolveRuntimeForce(entry, { recordOneKeys, knownAxisValues }) {
  const malformed = entryShapeProblem(entry, { forced: true, knownAxisValues })
  if (malformed) return { malformed }
  const widths = Object.entries(entry.widths).sort(([a], [b]) => Number(a) - Number(b))
  const label = (list) => list.map(([w]) => `${w}px`).join(', ')
  const unrecorded = widths.filter(([, record]) => !record.force)
  if (unrecorded.length > 0) {
    return {
      refusal: `the manifest records no force target at ${label(unrecorded)}, so it predates this story's visualForceState — rewrite it with \`${REWRITE_COMMAND}\``,
    }
  }
  // The light and the dark render of the story disagree on the force (T710, `combineThemeRecords`) in
  // match count, stamp or placing instance, or only one carries it: the record carries one theme's
  // answer and this flag, and neither theme's answer is the capture's.
  const themed = widths.filter(([, record]) => record.force.differsByTheme === true)
  if (themed.length > 0) {
    return {
      refusal: `the light and the dark render disagree on the force at ${label(themed)} (a different match count, stamp or placing instance, or a force only one theme carries): the capture shows both themes, so neither answer is credited`,
    }
  }
  const none = widths.filter(([, record]) => record.force.count === 0)
  if (none.length > 0) {
    return {
      refusal: `no element matched the force at ${label(none)}: the browser finds nothing for its role, name and nth`,
    }
  }
  const several = widths.filter(([, record]) => record.force.count > 1)
  if (several.length > 0) {
    return {
      refusal: `more than one element matched the force (${several.map(([w, r]) => `${r.force.count} at ${w}px`).join(', ')}): Playwright's strict mode refuses it, so no frame of it can be captured`,
    }
  }
  const stamps = new Set(widths.map(([, record]) => record.force.stamp ?? null))
  if (stamps.size > 1) {
    return {
      refusal: `the located element's stamp differs across widths (${widths.map(([w, r]) => `${r.force.stamp ?? 'none'} at ${w}px`).join(', ')}): the width decides which element the force reaches`,
    }
  }
  const placers = new Set(widths.map(([, record]) => JSON.stringify(record.force.placedBy ?? null)))
  if (placers.size > 1) {
    return {
      refusal: `the primitive instance that placed the located element differs across widths (${[...placers].join(' and ')})`,
    }
  }
  const stamp = widths[0][1].force.stamp ?? null
  const placedBy = widths[0][1].force.placedBy ?? null
  // A disabled element paints disabled, whatever state the harness forces on it: `hover()` and `press`
  // reach it as a disabled control, and `focus()` does nothing on one. `disabledAt` is the sorted unique
  // stamps of the host elements the placing instance's own file placed that the browser reports
  // `:disabled` or `aria-disabled="true"` (`tests/visual/state-coverage-runtime.ts`) — stamps, not
  // elements, so a sibling written at the same line shares one. Refused when the located element's
  // stamp is in the placing instance's `disabledAt` at any width, for hover, focus-visible and press
  // alike, at record 1 and record 3 both.
  if (
    stamp !== null &&
    widths.some(([, r]) => (r.force.placedBy?.disabledAt ?? []).includes(stamp))
  ) {
    return {
      refusal: `the located element's stamp ${stamp} is in its placing ${placedBy?.component ?? 'instance'}'s disabledAt (the browser reports it disabled, native or aria-disabled), so the forced state never paints on it`,
    }
  }
  const notes = []
  const elementStamp = stamp !== null && recordOneKeys.has(stamp) ? stamp : null
  let placing = null
  if (placedBy) {
    const row = rowAxesOf(placedBy)
    if (row.reason) notes.push(row.reason)
    else placing = { ...placedBy, row }
  }
  if (elementStamp === null && placing === null) {
    if (stamp === null) {
      return {
        refusal:
          'the located element carries no source stamp: no design-system source file wrote it (it is an element the story itself renders), so it is in no record-1 element and no tracked primitive placed it',
      }
    }
    return {
      refusal:
        `the located element's stamp ${stamp} is in no record-1 element and no tracked primitive placed it` +
        (notes.length > 0 ? ` (${notes.join('; ')})` : ''),
    }
  }
  return { stamp: elementStamp, placedBy: placing, notes }
}

// The runtime half of a story's own record, shared by the matrices: what it credits, per record.
// Built once per manifest entry (`computeStateCoverage`).
function sameInstance(a, b) {
  return canonicalInstance(a) === canonicalInstance(b)
}

// Walks the story files the Storybook globs index that `walkAllTsxFiles` does not (anywhere under
// `src`, and `.storybook/foundations`), reading each. The fixtures directory is the runtime pass's own
// and is not walked.
function walkStoryFiles() {
  const files = new Map()
  function walk(dir) {
    let names
    try {
      names = readdirSync(dir)
    } catch {
      return
    }
    for (const name of names) {
      const full = path.join(dir, name)
      if (statSync(full).isDirectory()) walk(full)
      else if (isStoryPath(name)) files.set(full, readFileSync(full, 'utf8'))
    }
  }
  walk(srcDir)
  walk(path.join(dsDir, '.storybook', 'foundations'))
  return files
}

// Every script module under `src` and `.storybook` that is not a test: what the import rule reads.
// A story file is one too (another story file importing a story is refused).
function walkModuleFiles() {
  const files = new Map()
  function walk(dir) {
    let names
    try {
      names = readdirSync(dir)
    } catch {
      return
    }
    for (const name of names) {
      if (name === 'node_modules') continue
      const full = path.join(dir, name)
      if (statSync(full).isDirectory()) walk(full)
      else if (/\.([cm]?[jt]sx?)$/.test(name) && !isTestModule(name)) {
        files.set(full, readFileSync(full, 'utf8'))
      }
    }
  }
  walk(srcDir)
  walk(path.join(dsDir, '.storybook'))
  return files
}

// Whether an object literal spreads another object (`{ ...BASE }`): what the spread brings in is not
// in this object's own properties, so neither its `tags` nor its `parameters` can be read from here.
function hasSpreadElement(object) {
  return Boolean(object) && object.properties.some((prop) => ts.isSpreadAssignment(prop))
}

// A story's tags as Storybook merges them: the default export's, then the story's own, a `!tag`
// removing one. `unreadable` is true when either side carries a `tags` that is not an array of string
// literals, or is an object that spreads another one (which may bring a `tags`): this pass cannot
// read either.
export function readStoryTags(metaObject, storyObject) {
  const tags = new Set()
  let unreadable = false
  for (const owner of [metaObject, storyObject]) {
    if (hasSpreadElement(owner) || findOwnerHazard(owner)) unreadable = true
    const property = readProp(owner, 'tags')
    if (property.unreadable) {
      unreadable = true
      continue
    }
    if (!property.present) continue
    const array = unwrapExpression(property.node)
    if (
      !array ||
      !ts.isArrayLiteralExpression(array) ||
      !array.elements.every(
        (el) => ts.isStringLiteral(el) || ts.isNoSubstitutionTemplateLiteral(el),
      )
    ) {
      unreadable = true
      continue
    }
    for (const el of array.elements) {
      if (el.text.startsWith('!')) tags.delete(el.text.slice(1))
      else tags.add(el.text)
    }
  }
  return { tags, unreadable }
}

// The design-system source files with a string literal holding the unprefixed class token `fixed`
// (`position: fixed`). A story captured as its root element's box (the record says neither clipped nor
// full-page, `tests/visual/stories.spec.ts`) that renders one may paint what that file
// placed outside the box, which the screenshot then does not show. Only this shape is identified: an
// absolutely positioned popover, a prefixed `fixed` (`focus:fixed`) and an element the story's own
// file positions are not.
function findOverlayFiles(filesByPath, sourceFiles) {
  const overlay = new Set()
  for (const [file, sourceFile] of sourceFiles) {
    if (isStoryPath(file) || isTestModule(file)) continue
    let found = false
    const visit = (node) => {
      if (found) return
      if (
        (ts.isStringLiteral(node) ||
          ts.isNoSubstitutionTemplateLiteral(node) ||
          ts.isTemplateHead(node) ||
          ts.isTemplateMiddle(node) ||
          ts.isTemplateTail(node)) &&
        node.text.split(/\s+/).includes('fixed')
      ) {
        found = true
        return
      }
      ts.forEachChild(node, visit)
    }
    visit(sourceFile)
    if (found) overlay.add(relPath(file))
  }
  return overlay
}

export function computeStateCoverage({
  componentDirs,
  filesByPath,
  storyFilesByPath = new Map(),
  moduleFilesByPath = new Map(),
  manifest = {},
}) {
  const allFiles = [...filesByPath.keys()].sort()
  // Every story file the Storybook globs index, wherever it lives: the ones the component walk already
  // read, and the rest (`storyFilesByPath`: foundations, `src/lib`, a tier directory's own files, a
  // `.stories.ts`).
  const storySources = new Map()
  for (const f of allFiles) if (isStoryPath(f)) storySources.set(f, filesByPath.get(f))
  for (const [f, text] of storyFilesByPath) storySources.set(f, text)
  assertStoryLabelBasesAreUnique([...storySources.keys()].sort())
  const sourceFiles = new Map(allFiles.map((f) => [f, parseTsx(f, filesByPath.get(f))]))

  const defaultsByPrimitive = {}
  const knownAxisValues = {}
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
    knownAxisValues[name] = readAxisValues(sourceFiles.get(indexPath), name)
  }
  if (defaultsByPrimitive.Menu) defaultsByPrimitive.Menu = { variant: null }
  else if (componentDirs.some((d) => d.name === 'Menu'))
    defaultsByPrimitive.Menu = { variant: null }

  const localElementsByComponent = new Map()
  const instancesByPrimitive = new Map(PRIMITIVE_NAMES.map((p) => [p, []]))
  const storyStatesByComponent = new Map()

  // Pass 1, static, source only: every local interactive element (record 1's rows) and every call site
  // of a tracked primitive (record 3's `Rest` column). Nothing about a story is read here.
  for (const filePath of allFiles) {
    if (isTestModule(filePath)) continue
    // A tracked primitive written in a STORY file credits nothing here, neither `Rest` nor `Disabled`:
    // a story's JSX may sit under an `args` key its render never passes, behind a branch that never
    // runs, or carry a `disabled` the primitive does not render (`<Button href disabled>` is an
    // enabled `<a>`). What a story mounts is what the manifest recorded, read in pass 2.
    if (isStoryPath(filePath)) continue
    const sourceFile = sourceFiles.get(filePath)
    const constMap = buildConstStringMap(sourceFile)
    const componentKey = componentKeyForFile(srcDir, filePath)

    const locals = findLocalElements(sourceFile, relPath(filePath), constMap)
    if (locals.length > 0) {
      localElementsByComponent.set(componentKey, [
        ...(localElementsByComponent.get(componentKey) ?? []),
        ...locals,
      ])
    }

    const jsxInstances = findPrimitiveInstances(sourceFile, relPath(filePath), defaultsByPrimitive)
    for (const inst of jsxInstances) {
      instancesByPrimitive.get(inst.primitive).push({ ...inst, kind: 'jsx', componentKey })
    }
  }

  // Pass 2, the runtime manifest: every story the globs index, joined to its entry.
  const recordOneKeys = new Set()
  const elementOwner = new Map()
  for (const [componentKey, elements] of localElementsByComponent) {
    for (const el of elements) {
      recordOneKeys.add(`${el.file}:${el.line}`)
      elementOwner.set(`${el.file}:${el.line}`, componentKey)
    }
  }
  const overlayFiles = findOverlayFiles(filesByPath, sourceFiles)
  const entriesByLocation = new Map()
  const manifestProblems = []
  for (const [id, entry] of Object.entries(manifest)) {
    // An entry that is not an object (`null`, a string, an array) is a manifest the pass did not
    // write: named by its key, never read for an `importPath` (T696).
    if (!isPlainObject(entry)) {
      manifestProblems.push({
        kind: 'malformed-entry',
        location: `${MANIFEST_PATH}:${id}`,
        detail:
          `${MANIFEST_PATH}'s entry ${id} is not an object (${show(entry)}). ` +
          `Run \`${REWRITE_COMMAND}\` to rewrite it.`,
      })
      continue
    }
    // `importPath` and `exportName` are the strings the capture writes; `String()` made an array or a
    // number a key that credits (T702). Such an entry is named by its key and credited from nothing.
    const notStrings = ['importPath', 'exportName'].filter(
      (field) => typeof entry[field] !== 'string',
    )
    if (notStrings.length > 0) {
      manifestProblems.push({
        kind: 'malformed-entry',
        location: `${MANIFEST_PATH}:${id}`,
        detail:
          `${MANIFEST_PATH}'s entry ${id} has ${notStrings.map((f) => `an ${f} that is not a string (${show(entry[f])})`).join(' and ')}. ` +
          `Run \`${REWRITE_COMMAND}\` to rewrite it.`,
      })
      continue
    }
    if (isFixtureImportPath(entry.importPath)) continue
    const key = `${normaliseImportPath(entry.importPath)}#${entry.exportName}`
    const group = entriesByLocation.get(key)
    if (group) group.duplicateIds.push(id)
    else entriesByLocation.set(key, { id, entry, duplicateIds: [id] })
  }
  // Two entries naming one story are a manifest the pass did not write (the capture keys an entry by
  // its story id, one per story): each is named by its key, and the story they name credits nothing
  // from either, since a map that kept the last one would credit what the first records otherwise
  // (T698). The safe direction is no credit: the check fails and the story reads as malformed.
  for (const [key, { duplicateIds }] of entriesByLocation) {
    if (duplicateIds.length < 2) continue
    const [file, exportName] = key.split('#')
    for (const id of duplicateIds) {
      manifestProblems.push({
        kind: 'malformed-entry',
        location: `${MANIFEST_PATH}:${id}`,
        detail:
          `${MANIFEST_PATH}'s entries ${duplicateIds.join(', ')} all name story ${exportName} of ${file}: ` +
          `the capture writes one entry per story, so none of them is credited. ` +
          `Run \`${REWRITE_COMMAND}\` to rewrite the manifest.`,
      })
    }
  }
  const partialRefusals = []
  const unkeyedMounts = []
  const seenLocations = new Set()
  const pushStateEntry = (componentKey, stateEntry) => {
    if (!storyStatesByComponent.has(componentKey)) storyStatesByComponent.set(componentKey, [])
    storyStatesByComponent.get(componentKey).push(stateEntry)
  }

  // T697: a module other than a test that imports a story module may reference a story's binding from
  // where the per-file reference rule below cannot see it. T701: so may one that globs files by a
  // pattern, whatever the pattern, and one that imports a test module, which is not read here. T704: so
  // may one whose `import()` or `require()` takes a specifier that is not a plain string literal.
  for (const filePath of [...moduleFilesByPath.keys()].sort()) {
    if (isTestModule(filePath)) continue
    const moduleSource = ts.createSourceFile(
      filePath,
      moduleFilesByPath.get(filePath),
      ts.ScriptTarget.Latest,
      true,
    )
    const packageRelative = path.relative(dsDir, filePath).split(path.sep).join('/')
    const quoted = (list) => list.map((item) => `\`${item}\``).join(', ')
    const specifiers = findStoryModuleImports(moduleSource)
    if (specifiers.length > 0) {
      manifestProblems.push({
        kind: 'imports-story-module',
        location: packageRelative,
        detail:
          `${packageRelative} imports a *.stories module (${quoted(specifiers)}): ` +
          "a story file is Storybook's, and a reference to its bindings from another file is one this " +
          'pass cannot see, so a tag or a force set that way is invisible here. Only a *.test.* file may ' +
          'import one; share what both need from a module that is not a story file.',
      })
    }
    const nonLiteral = findNonLiteralSpecifiers(moduleSource)
    if (nonLiteral.length > 0) {
      manifestProblems.push({
        kind: 'imports-story-module',
        location: packageRelative,
        detail:
          `${packageRelative} calls import() or require() with a non-literal specifier (${quoted(nonLiteral)}): ` +
          'a templated or concatenated specifier is compiled into a glob over every file its static parts ' +
          'can match, which can include a *.stories module, and this pass does not read what such a ' +
          'specifier loads, whatever it ends with. Write every specifier of a module that is not a test ' +
          'as a plain string literal, or move the dynamic load into a *.test.* file.',
      })
    }
    const requireRefs = findRequireReferences(moduleSource)
    if (requireRefs.length > 0) {
      manifestProblems.push({
        kind: 'imports-story-module',
        location: packageRelative,
        detail:
          `${packageRelative} references the identifier \`require\` other than as a declared name or as the ` +
          `direct callee of a call (${quoted(requireRefs.map((ref) => `line ${ref.line}: ${ref.text}`))}): ` +
          'a parenthesised, cast, aliased or passed `require` loads a specifier this pass does not read, ' +
          "which can be a *.stories module. In a module that is not a test, write `require('…')` " +
          'directly with a plain string literal, or move the load into a *.test.* file.',
      })
    }
    const globs = findImportMetaGlobs(moduleSource)
    if (globs.length > 0) {
      manifestProblems.push({
        kind: 'imports-story-module',
        location: packageRelative,
        detail:
          `${packageRelative} calls import.meta.glob (${quoted(globs)}): the files a pattern loads are ` +
          'not read here, and a pattern can reach a *.stories module without ending in `.stories` ' +
          '(`../src/**/*.stories.@(ts|tsx)`, `./*.stories.{ts,tsx}`, `./*`), so none is allowed in a ' +
          'module that is not a test. List the modules by name, or move the glob into a *.test.* file.',
      })
    }
    const testImports = findTestModuleImports(moduleSource)
    if (testImports.length > 0) {
      manifestProblems.push({
        kind: 'imports-test-module',
        location: packageRelative,
        detail:
          `${packageRelative} imports a *.test.* module (${quoted(testImports)}): a test module is not ` +
          'read by this pass, so a story module it imports, and what it does to that story, is ' +
          'invisible here. Only a *.test.* file may import one; share what both need from a module ' +
          'that is not a test.',
      })
    }
  }

  for (const filePath of [...storySources.keys()].sort()) {
    const sourceFile = sourceFiles.get(filePath) ?? parseTsx(filePath, storySources.get(filePath))
    const packageRelative = path.relative(dsDir, filePath).split(path.sep).join('/')
    const repositoryRelative = relPath(filePath)
    const homeKey = storyHomeKey(filePath)
    // T701: the one meta object is the default export's, read by `readDefaultExport`; a file whose
    // default export is not readable has none, and is named for it below. Nothing is read from the
    // first object in the file that happens to carry a `component`.
    const { object: metaObj, problem: defaultProblem } = readDefaultExport(sourceFile)
    const ownPrimitive = metaObj ? metaComponentName(metaObj) : null
    const ownTracked = ownPrimitive && PRIMITIVE_NAMES.includes(ownPrimitive) ? ownPrimitive : null
    const constNodeMap = buildTopLevelConstNodeMap(sourceFile)
    const topLevelDeclarations = findTopLevelDeclarations(sourceFile)

    const exportedStories = findExportedStoryObjects(sourceFile)
    // T697: what the file references outside its declarations and exports, among the stories and the
    // bindings the default export names. A reference to a default-export binding names every story.
    const defaultBindings = findDefaultExportBindings(sourceFile)
    const referencedAt = findBindingReferences(
      sourceFile,
      new Set([...exportedStories.map((story) => story.exportName), ...defaultBindings]),
    )
    const defaultReference = [...defaultBindings].find((name) => referencedAt.has(name))
    const referenceTo = (exportName) => {
      if (referencedAt.has(exportName)) {
        return { name: exportName, line: referencedAt.get(exportName), viaDefault: false }
      }
      if (defaultReference === undefined) return null
      return { name: defaultReference, line: referencedAt.get(defaultReference), viaDefault: true }
    }
    for (const { exportName, node } of exportedStories) {
      const location = `${packageRelative}#${exportName}`
      if (defaultProblem) {
        manifestProblems.push({
          kind: defaultProblem.kind,
          location: `${packageRelative}:${exportName}`,
          detail:
            defaultProblem.kind === 'unreadable-default-export'
              ? `the default export of ${packageRelative} is not one this pass can read: ` +
                `${defaultProblem.reason}. Story ${exportName} reads its tags and parameters from it, ` +
                'so it is credited nothing. Write `export default meta` (or `export { meta as ' +
                'default }`) over one top-level `const meta = { … }` object literal, or an inline ' +
                '`export default { … }`; `!`, `as`, `satisfies` and parentheses around either are read ' +
                'through.'
              : `binding \`${defaultProblem.binding}\` of ${packageRelative} ${defaultProblem.reason} ` +
                `The default export names it, so story ${exportName} reads its tags and parameters from it.`,
        })
      }
      // A fixture story is a plant, not a published story, whichever directory it sits in: every other
      // reader of the stories (`scripts/visual/story-index.mjs`) identifies one by its tag, so this does
      // too. It credits nothing and its manifest entry is not stale.
      const { tags, unreadable: tagsUnreadable } = readStoryTags(metaObj, node)
      if (tags.has(FIXTURE_TAG)) {
        seenLocations.add(location)
        continue
      }
      if (tagsUnreadable) {
        manifestProblems.push({
          kind: 'unreadable-tags',
          location: `${packageRelative}:${exportName}`,
          detail:
            `story ${exportName} of ${packageRelative} carries a \`tags\` that is not an array of ` +
            'string literals, or its story object or default export spreads another object (which may ' +
            'bring one), or either object has a `tags` this pass cannot read by name (a quoted or ' +
            'computed key, an accessor, a method, a property written twice) or a computed key it ' +
            'cannot evaluate, or either object has an accessor, a method or a `this` anywhere in it ' +
            `(T704), so this pass cannot tell whether it is a ${FIXTURE_TAG} story. Write ` +
            'the tags as one identifier-keyed array of string literals and spread nothing into the ' +
            'story or the default export, which carry no accessor, method or `this`.',
        })
      }
      const reference = referenceTo(exportName)
      if (reference) {
        manifestProblems.push({
          kind: 'referenced-after-declaration',
          location: `${packageRelative}:${exportName}`,
          detail:
            `story ${exportName} of ${packageRelative} is referenced outside its declaration and an ` +
            `export: \`${reference.name}\` at line ${reference.line}` +
            (reference.viaDefault
              ? ', the binding the default export names, whose tags and parameters every story of the file reads'
              : '') +
            '. Storybook reads what such a reference does to the object, and this pass reads the ' +
            'object literal, so a tag or a force it sets is invisible here. Write every annotation inside ' +
            'the object literal, and name the binding only in its declaration and in `export default`.',
        })
      }
      const storyBindingProblem = bindingDeclarationProblem(topLevelDeclarations, exportName)
      if (storyBindingProblem) {
        manifestProblems.push({
          kind: storyBindingProblem.kind,
          location: `${packageRelative}:${exportName}`,
          detail: `binding \`${exportName}\` of ${packageRelative} ${storyBindingProblem.reason}`,
        })
      }
      const found = entriesByLocation.get(location)
      if (!found) {
        manifestProblems.push({
          kind: 'no-entry',
          location: `${packageRelative}:${exportName}`,
          detail:
            `story ${exportName} of ${packageRelative} has no entry in ${MANIFEST_PATH} — it was ` +
            `added or renamed without recording what a browser renders for it. Build Storybook ` +
            `(\`${BUILD_STORYBOOK_COMMAND}\`) and run \`${REWRITE_COMMAND}\` to refresh the manifest.`,
        })
        continue
      }
      seenLocations.add(location)
      const { entry } = found
      const forced = extractVisualForceState(node)
      const recordsAForce = Object.values(entry.widths ?? {}).some((record) => record?.force)
      const parametersUnreadable = hasUnreadableParameters(node)
      const metaParametersUnreadable =
        !parametersUnreadable && hasUnreadableNamedParameters(metaObj)
      if (parametersUnreadable) {
        manifestProblems.push({
          kind: 'unreadable-parameters',
          location: `${packageRelative}:${exportName}`,
          detail:
            `story ${exportName} of ${packageRelative} carries a \`parameters\` that is not an object ` +
            'literal (an identifier, a call), or one this pass cannot read by name (a quoted or computed ' +
            'key, an accessor, a method, a property written twice, a computed key it cannot evaluate, ' +
            'or such a `visualForceState` inside it), or the story object has an ' +
            'accessor, a method or a `this` anywhere in it (T704), so this pass cannot read its ' +
            '`visualForceState`. Write the parameters as an object ' +
            'literal in the story, every key an identifier written once, and no accessor, method or `this` ' +
            'in the story object.',
        })
      } else if (metaParametersUnreadable) {
        // The default export's `parameters` is named for the same shapes, on every story of the file.
        manifestProblems.push({
          kind: 'unreadable-parameters',
          location: `${packageRelative}:${exportName}`,
          detail:
            `the default export of ${packageRelative} carries a \`parameters\` this pass cannot read by ` +
            'name (a quoted or computed key, an accessor, a method, a property written twice, a ' +
            'computed key it cannot evaluate, or such a `visualForceState` ' +
            'inside it), or has an accessor, a method or a `this` anywhere in it (T704), so it cannot ' +
            `read the \`visualForceState\` of story ${exportName}. Write the parameters as an object ` +
            'literal, every key an identifier written once, and no accessor, method or `this` in the ' +
            'default export.',
        })
      }
      // A forced state outside the three the harness drives (`hover`, `focus-visible`, `active`) is
      // rejected before anything is credited from it: an unknown string would credit the record-3
      // column of that name (`disabled`, `rest`) or throw at record 1, and a case variant or a
      // non-string is a state the browser does not apply either (T696). The manifest records no state,
      // only the force's target, so `parameters.visualForceState` is the one place it is read.
      if (
        forced &&
        !(typeof forced.state === 'string' && Object.hasOwn(RECORD1_STATE_HEADERS, forced.state))
      ) {
        manifestProblems.push({
          kind: 'unknown-force-state',
          location: `${packageRelative}:${exportName}`,
          detail:
            `story ${exportName} of ${packageRelative} forces state ${show(forced.state)}, which is ` +
            `none of ${Object.keys(RECORD1_STATE_HEADERS).join(', ')}: the harness applies only those, ` +
            'spelled exactly so.',
        })
        continue
      }
      if (!forced && recordsAForce && !parametersUnreadable) {
        manifestProblems.push({
          kind: 'unreadable-force',
          location: `${packageRelative}:${exportName}`,
          detail:
            `${MANIFEST_PATH} records a force target for story ${exportName} of ${packageRelative}, ` +
            'but its visualForceState carries no string-literal state this pass can read, so the ' +
            'frame it shows is accounted for nowhere. Give it a literal state.',
        })
      }
      const playBody = resolvePlayBody(node, sourceFile)
      const playFocusStatic = forced ? null : findPlayFocusTarget(playBody)
      const playClick = forced ? null : findPlayClickTarget(playBody)
      // The shape of the entry, before anything is read from it: a malformed one fails the check
      // naming the story, and credits nothing.
      // An entry another entry shares its story with is reported once, by key, above; the story reads
      // as malformed without a second report.
      const duplicated = found.duplicateIds.length > 1
      const shapeProblem = duplicated
        ? `${found.duplicateIds.length} entries (${found.duplicateIds.join(', ')}) name this story`
        : (filesProblem(entry) ??
          entryShapeProblem(entry, {
            forced: Boolean(forced || recordsAForce),
            knownAxisValues,
          }))
      if (shapeProblem && !duplicated) {
        manifestProblems.push({
          kind: 'malformed-entry',
          location: `${packageRelative}:${exportName}`,
          detail:
            `${MANIFEST_PATH}'s entry (${found.id}) for story ${exportName} of ${packageRelative} is ` +
            `malformed: ${shapeProblem}. Run \`${REWRITE_COMMAND}\` to rewrite it.`,
        })
      }
      // What the capture shows of this story, for the credit its mounts give (Disabled, and Rest of a
      // primitive's own story), read from the record the browser wrote and from nothing in the story's
      // source (T703). The manifest records which instances a story mounts, and, per width, whether a
      // `visualCaptureClip` applied (`readCaptureClip` on the settled story, so a clip written from
      // `play`, a loader or a decorator, through the `story` annotation, a `__proto__` key, the preview
      // or `Object.prototype` is in it when the browser applied it; the tests of the shapes through the
      // preview, a module importing it or a `config.tsx` feed this check a hand-written record, so no
      // browser has shown that those shapes clip) and whether the built index tags the frame
      // `visual-full-page`.
      //   - a clip at ANY captured width: the story is screenshotted through that clip alone, so it gives
      //     no mount credit (the record does not say whether a mount lies inside the clipped rect);
      //   - no clip, and not full-page at some width: a screenshot of the root element's box
      //     (`tests/visual/stories.spec.ts`), and an element in `position: fixed` need not intersect that
      //     box, so it gives none either when a design-system file it rendered carries one
      //     (`findOverlayFiles`);
      //   - otherwise the mounts credit.
      // The force's own credit is not narrowed by a clip: `applyForceState` and `resolveCaptureClip`
      // (`tests/visual/story-render.ts`) share only `locateTarget`, so nothing in the capture ties the
      // located element to the clip. The nightly state-signal sweep fails a forced story whose state
      // frame differs from its rest frame by no more than the threshold inside the captured frame; it
      // does not check that the target lies in the clip.
      // A story whose source this pass was refused a reading of (a reference to its binding, a default
      // export it cannot read, a binding declared twice or with `var` or `let`, a `parameters` or `tags`
      // it cannot read by name) fails the run for it below; it also gives no mount credit, the safe
      // direction, though the record is what decides every other story.
      const widthRecords = shapeProblem ? [] : Object.values(entry.widths)
      const clipped = widthRecords.some((record) => record.clip === true)
      const fullPage = widthRecords.length > 0 && widthRecords.every((record) => record.fullPage)
      const sourceUnread =
        reference !== null ||
        defaultProblem !== null ||
        storyBindingProblem !== null ||
        parametersUnreadable ||
        metaParametersUnreadable ||
        tagsUnreadable
      // `files` is read only once it is known to be an array of strings (`filesProblem`).
      const entryFiles = filesProblem(entry) ? [] : entry.files
      // `oneThemeFiles` (T711) is read only once `entryShapeProblem` has found it well-formed.
      const entryOneThemeFiles = shapeProblem ? [] : (entry.oneThemeFiles ?? [])
      const mayRenderOutsideRoot =
        !clipped && !fullPage && entryFiles.some((file) => overlayFiles.has(file))
      const mountCredit = !shapeProblem && !sourceUnread && !clipped && !mayRenderOutsideRoot
      // The two themes disagree on the focus at some width (T711, `combineThemeRecords`): one capture
      // shows an element focused that the record names none for, so the Rest credit of this story's own
      // mounts is withheld at every width, the placing instance and any other alike. The Disabled
      // credit does not read the focus and is unchanged.
      const focusDisagrees = widthRecords.some((record) => record.focusDiffersByTheme === true)
      const restCredit = mountCredit && !focusDisagrees
      let verdict = null
      if (shapeProblem) {
        verdict = { refusal: `the manifest entry is malformed (${shapeProblem})` }
      } else if (forced) {
        verdict = resolveRuntimeForce(entry, { recordOneKeys, knownAxisValues })
      }
      const focus = !forced && playFocusStatic && !shapeProblem ? stableFocus(entry) : null
      const label = storyLabel(filePath, exportName)

      // Record 1 and the element matrices: one entry in the story's own component's list (accounting
      // and bare-name printing read it there), and, when the credited or focused element belongs to
      // another component, a synthetic copy in that one's list under the qualified label.
      const credit = verdict && !verdict.refusal && verdict.stamp ? { stamp: verdict.stamp } : null
      const focusStamp = focus?.stamp && recordOneKeys.has(focus.stamp) ? focus.stamp : null
      const common = {
        argsLiterals: new Set(storyArgsStringLiterals(metaObj, node, constNodeMap)),
        playClick,
        // A malformed entry cannot say which files exactly one theme rendered, so no click credit reads its files.
        files: shapeProblem ? [] : entryFiles,
        oneThemeFiles: entryOneThemeFiles,
      }
      pushStateEntry(homeKey, {
        ...common,
        exportName,
        storyFile: path.basename(filePath),
        forced,
        credit,
        focusStamp,
        refusal: verdict?.refusal ?? null,
      })
      for (const stamp of new Set([credit?.stamp, focusStamp].filter(Boolean))) {
        const owner = elementOwner.get(stamp)
        if (owner === undefined || owner === homeKey) continue
        pushStateEntry(owner, {
          ...common,
          exportName: label,
          forced: stamp === credit?.stamp ? forced : null,
          credit: stamp === credit?.stamp ? credit : null,
          focusStamp: stamp === focusStamp ? focusStamp : null,
          synthetic: true,
        })
      }
      if (verdict && !verdict.refusal) {
        for (const note of verdict.notes) {
          partialRefusals.push({ componentKey: homeKey, exportName, note })
        }
      }

      // Record 3: the tracked instances the story mounts, as the browser rendered them.
      const placingForce = verdict && !verdict.refusal ? verdict.placedBy : null
      const placingFocus = focus?.placedBy ?? null
      let forceUsed = false
      let focusUsed = false
      const pushInstance = (mount, row, role) => {
        instancesByPrimitive.get(mount.component).push({
          primitive: mount.component,
          kind: mount.component === ownTracked ? 'own-story' : 'composed-story',
          componentKey: homeKey,
          file: repositoryRelative,
          storyName: exportName,
          variant: row.variant,
          size: row.size,
          disabled: mountCredit && (mount.disabledAt ?? []).length > 0,
          forced: role === 'force' ? forced : null,
          playFocus: role === 'focus',
          rest: restCredit && role === null && mount.component === ownTracked && !forced,
        })
      }
      for (const mount of shapeProblem ? [] : stableMounts(entry)) {
        if (!PRIMITIVE_NAMES.includes(mount.component)) continue
        const row = rowAxesOf(mount)
        if (row.reason) {
          unkeyedMounts.push({ componentKey: homeKey, exportName, reason: row.reason })
          continue
        }
        let role = null
        if (placingForce && !forceUsed && sameInstance(mount, placingForce)) {
          role = 'force'
          forceUsed = true
        } else if (placingFocus && !focusUsed && sameInstance(mount, placingFocus)) {
          role = 'focus'
          focusUsed = true
        }
        const credited = role !== null || (mountCredit && (mount.disabledAt ?? []).length > 0)
        if (credited || (restCredit && mount.component === ownTracked && !forced)) {
          pushInstance(mount, row, role)
        }
      }
      // The placing instance is always among a story's mounts; a manifest that disagrees still
      // credits the instance the force located, which is what the browser reported.
      if (placingForce && !forceUsed) pushInstance(placingForce, placingForce.row, 'force')
      if (placingFocus && !focusUsed) {
        const row = rowAxesOf(placingFocus)
        if (!row.reason && PRIMITIVE_NAMES.includes(placingFocus.component)) {
          pushInstance(placingFocus, row, 'focus')
        }
      }
    }
  }
  for (const [location, { id, duplicateIds }] of entriesByLocation) {
    if (seenLocations.has(location) || duplicateIds.length > 1) continue
    const [file, exportName] = location.split('#')
    manifestProblems.push({
      kind: 'stale-entry',
      location: `${file}:${exportName}`,
      detail:
        `${MANIFEST_PATH} has an entry (${id}) for ${exportName} of ${file}, but no story of that ` +
        `name is exported there as an object literal this pass reads. Run \`${REWRITE_COMMAND}\` ` +
        'to drop it, or restore the story.',
    })
  }

  // Print order: a component's own stories before the credits other components' stories give its
  // elements, and a primitive's call sites and own stories in source order before the composed stories
  // that mount it — the order the region has always read in, so a credit that did not change does not
  // move.
  for (const entries of storyStatesByComponent.values()) {
    entries.sort((a, b) => Number(Boolean(a.synthetic)) - Number(Boolean(b.synthetic)))
  }
  for (const instances of instancesByPrimitive.values()) {
    const rank = (inst) => (inst.kind === 'composed-story' ? 1 : 0)
    instances.sort((a, b) => rank(a) - rank(b) || (a.file < b.file ? -1 : a.file > b.file ? 1 : 0))
  }

  qualifyStoryNamesWhereAmbiguous(storyStatesByComponent)

  // One line per component directory, the ones with nothing to report included, so Record 1 can be
  // counted against `story-docs.mjs`'s own directory count (T594's own text).
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

  // The region's own rendered text, read back by `findUnaccountedForceStates` — what a reader opens,
  // never a second derivation of the same credits.
  const regionTextForAccounting = renderGeneratedRegion({
    componentDirCount: componentDirs.length,
    localElements,
    matrices,
  })

  return {
    componentDirCount: componentDirs.length,
    localElements,
    matrices,
    manifestProblems,
    // A forced story one half of whose credit was refused while the other half credited (a `Menu`
    // mounted with no `variant`: its trigger's record-1 cell is credited, no record-3 row exists).
    partialRefusals,
    // A mounted tracked instance with no row to land on, so its `Rest` and `Disabled` credit is not given.
    unkeyedMounts,
    unaccountedForceStates: findUnaccountedForceStates(
      storyStatesByComponent,
      regionTextForAccounting,
    ),
  }
}

export function describeMissingForceState({ componentKey, exportName, state, refusal }) {
  if (refusal) {
    return `${componentKey}'s ${exportName} forces "${state}" and is credited on no cell: ${refusal}.`
  }
  return (
    `${componentKey}'s ${exportName} forces "${state}" and the manifest places its frame, but no ` +
    'cell of the region names it — a lost frame.'
  )
}

// --- Matrix building -------------------------------------------------------------------------

// The row an instance lands on: its `variant|size` pair (an axis the primitive has none of is left
// out), or `null` when an axis the primitive keys its rows on has no settled value. A call site whose
// `variant` or `size` the source cannot settle (a forwarded prop, a computed expression, an axis
// attribute followed by a spread, or an axis it omits beside a spread anywhere) is the second case: it
// opens no row of its own (T695, T700), because the instances it mounts are credited at the rows the
// browser rendered them to, from the manifest, and a row named for an axis nothing resolved is one no
// story's frame can ever reach.
function axisKey(inst) {
  const parts = []
  for (const axis of [inst.variant, inst.size]) {
    if (axis?.resolved === 'n/a') continue
    if (axis?.value == null) return null
    parts.push(axis.value)
  }
  return parts.join('|') || '(no axis)'
}

function cellName(inst) {
  if (inst.kind === 'own-story' || inst.kind === 'composed-story')
    return storyLabel(inst.file, inst.storyName)
  return `${inst.componentKey}`
}

// Record 3 for one tracked primitive: one row per `variant|size` pair any instance lands on, one
// column per state. Two kinds of instance feed it:
//   - `jsx`: a call site in a design-system component file, read statically — its row is its literal
//     or default axis, and a call site with a dynamic axis opens no row (T695, `axisKey`). It fills
//     `Rest` and nothing else.
//   - `own-story` / `composed-story`: an instance the runtime manifest says a story mounted (T694,
//     `scripts/visual/state-coverage-runtime-model.mjs`), already placed on the row the browser
//     rendered it at — never resolved here. `forced` names the state the story's frame depicts at
//     this instance (the instance whose own element the force located), `playFocus` marks the instance
//     that holds focus after a `play()` that asserts it, `disabled` that the DOM reports one of its own
//     elements disabled, and `rest` that the story is a primitive's own and mounts it at rest.
// A cell is the story labels that credit it, `unresolved: <reason>` when only a play-driven focus
// note exists (never provable as a `:focus-visible` frame, T594's amendment), or `none`.
export function buildAxisMatrix(primitiveName, instances) {
  const rows = new Map()
  function rowFor(key) {
    if (!rows.has(key)) {
      rows.set(key, {
        key,
        rest: [],
        hover: [],
        'focus-visible': [],
        active: [],
        disabled: [],
        // A play-driven focus-visible note: the script can leave a real `:focus-visible` on a fresh
        // page, or the same frame a preceding story already captured, and cannot tell which, so it is
        // never a confirmed cover. A real match for the same cell outranks it.
        unresolvedByState: { hover: [], 'focus-visible': [], active: [], disabled: [] },
      })
    }
    return rows.get(key)
  }
  for (const inst of instances) {
    const key = axisKey(inst)
    if (key === null) {
      // A manifest instance is placed at the row the browser rendered, `rowAxesOf` having refused
      // one with no value on a keyed axis before it got here; only a call site read from the source
      // can arrive unsettled.
      if (inst.kind !== 'jsx') {
        throw new Error(
          `${primitiveName}: a ${inst.kind} instance (${inst.storyName ?? inst.file}) has no settled ` +
            'variant or size, and only a call site read from the source may land on no row.',
        )
      }
      continue
    }
    const row = rowFor(key)
    if (inst.kind === 'jsx') {
      row.rest.push(`${inst.componentKey} (${inst.file}:${inst.line})`)
      continue
    }
    const label = cellName(inst)
    if (inst.disabled) row.disabled.push(label)
    if (inst.forced) {
      const stateKey = inst.forced.state
      if (row[stateKey]) row[stateKey].push(label)
    } else if (inst.playFocus) {
      row.unresolvedByState['focus-visible'].push(
        `${label} (play-driven; frame not provable statically)`,
      )
    } else if (inst.rest !== false) {
      row.rest.push(label)
    }
  }
  return [...rows.values()]
    .sort((a, b) => a.key.localeCompare(b.key))
    .map((row) => {
      const cellFor = (stateList, unresolvedList) => {
        if (stateList.length) return [...new Set(stateList)]
        if (unresolvedList.length) return [`unresolved: ${[...new Set(unresolvedList)].join('; ')}`]
        return ['none']
      }
      return {
        variantSize: row.key,
        rest: row.rest.length ? [...new Set(row.rest)] : ['none'],
        hover: cellFor(row.hover, row.unresolvedByState.hover),
        focusVisible: cellFor(row['focus-visible'], row.unresolvedByState['focus-visible']),
        active: cellFor(row.active, row.unresolvedByState.active),
        disabled: cellFor(row.disabled, row.unresolvedByState.disabled),
      }
    })
}

// An element's role as a user agent derives it: its own `role` attribute, else its tag's intrinsic
// role. `null` for a dynamic `role={...}` (`MenuItemRow`'s own), which this pass cannot read. Only the
// static `play()`-click path below still compares by role (T694): a forced story is credited by the
// stamp the browser reports, never by role.
function impliedRoleOf(el) {
  return el.role === 'unresolved' ? null : el.role || (INTRINSIC_ROLE[el.tag] ?? null)
}

// The `play()`-click path's own name match: the one static credit left (T694 — the manifest records
// no click, so a click story's target is still read from the script). `name` is matched against each
// pool member's literal text, then against the story's own `args` strings; a name that neither
// settles is `'ambiguous'`, never a guess. With no name, safe only when the candidate is the pool's
// sole member.
function resolveClickMatch({ candidate, pool, name, argsLiterals }) {
  if (name) {
    const directTextMatches = pool.filter((c) => c.text && c.text.includes(name))
    if (directTextMatches.length > 1) return 'ambiguous'
    if (directTextMatches.length === 1)
      return directTextMatches[0] === candidate ? 'match' : 'reject'
    const inArgs = [...(argsLiterals ?? [])].some((lit) => lit.includes(name))
    return inArgs && pool.length === 1 ? 'match' : 'ambiguous'
  }
  return pool.length === 1 ? 'match' : 'ambiguous'
}

// One element's own cells and notes, from the story entries of its component. Three sources, in
// the order they are read:
//   - a forced story credits the element whose `file:line` is the stamp the browser reported for the
//     force's target (`entry.credit.stamp`, from `resolveRuntimeForce`) — role, name, `nth`, guards
//     and spreads are the browser's to settle, not this pass's (T694);
//   - a `play()` that asserts focus leaves a note on the element the browser says held focus
//     (`entry.focusStamp`) — never a cover, the script cannot tell a `:focus-visible` frame from the
//     one a preceding story captured (T594's amendment);
//   - a `play()` click credits an `activeStateConditional` element statically (`entry.playClick`),
//     only when the story's rendered files include the element's own file and that file is not in the
//     entry's `oneThemeFiles` (T711): the capture shows both themes, and an element of a file only one
//     of them rendered is not on the other's frame.
function buildElementCells(el, elements, storyObjectsAsEntered) {
  const storyObjectsWithMeta = asPrinted(storyObjectsAsEntered)
  const impliedRole = impliedRoleOf(el)
  const key = `${el.file}:${el.line}`
  const pool = elements.filter((o) => impliedRoleOf(o) === impliedRole && !o.ariaHidden)
  const cells = { hover: [], 'focus-visible': [], active: [] }
  const ambiguousReasons = { hover: [], 'focus-visible': [], active: [] }
  for (const {
    exportName,
    forced,
    credit,
    focusStamp,
    playClick,
    argsLiterals,
    files,
    oneThemeFiles,
  } of storyObjectsWithMeta) {
    if (forced) {
      if (credit?.stamp === key) cells[forced.state].push(exportName)
      continue
    }
    if (focusStamp === key) {
      ambiguousReasons['focus-visible'].push(
        `${exportName} (play-driven; frame not provable statically)`,
      )
      continue
    }
    if (
      el.activeStateConditional &&
      playClick &&
      impliedRole &&
      (playClick.role === impliedRole || playClick.role === 'unresolved') &&
      Array.isArray(files) &&
      files.includes(el.file) &&
      !(oneThemeFiles ?? []).includes(el.file) &&
      !el.ariaHidden
    ) {
      const verdict = resolveClickMatch({
        candidate: el,
        pool,
        name: playClick.name,
        argsLiterals,
      })
      if (verdict === 'match') cells.active.push(exportName)
      else if (verdict === 'ambiguous') {
        ambiguousReasons.active.push(
          `${exportName} (play-click-driven): ${pool.length} candidates share role ${JSON.stringify(impliedRole)}${playClick.name ? `, name ${JSON.stringify(playClick.name)} not literally resolvable` : ''}`,
        )
      }
    }
  }
  return { el, impliedRole, cells, ambiguousReasons }
}

// The 13 primitives with no `variant`/`size` axis of their own get one row per distinct local
// element `findLocalElements` found in their own index.tsx, and record 1 prints the same cells for
// every component's local elements: a cell lists the stories that credit it (`buildElementCells`), a
// `play()`-driven note as `unresolved: <reason>`, and `'none'` otherwise — a state no story's frame
// was located on, by the browser, at this element.
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
  // T595 (row 8, H5, the "ancestor of a forced descendant" family): `hover` and
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
  // for that state (nothing to credit when nothing paints), and only a *confirmed* descendant credit
  // counts.
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
  return perElement.map(({ el, cells, ambiguousReasons }) => {
    const cellFor = (state) =>
      cells[state].length > 0
        ? [...new Set(cells[state])]
        : ambiguousReasons[state].length > 0
          ? [`unresolved: ${ambiguousReasons[state].join('; ')}`]
          : ['none']
    // No credit exists for the Disabled cell of a record-1 element: the manifest records disabled
    // elements only among a tracked primitive's own (record 3), and a story's `args` are not what
    // renders, so a `disabled: true` in them proves nothing about an instance. Every cell is `none`.
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

// T671: `el.active` stays literal-only (every other reader of it keeps meaning exactly what it
// always has — see `activeStateConditional`'s own comment at `findLocalElements`); this is the one
// place a state-conditional ternary (`Tooltip`'s own `pinned ? 'border-border-strong' :
// 'border-transparent'`) needs to be human-readable at all, so the printed cell never shows the
// misleading bare `'none'` a real, painted conditional class would otherwise read as.
function activeClassText(activeText, stateConditional) {
  if (!stateConditional) return activeText
  const conditionalText = `${stateConditional.identifier} ? ${stateConditional.whenTrue} : ${stateConditional.whenFalse}`
  return activeText ? `${activeText} ${conditionalText}` : conditionalText
}

// The two table shapes the region prints, one source for the renderers below and for the reader
// that locates a state's column by its header text (`parseStateColumns`, T684) — a renamed header
// is then one edit, never a silent mismatch between what is printed and what is read back.
const RECORD1_STATE_HEADERS = {
  hover: 'Hover (class → story)',
  'focus-visible': 'Focus-visible (class → story)',
  active: 'Active (class → story)',
}
const RECORD3_STATE_HEADERS = {
  hover: 'Hover',
  'focus-visible': 'Focus-visible',
  active: 'Press (active)',
}
export const RECORD1_HEADERS = [
  'Component',
  'Element',
  'File:Line',
  ...Object.values(RECORD1_STATE_HEADERS),
]
export const RECORD3_HEADERS = ['Row', 'Rest', ...Object.values(RECORD3_STATE_HEADERS), 'Disabled']

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
        stateCell(
          activeClassText(el.active, el.activeStateConditional),
          el.coveredBy.active,
          classResolved,
        ),
      ])
    }
  }
  return table(RECORD1_HEADERS, rows)
}

export function renderMatrices(computed) {
  const sections = []
  for (const name of Object.keys(computed.matrices).sort()) {
    const rows = computed.matrices[name].map((row) => [
      row.variantSize,
      row.rest.length > 3 ? `${row.rest.length} credits` : row.rest.join('; '),
      row.hover.join('; '),
      row.focusVisible.join('; '),
      row.active.join('; '),
      row.disabled.join('; '),
    ])
    sections.push(`#### \`${name}\`\n\n${table(RECORD3_HEADERS, rows)}`)
  }
  return sections.join('\n\n')
}

// The credits that still rest on a static reading of source rather than on what a browser rendered,
// each with the words the region's legend uses to name it. The legend is built from this list and
// `state-coverage.test.mjs` pins both its ids and its phrases, so adding or deleting a static path
// without touching the legend fails a test.
export const STATIC_CREDITS = [
  {
    id: 'call-site-rest',
    legend:
      "`Rest`: a tracked primitive written in a design-system component file, never a story file, at the row its literal or default `variant` and `size` name (a Rest cell of more than three entries prints as `N credits`, which counts those call sites and the primitive's own stories together)",
  },
  {
    id: 'play-click',
    legend:
      'the `play()`-click credit of an element that paints `active` through a conditional class (the manifest records no click)',
  },
  {
    id: 'play-focus',
    legend:
      'which stories carry a `play()` that asserts focus (an `unresolved: ... (play-driven)` note, never a cover)',
  },
  {
    id: 'ancestor-inheritance',
    legend: 'the hover or active an ancestor inherits from a credited descendant',
  },
]

// What a reader needs to know about where each credit in the region comes from (T694): which are read
// from what a real browser rendered, which still rest on a static reading, which a story gives up, and
// the gaps that remain. Rendered inside the region, so it is regenerated, and checked, with the tables
// it describes.
export const REGION_LEGEND = [
  '**Where a credit comes from.** A forced story (`parameters.visualForceState`) credits a cell only',
  `by what a real browser rendered for it, recorded in \`${MANIFEST_PATH}\`: a record-1 cell when the`,
  'forced element is the one element found at every captured width and its source stamp is that',
  "element's `file:line`; a record-3 cell when the tracked primitive instance that placed it is at that",
  "row's variant and size. A force on an element whose stamp is in the placing instance's `disabledAt`",
  '(the host elements it placed that the browser reports `:disabled` or `aria-disabled="true"`) is',
  'refused, and so is a force the light and the dark render of the story answer differently (a',
  'different match count, stamp or placing instance, or a force only one theme carries).',
  "The Disabled column of every matrix, and a primitive's own stories' Rest column, come from",
  'the primitive instances a story mounts, as rendered, and from nothing else: a `disabled` or `loading`',
  "written at a call site, and a `disabled: true` in a story's `args`, credit no Disabled cell. The",
  'instances credited are the ones the light and the dark render both mount. A story',
  'gives no mount credit when the browser applied a `visualCaptureClip` to it in either theme at any',
  'captured width (the manifest records, per width, whether one applied, read from the settled story',
  'the capture itself reads, in the light theme and in the dark one, so a clip no object literal spells',
  'counts; it does not record whether a mount lies inside the clipped rect); when it has no clip, the',
  'built index does not tag it `visual-full-page` (also recorded per width) and it rendered a',
  'design-system file with an unprefixed `fixed` class (that element need',
  'not intersect the root box it is screenshotted as); or when its source is one this pass was refused',
  'a reading of, which also fails the run naming the story: the story or the default export is',
  'referenced outside its declaration and an export, the default export is not one this pass reads, a',
  'story or meta binding is declared twice or with `var` or `let`, its `parameters` is not an object',
  'literal, or its `parameters` or `tags` cannot be read by name (a quoted, computed or duplicated key,',
  'an accessor, a method, or a `this` in the',
  'story object or the default export), or its story object or default export spreads another object',
  '(its `tags` cannot be read). A tracked primitive',
  'written in a story file credits nothing. An entry that records no boolean `clip` and `fullPage` at',
  'every captured width fails the run, naming the story, and credits nothing. Every other forced story',
  'credits no cell and the check fails naming why (a filed, dated exception is the one way to tolerate',
  'it), except that a force whose located element is a record-1 element and whose placing instance has',
  'no matrix row credits that record-1 cell and names the record-3 half in a note; any other is refused',
  'like the rest. A manifest entry of the wrong shape fails the check, naming the story.',
  '',
  '**Still static, and read from source:**',
  '',
  ...STATIC_CREDITS.map((credit) => `- ${credit.legend}`),
  '',
  '**Residual gaps, not refused:** a forced element no tracked primitive placed (a record-1 element of',
  'another component) is credited without knowing whether it renders disabled, because the manifest',
  "records disabled elements only among a tracked primitive's own; a mounted instance the page does not",
  'show (`hidden`, `sr-only`, `opacity-0`, a closed `details`) is credited as mounted, because the',
  'manifest records what mounts, not what paints; a story tagged `visual-full-page` is screenshotted as',
  'the viewport, so a disabled instance behind its scrim is credited though the scrim covers it; the',
  'unprefixed-`fixed` refusal reads only a string literal of a non-story, non-test design-system file',
  'whose whitespace-separated tokens include exactly `fixed`, so a `fixed` behind a variant prefix',
  '(`focus:fixed`, `md:fixed`, `max-md:fixed`), a `[position:fixed]` property, an absolutely',
  'positioned element, and a `fixed` element the story file itself positions are all still credited;',
  "and a clipped story's forced credit is not narrowed by the clip: the nightly state-signal sweep",
  'fails a forced story whose state frame differs from its rest frame by no more than its comparison',
  'threshold inside the captured frame, and it does not check that the forced target lies inside the',
  'clip, because the force target and the clip are located independently.',
].join('\n')

export function renderGeneratedRegion(computed) {
  return [
    `<!-- state-coverage:begin -->`,
    `_Generated by \`scripts/checks/state-coverage.mjs --write\`. Do not hand-edit between these markers — run the script instead._`,
    '',
    REGION_LEGEND,
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
      `primitive-matrix row — the "(no local interactive element)" row excluded): ${formatCounts(r3)}`,
  )
  return { record1: r1, record3: r3 }
}

// --- T595 (row 8, H5): bucket (b), "a state the component's own spec answers as impossible,
// which no frame can depict" ----------------------------------------------------------------------
//
// Row 8's own closing rule (T595's own words) needs a cell that is not covered by any story to be
// one of exactly two other things: a spec-confirmed impossibility, or a dated register entry.
// `spec-completeness.mjs` already asserts that a spec *answers* every one of the ten vocabulary
// states — it never reads what the answer *says*, so it cannot tell "never disabled" from "always
// disabled on hover" apart. This section is that missing read, built the same way every other
// mechanical reading in this row already is: reusing the bold-label convention
// `spec-completeness.mjs` itself parses (`isClauseLeadingBoldSpan`, `normaliseStateToken`, imported
// rather than re-derived — CLAUDE.md's own rule against a fact living in two files) rather than a
// hand-maintained list of component shapes, which T595 forbids outright.
//
// The closed vocabulary of phrasings that count as "impossible" is exactly the five the row 8
// survey found repeated, verbatim, across the 25 bullets sharing this convention — never widened by
// a sixth phrasing that merely *sounds* negative (`state-coverage.test.mjs`'s own contrast: a real,
// substantive answer like `structural-tier.md`'s own Field "active — the control's own text-entry
// state; no separate paint" is not a closed-vocabulary answer, and this recogniser declines it
// rather than guessing a sixth phrase into existence):
//   - `never`              — `structural-tier.md:667`, "a link is never disabled."
//   - `none;`              — `shared-primitives.md:285`, "hover / active — none; the root is not
//     interactive."
//   - `is not interactive` — the same bullet, a second, independent phrase.
//   - `has no visual form` — `shared-primitives.md:295`, "The heading's own frame therefore has no
//     visual form for this state."
//   - `has no active state` — `structural-tier.md:839-840`, "The table itself has no active state."
const IMPOSSIBLE_ANSWER_PATTERNS = [
  /\bnever\b/i,
  /\bnone;/i,
  /\bis not interactive\b/i,
  /\bhas no visual form\b/i,
  /\bhas no active state\b/i,
]

// Only the answer's own *leading* sentence is tested against the closed vocabulary above — never
// the whole, often paragraph-long, answer text. Every real citation above states its verdict in the
// clause immediately after the state's own label; what follows is justification, history or a
// correction, and a coincidental match buried in it can answer something else entirely rather than
// this state (found live: `tooltip.md:139`'s own "this used to say 'its `Button` state,' which was
// never true" is a correction about a stale sentence in this very file, not about the trigger's own
// `active` state, which the clauses right after it go on to describe as a real, painted press
// treatment; `manual-upload.md:184`'s own focus-visible answer names three composed controls' own
// rings in full and only says "never" four sentences later, about the ring's relationship to a
// boundary, not about whether this state happens; `archival-control.md`'s own hover answer opens
// "owned by `Button` and by the privacy link" and only reaches "is not interactive" in its *second*
// sentence, about the section wrapping the link, immediately followed by "**Not true of the shipped
// link today**" — the exact opposite of impossible. All three are `state-coverage.test.mjs`'s own
// contrast fixtures for this rule.) A trailing `**` is swallowed with the sentence's own closing
// mark (`structural-tier.md:667`'s own "— **a link is never disabled.**") rather than treated as
// prose that continues past it.
function leadingSentence(answerText) {
  const m = answerText.match(/^[\s\S]*?[.!?]\*{0,2}(?=\s|$)/)
  return m ? m[0] : answerText
}

export function answerSaysImpossible(answerText) {
  const lead = leadingSentence(answerText)
  return IMPOSSIBLE_ANSWER_PATTERNS.some((re) => re.test(lead))
}

// Every clause-leading bold span (`isClauseLeadingBoldSpan`) whose own split-and-normalised tokens
// (`normaliseStateToken`, applied per `/`- or `,`-separated part, the same fold `checkVocabulary`
// already applies) include at least one word from the closed state vocabulary — both a candidate
// *label* for a target state and a *boundary* the next label's own answer text stops at, the same
// dual role `checkVocabulary`'s own scan already gives a bold span, just kept as positions here
// instead of being reduced to a presence check.
export function findVocabularyBoundarySpans(specSource, vocabulary) {
  const vocabularySet = new Set(vocabulary)
  const spans = []
  for (const m of specSource.matchAll(/\*\*([^*\n]+)\*\*/g)) {
    if (!isClauseLeadingBoldSpan(specSource, m.index)) continue
    const tokens = m[1]
      .split(/[/,]/)
      .map((part) => normaliseStateToken(part))
      .filter((token) => vocabularySet.has(token))
    if (tokens.length === 0) continue
    spans.push({ raw: m[1], tokens, start: m.index, end: m.index + m[0].length })
  }
  return spans
}

// The one state label in `specSource` (scoped to `componentName`'s own section first, for a
// multi-component file) that answers `state`, and what its own answer text says — `'impossible'`
// only when that text matches the closed vocabulary above; `'decline'` for every other outcome,
// named with a reason rather than guessed: no per-component boundary to scope to (the "one shared
// numbered States section naming every component inline" shape `spec-completeness.mjs`'s own file
// header names — `match-history.md`, `player-search.md`, `privacy-data-rights.md` — has no such
// boundary, and reading the whole document unscoped risks crediting one component's clause to
// another's cell, the exact cross-component leak row 8 warns against, so this recognises the same
// shape `spec-completeness.mjs` falls back on but declines instead of falling back), the state
// answered zero or more than once in scope, or a real answer that simply does not use the closed
// vocabulary. The answer text runs from the end of the matched label to the start of the *next*
// vocabulary-boundary span (any span `findVocabularyBoundarySpans` found, not only this state's own
// label) — this is what keeps a *nested* emphasis inside the same answer (`structural-tier.md:667`'s
// own "— **a link is never disabled.**", itself a clause-leading bold span whose own token is "a",
// not a vocabulary word) from being mistaken for the *next* state's label and truncating the answer
// before the very phrase that answers it.
export function resolveSpecAnswerForState({
  specSource,
  components,
  componentName,
  state,
  vocabulary,
}) {
  let scopeText
  if (components.length === 1) {
    scopeText = specSource
  } else {
    const section = findComponentSection(specSource, componentName)
    if (section == null) {
      return {
        status: 'decline',
        reason:
          'multi-component file with no per-component heading to scope to (row 8 Method, "Records 2 and 4… no mechanical completeness guard")',
      }
    }
    scopeText = section
  }
  const spans = findVocabularyBoundarySpans(scopeText, vocabulary)
  const matches = spans.filter((s) => s.tokens.includes(state))
  if (matches.length === 0) {
    return {
      status: 'decline',
      reason: `spec never answers "${state}" in ${componentName}'s own scope`,
    }
  }
  if (matches.length > 1) {
    return {
      status: 'decline',
      reason: `"${state}" is answered more than once in ${componentName}'s own scope`,
    }
  }
  const [span] = matches
  const next = spans.find((s) => s.start > span.start)
  const answerText = scopeText.slice(span.end, next ? next.start : scopeText.length).trim()
  return answerSaysImpossible(answerText)
    ? { status: 'impossible', answerText }
    : {
        status: 'decline',
        reason: 'spec answers this state, but not with the closed impossible vocabulary',
        answerText,
      }
}

// The one `## Index` row (`parseIndexTable`, `spec-completeness.mjs`) whose own component cell
// names this `componentKey` (`"primitives/Link"` — `segment/name`, the same key
// `computed.localElements`/`computed.matrices` already use) — `null` when zero or more than one row
// claims it, never guessed (the Index is the single source `spec-completeness.mjs` itself already
// trusts for this, not a second, hand-written map).
export function mapComponentKeyToSpecFile(readmeSource, componentKey) {
  const [segment, name] = componentKey.split('/')
  const rows = parseIndexTable(readmeSource)
  const matches = rows.filter((row) =>
    row.components.some((c) => c.name === name && c.segment === segment),
  )
  if (matches.length !== 1) return null
  return { specFile: matches[0].specFile, components: matches[0].components, componentName: name }
}

// Record 1's own class half, read for exactly the state being judged — never `disabled`, which is
// not a pseudo-class at all (and a record-1 element's Disabled cell is never credited).
const RECORD1_STATE_CLASS_TEXT = {
  hover: (el) => el.hover,
  'focus-visible': (el) => combineFocusClassText(el.focus, el.focusVisible),
  active: (el) => el.active,
}

// Guard 1 (T595's own required contrast): a real `hover:`/`focus-visible:`/`active:` utility
// painted on the exact element is proof the component visually responds to this state — the cell is
// a story gap, never an impossibility, whatever a nearby spec sentence says. Checked before spec
// text is even read, the same "positive knowledge first" precedence row 8's own Method section
// already holds for `'none'` itself.
function record1CellIsPainted(el, state) {
  const classTextOf = RECORD1_STATE_CLASS_TEXT[state]
  return classTextOf ? classTextOf(el) != null : false
}

// A `record3` row's own local-element identity, when it is one (`"tag @ file:line"`, the shape
// `Table`/`Page`/`Dialog`/`Tooltip` — every primitive *outside* `PRIMITIVE_NAMES` — render, sharing
// record 1's own elements exactly rather than a second, axis-keyed set); `null` for an axis row
// (`"destructive|lg"`), which has no single element to pin a class check to at all.
function findRecord1ElementForRow(row, record1Elements) {
  const m = row.variantSize.match(/ @ (.+):(\d+)$/)
  if (!m) return null
  const [, file, lineStr] = m
  const line = Number(lineStr)
  return record1Elements.find((el) => el.file === file && el.line === line) ?? null
}

// Guard 2: a `'none'` cell is only eligible for an "impossible" verdict when *every* sibling row in
// the same scope reads `'none'` for this exact state too — a single sibling with real, positive
// coverage is proof the spec's own answer cannot describe every candidate the cell's own component
// carries, whatever wording it uses (`Table`'s own "the table itself has no active state" is real
// only of the scroll region, never of the row link one row down, which already carries
// `RowLinkActive`) — so this declines *every* `'none'` cell in the scope for that state rather than
// guess which one the spec sentence was really about, T595's own answer to the mapping risk this
// task's brief names explicitly.
function anySiblingCovered(cellsForState) {
  return cellsForState.some((coverageList) => classifyCoverage(coverageList) !== 'none')
}

export function classifyRecord1NoneCells(
  computed,
  { readmeSource, specSourcesByFile, vocabulary },
) {
  const results = []
  const STATES = ['hover', 'focus-visible', 'active']
  const coverageOf = (el, state) =>
    state === 'hover'
      ? el.coveredBy.hover
      : state === 'focus-visible'
        ? el.coveredBy.focusVisible
        : el.coveredBy.active
  for (const { componentKey, elements } of computed.localElements) {
    for (const state of STATES) {
      const siblingCovered = anySiblingCovered(elements.map((el) => coverageOf(el, state)))
      for (const el of elements) {
        if (classifyCoverage(coverageOf(el, state)) !== 'none') continue
        const base = { record: 1, componentKey, tag: el.tag, file: el.file, line: el.line, state }
        if (record1CellIsPainted(el, state)) {
          results.push({
            ...base,
            status: 'decline',
            reason:
              'a real class is painted for this state on this exact element — a story gap, never impossible',
          })
          continue
        }
        // Guard 1.5 (T595, group 3): an element that is inert by construction — `hidden` and
        // `tabIndex={-1}`, both literal (`isInertByConstruction`) — cannot receive a hover, a
        // focus-visible ring or a press in *any* frame, a source-level fact that outranks a
        // sibling's own coverage (which says nothing about whether *this* element can physically
        // carry the state) and needs no spec confirmation at all, the same "positive knowledge"
        // precedence guard 1 already holds for a painted class.
        if (el.inertByConstruction) {
          results.push({
            ...base,
            status: 'impossible',
            reason:
              'inert by construction: hidden and tabIndex={-1}, both literal — cannot receive pointer or focus in any frame',
          })
          continue
        }
        if (siblingCovered) {
          results.push({
            ...base,
            status: 'decline',
            reason: 'another local element in this component has real coverage for this same state',
          })
          continue
        }
        const mapping = mapComponentKeyToSpecFile(readmeSource, componentKey)
        if (!mapping) {
          results.push({
            ...base,
            status: 'decline',
            reason: 'component does not map to exactly one Index row',
          })
          continue
        }
        const specSource = specSourcesByFile.get(mapping.specFile)
        if (!specSource) {
          results.push({
            ...base,
            status: 'decline',
            reason: `spec file ${mapping.specFile} was not read`,
          })
          continue
        }
        const answer = resolveSpecAnswerForState({
          specSource,
          components: mapping.components,
          componentName: mapping.componentName,
          state,
          vocabulary,
        })
        results.push({
          ...base,
          status: answer.status,
          reason: answer.status === 'decline' ? answer.reason : undefined,
          answerText: answer.answerText,
        })
      }
    }
  }
  return results
}

export function classifyRecord3NoneCells(
  computed,
  { readmeSource, specSourcesByFile, vocabulary },
) {
  const results = []
  const STATES = ['hover', 'focus-visible', 'active', 'disabled']
  const coverageOf = (row, state) =>
    state === 'hover'
      ? row.hover
      : state === 'focus-visible'
        ? row.focusVisible
        : state === 'active'
          ? row.active
          : row.disabled
  for (const [primitiveName, rows] of Object.entries(computed.matrices)) {
    const realRows = rows.filter(
      (row) =>
        row.variantSize !== '(no local interactive element)' &&
        !row.variantSize.startsWith('(unresolved matches'),
    )
    const componentKey = `primitives/${primitiveName}`
    const record1Elements =
      computed.localElements.find((x) => x.componentKey === componentKey)?.elements ?? []
    for (const state of STATES) {
      const siblingCovered = anySiblingCovered(realRows.map((row) => coverageOf(row, state)))
      // Guard 3, axis rows only (`PRIMITIVE_NAMES` — `Button`/`Link`/`Field`/`Menu` — the shape
      // `buildAxisMatrix` produces, one row per `variant|size` rather than per element): a class is
      // never resolved per axis row at all (record 1's own Method section: "renders that prop's own
      // *default* value, never a union of every entry" — a non-default variant's own class is
      // genuinely unknown here), so the only safe reading of "does this primitive ever paint a
      // class for this state" is whether *any* of the primitive's own record-1 local elements do —
      // real, positive evidence the DOM responds to this pseudo-class somewhere in this component,
      // which a spec's "never" cannot survive regardless of which variant painted it. Never applied
      // to `disabled`, which record 1 does not track at all (the same exclusion `RECORD1_STATE_CLASS_TEXT`
      // already holds).
      const anyOwnElementPainted =
        state === 'disabled' ? false : record1Elements.some((el) => record1CellIsPainted(el, state))
      for (const row of realRows) {
        if (classifyCoverage(coverageOf(row, state)) !== 'none') continue
        const base = { record: 3, primitiveName, variantSize: row.variantSize, state }
        const ownElement = findRecord1ElementForRow(row, record1Elements)
        if (ownElement && record1CellIsPainted(ownElement, state)) {
          results.push({
            ...base,
            status: 'decline',
            reason:
              'a real class is painted for this state on this exact element — a story gap, never impossible',
          })
          continue
        }
        if (!ownElement && anyOwnElementPainted) {
          results.push({
            ...base,
            status: 'decline',
            reason:
              "this primitive's own local element paints a class for this state elsewhere in its default rendering — a non-default variant's own class is unresolved here, never assumed absent",
          })
          continue
        }
        if (siblingCovered) {
          results.push({
            ...base,
            status: 'decline',
            reason: 'another row of this primitive matrix has real coverage for this same state',
          })
          continue
        }
        const mapping = mapComponentKeyToSpecFile(readmeSource, componentKey)
        if (!mapping) {
          results.push({
            ...base,
            status: 'decline',
            reason: 'component does not map to exactly one Index row',
          })
          continue
        }
        const specSource = specSourcesByFile.get(mapping.specFile)
        if (!specSource) {
          results.push({
            ...base,
            status: 'decline',
            reason: `spec file ${mapping.specFile} was not read`,
          })
          continue
        }
        const answer = resolveSpecAnswerForState({
          specSource,
          components: mapping.components,
          componentName: mapping.componentName,
          state,
          vocabulary,
        })
        results.push({
          ...base,
          status: answer.status,
          reason: answer.status === 'decline' ? answer.reason : undefined,
          answerText: answer.answerText,
        })
      }
    }
  }
  return results
}

// I/O: every `.md` file directly under `packages/design-system/specs/`, by its own basename (the
// same key `## Index` rows and `mapComponentKeyToSpecFile`'s own `specFile` already use) — the spec
// analogue of `readAllSourceFiles` above, kept separate because a fixture-driven test never needs a
// real filesystem read for the pure functions above it.
export function readAllSpecFiles() {
  const files = new Map()
  for (const entry of readdirSync(specsDir)) {
    if (!entry.endsWith('.md')) continue
    files.set(entry, readFileSync(path.join(specsDir, entry), 'utf8'))
  }
  return files
}

// The whole recogniser, end to end, against the live tree: every confirmed `'none'` cell in both
// records, classified `'impossible'` or `'decline'` (with a reason) — wired into `main`'s own exit
// code by `checkCellGate` below (T595's own closing commit: "the cell gate... lands in the commit
// that closes the last [open cell]").
export function classifyImpossiblePerSpec(computed, { readmeSource, specSourcesByFile }) {
  const vocabulary = deriveVocabulary(readmeSource)
  return {
    record1: classifyRecord1NoneCells(computed, { readmeSource, specSourcesByFile, vocabulary }),
    record3: classifyRecord3NoneCells(computed, { readmeSource, specSourcesByFile, vocabulary }),
  }
}

// --- The cell gate (T595's own closing commit) --------------------------------------------------
//
// T595's own three closures for a cell still reading `'none'`: closed by a story that depicts the
// state (this run's own generated region would then read `'covered'`, never reaching this code at
// all); a state the component's own spec answers as impossible (`classifyImpossiblePerSpec`
// above); or named in a dated entry in row 8, outside the generated region, saying why it stays and
// who owes it. This section is the third closure and the gate that requires one of the three for
// every cell — never wired as a fourth, silent way to close one, and never satisfied by an entry
// that does not name the exact cell it closes (`cellKey` below is what "name" means: a full,
// unambiguous identity — never a component name, a reason string or a state alone, any of which
// would let one entry silently cover every cell that happens to share it).
//
// A dated entry lives inside row 8's own prose as an HTML comment rather than a second file next to
// it, because T595 names "the register" as row 8 itself: an entry that could drift from the
// markdown a reader actually opens would be the exact hazard `a11y-allowlist.mjs`'s own single-file
// steady state, and `story-baseline-duplicates-debt.json`'s deliberate exception to it (a *list* of
// PNG pairs has no prose home), both already avoid for their own subjects. Comment syntax keeps the
// entry invisible in the rendered register, the same choice the `state-coverage:begin`/`end`
// markers already made, and — unlike a `// visual-equivalence: <id>: <reason>` single-line marker,
// the shape `story-baselines-duplicates.mjs` uses for a *pair* of story ids — a cell identity here
// carries too many fields (record, component or primitive, element or axis row, state, `file:line`
// for an element) to fit one line per entry without either truncating a field or inventing
// per-field escaping; a block comment with one cell per line inside it needs neither.
//
// **Two block kinds, not one (row 8's own Method section, "8g" — found and fixed 2026-09-20,
// verifying T595's first attempt at this closing commit, `863f111a`).** `<!-- state-coverage-debt
// … -->` is time-boxed by construction: every well-formed entry expires on its own `fixBy`, on
// purpose, so a real gap cannot be closed once and forgotten. But not every declining cell this
// closure names is a gap — Guard 2 of `classifyRecord1NoneCells`/`classifyRecord3NoneCells` (row
// 8's own Method section) and a real, substantive, non-impossible spec answer painting no class at
// all are both structural facts about what this extractor can ever read, never debt a future commit
// clears; forcing either through a `fixBy` means the entry must be re-dated forever to stay green,
// which is exactly "an allowlist with no enforced expiry is how a temporary exception becomes
// permanent" (this file's own comment on `KNOWN_UNACCOUNTED_FORCE_STATES`, below) in the other
// direction — a *perpetually renewed* exception is the same failure as an unenforced one, both being
// a record nobody actually has to keep true. `<!-- state-coverage-permanent … -->` is the second
// kind: no `fixBy`, no `owner` — nothing is owed — and a `reason` stating the structural fact rather
// than a deadline. It is a refinement of T595's third closure, not a fourth one: it still names the
// cell exactly, inside the same machine-readable block shape, and still says why it stays; it
// differs only in what it says is owed. `checkCellGate` enforces the split both ways: a permanent
// entry carrying a `fixBy` or an `owner`, or a debt entry missing its `date`, `fixBy` or `owner`, is
// malformed and fails the run exactly as a debt entry missing only `fixBy` already did — so the two
// shapes cannot blur back into one that silently stops requiring either its expiry or its reason.
//
// Block shape (fields are `key: value` lines; a cell line starts with `R1 ` or `R3 `; blank lines
// and any other line are ignored, so a human sentence can sit beside the fields for a reader who
// never runs the parser):
//
//   <!-- state-coverage-debt
//   date: 2026-09-20
//   fixBy: 2026-09-27
//   owner: <free text — a task id that owes the fix>
//   R1 <componentKey> <hover|focus-visible|active> <tag>@<file>:<line>
//   R3 <primitiveName> <hover|focus-visible|active|disabled> <variantSize>
//   -->
//
//   <!-- state-coverage-permanent
//   date: 2026-09-20
//   reason: <free text — the structural fact that means nothing is, or ever could be, owed>
//   R1 <componentKey> <hover|focus-visible|active> <tag>@<file>:<line>
//   R3 <primitiveName> <hover|focus-visible|active|disabled> <variantSize>
//   -->
//
// `componentKey`/`tag`/`file`/`line` and `primitiveName`/`variantSize` are copied verbatim from the
// generated region's own row identity (`classifyRecord1NoneCells`/`classifyRecord3NoneCells`'s own
// `componentKey`/`tag`/`file`/`line` and `primitiveName`/`variantSize` fields) — the same strings a
// reader can already find in the table above, never a paraphrase, so a cell that ever moves (a
// line number shifts, a variant is renamed) makes its own entry stop matching rather than silently
// keep covering the wrong row.
const ROW8_DEBT_BLOCK_RE = /<!--\s*state-coverage-debt\b([\s\S]*?)-->/g
const ROW8_PERMANENT_BLOCK_RE = /<!--\s*state-coverage-permanent\b([\s\S]*?)-->/g
const ROW8_DEBT_R1_LINE_RE = /^R1\s+(\S+)\s+(hover|focus-visible|active)\s+([^@\s]+)@(.+):(\d+)$/
const ROW8_DEBT_R3_LINE_RE = /^R3\s+(\S+)\s+(hover|focus-visible|active|disabled)\s+(.+)$/

// The field/cell parsing both block kinds share — a field line (`key: value`, case-sensitive key)
// and a cell line (`R1 …`/`R3 …`) can appear in any order; a line matching neither is silently
// skipped, which is what lets an entry carry a plain-English sentence next to its own fields
// without a second, competing syntax to keep that sentence out of the parser's way.
function parseRow8Block(blockBody) {
  const fields = {}
  const cells = []
  for (const rawLine of blockBody.split('\n')) {
    const line = rawLine.trim()
    if (line.length === 0) continue
    const r1 = line.match(ROW8_DEBT_R1_LINE_RE)
    if (r1) {
      const [, componentKey, state, tag, file, lineStr] = r1
      cells.push({ record: 1, componentKey, state, tag, file, line: Number(lineStr) })
      continue
    }
    const r3 = line.match(ROW8_DEBT_R3_LINE_RE)
    if (r3) {
      const [, primitiveName, state, variantSize] = r3
      cells.push({ record: 3, primitiveName, state, variantSize })
      continue
    }
    const kv = line.match(/^([a-zA-Z]+):\s*(.*)$/)
    if (kv) fields[kv[1]] = kv[2]
  }
  return { fields, cells }
}

// Every `<!-- state-coverage-debt … -->` block in row 8's own prose, parsed into `{ date, fixBy,
// owner, cells, raw }` — `cells` each carrying `record` plus that record's own identity fields,
// exactly as `classifyRecord1NoneCells`/`classifyRecord3NoneCells` name them, so `cellKey` (below)
// can be applied to a parsed entry's cell and a classified cell interchangeably.
export function parseRow8DebtEntries(readmeText) {
  const entries = []
  for (const m of readmeText.matchAll(ROW8_DEBT_BLOCK_RE)) {
    const { fields, cells } = parseRow8Block(m[1])
    entries.push({ ...fields, cells, raw: m[0] })
  }
  return entries
}

// Every `<!-- state-coverage-permanent … -->` block, parsed the same way into `{ date, reason,
// cells, raw }` — the non-expiring counterpart above ("8g" of row 8's own Method section): no
// `fixBy`, no `owner`, because nothing here is owed.
export function parseRow8PermanentEntries(readmeText) {
  const entries = []
  for (const m of readmeText.matchAll(ROW8_PERMANENT_BLOCK_RE)) {
    const { fields, cells } = parseRow8Block(m[1])
    entries.push({ ...fields, cells, raw: m[0] })
  }
  return entries
}

// The one identity a cell is known by across all three sources this gate compares — a classified
// `'none'` cell, a live cell this run just extracted, and a parsed debt-entry cell — so "does this
// entry name this cell" is a single string comparison, never a field-by-field guess. Deliberately
// includes every field row 8's own generated region uses to key a row (`tag` included for record
// 1, even though `file:line` alone is already unique in this tree today, because the entry's own
// text is what a reader checks the claim against, and a `tag` mismatch there is exactly the kind of
// stale entry this gate exists to catch) and deliberately excludes nothing a real cell needs to be
// told apart from its sibling — a key built from only `componentKey`/state, for instance, would let
// one entry close every element of a component sharing that state, the "an entry must not close a
// cell it does not name" failure `state-coverage.test.mjs` plants directly.
function cellKey(c) {
  return c.record === 1
    ? `R1|${c.componentKey}|${c.tag}|${c.file}|${c.line}|${c.state}`
    : `R3|${c.primitiveName}|${c.variantSize}|${c.state}`
}

// Record 1's own hover/focus-visible/active cell for every local element, and record 3's own
// hover/focus-visible/active/disabled cell for every real matrix row (never `rest`, which neither
// `classifyRecord1NoneCells` nor `classifyRecord3NoneCells` classifies — T595's own scope is the
// `'none'` cells those two functions already read) — `'covered'`, `'none'` or `'unresolved'`,
// mirroring `countRecord1Cells`/`countRecord3Cells`'s own per-cell rule exactly (record 1's class
// half first: an unresolved class expression makes the cell `'unresolved'` regardless of what its
// story half alone would say) rather than re-deriving it a second way that could drift from the
// count this file already prints every run.
function collectRecord1CellStatuses(computed) {
  const cells = []
  for (const { componentKey, elements } of computed.localElements) {
    for (const el of elements) {
      const classResolved = (el.classUnresolvedRefs ?? []).length === 0
      const pairs = [
        ['hover', el.hover, el.coveredBy.hover],
        [
          'focus-visible',
          combineFocusClassText(el.focus, el.focusVisible),
          el.coveredBy.focusVisible,
        ],
        ['active', el.active, el.coveredBy.active],
      ]
      for (const [state, classText, coverageList] of pairs) {
        const classHalf = classifyClassHalf(classText, classResolved)
        const status = classHalf === 'unresolved' ? 'unresolved' : classifyCoverage(coverageList)
        cells.push({
          record: 1,
          componentKey,
          tag: el.tag,
          file: el.file,
          line: el.line,
          state,
          status,
        })
      }
    }
  }
  return cells
}

function collectRecord3CellStatuses(computed) {
  const cells = []
  for (const [primitiveName, rows] of Object.entries(computed.matrices)) {
    for (const row of rows) {
      if (row.variantSize === '(no local interactive element)') continue
      if (row.variantSize.startsWith('(unresolved matches')) continue
      const pairs = [
        ['hover', row.hover],
        ['focus-visible', row.focusVisible],
        ['active', row.active],
        ['disabled', row.disabled],
      ]
      for (const [state, coverageList] of pairs) {
        cells.push({
          record: 3,
          primitiveName,
          variantSize: row.variantSize,
          state,
          status: classifyCoverage(coverageList),
        })
      }
    }
  }
  return cells
}

function describeCell(c) {
  return c.record === 1
    ? `record 1's ${c.componentKey} ${c.tag}@${c.file}:${c.line} (${c.state})`
    : `record 3's ${c.primitiveName} ${c.variantSize} (${c.state})`
}

// The gate itself: every hover/focus-visible/active(/disabled) cell in the live tree, classified
// against the three closures T595 permits. `today` is injectable so a test can plant an entry on
// either side of its own `fixBy` without waiting on the calendar — production code never passes it,
// so `main` always checks against the real date.
export function checkCellGate(
  computed,
  { readmeSource, specSourcesByFile, today = new Date().toISOString().slice(0, 10) },
) {
  const classified = classifyImpossiblePerSpec(computed, { readmeSource, specSourcesByFile })
  const classifiedByKey = new Map()
  for (const row of [...classified.record1, ...classified.record3]) {
    classifiedByKey.set(cellKey(row), row)
  }

  // Filed exceptions are validated the same way `findUnaccountedForceStates` already validates
  // `KNOWN_UNACCOUNTED_FORCE_STATES`: a missing or invalid `date`/`fixBy` is malformed regardless of
  // what it might otherwise have covered, and a well-formed debt entry whose own `fixBy` has passed
  // is `expired` rather than quietly kept `known` — an allowlist with no enforced expiry is how a
  // temporary exception becomes permanent (row 8's own Method section, T598's identical rule for
  // `KNOWN_UNACCOUNTED_FORCE_STATES`). No debt entry is allowed to keep closing the cells it names
  // past its own `fixBy`.
  const parsedDebtEntries = parseRow8DebtEntries(readmeSource)
  const malformedEntries = []
  const expiredEntries = []
  const liveEntries = []
  for (const entry of parsedDebtEntries) {
    const missing = ['date', 'fixBy', 'owner'].filter(
      (f) => typeof entry[f] !== 'string' || entry[f].trim() === '',
    )
    const invalid = ['date', 'fixBy'].filter(
      (f) => !missing.includes(f) && !isValidIsoDate(entry[f]),
    )
    const malformed = [...missing, ...invalid]
    if (malformed.length > 0) {
      malformedEntries.push({ entry, malformed, kind: 'debt' })
    } else if (entry.fixBy < today) {
      expiredEntries.push(entry)
    } else {
      liveEntries.push(entry)
    }
  }

  // `<!-- state-coverage-permanent … -->` (row 8's own Method section, "8g"): a structural fact, not
  // debt, so it carries `date`/`reason` and never `fixBy`/`owner` — the split `checkCellGate`
  // enforces both ways, so a `fixBy`/`owner` sitting on a permanent entry (still time-boxed in
  // substance, whatever its marker says) is exactly as malformed as a debt entry missing one.
  const parsedPermanentEntries = parseRow8PermanentEntries(readmeSource)
  const permanentEntries = []
  for (const entry of parsedPermanentEntries) {
    const missing = ['date', 'reason'].filter(
      (f) => typeof entry[f] !== 'string' || entry[f].trim() === '',
    )
    const invalidDate = !missing.includes('date') && !isValidIsoDate(entry.date) ? ['date'] : []
    const forbidden = ['fixBy', 'owner']
      .filter((f) => typeof entry[f] === 'string' && entry[f].trim() !== '')
      .map((f) => `${f} (a permanent entry may not carry ${f})`)
    const malformed = [...missing, ...invalidDate, ...forbidden]
    if (malformed.length > 0) {
      malformedEntries.push({ entry, malformed, kind: 'permanent' })
    } else {
      permanentEntries.push(entry)
    }
  }

  const liveKeys = new Set()
  for (const entry of liveEntries) for (const c of entry.cells) liveKeys.add(cellKey(c))
  for (const entry of permanentEntries) for (const c of entry.cells) liveKeys.add(cellKey(c))
  const expiredKeys = new Set()
  for (const entry of expiredEntries) for (const c of entry.cells) expiredKeys.add(cellKey(c))

  const unresolved = []
  const uncovered = []
  const expiredCovering = []
  for (const cell of [
    ...collectRecord1CellStatuses(computed),
    ...collectRecord3CellStatuses(computed),
  ]) {
    if (cell.status === 'covered') continue
    if (cell.status === 'unresolved') {
      unresolved.push(cell)
      continue
    }
    // cell.status === 'none'
    const key = cellKey(cell)
    if (classifiedByKey.get(key)?.status === 'impossible') continue
    if (liveKeys.has(key)) continue
    if (expiredKeys.has(key)) {
      expiredCovering.push(cell)
      continue
    }
    uncovered.push(cell)
  }
  return {
    unresolved,
    uncovered,
    expiredCovering,
    malformedEntries,
    expiredEntries,
    liveEntries,
    permanentEntries,
  }
}

// --- main --------------------------------------------------------------------------------------

// Exported so a test can run `computeStateCoverage` against the live tree end to end — needed for
// exactly one thing a fixture cannot stand in for: whether `KNOWN_UNACCOUNTED_FORCE_STATES`'s own
// membership still matches the live tree's real gaps (T595).
export function readAllSourceFiles() {
  const componentDirs = listComponentDirs(srcDir)
  const filesByPath = new Map()
  for (const filePath of walkAllTsxFiles(srcDir)) {
    filesByPath.set(filePath, readFileSync(filePath, 'utf8'))
  }
  return {
    componentDirs,
    filesByPath,
    storyFilesByPath: walkStoryFiles(),
    moduleFilesByPath: walkModuleFiles(),
  }
}

// The committed runtime manifest (T693), parsed, or `{ problem }` naming the file and the command that
// rewrites it. A missing file is a problem, never an empty manifest: an empty one would report every
// story as having no entry, one line each, burying the one cause.
export function readManifest() {
  let text
  try {
    text = readFileSync(path.join(rootDir, MANIFEST_PATH), 'utf8')
  } catch {
    return {
      problem: `${MANIFEST_PATH} does not exist — build Storybook (\`${BUILD_STORYBOOK_COMMAND}\`) and run \`${REWRITE_COMMAND}\` to record it.`,
    }
  }
  return parseManifest(text, { label: MANIFEST_PATH })
}

function main() {
  const write = process.argv.includes('--write')
  const { componentDirs, filesByPath, storyFilesByPath, moduleFilesByPath } = readAllSourceFiles()
  const loaded = readManifest()
  if (loaded.problem) {
    fail(loaded.problem)
    return
  }
  const computed = computeStateCoverage({
    componentDirs,
    filesByPath,
    storyFilesByPath,
    moduleFilesByPath,
    manifest: loaded.manifest,
  })
  const freshRegion = renderGeneratedRegion(computed)

  // A story with no manifest entry (or an entry for no story) cannot be credited from what a browser
  // rendered: the check fails naming it and the command that refreshes the manifest (T694).
  for (const problem of computed.manifestProblems) fail(problem.detail)
  for (const { componentKey, exportName, note } of computed.partialRefusals) {
    log(`${componentKey}'s ${exportName} credits only part of what it forces: ${note}.`)
  }
  for (const { componentKey, exportName, reason } of computed.unkeyedMounts) {
    log(
      `${componentKey}'s ${exportName} mounts an instance with no matrix row to credit: ${reason}.`,
    )
  }

  // A real `visualForceState` this run could not find credited anywhere, and not named in any
  // `unresolved: <reason>` either — a frame the region has silently lost (T595, the exact shape
  // mechanism 3's own first draft shipped: a name traced far enough to reject every wrong candidate
  // and credited nowhere). Fails the run rather than only printing a tally — the same choice
  // `2f04a6ef`'s inline-claim sum invariant made, for the same reason: the point is catching the
  // *next* silent loss unattended, not this one, which a printed line nobody reads would not do. A
  // well-formed, unexpired member of `KNOWN_UNACCOUNTED_FORCE_STATES` is reported, every run, but
  // never fails on its own — a filed, dated, *owned* exception, not a suppression
  // (`a11y-allowlist.mjs`'s own pattern, down to the field names). A member that is malformed or
  // past its own `fixBy` fails exactly like an unfiled loss: an allowlist entry nobody enforces the
  // deadline on is not an exception, it is a rename of the original bug (T598's own deadline is
  // 2026-09-27, the same date row 8 (H5) itself carries).
  const { missing, known, expired } = computed.unaccountedForceStates
  for (const entry of missing) fail(describeMissingForceState(entry))
  for (const entry of expired) {
    const detail = entry.malformed
      ? `malformed filed exception (${entry.malformed.join(', ')})`
      : `filed exception past its own fixBy (${entry.fixBy}, owed to ${entry.fixOwed})`
    fail(
      `${entry.componentKey}'s own ${entry.exportName} forces "${entry.state}" and is still ` +
        `credited nowhere — ${detail}.`,
    )
  }
  for (const { componentKey, exportName, state, date, fixOwed, fixBy, reason } of known) {
    log(
      `known, filed exception — ${componentKey}'s own ${exportName} forces "${state}" and is ` +
        `still credited nowhere (filed ${date}, owed to ${fixOwed}, fix by ${fixBy}): ${reason}`,
    )
  }
  if (missing.length === 0 && expired.length === 0) {
    log(
      `every real visualForceState is credited on some cell or named in some unresolved reason ` +
        `(${known.length} filed exception${known.length === 1 ? '' : 's'}).`,
    )
  }

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

  // T595's own closing commit: every cell in the generated region above is now required to be one
  // of the three things row 8's own Method section names — covered by a story, answered impossible
  // by the component's own spec, or named in a live, dated row-8 debt entry — checked only once the
  // region itself is confirmed to match a fresh render (the comparison above), so a cell gate
  // failure is never conflated with plain drift.
  const cellGate = checkCellGate(computed, {
    readmeSource: readmeText,
    specSourcesByFile: readAllSpecFiles(),
  })
  for (const cell of cellGate.unresolved) {
    fail(
      `${describeCell(cell)} is unresolved — T595 requires every cell resolved to 'covered' or ` +
        "'none' in the extractor; 'unresolved' is not one of the cell gate's three closures.",
    )
  }
  for (const cell of cellGate.uncovered) {
    fail(
      `${describeCell(cell)} reads 'none' and is closed by no story, no spec answering it ` +
        'impossible, and no live row-8 debt or permanent entry naming it exactly — file a dated ' +
        '`<!-- state-coverage-debt -->` or `<!-- state-coverage-permanent -->` entry for it or ' +
        'close it.',
    )
  }
  for (const cell of cellGate.expiredCovering) {
    fail(
      `${describeCell(cell)}'s only row-8 debt entry is past its own fixBy — renew the entry ` +
        '(with a fresh date), close the cell for real, or refile it as ' +
        '`<!-- state-coverage-permanent -->` if nothing is actually owed.',
    )
  }
  for (const { entry, malformed, kind } of cellGate.malformedEntries) {
    fail(
      `a row-8 ${kind ?? 'debt'} entry is malformed (${malformed.join(', ')}): ` +
        `${JSON.stringify(entry.cells.map(cellKey))}`,
    )
  }
  for (const entry of cellGate.expiredEntries) {
    fail(
      `a row-8 debt entry filed ${entry.date} is past its own fixBy (${entry.fixBy}), owed to ` +
        `${entry.owner ?? 'no owner recorded'}: ${JSON.stringify(entry.cells.map(cellKey))}`,
    )
  }
  if (
    cellGate.unresolved.length === 0 &&
    cellGate.uncovered.length === 0 &&
    cellGate.expiredCovering.length === 0 &&
    cellGate.malformedEntries.length === 0 &&
    cellGate.expiredEntries.length === 0
  ) {
    log(
      `every cell in row 8's generated region is covered, answered impossible, or named in a live ` +
        `debt or permanent entry (${cellGate.liveEntries.length} live debt entr` +
        `${cellGate.liveEntries.length === 1 ? 'y' : 'ies'}, ${cellGate.permanentEntries.length} ` +
        `permanent entr${cellGate.permanentEntries.length === 1 ? 'y' : 'ies'}).`,
    )
  }
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
