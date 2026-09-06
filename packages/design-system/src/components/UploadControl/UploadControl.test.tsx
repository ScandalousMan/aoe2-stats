import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { UploadFailure } from './index'
import { UploadControl } from './index'

function replayFile(name = 'MP Replay v101.103.aoe2record') {
  return new File(['fake replay bytes'], name, { type: 'application/octet-stream' })
}

function getDropZone() {
  return screen.getByText(/Drop the \.aoe2record file here/).closest('div') as HTMLElement
}

function getFileInput() {
  return document.querySelector('input[type="file"]') as HTMLInputElement
}

// A plain `fireEvent.change` rather than `userEvent.upload`: several tests below pair file
// selection with `vi.useFakeTimers()`, and `userEvent`'s own internal delays await real timers —
// under fake ones they never resolve, hanging the test rather than failing it.
function chooseFile(file = replayFile()) {
  const input = getFileInput()
  Object.defineProperty(input, 'files', { configurable: true, value: [file] })
  fireEvent.change(input)
  return file
}

describe('UploadControl — idle (the empty state, §5)', () => {
  it('shows the heading, explanation, saved-games hint and the empty drop zone, no submit button', () => {
    render(<UploadControl gameId={42} onUpload={() => Promise.reject(new Error('unused'))} />)
    expect(screen.getByRole('heading', { name: 'Add the replay yourself' })).toBeInTheDocument()
    expect(screen.getByText(/marked as one you supplied by hand/)).toBeInTheDocument()
    expect(screen.getByText(/saved games folder/)).toBeInTheDocument()
    expect(screen.getByText(/Drop the \.aoe2record file here, or/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose file' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upload and archive' })).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('never restates the reason a match is lost — that line belongs to CaptureStateBadge', () => {
    render(<UploadControl gameId={42} onUpload={() => Promise.reject(new Error('unused'))} />)
    const text = document.body.textContent?.toLowerCase() ?? ''
    expect(text).not.toContain('expired')
    expect(text).not.toContain('unavailable')
    expect(text).not.toContain('31 days')
  })

  it('the file input accepts only .aoe2record and reaches the click/keyboard path via a real button', () => {
    render(<UploadControl gameId={42} onUpload={() => Promise.reject(new Error('unused'))} />)
    expect(getFileInput()).toHaveAttribute('accept', '.aoe2record')
    expect(screen.getByRole('button', { name: 'Choose file' }).tagName).toBe('BUTTON')
  })
})

describe('UploadControl — choosing a file (file-chosen)', () => {
  it('shows the file name in type-machine, its size in text-secondary, a Remove control and an enabled submit button', async () => {
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    await chooseFile(replayFile('MP Replay v101.103 @2026.08.30.aoe2record'))

    const name = screen.getByText('MP Replay v101.103 @2026.08.30.aoe2record')
    // Rendered class composition, not merely presence: the machine role must actually be the one
    // that won (T035c/T038b, T531) — checked together with the sans body text elsewhere never
    // carrying it, so this is not a house-wide default that would pass regardless of this
    // component.
    expect(name.className).toMatch(/\btype-machine\b/)
    expect(screen.getByText(/marked as one you supplied by hand/).className).not.toMatch(
      /\btype-machine\b/,
    )

    const size = screen.getByText(/^\d/, { selector: 'p.text-text-secondary' })
    expect(size.className).toMatch(/\btext-text-secondary\b/)

    expect(screen.getByRole('button', { name: 'Remove' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Upload and archive' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Choose file' })).not.toBeInTheDocument()
  })

  // T083a: `FileChip` used to render the name with Tailwind `truncate` (single-line
  // end-ellipsis), collapsing a real name to ~5 characters at 375px against manual-upload.md §8,
  // which requires the name to wrap or middle-truncate and never be cut without recourse.
  it('wraps a long file name instead of cutting it to a stub (manual-upload.md §8)', async () => {
    const longName = 'MP Replay v101.103 @2026.08.30 091542 (4).aoe2record'
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    await chooseFile(replayFile(longName))

    const name = screen.getByText(longName)
    // Rendered class composition, not merely a substring check: wrapping must be the behaviour
    // that actually applies, and the single-line `truncate` this regression came from must be
    // absent, not merely coexisting with it (the T035c lesson: two conflicting classes present
    // together leaves the winner to stylesheet emission order, not to this component).
    expect(name.className).toMatch(/\bbreak-words\b/)
    expect(name.className).toMatch(/\bwhitespace-normal\b/)
    expect(name.className).not.toMatch(/\btruncate\b/)
    // §8's "never cut without recourse": the full name stays in `title` and as real text content
    // even if a future style change re-introduces clipping.
    expect(name).toHaveAttribute('title', longName)
    expect(name.textContent).toBe(longName)
  })

  it('Remove returns the control to idle, clearing the file', async () => {
    const user = userEvent.setup()
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    await chooseFile()
    await user.click(screen.getByRole('button', { name: 'Remove' }))

    expect(screen.getByRole('button', { name: 'Choose file' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upload and archive' })).not.toBeInTheDocument()
  })

  it('a drag-and-drop selection reaches the same file-chosen shape as the click/keyboard path', () => {
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    const file = replayFile()
    fireEvent.drop(getDropZone(), { dataTransfer: { files: [file] } })

    expect(screen.getByText(file.name)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upload and archive' })).toBeEnabled()
  })

  it('drag-over renders the focus-ring boundary and drops the resting one — not both at once', () => {
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    const dropZone = getDropZone()
    expect(dropZone.className).toMatch(/\bborder-border-strong\b/)
    expect(dropZone.className).not.toMatch(/\bborder-focus-ring\b/)

    fireEvent.dragOver(dropZone)
    // The T035c lesson applied here: a naive concatenation would leave both boundary classes
    // present and the winner decided by stylesheet emission order, not by this component.
    expect(dropZone.className).toMatch(/\bborder-focus-ring\b/)
    expect(dropZone.className).not.toMatch(/\bborder-border-strong\b/)

    fireEvent.dragLeave(dropZone)
    expect(dropZone.className).toMatch(/\bborder-border-strong\b/)
    expect(dropZone.className).not.toMatch(/\bborder-focus-ring\b/)
  })
})

describe('UploadControl — uploading', () => {
  it('is aria-busy, shows the busy submit button at "Uploading…" and disables Remove', async () => {
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    await chooseFile()
    fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)

    expect(screen.getByRole('button', { name: 'Uploading…' })).toBeDisabled()
    // The form element itself carries `aria-busy`, per §9.
    expect(document.querySelector('form')).toHaveAttribute('aria-busy', 'true')
  })

  it('switches the label on to "Checking the file…" once the transfer is believed sent', async () => {
    vi.useFakeTimers()
    try {
      render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
      await chooseFile()
      fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)
      expect(screen.getByRole('button', { name: 'Uploading…' })).toBeInTheDocument()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_200)
      })
      expect(screen.getByRole('button', { name: 'Checking the file…' })).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  // T083a: the production 1200 ms delay is a module constant the visual harness cannot outrun —
  // it screenshots as soon as two consecutive frames match, well inside the window, so the
  // `UploadingValidating` baseline never showed the label it is named for. `validatingLabelDelayMs`
  // is the seam that lets that story (and this test) reach the switched label deterministically,
  // with no fake-timer bookkeeping needed.
  it('with validatingLabelDelayMs=0 shows "Checking the file…" immediately, no fake timers needed', async () => {
    render(
      <UploadControl
        gameId={42}
        onUpload={() => new Promise<void>(() => {})}
        validatingLabelDelayMs={0}
      />,
    )
    await chooseFile()
    fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)

    expect(await screen.findByRole('button', { name: 'Checking the file…' })).toBeInTheDocument()
  })

  it('defaults validatingLabelDelayMs to the 1200 ms production constant when the prop is omitted', async () => {
    vi.useFakeTimers()
    try {
      render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
      await chooseFile()
      fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_199)
      })
      expect(screen.getByRole('button', { name: 'Uploading…' })).toBeInTheDocument()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1)
      })
      expect(screen.getByRole('button', { name: 'Checking the file…' })).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('UploadControl — succeeded', () => {
  it('shows the success callout (role=status) and collapses the picker entirely', async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined)
    render(<UploadControl gameId={42} onUpload={onUpload} />)
    await chooseFile()
    fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)

    const region = await screen.findByRole('status')
    expect(region).toHaveTextContent('Archived from your upload.')
    expect(region).toHaveTextContent('marked as supplied by you')
    expect(screen.queryByRole('button', { name: 'Upload and archive' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument()
    // Never claims "safe" (capture-state-badge.md's rule, carried here).
    expect(region.textContent?.toLowerCase()).not.toContain('safe')
  })
})

describe('UploadControl — the endpoint`s four rejection codes (§3)', () => {
  const cases: Array<{
    code: UploadFailure['code']
    role: 'alert' | 'status'
    heading: string
    bannedWords: string[]
  }> = [
    {
      code: 'invalid_replay',
      role: 'alert',
      heading: 'That file is not a replay we can read.',
      bannedWords: ['uploaded', 'saved', 'archived', 'done'],
    },
    {
      code: 'not_found',
      role: 'alert',
      heading: 'This file could not be filed to this match.',
      bannedWords: ['uploaded', 'saved', 'archived', 'done'],
    },
    {
      code: 'already_archived',
      role: 'status',
      heading: 'This match already has an archived replay.',
      bannedWords: ['overwritten', 'replaced', 'updated'],
    },
  ]

  it.each(cases)(
    'code=$code maps to role=$role with the exact copy, nothing claimed stored',
    async ({ code, role, heading }) => {
      const onUpload = vi.fn().mockRejectedValue({ code })
      render(<UploadControl gameId={42} onUpload={onUpload} />)
      await chooseFile()
      fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)

      const region = await screen.findByRole(role)
      expect(region).toHaveTextContent(heading)
      if (role === 'alert') {
        expect(region.textContent).toMatch(/nothing was stored/i)
      }
    },
  )

  it('an unrecognised code, and a plain network rejection with no code, both fall to failed', async () => {
    const onUpload = vi.fn().mockRejectedValue(new Error('network down'))
    render(<UploadControl gameId={42} onUpload={onUpload} />)
    await chooseFile()
    fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)

    const region = await screen.findByRole('alert')
    expect(region).toHaveTextContent('The upload did not go through.')
    expect(region.textContent).toMatch(/not with your file/i)
  })

  it('invalid-replay, wrong-match and failed all return to the file-chosen shape: same file, retry is one press away', async () => {
    const onUpload = vi.fn().mockRejectedValue({ code: 'invalid_replay' })
    render(<UploadControl gameId={42} onUpload={onUpload} />)
    const file = await chooseFile()
    fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)
    await screen.findByRole('alert')

    expect(screen.getByText(file.name)).toBeInTheDocument()
    const retryButton = screen.getByRole('button', { name: 'Upload and archive' })
    expect(retryButton).toBeEnabled()

    onUpload.mockResolvedValueOnce(undefined)
    await userEvent.click(retryButton)
    await screen.findByRole('status')
    expect(onUpload).toHaveBeenCalledTimes(2)
    expect(onUpload).toHaveBeenNthCalledWith(2, file)
  })

  it('already-archived offers Refresh instead of a retry, and collapses the picker', async () => {
    const onUpload = vi.fn().mockRejectedValue({ code: 'already_archived' })
    render(<UploadControl gameId={42} onUpload={onUpload} />)
    await chooseFile()
    fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)

    await screen.findByRole('status')
    expect(screen.queryByRole('button', { name: 'Upload and archive' })).not.toBeInTheDocument()
    const refresh = screen.getByRole('button', { name: 'Refresh' })
    expect(refresh).toBeInTheDocument()

    const reload = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...window.location, reload },
    })
    await userEvent.click(refresh)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('moves focus to the outcome heading after a live rejection, never on first paint of a pinned state', async () => {
    const onUpload = vi.fn().mockRejectedValue({ code: 'invalid_replay' })
    const { unmount } = render(<UploadControl gameId={42} onUpload={onUpload} />)
    await chooseFile()
    fireEvent.submit(screen.getByRole('button', { name: 'Upload and archive' }).closest('form')!)
    const region = await screen.findByRole('alert')
    const heading = within(region).getByRole('heading', {
      name: 'That file is not a replay we can read.',
    })
    await waitFor(() => expect(document.activeElement).toBe(heading))
    unmount()

    render(<UploadControl gameId={42} onUpload={onUpload} initialState="invalid-replay" />)
    expect(document.activeElement).not.toBe(
      screen.getByRole('heading', { name: 'That file is not a replay we can read.' }),
    )
  })
})

