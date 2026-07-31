"""Deterministic public JSON rendering for successful baseline comparisons.

The comparison document intentionally exposes only aggregate comparison data.
In particular, the compatibility context is represented by a domain-separated
digest instead of requirements, resolver observations, or their individual
fingerprints.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .baseline import Baseline, BaselineDistribution, BaselineResolutionContext
from .diff import AnalysisDiff

_COMPARISON_CONTEXT_DOMAIN = b"uv-packsize/comparison-context/v1\0"
_NONRECONCILIATION_REASON = "duplicate-owned-files-may-be-counted-per-distribution"


def _comparison_context_projection(
    context: BaselineResolutionContext,
) -> dict[str, object]:
    """Return the complete safe baseline context in a fixed key order."""

    return {
        "requirements": [
            {
                "input_index": requirement.input_index,
                "kind": requirement.kind,
                "name": requirement.name,
                "extras": list(requirement.extras),
                "has_specifier": requirement.has_specifier,
                "has_marker": requirement.has_marker,
            }
            for requirement in context.requirements
        ],
        "python_version_fingerprint": context.python_version_fingerprint,
        "platform_fingerprint": context.platform_fingerprint,
        "architecture_fingerprint": context.architecture_fingerprint,
        "path_flavor": context.path_flavor,
        "case_rule": context.case_rule,
        "uv_version_fingerprint": context.uv_version_fingerprint,
        "build_policy": context.build_policy,
        "compile_bytecode": context.compile_bytecode,
        "extras": list(context.extras),
        "index_identifiers": list(context.index_identifiers),
        "resolution_strategy_fingerprint": context.resolution_strategy_fingerprint,
    }


def _comparison_context_fingerprint(context: BaselineResolutionContext) -> str:
    """Hash the canonical safe projection used to establish comparability."""

    if type(context) is not BaselineResolutionContext:
        raise TypeError("context must be an exact BaselineResolutionContext")
    payload = json.dumps(
        _comparison_context_projection(context),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(_COMPARISON_CONTEXT_DOMAIN + payload).hexdigest()


def _measurement_to_json(diff: AnalysisDiff) -> dict[str, str]:
    measurement = diff.baseline.measurement
    return {
        "kind": measurement.kind,
        "unit": measurement.unit,
        "ownership": measurement.ownership,
        "deduplication": measurement.deduplication,
    }


def _side_to_json(baseline: Baseline, completeness: str) -> dict[str, object]:
    return {
        "totals": {
            "global_logical_bytes": baseline.global_logical_bytes,
            "distribution_logical_bytes": sum(
                distribution.logical_bytes for distribution in baseline.distributions
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


def _distribution_to_json(delta: Any) -> dict[str, object]:
    def side(value: BaselineDistribution | None) -> dict[str, object] | None:
        if value is None:
            return None
        return {"version": value.version, "logical_bytes": value.logical_bytes}

    return {
        "name": delta.name,
        "kind": delta.kind.value,
        "baseline": side(delta.baseline_distribution),
        "current": side(delta.current_distribution),
        "logical_bytes_delta": delta.logical_bytes_delta,
    }


def _validate_diff(diff: object) -> AnalysisDiff:
    if type(diff) is not AnalysisDiff:
        raise TypeError("diff must be an exact AnalysisDiff")
    # Dataclasses are immutable by convention only. Reapply the model's strict
    # invariants so a forged object cannot produce an invalid public document.
    diff.__post_init__()
    return diff


def _require_utf8_strings(value: object) -> None:
    """Reject lone surrogates before the public UTF-8 JSON boundary."""

    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if any("\ud800" <= character <= "\udfff" for character in item):
                raise ValueError("comparison JSON contains an invalid string")
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def comparison_diff_to_json_object(diff: AnalysisDiff) -> dict[str, object]:
    """Convert an exact, valid :class:`AnalysisDiff` to schema v1 JSON data."""

    diff = _validate_diff(diff)
    context = diff.baseline.resolution_context
    if type(context) is not BaselineResolutionContext:  # guarded by AnalysisDiff
        raise TypeError("comparison requires an exact BaselineResolutionContext")
    nonreconciliation_delta = (
        diff.distribution_logical_bytes_delta - diff.global_logical_bytes_delta
    )
    nonreconciliation_present = nonreconciliation_delta != 0
    document = {
        "schema_version": 1,
        "measurement": _measurement_to_json(diff),
        "context": {
            "input_kind": "fresh-install",
            "comparison_context_fingerprint": _comparison_context_fingerprint(context),
        },
        "baseline": _side_to_json(diff.baseline, diff.baseline_completeness.value),
        "current": _side_to_json(diff.current, diff.current_completeness.value),
        "changes": {
            "totals": {
                "global_logical_bytes_delta": diff.global_logical_bytes_delta,
                "distribution_logical_bytes_delta": diff.distribution_logical_bytes_delta,
            },
            "distributions": [
                _distribution_to_json(delta) for delta in diff.distributions
            ],
            "nonreconciliation": {
                "present": nonreconciliation_present,
                "distribution_minus_global_logical_bytes_delta": nonreconciliation_delta,
                "reason": (
                    _NONRECONCILIATION_REASON if nonreconciliation_present else None
                ),
            },
        },
        "completeness": diff.completeness.value,
    }
    _require_utf8_strings(document)
    return document


def render_comparison_json(diff: AnalysisDiff) -> str:
    """Render comparison schema v1 with stable indentation and one newline."""

    return (
        json.dumps(
            comparison_diff_to_json_object(diff),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
