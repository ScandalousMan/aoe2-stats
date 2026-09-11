import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { Button } from '../Button'
import { ErrorState } from './index'

const meta: Meta<typeof ErrorState> = {
  id: 'primitives-errorstate',
  title: 'Primitives/Feedback & status/ErrorState',
  component: ErrorState,
}

export default meta
type Story = StoryObj<typeof ErrorState>

export const Default: Story = {
  args: {
    heading: 'We could not load this match history',
    explanation: 'Something went wrong on our side. Your data is safe — try again.',
    action: <Button variant="secondary">Try again</Button>,
  },
}

// The retry stays enabled after a failed attempt (FR-024): a retry that greys itself out after
// failing is how a recoverable error becomes permanent.
export const RetryFailedStaysEnabled: Story = {
  render: () => {
    function RetryDemo() {
      const [attempts, setAttempts] = useState(1)
      return (
        <ErrorState
          heading="We could not load this match history"
          explanation={`Something went wrong on our side. This was attempt ${attempts}.`}
          action={
            <Button variant="secondary" onClick={() => setAttempts((n) => n + 1)}>
              Try again
            </Button>
          }
        />
      )
    }
    return <RetryDemo />
  },
}

export const RetryInProgress: Story = {
  args: {
    heading: 'We could not load this match history',
    explanation: 'Something went wrong on our side. Your data is safe — try again.',
    action: (
      <Button variant="secondary" loading loadingLabel="Trying again…">
        Try again
      </Button>
    ),
  },
}

// The one recovery case with no action: an explicit sentence stands in for the button, and the
// absence is never silent (FR-024).
export const RecoveryNone: Story = {
  args: {
    heading: "This match's replay is gone",
    explanation:
      "The replay left Microsoft's servers before archival could capture it, and originals are never re-requested after that window closes.",
    recovery: 'none',
    recoveryText: "Nothing can retrieve it — this match's stats are still available above.",
  },
}

export const WithTechnicalDetail: Story = {
  args: {
    heading: 'We could not start that download',
    explanation: 'The archive service did not respond in time. Try again in a moment.',
    action: <Button variant="secondary">Try again</Button>,
    technicalDetail: 'reference: replay-download-504-a1b2c3d4e5f6',
  },
}

// Announced on mount (`role="alert"`) because this replaces content after an interaction, rather
// than being the initial render of a failed route (structural-tier.md §13).
export const AnnouncedAfterAnInteraction: Story = {
  args: {
    heading: 'We could not update your favourites',
    explanation: 'The change did not save. Try again.',
    action: <Button variant="secondary">Try again</Button>,
    announce: true,
  },
}

// Captured beside an `EmptyState` of the same region, the two must be unmistakably different: one
// has a stripe and a recovery, the other has neither.
export const BesideAnEmptyState: Story = {
  render: () => (
    <div className="grid grid-cols-2 gap-8">
      <div>
        <p className="mb-2 font-sans text-xs text-text-secondary">Nothing here (EmptyState)</p>
        <p className="type-display text-xl font-semibold text-text-primary">No matches yet</p>
        <p className="type-body text-md mt-2 text-text-secondary">
          This profile has not played a ranked match yet.
        </p>
      </div>
      <div>
        <p className="mb-2 font-sans text-xs text-text-secondary">
          We could not find out (ErrorState)
        </p>
        <ErrorState
          heading="We could not load this match history"
          explanation="Something went wrong on our side. Try again."
          action={<Button variant="secondary">Try again</Button>}
        />
      </div>
    </div>
  ),
}

// The caller defect this component exists to make impossible to ship silently: with no heading,
// nothing renders at all — a failure with no words is worse than a blank region.
export const NoHeadingRendersNothing: Story = {
  render: () => (
    <div>
      <p className="mb-2 font-sans text-xs text-text-secondary">Nothing renders below this line.</p>
      <ErrorState heading="" explanation="" recovery="none" recoveryText="" />
    </div>
  ),
}

// structural-tier.md §13 "hover / focus-visible / active — none of its own; the recovery action
// carries `Button`'s."
export const HoverFocusActiveNotApplicable: Story = {
  render: () => (
    <div className="flex flex-col gap-2">
      <p className="type-supporting text-sm text-text-secondary">
        An error state has no hover, focus or active rendering of its own — the recovery action
        inside it carries `Button`'s.
      </p>
      <ErrorState
        heading="We could not load this match history"
        explanation="Something went wrong on our side. Your data is safe — try again."
        action={<Button variant="secondary">Try again</Button>}
      />
    </div>
  ),
}

// §13 "disabled — never, and this is the state FR-024 is about: the control that caused the
// failure returns to being pressable." See `RetryFailedStaysEnabled` above for the same fact
// demonstrated by an actual retry.
export const DisabledNotApplicable: Story = {
  render: () => (
    <p className="type-supporting text-sm text-text-secondary">
      An error state is never disabled — the retry that caused the failure always returns to being
      pressable, never greyed out after failing.
    </p>
  ),
}
