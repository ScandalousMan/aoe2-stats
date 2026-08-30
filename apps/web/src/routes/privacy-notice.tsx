import { createFileRoute } from '@tanstack/react-router'
import { PrivacyNoticeContainer } from '../features/privacy/PrivacyNoticeContainer'

// T095: FR-041's privacy notice, `/privacy-notice`. Deliberately no `beforeLoad` gate — this
// route is for a signed-in user and a non-user alike (privacy-notice.md §1), and it is meant to
// be publicly reachable and indexable, unlike every other route `robots.txt` disallows.
export const Route = createFileRoute('/privacy-notice')({
  component: PrivacyNoticeRoute,
})

function PrivacyNoticeRoute() {
  return <PrivacyNoticeContainer />
}
