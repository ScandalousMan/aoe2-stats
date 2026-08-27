# Contract: HTTP API

What the front end and the scheduler may rely on. Paths under `/api`. All responses JSON except
replay downloads. Authentication is the session cookie unless stated otherwise.

Errors use a single shape — `{"error": {"code": "...", "message": "...", "detail": {...}}}` — with a
stable machine-readable `code`. The front end branches on `code`, never on `message`, so wording can
change without breaking a client.

`detail` MUST NOT carry a configuration value, a credential, a connection string or a URL that
embeds one, on any route — a health check above all, since `/api/health` is unauthenticated. It MAY
carry a key _name_ (`S3_ENDPOINT_URL`) and a failure _class_ (`SignatureDoesNotMatch`,
`OperationalError`): both are diagnosis an operator needs, and neither is the secret that produced
them (T014e).

## Authentication

| Method | Path                       | Notes                                                                                                                                                                  |
| ------ | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/auth/steam/start`    | 302 to Steam. Sets a short-lived state cookie. Accepts `?link=1` when already signed in, to add a second Steam account rather than replace the session                 |
| `GET`  | `/api/auth/steam/callback` | Verifies the assertion server-side, resolves the profile, creates or extends the session, 302 to the app. **Never trusts the callback without `check_authentication`** |
| `POST` | `/api/auth/signout`        | Invalidates the session server-side, clears the cookie                                                                                                                 |
| `GET`  | `/api/me`                  | Session, allowlist state, archival objection state, linked profiles, which is primary                                                                                  |

**The session cookie is named `session_id`** (T028, `apps/api/src/aoe2stats_api/security.py`) —
its value is `<sessions.id>.<hmac-sha256 signature>`, base64url-encoded and padding-stripped, so a
tampered or fabricated cookie is rejected before it ever reaches the database. `sessions.id`
itself, not the signed wrapper, is what every other part of this contract means by "the session":
opaque, 256 bits of randomness (data-model.md), looked up fresh on every request so that
revocation (`POST /api/auth/signout`, and later `POST /api/privacy/erase`) is immediate and
server-side rather than something a client can outlast by keeping an unexpired token. `HttpOnly`,
`Secure`, `SameSite=Lax`, path `/`.

The short-lived state cookie `GET /api/auth/steam/start` sets is named `steam_oauth_state`,
distinct from the session cookie and signed the same way. It carries the CSRF `state` value
embedded in the outbound `return_to` Steam is asked to echo back (research.md §2): the callback
accepts a `state` only if it matches what _this browser's own_ `steam_oauth_state` cookie says was
minted for it, which is what ties the value to the browser session and refuses a `state` minted
for one browser if replayed from another. Single-use and its ten-minute expiry are both enforced
server-side against the `csrf_states` table (data-model.md, T028b), never by trusting the cookie's
own `max-age` or the fact that the callback response asks the client to clear it: a `state` this
table already marked consumed, or one past its own `expires_at`, is refused even when the cookie
that carries it still verifies.

`GET /api/me` returns 200 with `{"authenticated": false}` rather than 401 when signed out: it is the
front end's bootstrap call, and an error status for the ordinary case makes every client log noise.

**Amended 2026-08-27 (T405) — consent retired in favour of an objection, constitution IX 4.0.0.**
An authenticated `GET /api/me` answers `archival_objected` as the state that is true **right
now** — `archival_objected_at IS NOT NULL`, the same predicate the ingester's own gate reads
(data-model.md) — with `false` the state of a user who has answered no question at all, since
archival is on by default under legitimate interest and there is no "never asked" state left to
distinguish from it. `archival_objected_at` (a nullable ISO 8601 timestamp, `null` for a user who
is archiving, whether because they never objected or because they objected and later resumed) is
returned alongside it, in the same field name `POST /api/privacy/archival-objection` already
answers with, so a client can render "archiving" or "objected, as of ..." from a single
`GET /api/me` after a plain page reload, with no state of its own to carry between requests.

Failure codes that carry product meaning, not just HTTP semantics:

| Code                      | When                                                                                                                                                                               |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `steam_assertion_invalid` | `check_authentication` said no. Log it; this is either a bug or an attack                                                                                                          |
| `no_aoe2_profile`         | Steam verified, no AoE2 profile exists (FR-003). Not an error to the user, an explanation                                                                                          |
| `not_allowlisted`         | Closed beta (FR-005)                                                                                                                                                               |
| `profile_already_linked`  | That profile belongs to another account                                                                                                                                            |
| `provider_unavailable`    | Relic rate-limited, errored, timed out, or answered a non-JSON body mid-callback (T029b). Recoverable — the caller retries; the failing call is still recorded in `provider_calls` |

## Profiles

| Method   | Path                                 | Notes                                                                                                                                                                                                   |
| -------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`    | `/api/profiles`                      | The caller's linked profiles with current ratings per leaderboard, each carrying a `leaderboard_name` the API names (T033a) — Relic's own `getPersonalStat` returns only `leaderboard_id`, never a name |
| `POST`   | `/api/profiles/{profile_id}/primary` | Choose which profile the interface shows (FR-043)                                                                                                                                                       |
| `DELETE` | `/api/profiles/{profile_id}`         | Unlink. Response states what happens to archived replays **before** the client confirms (FR-004)                                                                                                        |
| `GET`    | `/api/profiles/{profile_id}/ratings` | Rating history from snapshots                                                                                                                                                                           |

