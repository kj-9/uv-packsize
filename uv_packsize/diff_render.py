"""Pure, safe text presentation for completed baseline comparisons."""

from __future__ import annotations

from uv_packsize.diff import (
    MAX_BASELINE_INTEGER,
    AnalysisDiff,
    DistributionChangeKind,
    DistributionDelta,
)
from uv_packsize.models import Completeness
from uv_packsize.render import format_size
from uv_packsize.text_render import render_table, safe_display


def format_signed_size(delta: int) -> str:
    """Format a bounded signed byte delta without changing ``format_size``."""

    if isinstance(delta, bool) or not isinstance(delta, int):
        raise TypeError("delta must be an int")
    if not -MAX_BASELINE_INTEGER <= delta <= MAX_BASELINE_INTEGER:
        raise ValueError("delta must be within the signed diff range")
    if delta == 0:
        return "0 B"
    return ("+" if delta > 0 else "-") + format_size(abs(delta))


def render_diff_report(diff: AnalysisDiff) -> str:
    """Return a deterministic report for an already compatible ``AnalysisDiff``."""

    if not isinstance(diff, AnalysisDiff):
        raise TypeError("diff must be an AnalysisDiff")
    return "\n\n".join(render_diff_sections(diff))


def render_diff_sections(diff: AnalysisDiff) -> tuple[str, ...]:
    """Return deterministic comparison-only report sections.

    The comparison and its baselines have already been validated by
    :func:`compare_baselines`; this module deliberately performs neither I/O
    nor compatibility policy.
    """

    if not isinstance(diff, AnalysisDiff):
        raise TypeError("diff must be an AnalysisDiff")

    sections = [_render_size_comparison(diff)]
    if diff.completeness is Completeness.INCOMPLETE:
        sections.append(_render_incomplete_note(diff))
    sections.extend(_render_distribution_sections(diff))
    if diff.distribution_logical_bytes_delta != diff.global_logical_bytes_delta:
        sections.append(_render_nonreconciliation_note(diff))
    return tuple(sections)


def _render_size_comparison(diff: AnalysisDiff) -> str:
    rows = (
        (
            "Global logical size",
            format_size(diff.baseline.global_logical_bytes),
            format_size(diff.current.global_logical_bytes),
            format_signed_size(diff.global_logical_bytes_delta),
        ),
        (
            "Distribution-owned aggregate",
            format_size(
                sum(item.baseline_logical_bytes for item in diff.distributions)
            ),
            format_size(sum(item.current_logical_bytes for item in diff.distributions)),
            format_signed_size(diff.distribution_logical_bytes_delta),
        ),
    )
    return "\n".join(
        (
            "--- Size Comparison ---",
            *_render_table(
                ("Metric", "Baseline", "Current", "Change"), rows, (1, 2, 3)
            ),
        )
    )


def _render_distribution_sections(diff: AnalysisDiff) -> tuple[str, ...]:
    added = []
    removed = []
    changed = []
    for item in diff.distributions:
        if item.kind is DistributionChangeKind.ADDED:
            assert item.current_distribution is not None
            added.append(
                (
                    _safe_text(item.name),
                    _safe_text(item.current_distribution.version),
                    format_size(item.current_logical_bytes),
                )
            )
        elif item.kind is DistributionChangeKind.REMOVED:
            assert item.baseline_distribution is not None
            removed.append(
                (
                    _safe_text(item.name),
                    _safe_text(item.baseline_distribution.version),
                    format_size(item.baseline_logical_bytes),
                )
            )
        elif (
            item.kind is DistributionChangeKind.VERSION_CHANGED
            or item.logical_bytes_delta
        ):
            assert item.baseline_distribution is not None
            assert item.current_distribution is not None
            changed.append(
                (
                    _safe_text(item.name),
                    _safe_text(item.baseline_distribution.version),
                    _safe_text(item.current_distribution.version),
                    format_size(item.baseline_logical_bytes),
                    format_size(item.current_logical_bytes),
                    _change_type(item),
                    format_signed_size(item.logical_bytes_delta),
                )
            )
    if not (added or removed or changed):
        return ("--- Distribution Changes ---\nNo distribution changes.",)

    sections = []
    if added:
        sections.append(
            "\n".join(
                (
                    "--- Added Distributions ---",
                    *_render_table(
                        ("Name", "Version", "Current size"), tuple(added), (2,)
                    ),
                )
            )
        )
    if removed:
        sections.append(
            "\n".join(
                (
                    "--- Removed Distributions ---",
                    *_render_table(
                        ("Name", "Version", "Baseline size"), tuple(removed), (2,)
                    ),
                )
            )
        )
    if changed:
        sections.append(
            "\n".join(
                (
                    "--- Changed Distributions ---",
                    *_render_table(
                        (
                            "Name",
                            "Baseline version",
                            "Current version",
                            "Baseline size",
                            "Current size",
                            "Change type",
                            "Change",
                        ),
                        tuple(changed),
                        (3, 4, 6),
                    ),
                )
            )
        )
    return tuple(sections)


def _render_incomplete_note(diff: AnalysisDiff) -> str:
    return (
        "Warning: incomplete comparison; deltas may be partial "
        f"(baseline: {_warning_counts(diff.baseline.warnings.warning_code_counts)}; "
        f"current: {_warning_counts(diff.current.warnings.warning_code_counts)})."
    )


def _warning_counts(counts: tuple[tuple[str, int], ...]) -> str:
    return ", ".join(f"{code}: {count}" for code, count in counts) or "none"


def _render_nonreconciliation_note(diff: AnalysisDiff) -> str:
    return (
        "Note: distribution-owned aggregate change "
        f"{format_signed_size(diff.distribution_logical_bytes_delta)} does not "
        "reconcile with global logical size change "
        f"{format_signed_size(diff.global_logical_bytes_delta)} because distribution "
        "totals may count duplicate-owned files; global counts canonical identity once."
    )


def _safe_text(value: str) -> str:
    """Backward-compatible private alias for the shared display primitive."""

    return safe_display(value)


def _change_type(item: DistributionDelta) -> str:
    """Classify the displayed delta without exposing ``UNCHANGED`` as a change."""

    version_changed = item.kind is DistributionChangeKind.VERSION_CHANGED
    size_changed = item.logical_bytes_delta != 0
    if version_changed and size_changed:
        return "version+size"
    if version_changed:
        return "version"
    assert size_changed
    return "size"


def _render_table(
    header: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    right_align_indexes: tuple[int, ...],
) -> tuple[str, ...]:
    return render_table(header, rows, right_align_indexes)
