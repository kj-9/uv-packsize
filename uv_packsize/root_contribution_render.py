"""Pure text presentation for non-split requested-root contributions.

The module formats an already-derived :class:`RootContributionResult` only.
It deliberately leaves graph construction, inventory collection, and public
CLI/JSON choices to higher layers.  Its section API lets future report
compositors render the ordinary analysis report once and suppress a duplicate
safe graph-warning summary.
"""

from collections import Counter

from uv_packsize.dependency_graph import DependencyGraphCompleteness
from uv_packsize.models import Completeness
from uv_packsize.render import format_size, render_analysis_report
from uv_packsize.root_contributions import RootContributionResult
from uv_packsize.text_render import render_table, safe_display


def render_root_contribution_report(
    result: RootContributionResult,
    *,
    show_scripts: bool = False,
) -> str:
    """Return the ordinary report followed by root-contribution sections.

    ``show_scripts`` is passed solely to the ordinary report renderer.  Root
    contribution totals always remain global-inventory totals.
    """

    _validate_inputs(result, show_scripts)
    prefix = render_analysis_report(result.analysis, show_scripts=show_scripts)
    return "\n\n".join((prefix, *render_root_contribution_sections(result)))


def render_root_contribution_sections(
    result: RootContributionResult,
    *,
    include_graph_warning_summary: bool = True,
) -> tuple[str, ...]:
    """Return deterministic root-contribution-only sections.

    When the graph is incomplete, no contribution numbers are rendered.  The
    optional warning summary contains only warning code/count pairs, so a
    compositor can suppress it after emitting the same safe summary elsewhere.
    """

    if not isinstance(result, RootContributionResult):
        raise TypeError("result must be a RootContributionResult")
    if not isinstance(include_graph_warning_summary, bool):
        raise TypeError("include_graph_warning_summary must be a bool")

    if result.graph_completeness is DependencyGraphCompleteness.INCOMPLETE:
        unavailable = _render_unavailable_sections(
            result,
            include_graph_warning_summary=include_graph_warning_summary,
        )
        return unavailable

    # RootContributionResult validates this availability invariant.
    assert result.roots is not None
    assert result.root_set_totals is not None
    sections = [
        _render_root_contributions(result),
        _render_shared_root_sets(result),
        _render_reconciliation(result),
    ]
    if result.inventory_completeness is Completeness.INCOMPLETE:
        sections.append(
            "Note: incomplete inventory; contribution values are measured partial bytes."
        )
    return tuple(sections)


def _validate_inputs(result: RootContributionResult, show_scripts: bool) -> None:
    if not isinstance(result, RootContributionResult):
        raise TypeError("result must be a RootContributionResult")
    if not isinstance(show_scripts, bool):
        raise TypeError("show_scripts must be a bool")


def _render_unavailable_sections(
    result: RootContributionResult,
    *,
    include_graph_warning_summary: bool,
) -> tuple[str, ...]:
    first_lines = [
        "--- Root Contributions ---",
        "Unavailable: incomplete dependency graph.",
    ]
    if include_graph_warning_summary:
        first_lines.append(_render_graph_warning_summary(result))
    return (
        "\n".join(first_lines),
        "--- Shared Root-Set Bytes ---\nUnavailable: incomplete dependency graph.",
        "--- Contribution Reconciliation ---\nUnavailable: incomplete dependency graph.",
    )


def _render_root_contributions(result: RootContributionResult) -> str:
    assert result.roots is not None
    rows = tuple(
        (
            _safe_text(root.root_name),
            ", ".join(str(index + 1) for index in root.root_input_indexes) or "-",
            root.exclusive.logical_bytes,
            root.shared.logical_bytes,
            root.closure.logical_bytes,
        )
        for root in sorted(result.roots, key=lambda root: root.root_name)
    )
    lines = ["--- Root Contributions ---"]
    if not rows:
        lines.append("No recognized requested roots.")
    else:
        lines.extend(
            _render_table(
                header=("Root", "Input indices", "Exclusive", "Shared", "Closure"),
                rows=tuple(
                    (
                        root_name,
                        input_indexes,
                        format_size(exclusive),
                        format_size(shared),
                        format_size(closure),
                    )
                    for root_name, input_indexes, exclusive, shared, closure in rows
                ),
                right_align_indexes=(2, 3, 4),
            )
        )
    lines.append(
        "Note: Closure = Exclusive + Shared for one root; closures must not be summed across roots."
    )
    return "\n".join(lines)


def _render_shared_root_sets(result: RootContributionResult) -> str:
    assert result.root_set_totals is not None
    buckets = tuple(
        bucket for bucket in result.root_set_totals if len(bucket.root_names) >= 2
    )
    lines = ["--- Shared Root-Set Bytes ---"]
    if not buckets:
        lines.extend(
            ("No shared root-set buckets.", "Total shared root-set bytes  0 B")
        )
        return "\n".join(lines)
    rows = tuple(
        (
            ", ".join(_safe_text(name) for name in bucket.root_names),
            format_size(bucket.logical_bytes),
        )
        for bucket in buckets
    )
    lines.extend(
        _render_table(
            header=("Exact root set", "Size"), rows=rows, right_align_indexes=(1,)
        )
    )
    lines.append(
        "Total shared root-set bytes  "
        + format_size(sum(bucket.logical_bytes for bucket in buckets))
    )
    return "\n".join(lines)


def _render_reconciliation(result: RootContributionResult) -> str:
    assert result.root_set_totals is not None
    exclusive = sum(
        bucket.logical_bytes
        for bucket in result.root_set_totals
        if len(bucket.root_names) == 1
    )
    shared = sum(
        bucket.logical_bytes
        for bucket in result.root_set_totals
        if len(bucket.root_names) >= 2
    )
    unattributed = sum(
        bucket.logical_bytes
        for bucket in result.root_set_totals
        if not bucket.root_names
    )
    lines = ["--- Contribution Reconciliation ---"]
    lines.extend(
        _render_table(
            header=("Component", "Size"),
            rows=(
                ("Exclusive root-set bytes", format_size(exclusive)),
                ("Shared root-set bytes", format_size(shared)),
                ("Unattributed bytes", format_size(unattributed)),
                ("Global total", format_size(result.footprint.logical_bytes)),
            ),
            right_align_indexes=(1,),
        )
    )
    lines.append("Exclusive + Shared + Unattributed = Global total.")
    return "\n".join(lines)


def _render_graph_warning_summary(result: RootContributionResult) -> str:
    counts = Counter(warning.code.value for warning in result.explained.graph.warnings)
    summary = "; ".join(f"{code}: {counts[code]}" for code in sorted(counts))
    return f"Warning: incomplete dependency graph ({summary})."


def _safe_text(value: str) -> str:
    """Backward-compatible private alias for the shared display primitive."""

    return safe_display(value)


def _render_table(
    *,
    header: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    right_align_indexes: tuple[int, ...],
) -> tuple[str, ...]:
    """Render preformatted strings with shared validation and safe display."""

    return render_table(header, rows, right_align_indexes)
