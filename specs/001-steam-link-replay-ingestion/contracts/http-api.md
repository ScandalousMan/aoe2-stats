# Contract: HTTP API

What the front end and the scheduler may rely on. Paths under `/api`. All responses JSON except
replay downloads. Authentication is the session cookie unless stated otherwise.

Errors use a single shape — `{"error": {"code": "...", "message": "...", "detail": {...}}}` — with a
stable machine-readable `code`. The front end branches on `code`, never on `message`, so wording can
change without breaking a client.

## Authentication

| Method | Path                       | Notes                                                                                                                                                                  |
| ------ | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/auth/steam/start`    | 302 to Steam. Sets a short-lived state cookie. Accepts `?link=1` when already signed in, to add a second Steam account rather than replace the session                 |
| `GET`  | `/api/auth/steam/callback` | Verifies the assertion server-side, resolves the profile, creates or extends the session, 302 to the app. **Never trusts the callback without `check_authentication`** |
| `POST` | `/api/auth/signout`        | Invalidates the session server-side, clears the cookie                                                                                                                 |
| `GET`  | `/api/me`                  | Session, allowlist state, consent state, linked profiles, which is primary                                                                                             |

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

## Operations

| Method        | Path               | Auth                                 | Notes                                                                                                                                                                                |
| ------------- | ------------------ | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET`         | `/api/health`      | none                                 | Liveness plus database and object-store reachability                                                                                                                                 |
| `GET`, `POST` | `/api/cron/ingest` | `Authorization: Bearer $CRON_SECRET` | Runs one cycle. **401 without a valid, non-empty secret** (constitution VIII — an unset `CRON_SECRET` refuses outright rather than matching an empty bearer). Returns the run report |

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
