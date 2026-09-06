import { Page, PrivacyNotice } from 'design-system'

// T095: composes `PrivacyNotice` (T093's spec) at `/privacy-notice`. Deliberately outside any
// session gate — FR-041's notice is for a user and a non-user alike, and `PrivacyNotice` itself
// takes no data-fetching prop at all (privacy-notice.md §5: "must be fully readable at first
// paint before any network call resolves").
//
// `lastUpdated` is the build-time constant privacy-notice.md §3 requires, never fetched — bump it
// only alongside an actual copy change to §4, together with the `docs/privacy/processing-register.md`
// change that makes the new copy true (privacy-notice.md's own header).
const LAST_UPDATED = '2026-08-30'

// `Page` owns this route's one main landmark and its reading width (`measure`, the token
// `size.page` names for "the privacy notice and every prose route" — structural-tier.md §5).
// `PrivacyNotice` (privacy-notice.md) predates the structural tier and still carries its own
// visible `<h1>` and "Last updated" subtitle — a call-site duplication of `Page`'s own header,
// left for `PrivacyNotice`'s own spec to reconcile (T557/T558) rather than solved here by
// reaching into a component outside this task's scope. `titleHidden` keeps `Page`'s required
// title out of the picture so the reader sees the one heading `PrivacyNotice` already renders.
export function PrivacyNoticeContainer() {
  return (
    <Page title="Privacy notice" titleHidden width="measure">
      <PrivacyNotice
        lastUpdated={LAST_UPDATED}
        hrefs={{
          archivalControl: '/dashboard',
          privacyRoute: '/privacy',
          objectionForm: '/object',
        }}
      />
    </Page>
  )
}
