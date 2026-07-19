"""Deterministic, safe JSON rendering for :class:`AnalysisResult`.

Schema v1 is a major compatibility boundary: incompatible public changes must
use a later schema version. This module is deliberately pure; CLI output and
its error/exit contract are connected separately.
"""

import json
import re

from uv_packsize.models import AnalysisResult, AnalysisWarning, ResolutionContext

_NORMALIZED_NAME_SEPARATOR = re.compile(r"[-_.]+")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9]+(?:[-_.]+[A-Za-z0-9]+)*$")
_REQUIREMENT_PREFIX = re.compile(
    r"^(?P<name>[A-Za-z0-9]+(?:[-_.]+[A-Za-z0-9]+)*)(?:\[(?P<extras>[^\]]*)\])?(?P<rest>.*)$"
)
_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://[^\s/][^\s]*$")
_FILE_URI = re.compile(r"^file:///[^\s]+$")
_FILE_ABSOLUTE_URI = re.compile(r"^file:/[^/\s][^\s]*$")
_FILE_NETWORK_URI = re.compile(r"^file://[^/\s]+/[^\s]+$")
_VCS_FILE_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*\+file:///[^\s]+$")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_WINDOWS_UNC_PATH = re.compile(r"^\\\\[^\\/]+[\\/][^\\/]+(?:[\\/].*)?$")
_SPECIFIER = re.compile(r"(?:===|==|!=|<=|>=|~=|<|>)")


def _normalized_name(value: str) -> str | None:
    if not _SAFE_NAME.fullmatch(value):
        return None
    return _NORMALIZED_NAME_SEPARATOR.sub("-", value).lower()


def _safe_extras(value: str | None) -> list[str]:
    if value is None:
        return []
    return sorted(
        {
            normalized
            for extra in value.split(",")
            if (normalized := _normalized_name(extra.strip())) is not None
        }
    )


def _is_local_path(value: str) -> bool:
    return (
        value.startswith(("./", "../", "/", "~/", ".\\", "..\\", "~\\"))
        or _WINDOWS_ABSOLUTE_PATH.match(value) is not None
        or _WINDOWS_UNC_PATH.fullmatch(value) is not None
        or _FILE_URI.fullmatch(value) is not None
        or _FILE_ABSOLUTE_URI.fullmatch(value) is not None
        or _FILE_NETWORK_URI.fullmatch(value) is not None
    )


def _target_kind(value: str) -> str:
    if _is_local_path(value):
        return "local-path"
    if _VCS_FILE_URI.fullmatch(value) is not None:
        return "direct-url"
    if _URI.fullmatch(value) is not None:
        return "direct-url"
    return "opaque"


def _requirement_projection(input_index: int, requirement: str) -> dict[str, object]:
    """Return a non-reversible requirement summary that cannot leak raw input."""

    marker_part = requirement.split(";", maxsplit=1)
    marker_free = marker_part[0].strip()
    has_marker = len(marker_part) == 2

    kind = _target_kind(marker_free)
    if kind != "opaque":
        name = None
        extras = []
        has_specifier = False
    elif (match := _REQUIREMENT_PREFIX.fullmatch(marker_free)) is not None:
        name = _normalized_name(match.group("name"))
        extras = _safe_extras(match.group("extras"))
        remainder = match.group("rest").strip()
        if remainder.startswith("@"):
            target = remainder[1:].strip()
            kind = _target_kind(target)
            if kind == "opaque":
                name = None
                extras = []
            has_specifier = False
        elif not remainder or _SPECIFIER.match(remainder) is not None:
            kind = "named"
            has_specifier = bool(remainder)
        else:
            kind = "opaque"
            name = None
            extras = []
            has_specifier = False
    else:
        kind = "opaque"
        name = None
        extras = []
        has_specifier = False

    return {
        "input_index": input_index,
        "kind": kind,
        "name": name,
        "extras": extras,
        "has_specifier": has_specifier,
        "has_marker": has_marker,
    }


def _context_to_json(context: ResolutionContext) -> dict[str, object]:
    return {
        "requirements": [
            _requirement_projection(index, requirement)
            for index, requirement in enumerate(context.requirements)
        ],
        "python_version": context.python_version,
        "platform": context.platform,
        "architecture": context.architecture,
        "path_flavor": context.path_flavor.value,
        "case_rule": context.case_rule.value,
        "uv_version": context.uv_version,
        "build_policy": context.build_policy.value,
        "compile_bytecode": context.compile_bytecode,
        "extras": list(context.extras),
        "index_identifiers": list(context.index_identifiers),
        "resolution_strategy": context.resolution_strategy,
    }


def _warning_to_json(warning: AnalysisWarning) -> dict[str, str]:
    return {
        "code": warning.code.value,
        "target_kind": warning.target_kind.value,
        "target_identity": warning.target_identity,
    }


def analysis_result_to_json_object(result: AnalysisResult) -> dict[str, object]:
    """Convert an analysis model to the ordered public schema-v1 object."""

    if not isinstance(result, AnalysisResult):
        raise TypeError("result must be an AnalysisResult")

    distribution_total = sum(
        distribution.total_logical_bytes for distribution in result.distributions
    )
    return {
        "schema_version": 1,
        "measurement": {
            "kind": "installed-logical-size",
            "unit": "bytes",
            "ownership": "distribution-owned-files",
            "deduplication": "canonical-identity",
        },
        "context": _context_to_json(result.context),
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
            {
                "canonical_identity": ownership.canonical_identity,
                "owners": list(ownership.owners),
            }
            for ownership in result.duplicate_ownerships
        ],
        "completeness": result.completeness.value,
        "totals": {
            "global_logical_bytes": result.total_logical_bytes,
            "distribution_logical_bytes": distribution_total,
        },
    }


def render_analysis_json(result: AnalysisResult) -> str:
    """Render schema v1 with stable whitespace and exactly one trailing newline."""

    return (
        json.dumps(
            analysis_result_to_json_object(result),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
