"""Pure, redacted rich-summary projections for analysis and comparison results.

This module is intentionally not connected to Click.  Its views retain only
small, display-safe measurement facts so a later opt-in CLI surface cannot
accidentally expose raw requirements, paths, versions, lock identities, or
context fingerprints.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from uv_packsize.baseline import (
    Baseline,
    BaselineDistribution,
    BaselineDuplicateOwnershipSummary,
    BaselineExistingPrefixContext,
    BaselineMeasurement,
    BaselineProjectLockContext,
    BaselineRequirement,
    BaselineResolutionContext,
    BaselineWarningSummary,
)
from uv_packsize.diff import AnalysisDiff, project_lock_changed
from uv_packsize.models import (
    AnalysisResult,
    AnalysisWarning,
    Completeness,
    DistributionResult,
    ExistingPrefixContext,
    FileEntry,
    ProjectLockContext,
    ResolutionContext,
    WarningCode,
    normalize_distribution_name,
)
from uv_packsize.render import format_size
from uv_packsize.text_render import render_table

_TOP_LIMIT = 5


class RichInputKind(str, Enum):
    """The closed input kinds that a redacted rich report can describe."""

    FRESH_INSTALL = "fresh-install"
    PROJECT_LOCK = "project-lock"
    EXISTING_PREFIX = "existing-prefix"


class RichBuildPolicy(str, Enum):
    """The build policy, including the deliberately unknown prefix case."""

    WHEEL_ONLY = "wheel-only"
    ALLOW_BUILD = "allow-build"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class RichDistribution:
    """One redacted distribution-size row without its resolved version."""

    name: str
    owned_logical_bytes: int

    def __post_init__(self) -> None:
        if normalize_distribution_name(self.name) != self.name:
            raise ValueError("name must be a normalized distribution name")
        _nonnegative(self.owned_logical_bytes, "owned_logical_bytes")


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class RichDistributionChange:
    """A redacted per-distribution comparison row without either version."""

    name: str
    baseline_owned_logical_bytes: int
    current_owned_logical_bytes: int

    def __post_init__(self) -> None:
        if normalize_distribution_name(self.name) != self.name:
            raise ValueError("name must be a normalized distribution name")
        _nonnegative(self.baseline_owned_logical_bytes, "baseline_owned_logical_bytes")
        _nonnegative(self.current_owned_logical_bytes, "current_owned_logical_bytes")
        if self.logical_bytes_delta == 0:
            raise ValueError("top changes must have a non-zero delta")

    @property
    def logical_bytes_delta(self) -> int:
        return self.current_owned_logical_bytes - self.baseline_owned_logical_bytes


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class RichAnalysisView:
    """Redacted, immutable facts for one completed analysis."""

    input_kind: RichInputKind
    build_policy: RichBuildPolicy
    completeness: Completeness
    warning_code_counts: tuple[tuple[str, int], ...]
    distribution_count: int
    canonical_global_logical_bytes: int
    distribution_owned_aggregate_bytes: int
    top_distributions: tuple[RichDistribution, ...]

    def __post_init__(self) -> None:
        _validate_analysis_view(self)


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class RichComparisonView:
    """Redacted, immutable facts for one compatible baseline comparison."""

    baseline: RichAnalysisView
    current: RichAnalysisView
    distribution_change_count: int
    top_changes: tuple[RichDistributionChange, ...]
    lock_changed: bool | None

    def __post_init__(self) -> None:
        _validate_comparison_view(self)


def project_rich_analysis(result: AnalysisResult) -> RichAnalysisView:
    """Project an exact validated analysis result without retaining raw inputs."""

    if type(result) is not AnalysisResult:
        raise TypeError("result must be an exact AnalysisResult")
    if not _is_valid_analysis_result(result):
        raise ValueError("analysis result is invalid") from None

    input_kind, build_policy = _analysis_context_summary(result)
    warning_counts: dict[str, int] = {}
    for warning in (
        *result.warnings,
        *(
            warning
            for distribution in result.distributions
            for warning in distribution.warnings
        ),
    ):
        warning_counts[warning.code.value] = (
            warning_counts.get(warning.code.value, 0) + 1
        )
    distributions = tuple(
        RichDistribution(
            name=distribution.name,
            owned_logical_bytes=distribution.total_logical_bytes,
        )
        for distribution in result.distributions
    )
    return RichAnalysisView(
        input_kind=input_kind,
        build_policy=build_policy,
        completeness=result.completeness,
        warning_code_counts=tuple(sorted(warning_counts.items())),
        distribution_count=len(distributions),
        canonical_global_logical_bytes=result.total_logical_bytes,
        distribution_owned_aggregate_bytes=sum(
            distribution.owned_logical_bytes for distribution in distributions
        ),
        top_distributions=_top_distributions(distributions),
    )


def project_rich_comparison(diff: AnalysisDiff) -> RichComparisonView:
    """Project an exact validated comparison without retaining baseline contents."""

    if type(diff) is not AnalysisDiff:
        raise TypeError("diff must be an exact AnalysisDiff")
    if not _is_valid_analysis_diff(diff):
        raise ValueError("analysis diff is invalid") from None

    baseline = _rich_view_from_baseline(diff.baseline)
    current = _rich_view_from_baseline(diff.current)
    changes = tuple(
        RichDistributionChange(
            name=item.name,
            baseline_owned_logical_bytes=item.baseline_logical_bytes,
            current_owned_logical_bytes=item.current_logical_bytes,
        )
        for item in diff.distributions
        if item.logical_bytes_delta
    )
    return RichComparisonView(
        baseline=baseline,
        current=current,
        distribution_change_count=len(changes),
        top_changes=tuple(
            sorted(
                changes, key=lambda item: (-abs(item.logical_bytes_delta), item.name)
            )[:_TOP_LIMIT]
        ),
        lock_changed=(
            project_lock_changed(diff.baseline, diff.current)
            if baseline.input_kind is RichInputKind.PROJECT_LOCK
            else None
        ),
    )


def render_rich_analysis_report(view: RichAnalysisView) -> str:
    """Render an exact, terminal-safe ASCII summary for one analysis view."""

    _require_analysis_view(view)
    lines = [
        "--- Rich Analysis Summary ---",
        f"Input kind: {view.input_kind.value}",
        f"Build policy: {view.build_policy.value}",
        f"Completeness: {view.completeness.value}",
        "Warnings: " + _render_warnings(view.warning_code_counts),
        f"Distributions: {view.distribution_count}",
        "Canonical global size: " + format_size(view.canonical_global_logical_bytes),
        "Distribution-owned aggregate: "
        + format_size(view.distribution_owned_aggregate_bytes),
    ]
    lines.extend(_aggregate_note(view))
    lines.extend(("", _render_top_distributions(view)))
    return "\n".join(lines)


def render_rich_comparison_report(view: RichComparisonView) -> str:
    """Render an exact, terminal-safe ASCII summary for one comparison view."""

    _require_comparison_view(view)
    baseline, current = view.baseline, view.current
    lines = [
        "--- Rich Comparison Summary ---",
        f"Input kind: {current.input_kind.value}",
        f"Build policy: {current.build_policy.value}",
        f"Baseline completeness: {baseline.completeness.value}",
        "Baseline warnings: " + _render_warnings(baseline.warning_code_counts),
        f"Baseline distributions: {baseline.distribution_count}",
        f"Current completeness: {current.completeness.value}",
        "Current warnings: " + _render_warnings(current.warning_code_counts),
        f"Current distributions: {current.distribution_count}",
        "Canonical global size: "
        + format_size(baseline.canonical_global_logical_bytes)
        + " -> "
        + format_size(current.canonical_global_logical_bytes),
        "Canonical global change: "
        + _format_signed_size(
            current.canonical_global_logical_bytes
            - baseline.canonical_global_logical_bytes
        ),
        "Distribution-owned aggregate: "
        + format_size(baseline.distribution_owned_aggregate_bytes)
        + " -> "
        + format_size(current.distribution_owned_aggregate_bytes),
        "Distribution-owned aggregate change: "
        + _format_signed_size(
            current.distribution_owned_aggregate_bytes
            - baseline.distribution_owned_aggregate_bytes
        ),
    ]
    if view.lock_changed is not None:
        lines.append("Lock changed: " + ("yes" if view.lock_changed else "no"))
    lines.extend(_comparison_aggregate_notes(view))
    lines.extend(("", _render_top_changes(view)))
    return "\n".join(lines)


def _analysis_context_summary(
    result: AnalysisResult,
) -> tuple[RichInputKind, RichBuildPolicy]:
    context = result.context
    if type(context) is ResolutionContext:
        return RichInputKind.FRESH_INSTALL, RichBuildPolicy(context.build_policy.value)
    if type(context) is ProjectLockContext:
        return RichInputKind.PROJECT_LOCK, RichBuildPolicy(context.build_policy.value)
    assert type(context) is ExistingPrefixContext
    return RichInputKind.EXISTING_PREFIX, RichBuildPolicy.UNKNOWN


def _is_valid_analysis_result(result: AnalysisResult) -> bool:
    """Rebuild every nested model to reject forged frozen instances."""

    try:
        supplied_warnings = tuple(
            _clone_analysis_warning(warning)
            for warning in result.warnings
            if warning.code is not WarningCode.DUPLICATE_OWNERSHIP
        )
        return (
            AnalysisResult(
                context=_clone_analysis_context(result.context),
                distributions=tuple(
                    _clone_distribution(distribution)
                    for distribution in result.distributions
                ),
                warnings=supplied_warnings,
            )
            == result
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _clone_analysis_context(
    context: ResolutionContext | ExistingPrefixContext | ProjectLockContext,
) -> ResolutionContext | ExistingPrefixContext | ProjectLockContext:
    if type(context) is ResolutionContext:
        return ResolutionContext(
            requirements=context.requirements,
            python_version=context.python_version,
            platform=context.platform,
            architecture=context.architecture,
            path_flavor=context.path_flavor,
            case_rule=context.case_rule,
            uv_version=context.uv_version,
            build_policy=context.build_policy,
            compile_bytecode=context.compile_bytecode,
            extras=context.extras,
            index_identifiers=context.index_identifiers,
            resolution_strategy=context.resolution_strategy,
        )
    if type(context) is ExistingPrefixContext:
        return ExistingPrefixContext(
            path_flavor=context.path_flavor,
            case_rule=context.case_rule,
            python_version=context.python_version,
            platform=context.platform,
            architecture=context.architecture,
        )
    if type(context) is ProjectLockContext:
        return ProjectLockContext(
            root_package=context.root_package,
            workspace_member=context.workspace_member,
            dependency_group_selection=context.dependency_group_selection,
            dependency_groups=context.dependency_groups,
            extras=context.extras,
            python_version=context.python_version,
            platform=context.platform,
            architecture=context.architecture,
            path_flavor=context.path_flavor,
            case_rule=context.case_rule,
            uv_version=context.uv_version,
            build_policy=context.build_policy,
            compile_bytecode=context.compile_bytecode,
            resolution_strategy=context.resolution_strategy,
            lock_identity=context.lock_identity,
        )
    raise TypeError("analysis context must have an exact supported type")


def _clone_distribution(distribution: DistributionResult) -> DistributionResult:
    if type(distribution) is not DistributionResult:
        raise TypeError("distribution must be an exact DistributionResult")
    return DistributionResult(
        name=distribution.name,
        version=distribution.version,
        files=tuple(_clone_file_entry(item) for item in distribution.files),
        warnings=tuple(_clone_analysis_warning(item) for item in distribution.warnings),
    )


def _clone_file_entry(entry: FileEntry) -> FileEntry:
    if type(entry) is not FileEntry:
        raise TypeError("file entry must be an exact FileEntry")
    return FileEntry(
        path=entry.path,
        canonical_identity=entry.canonical_identity,
        logical_bytes=entry.logical_bytes,
        category=entry.category,
        origin=entry.origin,
        symlink_target=entry.symlink_target,
    )


def _clone_analysis_warning(warning: AnalysisWarning) -> AnalysisWarning:
    if type(warning) is not AnalysisWarning:
        raise TypeError("analysis warning must be an exact AnalysisWarning")
    return AnalysisWarning(
        code=warning.code,
        target_kind=warning.target_kind,
        target_identity=warning.target_identity,
    )


def _is_valid_analysis_diff(diff: AnalysisDiff) -> bool:
    """Reject forged baseline trees before reusing the diff's invariants."""

    if not _has_exact_baseline_tree(diff.baseline) or not _has_exact_baseline_tree(
        diff.current
    ):
        return False
    try:
        diff.__post_init__()
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _has_exact_baseline_tree(baseline: object) -> bool:
    try:
        if type(baseline) is not Baseline:
            return False
        if not all(
            (
                type(baseline.measurement) is BaselineMeasurement,
                type(baseline.warnings) is BaselineWarningSummary,
                type(baseline.duplicate_ownership) is BaselineDuplicateOwnershipSummary,
                isinstance(baseline.distributions, tuple),
                all(
                    type(item) is BaselineDistribution
                    for item in baseline.distributions
                ),
            )
        ):
            return False
        if baseline.schema_version == 1:
            context = baseline.resolution_context
            return (
                type(context) is BaselineResolutionContext
                and isinstance(context.requirements, tuple)
                and all(
                    type(item) is BaselineRequirement for item in context.requirements
                )
            )
        if baseline.schema_version == 3:
            return type(baseline.project_lock_context) is BaselineProjectLockContext
        return (
            baseline.schema_version == 2
            and type(baseline.existing_prefix_context) is BaselineExistingPrefixContext
        )
    except (AttributeError, TypeError):
        return False


