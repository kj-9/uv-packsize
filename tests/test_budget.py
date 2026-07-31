"""Budget policy unit tests: no installation, rendering, or I/O."""

from dataclasses import fields, replace
from pathlib import Path
from typing import cast

import pytest

from uv_packsize.baseline import (
    MAX_BASELINE_INTEGER,
    Baseline,
    BaselineDistribution,
    BaselineDuplicateOwnershipSummary,
    BaselineWarningSummary,
    parse_baseline_json,
)
from uv_packsize.budget import (
    BudgetEvaluation,
    BudgetEvaluationError,
    BudgetEvaluationErrorReason,
    BudgetPolicy,
    BudgetViolation,
    BudgetViolationKind,
    IncompleteBudgetPolicy,
    evaluate_budget,
)
from uv_packsize.diff import compare_baselines
from uv_packsize.models import Completeness

ROOT = Path(__file__).parents[1]


def baseline():
    source = parse_baseline_json(
        (ROOT / "tests/golden/analysis-result-v1.json").read_text()
    )
    return replace(
        source,
        warnings=BaselineWarningSummary(
            completeness="complete", warning_code_counts=()
        ),
        duplicate_ownership=BaselineDuplicateOwnershipSummary(present=False, count=0),
    )


def incomplete(value):
    return replace(
        value,
        warnings=BaselineWarningSummary(
            completeness="incomplete", warning_code_counts=(("missing-file", 1),)
        ),
    )


def test_empty_policy_is_a_passing_no_op_even_when_current_is_incomplete():
    before = incomplete(baseline())
    result = evaluate_budget(
        before, BudgetPolicy(), comparison=compare_baselines(before, before)
    )

    assert result.passed
    assert result.current_completeness is Completeness.INCOMPLETE
    assert result.comparison_completeness is None
    assert result.global_logical_bytes_increase is None
    assert result.violations == ()


def test_total_limit_uses_current_canonical_global_only_at_boundaries():
    current = replace(baseline(), global_logical_bytes=10)
    assert evaluate_budget(current, BudgetPolicy(max_total_logical_bytes=10)).passed
    result = evaluate_budget(current, BudgetPolicy(max_total_logical_bytes=9))
    assert result.violations == (
        BudgetViolation(
            kind=BudgetViolationKind.MAX_TOTAL_EXCEEDED,
            limit=9,
            observed=10,
            excess=1,
        ),
    )


def test_increase_limit_supports_negative_zero_equal_and_one_over():
    before = baseline()
    for delta, limit, passed in (
        (-1, 0, True),
        (0, 0, True),
        (1, 1, True),
        (2, 1, False),
    ):
        current = replace(
            before, global_logical_bytes=before.global_logical_bytes + delta
        )
        result = evaluate_budget(
            current,
            BudgetPolicy(max_increase_logical_bytes=limit),
            comparison=compare_baselines(before, current),
        )
        assert result.passed is passed
        assert result.global_logical_bytes_increase == delta
        if not passed:
            assert result.violations[-1] == BudgetViolation(
                kind=BudgetViolationKind.MAX_INCREASE_EXCEEDED,
                limit=limit,
                observed=delta,
                excess=1,
            )


def test_both_limits_have_canonical_violation_order_and_keep_numeric_findings():
    before = incomplete(baseline())
    current = replace(before, global_logical_bytes=100)
    result = evaluate_budget(
        current,
        BudgetPolicy(max_total_logical_bytes=10, max_increase_logical_bytes=2),
        comparison=compare_baselines(before, current),
    )
    assert [item.kind for item in result.violations] == [
        BudgetViolationKind.INCOMPLETE,
        BudgetViolationKind.MAX_TOTAL_EXCEEDED,
        BudgetViolationKind.MAX_INCREASE_EXCEEDED,
    ]


