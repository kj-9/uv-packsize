from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from uv_packsize.dependency_graph import (
    DependencyGraphCompleteness,
    DependencyGraphWarningCode,
    DependencyKind,
    InstalledDistributionMetadata,
    MarkerEnvironment,
    RootRequirementStatus,
    build_dependency_graph,
)
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    ExistingPrefixContext,
    PathFlavor,
    ResolutionContext,
    normalize_distribution_name,
)


def environment(**overrides: str) -> MarkerEnvironment:
    values = {
        "implementation_name": "cpython",
        "implementation_version": "3.12.4",
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "platform_release": "6.8",
        "platform_system": "Linux",
        "platform_version": "#1",
        "python_full_version": "3.12.4",
        "python_version": "3.12",
        "sys_platform": "linux",
    }
    values.update(overrides)
    return MarkerEnvironment(**values)


def analysis(
    requirements: tuple[str, ...],
    installed: tuple[tuple[str, str], ...],
    **context_overrides: Any,
) -> AnalysisResult:
    context_values: dict[str, Any] = {
        "requirements": requirements,
        "python_version": "3.12.4",
        "platform": "linux",
        "architecture": "x86_64",
        "path_flavor": PathFlavor.POSIX,
        "case_rule": CaseRule.SENSITIVE,
        "uv_version": "0.11.3",
        "build_policy": BuildPolicy.WHEEL_ONLY,
        "compile_bytecode": False,
    }
    context_values.update(context_overrides)
    return AnalysisResult(
        context=ResolutionContext(**context_values),
        distributions=tuple(
            DistributionResult(name=name, version=version, files=())
            for name, version in installed
        ),
    )


def existing_prefix_analysis(
    installed: tuple[tuple[str, str], ...],
) -> AnalysisResult:
    return AnalysisResult(
        context=ExistingPrefixContext(
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
        ),
        distributions=tuple(
            DistributionResult(name=name, version=version, files=())
            for name, version in installed
        ),
    )


def metadata(
    *values: tuple[str, str, tuple[str, ...]],
) -> tuple[InstalledDistributionMetadata, ...]:
    return tuple(
        InstalledDistributionMetadata(
            name=name, version=version, requires_dist=requires
        )
        for name, version, requires in values
    )


def test_normalize_distribution_name_is_public_and_shared_by_graph_models():
    assert normalize_distribution_name("Example_Pkg.Name") == "example-pkg-name"
    assert (
        InstalledDistributionMetadata(name="Example_Pkg", version="1").name
        == "example-pkg"
    )


def test_graph_rejects_existing_prefix_context_without_reading_resolution_fields():
    result = existing_prefix_analysis((("root", "1"),))

    with pytest.raises(
        TypeError, match="^dependency graph requires a ResolutionContext$"
    ):
        build_dependency_graph(result, (), environment())


def test_graph_is_deterministic_and_classifies_direct_transitive_shared_and_unattributed():
    result = analysis(
        ("Root_A", "root-b"),
        (
            ("unused", "1"),
            ("shared", "1"),
            ("leaf", "1"),
            ("root-b", "1"),
            ("root-a", "1"),
        ),
    )
    graph = build_dependency_graph(
        result,
        metadata(
            ("root-b", "1", ("shared",)),
            ("shared", "1", ("leaf",)),
            ("unused", "1", ()),
            ("leaf", "1", ()),
            ("root-a", "1", ("shared",)),
        ),
        environment(),
    )

    assert [(edge.source_name, edge.target_name) for edge in graph.edges] == [
        ("root-a", "shared"),
        ("root-b", "shared"),
        ("shared", "leaf"),
    ]
    assert [
        (node.name, node.kind, node.root_names, node.is_shared) for node in graph.nodes
    ] == [
        ("leaf", DependencyKind.TRANSITIVE, ("root-a", "root-b"), True),
        ("root-a", DependencyKind.ROOT, ("root-a",), False),
        ("root-b", DependencyKind.ROOT, ("root-b",), False),
        ("shared", DependencyKind.DIRECT, ("root-a", "root-b"), True),
        ("unused", DependencyKind.UNATTRIBUTED, (), False),
    ]
    assert graph.completeness is DependencyGraphCompleteness.COMPLETE
    with pytest.raises(FrozenInstanceError):
        cast(Any, graph.nodes[0]).name = "changed"


