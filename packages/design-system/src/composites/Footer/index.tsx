import { cx } from '../../lib/cx'
import { Link } from '../../primitives/Link'

// packages/design-system/specs/footer.md

export interface FooterProps {
  /** Renders "Read the privacy notice", linking here. Omitted entirely when absent. */
  privacyNoticeHref?: string
  /** Renders "Object to what is held about me", linking here. Omitted entirely when absent. */
  objectionHref?: string
  className?: string
}

// §4 — normative, copied verbatim from README.md's "Non-commercial" section. A change here
// happens in the same PR as the matching change to README.md, never alone. `Footer.test.tsx`
// asserts the two stay identical.
export const disclaimer =
  'aoe2-stats was created under Microsoft\'s "Game Content Usage Rules" using assets from Age of Empires II: Definitive Edition, (c) Microsoft Corporation.'

export const affiliationNote =
  "This project is not affiliated with or endorsed by Microsoft or World's Edge."

/** The Microsoft Game Content Usage Rules disclaimer (constitution X), mounted in the web shell by
 * T098a so it renders on every route. §5: this component has effectively one state — the
 * disclaimer and the affiliation note are never conditional; `LinkRow`'s two entries render
 * independently, only when their own href prop is supplied.
 *
 * T591: these two links used to be a hand-rolled `<a>` pair carrying their own copy of `Link`
 * `standalone`'s ink/underline/focus-ring/active recipe (`linkClasses`/`focusRing`, T560's own
 * remediation of the gap) — a plain `active:underline-offset-4` colour-adjacent signal that turned
 * out too weak for the duplicate check to tell apart from hover at this row's size
 * (story-baseline-duplicates-debt.json). Rendering the primitive directly instead of copying its
 * recipe gets the fix (`standalone`'s own `active:bg-surface-sunken active:ring-2
 * active:ring-border-strong`, T583) with no second copy to drift out of sync again. */
export function Footer({ privacyNoticeHref, objectionHref, className }: FooterProps) {
  const hasLinks = Boolean(privacyNoticeHref || objectionHref)

  return (
    <footer className={cx('border-t border-border bg-background px-4 py-6 md:px-6', className)}>
      <p className="font-sans text-sm text-text-secondary">{disclaimer}</p>
      <p className="mt-2 font-sans text-sm text-text-secondary">{affiliationNote}</p>
      {hasLinks && (
        <div className="mt-4 flex flex-col gap-4 md:flex-row">
          {privacyNoticeHref && (
            <Link href={privacyNoticeHref} variant="standalone">
              Read the privacy notice
            </Link>
          )}
          {objectionHref && (
            <Link href={objectionHref} variant="standalone">
              Object to what is held about me
            </Link>
          )}
        </div>
      )}
    </footer>
  )
}
