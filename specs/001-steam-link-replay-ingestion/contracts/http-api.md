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
| `GET`  | `/api/me`                  | Session, allowlist state, consent state, linked profiles, which is primary                                                                                             |

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
for one browser if replayed from another.

`GET /api/me` returns 200 with `{"authenticated": false}` rather than 401 when signed out: it is the
front end's bootstrap call, and an error status for the ordinary case makes every client log noise.

Failure codes that carry product meaning, not just HTTP semantics:

| Code                      | When                                                                                      |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| `steam_assertion_invalid` | `check_authentication` said no. Log it; this is either a bug or an attack                 |
| `no_aoe2_profile`         | Steam verified, no AoE2 profile exists (FR-003). Not an error to the user, an explanation |
| `not_allowlisted`         | Closed beta (FR-005)                                                                      |
| `profile_already_linked`  | That profile belongs to another account                                                   |

## Profiles

| Method   | Path                                 | Notes                                                                                            |
| -------- | ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `GET`    | `/api/profiles`                      | The caller's linked profiles with current ratings per leaderboard                                |
| `POST`   | `/api/profiles/{profile_id}/primary` | Choose which profile the interface shows (FR-043)                                                |
| `DELETE` | `/api/profiles/{profile_id}`         | Unlink. Response states what happens to archived replays **before** the client confirms (FR-004) |
| `GET`    | `/api/profiles/{profile_id}/ratings` | Rating history from snapshots                                                                    |

## Matches

| Method | Path                                      | Notes                                                                                                  |
| ------ | ----------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `GET`  | `/api/matches?profile_id=&cursor=&limit=` | Newest first, cursor paginated. Each row carries its capture status and `capture_deadline_at` (FR-027) |
| `GET`  | `/api/matches/{game_id}`                  | All participants, teams, civs, results, rating changes                                                 |

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

| Method | Path                       | Notes                                                                                                            |
| ------ | -------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `POST` | `/api/privacy/consent`     | Grant or withdraw ingestion consent (FR-034, FR-035). Separate from account creation, always                     |
| `POST` | `/api/privacy/export`      | Starts an export; returns a job reference                                                                        |
| `GET`  | `/api/privacy/export/{id}` | Status, then a signed URL to the archive                                                                         |
| `POST` | `/api/privacy/erase`       | Requires an explicit confirmation token from a prior `GET`. Irreversible (FR-037)                                |
| `POST` | `/api/privacy/object`      | Third-party objection (FR-039). **Unauthenticated by design** — the person objecting is by definition not a user |

`/api/privacy/object` is the one unauthenticated write in the system. It is rate limited and it does
not act immediately: it records a request for a human to resolve. An endpoint that let anyone
pseudonymise any profile on demand would be a denial-of-service vector against the data.

`POST /api/privacy/consent` takes `{"granted": bool}` (T032). `true` grants — recording
`users.ingest_consent_at` the first time only, so a repeated grant never rewrites when consent was
first given — and clears any prior withdrawal, since the ingester's selection query
(data-model.md) is `ingest_consent_at IS NOT NULL AND ingest_consent_withdrawn_at IS NULL`.
`false` withdraws by setting `users.ingest_consent_withdrawn_at`, which is added on top of
`ingest_consent_at` and never clears it (data-model.md: "Kept after withdrawal; erasure is a
separate act") — and is a no-op, not an error, when there was never a grant to withdraw. Declining
consent on an account that has not yet granted it (FR-034: separate from account creation) leaves
the rest of the account untouched and still answers 200.

## Operations

| Method        | Path               | Auth                                 | Notes                                                                                                                                                                                |
| ------------- | ------------------ | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET`         | `/api/health`      | none                                 | Liveness plus database and object-store reachability                                                                                                                                 |
| `GET`, `POST` | `/api/cron/ingest` | `Authorization: Bearer $CRON_SECRET` | Runs one cycle. **401 without a valid, non-empty secret** (constitution VIII — an unset `CRON_SECRET` refuses outright rather than matching an empty bearer). Returns the run report |

A failing `/api/health` names, in `detail`, which dependency broke and why — `error_class` for a
database or object-store probe (the exception class, or a `ClientError`'s S3 error code such as
`SignatureDoesNotMatch`), `missing_or_invalid_keys` when `Settings` itself could not be built —
never the value behind either (T014e, and the `detail` rule above).

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
