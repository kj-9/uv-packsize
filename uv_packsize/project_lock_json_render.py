"""Pure schema-v3 JSON rendering for project-lock analyses.

This intentionally lives beside, rather than inside, the v1/v2 renderer so
the closed older serializer and its byte contract cannot change accidentally.
"""

from __future__ import annotations

import json

from .json_render import _warning_to_json
from .models import AnalysisResult, ProjectLockContext


def project_lock_analysis_to_json_object(result: AnalysisResult) -> dict[str, object]:
    """Convert an exact project-lock analysis to the closed v3 document."""

    if type(result) is not AnalysisResult:
        raise TypeError("result must be an exact AnalysisResult")
    if type(result.context) is not ProjectLockContext:
        raise TypeError("schema v3 requires an exact ProjectLockContext")
    context = result.context
    distribution_total = sum(item.total_logical_bytes for item in result.distributions)
    return {
        "schema_version": 3,
        "measurement": {
            "kind": "installed-logical-size",
            "unit": "bytes",
            "ownership": "distribution-owned-files",
            "deduplication": "canonical-identity",
        },
        "context": {
            "input_kind": "project-lock",
            "root_package": context.root_package,
            "workspace_member": context.workspace_member,
            "dependency_group_selection": context.dependency_group_selection.value,
            "dependency_groups": list(context.dependency_groups),
            "extras": list(context.extras),
            "python_version": context.python_version,
            "platform": context.platform,
            "architecture": context.architecture,
            "path_flavor": context.path_flavor.value,
            "case_rule": context.case_rule.value,
            "uv_version": context.uv_version,
            "build_policy": context.build_policy.value,
            "compile_bytecode": context.compile_bytecode,
            "resolution_strategy": context.resolution_strategy,
            "lock_identity": context.lock_identity,
        },
        "distributions": [
            {
                "name": distribution.name,
                "version": distribution.version,
                "files": [
                    {
                        "path": file.path,
                        "canonical_identity": file.canonical_identity,
                        "logical_bytes": file.logical_bytes,
                        "category": file.category.value,
                        "origin": file.origin.value,
                        "is_symlink": file.symlink_target is not None,
                    }
                    for file in distribution.files
                ],
                "warnings": [
                    _warning_to_json(warning) for warning in distribution.warnings
                ],
                "completeness": distribution.completeness.value,
                "totals": {"logical_bytes": distribution.total_logical_bytes},
            }
            for distribution in result.distributions
        ],
        "warnings": [_warning_to_json(warning) for warning in result.warnings],
        "duplicate_ownerships": [
            {"canonical_identity": item.canonical_identity, "owners": list(item.owners)}
            for item in result.duplicate_ownerships
        ],
        "completeness": result.completeness.value,
        "totals": {
            "global_logical_bytes": result.total_logical_bytes,
            "distribution_logical_bytes": distribution_total,
        },
    }


def render_project_lock_analysis_json(result: AnalysisResult) -> str:
    """Render a deterministic schema-v3 analysis document with one newline."""

    return (
        json.dumps(
            project_lock_analysis_to_json_object(result),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
