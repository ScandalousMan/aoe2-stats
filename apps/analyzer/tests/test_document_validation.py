"""The analyzer refuses to publish a document that breaks the contract (T661, US3).

Every test was ``xfail(strict=True)`` until its seam landed, and each imports the seam **inside its
own body**, so a missing symbol is a per-test expected failure and not a collection error. T655
defined ``validate_document`` and took the marker off every case that injects its own register; the
one case that reads the packaged register stays ``xfail`` until T656 promotes its datum. When a seam
lands the marker must come off in the same change: ``strict`` turns an unexpected pass into a
failure, which is how this file is kept honest.

**The seam this file assumes**, for whoever lands T655 and T656 (``contracts/analysis-document.md``
names the validator, ``aoe2stats_core.truth.validate``, which already exists, but not the analyzer
function that runs it before the object is written):

- ``aoe2stats_analyzer.extract.validate_document(document, register=None) -> None``. It is the one
  gate ``run.py`` calls **before** writing the object (T656). ``register`` defaults to the packaged
  ``aoe2stats_core.truth.register.REGISTER`` entries (a mapping of datum id to entry); a test passes
  a small one so each case isolates a single rule. It delegates to
  ``aoe2stats_core.truth.validate.validate`` and lets its ``DocumentInvalid`` propagate unchanged
  (``rules``: the contract rule numbers broken; the message names each violation), so 003's failure
  path records the validator's own message.

Which contract rule answers each case, as ``aoe2stats_core.truth.validate`` reports it today:

- empty dependency record: rule 9 (SC-011, FR-044);
- a datum whose ``requires_knowledge`` meets a ``blocking`` gap: rule 8 (FR-037). The injected
  register's ``requires_knowledge`` is bare field names (``("cost",)``), as ``register.toml``
  writes them, and a gap's ``prevents`` names data. Since T666a the case is also run **on the
  packaged register** with the gaps the real coverage pass produces (the last section below);
  until then it passed only against an injected register in a format the real one never uses;
- a value with no tier: rule 3 when its provenance entry lacks the tier, rule 2 when it has no
  provenance entry at all (SC-002, FR-007);
- an inferred datum whose register status is not ``published``: rule 1, message
  ``inferred datum '<id>' is not a published register datum``. T656 promotes
  ``participant.group_silence_episodes`` for exactly this reason.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_core.truth.tiers import Tier
from aoe2stats_core.truth.validate import identity_digest


@dataclass(frozen=True)
class Entry:
    """The duck-typed register entry the validator reads."""

    path: str | None
    tier: Tier
    status: str = "published"
    non_claim: str | None = None
    requires_knowledge: tuple[str, ...] = ()


def _register(*, silence_status: str = "published") -> dict[str, Entry]:
    return {
        "document.schema_version": Entry("schema_version", Tier.OBSERVED),
        "participant.civ_id": Entry("participants[].civ_id", Tier.OBSERVED),
        "participant.army_cost": Entry(
            "participants[].army_cost", Tier.DERIVED, requires_knowledge=("cost",)
        ),
        "participant.group_silence_episodes": Entry(
            None,
            Tier.INFERRED,
            status=silence_status,
            non_claim="not a casualty count",
        ),
    }


def _identity(parser_dependencies: dict[str, str] | None = None) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "recording": {"object_key": "k", "sha256": "ab"},
        "parser": {"name": "aoe2rec-py", "version": "1.0"},
        "parser_dependencies": (
            {"aoe2rec-py": "1.0"} if parser_dependencies is None else parser_dependencies
        ),
        "knowledge": {"source": "s", "source_version": "1", "describes_build": 1, "digest": "d"},
        "reconstruction_engine": "not-applicable",
        "analytics": "a1",
    }
    # Recomputed, so a case that empties the dependency record trips rule 9 and nothing else.
    identity["digest"] = identity_digest(identity)
    return identity


def _document() -> dict[str, Any]:
    """A complete document: non-empty dependency record, every value tiered, no gap."""
    return {
        "schema_version": 2,
        "envelope": {"extracted_at": "2026-01-01T00:00:00Z"},
        "extracted_at": "2026-01-01T00:00:00Z",
        "participants": [{"civ_id": 3, "army_cost": 120}],
        "identity": _identity(),
        "provenance": {
            "document.schema_version": {"tier": "observed", "method": "write@1", "inputs": []},
            "participant.civ_id": {"tier": "observed", "method": "decode@1", "inputs": []},
            "participant.army_cost": {
                "tier": "derived",
                "method": "army-cost@1",
                "inputs": ["participant.civ_id"],
            },
            "participant.group_silence_episodes": {
                "tier": "inferred",
                "method": "group-silence.banding@1",
                "inputs": [],
            },
        },
        "inferred": {
            "participant.group_silence_episodes": [
                {
                    "participant": 1,
                    "from_ms": 0,
                    "units": 2,
                    "confidence": {"level": "medium", "basis": "silence lasted 200 s"},
                    "non_claim": "not a casualty count",
                }
            ]
        },
        "knowledge_gaps": [],
    }


def _gap(
    severity: str,
    *,
    field: str = "cost",
    prevents: tuple[str, ...] = ("participant.army_cost",),
) -> dict[str, Any]:
    return {
        "entity": {"kind": "unit", "id": 0},
        "field": field,
        "build": 1,
        "civilisation": 0,
        "cause": "civilisation-not-modelled",
        "prevents": list(prevents) if severity == "blocking" else [],
        "severity": severity,
    }


def _rejected(
    document: dict[str, Any], register: dict[str, Entry], *rules: int, exact: bool = True
) -> Any:  # DocumentInvalid, imported in the body
    from aoe2stats_analyzer.extract import validate_document
    from aoe2stats_core.truth.validate import DocumentInvalid

    with pytest.raises(DocumentInvalid) as info:
        validate_document(document, register=register)
    if exact:
        assert info.value.rules == frozenset(rules)
    else:
        assert frozenset(rules) <= info.value.rules
    assert str(info.value)
    return info.value


def _accepted(document: dict[str, Any], register: dict[str, Entry]) -> None:
    from aoe2stats_analyzer.extract import validate_document

    validate_document(document, register=register)


# --- the contrast case that fixes the boundary --------------------------------------------------


def test_a_complete_document_is_accepted() -> None:
    _accepted(_document(), _register())


# --- SC-011: an empty dependency record ---------------------------------------------------------


def test_a_document_whose_dependency_record_is_empty_is_rejected() -> None:
    document = _document()
    document["identity"] = _identity(parser_dependencies={})

    error = _rejected(document, _register(), 9)

    assert "parser_dependencies" in str(error)


# --- FR-037: a blocking gap withholds every dependent value -------------------------------------


def test_a_datum_whose_knowledge_meets_a_blocking_gap_is_rejected() -> None:
    document = _document()
    document["knowledge_gaps"] = [_gap("blocking")]

    error = _rejected(document, _register(), 8)

    assert "participant.army_cost" in str(error)


def test_a_datum_whose_knowledge_meets_only_an_informational_gap_is_accepted() -> None:
    document = _document()
    document["knowledge_gaps"] = [_gap("informational")]

    _accepted(document, _register())


def test_a_blocking_gap_on_knowledge_no_datum_needs_withholds_nothing() -> None:
    document = _document()
    document["knowledge_gaps"] = [
        _gap("blocking", field="production_time", prevents=("participant.something_else",))
    ]

    _accepted(document, _register())


# --- SC-002: no value without its tier ----------------------------------------------------------


def test_a_value_whose_provenance_carries_no_tier_is_rejected() -> None:
    document = _document()
    del document["provenance"]["participant.civ_id"]["tier"]

    error = _rejected(document, _register(), 3)

    assert "participant.civ_id" in str(error)


def test_a_value_with_no_provenance_entry_at_all_is_rejected() -> None:
    document = _document()
    del document["provenance"]["participant.civ_id"]

    error = _rejected(document, _register(), 2)

    assert "participant.civ_id" in str(error)


def test_an_inferred_value_with_no_tier_is_rejected() -> None:
    document = _document()
    del document["provenance"]["participant.group_silence_episodes"]["tier"]

    _rejected(document, _register(), 3)


# --- the register status gate, and why T656 promotes group_silence_episodes ---------------------


def test_an_inferred_datum_whose_register_status_is_not_published_is_rejected() -> None:
    document = _document()

    # Rule 2 follows from rule 1: the unpublished datum is not counted as present, so its
    # provenance entry names something "not in the document". Only rule 1 is the cause.
    error = _rejected(document, _register(silence_status="planned"), 1, exact=False)

    assert "participant.group_silence_episodes" in str(error)
    assert "not a published register datum" in str(error)


def test_the_packaged_register_publishes_the_one_inferred_datum_this_feature_ships() -> None:
    """Against the real register, not an injected one: the entry is published (T656), so a document
    carrying ``participant.group_silence_episodes`` passes, and ``schema_version`` — a published
    datum — owes its provenance entry like any other (FR-007)."""
    from aoe2stats_analyzer.extract import validate_document

    document = {
        "schema_version": 2,
        "identity": _identity(),
        "provenance": {
            "document.schema_version": copy.deepcopy(
                _document()["provenance"]["document.schema_version"]
            ),
            "participant.group_silence_episodes": copy.deepcopy(
                _document()["provenance"]["participant.group_silence_episodes"]
            ),
        },
        "inferred": copy.deepcopy(_document()["inferred"]),
        "knowledge_gaps": [],
    }

    validate_document(document)


# --- the two locks, on the packaged register (T666a) ---------------------------------------------
#
# Everything above injects a register of its own, which is how rule 8 passed its test while it could
# never fire against the real one. These cases read the packaged register and the gaps the real
# coverage pass produces from the committed recordings. No entry of the packaged register is both
# published and knowledge-dependent yet, so the one datum a later feature will publish first,
# ``reconstruction.resources_spent`` (``requires_knowledge = ["cost"]``), is flipped to published at
# a path: the register's own entry, in its own format, in the state it will have on that day.

_RECORDINGS = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays"
_WITH_COST_GAPS = _RECORDINGS / "AgeIIDE_Replay_504695319.zip"
_WITHOUT = _RECORDINGS / "AgeIIDE_Replay_500546441.zip"
_KNOWLEDGE_DATUM = "reconstruction.resources_spent"
_ALWAYS_THERE = "participant.civ_id"


def _extractor() -> Any:
    from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

    return Aoe2RecExtractor(max_raw_bytes=25_165_824)


def _real_document(recording: Path) -> dict[str, Any]:
    from aoe2stats_analyzer.extract import build_document

    return build_document(
        _extractor(),
        recording.read_bytes(),
        game_id=1,
        object_key="retained-recordings/1/1.zip",
        zip_sha256="ab" * 32,
        extracted_at=datetime(2026, 10, 3, 12, 0, tzinfo=UTC),
    )


@pytest.fixture(scope="module")
def cost_gap_document() -> dict[str, Any]:
    return _real_document(_WITH_COST_GAPS)


@pytest.fixture(scope="module")
def other_document() -> dict[str, Any]:
    return _real_document(_WITHOUT)


def _packaged_with_a_published_knowledge_datum() -> dict[str, Any]:
    from aoe2stats_analyzer.extract import _packaged_register
    from aoe2stats_core.truth.register import REGISTER

    register = dict(_packaged_register())
    entry = REGISTER[_KNOWLEDGE_DATUM]
    assert entry.requires_knowledge == ("cost",)  # the register's own, bare format
    register[_KNOWLEDGE_DATUM] = dataclasses.replace(
        entry, status="published", path="participants[].resources_spent"
    )
    return register


def _publishing_the_knowledge_datum(document: dict[str, Any]) -> dict[str, Any]:
    planted = copy.deepcopy(document)
    planted["participants"][0]["resources_spent"] = 10
    planted["provenance"][_KNOWLEDGE_DATUM] = {
        "tier": "reconstructed",
        "method": "resources-spent@1",
        "inputs": [],
    }
    return planted


def _blocking(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [gap for gap in document["knowledge_gaps"] if gap["severity"] == "blocking"]


def _whole_build_gaps() -> list[dict[str, Any]]:
    """What the coverage pass returns for the committed recording once its build is one no snapshot
    describes: the single whole-build gap, naming no entity and no field."""
    from aoe2stats_analyzer.extract import _gap_record
    from aoe2stats_core.replay.events import EventKind, MatchStartedPayload
    from aoe2stats_knowledge.coverage import coverage

    events = []
    for event in _extractor().events(_WITHOUT.read_bytes()):
        if event.kind is EventKind.MATCH_STARTED and isinstance(event.payload, MatchStartedPayload):
            event = dataclasses.replace(event, payload=dataclasses.replace(event.payload, build=1))
        events.append(event)
    gaps = [_gap_record(gap) for gap in coverage(events)]
    assert [gap["cause"] for gap in gaps] == ["no-snapshot-for-build"]
    assert gaps[0]["entity"] is None
    assert gaps[0]["field"] is None
    return gaps


def test_a_real_blocking_gap_refuses_the_datum_whose_knowledge_it_prevents(
    cost_gap_document: dict[str, Any],
) -> None:
    from aoe2stats_analyzer.extract import validate_document
    from aoe2stats_core.truth.validate import DocumentInvalid

    blocking = _blocking(cost_gap_document)
    assert any(_KNOWLEDGE_DATUM in gap["prevents"] for gap in blocking), blocking
    register = _packaged_with_a_published_knowledge_datum()

    with pytest.raises(DocumentInvalid) as info:
        validate_document(_publishing_the_knowledge_datum(cost_gap_document), register)

    assert info.value.rules == frozenset({8})
    assert _KNOWLEDGE_DATUM in str(info.value)


def test_the_same_gaps_leave_a_datum_that_needs_no_knowledge_alone(
    cost_gap_document: dict[str, Any],
) -> None:
    from aoe2stats_analyzer.extract import validate_document

    assert _blocking(cost_gap_document)
    register = _packaged_with_a_published_knowledge_datum()
    assert register[_ALWAYS_THERE].requires_knowledge == ()
    assert _ALWAYS_THERE in cost_gap_document["provenance"]

    validate_document(cost_gap_document, register)  # the datum is simply not in the document


def test_a_real_informational_gap_blocks_nothing(
    cost_gap_document: dict[str, Any], other_document: dict[str, Any]
) -> None:
    from aoe2stats_analyzer.extract import validate_document

    informational = [
        g for g in other_document["knowledge_gaps"] if g["severity"] == "informational"
    ]
    assert informational
    assert not _blocking(other_document)
    register = _packaged_with_a_published_knowledge_datum()
    planted = _publishing_the_knowledge_datum(other_document)

    validate_document(planted, register)

    only_informational = copy.deepcopy(cost_gap_document)
    only_informational["knowledge_gaps"] = [
        g for g in only_informational["knowledge_gaps"] if g["severity"] == "informational"
    ]
    validate_document(_publishing_the_knowledge_datum(only_informational), register)


def test_a_whole_build_gap_blocks_every_knowledge_dependent_datum(
    other_document: dict[str, Any],
) -> None:
    from aoe2stats_analyzer.extract import validate_document
    from aoe2stats_core.truth.validate import DocumentInvalid

    register = _packaged_with_a_published_knowledge_datum()
    gaps = _whole_build_gaps()

    planted = _publishing_the_knowledge_datum(other_document)
    planted["knowledge_gaps"] = gaps
    with pytest.raises(DocumentInvalid) as info:
        validate_document(planted, register)
    assert info.value.rules == frozenset({8})
    assert _KNOWLEDGE_DATUM in str(info.value)

    # The contrast: the same gap, a document whose every datum needs no knowledge.
    plain = copy.deepcopy(other_document)
    plain["knowledge_gaps"] = gaps
    validate_document(plain, register)


def test_a_whole_build_gap_blocks_even_when_its_prevents_list_is_empty(
    other_document: dict[str, Any],
) -> None:
    from aoe2stats_analyzer.extract import validate_document
    from aoe2stats_core.truth.validate import DocumentInvalid

    planted = _publishing_the_knowledge_datum(other_document)
    planted["knowledge_gaps"] = [{**_whole_build_gaps()[0], "prevents": []}]

    with pytest.raises(DocumentInvalid) as info:
        validate_document(planted, _packaged_with_a_published_knowledge_datum())

    assert info.value.rules == frozenset({8})


# FR-011, SC-003: the wildcard data of the real register take one key and one scalar.


def test_a_real_dependency_name_with_dots_is_accepted(other_document: dict[str, Any]) -> None:
    from aoe2stats_analyzer.extract import validate_document

    document = copy.deepcopy(other_document)
    document["engine"]["deps"]["zope.interface"] = "7.0"

    validate_document(document)


@pytest.mark.parametrize(
    "path, key, value",
    [
        (("engine", "deps"), "verdict", {"player_1": "lost the fight"}),
        (("engine", "deps"), "zope.interface", {"7.0": "ok"}),
        (("engine", "deps"), "verdict", 7),  # a version is a string
        (("participants", 0, "age_up_commands"), "coaching_note", "should have walled earlier"),
        (("participants", 0, "age_up_commands"), "101", {"at": 1}),
        (("participants", 0, "age_up_commands"), "101", ["walled"]),
    ],
)
def test_a_value_the_wildcards_do_not_take_is_refused_on_the_real_register(
    other_document: dict[str, Any], path: tuple[str | int, ...], key: str, value: Any
) -> None:
    from aoe2stats_analyzer.extract import validate_document
    from aoe2stats_core.truth.validate import DocumentInvalid

    document = copy.deepcopy(other_document)
    target: Any = document
    for step in path:
        target = target[step]
    target[key] = value

    with pytest.raises(DocumentInvalid) as info:
        validate_document(document)

    assert 1 in info.value.rules
    assert key in str(info.value)
