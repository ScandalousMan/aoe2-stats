import type { Meta, StoryObj } from '@storybook/react-vite'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'
import radius from '../../tokens/radius.json'

// T563 (FR-040, FR-041, FR-013). Radius is assigned by role, not by size, so two components of
// the same role cannot differ — the values below are read from `radius.json` directly; the "what
// belongs at this role" text is this file's own condensed form of that JSON's `$comment`
// (specs/README.md carries none of its own — the token source is the one place this is written).

type RadiusRole = 'control' | 'panel' | 'overlay' | 'pill'

const ROLE_MEANING: Record<RadiusRole, string> = {
  control:
    'Small, interactive, form-like shapes — buttons, inputs, search boxes, nav links — and the compact inline marks beside them (avatars, flags, civilisation icons, colour swatches).',
  panel:
    'Card- or container-shaped blocks of content — panels, list rows acting as cards, table containers, the match-detail and analysis-timeline blocks.',
  overlay: 'Floating surfaces above the page — dialogs, menus, tooltips.',
  pill: 'Fully-rounded chips — badges, the rating record bar.',
}

// One literal per role, matching build-tokens.mjs's rounded-<role> utility exactly.
const ROLE_CLASS: Record<RadiusRole, string> = {
  control: 'rounded-control',
  panel: 'rounded-panel',
  overlay: 'rounded-overlay',
  pill: 'rounded-pill',
}

const ROLES: RadiusRole[] = (['control', 'panel', 'overlay', 'pill'] as const).filter(
  (role) => role in radius,
)

const meta: Meta = {
  title: 'Foundations/Radii',
  parameters: { layout: 'fullscreen' },
}

export default meta
type Story = StoryObj

export const Overview: Story = {
  render: () => (
    <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
      <Section
        heading="Radii"
        description="Assigned by role, not by size — a component reaches for the role it is, and two components of the same role cannot differ."
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {ROLES.map((role) => (
            <div
              key={role}
              className="flex flex-col gap-3 rounded-panel border-hairline border-border p-4"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <code className="type-machine rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
                  {role}
                </code>
                <Text role="supporting">{radius[role]}</Text>
              </div>
              <Text role="supporting">{ROLE_MEANING[role]}</Text>
              <div
                className={cx(
                  'h-20 w-32 border-hairline border-border-strong bg-surface-sunken',
                  ROLE_CLASS[role],
                )}
              />
            </div>
          ))}
        </div>
      </Section>
    </div>
  ),
}
