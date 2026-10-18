# Contract: function layout

What the deployed site promises at its routes after this feature. **Nothing a client sees changes**:
same paths, methods, authentication, responses. What changes is which stored function answers, and
that is the contract the routing check and the dry run assert.

## Routes → functions

| Public path          | Methods   | Function         | Time limit              | Reached by                                                                 |
| -------------------- | --------- | ---------------- | ----------------------- | -------------------------------------------------------------------------- |
| `/api/analyze`       | POST      | `api/analyze.py` | long (unchanged, 300 s) | filesystem (the file's own path)                                           |
| `/api/cron/ingest`   | GET, POST | `api/analyze.py` | long (unchanged, 300 s) | rewrite `/api/cron/ingest` → `/api/analyze`, listed **before** `/api/(.*)` |
| every other `/api/*` | as today  | `api/index.py`   | short (unchanged, 10 s) | rewrite `/api/(.*)` → `/api/index`                                         |
| everything else      | GET       | static build     | —                       | rewrite `/(.*)` → `/index.html`                                            |

Before this feature `/api/cron/ingest` was served by its own function, `api/cron/ingest.py`, reached
through the filesystem. That file no longer exists.

## Invariants

1. **Exactly two function entries** in `vercel.json`'s `functions`, one per row above that names a
   file. Each carries the same `excludeFiles` value (research R1).
2. **Rewrite order**: the `/api/cron/ingest` rewrite precedes `/api/(.*)`. Asserted by
   `scripts/checks/spa-routing.mjs`; a cron request that fell through to `api/index.py` would be
   cut off at the short limit mid-capture (plan, Constitution Check I).
3. **The app sees the original path.** The merged Starlette app declares both routes at their public
   paths, `/api/analyze` and `/api/cron/ingest`, never at `/api/analyze` alone.
4. **Authentication is unchanged and checked first**:
   - `/api/cron/ingest`: a missing or wrong bearer secret → `401` with error code `unauthorized`,
     before any database or provider work.
   - `/api/analyze`: no session cookie → the existing `401` refusal, before any database work.
5. **The cron schedule's `path` is still `/api/cron/ingest`** in `vercel.json`'s `crons`.
6. `api/index.py` stays a thin re-export of `create_app()`'s `app`. The local and phase-2 route
   `POST /api/cron/ingest` inside `create_app()` (`routers/cron.py`) is unaffected. In production
   it is never reached, because the rewrite in invariant 2 sends that path elsewhere first, as the
   filesystem did before.
7. `scripts/checks/api_entrypoint_deps.py` passes over every file under `api/`.

## Verification

- Offline: `node scripts/checks/spa-routing.mjs`; the bundle dry run's route probes (research R8);
  `apps/api/tests/test_analyze_entrypoint.py` and `test_cron_ingest_entrypoint.py`, both against
  `api.analyze`.
- Production: quickstart §5. A manual analysis request, a manual trigger of the ingestion run, and
  the next scheduled run, each read back from the run's own report.
