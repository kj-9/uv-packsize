"""Pure text presentation tests for budget evaluation results."""

from dataclasses import replace
from pathlib import Path

import pytest

from uv_packsize.baseline import (
    BaselineDuplicateOwnershipSummary,
    BaselineWarningSummary,
    parse_baseline_json,
)
from uv_packsize.budget import (
    BudgetEvaluation,
    BudgetPolicy,
    IncompleteBudgetPolicy,
    evaluate_budget,
)
from uv_packsize.budget_render import render_budget_report, render_budget_sections
from uv_packsize.diff import compare_baselines

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


def test_no_op_is_explicit_and_does_not_evaluate_incomplete_measurements():
    report = render_budget_report(
        evaluate_budget(incomplete(baseline()), BudgetPolicy())
    )

    assert report == "\n".join(
        (
            "--- Size Budget ---",
            "Result: PASS",
            "Authority: canonical global logical bytes; distribution-owned aggregates are not budget inputs.",
            "No limits configured; this is a no-op policy.",
            "Completeness is not evaluated by a no-op policy.",
        )
    )
    assert not report.endswith("\n")


def test_total_limit_renders_canonical_global_total_and_remaining_or_excess():
    current = replace(baseline(), global_logical_bytes=11)
    passing = render_budget_report(
        evaluate_budget(current, BudgetPolicy(max_total_logical_bytes=12))
    )
    failing = render_budget_report(
        evaluate_budget(current, BudgetPolicy(max_total_logical_bytes=10))
    )

    assert "Current canonical global logical size: 11 B" in passing
    assert "Maximum total logical size: 12 B" in passing
    assert "Total budget: within limit (1 B remaining)." in passing
    assert "Result: PASS" in passing
    assert "Total budget: exceeded by 1 B." in failing
    assert (
        "Maximum total logical size exceeded: observed 11 B, limit 10 B, excess 1 B."
        in failing
    )
    assert "Distribution" not in "\n".join(failing.splitlines()[3:])


def test_increase_limit_renders_signed_observation_and_negative_delta_headroom():
    before = baseline()
    current = replace(before, global_logical_bytes=before.global_logical_bytes - 2)
    report = render_budget_report(
        evaluate_budget(
            current,
            BudgetPolicy(max_increase_logical_bytes=0),
            comparison=compare_baselines(before, current),
        )
    )

    assert "Observed canonical global logical-size increase: -2 B" in report
    assert "Maximum logical-size increase: 0 B" in report
    assert (
        "Increase budget: within limit (2 B remaining after the signed increase)."
        in report
    )
    assert "Comparison measurement completeness: complete." in report
    assert "distribution-owned aggregate" in report


def test_both_limits_render_canonical_violation_order_and_numeric_details():
    before = incomplete(baseline())
    current = replace(before, global_logical_bytes=100)
    report = render_budget_report(
        evaluate_budget(
            current,
            BudgetPolicy(max_total_logical_bytes=10, max_increase_logical_bytes=2),
            comparison=compare_baselines(before, current),
        )
    )

    violations = report.split("--- Budget Violations ---\n", 1)[1].splitlines()
    assert violations == [
        "1. Incomplete measurement is not allowed by the budget policy.",
        "2. Maximum total logical size exceeded: observed 100 B, limit 10 B, excess 90 B.",
        "3. Maximum logical-size increase exceeded: observed "
        f"+{current.global_logical_bytes - before.global_logical_bytes} B, "
        "limit 2 B, excess "
        f"{current.global_logical_bytes - before.global_logical_bytes - 2} B.",
    ]


def test_incomplete_fail_and_allow_partial_are_distinct_and_safe():
    before = incomplete(baseline())
    current = incomplete(before)
    comparison = compare_baselines(before, current)
    failed = render_budget_report(
        evaluate_budget(
            current,
            BudgetPolicy(max_increase_logical_bytes=0),
            comparison=comparison,
        )
    )
    allowed = render_budget_report(
        evaluate_budget(
            current,
            BudgetPolicy(
                max_increase_logical_bytes=0,
                incomplete_policy=IncompleteBudgetPolicy.ALLOW_PARTIAL,
            ),
            comparison=comparison,
        )
    )

    assert "Result: FAIL" in failed
    assert "Incomplete-result policy: fail." in failed
    assert "--- Budget Violations ---" in failed
    assert "Result: PASS" in allowed
    assert "Incomplete-result policy: allow-partial." in allowed
    assert "--- Budget Violations ---" not in allowed
    for report in (failed, allowed):
        assert "Current measurement completeness: incomplete." in report
        assert "Comparison measurement completeness: incomplete." in report
        assert "missing-file" not in report


def test_sections_equal_report_and_pass_does_not_render_a_violation_section():
    evaluation = evaluate_budget(baseline(), BudgetPolicy(max_total_logical_bytes=999))

    sections = render_budget_sections(evaluation)

    assert render_budget_report(evaluation) == "\n\n".join(sections)
    assert len(sections) == 1
    assert "Budget Violations" not in sections[0]


@pytest.mark.parametrize("value", [None, object(), BudgetPolicy()])
def test_public_boundary_rejects_wrong_types(value):
    with pytest.raises(TypeError, match="exact BudgetEvaluation"):
        render_budget_report(value)


def test_public_boundary_rejects_subclasses_and_forged_instances():
    evaluation = evaluate_budget(baseline(), BudgetPolicy(max_total_logical_bytes=999))

    class Subclass(BudgetEvaluation):
        pass

    subclass = Subclass(
        policy=evaluation.policy,
        current_global_logical_bytes=evaluation.current_global_logical_bytes,
        global_logical_bytes_increase=evaluation.global_logical_bytes_increase,
        current_completeness=evaluation.current_completeness,
        comparison_completeness=evaluation.comparison_completeness,
        violations=evaluation.violations,
    )
    with pytest.raises(TypeError, match="exact BudgetEvaluation"):
        render_budget_report(subclass)

    forged = object.__new__(BudgetEvaluation)
    with pytest.raises(ValueError, match="budget evaluation is invalid"):
        render_budget_report(forged)

    object.__setattr__(evaluation, "current_global_logical_bytes", -1)
    with pytest.raises(ValueError, match="budget evaluation is invalid"):
        render_budget_report(evaluation)


def test_reports_are_byte_deterministic_and_do_not_expose_baseline_details():
    current = replace(baseline(), global_logical_bytes=1)
    evaluation = evaluate_budget(current, BudgetPolicy(max_total_logical_bytes=0))

    first = render_budget_report(evaluation)
    second = render_budget_report(evaluation)

    assert first == second
    assert first.isascii()
    assert "alpha-pkg" not in first
    assert "fingerprint" not in first
