"""Opt-in, pure text presentation for dependency-path explanations.

The module only formats :class:`ExplainedAnalysisResult`.  It deliberately
does not construct graphs, read metadata, or map adapter failures to CLI
errors; those boundaries remain available to a later CLI integration task.
"""

from collections import Counter

from uv_packsize.dependency_graph import DependencyGraphCompleteness
from uv_packsize.dependency_paths import ExplainedAnalysisResult
from uv_packsize.render import render_analysis_report


def render_explained_analysis_report(
    result: ExplainedAnalysisResult,
    *,
    show_scripts: bool = False,
) -> str:
    """Return the ordinary report followed by deterministic explanations.

    The ordinary report is deliberately rendered first and unchanged.  This
    makes the default text contract reusable as an exact prefix while keeping
    explanations opt-in at the future CLI boundary.
    """

    if not isinstance(result, ExplainedAnalysisResult):
        raise TypeError("result must be an ExplainedAnalysisResult")
    if not isinstance(show_scripts, bool):
        raise TypeError("show_scripts must be a bool")

    prefix = render_analysis_report(result.analysis, show_scripts=show_scripts)
    return "\n\n".join((prefix, *render_explanation_sections(result)))


def render_explanation_sections(
    result: ExplainedAnalysisResult,
    *,
    include_graph_warning_summary: bool = True,
) -> tuple[str, ...]:
    """Return deterministic explanation-only sections for report composition.

    A compositor that emits another graph-derived section can suppress the
    shared, sanitized warning summary while preserving all explanation data.
    """

    if not isinstance(result, ExplainedAnalysisResult):
        raise TypeError("result must be an ExplainedAnalysisResult")
    if not isinstance(include_graph_warning_summary, bool):
        raise TypeError("include_graph_warning_summary must be a bool")
    sections = (
        _render_requested_roots(result),
        _render_dependency_attribution(result),
        _render_dependency_paths(result),
    )
    if (
        include_graph_warning_summary
        and result.graph.completeness is DependencyGraphCompleteness.INCOMPLETE
    ):
        sections = (*sections, _render_graph_warning_summary(result))
    return sections


def _render_requested_roots(result: ExplainedAnalysisResult) -> str:
    lines = ["--- Requested Roots ---", "Input  Distribution  Status"]
    for root in result.graph.roots:
        name = root.name if root.name is not None else "-"
        lines.append(f"{root.input_index + 1}  {name}  {root.status.value}")
    if len(lines) == 2:
        lines.append("No requested roots.")
    return "\n".join(lines)


def _render_dependency_attribution(result: ExplainedAnalysisResult) -> str:
    lines = [
        "--- Dependency Attribution ---",
        "Distribution  Version  Kind  Shared  Reachable Roots",
    ]
    for attribution in result.attributions:
        node = attribution.node
        roots = ", ".join(node.root_names) or "-"
        lines.append(
            f"{node.name}  {node.version}  {node.kind.value}  "
            f"{'yes' if node.is_shared else 'no'}  {roots}"
        )
    if len(lines) == 2:
        lines.append("No installed distributions.")
    return "\n".join(lines)


def _render_dependency_paths(result: ExplainedAnalysisResult) -> str:
    lines = ["--- Dependency Paths ---", "Input  Path"]
    paths = sorted(
        (
            path
            for attribution in result.attributions
            for path in attribution.paths
            if path.edge_count > 0
        ),
        key=lambda path: (path.root_input_index, path.edge_count, path.nodes),
    )
    for path in paths:
        lines.append(f"{path.root_input_index + 1}  {' -> '.join(path.nodes)}")
    if len(lines) == 2:
        lines.append("No dependency paths.")
    return "\n".join(lines)


def _render_graph_warning_summary(result: ExplainedAnalysisResult) -> str:
    counts = Counter(warning.code.value for warning in result.graph.warnings)
    summary = "; ".join(f"{code}: {counts[code]}" for code in sorted(counts))
    return f"Warning: incomplete dependency graph ({summary})."
