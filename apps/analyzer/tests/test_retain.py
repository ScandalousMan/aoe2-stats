"""T362 — retention tests for `apps/analyzer/src/aoe2stats_analyzer/retain.py`, implemented at
**T363**, which also adds the retained-recording key function to `packages/storage/src/
aoe2stats_storage/objects.py`. Neither exists yet, so every test below carries
`@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")` per `CLAUDE.md`'s test-first
convention, and imports `aoe2stats_analyzer.retain` **inside its own body**, never at module scope
— a module-scope import of a module that does not exist is a collection error that takes the whole
`apps/analyzer/tests` suite down, a different and worse failure than an expected `xfail`.

**T363 is blocked this session, deliberately.** 001's T090/T091/T092 (export, erasure, third-party
objection) have not landed, and constitution IX requires those routes before a third party's
recording may actually be retained in production. This file writes the contract T363 must satisfy
without implementing it, and without implementing 001's erasure either — the erasure- and
objection-shaped tests below simulate *only the database-level outcome* those routes will one day
produce (a `users` row deleted, a `match_players.profile_id` pseudonymised in place), because that
outcome is what `retained_recordings` — a table T304/T305 already shipped — must survive regardless
of which route produces it. They do not exercise 001's own routing, authorisation or request shape;
that is 001's own test suite's job once T090-T092 land.

**The interface under test is designed here, not merely exercised**, the same way
`test_rate_limits.py` designed `check_and_increment` ahead of T307:

- `retain_recording(session, object_store, *, game_id, profile_id, zip_bytes,
  requested_by_user_id=None) -> RetainedRecording` — idempotent per `(game_id, profile_id)`
  (mirrors `replay_object_key`'s own idempotence, `objects.py`): the first call computes the
  sha256, uploads under `retained_recording_object_key(game_id, profile_id)` and inserts the row;
  every later call for the same pair — a recompute, a parser version change, or simply a second
  analysis request — returns the existing row unchanged and performs no second upload and no
  delete. This idempotence is *how* T362's "never deleted by a recompute or a parser change"
  becomes a property of the write path itself rather than a promise nobody enforces.
- `retrieve_recording(session, object_store, *, game_id, profile_id) -> bytes` — downloads the
  object under the row's own `object_key`, recomputes its sha256 and compares it against
  `RetainedRecording.zip_sha256`, raising `RecordingIntegrityError` on mismatch rather than handing
  back bytes nothing has checked.
- `RecordingIntegrityError` — the exception `retrieve_recording` raises on a checksum mismatch.

`packages/storage/src/aoe2stats_storage/objects.py` gains `retained_recording_object_key(game_id,
profile_id) -> str`, called the same way every existing test calls `replay_object_key` — never a
literal string this file invents, so the exact prefix stays T363's choice and this file only
asserts the *properties* R9 and FR-048 require of it: distinct from `replay_object_key`'s value for
the same pair, and resolving to a genuinely different object rather than colliding with it.

**The own-match contrast case is deliberately not a repeat of the third-party ones.**
`data-model.md`'s `retained_recordings` section states why: the two objects are the same bytes held
under two different legal bases with two different lifetimes, so a match this service already holds
as a `replay_captures` row must still gain its own, second `retained_recordings` row and object when
someone asks for it to be analysed — reading the existing capture and retaining nothing would leave
the published analysis unrecomputable the first time that capture's owner erases. Erasure of that
owner (simulated below by deleting their `users` row and, as production erasure would, their
`replay_captures` row and its object) must delete the capture and leave the retained copy and the
published analysis exactly as they were.

`ProfileLink`/`SteamIdentity` are deliberately not seeded anywhere in this file: the ownership walk
that decides *which* captures an erasure route must delete (`profile_links` → `profile_id` →
`replay_captures`) is 001's own erasure logic (T091), not `retain.py`'s concern and not under test
here. Every scenario below seeds only what `retain_recording`/`retrieve_recording` and the
`retained_recordings` row's own foreign keys require, and simulates an erasure's *outcome* directly
against the rows it would touch.

**Fixtures.** `db_session` comes from the new `apps/analyzer/tests/conftest.py`, added alongside
this file — see that module's own docstring for why: pytest resolves a fixture only through a
conftest ancestor or the requesting module's own namespace, and every one of Phase 7's `[P]` test
files needs it, not only this one. `ObjectStore` is exercised against `_FakeS3Client`, the same
structural `S3Client` Protocol fake
`test_quarantine.py` and `test_capture_run_id.py` use, extended here with an optional
`forbidden_delete_keys` set that raises the instant a forbidden key is passed to `delete_object` —
proving a deletion never happens as a property of the call itself, not merely absent from a later
assertion, the same discipline `test_favourite_no_capture.py`'s forbidding provider fakes use.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ReplayCapture,
    RetainedRecording,
    User,
)
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig, replay_object_key

_GAME_ID = 970_000_001
_OTHER_GAME_ID = 970_000_002
_OWN_MATCH_GAME_ID = 970_000_003
_PROFILE_ID = 970_100_001
_OTHER_PROFILE_ID = 970_100_002
_OWNER_PROFILE_ID = 970_100_003
_PSEUDONYM_PROFILE_ID = -1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Body:
    """Wraps a `bytes` payload with the `.read()` interface `ObjectStore._get_sync` expects from
    `get_object(...)["Body"]` — a real `boto3` `StreamingBody` exposes the same surface."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    """Satisfies `aoe2stats_storage.objects.S3Client` structurally, exactly as `test_quarantine.py`
    and `test_capture_run_id.py`'s own fakes do. `forbidden_delete_keys` raises `AssertionError`
    the instant `delete_object` is called for one of those keys — proving the call never happens,
    rather than merely checking `delete_calls` afterward — for the tests whose entire point is that
    a retained recording's object is never removed for any reason T362 lists.
    """

    def __init__(self, *, forbidden_delete_keys: frozenset[str] = frozenset()) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.forbidden_delete_keys = forbidden_delete_keys

    def put_object(self, **kwargs: Any) -> Any:
        self.objects[kwargs["Key"]] = kwargs["Body"]
        self.put_calls.append(kwargs["Key"])
        return {}

    def get_object(self, **kwargs: Any) -> Any:
        return {"Body": _Body(self.objects[kwargs["Key"]])}

    def delete_object(self, **kwargs: Any) -> Any:
        key = kwargs["Key"]
        assert key not in self.forbidden_delete_keys, (
            f"delete_object was called for {key!r}, a retained recording's own object key. A "
            "retained recording is never deleted, for any reason (constitution IX 3.0.0/4.0.0, "
            "FR-046, data-model.md's retained_recordings section)."
        )
        self.delete_calls.append(key)
        self.objects.pop(key, None)
        return {}

    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> Any:
        raise NotImplementedError("not exercised by this file")

    def get_paginator(self, operation_name: str) -> Any:
        raise NotImplementedError("not exercised by this file")


def _object_store(client: _FakeS3Client) -> ObjectStore:
    return ObjectStore(
        ObjectStoreConfig(
            endpoint_url="https://fake-object-store.example",
            bucket="aoe2-analysis-test",
            access_key_id="test",
            secret_access_key="test",
            region="eu",
        ),
        client=client,
    )


async def _seed_match(db_session: AsyncSession, *, game_id: int) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=datetime.now(UTC),
            source="test",
            raw_payload={},
        )
    )
    await db_session.commit()


async def _seed_profile(db_session: AsyncSession, *, profile_id: int, alias: str) -> None:
    db_session.add(
        AoeProfile(
            profile_id=profile_id,
            alias=alias,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
    )
    await db_session.commit()


async def _seed_match_player(db_session: AsyncSession, *, game_id: int, profile_id: int) -> None:
    db_session.add(MatchPlayer(game_id=game_id, profile_id=profile_id))
    await db_session.commit()


async def _seed_user(db_session: AsyncSession) -> User:
    user = User(allowlisted_at=datetime.now(UTC))
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_replay_capture(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    object_key: str,
    zip_bytes: bytes,
) -> ReplayCapture:
    """001's own archive of the linked user's point of view — already `stored` before this
    feature's analysis is ever requested, exactly the shape the own-match contrast case needs."""
    capture = ReplayCapture(
        game_id=game_id,
        profile_id=profile_id,
        status=CaptureStatus.STORED,
        capture_deadline_at=datetime.now(UTC),
        stored_at=datetime.now(UTC),
        object_key=object_key,
        zip_bytes=len(zip_bytes),
        zip_sha256=_sha256(zip_bytes),
        source=CaptureSource.AUTOMATIC,
    )
    db_session.add(capture)
    await db_session.commit()
    return capture


