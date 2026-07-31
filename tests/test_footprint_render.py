from typing import Any

import pytest

from uv_packsize.dependency_graph import (
    DependencyGraph,
    DependencyGraphWarning,
    DependencyGraphWarningCode,
    DependencyGraphWarningTargetKind,
    InstalledDistributionMetadata,
    MarkerEnvironment,
    build_dependency_graph,
)
from uv_packsize.dependency_paths import explain_dependency_paths
from uv_packsize.footprint import FootprintRole, summarize_footprint
from uv_packsize.footprint_render import (
    render_footprint_report,
    render_footprint_sections,
)
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ResolutionContext,
)
from uv_packsize.render import render_analysis_report


def marker_environment() -> MarkerEnvironment:
    return MarkerEnvironment(
        implementation_name="cpython",
        implementation_version="3.12.4",
        os_name="posix",
        platform_machine="x86_64",
        platform_python_implementation="CPython",
        platform_release="6.8",
        platform_system="Linux",
        platform_version="#1",
        python_full_version="3.12.4",
        python_version="3.12",
        sys_platform="linux",
    )


def entry(identity: str, size: int, category: FileCategory) -> FileEntry:
    return FileEntry(
        path=identity,
        canonical_identity=identity,
        logical_bytes=size,
        category=category,
        origin=FileOrigin.RECORD,
    )


def footprint(
    distributions: tuple[tuple[str, tuple[FileEntry, ...], tuple[str, ...]], ...],
    *,
    graph_warning: DependencyGraphWarning | None = None,
):
    analysis = AnalysisResult(
        context=ResolutionContext(
            requirements=("root",),
            python_version="3.12.4",
            platform="linux",
            architecture="x86_64",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=False,
        ),
        distributions=tuple(
            DistributionResult(name=name, version="1", files=files)
            for name, files, _requires in distributions
        ),
    )
    graph = build_dependency_graph(
        analysis,
        tuple(
            InstalledDistributionMetadata(
                name=name, version="1", requires_dist=requires
            )
            for name, _files, requires in distributions
        ),
        marker_environment(),
    )
    if graph_warning is not None:
        graph = DependencyGraph(
            roots=graph.roots,
            nodes=graph.nodes,
            edges=graph.edges,
            warnings=(graph_warning,),
        )
    return summarize_footprint(explain_dependency_paths(analysis, graph))


def test_footprint_report_preserves_ordinary_report_as_exact_prefix():
    result = footprint((("root", (entry("root.py", 3, FileCategory.PYTHON),), ()),))

    report = render_footprint_report(result)
    prefix = render_analysis_report(result.analysis)

    assert report.startswith(prefix)
    assert report == f"{prefix}\n\n" + "\n\n".join(render_footprint_sections(result))


def test_category_breakdown_has_all_categories_in_enum_order_including_zeroes():
    result = footprint((("root", (entry("root.py", 1024, FileCategory.PYTHON),), ()),))

    categories = render_footprint_sections(result)[0].splitlines()

    assert categories == [
        "--- File Category Breakdown ---",
        "Category        Size",
        "----------  --------",
        "python      1.00 KiB",
        "native           0 B",
        "data             0 B",
        "metadata         0 B",
        "script           0 B",
        "other            0 B",
        "----------  --------",
        "Total size  1.00 KiB",
    ]


def test_dependency_attribution_uses_fixed_roles_and_global_total_footer():
    result = footprint(
        (
            ("root", (entry("root.py", 1, FileCategory.PYTHON),), ("direct",)),
            ("direct", (entry("direct.bin", 2, FileCategory.NATIVE),), ("leaf",)),
            ("leaf", (entry("leaf.dat", 4, FileCategory.DATA),), ()),
            ("orphan", (entry("orphan.txt", 8, FileCategory.OTHER),), ()),
        )
    )

    attribution = render_footprint_sections(result)[1]

    assert attribution.splitlines() == [
        "--- Dependency Size Attribution ---",
        "Role             Size",
        "---------------  ----",
        "self              1 B",
        "direct            2 B",
        "transitive        4 B",
        "unattributed      8 B",
        "mixed-ownership   0 B",
        "---------------  ----",
        "Total size       15 B",
    ]
    assert tuple(total.role for total in result.role_totals or ()) == tuple(
        FootprintRole
    )


def test_empty_footprint_keeps_all_zero_rows_and_units():
    result = footprint((("root", (), ()),))

    sections = render_footprint_sections(result)

    assert sections[0].count("  0 B") == len(FileCategory) + 1
    assert sections[1].count("  0 B") == len(FootprintRole) + 1


def test_bin_changes_only_the_existing_prefix_not_footprint_sections():
    result = footprint(
        (
            (
                "root",
                (
                    entry("root.py", 1, FileCategory.PYTHON),
                    entry("bin/tool", 2, FileCategory.SCRIPT),
                ),
                (),
            ),
        )
    )

    ordinary = render_footprint_report(result)
    with_binaries = render_footprint_report(result, show_scripts=True)

    assert ordinary != with_binaries
    assert (
        ordinary.split("\n\n--- File Category Breakdown ---", 1)[1]
        == (with_binaries.split("\n\n--- File Category Breakdown ---", 1)[1])
    )


def test_incomplete_graph_never_renders_role_numbers_or_unsafe_details():
    secret = "very-secret-metadata-or-path"
    result = footprint(
        (("root", (entry("root.py", 5, FileCategory.PYTHON),), ()),),
        graph_warning=DependencyGraphWarning(
            code=DependencyGraphWarningCode.MISSING_METADATA,
            target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
            target_identity="root",
        ),
    )

    sections = render_footprint_sections(result)

    assert sections[1] == (
        "--- Dependency Size Attribution ---\n"
        "Unavailable: incomplete dependency graph.\n"
        "Warning: incomplete dependency graph (missing-metadata: 1)."
    )
    assert "5 B" not in sections[1]
    assert secret not in sections[1]
    assert "root" not in sections[1]


def test_sections_allow_a_compositor_to_suppress_duplicate_graph_warning_summary():
    result = footprint(
        (("root", (), ()),),
        graph_warning=DependencyGraphWarning(
            code=DependencyGraphWarningCode.MISSING_METADATA,
            target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
            target_identity="root",
        ),
    )

    sections = render_footprint_sections(result, include_graph_warning_summary=False)

    assert sections[1] == (
        "--- Dependency Size Attribution ---\nUnavailable: incomplete dependency graph."
    )


@pytest.mark.parametrize("value", [None, object()])
def test_renderers_reject_non_footprint_results(value: Any):
    with pytest.raises(TypeError, match="FootprintResult"):
        render_footprint_report(value)
    with pytest.raises(TypeError, match="FootprintResult"):
        render_footprint_sections(value)


@pytest.mark.parametrize("value", [None, 1])
def test_renderers_validate_boolean_options(value: Any):
    result = footprint((("root", (), ()),))
    with pytest.raises(TypeError, match="show_scripts must be a bool"):
        render_footprint_report(result, show_scripts=value)
    with pytest.raises(TypeError, match="include_graph_warning_summary must be a bool"):
        render_footprint_sections(result, include_graph_warning_summary=value)
