"""Pure, safe baseline comparison models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import cast

from .baseline import (
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
from .models import Completeness, normalize_distribution_name

MAX_BASELINE_INTEGER = (1 << 63) - 1
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_INDEX_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WARNING_CODES = frozenset(
    {
        "duplicate-ownership",
        "duplicate-record-entry",
        "filesystem-error",
        "filesystem-layout-error",
        "invalid-record",
        "invalid-record-path",
        "invalid-metadata",
        "missing-file",
        "missing-metadata",
        "missing-record",
        "missing-record-self-entry",
        "record-path-outside-prefix",
        "unsupported-file-type",
    }
)
_INCOMPLETE_WARNING_CODES = _WARNING_CODES - {
    "duplicate-ownership",
    "duplicate-record-entry",
}


class DistributionChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    VERSION_CHANGED = "version-changed"
    UNCHANGED = "unchanged"


class ComparisonIncompatibilityReason(str, Enum):
    UNSUPPORTED_SCHEMA = "unsupported-schema"
    MEASUREMENT_MISMATCH = "measurement-mismatch"
    CONTEXT_MISMATCH = "context-mismatch"
    UNSUPPORTED_EXISTING_PREFIX = "unsupported-existing-prefix"


class IncompatibleComparisonError(ValueError):
    """A comparison failure whose message deliberately contains no input data."""

    def __init__(self, reason: ComparisonIncompatibilityReason) -> None:
        self.reason = reason
        super().__init__(f"Baselines cannot be compared ({reason.value}).")


def _project_compatibility_context(
    context: BaselineProjectLockContext,
) -> tuple[object, ...]:
    """Return project comparison inputs while deliberately excluding lock bytes."""

    return (
        context.root_package,
        context.workspace_member,
        context.dependency_group_selection,
        context.dependency_groups,
        context.extras,
        context.python_version_fingerprint,
        context.platform_fingerprint,
        context.architecture_fingerprint,
        context.path_flavor,
        context.case_rule,
        context.uv_version_fingerprint,
        context.build_policy,
        context.compile_bytecode,
        context.resolution_strategy_fingerprint,
    )


def project_lock_changed(baseline: Baseline, current: Baseline) -> bool:
    """Whether comparable project-lock baselines were made from different locks."""

    _validate_baseline(baseline)
    _validate_baseline(current)
    if baseline.schema_version != 3 or current.schema_version != 3:
        raise TypeError("lock change is defined only for schema v3 baselines")
    left, right = baseline.project_lock_context, current.project_lock_context
    if not isinstance(left, BaselineProjectLockContext) or not isinstance(
        right, BaselineProjectLockContext
    ):
        raise TypeError("project baselines require project lock contexts")
    return left.lock_identity != right.lock_identity


def _nonnegative(value: object, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > MAX_BASELINE_INTEGER
    ):
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _signed_delta(value: object, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -MAX_BASELINE_INTEGER <= value <= MAX_BASELINE_INTEGER
    ):
        raise ValueError(f"{field} must be a signed baseline integer")
    return value


def _safe_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _fingerprint(value: object) -> None:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise ValueError("resolution_context fingerprint is invalid")


def _validate_requirement(item: object, index: int) -> None:  # noqa: PLR0912
    if not isinstance(item, BaselineRequirement):
        raise TypeError(
            "resolution_context requirements must contain BaselineRequirement"
        )
    if (
        isinstance(item.input_index, bool)
        or not isinstance(item.input_index, int)
        or item.input_index != index
    ):
        raise ValueError(
            "resolution_context requirements must have canonical input order"
        )
    if item.kind not in {"named", "direct-url", "local-path", "opaque"}:
        raise ValueError("resolution_context requirement kind is invalid")
    if item.name is not None and normalize_distribution_name(item.name) != item.name:
        raise ValueError("resolution_context requirement name is not normalized")
    if not isinstance(item.extras, tuple):
        raise TypeError("resolution_context requirement extras must be a tuple")
    if tuple(sorted(set(item.extras))) != item.extras:
        raise ValueError("resolution_context requirement extras are not canonical")
    for extra in item.extras:
        if normalize_distribution_name(extra) != extra:
            raise ValueError("resolution_context requirement extra is not normalized")
    if not isinstance(item.has_specifier, bool) or not isinstance(
        item.has_marker, bool
    ):
        raise TypeError("resolution_context requirement flags must be bool")
    if (
        (item.kind == "named" and item.name is None)
        or (
            item.kind == "opaque"
            and (item.name is not None or item.extras or item.has_specifier)
        )
        or (item.kind in {"direct-url", "local-path"} and item.has_specifier)
        or (item.name is None and item.extras)
    ):
        raise ValueError("resolution_context requirement fields are inconsistent")


def _validate_context(value: object) -> BaselineResolutionContext:  # noqa: PLR0912
    if not isinstance(value, BaselineResolutionContext):
        raise TypeError("resolution_context must be a BaselineResolutionContext")
    if not isinstance(value.requirements, tuple) or not value.requirements:
        raise ValueError("resolution_context requirements must be a non-empty tuple")
    for index, item in enumerate(value.requirements):
        _validate_requirement(item, index)
    for field in (
        "python_version_fingerprint",
        "platform_fingerprint",
        "architecture_fingerprint",
        "uv_version_fingerprint",
        "resolution_strategy_fingerprint",
    ):
        _fingerprint(getattr(value, field))
    if value.path_flavor not in {"posix", "windows"} or value.case_rule not in {
        "sensitive",
        "insensitive",
    }:
        raise ValueError("resolution_context path semantics are invalid")
    if value.build_policy not in {"wheel-only", "allow-build"} or not isinstance(
        value.compile_bytecode, bool
    ):
        raise ValueError("resolution_context policy is invalid")
    for items in (value.extras, value.index_identifiers):
        if not isinstance(items, tuple) or tuple(sorted(set(items))) != items:
            raise ValueError("resolution_context collections are not canonical")
        for item in items:
            if not isinstance(item, str):
                raise TypeError("resolution_context collection item must be a string")
    for extra in value.extras:
        if normalize_distribution_name(extra) != extra:
            raise ValueError("resolution_context extra is not normalized")
    if any(not _INDEX_IDENTIFIER.fullmatch(item) for item in value.index_identifiers):
        raise ValueError("resolution_context index identifier is invalid")
    return value


def _validate_existing_prefix_context(value: object) -> None:
    if not isinstance(value, BaselineExistingPrefixContext):
        raise TypeError(
            "existing_prefix_context must be a BaselineExistingPrefixContext"
        )
    for fingerprint in (
        value.python_version_fingerprint,
        value.platform_fingerprint,
        value.architecture_fingerprint,
    ):
        if fingerprint is not None:
            _fingerprint(fingerprint)
    if value.path_flavor not in {"posix", "windows"} or value.case_rule not in {
        "sensitive",
        "insensitive",
    }:
        raise ValueError("existing_prefix_context path semantics are invalid")


def _validate_project_lock_context(value: object) -> BaselineProjectLockContext:
    if not isinstance(value, BaselineProjectLockContext):
        raise TypeError("project_lock_context must be a BaselineProjectLockContext")
    if normalize_distribution_name(value.root_package) != value.root_package:
        raise ValueError("project_lock_context root_package is invalid")
    if value.workspace_member is not None and (
        normalize_distribution_name(value.workspace_member) != value.workspace_member
        or value.workspace_member != value.root_package
    ):
        raise ValueError("project_lock_context workspace_member is invalid")
    if value.dependency_group_selection not in {"none", "explicit", "all"}:
        raise ValueError("project_lock_context dependency group selection is invalid")
    for field in ("dependency_groups", "extras"):
        items = getattr(value, field)
        if not isinstance(items, tuple) or tuple(sorted(set(items))) != items:
            raise ValueError(f"project_lock_context {field} are not canonical")
        if any(normalize_distribution_name(item) != item for item in items):
            raise ValueError(f"project_lock_context {field} are invalid")
    if value.dependency_group_selection == "none" and value.dependency_groups:
        raise ValueError("project_lock_context none selection has groups")
    if value.dependency_group_selection == "explicit" and not value.dependency_groups:
        raise ValueError("project_lock_context explicit selection lacks groups")
    for field in (
        "python_version_fingerprint",
        "platform_fingerprint",
        "architecture_fingerprint",
        "uv_version_fingerprint",
        "resolution_strategy_fingerprint",
        "lock_identity",
    ):
        _fingerprint(getattr(value, field))
    if value.path_flavor not in {"posix", "windows"} or value.case_rule not in {
        "sensitive",
        "insensitive",
    }:
        raise ValueError("project_lock_context path semantics are invalid")
    if value.build_policy not in {"wheel-only", "allow-build"} or not isinstance(
        value.compile_bytecode, bool
    ):
        raise ValueError("project_lock_context policy is invalid")
    return value


def _supported_measurement(value: BaselineMeasurement) -> bool:
    return (value.kind, value.unit, value.ownership, value.deduplication) == (
        "installed-logical-size",
        "bytes",
        "distribution-owned-files",
        "canonical-identity",
    )


def _validate_baseline(  # noqa: PLR0912, PLR0915
    value: object, *, require_supported_measurement: bool = True
) -> Baseline:
    if not isinstance(value, Baseline):
        raise TypeError("baseline must be a Baseline")
    if isinstance(value.schema_version, bool) or not isinstance(
        value.schema_version, int
    ):
        raise ValueError("schema_version must be an integer")
    if not isinstance(value.measurement, BaselineMeasurement):
        raise TypeError("measurement must be a BaselineMeasurement")
    if require_supported_measurement and not _supported_measurement(value.measurement):
        raise ValueError("measurement must use the supported contract")
    _nonnegative(value.global_logical_bytes, "global_logical_bytes")
    if not isinstance(value.distributions, tuple):
        raise TypeError("distributions must be a tuple")
    names = []
    for item in value.distributions:
        if not isinstance(item, BaselineDistribution):
            raise TypeError("distributions must contain BaselineDistribution")
        if normalize_distribution_name(item.name) != item.name:
            raise ValueError("distribution names must be normalized")
        _safe_string(item.version, "distribution version")
        _nonnegative(item.logical_bytes, "distribution logical_bytes")
        names.append(item.name)
    if names != sorted(names) or len(names) != len(set(names)):
        raise ValueError("distributions must be uniquely sorted by name")
    if not isinstance(
        value.warnings, BaselineWarningSummary
    ) or value.warnings.completeness not in {"complete", "incomplete"}:
        raise ValueError("warnings are invalid")
    if not isinstance(value.warnings.warning_code_counts, tuple):
        raise TypeError("warning_code_counts must be a tuple")
    codes = []
    for pair in value.warnings.warning_code_counts:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("warning_code_counts are invalid")
        code, count = pair
        if not isinstance(code, str) or code not in _WARNING_CODES:
            raise ValueError("warning code is invalid")
        if _nonnegative(count, "warning count") == 0:
            raise ValueError("warning count must be positive")
        codes.append(code)
    if codes != sorted(codes) or len(codes) != len(set(codes)):
        raise ValueError("warning_code_counts must be canonical")
    is_incomplete = any(code in _INCOMPLETE_WARNING_CODES for code in codes)
    if (value.warnings.completeness == "incomplete") != is_incomplete:
        raise ValueError("warning completeness is inconsistent")
    if not isinstance(value.duplicate_ownership, BaselineDuplicateOwnershipSummary):
        raise TypeError(
            "duplicate_ownership must be a BaselineDuplicateOwnershipSummary"
        )
    if not isinstance(value.duplicate_ownership.present, bool):
        raise TypeError("duplicate_ownership present must be bool")
    if value.duplicate_ownership.present != (
        _nonnegative(value.duplicate_ownership.count, "duplicate_ownership count") > 0
    ):
        raise ValueError("duplicate_ownership summary is inconsistent")
    duplicate_warning_count = dict(value.warnings.warning_code_counts).get(
        "duplicate-ownership", 0
    )
    if duplicate_warning_count != value.duplicate_ownership.count:
        raise ValueError("duplicate_ownership warning summary is inconsistent")
    if value.schema_version == 1:
        if (
            value.input_kind != "fresh-install"
            or value.existing_prefix_context is not None
            or value.project_lock_context is not None
        ):
            raise ValueError("schema v1 baseline context is invalid")
        _validate_context(value.resolution_context)
    elif value.schema_version == 2:
        if (
            value.input_kind != "existing-prefix"
            or value.resolution_context is not None
            or value.existing_prefix_context is None
            or value.project_lock_context is not None
        ):
            raise ValueError("schema v2 baseline context is invalid")
        _validate_existing_prefix_context(value.existing_prefix_context)
    elif value.schema_version == 3:
        if (
            value.input_kind != "project-lock"
            or value.resolution_context is not None
            or value.existing_prefix_context is not None
        ):
            raise ValueError("schema v3 baseline context is invalid")
        _validate_project_lock_context(value.project_lock_context)
    return value


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class DistributionDelta:
    name: str
    baseline_distribution: BaselineDistribution | None
    current_distribution: BaselineDistribution | None
    kind: DistributionChangeKind

    def __post_init__(self) -> None:
        if normalize_distribution_name(self.name) != self.name:
            raise ValueError("name must be normalized")
        for item in (self.baseline_distribution, self.current_distribution):
            if item is not None:
                if not isinstance(item, BaselineDistribution) or item.name != self.name:
                    raise ValueError("distribution projection is invalid")
                _safe_string(item.version, "distribution version")
                _nonnegative(item.logical_bytes, "distribution logical_bytes")
        if not isinstance(self.kind, DistributionChangeKind):
            raise TypeError("kind must be a DistributionChangeKind")
        if self.baseline_distribution is None and self.current_distribution is None:
            raise ValueError("a distribution delta requires one projection")
        expected = (
            DistributionChangeKind.ADDED
            if self.baseline_distribution is None
            else DistributionChangeKind.REMOVED
            if self.current_distribution is None
            else DistributionChangeKind.UNCHANGED
            if self.baseline_distribution.version == self.current_distribution.version
            else DistributionChangeKind.VERSION_CHANGED
        )
        if self.kind is not expected:
            raise ValueError(
                "distribution change kind is inconsistent with projections"
            )

    @property
    def baseline_logical_bytes(self) -> int:
        return (
            0
            if self.baseline_distribution is None
            else self.baseline_distribution.logical_bytes
        )

    @property
    def current_logical_bytes(self) -> int:
        return (
            0
            if self.current_distribution is None
            else self.current_distribution.logical_bytes
        )

    @property
    def logical_bytes_delta(self) -> int:
        return self.current_logical_bytes - self.baseline_logical_bytes

    @property
    def baseline_bytes(self) -> int:
        return self.baseline_logical_bytes

    @property
    def current_bytes(self) -> int:
        return self.current_logical_bytes

    @property
    def signed_logical_bytes_delta(self) -> int:
        return self.logical_bytes_delta

    baseline = property(lambda self: self.baseline_distribution)
    current = property(lambda self: self.current_distribution)

    def __repr__(self) -> str:
        return (
            "DistributionDelta("
            f"kind={self.kind.value!r}, baseline_logical_bytes={self.baseline_logical_bytes}, "
            f"current_logical_bytes={self.current_logical_bytes}, "
            f"logical_bytes_delta={self.logical_bytes_delta})"
        )


def _deltas(baseline: Baseline, current: Baseline) -> tuple[DistributionDelta, ...]:
    left = {item.name: item for item in baseline.distributions}
    right = {item.name: item for item in current.distributions}
    return tuple(
        DistributionDelta(
            name=name,
            baseline_distribution=left.get(name),
            current_distribution=right.get(name),
            kind=(
                DistributionChangeKind.ADDED
                if name not in left
                else DistributionChangeKind.REMOVED
                if name not in right
                else DistributionChangeKind.UNCHANGED
                if left[name].version == right[name].version
                else DistributionChangeKind.VERSION_CHANGED
            ),
        )
        for name in sorted(left.keys() | right.keys())
    )


def _completeness(baseline: Baseline) -> Completeness:
    return (
        Completeness.INCOMPLETE
        if baseline.warnings.is_incomplete
        else Completeness.COMPLETE
    )


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class AnalysisDiff:
    baseline: Baseline
    current: Baseline
    distributions: tuple[DistributionDelta, ...]
    global_logical_bytes_delta: int
    distribution_logical_bytes_delta: int
    baseline_completeness: Completeness
    current_completeness: Completeness
    completeness: Completeness

    @property
    def global_signed_logical_bytes_delta(self) -> int:
        return self.global_logical_bytes_delta

    @property
    def distribution_signed_logical_bytes_delta(self) -> int:
        return self.distribution_logical_bytes_delta

    def __post_init__(self) -> None:
        baseline, current = (
            _validate_baseline(self.baseline),
            _validate_baseline(self.current),
        )
        if (
            baseline.schema_version not in {1, 3}
            or current.schema_version != baseline.schema_version
        ):
            raise ValueError("diff supports matching fresh or project-lock baselines")
        if not _supported_measurement(
            baseline.measurement
        ) or not _supported_measurement(current.measurement):
            raise ValueError(
                "diff baselines must use the supported measurement contract"
            )
        contexts_match = (
            baseline.resolution_context == current.resolution_context
            if baseline.schema_version == 1
            else _project_compatibility_context(
                cast(BaselineProjectLockContext, baseline.project_lock_context)
            )
            == _project_compatibility_context(
                cast(BaselineProjectLockContext, current.project_lock_context)
            )
        )
        if baseline.measurement != current.measurement or not contexts_match:
            raise ValueError("diff baselines must have matching comparison context")
        deltas = _deltas(baseline, current)
        if not isinstance(self.distributions, tuple) or self.distributions != deltas:
            raise ValueError("distributions must be the canonical full outer join")
        if (
            _signed_delta(self.global_logical_bytes_delta, "global_logical_bytes_delta")
            != current.global_logical_bytes - baseline.global_logical_bytes
            or _signed_delta(
                self.distribution_logical_bytes_delta,
                "distribution_logical_bytes_delta",
            )
            != sum(item.logical_bytes_delta for item in deltas)
        ):
            raise ValueError("diff totals are inconsistent")
        if (
            type(self.baseline_completeness) is not Completeness
            or type(self.current_completeness) is not Completeness
            or type(self.completeness) is not Completeness
        ):
            raise TypeError("diff completeness values must be Completeness")
        left, right = _completeness(baseline), _completeness(current)
        aggregate = (
            Completeness.INCOMPLETE
            if Completeness.INCOMPLETE in {left, right}
            else Completeness.COMPLETE
        )
        if (
            self.baseline_completeness,
            self.current_completeness,
            self.completeness,
        ) != (left, right, aggregate):
            raise ValueError("diff completeness is inconsistent")

    def __repr__(self) -> str:
        return (
            "AnalysisDiff("
            f"distribution_count={len(self.distributions)}, "
            f"global_logical_bytes_delta={self.global_logical_bytes_delta}, "
            f"distribution_logical_bytes_delta={self.distribution_logical_bytes_delta}, "
            f"baseline_completeness={self.baseline_completeness.value!r}, "
            f"current_completeness={self.current_completeness.value!r}, "
            f"completeness={self.completeness.value!r})"
        )


def compare_baselines(baseline: Baseline, current: Baseline) -> AnalysisDiff:
    """Compare compatible v1 fresh-install baselines without I/O or rendering."""
    baseline, current = (
        _validate_baseline(baseline, require_supported_measurement=False),
        _validate_baseline(current, require_supported_measurement=False),
    )
    if baseline.schema_version not in {1, 2, 3} or current.schema_version not in {
        1,
        2,
        3,
    }:
        raise IncompatibleComparisonError(
            ComparisonIncompatibilityReason.UNSUPPORTED_SCHEMA
        )
    if baseline.schema_version == 2 or current.schema_version == 2:
        raise IncompatibleComparisonError(
            ComparisonIncompatibilityReason.UNSUPPORTED_EXISTING_PREFIX
        )
    if baseline.measurement != current.measurement:
        raise IncompatibleComparisonError(
            ComparisonIncompatibilityReason.MEASUREMENT_MISMATCH
        )
    if not _supported_measurement(baseline.measurement):
        raise ValueError("baseline measurement contract is unsupported")
    if baseline.schema_version != current.schema_version:
        raise IncompatibleComparisonError(
            ComparisonIncompatibilityReason.CONTEXT_MISMATCH
        )
    contexts_match = (
        baseline.resolution_context == current.resolution_context
        if baseline.schema_version == 1
        else _project_compatibility_context(
            cast(BaselineProjectLockContext, baseline.project_lock_context)
        )
        == _project_compatibility_context(
            cast(BaselineProjectLockContext, current.project_lock_context)
        )
    )
    if not contexts_match:
        raise IncompatibleComparisonError(
            ComparisonIncompatibilityReason.CONTEXT_MISMATCH
        )
    distributions = _deltas(baseline, current)
    left, right = _completeness(baseline), _completeness(current)
    return AnalysisDiff(
        baseline=baseline,
        current=current,
        distributions=distributions,
        global_logical_bytes_delta=current.global_logical_bytes
        - baseline.global_logical_bytes,
        distribution_logical_bytes_delta=sum(
            item.logical_bytes_delta for item in distributions
        ),
        baseline_completeness=left,
        current_completeness=right,
        completeness=Completeness.INCOMPLETE
        if Completeness.INCOMPLETE in {left, right}
        else Completeness.COMPLETE,
    )
