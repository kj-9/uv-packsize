"""Pure text presentation for global footprint aggregates.

This module deliberately renders only an already-derived
:class:`~uv_packsize.footprint.FootprintResult`.  It does not build an
inventory or dependency graph, and it does not decide which public CLI option
enables the presentation.  Keeping the sections separate also lets a future
opt-in report compose them with other explanation sections without duplicating
the dependency-graph warning summary.
"""

from collections import Counter

from uv_packsize.dependency_graph import DependencyGraphCompleteness
from uv_packsize.footprint import FootprintResult
from uv_packsize.render import format_size, render_analysis_report


def render_footprint_report(
    result: FootprintResult,
    *,
    show_scripts: bool = False,
) -> str:
    """Return the ordinary report followed by global footprint sections.

    The ordinary report is rendered unchanged first, so callers can treat it
    as a byte-identical prefix.  ``show_scripts`` remains a presentation-only
    option: it affects that prefix but never any globally-deduplicated
    footprint total.
    """

    _validate_inputs(result, show_scripts)
    prefix = render_analysis_report(result.analysis, show_scripts=show_scripts)
    sections = render_footprint_sections(result)
    return "\n\n".join((prefix, *sections))


def render_footprint_sections(
    result: FootprintResult,
    *,
    include_graph_warning_summary: bool = True,
) -> tuple[str, ...]:
    """Return deterministic footprint-only sections for report composition.

    ``include_graph_warning_summary`` controls only the safe graph-warning
    summary emitted when attribution is unavailable.  A compositor that
    already renders the same graph warning can set it to ``False`` to avoid a
    duplicate warning while retaining the availability statement.
    """

    if not isinstance(result, FootprintResult):
        raise TypeError("result must be a FootprintResult")
    if not isinstance(include_graph_warning_summary, bool):
        raise TypeError("include_graph_warning_summary must be a bool")

    sections = [_render_category_breakdown(result)]
    sections.append(
        _render_dependency_size_attribution(
            result,
            include_graph_warning_summary=include_graph_warning_summary,
        )
    )
    return tuple(sections)


def _validate_inputs(result: FootprintResult, show_scripts: bool) -> None:
    if not isinstance(result, FootprintResult):
        raise TypeError("result must be a FootprintResult")
    if not isinstance(show_scripts, bool):
        raise TypeError("show_scripts must be a bool")


def _render_category_breakdown(result: FootprintResult) -> str:
    return _render_total_table(
        title="File Category Breakdown",
        header_title="Category",
        rows=tuple(
            (total.category.value, total.logical_bytes)
            for total in result.category_totals
        ),
        footer_title="Total size",
        footer_value=result.logical_bytes,
    )


def _render_dependency_size_attribution(
    result: FootprintResult,
    *,
    include_graph_warning_summary: bool,
) -> str:
    if result.graph_completeness is DependencyGraphCompleteness.INCOMPLETE:
        lines = [
            "--- Dependency Size Attribution ---",
            "Unavailable: incomplete dependency graph.",
        ]
        if include_graph_warning_summary:
            lines.append(_render_graph_warning_summary(result))
        return "\n".join(lines)

    # FootprintResult validates this availability invariant at construction.
    assert result.role_totals is not None
    return _render_total_table(
        title="Dependency Size Attribution",
        header_title="Role",
        rows=tuple(
            (total.role.value, total.logical_bytes) for total in result.role_totals
        ),
        footer_title="Total size",
        footer_value=result.logical_bytes,
    )


def _render_graph_warning_summary(result: FootprintResult) -> str:
    counts = Counter(warning.code.value for warning in result.explained.graph.warnings)
    summary = "; ".join(f"{code}: {counts[code]}" for code in sorted(counts))
    return f"Warning: incomplete dependency graph ({summary})."


def _render_total_table(
    *,
    title: str,
    header_title: str,
    rows: tuple[tuple[str, int], ...],
    footer_title: str,
    footer_value: int,
) -> str:
    """Render a non-empty deterministic total table using shared size units."""

    name_width = max(
        len(header_title), len(footer_title), *(len(name) for name, _ in rows)
    )
    size_width = max(
        len("Size"),
        len(format_size(footer_value)),
        *(len(format_size(size)) for _name, size in rows),
    )
    separator = f"{'-' * name_width}  {'-' * size_width}"
    lines = [
        f"--- {title} ---",
        f"{header_title.ljust(name_width)}  {'Size'.rjust(size_width)}",
        separator,
        *(
            f"{name.ljust(name_width)}  {format_size(size).rjust(size_width)}"
            for name, size in rows
        ),
        separator,
        f"{footer_title.ljust(name_width)}  {format_size(footer_value).rjust(size_width)}",
    ]
    return "\n".join(lines)
