#!/usr/bin/env node
// T675 (slice 1/N — the package-wide sweep only; see this task's own text in tasks.md and row 1 of
// packages/design-system/specs/README.md's "Verification-coverage gap register" for what the later
// slices still owe).
//
// Pure discovery + pairing + classification logic for the comparator-blind-spot sweep. Nothing in
// this file touches the filesystem beyond reading `.stories.tsx` source (`readFileSync` is the
// caller's job, not this module's — every exported function here takes source text or already-
// parsed data, the same "no filesystem access below the pure functions" discipline
// `scripts/checks/state-coverage.mjs` documents at its own top) and nothing here launches a
// browser — `tests/visual/state-signal-sweep.spec.ts` is the one Playwright consumer, and
// `state-signal-model.test.mjs` is the one `node --test` consumer, of the exact same functions.
//
// Story extraction below reuses `scripts/checks/state-coverage.mjs`'s own exported AST helpers
// (`parseTsx`, `findMeta`, `findExportedStoryObjects`, `extractVisualForceState`,
// `buildTopLevelConstNodeMap`, `findPlayFocusTarget`) rather than writing a second parser, per this
// task's own instruction. Three things that file has no reason to expose are written fresh here,
// each narrowly scoped to what this sweep alone needs:
//   - `resolvePlayBody` is private there (not exported) — reimplemented verbatim from its own
//     shape (a story's own `play`, an arrow/function expression or an identifier resolved against
//     the file's top-level declarations) because ESM does not expose a module's unexported
//     bindings to an importer; there is no way to reuse the binding itself, only its shape.
//   - `extractVisualCaptureClip` reads `parameters.visualCaptureClip` the same way
//     `extractVisualForceState` reads `parameters.visualForceState` — state-coverage.mjs never
//     reads this parameter at all (grep confirms zero occurrences), so there is nothing to reuse.
//   - The "same args once state/clip parameters are removed" pairing rule this task's own text
//     asks for is answered by *source-text* equality of each merged arg property (meta's `args`
//     overridden by the story's own, spreads of a top-level const object expanded one level via
//     `buildTopLevelConstNodeMap`), not by `evaluateMergedArgsObject`'s evaluated JS values. Every
//     real pairing in this tree already writes the paired stories' `args` byte-for-byte identically
//     (Button's `Hover`/`Primary`, Dialog's `Hover`/`Default`, Menu's `TriggerHover`/
///    `ClosedTrigger` — confirmed by reading each file directly), and text equality sidesteps a
//     real gap in evaluated-value equality: a nested JSX literal inside an `args` object (Menu's
//     `items[0].badge: <span>Primary</span>`) evaluates to the same *unresolvable* sentinel on
//     both sides of a real match, which would make evaluated-value equality either treat every
//     unresolvable leaf as a match (wrong: two genuinely different unresolvable expressions would
//     then look equal) or refuse to compare at all (wrong: it would falsely call every JSX-bearing
//     pair "not measurable"). Source text does not have this problem: prettier enforces one quote
//     style and one property order is never reordered by this codebase's own formatting, so two
//     properties are byte-identical text if and only if they are the same expression, whether or
//     not that expression is statically evaluable. `argsTextMapsEqual`'s own test file exercises
//     the size trap this task's text names directly (`Primary` carries `size: 'lg'`; a sibling that
//     omits `size` entirely differs in *key set*, not merely in value, so it is never paired).
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
// `visualCaptureClip` in this tree that is not written inline uses. An earlier version of this
// function only ever checked `ts.isObjectLiteralExpression(clip)` directly, which is `false` for an
// identifier, so it silently read every one of those four as "no clip at all" — the reason
// `Dialog Active` and `Menu TriggerFocusVisible` first classified into "defended, no clip" rather
// than "defended, already clipped": confirmed by re-running the sweep after this fix moved both.
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

// --- "Same args" pairing, by source text, not by evaluated value ---------------------------------
// See this file's header comment for why text, not `evaluateMergedArgsObject`'s evaluated values.

