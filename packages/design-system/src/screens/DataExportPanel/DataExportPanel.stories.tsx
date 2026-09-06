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

// privacy-data-rights.md §5 "loading — `requesting` shows the `RequestButton` in its loading
// state" — the first of the two loading phases, distinct from `preparing` below.
export const Requesting: Story = {
  name: 'requesting — the request button in its own loading state',
  args: { ...noopHandlers, initialState: 'requesting' },
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

// §5 "empty — the `idle` state is the empty state — no export has been requested yet." Named
// separately from `Idle` above so the state has its own entry matching the closed vocabulary,
// even though the rendering is identical.
export const Empty: Story = {
  name: 'empty — the idle state, named for the vocabulary (identical rendering to Idle)',
  args: { ...noopHandlers, initialState: 'idle' },
}

// §5 "hover / focus-visible / active — owned by the `Button`s, the `DownloadLink`... the sections
// themselves are not interactive." / "disabled — the `RequestButton` disables while a request is
// in flight or a job is preparing" (already shown by `Requesting`/`Preparing` above).
export const HoverFocusActiveNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The panel's own sections are not interactive — hover, focus and active all belong to the
        `RequestButton` and the `DownloadLink` inside it, already covered by their own components'
        stories.
      </p>
      <DataExportPanel {...args} />
    </div>
  ),
  args: { ...noopHandlers, initialState: 'idle' },
}
