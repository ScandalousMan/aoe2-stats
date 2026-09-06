import type { Meta, StoryObj } from '@storybook/react-vite'
import { DataExportPanel } from './index'

const meta: Meta<typeof DataExportPanel> = {
  title: 'Screens/DataExportPanel',
  component: DataExportPanel,
}

export default meta
type Story = StoryObj<typeof DataExportPanel>

// `initialState` renders one fixed frame without driving real promises (privacy-data-rights.md
// §3) — the callbacks below are never actually exercised by these stories.
const noopHandlers = {
  onRequestExport: () => new Promise<{ id: string }>(() => {}),
  onPollExport: () => new Promise<never>(() => {}),
}

export const Idle: Story = {
  name: 'default — idle, no progress or ready region',
  args: { ...noopHandlers, initialState: 'idle' },
}

export const Preparing: Story = {
  name: 'preparing — info callout with a skeleton at the download link footprint',
  args: { ...noopHandlers, initialState: 'preparing' },
}

export const Ready: Story = {
  name: 'ready — success callout, download link and expiry note',
  args: { ...noopHandlers, initialState: 'ready' },
}

export const Failed: Story = {
  name: 'failed — danger callout with a retry action, request button enabled again',
  args: { ...noopHandlers, initialState: 'failed' },
}
