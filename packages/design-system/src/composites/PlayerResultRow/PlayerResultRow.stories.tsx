import type { Meta, StoryObj } from '@storybook/react-vite'
import { userEvent } from 'storybook/test'
import { PlayerResultRow } from './index'
import type { PlayerSearchResultData } from './index'

const meta: Meta<typeof PlayerResultRow> = {
  title: 'Composite/PlayerResultRow',
  component: PlayerResultRow,
}

export default meta
type Story = StoryObj<typeof PlayerResultRow>

const base: PlayerSearchResultData = {
  profileId: '12345',
  href: '/players/12345',
  alias: 'aoe2villain',
  country: 'France',
  gamesPlayed: 1042,
  clan: 'GL',
}

export const SourceBacked: Story = {
  name: 'Source-backed result — country, standing and clan all known',
  args: { result: base },
}

// player-search.md §5 "hover / focus-visible / active — `PlayerResultRow`: whole-row hover fill
// `surface-sunken`... nothing inside the row — including `Standing` — has its own hover; focus
// ring on the row's own link wrapper."
export const Hover: Story = {
  args: { result: base },
  play: async ({ canvasElement }) => {
    const link = canvasElement.querySelector('a[href="/players/12345"]')
    if (link) await userEvent.hover(link)
  },
}

export const FocusVisible: Story = {
  args: { result: base },
  play: async () => {
    await userEvent.tab()
  },
}

export const Active: Story = {
  args: { result: base },
  play: async ({ canvasElement }) => {
    const link = canvasElement.querySelector('a[href="/players/12345"]')
    if (link) await userEvent.pointer({ keys: '[MouseLeft>]', target: link })
  },
}

// §5 "disabled — `Input` only... there is no other disabled condition for either component." This
// row has no loading, error or empty rendering of its own either — it is always a fully-resolved
// result by the time `SearchBox` renders one.
export const DisabledLoadingErrorEmptyNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        A result row has no disabled, loading, error or empty rendering of its own — by the time
        `SearchBox` renders one, it is always a fully-resolved result. Those states belong to
        `SearchBox`'s own `ResultsRegion`.
      </p>
      <PlayerResultRow result={base} />
    </div>
  ),
}

export const NoClanTag: Story = {
  name: 'No clan tag — no empty bracket rendered',
  args: { result: { ...base, profileId: '12346', clan: null } },
}

// §4: `aoe_profiles` has no games-played column, so a locally-known result cannot carry one —
// `Standing` renders nothing for it, never a fabricated `0`, and `clan` becomes the fallback
// distinguisher.
export const LocallyKnownFallback: Story = {
  name: 'Locally-known result (FR-004d) — no games-played count, clan is the fallback distinguisher',
  args: {
    result: {
      profileId: '12347',
      href: '/players/12347',
      alias: 'aoe2villain',
      country: 'Germany',
      gamesPlayed: null,
      clan: 'GL',
    },
  },
}

export const NoCountryKnown: Story = {
  name: 'No country known — the field is absent, not blank-filled',
  args: { result: { ...base, profileId: '12348', country: null } },
}

export const AliasOnly: Story = {
  name: 'Alias only — no country, no standing, no clan',
  args: {
    result: {
      profileId: '12349',
      href: '/players/12349',
      alias: 'newplayer99',
      country: null,
      gamesPlayed: null,
      clan: null,
    },
  },
}

// §4a: the source's own claim, carried and labelled, never turned into a second link or any
// affordance suggesting this result and another are the same person.
export const UnverifiedSteamClaim: Story = {
  name: 'Unverified Steam claim shown — labelled, plain text, no second affordance (FR-004b, §4a)',
  args: {
    result: {
      ...base,
      profileId: '12350',
      unverifiedSteamId: '76561198012345678',
    },
  },
}

export const NoUnverifiedSteamClaimKnown: Story = {
  name: 'No unverified Steam claim known — the line is absent, not blank-filled (§4a)',
  args: { result: { ...base, profileId: '12351', unverifiedSteamId: null } },
}

// FR-002: "at minimum country and current standing" so two players sharing a name stay tellable
// apart at a glance.
export const NearIdenticalNames: Story = {
  name: 'Two near-identical aliases, told apart by country and standing (FR-002)',
  render: () => (
    <ul className="flex flex-col gap-3">
      <li>
        <PlayerResultRow
          result={{
            profileId: '1',
            href: '/players/1',
            alias: 'TheViper',
            country: 'Netherlands',
            gamesPlayed: 8213,
            clan: null,
          }}
        />
      </li>
      <li>
        <PlayerResultRow
          result={{
            profileId: '2',
            href: '/players/2',
            alias: 'TheViper',
            country: 'Belgium',
            gamesPlayed: 412,
            clan: 'RED',
          }}
        />
      </li>
    </ul>
  ),
}
