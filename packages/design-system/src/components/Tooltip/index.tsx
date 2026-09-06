import type { FocusEvent, KeyboardEvent, ReactNode } from 'react'
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { iconTokens, spaceTokens } from '../../../tokens/generated/tokens'
import { cx } from '../../lib/cx'

// packages/design-system/specs/tooltip.md

export type TooltipRelation = 'label' | 'describe'
export type TooltipPlacement = 'block-start' | 'block-end'

export interface TooltipProps {
  /** Exactly one child (§2 anatomy) — this component wraps it in the real `<button
   * type="button">` that becomes the trigger. The child itself is never made focusable or given
   * ARIA of its own; only the wrapping button is a tab stop. */
  children: ReactNode
  /** The tooltip's visible text. `null`, `undefined`, or blank after trimming renders the
   * trigger's child alone, unwrapped — no button, no tab stop, no `role="tooltip"` element (§4
   * empty). The test is emptiness, not nullishness. */
  content?: string | null
  /** Visually hidden text prepended to the trigger's accessible name/description, naming what
   * `content` is a value OF ("Country: "), so the accessible name reads "Country: France" and not
   * the bare "France, button" (§8). */
  qualifier?: string
  /** `"label"` (default) — `content` **is** the trigger's accessible name (`aria-labelledby`).
   * `"describe"` — `content` **adds to** an existing visible label (`aria-describedby`). A
   * trigger that already shows its label as text takes `"describe"`; `"label"` there replaces
   * what a sighted user sees with what they cannot, and fails WCAG 2.5.3 (§3). */
  relation?: TooltipRelation
  /** The preferred side; flips to the other when the preferred side would overflow the viewport
   * (§3a). There is no third position and no inline-axis placement. */
  placement?: TooltipPlacement
  className?: string
}

// Interaction timing, not a design token (same category as `SearchBox`'s `debounceMs` and
// `useDelayedVisible`'s `DELAY_MS`): mirrors `motion.duration.normal` / `motion.duration.fast`
// (tokens/motion.json) so a pointer crossing the trigger on its way elsewhere does not strobe the
// surface open and shut (tooltip.md §4 hover).
const HOVER_OPEN_DELAY_MS = 200 // motion.duration.normal
const HOVER_CLOSE_GRACE_MS = 120 // motion.duration.fast — the grace that makes the space-2 gap
// between the trigger and the hoverable surface crossable (§4 hover).

function isBlank(content?: string | null): content is undefined | null | '' {
  return content == null || content.trim() === ''
}

// §3a/§10: the surface must stay at least `space-4` clear of both viewport edges. `space-4`
// (tokens/space.json) is authored in `rem`, and `getComputedStyle` returns a custom property
// verbatim — the platform never resolves it to a pixel number the way it resolves a length
// *property* such as `width` (unlike a value read off `iconTokens.xl`, which is only ever handed
// back to CSS, never compared against a `getBoundingClientRect` number in JS). So the token is
// resolved by letting the browser do exactly that: a throwaway, unpainted element takes the token
// as its own `width`, and its measured box is the token in px at the current root font size —
// correct at 200% zoom (§7) and if the token were ever re-authored in a different unit, with no
// px/rem literal of our own anywhere in this file.
function resolveTokenPx(cssValue: string): number {
  const probe = document.createElement('div')
  probe.style.position = 'absolute'
  probe.style.visibility = 'hidden'
  probe.style.width = cssValue
  document.body.appendChild(probe)
  const px = probe.getBoundingClientRect().width
  document.body.removeChild(probe)
  return px
}

// `:focus-visible` is the browser's own keyboard-vs-pointer heuristic, resolved synchronously the
// moment focus lands — checking it in `onFocus` does not depend on the `keydown`/`pointerdown`
// listeners below ever having committed first, unlike `keyboardModalityRef`, which is only
// trustworthy once its `useEffect` has run. A story's `play` step can call `userEvent.tab()`
// before that commit lands (this is what made `KeyboardFocusRevealed` flaky), but a real focus
// event's own `:focus-visible` state is never subject to that race.
// jsdom implements the selector but not the actual heuristic — it resolves `:focus-visible`
// identically to `:focus` (always true while focused, mouse click included), which is why it is
// unusable as a signal there; this environment falls back to the ref instead of trusting a value
// the environment cannot actually produce.
const FOCUS_VISIBLE_UNRELIABLE =
  typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)

/** A trigger and its content (§2). No portal: the content renders as a positioned sibling of the
 * trigger, inside the caller's own DOM (§2 rule 3). The content is always in the DOM and carries
 * the `hidden` attribute while closed, so its accessible name/description resolves without the
 * tooltip ever being opened (§8) — the defect a mount-on-open implementation ships with. */
