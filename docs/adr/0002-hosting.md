# ADR 0002 — Hosting: Vercel Hobby now, OVH VPS later

- **Status**: accepted
- **Date**: 2026-08-19

## Context

The project needs somewhere to run a React front end, a Python API, a daily ingestion job, a small
relational database, and a permanently growing archive of replay files. The domain is registered at
OVH. The priority for phase 1 is the lowest possible operational burden, not scale.

The original plan was an OVH VPS with Docker Compose (~8.49 EUR/month). The question raised was
whether Vercel Hobby could serve as a simpler starting point.

## The deciding constraint

Vercel Hobby restricts cron jobs to **once per day**, with ±59 minutes of scheduling imprecision.
More frequent expressions fail at deploy time. That looks fatal for an ingestion pipeline.

It is not, because of ADR-adjacent measurement: the replay retention window is ~31 days
(see `docs/data-sources.md`) and the internal capture budget is 21 days. A daily job produces at most
~25 h of detection lag, leaving about 20 days of margin. Live stats and match history are read from
the Relic API per request, so nothing the user _sees_ is delayed — only archival is batched.

## Corrections to widely-cited limits

- The often-quoted **60 s** Hobby function limit applies only to projects created before April 2025
  without Fluid compute. With Fluid compute, the default for new projects, **Hobby allows 300 s** and
  2 GB / 1 vCPU. At roughly 5 s per replay (download, checksum, upload) that is ~50 replays per run.
- The Python runtime supports **3.12, 3.13 and 3.14**, has a first-class FastAPI preset, reads
  dependencies from `pyproject.toml` with `uv.lock`, and allows a **500 MB** bundle.
- Active CPU is billed only on real CPU time; I/O wait is not counted. The Hobby allowance of
  4 CPU-hours per month is ~26 000 replay parses at the measured 0.54 s each, so even V2 parsing fits.

## Decision

**Phase 1 — 0 EUR/month:**

| Layer          | Choice                                         | Free allowance                                 |
| -------------- | ---------------------------------------------- | ---------------------------------------------- |
| Front end      | Vercel Hobby, Vite + React static build        | 100 GB transfer                                |
| API            | Vercel Python Function, FastAPI, region `cdg1` | 1 M invocations                                |
| Ingestion      | Vercel Cron, once daily, `maxDuration: 300`    | —                                              |
| Database       | Neon free, EU region                           | 0.5 GB storage, 100 CU-hours/month             |
| Replay storage | **Cloudflare R2**, EU jurisdiction             | **10 GB, 1 M writes, 10 M reads, zero egress** |
| Domain         | registered at OVH, DNS pointed at Vercel       | —                                              |

Vercel Blob was rejected for replay storage: its Hobby allowance is about **1 GB**, roughly 660
replays. R2's 10 GB covers ~6 600 replays, about 3.5 years for a single heavy player.

**Phase 2 — OVH VPS**, triggered by any of: R2 exceeding 10 GB, Neon exceeding 0.5 GB, wanting
sub-hour capture lag, or more than ~20 active users. VPS-2 (6 vCore / 12 GB / 100 GB NVMe) is about
8.49 EUR excl. VAT per month, plus OVH Object Storage at 0.0119 EUR/GB/month with egress free since
2026-01-01. The daily cron then becomes a long-lived worker with 5-minute polling.

## Constraints this imposes on the code

Constitution principle XII exists because of this ADR. In particular:

- The ingester is a **library** exposing `run_once(budget_seconds)`. Its only two entrypoints are a
  ~10-line Vercel cron handler (`api/cron/ingest.py`) and a ~10-line worker loop (`worker.py`).
- **No queue broker in phase 1.** `replay_captures.status` is the queue, claimed with
  `SELECT ... FOR UPDATE SKIP LOCKED`. This works identically on Neon and on self-hosted Postgres and
  removes Redis from the phase-1 stack.
- Object storage is reached only through the S3 API behind `packages/storage`. Moving from R2 to OVH
  is four environment variables plus a bulk copy.
- No local filesystem state. Serverless filesystems are ephemeral and read-only outside `/tmp`.
- A run interrupted by its time budget must leave no row in `downloading` and resume cleanly.

## The single-page fallback is a host requirement, not a Vercel setting

Every route the client-side router owns must resolve to `index.html` on a direct request — a
reload, a bookmark, a shared link, a browser restore — not only on an in-app navigation, which
never reaches the origin at all. On Vercel this is one rewrite entry in `vercel.json`, placed below
the `/api/(.*)` rewrite so the API keeps winning; `scripts/checks/spa-routing.mjs` asserts the
ordering holds. Phase 2's OVH reverse proxy does not read `vercel.json` and inherits none of this:
its own configuration needs the equivalent fallback (nginx's `try_files ... /index.html`, or
Caddy's `try_files`), or the same routes will 404 again on the new host, for the same reason.

## Regions: EU only

Vercel functions default to `iad1` (US East). Hobby allows changing the default region, so
**`cdg1` is mandatory**, with Neon in an EU region and the R2 bucket under EU jurisdiction. Given
that archived replays contain third-party players' in-game chat, this is a GDPR requirement, not a
preference. It is written into constitution principle IX.

## Risks accepted

- **A silently stopped cron is invisible** without an always-on process to notice. Mitigation: a
  nightly GitHub Actions job reads the most recent `ingest_runs` row and fails if it is older than
  30 h. This is the single most important monitor on this stack.
- **Free-tier ceilings** could stall ingestion silently. Mitigation: the nightly job warns at 70 % of
  any allowance, so the phase-2 move is planned rather than forced.
- **Cron imprecision** (±59 min, no delivery guarantee). Absorbed by the 21-day budget. Escape
  hatches, in order: 24 separate daily cron entries (allowed — 100 per project — though it leans on
  the letter of the limit), a GitHub Actions scheduled workflow, then Vercel Pro or phase 2.
- **Neon cold starts**: compute suspends after 5 minutes idle, so the daily cron always hits a cold
  database. Use the pooled connection string with a generous connect timeout; a few seconds against
  a 300 s budget is irrelevant.

## A note on terms

Vercel Hobby is limited to non-commercial personal use. This is not an additional constraint:
Microsoft's Game Content Usage Rules already forbid monetizing this project. Both would be breached
by the same decision, which makes it a product question rather than an infrastructure one.
