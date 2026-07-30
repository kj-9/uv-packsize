"""Pure installed-metadata dependency graph construction.

This module deliberately does not read installed metadata itself and never
consults the executing interpreter's marker environment.  Adapters supply the
already-read Core Metadata and the complete target marker environment instead.
The graph is separate from :mod:`uv_packsize.models`: it contains relationships
and attribution only, never file inventories or byte totals.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from packaging.requirements import InvalidRequirement, Requirement

from uv_packsize.models import AnalysisResult, normalize_distribution_name

_MARKER_VARIABLES = (
    "implementation_name",
    "implementation_version",
    "os_name",
    "platform_machine",
    "platform_python_implementation",
    "platform_release",
    "platform_system",
    "platform_version",
    "python_full_version",
    "python_version",
    "sys_platform",
)


def _require_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError(f"{field_name} must be a non-empty string without NUL")
    return value


def _extras(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{field_name} must be an iterable of distribution names")
    return tuple(sorted({normalize_distribution_name(value) for value in values}))


class RootRequirementStatus(str, Enum):
    """Safe outcome of identifying one requested root requirement."""

    RECOGNIZED = "recognized"
    INACTIVE = "inactive"
    VERSION_MISMATCH = "version-mismatch"
    UNMATCHED = "unmatched"
    UNIDENTIFIABLE = "unidentifiable"


class DependencyKind(str, Enum):
    """Relationship of an installed distribution to recognized roots."""

    ROOT = "root"
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    UNATTRIBUTED = "unattributed"


class DependencyGraphWarningCode(str, Enum):
    """Machine-readable graph conditions, distinct from size warnings."""

    INVALID_ROOT_REQUIREMENT = "invalid-root-requirement"
    ROOT_MARKER_INDETERMINATE = "root-marker-indeterminate"
    ROOT_VERSION_MISMATCH = "root-version-mismatch"
    ROOT_UNMATCHED = "root-unmatched"
    INVALID_REQUIRES_DIST = "invalid-requires-dist"
    MARKER_INDETERMINATE = "marker-indeterminate"
    MISSING_METADATA = "missing-metadata"
    METADATA_VERSION_MISMATCH = "metadata-version-mismatch"
    MISSING_DEPENDENCY_TARGET = "missing-dependency-target"

    @property
    def causes_incomplete_result(self) -> bool:
        return True


class DependencyGraphWarningTargetKind(str, Enum):
    """Safe namespace of a graph warning target."""

    DISTRIBUTION = "distribution"
    ROOT_INPUT = "root-input"


class DependencyGraphCompleteness(str, Enum):
    """Whether dependency attribution is complete enough to trust."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkerEnvironment:
    """Complete target environment used for PEP 508 marker evaluation.

    All standard marker variables are required so :mod:`packaging` never needs
    to fill absent values from the host interpreter.  ``extra`` is supplied per
    edge by the graph builder and is intentionally not a constructor field.
    """

    implementation_name: str
    implementation_version: str
    os_name: str
    platform_machine: str
    platform_python_implementation: str
    platform_release: str
    platform_system: str
    platform_version: str
    python_full_version: str
    python_version: str
    sys_platform: str

    def __post_init__(self) -> None:
        for field_name in _MARKER_VARIABLES:
            _require_string(getattr(self, field_name), field_name)

    def as_mapping(self, *, extra: str) -> dict[str, str]:
        """Return a complete explicit environment for one selected extra."""

        return {
            field_name: getattr(self, field_name) for field_name in _MARKER_VARIABLES
        } | {"extra": extra}


@dataclass(frozen=True, slots=True, kw_only=True)
class InstalledDistributionMetadata:
    """Core Metadata needed for graph construction, supplied by an adapter."""

    name: str
    version: str
    requires_dist: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", normalize_distribution_name(self.name))
        _require_string(self.version, "version")
        if isinstance(self.requires_dist, str):
            raise TypeError("requires_dist must be a tuple of strings, not a string")
        requires_dist = tuple(self.requires_dist)
        if any(not isinstance(value, str) for value in requires_dist):
            raise TypeError("requires_dist must contain strings")
        object.__setattr__(self, "requires_dist", requires_dist)


