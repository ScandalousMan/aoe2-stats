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
