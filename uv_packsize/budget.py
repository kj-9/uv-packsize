"""Pure, safe size-budget policy evaluation.

This module intentionally has no configuration, rendering, filesystem, or CLI
boundary.  It consumes the already-redacted comparison domain only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .baseline import MAX_BASELINE_INTEGER, Baseline
from .diff import AnalysisDiff, _validate_baseline
from .models import Completeness


class IncompleteBudgetPolicy(str, Enum):
    """How a policy handles a measurement known to be incomplete."""

    FAIL = "fail"
    ALLOW_PARTIAL = "allow-partial"


class BudgetViolationKind(str, Enum):
    """The stable, data-free kinds of budget failure."""

    INCOMPLETE = "incomplete"
    MAX_TOTAL_EXCEEDED = "max-total-exceeded"
    MAX_INCREASE_EXCEEDED = "max-increase-exceeded"


class BudgetEvaluationErrorReason(str, Enum):
    """Sanitized reasons for inputs that cannot be evaluated."""

    MISSING_COMPARISON = "missing-comparison"
    CURRENT_MISMATCH = "current-mismatch"
    INVALID_INPUT = "invalid-input"


class BudgetEvaluationError(ValueError):
    """A budget input failure that never reflects baseline contents."""

    def __init__(self, reason: BudgetEvaluationErrorReason) -> None:
        self.reason = reason
        super().__init__(f"Budget evaluation failed ({reason.value}).")


def _nonnegative(value: object, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= MAX_BASELINE_INTEGER
    ):
        raise ValueError(f"{field} must be a non-negative baseline integer")
    return value


def _signed(value: object, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -MAX_BASELINE_INTEGER <= value <= MAX_BASELINE_INTEGER
    ):
        raise ValueError(f"{field} must be a signed baseline integer")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class BudgetPolicy:
    """Optional global size limits; an empty policy always passes as a no-op."""

    max_total_logical_bytes: int | None = None
    max_increase_logical_bytes: int | None = None
    incomplete_policy: IncompleteBudgetPolicy = IncompleteBudgetPolicy.FAIL

    def __post_init__(self) -> None:
        for field in ("max_total_logical_bytes", "max_increase_logical_bytes"):
            value = getattr(self, field)
            if value is not None:
                _nonnegative(value, field)
        if type(self.incomplete_policy) is not IncompleteBudgetPolicy:
            raise TypeError("incomplete_policy must be an IncompleteBudgetPolicy")


@dataclass(frozen=True, slots=True, kw_only=True)
class BudgetViolation:
    """A minimal, serializable-in-principle budget failure projection."""

    kind: BudgetViolationKind
    limit: int | None = None
    observed: int | None = None
    excess: int | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not BudgetViolationKind:
            raise TypeError("kind must be a BudgetViolationKind")
        if self.kind is BudgetViolationKind.INCOMPLETE:
            if any(
                value is not None for value in (self.limit, self.observed, self.excess)
            ):
                raise ValueError("incomplete violations have no numeric values")
            return
        if self.limit is None or self.observed is None or self.excess is None:
            raise ValueError("numeric violations require limit, observed, and excess")
        _nonnegative(self.limit, "limit")
        if self.kind is BudgetViolationKind.MAX_TOTAL_EXCEEDED:
            _nonnegative(self.observed, "observed")
        else:
            _signed(self.observed, "observed")
        _nonnegative(self.excess, "excess")
        if self.excess <= 0 or self.observed - self.limit != self.excess:
            raise ValueError("numeric violation excess is inconsistent")


_CANONICAL_VIOLATION_ORDER = {
    BudgetViolationKind.INCOMPLETE: 0,
    BudgetViolationKind.MAX_TOTAL_EXCEEDED: 1,
    BudgetViolationKind.MAX_INCREASE_EXCEEDED: 2,
}


def _expected_violations(
    policy: BudgetPolicy,
    current_global_logical_bytes: int,
    global_logical_bytes_increase: int | None,
    current_completeness: Completeness,
    comparison_completeness: Completeness | None,
) -> tuple[BudgetViolation, ...]:
    has_limit = (
        policy.max_total_logical_bytes is not None
        or policy.max_increase_logical_bytes is not None
    )
    incomplete = has_limit and (
        current_completeness is Completeness.INCOMPLETE
        or comparison_completeness is Completeness.INCOMPLETE
    )
    values: list[BudgetViolation] = []
    if incomplete and policy.incomplete_policy is IncompleteBudgetPolicy.FAIL:
        values.append(BudgetViolation(kind=BudgetViolationKind.INCOMPLETE))
    if (
        policy.max_total_logical_bytes is not None
        and current_global_logical_bytes > policy.max_total_logical_bytes
    ):
        values.append(
            BudgetViolation(
                kind=BudgetViolationKind.MAX_TOTAL_EXCEEDED,
                limit=policy.max_total_logical_bytes,
                observed=current_global_logical_bytes,
                excess=current_global_logical_bytes - policy.max_total_logical_bytes,
            )
        )
    if (
        policy.max_increase_logical_bytes is not None
        and global_logical_bytes_increase is not None
        and global_logical_bytes_increase > policy.max_increase_logical_bytes
    ):
        values.append(
            BudgetViolation(
                kind=BudgetViolationKind.MAX_INCREASE_EXCEEDED,
                limit=policy.max_increase_logical_bytes,
                observed=global_logical_bytes_increase,
                excess=global_logical_bytes_increase
                - policy.max_increase_logical_bytes,
            )
        )
    return tuple(values)


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class BudgetEvaluation:
    """Safe policy outcome, without retaining a baseline or comparison graph."""

    policy: BudgetPolicy
    current_global_logical_bytes: int
    global_logical_bytes_increase: int | None
    current_completeness: Completeness
    comparison_completeness: Completeness | None
    violations: tuple[BudgetViolation, ...]

    def __post_init__(self) -> None:
        if type(self.policy) is not BudgetPolicy:
            raise TypeError("policy must be an exact BudgetPolicy")
        self.policy.__post_init__()
        _nonnegative(self.current_global_logical_bytes, "current_global_logical_bytes")
        if self.global_logical_bytes_increase is not None:
            _signed(self.global_logical_bytes_increase, "global_logical_bytes_increase")
        if type(self.current_completeness) is not Completeness:
            raise TypeError("current_completeness must be Completeness")
        if (
            self.comparison_completeness is not None
            and type(self.comparison_completeness) is not Completeness
        ):
            raise TypeError("comparison_completeness must be Completeness or None")
        needs_comparison = self.policy.max_increase_logical_bytes is not None
        if needs_comparison != (self.global_logical_bytes_increase is not None):
            raise ValueError("increase presence must match the policy")
        if needs_comparison != (self.comparison_completeness is not None):
            raise ValueError("comparison completeness presence must match the policy")
        if not isinstance(self.violations, tuple):
            raise TypeError("violations must be a tuple")
        kinds = []
        for violation in self.violations:
            if type(violation) is not BudgetViolation:
                raise TypeError("violations must contain exact BudgetViolation")
            kinds.append(violation.kind)
        if len(kinds) != len(set(kinds)) or kinds != sorted(
            kinds, key=_CANONICAL_VIOLATION_ORDER.__getitem__
        ):
            raise ValueError("violations must have canonical unique order")
        if self.violations != _expected_violations(
            self.policy,
            self.current_global_logical_bytes,
            self.global_logical_bytes_increase,
            self.current_completeness,
            self.comparison_completeness,
        ):
            raise ValueError("violations must match the policy outcome")

    @property
    def passed(self) -> bool:
        return not self.violations

    def __repr__(self) -> str:
        return (
            "BudgetEvaluation("
            f"current_global_logical_bytes={self.current_global_logical_bytes}, "
            f"global_logical_bytes_increase={self.global_logical_bytes_increase}, "
            f"current_completeness={self.current_completeness.value!r}, "
            f"comparison_completeness="
            f"{None if self.comparison_completeness is None else self.comparison_completeness.value!r}, "
            f"violation_kinds={tuple(item.kind.value for item in self.violations)!r})"
        )


def _current_completeness(current: Baseline) -> Completeness:
    return (
        Completeness.INCOMPLETE
        if current.warnings.is_incomplete
        else Completeness.COMPLETE
    )


def _validate_current(value: object) -> Baseline:
    if type(value) is not Baseline:
        raise BudgetEvaluationError(BudgetEvaluationErrorReason.INVALID_INPUT)
    try:
        validated = _validate_baseline(value)
        if validated.schema_version != 1:
            raise ValueError("budget supports only v1 fresh-install baselines")
        return validated
    except (TypeError, ValueError):
        raise BudgetEvaluationError(BudgetEvaluationErrorReason.INVALID_INPUT) from None


def _validate_comparison(value: object) -> AnalysisDiff:
    if type(value) is not AnalysisDiff:
        raise BudgetEvaluationError(BudgetEvaluationErrorReason.INVALID_INPUT)
    try:
        # Re-run the immutable model's invariant checks, including canonical
        # global delta and completeness, to reject object.__new__ forgeries.
        value.__post_init__()
    except (AttributeError, TypeError, ValueError):
        raise BudgetEvaluationError(BudgetEvaluationErrorReason.INVALID_INPUT) from None
    return value


def evaluate_budget(
    current: Baseline,
    policy: BudgetPolicy,
    *,
    comparison: AnalysisDiff | None = None,
) -> BudgetEvaluation:
    """Evaluate canonical globals; a comparison must share ``current`` identity."""
    current = _validate_current(current)
    if type(policy) is not BudgetPolicy:
        raise BudgetEvaluationError(BudgetEvaluationErrorReason.INVALID_INPUT)
    try:
        policy.__post_init__()
    except (TypeError, ValueError):
        raise BudgetEvaluationError(BudgetEvaluationErrorReason.INVALID_INPUT) from None

    increase: int | None = None
    comparison_completeness: Completeness | None = None
    if policy.max_increase_logical_bytes is not None:
        if comparison is None:
            raise BudgetEvaluationError(BudgetEvaluationErrorReason.MISSING_COMPARISON)
        comparison = _validate_comparison(comparison)
        if comparison.current is not current:
            raise BudgetEvaluationError(BudgetEvaluationErrorReason.CURRENT_MISMATCH)
        increase = comparison.global_logical_bytes_delta
        comparison_completeness = comparison.completeness

    current_completeness = _current_completeness(current)
    return BudgetEvaluation(
        policy=policy,
        current_global_logical_bytes=current.global_logical_bytes,
        global_logical_bytes_increase=increase,
        current_completeness=current_completeness,
        comparison_completeness=comparison_completeness,
        violations=_expected_violations(
            policy,
            current.global_logical_bytes,
            increase,
            current_completeness,
            comparison_completeness,
        ),
    )
