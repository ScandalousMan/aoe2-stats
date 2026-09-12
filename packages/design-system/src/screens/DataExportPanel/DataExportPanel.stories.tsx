import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'
import { DataExportPanel } from './index'

const meta: Meta<typeof DataExportPanel> = {
  id: 'screens-dataexportpanel',
  title: 'Screens/Account & privacy/DataExportPanel',
  component: DataExportPanel,
  parameters: {
    docs: {
      description: {
        component: `Lets a signed-in user take a complete copy of everything this service holds about them, in one archive, and download it.`,
      },
    },
  },
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

// The skeleton at the download-link footprint stays invisible for the first `duration.normal`
// (200ms, `useDelayedVisible`) so a fast-resolving load never flashes a pulse — a `setTimeout`,
// not a wall clock, but a clock all the same (T568, FR-047). Waiting here for the pulse to exist,
// rather than screenshotting whatever frame Storybook happened to reach first, is what makes this
// baseline the same no matter how long mounting this particular story took.
export const Preparing: Story = {
  name: 'preparing — info callout with a skeleton at the download link footprint',
  args: { ...noopHandlers, initialState: 'preparing' },
  play: async ({ canvasElement }) => {
    await waitFor(() => {
      expect(canvasElement.querySelector('[class*="animate-pulse"]')).not.toBeNull()
    })
  },
}

// `Ready`, `ReadyFocusVisible` and `ReadyActive` share one `visualCaptureClip` (README's standing
// rule: a state whose signal is smaller than ~1% of its frame is captured clipped to the control
// that carries it) so the three stay each other's verification — the panel's own full-page frame
// is over a hundred times the download link's footprint, which is exactly what made
// `ready`/`ready-focus-visible` an undocumented full-set match the first time these stories were
// captured (found 2026-09-12, T587/T588's baseline regeneration): the inward focus ring and the
// underline signal are both real (T586, T588) but neither survives a whole-panel diff ratio.
const downloadLinkClip = { parts: [{ role: 'link' as const }], pad: '2' }

export const Ready: Story = {
  name: 'ready — success callout, download link and expiry note',
  args: { ...noopHandlers, initialState: 'ready' },
  parameters: { visualCaptureClip: downloadLinkClip },
}

// §5 "hover / focus-visible / active": `DownloadLink`'s standard ring rings inward instead
// (`Button/primary`'s own override, T586) — forced from Playwright in `tests/visual/stories.spec.ts`
// (see that file's own `VisualForceState` comment), the same way `Callout.stories.tsx`'s own
// `FocusVisible` drives a real button. `role: 'link'` is unambiguous here: the download link is the
// only anchor the `ready` state renders.
export const ReadyFocusVisible: Story = {
  name: 'ready — focus-visible on the download link',
  args: { ...noopHandlers, initialState: 'ready' },
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'link' },
    visualCaptureClip: downloadLinkClip,
  },
}

// §5 "`DownloadLink`'s own hover and press are not colour alone" (T588): pressed, the label's own
// underline drops to `underline-offset-4` — the row-6/H3 press signal this story exists to prove is
// large enough to hold a baseline, closing row 5/H2 of README's gap register (no story drove
// `:active` on this link before this one).
export const ReadyActive: Story = {
  name: 'ready — active (pressed) on the download link',
  args: { ...noopHandlers, initialState: 'ready' },
  parameters: {
    visualForceState: { state: 'active', role: 'link' },
    visualCaptureClip: downloadLinkClip,
  },
}

export const Failed: Story = {
  name: 'failed — danger callout with a retry action, request button enabled again',
  args: { ...noopHandlers, initialState: 'failed' },
}

// §5 "empty — the `idle` state is the empty state — no export has been requested yet." Named
// separately from `Idle` above so the state has its own entry matching the closed vocabulary,
// even though the rendering is identical.
// visual-equivalence: screens-dataexportpanel--idle: privacy-data-rights.md §5 "empty" states the
// idle state IS the empty state — this story's own name says "identical rendering to Idle" — so
// the two are byte-identical by design.
export const Empty: Story = {
  name: 'empty — the idle state, named for the vocabulary (identical rendering to Idle)',
  args: { ...noopHandlers, initialState: 'idle' },
}

// §5 "hover / focus-visible / active — owned by the `Button`s, the `DownloadLink`... the sections
// themselves are not interactive." / "disabled — the `RequestButton` disables while a request is
// in flight or a job is preparing" (already shown by `Requesting`/`Preparing` above).
//
// Corrected (README's gap register row 5/H2): this story used to claim hover, focus and active were
// "already covered by their own components' stories" for both interactive elements the `idle` state
// shows here — true only for the `RequestButton`, an unmodified `Button`, whose own
// `Button.stories.tsx` file carries every one of those states. `DownloadLink` is not a `Button`
// instance; it is a local anchor styled directly inside this screen (`index.tsx`'s `ready` branch),
// so nothing outside this file ever drove its `:focus-visible` or `:active` — the `ReadyFocusVisible`
// and `ReadyActive` stories above are that coverage, added here rather than claimed elsewhere.
export const HoverFocusActiveNotApplicable: Story = {
  name: 'hover / focus / active — not applicable to the idle sections themselves',
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The panel's own sections are not interactive. The `RequestButton` shown here is an
        unmodified `Button`, already covered by `Button.stories.tsx`'s own hover, focus-visible and
        active stories. The download link only exists in the `ready` state — see `ReadyFocusVisible`
        and `ReadyActive` above for its own coverage.
      </p>
      <DataExportPanel {...args} />
    </div>
  ),
  args: { ...noopHandlers, initialState: 'idle' },
}
