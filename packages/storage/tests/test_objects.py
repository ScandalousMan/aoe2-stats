"""Unit tests for `aoe2stats_storage.objects`.

`ObjectStore` is exercised against a fake `S3Client` (see the `S3Client` Protocol in the module
under test) rather than a real bucket or a mocking framework: constitution III's network-blocking
fixture (`tests/conftest.py`) applies here like everywhere else, and the fake is enough to prove
both the key scheme and the worker-thread offload without either a live endpoint or a new heavy
dependency.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from aoe2stats_storage import objects
from aoe2stats_storage.objects import (
    DEFAULT_SIGNED_URL_EXPIRES_IN_SECONDS,
    REPLAY_CONTENT_TYPE,
    ObjectStore,
    ObjectStoreConfig,
    replay_object_key,
)


class _FakePaginator:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages

    def paginate(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._pages


class _FakeS3Client:
    """Records every call and its calling thread; answers deterministically."""

    def __init__(self, pages: list[dict[str, Any]] | None = None) -> None:
        self.put_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.presign_calls: list[dict[str, Any]] = []
        self.calling_threads: set[int] = set()
        self._pages = pages if pages is not None else [{"Contents": []}]

    def put_object(self, **kwargs: Any) -> None:
        self.calling_threads.add(threading.get_ident())
        self.put_calls.append(kwargs)

    def delete_object(self, **kwargs: Any) -> None:
        self.calling_threads.add(threading.get_ident())
        self.delete_calls.append(kwargs)

    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> str:
        self.calling_threads.add(threading.get_ident())
        self.presign_calls.append({"client_method": client_method, **kwargs})
        bucket = kwargs["Params"]["Bucket"]
        key = kwargs["Params"]["Key"]
        expires_in = kwargs["ExpiresIn"]
        return f"https://example-bucket.invalid/{bucket}/{key}?expires={expires_in}"

    def get_paginator(self, operation_name: str) -> _FakePaginator:
        assert operation_name == "list_objects_v2"
        self.calling_threads.add(threading.get_ident())
        return _FakePaginator(self._pages)


@pytest.fixture
def config() -> ObjectStoreConfig:
    return ObjectStoreConfig(
        endpoint_url="https://example.eu.r2.cloudflarestorage.com",
        bucket="aoe2-stats-replays",
        access_key_id="AKIAEXAMPLE",
        secret_access_key="shh",
        region="auto",
    )


# --- the key scheme ------------------------------------------------------------------------------


def test_replay_object_key_is_scoped_by_game_and_profile() -> None:
    assert replay_object_key(game_id=123, profile_id=456) == "replays/123/456.zip"


def test_replay_object_key_gives_a_distinct_key_per_profile_on_a_shared_match() -> None:
    # FR-016: two consenting users in one game share a `matches` row but never a blob.
    key_a = replay_object_key(game_id=999, profile_id=1)
    key_b = replay_object_key(game_id=999, profile_id=2)
    assert key_a != key_b
    assert key_a == "replays/999/1.zip"
    assert key_b == "replays/999/2.zip"


def test_replay_object_key_is_deterministic() -> None:
    # Idempotent by construction: retrying a capture after a crash must resolve to the same key.
    assert replay_object_key(1, 2) == replay_object_key(1, 2)


# --- put -------------------------------------------------------------------------------------


async def test_put_uploads_the_body_under_the_key_with_the_replay_content_type(
    config: ObjectStoreConfig,
) -> None:
    client = _FakeS3Client()
    store = ObjectStore(config, client=client)

    await store.put("replays/1/2.zip", b"zip-bytes")

    assert client.put_calls == [
        {
            "Bucket": "aoe2-stats-replays",
            "Key": "replays/1/2.zip",
            "Body": b"zip-bytes",
            "ContentType": REPLAY_CONTENT_TYPE,
        }
    ]


async def test_put_accepts_an_explicit_content_type(config: ObjectStoreConfig) -> None:
    client = _FakeS3Client()
    store = ObjectStore(config, client=client)

    await store.put("some/key", b"data", content_type="text/plain")

    assert client.put_calls[0]["ContentType"] == "text/plain"


# --- signed_get_url ----------------------------------------------------------------------------


async def test_signed_get_url_signs_a_get_for_the_bucket_and_key(
    config: ObjectStoreConfig,
) -> None:
    client = _FakeS3Client()
    store = ObjectStore(config, client=client)

    url = await store.signed_get_url("replays/1/2.zip")

    assert client.presign_calls == [
        {
            "client_method": "get_object",
            "Params": {"Bucket": "aoe2-stats-replays", "Key": "replays/1/2.zip"},
            "ExpiresIn": DEFAULT_SIGNED_URL_EXPIRES_IN_SECONDS,
        }
    ]
    assert url == (
        "https://example-bucket.invalid/aoe2-stats-replays/replays/1/2.zip"
        f"?expires={DEFAULT_SIGNED_URL_EXPIRES_IN_SECONDS}"
    )


async def test_signed_get_url_expiry_is_overridable_and_short_lived_by_default(
    config: ObjectStoreConfig,
) -> None:
    client = _FakeS3Client()
    store = ObjectStore(config, client=client)

    await store.signed_get_url("k", expires_in=60)

    assert client.presign_calls[0]["ExpiresIn"] == 60
    # contracts/http-api.md: the bucket is never public, every read is short-lived.
    assert DEFAULT_SIGNED_URL_EXPIRES_IN_SECONDS <= 900


# --- delete ------------------------------------------------------------------------------------


async def test_delete_removes_the_object_by_key(config: ObjectStoreConfig) -> None:
    client = _FakeS3Client()
    store = ObjectStore(config, client=client)

    await store.delete("replays/1/2.zip")

    assert client.delete_calls == [{"Bucket": "aoe2-stats-replays", "Key": "replays/1/2.zip"}]


# --- list_keys -----------------------------------------------------------------------------------


async def test_list_keys_flattens_a_single_page(config: ObjectStoreConfig) -> None:
    client = _FakeS3Client(
        pages=[{"Contents": [{"Key": "replays/1/2.zip"}, {"Key": "replays/1/3.zip"}]}]
    )
    store = ObjectStore(config, client=client)

    keys = await store.list_keys(prefix="replays/1/")

    assert keys == ["replays/1/2.zip", "replays/1/3.zip"]


async def test_list_keys_flattens_multiple_pages(config: ObjectStoreConfig) -> None:
    client = _FakeS3Client(
        pages=[
            {"Contents": [{"Key": "replays/1/2.zip"}]},
            {"Contents": [{"Key": "replays/1/3.zip"}]},
        ]
    )
    store = ObjectStore(config, client=client)

    keys = await store.list_keys()

    assert keys == ["replays/1/2.zip", "replays/1/3.zip"]


async def test_list_keys_handles_an_empty_bucket_without_a_contents_key(
    config: ObjectStoreConfig,
) -> None:
    # `list_objects_v2` omits `Contents` entirely when a page (or the whole listing) is empty.
    client = _FakeS3Client(pages=[{}])
    store = ObjectStore(config, client=client)

    keys = await store.list_keys()

    assert keys == []


# --- never blocks the event loop ----------------------------------------------------------------


async def test_every_call_runs_off_the_event_loop_thread(config: ObjectStoreConfig) -> None:
    client = _FakeS3Client(pages=[{"Contents": []}])
    store = ObjectStore(config, client=client)
    event_loop_thread = threading.get_ident()

    await store.put("k", b"body")
    await store.signed_get_url("k")
    await store.delete("k")
    await store.list_keys()

    assert event_loop_thread not in client.calling_threads


# --- building the real client ---------------------------------------------------------------------


def test_object_store_builds_a_boto3_client_from_config_when_none_is_injected(
    config: ObjectStoreConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_boto3_client(service_name: str, **kwargs: Any) -> _FakeS3Client:
        captured["service_name"] = service_name
        captured.update(kwargs)
        return _FakeS3Client()

    monkeypatch.setattr(objects.boto3, "client", fake_boto3_client)

    store = ObjectStore(config)

    assert store._client is not None
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == config.endpoint_url
    assert captured["aws_access_key_id"] == config.access_key_id
    assert captured["aws_secret_access_key"] == config.secret_access_key
    assert captured["region_name"] == config.region
    # SigV4 everywhere so phase 2 (OVH Object Storage) needs no change here.
    assert captured["config"].signature_version == "s3v4"
