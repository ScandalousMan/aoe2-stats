"""Tests for `scripts/ops/revalidate_quarantined.py` (T673).

The selection, the read-back and the writes are tested where they live
(`apps/ingester/tests/test_revalidate_quarantined.py`); this file pins what the operator command
adds: a provider that refuses every call, the environment it needs and refuses without, the
`--after` contract, and a report that cannot put an engine's terminal escape codes on a terminal.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
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
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.objects import ObjectNotFound

# See scripts/checks/tests/test_cron_liveness.py for why these are re-exported this way.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

from scripts.ops.revalidate_quarantined import (
    RefusedDownloadError,
    SettingsError,
    _NoReplayProvider,
    build_arg_parser,
    exit_code,
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


async def _link(session: AsyncSession, profile_id: int) -> None:
    """An active link held by a user who has not objected: a capture needs one to be selected."""
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    steam_id64 = f"76561198{profile_id:010d}"
    session.add(User(id=user_id, created_at=now, allowlisted_at=now, archival_objected_at=None))
    session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user_id, verified_at=now, last_sign_in_at=now)
    )
    await session.flush()
    session.add(
        ProfileLink(
            id=uuid.uuid4(),
            user_id=user_id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
        )
    )
    await session.commit()


async def _seed(
    session: AsyncSession,
    store: _GetOnlyStore,
    game_id: int,
    *,
    capture_id: uuid.UUID | None = None,
) -> uuid.UUID:
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
    capture_id = capture_id or uuid.uuid4()
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
    await _link(session, game_id + 7)
    return capture_id


async def _seed_second_capture(
    session: AsyncSession,
    store: _GetOnlyStore,
    game_id: int,
    *,
    capture_id: uuid.UUID,
    profile_id: int,
) -> None:
    """A second tracked profile's capture of the match `_seed` made: the same `completed_at`
    (it is the match's), its own object key, an active link."""
    key = f"replays/{game_id}-{profile_id}.zip"
    store.objects[key] = _BODY
    session.add(AoeProfile(profile_id=profile_id, alias="p", country="FR"))
    await session.flush()
    session.add(
        ReplayCapture(
            id=capture_id,
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.QUARANTINED,
            capture_deadline_at=datetime.now(UTC) + timedelta(days=17),
            source=CaptureSource.AUTOMATIC,
            object_key=key,
            zip_bytes=len(_BODY),
            zip_sha256=hashlib.sha256(_BODY).hexdigest(),
            last_error="PanicException: boom",
            attempts=1,
        )
    )
    await session.commit()
    await _link(session, profile_id)


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


@pytest.fixture
def no_ambient_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Settings` reads the process environment as well as the mapping it is given, so a test that
    expects a refusal must not inherit a developer's or CI's variables: clear all of them."""
    for key in list(os.environ):
        monkeypatch.delenv(key)


def test_a_missing_application_key_is_named_and_no_value_is_printed(
    no_ambient_environment: None,
) -> None:
    """The mapping lacks the bucket name, and so must the process: the runbook's first step
    exports it, and `Settings` would take it from there (T673c)."""
    environ = _application_environment("postgresql+psycopg://u:p@h/d")
    del environ["S3_BUCKET"]
    with pytest.raises(SettingsError) as caught:
        settings_from_environment(environ)
    assert "S3_BUCKET" in str(caught.value)
    assert not any(value in str(caught.value) for value in _SECRETS.values())


def test_a_real_run_with_an_s3_endpoint_that_carries_a_bucket_path_is_refused_by_settings(
    capsys: pytest.CaptureFixture[str], no_ambient_environment: None
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
    capsys: pytest.CaptureFixture[str], no_ambient_environment: None
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


_RUNBOOK = "docs/runbooks/revalidate-quarantined.md"


def _after_texts(capsys: pytest.CaptureFixture[str]) -> dict[str, str]:
    """The two texts that tell an operator which `--after` value to give: the option's help and
    the refusal of a bare timestamp."""
    parser = build_arg_parser()
    [help_text] = [a.help for a in parser._actions if "--after" in a.option_strings]
    with pytest.raises(SystemExit):
        parser.parse_args(["--after", "2026-09-30T12:00:00+00:00"])
    return {"help": " ".join((help_text or "").split()), "refusal": capsys.readouterr().err}


@pytest.mark.parametrize("text", ["help", "refusal"])
def test_neither_after_text_offers_the_previous_runs_value_after_a_stop_and_both_name_the_runbook(
    text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """After a stop, the only `--after` value the previous run printed is the stop line's, which
    excludes the stopped row; the runbook names the one to give. So neither text may tell the
    operator to copy what the previous run printed, and both point at the runbook for a stop. The
    value a "more candidates remain" line prints is still the one to copy for a page."""
    out = _after_texts(capsys)[text]

    assert "previous run printed" not in out
    assert "more candidates remain" in out
    assert _RUNBOOK in out


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
    for index in range(len(ids)):
        await _link(db_session, 8_100_010 + index)

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


def test_the_report_counts_the_unselected_rows_by_label() -> None:
    from aoe2stats_ingester.capture import RevalidationReport

    report = RevalidationReport(
        outcomes=(),
        truncated=False,
        last_completed_at=None,
        unselected_by_reason=(("PanicException (archival objected)", 2), ("wall-clock cap", 1)),
    )

    lines = format_report(report, dry_run=True)

    assert any("3 other quarantined row(s)" in line for line in lines)
    assert any(
        line.endswith("PanicException (archival objected)") and "2" in line for line in lines
    )
    assert exit_code(report) == 0


@pytest.mark.parametrize(
    ("stop", "needle"),
    [
        pytest.param({"aborted_by": "ClientError"}, "the object store failed", id="store"),
        pytest.param(
            {"write_failed_by": "OperationalError"}, "a database error stopped the run", id="db"
        ),
    ],
)
def test_a_stopped_run_names_the_error_class_prints_no_more_candidates_line_and_exits_non_zero(
    stop: dict[str, str], needle: str
) -> None:
    """A truncated report with a cursor prints the "more candidates remain" line; a stopped one,
    which carries the row it stopped at, does not: its stop line carries the `--after` value
    instead. Contrast: the same report, not stopped, does print it and exits zero."""
    from aoe2stats_ingester.capture import (
        RevalidationOutcome,
        RevalidationReport,
        RevalidationStop,
    )

    when = datetime(2026, 9, 27, tzinfo=UTC)
    outcomes = (RevalidationOutcome(uuid.uuid4(), 1, 2, when, "stored"),)
    common: dict[str, Any] = {
        "outcomes": outcomes,
        "truncated": True,
        "last_completed_at": when,
        "last_capture_id": uuid.UUID(int=9),
    }

    stopped = RevalidationReport(
        **common, stopped_row=RevalidationStop(uuid.UUID(int=10), 3, 4, when), **stop
    )
    lines = format_report(stopped, dry_run=False)
    assert any("STOPPED" in line and needle in line for line in lines)
    [stop_line] = [line for line in lines if "STOPPED" in line]
    assert f"--after {when.isoformat()},{uuid.UUID(int=10)} starts past that row" in stop_line
    assert any(next(iter(stop.values())) in line for line in lines)
    assert not any("more candidates remain" in line for line in lines)
    assert exit_code(stopped) == 1

    running = RevalidationReport(**common)
    assert any("more candidates remain" in line for line in format_report(running, dry_run=False))
    assert exit_code(running) == 0


def test_a_database_stop_says_the_listed_rows_were_examined_not_that_they_were_written() -> None:
    """Level: the report's text (T673c). The report lists every row examined before the database
    error, whatever its outcome: here one `stored`, one `still_quarantined` and one `inconclusive`,
    which was not written at all. So the stop line says "examined", and says nothing about what
    was written, the failing row included (a commit that raises leaves its state unknown). It
    names no write either: the error may have come from the read that tells why a write was
    refused. Contrast: the store stop, which fails on a read before any write for its row, still
    says that row was not written."""
    from aoe2stats_ingester.capture import RevalidationOutcome, RevalidationReport

    when = datetime(2026, 9, 27, tzinfo=UTC)
    outcomes = (
        RevalidationOutcome(uuid.UUID(int=1), 1, 2, when, "stored"),
        RevalidationOutcome(uuid.UUID(int=2), 3, 4, when, "still_quarantined", "PanicException: x"),
        RevalidationOutcome(uuid.UUID(int=3), 5, 6, when, "inconclusive", "wall-clock cap"),
    )
    common: dict[str, Any] = {
        "outcomes": outcomes,
        "truncated": False,
        "last_completed_at": when,
        "last_capture_id": uuid.UUID(int=3),
    }

    lines = format_report(
        RevalidationReport(**common, write_failed_by="OperationalError"), dry_run=False
    )

    [stop] = [line for line in lines if "STOPPED" in line]
    assert "a database error stopped the run: OperationalError" in stop
    assert "write" not in stop
    assert "The rows listed above were examined" in stop
    assert "written" not in stop
    assert "no later row was examined" in stop
    assert any(
        "3 row(s) examined (inconclusive=1, still_quarantined=1, stored=1)" in line
        for line in lines
    )

    [store_stop] = [
        line
        for line in format_report(
            RevalidationReport(**common, aborted_by="ClientError"), dry_run=False
        )
        if "STOPPED" in line
    ]
    assert "The row it failed on was not written" in store_stop


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
    assert "dry run, the database was read; no object was read and nothing was written" in out
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


class _CancelledOnTheSecondGet(_GetOnlyStore):
    async def get(self, key: str) -> bytes:
        if self.gets:
            raise asyncio.CancelledError
        return await super().get(key)


async def test_main_prints_no_report_for_a_page_that_is_interrupted(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Level: `main` (T673c). Only the store stop and the database stop print the rows examined
    so far. A cancellation at the second row's read-back, which is where an interrupt would
    surface (no task is cancelled here), leaves `main` with nothing printed: the first row is
    `stored` and no line says so. Contrast: the two stop tests below, which print it."""
    store = _CancelledOnTheSecondGet({})
    first = await _seed(db_session, store, 800_140)
    await _seed(db_session, store, 800_141)
    run = _ConfiguredByTheRun(store)

    def _call() -> object:
        try:
            return main(
                ["--limit", "5"],
                _application_environment(database_url),
                make_object_store=run.make_object_store,
                make_validator=run.make_validator,
            )
        except BaseException as exc:
            return exc

    result = await asyncio.to_thread(_call)

    assert isinstance(result, asyncio.CancelledError)
    assert capsys.readouterr().out == ""
    assert (await _snapshot(db_session, first))[0] == CaptureStatus.STORED


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


async def test_main_stops_non_zero_on_a_failed_write_and_reports_the_rows_already_examined(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Level: `main`. The second row's write fails; the report of the row examined before it is
    still printed. That row is `stored` here, and of the rows the command writes only a `stored`
    one leaves the selection, so a re-run would not list it again. The error's text (it carries
    SQL) never prints.

    The stand-in replaces the whole write and raises before any statement runs, so the last
    assertion holds for this stand-in only: it says nothing about a row whose real commit
    raises."""
    from sqlalchemy.exc import OperationalError

    from aoe2stats_ingester.capture import CaptureDrain

    store = _GetOnlyStore({})
    first = await _seed(db_session, store, 800_130)
    second = await _seed(db_session, store, 800_131)
    real = CaptureDrain._mark_stored
    calls = {"n": 0}

    async def _second_write_fails(self: Any, *args: Any, **kwargs: Any) -> bool:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OperationalError("UPDATE secret_table SET x = 'secret-value'", {}, Exception("x"))
        return await real(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(CaptureDrain, "_mark_stored", _second_write_fails)
    before = await _snapshot(db_session, second)
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
    assert "1 row(s) examined (stored=1)" in out
    assert "STOPPED" in out and "OperationalError" in out
    assert "The rows listed above were examined" in out
    assert "secret" not in out
    assert (await _snapshot(db_session, first))[0] == CaptureStatus.STORED
    assert await _snapshot(db_session, second) == before


# === T673d: remediation of #129's fourth review ================================================

_REALISTIC_KEY = "replays/511523321/12345678.zip"


async def test_a_checksum_mismatch_line_for_a_realistic_key_carries_both_checksums(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Level: the printed line. `integrity_failure` writes nothing, so its reason exists nowhere
    else; it is printed whole. With an ordinary object key the reason is longer than the width a
    stored reason is cut at, and the checksum the object store holds, the one that lets the
    operator tell corruption from a wrong record, comes last."""
    store = _GetOnlyStore({})
    capture_id = await _seed(db_session, store, 800_200)
    row = await db_session.get(ReplayCapture, capture_id)
    assert row is not None
    row.object_key = _REALISTIC_KEY
    await db_session.commit()
    store.objects[_REALISTIC_KEY] = b"drifted"

    report = await revalidate(session_factory, object_store=store, validator=_Opens(), limit=5)

    [line] = [
        line
        for line in format_report(report, dry_run=False)
        if line.startswith("integrity_failure")
    ]
    recorded, held = hashlib.sha256(_BODY).hexdigest(), hashlib.sha256(b"drifted").hexdigest()
    assert _REALISTIC_KEY in line
    assert recorded in line and held in line
    assert line.endswith(held)
    assert len(report.outcomes[0].reason or "") > 160  # longer than the cut a stored reason gets


def test_only_a_reason_that_is_stored_elsewhere_is_cut_and_the_two_that_are_not_are_whole() -> None:
    """Contrast for the test above: a `still_quarantined` reason longer than the width is still
    cut (the row holds it in full), while an `inconclusive` one, which is not written anywhere,
    is printed whole. All of them stay one printable ASCII line."""
    from aoe2stats_ingester.capture import RevalidationOutcome, RevalidationReport

    when = datetime(2026, 9, 27, tzinfo=UTC)
    long_reason = "EngineParseError: " + "y" * 400 + "\x1b[1m END"
    outcomes = tuple(
        RevalidationOutcome(uuid.UUID(int=n), n, n + 1, when, kind, long_reason)  # type: ignore[arg-type]
        for n, kind in enumerate(("still_quarantined", "inconclusive", "integrity_failure"), 1)
    )
    report = RevalidationReport(
        outcomes=outcomes, truncated=False, last_completed_at=when, last_capture_id=uuid.UUID(int=3)
    )

    cut, inconclusive, integrity, *_ = format_report(report, dry_run=False)

    assert cut.endswith("...") and "END" not in cut
    assert inconclusive.endswith("END") and integrity.endswith("END")
    assert "\x1b" not in "".join([cut, inconclusive, integrity])
    assert all("\n" not in line for line in (cut, inconclusive, integrity))


def test_a_dry_runs_summary_says_selected_where_no_object_was_read() -> None:
    from aoe2stats_ingester.capture import RevalidationOutcome, RevalidationReport

    when = datetime(2026, 9, 27, tzinfo=UTC)
    report = RevalidationReport(
        outcomes=(RevalidationOutcome(uuid.UUID(int=1), 1, 2, when, "selected"),),
        truncated=False,
        last_completed_at=when,
        last_capture_id=uuid.UUID(int=1),
    )

    dry = format_report(report, dry_run=True)
    real = format_report(report, dry_run=False)

    assert any("1 row(s) selected (selected=1)" in line for line in dry)
    assert not any("examined" in line for line in dry)
    assert any("1 row(s) examined (selected=1)" in line for line in real)


def test_a_run_that_does_not_stop_prints_no_stop_line_and_a_stopped_one_no_continuation() -> None:
    """Contrast for the two stop tests below: the same report without a stop has no `STOPPED`
    line and names no stopped row; with a stop, the `--after` it prints starts past the stopped
    row, and the "more candidates remain" continuation is not printed."""
    from aoe2stats_ingester.capture import (
        RevalidationOutcome,
        RevalidationReport,
        RevalidationStop,
    )

    when = datetime(2026, 9, 27, tzinfo=UTC)
    common: dict[str, Any] = {
        "outcomes": (RevalidationOutcome(uuid.UUID(int=1), 1, 2, when, "stored"),),
        "truncated": True,
        "last_completed_at": when,
        "last_capture_id": uuid.UUID(int=1),
    }
    stop = RevalidationStop(uuid.UUID(int=2), 3, 4, when + timedelta(hours=1))

    running = format_report(RevalidationReport(**common, stopped_row=None), dry_run=False)
    assert not any("STOPPED" in line or "starts past" in line for line in running)
    assert any("more candidates remain" in line for line in running)

    for field in ("aborted_by", "write_failed_by"):
        lines = format_report(
            RevalidationReport(**common, stopped_row=stop, **{field: "SomeError"}), dry_run=False
        )
        [line] = [line for line in lines if "STOPPED" in line]
        assert "game 3, profile 4, recorded 2026-09-27T01:00:00+00:00" in line
        assert f"--after 2026-09-27T01:00:00+00:00,{uuid.UUID(int=2)} starts past" in line
        assert not any("more candidates remain" in line for line in lines)


class _FailsOnOneKey(_GetOnlyStore):
    def __init__(self, objects: dict[str, bytes], *, fail_on: str) -> None:
        super().__init__(objects)
        self._fail_on = fail_on

    async def get(self, key: str) -> bytes:
        if key == self._fail_on:
            self.gets.append(key)
            raise ConnectionError("https://account.example/secret-path is unreachable")
        return await super().get(key)


async def _stopped_line_then_a_run_given_its_after_value(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
    *,
    stopped_game: int,
    behind_game: int,
    stop_out: str,
    same_time_profile: int | None = None,
) -> None:
    """The stop line must name the row it stopped at, and the `--after` value it prints must,
    given to a run, leave that row out and select the one behind it. With `same_time_profile`,
    the match also has a second capture (by that profile) that shares the stopped row's
    `completed_at`, and the run given the value selects that one too."""
    [line] = [line for line in stop_out.splitlines() if "STOPPED" in line]
    completed_at = await db_session.scalar(
        select(Match.completed_at).where(Match.game_id == stopped_game)
    )
    assert completed_at is not None
    assert f"game {stopped_game}, profile {stopped_game + 7}, recorded " in line
    assert completed_at.isoformat() in line
    found = re.search(r"--after (\S+) starts past that row", line)
    assert found is not None
    value = found.group(1)
    assert "secret" not in line

    # Without the value the stopped row is selected again (selection is oldest first).
    assert (
        await asyncio.to_thread(main, ["--dry-run", "--limit", "5"], {"DATABASE_URL": database_url})
        == 0
    )
    unrestricted = capsys.readouterr().out
    assert f"game {stopped_game} profile {stopped_game + 7} " in unrestricted

    assert (
        await asyncio.to_thread(
            main,
            ["--dry-run", "--limit", "5", "--after", value],
            {"DATABASE_URL": database_url},
        )
        == 0
    )
    resumed = capsys.readouterr().out
    assert f"game {stopped_game} profile {stopped_game + 7} " not in resumed
    assert f"game {behind_game} " in resumed
    if same_time_profile is not None:
        assert f"game {stopped_game} profile {same_time_profile} " in resumed
    assert "STOPPED" not in resumed and "starts past" not in resumed


async def test_a_store_stop_names_its_row_and_the_after_value_it_prints_starts_past_it(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The stopped match also has a second capture that shares its recording time. The stopped
    row is the one with the lower capture id (`UUID(int=1)` against `UUID(int=2)`, both fixed),
    and `fail_on` is its key, so the run stops at it and the second capture sorts behind it."""
    store = _FailsOnOneKey({}, fail_on="replays/800301.zip")
    await _seed(db_session, store, 800_300)
    await _seed(db_session, store, 800_301, capture_id=uuid.UUID(int=1))
    await _seed_second_capture(
        db_session, store, 800_301, capture_id=uuid.UUID(int=2), profile_id=900_001
    )
    await _seed(db_session, store, 800_302)
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
    assert "the object store failed with ConnectionError" in out
    assert store.gets == ["replays/800300.zip", "replays/800301.zip"]
    await _stopped_line_then_a_run_given_its_after_value(
        db_session,
        database_url,
        capsys,
        stopped_game=800_301,
        behind_game=800_302,
        stop_out=out,
        same_time_profile=900_001,
    )


async def test_a_database_stop_names_its_row_and_the_after_value_it_prints_starts_past_it(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    from aoe2stats_ingester.capture import CaptureDrain

    store = _GetOnlyStore({})
    await _seed(db_session, store, 800_310)
    await _seed(db_session, store, 800_311)
    await _seed(db_session, store, 800_312)
    real = CaptureDrain._mark_stored
    calls = {"n": 0}

    async def _second_write_fails(self: Any, *args: Any, **kwargs: Any) -> bool:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OperationalError("UPDATE secret_table SET x = 'secret-value'", {}, Exception("x"))
        return await real(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(CaptureDrain, "_mark_stored", _second_write_fails)
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
    assert "a database error stopped the run: OperationalError" in out
    await _stopped_line_then_a_run_given_its_after_value(
        db_session,
        database_url,
        capsys,
        stopped_game=800_311,
        behind_game=800_312,
        stop_out=out,
    )


async def _run_given_the_stop_lines_value(
    stop_out: str,
    database_url: str,
    run: _ConfiguredByTheRun,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    """A real run given the `--after` value the stop line prints; its exit code and output."""
    found = re.search(r"--after (\S+) starts past that row", stop_out)
    assert found is not None
    code = await asyncio.to_thread(
        main,
        ["--limit", "5", "--after", found.group(1)],
        _application_environment(database_url),
        make_object_store=run.make_object_store,
        make_validator=run.make_validator,
    )
    return code, capsys.readouterr().out


async def test_a_store_stop_at_the_last_selected_row_leaves_the_next_run_nothing_to_select(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The runbook says the next run stops again while the failure lasts, "if a row lies past the
    stopped one". When the stopped row is the last one selected none does: the run given the stop
    line's value selects no row, so it reads no object, reports that it examined nothing and
    exits 0, with the store still failing. A run that examined nothing shows nothing about the
    failure."""
    store = _FailsOnOneKey({}, fail_on="replays/800321.zip")
    await _seed(db_session, store, 800_320)
    await _seed(db_session, store, 800_321)
    run = _ConfiguredByTheRun(store)
    first = await asyncio.to_thread(
        main,
        ["--limit", "5"],
        _application_environment(database_url),
        make_object_store=run.make_object_store,
        make_validator=run.make_validator,
    )
    stopped = capsys.readouterr().out
    assert first == 1 and "the object store failed with ConnectionError" in stopped
    assert store.gets == ["replays/800320.zip", "replays/800321.zip"]
    store.gets.clear()

    code, out = await _run_given_the_stop_lines_value(stopped, database_url, run, capsys)

    assert code == 0
    assert "0 row(s) examined (nothing)." in out
    assert "STOPPED" not in out and "more candidates remain" not in out
    assert store.gets == []


async def test_a_database_stop_at_the_last_selected_row_leaves_the_next_run_nothing_to_select(
    db_session: AsyncSession,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same for a database stop: the second write fails, at the last selected row, and the
    run given the stop line's value selects nothing, so it writes nothing and exits 0 while the
    failure is still there."""
    from sqlalchemy.exc import OperationalError

    from aoe2stats_ingester.capture import CaptureDrain

    store = _GetOnlyStore({})
    await _seed(db_session, store, 800_330)
    await _seed(db_session, store, 800_331)
    real = CaptureDrain._mark_stored
    calls = {"n": 0}

    async def _every_write_after_the_first_fails(self: Any, *args: Any, **kwargs: Any) -> bool:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise OperationalError("UPDATE t SET x = 1", {}, Exception("x"))
        return await real(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(CaptureDrain, "_mark_stored", _every_write_after_the_first_fails)
    run = _ConfiguredByTheRun(store)
    first = await asyncio.to_thread(
        main,
        ["--limit", "5"],
        _application_environment(database_url),
        make_object_store=run.make_object_store,
        make_validator=run.make_validator,
    )
    stopped = capsys.readouterr().out
    assert first == 1 and "a database error stopped the run: OperationalError" in stopped
    assert calls["n"] == 2
    store.gets.clear()

    code, out = await _run_given_the_stop_lines_value(stopped, database_url, run, capsys)

    assert code == 0
    assert "0 row(s) examined (nothing)." in out
    assert "STOPPED" not in out and "more candidates remain" not in out
    assert store.gets == [] and calls["n"] == 2