@pytest.mark.parametrize("which", ["current", "baseline", "both"])
def test_incomplete_fail_or_allow_partial_for_relevant_inputs(which):
    before, current = baseline(), baseline()
    if which in {"baseline", "both"}:
        before = incomplete(before)
    if which in {"current", "both"}:
        current = incomplete(current)
    comparison = compare_baselines(before, current)
    failed = evaluate_budget(
        current,
        BudgetPolicy(max_increase_logical_bytes=0),
        comparison=comparison,
    )
    allowed = evaluate_budget(
        current,
        BudgetPolicy(
            max_increase_logical_bytes=0,
            incomplete_policy=IncompleteBudgetPolicy.ALLOW_PARTIAL,
        ),
        comparison=comparison,
    )
    assert failed.violations[0].kind is BudgetViolationKind.INCOMPLETE
    assert allowed.passed
    assert allowed.comparison_completeness is Completeness.INCOMPLETE


def test_total_only_ignores_baseline_incompleteness_and_nonreconciliation():
    before = incomplete(baseline())
    current = replace(
        baseline(),
        global_logical_bytes=0,
        distributions=(
            BaselineDistribution(name="duplicate", version="1", logical_bytes=99),
        ),
    )
    result = evaluate_budget(
        current,
        BudgetPolicy(max_total_logical_bytes=0),
        comparison=compare_baselines(before, current),
    )
    assert result.passed
    assert result.comparison_completeness is None


def test_global_delta_not_distribution_delta_is_budget_authority():
    before = baseline()
    current = replace(
        before,
        global_logical_bytes=before.global_logical_bytes,
        distributions=(
            BaselineDistribution(name="duplicate", version="1", logical_bytes=99),
        ),
    )
    comparison = compare_baselines(before, current)
    assert comparison.global_logical_bytes_delta == 0
    assert comparison.distribution_logical_bytes_delta != 0
    assert evaluate_budget(
        current, BudgetPolicy(max_increase_logical_bytes=0), comparison=comparison
    ).passed


def test_missing_and_mismatched_comparison_are_sanitized():
    current = baseline()
    with pytest.raises(BudgetEvaluationError) as missing:
        evaluate_budget(current, BudgetPolicy(max_increase_logical_bytes=0))
    assert missing.value.reason is BudgetEvaluationErrorReason.MISSING_COMPARISON

    secret = "private-package"
    other = replace(
        current,
        distributions=(
            BaselineDistribution(name=secret, version="1", logical_bytes=0),
        ),
    )
    with pytest.raises(BudgetEvaluationError) as mismatch:
        evaluate_budget(
            current,
            BudgetPolicy(max_increase_logical_bytes=0),
            comparison=compare_baselines(other, other),
        )
    assert mismatch.value.reason is BudgetEvaluationErrorReason.CURRENT_MISMATCH
    assert secret not in str(mismatch.value)


def test_increase_comparison_requires_exact_current_object_identity():
    current = baseline()
    equivalent_copy = replace(current)
    comparison = compare_baselines(current, equivalent_copy)
    with pytest.raises(BudgetEvaluationError) as mismatch:
        evaluate_budget(
            current, BudgetPolicy(max_increase_logical_bytes=0), comparison=comparison
        )
    assert mismatch.value.reason is BudgetEvaluationErrorReason.CURRENT_MISMATCH


def test_increase_comparison_rejects_subclass_with_forged_equality():
    class EqualBaseline(Baseline):
        __hash__ = Baseline.__hash__

        def __eq__(self, _other: object) -> bool:
            return True

    current = baseline()
    forged_current = EqualBaseline(
        **{field.name: getattr(current, field.name) for field in fields(Baseline)}
    )
    comparison = compare_baselines(current, forged_current)
    with pytest.raises(BudgetEvaluationError) as mismatch:
        evaluate_budget(
            current, BudgetPolicy(max_increase_logical_bytes=0), comparison=comparison
        )
    assert mismatch.value.reason is BudgetEvaluationErrorReason.CURRENT_MISMATCH


