"""Pure, immutable dependency-path explanations for an installed graph.

The graph builder owns Core Metadata interpretation.  This module only checks
that such a graph still agrees with an :class:`AnalysisResult`, then derives
per-input reachability and deterministic shortest paths.  It has no renderer,
filesystem, subprocess, or byte-attribution responsibilities.
"""

from collections import deque
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement

from uv_packsize.dependency_graph import (
    DependencyGraph,
    DependencyGraphCompleteness,
    DependencyGraphNode,
    DependencyKind,
    RootRequirementStatus,
)
from uv_packsize.models import AnalysisResult, Completeness, normalize_distribution_name


def _input_indexes(values: tuple[int, ...]) -> tuple[int, ...]:
    if isinstance(values, str):
        raise TypeError("root_input_indexes must be a tuple of integers")
    indexes = tuple(values)
    if any(
        not isinstance(index, int) or isinstance(index, bool) or index < 0
        for index in indexes
    ):
        raise ValueError("root_input_indexes must contain non-negative integers")
    if len(indexes) != len(set(indexes)):
        raise ValueError("root_input_indexes must not contain duplicates")
    return tuple(sorted(indexes))


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyPath:
    """One simple path from a recognized root input to an installed node."""

    root_input_index: int
    nodes: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.root_input_index, int)
            or isinstance(self.root_input_index, bool)
            or self.root_input_index < 0
        ):
            raise ValueError("root_input_index must be a non-negative integer")
        if isinstance(self.nodes, str):
            raise TypeError("nodes must be a tuple of distribution names")
        nodes = tuple(normalize_distribution_name(node) for node in self.nodes)
        if not nodes:
            raise ValueError("nodes must not be empty")
        if len(nodes) != len(set(nodes)):
            raise ValueError("nodes must be a simple path")
        object.__setattr__(self, "nodes", nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of dependency edges in the path."""

        return len(self.nodes) - 1


@dataclass(frozen=True, slots=True, kw_only=True)
class DistributionAttribution:
    """One graph node with root-input reachability and deterministic paths."""

    node: DependencyGraphNode
    root_input_indexes: tuple[int, ...]
    canonical_path: DependencyPath | None
    paths: tuple[DependencyPath, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node, DependencyGraphNode):
            raise TypeError("node must be a DependencyGraphNode")
        indexes = _input_indexes(self.root_input_indexes)
        object.__setattr__(self, "root_input_indexes", indexes)
        if self.canonical_path is not None and not isinstance(
            self.canonical_path, DependencyPath
        ):
            raise TypeError("canonical_path must be a DependencyPath or None")
        paths = tuple(self.paths)
        if any(not isinstance(path, DependencyPath) for path in paths):
            raise TypeError("paths must contain DependencyPath values")
        # Retain a small constructor compatibility boundary for callers that
        # used the P3-02a canonical-path-only model.  An explained result still
        # verifies the complete set of root paths against the graph below.
        if not paths and self.canonical_path is not None:
            paths = (self.canonical_path,)
        if len(paths) != len(set(paths)):
            raise ValueError("paths must not contain duplicates")
        paths = tuple(sorted(paths, key=_path_key))
        if bool(indexes) != bool(paths):
            raise ValueError("paths must exist exactly when roots reach a node")
        if indexes != tuple(sorted({path.root_input_index for path in paths})):
            raise ValueError("paths must match reachable root input indexes")
        if len(paths) != len(indexes):
            raise ValueError("paths must contain one path per reachable root input")
        if any(path.nodes[-1] != self.node.name for path in paths):
            raise ValueError("paths must terminate at the attributed node")
        expected_canonical = min(paths, key=_path_key) if paths else None
        if self.canonical_path != expected_canonical:
            raise ValueError("canonical_path must be the deterministic first path")
        object.__setattr__(self, "paths", paths)


def _path_key(path: DependencyPath) -> tuple[int, int, tuple[str, ...]]:
    return (path.edge_count, path.root_input_index, path.nodes)


def _shortest_paths(
    root_input_index: int,
    root_name: str,
    adjacency: dict[str, tuple[str, ...]],
) -> dict[str, DependencyPath]:
    """Find lexical, simple shortest paths from one root with BFS."""

    paths = {
        root_name: DependencyPath(root_input_index=root_input_index, nodes=(root_name,))
    }
    queue = deque([paths[root_name]])
    while queue:
        path = queue.popleft()
        for target_name in adjacency[path.nodes[-1]]:
            if target_name in paths:
                continue
            target_path = DependencyPath(
                root_input_index=root_input_index,
                nodes=(*path.nodes, target_name),
            )
            paths[target_name] = target_path
            queue.append(target_path)
    return paths


def _matching_graph_nodes(
    analysis: AnalysisResult, graph: DependencyGraph
) -> dict[str, DependencyGraphNode]:
    analysis_versions = {
        distribution.name: distribution.version
        for distribution in analysis.distributions
    }
    graph_nodes = {node.name: node for node in graph.nodes}
    graph_versions = {name: node.version for name, node in graph_nodes.items()}
    if analysis_versions != graph_versions:
        raise ValueError("analysis distributions and dependency graph nodes must match")
    return graph_nodes


def _recognized_roots(
    analysis: AnalysisResult,
    graph: DependencyGraph,
    nodes: dict[str, DependencyGraphNode],
) -> tuple[tuple[int, str], ...]:
    expected_indexes = tuple(range(len(analysis.context.requirements)))
    if tuple(root.input_index for root in graph.roots) != expected_indexes:
        raise ValueError("dependency graph roots must match analysis input indexes")
    recognized = tuple(
        (root.input_index, root.name)
        for root in graph.roots
        if root.status is RootRequirementStatus.RECOGNIZED
    )
    if any(name is None or name not in nodes for _, name in recognized):
        raise ValueError("recognized dependency graph roots must be installed nodes")
    named_roots = tuple((index, name) for index, name in recognized if name is not None)
    for input_index, name in named_roots:
        try:
            requirement_name = normalize_distribution_name(
                Requirement(analysis.context.requirements[input_index]).name
            )
        except (InvalidRequirement, ValueError):
            raise ValueError(
                "recognized dependency graph roots must match analysis inputs"
            ) from None
        if name != requirement_name:
            raise ValueError(
                "recognized dependency graph roots must match analysis inputs"
            )
    return named_roots


def _adjacency(
    graph: DependencyGraph, nodes: dict[str, DependencyGraphNode]
) -> dict[str, tuple[str, ...]]:
    adjacency_lists = {name: [] for name in nodes}
    for edge in graph.edges:
        if edge.source_name not in nodes or edge.target_name not in nodes:
            raise ValueError("dependency graph edges must connect installed nodes")
        adjacency_lists[edge.source_name].append(edge.target_name)
    return {
        name: tuple(sorted(set(targets))) for name, targets in adjacency_lists.items()
    }


def _validate_node_attribution(
    nodes: dict[str, DependencyGraphNode],
    adjacency: dict[str, tuple[str, ...]],
    roots: tuple[tuple[int, str], ...],
) -> None:
    reached_by_name: dict[str, set[str]] = {name: set() for name in nodes}
    distances: dict[str, int] = {}
    for root_input_index, root_name in roots:
        for name, path in _shortest_paths(
            root_input_index, root_name, adjacency
        ).items():
            reached_by_name[name].add(root_name)
            distances[name] = min(distances.get(name, path.edge_count), path.edge_count)

    recognized_names = {name for _, name in roots}
    for name, node in nodes.items():
        root_names = tuple(sorted(reached_by_name[name]))
        kind = (
            DependencyKind.ROOT
            if name in recognized_names
            else DependencyKind.UNATTRIBUTED
            if not root_names
            else DependencyKind.DIRECT
            if distances[name] == 1
            else DependencyKind.TRANSITIVE
        )
        if (
            node.root_names != root_names
            or node.is_shared != (len(root_names) >= 2)
            or node.kind is not kind
        ):
            raise ValueError("dependency graph node attribution is inconsistent")


def _validated_graph(
    analysis: AnalysisResult,
    graph: DependencyGraph,
) -> tuple[dict[str, DependencyGraphNode], dict[str, tuple[str, ...]]]:
    """Validate graph/model agreement and return deterministic adjacency."""

    if not isinstance(analysis, AnalysisResult):
        raise TypeError("analysis must be an AnalysisResult")
    if not isinstance(graph, DependencyGraph):
        raise TypeError("graph must be a DependencyGraph")

    graph_nodes = _matching_graph_nodes(analysis, graph)
    roots = _recognized_roots(analysis, graph, graph_nodes)
    adjacency = _adjacency(graph, graph_nodes)
    _validate_node_attribution(graph_nodes, adjacency, roots)
    return graph_nodes, adjacency


def _derived_attributions(
    analysis: AnalysisResult,
    graph: DependencyGraph,
) -> tuple[DistributionAttribution, ...]:
    nodes, adjacency = _validated_graph(analysis, graph)
    paths_by_node: dict[str, list[DependencyPath]] = {name: [] for name in nodes}
    for root in graph.roots:
        if root.status is not RootRequirementStatus.RECOGNIZED:
            continue
        assert root.name is not None
        for name, path in _shortest_paths(
            root.input_index, root.name, adjacency
        ).items():
            paths_by_node[name].append(path)

    return tuple(
        DistributionAttribution(
            node=node,
            root_input_indexes=tuple(
                sorted({path.root_input_index for path in paths_by_node[name]})
            ),
            canonical_path=(
                min(paths_by_node[name], key=_path_key) if paths_by_node[name] else None
            ),
            paths=tuple(sorted(paths_by_node[name], key=_path_key)),
        )
        for name, node in sorted(nodes.items())
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExplainedAnalysisResult:
    """Analysis plus graph explanations, without changing either source model."""

    analysis: AnalysisResult
    graph: DependencyGraph
    attributions: tuple[DistributionAttribution, ...]

    def __post_init__(self) -> None:
        expected = _derived_attributions(self.analysis, self.graph)
        attributions = tuple(self.attributions)
        if any(
            not isinstance(attribution, DistributionAttribution)
            for attribution in attributions
        ):
            raise TypeError("attributions must contain DistributionAttribution values")
        if attributions != expected:
            raise ValueError("dependency path attributions are inconsistent with graph")
        object.__setattr__(self, "attributions", expected)

    @property
    def inventory_completeness(self) -> Completeness:
        """Completeness of measured file inventory, independent of graph data."""

        return self.analysis.completeness

    @property
    def graph_completeness(self) -> DependencyGraphCompleteness:
        """Completeness of installed-metadata dependency attribution."""

        return self.graph.completeness

    @property
    def completeness(self) -> Completeness:
        """Combined completeness without conflating its two component states."""

        if (
            self.inventory_completeness is Completeness.INCOMPLETE
            or self.graph_completeness is DependencyGraphCompleteness.INCOMPLETE
        ):
            return Completeness.INCOMPLETE
        return Completeness.COMPLETE


def explain_dependency_paths(
    analysis: AnalysisResult,
    graph: DependencyGraph,
) -> ExplainedAnalysisResult:
    """Compose validated per-input dependency paths with no byte attribution."""

    return ExplainedAnalysisResult(
        analysis=analysis,
        graph=graph,
        attributions=_derived_attributions(analysis, graph),
    )
