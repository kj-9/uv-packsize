from dataclasses import FrozenInstanceError
from typing import Any, cast

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
from uv_packsize.footprint import FileCategoryTotal, summarize_footprint
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
from uv_packsize.root_contributions import (
    RootContribution,
    RootContributionResult,
    RootScopedTotal,
    RootSetTotal,
    summarize_root_contributions,
)


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


def explained(
    requirements: tuple[str, ...],
    distributions: tuple[tuple[str, str, tuple[FileEntry, ...], tuple[str, ...]], ...],
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
            DistributionResult(name=name, version=version, files=files)
            for name, version, files, _requires in distributions
        ),
        warnings=analysis_warnings,
    )
    graph = build_dependency_graph(
        analysis,
        tuple(
            InstalledDistributionMetadata(
                name=name, version=version, requires_dist=requires
            )
            for name, version, _files, requires in distributions
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
    return explain_dependency_paths(analysis, graph)


def category_bytes(total) -> dict[FileCategory, int]:
    return {item.category: item.logical_bytes for item in total.category_totals}


def root_sets(result):
    assert result.root_set_totals is not None
    return {total.root_names: total for total in result.root_set_totals}


def roots(result):
    assert result.roots is not None
    return {root.root_name: root for root in result.roots}


def test_empty_inventory_has_unattributed_and_singleton_zero_buckets():
    result = summarize_root_contributions(
        explained(("root",), (("root", "1", (), ()),))
    )

    assert [total.root_names for total in result.root_set_totals or ()] == [
        (),
        ("root",),
    ]
    assert all(
        total.logical_bytes == total.file_count == 0
        for total in root_sets(result).values()
    )
    assert category_bytes(root_sets(result)[()]) == {
        category: 0 for category in FileCategory
    }
    root = roots(result)["root"]
    assert root.closure.logical_bytes == 0
    assert result.footprint == summarize_footprint(result.explained)


def test_two_roots_shared_bytes_are_not_split_or_double_counted():
    result = summarize_root_contributions(
        explained(
            ("root-a", "root-b"),
            (
                ("root-a", "1", (file("a.py", 2, FileCategory.PYTHON),), ("shared",)),
                ("root-b", "1", (file("b.dat", 3, FileCategory.DATA),), ("shared",)),
                ("shared", "1", (file("shared.bin", 5, FileCategory.NATIVE),), ()),
            ),
        )
    )

    totals = root_sets(result)
    assert [total.root_names for total in result.root_set_totals or ()] == [
        (),
        ("root-a",),
        ("root-b",),
        ("root-a", "root-b"),
    ]
    assert totals[("root-a",)].logical_bytes == 2
    assert totals[("root-b",)].logical_bytes == 3
    assert totals[("root-a", "root-b")].logical_bytes == 5
    assert category_bytes(totals[("root-a",)]) == {
        category: 2 if category is FileCategory.PYTHON else 0
        for category in FileCategory
    }
    assert category_bytes(totals[("root-a", "root-b")]) == {
        category: 5 if category is FileCategory.NATIVE else 0
        for category in FileCategory
    }
    assert result.footprint.logical_bytes == 10
    assert roots(result)["root-a"].closure.logical_bytes == 7
    assert roots(result)["root-a"].exclusive.logical_bytes == 2
    assert roots(result)["root-a"].shared.logical_bytes == 5
    assert roots(result)["root-b"].closure.logical_bytes == 8


def test_valid_empty_root_graph_has_only_the_unattributed_zero_bucket():
    result = summarize_root_contributions(
        explained(
            ("root; python_version < '0'",),
            (("root", "1", (), ()),),
        )
    )

    assert result.root_set_totals is not None
    assert result.root_set_totals[0].root_names == ()
    assert result.root_set_totals[0].file_count == 0
    assert result.roots == ()


def test_duplicate_root_inputs_keep_all_indexes_without_changing_bytes():
    result = summarize_root_contributions(
        explained(
            ("root", "Root"),
            (("root", "1", (file("root.py", 7, FileCategory.PYTHON),), ()),),
        )
    )

    assert roots(result)["root"].root_input_indexes == (0, 1)
    assert root_sets(result)[("root",)].logical_bytes == 7
    assert result.footprint.logical_bytes == 7


def test_root_also_dependency_and_cycle_use_node_root_name_union():
    result = summarize_root_contributions(
        explained(
            ("root", "also-root"),
            (
                (
                    "root",
                    "1",
                    (file("root.py", 1, FileCategory.PYTHON),),
                    ("also-root",),
                ),
                (
                    "also-root",
                    "1",
                    (file("also.py", 2, FileCategory.DATA),),
                    ("root",),
                ),
            ),
        )
    )

    assert root_sets(result)[("also-root", "root")].logical_bytes == 3
    assert roots(result)["root"].exclusive.logical_bytes == 0
    assert roots(result)["root"].shared.logical_bytes == 3
    assert roots(result)["also-root"].root_input_indexes == (1,)


def test_unattributed_and_duplicate_owner_files_use_union_of_owner_root_names():
    duplicate = file("duplicate.py", 7, FileCategory.SCRIPT)
    result = summarize_root_contributions(
        explained(
            ("root-a", "root-b"),
            (
                ("root-a", "1", (duplicate,), ("dep",)),
                ("root-b", "1", (duplicate,), ("dep",)),
                ("dep", "1", (file("dep.py", 3, FileCategory.DATA),), ()),
                ("orphan", "1", (file("orphan", 5, FileCategory.OTHER),), ()),
            ),
        )
    )

    totals = root_sets(result)
    assert totals[("root-a", "root-b")].logical_bytes == 10
    assert totals[()].logical_bytes == 5
    assert totals[("root-a", "root-b")].file_count == 2
    assert result.footprint.logical_bytes == 15


def test_incomplete_graph_hides_contribution_totals_but_keeps_footprint_categories():
    result = summarize_root_contributions(
        explained(
            ("root",),
            (("root", "1", (file("root.py", 5, FileCategory.PYTHON),), ()),),
            graph_warning=DependencyGraphWarning(
                code=DependencyGraphWarningCode.MISSING_METADATA,
                target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                target_identity="root",
            ),
        )
    )

    assert result.root_set_totals is None
    assert result.roots is None
    assert category_bytes(result.footprint)[FileCategory.PYTHON] == 5


def test_inventory_incomplete_keeps_measured_totals_and_delegates_completeness():
    result = summarize_root_contributions(
        explained(
            ("root",),
            (("root", "1", (file("root.py", 5, FileCategory.PYTHON),), ()),),
            analysis_warnings=(
                AnalysisWarning(
                    code=WarningCode.MISSING_RECORD,
                    target_kind=WarningTargetKind.DISTRIBUTION,
                    target_identity="root==1",
                ),
            ),
        )
    )

    assert root_sets(result)[("root",)].logical_bytes == 5
    assert result.inventory_completeness is result.explained.inventory_completeness
    assert result.graph_completeness is result.explained.graph_completeness
    assert result.completeness is result.explained.completeness
    assert (
        result.footprint.inventory_completeness
        is result.explained.inventory_completeness
    )
    assert result.footprint.completeness is result.explained.completeness


def test_result_is_deterministic_immutable_and_rejects_forged_values():
    forward = explained(
        ("root",),
        (
            ("root", "1", (file("root.py", 2, FileCategory.PYTHON),), ("child",)),
            ("child", "1", (file("child.dat", 3, FileCategory.DATA),), ()),
        ),
    )
    reverse = explained(
        ("root",),
        (
            ("child", "1", (file("child.dat", 3, FileCategory.DATA),), ()),
            ("root", "1", (file("root.py", 2, FileCategory.PYTHON),), ("child",)),
        ),
    )
    result = summarize_root_contributions(forward)

    assert result == summarize_root_contributions(reverse)
    with pytest.raises(FrozenInstanceError):
        cast(Any, result).roots = None
    with pytest.raises(ValueError, match="inconsistent with explained analysis"):
        RootContributionResult(
            explained=forward,
            footprint=result.footprint,
            root_set_totals=(),
            roots=(),
        )
    with pytest.raises(ValueError, match="equal category totals"):
        RootSetTotal(
            root_names=("root",),
            logical_bytes=1,
            category_totals=tuple(
                FileCategoryTotal(category=category, logical_bytes=0)
                for category in FileCategory
            ),
            file_count=1,
        )
    zero_total = RootScopedTotal(
        logical_bytes=0,
        category_totals=tuple(
            FileCategoryTotal(category=category, logical_bytes=0)
            for category in FileCategory
        ),
        file_count=0,
    )
    with pytest.raises(ValueError, match="closure must equal"):
        RootContribution(
            root_name="root",
            root_input_indexes=(0,),
            closure=RootScopedTotal(
                logical_bytes=1,
                category_totals=tuple(
                    FileCategoryTotal(
                        category=category,
                        logical_bytes=1 if category is FileCategory.PYTHON else 0,
                    )
                    for category in FileCategory
                ),
                file_count=1,
            ),
            exclusive=zero_total,
            shared=zero_total,
        )
