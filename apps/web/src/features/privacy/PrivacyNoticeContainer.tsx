import { PrivacyNotice } from 'design-system'

// T095: composes `PrivacyNotice` (T093's spec) at `/privacy-notice`. Deliberately outside any
// session gate — FR-041's notice is for a user and a non-user alike, and `PrivacyNotice` itself
// takes no data-fetching prop at all (privacy-notice.md §5: "must be fully readable at first
// paint before any network call resolves").
//
// `lastUpdated` is the build-time constant privacy-notice.md §3 requires, never fetched — bump it
// only alongside an actual copy change to §4, together with the `docs/privacy/processing-register.md`
// change that makes the new copy true (privacy-notice.md's own header).
const LAST_UPDATED = '2026-08-30'

// `PrivacyNotice` composes `Page` itself (005, structural retrofit, T558) — this screen is always
// the whole of its route, the same reasoning `SignInScreen` and `ThirdPartyObjectionForm` already
// carry — so this container no longer wraps it in a second `Page`. Its own visible heading is now
// an `<h2>`, downgraded from the `<h1>` it used to duplicate `Page`'s hidden one with.
export function PrivacyNoticeContainer() {
  return (
    <PrivacyNotice
      lastUpdated={LAST_UPDATED}
      hrefs={{
        archivalControl: '/dashboard',
        privacyRoute: '/privacy',
        objectionForm: '/object',
      }}
    />
  )
}
