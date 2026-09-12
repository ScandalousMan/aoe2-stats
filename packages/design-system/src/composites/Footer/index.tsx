import { cx } from '../../lib/cx'

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

// T560 (FR-038): the same inline-link classes `ThirdPartyObjectionForm`, `AccountErasurePanel` and
// `PrivacyNotice` already give every inline link in the product — footer.md §5 already documents a
// focus ring and a `duration.fast`/`easing.standard` transition for these two links, and neither
// was actually built. Same category, same behaviour.
// T589: `outline-offset-ring` (`border.json`'s `ring-offset`, 2px) names the offset this ring
// shipped as a bare `outline-offset-2` literal — same rendered offset, now a named token.
const focusRing =
  'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring'

// Fourth-pass review remediation (FR-037): hover and active shared `link-hover` with no other
// signal, so a press was not distinguishable from a hover in a still image.
// `active:underline-offset-4` gives press its own frame without a fill (this is an inline link
// inside the disclaimer's own text flow — the same reasoning `Link`'s `inline` variant states for
// withholding a fill, `Link/index.tsx`) — the identical fix now shared with `Link`, `PrivacyNotice`,
// `ThirdPartyObjectionForm` and `AccountErasurePanel`'s own copies of this pattern.
const linkClasses = cx(
  'py-2 font-sans text-sm text-link underline transition-colors duration-120 ease-standard motion-reduce:duration-0',
  'hover:text-link-hover active:text-link-hover active:underline-offset-4',
  focusRing,
)

/** The Microsoft Game Content Usage Rules disclaimer (constitution X), mounted in the web shell by
 * T098a so it renders on every route. §5: this component has effectively one state — the
 * disclaimer and the affiliation note are never conditional; `LinkRow`'s two entries render
 * independently, only when their own href prop is supplied. */
export function Footer({ privacyNoticeHref, objectionHref, className }: FooterProps) {
  const hasLinks = Boolean(privacyNoticeHref || objectionHref)

  return (
    <footer className={cx('border-t border-border bg-background px-4 py-6 md:px-6', className)}>
      <p className="font-sans text-sm text-text-secondary">{disclaimer}</p>
      <p className="mt-2 font-sans text-sm text-text-secondary">{affiliationNote}</p>
      {hasLinks && (
        <div className="mt-4 flex flex-col gap-4 md:flex-row">
          {privacyNoticeHref && (
            <a href={privacyNoticeHref} className={linkClasses}>
              Read the privacy notice
            </a>
          )}
          {objectionHref && (
            <a href={objectionHref} className={linkClasses}>
              Object to what is held about me
            </a>
          )}
        </div>
      )}
    </footer>
  )
}