def _rich_view_from_baseline(baseline: Baseline) -> RichAnalysisView:
    # ``AnalysisDiff.__post_init__`` has already revalidated this trusted source.
    input_kind = RichInputKind(baseline.input_kind)
    if input_kind is RichInputKind.FRESH_INSTALL:
        assert baseline.resolution_context is not None
        policy = RichBuildPolicy(baseline.resolution_context.build_policy)
    else:
        assert baseline.project_lock_context is not None
        policy = RichBuildPolicy(baseline.project_lock_context.build_policy)
    distributions = tuple(
        RichDistribution(name=item.name, owned_logical_bytes=item.logical_bytes)
        for item in baseline.distributions
    )
    return RichAnalysisView(
        input_kind=input_kind,
        build_policy=policy,
        completeness=Completeness(baseline.warnings.completeness),
        warning_code_counts=baseline.warnings.warning_code_counts,
        distribution_count=len(distributions),
        canonical_global_logical_bytes=baseline.global_logical_bytes,
        distribution_owned_aggregate_bytes=sum(
            item.owned_logical_bytes for item in distributions
        ),
        top_distributions=_top_distributions(distributions),
    )


def _top_distributions(
    distributions: tuple[RichDistribution, ...],
) -> tuple[RichDistribution, ...]:
    return tuple(
        sorted(distributions, key=lambda item: (-item.owned_logical_bytes, item.name))[
            :_TOP_LIMIT
        ]
    )


