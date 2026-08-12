from dataclasses import fields, replace
from typing import Any, cast

import pytest

from uv_packsize.baseline import Baseline, BaselineDistribution, analysis_result_to_baseline
from uv_packsize.diff import AnalysisDiff, compare_baselines
from uv_packsize.models import (
    AnalysisResult,
    AnalysisWarning,
    BuildPolicy,
    CaseRule,
    DependencyGroupSelection,
    DistributionResult,
    ExistingPrefixContext,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ProjectLockContext,
    ResolutionContext,
    WarningCode,
    WarningTargetKind,
)
from uv_packsize.rich_report import (
    RichAnalysisView,
    RichBuildPolicy,
    RichComparisonView,
    RichDistribution,
    RichDistributionChange,
    RichInputKind,
    project_rich_analysis,
    project_rich_comparison,
    render_rich_analysis_report,
    render_rich_comparison_report,
)


def _file(name: str, size: int) -> FileEntry:
    return FileEntry(
        path=f"private/{name}.py",
        canonical_identity=f"private/{name}.py",
        logical_bytes=size,
        category=FileCategory.PYTHON,
        origin=FileOrigin.RECORD,
    )


def _fresh_result(*, warning: AnalysisWarning | None = None) -> AnalysisResult:
    return AnalysisResult(
        context=ResolutionContext(
            requirements=("private-package @ https://token@example.invalid/wheel",),
            python_version="3.14.0",
            platform="linux",
            architecture="x86_64",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=False,
        ),
        distributions=(
            DistributionResult(
                name="zeta", version="secret-version", files=(_file("zeta", 1),)
            ),
            DistributionResult(
                name="alpha", version="secret-version", files=(_file("alpha", 10),)
            ),
            DistributionResult(
                name="beta", version="secret-version", files=(_file("beta", 5),)
            ),
        ),
        warnings=() if warning is None else (warning,),
    )


def test_analysis_projection_is_redacted_canonical_and_renders_exact_ascii_summary():
    result = _fresh_result()

    view = project_rich_analysis(result)

    assert view.input_kind is RichInputKind.FRESH_INSTALL
    assert view.build_policy is RichBuildPolicy.WHEEL_ONLY
    assert view.distribution_count == 3
    assert [item.name for item in view.top_distributions] == ["alpha", "beta", "zeta"]
    assert render_rich_analysis_report(view) == (
        "--- Rich Analysis Summary ---\n"
        "Input kind: fresh-install\n"
        "Build policy: wheel-only\n"
        "Completeness: complete\n"
        "Warnings: none\n"
        "Distributions: 3\n"
        "Canonical global size: 16 B\n"
        "Distribution-owned aggregate: 16 B\n\n"
        "--- Top Distributions (Showing 3 of 3) ---\n"
        "Distribution  Owned size\n"
        "------------  ----------\n"
        "alpha               10 B\n"
        "beta                 5 B\n"
        "zeta                 1 B"
    )
    rendered = render_rich_analysis_report(view)
    assert rendered.isascii()
    for secret in ("private-package", "token@", "private/", "secret-version"):
        assert secret not in rendered
        assert secret not in repr(view)
    assert {field.name for field in fields(view)} == {
        "input_kind",
        "build_policy",
        "completeness",
        "warning_code_counts",
        "distribution_count",
        "canonical_global_logical_bytes",
        "distribution_owned_aggregate_bytes",
        "top_distributions",
    }


def test_analysis_projection_reports_incomplete_warning_and_nonreconciling_aggregate():
    shared = _file("shared", 3)
    result = AnalysisResult(
        context=_fresh_result().context,
        distributions=(
            DistributionResult(
                name="alpha",
                version="1",
                files=(shared,),
                warnings=(
                    AnalysisWarning(
                        code=WarningCode.MISSING_RECORD,
                        target_kind=WarningTargetKind.DISTRIBUTION,
                        target_identity="alpha==1",
                    ),
                ),
            ),
            DistributionResult(name="beta", version="1", files=(shared,)),
        ),
        warnings=(),
    )

    view = project_rich_analysis(result)
    report = render_rich_analysis_report(view)

    assert view.warning_code_counts == (
        ("duplicate-ownership", 1),
        ("missing-record", 1),
    )
    assert "Completeness: incomplete" in report
    assert "Warnings: duplicate-ownership: 1, missing-record: 1" in report
    assert "aggregate differs from canonical global by +3 B" in report
    assert "alpha==1" not in report


