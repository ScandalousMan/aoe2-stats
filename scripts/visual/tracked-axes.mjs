// The axes the runtime pass records for the tracked primitives (T693 piece 2), checked against the
// sources they come from. A tracked primitive defaults its axes in its own destructuring and exports
// the same defaults as `<X>_AXIS_DEFAULTS`, which `packages/design-system/.storybook/preview.tsx`
// registers; the pass merges what a caller passed over that constant. The three can drift apart — a
// destructuring default turned into a literal, a default added to `Menu`'s required `variant`, an axis
// listed in the registry that the primitive never destructures — and then the pass would record an
// axis the browser does not render. `findAxisDrift` reads the sources and names each such disagreement;
// `tracked-axes.test.mjs` runs it on the real files and on scratch edits of them.
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const ts = createRequire(path.join(rootDir, 'packages', 'design-system', 'package.json'))(
  'typescript',
)

export const TRACKED_PRIMITIVES = ['Button', 'Field', 'Link', 'Menu']
// The only axes the pass records.
const AXES = ['variant', 'size']

const parse = (text, name) =>
  ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

const unwrap = (expression) => {
  let current = expression
  while (
    ts.isParenthesizedExpression(current) ||
    ts.isAsExpression(current) ||
    ts.isSatisfiesExpression(current)
  ) {
    current = current.expression
  }
  return current
}

const propertyNames = (literal) =>
  literal.properties.map((p) => p.name?.getText() ?? '').filter(Boolean)

// What a primitive's own destructuring says about `variant` and `size`: `{ axis: initializerText | null }`
// for the binding elements of the component function's first parameter and of the destructuring
// declarations at the top level of its body.
function destructuredAxes(sourceFile, component) {
  const fn = sourceFile.statements.find(
    (s) => ts.isFunctionDeclaration(s) && s.name?.text === component,
  )
  if (!fn) return null
  const found = {}
  const read = (pattern) => {
    for (const element of pattern.elements) {
      const name = (element.propertyName ?? element.name).getText(sourceFile)
      if (AXES.includes(name) && ts.isIdentifier(element.name)) {
        found[name] = element.initializer ? element.initializer.getText(sourceFile) : null
      }
    }
  }
  const first = fn.parameters[0]
  if (first && ts.isObjectBindingPattern(first.name)) read(first.name)
  for (const statement of fn.body?.statements ?? []) {
    if (!ts.isVariableStatement(statement)) continue
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isObjectBindingPattern(declaration.name)) read(declaration.name)
    }
  }
  return found
}

// The keys of the exported `<X>_AXIS_DEFAULTS` constant, or `null` when there is none.
function exportedDefaultsKeys(sourceFile, constant) {
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.name.text === constant) {
        const value = declaration.initializer && unwrap(declaration.initializer)
        return value && ts.isObjectLiteralExpression(value) ? propertyNames(value) : null
      }
    }
  }
  return null
}

// What the preview registers per primitive: `{ name: { axes: 'IDENT' | string[] } }`.
function registryAxes(previewText) {
  const sourceFile = parse(previewText, 'preview.tsx')
  const registry = {}
  const visit = (node) => {
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
      node.left.getText(sourceFile).endsWith('__DS_TRACKED_PRIMITIVES__') &&
      ts.isObjectLiteralExpression(node.right)
    ) {
      for (const property of node.right.properties) {
        if (
          !ts.isPropertyAssignment(property) ||
          !ts.isObjectLiteralExpression(property.initializer)
        ) {
          continue
        }
        const axes = property.initializer.properties.find(
          (p) => ts.isPropertyAssignment(p) && p.name.getText(sourceFile) === 'axes',
        )
        if (!axes) continue
        registry[property.name.getText(sourceFile)] = ts.isIdentifier(axes.initializer)
          ? axes.initializer.text
          : ts.isObjectLiteralExpression(axes.initializer)
            ? propertyNames(axes.initializer)
            : null
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return registry
}

// One message per disagreement. `files` maps a primitive name to its `index.tsx` text; `preview` is
// `preview.tsx`'s text.
export function findAxisDrift({ files, preview }) {
  const problems = []
  const registry = registryAxes(preview)
  for (const name of Object.keys(registry)) {
    if (!TRACKED_PRIMITIVES.includes(name)) {
      problems.push(`${name}: the preview registers it but the axis check does not track it`)
    }
  }
  for (const name of TRACKED_PRIMITIVES) {
    const constant = `${name.toUpperCase()}_AXIS_DEFAULTS`
    const source = parse(files[name], `${name}/index.tsx`)
    const axes = destructuredAxes(source, name)
    if (!axes) {
      problems.push(`${name}: no \`export function ${name}\` found to read its axes from`)
      continue
    }
    for (const [axis, initializer] of Object.entries(axes)) {
      const expected = `${constant}.${axis}`
      if (name === 'Menu' && axis === 'variant') {
        if (initializer !== null) {
          problems.push(
            `${name}: \`variant\` has a default (\`${initializer}\`) but is required — the registry records it as passed or null`,
          )
        }
      } else if (initializer !== expected) {
        problems.push(
          `${name}: \`${axis}\` is destructured with ${initializer === null ? 'no default' : `\`${initializer}\``}, expected \`${expected}\``,
        )
      }
    }
    const registered = registry[name]
    if (registered === undefined) {
      problems.push(`${name}: the preview's registry does not list it`)
      continue
    }
    const defaults = exportedDefaultsKeys(source, constant)
    const withDefault = Object.keys(axes).filter((axis) => axes[axis] !== null)
    if (withDefault.length > 0) {
      if (registered !== constant) {
        problems.push(
          `${name}: the registry's axes should be \`${constant}\`, it is ${Array.isArray(registered) ? 'a literal' : `\`${registered}\``}`,
        )
      }
      if (defaults === null) problems.push(`${name}: it does not export \`${constant}\``)
      else if (JSON.stringify([...defaults].sort()) !== JSON.stringify([...withDefault].sort())) {
        problems.push(
          `${name}: \`${constant}\` has ${JSON.stringify(defaults)}, the destructuring defaults ${JSON.stringify(withDefault)}`,
        )
      }
    } else if (Array.isArray(registered)) {
      const listed = [...registered].sort()
      const destructured = Object.keys(axes).sort()
      if (JSON.stringify(listed) !== JSON.stringify(destructured)) {
        const extra = listed.filter((a) => !destructured.includes(a))
        const missing = destructured.filter((a) => !listed.includes(a))
        for (const axis of extra) {
          problems.push(`${name}: the registry lists \`${axis}\`, which ${name} never destructures`)
        }
        for (const axis of missing) {
          problems.push(`${name}: ${name} destructures \`${axis}\`, which the registry omits`)
        }
      }
    } else {
      problems.push(`${name}: the registry's axes should be a literal listing ${Object.keys(axes)}`)
    }
  }
  return problems
}
