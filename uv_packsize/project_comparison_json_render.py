"""Pure closed comparison-result-v2 renderer for project-lock baselines."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from .baseline import Baseline, BaselineDistribution, BaselineProjectLockContext
from .diff import AnalysisDiff, project_lock_changed

_DOMAIN = b"uv-packsize/project-lock-comparison-context/v2\0"
_NONRECONCILIATION_REASON = "duplicate-owned-files-may-be-counted-per-distribution"


def _context_projection(context: BaselineProjectLockContext) -> dict[str, object]:
    """Comparison inputs; deliberately do not include the lock identity."""

    return {
        "root_package": context.root_package,
        "workspace_member": context.workspace_member,
        "dependency_group_selection": context.dependency_group_selection,
        "dependency_groups": list(context.dependency_groups),
        "extras": list(context.extras),
        "python_version_fingerprint": context.python_version_fingerprint,
        "platform_fingerprint": context.platform_fingerprint,
        "architecture_fingerprint": context.architecture_fingerprint,
        "path_flavor": context.path_flavor,
        "case_rule": context.case_rule,
        "uv_version_fingerprint": context.uv_version_fingerprint,
        "build_policy": context.build_policy,
        "compile_bytecode": context.compile_bytecode,
        "resolution_strategy_fingerprint": context.resolution_strategy_fingerprint,
    }


def project_lock_comparison_context_fingerprint(
    context: BaselineProjectLockContext,
) -> str:
    if type(context) is not BaselineProjectLockContext:
        raise TypeError("context must be an exact BaselineProjectLockContext")
    payload = json.dumps(
        _context_projection(context),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(_DOMAIN + payload).hexdigest()


def _side(baseline: Baseline, completeness: str) -> dict[str, object]:
    return {
        "totals": {
            "global_logical_bytes": baseline.global_logical_bytes,
            "distribution_logical_bytes": sum(
                item.logical_bytes for item in baseline.distributions
            ),
        },
        "completeness": completeness,
        "warning_code_counts": [
            {"code": code, "count": count}
            for code, count in baseline.warnings.warning_code_counts
        ],
        "duplicate_ownership": {
            "present": baseline.duplicate_ownership.present,
            "count": baseline.duplicate_ownership.count,
        },
    }


def _distribution(delta: Any) -> dict[str, object]:
    def side(value: BaselineDistribution | None) -> dict[str, object] | None:
        return (
            None
            if value is None
            else {"version": value.version, "logical_bytes": value.logical_bytes}
        )

    return {
        "name": delta.name,
        "kind": delta.kind.value,
        "baseline": side(delta.baseline_distribution),
        "current": side(delta.current_distribution),
        "logical_bytes_delta": delta.logical_bytes_delta,
    }


def project_lock_comparison_to_json_object(diff: AnalysisDiff) -> dict[str, object]:
    """Convert an exact v3 diff to comparison-result-v2 JSON data."""

    if type(diff) is not AnalysisDiff:
        raise TypeError("diff must be an exact AnalysisDiff")
    diff.__post_init__()
    if diff.baseline.schema_version != 3 or diff.current.schema_version != 3:
        raise TypeError("comparison v2 requires schema v3 project-lock baselines")
    context = cast(BaselineProjectLockContext, diff.baseline.project_lock_context)
    delta = diff.distribution_logical_bytes_delta - diff.global_logical_bytes_delta
    return {
        "schema_version": 2,
        "measurement": {
            "kind": diff.baseline.measurement.kind,
            "unit": diff.baseline.measurement.unit,
            "ownership": diff.baseline.measurement.ownership,
            "deduplication": diff.baseline.measurement.deduplication,
        },
        "context": {
            "input_kind": "project-lock",
            "comparison_context_fingerprint": project_lock_comparison_context_fingerprint(
                context
            ),
            "lock_changed": project_lock_changed(diff.baseline, diff.current),
        },
        "baseline": _side(diff.baseline, diff.baseline_completeness.value),
        "current": _side(diff.current, diff.current_completeness.value),
        "changes": {
            "totals": {
                "global_logical_bytes_delta": diff.global_logical_bytes_delta,
                "distribution_logical_bytes_delta": diff.distribution_logical_bytes_delta,
            },
            "distributions": [_distribution(item) for item in diff.distributions],
            "nonreconciliation": {
                "present": delta != 0,
                "distribution_minus_global_logical_bytes_delta": delta,
                "reason": _NONRECONCILIATION_REASON if delta else None,
            },
        },
        "completeness": diff.completeness.value,
    }


def render_project_lock_comparison_json(diff: AnalysisDiff) -> str:
    return (
        json.dumps(
            project_lock_comparison_to_json_object(diff),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
