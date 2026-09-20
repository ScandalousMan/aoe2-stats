import type { Meta, StoryObj } from '@storybook/react-vite'
import { PrivacyNotice } from './index'

const meta: Meta<typeof PrivacyNotice> = {
  id: 'screens-privacynotice',
  title: 'Screens/Account & privacy/PrivacyNotice',
  component: PrivacyNotice,
  parameters: {
    docs: {
      description: {
        component: `Tells a person everything this service holds about them, where it came from, on what legal basis, for how long, and the exact control that stops, exports or erases it.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof PrivacyNotice>

const hrefs = {
  archivalControl: '/dashboard',
  privacyRoute: '/privacy',
  objectionForm: '/object',
}

// privacy-notice.md §5 "empty" is answered by this story: no `controllerContact` (renders
// `ContactUnpublished`) and no `changeNote` (renders nothing, per `Callout`'s own empty rule) —
// both of `PrivacyNotice`'s own empty cases, at once, rather than a state this component invents.
export const Default: Story = {
  name: 'default — no contact published yet, showsAnalysisRetention true',
  args: { lastUpdated: '2026-08-30', hrefs },
}

export const WithAnalysisRetentionHidden: Story = {
  name: 'showsAnalysisRetention false — the analysis category entry is absent, and no other',
  args: { lastUpdated: '2026-08-30', hrefs, showsAnalysisRetention: false },
}

export const WithPublishedContact: Story = {
  name: 'with a published controller contact',
  args: {
    lastUpdated: '2026-08-30',
    hrefs,
    controllerContact: {
      name: 'aoe2-stats',
      postalAddress: '1 Example Street, Paris, France',
      contactRoute: '/contact',
    },
  },
}

export const WithChangeNote: Story = {
  name: 'with a change note since the previous version',
  args: {
    lastUpdated: '2026-08-30',
    hrefs,
    changeNote: {
      heading: 'What changed',
      body: 'We added the third-party objection form and the export and erasure controls.',
      date: '30 August 2026',
    },
  },
}

export const WithProcessingRegisterLink: Story = {
  name: 'with a link to the public processing register',
  args: {
    lastUpdated: '2026-08-30',
    hrefs: { ...hrefs, processingRegister: '/docs/privacy/processing-register' },
  },
}

// T096 defect 1 (visual review): §4.4's ProcessorList and OutwardCallList are `<table>`s that
// overflowed the 375 viewport because no story ever captured that width — every other story here
// renders at the suite's default desktop viewport, where the bug is invisible. Every story is now
// captured at 375px as a matter of course (T504), so this story needs no tag to reach that width.
// §10's acceptance criterion is "at 375 no horizontal scrollbar… in any section, including both
// tables"; this is the story that can actually catch a regression of it.
// visual-equivalence: screens-privacynotice--default: args are identical
// ({ lastUpdated: '2026-08-30', hrefs }) and every story is captured at 375px as a matter of course
// (T504, per this story's own comment above), so this story adds a Storybook-reader affordance, not
// a captured fact distinct from Default.
export const MobileViewport: Story = {
  name: '375px viewport — §4.4 storage tables stack, no horizontal overflow',
  args: { lastUpdated: '2026-08-30', hrefs },
}

// §5 "hover — inline links and `Contents` entries only... `ObjectionCallToAction` hovers as
// `Button/secondary`. No other part of this component responds to a pointer." Forced from
// Playwright in `tests/visual/stories.spec.ts` (see that file's own `VisualForceState` comment) —
// a `play()` could only dispatch a synthetic event, which the CSS pseudo-class ignores. `nth: 0`
// picks the first link the same way `getAllByRole(...)[0]` used to.
// T591: this group clips to the first link — the hover/focus/active signal on one inline link is
// a small mark on the whole document's frame, invisible to the duplicate check at that scale
// (story-baseline-duplicates-debt.json).
const FIRST_LINK_CLIP = { parts: [{ role: 'link', nth: 0 }], pad: '2' } as const

export const Hover: Story = {
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'hover', role: 'link', nth: 0 },
    visualCaptureClip: FIRST_LINK_CLIP,
  },
}

// §5 "focus-visible — the standard ring... on every link and on the objection button."
export const FocusVisible: Story = {
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'link', nth: 0 },
    visualCaptureClip: FIRST_LINK_CLIP,
  },
}

// §5 "active — links render in `link-hover` while pressed... Nothing translates or scales."
export const Active: Story = {
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'active', role: 'link', nth: 0 },
    visualCaptureClip: FIRST_LINK_CLIP,
  },
}

// README's gap register row 8 (H5), F10: `Hover`/`FocusVisible`/`Active` above all clip and force
// `nth: 0`, which — confirmed by `state-coverage.mjs`'s own extractor — resolves to the first
// `Contents` entry, not to `InlineLink` (`index.tsx:242`, the recipe every `RightsItem` control
// uses). §5's own "hover — inline links and `Contents` entries only" names both, so this component
// owes `InlineLink` its own frame, distinct from the nav item above. `nth: 9` is this render's real
// DOM position under the default `hrefs` (no `controllerContact`, no `processingRegister`): the
// nine `Contents` entries occupy positions 0-8, and `InlineLink`'s own earliest call site in this
// file — "Object to archival" (§6's first `RightsItem`) — is the tenth link rendered, matching
// `getAllByRole('link')[9]` the same way `nth: 0` above matches `getAllByRole('link')[0]` — verified
// against the real DOM, which is what the Playwright capture actually drives.
//
// `state-coverage.mjs` credits this trio directly: its candidate pool used to hold one
// declaration-site slot per JSX occurrence in source regardless of how many real instances a
// `.map()` renders — `Contents` alone collapsed nine real elements into one slot, so no `nth` past
// the pool's own small size could ever be placed. Fixed at its root, not worked around here: a
// `.map()`/`.flatMap()` candidate's own real width is now resolved from its backing array (`
// SECTIONS_TOC.length`, evaluated once into every story's own scope) and a helper's own real width
// from the count of its own call sites this story's scope confirms reached — `InlineLink`'s four,
// under these default `hrefs` — both contributing their real slot count to the ordering instead of
// one apiece. The one side effect worth naming: the contact-route anchor
// (`index.tsx:797`, T596's own subject, not this task's) shares this component's `link` pool, and
// this fix correctly rules it out of `nth: 9`'s own range (a clean `reject`, not `ambiguous`) — and,
// as of T599, its own cells now read `none`, not `unresolved`. `ObjectionCallToAction`'s own
// `selector` match (below) used to attempt this anchor's `href` without ever checking whether it
// renders at all; `resolveSelectorMatch`'s own caller now excludes a candidate this story's scope
// confirms `'unreached'` before attempting it — and the cell's own reason names
// `ObjectionCallToActionHover`/`FocusVisible`/`Active` below, whose own args are
// `{ lastUpdated, hrefs }`, no `controllerContact`. `buildStoryPropsScope`
// (`scripts/checks/state-coverage.mjs`) used to seed a component prop with no destructuring default
// as unknown whenever the story it is evaluating for did not name it in `args`, rather than as the
// `undefined` it actually is at render; T599 fixed that package-wide, so evaluated against those
// stories' own scope, `controllerContact` now resolves to its real value there, `undefined`, and
// this anchor's guard, `controllerContact ? <a…> : …`, is `'unreached'`, not `'unresolved'`.
// `WithPublishedContact` above does set `controllerContact` and genuinely renders this anchor (with
// `href="/contact"`), but it forces no state at all, so it never enters this comparison either way
// — the gap was never "no story sets `controllerContact`," it was that the one story that does
// carries no `visualForceState`, and the three that do carry one never set it.
const INLINE_LINK_CLIP = { parts: [{ role: 'link', nth: 9 }], pad: '2' } as const

export const InlineLinkHover: Story = {
  name: 'hover on the InlineLink recipe ("Object to archival")',
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'hover', role: 'link', nth: 9 },
    visualCaptureClip: INLINE_LINK_CLIP,
  },
}

export const InlineLinkFocusVisible: Story = {
  name: 'focus-visible on the InlineLink recipe ("Object to archival")',
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'link', nth: 9 },
    visualCaptureClip: INLINE_LINK_CLIP,
  },
}