def _validate_analysis_view(view: RichAnalysisView) -> None:
    if type(view.input_kind) is not RichInputKind:
        raise TypeError("input_kind must be RichInputKind")
    if type(view.build_policy) is not RichBuildPolicy:
        raise TypeError("build_policy must be RichBuildPolicy")
    if type(view.completeness) is not Completeness:
        raise TypeError("completeness must be Completeness")
    if view.input_kind is RichInputKind.EXISTING_PREFIX:
        if view.build_policy is not RichBuildPolicy.UNKNOWN:
            raise ValueError("existing-prefix build policy must be unknown")
    elif view.build_policy is RichBuildPolicy.UNKNOWN:
        raise ValueError("fresh/project build policy must be known")
    _validate_warning_counts(view.warning_code_counts, view.completeness)
    _nonnegative(view.distribution_count, "distribution_count")
    _nonnegative(view.canonical_global_logical_bytes, "canonical_global_logical_bytes")
    _nonnegative(
        view.distribution_owned_aggregate_bytes,
        "distribution_owned_aggregate_bytes",
    )
    if view.canonical_global_logical_bytes > view.distribution_owned_aggregate_bytes:
        raise ValueError("canonical global bytes cannot exceed owned aggregate")
    _validate_top_distributions(view)


def _validate_top_distributions(view: RichAnalysisView) -> None:
    if not isinstance(view.top_distributions, tuple):
        raise TypeError("top_distributions must be a tuple")
    if len(view.top_distributions) != min(_TOP_LIMIT, view.distribution_count):
        raise ValueError("top_distributions must fill the display limit")
    if any(type(item) is not RichDistribution for item in view.top_distributions):
        raise TypeError("top_distributions must contain exact RichDistribution")
    for item in view.top_distributions:
        item.__post_init__()
    if len({item.name for item in view.top_distributions}) != len(
        view.top_distributions
    ):
        raise ValueError("top_distributions must not repeat names")
    if any(
        item.owned_logical_bytes > view.distribution_owned_aggregate_bytes
        for item in view.top_distributions
    ):
        raise ValueError("top distribution cannot exceed owned aggregate")
    if (
        view.distribution_count <= _TOP_LIMIT
        and sum(item.owned_logical_bytes for item in view.top_distributions)
        != view.distribution_owned_aggregate_bytes
    ):
        raise ValueError("top distributions must reconcile with owned aggregate")
    expected = tuple(
        sorted(
            view.top_distributions,
            key=lambda item: (-item.owned_logical_bytes, item.name),
        )
    )
    if view.top_distributions != expected:
        raise ValueError("top_distributions must use canonical order")