async def _seed_published_analysis(
    db_session: AsyncSession,
    *,
    game_id: int,
    point_of_view_profile_id: int,
    requested_by_user_id: uuid.UUID | None,
) -> MatchAnalysis:
    analysis = MatchAnalysis(
        game_id=game_id,
        state=MatchAnalysisState.PUBLISHED,
        point_of_view_profile_id=point_of_view_profile_id,
        parser_name="aoe2rec-py",
        parser_version="1.0.0",
        requested_by_user_id=requested_by_user_id,
        finished_at=datetime.now(UTC),
        result_key=f"analyses/{game_id}.json",
    )
    db_session.add(analysis)
    await db_session.commit()
    return analysis


# --- Byte-for-byte storage and checksum verification (FR-033) ------------------------------------


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_the_recording_is_stored_byte_for_byte_with_a_sha256_verified_on_retrieval(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import retain_recording, retrieve_recording

    await _seed_match(db_session, game_id=_GAME_ID)
    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)
    zip_bytes = b"a fake .aoe2record zip, byte for byte"

    retained = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=None,
    )

    assert retained.zip_bytes == len(zip_bytes)
    assert retained.zip_sha256 == _sha256(zip_bytes)
    assert fake_client.objects[retained.object_key] == zip_bytes

    fetched = await retrieve_recording(
        db_session, object_store, game_id=_GAME_ID, profile_id=_PROFILE_ID
    )
    assert fetched == zip_bytes


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_a_corrupted_object_fails_the_sha256_check_on_retrieval(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import (
        RecordingIntegrityError,
        retain_recording,
        retrieve_recording,
    )

    await _seed_match(db_session, game_id=_GAME_ID)
    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)
    zip_bytes = b"the original bytes, checksummed at retention"

    retained = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=None,
    )
    # Simulates bit rot or an out-of-band tamper: the object no longer matches the sha256 recorded
    # at retention, without touching the row.
    fake_client.objects[retained.object_key] = b"not the same bytes at all"

    with pytest.raises(RecordingIntegrityError):
        await retrieve_recording(db_session, object_store, game_id=_GAME_ID, profile_id=_PROFILE_ID)