function normalisedText(sourceFile, node) {
  return node.getText(sourceFile).replace(/\s+/g, ' ').trim()
}

// Populates `map` (propName -> its own initializer's normalised source text) from one `args`
// object literal, meta's first and the story's own second so the story's own value wins — the same
// override order `evaluateMergedArgsObject` uses, just carrying text instead of a value. A spread
// of a top-level const object (`...noopHandlers`) is expanded one level via `constNodeMap`
// (`buildTopLevelConstNodeMap`, reused) so `AccountErasurePanel`-shaped stories compare correctly;
// a spread this cannot resolve (anything other than a bare identifier naming a top-level const
// object literal — none exist in this tree today) leaves the property set incomplete on purpose,
// which can only ever make two stories compare *unequal* that a fuller resolution might have
// matched, never the reverse — the pairing rule's own "never silently paired" rule already asks for
// that direction of caution when in doubt.
function collectArgsText(sourceFile, objLiteral, constNodeMap, map, seen = new Set()) {
  if (!objLiteral || !ts.isObjectLiteralExpression(objLiteral)) return
  for (const prop of objLiteral.properties) {
    if (ts.isPropertyAssignment(prop) && !ts.isComputedPropertyName(prop.name)) {
      map.set(prop.name.getText(sourceFile), normalisedText(sourceFile, prop.initializer))
    } else if (ts.isShorthandPropertyAssignment(prop)) {
      map.set(prop.name.text, prop.name.getText(sourceFile))
    } else if (
      ts.isSpreadAssignment(prop) &&
      ts.isIdentifier(prop.expression) &&
      !seen.has(prop.expression.text)
    ) {
      const target = constNodeMap.get(prop.expression.text)
      if (target) {
        collectArgsText(
          sourceFile,
          target,
          constNodeMap,
          map,
          new Set([...seen, prop.expression.text]),
        )
      }
    }
  }
}

export function mergedArgsTextMap(sourceFile, metaObj, storyObj, constNodeMap) {
  const map = new Map()
  collectArgsText(sourceFile, getProp(metaObj, 'args'), constNodeMap, map)
  collectArgsText(sourceFile, getProp(storyObj, 'args'), constNodeMap, map)
  return map
}

// Two stories carry "the same args" exactly when their merged text maps agree on every key AND
// carry the same key set — a key present on one side and absent on the other (`Primary`'s own
// `size: 'lg'` against a sibling that omits `size` and relies on the component's own default) is a
// difference in what is being asked for, not only in its value, so it is never treated as a match
// (this task's own named trap).
export function argsTextMapsEqual(a, b) {
  if (a.size !== b.size) return false
  for (const [key, value] of a) {
    if (b.get(key) !== value) return false
  }
  return true
}

// --- Per-file story-state extraction ---------------------------------------------------------

