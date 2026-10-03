"""The identity block round trip and the single digest function (T653 helpers)."""

from __future__ import annotations

from aoe2stats_core.truth import validate as validate_module
from aoe2stats_core.truth.identity import AnalysisIdentity, identity_digest

IDENTITY = AnalysisIdentity(
    recording={"object_key": "replays/2026/10/abc.zip", "sha256": "a" * 64},
    parser_name="aoe2rec-py",
    parser_version="0.3.1",
    parser_dependencies={"aoe2rec-py": "0.3.1", "pydantic": "2.11.0"},
    knowledge={"absent": "no-snapshot-for-build", "build": 101000},
    analytics="1.0.0",
)


def test_to_block_nests_the_parser_and_carries_the_digest() -> None:
    block = IDENTITY.to_block()
    assert block["parser"] == {"name": "aoe2rec-py", "version": "0.3.1"}
    assert block["digest"] == IDENTITY.digest
    assert block["reconstruction_engine"] == "not-applicable"


def test_from_block_round_trips_to_an_equal_identity_and_digest() -> None:
    block = IDENTITY.to_block()
    rebuilt = AnalysisIdentity.from_block(block)
    assert rebuilt == IDENTITY
    assert rebuilt.digest == block["digest"]


def test_the_validator_recomputes_with_the_same_function() -> None:
    assert validate_module.identity_digest is identity_digest
    block = IDENTITY.to_block()
    assert identity_digest(block) == block["digest"]
