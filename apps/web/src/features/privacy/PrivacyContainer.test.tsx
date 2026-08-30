import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// `useNavigate` needs a mounted `RouterProvider` this test never builds — mirrors
// `FavouritesContainer.test.tsx`'s and `SearchContainer.test.tsx`'s identical setup.
const navigateMock = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const { PrivacyContainer } = await import('./PrivacyContainer')

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
}

const authenticatedSession = {
  authenticated: true,
  user_id: 'user-1',
  allowlisted: true,
  archival_objected: false,
  archival_objected_at: null,
  profiles: [],
}

const unauthenticatedSession = { authenticated: false }

function installFakeApi({
  session = authenticatedSession,
  exportStartHandler,
  exportPollHandler,
  eraseGetHandler,
  erasePostHandler,
  archivalHandler,
}: {
  session?: typeof authenticatedSession | typeof unauthenticatedSession
  exportStartHandler?: () => Response
  exportPollHandler?: (id: string) => Response
  eraseGetHandler?: () => Response
  erasePostHandler?: (token: string) => Response
  archivalHandler?: () => Response
}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'

    if (path === '/api/me' && method === 'GET') {
      return jsonResponse(session)
    }
    if (path === '/api/privacy/export' && method === 'POST') {
      return exportStartHandler
        ? exportStartHandler()
        : jsonResponse({ id: 'job-1', status: 'completed' })
    }
    const pollMatch = /^\/api\/privacy\/export\/([\w-]+)$/.exec(path)
    if (pollMatch && method === 'GET' && pollMatch[1]) {
      return exportPollHandler
        ? exportPollHandler(pollMatch[1])
        : jsonResponse({ id: pollMatch[1], status: 'completed', download_url: '/archive.zip' })
    }
    if (path === '/api/privacy/erase' && method === 'GET') {
      return eraseGetHandler ? eraseGetHandler() : jsonResponse({ confirmation_token: 'confirm-1' })
    }
    if (path === '/api/privacy/erase' && method === 'POST') {
      const body = init?.body
        ? (JSON.parse(String(init.body)) as { confirmation_token: string })
        : { confirmation_token: '' }
      return erasePostHandler
        ? erasePostHandler(body.confirmation_token)
        : jsonResponse({ status: 'erased' })
    }
    if (path === '/api/privacy/archival-objection' && method === 'POST') {
      return archivalHandler
        ? archivalHandler()
        : jsonResponse({ archival_objected: true, archival_objected_at: '2026-08-30T00:00:00Z' })
    }
    throw new Error(`Unhandled fetch in test: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPrivacy() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return render(<PrivacyContainer />, { wrapper })
}

describe('PrivacyContainer — composition order and gating', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it('prompts to sign in when the session is unauthenticated', async () => {
    installFakeApi({ session: unauthenticatedSession })
    renderPrivacy()

    expect(await screen.findByText('Sign in to manage your data')).toBeInTheDocument()
    expect(screen.queryByText('Erase your account')).not.toBeInTheDocument()
  })

  it('composes ArchivalControl, DataExportPanel then AccountErasurePanel, in that order', async () => {
    installFakeApi({})
    renderPrivacy()

    const archival = await screen.findByText('Replay archival')
    const exportHeading = await screen.findByText('Get a copy of your data')
    const erasureHeading = await screen.findByText('Erase your account')

    expect(
      archival.compareDocumentPosition(exportHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(
      exportHeading.compareDocumentPosition(erasureHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })
})

describe('PrivacyContainer — export (FR-036)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it('requests an export and shows the download link once it completes', async () => {
    installFakeApi({})
    const user = userEvent.setup()
    renderPrivacy()

    await screen.findByText('Get a copy of your data')
    await user.click(screen.getByRole('button', { name: 'Export my data' }))

    const link = await screen.findByRole('link', { name: 'Download the archive' })
    expect(link).toHaveAttribute('href', '/archive.zip')
  })
})

describe('PrivacyContainer — erasure (FR-037), the terminal swap', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    navigateMock.mockClear()
  })

  it('erases the account and swaps the whole route to ErasedScreen, dropping the other panels', async () => {
    installFakeApi({})
    const user = userEvent.setup()
    renderPrivacy()

    await screen.findByText('Erase your account')
    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))
    await user.click(screen.getByRole('button', { name: 'Erase my account permanently' }))

    expect(await screen.findByText('Your account has been erased.')).toBeInTheDocument()
    expect(screen.queryByText('Replay archival')).not.toBeInTheDocument()
    expect(screen.queryByText('Get a copy of your data')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('re-mints and retries on a 403 without ever showing the terminal screen prematurely', async () => {
    let calls = 0
    installFakeApi({
      erasePostHandler: (token) => {
        calls += 1
        if (calls === 1) {
          return jsonResponse(
            { error: { code: 'confirmation_token_invalid', message: 'expired' } },
            403,
          )
        }
        expect(token).toBe('confirm-1')
        return jsonResponse({ status: 'erased' })
      },
    })
    const user = userEvent.setup()
    renderPrivacy()

    await screen.findByText('Erase your account')
    await user.click(screen.getByRole('button', { name: 'Erase my account' }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /I understand this cannot be undone/ }))
    await user.click(screen.getByRole('button', { name: 'Erase my account permanently' }))

    await screen.findByText('Your confirmation expired.')
    expect(screen.queryByText('Your account has been erased.')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Erase my account permanently' }))
    expect(await screen.findByText('Your account has been erased.')).toBeInTheDocument()
  })
})
