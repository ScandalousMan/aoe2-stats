"""The Vercel entrypoint for the FastAPI application (T014c).

`api/cron/ingest.py` (T018) is the *only* other platform-shaped file in the tree; Vercel's
filesystem routing gives that file precedence over the `/api/(.*)` rewrite `vercel.json` (T014c)
declares, so a request to `/api/cron/ingest` never reaches this module and keeps the cron's own
300 s `maxDuration` instead of the shorter one set here for the request path (ADR-0002). Every
other `/api/*` request is rewritten to `/api/index` and lands here.

Five lines around `create_app()`, deliberately: this file re-exports `app` and nothing else, so
nothing under `apps/`, `packages/` or `infra/` can come to depend on it, or on running on Vercel at
all (constitution XII). The application itself — routing, error envelope, dependency wiring — is
entirely `apps/api/src/aoe2stats_api/app.py`'s (T014); this module only makes it reachable from
Vercel's Python runtime.
"""

from __future__ import annotations

from aoe2stats_api.app import app

__all__ = ["app"]
