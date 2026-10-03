#!/usr/bin/env node
// T675 (slice 2/N — closes the "55 of 113 not measurable" residue slice 1 left; see T675's closing note in
// packages/design-system/specs/README.md's "Verification-coverage gap register" for the measured
// numbers and this task's own text in tasks.md for the Done clause this slice closes: "the sweep
// runs against every state story in the tree").
//
// Pure discovery + self-pairing + classification logic for the comparator-blind-spot sweep. Nothing
// in this file touches the filesystem except `listStoryFilesOnDisk` (T679, one directory listing,
// kept apart from the pure functions it feeds); reading `.stories.tsx` source (`readFileSync`) is
// the caller's job, not this module's — every other exported function here takes source text or
// already-parsed data, the same "no filesystem access below the pure functions" discipline
// `scripts/checks/state-coverage.mjs` documents at its own top — and nothing here launches a
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
import { readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'
import {
  parseTsx,
  findMeta,
  findExportedStoryObjects,
  extractVisualForceState,
  buildTopLevelConstNodeMap,
  findPlayFocusTarget,
  unwrapExpression,
} from '../checks/state-coverage.mjs'
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
//
// Loaded with a dynamic `import()`, never `dsRequire(...)`: that subpath is ESM-only, and
// `require()` of an ES module needs Node >= 20.19 (root `package.json` allows `>=20`) — on an
// older Node it died with ERR_REQUIRE_ESM at import time. The top-level `await` keeps every
// consumer's own call sites synchronous. `run.mjs` imports this module lazily, only for
// `--state-signal-sweep`, so an ordinary `pnpm test:visual` never loads it at all.
const { toId, storyNameFromExport } = await import(
  pathToFileURL(dsRequire.resolve('storybook/internal/csf')).href
)

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

// The text of a property's name when it is a plain identifier or string-literal key (`id` and
// `'id'` are the same key); `null` for a computed key, which this file cannot read statically.
function propertyNameText(nameNode) {
  if (ts.isIdentifier(nameNode) || ts.isStringLiteralLike(nameNode)) return nameNode.text
  return null
}

function getProp(objLiteral, name) {
  if (!objLiteral || !ts.isObjectLiteralExpression(objLiteral)) return undefined
  for (const prop of objLiteral.properties) {
    if (ts.isPropertyAssignment(prop) && propertyNameText(prop.name) === name)
      return prop.initializer
    if (ts.isShorthandPropertyAssignment(prop) && prop.name.text === name) return prop.name
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
  // `unwrapExpression` (state-coverage.mjs): `buildTopLevelConstNodeMap` already unwraps a
  // referenced top-level const, but a clip written inline — `visualCaptureClip: {...} as const`,
  // directly in `parameters`, no separate declaration — never passes through that map at all, so
  // it needs the same unwrap here.
  clip = unwrapExpression(clip)
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
    // T675 slice 4c: `fragment` (`story-render.ts`'s own `VisualCaptureClipPart`) — extracted the
    // same way every other part field is, for the same reason: this function's own job is reading
    // back the real shape a story declares, not a subset of it chosen before `fragment` existed.
    // `hasClip` (this file's own caller, `run.mjs`) does not read it — whether a clip is present at
    // all does not depend on which of its parts name `fragment` — so this is completeness, not a
    // second behaviour.
    const fragment = literalOf(getProp(el, 'fragment'))
    parts.push({
      selector: selector.present && selector.literal ? selector.value : undefined,
      role: role.present && role.literal ? role.value : undefined,
      name: name.present && name.literal ? name.value : undefined,
      nth: nth.present && nth.literal ? nth.value : undefined,
      fragment: fragment.present && fragment.literal ? fragment.value : undefined,
    })
  }
  const pad = literalOf(getProp(clip, 'pad'))
  return { parts, pad: pad.present && pad.literal ? pad.value : undefined }
}

// The object literal a file's default export names, resolved through every syntax a meta is written
// in: `export default meta` (a top-level const, with or without a type annotation, `satisfies`,
// `as` or parentheses on its initializer), `export { meta as default }`, and an inline
// `export default { ... }` (likewise wrapped). `null` when the default export is not, or does not
// resolve to, an object literal in this file (a call such as `defineMeta(...)`, an import).
function findDefaultExportMeta(sourceFile, constNodeMap) {
  const resolve = (expr) => {
    expr = unwrapExpression(expr)
    if (expr && ts.isIdentifier(expr)) expr = constNodeMap.get(expr.text)
    return expr && ts.isObjectLiteralExpression(expr) ? expr : null
  }
  for (const statement of sourceFile.statements) {
    if (ts.isExportAssignment(statement) && !statement.isExportEquals) {
      const found = resolve(statement.expression)
      if (found) return found
    }
    if (
      ts.isExportDeclaration(statement) &&
      !statement.moduleSpecifier &&
      statement.exportClause &&
      ts.isNamedExports(statement.exportClause)
    ) {
      for (const specifier of statement.exportClause.elements) {
        if (specifier.name.text !== 'default') continue
        const found = resolve(specifier.propertyName ?? specifier.name)
        if (found) return found
      }
    }
  }
  return null
}

// Whether a meta object can carry a `component`: it names one (`component: C`, `'component': C`,
// shorthand), or it holds something this file cannot read statically (a spread, a computed key) that
// might. The conservative reading is the strict one — such a meta is a component file.
function mayCarryComponent(metaObj) {
  return metaObj.properties.some((prop) => {
    if (ts.isSpreadAssignment(prop)) return true
    if (!prop.name) return false
    if (ts.isComputedPropertyName(prop.name)) return true
    return propertyNameText(prop.name) === 'component'
  })
}

// --- Per-file story-state extraction ---------------------------------------------------------

function noLiteralIdMessage(filePath) {
  return (
    `${filePath}: meta has no string-literal "id" — every component story file this sweep has ` +
    'seen so far sets one explicitly (a component is never keyed by its title); extend this ' +
    'function deliberately before relying on title-derived ids for one.'
  )
}

// One exported story's own shape this sweep needs — never the full record `state-coverage.mjs`'s
// own `computeStateCoverage` builds, which answers a different question (does *some* story credit a
// specific interactive element) than this one (does *this* story's own forced state have a faithful
// rest — itself, with the state not applied — and what does the comparator say about the two).
export function extractFileStoryStates(filePath, source) {
  const sourceFile = parseTsx(filePath, source)
  const constNodeMap = buildTopLevelConstNodeMap(sourceFile)
  // T679: the meta is the object the file's default export names, however it is written
  // (`findDefaultExportMeta`); `findMeta` (a top-level const with a `component` key) is only the
  // fallback for a default export that does not resolve to an object literal here. Whether the file
  // is a *component* file or a componentless page (a foundations page under `.storybook/foundations/`,
  // documenting the token system itself) is decided from that object alone: a meta that carries a
  // `component` — or might, see `mayCarryComponent` — is a component file, in every syntax.
  const metaObj = findDefaultExportMeta(sourceFile, constNodeMap) ?? findMeta(sourceFile)
  if (!metaObj) {
    // T675 remediation (N3, the twin of M1(a)): used to `return null` here, and
    // `buildStoryFileWork`'s own `if (result) { ... }` below turned that into an empty
    // `{ measurable: [], notMeasurable: [] }` silently — a story file with no meta object this
    // function can locate vanished from the sweep exactly the way an unkeyable file (no literal
    // `meta.id`, thrown below) used to before M1. Thrown here for the same reason and caught the
    // same way: `buildStoryFileWork`'s own `try`/`catch` already turns any throw from this function
    // into an `unkeyable` entry, named by file, which is the only path M1 built for "this sweep
    // cannot key this file at all".
    throw new Error(
      `${filePath}: no default-exported meta object found (no object literal behind the default ` +
        'export, and no top-level const with a "component" property) — every story file this ' +
        'sweep has seen so far has one; extend this function deliberately before relying on a ' +
        'different shape.',
    )
  }
  // Storybook derives every story id from `meta.id` when set, else from `meta.title`, sanitised the
  // same way either way (`toId` below). This sweep reads an explicit `id` wherever there is one, and
  // falls back to the literal `title` for a componentless page alone: a component file that relies
  // on its title-derived id is the shape it refuses, so a file that breaks the convention is caught
  // here rather than mis-attributed.
  const idLit = literalOf(getProp(metaObj, 'id'))
  let kind
  if (idLit.present) {
    if (!idLit.literal) throw new Error(noLiteralIdMessage(filePath))
    kind = idLit.value
  } else if (mayCarryComponent(metaObj)) {
    throw new Error(noLiteralIdMessage(filePath))
  } else {
    const titleLit = literalOf(getProp(metaObj, 'title'))
    if (!titleLit.present || !titleLit.literal) {
      throw new Error(
        `${filePath}: meta has no "component" and no string-literal "title" — a componentless ` +
          'page is keyed by its literal title, and this one has none this sweep can read.',
      )
    }
    kind = titleLit.value
  }
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
// `{ theme, width, diffPixels, totalPixels, ratio, dimensionMismatch, stateMatchesBaseline }`.
// `hasClip` is whether the story itself already names a `visualCaptureClip` (both frames — state
// and self-rest — are cropped to it either way, per this task's own method — `hasClip` only changes
// which of the outcomes below applies, never how the numbers themselves were produced).
//
// Seven outcomes. `'state-not-reproduced'` (slice 3) is checked first and overrides every other
// question this function could otherwise answer: if `tests/visual/state-signal-sweep.spec.ts`'s own
// state capture does not match that story's *committed* baseline for some unit
// (`stateMatchesBaseline === false`), nothing this function could conclude from comparing that same
// capture to its own rest is trustworthy — the capture itself failed, not the comparison. Found
// necessary reading one committed baseline directly (`Tooltip` `HoverRevealed`'s own, still showing
// its tooltip open where this sweep's *rest* capture should have shown it closed) — the same shape
// as `dimension-mismatch` below (a check this function answers before trusting the pixel diff at
// all), but about the state frame's own fidelity rather than the two frames' own comparability.
// `dimension-mismatch` is checked second, for the same reason it always was. The remaining five are
// the four this task's own text names plus one it does not (a story that already defends over 1% on
// every unit *without* any clip at all — no real example in this tree's own required contrast list,
// but nothing rules it out elsewhere, and silently folding it into "defended" would erase the fact
// that no clip was needed for it, information a later reader might want): `zero` (no clip can help),
// `clip-fixes` (a clip is a mechanical fix), `clipped-still-under-threshold` (already clipped, still
// at or under 1% — this task's own "flag a clip that does not defend"), `defended` (already clipped,
// over 1% everywhere) and `defended-without-clip` (over 1% everywhere, no clip in the picture at
// all).
export function classifyBucket({ hasClip, unitResults }) {
  if (unitResults.length === 0) {
    throw new Error('classifyBucket: unitResults must not be empty.')
  }
  const unreproduced = unitResults.filter((u) => u.stateMatchesBaseline === false)
  if (unreproduced.length > 0) {
    return {
      bucket: 'state-not-reproduced',
      detail:
        `${unreproduced.length} of ${unitResults.length} unit(s) render a state frame that does ` +
        "not match this story's own committed baseline (beyond " +
        "tests/visual/state-signal-sweep.spec.ts's own BASELINE_MAX_DIFF_RATIO — see that " +
        "constant's own comment for why it is wider than playwright.config.ts's own " +
        'maxDiffPixelRatio) — this sweep failed to reproduce the state itself, so its own ' +
        'state-vs-rest diff answers nothing about whether the two are really distinguishable.',
    }
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

// T675 slice 4b: turns the sweep from a report into a gate. Five of `classifyBucket`'s eight
// outcomes fail — `zero`/`zero-despite-clip` (no non-fill signal at all), `clip-fixes`/
// `clipped-still-under-threshold` (a real signal that still does not clear the comparator's own
// 1% floor, clipped or not), and `state-not-reproduced` (the sweep could not even confirm the state
// frame it measured, so nothing it found can be trusted as a pass). Two pass: `defended`/
// `defended-without-clip` (a real, over-1% signal, FR-037's own bar), and `dimension-mismatch` —
// not because it is safe by inspection, but because a size or layout change fails
// `toHaveScreenshot` outright in the real visual suite (`playwright.config.ts`'s own
// `maxDiffPixelRatio`), so it is defended by construction and this sweep does not need to re-prove
// it. No allowlist, no per-story exception: every failing bucket names the story that earned it, and
// the only way off this list is a real, clipped, over-threshold signal.
const SWEEP_GATE_FAILING_BUCKETS = new Set([
  'zero',
  'zero-despite-clip',
  'clip-fixes',
  'clipped-still-under-threshold',
  'state-not-reproduced',
])

// T675 remediation (M1): the sweep used to fail open in three ways that made "no allowlist" untrue
// in practice, all closed here rather than papered over with an allowlist per this finding's own
// instruction:
//   (a) a story file this sweep cannot key at all (`extractFileStoryStates` throws — see
//       `buildStoryFileWork` for the cases) was only logged and skipped by the caller, never turned into a result this
//       function could see. Now the caller (`buildStoryFileWork` below) turns that throw into an
//       `unkeyableFiles` entry, and every one of those is an unconditional gate failure, named by
//       file.
//   (b) a not-measurable state story (`planSelfRest`'s own `measurable: false`) never reached this
//       function at all — the caller only ever passed `measurable`'s eventual classifications.
//       There is no genuinely-by-design "not measurable" case in this tree today: the one static
//       reason `planSelfRest` can return for an actual state story, `'play-focus-target-unresolved'`,
//       is (per that function's own comment) a real gap this sweep cannot confirm past, not an
//       intentional exemption — so every `notMeasurable` entry fails here too, named with its own
//       reason.
//   (c) `classified` reaching this function empty, or shorter/longer than the `measurable` list the
//       caller planned, used to be invisible: the old `decideSweepGate(classified)` read only
//       `classified` itself, so "nothing was classified at all" and "every measured pair classified
//       cleanly" looked identical (`pass: true`) — the exact shape a crashed Playwright render (a
//       measurable pair that planned a classification and produced none) hid behind. Both are gate
//       failures now, checked before any individual bucket.
//
// T675 remediation (N3): `measurableCount` alone answers only "how many", never "which ones" — a
// run that planned {a, b} but classified {a, c} (one crashed, an unrelated one somehow classified
// twice, or any other same-length swap) passed the count check above with nothing to show for it.
// `measurableIds`, when the caller supplies it (`run.mjs` does; the many pre-existing tests above
// that only ever supplied `measurableCount` still pass without it, unaffected), is compared against
// `classified`'s own story ids as sets — a planned id absent from `classified` ("missing") or a
// classified id never planned as measurable ("unexpected") each fail the gate, named, independent
// of whether the two lists happen to be the same length.
export function decideSweepGate({
  classified,
  measurableCount,
  measurableIds,
  notMeasurable = [],
  unkeyableFiles = [],
  discoveryGaps = [],
}) {
  const failures = []

  // T679: every gap `buildStateSignalWork` found between what Storybook's built index lists, what
  // this sweep's source parse reached and the story files on disk is an unconditional failure, named — the same "no allowlist"
  // rule as the buckets below, applied to discovery itself.
  for (const g of discoveryGaps) {
    failures.push({
      kind: 'discovery-gap',
      stateId: g.stateId ?? null,
      bucket: `discovery-gap:${g.kind}`,
      file: g.file,
      detail: g.detail,
    })
  }

  for (const u of unkeyableFiles) {
    failures.push({
      kind: 'unkeyable-file',
      stateId: null,
      bucket: 'unkeyable-file',
      file: u.file,
      detail: u.detail,
    })
  }

  for (const nm of notMeasurable) {
    failures.push({
      kind: 'not-measurable',
      stateId: nm.stateId,
      bucket: `not-measurable:${nm.reason}`,
      file: nm.file,
      reason: nm.reason,
      detail: nm.detail,
    })
  }

  if (classified.length === 0) {
    failures.push({
      kind: 'no-classifications',
      stateId: null,
      bucket: 'no-classifications',
      file: null,
      detail:
        'classified is empty — the gate cannot pass vacuously. Either no state story was ' +
        'discovered at all (a discovery defect) or every measurable pair failed to produce a ' +
        'classification.',
    })
  } else if (classified.length !== measurableCount) {
    failures.push({
      kind: 'measurable-count-mismatch',
      stateId: null,
      bucket: 'measurable-count-mismatch',
      file: null,
      detail:
        `${measurableCount} measurable pair(s) were planned but ${classified.length} were ` +
        'classified — a measurable pair that produced no classification (e.g. a Playwright test ' +
        'that crashed), or a classification no planned pair accounts for, must fail, not be ' +
        'silently dropped.',
    })
  }

  if (measurableIds) {
    const classifiedIds = new Set(classified.map((c) => c.stateId))
    const measurableIdSet = new Set(measurableIds)
    const missing = measurableIds.filter((id) => !classifiedIds.has(id))
    const unexpected = [...classifiedIds].filter((id) => !measurableIdSet.has(id))
    if (missing.length > 0 || unexpected.length > 0) {
      failures.push({
        kind: 'measurable-id-mismatch',
        stateId: null,
        bucket: 'measurable-id-mismatch',
        file: null,
        detail:
          `classified's own story ids do not match the ids planned as measurable (the two lists ` +
          `may or may not be the same length) — missing (planned, never classified): ` +
          `${missing.length > 0 ? missing.join(', ') : '(none)'}; unexpected (classified, never ` +
          `planned as measurable): ${unexpected.length > 0 ? unexpected.join(', ') : '(none)'}.`,
      })
    }
  }

  for (const c of classified) {
    if (SWEEP_GATE_FAILING_BUCKETS.has(c.bucket)) {
      failures.push({ kind: 'classification', ...c })
    }
  }

  return { pass: failures.length === 0, failures }
}

// T675 remediation (M1): the pure per-file decision `run.mjs`'s own file-scan loop needs —
// extracted here so it is unit-testable without the filesystem/browser discipline this module
// already holds everywhere else (see this file's own header comment). Takes a file path and its
// already-read source (the caller's job, per that same discipline) and returns either:
//   - `{ unkeyable: { file, detail } }` when `extractFileStoryStates` cannot key the file at all (a
//     component meta with no literal `id`, a componentless page with no literal `title`, or no
//     meta object found) — this used to be swallowed by a `try`/`catch`/`continue` in `run.mjs` with
//     nothing but a log line to show for it; now it is a value the caller collects and the gate
//     above can fail on, named.
//   - `{ measurable: [...], notMeasurable: [...] }` otherwise — the same two lists
//     `buildStateSignalWork` (`run.mjs`) used to build inline.
export function buildStoryFileWork(filePath, source) {
  let result
  try {
    result = extractFileStoryStates(filePath, source)
  } catch (err) {
    return { unkeyable: { file: path.relative(rootDir, filePath), detail: err.message } }
  }
  const measurable = []
  const notMeasurable = []
  // T679: every exported story id the parse saw, state or not — `reconcileFile` compares this
  // against the ids the built Storybook index lists for the same file.
  const storyIds = result ? result.stories.map((story) => story.id) : []
  if (result) {
    const relFile = path.relative(rootDir, filePath)
    for (const story of result.stories) {
      if (!story.isStateStory) continue
      const plan = planSelfRest(story)
      if (plan.measurable) {
        measurable.push({
          stateId: story.id,
          exportName: story.exportName,
          mode: plan.mode,
          hasClip: story.clip !== null,
          file: relFile,
        })
      } else {
        notMeasurable.push({
          stateId: story.id,
          exportName: story.exportName,
          file: relFile,
          reason: plan.reason,
          detail: plan.detail,
        })
      }
    }
  }
  return { measurable, notMeasurable, storyIds }
}

// --- Discovery ---------------------------------------------------------------------------------

// T679: discovery used to be a filesystem walk (`findStoryFile`, the first `*.stories.tsx` per
// directory under three tiers), so a second story file in one directory, or a state story outside
// those tiers (`.storybook/foundations/`), was never swept and never reported — "no allowlist" held
// only for what the walk reached. The source of truth is now the built Storybook index, the same
// file `scripts/checks/story-baselines.mjs` reads: every story file it lists is parsed, and the gate
// fails (`decideSweepGate`, `discoveryGaps`) on any of these disagreements, each named:
//   - an indexed story the parse of its file never produced (`reconcileFile`) — the index carries no
//     notion of a *state* story (that is a source-level fact), so a story the parse missed could be
//     one;
//   - a state story the parse found that the index does not list (`reconcileFile`) — only state
//     stories are checked in this direction, not every parsed story;
//   - an indexed file that cannot be read;
//   - a story file on disk (`listStoryFilesOnDisk`) that the index lists no story for
//     (`findUnindexedStoryFiles`) — what a build that predates a story file looks like. A build that
//     changed a story's args or parameters under the same ids is not detectable this way.

// Stories (not `docs` entries) of a parsed `index.json`, as `{ id, file }` with `file` relative to
// the design-system package, the shape `entry.importPath` has once its leading `./` is removed.
export function indexedStories(index) {
  return Object.values(index?.entries ?? index?.stories ?? {})
    .filter((entry) => entry.type === undefined || entry.type === 'story')
    .map((entry) => ({ id: entry.id, file: (entry.importPath ?? '').replace(/^\.\//, '') }))
}

// Index story ids grouped by the story file that declares them, files in a stable order.
export function groupIndexByFile(index) {
  const byFile = new Map()
  for (const { id, file } of indexedStories(index)) {
    if (!byFile.has(file)) byFile.set(file, [])
    byFile.get(file).push(id)
  }
  return new Map([...byFile.entries()].sort(([a], [b]) => a.localeCompare(b)))
}

// Pure reconciliation of one story file's index entry against its parse. `parsed` is
// `buildStoryFileWork`'s own result for that file. Returns the gaps (possibly none), each
// `{ kind, file, stateId?, detail }`:
//   - `'indexed-story-not-parsed'`: the index lists a story id the source parse never produced — the
//     parse cannot say whether it is a state story, so it is a failure rather than a guess.
//   - `'state-story-not-indexed'`: the parse found a state story the index does not list for this
//     file — a stale build, or a story Storybook excludes; either way the sweep cannot render it.
export function reconcileFile({ file, indexedIds, parsed }) {
  const gaps = []
  const parsedIds = new Set(parsed.storyIds)
  const indexedSet = new Set(indexedIds)
  for (const id of indexedIds) {
    if (!parsedIds.has(id)) {
      gaps.push({
        kind: 'indexed-story-not-parsed',
        file,
        stateId: id,
        detail:
          `${id} is listed by the built Storybook index for ${file}, but the source parse of that ` +
          'file produced no story with this id — whether it is a state story cannot be decided, ' +
          'so it is not swept.',
      })
    }
  }
  for (const item of [...parsed.measurable, ...parsed.notMeasurable]) {
    if (!indexedSet.has(item.stateId)) {
      gaps.push({
        kind: 'state-story-not-indexed',
        file,
        stateId: item.stateId,
        detail:
          `${item.stateId} is a state story in ${file}, but the built Storybook index does not ` +
          'list it — the index is stale (rebuild Storybook) or the story is excluded from it.',
      })
    }
  }
  return gaps
}

// Story files on disk (`stories` globs of `.storybook/main.ts`) that the index lists no story for.
// This is what catches a stale build that predates a whole new story file, which enumerating the
// index alone cannot see.
export function findUnindexedStoryFiles({ indexedFiles, diskFiles }) {
  const indexed = new Set(indexedFiles)
  return [...diskFiles]
    .filter((file) => !indexed.has(file))
    .sort()
    .map((file) => ({
      kind: 'story-file-not-indexed',
      file,
      stateId: null,
      detail:
        `${file} is a story file on disk but the built Storybook index lists no story for it — ` +
        'the index is stale (rebuild Storybook), or the file is outside the `stories` globs of ' +
        '.storybook/main.ts and is never rendered.',
    }))
}

// The whole pure pipeline: index in, work and gaps out. `readSource(absolutePath)` is the caller's
// (filesystem) job, injected so this stays filesystem-free like every function above it;
// `diskFiles` is the caller's listing of story files on disk, relative to the package.
export function buildStateSignalWork({ index, readSource, diskFiles = null, baseDir = dsDir }) {
  const measurable = []
  const notMeasurable = []
  const unkeyableFiles = []
  const discoveryGaps = []
  const byFile = groupIndexByFile(index)
  for (const [file, indexedIds] of byFile) {
    const filePath = path.join(baseDir, file)
    let source
    try {
      source = readSource(filePath)
    } catch (err) {
      discoveryGaps.push({
        kind: 'unreadable-story-file',
        file,
        stateId: null,
        detail: `${file} is listed by the built Storybook index but cannot be read: ${err.message}`,
      })
      continue
    }
    const work = buildStoryFileWork(filePath, source)
    if (work.unkeyable) {
      unkeyableFiles.push(work.unkeyable)
      continue
    }
    measurable.push(...work.measurable)
    notMeasurable.push(...work.notMeasurable)
    discoveryGaps.push(...reconcileFile({ file, indexedIds, parsed: work }))
  }
  if (diskFiles) {
    discoveryGaps.push(...findUnindexedStoryFiles({ indexedFiles: byFile.keys(), diskFiles }))
  }
  return {
    measurable,
    notMeasurable,
    unkeyableFiles,
    discoveryGaps,
    filesDiscovered: byFile.size,
    indexedStoryCount: [...byFile.values()].reduce((n, ids) => n + ids.length, 0),
  }
}

// The directories `.storybook/main.ts`'s `stories` globs start from, relative to the package
// (`../src/**/*.stories.@(ts|tsx)` and `./foundations/**/*.stories.@(ts|tsx)`). A second copy of
// those globs' base directories, so `state-signal-model.test.mjs` reads the real `stories` array and
// fails when it and this list stop agreeing.
export const STORY_WALK_ROOTS = ['src', '.storybook/foundations']

// Every `*.stories.ts(x)` file under `STORY_WALK_ROOTS`, as paths relative to the package. The one
// filesystem-touching function in this module, kept next to the pure ones it feeds
// (`findUnindexedStoryFiles`) and called by `run.mjs` alone. Below a root it skips `node_modules` and
// dot-entries, as a `**` glob with picomatch's default `dot: false` does; a root that is itself a
// dot-directory (`.storybook/foundations`) is walked, being named explicitly.
export function listStoryFilesOnDisk(baseDir = dsDir) {
  const files = []
  const walk = (relDir) => {
    let entries
    try {
      entries = readdirSync(path.join(baseDir, relDir), { withFileTypes: true })
    } catch {
      return
    }
    for (const entry of entries) {
      if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue
      const rel = path.posix.join(relDir, entry.name)
      if (entry.isDirectory()) walk(rel)
      else if (/\.stories\.tsx?$/.test(entry.name)) files.push(rel)
    }
  }
  for (const root of STORY_WALK_ROOTS) walk(root)
  return files.sort()
}

// A parsed `index.json` the sweep can work from: an object with at least one story. The sweep's
// work list is built from this alone, so an unparseable text, a shape without entries, or an index
// with no story is a failure (`run.mjs` exits 1 on the throw), never an empty sweep.
export function parseSweepIndex(text) {
  let index
  try {
    index = JSON.parse(text)
  } catch (err) {
    throw new Error(`index.json is not valid JSON (${err.message})`)
  }
  if (indexedStories(index).length === 0) {
    throw new Error('index.json lists no story (no "entries"/"stories" object with a story in it)')
  }
  return index
}
