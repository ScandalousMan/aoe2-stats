import { createFileRoute } from '@tanstack/react-router'
import { ObjectContainer } from '../features/privacy/ObjectContainer'

// T095: the third-party objection route, `/object` — **outside the session** (FR-039). No
// `beforeLoad` gate of any kind: this route's entire audience has no account and no session
// cookie, reachable from `PrivacyNotice` §4.7's call to action and, once T098 lands, the site
// footer. Without this route FR-039's "a way to object" was an unauthenticated JSON endpoint with
// no way for the person it exists for to reach it.
export const Route = createFileRoute('/object')({
  component: ObjectRoute,
})

function ObjectRoute() {
  return <ObjectContainer />
}
