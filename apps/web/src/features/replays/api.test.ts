import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from '../../lib/api'
import {
  replayDownloadPath,
  triggerReplayDownload,
  triggerReplayPointOfViewDownload,
  uploadReplay,
  uploadReplayPath,
} from './api'

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

describe('triggerReplayPointOfViewDownload', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('navigates the current tab to the server-minted download_path, verbatim', () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })

    triggerReplayPointOfViewDownload('/api/matches/700800900/replay/196240')

    expect(assign).toHaveBeenCalledExactlyOnceWith('/api/matches/700800900/replay/196240')
  })
})

describe('uploadReplayPath', () => {
  it('builds the same-origin upload path for a game id', () => {
    expect(uploadReplayPath(700_800_900)).toBe('/api/replays/700800900/upload')
  })
})

// T084: `manual-upload.md`'s four outcomes, mapped from the endpoint's own response the way every
// other route in this app maps them — `uploadReplay` rejects with `ApiRequestError`, carrying
// `.code`, which `UploadControl`'s `stateForFailure` reads directly.

describe('uploadReplay', () => {
  function jsonResponse(body: unknown, status: number) {
    return {
      status,
      ok: status >= 200 && status < 300,
      statusText: 'status text',
      json: () => Promise.resolve(body),
    } as Response
  }

  function aFile(): File {
    return new File([new Uint8Array(4)], 'MP Replay v101.103 (1).aoe2record', {
      type: 'application/octet-stream',
    })
  }

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs multipart to the upload path, same-origin, and resolves with the body on 200', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ status: 'stored', source: 'manual' }, 200),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await uploadReplay(700_800_900, aFile())

    expect(result).toEqual({ status: 'stored', source: 'manual' })
    const [path, init] = fetchMock.mock.calls[0]!
    expect(path).toBe('/api/replays/700800900/upload')
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('same-origin')
    expect(init?.body).toBeInstanceOf(FormData)
    // The browser must set `Content-Type` itself (boundary included) — this request must never
    // set it by hand, per `uploadReplay`'s own note.
    expect(init?.headers).not.toHaveProperty('Content-Type')
  })

  it('rejects with code invalid_replay on 422', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ error: { code: 'invalid_replay', message: 'Not a replay.' } }, 422),
      ),
    )

    await expect(uploadReplay(700_800_900, aFile())).rejects.toMatchObject({
      code: 'invalid_replay',
    })
  })

  it('rejects with code not_found on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ error: { code: 'not_found', message: 'No such match.' } }, 404),
      ),
    )

    await expect(uploadReplay(700_800_900, aFile())).rejects.toMatchObject({
      code: 'not_found',
    })
  })

  it('rejects with code already_archived on 409', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ error: { code: 'already_archived', message: 'Already archived.' } }, 409),
      ),
    )

    await expect(uploadReplay(700_800_900, aFile())).rejects.toMatchObject({
      code: 'already_archived',
    })
  })

  it('rejects with code unknown_error on an unrecognised 5xx envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(null, 500)),
    )

    await expect(uploadReplay(700_800_900, aFile())).rejects.toMatchObject({
      code: 'unknown_error',
    })
  })

  it('rejects with code network_error when the request never reaches the server', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    await expect(uploadReplay(700_800_900, aFile())).rejects.toMatchObject({
      code: 'network_error',
    })
  })

  it('throws the real ApiRequestError type, not just a code-shaped object', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ error: { code: 'invalid_replay', message: 'Not a replay.' } }, 422),
      ),
    )

    await expect(uploadReplay(700_800_900, aFile())).rejects.toBeInstanceOf(ApiRequestError)
  })
})
