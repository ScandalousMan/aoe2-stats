"""Tests for `scripts/ops/revalidate_quarantined.py` (T673).

The selection, the read-back and the writes are tested where they live
(`apps/ingester/tests/test_revalidate_quarantined.py`); this file pins what the operator command
adds: a provider that refuses every call, the environment it needs and refuses without, the
`--after` contract, and a report that cannot put an engine's terminal escape codes on a terminal.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_core.replay.validation import ReplayValidationResult
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ReplayCapture,
)
from aoe2stats_storage.objects import ObjectNotFound

# See scripts/checks/tests/test_cron_liveness.py for why these are re-exported this way.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

from scripts.ops.revalidate_quarantined import (
    RefusedDownloadError,
    SettingsError,
    _NoReplayProvider,
    build_arg_parser,
    format_report,
    main,
    object_store_from_settings,
    revalidate,
    settings_from_environment,
)

_BODY = b"recording"
_SECRETS = {
    "S3_ACCESS_KEY_ID": "very-secret-key-id",
    "S3_SECRET_ACCESS_KEY": "very-secret-value",
}
_ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"


def _application_environment(database_url: str, **overrides: str) -> dict[str, str]:
    """A complete, valid application environment, taken from `.env.example`'s own keys so that a
    key added there is added here without anyone editing this file (blank values are the secrets
    the template leaves for the deployment to fill)."""
    environ: dict[str, str] = {}
    for line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            environ[match.group(1)] = match.group(2) or f"test-{match.group(1).lower()}"
    environ.update(
        DATABASE_URL=database_url,
        S3_ENDPOINT_URL="https://account.eu.r2.cloudflarestorage.com",
        S3_REGION="auto",
        CRON_SECRET="c" * 32,
        BETA_ALLOWLIST_STEAM_IDS="",
        **_SECRETS,
    )
    environ.update(overrides)
    return environ


def _must_not_be_called(*_: Any) -> Any:
    raise AssertionError("the run was refused before this was built")


class _GetOnlyStore:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.gets: list[str] = []

    async def get(self, key: str) -> bytes:
        self.gets.append(key)
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]

    async def put(self, key: str, body: bytes, *, content_type: str = "") -> None:
        raise AssertionError("a re-validation never writes an object")

    async def delete(self, key: str) -> None:
        raise AssertionError("a re-validation never deletes an object")


class _Opens:
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        return ReplayValidationResult(
            inner_filename="AgeIIDE_Replay_1.aoe2record",
            inner_bytes=9,
            engine_name="aoe2rec-py",
            engine_version="0.1.24",
        )


async def _seed(session: AsyncSession, store: _GetOnlyStore, game_id: int) -> uuid.UUID:
    completed_at = datetime.now(UTC) - timedelta(days=4)
    key = f"replays/{game_id}.zip"
    store.objects[key] = _BODY
    session.add(AoeProfile(profile_id=game_id + 7, alias="p", country="FR"))
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    capture_id = uuid.uuid4()
    session.add(
        ReplayCapture(
            id=capture_id,
            game_id=game_id,
            profile_id=game_id + 7,
            status=CaptureStatus.QUARANTINED,
            capture_deadline_at=completed_at + timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
            object_key=key,
            zip_bytes=len(_BODY),
            zip_sha256=hashlib.sha256(_BODY).hexdigest(),
            last_error="PanicException: boom",
            attempts=1,
        )
    )
    await session.commit()
    return capture_id


async def test_the_provider_handed_to_the_drain_refuses_every_call() -> None:
    with pytest.raises(RefusedDownloadError):
        await _NoReplayProvider().fetch_replay(1, 2)


async def test_a_run_stores_the_row_through_the_real_drain_and_only_reads_the_store(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    store = _GetOnlyStore({})
    capture_id = await _seed(db_session, store, 800_001)

    report = await revalidate(session_factory, object_store=store, validator=_Opens(), limit=5)

    assert [o.outcome for o in report.outcomes] == ["stored"]
    assert store.gets == [f"replays/{800_001}.zip"]
    db_session.expire_all()
    row = (
        await db_session.execute(select(ReplayCapture).where(ReplayCapture.id == capture_id))
    ).scalar_one()
    assert row.status == CaptureStatus.STORED
    assert row.validated_by == "aoe2rec-py@0.1.24"


async def test_a_dry_run_selects_without_an_object_store_an_engine_or_a_write(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    store = _GetOnlyStore({})
    capture_id = await _seed(db_session, store, 800_002)
    before = await _snapshot(db_session, capture_id)

    report = await revalidate(
        session_factory, object_store=None, validator=None, limit=5, dry_run=True
    )

    assert [o.outcome for o in report.outcomes] == ["selected"]
    assert store.gets == []
    assert await _snapshot(db_session, capture_id) == before


async def _snapshot(db_session: AsyncSession, capture_id: uuid.UUID) -> tuple[Any, ...]:
    db_session.expire_all()
    row = (
        await db_session.execute(select(ReplayCapture).where(ReplayCapture.id == capture_id))
    ).scalar_one()
    return (row.status, row.last_error, row.stored_at, row.validated_by, row.inner_bytes)


def test_the_object_store_is_built_from_the_applications_own_validated_settings() -> None:
    settings = settings_from_environment(_application_environment("postgresql+psycopg://u:p@h/d"))
    assert object_store_from_settings(settings) is not None


def test_a_missing_application_key_is_named_and_no_value_is_printed() -> None:
    environ = _application_environment("postgresql+psycopg://u:p@h/d")
    del environ["S3_BUCKET"]
    with pytest.raises(SettingsError) as caught:
        settings_from_environment(environ)
    assert "S3_BUCKET" in str(caught.value)
    assert not any(value in str(caught.value) for value in _SECRETS.values())


def test_a_real_run_with_an_s3_endpoint_that_carries_a_bucket_path_is_refused_by_settings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The application's own validator, not a copy of it: `Settings` rejects the account host
    with the bucket appended, which the object store would answer as a riddle on first use."""
    environ = _application_environment(
        "postgresql+psycopg://u:p@127.0.0.1:1/none",
        S3_ENDPOINT_URL="https://account.eu.r2.cloudflarestorage.com/bucket",
    )

    assert main([], environ=environ, make_object_store=_must_not_be_called) == 1

    err = capsys.readouterr().err
    assert "S3_ENDPOINT_URL" in err
    assert not any(value in err for value in _SECRETS.values())