def test_graph_is_stable_for_input_permutations():
    result = analysis(("a",), (("a", "1"), ("b", "1")))
    first = build_dependency_graph(
        result,
        metadata(("a", "1", ("b",)), ("b", "1", ())),
        environment(),
    )
    second = build_dependency_graph(
        analysis(("a",), (("b", "1"), ("a", "1"))),
        metadata(("b", "1", ()), ("a", "1", ("b",))),
        environment(),
    )

    assert first == second


def test_explicit_marker_environment_omits_inactive_edges_without_using_host():
    result = analysis(
        ("root",), (("root", "1"), ("linux-only", "1"), ("win-only", "1"))
    )
    graph = build_dependency_graph(
        result,
        metadata(
            (
                "root",
                "1",
                (
                    "linux-only; sys_platform == 'linux'",
                    "win-only; sys_platform == 'win32'",
                ),
            ),
            ("linux-only", "1", ()),
            ("win-only", "1", ()),
        ),
        environment(sys_platform="win32", os_name="nt"),
    )

    assert [(edge.source_name, edge.target_name) for edge in graph.edges] == [
        ("root", "win-only")
    ]
    assert {node.name: node.kind for node in graph.nodes} == {
        "root": DependencyKind.ROOT,
        "linux-only": DependencyKind.UNATTRIBUTED,
        "win-only": DependencyKind.DIRECT,
    }


def test_inactive_root_marker_is_not_recognized_or_reported_as_an_error():
    graph = build_dependency_graph(
        analysis(("root; python_version < '3.11'",), (("root", "1"),)),
        metadata(("root", "1", ())),
        environment(python_version="3.12", python_full_version="3.12.4"),
    )

    assert graph.roots[0].status is RootRequirementStatus.INACTIVE
    assert graph.nodes[0].kind is DependencyKind.UNATTRIBUTED
    assert graph.warnings == ()


def test_indeterminate_root_marker_is_safe_and_makes_the_graph_incomplete():
    graph = build_dependency_graph(
        analysis(("root; python_version ~= 'bogus'",), (("root", "1"),)),
        metadata(("root", "1", ())),
        environment(),
    )

    assert graph.roots[0].name is None
    assert graph.roots[0].status is RootRequirementStatus.UNIDENTIFIABLE
    assert graph.warnings == (graph.warnings[0],)
    assert (
        graph.warnings[0].code is DependencyGraphWarningCode.ROOT_MARKER_INDETERMINATE
    )
    assert graph.completeness is DependencyGraphCompleteness.INCOMPLETE


def test_root_version_specifiers_follow_packagings_default_prerelease_policy():
    default_policy_graph = build_dependency_graph(
        analysis(("root>=1.0",), (("root", "1.1rc1"),)),
        metadata(("root", "1.1rc1", ())),
        environment(),
    )
    explicit_prerelease_graph = build_dependency_graph(
        analysis(("root>=1.0rc1",), (("root", "1.1rc1"),)),
        metadata(("root", "1.1rc1", ())),
        environment(),
    )

    assert (
        default_policy_graph.roots[0].status is RootRequirementStatus.VERSION_MISMATCH
    )
    assert explicit_prerelease_graph.roots[0].status is RootRequirementStatus.RECOGNIZED


def test_extras_propagate_to_a_fixed_point_for_marker_evaluation():
    result = analysis(
        ("root[feature]",), (("root", "1"), ("middle", "1"), ("leaf", "1"))
    )
    graph = build_dependency_graph(
        result,
        metadata(
            ("root", "1", ("middle[child]; extra == 'feature'",)),
            ("middle", "1", ("leaf; extra == 'child'",)),
            ("leaf", "1", ()),
        ),
        environment(),
    )

    assert [(edge.source_name, edge.target_name) for edge in graph.edges] == [
        ("middle", "leaf"),
        ("root", "middle"),
    ]
    assert [edge.requested_extras for edge in graph.edges] == [(), ("child",)]


def test_markers_evaluate_the_empty_extra_even_when_an_extra_is_selected():
    graph = build_dependency_graph(
        analysis(("root[docs]",), (("root", "1"), ("child", "1"))),
        metadata(
            ("root", "1", ("child; extra != 'docs'",)),
            ("child", "1", ()),
        ),
        environment(),
    )

    assert [(edge.source_name, edge.target_name) for edge in graph.edges] == [
        ("root", "child")
    ]


def test_context_extras_do_not_activate_an_optional_edge_for_a_root_requirement():
    graph = build_dependency_graph(
        analysis(
            ("root",),
            (("root", "1"), ("docs-child", "1")),
            extras=("docs",),
        ),
        metadata(
            ("root", "1", ("docs-child; extra == 'docs'",)),
            ("docs-child", "1", ()),
        ),
        environment(),
    )

    assert graph.roots[0].selected_extras == ()
    assert graph.edges == ()