## Matches

| Method | Path                                      | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------ | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/matches?profile_id=&cursor=&limit=` | Newest first, cursor paginated. Each row carries its capture status and `capture_deadline_at` (FR-027), a `civilisation_name` the API names (T070c) alongside the raw `civilisation` id, a `leaderboard_name` the API names (T070f, the same `leaderboards.py` mapping `/api/profiles` already uses) alongside the raw `leaderboard_id`, and an `opponents` array restricted to participants on a different team than the caller's own — never a teammate (T070d) |
| `GET`  | `/api/matches/{game_id}`                  | All participants, teams, civs, results, rating changes — each participant's `civ_id` is named as `civ_name` the same way (T070c), the match's own `leaderboard_id` carries a `leaderboard_name` the same way (T070f), and the response itself carries `capture_status`/`capture_deadline_at` for this match, the identical fields the list row above carries (FR-027, T070e)                                                                                      |

Only matches involving one of the caller's linked profiles are reachable. There is no endpoint that
takes an arbitrary `profile_id` and returns its history: FR-038 forbids exposing non-users, and an
endpoint that does it "just for logged-in users" is still a public directory of players.

## Replays

| Method | Path                              | Notes                                                                                                                              |
| ------ | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/replays/{game_id}/download` | 302 to a short-lived signed URL. Writes `replay_access_log` (FR-040)                                                               |
| `POST` | `/api/replays/{game_id}/upload`   | Manual fallback (FR-029). Multipart. Rejects a non-participant (FR-031), an invalid file (FR-030), or an existing archive (FR-032) |
| `GET`  | `/api/replays/status?profile_id=` | Counts per status, oldest pending, nearest deadline                                                                                |

The bucket is never public. A download is always a freshly signed URL with a short expiry, because a
replay contains other players' gameplay and chat.

## Privacy

| Method | Path                              | Notes                                                                                                            |
| ------ | --------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `POST` | `/api/privacy/archival-objection` | Object to archival, or resume it (FR-035). Separate from account creation, always                                |
| `POST` | `/api/privacy/export`             | Starts an export; returns a job reference                                                                        |
| `GET`  | `/api/privacy/export/{id}`        | Status, then a signed URL to the archive                                                                         |
| `POST` | `/api/privacy/erase`              | Requires an explicit confirmation token from a prior `GET`. Irreversible (FR-037)                                |
| `POST` | `/api/privacy/object`             | Third-party objection (FR-039). **Unauthenticated by design** — the person objecting is by definition not a user |

