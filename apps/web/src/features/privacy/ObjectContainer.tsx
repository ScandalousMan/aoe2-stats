import { ThirdPartyObjectionForm } from 'design-system'
import { objectToProcessing } from './api'

// T095: composes `ThirdPartyObjectionForm` (T094's spec) at `/object`, a route **outside the
// session** — no auth chrome, no fetch that requires a cookie, reachable from `PrivacyNotice` §4.7
// and (once T098 lands) the footer. Note for T098: the footer link this component is also meant
// to be reachable from does not exist yet; only the `PrivacyNotice` call-to-action reaches this
// route today.

export function ObjectContainer() {
  return (
    <ThirdPartyObjectionForm
      onSubmit={(profileId) => objectToProcessing(profileId).then(() => undefined)}
      privacyNoticeHref="/privacy-notice"
    />
  )
}
