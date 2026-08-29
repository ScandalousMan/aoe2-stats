"""The export archive assembler (T090): a pure function over already-fetched, already-JSON-safe
data, producing the zip bytes `GET /api/privacy/export/{id}` hands back a signed URL to.

**No SQL, no object-store call, no `aoe2stats_storage` import — the same split `alerting.py`
draws one level up in this package, for the same reason `packages/core`'s own `pyproject.toml`
declares zero dependencies.** `apps/api/src/aoe2stats_api/routers/privacy.py` does every read —
the account, the Steam identities, the profile links, the match records, the two 003 tables this
task names, and the replay blobs pulled out of the object store — and hands this module plain
`Mapping`/`bytes` values it already shaped into the export's own JSON documents. This module only
knows how to fold those into one zip; it could not query a row or fetch a blob if it tried, because
it holds no client capable of either.

**Archive shape** (this module's own contract, since neither `contracts/http-api.md` nor
`data-model.md` fixes one beyond "an archive assembled from the records and the blobs" — see
`apps/api/tests/test_export.py`'s own module docstring, which proposed this shape first): one
`<table>.json` document per table, holding either a single object (`account.json`) or a JSON array
of the rows the caller already serialised, plus the replay blobs verbatim under whatever entry
name the caller supplies — `replay_object_key`'s own `replays/{game_id}/{profile_id}.zip` scheme,
so the archive needs no separate manifest to tell a blob's entry apart from the object store's own
key for it.

**`profile_search_cache` and `rate_limit_counters` never reach this module at all** — T090's task
text and `specs/003-player-search-match-analysis/data-model.md` name why: neither is keyed to a
user an export could name (the first is a re-runnable public-search cache, the second is
rate-limiting bookkeeping), so the caller never builds a `Mapping` for either and there is nothing
here that could reintroduce them.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: The zip's own compression — small, textual JSON documents and already-compressed replay zips
#: alike; `ZIP_DEFLATED` costs nothing on the latter (deflate cannot shrink an already-deflated
#: member further, it just stores it slightly larger than `ZIP_STORED` would) and helps the former.
_COMPRESSION = zipfile.ZIP_DEFLATED


@dataclass(frozen=True, slots=True)
class ExportBundle:
    """Everything one export archive holds, already shaped into JSON-safe values by the caller.

    `account` is a single `Mapping` (`account.json`'s own root object); every other table is a
    `Sequence` of rows, written as a JSON array under `<name>.json`. `favourites` and
    `requested_analyses` are 003's own two tables, named explicitly in T090's task text —
    `favourites` (the profile ids and the dates) and the analyses the user requested (match ids and
    dates) — carried here as ordinary rows like every other table, not a special case this module
    treats differently.

    `replay_blobs` maps an archive entry name (the caller's own `replay_object_key(game_id,
    profile_id)` string) to the exact bytes captured for it — never re-encoded, never truncated,
    per FR-036's "archived replays" and constitution IV.
    """

    account: Mapping[str, Any]
    steam_identities: Sequence[Mapping[str, Any]] = field(default_factory=list)
    profile_links: Sequence[Mapping[str, Any]] = field(default_factory=list)
    matches: Sequence[Mapping[str, Any]] = field(default_factory=list)
    match_players: Sequence[Mapping[str, Any]] = field(default_factory=list)
    favourites: Sequence[Mapping[str, Any]] = field(default_factory=list)
    requested_analyses: Sequence[Mapping[str, Any]] = field(default_factory=list)
    replay_blobs: Mapping[str, bytes] = field(default_factory=dict)


def build_export_archive(bundle: ExportBundle) -> bytes:
    """Assemble `bundle` into one zip archive, held entirely in memory, and return its bytes.

    Never touches a filesystem: `zipfile.ZipFile` is given an `io.BytesIO` buffer, not a path, so
    this function has nothing to clean up and nothing that could collide with a concurrent caller
    — the same "no I/O" discipline `alerting.py`'s docstring states for this package as a whole,
    since an in-memory buffer is a value, not a resource.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=_COMPRESSION) as archive:
        archive.writestr("account.json", json.dumps(dict(bundle.account)))
        archive.writestr("steam_identities.json", json.dumps(list(bundle.steam_identities)))
        archive.writestr("profile_links.json", json.dumps(list(bundle.profile_links)))
        archive.writestr("matches.json", json.dumps(list(bundle.matches)))
        archive.writestr("match_players.json", json.dumps(list(bundle.match_players)))
        archive.writestr("favourites.json", json.dumps(list(bundle.favourites)))
        archive.writestr("requested_analyses.json", json.dumps(list(bundle.requested_analyses)))
        for entry_name, blob in bundle.replay_blobs.items():
            archive.writestr(entry_name, blob)
    return buffer.getvalue()
