"""The engine dependency record (T627, FR-044): built from installed metadata, never empty."""

from __future__ import annotations

from importlib import metadata

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from aoe2stats_replay_engine import dependencies as deps_module
from aoe2stats_replay_engine.aoe2rec import ENGINE_NAME
from aoe2stats_replay_engine.dependencies import (
    EngineDependencies,
    EngineDependencyError,
    read_engine_dependencies,
)


def test_the_real_installation_records_the_engine_and_each_declared_requirement() -> None:
    record = read_engine_dependencies(ENGINE_NAME)
    assert record.engine_name == ENGINE_NAME
    assert record.engine_version == metadata.version(ENGINE_NAME)
    assert record.versions[canonicalize_name(ENGINE_NAME)] == record.engine_version
    declared = [Requirement(r) for r in metadata.requires(ENGINE_NAME) or []]
    applicable = [r for r in declared if r.marker is None or r.marker.evaluate()]
    assert applicable, "the pinned engine is expected to declare at least one requirement"
    for requirement in applicable:
        assert record.versions[canonicalize_name(requirement.name)] == metadata.version(
            requirement.name
        )


def test_an_empty_record_is_a_construction_error() -> None:
    with pytest.raises(EngineDependencyError):
        EngineDependencies(ENGINE_NAME, "1.0", {})


def test_a_record_without_the_engine_entry_is_a_construction_error() -> None:
    with pytest.raises(EngineDependencyError):
        EngineDependencies(ENGINE_NAME, "1.0", {"pip": "1"})


def test_a_blank_version_is_a_construction_error() -> None:
    with pytest.raises(EngineDependencyError):
        EngineDependencies(ENGINE_NAME, "1.0", {canonicalize_name(ENGINE_NAME): "1.0", "pip": ""})


def test_an_engine_version_disagreeing_with_its_entry_is_a_construction_error() -> None:
    with pytest.raises(EngineDependencyError):
        EngineDependencies(ENGINE_NAME, "2.0", {canonicalize_name(ENGINE_NAME): "1.0"})


def test_a_declared_requirement_that_is_not_installed_raises_rather_than_being_invented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_requires = metadata.requires

    def requires(name: str) -> list[str] | None:
        return [*(real_requires(name) or []), "aoe2stats-surely-not-installed>=1"]

    monkeypatch.setattr(deps_module.metadata, "requires", requires)
    with pytest.raises(EngineDependencyError, match="not installed"):
        read_engine_dependencies(ENGINE_NAME)


def test_a_requirement_excluded_by_its_marker_is_not_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_requires = metadata.requires

    def requires(name: str) -> list[str] | None:
        return [*(real_requires(name) or []), 'aoe2stats-absent; python_version < "3"']

    monkeypatch.setattr(deps_module.metadata, "requires", requires)
    assert "aoe2stats-absent" not in read_engine_dependencies(ENGINE_NAME).versions


def test_an_uninstalled_engine_raises() -> None:
    with pytest.raises(EngineDependencyError, match="not installed"):
        read_engine_dependencies("aoe2stats-surely-not-installed")


def test_as_mapping_is_a_plain_serialisable_dict() -> None:
    mapping = read_engine_dependencies(ENGINE_NAME).as_mapping()
    assert type(mapping) is dict
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items())
