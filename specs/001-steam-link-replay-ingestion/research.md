# Phase 0 Research: Steam Linking and Replay Ingestion

Findings that were not already settled by `docs/data-sources.md`, `docs/adr/0001-replay-parser.md`
and `docs/adr/0002-hosting.md`. Those three are prerequisites for this document and are not repeated
here.

---

## 1. One Steam account holds exactly one AoE2 profile

**Decision**: Multi-profile support means letting a user link several Steam accounts, each proven by
its own sign-in. There is no discovery step.

**Rationale**: `getPersonalStat` was queried with three different Steam identifiers on 2026-08-19.
Each returned exactly one profile. Meanwhile a well-known player's public data shows four AoE2
profiles across four *distinct* Steam accounts. What players call a second profile is a second Steam
account. The original FR-007 — "discover every profile belonging to the signed-in identity" — was
therefore unimplementable as written, and the spec was corrected during planning.

**Alternatives considered**:

- *Use the third-party community mapping between a player's accounts.* Rejected on two grounds. It
  is an unverifiable claim about someone's identity, and acting on it would silently disclose that
  one account is an alternate of another — a thing players routinely take care to keep separate.
  Only a completed sign-in proves ownership. Now enforced by FR-045.
- *Support one profile only.* Rejected: a second account's replays face the same ~31-day window, and
  declining to capture them destroys them. Principle I applies.

---

## 2. Steam OpenID 2.0 without a dependency

**Decision**: Implement the verification directly in `packages/providers/steam/`. Two HTTP exchanges,
no library.

**Rationale**: The flow is small and entirely specified: redirect the user to
`https://steamcommunity.com/openid/login` with the OpenID 2.0 parameters, receive the callback, then
POST every returned parameter back to Steam with `openid.mode` replaced by `check_authentication`
and require `is_valid:true`. The identifier is then extracted from `openid.claimed_id`, which must
match `https://steamcommunity.com/openid/id/<17 digits>`. The Python OpenID 2.0 libraries are
long unmaintained, and pulling an abandoned dependency into the security-critical path of the only
authentication route in the system is worse than owning sixty lines we fully understand.

**Non-negotiable details**, each of which is a way this goes wrong if skipped:

- The `check_authentication` round trip is mandatory. Without it the callback is trivially forged and
  anyone can sign in as anyone.
- `openid.return_to` must be validated against our own configured URL, and `openid.claimed_id`
  against the exact expected pattern — no substring matching.
- The endpoint must be discovered or pinned to Steam's, never taken from the callback.
- A `state` value tied to the browser session guards the callback against CSRF.

**Alternatives considered**: `python-social-auth` (a large dependency for one provider, and it wants
a framework integration we do not have); `python3-openid` (unmaintained, and generic OpenID 2.0 is
far more surface than Steam's single fixed flow).

---

## 3. Sessions on a stateless function

**Decision**: A signed, `HttpOnly`, `Secure`, `SameSite=Lax` cookie holding an opaque session
identifier, with session state in Postgres.

**Rationale**: A self-contained token would avoid the database read, but it cannot be revoked, and
this application must be able to end a session immediately on erasure (FR-037), and to end it
without waiting for a token to expire on sign-out. Withdrawing ingestion consent is deliberately
not in this list: FR-034 requires an account that keeps working when consent is declined, so a
withdrawal that signed the user out would be punishing them for exercising the choice. The cookie is opaque so nothing about the user leaks into browser storage. The
lookup is one indexed read on a request path that already touches the database.

**Alternatives considered**: JWT in a cookie (revocation problem); JWT in local storage (adds XSS
exposure for no gain).

---

## 4. Postgres from a serverless function against Neon

**Decision**: `psycopg` 3 async through Neon's **pooled** connection string, with the driver's
prepared-statement cache disabled and pooling left to the platform.

**Rationale**: Each invocation is short-lived, so an in-process connection pool has nothing to
amortise and would instead exhaust the database's connection budget as concurrency rises. Neon's
pooler sits in front. The one real trap is server-side prepared statements: a transaction pooler
hands a different backend to each transaction, so cached prepared statements break. It must be
switched off explicitly rather than discovered in production.

**Also settled here**: the daily cron always hits a suspended compute, so the first connection pays a
cold start. With a generous connect timeout and one retry this is a few seconds against a 300 s
budget — irrelevant, but it must not be mistaken for an outage in the logs.

**Alternatives considered**: SQLAlchemy's own pooling with the direct (non-pooled) endpoint —
rejected, it is the documented way to run out of connections on this platform.

---

## 5. Object storage client

**Decision**: `boto3` against the S3-compatible endpoint, called from a worker thread so it does not
block the event loop. Endpoint, bucket and credentials come from the environment; nothing in the
code knows which provider is behind them.

**Rationale**: The S3 API is the portability contract that makes the phase-2 move a configuration
change (constitution XII). `boto3` is synchronous, and the async alternatives are thinner and less
maintained; for a workload of a handful of multi-megabyte uploads per run, offloading the sync call
is simpler and less risky than adopting an async S3 client.

**Verified while writing this**: the replay endpoint ignores `Range` and rejects `HEAD` with 405, so
a capture is always a full download held in memory. At the observed maximum of ~2.5 MB against 2 GB
of function memory, streaming to a temporary file buys nothing and adds a filesystem dependency the
constitution would rather not have.

---

## 6. Polling strategy inside a once-daily budget

**Decision**: A single run does the whole cycle: refresh ratings, discover matches, reconcile the
last 25 days, then drain the capture queue until the time budget is nearly spent.

**Rationale**: The heartbeat-versus-sweep distinction that a five-minute poller would need collapses
at daily cadence — there is no point checking `lastmatchdate` to decide whether to fetch the match
history when we are going to fetch it anyway. `getRecentMatchHistory` also covers unranked games,
which `lastmatchdate` does not. Batching keeps it to one call per ten profiles.

The queue is `replay_captures.status`, claimed with `SELECT ... FOR UPDATE SKIP LOCKED`. No broker.
This is the shape that survives the move to a five-minute worker unchanged: only the caller changes.

**Ordering rule**: drain by nearest `capture_deadline_at` first, never newest first. Under a
backlog, the replays closest to expiry are the ones that will be lost, and they must go first even
though the newest are the ones a user is most likely to be looking for.

---

## 7. Detecting that the cron did not run

**Decision**: Every run writes an `ingest_runs` row. An external nightly job reads the most recent
one and fails if it is older than 30 hours.

**Rationale**: This is the failure mode the whole phase-1 architecture is exposed to. Nothing inside
a system that is not running can report that it is not running, so the check has to come from
outside it — which is why it lives in the scheduled CI workflow rather than in the application. It is
already scaffolded in `.github/workflows/nightly.yml`, waiting on this feature's database.

**Alternatives considered**: an external uptime monitor pinging a health endpoint — rejected, it
proves the API is up, which is not the question. The question is whether the *cron* fired.

---

## Resolved by existing documents

| Question | Where |
| --- | --- |
| Which replay parser, and why | `docs/adr/0001-replay-parser.md` |
| Hosting, regions, and the constraints they impose | `docs/adr/0002-hosting.md` |
| Every external endpoint, its shape, its traps | `docs/data-sources.md` |
| Retention window and the 21-day capture budget | `docs/data-sources.md` |
| Rate-limiting posture and the honest User-Agent | `.claude/skills/aoe2-data-sources/SKILL.md` |

**No unresolved unknowns remain for this feature.**