def _validate_comparison_view(view: RichComparisonView) -> None:
    _require_analysis_view(view.baseline)
    _require_analysis_view(view.current)
    if view.baseline.input_kind is RichInputKind.EXISTING_PREFIX:
        raise ValueError("existing-prefix comparisons are unsupported")
    if (
        view.baseline.input_kind != view.current.input_kind
        or view.baseline.build_policy != view.current.build_policy
    ):
        raise ValueError("comparison views must have matching input conditions")
    expected_lock_kind = view.current.input_kind is RichInputKind.PROJECT_LOCK
    if expected_lock_kind != isinstance(view.lock_changed, bool):
        raise ValueError("lock_changed is defined only for project-lock views")
    if not isinstance(view.top_changes, tuple):
        raise TypeError("top_changes must be a tuple")
    _nonnegative(view.distribution_change_count, "distribution_change_count")
    if len(view.top_changes) != min(_TOP_LIMIT, view.distribution_change_count):
        raise ValueError("top_changes must fill the display limit")
    if any(type(item) is not RichDistributionChange for item in view.top_changes):
        raise TypeError("top_changes must contain exact RichDistributionChange")
    for item in view.top_changes:
        item.__post_init__()
    if len({item.name for item in view.top_changes}) != len(view.top_changes):
        raise ValueError("top_changes must not repeat names")
    expected = tuple(
        sorted(
            view.top_changes,
            key=lambda item: (-abs(item.logical_bytes_delta), item.name),
        )
    )
    if view.top_changes != expected:
        raise ValueError("top_changes must use canonical order")
    if view.distribution_change_count <= _TOP_LIMIT and sum(
        item.logical_bytes_delta for item in view.top_changes
    ) != (
        view.current.distribution_owned_aggregate_bytes
        - view.baseline.distribution_owned_aggregate_bytes
    ):
        raise ValueError("top changes must reconcile with owned aggregate change")


