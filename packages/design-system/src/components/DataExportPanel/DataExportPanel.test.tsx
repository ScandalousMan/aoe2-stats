import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DataExportPanel } from './index'

describe('DataExportPanel — idle (the empty state, §5)', () => {
  it('shows the contents statement and the request button, with no progress or ready region', () => {
    render(
      <DataExportPanel
        onRequestExport={() => Promise.reject(new Error('unused'))}
        onPollExport={() => Promise.reject(new Error('unused'))}
      />,
    )
    expect(screen.getByText(/We build a single archive/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export my data' })).toBeEnabled()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /download/i })).not.toBeInTheDocument()
  })

  it('never shows a "your previous exports" list — the API has none', () => {
    render(
      <DataExportPanel
        onRequestExport={() => Promise.reject(new Error('unused'))}
        onPollExport={() => Promise.reject(new Error('unused'))}
      />,
    )
    expect(screen.queryByText(/previous export/i)).not.toBeInTheDocument()
  })
})

describe('DataExportPanel — the request/poll flow', () => {
  it('requests, polls once and shows the ready region when the job completes immediately', async () => {
    const user = userEvent.setup()
    const onRequestExport = vi.fn().mockResolvedValue({ id: 'job-1' })
    const onPollExport = vi
      .fn()
      .mockResolvedValue({ status: 'completed', downloadUrl: '/archive.zip' })

    render(<DataExportPanel onRequestExport={onRequestExport} onPollExport={onPollExport} />)
    await user.click(screen.getByRole('button', { name: 'Export my data' }))

    await waitFor(() => expect(screen.getByText('Your export is ready.')).toBeInTheDocument())
    expect(onRequestExport).toHaveBeenCalledTimes(1)
    expect(onPollExport).toHaveBeenCalledWith('job-1')
    const link = screen.getByRole('link', { name: 'Download the archive' })
    expect(link).toHaveAttribute('href', '/archive.zip')
    expect(link).toHaveAttribute('download')
    expect(screen.getByText(/This link stops working after a short while/)).toBeInTheDocument()
  })

  it('disables and shows the loading label on the request button while requesting/preparing', async () => {
    let resolveRequest: (value: { id: string }) => void = () => {}
    const onRequestExport = vi.fn(
      () =>
        new Promise<{ id: string }>((resolve) => {
          resolveRequest = resolve
        }),
    )
    const onPollExport = vi.fn().mockResolvedValue({ status: 'completed', downloadUrl: '/a.zip' })

    const user = userEvent.setup()
    render(<DataExportPanel onRequestExport={onRequestExport} onPollExport={onPollExport} />)
    await user.click(screen.getByRole('button', { name: 'Export my data' }))

    expect(screen.getByRole('button', { name: 'Preparing your export…' })).toBeDisabled()
    resolveRequest({ id: 'job-2' })
    await waitFor(() => expect(screen.getByText('Your export is ready.')).toBeInTheDocument())
  })

  it('re-polls while the job is queued and settles once it completes', async () => {
    vi.useFakeTimers()
    const onRequestExport = vi.fn().mockResolvedValue({ id: 'job-3' })
    const onPollExport = vi
      .fn()
      .mockResolvedValueOnce({ status: 'queued' })
      .mockResolvedValueOnce({ status: 'completed', downloadUrl: '/queued-then-ready.zip' })

    render(<DataExportPanel onRequestExport={onRequestExport} onPollExport={onPollExport} />)
    await act(async () => {
      screen.getByRole('button', { name: 'Export my data' }).click()
    })

    expect(screen.getByText('Your export is being prepared.')).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000)
    })
    expect(screen.getByText('Your export is ready.')).toBeInTheDocument()

    expect(onPollExport).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })
})

describe('DataExportPanel — failure', () => {
  it('shows the failure region when the request itself fails, and the button returns to enabled', async () => {
    const user = userEvent.setup()
    const onRequestExport = vi.fn().mockRejectedValue(new Error('network'))
    const onPollExport = vi.fn()

    render(<DataExportPanel onRequestExport={onRequestExport} onPollExport={onPollExport} />)
    await user.click(screen.getByRole('button', { name: 'Export my data' }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent('We could not build your export')
    expect(screen.getByRole('button', { name: 'Export my data' })).toBeEnabled()
    expect(onPollExport).not.toHaveBeenCalled()
  })

  it('shows the failure region when polling fails, without claiming success', async () => {
    const user = userEvent.setup()
    const onRequestExport = vi.fn().mockResolvedValue({ id: 'job-4' })
    const onPollExport = vi.fn().mockRejectedValue(new Error('network'))

    render(<DataExportPanel onRequestExport={onRequestExport} onPollExport={onPollExport} />)
    await user.click(screen.getByRole('button', { name: 'Export my data' }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.queryByText('Your export is ready.')).not.toBeInTheDocument()
  })

  it('retrying from the failed state re-requests the export', async () => {
    const user = userEvent.setup()
    const onRequestExport = vi
      .fn()
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ id: 'job-5' })
    const onPollExport = vi
      .fn()
      .mockResolvedValue({ status: 'completed', downloadUrl: '/retry.zip' })

    render(<DataExportPanel onRequestExport={onRequestExport} onPollExport={onPollExport} />)
    await user.click(screen.getByRole('button', { name: 'Export my data' }))
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getByText('Your export is ready.')).toBeInTheDocument())
    expect(onRequestExport).toHaveBeenCalledTimes(2)
  })
})

describe('DataExportPanel — initialState (stories only)', () => {
  it('renders the ready frame without calling either callback', () => {
    const onRequestExport = vi.fn()
    const onPollExport = vi.fn()
    render(
      <DataExportPanel
        onRequestExport={onRequestExport}
        onPollExport={onPollExport}
        initialState="ready"
      />,
    )
    expect(screen.getByText('Your export is ready.')).toBeInTheDocument()
    expect(onRequestExport).not.toHaveBeenCalled()
    expect(onPollExport).not.toHaveBeenCalled()
  })

  it('renders the preparing frame with a skeleton, not a placeholder download link', () => {
    render(
      <DataExportPanel
        onRequestExport={() => Promise.reject(new Error('unused'))}
        onPollExport={() => Promise.reject(new Error('unused'))}
        initialState="preparing"
      />,
    )
    expect(screen.getByText('Your export is being prepared.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /download/i })).not.toBeInTheDocument()
  })
})
