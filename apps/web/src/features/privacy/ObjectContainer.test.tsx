import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ObjectContainer } from './ObjectContainer'

// T095: `ObjectContainer` reaches `POST /api/privacy/object` directly — no `QueryClientProvider`,
// no router context, no session cookie — this route is reachable with nothing else mounted,
// exactly like the real `/object` route (third-party-objection.md: "the whole screen works with
// no session cookie and no JavaScript-loaded data").

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

function installFakeApi(handler: () => Response) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    if (path === '/api/privacy/object' && method === 'POST') {
      return handler()
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('ObjectContainer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders with no session and no wrapper of any kind', () => {
    installFakeApi(() => jsonResponse({ id: 'req-1', status: 'recorded' }, 202))
    render(<ObjectContainer />)
    expect(
      screen.getByRole('heading', { name: 'Object to what is held about you' }),
    ).toBeInTheDocument()
  })

  it('records the objection and shows the recorded confirmation', async () => {
    const fetchMock = installFakeApi(() => jsonResponse({ id: 'req-1', status: 'recorded' }, 202))
    const user = userEvent.setup()
    render(<ObjectContainer />)

    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '123456')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    await waitFor(() =>
      expect(screen.getByText('Your objection has been recorded.')).toBeInTheDocument(),
    )
    expect(
      fetchMock.mock.calls.some(([input, init]) => {
        if (String(input) !== '/api/privacy/object' || init?.method !== 'POST') return false
        const body = JSON.parse(String(init.body)) as { profile_id: number }
        return body.profile_id === 123456
      }),
    ).toBe(true)
  })

  it('shows the rate-limited warning on a 429', async () => {
    installFakeApi(() =>
      jsonResponse(
        { error: { code: 'rate_limited', message: 'slow down', detail: { retry_after: 60 } } },
        429,
      ),
    )
    const user = userEvent.setup()
    render(<ObjectContainer />)

    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '1')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    expect(await screen.findByText('Too many objections right now.')).toBeInTheDocument()
  })

  it('shows the failure callout on a server error, without claiming success', async () => {
    installFakeApi(() => jsonResponse({ error: { code: 'unknown_error', message: 'boom' } }, 500))
    const user = userEvent.setup()
    render(<ObjectContainer />)

    await user.type(screen.getByLabelText('Your Age of Empires II profile id'), '1')
    await user.click(screen.getByRole('button', { name: 'Record my objection' }))

    expect(await screen.findByText('We could not record your objection.')).toBeInTheDocument()
    expect(screen.queryByText('Your objection has been recorded.')).not.toBeInTheDocument()
  })
})
