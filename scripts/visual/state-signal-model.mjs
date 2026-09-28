#!/usr/bin/env node
// T675 (slice 2/N — closes the "55 of 113 not measurable" residue slice 1 left; see row 1 of
// packages/design-system/specs/README.md's "Verification-coverage gap register" for the measured
// numbers and this task's own text in tasks.md for the Done clause this slice closes: "the sweep
// runs against every state story in the tree").
//
// Pure discovery + self-pairing + classification logic for the comparator-blind-spot sweep. Nothing
// in this file touches the filesystem beyond reading `.stories.tsx` source (`readFileSync` is the
// caller's job, not this module's — every exported function here takes source text or already-
// parsed data, the same "no filesystem access below the pure functions" discipline
// `scripts/checks/state-coverage.mjs` documents at its own top) and nothing here launches a
// browser — `tests/visual/state-signal-sweep.spec.ts` is the one Playwright consumer, and
// `state-signal-model.test.mjs` is the one `node --test` consumer, of the exact same functions.
//
// **Slice 1's sibling-pairing rule is retired, not kept alongside this one.** It paired a state
// story against a *different* sibling story sharing the same resolved args, `play` and `render` —
// which left 55 of 113 state stories unmeasurable: 34 with no sibling sharing that exact shape, 21
// tied among more than one candidate (`Menu`'s own `Selection`/`SheetBelowMd`/`ProfileSwitcher`
// equivalence class among them). The resting counterpart this slice uses instead is the state
// story *itself*, rendered with its own state not applied — same args, same `render`, same
// viewport, same clip, by construction, for every story that forces a state at all, which removes
// the "no sibling" and "tied siblings" cases outright rather than working around them. Nothing about
// `argsTextMap`/`playKey`/`renderKey` equality survives here: comparing a story's args against its
// *own* args is always true, so the whole text-equality apparatus slice 1 built for that purpose
// (`mergedArgsTextMap`, `collectArgsText`, `argsTextMapsEqual`, `pairRestingStory`) is deleted along
// with it, per this task's own instruction not to leave a second pairing rule alive.
//
// Story extraction below reuses `scripts/checks/state-coverage.mjs`'s own exported AST helpers
// (`parseTsx`, `findMeta`, `findExportedStoryObjects`, `extractVisualForceState`,
// `buildTopLevelConstNodeMap`, `findPlayFocusTarget`) rather than writing a second parser, per this
// task's own instruction. Two things that file has no reason to expose are written fresh here, each
// narrowly scoped to what this sweep alone needs:
//   - `resolvePlayBody` is private there (not exported) — reimplemented verbatim from its own
//     shape (a story's own `play`, an arrow/function expression or an identifier resolved against
//     the file's top-level declarations) because ESM does not expose a module's unexported
//     bindings to an importer; there is no way to reuse the binding itself, only its shape.
//   - `extractVisualCaptureClip` reads `parameters.visualCaptureClip` the same way
//     `extractVisualForceState` reads `parameters.visualForceState` — state-coverage.mjs never
//     reads this parameter at all (grep confirms zero occurrences), so there is nothing to reuse.
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import {
  parseTsx,
  findMeta,
  findExportedStoryObjects,
  extractVisualForceState,
  buildTopLevelConstNodeMap,
  findPlayFocusTarget,
} from '../checks/state-coverage.mjs'
import { listComponentDirs, findStoryFile } from '../checks/story-docs.mjs'
import { REVIEW_WIDTHS } from './review-widths.mjs'

export const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
export const dsDir = path.join(rootDir, 'packages', 'design-system')
export const srcDir = path.join(dsDir, 'src')

// `typescript` and `storybook` are direct devDependencies of packages/design-system, not of the
// workspace root — resolved through that package's own node_modules, the same `createRequire`
// idiom `state-coverage.mjs` already uses for `typescript`.
const dsRequire = createRequire(path.join(dsDir, 'package.json'))
const ts = dsRequire('typescript')
// `storybook/internal/csf` is the real package's own published subpath (`package.json`'s own
// `exports` map) carrying the exact `sanitize`/`toStartCaseStr`/`toId` functions the running
// Storybook build derives every story's `id` from — reused rather than reimplemented so a display
// name this file cannot special-case (an emoji, an acronym) can never compute a different id than
// the real build assigns it.
const { toId, storyNameFromExport } = dsRequire('storybook/internal/csf')

export const THEMES = ['light', 'dark']
export const WIDTHS = REVIEW_WIDTHS

