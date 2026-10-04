// T693 (third remediation of #114): the runtime pass's in-page reader, `inspect` in
// `tests/visual/state-coverage-runtime.ts`, against REAL React. `tests/visual/state-coverage-runtime-
// probe.spec.ts` drives it with synthetic fibers, which carry no alternate and so cannot show what
// this file shows: React writes `__reactFiber$` on a DOM node once, at creation. After an update the
// node's fiber may be the alternate of the one in the committed tree, and climbing `.return` from it
// reaches the alternate HostRoot — the PREVIOUS render's tree, with the previous render's props. A
// reader that descended from there recorded a stale variant, a stale size and stale mounts.
import { act, render } from '@testing-library/react'
import { memo, useState } from 'react'
import { createPortal } from 'react-dom'
import { describe, expect, it } from 'vitest'
import { STAMP_ATTRIBUTE } from '../../.storybook/source-stamp-attribute.cjs'
import {
  describeElement,
  describeFiles,
  describeMounts,
} from '../../../../tests/visual/state-coverage-runtime'
import type { TrackedRegistry } from '../../../../tests/visual/state-coverage-runtime'

const BUTTON_STAMP = 'packages/design-system/src/primitives/Button/index.tsx:10'
const LINK_STAMP = 'packages/design-system/src/primitives/Link/index.tsx:20'

function Button({ disabled }: { variant?: string; disabled?: boolean }) {
  return (
    <button type="button" disabled={disabled} {...{ [STAMP_ATTRIBUTE]: BUTTON_STAMP }}>
      go
    </button>
  )
}
function Link(_props: { variant?: string }) {
  return <a href="#x" {...{ [STAMP_ATTRIBUTE]: LINK_STAMP }} />
}
// Re-renders never reach it: its fibers keep `return` pointers into whichever parent they had.
const FrozenLink = memo(function FrozenLink() {
  return <Link variant="standalone" />
})

const registry: TrackedRegistry = {
  Button: {
    component: Button,
    directory: 'packages/design-system/src/primitives/Button/',
    axes: { variant: 'secondary' },
  },
  Link: {
    component: Link,
    directory: 'packages/design-system/src/primitives/Link/',
    axes: { variant: 'inline' },
  },
}
const opts = { registry, stampAttribute: STAMP_ATTRIBUTE }

let setStep: (step: number) => void = () => {}
function Host() {
  const [step, set] = useState(0)
  setStep = set
  return (
    <div>
      <Button variant={`v${step}`} disabled={step === 2} />
      <FrozenLink />
    </div>
  )
}

const disabledAtStep = (step: number) => (step === 2 ? [BUTTON_STAMP] : [])

describe('the fiber reader reads the committed tree, never the previous commit’s', () => {
  it.each([0, 1, 2, 3, 4])(
    'after %i updates: mounts carry the current variant, and disabledAt follows it',
    (updates) => {
      const { container } = render(<Host />)
      for (let step = 1; step <= updates; step += 1) act(() => setStep(step))
      expect(describeMounts(container, opts)).toEqual([
        {
          component: 'Button',
          variant: `v${updates}`,
          size: null,
          disabledAt: disabledAtStep(updates),
        },
        { component: 'Link', variant: 'standalone', size: null, disabledAt: [] },
      ])
    },
  )

  it.each([0, 1, 2, 3, 4])(
    'after %i updates: the placing instance carries the current variant, and disabledAt follows it',
    (updates) => {
      const { container } = render(<Host />)
      for (let step = 1; step <= updates; step += 1) act(() => setStep(step))
      const button = container.querySelector('button') as Element
      expect(describeElement(button, opts)).toEqual({
        stamp: BUTTON_STAMP,
        placedBy: {
          component: 'Button',
          variant: `v${updates}`,
          size: null,
          disabledAt: disabledAtStep(updates),
        },
      })
    },
  )

  it('an element inside a subtree no update reached is placed by the instance above it, at its own props', () => {
    const { container } = render(<Host />)
    for (let step = 1; step <= 3; step += 1) act(() => setStep(step))
    const anchor = container.querySelector('a') as Element
    expect(describeElement(anchor, opts)).toEqual({
      stamp: LINK_STAMP,
      placedBy: { component: 'Link', variant: 'standalone', size: null, disabledAt: [] },
    })
  })

  it('an element React has since unmounted was placed by nobody; a story root with nothing mounted records nothing', () => {
    const { container, unmount } = render(<Host />)
    const button = container.querySelector('button') as Element
    expect(describeElement(button, opts).placedBy).not.toBeNull()
    unmount()
    expect(describeElement(button, opts)).toEqual({ stamp: BUTTON_STAMP, placedBy: null })
    expect(describeMounts(document.createElement('div'), opts)).toEqual([])
  })
})

describe('describeFiles reads the whole document, portals included', () => {
  it('lists the file of an element a portal rendered outside the story root', () => {
    const PORTAL_STAMP = 'packages/design-system/src/primitives/Menu/index.tsx:300'
    function WithPortal() {
      return (
        <div>
          <Button />
          {createPortal(<div {...{ [STAMP_ATTRIBUTE]: PORTAL_STAMP }} />, document.body)}
        </div>
      )
    }
    const { container } = render(<WithPortal />)
    expect(container.querySelector(`[${STAMP_ATTRIBUTE}="${PORTAL_STAMP}"]`)).toBeNull()
    expect(describeFiles(container, opts)).toEqual([
      'packages/design-system/src/primitives/Button/index.tsx',
      'packages/design-system/src/primitives/Menu/index.tsx',
    ])
  })
})
