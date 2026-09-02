import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { Tooltip } from './index'

const meta: Meta<typeof Tooltip> = {
  title: 'Primitives/Tooltip',
  component: Tooltip,
}

export default meta
type Story = StoryObj<typeof Tooltip>

// A decorative trigger child (empty `alt`) — `CountryFlag`'s own real shape (country-flag.md
// §11): the tooltip is what gives the trigger its accessible name, not the image.
function FlagIcon() {
  return (
    <img
      src="https://flagcdn.com/24x18/fr.png"
      width={24}
      height={18}
      alt=""
      style={{ display: 'block' }}
    />
  )
}

// §4: the reveal is pointer- or keyboard-only, so a default capture shows none of it — every
// "open" story below forces the state with a play function, the same technique Menu's popover
// stories use for the same reason.
async function hoverOpen({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  await userEvent.hover(canvas.getByRole('button'))
  await canvas.findByRole('tooltip')
}

async function focusOpen({ canvasElement }: { canvasElement: HTMLElement }) {
  await userEvent.tab()
  await within(canvasElement).findByRole('tooltip')
}

async function pinOpen({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  const trigger = canvas.getByRole('button')
  await userEvent.click(trigger)
  await canvas.findByRole('tooltip')
  // The touch/pinned route has no pointer over the trigger and no focus ring — move the pointer
  // off it so the frame shows the pinned state alone (§10's pinned criterion).
  await userEvent.unhover(trigger)
  // `userEvent.click` dispatches a synthetic (untrusted) event, which real Chromium's
  // `:focus-visible` heuristic can resolve inconsistently with an actual click gesture, leaving a
  // spurious ring in the captured frame (round-2 finding B). A touch tap never produces
  // `:focus-visible` in the first place, so blurring the trigger removes any ambiguity outright —
  // §4 active: pinning is independent of focus/hover, so the tooltip stays open (verified in
  // Tooltip.test.tsx's "a press pins the tooltip open independently of the pointer" case, which
  // already unhovers past the close grace and asserts the surface is still present; blur is the
  // same independence, just the other open-source instead of hover).
  trigger.blur()
  await waitFor(() => expect(trigger).not.toHaveFocus())
}

// `visual-full-page` (scripts/visual/run.mjs): the surface is absolutely positioned against the
// trigger's own box, which does not grow to contain it — a screenshot clipped to the story root
// never reaches it.
export const Default: Story = {
  tags: ['visual-full-page'],
  args: {
    content: 'France',
    children: <FlagIcon />,
  },
}

export const HoverRevealed: Story = {
  tags: ['visual-full-page'],
  play: hoverOpen,
  args: {
    content: 'France',
    qualifier: 'Country:',
    children: <FlagIcon />,
  },
}

export const KeyboardFocusRevealed: Story = {
  tags: ['visual-full-page'],
  play: focusOpen,
  args: {
    content: 'France',
    qualifier: 'Country:',
    children: <FlagIcon />,
  },
}

// §4 active — the only route a touch user has, so it is its own story rather than an appendix to
// the hover one: the frame must show the surface with no pointer on the trigger and no focus ring.
export const Pinned: Story = {
  tags: ['visual-full-page'],
  play: pinOpen,
  args: {
    content: 'France',
    qualifier: 'Country:',
    children: <FlagIcon />,
  },
}

// §10 dismiss: Escape closes the surface while leaving focus on the trigger, and it stays
// dismissed — the frame must show the ring but no surface (§8's "stays dismissed" half).
async function dismissAfterEscape({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  await userEvent.tab()
  await canvas.findByRole('tooltip')
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(canvas.queryByRole('tooltip')).not.toBeInTheDocument())
}

// §10 dismiss: blur closes the surface outright — no surface anywhere in the frame.
async function dismissAfterBlur({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  await userEvent.tab()
  await canvas.findByRole('tooltip')
  await userEvent.tab() // moves focus off the trigger; the resulting blur closes the tooltip.
  await waitFor(() => expect(canvas.queryByRole('tooltip')).not.toBeInTheDocument())
}

export const DismissedAfterEscape: Story = {
  tags: ['visual-full-page'],
  play: dismissAfterEscape,
  args: {
    content: 'France',
    qualifier: 'Country:',
    children: <FlagIcon />,
  },
}

export const DismissedAfterBlur: Story = {
  tags: ['visual-full-page'],
  play: dismissAfterBlur,
  args: {
    content: 'France',
    qualifier: 'Country:',
    children: <FlagIcon />,
  },
}

// §7: text wraps, it is never truncated. Long enough to wrap onto a second line inside `max-w-xs`.
export const LongContent: Story = {
  tags: ['visual-full-page'],
  play: hoverOpen,
  args: {
    content:
      'Republic of the Congo — a claim carried exactly as the source reports it, unverified by this project.',
    children: <FlagIcon />,
  },
}

// §3: a trigger whose visible label is already text takes `relation="describe"` — `"label"`
// there would replace what a sighted user sees with what they cannot (WCAG 2.5.3).
export const DescribeRelation: Story = {
  tags: ['visual-full-page'],
  play: hoverOpen,
  args: {
    content: 'Ranked, 1v1 Random Map — this profile’s highest-rated ladder',
    relation: 'describe',
    children: 'Elo 1850',
  },
}

// §3a/§10 round-3: the mirror of `LongContent` above — a trigger near the viewport's RIGHT edge
// with wide content. The surface must shift LEFT to keep at least `space-4` clear of the right
// edge, still centred on the trigger's own axis otherwise; it never shrinks below `max-w-xs` or
// truncates its text.
export const NearRightEdge: Story = {
  tags: ['visual-full-page'],
  play: hoverOpen,
  args: {
    content:
      'Republic of the Congo — a claim carried exactly as the source reports it, unverified by this project.',
    children: <FlagIcon />,
  },
  decorators: [
    (StoryFn) => (
      <div className="flex justify-end">
        <StoryFn />
      </div>
    ),
  ],
}

// §3a/§10 round-3 regression guard: a trigger with ample room on both sides, but with content wide
// enough to reach `max-w-xs`, must stay exactly centred — the inline-axis correction fires only
// when an edge is actually threatened, never unconditionally. `AboveAFigure`/`RealisticIdentityBar`
// already cover a centred trigger with short content; this is the wide-content counterpart.
export const CenteredWideContent: Story = {
  tags: ['visual-full-page'],
  play: hoverOpen,
  args: {
    content:
      'Republic of the Congo — a claim carried exactly as the source reports it, unverified by this project.',
    children: <FlagIcon />,
  },
  decorators: [
    (StoryFn) => (
      <div className="flex justify-center">
        <StoryFn />
      </div>
    ),
  ],
}

// §3a: default placement is block-start (above), tried first for exactly the reason named there —
// so it never drops over a figure directly beneath it, like the rating board under `ProfileSummary`
// `IdentityBar`. This story stands the trigger where that board would sit, to show the surface
// clearing it.
export const AboveAFigure: Story = {
  tags: ['visual-full-page'],
  play: hoverOpen,
  args: {
    content: 'France',
    qualifier: 'Country:',
    children: <FlagIcon />,
  },
  decorators: [
    (StoryFn) => (
      <div className="flex flex-col gap-4">
        <StoryFn />
        <div className="rounded-lg border border-border bg-surface p-4 text-sm text-text-primary">
          Rating board — the figure the tooltip must never cover.
        </div>
      </div>
    ),
  ],
}

// §4 empty: content that is absent or blank after trimming renders no button and no surface —
// the trigger's child alone, unwrapped. Nothing to open, so no play function.
export const Blank: Story = {
  args: {
    content: '   ',
    children: <FlagIcon />,
  },
}

// A realistic combined story: the first real consumer's shape (T457) — a flag beside an alias,
// the country name only in the tooltip, revealed on hover.
export const RealisticIdentityBar: Story = {
  tags: ['visual-full-page'],
  play: hoverOpen,
  render: (args) => (
    <div className="flex items-center gap-2 text-lg font-semibold text-text-primary">
      <Tooltip {...args} />
      <span>Azhague33</span>
    </div>
  ),
  args: {
    content: 'France',
    qualifier: 'Country:',
    children: <FlagIcon />,
  },
}