// One percent, `story-baselines-duplicates.mjs`'s own `DUPLICATE_MAX_DIFF_RATIO` and
// `playwright.config.ts`'s own `maxDiffPixelRatio` — this task's own bucket boundary, not a new
// number invented for this file.
export const CLIP_FIX_THRESHOLD = 0.01

// --- Tiny AST accessors state-coverage.mjs keeps private -----------------------------------------
// (`getProp`/`literalOf` there are exactly this shape; not exported, so mirrored here rather than
// guessed at. Neither reads or resolves anything `state-coverage.mjs` does not already resolve the
// same way elsewhere in that file.)

function getProp(objLiteral, name) {
  if (!objLiteral || !ts.isObjectLiteralExpression(objLiteral)) return undefined
  for (const prop of objLiteral.properties) {
    if (ts.isPropertyAssignment(prop) && prop.name.getText() === name) return prop.initializer
    if (ts.isShorthandPropertyAssignment(prop) && prop.name.getText() === name) return prop.name
  }
  return undefined
}

function literalOf(expr) {
  if (!expr) return { present: false }
  // `{ role: 'link' as const }` (`AccountErasurePanel.stories.tsx`'s own `erasedScreenLinkClip`,
  // among others) wraps the literal in an `AsExpression` — unwrapped here the same way
  // `findExportedStoryObjects` already unwraps a story object's own top-level `satisfies`/`as`,
  // never guessed at: without this, every `as const`-annotated clip part's `role`/`name`/`selector`
  // read back `{ present: true, literal: false }` and silently vanished from the resolved clip.
  while (expr && (ts.isAsExpression(expr) || ts.isSatisfiesExpression(expr))) {
    expr = expr.expression
  }
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) {
    return { present: true, literal: true, value: expr.text }
  }
  if (ts.isNumericLiteral(expr)) return { present: true, literal: true, value: Number(expr.text) }
  if (expr.kind === ts.SyntaxKind.TrueKeyword) return { present: true, literal: true, value: true }
  if (expr.kind === ts.SyntaxKind.FalseKeyword)
    return { present: true, literal: true, value: false }
  return { present: true, literal: false }
}

// state-coverage.mjs's own private `resolvePlayBody` — see this file's header comment for why an
// unexported binding cannot be imported and is mirrored here instead, verbatim in shape.
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

// `parameters.visualCaptureClip`, read the same shape `extractVisualForceState` reads
// `parameters.visualForceState` in — state-coverage.mjs never reads this parameter (see this
// file's header comment), so there is no existing function to reuse here. `constNodeMap`
// (`buildTopLevelConstNodeMap`, reused) resolves a bare identifier naming a top-level const
// (`Button.stories.tsx`'s own `GHOST_LG_CLIP`, `Dialog.stories.tsx`'s `PRIMARY_ACTION_CLIP`,
// `Menu.stories.tsx`'s `TRIGGER_CLIP`) back to the object literal it names — the shape every real
// `visualCaptureClip` in this tree that is not written inline uses.
export function extractVisualCaptureClip(storyObj, constNodeMap = new Map()) {
  const params = getProp(storyObj, 'parameters')
  let clip = getProp(params, 'visualCaptureClip')
  if (clip && ts.isIdentifier(clip) && constNodeMap.has(clip.text)) {
    clip = constNodeMap.get(clip.text)
  }
  if (!clip || !ts.isObjectLiteralExpression(clip)) return null
  const partsExpr = getProp(clip, 'parts')
  if (!partsExpr || !ts.isArrayLiteralExpression(partsExpr)) return null
  const parts = []
  for (const el of partsExpr.elements) {
    if (!ts.isObjectLiteralExpression(el)) continue
    const selector = literalOf(getProp(el, 'selector'))
    const role = literalOf(getProp(el, 'role'))
    const name = literalOf(getProp(el, 'name'))
    const nth = literalOf(getProp(el, 'nth'))
    parts.push({
      selector: selector.present && selector.literal ? selector.value : undefined,
      role: role.present && role.literal ? role.value : undefined,
      name: name.present && name.literal ? name.value : undefined,
      nth: nth.present && nth.literal ? nth.value : undefined,
    })
  }
  const pad = literalOf(getProp(clip, 'pad'))
  return { parts, pad: pad.present && pad.literal ? pad.value : undefined }
}

// --- Per-file story-state extraction ---------------------------------------------------------

