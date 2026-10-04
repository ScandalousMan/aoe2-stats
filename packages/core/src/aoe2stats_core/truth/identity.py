"""The analysis identity: what a published analysis is a function of (FR-040, data-model.md §8).

The tuple is the recording, the parser's name and version, the parser's dependencies, the knowledge
snapshot, the reconstruction engine version and the analytics version. Its shape never changes:
the reconstruction engine carries an explicit ``NOT_APPLICABLE`` marker until 007 ships, so the
tuple is not retrofitted later. Analytics carries **no** such marker, because marking it
not-applicable would let a banding change keep the same digest and never trigger a recompute
(FR-042).

``identity_digest`` is the one canonical digest in the package: the document validator (rule 10)
recomputes the stored digest with this very function, so the identity and the validator cannot
disagree about what a digest is. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

NOT_APPLICABLE = "not-applicable"


def identity_digest(identity: Mapping[str, Any]) -> str:
    """Digest of every identity field except ``digest`` itself, over canonical JSON."""
    body = {k: v for k, v in identity.items() if k != "digest"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, kw_only=True)
class AnalysisIdentity:
    """The six identity components of a published analysis, built by keyword only."""

    recording: Mapping[str, Any]
    parser_name: str
    parser_version: str
    parser_dependencies: Mapping[str, str]
    knowledge: Mapping[str, Any]
    reconstruction_engine: str = NOT_APPLICABLE
    analytics: str

    def __post_init__(self) -> None:
        if not self.parser_dependencies:
            raise ValueError(
                "parser dependencies must be non-empty: an identity with no dependency record "
                "does not identify its engine (FR-044)"
            )
        if self.analytics == NOT_APPLICABLE:
            raise ValueError(
                "analytics has no not-applicable marker: it is a real version, and without it a "
                "banding change would keep the same digest (FR-042)"
            )
        # Copy the mappings so a caller's later mutation cannot move the digest.
        for name in ("recording", "parser_dependencies", "knowledge"):
            object.__setattr__(self, name, dict(getattr(self, name)))

    @classmethod
    def from_block(cls, block: Mapping[str, Any]) -> AnalysisIdentity:
        """Rebuild from a document's ``identity`` block, where the parser is nested.

        The block's ``digest`` is ignored here; compare it with ``.digest`` to detect a block
        that was altered after it was written.
        """
        return cls(
            recording=block["recording"],
            parser_name=block["parser"]["name"],
            parser_version=block["parser"]["version"],
            parser_dependencies=block["parser_dependencies"],
            knowledge=block["knowledge"],
            reconstruction_engine=block["reconstruction_engine"],
            analytics=block["analytics"],
        )

    def to_block(self) -> dict[str, Any]:
        """The document's ``identity`` block, ``digest`` included."""
        body = self._body()
        return {"digest": identity_digest(body), **body}

    @property
    def digest(self) -> str:
        """Hex SHA-256 over the canonical serialisation of the six components."""
        return identity_digest(self._body())

    def _body(self) -> dict[str, Any]:
        return {
            "recording": dict(self.recording),
            "parser": {"name": self.parser_name, "version": self.parser_version},
            "parser_dependencies": dict(self.parser_dependencies),
            "knowledge": dict(self.knowledge),
            "reconstruction_engine": self.reconstruction_engine,
            "analytics": self.analytics,
        }
