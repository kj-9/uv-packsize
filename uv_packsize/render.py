"""Deterministic text rendering for immutable analysis results.

The renderer deliberately has no knowledge of installation progress, Click, or
the filesystem.  It only formats the inventory already retained by an
``AnalysisResult``.
"""

from collections import Counter

from uv_packsize.models import AnalysisResult, Completeness, FileCategory, FileEntry
from uv_packsize.text_render import render_total_table

_VENV_BINARIES_TITLE = "Binaries in .venv/bin"
_PREFIX_BINARIES_TITLE = "Binaries in prefix"
_ALLOWED_BINARIES_TITLES = frozenset({_VENV_BINARIES_TITLE, _PREFIX_BINARIES_TITLE})


def format_size(logical_bytes: int) -> str:
    """Format non-negative logical bytes using binary size units."""

    if not isinstance(logical_bytes, int) or isinstance(logical_bytes, bool):
        raise TypeError("logical_bytes must be an int")
    if logical_bytes < 0:
        raise ValueError("logical_bytes must be non-negative")
    if logical_bytes == 0:
        return "0 B"
    if logical_bytes < 1024:
        return f"{logical_bytes} B"
    if logical_bytes < 1024**2:
        return f"{logical_bytes / 1024:.2f} KiB"
    if logical_bytes < 1024**3:
        return f"{logical_bytes / 1024**2:.2f} MiB"
    return f"{logical_bytes / 1024**3:.2f} GiB"


def render_analysis_report(
    result: AnalysisResult,
    *,
    show_scripts: bool = False,
    binaries_title: str = _VENV_BINARIES_TITLE,
) -> str:
    """Return the complete stable text report for an analysis result.

    ``show_scripts`` changes presentation only.  The final total always comes
    from the canonical-deduplicated global inventory held by ``result``.
    """

    if not isinstance(result, AnalysisResult):
        raise TypeError("result must be an AnalysisResult")
    if not isinstance(show_scripts, bool):
        raise TypeError("show_scripts must be a bool")
    if not isinstance(binaries_title, str):
        raise TypeError("binaries_title must be a str")
    if binaries_title not in _ALLOWED_BINARIES_TITLES:
        raise ValueError("binaries_title must be a supported stable title")

    package_rows = _distribution_rows(result, exclude_scripts=show_scripts)
    package_row_total = sum(size for _name, size in package_rows)
    package_total = (
        _global_total_without_scripts(result)
        if show_scripts
        else result.total_logical_bytes
    )
    sections = [
        _render_table(
            title="Package Sizes",
            header_title="Package",
            rows=package_rows,
            footer_title="Total Package Size",
            footer_value=package_total,
        )
    ]

    displayed_row_total = package_row_total
    if show_scripts:
        script_rows = _script_rows(result)
        script_total = sum(size for _path, size in script_rows)
        displayed_row_total += script_total
        sections.append(
            _render_table(
                title=binaries_title,
                header_title="Binary",
                rows=script_rows,
                footer_title="Total Binaries Size",
                footer_value=script_total,
            )
        )

    if result.completeness is Completeness.INCOMPLETE:
        sections.append(_incomplete_warning(result))
    if displayed_row_total != result.total_logical_bytes:
        row_kind = "displayed rows" if show_scripts else "distribution rows"
        sections.append(
            f"Note: {row_kind} total "
            f"{format_size(displayed_row_total)}, but Total size is "
            f"{format_size(result.total_logical_bytes)} because duplicate-owned "
            "files are counted once globally."
        )

    total_label = "Total size:"
    sections.append(f"{total_label}  {format_size(result.total_logical_bytes)}")
    return "\n\n".join(sections)


def _distribution_rows(
    result: AnalysisResult,
    *,
    exclude_scripts: bool,
) -> tuple[tuple[str, int], ...]:
    rows = []
    for distribution in result.distributions:
        total = sum(
            file.logical_bytes
            for file in distribution.files
            if not exclude_scripts or file.category is not FileCategory.SCRIPT
        )
        if total:
            rows.append((distribution.name, total))
    return tuple(sorted(rows, key=lambda row: (-row[1], row[0])))


def _script_rows(result: AnalysisResult) -> tuple[tuple[str, int], ...]:
    scripts_by_identity: dict[str, FileEntry] = {}
    for distribution in result.distributions:
        for file in distribution.files:
            if file.category is not FileCategory.SCRIPT:
                continue
            previous = scripts_by_identity.get(file.canonical_identity)
            if previous is None or file.path < previous.path:
                scripts_by_identity[file.canonical_identity] = file
    return tuple(
        sorted(
            ((file.path, file.logical_bytes) for file in scripts_by_identity.values()),
            key=lambda row: (-row[1], row[0]),
        )
    )


def _global_total_without_scripts(result: AnalysisResult) -> int:
    files_by_identity = {
        file.canonical_identity: file.logical_bytes
        for distribution in result.distributions
        for file in distribution.files
        if file.category is not FileCategory.SCRIPT
    }
    return sum(files_by_identity.values())


def _incomplete_warning(result: AnalysisResult) -> str:
    warnings = {
        warning
        for distribution in result.distributions
        for warning in distribution.warnings
        if warning.code.causes_incomplete_result
    } | {
        warning for warning in result.warnings if warning.code.causes_incomplete_result
    }
    counts = Counter(warning.code.value for warning in warnings)
    summary = "; ".join(f"{code}: {counts[code]}" for code in sorted(counts))
    return f"Warning: incomplete analysis ({summary})."


def _render_table(
    *,
    title: str,
    header_title: str,
    rows: tuple[tuple[str, int], ...],
    footer_title: str,
    footer_value: int,
) -> str:
    return render_total_table(
        title=title,
        header=(header_title, "Size"),
        rows=tuple((name, format_size(size)) for name, size in rows),
        footer=(footer_title, format_size(footer_value)),
    )