# --- Distinct key prefix, never resolving to replay_object_key's value (FR-048, R9) --------------


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_the_object_key_uses_its_own_prefix_and_never_resolves_to_replay_object_keys_value(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import retain_recording

    await _seed_match(db_session, game_id=_GAME_ID)
    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)

    # An archived capture already sits under `replay_object_key` for this *same* (game_id,
    # profile_id) pair — the exact collision R9 forbids, made concrete rather than hypothetical.
    capture_key = replay_object_key(_GAME_ID, _PROFILE_ID)
    capture_bytes = b"001's own archived capture of this exact point of view"
    fake_client.objects[capture_key] = capture_bytes

    retained_bytes = b"the recording retained for analysis of the same match and point of view"
    retained = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=retained_bytes,
        requested_by_user_id=None,
    )

    assert retained.object_key != capture_key
    assert not retained.object_key.startswith("replays/")

    # Resolution, not merely the string: each key still reaches only its own bytes.
    assert fake_client.objects[capture_key] == capture_bytes
    assert fake_client.objects[retained.object_key] == retained_bytes


# --- Never deleted: a recompute, a parser change, or the cap being reached -----------------------


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_a_recompute_never_deletes_or_re_uploads_the_retained_object(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import retain_recording

    await _seed_match(db_session, game_id=_GAME_ID)
    zip_bytes = b"retained once, read again on every recompute"

    first_client = _FakeS3Client()
    first_store = _object_store(first_client)
    first = await retain_recording(
        db_session,
        first_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=None,
    )
    first_client.forbidden_delete_keys = frozenset({first.object_key})

    # A recompute re-derives the analysis from the already-retained bytes; it calls the retention
    # path again for the same pair rather than skipping it, and must find the row idempotent.
    second = await retain_recording(
        db_session,
        first_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=None,
    )

    assert second.id == first.id
    assert second.object_key == first.object_key
    assert second.zip_sha256 == first.zip_sha256
    assert first_client.put_calls == [first.object_key]
    assert first_client.delete_calls == []


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_a_parser_version_change_never_deletes_or_modifies_the_retained_object(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import retain_recording

    await _seed_match(db_session, game_id=_GAME_ID)
    zip_bytes = b"retained under parser 1.0.0, re-read after an engine upgrade"

    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)
    retained = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=None,
    )
    fake_client.forbidden_delete_keys = frozenset({retained.object_key})
    analysis = await _seed_published_analysis(
        db_session,
        game_id=_GAME_ID,
        point_of_view_profile_id=_PROFILE_ID,
        requested_by_user_id=None,
    )

    # The parser engine changed; `run_once` (T365) recomputes by calling the retention path again
    # over the same bytes before re-extracting, never by discarding and re-fetching them.
    analysis.parser_version = "2.0.0"
    await db_session.commit()

    recomputed = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=None,
    )

    assert recomputed.id == retained.id
    assert recomputed.object_key == retained.object_key
    assert recomputed.zip_sha256 == retained.zip_sha256
    assert fake_client.objects[retained.object_key] == zip_bytes
    assert fake_client.delete_calls == []


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_the_retention_cap_being_reached_never_deletes_an_existing_retained_recording(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import retain_recording

    await _seed_match(db_session, game_id=_GAME_ID)
    await _seed_match(db_session, game_id=_OTHER_GAME_ID)
    first_bytes = b"retained before the cap was reached"
    second_bytes = b"a second, unrelated analysis retained after the cap is reached"

    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)
    first = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=first_bytes,
        requested_by_user_id=None,
    )
    fake_client.forbidden_delete_keys = frozenset({first.object_key})

    # `admission.py` (T359) is what refuses a *new* analysis once `ANALYSIS_RETENTION_CAP_BYTES`
    # is reached (FR-047); this call stands in for the one request that pushes the running total
    # past the cap and is nonetheless retained (or would have been refused before ever reaching
    # `retain_recording` — either way, `retain.py` itself carries no eviction logic to make room).
    await retain_recording(
        db_session,
        object_store,
        game_id=_OTHER_GAME_ID,
        profile_id=_OTHER_PROFILE_ID,
        zip_bytes=second_bytes,
        requested_by_user_id=None,
    )

    refreshed_first = await db_session.get(RetainedRecording, first.id)
    assert refreshed_first is not None
    assert refreshed_first.object_key == first.object_key
    assert refreshed_first.zip_sha256 == first.zip_sha256
    assert fake_client.objects[first.object_key] == first_bytes
    assert fake_client.delete_calls == []


