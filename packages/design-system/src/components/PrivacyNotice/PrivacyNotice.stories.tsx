import type { Meta, StoryObj } from '@storybook/react-vite'
import { PrivacyNotice } from './index'

const meta: Meta<typeof PrivacyNotice> = {
  title: 'Screens/PrivacyNotice',
  component: PrivacyNotice,
}

export default meta
type Story = StoryObj<typeof PrivacyNotice>

const hrefs = {
  archivalControl: '/dashboard',
  privacyRoute: '/privacy',
  objectionForm: '/object',
}

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
