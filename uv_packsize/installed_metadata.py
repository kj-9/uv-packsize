"""Safe installed Core Metadata adapter for dependency graph construction.

Only direct children of supplied ``site-packages`` layouts are inspected.  The
adapter does not resolve directory or file symlinks, does not run code, and
does not retain filesystem paths, metadata text, or parser diagnostics in its
result.
"""

import os
import stat
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from enum import Enum
from pathlib import Path

from uv_packsize.dependency_graph import (
    DependencyGraph,
    InstalledDistributionMetadata,
    InstalledMetadataState,
    InstalledMetadataStateKind,
    build_dependency_graph,
)
from uv_packsize.environment import InstalledEnvironment
from uv_packsize.inventory import (
    InventoryLayout,
    direct_dist_info_directories,
    validated_inventory_layouts,
)
from uv_packsize.models import (
    AnalysisResult,
    ResolutionContext,
    normalize_distribution_name,
)

_CORE_METADATA_VERSIONS = frozenset(
    {"1.0", "1.1", "1.2", "2.1", "2.2", "2.3", "2.4", "2.5"}
)


class InstalledMetadataAdapterErrorCode(str, Enum):
    """Stable failures at the analysis/environment bridge."""

    CONTEXT_MISMATCH = "context-mismatch"


class InstalledMetadataAdapterError(ValueError):
    """A bridge failure that never includes context values or filesystem paths."""

    def __init__(self, code: InstalledMetadataAdapterErrorCode, target: str):
        self.code = code
        self.target = target
        super().__init__(f"{code.value}: {target}")


@dataclass(frozen=True, slots=True, kw_only=True)
class _MetadataObservation:
    name: str
    metadata: InstalledDistributionMetadata | None = None
    state: InstalledMetadataStateKind | None = None

    def __post_init__(self) -> None:
        if (self.metadata is None) == (self.state is None):
            raise ValueError("an observation must contain metadata or a state")


def _dist_info_identity(path: Path) -> tuple[str, str] | None:
    """Infer a safe identity from a conventional dist-info directory name."""

    suffix = ".dist-info"
    if not path.name.casefold().endswith(suffix):
        return None
    stem = path.name[: -len(suffix)]
    name, separator, version = stem.rpartition("-")
    if not separator or not name or not version or "\0" in version:
        return None
    try:
        return normalize_distribution_name(name), version
    except (TypeError, ValueError):
        return None


