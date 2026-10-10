"""Tests for `scripts/ops/revalidate_quarantined.py` (T673).

The selection, the read-back and the writes are tested where they live
(`apps/ingester/tests/test_revalidate_quarantined.py`); this file pins what the operator command
adds: a provider that refuses every call, the environment it needs and refuses without, the
`--after` contract, and a report that cannot put an engine's terminal escape codes on a terminal.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

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
    _NoReplayProvider,
    build_arg_parser,
    format_report,
    main,
    object_store_from_environment,
    revalidate,
)

_BODY = b"recording"
_S3 = {
    "S3_ENDPOINT_URL": "https://account.eu.r2.cloudflarestorage.com",
    "S3_BUCKET": "bucket",
    "S3_ACCESS_KEY_ID": "key-id",
    "S3_SECRET_ACCESS_KEY": "very-secret-value",
    "S3_REGION": "auto",
}


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


async def test_a_dry_run_needs_no_object_store_and_no_engine(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(db_session, _GetOnlyStore({}), 800_002)

    report = await revalidate(
        session_factory, object_store=None, validator=None, limit=5, dry_run=True
    )

    assert [o.outcome for o in report.outcomes] == ["selected"]


def test_the_object_store_is_built_from_the_applications_own_variable_names() -> None:
    assert object_store_from_environment(_S3) is not None


@pytest.mark.parametrize("missing", sorted(_S3))
def test_a_missing_object_store_variable_is_named_and_its_value_is_not(missing: str) -> None:
    environ = {k: v for k, v in _S3.items() if k != missing}
    with pytest.raises(ValueError) as caught:
        object_store_from_environment(environ)
    assert missing in str(caught.value)
    assert "very-secret-value" not in str(caught.value)


def test_a_run_without_a_database_url_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], environ={}) == 1
    assert "DATABASE_URL is not set" in capsys.readouterr().err


def test_a_real_run_without_the_object_store_is_refused_but_a_dry_run_gets_past_that(
    capsys: pytest.CaptureFixture[str],
) -> None:
    environ = {"DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:1/none"}
    assert main([], environ=environ) == 1
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
        environ={"DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:1/none", **_S3},
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