def _require_analysis_view(view: object) -> RichAnalysisView:
    if type(view) is not RichAnalysisView:
        raise TypeError("view must be an exact RichAnalysisView")
    try:
        view.__post_init__()
    except (AttributeError, TypeError, ValueError):
        raise ValueError("rich analysis view is invalid") from None
    return view


def _require_comparison_view(view: object) -> RichComparisonView:
    if type(view) is not RichComparisonView:
        raise TypeError("view must be an exact RichComparisonView")
    try:
        view.__post_init__()
    except (AttributeError, TypeError, ValueError):
        raise ValueError("rich comparison view is invalid") from None
    return view


def _validate_warning_counts(
    counts: tuple[tuple[str, int], ...], completeness: Completeness
) -> None:
    if not isinstance(counts, tuple):
        raise TypeError("warning_code_counts must be a tuple")
    codes: list[str] = []
    incomplete = False
    for item in counts:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("warning_code_counts must contain pairs")
        code, count = item
        try:
            warning = WarningCode(code)
        except (TypeError, ValueError):
            raise ValueError("warning_code_counts contains an invalid code") from None
        _nonnegative(count, "warning count")
        if count == 0:
            raise ValueError("warning count must be positive")
        codes.append(code)
        incomplete = incomplete or warning.causes_incomplete_result
    if codes != sorted(codes) or len(codes) != len(set(codes)):
        raise ValueError("warning_code_counts must be canonical")
    expected = Completeness.INCOMPLETE if incomplete else Completeness.COMPLETE
    if completeness is not expected:
        raise ValueError("completeness must match warning codes")


