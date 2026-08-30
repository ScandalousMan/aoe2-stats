import type { Meta, StoryObj } from '@storybook/react-vite'
import { fireEvent, userEvent, within } from 'storybook/test'
import { UploadControl } from './index'

const meta: Meta<typeof UploadControl> = {
  title: 'Composite/UploadControl',
  component: UploadControl,
}

export default meta
type Story = StoryObj<typeof UploadControl>

// `onUpload` never resolves in a pinned `initialState` story (manual-upload.md §3's own words:
// "the route never sets it") — the frame is fixed by the prop, not by driving a real promise.
const noopOnUpload = () => new Promise<void>(() => {})

// The eight-member closed vocabulary (manual-upload.md §5), one baseline each.

export const Idle: Story = {
  name: 'idle — the empty drop zone, no submit button',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'idle' },
}

export const FileChosen: Story = {
  name: 'file-chosen — name, size and an enabled submit button',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'file-chosen' },
}

export const Uploading: Story = {
  name: 'uploading — busy submit button, "Uploading…"',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'uploading' },
}

export const Succeeded: Story = {
  name: 'succeeded — success callout, picker collapsed',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'succeeded' },
}

export const InvalidReplay: Story = {
  name: 'invalid-replay — 422, danger callout, file still selected for a retry',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'invalid-replay' },
}

export const WrongMatch: Story = {
  name: 'wrong-match — 404, danger callout, file still selected for a retry',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'wrong-match' },
}

export const AlreadyArchived: Story = {
  name: 'already-archived — 409, info callout with Refresh, picker collapsed',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'already-archived' },
}

export const Failed: Story = {
  name: 'failed — network/5xx, danger callout, file still selected for a retry',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'failed' },
}

// Beyond the closed vocabulary: interaction-driven frames a static `initialState` prop cannot
// pin, because they depend on a live sequence rather than one fixed render (the T035c/T038b
// lesson — a baseline that never exercises the real trigger protects nothing).

function replayFile() {
  return new File([new Uint8Array(1_400_000)], 'SP Replay v101.103.aoe2record', {
    type: 'application/octet-stream',
  })
}

export const DragOver: Story = {
  name: 'drag-over — the focus-ring-toned inset boundary, empty drop zone',
  args: { gameId: 42, onUpload: noopOnUpload, initialState: 'idle' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const dropZone = canvas.getByText(/Drop the \.aoe2record file here/).closest('div')
    if (dropZone) fireEvent.dragOver(dropZone)
  },
}

export const UploadingValidating: Story = {
  name: 'uploading — the label switches on to "Checking the file…"',
  args: {
    gameId: 42,
    onUpload: () => new Promise<void>(() => {}),
    initialState: 'idle',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvasElement.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, replayFile())
    await userEvent.click(canvas.getByRole('button', { name: 'Upload and archive' }))
    await canvas.findByRole('button', { name: 'Checking the file…' }, { timeout: 2_000 })
  },
}

export const RealSelectionThenSuccess: Story = {
  name: 'a real file selection, submitted, resolving to succeeded',
  args: {
    gameId: 42,
    onUpload: () => Promise.resolve(),
    initialState: 'idle',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvasElement.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, replayFile())
    await userEvent.click(canvas.getByRole('button', { name: 'Upload and archive' }))
    await canvas.findByText('Archived from your upload.')
  },
}
