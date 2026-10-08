// The one reader of a file's module specifiers, with the TypeScript parser, shared by the two
// consumers that must agree on what "a file imports X" means: `scripts/checks/state-coverage.mjs`
// (the story-module import rule, T701/T704/T705) and `scripts/visual/story-selection.mjs` (the
// import walk that selects a story when a module it imports changed, T707). Two readers would drift;
// a regex reader would miss `import()` types, `export … from` and `import x = require()`.
//
// `unwrapExpression` lives here, not in the checker, because `isPlainStringLiteral` needs it and the
// checker imports this module: it re-exports `unwrapExpression` so its other consumers
// (`state-signal-model.mjs`) keep their import.
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

// `typescript` is a direct devDependency of packages/design-system, not of the workspace root —
// resolved through that package's own node_modules, the idiom `state-coverage.mjs` uses.
const ts = createRequire(path.join(rootDir, 'packages', 'design-system', 'package.json'))(
  'typescript',
)

// Strips every `as <T>`, `satisfies <T>`, `x!` and `(...)` wrapper off an expression node, in whatever
// order and however many deep they nest (`({...} as const)`, `{...} satisfies X as const`, and so
// on) — never a single fixed shape, since nothing in this codebase's own TypeScript enforces one.
// `findExportedStoryObjects` used to unwrap `satisfies` then `as` once each, inline, which is what
// every real story object in this tree happens to need; `buildTopLevelConstNodeMap` unwrapped
// neither at all, so a top-level `const X = {...} as const` — the shape `Button.stories.tsx`'s own
// `PRIMARY_LG_CLIP` and most `visualCaptureClip` constants across this tree use — stored the
// `AsExpression` itself. Every caller that then asked `ts.isObjectLiteralExpression(node)` (T675's
// own `state-signal-model.mjs#extractVisualCaptureClip`, among others) got `false` and silently
// treated a real, present clip as absent — the sweep's own `hasClip` field misreporting `false`
// for a clipped story, found while implementing T675's own second-pass signals (slice 4b). Shared
// here so every caller unwraps the same way, once.
export function unwrapExpression(node) {
  while (
    node &&
    (ts.isAsExpression(node) ||
      ts.isSatisfiesExpression(node) ||
      ts.isParenthesizedExpression(node) ||
      ts.isNonNullExpression(node))
  ) {
    node = node.expression
  }
  return node
}

// Whether an expression is a plain string literal: a string or a no-substitution template, with `!`,
// `as`, `satisfies` and parentheses unwrapped. T704: it is the only specifier an `import()` or a
// `require()` of a non-test module may take. What a template with a substitution, a `+` concatenation, a
// conditional, a call or a variable evaluates to is not read, and its last literal part says nothing of
// what the first parts build, so none of them is told apart from the others.
function isPlainStringLiteral(expression) {
  const node = unwrapExpression(expression)
  return Boolean(node) && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))
}

const isRequireOrImportCall = (node) =>
  ts.isCallExpression(node) &&
  (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
    (ts.isIdentifier(node.expression) && node.expression.text === 'require'))

// Every module specifier a file names as a plain string literal, whatever the form: a static `import`
// (type-only included), an `export … from`, an `import x = require()`, a dynamic `import()` or an
// `import()` type, a `require()`. A specifier that is not a plain string literal is not in the list: it
// is `findNonLiteralSpecifiers`'s.
export function collectModuleSpecifiers(sourceFile) {
  const found = []
  const consider = (expression) => {
    if (!isPlainStringLiteral(expression)) return
    found.push(unwrapExpression(expression).text)
  }
  const visit = (node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      found.push(node.moduleSpecifier.text)
    } else if (
      ts.isImportEqualsDeclaration(node) &&
      ts.isExternalModuleReference(node.moduleReference)
    ) {
      consider(node.moduleReference.expression)
    } else if (
      ts.isImportTypeNode(node) &&
      ts.isLiteralTypeNode(node.argument) &&
      ts.isStringLiteral(node.argument.literal)
    ) {
      found.push(node.argument.literal.text)
    } else if (isRequireOrImportCall(node)) {
      consider(node.arguments[0])
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return found
}

// T704: every `import()` or `require()` (and `import x = require(...)`) in a file whose specifier is not
// a plain string literal: the text of the call, truncated. Vite compiles a templated `import()` into a
// glob over every file its static parts can match, so a specifier is not read from its last part (the
// T701 rule for `import.meta.glob`, applied to the call that becomes one). The wholly computed
// `import(name)` and `require(name)` are in the list: what they load is not readable at all.
export function findNonLiteralSpecifiers(sourceFile) {
  const found = []
  const describe = (node) => {
    const text = node.getText(sourceFile).replace(/\s+/g, ' ')
    found.push(text.length > 80 ? `${text.slice(0, 77)}...` : text)
  }
  const visit = (node) => {
    if (isRequireOrImportCall(node)) {
      if (!isPlainStringLiteral(node.arguments[0])) describe(node)
    } else if (
      ts.isImportEqualsDeclaration(node) &&
      ts.isExternalModuleReference(node.moduleReference) &&
      !isPlainStringLiteral(node.moduleReference.expression)
    ) {
      describe(node)
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return found
}
