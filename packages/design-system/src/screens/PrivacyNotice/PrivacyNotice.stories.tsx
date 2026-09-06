import type { Meta, StoryObj } from '@storybook/react-vite'
import { userEvent, within } from 'storybook/test'
import { PrivacyNotice } from './index'

const meta: Meta<typeof PrivacyNotice> = {
  id: 'screens-privacynotice',
  title: 'Screens/Account & privacy/PrivacyNotice',
  component: PrivacyNotice,
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
export const MobileViewport: Story = {
  name: '375px viewport — §4.4 storage tables stack, no horizontal overflow',
  args: { lastUpdated: '2026-08-30', hrefs },
}

// §5 "hover — inline links and `Contents` entries only... `ObjectionCallToAction` hovers as
// `Button/secondary`. No other part of this component responds to a pointer."
export const Hover: Story = {
  args: { lastUpdated: '2026-08-30', hrefs },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const links = canvas.getAllByRole('link')
    if (links[0]) await userEvent.hover(links[0])
  },
}

// §5 "focus-visible — the standard ring... on every link and on the objection button."
export const FocusVisible: Story = {
  args: { lastUpdated: '2026-08-30', hrefs },
  play: async () => {
    await userEvent.tab()
  },
}

// §5 "active — links render in `link-hover` while pressed... Nothing translates or scales."
export const Active: Story = {
  args: { lastUpdated: '2026-08-30', hrefs },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const links = canvas.getAllByRole('link')
    if (links[0]) await userEvent.pointer({ keys: '[MouseLeft>]', target: links[0] })
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
