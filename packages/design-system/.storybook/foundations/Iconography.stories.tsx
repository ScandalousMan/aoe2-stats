import type { Meta, StoryObj } from '@storybook/react-vite'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'
import icon from '../../tokens/icon.json'

// T563 (FR-040, FR-041, FR-011). The size scale is read from `icon.json` directly; the rest of
// the contract — alignment, accessible naming, minimum footprint — has no token to read (it is
// behaviour, not a value), so it is condensed here from `specs/README.md`'s "Iconography
// contract" section, which carries the full reasoning and the real call sites.

type IconSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl'

// One literal per step, matching build-tokens.mjs's `icon-<size>` utility exactly.
const ICON_CLASS: Record<IconSize, string> = {
  xs: 'icon-xs',
  sm: 'icon-sm',
  md: 'icon-md',
  lg: 'icon-lg',
  xl: 'icon-xl',
  '2xl': 'icon-2xl',
  '3xl': 'icon-3xl',
}

const SIZES = (Object.keys(ICON_CLASS) as IconSize[]).filter((size) => size in icon)

function Glyph({ className }: { className: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12h8M12 8v8" />
    </svg>
  )
}

const meta: Meta = {
  title: 'Foundations/Iconography',
  parameters: { layout: 'fullscreen' },
}

export default meta
type Story = StoryObj

export const Overview: Story = {
  render: () => (
    <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
      <Section
        heading="Iconography"
        description="A closed size scale, plus the rest of the contract: how an icon aligns with adjacent text, how it is given or denied an accessible name, and the minimum interactive footprint it owes. An icon is never the only carrier of a meaning (FR-011)."
      >
        <Section heading="Size scale">
          <div className="flex flex-wrap items-end gap-6">
            {SIZES.map((size) => (
              <div key={size} className="flex flex-col items-center gap-2">
                <Glyph className={cx(ICON_CLASS[size], 'text-text-primary')} />
                <code className="type-machine text-xs">icon-{size}</code>
                <Text role="supporting">{icon[size]}</Text>
              </div>
            ))}
          </div>
          <Text role="supporting">
            Six of the seven steps are space-scale multiples, so an icon and the space around it
            share one rhythm — icon-xl alone is fixed at 44px, the WCAG 2.5.8 touch-target floor,
            not a rhythm step.
          </Text>
        </Section>

        <Section
          heading="Text alignment"
          description="An icon beside text is a flex sibling of that text, centred against the row's box — never aligned to the text's own baseline."
        >
          <div className="inline-flex items-center gap-2 rounded-panel border-hairline border-border bg-surface p-3">
            <Glyph className="icon-md text-accent" />
            <span className="type-body text-text-primary">Label beside the mark</span>
          </div>
        </Section>

        <Section heading="Accessible naming — three shapes, and a fourth that is forbidden">
          <div className="flex flex-col gap-3">
            <div className="rounded-panel border-hairline border-border p-4">
              <p className="type-body text-sm font-semibold text-text-primary">
                Decorative — the meaning is already carried by adjacent visible text
              </p>
              <Text role="supporting">
                <code className="type-machine text-xs">aria-hidden=&quot;true&quot;</code> on the
                mark; the heading or label beside it carries the identity. The default, and the
                wrong place to also add a second name.
              </Text>
            </div>
            <div className="rounded-panel border-hairline border-border p-4">
              <p className="type-body text-sm font-semibold text-text-primary">
                The control&apos;s own accessible name covers the icon
              </p>
              <Text role="supporting">
                The enclosing control carries the name (an{' '}
                <code className="type-machine text-xs">aria-label</code>, when the visible text
                alone under-describes the action); the glyph inside stays decorative either way.
              </Text>
            </div>
            <div className="rounded-panel border-hairline border-border p-4">
              <p className="type-body text-sm font-semibold text-text-primary">
                The icon reveals a name that would otherwise not exist
              </p>
              <Text role="supporting">
                A <code className="type-machine text-xs">Tooltip</code> with{' '}
                <code className="type-machine text-xs">relation=&quot;label&quot;</code>, reachable
                on hover, keyboard focus and press alike, present in the accessibility tree whether
                or not it has ever opened.
              </Text>
            </div>
            <div className="rounded-panel border-hairline border-danger p-4">
              <p className="type-body text-sm font-semibold text-danger">
                Forbidden — an aria-label on the icon duplicating a name already stated beside it
              </p>
              <Text role="supporting">
                A name on the icon and a name on the text it duplicates is two names racing each
                other in the accessibility tree, not a second signal.
              </Text>
            </div>
          </div>
        </Section>

        <Section
          heading="Minimum interactive footprint"
          description="WCAG 2.5.8's 44×44px floor applies to any icon serving as, or sitting inside, an interactive control — whether or not the glyph itself renders that large."
        >
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex flex-col items-center gap-2">
              <div className="icon-xl flex items-center justify-center rounded-control bg-accent text-accent-contrast">
                <Glyph className="icon-md" />
              </div>
              <Text role="supporting">
                The icon&apos;s own box is the hit area — icon-xl (44px)
              </Text>
            </div>
            <div className="flex flex-col items-center gap-2">
              <div className="flex h-11 w-11 items-center justify-center rounded-control border-hairline border-border-strong">
                <Glyph className="icon-sm text-text-primary" />
              </div>
              <Text role="supporting">
                Padding on the control composes a smaller icon up to 44px — never a transparent
                overlay
              </Text>
            </div>
          </div>
        </Section>
      </Section>
    </div>
  ),
}
