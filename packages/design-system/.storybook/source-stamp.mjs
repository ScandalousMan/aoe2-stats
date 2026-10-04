// Source stamps for the Storybook build only (T693 piece 1, feature 005).
//
// `scripts/checks/state-coverage.mjs` guesses, from source, which element a forced story
// (`parameters.visualForceState`) lands on, and each adversarial review of #112 found another guess
// wrong. The capture harness already knows the answer: it locates the forced element with Playwright
// in the built Storybook. T693 records that answer — and to say *whose* element it is, the browser
// needs to read where each element was written. This module is how: a Vite transform, wired through
// `viteFinal` in `./main.ts` and nowhere else, that adds one attribute to every intrinsic JSX element
// of a design-system source file, holding the repository-rooted `file:line` the element's opening
// tag starts on — the key `scripts/checks/state-coverage.mjs` record 1 already prints for the same
// element (it takes the line of the node's own first token).
//
// What is stamped:
//   - every intrinsic JSX element of a file under `packages/design-system/src` that is not a story and
//     not a test. Two kinds of tag are intrinsic: a lowercase name (`div`, `button`, `svg`), and a
//     capitalised name that is a LOCAL VARIABLE holding a string — `const Heading = \`h${level}\``
//     then `<Heading>` renders an `<h2>`, not a component (`Callout`, `EmptyState`, `ErrorState`,
//     `Panel`, `Section` and `Text` all write theirs that way). A component tag (`<Button>`, an
//     imported name, a local function, class, arrow, `forwardRef` or `memo`, a `<Foo.Bar>`) is not
//     stamped — the element it renders is, from the file that wrote it.
//   - a capitalised tag the transform cannot classify — a destructured `as: Tag` prop, a parameter, a
//     member read, a cast to `ElementType`, a name declared nowhere — makes the transform THROW naming
//     its file:line. Skipping it silently is how an element ends up attributed to nobody; the fix is
//     to declare the tag as a string (optionally under `as` or `satisfies` with a string-literal type,
//     or a conditional of strings) or as a component.
//   - an element a design-system file hands to React's `cloneElement`: the call's own props gain the
//     stamp, keyed to the *call's* location. `Field` places its control that way (it clones its child
//     rather than rendering it), so without this the control would carry no stamp, or the caller's,
//     and could not be attributed to `Field`. A call is React's only when it resolves to an import:
//     a named import from `'react'` (aliased or not), or a member access on a default or namespace
//     import of `'react'`. A name imported from anywhere else, a method of another object and a bare
//     `cloneElement` with no import are not React's and are not stamped; redeclaring an imported name
//     anywhere in the file throws, naming file:line, since the call could then be anything. A call
//     with a spread argument (`cloneElement(...args)`) throws too, since the stamp could not be told
//     from a child there.
// A story file is never stamped: an element a story writes carries no stamp, which is exactly how the
// pass tells a forced element a primitive placed from one a story wrote beside it.
//
// Nothing reaches the markup `apps/web` builds: `apps/web/vite.config.ts` does not import this module,
// and `scripts/checks/stamp-absent.mjs` (run in CI after `pnpm --filter web build`) fails when the
// built output carries the attribute. `scripts/visual/source-stamp.test.mjs` covers both and the
// transform's own cases.
import { createRequire } from 'node:module'
import path from 'node:path'
import { STAMP_ATTRIBUTE } from './source-stamp-attribute.cjs'

// `typescript` is a direct devDependency of this package; resolved from this file, which sits inside
// it (`state-coverage.mjs` resolves it the same way).
const require = createRequire(import.meta.url)
const ts = require('typescript')

// The attribute's name has one definition, in a `.cjs` a Playwright spec can load (see that file).
export { STAMP_ATTRIBUTE }

const STAMPED_ROOT = 'packages/design-system/src/'
const STAMPED_EXTENSIONS = ['.tsx', '.ts', '.jsx', '.js']

// Whether a repository-rooted, posix path is a design-system source file the transform stamps.
export function isStampedFile(repoRelativePath) {
  if (!repoRelativePath.startsWith(STAMPED_ROOT)) return false
  if (!STAMPED_EXTENSIONS.some((ext) => repoRelativePath.endsWith(ext))) return false
  return !/\.(stories|test)\.[jt]sx?$/.test(repoRelativePath)
}

