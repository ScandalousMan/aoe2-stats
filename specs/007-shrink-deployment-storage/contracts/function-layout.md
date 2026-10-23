# Contract: function layout

What the deployed site promises at its routes after this feature. **Nothing a client sees changes,
and neither does the layout**: same three functions, same paths, methods, authentication, limits and
responses. Story 5 would have merged the two long-running functions and was dropped by
`/speckit-analyze` on 2026-10-18 (plan, Constitution Check): the replay parser must not share a
function with the ingestion run (constitution V). What this feature changes is what each function
stores, and this contract is what the bundle guard and the dry run hold in place while it does.

## Routes → functions

| Public path          | Methods   | Function             | Time limit              | Reached by                         |
| -------------------- | --------- | -------------------- | ----------------------- | ---------------------------------- |
| `/api/analyze`       | POST      | `api/analyze.py`     | long (unchanged, 300 s) | filesystem (the file's own path)   |
| `/api/cron/ingest`   | GET, POST | `api/cron/ingest.py` | long (unchanged, 300 s) | filesystem (the file's own path)   |
| every other `/api/*` | as today  | `api/index.py`       | short (unchanged, 10 s) | rewrite `/api/(.*)` → `/api/index` |
| everything else      | GET       | static build         | —                       | rewrite `/(.*)` → `/index.html`    |

## Invariants

1. **Exactly three function entries** in `vercel.json`'s `functions`, one per row above that names a
   file, at the limits shown. Each carries the same `excludeFiles` value (research R1). Asserted by
   `scripts/checks/tests/test_vercel_bundle.py`, so a later merge of the parser's function with the
   ingestion run fails CI (FR-012).
2. **Filesystem before rewrite**: both long-running paths resolve to their own files ahead of
   `/api/(.*)`. Asserted by `scripts/checks/spa-routing.mjs`, unchanged by this feature.
3. **Authentication is unchanged and checked first**:
   - `/api/cron/ingest`: a missing or wrong bearer secret → `401` with error code `unauthorized`,
     before any database or provider work.
   - `/api/analyze`: no session cookie → the existing `401` refusal, before any database work.
4. **The cron schedule's `path` is still `/api/cron/ingest`** in `vercel.json`'s `crons`.
5. `api/index.py` stays a thin re-export of `create_app()`'s `app`.
6. `scripts/checks/api_entrypoint_deps.py` passes over every file under `api/`.

## Verification

- Offline: `node scripts/checks/spa-routing.mjs`; the bundle guard; the bundle dry run's imports and
  route probes (research R8); the existing entrypoint tests under `apps/api/tests/`, untouched.
- Production: quickstart §5. A manual analysis request, a manual trigger of the ingestion run, and
  the next scheduled run, each read back from the run's own report.