// One exported story's own shape this sweep needs — never the full record `state-coverage.mjs`'s
// own `computeStateCoverage` builds, which answers a different question (does *some* story credit a
// specific interactive element) than this one (does *this* story's own forced state have a faithful
// rest — itself, with the state not applied — and what does the comparator say about the two).
export function extractFileStoryStates(filePath, source) {
  const sourceFile = parseTsx(filePath, source)
  const metaObj = findMeta(sourceFile)
  if (!metaObj) return null
  const idLit = literalOf(getProp(metaObj, 'id'))
  if (!idLit.present || !idLit.literal) {
    // Every story file with a `visualForceState` in the tree today sets an explicit `meta.id`
    // (confirmed by reading all 25) — a file relying instead on Storybook's own title-derived id
    // would need this sweep to sanitise `title` the same way `toId` does with no explicit `name`
    // half, which `toId` itself already does when called with only one argument; rather than
    // silently guess which of the two shapes a new file might pick, this throws so a future file
    // that breaks the convention is caught here rather than mis-attributed.
    throw new Error(
      `${filePath}: meta has no string-literal "id" — every story file this sweep has seen so far ` +
        'sets one explicitly; extend this function deliberately before relying on title-derived ids.',
    )
  }
  const kind = idLit.value
  const constNodeMap = buildTopLevelConstNodeMap(sourceFile)
  const storyObjs = findExportedStoryObjects(sourceFile)

  const stories = storyObjs.map(({ exportName, node }) => {
    const forced = extractVisualForceState(node)
    const playBody = resolvePlayBody(node, sourceFile)
    const playFocus = forced ? null : findPlayFocusTarget(playBody)
    // A story's own `name:` (`Menu.stories.tsx`'s `ClosedTrigger`, `"Closed trigger — the resting
    // half of expansion"`) overrides only the *display* label Storybook's sidebar shows — never the
    // `id` a URL navigates to, which Storybook derives from the export key alone regardless.
    // Confirmed against the real build (`storybook-static/index.json`): `ClosedTrigger`'s own real
    // id is `primitives-menu--closed-trigger`, not a sanitised form of its display name at all.
    const id = toId(kind, storyNameFromExport(exportName))
    const clip = extractVisualCaptureClip(node, constNodeMap)
    // A play()-left focus-visible frame with no `visualForceState` of its own (this task's own
    // "plus focus-visible frames left by a play()" clause) is still a *forced* state as far as this
    // sweep's own rendering is concerned: navigating to the story and letting its own play() run
    // already produces the "state" frame (`tests/visual/story-render.ts`'s own settle-wait already
    // waits for the story's play phase to finish before anything reads the DOM) — the "rest" is the
    // same render with that focus removed (`planSelfRest`'s own `'play-focus-blur'` mode).
    const isStateStory = Boolean(forced) || Boolean(playFocus)
    return { exportName, id, forced, playFocus, isStateStory, clip }
  })

  return { kind, stories }
}

// --- Self-pairing: the resting counterpart of a state story is itself ----------------------------

