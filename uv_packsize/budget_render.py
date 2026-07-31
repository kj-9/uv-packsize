"""Pure, safe text presentation for evaluated size budgets.

The renderer accepts only the scalar :class:`~uv_packsize.budget.BudgetEvaluation`
projection.  It deliberately knows nothing about baseline files, distributions,
configuration, or CLI exit codes.
"""

from __future__ import annotations

from .budget import (
    BudgetEvaluation,
    BudgetViolation,
    BudgetViolationKind,
)
from .diff_render import format_signed_size
from .models import Completeness
from .render import format_size


def render_budget_report(evaluation: BudgetEvaluation) -> str:
    """Render an evaluated budget as a deterministic, terminal-safe report."""

    return "\n\n".join(render_budget_sections(evaluation))


def render_budget_sections(evaluation: BudgetEvaluation) -> tuple[str, ...]:
    """Return deterministic budget-only report sections without a trailing LF."""

    evaluation = _validate_evaluation(evaluation)
    sections = [_render_budget(evaluation)]
    if evaluation.violations:
        sections.append(_render_violations(evaluation.violations))
    return tuple(sections)


def _validate_evaluation(value: object) -> BudgetEvaluation:
    """Reject subclasses and forged frozen instances at the public boundary."""

    if type(value) is not BudgetEvaluation:
        raise TypeError("evaluation must be an exact BudgetEvaluation")
    try:
        BudgetEvaluation.__post_init__(value)
    except (AttributeError, TypeError, ValueError):
        raise ValueError("budget evaluation is invalid") from None
    return value


def _render_budget(evaluation: BudgetEvaluation) -> str:
    policy = evaluation.policy
    has_total_limit = policy.max_total_logical_bytes is not None
    has_increase_limit = policy.max_increase_logical_bytes is not None
    lines = [
        "--- Size Budget ---",
        f"Result: {'PASS' if evaluation.passed else 'FAIL'}",
        "Authority: canonical global logical bytes; distribution-owned aggregates are not budget inputs.",
    ]
    if not has_total_limit and not has_increase_limit:
        lines.extend(
            (
                "No limits configured; this is a no-op policy.",
                "Completeness is not evaluated by a no-op policy.",
            )
        )
        return "\n".join(lines)

    if has_total_limit:
        assert policy.max_total_logical_bytes is not None
        lines.extend(
            (
                "Current canonical global logical size: "
                + format_size(evaluation.current_global_logical_bytes),
                "Maximum total logical size: "
                + format_size(policy.max_total_logical_bytes),
                "Total budget: "
                + _budget_outcome(
                    observed=evaluation.current_global_logical_bytes,
                    limit=policy.max_total_logical_bytes,
                    signed=False,
                ),
            )
        )
    if has_increase_limit:
        assert policy.max_increase_logical_bytes is not None
        assert evaluation.global_logical_bytes_increase is not None
        lines.extend(
            (
                "Observed canonical global logical-size increase: "
                + format_signed_size(evaluation.global_logical_bytes_increase),
                "Maximum logical-size increase: "
                + format_size(policy.max_increase_logical_bytes),
                "Increase budget: "
                + _budget_outcome(
                    observed=evaluation.global_logical_bytes_increase,
                    limit=policy.max_increase_logical_bytes,
                    signed=True,
                ),
            )
        )
    lines.extend(_completeness_lines(evaluation))
    return "\n".join(lines)


def _budget_outcome(*, observed: int, limit: int, signed: bool) -> str:
    excess = observed - limit
    if excess > 0:
        return f"exceeded by {format_size(excess)}."
    if excess == 0:
        return "at limit."
    headroom = format_size(-excess)
    if signed:
        return f"within limit ({headroom} remaining after the signed increase)."
    return f"within limit ({headroom} remaining)."


def _completeness_lines(evaluation: BudgetEvaluation) -> tuple[str, ...]:
    lines = [
        "Current measurement completeness: "
        + _completeness_label(evaluation.current_completeness)
        + ".",
    ]
    if evaluation.comparison_completeness is not None:
        lines.append(
            "Comparison measurement completeness: "
            + _completeness_label(evaluation.comparison_completeness)
            + "."
        )
    lines.append(
        "Incomplete-result policy: " + evaluation.policy.incomplete_policy.value + "."
    )
    return tuple(lines)


def _completeness_label(value: Completeness) -> str:
    if value is Completeness.COMPLETE:
        return "complete"
    assert value is Completeness.INCOMPLETE
    return "incomplete"


def _render_violations(violations: tuple[BudgetViolation, ...]) -> str:
    lines = ["--- Budget Violations ---"]
    lines.extend(
        f"{index}. {_violation_message(violation)}"
        for index, violation in enumerate(violations, start=1)
    )
    return "\n".join(lines)


def _violation_message(violation: BudgetViolation) -> str:
    if violation.kind is BudgetViolationKind.INCOMPLETE:
        return "Incomplete measurement is not allowed by the budget policy."
    assert violation.limit is not None
    assert violation.observed is not None
    assert violation.excess is not None
    if violation.kind is BudgetViolationKind.MAX_TOTAL_EXCEEDED:
        return (
            "Maximum total logical size exceeded: observed "
            f"{format_size(violation.observed)}, limit {format_size(violation.limit)}, "
            f"excess {format_size(violation.excess)}."
        )
    assert violation.kind is BudgetViolationKind.MAX_INCREASE_EXCEEDED
    return (
        "Maximum logical-size increase exceeded: observed "
        f"{format_signed_size(violation.observed)}, limit {format_size(violation.limit)}, "
        f"excess {format_size(violation.excess)}."
    )
