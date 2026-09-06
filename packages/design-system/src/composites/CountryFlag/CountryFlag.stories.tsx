import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { CountryFlag } from './index'

const meta: Meta<typeof CountryFlag> = {
  title: 'Composite/CountryFlag',
  component: CountryFlag,
}

export default meta
type Story = StoryObj<typeof CountryFlag>

const FRANCE_URL = '/game-assets/flags/fr.svg'
const JAPAN_URL = '/game-assets/flags/jp.svg'
const POLAND_URL = '/game-assets/flags/pl.svg'

// country-flag.md §11.9 — the reveal is pointer- or keyboard-only, so the default capture shows the
// flag alone with no country word anywhere in the frame. Every "open" story below forces the state
// with a play function (Tooltip's own stories use the same technique, for the same reason).
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
  await userEvent.unhover(trigger)
  trigger.blur()
  await waitFor(() => expect(trigger).not.toHaveFocus())
}

async function dismissAfterEscape({ canvasElement }: { canvasElement: HTMLElement }) {
  const canvas = within(canvasElement)
  await userEvent.tab()
  await canvas.findByRole('tooltip')
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(canvas.queryByRole('tooltip')).not.toBeInTheDocument())
}

// §11.9 — default: the flag stands alone, no country word anywhere in the frame.
export const Default: Story = {
  tags: ['visual-full-page'],
  args: { flagUrl: FRANCE_URL, countryName: 'France' },
}

export const SizeSm: Story = {
  name: 'Size — sm (16px, default, ProfileSummary compact)',
  args: { flagUrl: FRANCE_URL, countryName: 'France', size: 'sm' },
}

export const SizeMd: Story = {
  name: 'Size — md (24px, ProfileSummary board identity bar)',
  args: { flagUrl: FRANCE_URL, countryName: 'France', size: 'md' },
}

export const BothSizes: Story = {
  name: 'Both sizes in one frame',
  render: () => (
    <div className="flex items-center gap-6">
      <CountryFlag flagUrl={FRANCE_URL} countryName="France" size="sm" />
      <CountryFlag flagUrl={FRANCE_URL} countryName="France" size="md" />
    </div>
  ),
}

// §11.9 — the hover story: the country name in a tooltip above the flag.
export const FlagHoverRevealed: Story = {
  name: 'Hover — the country name opens in a tooltip above the flag',
  tags: ['visual-full-page'],
  play: hoverOpen,
  args: { flagUrl: FRANCE_URL, countryName: 'France' },
}

// §11.9 — the keyboard-focus story: the tooltip open AND the focus ring visible, in the same frame.
export const FlagKeyboardFocusRevealed: Story = {
  name: 'Keyboard focus — tooltip open and focus ring visible together',
  tags: ['visual-full-page'],
  play: focusOpen,
  args: { flagUrl: FRANCE_URL, countryName: 'France' },
}

// §11.9 — the pinned (pressed) story: the touch route, no pointer, no focus ring.
export const FlagPinned: Story = {
  name: 'Pinned (pressed) — the touch route, no pointer, no focus ring',
  tags: ['visual-full-page'],
  play: pinOpen,
  args: { flagUrl: FRANCE_URL, countryName: 'France' },
}

// §11.9 — after Escape: no tooltip, the flag still visibly focused.
export const FlagDismissedAfterEscape: Story = {
  name: 'After Escape — no tooltip, flag still visibly focused',
  tags: ['visual-full-page'],
  play: dismissAfterEscape,
  args: { flagUrl: FRANCE_URL, countryName: 'France' },
}

// §10 acceptance — a mostly-white flag needs a visible boundary against the light theme's
// parchment. Japan and Poland are the two named stories.
export const MostlyWhiteFlagJapan: Story = {
  name: 'Mostly-white flag — Japan (needs a visible boundary)',
  args: { flagUrl: JAPAN_URL, countryName: 'Japan' },
}

export const MostlyWhiteFlagPoland: Story = {
  name: 'Mostly-white flag — Poland (needs a visible boundary)',
  args: { flagUrl: POLAND_URL, countryName: 'Poland' },
}

// §11.4 — a country the pack does not cover. The designed degrade path (FR-008, FR-010), not a
// defect — no frame, no button, no tab stop, no tooltip, the name alone as plain text.
export const UncoveredCountry: Story = {
  name: 'Empty — uncovered country (flagUrl undefined, not a defect)',
  args: { countryName: 'Kiribati' },
}

// §11.4 — `flagUrl` resolved but the image fails to load/decode. Must be pixel-identical to
// UncoveredCountry above: the onError handler removes the image, its frame and its tooltip
// together.
export const FailedImage: Story = {
  name: 'Error — image fails to load (must render identically to the empty story above)',
  args: { flagUrl: '/game-assets/flags/does-not-exist.svg', countryName: 'Kiribati' },
}

// §4 "empty" (third case) — no country at all: the component renders null, nothing reserved.
export const NoCountryAtAll: Story = {
  name: 'Empty — no country at all (countryName blank, renders nothing)',
  render: () => (
    <div className="rounded-panel border border-dashed border-border p-4 font-sans text-xs text-text-secondary">
      Nothing renders below this line —{' '}
      <span className="inline-block align-middle">
        <CountryFlag flagUrl={FRANCE_URL} countryName="" />
      </span>
    </div>
  ),
}

// Acceptance: covered, uncovered, failed and no-country side by side. The uncovered and failed
// rows overlay pixel-for-pixel, and the no-country row leaves nothing where the pair would be.
export const CombinedList: Story = {
  name: 'Combined — covered, uncovered, failed and no-country side by side',
  render: () => (
    <ul className="flex flex-col gap-3">
      <li>
        <CountryFlag flagUrl={FRANCE_URL} countryName="France" />
      </li>
      <li>
        <CountryFlag countryName="Kiribati" />
      </li>
      <li>
        <CountryFlag flagUrl="/game-assets/flags/does-not-exist.svg" countryName="Kiribati" />
      </li>
      <li>Nothing renders on the next line — {<CountryFlag countryName="" />}</li>
    </ul>
  ),
}