def test_duplicate_active_requirements_coalesce_requested_extras():
    graph = build_dependency_graph(
        analysis(("root",), (("root", "1"), ("child", "1"))),
        metadata(
            ("root", "1", ("child[first]", "child[second]")),
            ("child", "1", ()),
        ),
        environment(),
    )

    assert len(graph.edges) == 1
    assert graph.edges[0].source_name == "root"
    assert graph.edges[0].target_name == "child"
    assert graph.edges[0].requested_extras == ("first", "second")


def test_cycles_are_safe_and_attribution_uses_bfs_distance():
    graph = build_dependency_graph(
        analysis(("root",), (("root", "1"), ("a", "1"), ("b", "1"))),
        metadata(
            ("root", "1", ("a",)),
            ("a", "1", ("b",)),
            ("b", "1", ("a",)),
        ),
        environment(),
    )

    assert {node.name: node.kind for node in graph.nodes} == {
        "a": DependencyKind.DIRECT,
        "b": DependencyKind.TRANSITIVE,
        "root": DependencyKind.ROOT,
    }


def test_root_statuses_handle_version_mismatch_missing_invalid_and_named_direct_reference():
    result = analysis(
        (
            "present==2",
            "missing>=1",
            "this is not valid @@@",
            "direct @ https://private.invalid/secret.whl",
        ),
        (("present", "1"), ("direct", "0")),
    )
    graph = build_dependency_graph(
        result,
        metadata(("present", "1", ()), ("direct", "0", ())),
        environment(),
    )

    assert [(root.name, root.status) for root in graph.roots] == [
        ("present", RootRequirementStatus.VERSION_MISMATCH),
        ("missing", RootRequirementStatus.UNMATCHED),
        (None, RootRequirementStatus.UNIDENTIFIABLE),
        ("direct", RootRequirementStatus.RECOGNIZED),
    ]
    assert {warning.code for warning in graph.warnings} >= {
        DependencyGraphWarningCode.INVALID_ROOT_REQUIREMENT,
        DependencyGraphWarningCode.ROOT_UNMATCHED,
        DependencyGraphWarningCode.ROOT_VERSION_MISMATCH,
    }
    assert graph.completeness is DependencyGraphCompleteness.INCOMPLETE


def test_missing_metadata_invalid_metadata_and_missing_active_target_are_safe_warnings():
    result = analysis(("root",), (("root", "1"), ("orphan", "1")))
    graph = build_dependency_graph(
        result,
        metadata(("root", "1", ("missing", "not valid @@@"))),
        environment(),
    )

    assert graph.edges == ()
    assert {(warning.code, warning.target_identity) for warning in graph.warnings} == {
        (DependencyGraphWarningCode.INVALID_REQUIRES_DIST, "root"),
        (DependencyGraphWarningCode.MISSING_DEPENDENCY_TARGET, "missing"),
        (DependencyGraphWarningCode.MISSING_METADATA, "orphan"),
    }
    assert graph.completeness is DependencyGraphCompleteness.INCOMPLETE


def test_metadata_version_mismatch_is_not_used_to_create_edges():
    graph = build_dependency_graph(
        analysis(("root",), (("root", "1"), ("child", "1"))),
        metadata(("root", "2", ("child",)), ("child", "1", ())),
        environment(),
    )

    assert graph.edges == ()
    assert graph.warnings == (graph.warnings[0],)
    assert (
        graph.warnings[0].code is DependencyGraphWarningCode.METADATA_VERSION_MISMATCH
    )


def test_graph_warnings_and_errors_do_not_leak_raw_requirements_urls_or_parser_diagnostics():
    secret = "https://token@private.invalid/hidden?key=secret"
    result = analysis((f"root @ {secret}",), (("root", "1"),))
    graph = build_dependency_graph(
        result,
        metadata(("root", "1", (f"child @ {secret}", "bad @@@"))),
        environment(),
    )

    rendered = repr(graph)
    assert secret not in rendered
    assert "bad @@@" not in rendered
    assert "token@" not in rendered


def test_dependency_graph_does_not_change_schema_v1_analysis_serialization():
    result = analysis(("root",), (("root", "1"),))
    before = render_analysis_json(result)

    build_dependency_graph(
        result,
        metadata(("root", "1", ())),
        environment(),
    )

    assert render_analysis_json(result) == before