// How `'react'` is imported: the local names `cloneElement` goes by (`cloneElement` itself, or `ce` for
// `import { cloneElement as ce }`), and the local names a default or namespace import goes by (so
// `React.cloneElement` and `R.cloneElement` resolve). Nothing else is React's.
function reactImports(sourceFile) {
  const named = new Set()
  const objects = new Set()
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement)) continue
    if (
      !ts.isStringLiteral(statement.moduleSpecifier) ||
      statement.moduleSpecifier.text !== 'react'
    ) {
      continue
    }
    const clause = statement.importClause
    if (!clause || clause.isTypeOnly) continue
    if (clause.name) objects.add(clause.name.text)
    const bindings = clause.namedBindings
    if (!bindings) continue
    if (ts.isNamespaceImport(bindings)) objects.add(bindings.name.text)
    else {
      for (const element of bindings.elements) {
        if (!element.isTypeOnly && (element.propertyName ?? element.name).text === 'cloneElement') {
          named.add(element.name.text)
        }
      }
    }
  }
  return { named, objects }
}

function isCloneElementCall(node, react) {
  if (!ts.isCallExpression(node)) return false
  const callee = node.expression
  if (ts.isIdentifier(callee)) return react.named.has(callee.text)
  return (
    ts.isPropertyAccessExpression(callee) &&
    callee.name.text === 'cloneElement' &&
    ts.isIdentifier(callee.expression) &&
    react.objects.has(callee.expression.text)
  )
}

// Every identifier a binding name (a plain name or a destructuring pattern) declares.
function boundIdentifiers(name, out = []) {
  if (ts.isIdentifier(name)) out.push(name)
  else {
    for (const element of name.elements) {
      if (ts.isBindingElement(element)) boundIdentifiers(element.name, out)
    }
  }
  return out
}

// The identifiers a node itself declares (not its descendants'): the places a name can be bound.
function declaredBy(node) {
  if (ts.isVariableDeclaration(node) || ts.isParameter(node) || ts.isBindingElement(node)) {
    // A binding element's own name is reached through its pattern's walk, so only plain ones here.
    return ts.isBindingElement(node)
      ? ts.isIdentifier(node.name)
        ? [node.name]
        : []
      : boundIdentifiers(node.name)
  }
  if (
    (ts.isFunctionDeclaration(node) ||
      ts.isClassDeclaration(node) ||
      ts.isFunctionExpression(node) ||
      ts.isClassExpression(node)) &&
    node.name
  ) {
    return [node.name]
  }
  return []
}

// ---- which tag a capitalised JSX identifier is ------------------------------------------------------

const unwrap = (expression) => {
  let current = expression
  while (
    ts.isParenthesizedExpression(current) ||
    ts.isNonNullExpression(current) ||
    ts.isAsExpression(current) ||
    ts.isSatisfiesExpression(current) ||
    ts.isTypeAssertionExpression(current)
  ) {
    current = current.expression
  }
  return current
}

// A type that only a string can have: a union of string-literal types, or a template-literal type.
function isStringType(typeNode) {
  if (ts.isParenthesizedTypeNode(typeNode)) return isStringType(typeNode.type)
  if (ts.isUnionTypeNode(typeNode)) return typeNode.types.every(isStringType)
  if (ts.isTemplateLiteralTypeNode(typeNode)) return true
  return (
    ts.isLiteralTypeNode(typeNode) &&
    (ts.isStringLiteral(typeNode.literal) || ts.isNoSubstitutionTemplateLiteral(typeNode.literal))
  )
}
const isConstType = (typeNode) =>
  ts.isTypeReferenceNode(typeNode) &&
  ts.isIdentifier(typeNode.typeName) &&
  typeNode.typeName.text === 'const'

// Whether an expression is a string at runtime, decided from its shape alone: a string or template
// literal, those under `as const`, a cast or `satisfies` to a string-literal type, parentheses, or a
// conditional whose two branches are. Anything else is not known to be one.
function isStringExpression(expression) {
  if (ts.isStringLiteral(expression) || ts.isNoSubstitutionTemplateLiteral(expression)) return true
  if (ts.isTemplateExpression(expression)) return true
  if (ts.isParenthesizedExpression(expression) || ts.isNonNullExpression(expression)) {
    return isStringExpression(expression.expression)
  }
  if (ts.isAsExpression(expression) || ts.isSatisfiesExpression(expression)) {
    if (!isConstType(expression.type) && isStringType(expression.type)) return true
    return isStringExpression(expression.expression)
  }
  if (ts.isConditionalExpression(expression)) {
    return isStringExpression(expression.whenTrue) && isStringExpression(expression.whenFalse)
  }
  return false
}

