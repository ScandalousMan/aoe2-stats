import type { Meta, StoryObj } from '@storybook/react-vite'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'
import font from '../../tokens/font.json'

// T563 (FR-040, FR-041, FR-007). The six functional roles `font.json`'s `role` group names —
// display, body, supporting, numeric, machine, identifier — read directly from that file below,
// so this page cannot say something the token source does not: a role added, renamed or retuned
// there is what a reader of this page sees next, with nothing hand-copied in between. The size
// scale is demonstrated the same way, through the real `text-*` utilities, never a hand-typed
// pixel figure. Full derivation and the typeface decision: specs/typography-tokens.md.

type FontRole = keyof typeof font.role

// `type-<role>` (build-tokens.mjs's `typeRoleUtilityBlocks`) is the utility a component actually
// writes — one literal per role, read here as a lookup rather than composed by interpolation
// (Tailwind's scanner needs the literal text `type-display` etc. somewhere in this file).
const ROLE_CLASS: Record<FontRole, string> = {
  display: 'type-display',
  body: 'type-body',
  supporting: 'type-supporting',
  numeric: 'type-numeric',
  machine: 'type-machine',
  identifier: 'type-identifier',
}

const ROLE_SAMPLE: Record<FontRole, string> = {
  display: 'Fraunces — a heading, always through Page or Section, never here directly',
  body: 'Sans — the reader’s primary sentence, "GL.TheViper won 2,481 rating."',
  supporting: 'Sans, one step down — a caption, a hint, the line under a heading',
  numeric: '2,481  01:47  +38',
  machine: 'aoe2rec-py_v1.4.2.zip  |  civ_id=17',
  identifier: 'Unresolved — a value the product could not resolve to a name',
}

const ROLE_MEANING: Record<FontRole, string> = {
  display:
    'A heading. Rendered only through Page or Section, which own the level — never written directly on a component.',
  body: "The reader's primary sentence — a paragraph, a label, a value with no other role.",
  supporting:
    'One size step down from body — a caption, a hint, a supporting line under a heading.',
  numeric:
    'A measured number a reader compares by eye — digits align because tabular-nums is part of the role, not a per-caller opt-in.',
  machine:
    'A raw identifier, a filename, a machine string — monospace, but never tabular: applying tabular-nums here would space out letters that carry no comparison.',
  identifier:
    'A value the product could not resolve to a name. Carries text-secondary by contract, inside the utility itself, so an unobserved value stays visibly distinct from a measured one even for a caller who never reads the contract.',
}

// font.json's own comment: `numeric` alone sets `font-variant-numeric: tabular-nums`; `identifier`
// alone sets `color`. Read here from the same file rather than restated as a second claim.
function roleDetail(role: FontRole): string | undefined {
  const definition = font.role[role] as { variantNumeric?: string; color?: string }
  if (definition.variantNumeric) return `font-variant-numeric: ${definition.variantNumeric}`
  if (definition.color) return `color: ${definition.color} (by contract, inside the utility)`
  return undefined
}

const SIZE_CLASS: Record<keyof typeof font.size, string> = {
  xs: 'text-xs',
  sm: 'text-sm',
  md: 'text-md',
  lg: 'text-lg',
  xl: 'text-xl',
  '2xl': 'text-2xl',
  '3xl': 'text-3xl',
  '4xl': 'text-4xl',
}

const WEIGHT_CLASS: Record<keyof typeof font.weight, string> = {
  normal: 'font-normal',
  medium: 'font-medium',
  semibold: 'font-semibold',
  bold: 'font-bold',
}

const TRACKING_CLASS: Record<keyof typeof font.tracking, string> = {
  tight: 'tracking-tight',
  normal: 'tracking-normal',
  wide: 'tracking-wide',
}

const meta: Meta = {
  title: 'Foundations/Typography',
  parameters: { layout: 'fullscreen' },
}

export default meta
type Story = StoryObj

export const Overview: Story = {
  render: () => (
    <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
      <Section
        heading="Typography"
        description="Six roles, named by function rather than by size, and the eight-step size scale they draw from. Every specimen below is the real family: font.json's `family` group, delivered by tokens/fonts (specs/typography-tokens.md)."
      >
        <Section heading="The six roles">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {(Object.keys(font.role) as FontRole[]).map((role) => (
              <div
                key={role}
                className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <code className="type-machine rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
                    type-{role}
                  </code>
                  <Text role="supporting">family: {font.role[role].family}</Text>
                </div>
                <Text role="supporting">{ROLE_MEANING[role]}</Text>
                {roleDetail(role) && (
                  <Text role="supporting">
                    <code className="type-machine text-xs">{roleDetail(role)}</code>
                  </Text>
                )}
                <p className={cx(ROLE_CLASS[role], 'text-lg text-text-primary')}>
                  {ROLE_SAMPLE[role]}
                </p>
              </div>
            ))}
          </div>
        </Section>

        <Section
          heading="The size scale"
          description="Eight steps, each a real Tailwind text-* utility over font.json's size.value/lineHeight pair — never a separate role of its own (FR-007: a role is a function, size is orthogonal to it)."
        >
          <div className="flex flex-col gap-3">
            {(Object.keys(font.size) as (keyof typeof font.size)[]).map((size) => (
              <div key={size} className="flex flex-wrap items-baseline gap-3">
                <code className="type-machine w-16 shrink-0 rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
                  {size}
                </code>
                <span className={cx('type-body text-text-primary', SIZE_CLASS[size])}>
                  The quick brown fox
                </span>
                <Text role="supporting">
                  value: {font.size[size].value} · line-height: {font.size[size].lineHeight}
                </Text>
              </div>
            ))}
          </div>
        </Section>

        <Section heading="Weight and tracking">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              {(Object.keys(font.weight) as (keyof typeof font.weight)[]).map((weight) => (
                <p
                  key={weight}
                  className={cx('type-body text-lg text-text-primary', WEIGHT_CLASS[weight])}
                >
                  {weight} ({font.weight[weight]})
                </p>
              ))}
            </div>
            <div className="flex flex-col gap-2">
              {(Object.keys(font.tracking) as (keyof typeof font.tracking)[]).map((tracking) => (
                <p
                  key={tracking}
                  className={cx('type-body text-lg text-text-primary', TRACKING_CLASS[tracking])}
                >
                  {tracking} tracking ({font.tracking[tracking]})
                </p>
              ))}
            </div>
          </div>
        </Section>

        <Section
          heading="Delivery"
          description="The three families each role reads from `font.family` (above), and the file each is actually shipped as — read from `font.json`'s own `face` group rather than restated: which weights are self-hosted, in what style, under which font-display strategy. The typeface decision itself — why these three, and the licence record for each — is specs/typography-tokens.md; the facts on this row are the ones that answer 'which font actually renders this role' without opening it."
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {(Object.keys(font.face) as (keyof typeof font.face)[]).map((name) => (
              <div
                key={name}
                className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <code className="type-machine rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
                    {name}
                  </code>
                  <Text role="supporting">{font.face[name].family}</Text>
                </div>
                <Text role="supporting">
                  <code className="type-machine text-xs">{font.family[name]}</code>
                </Text>
                <Text role="supporting">
                  weight {font.face[name].weight} · {font.face[name].style} · font-display:{' '}
                  {font.face[name].display}
                </Text>
                <Text role="supporting">
                  <code className="type-machine text-xs">{font.face[name].src}</code>
                </Text>
              </div>
            ))}
          </div>
        </Section>
      </Section>
    </div>
  ),
}
