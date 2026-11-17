"""The reconstruction's contribution to the published document, version 3 (FR-021, FR-022).

Two things only: the identity component that names this engine, and the `reconstructed` block.
Contract: `specs/008-match-reconstruction/contracts/reconstruction-document.md`.

**The identity** is `aoe2stats-reconstruction@<__version__>+rules:sha256:<hex>`, where `<hex>`
is the SHA-256 of the bytes of the packaged `rules.toml`. A change to the package version or to
any byte of the registry moves it, and with it the identity digest, so the staleness test
recomputes and the old document stays at its own key (006 FR-042). `__version__` is embedded
verbatim.

**The block** is empty in this phase: no rule is wired to a datum yet, so nothing is reconstructed.
An empty block is still present, because the engine ran and found nothing to value (rule 14).
"""

from __future__ import annotations

import hashlib
from importlib import resources
from typing import Any

from aoe2stats_reconstruction import __version__

__all__ = ["PACKAGE_NAME", "SCHEMA_VERSION", "reconstructed_block", "reconstruction_engine"]

PACKAGE_NAME = "aoe2stats-reconstruction"

#: The document version this package contributes to (006 shipped 2).
SCHEMA_VERSION = 3


def rules_digest() -> str:
    """SHA-256 hex of the packaged rules registry's bytes."""
    data = resources.files("aoe2stats_reconstruction").joinpath("rules.toml").read_bytes()
    return hashlib.sha256(data).hexdigest()


def reconstruction_engine() -> str:
    """The identity's `reconstruction_engine` component for the installed package."""
    return f"{PACKAGE_NAME}@{__version__}+rules:sha256:{rules_digest()}"


def reconstructed_block() -> dict[str, Any]:
    """The document's `reconstructed` block: empty until a rule is wired to a datum."""
    return {}