@dataclass(frozen=True, slots=True, kw_only=True)
class RootRequirement:
    """Non-reversible, safe root-recognition record."""

    input_index: int
    name: str | None
    status: RootRequirementStatus
    selected_extras: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.input_index, int)
            or isinstance(self.input_index, bool)
            or self.input_index < 0
        ):
            raise ValueError("input_index must be a non-negative integer")
        if self.name is not None:
            object.__setattr__(self, "name", normalize_distribution_name(self.name))
        if not isinstance(self.status, RootRequirementStatus):
            raise TypeError("status must be a RootRequirementStatus")
        if (
            self.status is RootRequirementStatus.UNIDENTIFIABLE
            and self.name is not None
        ):
            raise ValueError("an unidentifiable root must not have a name")
        if (
            self.status is not RootRequirementStatus.UNIDENTIFIABLE
            and self.name is None
        ):
            raise ValueError("an identifiable root must have a name")
        object.__setattr__(
            self, "selected_extras", _extras(self.selected_extras, "selected_extras")
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyGraphWarning:
    """A safe typed graph warning with no metadata text or parser diagnostics."""

    code: DependencyGraphWarningCode
    target_kind: DependencyGraphWarningTargetKind
    target_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, DependencyGraphWarningCode):
            raise TypeError("code must be a DependencyGraphWarningCode")
        if not isinstance(self.target_kind, DependencyGraphWarningTargetKind):
            raise TypeError("target_kind must be a DependencyGraphWarningTargetKind")
        if self.target_kind is DependencyGraphWarningTargetKind.DISTRIBUTION:
            object.__setattr__(
                self,
                "target_identity",
                normalize_distribution_name(self.target_identity),
            )
        elif not self.target_identity.isdecimal():
            raise ValueError("root-input target_identity must be a decimal input index")


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyEdge:
    """One active dependency edge between installed distributions."""

    source_name: str
    target_name: str
    requested_extras: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_name", normalize_distribution_name(self.source_name)
        )
        object.__setattr__(
            self, "target_name", normalize_distribution_name(self.target_name)
        )
        object.__setattr__(
            self,
            "requested_extras",
            _extras(self.requested_extras, "requested_extras"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyGraphNode:
    """An installed distribution with deterministic root attribution."""

    name: str
    version: str
    kind: DependencyKind
    root_names: tuple[str, ...] = ()
    is_shared: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", normalize_distribution_name(self.name))
        _require_string(self.version, "version")
        if not isinstance(self.kind, DependencyKind):
            raise TypeError("kind must be a DependencyKind")
        object.__setattr__(self, "root_names", _extras(self.root_names, "root_names"))
        if not isinstance(self.is_shared, bool):
            raise TypeError("is_shared must be a bool")
        if self.is_shared != (len(self.root_names) >= 2):
            raise ValueError("is_shared must match root reachability")
        if self.kind is DependencyKind.UNATTRIBUTED and self.root_names:
            raise ValueError("an unattributed node cannot have recognized roots")
        if self.kind is not DependencyKind.UNATTRIBUTED and not self.root_names:
            raise ValueError("an attributed node must have recognized roots")


def _warning_key(warning: DependencyGraphWarning) -> tuple[str, str, str]:
    return (warning.code.value, warning.target_kind.value, warning.target_identity)


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyGraph:
    """Immutable graph and attribution result; it deliberately has no bytes."""

    roots: tuple[RootRequirement, ...]
    nodes: tuple[DependencyGraphNode, ...]
    edges: tuple[DependencyEdge, ...]
    warnings: tuple[DependencyGraphWarning, ...] = ()

    def __post_init__(self) -> None:
        roots = tuple(self.roots)
        if any(not isinstance(root, RootRequirement) for root in roots):
            raise TypeError("roots must contain RootRequirement values")
        if len({root.input_index for root in roots}) != len(roots):
            raise ValueError("roots cannot contain duplicate input indexes")
        object.__setattr__(
            self, "roots", tuple(sorted(roots, key=lambda root: root.input_index))
        )

        nodes = tuple(self.nodes)
        if any(not isinstance(node, DependencyGraphNode) for node in nodes):
            raise TypeError("nodes must contain DependencyGraphNode values")
        if len({node.name for node in nodes}) != len(nodes):
            raise ValueError("nodes cannot contain duplicate distribution names")
        object.__setattr__(
            self, "nodes", tuple(sorted(nodes, key=lambda node: node.name))
        )
        node_names = {node.name for node in nodes}

        edges = tuple(self.edges)
        if any(not isinstance(edge, DependencyEdge) for edge in edges):
            raise TypeError("edges must contain DependencyEdge values")
        if any(
            edge.source_name not in node_names or edge.target_name not in node_names
            for edge in edges
        ):
            raise ValueError("edges must connect graph nodes")
        edges_by_endpoints: dict[tuple[str, str], set[str]] = {}
        for edge in edges:
            edges_by_endpoints.setdefault(
                (edge.source_name, edge.target_name), set()
            ).update(edge.requested_extras)
        object.__setattr__(
            self,
            "edges",
            tuple(
                DependencyEdge(
                    source_name=source_name,
                    target_name=target_name,
                    requested_extras=tuple(sorted(requested_extras)),
                )
                for (source_name, target_name), requested_extras in sorted(
                    edges_by_endpoints.items()
                )
            ),
        )

        warnings = tuple(self.warnings)
        if any(not isinstance(warning, DependencyGraphWarning) for warning in warnings):
            raise TypeError("warnings must contain DependencyGraphWarning values")
        object.__setattr__(
            self,
            "warnings",
            tuple(sorted(set(warnings), key=_warning_key)),
        )

    @property
    def completeness(self) -> DependencyGraphCompleteness:
        if any(warning.code.causes_incomplete_result for warning in self.warnings):
            return DependencyGraphCompleteness.INCOMPLETE
        return DependencyGraphCompleteness.COMPLETE


class _MarkerState(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INDETERMINATE = "indeterminate"


def _evaluate_marker(
    requirement: Requirement,
    environment: MarkerEnvironment,
    selected_extras: tuple[str, ...],
) -> _MarkerState:
    if requirement.marker is None:
        return _MarkerState.ACTIVE
    # PEP 508 markers that mention ``extra`` are active if any selected extra
    # satisfies them.  Evaluating with the empty extra also handles markers
    # such as ``extra != 'docs'`` without consulting host state.
    extras = ("", *selected_extras)
    try:
        return (
            _MarkerState.ACTIVE
            if any(
                requirement.marker.evaluate(
                    environment=environment.as_mapping(extra=extra)
                )
                for extra in extras
            )
            else _MarkerState.INACTIVE
        )
    except Exception:
        return _MarkerState.INDETERMINATE


def _parse_requirement(value: str) -> Requirement | None:
    try:
        return Requirement(value)
    except InvalidRequirement:
        return None


def _matches_installed_version(requirement: Requirement, version: str) -> bool:
    """Safely test a parsed root specifier without exposing version diagnostics."""

    try:
        return requirement.specifier.contains(version)
    except Exception:
        return False


def _metadata_by_name(
    metadata: Iterable[InstalledDistributionMetadata],
) -> dict[str, InstalledDistributionMetadata]:
    values = tuple(metadata)
    if any(not isinstance(value, InstalledDistributionMetadata) for value in values):
        raise TypeError("metadata must contain InstalledDistributionMetadata values")
    by_name = {value.name: value for value in values}
    if len(by_name) != len(values):
        raise ValueError(
            "metadata cannot contain duplicate normalized distribution names"
        )
    return by_name


def _root_requirements(
    analysis: AnalysisResult,
    installed_versions: Mapping[str, str],
    environment: MarkerEnvironment,
    warnings: set[DependencyGraphWarning],
) -> tuple[RootRequirement, ...]:
    roots: list[RootRequirement] = []
    for index, value in enumerate(analysis.context.requirements):
        requirement = _parse_requirement(value)
        if requirement is None:
            warnings.add(
                DependencyGraphWarning(
                    code=DependencyGraphWarningCode.INVALID_ROOT_REQUIREMENT,
                    target_kind=DependencyGraphWarningTargetKind.ROOT_INPUT,
                    target_identity=str(index),
                )
            )
            roots.append(
                RootRequirement(
                    input_index=index,
                    name=None,
                    status=RootRequirementStatus.UNIDENTIFIABLE,
                )
            )
            continue

        name = normalize_distribution_name(requirement.name)
        extras = _extras(requirement.extras, "requirement extras")
        marker_state = _evaluate_marker(requirement, environment, extras)
        if marker_state is _MarkerState.INDETERMINATE:
            warnings.add(
                DependencyGraphWarning(
                    code=DependencyGraphWarningCode.ROOT_MARKER_INDETERMINATE,
                    target_kind=DependencyGraphWarningTargetKind.ROOT_INPUT,
                    target_identity=str(index),
                )
            )
            roots.append(
                RootRequirement(
                    input_index=index,
                    name=None,
                    status=RootRequirementStatus.UNIDENTIFIABLE,
                )
            )
        elif marker_state is _MarkerState.INACTIVE:
            roots.append(
                RootRequirement(
                    input_index=index,
                    name=name,
                    status=RootRequirementStatus.INACTIVE,
                    selected_extras=extras,
                )
            )
        elif name not in installed_versions:
            warnings.add(
                DependencyGraphWarning(
                    code=DependencyGraphWarningCode.ROOT_UNMATCHED,
                    target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                    target_identity=name,
                )
            )
            roots.append(
                RootRequirement(
                    input_index=index,
                    name=name,
                    status=RootRequirementStatus.UNMATCHED,
                    selected_extras=extras,
                )
            )
        elif requirement.url is None and not _matches_installed_version(
            requirement, installed_versions[name]
        ):
            warnings.add(
                DependencyGraphWarning(
                    code=DependencyGraphWarningCode.ROOT_VERSION_MISMATCH,
                    target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                    target_identity=name,
                )
            )
            roots.append(
                RootRequirement(
                    input_index=index,
                    name=name,
                    status=RootRequirementStatus.VERSION_MISMATCH,
                    selected_extras=extras,
                )
            )
        else:
            roots.append(
                RootRequirement(
                    input_index=index,
                    name=name,
                    status=RootRequirementStatus.RECOGNIZED,
                    selected_extras=extras,
                )
            )
    return tuple(roots)


def _classify_nodes(
    installed_versions: Mapping[str, str],
    edges: Iterable[DependencyEdge],
    roots: tuple[RootRequirement, ...],
) -> tuple[DependencyGraphNode, ...]:
    adjacency = {name: [] for name in installed_versions}
    for edge in edges:
        adjacency[edge.source_name].append(edge.target_name)
    for targets in adjacency.values():
        targets.sort()

    recognized = sorted(
        {
            root.name
            for root in roots
            if root.status is RootRequirementStatus.RECOGNIZED and root.name is not None
        }
    )
    roots_by_node: dict[str, set[str]] = {name: set() for name in installed_versions}
    distances: dict[str, int] = {}
    for root_name in recognized:
        queue = [(root_name, 0)]
        seen = {root_name}
        while queue:
            name, distance = queue.pop(0)
            roots_by_node[name].add(root_name)
            distances[name] = min(distances.get(name, distance), distance)
            for target in adjacency[name]:
                if target not in seen:
                    seen.add(target)
                    queue.append((target, distance + 1))

    nodes: list[DependencyGraphNode] = []
    root_set = set(recognized)
    for name in sorted(installed_versions):
        root_names = tuple(sorted(roots_by_node[name]))
        if name in root_set:
            kind = DependencyKind.ROOT
        elif not root_names:
            kind = DependencyKind.UNATTRIBUTED
        elif distances[name] == 1:
            kind = DependencyKind.DIRECT
        else:
            kind = DependencyKind.TRANSITIVE
        nodes.append(
            DependencyGraphNode(
                name=name,
                version=installed_versions[name],
                kind=kind,
                root_names=root_names,
                is_shared=len(root_names) >= 2,
            )
        )
    return tuple(nodes)


def _usable_metadata(
    installed_versions: Mapping[str, str],
    supplied_metadata: Mapping[str, InstalledDistributionMetadata],
    warnings: set[DependencyGraphWarning],
) -> dict[str, InstalledDistributionMetadata]:
    usable_metadata: dict[str, InstalledDistributionMetadata] = {}
    for name, version in installed_versions.items():
        value = supplied_metadata.get(name)
        if value is None:
            warnings.add(
                DependencyGraphWarning(
                    code=DependencyGraphWarningCode.MISSING_METADATA,
                    target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                    target_identity=name,
                )
            )
        elif value.version != version:
            warnings.add(
                DependencyGraphWarning(
                    code=DependencyGraphWarningCode.METADATA_VERSION_MISMATCH,
                    target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                    target_identity=name,
                )
            )
        else:
            usable_metadata[name] = value
    return usable_metadata


def _active_edges(
    *,
    installed_versions: Mapping[str, str],
    usable_metadata: Mapping[str, InstalledDistributionMetadata],
    selected_extras: dict[str, set[str]],
    marker_environment: MarkerEnvironment,
    warnings: set[DependencyGraphWarning],
) -> tuple[DependencyEdge, ...]:
    """Resolve active metadata edges until requested extras stop expanding."""

    requested_extras_by_endpoints: dict[tuple[str, str], set[str]] = {}
    changed = True
    while changed:
        changed = False
        for source_name in sorted(usable_metadata):
            source_extras = tuple(sorted(selected_extras[source_name]))
            for raw_requirement in usable_metadata[source_name].requires_dist:
                requirement = _parse_requirement(raw_requirement)
                if requirement is None:
                    warnings.add(
                        DependencyGraphWarning(
                            code=DependencyGraphWarningCode.INVALID_REQUIRES_DIST,
                            target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                            target_identity=source_name,
                        )
                    )
                    continue
                marker_state = _evaluate_marker(
                    requirement, marker_environment, source_extras
                )
                if marker_state is _MarkerState.INDETERMINATE:
                    warnings.add(
                        DependencyGraphWarning(
                            code=DependencyGraphWarningCode.MARKER_INDETERMINATE,
                            target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                            target_identity=source_name,
                        )
                    )
                    continue
                if marker_state is _MarkerState.INACTIVE:
                    continue

                target_name = normalize_distribution_name(requirement.name)
                if target_name not in installed_versions:
                    warnings.add(
                        DependencyGraphWarning(
                            code=DependencyGraphWarningCode.MISSING_DEPENDENCY_TARGET,
                            target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                            target_identity=target_name,
                        )
                    )
                    continue
                requested_extras = _extras(requirement.extras, "requirement extras")
                requested_extras_by_endpoints.setdefault(
                    (source_name, target_name), set()
                ).update(requested_extras)
                before = len(selected_extras[target_name])
                selected_extras[target_name].update(requested_extras)
                changed = changed or len(selected_extras[target_name]) != before
    return tuple(
        DependencyEdge(
            source_name=source_name,
            target_name=target_name,
            requested_extras=tuple(sorted(requested_extras)),
        )
        for (source_name, target_name), requested_extras in sorted(
            requested_extras_by_endpoints.items()
        )
    )


def build_dependency_graph(
    analysis: AnalysisResult,
    metadata: Iterable[InstalledDistributionMetadata],
    marker_environment: MarkerEnvironment,
) -> DependencyGraph:
    """Build a deterministic dependency graph from supplied installed metadata.

    Invalid Core Metadata and missing installed targets are represented by safe
    typed warnings.  The raw metadata value, direct-reference URL, marker, and
    parser diagnostic are intentionally never retained in the returned graph.
    """

    if not isinstance(analysis, AnalysisResult):
        raise TypeError("analysis must be an AnalysisResult")
    if not isinstance(marker_environment, MarkerEnvironment):
        raise TypeError("marker_environment must be a MarkerEnvironment")

    installed_versions = {
        distribution.name: distribution.version
        for distribution in analysis.distributions
    }
    warnings: set[DependencyGraphWarning] = set()
    usable_metadata = _usable_metadata(
        installed_versions,
        _metadata_by_name(metadata),
        warnings,
    )

    roots = _root_requirements(
        analysis, installed_versions, marker_environment, warnings
    )
    selected_extras: dict[str, set[str]] = {name: set() for name in installed_versions}
    for root in roots:
        if root.status is RootRequirementStatus.RECOGNIZED and root.name is not None:
            selected_extras[root.name].update(root.selected_extras)

    edges = _active_edges(
        installed_versions=installed_versions,
        usable_metadata=usable_metadata,
        selected_extras=selected_extras,
        marker_environment=marker_environment,
        warnings=warnings,
    )

    return DependencyGraph(
        roots=roots,
        nodes=_classify_nodes(installed_versions, edges, roots),
        edges=tuple(edges),
        warnings=tuple(warnings),
    )
