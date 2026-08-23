import { afterEach, describe, expect, it, vi } from 'vitest'
import { replayDownloadPath, triggerReplayDownload } from './api'

describe('replayDownloadPath', () => {
  it('builds the same-origin download path for a game id', () => {
    expect(replayDownloadPath(700_800_900)).toBe('/api/replays/700800900/download')
  })
})

describe('triggerReplayDownload', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('navigates the current tab to the download endpoint, same-origin, not a signed bucket URL', () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })

    triggerReplayDownload(700_800_900)

    expect(assign).toHaveBeenCalledExactlyOnceWith('/api/replays/700800900/download')
  })
})
