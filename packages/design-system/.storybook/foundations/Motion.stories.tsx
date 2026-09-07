import type { Meta, StoryObj } from '@storybook/react-vite'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'
import motion from '../../tokens/motion.json'

// T563 (FR-040, FR-041, FR-010). Durations, easings and the two loops the system actually runs —
// `spin`, `pulse` — read from `motion.json` directly. Every duration a component uses comes from
// this file (FR-010); this page demonstrates the closed set rather than restating it as prose.

type Duration = keyof typeof motion.duration
type Easing = keyof typeof motion.easing
type AnimationName = keyof typeof motion.animation

// One literal duration-<n> per key: Tailwind's duration utility already takes a bare millisecond
// number, so these are the closed set a component picks from (duration-120, not duration-137).
const DURATION_CLASS: Record<Duration, string> = {
  instant: 'duration-0',
  fast: 'duration-120',
  normal: 'duration-200',
  slow: 'duration-320',
}

const EASING_CLASS: Record<Easing, string> = {
  standard: 'ease-standard',
  decelerate: 'ease-decelerate',
  accelerate: 'ease-accelerate',
  linear: 'ease-linear',
}

// `motion-safe:animate-<name>` — every loop is gated behind the same variant at every real call
// site, so under `prefers-reduced-motion: reduce` the utility does not apply at all and the
// element sits at its resting frame (FR-055). Toggle "Emulate CSS media feature
// prefers-reduced-motion" in the browser's dev tools to see it stop here, in the same story.
const ANIMATION_CLASS: Record<AnimationName, string> = {
  spin: 'motion-safe:animate-spin',
  pulse: 'motion-safe:animate-pulse',
}

const ANIMATION_MEANING: Record<AnimationName, string> = {
  spin: 'A loading spinner — the one place the system asks a reader to wait.',
  pulse: 'A skeleton standing in for content that has not arrived yet.',
}

const meta: Meta = {
  title: 'Foundations/Motion',
  parameters: { layout: 'fullscreen' },
}

export default meta
type Story = StoryObj

export const Overview: Story = {
  render: () => (
    <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
      <Section
        heading="Motion"
        description="Durations and easings for transitions, and the two loops the system actually runs. Under a reduced-motion preference every transition drops to instant and every loop stops on its resting frame — this is a real state, not an afterthought (specs/README.md rule 5)."
      >
        <Section heading="Durations">
          <div className="flex flex-wrap gap-4">
            {(Object.keys(motion.duration) as Duration[]).map((key) => (
              <div key={key} className="flex flex-col items-center gap-2">
                <div className="h-10 w-24 overflow-hidden rounded-panel bg-surface-sunken">
                  <div
                    className={cx(
                      'group h-full w-4 bg-accent transition-all ease-standard hover:ml-20 motion-reduce:duration-0',
                      DURATION_CLASS[key],
                    )}
                  />
                </div>
                <code className="type-machine text-xs">{key}</code>
                <Text role="supporting">{motion.duration[key]}</Text>
              </div>
            ))}
          </div>
          <Text role="supporting">Hover a bar to see its own duration carry the move.</Text>
        </Section>

        <Section heading="Easings">
          <div className="flex flex-col gap-2">
            {(Object.keys(motion.easing) as Easing[]).map((key) => (
              <div key={key} className="flex items-center gap-3">
                <code className="type-machine w-24 shrink-0 rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
                  {key}
                </code>
                <div className="h-6 w-40 overflow-hidden rounded-panel bg-surface-sunken">
                  <div
                    className={cx(
                      'group h-full w-4 bg-accent transition-all duration-320 hover:ml-32 motion-reduce:duration-0',
                      EASING_CLASS[key],
                    )}
                  />
                </div>
                <Text role="supporting">{motion.easing[key]}</Text>
              </div>
            ))}
          </div>
        </Section>

        <Section heading="The loops">
          <div className="flex flex-wrap gap-6">
            {(Object.keys(motion.animation) as AnimationName[]).map((name) => (
              <div key={name} className="flex flex-col items-center gap-2">
                {name === 'spin' ? (
                  <div
                    className={cx(
                      'h-10 w-10 rounded-full border-2 border-border-strong border-t-transparent',
                      ANIMATION_CLASS[name],
                    )}
                    role="status"
                    aria-label="Loading"
                  />
                ) : (
                  <div
                    className={cx(
                      'h-10 w-24 rounded-control bg-surface-sunken',
                      ANIMATION_CLASS[name],
                    )}
                    aria-hidden="true"
                  />
                )}
                <code className="type-machine text-xs">{name}</code>
                <Text role="supporting">{ANIMATION_MEANING[name]}</Text>
                <Text role="supporting">
                  <code className="type-machine text-xs">
                    duration: {motion.duration[motion.animation[name].duration as Duration]} (
                    {motion.animation[name].duration}) · easing:{' '}
                    {motion.easing[motion.animation[name].easing as Easing]} (
                    {motion.animation[name].easing}) · {motion.animation[name].iterationCount}
                  </code>
                </Text>
              </div>
            ))}
          </div>
        </Section>
      </Section>
    </div>
  ),
}
