"""The replay-engine Protocol: capture-time validation only.

`core` holds this Protocol and nothing else replay-related — no parser, no bytes on disk, no
network — because `core` is what `apps/api` imports (constitution V: the API must never load an
engine). The concrete adapter that satisfies this Protocol lives in `packages/replay-engine`,
imported only by the ingester, which runs it behind a `BaseException`-catching, wall-clock-capped
barrier (T055) so that an engine crash costs one capture, never the run and never the API process.

Capture-time validation checks exactly what `replay_captures` needs and nothing more: that the
downloaded archive is a well-formed single-member `.aoe2record` zip, and that the engine which
opened it identifies itself, so `validated_by` records which engine and version vouched for the
file (data-model.md). Full replay parsing — match extraction, opening detection, elo — is a V2
concern behind the still-empty `replay_parses` table and a different interface; nothing here reads
so much as one operation out of the replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class ReplayValidationError(Exception):
    """Base class for a replay that failed capture-time validation.

    Deliberately a plain `Exception`, not a `BaseException`. A native engine that panics instead of
    returning an error — `aoe2rec-py`'s PyO3 bridge raises `pyo3_runtime.PanicException`, which
    inherits `BaseException` directly and not `Exception`, confirmed against every malformed input
    this package's own tests threw at it — is left to propagate through the adapter untouched. That
    is not an oversight: it is exactly the failure T055's containment barrier exists to catch, and
    catching it here would only hide it one layer too early.
    """


class MalformedArchiveError(ReplayValidationError):
    """The blob is not a well-formed single-member `.aoe2record` archive.

    Raised by the adapter itself, before the engine is ever invoked: not a zip at all, not exactly
    one member, an inner filename that does not match the naming scheme aoe.ms publishes
    (`docs/data-sources.md`), or a decompression ratio far outside the normal range — a zip bomb,
    not a replay (the `replay-parsing` skill).
    """


class EngineParseError(ReplayValidationError):
    """The archive is well-formed but the engine explicitly rejected the inner replay bytes.

    Wraps whatever ordinary `Exception` the engine raised, so a caller sees one stable type instead
    of a third-party one. A raw engine crash (a `BaseException`, not an `Exception`) is not wrapped
    here — see `ReplayValidationError`.
    """


@dataclass(frozen=True, slots=True)
class ReplayValidationResult:
    """What a successful capture-time validation records on `replay_captures`.

    `inner_filename` and `inner_bytes` come from the archive itself; `engine_name` and
    `engine_version` identify the parser that vouched for it. Together they are exactly the
    `inner_filename`, `inner_bytes` and `validated_by` columns data-model.md describes — this
    result carries nothing the schema does not ask for.
    """

    inner_filename: str
    inner_bytes: int
    engine_name: str
    engine_version: str


@runtime_checkable
class ReplayValidator(Protocol):
    """Satisfied by every replay engine adapter (constitution V: pluggable, swappable).

    One method, pure with respect to everything but the bytes it is given: no filesystem, no
    network, no persistence, no partial state left behind on failure. The caller decides what to do
    with the result or the exception; this Protocol only decides the shape of both, which is what
    lets `aoe2rec-py` and `aoc-mgz` sit behind it interchangeably.
    """

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        """Validate a downloaded replay archive at capture time.

        Raises `MalformedArchiveError` for an archive that fails well-formedness on its own terms,
        or `EngineParseError` for one the engine explicitly rejected via an ordinary `Exception`.
        Any `BaseException` that is not an `Exception` — in particular a native engine crash — is
        not this Protocol's to catch; it is the containment barrier's (T055).
        """
        ...