def test_a_dry_run_without_a_database_url_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--dry-run"], environ={}) == 1
    assert "DATABASE_URL is not set" in capsys.readouterr().err


def test_a_real_run_without_the_applications_environment_is_refused_and_names_the_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    environ = {"DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:1/none"}
    assert main([], environ=environ, make_object_store=_must_not_be_called) == 1
    assert "S3_ENDPOINT_URL" in capsys.readouterr().err


def test_a_limit_below_one_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--limit", "0"], environ={"DATABASE_URL": "x"}) == 1
    assert "--limit" in capsys.readouterr().err


_AT = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
_CURSOR_ID = uuid.UUID(int=7)


def test_after_is_a_timestamp_and_an_id_and_normalises_the_offset() -> None:
    args = build_arg_parser().parse_args(["--after", f"2026-09-30T14:00:00+02:00,{_CURSOR_ID}"])
    assert args.after == (_AT, _CURSOR_ID)


@pytest.mark.parametrize(
    ("value", "needle"),
    [
        pytest.param("2026-09-30T12:00:00+00:00", "the capture id is required", id="no-id"),
        pytest.param(f"2026-09-30T12:00:00,{_CURSOR_ID}", "time zone", id="no-zone"),
        pytest.param("2026-09-30T12:00:00+00:00,not-a-uuid", "capture id", id="bad-id"),
        pytest.param(f",{_CURSOR_ID}", "timestamp", id="no-timestamp"),
        pytest.param("", "the capture id is required", id="empty"),
    ],
)
def test_a_timestamp_without_an_id_or_a_malformed_cursor_is_refused(
    value: str, needle: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bare timestamp must not silently fall back to the lossy comparison: it would skip every
    capture of a shared match that the previous page cut between."""
    with pytest.raises(SystemExit) as refused:
        build_arg_parser().parse_args(["--after", value])
    assert refused.value.code == 2
    assert needle in capsys.readouterr().err


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-30T12:00:00+00:00",
        f"2026-09-30T12:00:00,{_CURSOR_ID}",
        "2026-09-30T12:00:00+00:00,not-a-uuid",
        "",
    ],
)
def test_main_refuses_a_malformed_cursor_with_exit_one_before_touching_anything(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["--after", value],
        environ=_application_environment("postgresql+psycopg://u:p@127.0.0.1:1/none"),
    )
    assert code == 1
    assert "--after" in capsys.readouterr().err


async def test_the_printed_continuation_value_parses_and_resumes_at_the_right_row(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Three captures of one match, `--limit 1`: follow the printed `--after` value, through the
    argument parser, until the report stops asking to continue. Each row once, in id order."""
    completed_at = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    db_session.add(
        Match(
            game_id=810_001,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    ids = [uuid.UUID(int=n) for n in (3, 1, 2)]
    for index, capture_id in enumerate(ids):
        profile_id = 8_100_010 + index
        db_session.add(AoeProfile(profile_id=profile_id, alias="p", country="FR"))
        await db_session.flush()
        db_session.add(
            ReplayCapture(
                id=capture_id,
                game_id=810_001,
                profile_id=profile_id,
                status=CaptureStatus.QUARANTINED,
                capture_deadline_at=completed_at + timedelta(days=21),
                source=CaptureSource.AUTOMATIC,
                object_key=f"replays/810001-{index}.zip",
                zip_bytes=1,
                zip_sha256="0" * 64,
                last_error="EngineParseError: aoe2rec-py rejected the replay: x",
                attempts=1,
            )
        )
    await db_session.commit()

    examined: list[uuid.UUID] = []
    argv: list[str] = []
    for _ in range(10):
        args = build_arg_parser().parse_args(argv)
        report = await revalidate(
            session_factory,
            object_store=None,
            validator=None,
            limit=1,
            after=args.after,
            dry_run=True,
        )
        examined += [o.capture_id for o in report.outcomes]
        lines = format_report(report, dry_run=True)
        continuation = [line for line in lines if "--after " in line]
        if not report.truncated:
            assert continuation == []
            break
        assert len(continuation) == 1
        argv = ["--after", continuation[0].split("--after ", 1)[1]]
    else:
        raise AssertionError("did not terminate")

    assert examined == [uuid.UUID(int=n) for n in (1, 2, 3)]


def test_a_reason_with_terminal_escape_codes_is_printed_as_one_safe_line() -> None:
    from aoe2stats_ingester.capture import RevalidationOutcome, RevalidationReport

    panic = "PanicException: called `unwrap()`\n 0: \x1b[1mError: bad magic\x1b[22m\n" + "x" * 500
    when = datetime(2026, 9, 27, tzinfo=UTC)
    report = RevalidationReport(
        outcomes=(RevalidationOutcome(uuid.uuid4(), 1, 2, when, "still_quarantined", panic),),
        truncated=True,
        last_completed_at=when,
        last_capture_id=uuid.UUID(int=9),
    )

    lines = format_report(report, dry_run=False)

    assert "\x1b" not in "".join(lines)
    assert all("\n" not in line for line in lines)
    assert len(lines[0]) < 300
    assert any(
        line.endswith(f"--after 2026-09-27T00:00:00+00:00,{uuid.UUID(int=9)}") for line in lines
    )


def test_the_report_counts_the_unselected_rows_by_label_and_a_stop_is_named() -> None:
    from aoe2stats_ingester.capture import RevalidationReport

    report = RevalidationReport(
        outcomes=(),
        truncated=False,
        last_completed_at=None,
        unselected_by_reason=(("PanicException (archival objected)", 2), ("wall-clock cap", 1)),
        aborted_by="ClientError",
    )

    lines = format_report(report, dry_run=True)

    assert any("3 other quarantined row(s)" in line for line in lines)
    assert any(
        line.endswith("PanicException (archival objected)") and "2" in line for line in lines
    )
    assert any("STOPPED" in line and "ClientError" in line for line in lines)
    assert not any("--after" in line for line in lines)


# --- The entry point, end to end (level: `main`) ---------------------------------------------


class _ConfiguredByTheRun:
    """What `main` is allowed to build: it records that it was asked, and hands back fakes."""

    def __init__(self, store: _GetOnlyStore) -> None:
        self.store = store
        self.stores_built = 0
        self.validators_built = 0

    def make_object_store(self, settings: Any) -> Any:
        self.stores_built += 1
        return self.store

    def make_validator(self) -> Any:
        self.validators_built += 1
        return _Opens()


async def test_main_drives_a_successful_dry_run_and_then_a_real_run(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One test, the whole entry point: argument parsing, environment, the drain, the report and
    the exit code. A dry run first (it must neither build the store nor load the engine), then
    the real run over the same row."""
    store = _GetOnlyStore({})
    capture_id = await _seed(db_session, store, 800_100)
    # An unselected quarantined row, so the dry run has something to count.
    other = await _seed(db_session, store, 800_101)
    row = await db_session.get(ReplayCapture, other)
    assert row is not None
    row.last_error = "reclaim checksum mismatch for 'k': row records a, object store holds b"
    await db_session.commit()
    run = _ConfiguredByTheRun(store)
    monkeypatch.delitem(sys.modules, "aoe2stats_replay_engine.aoe2rec", raising=False)

    dry = await asyncio.to_thread(
        main,
        ["--dry-run", "--limit", "5"],
        {"DATABASE_URL": database_url},
        make_object_store=run.make_object_store,
        make_validator=run.make_validator,
    )

    out = capsys.readouterr().out
    assert dry == 0
    assert "selected" in out and "game 800100" in out
    assert "1 other quarantined row(s)" in out and "reclaim checksum mismatch" in out
    assert "dry run, nothing was read or written" in out
    assert (run.stores_built, run.validators_built) == (0, 0)
    assert "aoe2stats_replay_engine.aoe2rec" not in sys.modules
    assert store.gets == []
    assert (await _snapshot(db_session, capture_id))[0] == CaptureStatus.QUARANTINED

    real = await asyncio.to_thread(
        main,
        ["--limit", "5"],
        _application_environment(database_url),
        make_object_store=run.make_object_store,
        make_validator=run.make_validator,
    )

    out = capsys.readouterr().out
    assert real == 0
    assert "stored" in out and "1 row(s) examined (stored=1)" in out
    assert (run.stores_built, run.validators_built) == (1, 1)
    assert store.gets == [f"replays/{800_100}.zip"]
    assert (await _snapshot(db_session, capture_id))[0] == CaptureStatus.STORED
    assert (await _snapshot(db_session, other))[0] == CaptureStatus.QUARANTINED


async def test_main_ends_non_zero_after_the_report_when_an_object_failed_its_integrity_check(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = _GetOnlyStore({})
    capture_id = await _seed(db_session, store, 800_110)
    store.objects[f"replays/{800_110}.zip"] = b"drifted"
    before = await _snapshot(db_session, capture_id)
    run = _ConfiguredByTheRun(store)

    code = await asyncio.to_thread(
        main,
        ["--limit", "5"],
        _application_environment(database_url),
        make_object_store=run.make_object_store,
        make_validator=run.make_validator,
    )

    out = capsys.readouterr().out
    assert code == 1
    assert "integrity_failure" in out and "1 row(s) examined" in out
    assert await _snapshot(db_session, capture_id) == before


class _TransportDownStore(_GetOnlyStore):
    async def get(self, key: str) -> bytes:
        raise ConnectionError("https://account.example/secret-path is unreachable")


async def test_main_stops_non_zero_on_a_store_error_and_prints_its_class_never_its_text(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = _TransportDownStore({})
    capture_id = await _seed(db_session, store, 800_120)
    before = await _snapshot(db_session, capture_id)
    run = _ConfiguredByTheRun(store)

    code = await asyncio.to_thread(
        main,
        ["--limit", "5"],
        _application_environment(database_url),
        make_object_store=run.make_object_store,
        make_validator=run.make_validator,
    )

    out = capsys.readouterr().out
    assert code == 1
    assert "STOPPED" in out and "ConnectionError" in out
    assert "secret-path" not in out
    assert await _snapshot(db_session, capture_id) == before