// Whether an expression is a component at runtime, from its shape: a function or class expression, or
// a `forwardRef(...)` / `memo(...)` call (bare or as a member).
function isComponentExpression(expression) {
  const inner = unwrap(expression)
  if (ts.isArrowFunction(inner) || ts.isFunctionExpression(inner) || ts.isClassExpression(inner)) {
    return true
  }
  if (!ts.isCallExpression(inner)) return false
  const callee = inner.expression
  const name = ts.isIdentifier(callee)
    ? callee.text
    : ts.isPropertyAccessExpression(callee)
      ? callee.name.text
      : ''
  return name === 'forwardRef' || name === 'memo'
}

// The nearest declaration of `name` visible from `from`, innermost scope first: parameters of an
// enclosing function, then the statements of each enclosing block, then the module's. `kind` is
// `import`, `component` (function, class, arrow, forwardRef, memo), `string`, or `opaque` — a
// parameter, a destructured binding, a variable of any other shape, or no declaration found at all.
function resolveTagBinding(from, name, sourceFile) {
  const fromStatements = (statements) => {
    for (const statement of statements) {
      if (ts.isImportDeclaration(statement)) {
        const clause = statement.importClause
        if (!clause) continue
        if (clause.name?.text === name) return { kind: 'import' }
        const bindings = clause.namedBindings
        if (bindings && ts.isNamespaceImport(bindings) && bindings.name.text === name) {
          return { kind: 'import' }
        }
        if (bindings && ts.isNamedImports(bindings)) {
          if (bindings.elements.some((element) => element.name.text === name)) {
            return { kind: 'import' }
          }
        }
      } else if (ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement)) {
        if (statement.name?.text === name) return { kind: 'component' }
      } else if (ts.isVariableStatement(statement)) {
        for (const declaration of statement.declarationList.declarations) {
          const found = boundIdentifiers(declaration.name).some((id) => id.text === name)
          if (!found) continue
          if (!ts.isIdentifier(declaration.name) || !declaration.initializer) {
            return { kind: 'opaque', why: 'it is a destructured or uninitialised binding' }
          }
          if (isComponentExpression(declaration.initializer)) return { kind: 'component' }
          if (isStringExpression(declaration.initializer)) return { kind: 'string' }
          return {
            kind: 'opaque',
            why: `its initializer \`${declaration.initializer.getText(sourceFile).split('\n')[0]}\` is neither a component nor a string`,
          }
        }
      }
    }
    return null
  }
  for (let scope = from.parent; scope; scope = scope.parent) {
    if (ts.isFunctionLike(scope)) {
      if (ts.isFunctionExpression(scope) && scope.name?.text === name) return { kind: 'component' }
      for (const parameter of scope.parameters ?? []) {
        if (boundIdentifiers(parameter.name).some((id) => id.text === name)) {
          return { kind: 'opaque', why: 'it is a parameter or a destructured prop' }
        }
      }
    } else if (ts.isCatchClause(scope) && scope.variableDeclaration) {
      if (boundIdentifiers(scope.variableDeclaration.name).some((id) => id.text === name)) {
        return { kind: 'opaque', why: 'it is a catch binding' }
      }
    } else if (
      (ts.isForStatement(scope) || ts.isForOfStatement(scope) || ts.isForInStatement(scope)) &&
      scope.initializer &&
      ts.isVariableDeclarationList(scope.initializer)
    ) {
      for (const declaration of scope.initializer.declarations) {
        if (boundIdentifiers(declaration.name).some((id) => id.text === name)) {
          return { kind: 'opaque', why: 'it is a loop binding' }
        }
      }
    }
    const statements =
      ts.isBlock(scope) || ts.isSourceFile(scope) || ts.isModuleBlock(scope)
        ? scope.statements
        : ts.isCaseClause(scope) || ts.isDefaultClause(scope)
          ? scope.statements
          : null
    if (statements) {
      const found = fromStatements(statements)
      if (found) return found
    }
  }
  return { kind: 'opaque', why: 'it is declared nowhere in this file' }
}

