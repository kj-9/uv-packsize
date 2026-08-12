from typing import Any

import pytest

from uv_packsize.dependency_graph import (
    InstalledDistributionMetadata,
    MarkerEnvironment,
    build_dependency_graph,
)
from uv_packsize.dependency_paths import explain_dependency_paths
from uv_packsize.explanation import render_explained_analysis_report
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    DistributionResult,
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


def analysis(
    requirements: tuple[str, ...],
    installed: tuple[tuple[str, str], ...],
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
    )


def explained(
    result: AnalysisResult,
    *metadata: tuple[str, str, tuple[str, ...]],
):
    dependency_graph = build_dependency_graph(
        result,
        tuple(
            InstalledDistributionMetadata(
                name=name, version=version, requires_dist=requires
            )
            for name, version, requires in metadata
        ),
        marker_environment(),
    )
    return explain_dependency_paths(result, dependency_graph)


def test_explanation_preserves_the_exact_ordinary_report_as_a_prefix():
    result = analysis(("root",), (("root", "1"), ("child", "2")))
    explanation = explained(result, ("root", "1", ("child",)), ("child", "2", ()))

    report = render_explained_analysis_report(explanation)

    assert report.startswith(render_analysis_report(result))
    assert report == (
        f"{render_analysis_report(result)}\n\n"
        "--- Requested Roots ---\n"
        "Input  Distribution  Status\n"
        "1  root  recognized\n\n"
        "--- Dependency Attribution ---\n"
        "Distribution  Version  Kind  Shared  Reachable Roots\n"
        "child  2  direct  no  root\n"
        "root  1  root  no  root\n\n"
        "--- Dependency Paths ---\n"
        "Input  Path\n"
        "1  root -> child"
    )


def test_explanation_renders_one_deterministic_path_per_recognized_input_and_node():
    result = analysis(
        ("root-b", "root-a", "Root-B"),
        (("root-a", "1"), ("root-b", "1"), ("shared", "1"), ("leaf", "1")),
    )
    explanation = explained(
        result,
        ("root-a", "1", ("shared",)),
        ("root-b", "1", ("shared",)),
        ("shared", "1", ("leaf",)),
        ("leaf", "1", ()),
    )

    report = render_explained_analysis_report(explanation)

    paths = report.split("--- Dependency Paths ---\nInput  Path\n", 1)[1].splitlines()
    assert paths == [
        "1  root-b -> shared",
        "1  root-b -> shared -> leaf",
        "2  root-a -> shared",
        "2  root-a -> shared -> leaf",
        "3  root-b -> shared",
        "3  root-b -> shared -> leaf",
    ]
    assert "shared  1  direct  yes  root-a, root-b" in report
    assert "root-b -> root-b" not in report


def test_explanation_uses_sanitized_graph_warning_codes_without_secret_inputs():
    secret = "https://private.invalid/very-secret-token"
    result = analysis((f"root @ {secret}",), (("root", "1"),))
    explanation = explained(result, ("root", "1", ("not a requirement @@@",)))

    report = render_explained_analysis_report(explanation)

    assert "Warning: incomplete dependency graph (invalid-requires-dist: 1)." in report
    assert secret not in report
    assert "not a requirement" not in report


def test_explanation_escapes_metadata_control_and_wide_versions():
    result = analysis(("root",), (("root", "v\x1b[31m\u2603"),))
    explanation = explained(result, ("root", "v\x1b[31m\u2603", ()))

    report = render_explained_analysis_report(explanation)

    assert "v?[31m\\u2603" in report
    assert "\x1b" not in report
    assert report.isascii()


@pytest.mark.parametrize("value", [None, object()])
def test_explanation_renderer_rejects_non_explained_results(value: Any):
    with pytest.raises(TypeError, match="ExplainedAnalysisResult"):
        render_explained_analysis_report(value)