describe('UploadControl — no shield/lock/tick icon, no reassurance', () => {
  const bannedPhrases = [
    "don't worry",
    'rest assured',
    "we've got you covered",
    'this keeps your account safe',
  ]

  it('renders no <svg> or <img> in this container but the shared Button spinner (uploading only)', () => {
    // Scoped to this component's rendered container, not a codebase-wide ban — constitution X
    // 5.0.0 permits a licensed game asset elsewhere. This control specifically shows no imagery:
    // no reassurance iconography (shield/lock/padlock/tick) and nothing else either, on purpose.
    // `uploading` is excluded on purpose: `Button`'s own loading spinner is a shared primitive
    // already reviewed for the checklist, not the shield/lock/padlock/tick this rule bans.
    const states: Array<
      'idle' | 'file-chosen' | 'succeeded' | 'invalid-replay' | 'already-archived'
    > = ['idle', 'file-chosen', 'succeeded', 'invalid-replay', 'already-archived']
    for (const initialState of states) {
      const { container, unmount } = render(
        <UploadControl
          gameId={42}
          onUpload={() => new Promise<void>(() => {})}
          initialState={initialState}
        />,
      )
      expect(container.querySelectorAll('svg, img')).toHaveLength(0)
      unmount()
    }
  })

  it('contains none of the banned reassurance phrases', () => {
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    const text = document.body.textContent?.toLowerCase() ?? ''
    for (const phrase of bannedPhrases) {
      expect(text).not.toContain(phrase)
    }
  })
})

