import type { Meta, StoryObj } from '@storybook/react-vite'
import { Fragment } from 'react'
import { Section, Text } from '../../src'
import { cx } from '../../src/lib/cx'
import elevation from '../../tokens/elevation.json'

// T563 (FR-040, FR-041, FR-009). `elevation.json` carries its own `$meaning` per level — what it
// means and what may sit at it — read directly below rather than restated, so this page cannot
// drift from the token source. Full reasoning: specs/README.md, "Elevation".

type ElevationLevel = keyof typeof elevation.$meaning

// `$meaning`'s own prose is written for a markdown reader (`` `Dialog` ``, meant for
// specs/README.md); rendered verbatim in JSX that would show the backticks themselves. This
// renders the same string, splitting only on the backtick pairs the source already carries — no
// second copy of the text, just the punctuation markdown owns translated to a <code> span.
function renderMarkdownCode(text: string) {
  return text.split(/(`[^`]+`)/g).map((segment, index) => {
    if (segment.startsWith('`') && segment.endsWith('`')) {
      return (
        <code key={index} className="type-machine text-xs">
          {segment.slice(1, -1)}
        </code>
      )
    }
    return <Fragment key={index}>{segment}</Fragment>
  })
}

// One literal per level, matching the real `shadow-<level>` utility a component writes.
const SHADOW_CLASS: Record<ElevationLevel, string> = {
  none: 'shadow-none',
  raised: 'shadow-raised',
  overlay: 'shadow-overlay',
  modal: 'shadow-modal',
}

const LEVELS = Object.keys(elevation.$meaning) as ElevationLevel[]

const meta: Meta = {
  title: 'Foundations/Elevation',
  parameters: { layout: 'fullscreen' },
}

export default meta
type Story = StoryObj

export const Overview: Story = {
  render: (_args, context) => {
    const theme = context.globals.theme === 'dark' ? 'dark' : 'light'
    const shadows = elevation[theme]

    return (
      <div className="mx-auto flex max-w-page flex-col gap-8 p-6">
        <Section
          heading="Elevation"
          description="Four levels. A shadow is a claim about where a surface sits relative to everything else on the page, not a decoration picked by eye — each level states what it means and what may sit at it. The raw box-shadow value below is read from elevation.json for the active theme, the same value the shadow-<level> utility resolves to."
        >
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            {LEVELS.map((level) => (
              <div key={level} className="flex flex-col gap-3 rounded-panel bg-surface p-4">
                <code className="type-machine w-fit rounded-control bg-surface-sunken px-1.5 py-0.5 text-xs">
                  {level}
                </code>
                <Text role="supporting">{renderMarkdownCode(elevation.$meaning[level])}</Text>
                <Text role="supporting">
                  <code className="type-machine text-xs">{shadows[level]}</code>
                </Text>
                <div className="flex justify-center py-4">
                  <div
                    className={cx(
                      'flex h-16 w-32 items-center justify-center rounded-panel bg-surface-raised text-xs',
                      SHADOW_CLASS[level],
                    )}
                  >
                    shadow-{level}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Text role="supporting">
            Themed like colour: dark surfaces need a darker, less transparent shadow to read at all,
            so the same names carry different values per theme — switch the theme toolbar above to
            see it.
          </Text>
        </Section>
      </div>
    )
  },
}