// `code` with every stamp inserted, or `null` when there is nothing to stamp. Insertions only ever
// add characters on the line they are written on, so no line number moves.
export function stampSource(code, repoRelativePath) {
  const scriptKind = repoRelativePath.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const sourceFile = ts.createSourceFile(
    repoRelativePath,
    code,
    ts.ScriptTarget.Latest,
    true,
    scriptKind,
  )
  const insertions = []
  // Whether an identifier tag is an intrinsic element: lowercase, or a local variable holding a string.
  const isStampedTag = (node, tag) => {
    if (/^[a-z]/.test(tag.text)) return true
    const binding = resolveTagBinding(node, tag.text, sourceFile)
    if (binding.kind === 'string') return true
    if (binding.kind !== 'opaque') return false
    throw new Error(
      `${keyOf(node)}: <${tag.text}> is a capitalised JSX tag the source stamp cannot classify as a ` +
        `component or as a string tag — ${binding.why}. Declare it as a string (a literal, a template ` +
        'literal, a cast to a string-literal type, or a conditional of those) so it is stamped, or ' +
        'as a component.',
    )
  }
  const react = reactImports(sourceFile)
  const keyOf = (node) =>
    `${repoRelativePath}:${sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1}`

  // An imported name that is declared again anywhere in the file could be anything at a call site.
  const tracked = new Set([...react.named, ...react.objects])
  if (tracked.size > 0) {
    const guard = (node) => {
      for (const id of declaredBy(node)) {
        if (tracked.has(id.text)) {
          throw new Error(
            `${repoRelativePath}:${sourceFile.getLineAndCharacterOfPosition(id.getStart(sourceFile)).line + 1}: ` +
              `\`${id.text}\` is imported from 'react' and redeclared here, so the source stamp cannot ` +
              "tell whether a cloneElement call through it is React's. Rename the declaration.",
          )
        }
      }
      ts.forEachChild(node, guard)
    }
    guard(sourceFile)
  }

  const visit = (node) => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName
      if (ts.isIdentifier(tag) && isStampedTag(node, tag)) {
        insertions.push({
          pos: tag.getEnd(),
          text: ` ${STAMP_ATTRIBUTE}="${keyOf(node)}"`,
        })
      }
    } else if (isCloneElementCall(node, react)) {
      // A spread argument hides which argument is the props, so the stamp could land as a child
      // (`cloneElement(...args)` takes its props from the spread). Refuse rather than guess.
      if (node.arguments.some(ts.isSpreadElement)) {
        throw new Error(
          `${keyOf(node)}: cloneElement is called with a spread argument, so the source stamp ` +
            'cannot tell which argument is the props. Pass the element and props explicitly.',
        )
      }
      const stamp = `'${STAMP_ATTRIBUTE}': '${keyOf(node)}'`
      const [element, props] = node.arguments
      if (!props) {
        // `cloneElement(element)`: give it a props argument of its own.
        if (element) insertions.push({ pos: element.getEnd(), text: `, { ${stamp} }` })
      } else if (ts.isObjectLiteralExpression(props)) {
        insertions.push({ pos: props.getStart(sourceFile) + 1, text: ` ${stamp},` })
      } else {
        // `cloneElement(element, someProps)`: spread what the caller passed after the stamp, so a
        // props object that names the attribute itself still wins, as an object literal's would.
        insertions.push({ pos: props.getStart(sourceFile), text: `{ ${stamp}, ...(` })
        insertions.push({ pos: props.getEnd(), text: ') }' })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)

  if (insertions.length === 0) return null
  let out = code
  for (const { pos, text } of [...insertions].sort((a, b) => b.pos - a.pos)) {
    out = out.slice(0, pos) + text + out.slice(pos)
  }
  return out
}

// The Vite plugin `./main.ts` pushes in `viteFinal`. `enforce: 'pre'` so it reads the TSX the author
// wrote, before JSX is compiled away. `rootDir` is the repository root: stamps are repository-rooted.
export function sourceStampPlugin({ rootDir }) {
  return {
    name: 'ds-source-stamp',
    enforce: 'pre',
    transform(code, id) {
      const file = id.split('?')[0]
      if (!path.isAbsolute(file)) return null
      const rel = path.relative(rootDir, file).split(path.sep).join('/')
      if (!isStampedFile(rel)) return null
      const stamped = stampSource(code, rel)
      return stamped === null ? null : { code: stamped, map: null }
    },
  }
}