export const InlineLinkActive: Story = {
  name: 'active (pressed) on the InlineLink recipe ("Object to archival")',
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'active', role: 'link', nth: 9 },
    visualCaptureClip: INLINE_LINK_CLIP,
  },
}

// README's gap register row 8 (H5), F10: `ObjectionCallToAction` (`index.tsx:740`, §2's own name
// for the anchor in section 7, "If you are not a user of this service") painted zero coverage on
// every state before this trio — a rendering defect it does not have (it carries real
// `hover:`/`focus-visible:`/`active:` classes, §5's own "`ObjectionCallToAction` hovers as
// `Button/secondary`"), only a missing frame. Targeted by `selector` rather than `role`+`nth`: this
// anchor's own `href={hrefs.objectionForm}` is a literal in this story's own `args`
// (`hrefs.objectionForm`, `'/object'`, defined once above), unique in the whole render, so
// `a[href="/object"]` names it directly and unambiguously, with no positional reasoning needed at
// all — `nth: 13` would work too now that `InlineLinkHover`'s own fix gives `state-coverage.mjs`'s
// candidate pool each group's real width, but a selector keyed to this anchor's own unique `href`
// is simpler and does not depend on how many links render before it. It has its own residual
// boundary, worth naming rather than hiding behind the choice: `resolveSelectorMatch`'s own caller
// now excludes a candidate this story's scope confirms `'unreached'` before ever attempting its own
// attribute, the same guard-fold `InlineLinkHover`'s own fix uses for `nth` — and the contact-route
// anchor (`index.tsx:797`, T596's own subject) renders behind `controllerContact ? <a…> : …`. This
// trio's own args (below) never set `controllerContact`, but as of T599's package-wide
// `buildStoryPropsScope` fix, evaluated against *this* trio's own scope, `controllerContact`
// resolves to its real value there — `undefined`, since Storybook's own `args` are the complete
// prop set and a key absent from it is genuinely `undefined`, not unknown — so its guard is
// `'unreached'` (confirmed false), not `'unresolved'` (genuinely unknown) as it used to read.
// `WithPublishedContact` above does set `controllerContact` and genuinely renders this anchor, but
// carries no `visualForceState`, so it never enters this trio's own comparison either way.
// The selector string is inlined directly in every `visualForceState` below, never read from a
// shared identifier — `state-coverage.mjs`'s own `extractVisualForceState` resolves a
// `visualForceState` field only when it is a literal AST node at that exact position
// (`literalOf`), the same convention `MatchRow`/`FavouritesList`/`PlayerResultRow`'s own row-link
// selectors already follow. `visualCaptureClip` carries no such restriction (the extractor never
// reads it at all), so the clip constant below may and does reuse the same string once.
const OBJECTION_CALL_TO_ACTION_CLIP = {
  parts: [{ selector: 'a[href="/object"]' }],
  pad: '2',
} as const