def _read_regular_bytes(path: Path) -> bytes:
    """Read one regular file without following a symlink where supported."""

    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError("METADATA is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("METADATA is not a regular file")
        with os.fdopen(descriptor, "rb") as metadata_file:
            descriptor = -1
            return metadata_file.read()
    finally:
        if descriptor != -1:
            os.close(descriptor)


def _parse_metadata(raw: bytes) -> InstalledDistributionMetadata | None:
    """Parse complete UTF-8 Core Metadata without preserving diagnostics.

    ``Metadata-Version`` must name one version supported by the current Core
    Metadata specification. Unknown, newer, withdrawn, malformed, missing, and
    duplicate declarations are conservatively invalid.
    """

    try:
        raw.decode("utf-8", errors="strict")
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except (UnicodeError, ValueError):
        return None
    if message.defects:
        return None
    metadata_versions = message.get_all("Metadata-Version", ())
    names = message.get_all("Name", ())
    versions = message.get_all("Version", ())
    if (
        len(metadata_versions) != 1
        or str(metadata_versions[0]) not in _CORE_METADATA_VERSIONS
        or len(names) != 1
        or len(versions) != 1
    ):
        return None
    try:
        return InstalledDistributionMetadata(
            name=str(names[0]),
            version=str(versions[0]),
            requires_dist=tuple(
                str(value) for value in message.get_all("Requires-Dist", ())
            ),
        )
    except (TypeError, ValueError):
        return None


def _observe_dist_info(
    *,
    path: Path,
    installed_versions: dict[str, str],
) -> _MetadataObservation | None:
    """Read one candidate and return a safe outcome for an installed name."""

    fallback_identity = _dist_info_identity(path)
    fallback_name = fallback_identity[0] if fallback_identity is not None else None
    metadata = None
    state = InstalledMetadataStateKind.INVALID
    try:
        mode = path.lstat().st_mode
    except OSError:
        mode = 0
    if stat.S_ISDIR(mode):
        try:
            raw = _read_regular_bytes(path / "METADATA")
        except FileNotFoundError:
            state = InstalledMetadataStateKind.MISSING
        except (OSError, ValueError):
            pass
        else:
            metadata = _parse_metadata(raw)
    if metadata is None:
        if fallback_name in installed_versions:
            return _MetadataObservation(
                name=fallback_name,
                state=state,
            )
        return None

    # Prefer the directory identity if it identifies an installed result: it
    # lets a different Name header be represented as a safe name mismatch.
    name = fallback_name if fallback_name in installed_versions else metadata.name
    if name not in installed_versions:
        return None
    if metadata.name != name:
        return _MetadataObservation(
            name=name,
            state=InstalledMetadataStateKind.NAME_MISMATCH,
        )
    if metadata.version != installed_versions[name]:
        return _MetadataObservation(
            name=name,
            state=InstalledMetadataStateKind.VERSION_MISMATCH,
        )
    return _MetadataObservation(name=name, metadata=metadata)


def _metadata_inputs(
    analysis: AnalysisResult,
    layouts: tuple[InventoryLayout, ...],
) -> tuple[
    tuple[InstalledDistributionMetadata, ...], tuple[InstalledMetadataState, ...]
]:
    installed_versions = {
        distribution.name: distribution.version
        for distribution in analysis.distributions
    }
    observations: dict[str, list[_MetadataObservation]] = {}
    for layout in layouts:
        for dist_info_dir in direct_dist_info_directories(layout):
            observation = _observe_dist_info(
                path=dist_info_dir,
                installed_versions=installed_versions,
            )
            if observation is not None:
                observations.setdefault(observation.name, []).append(observation)

    metadata: list[InstalledDistributionMetadata] = []
    states: list[InstalledMetadataState] = []
    for name in sorted(observations):
        values = observations[name]
        if len(values) != 1:
            states.append(
                InstalledMetadataState(
                    name=name,
                    kind=InstalledMetadataStateKind.DUPLICATE,
                )
            )
        elif values[0].metadata is not None:
            metadata.append(values[0].metadata)
        else:
            state = values[0].state
            if state is None:
                raise AssertionError("metadata observation state is required")
            states.append(InstalledMetadataState(name=name, kind=state))
    return tuple(metadata), tuple(states)


def build_installed_dependency_graph(
    analysis: AnalysisResult,
    environment: InstalledEnvironment,
) -> DependencyGraph:
    """Build a graph from one validated installed environment.

    The environment is the single source of layouts, marker values, and
    resolution context.  Layout compatibility and duplicate-site checks use the
    inventory collector's existing semantics.  Missing, unreadable, invalid,
    duplicate, and name/version-mismatched metadata become safe graph warnings.
    """

    if not isinstance(analysis, AnalysisResult):
        raise TypeError("analysis must be an AnalysisResult")
    if not isinstance(analysis.context, ResolutionContext):
        raise TypeError("installed dependency metadata requires a ResolutionContext")
    if not isinstance(environment, InstalledEnvironment):
        raise TypeError("environment must be an InstalledEnvironment")
    if analysis.context != environment.context:
        raise InstalledMetadataAdapterError(
            InstalledMetadataAdapterErrorCode.CONTEXT_MISMATCH,
            "installed-environment",
        )
    layouts = validated_inventory_layouts(environment.layouts)
    metadata, metadata_states = _metadata_inputs(analysis, layouts)
    return build_dependency_graph(
        analysis,
        metadata,
        environment.marker_environment,
        metadata_states=metadata_states,
    )
