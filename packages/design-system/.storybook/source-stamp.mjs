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
//   - every intrinsic JSX element (a lowercase tag name: `div`, `button`, `svg`) of a file under
//     `packages/design-system/src` that is not a story and not a test. A component tag (`<Button>`)
//     is not stamped — the element it renders is, from the file that wrote it.
//   - an element a design-system file hands to `cloneElement`: the call's own props gain the stamp,
//     keyed to the *call's* location. `Field` places its control that way (it clones its child
//     rather than rendering it), so without this the control would carry no stamp, or the caller's,
//     and could not be attributed to `Field`.
// A story file is never stamped: an element a story writes carries no stamp, which is exactly how the
// pass tells a forced element a primitive placed from one a story wrote beside it.
//
// Nothing reaches the markup `apps/web` builds: `apps/web/vite.config.ts` does not import this module,
// and `scripts/checks/stamp-absent.mjs` (run in CI after `pnpm --filter web build`) fails when the
// built output carries the attribute. `scripts/visual/source-stamp.test.mjs` covers both and the
// transform's own cases.
import { createRequire } from 'node:module'
import path from 'node:path'

// `typescript` is a direct devDependency of this package; resolved from this file, which sits inside
// it (`state-coverage.mjs` resolves it the same way).
const require = createRequire(import.meta.url)
const ts = require('typescript')

export const STAMP_ATTRIBUTE = 'data-ds-src'

const STAMPED_ROOT = 'packages/design-system/src/'
const STAMPED_EXTENSIONS = ['.tsx', '.ts', '.jsx', '.js']

// Whether a repository-rooted, posix path is a design-system source file the transform stamps.
export function isStampedFile(repoRelativePath) {
  if (!repoRelativePath.startsWith(STAMPED_ROOT)) return false
  if (!STAMPED_EXTENSIONS.some((ext) => repoRelativePath.endsWith(ext))) return false
  return !/\.(stories|test)\.[jt]sx?$/.test(repoRelativePath)
}

function isCloneElementCall(node) {
  if (!ts.isCallExpression(node)) return false
  const callee = node.expression
  if (ts.isIdentifier(callee)) return callee.text === 'cloneElement'
  return ts.isPropertyAccessExpression(callee) && callee.name.text === 'cloneElement'
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
  const keyOf = (node) =>
    `${repoRelativePath}:${sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1}`

  const visit = (node) => {
    if (
      (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
      ts.isIdentifier(node.tagName) &&
      /^[a-z]/.test(node.tagName.text)
    ) {
      insertions.push({
        pos: node.tagName.getEnd(),
        text: ` ${STAMP_ATTRIBUTE}="${keyOf(node)}"`,
      })
    } else if (isCloneElementCall(node)) {
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