export function Tooltip({
  children,
  content,
  qualifier,
  relation = 'label',
  placement = 'block-start',
  className,
}: TooltipProps) {
  const contentId = useId()
  const triggerRef = useRef<HTMLButtonElement>(null)
  const surfaceRef = useRef<HTMLSpanElement>(null)

  const [hoverOpen, setHoverOpen] = useState(false)
  const [focusOpen, setFocusOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  // Escape dismisses while leaving focus on the trigger, and stays dismissed until focus leaves
  // and returns, or the pointer re-enters (§8) — this flag is that "stays dismissed" memory.
  const [dismissed, setDismissed] = useState(false)
  const [resolvedPlacement, setResolvedPlacement] = useState<TooltipPlacement>(placement)
  // §3a/§10: the extra horizontal translate that keeps the surface >= `space-4` from both
  // viewport edges. Zero means "centred on the trigger, no correction needed" — the common case.
  const [inlineOffsetPx, setInlineOffsetPx] = useState(0)

  const openTimerRef = useRef<number | undefined>(undefined)
  const closeTimerRef = useRef<number | undefined>(undefined)
  // Counts the trigger and the surface together: the surface is itself hoverable (§4 hover), so
  // the close timer only starts once the pointer has left both.
  const pointerRegionRef = useRef(0)
  // The standard `:focus-visible` polyfill technique: a mouse-down that ends in focus must never
  // open the surface (§4 focus-visible — "a mouse-down does not"); only Tab, `autofocus`
  // restoration or a programmatic `focus()` should.
  const keyboardModalityRef = useRef(false)

  const blank = isBlank(content)
  const isOpen = !blank && !dismissed && (hoverOpen || focusOpen || pinned)

  useEffect(() => {
    function onKeyDown() {
      keyboardModalityRef.current = true
    }
    function onPointerDown() {
      keyboardModalityRef.current = false
    }
    document.addEventListener('keydown', onKeyDown, true)
    document.addEventListener('pointerdown', onPointerDown, true)
    document.addEventListener('mousedown', onPointerDown, true)
    return () => {
      document.removeEventListener('keydown', onKeyDown, true)
      document.removeEventListener('pointerdown', onPointerDown, true)
      document.removeEventListener('mousedown', onPointerDown, true)
    }
  }, [])

  useEffect(
    () => () => {
      window.clearTimeout(openTimerRef.current)
      window.clearTimeout(closeTimerRef.current)
    },
    [],
  )

  // §3a: preferred side, then the opposite one, measured against the viewport once the surface
  // actually opens. jsdom has no layout engine — every rect reads 0×0 there, so this is a no-op
  // in the unit tests below and is exercised for real only by the Storybook/Playwright visual
  // run, which renders in an actual browser.
  useLayoutEffect(() => {
    if (!isOpen) {
      setResolvedPlacement(placement)
      // Reset to centred: the next open recomputes the correction from a clean, centred
      // baseline (below) rather than compounding on top of whatever the last open settled on.
      setInlineOffsetPx(0)
      return
    }
    const trigger = triggerRef.current
    const surface = surfaceRef.current
    if (!trigger || !surface) return
    const triggerRect = trigger.getBoundingClientRect()
    const surfaceRect = surface.getBoundingClientRect()
    const spaceAbove = triggerRect.top
    const spaceBelow = window.innerHeight - triggerRect.bottom
    if (placement === 'block-start' && spaceAbove < surfaceRect.height && spaceBelow > spaceAbove) {
      setResolvedPlacement('block-end')
    } else if (
      placement === 'block-end' &&
      spaceBelow < surfaceRect.height &&
      spaceAbove > spaceBelow
    ) {
      setResolvedPlacement('block-start')
    } else {
      setResolvedPlacement(placement)
    }

    // §3a/§7/§10: shift along the inline axis so the surface stays >= `space-4` clear of both
    // viewport edges, centred on the trigger otherwise. `surfaceRect` here reflects the pure
    // centred position (the offset was reset to 0 on the close that necessarily preceded this
    // open — see above), so the deficit against each edge is computed once, not accumulated.
    // Shift, never shrink or truncate (§3a): only a translate is applied; `w-max max-w-xs` is
    // untouched.
    const minEdgeGapPx = resolveTokenPx(spaceTokens['4'])
    const leftDeficit = minEdgeGapPx - surfaceRect.left
    const rightDeficit = surfaceRect.right - (window.innerWidth - minEdgeGapPx)
    if (leftDeficit > 0) {
      setInlineOffsetPx(leftDeficit)
    } else if (rightDeficit > 0) {
      setInlineOffsetPx(-rightDeficit)
    } else {
      setInlineOffsetPx(0)
    }
  }, [isOpen, placement])

  function enterHoverRegion() {
    pointerRegionRef.current += 1
    window.clearTimeout(closeTimerRef.current)
    setDismissed(false) // §8: an Escape dismissal ends when the pointer re-enters
    if (hoverOpen) return
    window.clearTimeout(openTimerRef.current)
    openTimerRef.current = window.setTimeout(() => setHoverOpen(true), HOVER_OPEN_DELAY_MS)
  }

  function leaveHoverRegion() {
    pointerRegionRef.current = Math.max(0, pointerRegionRef.current - 1)
    window.clearTimeout(openTimerRef.current)
    if (pointerRegionRef.current > 0) return // still over the trigger or the surface (§4 hover)
    closeTimerRef.current = window.setTimeout(() => setHoverOpen(false), HOVER_CLOSE_GRACE_MS)
  }

  function handleFocus(event: FocusEvent<HTMLButtonElement>) {
    // `:focus-visible`, not `:focus` (§4 focus-visible): only a keyboard-driven focus opens.
    if (FOCUS_VISIBLE_UNRELIABLE) {
      if (keyboardModalityRef.current) setFocusOpen(true)
      return
    }
    let keyboardFocus = keyboardModalityRef.current
    try {
      keyboardFocus = event.currentTarget.matches(':focus-visible')
    } catch {
      // `:focus-visible` unsupported or throws here too — keep the ref-based result.
    }
    if (keyboardFocus) setFocusOpen(true)
  }

  function handleBlur() {
    setFocusOpen(false)
    setDismissed(false) // §8: an Escape dismissal ends when focus leaves and returns
  }

  function handleActivate() {
    // §4 active: a press on an already-pinned tooltip unpins it; a press on one that is only
    // open by hover pins it rather than toggling it shut — the three open sources OR together.
    setPinned((wasPinned) => !wasPinned)
    setDismissed(false)
  }

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape' && isOpen) {
      setDismissed(true)
      setPinned(false)
    }
  }

  // §4 empty: content that is absent or blank after trimming renders the trigger's child alone,
  // unwrapped — no button, no tab stop, no `aria-labelledby`, no `role="tooltip"` element.
  if (blank) return <>{children}</>

  return (
    // `w-fit self-start`: an ancestor `flex flex-col` (or grid) container with the default
    // cross-axis stretch would otherwise blockify this anchor and stretch it to the full row/
    // column width, which moves the `left-1/2 -translate-x-1/2` centring math below off the
    // trigger and onto the stretched anchor instead (§3a/§10 — the surface must stay centred on
    // the trigger, not on whatever box it happens to sit inside). `w-fit` gives the anchor a
    // definite (non-`auto`) cross size, and `self-start` opts it out of `align-items: stretch`
    // directly — either alone defeats the stretch; together they hold for both flex and grid
    // ancestors regardless of their axis, so a flex-row parent (already unaffected, since
    // `items-center` there does not stretch) behaves the same as a flex-column one.
    <span className={cx('relative inline-block w-fit self-start', className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-labelledby={relation === 'label' ? contentId : undefined}
        aria-describedby={relation === 'describe' ? contentId : undefined}
        onMouseEnter={enterHoverRegion}
        onMouseLeave={leaveHoverRegion}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onClick={handleActivate}
        onKeyDown={handleTriggerKeyDown}
        className={cx(
          'inline-flex cursor-default items-center justify-center bg-transparent p-1',
          'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
        )}
        style={{ minWidth: iconTokens.xl, minHeight: iconTokens.xl }}
      >
        {children}
      </button>
      <span
        ref={surfaceRef}
        id={contentId}
        role="tooltip"
        hidden={!isOpen}
        onMouseEnter={enterHoverRegion}
        onMouseLeave={leaveHoverRegion}
        // §3a/§10: the base centring is the `left-1/2 -translate-x-1/2` pair below. Tailwind v4's
        // translate utilities set the CSS `translate` property (not `transform`) — `translate` and
        // `transform` are independent properties that both apply and compose, so an inline
        // `transform` here would add to the class's -50% rather than replace it. Overriding
        // `translate` itself (the same property `-translate-x-1/2` sets) is what lets a plain
        // inline style win outright: offset 0 leaves the class's `-50%` alone (centred, no inline
        // style at all), and a nonzero `inlineOffsetPx` (computed above) fully replaces it with
        // -50% plus the correction, still on the surface's own axis.
        style={
          inlineOffsetPx !== 0 ? { translate: `calc(-50% + ${inlineOffsetPx}px) 0` } : undefined
        }
        className={cx(
          // `w-max` (width: max-content) decouples the surface's own shrink-to-fit width from its
          // containing block — the anchor above, which `w-fit self-start` (§ anchor comment) holds
          // at exactly the trigger's ~44px box. Without it, the browser's shrink-to-fit algorithm
          // resolves "available width" against that 44px anchor instead of the surface's own
          // content, and a long tooltip collapses to a narrow column instead of filling toward
          // `max-w-xs` (320px) before it wraps (§3a placement note, §7 responsive). `max-w-xs`
          // still caps it there; short content (e.g. "France") still sizes to its own text either
          // way. `left-1/2 -translate-x-1/2` centres on the surface's own width, which `w-max`
          // does not change the meaning of.
          'absolute left-1/2 z-10 w-max max-w-xs -translate-x-1/2 rounded-overlay border border-border bg-surface-raised px-2 py-1',
          'font-sans text-sm font-normal text-text-primary opacity-100 shadow-overlay',
          'transition-opacity ease-decelerate motion-reduce:duration-0',
          isOpen ? 'duration-120' : 'duration-0',
          resolvedPlacement === 'block-start' ? 'bottom-full mb-2' : 'top-full mt-2',
        )}
      >
        {qualifier && <span className="sr-only">{qualifier} </span>}
        {content}
      </span>
    </span>
  )
}
