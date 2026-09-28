"""The engine dependency record (T627, FR-044).

The `replay-parsing` skill requires `parser_name`, `parser_version` and `engine_deps` on every
recording's analysis so a later upgrade can tell which ones need re-parsing. This module builds the
`engine_deps` half from what is *installed*, never from a constant: the engine's own distribution
metadata, then each requirement that distribution declares.

Missing knowledge is never papered over (FR-038). A declared requirement that is not installed
raises `EngineDependencyError`; it is not recorded as an empty string, `"unknown"` or the pinned
version from `pyproject.toml`. A requirement whose environment marker excludes it on this platform
is not a requirement here and is skipped, and one guarded by an extra is likewise skipped because no
extra is requested. The record itself refuses to exist empty or without the engine's own entry, so
no caller can publish an analysis that claims an engine and records nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import metadata
from types import MappingProxyType

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


class EngineDependencyError(RuntimeError):
    """The engine's dependency record cannot be built truthfully."""


@dataclass(frozen=True)
class EngineDependencies:
    """The engine and every requirement it declares, each with its installed version.

    `versions` is keyed by canonical distribution name and always contains `engine_name`.
    """

    engine_name: str
    engine_version: str
    versions: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.versions:
            raise EngineDependencyError("an empty dependency record identifies no engine")
        if canonicalize_name(self.engine_name) not in self.versions:
            raise EngineDependencyError(
                f"the record has no entry for the engine {self.engine_name}"
            )
        if any(not name or not version for name, version in self.versions.items()):
            raise EngineDependencyError("a dependency entry lacks a name or a version")
        if self.versions[canonicalize_name(self.engine_name)] != self.engine_version:
            raise EngineDependencyError("the engine's own entry disagrees with engine_version")
        object.__setattr__(self, "versions", MappingProxyType(dict(sorted(self.versions.items()))))

    def as_mapping(self) -> dict[str, str]:
        """The record as a plain, JSON-ready `{distribution: version}` mapping."""
        return dict(self.versions)


def read_engine_dependencies(engine_name: str) -> EngineDependencies:
    """Build the record from installed distribution metadata; raise if any requirement is absent."""
    try:
        engine_version = metadata.version(engine_name)
    except metadata.PackageNotFoundError as exc:
        raise EngineDependencyError(f"{engine_name} is not installed") from exc
    versions: dict[str, str] = {canonicalize_name(engine_name): engine_version}
    for line in metadata.requires(engine_name) or []:
        requirement = Requirement(line)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        try:
            versions[canonicalize_name(requirement.name)] = metadata.version(requirement.name)
        except metadata.PackageNotFoundError as exc:
            raise EngineDependencyError(
                f"{engine_name} requires {requirement.name}, which is not installed"
            ) from exc
    return EngineDependencies(engine_name, engine_version, versions)
