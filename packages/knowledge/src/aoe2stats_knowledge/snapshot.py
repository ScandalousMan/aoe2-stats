"""A knowledge snapshot's identity, its digest and load-time verification (FR-024, FR-025).

Contract: [contracts/knowledge-base.md](../../../../specs/006-replay-analysis-foundations/
contracts/knowledge-base.md), "Identity and immutability". Data model:
[data-model.md](../../../../specs/006-replay-analysis-foundations/data-model.md) §6.

A snapshot's identity is its ``source``, that source's own ``source_version``, the game build it
``describes_build``, and a ``digest`` over its canonical content — ``rules.json`` and
``effects.toml`` — recorded in the snapshot's ``snapshot.toml``. On load the digest is recomputed
from the packaged files and compared; a mismatch refuses to load rather than serving content that
no longer matches what was recorded (FR-025's "never modified or removed" is asserted here, at
every load, not merely at publish time — publish-time enforcement is T639's promotion sequence).

Every snapshot directory is read through :mod:`importlib.resources`, never a bare filesystem path,
so the same code resolves a snapshot identically whether the package is installed from a wheel (a
serverless bundle) or run from an editable checkout (a virtual environment). ``packages/knowledge/
snapshots/`` sits beside ``src/`` rather than inside it, so that it is easy to find and review as
vendored-adjacent, git-tracked data; ``pyproject.toml``'s ``force-include`` maps it into the wheel
at ``aoe2stats_knowledge/snapshots`` for a real build, and ``src/aoe2stats_knowledge/snapshots`` is
a checked-in symlink back to it for the editable/dev case — both resolve to the identical tree
through the identical anchor, ``importlib.resources.files("aoe2stats_knowledge") / "snapshots"``.

This module does not yet implement promotion (T639), build resolution (T641) or carry-forward
(T642); it is the identity and digest mechanism those build on.
"""

from __future__ import annotations

import hashlib
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from typing import Any, Final

#: The package this module's data is anchored to. Never a filesystem path: `importlib.resources`
#: resolves it the same way whether installed from a wheel or run from an editable checkout.
_PACKAGE: Final[str] = "aoe2stats_knowledge"

#: `snapshot.toml`'s own filename, inside each snapshot directory.
IDENTITY_FILENAME: Final[str] = "snapshot.toml"

#: The two files the digest is computed over, in this fixed order (contracts/knowledge-base.md,
#: "Identity and immutability": "the digest is recomputed over rules.json and effects.toml").
DIGESTED_FILENAMES: Final[tuple[str, str]] = ("rules.json", "effects.toml")


class SnapshotError(ValueError):
    """A packaged snapshot could not be loaded: malformed identity or, most importantly, a
    digest that no longer matches its recorded one (FR-025)."""


class SnapshotDigestMismatch(SnapshotError):
    """The digest recomputed from `rules.json` and `effects.toml` disagrees with the digest
    recorded in `snapshot.toml`. Raised in place of returning a `Snapshot` — there is no partial
    or best-effort load, because a mismatch is exactly the condition FR-025 exists to catch."""