def test_analysis_projection_limits_top_rows_to_five_with_total_count():
    result = AnalysisResult(
        context=_fresh_result().context,
        distributions=tuple(
            DistributionResult(
                name=name,
                version="1",
                files=(_file(name, size),),
            )
            for name, size in (
                ("alpha", 1),
                ("beta", 6),
                ("gamma", 5),
                ("delta", 4),
                ("epsilon", 3),
                ("zeta", 2),
            )
        ),
    )

    view = project_rich_analysis(result)
    report = render_rich_analysis_report(view)

    assert [item.name for item in view.top_distributions] == [
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
    ]
    assert "Top Distributions (Showing 5 of 6)" in report
    assert "alpha" not in report


def test_existing_prefix_projection_marks_build_policy_unknown():
    result = AnalysisResult(
        context=ExistingPrefixContext(
            path_flavor=PathFlavor.POSIX, case_rule=CaseRule.SENSITIVE
        ),
        distributions=(),
    )

    view = project_rich_analysis(result)

    assert (view.input_kind, view.build_policy) == (
        RichInputKind.EXISTING_PREFIX,
        RichBuildPolicy.UNKNOWN,
    )
    assert "Showing 0 of 0" in render_rich_analysis_report(view)


def test_comparison_projection_has_top_changes_without_versions_or_lock_identity():
    before = analysis_result_to_baseline(_fresh_result())
    current = replace(
        before,
        global_logical_bytes=30,
        distributions=(
            BaselineDistribution(
                name="alpha", version="other-secret", logical_bytes=20
            ),
            BaselineDistribution(name="beta", version="other-secret", logical_bytes=5),
            BaselineDistribution(name="new", version="other-secret", logical_bytes=5),
        ),
    )

    view = project_rich_comparison(compare_baselines(before, current))
    report = render_rich_comparison_report(view)

    assert view.lock_changed is None
    assert view.distribution_change_count == 3
    assert [item.name for item in view.top_changes] == ["alpha", "new", "zeta"]
    assert "Top Changes (Showing 3 of 3)" in report
    assert "Canonical global change: +14 B" in report
    assert "Distribution-owned aggregate change: +14 B" in report
    assert "Lock changed:" not in report
    assert "secret-version" not in report
    assert "other-secret" not in report


def test_project_comparison_exposes_only_the_lock_changed_boolean():
    def result(lock_identity: str) -> AnalysisResult:
        return AnalysisResult(
            context=ProjectLockContext(
                root_package="private-project",
                workspace_member=None,
                dependency_group_selection=DependencyGroupSelection.NONE,
                dependency_groups=(),
                extras=(),
                python_version="3.14.0",
                platform="linux",
                architecture="x86_64",
                path_flavor=PathFlavor.POSIX,
                case_rule=CaseRule.SENSITIVE,
                uv_version="0.11.3",
                build_policy=BuildPolicy.WHEEL_ONLY,
                compile_bytecode=False,
                lock_identity=lock_identity,
            ),
            distributions=(),
        )

    before = analysis_result_to_baseline(result("a" * 64))
    current = analysis_result_to_baseline(result("b" * 64))
    view = project_rich_comparison(compare_baselines(before, current))
    report = render_rich_comparison_report(view)

    assert view.lock_changed is True
    assert "Lock changed: yes" in report
    assert "a" * 64 not in report
    assert "b" * 64 not in report
    assert "private-project" not in report


def test_view_renderers_reject_forged_or_inconsistent_views():
    valid = project_rich_analysis(_fresh_result())
    forged = object.__new__(RichAnalysisView)
    object.__setattr__(forged, "input_kind", RichInputKind.FRESH_INSTALL)
    object.__setattr__(forged, "build_policy", RichBuildPolicy.WHEEL_ONLY)
    object.__setattr__(forged, "completeness", valid.completeness)
    object.__setattr__(forged, "warning_code_counts", ())
    object.__setattr__(forged, "distribution_count", 2)
    object.__setattr__(forged, "canonical_global_logical_bytes", 1)
    object.__setattr__(forged, "distribution_owned_aggregate_bytes", 1)
    object.__setattr__(forged, "top_distributions", ())

    with pytest.raises(ValueError, match="rich analysis view is invalid"):
        render_rich_analysis_report(forged)
    with pytest.raises(TypeError, match="RichComparisonView"):
        render_rich_comparison_report(cast(Any, valid))
    with pytest.raises(ValueError, match="lock_changed"):
        RichComparisonView(
            baseline=valid,
            current=valid,
            distribution_change_count=0,
            top_changes=(),
            lock_changed=False,
        )
    with pytest.raises(ValueError, match="valid distribution name"):
        RichDistribution(name="bad name", owned_logical_bytes=1)