# --- Never deleted: an erasure, or a third-party objection (constitution IX 3.0.0) ----------------


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_erasure_of_the_requesting_user_clears_the_link_but_leaves_object_and_row_untouched(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import retain_recording, retrieve_recording

    await _seed_match(db_session, game_id=_GAME_ID)
    requester = await _seed_user(db_session)
    zip_bytes = b"an already-public recording, retained because the requester asked for it"

    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)
    retained = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=requester.id,
    )
    fake_client.forbidden_delete_keys = frozenset({retained.object_key})
    analysis = await _seed_published_analysis(
        db_session,
        game_id=_GAME_ID,
        point_of_view_profile_id=_PROFILE_ID,
        requested_by_user_id=requester.id,
    )

    # The erasure route itself (001 T091) is not built yet; deleting the `users` row is the one
    # database fact that route will produce, and `retained_recordings.requested_by_user_id` /
    # `match_analyses.requested_by_user_id` are both `ondelete="SET NULL"` against it
    # (data-model.md: "the bytes are an already-public recording ... not the requester's data").
    await db_session.delete(requester)
    await db_session.commit()

    await db_session.refresh(retained)
    await db_session.refresh(analysis)

    assert retained.requested_by_user_id is None
    assert retained.object_key is not None
    assert retained.zip_sha256 == _sha256(zip_bytes)
    assert analysis.requested_by_user_id is None
    assert analysis.state == MatchAnalysisState.PUBLISHED

    fetched = await retrieve_recording(
        db_session, object_store, game_id=_GAME_ID, profile_id=_PROFILE_ID
    )
    assert fetched == zip_bytes
    assert fake_client.delete_calls == []


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_a_third_party_objection_pseudonymises_the_profile_but_leaves_recording_untouched(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.retain import retain_recording, retrieve_recording

    await _seed_match(db_session, game_id=_GAME_ID)
    await _seed_profile(db_session, profile_id=_PROFILE_ID, alias="third-party-player")
    await _seed_match_player(db_session, game_id=_GAME_ID, profile_id=_PROFILE_ID)
    zip_bytes = b"a third party's already-public recording, retained for a published analysis"

    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)
    retained = await retain_recording(
        db_session,
        object_store,
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        zip_bytes=zip_bytes,
        requested_by_user_id=None,
    )
    fake_client.forbidden_delete_keys = frozenset({retained.object_key})
    analysis = await _seed_published_analysis(
        db_session,
        game_id=_GAME_ID,
        point_of_view_profile_id=_PROFILE_ID,
        requested_by_user_id=None,
    )

    # Constitution IX 3.0.0: an objection or an erasure by a person *appearing in* the recording
    # pseudonymises every identifier this service holds about them "the same instrument 001's
    # erasure applies to matches and match_players" — never the recording. Simulated directly
    # against `match_players`, the exact table the amendment names, since 001's own route
    # (T090-T092) is not built yet.
    match_player = await db_session.get(MatchPlayer, (_GAME_ID, _PROFILE_ID))
    assert match_player is not None
    match_player.profile_id = _PSEUDONYM_PROFILE_ID
    await db_session.flush()
    await db_session.commit()

    refreshed = await db_session.get(RetainedRecording, retained.id)
    assert refreshed is not None
    # `retained_recordings.profile_id` carries no foreign key to `aoe_profiles` or `match_players`
    # (data-model.md, R9) precisely so a pseudonymisation elsewhere cannot reach it: the row still
    # names the original profile_id, the object key, and the checksum, unchanged.
    assert refreshed.profile_id == _PROFILE_ID
    assert refreshed.object_key == retained.object_key
    assert refreshed.zip_sha256 == retained.zip_sha256

    fetched = await retrieve_recording(
        db_session, object_store, game_id=_GAME_ID, profile_id=_PROFILE_ID
    )
    assert fetched == zip_bytes

    await db_session.refresh(analysis)
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.result_key == f"analyses/{_GAME_ID}.json"
    assert fake_client.delete_calls == []


