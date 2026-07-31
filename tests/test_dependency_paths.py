from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from uv_packsize.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphCompleteness,
    DependencyGraphNode,
    DependencyGraphWarning,
    DependencyGraphWarningCode,
    DependencyGraphWarningTargetKind,
    DependencyKind,
    InstalledDistributionMetadata,
    MarkerEnvironment,
    RootRequirement,
    RootRequirementStatus,
    build_dependency_graph,
)
from uv_packsize.dependency_paths import (
    DependencyPath,
    DistributionAttribution,
    ExplainedAnalysisResult,
    explain_dependency_paths,
)
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import (
    AnalysisResult,
    AnalysisWarning,
    BuildPolicy,
    CaseRule,
    Completeness,
    DistributionResult,
    PathFlavor,
    ResolutionContext,
    WarningCode,
    WarningTargetKind,
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


def analysis(
    requirements: tuple[str, ...],
    installed: tuple[tuple[str, str], ...],
    *,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> AnalysisResult:
    return AnalysisResult(
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
            DistributionResult(name=name, version=version, files=())
            for name, version in installed
        ),
        warnings=warnings,
    )


def graph(
    result: AnalysisResult,
    *values: tuple[str, str, tuple[str, ...]],
) -> DependencyGraph:
    return build_dependency_graph(
        result,
        tuple(
            InstalledDistributionMetadata(
                name=name, version=version, requires_dist=requires
            )
            for name, version, requires in values
        ),
        environment(),
    )


def by_name(result: ExplainedAnalysisResult) -> dict[str, DistributionAttribution]:
    return {attribution.node.name: attribution for attribution in result.attributions}


def test_cycle_paths_are_simple_shortest_and_canonical():
    result = analysis(("root",), (("root", "1"), ("a", "1"), ("b", "1")))
    explained = explain_dependency_paths(
        result,
        graph(
            result,
            ("root", "1", ("a",)),
            ("a", "1", ("b",)),
            ("b", "1", ("a",)),
        ),
    )

    assert by_name(explained)["b"].canonical_path == DependencyPath(
        root_input_index=0, nodes=("root", "a", "b")
    )
    assert explained.attributions[0].node.name == "a"


def test_equal_routes_use_lexical_path_tie_breaker():
    result = analysis(
        ("root",),
        (("root", "1"), ("z", "1"), ("a", "1"), ("target", "1")),
    )
    explained = explain_dependency_paths(
        result,
        graph(
            result,
            ("root", "1", ("z", "a")),
            ("z", "1", ("target",)),
            ("a", "1", ("target",)),
            ("target", "1", ()),
        ),
    )

    assert by_name(explained)["target"].canonical_path == DependencyPath(
        root_input_index=0, nodes=("root", "a", "target")
    )


def test_shared_reachability_keeps_each_root_input_and_selects_canonical_path():
    result = analysis(
        ("root-b", "root-a"),
        (("root-a", "1"), ("root-b", "1"), ("shared", "1")),
    )
    explained = explain_dependency_paths(
        result,
        graph(
            result,
            ("root-a", "1", ("shared",)),
            ("root-b", "1", ("shared",)),
            ("shared", "1", ()),
        ),
    )

    shared = by_name(explained)["shared"]
    assert shared.root_input_indexes == (0, 1)
    assert shared.canonical_path == DependencyPath(
        root_input_index=0, nodes=("root-b", "shared")
    )
    assert shared.node.is_shared is True


def test_duplicate_root_inputs_are_retained_without_changing_graph_shared_status():
    result = analysis(("root", "Root"), (("root", "1"), ("child", "1")))
    explained = explain_dependency_paths(
        result,
        graph(result, ("root", "1", ("child",)), ("child", "1", ())),
    )

    child = by_name(explained)["child"]
    assert child.root_input_indexes == (0, 1)
    assert child.node.root_names == ("root",)
    assert child.node.is_shared is False


def test_recognized_root_index_is_retained_when_other_input_is_not_recognized():
    result = analysis(
        ("this is not valid @@@", "root"),
        (("root", "1"), ("child", "1")),
    )
    explained = explain_dependency_paths(
        result,
        graph(result, ("root", "1", ("child",)), ("child", "1", ())),
    )

    assert by_name(explained)["root"].root_input_indexes == (1,)
    assert by_name(explained)["child"].root_input_indexes == (1,)


def test_root_that_is_also_dependency_uses_zero_hop_path():
    result = analysis(
        ("root", "also-root"),
        (("root", "1"), ("also-root", "1")),
    )
    explained = explain_dependency_paths(
        result,
        graph(
            result,
            ("root", "1", ("also-root",)),
            ("also-root", "1", ()),
        ),
    )

    attribution = by_name(explained)["also-root"]
    assert attribution.root_input_indexes == (0, 1)
    assert attribution.canonical_path == DependencyPath(
        root_input_index=1, nodes=("also-root",)
    )
    assert attribution.node.kind is DependencyKind.ROOT


def test_unattributed_distribution_has_no_path_or_root_indexes():
    result = analysis(("root",), (("root", "1"), ("orphan", "1")))
    explained = explain_dependency_paths(
        result,
        graph(result, ("root", "1", ()), ("orphan", "1", ())),
    )

    orphan = by_name(explained)["orphan"]
    assert orphan.root_input_indexes == ()
    assert orphan.canonical_path is None


def test_component_completeness_remains_separate_from_combined_completeness():
    warning = AnalysisWarning(
        code=WarningCode.MISSING_METADATA,
        target_kind=WarningTargetKind.DISTRIBUTION,
        target_identity="root==1",
    )
    inventory_incomplete = analysis(("root",), (("root", "1"),), warnings=(warning,))
    complete_graph = graph(inventory_incomplete, ("root", "1", ()))
    explained = explain_dependency_paths(inventory_incomplete, complete_graph)

    assert explained.inventory_completeness is Completeness.INCOMPLETE
    assert explained.graph_completeness is DependencyGraphCompleteness.COMPLETE
    assert explained.completeness is Completeness.INCOMPLETE

    incomplete_graph = DependencyGraph(
        roots=complete_graph.roots,
        nodes=complete_graph.nodes,
        edges=complete_graph.edges,
        warnings=(
            DependencyGraphWarning(
                code=DependencyGraphWarningCode.MISSING_METADATA,
                target_kind=DependencyGraphWarningTargetKind.DISTRIBUTION,
                target_identity="root",
            ),
        ),
    )
    graph_incomplete = explain_dependency_paths(
        analysis(("root",), (("root", "1"),)), incomplete_graph
    )
    assert graph_incomplete.inventory_completeness is Completeness.COMPLETE
    assert graph_incomplete.graph_completeness is DependencyGraphCompleteness.INCOMPLETE
    assert graph_incomplete.completeness is Completeness.INCOMPLETE


def test_rejects_distribution_mismatch_and_hand_built_inconsistent_node_labels():
    result = analysis(("root",), (("root", "1"),))
    wrong_version = DependencyGraph(
        roots=(
            RootRequirement(
                input_index=0, name="root", status=RootRequirementStatus.RECOGNIZED
            ),
        ),
        nodes=(
            DependencyGraphNode(
                name="root",
                version="2",
                kind=DependencyKind.ROOT,
                root_names=("root",),
            ),
        ),
        edges=(),
    )
    with pytest.raises(ValueError, match="must match"):
        explain_dependency_paths(result, wrong_version)

    inconsistent = DependencyGraph(
        roots=(
            RootRequirement(
                input_index=0, name="root", status=RootRequirementStatus.RECOGNIZED
            ),
        ),
        nodes=(
            DependencyGraphNode(
                name="root",
                version="1",
                kind=DependencyKind.ROOT,
                root_names=("root",),
            ),
            DependencyGraphNode(
                name="child",
                version="1",
                kind=DependencyKind.UNATTRIBUTED,
            ),
        ),
        edges=(DependencyEdge(source_name="root", target_name="child"),),
    )
    inconsistent_result = analysis(("root",), (("root", "1"), ("child", "1")))
    with pytest.raises(ValueError, match="attribution is inconsistent"):
        explain_dependency_paths(inconsistent_result, inconsistent)


def test_rejects_missing_root_input_indexes_and_recognized_root_name_mismatch():
    missing_index_result = analysis(
        ("root", "ignored"), (("root", "1"), ("ignored", "1"))
    )
    missing_index_graph = DependencyGraph(
        roots=(
            RootRequirement(
                input_index=0, name="root", status=RootRequirementStatus.RECOGNIZED
            ),
        ),
        nodes=(
            DependencyGraphNode(
                name="root",
                version="1",
                kind=DependencyKind.ROOT,
                root_names=("root",),
            ),
            DependencyGraphNode(
                name="ignored",
                version="1",
                kind=DependencyKind.UNATTRIBUTED,
            ),
        ),
        edges=(),
    )
    with pytest.raises(ValueError, match="input indexes"):
        explain_dependency_paths(missing_index_result, missing_index_graph)

    mismatch_result = analysis(("other",), (("root", "1"), ("other", "1")))
    mismatch_graph = DependencyGraph(
        roots=(
            RootRequirement(
                input_index=0, name="root", status=RootRequirementStatus.RECOGNIZED
            ),
        ),
        nodes=(
            DependencyGraphNode(
                name="root",
                version="1",
                kind=DependencyKind.ROOT,
                root_names=("root",),
            ),
            DependencyGraphNode(
                name="other",
                version="1",
                kind=DependencyKind.UNATTRIBUTED,
            ),
        ),
        edges=(),
    )
    with pytest.raises(ValueError, match="must match analysis inputs"):
        explain_dependency_paths(mismatch_result, mismatch_graph)


def test_rejects_graph_node_name_set_mismatch():
    result = analysis(("root",), (("root", "1"),))
    graph_with_other_node = DependencyGraph(
        roots=(
            RootRequirement(
                input_index=0, name="root", status=RootRequirementStatus.RECOGNIZED
            ),
        ),
        nodes=(
            DependencyGraphNode(
                name="other",
                version="1",
                kind=DependencyKind.UNATTRIBUTED,
            ),
        ),
        edges=(),
    )

    with pytest.raises(ValueError, match="must match"):
        explain_dependency_paths(result, graph_with_other_node)


def test_models_reject_malformed_paths_and_result_rejects_non_edge_unknown_paths_safely():
    with pytest.raises(ValueError, match="simple path"):
        DependencyPath(root_input_index=0, nodes=("root", "root"))
    with pytest.raises(ValueError, match="root_input_index"):
        DependencyPath(root_input_index=-1, nodes=("root",))

    result = analysis(
        ("root @ https://secret.invalid/token",),
        (("root", "1"), ("child", "1"), ("orphan", "1")),
    )
    dependency_graph = graph(
        result,
        ("root", "1", ("child",)),
        ("child", "1", ()),
        ("orphan", "1", ()),
    )
    valid = explain_dependency_paths(result, dependency_graph)
    root = by_name(valid)["root"]
    orphan = by_name(valid)["orphan"]
    unknown = DistributionAttribution(
        node=root.node,
        root_input_indexes=(0,),
        canonical_path=DependencyPath(root_input_index=0, nodes=("root", "unknown")),
    )
    non_edge = DistributionAttribution(
        node=orphan.node,
        root_input_indexes=(0,),
        canonical_path=DependencyPath(root_input_index=0, nodes=("root", "orphan")),
    )
    for replacement in (unknown, non_edge):
        invalid = tuple(
            replacement
            if attribution.node.name == replacement.node.name
            else attribution
            for attribution in valid.attributions
        )
        with pytest.raises(ValueError) as caught:
            ExplainedAnalysisResult(
                analysis=result, graph=dependency_graph, attributions=invalid
            )
        assert "https://secret.invalid/token" not in str(caught.value)


def test_result_is_permutation_stable_and_immutable():
    first_analysis = analysis(("root",), (("z", "1"), ("root", "1"), ("a", "1")))
    first = explain_dependency_paths(
        first_analysis,
        graph(
            first_analysis,
            ("z", "1", ()),
            ("root", "1", ("a",)),
            ("a", "1", ()),
        ),
    )
    second_analysis = analysis(("root",), (("a", "1"), ("z", "1"), ("root", "1")))
    second = explain_dependency_paths(
        second_analysis,
        graph(
            second_analysis,
            ("a", "1", ()),
            ("root", "1", ("a",)),
            ("z", "1", ()),
        ),
    )

    assert first == second
    assert [attribution.node.name for attribution in first.attributions] == [
        "a",
        "root",
        "z",
    ]
    with pytest.raises(FrozenInstanceError):
        cast(Any, first.attributions[0]).node = first.attributions[1].node


def test_explaining_does_not_change_schema_v1_serialization_bytes():
    result = analysis(("root",), (("root", "1"),))
    before = render_analysis_json(result)

    explain_dependency_paths(result, graph(result, ("root", "1", ())))

    assert render_analysis_json(result) == before
