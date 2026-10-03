"""Tests for the analysis identity (T654, written before T653): FR-040, FR-042, FR-044.

Written ``xfail(strict=True)`` ahead of T653, which removed the markers. The module is still
imported inside each body, which is how it was written before the module existed.

The interface, from data-model.md section 8:

- ``AnalysisIdentity``: a frozen dataclass built with keyword arguments ``recording``,
  ``parser_name``, ``parser_version``, ``parser_dependencies``, ``knowledge``, ``analytics`` and
  ``reconstruction_engine`` (the last defaulting to ``NOT_APPLICABLE``). ``recording``,
  ``parser_dependencies`` and ``knowledge`` are mappings of strings to JSON scalars; ``analytics``
  is a string and has no default.
- ``AnalysisIdentity.digest``: a property returning the hex digest string.
- ``NOT_APPLICABLE``: the module constant, equal to ``"not-applicable"``.
- An empty ``parser_dependencies`` mapping, and ``analytics`` set to ``NOT_APPLICABLE``, raise
  ``ValueError`` at construction.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

import pytest

BASE: dict[str, Any] = {
    "recording": {"object_key": "replays/2026/10/abc.zip", "sha256": "a" * 64},
    "parser_name": "aoe2rec-py",
    "parser_version": "0.3.1",
    "parser_dependencies": {"aoe2rec-py": "0.3.1", "pydantic": "2.11.0", "construct": "2.10.70"},
    "knowledge": {
        "source": "aoe2-data",
        "source_version": "2026-09-01",
        "describes_build": 101000,
        "digest": "b" * 64,
    },
    "reconstruction_engine": "not-applicable",
    "analytics": "1.0.0",
}

# One alternative value per component; each differs from BASE in that component alone.
VARIANTS: dict[str, Any] = {
    "recording": {"object_key": "replays/2026/10/abc.zip", "sha256": "c" * 64},
    "parser_name": "aoc-mgz",
    "parser_version": "0.3.2",
    "parser_dependencies": {
        "aoe2rec-py": "0.3.1",
        "pydantic": "2.12.0",
        "construct": "2.10.70",
    },
    "knowledge": {
        "source": "aoe2-data",
        "source_version": "2026-09-01",
        "describes_build": 101000,
        "digest": "d" * 64,
    },
    "reconstruction_engine": "1.0.0",
    "analytics": "1.0.1",
}


def _build(**overrides: Any) -> Any:
    from aoe2stats_core.truth.identity import AnalysisIdentity

    return AnalysisIdentity(**{**BASE, **overrides})


def _digest_in_fresh_process(kwargs: dict[str, Any], hash_seed: str) -> str:
    code = (
        "import json, sys\n"
        "from aoe2stats_core.truth.identity import AnalysisIdentity\n"
        "print(AnalysisIdentity(**json.loads(sys.stdin.read())).digest)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps(kwargs),
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
    )
    return out.stdout.strip()


def test_digest_is_stable_across_processes() -> None:
    here = _build().digest
    assert here
    assert _digest_in_fresh_process(BASE, "1") == here
    assert _digest_in_fresh_process(BASE, "2") == here


def test_digest_is_insensitive_to_field_ordering() -> None:
    from aoe2stats_core.truth.identity import AnalysisIdentity

    reversed_kwargs = dict(reversed(list(BASE.items())))
    assert list(reversed_kwargs) != list(BASE)
    assert AnalysisIdentity(**reversed_kwargs).digest == _build().digest


def test_digest_is_insensitive_to_key_order_inside_each_mapping() -> None:
    shuffled = {
        name: dict(reversed(list(value.items()))) if isinstance(value, dict) else value
        for name, value in BASE.items()
    }
    assert _build(**shuffled).digest == _build().digest


def test_reordering_dependency_entries_does_not_change_the_digest() -> None:
    deps = BASE["parser_dependencies"]
    reordered = dict(reversed(list(deps.items())))
    assert list(reordered) != list(deps)
    assert _build(parser_dependencies=reordered).digest == _build().digest


@pytest.mark.parametrize("component", sorted(VARIANTS))
def test_differing_in_any_one_component_changes_the_digest(component: str) -> None:
    assert BASE[component] != VARIANTS[component]
    assert _build(**{component: VARIANTS[component]}).digest != _build().digest


def test_every_component_has_a_variant() -> None:
    # Guards the parametrisation: a component added to the tuple without a case here fails.
    from dataclasses import fields

    from aoe2stats_core.truth.identity import AnalysisIdentity

    components = {f.name for f in fields(AnalysisIdentity)}
    assert components == set(BASE) == set(VARIANTS)


def test_an_empty_dependency_record_is_refused() -> None:
    with pytest.raises(ValueError, match="dependenc"):
        _build(parser_dependencies={})


def test_a_non_empty_dependency_record_is_accepted() -> None:
    assert _build(parser_dependencies={"aoe2rec-py": "0.3.1"}).digest


def test_reconstruction_engine_carries_the_not_applicable_marker() -> None:
    from aoe2stats_core.truth.identity import NOT_APPLICABLE, AnalysisIdentity

    assert NOT_APPLICABLE == "not-applicable"
    without_engine = {k: v for k, v in BASE.items() if k != "reconstruction_engine"}
    assert AnalysisIdentity(**without_engine).reconstruction_engine == NOT_APPLICABLE


def test_analytics_is_never_not_applicable() -> None:
    from aoe2stats_core.truth.identity import NOT_APPLICABLE, AnalysisIdentity

    with pytest.raises(ValueError, match="analytics"):
        _build(analytics=NOT_APPLICABLE)
    without_analytics = {k: v for k, v in BASE.items() if k != "analytics"}
    with pytest.raises(TypeError):
        AnalysisIdentity(**without_analytics)