# --- The own-match contrast case (data-model.md's retained_recordings section) -------------------


@pytest.mark.xfail(strict=True, reason="T363 not implemented yet")
async def test_an_own_match_still_gets_a_second_row_and_object_under_the_retention_prefix(
    db_session: AsyncSession,
) -> None:
    """The case `data-model.md` says "an implementer will otherwise skip, because skipping it
    looks like an optimisation": a match this service already holds as a `replay_captures` row
    (the user's own, 001) still gains its own, separate `retained_recordings` row and object when
    that same user asks for it to be analysed — the two are the same bytes under two different
    legal bases and two different lifetimes, not one file with two labels."""
    from aoe2stats_analyzer.retain import retain_recording, retrieve_recording

    await _seed_match(db_session, game_id=_OWN_MATCH_GAME_ID)
    owner = await _seed_user(db_session)
    match_bytes = b"the one recording of this match and point of view, held under two bases"

    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)

    capture_key = replay_object_key(_OWN_MATCH_GAME_ID, _OWNER_PROFILE_ID)
    capture = await _seed_replay_capture(
        db_session,
        game_id=_OWN_MATCH_GAME_ID,
        profile_id=_OWNER_PROFILE_ID,
        object_key=capture_key,
        zip_bytes=match_bytes,
    )
    fake_client.objects[capture_key] = match_bytes

    retained = await retain_recording(
        db_session,
        object_store,
        game_id=_OWN_MATCH_GAME_ID,
        profile_id=_OWNER_PROFILE_ID,
        zip_bytes=match_bytes,
        requested_by_user_id=owner.id,
    )
    analysis = await _seed_published_analysis(
        db_session,
        game_id=_OWN_MATCH_GAME_ID,
        point_of_view_profile_id=_OWNER_PROFILE_ID,
        requested_by_user_id=owner.id,
    )

    # Two rows, two objects, both holding the same bytes under two different keys.
    assert retained.object_key != capture_key
    assert retained.id != capture.id
    assert fake_client.objects[capture_key] == match_bytes
    assert fake_client.objects[retained.object_key] == match_bytes

    fake_client.forbidden_delete_keys = frozenset({retained.object_key})

    # Erasure of the owner (001, not yet built): deletes their capture — the row and its object —
    # and the `users` row itself, but must never reach the retained copy or the published
    # analysis. `replay_captures` carries no foreign key to `users` (ownership runs through
    # `profile_links`, out of scope here — see the module docstring), so the capture's own
    # deletion is simulated directly, exactly as 001's erasure route will perform it.
    await object_store.delete(capture_key)
    await db_session.delete(capture)
    await db_session.delete(owner)
    await db_session.commit()

    deleted_capture = await db_session.get(ReplayCapture, capture.id)
    assert deleted_capture is None
    assert capture_key not in fake_client.objects

    await db_session.refresh(retained)
    await db_session.refresh(analysis)
    assert retained.requested_by_user_id is None
    assert retained.object_key is not None
    assert retained.zip_sha256 == _sha256(match_bytes)
    assert analysis.requested_by_user_id is None
    assert analysis.state == MatchAnalysisState.PUBLISHED

    fetched = await retrieve_recording(
        db_session, object_store, game_id=_OWN_MATCH_GAME_ID, profile_id=_OWNER_PROFILE_ID
    )
    assert fetched == match_bytes
