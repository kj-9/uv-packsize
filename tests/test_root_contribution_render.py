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
from uv_packsize.models import (
    AnalysisResult,
    AnalysisWarning,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ResolutionContext,
    WarningCode,
    WarningTargetKind,
)
from uv_packsize.render import render_analysis_report
from uv_packsize.root_contribution_render import (
    _render_table,
    _safe_text,
    render_root_contribution_report,
    render_root_contribution_sections,
)
from uv_packsize.root_contributions import summarize_root_contributions


def environment() -> MarkerEnvironment:
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


def file(identity: str, size: int, category: FileCategory) -> FileEntry:
    return FileEntry(
        path=identity,
        canonical_identity=identity,
        logical_bytes=size,
        category=category,
        origin=FileOrigin.RECORD,
    )


def result(
    requirements: tuple[str, ...],
    distributions: tuple[tuple[str, tuple[FileEntry, ...], tuple[str, ...]], ...],
    *,
    graph_warning: DependencyGraphWarning | None = None,
    analysis_warnings: tuple[AnalysisWarning, ...] = (),
):
    analysis = AnalysisResult(
        context=ResolutionContext(
            requirements=requirements,
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
        warnings=analysis_warnings,
    )
    graph = build_dependency_graph(
        analysis,
        tuple(
            InstalledDistributionMetadata(
                name=name, version="1", requires_dist=requires
            )
            for name, _files, requires in distributions
        ),
        environment(),
    )
    if graph_warning is not None:
        graph = DependencyGraph(
            roots=graph.roots,
            nodes=graph.nodes,
            edges=graph.edges,
            warnings=(graph_warning,),
        )
    return summarize_root_contributions(explain_dependency_paths(analysis, graph))


def test_report_preserves_ordinary_report_as_exact_prefix_and_bin_only_changes_prefix():
    contribution = result(
        ("root",),
        (
            (
                "root",
                (
                    file("root.py", 1024, FileCategory.PYTHON),
                    file("tool", 2, FileCategory.SCRIPT),
                ),
                (),
            ),
        ),
    )

    report = render_root_contribution_report(contribution)
    with_scripts = render_root_contribution_report(contribution, show_scripts=True)
    prefix = render_analysis_report(contribution.analysis)

    assert report.startswith(prefix)
    assert report == f"{prefix}\n\n" + "\n\n".join(
        render_root_contribution_sections(contribution)
    )
    assert (
        report.split("\n\n--- Root Contributions ---", 1)[1]
        == with_scripts.split("\n\n--- Root Contributions ---", 1)[1]
    )


def test_complete_graph_renders_non_split_root_sets_and_reconciliation():
    contribution = result(
        ("root-b", "root-a", "Root-A"),
        (
            ("root-a", (file("a", 1024, FileCategory.PYTHON),), ("shared",)),
            ("root-b", (file("b", 1024**2, FileCategory.DATA),), ("shared",)),
            ("shared", (file("shared", 1024**3, FileCategory.NATIVE),), ()),
            ("orphan", (file("orphan", 3, FileCategory.OTHER),), ()),
        ),
    )

    roots, shared, reconciliation = render_root_contribution_sections(contribution)

    assert roots.index("root-a") < roots.index("root-b")
    assert "2, 3" in roots
    assert "1.00 KiB" in roots
    assert "1.00 MiB" in roots
    assert "1.00 GiB" in roots
    assert "1073741824" not in roots
    assert "closures must not be summed across roots" in roots
    assert shared.count("root-a, root-b") == 1
    assert "1.00 GiB" in shared
    assert "Exclusive + Shared + Unattributed = Global total." in reconciliation
    assert "3 B" in reconciliation


def test_zero_shared_bucket_and_no_roots_are_explicit():
    no_shared = result(("root",), (("root", (), ()),))
    no_roots = result(("root; python_version < '0'",), (("root", (), ()),))

    assert (
        "No shared root-set buckets.\nTotal shared root-set bytes  0 B"
        in render_root_contribution_sections(no_shared)[1]
    )
    assert (
        "No recognized requested roots."
        in render_root_contribution_sections(no_roots)[0]
    )


def test_incomplete_graph_hides_all_contribution_numbers_and_target_details():
    secret = "secret-target"
    contribution = result(
        ("root",),
        (("root", (file("root", 5, FileCategory.PYTHON),), ()),),
        graph_warning=DependencyGraphWarning(
            code=DependencyGraphWarningCode.MISSING_METADATA,
            target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
            target_identity=secret,
        ),
    )

    sections = render_root_contribution_sections(contribution)

    assert all("5 B" not in section for section in sections)
    assert all(secret not in section for section in sections)
    assert sections[0].endswith("missing-metadata: 1).")
    assert (
        render_root_contribution_sections(
            contribution, include_graph_warning_summary=False
        )[0]
        == "--- Root Contributions ---\nUnavailable: incomplete dependency graph."
    )


def test_incomplete_inventory_keeps_partial_values_and_safe_note():
    contribution = result(
        ("root",),
        (("root", (file("root", 5, FileCategory.PYTHON),), ()),),
        analysis_warnings=(
            AnalysisWarning(
                code=WarningCode.MISSING_RECORD,
                target_kind=WarningTargetKind.DISTRIBUTION,
                target_identity="secret-path==1",
            ),
        ),
    )

    sections = render_root_contribution_sections(contribution)

    assert "5 B" in sections[0]
    assert (
        sections[-1]
        == "Note: incomplete inventory; contribution values are measured partial bytes."
    )
    assert "secret-path" not in "\n".join(sections)


def test_terminal_controls_are_sanitized():
    assert _safe_text("root\x1b[31m\n") == "root?[31m?"


def test_table_aligns_every_requested_numeric_column_without_reformatting_values():
    lines = _render_table(
        header=("Root", "Exclusive", "Shared", "Closure"),
        rows=(
            ("alpha", "1 B", "1.00 KiB", "1.00 MiB"),
            ("beta", "1.00 GiB", "2 B", "1 B"),
        ),
        right_align_indexes=(1, 2, 3),
    )

    assert lines[2].index("1 B") + len("1 B") == lines[3].index("1.00 GiB") + len(
        "1.00 GiB"
    )
    assert lines[2].index("1.00 KiB") + len("1.00 KiB") == lines[3].index("2 B") + len(
        "2 B"
    )
    assert lines[2].index("1.00 MiB") + len("1.00 MiB") == lines[3].index("1 B") + len(
        "1 B"
    )


@pytest.mark.parametrize("value", [None, object()])
def test_renderers_reject_wrong_result_type(value: Any):
    with pytest.raises(TypeError, match="RootContributionResult"):
        render_root_contribution_report(value)
    with pytest.raises(TypeError, match="RootContributionResult"):
        render_root_contribution_sections(value)


@pytest.mark.parametrize("value", [None, 1])
def test_renderers_validate_boolean_options(value: Any):
    contribution = result(("root",), (("root", (), ()),))
    with pytest.raises(TypeError, match="show_scripts must be a bool"):
        render_root_contribution_report(contribution, show_scripts=value)
    with pytest.raises(TypeError, match="include_graph_warning_summary must be a bool"):
        render_root_contribution_sections(
            contribution, include_graph_warning_summary=value
        )
