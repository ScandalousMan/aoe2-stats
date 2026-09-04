#!/usr/bin/env python3
"""Nightly free-tier watch (T100).

`docs/adr/0002-hosting.md`'s own "Risks accepted" section states the mitigation this script *is*:
"Free-tier ceilings could stall ingestion silently. Mitigation: the nightly job warns at 70% of any
allowance, so the phase-2 move is planned rather than forced." Nothing before this task actually did
that — the job was a `TODO` placeholder in `.github/workflows/nightly.yml` — so a ceiling could have
been crossed with nothing but a print statement nobody reads, which is exactly the silent stall the
ADR names. This raises a real, persisted severity-2 `free_tier` alert (`AlertKind.FREE_TIER`,
`packages/storage/src/aoe2stats_storage/models.py`) through `raise_alert`
(`packages/core/src/aoe2stats_core/alerting.py`) instead, and fails the job itself so `.github/
workflows/nightly.yml`'s `report` job opens an issue — a print alone answers to nobody, the same
reason `cron_liveness.py` and `capture_audit.py` both fail loudly rather than only logging.

**The three allowances `docs/adr/0002-hosting.md`'s Decision table names, of which two can be
measured here and one cannot:**

- **Cloudflare R2 stored bytes** (10 GB free): measured as the sum of `replay_captures.zip_bytes`
  across every row that ever completed an upload (`zip_bytes IS NOT NULL`). Constitution IV — the
  original replay zip is "never modified and never deleted" — is what makes this sum exact rather
  than an estimate: nothing in this codebase ever shrinks what R2 holds behind a `stored` row, so
  the total this script already durably records *is* what R2 holds, with no second, independently
  billed call to R2's own usage API needed to double-check it.
- **Neon storage** (0.5 GB free): measured with `pg_database_size(current_database())`, over the
  exact same `DATABASE_URL` connection every other script in this directory already opens — not a
  separate Neon API call, which would need a Neon API token this project has no environment variable
  for.
- **Vercel invocations** (1 M free/month): **not measured**. Vercel exposes no invocation count over
  either connection this script already holds (`DATABASE_URL`, and R2's usage is read from the
  database above rather than from R2 itself) — only through the Vercel API, which needs a Vercel API
  token this project has no wired credential or environment variable for. Constitution III confines
  every external network call to `packages/providers`, and `scripts/checks` is deliberately outside
  it (plan.md), so this script may not add one merely to read a usage counter. Inventing a number
  here would be worse than silence: `check_vercel_invocations` below prints an explicit skip message
  instead, naming exactly what is missing, and never contributes to this script's exit code.

Ceiling values are not restated from `docs/adr/0002-hosting.md` as bare literals: each is read from
an environment variable, falling back to the ADR's own figure exactly the way `cron_liveness.py`'s
`_read_run_budget_seconds` falls back to `_DEFAULT_INGEST_RUN_BUDGET_SECONDS` — a knob a deployment
can override (a provider raising or lowering a free tier is exactly the kind of fact that changes
without this repository changing), never an independently invented number.

**A fourth allowance, added by 003's T378: recordings retained for analysis
(`retained_recordings.zip_bytes`, `data-model.md`), watched against `ANALYSIS_RETENTION_CAP_BYTES`
(FR-047, already a settings key elsewhere — `apps/api/src/aoe2stats_api/settings.py`,
`.env.example`).** `retained_recordings` is a separate table under its own object-store prefix
(`retained_recording_object_key`, `packages/storage/src/aoe2stats_storage/objects.py`) precisely so
it is never counted together with `replay_captures` — 001's capture archive and 003's retained
analysis copies are the same kind of bytes under two different legal bases and two different
lifetimes (data-model.md's `retained_recordings` section), and folding one sum into the other would
misstate both ceilings at once, which is the failure FR-048 exists to prevent, arriving through this
monitor rather than through a query. `retained_recording_bytes` below sums only that table, the same
way `r2_stored_bytes` sums only `replay_captures` — neither function's `SELECT` mentions the other's
table, so the separation is enforced by the query shape, not merely by convention.

Usage:  uv run scripts/checks/free_tier_watch.py
Exit:   0 if every measured allowance is under 70% of its ceiling (Vercel invocations never counts,
        being unmeasured); 1 if any measured allowance is at or over 70% — a `free_tier` alert is
        raised for each one that is.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord, raise_alert
from aoe2stats_storage.models import Alert as AlertRow
from aoe2stats_storage.models import AlertKind, ReplayCapture, RetainedRecording
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

_DATABASE_URL_ENV = "DATABASE_URL"

#: `docs/adr/0002-hosting.md`'s "Risks accepted" section, verbatim: "the nightly job warns at 70% of
#: any allowance". Not a per-allowance knob: the ADR states one fraction for every allowance, so one
#: constant is what "the same rule everywhere" looks like in code.
WARN_THRESHOLD_FRACTION = 0.70

#: Decimal GB, matching how every provider in `docs/adr/0002-hosting.md`'s Decision table quotes its
#: own allowance (Cloudflare, Neon and Vercel all market storage in decimal, not binary, units).
_BYTES_PER_GB = 1_000_000_000

_R2_FREE_TIER_BYTES_ENV = "R2_FREE_TIER_BYTES"
#: `docs/adr/0002-hosting.md`, Decision table: "Replay storage | Cloudflare R2 ... | **10 GB**, 1 M
#: writes, 10 M reads, zero egress". Only the stored-bytes figure is watched by this script — the
#: write/read counts are Cloudflare API metrics this project has no credentialed access to, the same
#: reasoning `check_vercel_invocations` states at length for Vercel's own invocation count.
_DEFAULT_R2_FREE_TIER_BYTES = 10 * _BYTES_PER_GB

_NEON_FREE_TIER_BYTES_ENV = "NEON_FREE_TIER_STORAGE_BYTES"
#: `docs/adr/0002-hosting.md`, Decision table: "Database | Neon free, EU region | **0.5 GB**
#: storage, 100 CU-hours/month". Only the storage figure is watched — CU-hours is compute time,
#: not a size `pg_database_size` can answer.
_DEFAULT_NEON_FREE_TIER_BYTES = int(0.5 * _BYTES_PER_GB)

_VERCEL_FREE_TIER_INVOCATIONS_ENV = "VERCEL_FREE_TIER_INVOCATIONS"
#: `docs/adr/0002-hosting.md`, Decision table: "API | Vercel Python Function ... | **1 M**
#: invocations". Kept here, unused by any measurement below, so the one number this script would
#: need the moment a Vercel-API-backed measurement becomes possible is already named in one place
#: rather than invented again at that point.
_DEFAULT_VERCEL_FREE_TIER_INVOCATIONS = 1_000_000

_ANALYSIS_RETENTION_CAP_BYTES_ENV = "ANALYSIS_RETENTION_CAP_BYTES"
#: FR-047's own total retention cap for `retained_recordings`, already a settings key elsewhere
#: (`apps/api/src/aoe2stats_api/settings.py`'s `analysis_retention_cap_bytes`) — not a new one
#: invented here. The default mirrors `.env.example`'s own product choice (2 GiB, set below R2's
#: 10 GB free tier so capture always has headroom): a ceiling this script falls back to only when
#: the environment does not set one, the same convention `_DEFAULT_R2_FREE_TIER_BYTES` and
#: `_DEFAULT_NEON_FREE_TIER_BYTES` follow above.
_DEFAULT_ANALYSIS_RETENTION_CAP_BYTES = 2 * 1024**3


def usage_fraction(used_bytes: int, ceiling_bytes: int) -> float:
    """`used_bytes / ceiling_bytes`, pure and DB-free so the 70% boundary is testable without a
    database. `ceiling_bytes` is always a positive constant or environment override in production,
    but a non-positive value here reads as "unmeasurable" (0.0) rather than raising: a
    misconfigured ceiling must not crash the whole nightly job over one allowance.
    """
    if ceiling_bytes <= 0:
        return 0.0
    return used_bytes / ceiling_bytes


def is_over_warn_threshold(fraction: float) -> bool:
    """True at or above `WARN_THRESHOLD_FRACTION` — `>=`, not `>`: the ADR's own "70%" is the
    trigger point itself, not a strictly-past-it one.
    """
    return fraction >= WARN_THRESHOLD_FRACTION


async def r2_stored_bytes(session: AsyncSession) -> int:
    """The sum of `replay_captures.zip_bytes` across every row that ever completed an upload — see
    the module docstring for why this sum is exact rather than an estimate. `0` when the table is
    empty or nothing has ever stored (`COALESCE`, matching `capture_audit.py`'s own `expired_total`
    for the identical reason: Postgres returns `NULL` for a `SUM` over zero rows).
    """
    result = await session.execute(
        select(func.coalesce(func.sum(ReplayCapture.zip_bytes), 0)).where(
            ReplayCapture.zip_bytes.is_not(None)
        )
    )
    # `COALESCE` already guarantees a non-null value at runtime; the `or 0` below is only to
    # narrow the static type `func.sum` leaves as `int | None` (`zip_bytes` is itself nullable,
    # unlike `capture_audit.py`'s `IngestRun.expired_total`, which is why that sibling's identical
    # pattern needs no such narrowing).
    return int(result.scalar_one() or 0)


async def neon_storage_bytes(session: AsyncSession) -> int:
    """The current database's own on-disk size, in bytes, read with Postgres's built-in
    `pg_database_size(current_database())` — over the same `DATABASE_URL` connection every other
    script in this directory already opens, not a separate, credentialed Neon API call.
    """
    result = await session.execute(select(func.pg_database_size(func.current_database())))
    return int(result.scalar_one())


async def retained_recording_bytes(session: AsyncSession) -> int:
    """The sum of `retained_recordings.zip_bytes` (003, FR-033/FR-047) — a table `r2_stored_bytes`
    above never touches, and this `SELECT` never touches `replay_captures` in turn: the two totals
    are computed by two disjoint queries, not filtered apart from one shared one, so a row seeded
    into either table can never contribute to the other's sum. `data-model.md`'s own
    `retained_recordings` section: "`ANALYSIS_RETENTION_CAP_BYTES` counts the retained copy only —
    the capture is 001's and is already counted under 001's prefix (FR-048), which is the whole
    reason T378 counts the two prefixes separately." `zip_bytes` is `NOT NULL` on this table
    (unlike `ReplayCapture.zip_bytes`, set only once an upload completes), so no `IS NOT NULL`
    filter is needed here; `COALESCE` still guards the empty-table case the same way
    `r2_stored_bytes` does.
    """
    result = await session.execute(select(func.coalesce(func.sum(RetainedRecording.zip_bytes), 0)))
    return int(result.scalar_one() or 0)


def check_vercel_invocations() -> None:
    """Deliberately measures nothing — see the module docstring's third bullet for exactly what is
    missing and why. Exists as its own function, rather than an inline print in `_run`, so the gap
    is named at the same call-site level as the two real measurements above it, not folded away as
    an afterthought.
    """
    print(
        "free-tier-watch: SKIP — Vercel invocations cannot be measured from here. Vercel exposes "
        "usage only through its own API, which needs a Vercel API token this project has no wired "
        "environment variable for; constitution III confines every external network call to "
        "packages/providers, and scripts/checks sits outside it (plan.md). Watch this allowance "
        f"({_DEFAULT_VERCEL_FREE_TIER_INVOCATIONS:,} invocations/month free, "
        f"{_VERCEL_FREE_TIER_INVOCATIONS_ENV} names the ceiling if a credentialed measurement is "
        "ever wired) manually in the Vercel dashboard until then."
    )


@dataclass(frozen=True, slots=True)
class _Allowance:
    """One measured allowance, paired with the ceiling it is measured against — the unit `_run`
    below loops over rather than repeating the same five lines three times.
    """

    name: str
    used_bytes: int
    ceiling_bytes: int


class _DatabaseAlertSink:
    """The `AlertSink` this script's own `raise_alert` call writes through.

    Mirrors `apps/ingester/src/aoe2stats_ingester/capture.py`'s `_DatabaseAlertSink` exactly for the
    `write` half — same table, same construction — but is not imported from there:
    `scripts/checks` sits deliberately outside the uv workspace (plan.md) and does not reach into
    `apps/ingester`'s internals, the same reason `capture_audit.py`'s `_nearest_rank` is a verbatim
    copy rather than an import. Unlike that class, `unacknowledged_severity_one` is never a real
    query here: this script only ever produces alerts, never reads them back (that is
    `alert_audit.py`'s job), so it raises rather than risking a second, silently diverging
    implementation of a read nothing here calls — the same reasoning `alert_audit.py`'s own
    `_ReadOnlyAlertSink.write` states for the opposite half.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        row = AlertRow(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=dict(detail) if detail is not None else None,
            ingest_run_id=ingest_run_id,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AlertRecord(
                id=row.id,
                kind=row.kind,
                severity=row.severity,
                detail=row.detail,
                raised_at=row.raised_at,
                ingest_run_id=row.ingest_run_id,
                acknowledged_at=row.acknowledged_at,
            )

    async def unacknowledged_severity_one(self) -> Sequence[AlertRecord]:
        raise NotImplementedError(
            "free_tier_watch.py only ever raises alerts, never reads them back; see the class "
            "docstring for why this exists at all."
        )


def _read_int_env(name: str, default: int) -> int:
    """`name` from the environment, falling back to `default` — the same pattern
    `cron_liveness.py`'s `_read_run_budget_seconds` uses for `INGEST_RUN_BUDGET_SECONDS`. A missing
    ceiling override is not an error: the ADR's own figure, carried as `default`, is a sane number
    to check against on its own.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


async def _run() -> int:
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"free-tier-watch: {_DATABASE_URL_ENV} is not set; nothing to check against.")
        return 1

    session_factory = build_session_factory(build_engine(database_url))
    sink = _DatabaseAlertSink(session_factory)

    async with session_factory() as session:
        allowances = [
            _Allowance(
                name="Cloudflare R2 stored bytes",
                used_bytes=await r2_stored_bytes(session),
                ceiling_bytes=_read_int_env(_R2_FREE_TIER_BYTES_ENV, _DEFAULT_R2_FREE_TIER_BYTES),
            ),
            _Allowance(
                name="Neon storage",
                used_bytes=await neon_storage_bytes(session),
                ceiling_bytes=_read_int_env(
                    _NEON_FREE_TIER_BYTES_ENV, _DEFAULT_NEON_FREE_TIER_BYTES
                ),
            ),
            # 003's T378: `retained_recordings` is a table `r2_stored_bytes` above never touches,
            # thresholded against its own cap (FR-047) rather than folded into R2's — counting the
            # two together is exactly the double-count FR-048 forbids, arriving through this
            # monitor rather than through a query (module docstring).
            _Allowance(
                name="Analysis retention (retained recordings)",
                used_bytes=await retained_recording_bytes(session),
                ceiling_bytes=_read_int_env(
                    _ANALYSIS_RETENTION_CAP_BYTES_ENV, _DEFAULT_ANALYSIS_RETENTION_CAP_BYTES
                ),
            ),
        ]

    ok = True
    for allowance in allowances:
        fraction = usage_fraction(allowance.used_bytes, allowance.ceiling_bytes)
        if is_over_warn_threshold(fraction):
            ok = False
            print(
                f"free-tier-watch: WARN — {allowance.name} at {fraction:.0%} of its free "
                f"allowance ({allowance.used_bytes:,} / {allowance.ceiling_bytes:,} bytes). "
                "docs/adr/0002-hosting.md: plan the phase-2 move rather than being forced into it."
            )
            await raise_alert(
                sink,
                kind=AlertKind.FREE_TIER,
                severity=2,
                detail={
                    "allowance": allowance.name,
                    "used_bytes": allowance.used_bytes,
                    "ceiling_bytes": allowance.ceiling_bytes,
                    "fraction": fraction,
                },
            )
        else:
            print(
                f"free-tier-watch: OK — {allowance.name} at {fraction:.0%} of its free allowance "
                f"({allowance.used_bytes:,} / {allowance.ceiling_bytes:,} bytes)."
            )

    check_vercel_invocations()

    return 0 if ok else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