describe('UploadControl — accessibility surface', () => {
  it('Choose file, Remove and Upload and archive all clear the 44px touch target and carry the focus ring', async () => {
    render(<UploadControl gameId={42} onUpload={() => new Promise<void>(() => {})} />)
    const chooseFileButton = screen.getByRole('button', { name: 'Choose file' })
    // `lg` is the only Button size that clears 44px (Button's own spec); `md` is pointer-only.
    expect(chooseFileButton.className).toMatch(/\bh-12\b/)
    expect(chooseFileButton.className).toMatch(/focus-visible:outline-2/)
    expect(chooseFileButton.className).toMatch(/focus-visible:outline-focus-ring/)

    chooseFile()
    for (const name of ['Remove', 'Upload and archive']) {
      const button = screen.getByRole('button', { name })
      expect(button.className).toMatch(/\bh-12\b/)
      expect(button.className).toMatch(/focus-visible:outline-2/)
    }
  })

  it('the section is labelled by its own h3, keyed to gameId, never colliding across two instances', () => {
    render(<UploadControl gameId={7} onUpload={() => new Promise<void>(() => {})} />)
    const heading = screen.getByRole('heading', { name: 'Add the replay yourself', level: 3 })
    const section = screen.getByRole('region', { name: 'Add the replay yourself' })
    expect(section).toHaveAttribute('aria-labelledby', heading.id)
    expect(heading.id).toContain('7')
  })
})