def test_view_invariants_reject_unreconciled_top_rows_and_changes():
    item = RichDistribution(name="alpha", owned_logical_bytes=1)
    with pytest.raises(ValueError, match="canonical global bytes"):
        RichAnalysisView(
            input_kind=RichInputKind.FRESH_INSTALL,
            build_policy=RichBuildPolicy.WHEEL_ONLY,
            completeness=project_rich_analysis(_fresh_result()).completeness,
            warning_code_counts=(),
            distribution_count=1,
            canonical_global_logical_bytes=2,
            distribution_owned_aggregate_bytes=1,
            top_distributions=(item,),
        )


def test_analysis_projection_rejects_forged_nested_source_models():
    valid = _fresh_result()
    forged_context = object.__new__(ResolutionContext)
    for name, value in (
        ("requirements", ("root",)),
        ("python_version", " invalid"),
        ("platform", "linux"),
        ("architecture", "x86_64"),
        ("path_flavor", PathFlavor.POSIX),
        ("case_rule", CaseRule.SENSITIVE),
        ("uv_version", "0.11.3"),
        ("build_policy", BuildPolicy.WHEEL_ONLY),
        ("compile_bytecode", False),
        ("extras", ()),
        ("index_identifiers", ()),
        ("resolution_strategy", "highest"),
    ):
        object.__setattr__(forged_context, name, value)
    with pytest.raises(ValueError, match="analysis result is invalid"):
        project_rich_analysis(
            AnalysisResult(
                context=forged_context,
                distributions=valid.distributions,
            )
        )


def test_comparison_projection_rejects_forged_nested_baseline_tree():
    source = _fresh_result()
    valid_diff = compare_baselines(
        analysis_result_to_baseline(source), analysis_result_to_baseline(source)
    )
    forged_baseline = object.__new__(Baseline)
    forged_diff = object.__new__(AnalysisDiff)
    for name in (
        "current",
        "distributions",
        "global_logical_bytes_delta",
        "distribution_logical_bytes_delta",
        "baseline_completeness",
        "current_completeness",
        "completeness",
    ):
        object.__setattr__(forged_diff, name, getattr(valid_diff, name))
    object.__setattr__(forged_diff, "baseline", forged_baseline)

    with pytest.raises(ValueError, match="analysis diff is invalid"):
        project_rich_comparison(forged_diff)

    forged_file = object.__new__(FileEntry)
    for name, value in (
        ("path", "/private/invalid.py"),
        ("canonical_identity", "private/valid.py"),
        ("logical_bytes", 1),
        ("category", FileCategory.PYTHON),
        ("origin", FileOrigin.RECORD),
        ("symlink_target", None),
    ):
        object.__setattr__(forged_file, name, value)
    with pytest.raises(ValueError, match="analysis result is invalid"):
        project_rich_analysis(
            AnalysisResult(
                context=valid.context,
                distributions=(
                    DistributionResult(name="alpha", version="1", files=(forged_file,)),
                ),
            )
        )

    forged_warning = object.__new__(AnalysisWarning)
    object.__setattr__(forged_warning, "code", WarningCode.MISSING_FILE)
    object.__setattr__(forged_warning, "target_kind", WarningTargetKind.DISTRIBUTION)
    object.__setattr__(forged_warning, "target_identity", "alpha==1")
    with pytest.raises(ValueError, match="analysis result is invalid"):
        project_rich_analysis(
            AnalysisResult(
                context=valid.context,
                distributions=(
                    DistributionResult(
                        name="alpha",
                        version="1",
                        files=(),
                        warnings=(forged_warning,),
                    ),
                ),
            )
        )

    valid = project_rich_analysis(_fresh_result())
    with pytest.raises(ValueError, match="top changes must reconcile"):
        RichComparisonView(
            baseline=valid,
            current=valid,
            distribution_change_count=1,
            top_changes=(
                RichDistributionChange(
                    name="alpha",
                    baseline_owned_logical_bytes=0,
                    current_owned_logical_bytes=1,
                ),
            ),
            lock_changed=None,
        )