// One exported story's own shape this sweep needs — never the full record `state-coverage.mjs`'s
// own `computeStateCoverage` builds, which answers a different question (does *some* story credit
// a specific interactive element) than this one (does *this* story's own forced state have a
// same-args, same-size resting sibling in its own file, and what does the comparator say about the
// two).
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
    // id is `primitives-menu--closed-trigger`, not a sanitised form of its display name at all — an
    // earlier version of this function used the override for `id` too and every pair naming a
    // `name`-overridden story 404'd ("Couldn't find story matching …") the moment the sweep tried
    // to navigate to it.
    const id = toId(kind, storyNameFromExport(exportName))
    const clip = extractVisualCaptureClip(node, constNodeMap)
    const argsTextMap = mergedArgsTextMap(sourceFile, metaObj, node, constNodeMap)
    // A play()-left focus-visible frame with no `visualForceState` of its own (this task's own
    // "plus focus-visible frames left by a play()" clause) is still a *forced* state as far as
    // this sweep's own rendering is concerned: navigating to the story and letting its own play()
    // run is enough, no `applyForceState` call needed (`tests/visual/story-render.ts`'s own
    // settle-wait already waits for the story's play phase to finish before anything reads the
    // DOM) — `isStateStory` below folds both into one boolean because the pairing rule treats them
    // identically (this file's own resting counterpart is whichever sibling story is genuinely
    // unforced), but `forced`/`playFocus` stay separate fields so the sweep knows *which* one to
    // drive from Playwright.
    const isStateStory = Boolean(forced) || Boolean(playFocus)
    // A story's own `play` is not an "arg" — `argsTextMap` above never sees it — but it is still
    // part of what the rendered frame *is*: `Menu.stories.tsx`'s own `Expansion` and `ClosedTrigger`
    // carry byte-identical `args` (an open-panel story and its own closed resting half share the
    // same trigger data on purpose) yet render completely differently, because `Expansion` runs
    // `play: openMenu` and `ClosedTrigger` has no `play` at all. Comparing this alongside args text
    // is what keeps `TriggerHover`/`TriggerActive`/`TriggerFocusVisible` from pairing with
    // `Expansion` by args-coincidence — the resting counterpart must run the *same* play (most
    // often: neither runs one) as well as carry the same args. An identifier `play` (`openMenu`) is
    // compared by name, not by re-resolving and re-comparing the function body: two different
    // top-level functions sharing one body would be a separate, harder-to-imagine defect this sweep
    // does not try to catch.
    const playExpr = getProp(node, 'play')
    const playKey = playExpr ? normalisedText(sourceFile, playExpr) : null
    // The same reasoning as `playKey` above, for a story's own `render:` — `Footer.stories.tsx`'s
    // own `DisabledLoadingErrorNotApplicable` carries byte-identical `args` to `BothLinks` but
    // wraps the component in an extra explanatory `<p>` via its own `render:`, a real difference in
    // what is on screen that `argsTextMap` (which never reads `render:`) cannot see on its own.
    const renderExpr = getProp(node, 'render')
    const renderKey = renderExpr ? normalisedText(sourceFile, renderExpr) : null
    return {
      exportName,
      id,
      forced,
      playFocus,
      isStateStory,
      clip,
      argsTextMap,
      playKey,
      renderKey,
    }
  })

  return { kind, stories }
}

// --- Pairing ---------------------------------------------------------------------------------

// The state story's own resting counterpart: the one sibling in `allStoriesInFile` that is not
// itself a state story and shares its exact merged-args text map — see `argsTextMapsEqual`'s own
// comment for what "same" means here. Zero candidates and more than one candidate are both
// reported, never guessed past (`measurable: false`, with a machine-readable `reason` naming which
// of the two it was and, for the ambiguous case, every tied candidate).
export function pairRestingStory(stateStory, allStoriesInFile) {
  const candidates = allStoriesInFile.filter(
    (s) =>
      s !== stateStory &&
      !s.isStateStory &&
      s.playKey === stateStory.playKey &&
      s.renderKey === stateStory.renderKey &&
      argsTextMapsEqual(s.argsTextMap, stateStory.argsTextMap),
  )
  if (candidates.length === 0) {
    return {
      measurable: false,
      reason: 'no-same-args-sibling',
      detail:
        `no sibling story in this file shares ${stateStory.exportName}'s own resolved args ` +
        '(including its size) and own play() behavior once the state/clip parameters are removed.',
    }
  }
  if (candidates.length > 1) {
    return {
      measurable: false,
      reason: 'ambiguous-siblings',
      detail: `${candidates.length} siblings share the same args: ${candidates
        .map((c) => c.exportName)
        .join(', ')}.`,
    }
  }
  return { measurable: true, restStory: candidates[0] }
}

// --- Classification ----------------------------------------------------------------------------

// `unitResults`: one entry per {theme, width} this state story renders in, each
// `{ theme, width, diffPixels, totalPixels, ratio, dimensionMismatch }`. `hasClip` is whether the
// *state* story itself already names a `visualCaptureClip` (both frames are cropped to it either
// way, per this task's own method — `hasClip` only changes which of the four/five outcomes below
// applies, never how the numbers themselves were produced).
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