@dataclass(frozen=True, slots=True)
class SnapshotIdentity:
    """FR-024's four-field identity: a knowledge source, that source's own version, the game
    build the snapshot describes, and a digest of its canonical content."""

    source: str
    source_version: str
    describes_build: int
    digest: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("source", self.source),
            ("source_version", self.source_version),
            ("digest", self.digest),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SnapshotError(f"{field_name} must be a non-blank string, got {value!r}")
        if not isinstance(self.describes_build, int) or isinstance(self.describes_build, bool):
            raise SnapshotError(f"describes_build must be an int, got {self.describes_build!r}")
        if not self.digest.startswith("sha256:") or len(self.digest) != len("sha256:") + 64:
            raise SnapshotError(
                f"digest must be a 'sha256:'-prefixed 64-character hex digest, got {self.digest!r}"
            )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One packaged knowledge snapshot, verified against its own content on load.

    This is the identity slice only: `directory` is the snapshot's directory name under the
    packaged `snapshots/` root, and `identity` is its FR-024 identity. T639 extends this dataclass
    with promotion and validation; T640 with the normalised rules body it carries.
    """

    directory: str
    identity: SnapshotIdentity


def compute_digest(rules_json: bytes, effects_toml: bytes) -> str:
    """The FR-024 digest over a snapshot's canonical content: `rules.json` then `effects.toml`.

    Each file is hashed with its name and byte length as an unambiguous prefix, so the two files
    cannot be shuffled or truncated into producing the same digest as a different pair of
    contents. Returned as `"sha256:" + hex digest`, the same shape `MANIFEST.json` already uses
    for a pack's own per-file digests.
    """
    hasher = hashlib.sha256()
    for filename, content in zip(DIGESTED_FILENAMES, (rules_json, effects_toml), strict=True):
        hasher.update(filename.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return f"sha256:{hasher.hexdigest()}"


def _snapshots_root() -> resources.abc.Traversable:
    """The packaged `snapshots/` root, resolved through `importlib.resources` alone."""
    return resources.files(_PACKAGE).joinpath("snapshots")


def list_snapshot_directories() -> tuple[str, ...]:
    """Every directory committed under the packaged `snapshots/` root, sorted by name.

    Never a bare filesystem walk: this is the same `importlib.resources` traversal `load_snapshot`
    uses, so a snapshot that is invisible to one is invisible to the other.
    """
    root = _snapshots_root()
    if not root.is_dir():
        return ()
    return tuple(sorted(entry.name for entry in root.iterdir() if entry.is_dir()))


def _require_table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise SnapshotError(f"snapshot.toml: missing or malformed [{key}] table")
    return value


def _require_str(table: Mapping[str, Any], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SnapshotError(f"snapshot.toml: [snapshot].{key} must be a non-blank string")
    return value


def _require_int(table: Mapping[str, Any], key: str) -> int:
    value = table.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SnapshotError(f"snapshot.toml: [snapshot].{key} must be an integer")
    return value


def parse_identity(snapshot_toml_text: str) -> SnapshotIdentity:
    """Parse `snapshot.toml`'s `[snapshot]` table into a `SnapshotIdentity`.

    Reads exactly the four FR-024 fields and ignores every other key `snapshot.toml` may carry
    (`promoted`, `civilisations_modelled`, a validation table): those belong to T639's promotion
    sequence, not this task's identity mechanism, and a table that carries them is not malformed.
    """
    try:
        data = tomllib.loads(snapshot_toml_text)
    except tomllib.TOMLDecodeError as exc:
        raise SnapshotError(f"snapshot.toml is not valid TOML: {exc}") from exc
    table = _require_table(data, "snapshot")
    return SnapshotIdentity(
        source=_require_str(table, "source"),
        source_version=_require_str(table, "source_version"),
        describes_build=_require_int(table, "describes_build"),
        digest=_require_str(table, "digest"),
    )


def load_snapshot(directory: str) -> Snapshot:
    """Load one packaged snapshot by its directory name under `snapshots/`.

    Recomputes the digest over the packaged `rules.json` and `effects.toml` and compares it with
    the digest `snapshot.toml` records; a disagreement raises `SnapshotDigestMismatch` instead of
    returning anything — there is no code path that serves stale or tampered content (FR-025).
    """
    snapshot_dir = _snapshots_root().joinpath(directory)
    if not snapshot_dir.is_dir():
        raise SnapshotError(f"no packaged snapshot directory {directory!r}")
    identity_text = snapshot_dir.joinpath(IDENTITY_FILENAME).read_text(encoding="utf-8")
    identity = parse_identity(identity_text)
    rules_json = snapshot_dir.joinpath("rules.json").read_bytes()
    effects_toml = snapshot_dir.joinpath("effects.toml").read_bytes()
    recomputed = compute_digest(rules_json, effects_toml)
    if recomputed != identity.digest:
        raise SnapshotDigestMismatch(
            f"{directory}: recorded digest {identity.digest} does not match the digest "
            f"recomputed over rules.json and effects.toml, {recomputed}"
        )
    return Snapshot(directory=directory, identity=identity)


def load_all_snapshots() -> tuple[Snapshot, ...]:
    """Every packaged snapshot, loaded and digest-verified, in directory-name order.

    Used by the immutability test that walks every committed snapshot directory — a snapshot that
    fails to load (a bad digest, a malformed identity) raises rather than being silently skipped.
    """
    return tuple(load_snapshot(name) for name in list_snapshot_directories())