def test_maximum_and_zero_boundaries_are_safe():
    before = replace(baseline(), global_logical_bytes=0, distributions=())
    current = replace(before, global_logical_bytes=MAX_BASELINE_INTEGER)
    result = evaluate_budget(
        current,
        BudgetPolicy(
            max_total_logical_bytes=MAX_BASELINE_INTEGER - 1,
            max_increase_logical_bytes=0,
        ),
        comparison=compare_baselines(before, current),
    )
    assert [item.excess for item in result.violations] == [1, MAX_BASELINE_INTEGER]
    assert evaluate_budget(
        current, BudgetPolicy(max_total_logical_bytes=MAX_BASELINE_INTEGER)
    ).passed


@pytest.mark.parametrize(
    "factory",
    [
        lambda: BudgetPolicy(max_total_logical_bytes=True),
        lambda: BudgetPolicy(max_increase_logical_bytes=-1),
        lambda: BudgetPolicy(max_total_logical_bytes=MAX_BASELINE_INTEGER + 1),
        lambda: BudgetPolicy(incomplete_policy=cast(IncompleteBudgetPolicy, "fail")),
        lambda: BudgetViolation(kind=cast(BudgetViolationKind, "incomplete")),
        lambda: BudgetViolation(kind=BudgetViolationKind.INCOMPLETE, limit=0),
        lambda: BudgetViolation(
            kind=BudgetViolationKind.MAX_TOTAL_EXCEEDED, limit=1, observed=1, excess=0
        ),
        lambda: BudgetViolation(
            kind=BudgetViolationKind.MAX_INCREASE_EXCEEDED,
            limit=0,
            observed=True,
            excess=1,
        ),
    ],
)
def test_policy_and_violation_reject_forged_values(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_evaluation_is_immutable_hashable_deterministic_and_rejects_forgery():
    current = baseline()
    result = evaluate_budget(current, BudgetPolicy(max_total_logical_bytes=0))
    assert result == evaluate_budget(current, BudgetPolicy(max_total_logical_bytes=0))
    assert hash(result)
    with pytest.raises(AttributeError):
        field = "".join(("viola", "tions"))
        setattr(result, field, ())
    with pytest.raises(ValueError):
        replace(result, violations=result.violations * 2)
    with pytest.raises((TypeError, ValueError)):
        BudgetEvaluation(
            policy=BudgetPolicy(),
            current_global_logical_bytes=0,
            global_logical_bytes_increase=0,
            current_completeness=Completeness.COMPLETE,
            comparison_completeness=None,
            violations=(),
        )


def test_forged_and_private_inputs_do_not_leak_to_evaluation_or_errors():
    current = baseline()
    secret = "f" * 64
    private = replace(
        current,
        distributions=(
            BaselineDistribution(
                name="private-package", version="private", logical_bytes=0
            ),
        ),
        resolution_context=replace(
            current.resolution_context, platform_fingerprint=secret
        ),
    )
    result = evaluate_budget(private, BudgetPolicy())
    assert secret not in repr(result)
    assert "private-package" not in repr(result)
    forged = object.__new__(type(compare_baselines(current, current)))
    with pytest.raises(BudgetEvaluationError) as error:
        evaluate_budget(
            current, BudgetPolicy(max_increase_logical_bytes=0), comparison=forged
        )
    assert error.value.reason is BudgetEvaluationErrorReason.INVALID_INPUT
    assert secret not in str(error.value)


def test_invalid_current_and_plain_policy_are_typed_errors():
    with pytest.raises(BudgetEvaluationError) as current:
        evaluate_budget(cast(Baseline, object()), BudgetPolicy())
    assert current.value.reason is BudgetEvaluationErrorReason.INVALID_INPUT
    with pytest.raises(BudgetEvaluationError) as policy:
        evaluate_budget(baseline(), cast(BudgetPolicy, object()))
    assert policy.value.reason is BudgetEvaluationErrorReason.INVALID_INPUT