`/api/privacy/object` is the one unauthenticated write in the system. It is rate limited and it does
not act immediately: it records a request for a human to resolve. An endpoint that let anyone
pseudonymise any profile on demand would be a denial-of-service vector against the data. It is
distinct from `/api/privacy/archival-objection` below, which is the _linked user's own_ Art. 21
objection to their own archival, and is behind the session cookie like the rest of this section.

**Amended 2026-08-27 (T405) — renamed from `/api/privacy/consent`, with an inverted meaning, not
added alongside it.** Constitution IX 4.0.0 retired the opt-in consent gate archival used to sit
behind; there is no longer a grant to record, so the old route and its `{"granted": bool}` body do
not exist any more. `POST /api/privacy/archival-objection` takes `{"objected": bool}` (T405).
`true` objects — recording `users.archival_objected_at` the first time only, so a repeated
objection never rewrites when it was first made (data-model.md) — which the ingester's own gate
reads as `archival_objected_at IS NOT NULL` and stops capturing this user's recordings from the
next cycle on. `false` resumes archival by clearing `users.archival_objected_at` back to `null`,
and is a no-op, not an error, when there was never an objection to clear. Both directions answer
200 with `{"archival_objected": bool, "archival_objected_at": <ISO 8601 timestamp or null>}`.

## Operations

| Method        | Path               | Auth                                 | Notes                                                                                                                                                                                |
| ------------- | ------------------ | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET`         | `/api/health`      | none                                 | Liveness plus database and object-store reachability, **and schema currency** (2026-08-23, 003 T394)                                                                                 |
| `GET`, `POST` | `/api/cron/ingest` | `Authorization: Bearer $CRON_SECRET` | Runs one cycle. **401 without a valid, non-empty secret** (constitution VIII — an unset `CRON_SECRET` refuses outright rather than matching an empty bearer). Returns the run report |

A failing `/api/health` names, in `detail`, which dependency broke and why — `error_class` for a
database or object-store probe (the exception class, or a `ClientError`'s S3 error code such as
`SignatureDoesNotMatch`), `missing_or_invalid_keys` when `Settings` itself could not be built —
never the value behind either (T014e, and the `detail` rule above).

**Amended 2026-08-23 (003 T390, T394)**, after an outage in which every `/api/*` route answered a
bare `internal_error` 500 for a day. Two additions, both to this route's contract and one of them
to every route's:

- `configuration_invalid` with `missing_or_invalid_keys` is no longer this route's alone. Every
  route answers it, from a single handler in `app.py`, because `Settings` fails while FastAPI
  resolves a route's dependencies and the route that fails is whichever one the caller asked for.
- `/api/health` also answers **503 `schema_out_of_date`**, with `detail` naming `expected` (the
  Alembic revision this build was compiled with) and `found` (the database's, or `null` when
  nothing has ever been migrated). Distinct from `database_unavailable` on purpose: reachable and
  correct are different claims, and only the second one tells an operator to run a migration. The
  healthy 200 body gains `schema_revision` alongside `status`, `database` and `object_store`, so
  the value is readable without provoking a failure.

`/api/cron/ingest` returns 200 with a report even when individual captures failed. A non-200 means
the cycle could not run at all. The distinction matters: the scheduler retries the second, and the
next cycle handles the first.

In production Vercel routes `/api/cron/ingest` to `api/cron/ingest.py`, which holds the 300 s
duration the cycle needs; the FastAPI route of the same path is the local and phase-2-VPS caller.
Both are ten lines around `run_once()`. Neither calls the other: an HTTP hop between two functions
would put the cycle in the one that has no extended duration.

Vercel Cron Jobs always call the scheduled path with **`GET`**, attaching the bearer token
themselves — so `api/cron/ingest.py` accepts both `GET` and `POST`. The FastAPI route accepts only
`POST`: nothing schedules it, it exists for the quickstart's manual `curl -X POST` and the phase-2
worker loop, both of which keep using `POST`.
