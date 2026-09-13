import type { Meta, StoryObj } from '@storybook/react-vite'
import { AccountErasurePanel, ErasedScreen } from './index'

const meta: Meta<typeof AccountErasurePanel> = {
  id: 'screens-accounterasurepanel',
  title: 'Screens/Account & privacy/AccountErasurePanel',
  component: AccountErasurePanel,
  parameters: {
    docs: {
      description: {
        component: `Lets a signed-in user permanently destroy their account and everything attached to it, understanding before they confirm what survives.`,
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof AccountErasurePanel>

// `initialState` renders one fixed frame without driving real promises (privacy-data-rights.md
// §3) — the callbacks below are never actually exercised by these stories.
const noopHandlers = {
  onRequestConfirmation: () => new Promise<{ confirmationToken: string }>(() => {}),
  onErase: () => new Promise<void>(() => {}),
}

export const Idle: Story = {
  name: 'default — the irreversible lede and both consequence groups, before any dialog',
  args: { ...noopHandlers, initialState: 'idle' },
}

// privacy-data-rights.md §5 "loading — ... `minting` shows the `EraseButton` busy while the token
// is fetched" — the phase before the dialog opens, distinct from `erasing` below.
export const Minting: Story = {
  name: 'minting — the erase button busy while the confirmation token is fetched',
  args: { ...noopHandlers, initialState: 'minting' },
}

export const Confirming: Story = {
  name: 'confirming — the dialog open, checkbox unchecked, confirm disabled',
  args: { ...noopHandlers, initialState: 'confirming' },
}

export const ConfirmationExpired: Story = {
  name: 'confirmation expired — the 403 from POST, offering to confirm again',
  args: { ...noopHandlers, initialState: 'confirmation-expired' },
}

export const Failed: Story = {
  name: 'failed — the dialog stays open, confirm re-enabled, nothing erased',
  args: { ...noopHandlers, initialState: 'failed' },
}

export const Erasing: Story = {
  name: 'erasing — the POST in flight, confirm busy, cancel disabled',
  args: { ...noopHandlers, initialState: 'erasing' },
}

export const Erased: Story = {
  name: 'terminal — ErasedScreen, no "sign back in" affordance',
  render: () => <ErasedScreen homeHref="/privacy-notice" />,
}

// README's gap register row 7 (H4): `ErasedScreen`'s privacy-notice link is a local anchor styled
// directly inside this screen (`index.tsx`), not a `Button` instance and not owned by any dialog or
// checkbox — the same shape as `ThirdPartyObjectionForm`'s own inline link, which carries this same
// `Hover`/`FocusVisible`/`Active` trio under a link clip (T591's "all three or none"). Not
// `PrivacyNotice`: its trio forces and clips `role: 'link', nth: 0`, the first table-of-contents
// entry, not its inline-link recipe (`inlineLinkClasses`, `PrivacyNotice/index.tsx`), which has no
// state frame of its own (README's gap register row 8, T594). `role: 'link'` is unambiguous here:
// `ErasedScreen` renders exactly one anchor.
const erasedScreenLinkClip = { parts: [{ role: 'link' as const }], pad: '2' }

export const ErasedScreenHover: Story = {
  name: 'terminal — hover on the ErasedScreen privacy-notice link',
  render: () => <ErasedScreen homeHref="/privacy-notice" />,
  parameters: {
    visualForceState: { state: 'hover', role: 'link' },
    visualCaptureClip: erasedScreenLinkClip,
  },
}

export const ErasedScreenFocusVisible: Story = {
  name: 'terminal — focus-visible on the ErasedScreen privacy-notice link',
  render: () => <ErasedScreen homeHref="/privacy-notice" />,
  parameters: {
    visualForceState: { state: 'focus-visible', role: 'link' },
    visualCaptureClip: erasedScreenLinkClip,
  },
}

export const ErasedScreenActive: Story = {
  name: 'terminal — active (pressed) on the ErasedScreen privacy-notice link',
  render: () => <ErasedScreen homeHref="/privacy-notice" />,
  parameters: {
    visualForceState: { state: 'active', role: 'link' },
    visualCaptureClip: erasedScreenLinkClip,
  },
}

// privacy-data-rights.md §5 "hover / focus-visible / active — owned by the `Button`s, the
// `DownloadLink`, the `ErasedScreen`'s privacy-notice link, the `Dialog`'s actions and the
// `Acknowledgement` checkbox; the sections themselves are not interactive." This story defers the
// states of the `Button` this screen renders directly (`Erase my account`) and of the `Dialog`'s own
// primary/secondary actions, each a `Button` instance covered by `Button.stories.tsx`. It does not
// defer the acknowledgement checkbox: a plain `<input type="checkbox">` styled locally in this file
// (`focusRing`, `index.tsx`), owned by no component with its own stories. Its focus-visible is not
// yet captured anywhere; that capture is owed by T594 (README's gap register row 8). Corrected
// (README's gap register row 7/H4): it used to defer `ErasedScreen`'s link too, a local anchor
// styled inside this same file that none of those components own. That link's own hover,
// focus-visible and active are not deferred to anyone; they are `ErasedScreenHover`,
// `ErasedScreenFocusVisible` and `ErasedScreenActive` above, judged against §5's own paragraph on
// that link.
export const HoverFocusActiveNotApplicable: Story = {
  render: (args) => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        The panel's own sections are not interactive — hover, focus and active belong to the buttons
        and the dialog's actions, each already covered by their own components' stories. Two things
        are not covered here: the acknowledgement checkbox is a local control of this screen whose
        focus-visible no story captures yet (owed by task T594), and `ErasedScreen`'s privacy-notice
        link is a local anchor styled inside this screen — see `ErasedScreenHover`,
        `ErasedScreenFocusVisible` and `ErasedScreenActive` above for its own coverage.
      </p>
      <AccountErasurePanel {...args} />
    </div>
  ),
  args: { ...noopHandlers, initialState: 'idle' },
}

// §5 "empty — not applicable — it is a single irreversible action, not a collection; there is no
// 'nothing yet' fact for an empty state to represent, and this is stated rather than omitted."
export const EmptyNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      This is a single irreversible action, not a collection — there is no "nothing yet" fact for an
      empty state to represent.
    </p>
  ),
}