def _nonnegative(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")


def _render_warnings(counts: tuple[tuple[str, int], ...]) -> str:
    return ", ".join(f"{code}: {count}" for code, count in counts) or "none"


def _aggregate_note(view: RichAnalysisView) -> tuple[str, ...]:
    difference = (
        view.distribution_owned_aggregate_bytes - view.canonical_global_logical_bytes
    )
    if difference == 0:
        return ()
    return (
        "Note: aggregate differs from canonical global by "
        + _format_signed_size(difference)
        + "; duplicate-owned files are counted once globally.",
    )


def _comparison_aggregate_notes(view: RichComparisonView) -> tuple[str, ...]:
    notes = []
    for label, side in (("baseline", view.baseline), ("current", view.current)):
        difference = (
            side.distribution_owned_aggregate_bytes
            - side.canonical_global_logical_bytes
        )
        if difference:
            notes.append(
                f"Note: {label} aggregate differs from canonical global by "
                + _format_signed_size(difference)
                + "; duplicate-owned files are counted once globally."
            )
    return tuple(notes)


def _render_top_distributions(view: RichAnalysisView) -> str:
    heading = (
        "--- Top Distributions "
        f"(Showing {len(view.top_distributions)} of {view.distribution_count}) ---"
    )
    if not view.top_distributions:
        return heading + "\nNo distributions to display."
    return "\n".join(
        (
            heading,
            *render_table(
                ("Distribution", "Owned size"),
                tuple(
                    (item.name, format_size(item.owned_logical_bytes))
                    for item in view.top_distributions
                ),
                (1,),
            ),
        )
    )


def _render_top_changes(view: RichComparisonView) -> str:
    heading = (
        "--- Top Changes "
        f"(Showing {len(view.top_changes)} of {view.distribution_change_count}) ---"
    )
    if not view.top_changes:
        return heading + "\nNo distribution changes."
    return "\n".join(
        (
            heading,
            *render_table(
                ("Distribution", "Baseline owned", "Current owned", "Change"),
                tuple(
                    (
                        item.name,
                        format_size(item.baseline_owned_logical_bytes),
                        format_size(item.current_owned_logical_bytes),
                        _format_signed_size(item.logical_bytes_delta),
                    )
                    for item in view.top_changes
                ),
                (1, 2, 3),
            ),
        )
    )


def _format_signed_size(value: int) -> str:
    return (
        "0 B" if value == 0 else ("+" if value > 0 else "-") + format_size(abs(value))
    )
