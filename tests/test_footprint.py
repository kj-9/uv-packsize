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
from uv_packsize.footprint import (
    DependencyRoleTotal,
    FileCategoryTotal,
    FootprintResult,
    FootprintRole,
    summarize_footprint,
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


def file(
    identity: str,
    logical_bytes: int,
    category: FileCategory,
) -> FileEntry:
    return FileEntry(
        path=identity,
        canonical_identity=identity,
        logical_bytes=logical_bytes,
        category=category,
        origin=FileOrigin.RECORD,
    )


def explained(
    requirements: tuple[str, ...],
    distributions: tuple[tuple[str, str, tuple[FileEntry, ...], tuple[str, ...]], ...],
    *,
    graph_warning: DependencyGraphWarning | None = None,
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


def categories(result) -> dict[FileCategory, int]:
    return {total.category: total.logical_bytes for total in result.category_totals}


def roles(result) -> dict[FootprintRole, DependencyRoleTotal]:
    assert result.role_totals is not None
    return {total.role: total for total in result.role_totals}


def test_category_totals_include_every_category_zero_and_empty_inventory():
    result = summarize_footprint(explained(("root",), (("root", "1", (), ()),)))

    assert tuple(total.category for total in result.category_totals) == tuple(
        FileCategory
    )
    assert categories(result) == {category: 0 for category in FileCategory}
    assert result.logical_bytes == 0
    assert result.role_totals is not None
    assert all(total.logical_bytes == 0 for total in result.role_totals)


def test_category_totals_are_global_deduplicated_and_cover_all_categories():
    values = tuple(
        file(f"root/{category.value}", index + 1, category)
        for index, category in enumerate(FileCategory)
    )
    result = summarize_footprint(explained(("root",), (("root", "1", values, ()),)))

    assert categories(result) == {
        category: index + 1 for index, category in enumerate(FileCategory)
    }
    assert result.logical_bytes == sum(range(1, len(FileCategory) + 1))


def test_roles_classify_direct_transitive_unattributed_and_root_as_self():
    result = summarize_footprint(
        explained(
            ("root", "also-root"),
            (
                (
                    "root",
                    "1",
                    (file("root.py", 1, FileCategory.PYTHON),),
                    ("direct", "also-root"),
                ),
                ("also-root", "1", (file("also.py", 2, FileCategory.DATA),), ()),
                (
                    "direct",
                    "1",
                    (file("direct.py", 4, FileCategory.NATIVE),),
                    ("transitive",),
                ),
                (
                    "transitive",
                    "1",
                    (file("transitive.py", 8, FileCategory.METADATA),),
                    (),
                ),
                ("orphan", "1", (file("orphan.py", 16, FileCategory.OTHER),), ()),
            ),
        )
    )

    totals = roles(result)
    assert totals[FootprintRole.SELF].logical_bytes == 3
    assert totals[FootprintRole.DIRECT].logical_bytes == 4
    assert totals[FootprintRole.TRANSITIVE].logical_bytes == 8
    assert totals[FootprintRole.UNATTRIBUTED].logical_bytes == 16
    assert totals[FootprintRole.MIXED_OWNERSHIP].logical_bytes == 0
    assert sum(total.logical_bytes for total in totals.values()) == result.logical_bytes


def test_root_that_is_also_a_dependency_is_counted_as_self():
    result = summarize_footprint(
        explained(
            ("root", "also-root"),
            (
                ("root", "1", (), ("also-root",)),
                (
                    "also-root",
                    "1",
                    (file("also-root.py", 5, FileCategory.PYTHON),),
                    (),
                ),
            ),
        )
    )

    assert roles(result)[FootprintRole.SELF].logical_bytes == 5
    assert roles(result)[FootprintRole.DIRECT].logical_bytes == 0


def test_shared_dependency_with_duplicate_root_input_is_direct_once():
    result = summarize_footprint(
        explained(
            ("root-a", "root-b", "Root_A"),
            (
                ("root-a", "1", (), ("shared",)),
                ("root-b", "1", (), ("shared",)),
                (
                    "shared",
                    "1",
                    (file("shared.py", 7, FileCategory.DATA),),
                    (),
                ),
            ),
        )
    )

    assert result.logical_bytes == 7
    assert roles(result)[FootprintRole.DIRECT].logical_bytes == 7
    assert roles(result)[FootprintRole.MIXED_OWNERSHIP].logical_bytes == 0


def test_duplicate_ownership_is_deduplicated_once_when_owner_roles_match():
    shared = file("shared.py", 9, FileCategory.SCRIPT)
    result = summarize_footprint(
        explained(
            ("first", "second"),
            (
                ("first", "1", (shared,), ()),
                ("second", "1", (shared,), ()),
            ),
        )
    )

    assert result.logical_bytes == 9
    assert roles(result)[FootprintRole.SELF].logical_bytes == 9
    assert categories(result)[FileCategory.SCRIPT] == 9


def test_duplicate_ownership_with_distinct_kinds_is_mixed_once():
    shared = file("shared.py", 9, FileCategory.SCRIPT)
    result = summarize_footprint(
        explained(
            ("root",),
            (
                ("root", "1", (shared,), ("child",)),
                ("child", "1", (shared,), ()),
            ),
        )
    )

    assert result.logical_bytes == 9
    assert roles(result)[FootprintRole.MIXED_OWNERSHIP].logical_bytes == 9
    assert roles(result)[FootprintRole.SELF].logical_bytes == 0
    assert roles(result)[FootprintRole.DIRECT].logical_bytes == 0


def test_direct_and_transitive_duplicate_is_mixed_and_role_matrix_matches_global():
    shared = file("shared.py", 9, FileCategory.DATA)
    result = summarize_footprint(
        explained(
            ("root",),
            (
                (
                    "root",
                    "1",
                    (file("root.py", 1, FileCategory.PYTHON),),
                    ("direct",),
                ),
                (
                    "direct",
                    "1",
                    (shared, file("direct.py", 2, FileCategory.NATIVE)),
                    ("transitive",),
                ),
                (
                    "transitive",
                    "1",
                    (shared, file("transitive.py", 4, FileCategory.METADATA)),
                    (),
                ),
            ),
        )
    )

    totals = roles(result)
    assert result.logical_bytes == 16
    assert totals[FootprintRole.MIXED_OWNERSHIP].logical_bytes == 9
    assert {
        category: sum(
            next(
                total.logical_bytes
                for total in role_total.category_totals
                if total.category is category
            )
            for role_total in totals.values()
        )
        for category in FileCategory
    } == categories(result)


def test_graph_incompleteness_hides_role_totals_without_hiding_categories():
    result = summarize_footprint(
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

    assert result.role_totals is None
    assert categories(result)[FileCategory.PYTHON] == 5
    assert result.logical_bytes == 5


def test_results_are_deterministic_immutable_and_reject_forged_totals():
    forward = explained(
        ("root",),
        (
            ("root", "1", (file("root.py", 2, FileCategory.PYTHON),), ("child",)),
            ("child", "1", (file("child.py", 3, FileCategory.DATA),), ()),
        ),
    )
    reverse = explained(
        ("root",),
        (
            ("child", "1", (file("child.py", 3, FileCategory.DATA),), ()),
            ("root", "1", (file("root.py", 2, FileCategory.PYTHON),), ("child",)),
        ),
    )
    result = summarize_footprint(forward)

    assert result == summarize_footprint(reverse)
    with pytest.raises(FrozenInstanceError):
        cast(Any, result).logical_bytes = 0
    with pytest.raises(ValueError, match="equal category totals"):
        FootprintResult(
            explained=forward,
            logical_bytes=6,
            category_totals=result.category_totals,
            role_totals=result.role_totals,
        )
    with pytest.raises(ValueError, match="equal its category totals"):
        DependencyRoleTotal(
            role=FootprintRole.SELF,
            logical_bytes=1,
            category_totals=tuple(
                FileCategoryTotal(category=category, logical_bytes=0)
                for category in FileCategory
            ),
        )
