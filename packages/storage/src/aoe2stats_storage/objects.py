"""S3-compatible object store for replay blobs.

Constitution XII: "object storage is reached only through the S3 API behind
`packages/storage`." This is that boundary. It is deliberately not in `packages/providers`:
the DataProvider boundary (constitution III) is for *external data sources* — things with a
schema we do not control and a window that closes. Cloudflare R2 (phase 1) and OVH Object
Storage (phase 2) are infrastructure we configure, reached through one portable API (the S3
API itself), which is the whole point of `.env.example`'s four `S3_*` variables being the
only thing that differs between the two phases.

`boto3` is synchronous. Every public method here offloads its one blocking call to a worker
thread with `asyncio.to_thread`, per research.md §5, so a capture or a download never blocks
the event loop the rest of the application shares.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
from botocore.client import Config as BotoConfig

#: What every archived replay is: a single-member zip (data-model.md, quickstart scenario 3).
REPLAY_CONTENT_TYPE = "application/zip"

#: Short-lived by construction (contracts/http-api.md: "a freshly signed URL with a short
#: expiry"). Five minutes is enough for a redirect and a download to start, and short enough
#: that a leaked URL — logged, forwarded, cached by a proxy — exposes little.
DEFAULT_SIGNED_URL_EXPIRES_IN_SECONDS = 300


def replay_object_key(game_id: int, profile_id: int) -> str:
    """The key scheme for an archived replay: one object per `(game_id, profile_id)`.

    This mirrors `replay_captures`' own dedup constraint (`UNIQUE (game_id, profile_id)`,
    data-model.md) exactly, on purpose:

    - it needs no round trip to the database — a caller that already has both ids can
      address the blob without a lookup;
    - it is idempotent — retrying a capture after a crash resolves to the same key rather
      than accumulating an orphan per attempt;
    - it keeps two users' points of view on one shared match apart. A match two consenting
      players both took part in produces one `matches` row but two `replay_captures` rows
      (FR-016), and this scheme gives each its own object: neither user's signed URL can
      ever resolve to the other's blob, because the key it is signed for is not the key the
      other row holds.

    The scheme is shared by capture (`source = 'automatic'`) and manual upload
    (`source = 'manual'`, T081): both address the same `(game_id, profile_id)` pair, so both
    resolve to the same key, which is what lets an upload detect "an archive already exists"
    (FR-032) by checking one key rather than reasoning about source.
    """
    return f"replays/{game_id}/{profile_id}.zip"


@dataclass(frozen=True, slots=True)
class ObjectStoreConfig:
    """The four variables `.env.example` says are the only ones that differ by provider."""

    endpoint_url: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    region: str


class S3Client(Protocol):
    """The slice of the `boto3` S3 client surface this module actually calls.

    Named so a test can hand `ObjectStore` a fake that implements only this much, instead of
    a real `boto3` client — which would mean either a live bucket or reaching for a heavier
    mocking dependency the workspace does not otherwise need. `boto3.client("s3", ...)`
    satisfies this Protocol structurally; it never has to import it.
    """

    def put_object(self, **kwargs: Any) -> Any: ...
    def get_object(self, **kwargs: Any) -> Any: ...
    def delete_object(self, **kwargs: Any) -> Any: ...
    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> Any: ...
    def get_paginator(self, operation_name: str) -> Any: ...


def _build_client(config: ObjectStoreConfig) -> S3Client:
    client: S3Client = boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region,
        # SigV4 everywhere: it is what R2 requires and what OVH Object Storage also accepts,
        # so phase 2 needs no change here (constitution XII).
        config=BotoConfig(signature_version="s3v4"),
    )
    return client


class ObjectStore:
    """Put, get, sign, delete and list replay blobs, without blocking the event loop.

    The bucket is never public (contracts/http-api.md): every read a browser or an external
    client is ever handed goes through a freshly signed, short-expiry URL, never a stored or
    reused one. `get` is the one exception, and it is not exposed to any of them — it is a direct,
    in-process read for the application's own use (see its docstring).
    """

    def __init__(self, config: ObjectStoreConfig, *, client: S3Client | None = None) -> None:
        self._bucket = config.bucket
        self._client = client if client is not None else _build_client(config)

    async def put(self, key: str, body: bytes, *, content_type: str = REPLAY_CONTENT_TYPE) -> None:
        """Upload `body` under `key`, overwriting whatever was there before.

        Capture writes the blob before it validates or marks the row (data-model.md's write
        ordering, FR-023); this call has no opinion on that order; it only performs the one
        write the caller asked for, in a worker thread.
        """
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    async def get(self, key: str) -> bytes:
        """Download the full body stored under `key`.

        The counterpart to `put`: capture's reclaim path (`apps/ingester/src/
        aoe2stats_ingester/capture.py`) is what this exists for — a stale `downloading` row that
        already carries a committed `object_key`/`zip_sha256` needs its bytes back in-process to
        verify them and run them through validation a second time, rather than trusting the
        checksum an earlier, now-dead run recorded without ever re-checking it. Every other caller
        of this class reaches for `signed_get_url` instead, which is the only path a browser or an
        external client is ever handed (the bucket is never public); this method is for the one
        caller that is the application itself.
        """
        return await asyncio.to_thread(self._get_sync, key)

    def _get_sync(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body: bytes = response["Body"].read()
        return body

    async def signed_get_url(
        self,
        key: str,
        *,
        expires_in: int = DEFAULT_SIGNED_URL_EXPIRES_IN_SECONDS,
        filename: str | None = None,
    ) -> str:
        """A short-lived, presigned `GET` URL for `key`.

        Signing is local computation (an HMAC over the request, no I/O) rather than a network
        call, but it still runs through the worker thread: the caller gets one uniform,
        never-blocks contract across every method on this class, and the cost of a thread
        hop here is negligible next to a request that is about to redirect a browser anyway.

        `filename`, when given, becomes this URL's own `response-content-disposition`, passed to
        `boto3` as `ResponseContentDisposition` — a `GetObject` request parameter both AWS S3 and
        Cloudflare R2 honour (R2's S3-compatible `GetObject` implementation serves the standard
        `response-*` override parameters; `docs/adr/0002-hosting.md`'s "Object storage is reached
        only through the S3 API" is exactly the guarantee that makes this portable to phase 2's OVH
        Object Storage too). It exists because a browser derives the filename it saves a download
        under from the signed URL's own last path segment, never from the object key inside it — a
        caller that redirects a browser to a signed URL (every `archived` branch in
        `apps/api/src/aoe2stats_api/routers/replays.py`) needs this to control that name, since
        `replay_object_key`'s `{game_id}/{profile_id}.zip` shape puts `game_id` in a path segment
        the browser never reads. It rides on the signed URL itself — covered by the SigV4 signature
        the same as `Bucket`/`Key`, so it cannot be tampered with by whoever holds the URL — rather
        than as a response header this class sets after the fact, because there is no "after the
        fact" here: this method never touches the object, it only computes a URL a caller redirects
        a browser to directly.

        Optional, not required: `apps/ingester/tests/test_quarantine.py` calls this for a quarantine
        review tool, never a browser redirect, and genuinely wants no disposition override — that
        caller keeps working unchanged, still getting a URL whose filename is the key's own last
        segment.
        """
        params: dict[str, str] = {"Bucket": self._bucket, "Key": key}
        if filename is not None:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    async def delete(self, key: str) -> None:
        """Delete `key`.

        The one caller allowed to reach for this is GDPR erasure (T091, constitution IX): the
        original zip is otherwise never modified and never deleted (constitution IV). A
        capture that turns out to be unparsable is quarantined, not deleted — after ~31 days
        the source holds no replacement, so an unreadable blob is evidence, not garbage.
        """
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def list_keys(self, prefix: str = "") -> list[str]:
        """Every key under `prefix`, paginated transparently.

        Erasure is verified "by listing the bucket, not by trusting a success response"
        (quickstart scenario 10) — this is that listing. It reads the bucket itself rather
        than the database, which is the entire point: a row that says an object is gone is a
        claim, not a fact.
        """
        return await asyncio.to_thread(self._list_keys_sync, prefix)

    def _list_keys_sync(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys
