import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SignInContainer } from './SignInContainer'

// `SignInContainer` wires `SignInScreen` (design-system) to exactly two real effects — a
// full-page navigation to Steam and a client-side navigation home — and to nothing else (its own
// docstring). This suite proves those two wires, plus that `errorCode` really reaches
// `SignInScreen` as the outcome `resolveOutcome` says it should, without re-testing
// `SignInScreen`'s own rendering (that belongs to design-system's suite).

/** `continueWithSteam` defers `window.location.assign` by one macrotask (module docstring,
 * steamStart.ts) purely so React can commit the "leaving" phase's label before the SPA unloads —
 * a real timer under fake-timer control deadlocks against Testing Library's own event loop, so
 * this spies on `window.setTimeout` and runs the callback immediately instead of advancing a
 * clock, which is the behaviour that actually matters here: the effect fires, in order. */
function runDeferredNavigationSynchronously() {
  return vi.spyOn(window, 'setTimeout').mockImplementation(((callback: () => void) => {
    callback()
    return 0 as unknown as ReturnType<typeof window.setTimeout>
  }) as typeof window.setTimeout)
}

describe('SignInContainer', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('navigates to Steam via buildSteamStartUrl when "Continue with Steam" is clicked', async () => {
    runDeferredNavigationSynchronously()
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    const user = userEvent.setup()

    render(<SignInContainer linkMode={false} errorCode={undefined} onNavigateHome={() => {}} />)
    await user.click(screen.getByRole('button', { name: 'Continue with Steam' }))

    expect(assign).toHaveBeenCalledWith('/api/auth/steam/start')
  })

  it('builds the link-mode start URL (?link=1) when linkMode is true', async () => {
    runDeferredNavigationSynchronously()
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    const user = userEvent.setup()

    render(<SignInContainer linkMode={true} errorCode={undefined} onNavigateHome={() => {}} />)
    await user.click(screen.getByRole('button', { name: 'Continue with Steam' }))

    expect(assign).toHaveBeenCalledWith('/api/auth/steam/start?link=1')
  })

  it('renders the "leaving" phase synchronously on click, before the deferred navigation fires', async () => {
    // The real `window.setTimeout` here, deliberately: this is exactly the assertion that
    // `continueWithSteam` commits the "leaving" phase before the navigation macrotask has even
    // been given a chance to run.
    vi.stubGlobal('location', { ...window.location, assign: vi.fn() })
    const user = userEvent.setup()

    render(<SignInContainer linkMode={false} errorCode={undefined} onNavigateHome={() => {}} />)
    await user.click(screen.getByRole('button', { name: 'Continue with Steam' }))

    expect(screen.getByRole('button', { name: 'Taking you to Steam…' })).toBeInTheDocument()
  })

  it('calls onNavigateHome, a client-side navigation, from Cancel in link mode', async () => {
    const user = userEvent.setup()
    const onNavigateHome = vi.fn()
    render(
      <SignInContainer linkMode={true} errorCode={undefined} onNavigateHome={onNavigateHome} />,
    )
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onNavigateHome).toHaveBeenCalledTimes(1)
  })

  it('resolves errorCode through resolveOutcome: not_allowlisted reaches SignInScreen as its own outcome', () => {
    render(
      <SignInContainer linkMode={false} errorCode="not_allowlisted" onNavigateHome={() => {}} />,
    )
    expect(screen.getByText(/this steam account is not on the beta list/i)).toBeInTheDocument()
  })

  it('resolves an undocumented error code to the unreachable outcome, never a blank panel', () => {
    render(
      <SignInContainer
        linkMode={false}
        errorCode="some_code_this_front_end_was_never_told_about"
        onNavigateHome={() => {}}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Steam did not answer' })).toBeInTheDocument()
  })

  it('resolves provider_unavailable (T029b) onto the unreachable outcome', () => {
    render(
      <SignInContainer
        linkMode={false}
        errorCode="provider_unavailable"
        onNavigateHome={() => {}}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Steam did not answer' })).toBeInTheDocument()
  })

  it('renders no outcome at all when there is no error code', () => {
    render(<SignInContainer linkMode={false} errorCode={undefined} onNavigateHome={() => {}} />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('retry actions reuse the same real effect: a fresh /api/auth/steam/start round trip', async () => {
    runDeferredNavigationSynchronously()
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    const user = userEvent.setup()

    render(<SignInContainer linkMode={false} errorCode="unreachable" onNavigateHome={() => {}} />)
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(assign).toHaveBeenCalledWith('/api/auth/steam/start')
  })
})
