import type { Meta, StoryObj } from '@storybook/react-vite'
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

export const Default: Story = {
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

// §4 "empty" (first case) — a country the pack does not cover, or a value that is not a code at
// all. The designed degrade path (FR-008, FR-010), not a defect — no frame, no globe, no "?" tile.
export const UncoveredCountry: Story = {
  name: 'Empty — uncovered country (flagUrl undefined, not a defect)',
  args: { countryName: 'Kiribati' },
}

// §4 "error" — `flagUrl` resolved but the image fails to load/decode. Must be pixel-identical to
// UncoveredCountry above: the onError handler removes the image and its frame together.
export const FailedImage: Story = {
  name: 'Error — image fails to load (must render identically to the empty story above)',
  args: { flagUrl: '/game-assets/flags/does-not-exist.svg', countryName: 'Kiribati' },
}

// §4 "empty" (third case) — no country at all: the component renders null, nothing reserved.
export const NoCountryAtAll: Story = {
  name: 'Empty — no country at all (countryName blank, renders nothing)',
  render: () => (
    <div className="rounded-sm border border-dashed border-border p-4 font-sans text-xs text-text-secondary">
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
