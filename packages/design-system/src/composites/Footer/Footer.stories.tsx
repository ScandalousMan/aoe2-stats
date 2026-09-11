import type { Meta, StoryObj } from '@storybook/react-vite'
import { Footer } from './index'

const meta: Meta<typeof Footer> = {
  id: 'composite-footer',
  title: 'Composites/Site chrome/Footer',
  component: Footer,
  parameters: {
    docs: {
      description: {
        component: `Carries, on every page, the required Game Content Usage Rules attribution and the two ways a person not signed in can reach their own rights over their data.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof Footer>

// footer.md §5's states: the disclaimer and affiliation note never change; only LinkRow's
// membership does, driven entirely by which href props are supplied.

export const NoLinks: Story = {
  name: 'no links — disclaimer only, the state before T098a wires any route',
  args: {},
}

export const BothLinks: Story = {
  name: 'both links — privacy notice and the third-party objection form',
  args: { privacyNoticeHref: '/privacy-notice', objectionHref: '/object' },
}

export const PrivacyNoticeOnly: Story = {
  name: 'privacy notice link only',
  args: { privacyNoticeHref: '/privacy-notice' },
}

export const ObjectionOnly: Story = {
  name: 'objection link only',
  args: { objectionHref: '/object' },
}

// §5 "hover — `PrivacyNoticeLink` and `ObjectionLink` only... Nothing else in this component
// responds to a pointer." Forced from Playwright in `tests/visual/stories.spec.ts` (see that
// file's own `VisualForceState` comment) — a `play()` could only dispatch a synthetic event, which
// the CSS pseudo-class ignores. `nth: 0` picks the first link the same way `getAllByRole(...)[0]`
// used to.
export const Hover: Story = {
  args: { privacyNoticeHref: '/privacy-notice', objectionHref: '/object' },
  parameters: { visualForceState: { state: 'hover', role: 'link', nth: 0 } },
}

// §5 "focus-visible — the standard ring... on each link that is present. The disclaimer and the
// affiliation note are not focusable."
export const FocusVisible: Story = {
  args: { privacyNoticeHref: '/privacy-notice', objectionHref: '/object' },
  parameters: { visualForceState: { state: 'focus-visible', role: 'link', nth: 0 } },
}

// §5 "active — links render `link-hover` while pressed... Nothing translates or scales."
export const Active: Story = {
  args: { privacyNoticeHref: '/privacy-notice', objectionHref: '/object' },
  parameters: { visualForceState: { state: 'active', role: 'link', nth: 0 } },
}

// §5 "disabled — not applicable... loading — none... error — none of its own." Grouped as one
// story: all three share the same reasoning (a build-time-constant component with no network
// dependency and no dimmed middle state for a link).
export const DisabledLoadingErrorNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        Every string here is a build-time constant: no loading phase, no error state, and no
        disabled middle state for a link — a link is either rendered or omitted.
      </p>
      <Footer {...args} />
    </div>
  ),
  args: { privacyNoticeHref: '/privacy-notice', objectionHref: '/object' },
}