export const ObjectionCallToActionHover: Story = {
  name: 'hover on ObjectionCallToAction ("Object to what is held about me")',
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'hover', selector: 'a[href="/object"]' },
    visualCaptureClip: OBJECTION_CALL_TO_ACTION_CLIP,
  },
}

export const ObjectionCallToActionFocusVisible: Story = {
  name: 'focus-visible on ObjectionCallToAction ("Object to what is held about me")',
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'focus-visible', selector: 'a[href="/object"]' },
    visualCaptureClip: OBJECTION_CALL_TO_ACTION_CLIP,
  },
}

export const ObjectionCallToActionActive: Story = {
  name: 'active (pressed) on ObjectionCallToAction ("Object to what is held about me")',
  args: { lastUpdated: '2026-08-30', hrefs },
  parameters: {
    visualForceState: { state: 'active', selector: 'a[href="/object"]' },
    visualCaptureClip: OBJECTION_CALL_TO_ACTION_CLIP,
  },
}

// §5 "disabled — nothing in this component is ever disabled. A right that is described and then
// greyed out has been withdrawn without saying so."
export const DisabledNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Nothing in this component is ever disabled — a right that is described and then greyed out
        has been withdrawn without saying so. A failure belongs to the route a link leads to, never
        to the sentence stating the right.
      </p>
      <PrivacyNotice {...args} />
    </div>
  ),
  args: { lastUpdated: '2026-08-30', hrefs },
}

// §5 "loading — none, and this is a requirement. The component takes no data-fetching prop,
// renders no `Skeleton`, and must be fully readable at first paint."
export const LoadingNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      This component takes no data-fetching prop and renders no `Skeleton` — it must be fully
      readable at first paint, before any network call could resolve. Every story on this page is
      already that first paint.
    </p>
  ),
}

// §5 "error — none of its own; there is nothing here that can fail... This component keeps
// stating what the rights are while either of those is broken, which is correct."
export const ErrorNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        This component carries no error state of its own — an export or erasure that fails renders
        its error on the privacy route, and a failed objection renders on the objection form. This
        component keeps stating the rights regardless.
      </p>
      <PrivacyNotice {...args} />
    </div>
  ),
  args: { lastUpdated: '2026-08-30', hrefs },
}