// What it takes to capture a faithful "without the state" frame of `story`, from `story` alone —
// never a sibling. Two real shapes exist in this tree today, and a third, static "cannot tell"
// case this sweep refuses to guess past:
//   - `'forced'` (109 of 113 state stories): `story.forced` names a real CSS pseudo-class
//     (`tests/visual/story-render.ts`'s own `applyForceState` drives it, after the story has
//     settled). The rest is the *same* settled render, captured *before* that driving — always
//     faithful, by construction: nothing about "not yet having pressed the button" can fail to be a
//     valid rest frame for "having pressed it".
//   - `'play-focus-blur'` (the remaining real cases, e.g. `Dialog` `KeyboardFocusOrderAndTrap`): no
//     `visualForceState` names the state — it is whatever `document.activeElement` genuinely is
//     once the story's own `play()` has finished. The rest is the same settled render with that
//     element blurred (`document.activeElement.blur()`, run by the spec after capturing the state
//     frame) — safe for every real case in this tree (confirmed by reading `Dialog`'s own focus trap
//     and `Menu`'s own roving-focus effect: both key off real `keydown`/state-driven re-renders,
//     never `blur`, so a programmatic `.blur()` triggers neither) and, unlike `'forced'`, decided
//     for real at render time — `document.activeElement` is a DOM fact this static pass cannot
//     compute, so nothing here inspects the play body except to confirm one thing genuinely
//     resolves.
//   - Not measurable: `story.playFocus` was found but its own target does not resolve to a role or
//     selector this sweep trusts (`findPlayFocusTarget`'s own `'unresolved'` sentinel — a `.focus()`
//     call on an expression this static pass cannot read back as a role/selector at all). Blurring
//     `document.activeElement` would still work mechanically at render time, but nothing here can
//     confirm in advance which element that even is, so this is reported rather than guessed —
//     unexercised by any real story in this tree today (all four real `'play-focus-blur'` cases
//     resolve a role cleanly), proven instead by `state-signal-model.test.mjs`'s own synthetic
//     fixture.
export function planSelfRest(story) {
  if (story.forced) {
    return { measurable: true, mode: 'forced' }
  }
  if (story.playFocus) {
    if (!story.playFocus.role || story.playFocus.role === 'unresolved') {
      return {
        measurable: false,
        reason: 'play-focus-target-unresolved',
        detail:
          `${story.exportName}'s own play() calls .focus()/toHaveFocus() on a target this sweep ` +
          `cannot resolve to a role or selector (${JSON.stringify(story.playFocus)}) — blurring ` +
          'document.activeElement at render time would still work mechanically, but nothing here ' +
          'can confirm in advance which element that even is, so this is reported rather than ' +
          'guessed.',
      }
    }
    return { measurable: true, mode: 'play-focus-blur' }
  }
  return {
    measurable: false,
    reason: 'not-a-state-story',
    detail:
      `${story.exportName} forces no state (\`visualForceState\`) and its own play(), if any, ` +
      'leaves no discovered focus target — nothing to pair against itself.',
  }
}

// --- Classification ----------------------------------------------------------------------------

// `unitResults`: one entry per {theme, width} this state story renders in, each
// `{ theme, width, diffPixels, totalPixels, ratio, dimensionMismatch }`. `hasClip` is whether the
// story itself already names a `visualCaptureClip` (both frames — state and self-rest — are cropped
// to it either way, per this task's own method — `hasClip` only changes which of the four/five
// outcomes below applies, never how the numbers themselves were produced).
//
// Five outcomes, the four this task's own text names plus one it does not (a story that already
// defends over 1% on every unit *without* any clip at all — no real example in this tree's own
// required contrast list, but nothing rules it out elsewhere, and silently folding it into
// "defended" would erase the fact that no clip was needed for it, information a later reader might
// want): `zero` (no clip can help), `clip-fixes` (a clip is a mechanical fix), `clipped-still-under-threshold`
// (already clipped, still at or under 1% — this task's own "flag a clip that does not defend"),
// `defended` (already clipped, over 1% everywhere) and `defended-without-clip` (over 1% everywhere,
// no clip in the picture at all).
export function classifyBucket({ hasClip, unitResults }) {
  if (unitResults.length === 0) {
    throw new Error('classifyBucket: unitResults must not be empty.')
  }
  const mismatched = unitResults.filter((u) => u.dimensionMismatch)
  if (mismatched.length > 0) {
    return {
      bucket: 'dimension-mismatch',
      detail:
        `${mismatched.length} of ${unitResults.length} unit(s) render the state and resting ` +
        'story at different pixel dimensions, so the comparator cannot answer this pair at all — ' +
        'a real signal (probably a size- or layout-affecting state), not a comparator blind spot.',
    }
  }
  const ratios = unitResults.map((u) => u.ratio)
  const allZero = ratios.every((r) => r === 0)
  const minRatio = Math.min(...ratios)
  if (allZero) {
    return { bucket: hasClip ? 'zero-despite-clip' : 'zero', minRatio: 0 }
  }
  if (minRatio <= CLIP_FIX_THRESHOLD) {
    return { bucket: hasClip ? 'clipped-still-under-threshold' : 'clip-fixes', minRatio }
  }
  return { bucket: hasClip ? 'defended' : 'defended-without-clip', minRatio }
}

// --- Discovery ---------------------------------------------------------------------------------

// Every `*.stories.tsx` file under the package's three tiers — `listComponentDirs`/`findStoryFile`
// reused from `scripts/checks/story-docs.mjs` rather than a third directory walk (`run.mjs` reads
// the built Storybook index instead; `state-coverage.mjs` reads the filesystem the same way this
// does).
export function discoverStoryFiles(rootSrcDir = srcDir) {
  const files = []
  for (const { segment, name } of listComponentDirs(rootSrcDir)) {
    const storyFile = findStoryFile(rootSrcDir, segment, name)
    if (storyFile) files.push(storyFile)
  }
  return files
}
