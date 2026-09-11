import type { Meta, StoryObj } from '@storybook/react-vite'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'
import space from '../../tokens/space.json'

// T563 (FR-040, FR-041, FR-008). `space.json`'s own `rhythm` group is the answer to "which step
// expresses which relationship" — read directly here rather than restated, so a change to the
// rule shows up on this page without a second edit. Full rationale: tokens/space.json's own
// `$comment`, and `specs/README.md`'s spacing section.

type RhythmKey = keyof typeof space.rhythm

// space.scale's keys map onto Tailwind's gap-<n> utility one-to-one (space.json's own `unit`
// feeds Tailwind's spacing multiplier) — literal per key so Tailwind's scanner finds each one.
const GAP_CLASS: Record<string, string> = {
  '0': 'gap-0',
  px: 'gap-px',
  '1': 'gap-1',
  '2': 'gap-2',
  '3': 'gap-3',
  '4': 'gap-4',
  '5': 'gap-5',
  '6': 'gap-6',
  '8': 'gap-8',
  '10': 'gap-10',
  '12': 'gap-12',
  '16': 'gap-16',
  '20': 'gap-20',
  '24': 'gap-24',
  '32': 'gap-32',
}

// Same scale, read as a width so the scale demo below needs no inline style — Tailwind's width
// utility draws from the same `--spacing` multiplier `space.json`'s `unit` feeds (preset.css).
const WIDTH_CLASS: Record<string, string> = {
  '0': 'w-0',
  px: 'w-px',
  '1': 'w-1',
  '2': 'w-2',
  '3': 'w-3',
  '4': 'w-4',
  '5': 'w-5',
  '6': 'w-6',
  '8': 'w-8',
  '10': 'w-10',
  '12': 'w-12',
  '16': 'w-16',
  '20': 'w-20',
  '24': 'w-24',
  '32': 'w-32',
}

const RHYTHM_LABEL: Record<RhythmKey, string> = {
  'within-component': 'Within a component',
  'between-components': 'Between components',
  'between-sections': 'Between sections',
}

const RHYTHM_MEANING: Record<RhythmKey, string> = {
  'within-component':
    "A component's own internal layout — a label and its value, an icon and its text.",
  'between-components':
    'Two adjacent, independently-meaningful components stacked on one page — a page header and the list beneath it.',
  'between-sections':
    'The relationship this rule exists to fix: today written as mt-6 in three places, mt-8 in three others and gap-12 in one, with nothing saying which is right. Section and Page are the only primitives allowed to express it (FR-008).',
}

function RhythmDemo({ rhythmKey }: { rhythmKey: RhythmKey }) {
  const scaleStep = space.rhythm[rhythmKey]
  const gapClass = GAP_CLASS[scaleStep]
  return (
    <div className="flex flex-col gap-2 rounded-panel border-hairline border-border p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <code className="type-machine rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
          {rhythmKey}
        </code>
        <Text role="supporting">
          step {scaleStep} · {space.scale[scaleStep as keyof typeof space.scale]}
        </Text>
      </div>
      <p className="type-body text-sm text-text-primary">{RHYTHM_LABEL[rhythmKey]}</p>
      <Text role="supporting">{RHYTHM_MEANING[rhythmKey]}</Text>
      <div className={cx('flex', gapClass)}>
        <div className="h-10 w-16 rounded-control bg-surface-sunken" />
        <div className="h-10 w-16 rounded-control bg-surface-sunken" />
        <div className="h-10 w-16 rounded-control bg-surface-sunken" />
      </div>
    </div>
  )
}

const meta: Meta = {
  title: 'Foundations/Spacing',
  parameters: { layout: 'fullscreen' },
}

export default meta
type Story = StoryObj

export const Overview: Story = {
  render: () => (
    <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
      <Section
        heading="Spacing"
        description="One scale, and the rule naming which of its steps expresses which relationship — a rhythm rather than a habit."
      >
        <Section heading="The three relationships">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {(Object.keys(space.rhythm) as RhythmKey[]).map((key) => (
              <RhythmDemo key={key} rhythmKey={key} />
            ))}
          </div>
        </Section>

        <Section heading="The scale" description="Every step, drawn at its own width.">
          <div className="flex flex-col gap-2">
            {Object.entries(space.scale).map(([step, value]) => (
              <div key={step} className="flex items-center gap-3">
                <code className="type-machine w-10 shrink-0 rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
                  {step}
                </code>
                <div
                  className={cx('h-4 rounded-control bg-accent', WIDTH_CLASS[step])}
                  aria-hidden="true"
                />
                <Text role="supporting">{value}</Text>
              </div>
            ))}
          </div>
        </Section>
      </Section>
    </div>
  ),
}
