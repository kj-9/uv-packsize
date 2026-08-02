"""Safe, immutable comparison inputs decoded from public analysis JSON.

This module deliberately accepts only the two committed public schemas.  It is
not a general JSON Schema implementation: keeping the closed-shape decoder
next to the comparison projection prevents a baseline from carrying raw
requirements, paths, symlink targets, or other irrelevant input details.
"""

from __future__ import annotations

import json
import os
import re
import stat
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, NoReturn, cast

from .json_render import _requirement_projection
from .models import (
    AnalysisResult,
    ProjectLockContext,
    ResolutionContext,
    normalize_distribution_name,
)

MAX_BASELINE_BYTES = 8 * 1024 * 1024
MAX_BASELINE_NESTING = 64
MAX_BASELINE_ITEMS = 100_000
MAX_BASELINE_STRING_CHARS = 1_000_000
MAX_BASELINE_INTEGER = (1 << 63) - 1

_NAME = re.compile(r"^[A-Za-z0-9]+(?:[-_.]+[A-Za-z0-9]+)*$")
_PATH = re.compile(
    r"^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\.{1,2}(?:/|$))(?!.*//)(?!.*\\)(?!.*\0).+$"
)
_SAFE_OBSERVATION = re.compile(
    r"^(?!\s)(?![\s\S]*\s$)(?![\s\S]*[\\/])(?!~)(?![A-Za-z]:)(?![\s\S]*\0)[\s\S]+$"
)
_INDEX_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_PROJECT_OBSERVATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
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
_WARNING_TARGET_KINDS = {
    "duplicate-ownership": "file",
    "duplicate-record-entry": "file",
    "filesystem-error": "file",
    "filesystem-layout-error": "distribution",
    "invalid-record": "distribution",
    "invalid-record-path": "distribution",
    "invalid-metadata": "distribution",
    "missing-file": "file",
    "missing-metadata": "distribution",
    "missing-record": "distribution",
    "missing-record-self-entry": "distribution",
    "record-path-outside-prefix": "distribution",
    "unsupported-file-type": "file",
}


class BaselineError(ValueError):
    """A sanitized baseline failure suitable for a future CLI boundary."""

    def __init__(self, code: str, field: str = "document") -> None:
        self.code = code
        self.field = field
        super().__init__(f"Invalid baseline JSON ({code} at {field}).")


class BaselineLoadError(BaselineError):
    """A sanitized file read failure; paths and OS diagnostics stay private."""

    def __init__(self, code: str) -> None:
        super().__init__(code, "file")


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineMeasurement:
    kind: str
    unit: str
    ownership: str
    deduplication: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineRequirement:
    input_index: int
    kind: str
    name: str | None
    extras: tuple[str, ...]
    has_specifier: bool
    has_marker: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineResolutionContext:
    requirements: tuple[BaselineRequirement, ...]
    python_version_fingerprint: str
    platform_fingerprint: str
    architecture_fingerprint: str
    path_flavor: str
    case_rule: str
    uv_version_fingerprint: str
    build_policy: str
    compile_bytecode: bool
    extras: tuple[str, ...]
    index_identifiers: tuple[str, ...]
    resolution_strategy_fingerprint: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineExistingPrefixContext:
    python_version_fingerprint: str | None
    platform_fingerprint: str | None
    architecture_fingerprint: str | None
    path_flavor: str
    case_rule: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineProjectLockContext:
    root_package: str
    workspace_member: str | None
    dependency_group_selection: str
    dependency_groups: tuple[str, ...]
    extras: tuple[str, ...]
    python_version_fingerprint: str
    platform_fingerprint: str
    architecture_fingerprint: str
    path_flavor: str
    case_rule: str
    uv_version_fingerprint: str
    build_policy: str
    compile_bytecode: bool
    resolution_strategy_fingerprint: str
    lock_identity: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineDistribution:
    name: str
    version: str
    logical_bytes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineWarningSummary:
    completeness: str
    warning_code_counts: tuple[tuple[str, int], ...]

    @property
    def is_incomplete(self) -> bool:
        return self.completeness == "incomplete"


@dataclass(frozen=True, slots=True, kw_only=True)
class BaselineDuplicateOwnershipSummary:
    present: bool
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Baseline:
    schema_version: int
    input_kind: str
    measurement: BaselineMeasurement
    global_logical_bytes: int
    distributions: tuple[BaselineDistribution, ...]
    warnings: BaselineWarningSummary
    duplicate_ownership: BaselineDuplicateOwnershipSummary
    resolution_context: BaselineResolutionContext | None
    existing_prefix_context: BaselineExistingPrefixContext | None
    project_lock_context: BaselineProjectLockContext | None = None


def _baseline_requirement_from_input(
    input_index: int, requirement: str
) -> BaselineRequirement:
    """Apply the public JSON requirement redaction without rendering JSON."""

    projection = _requirement_projection(input_index, requirement)
    return BaselineRequirement(
        input_index=cast(int, projection["input_index"]),
        kind=cast(str, projection["kind"]),
        name=cast(str | None, projection["name"]),
        extras=tuple(cast(list[str], projection["extras"])),
        has_specifier=cast(bool, projection["has_specifier"]),
        has_marker=cast(bool, projection["has_marker"]),
    )


def analysis_result_to_baseline(result: AnalysisResult) -> Baseline:
    """Project a fresh-install analysis into the safe v1 comparison model.

    This deliberately does not serialize the analysis result.  The projection
    mirrors the committed v1 JSON decoder while retaining only comparison
    fields, so requirements and free-form resolver observations remain
    non-reversible and file paths never enter the baseline representation.
    """

    if type(result) is not AnalysisResult:
        raise TypeError("result must be an exact AnalysisResult")
    if type(result.context) not in {ResolutionContext, ProjectLockContext}:
        raise TypeError("result must have a fresh or project-lock context")

    context = result.context
    distributions = tuple(
        BaselineDistribution(
            name=distribution.name,
            version=distribution.version,
            logical_bytes=distribution.total_logical_bytes,
        )
        for distribution in result.distributions
    )
    warning_counts = Counter(warning.code.value for warning in result.warnings)
    for distribution in result.distributions:
        warning_counts.update(warning.code.value for warning in distribution.warnings)
    warning_code_counts = tuple(sorted(warning_counts.items()))
    duplicate_count = len(result.duplicate_ownerships)
    global_logical_bytes = result.total_logical_bytes
    if any(
        value > MAX_BASELINE_INTEGER
        for value in (
            global_logical_bytes,
            *(distribution.logical_bytes for distribution in distributions),
            *(count for _, count in warning_code_counts),
            duplicate_count,
        )
    ):
        raise ValueError("analysis result exceeds baseline integer bounds")

    return Baseline(
        schema_version=1 if type(context) is ResolutionContext else 3,
        input_kind="fresh-install"
        if type(context) is ResolutionContext
        else "project-lock",
        measurement=BaselineMeasurement(
            kind="installed-logical-size",
            unit="bytes",
            ownership="distribution-owned-files",
            deduplication="canonical-identity",
        ),
        global_logical_bytes=global_logical_bytes,
        distributions=distributions,
        warnings=BaselineWarningSummary(
            completeness=result.completeness.value,
            warning_code_counts=warning_code_counts,
        ),
        duplicate_ownership=BaselineDuplicateOwnershipSummary(
            present=bool(duplicate_count), count=duplicate_count
        ),
        resolution_context=BaselineResolutionContext(
            requirements=tuple(
                _baseline_requirement_from_input(index, requirement)
                for index, requirement in enumerate(context.requirements)
            ),
            python_version_fingerprint=_fingerprint(
                "python_version", context.python_version
            ),
            platform_fingerprint=_fingerprint("platform", context.platform),
            architecture_fingerprint=_fingerprint("architecture", context.architecture),
            path_flavor=context.path_flavor.value,
            case_rule=context.case_rule.value,
            uv_version_fingerprint=_fingerprint("uv_version", context.uv_version),
            build_policy=context.build_policy.value,
            compile_bytecode=context.compile_bytecode,
            extras=context.extras,
            index_identifiers=context.index_identifiers,
            resolution_strategy_fingerprint=_fingerprint(
                "resolution_strategy", context.resolution_strategy
            ),
        )
        if type(context) is ResolutionContext
        else None,
        existing_prefix_context=None,
        project_lock_context=BaselineProjectLockContext(
            root_package=context.root_package,
            workspace_member=context.workspace_member,
            dependency_group_selection=context.dependency_group_selection.value,
            dependency_groups=context.dependency_groups,
            extras=context.extras,
            python_version_fingerprint=_fingerprint(
                "python_version", context.python_version
            ),
            platform_fingerprint=_fingerprint("platform", context.platform),
            architecture_fingerprint=_fingerprint("architecture", context.architecture),
            path_flavor=context.path_flavor.value,
            case_rule=context.case_rule.value,
            uv_version_fingerprint=_fingerprint("uv_version", context.uv_version),
            build_policy=context.build_policy.value,
            compile_bytecode=context.compile_bytecode,
            resolution_strategy_fingerprint=_fingerprint(
                "resolution_strategy", context.resolution_strategy
            ),
            lock_identity=context.lock_identity,
        )
        if type(context) is ProjectLockContext
        else None,
    )


def _error(code: str, field: str) -> NoReturn:
    raise BaselineError(code, field)


def _object(value: Any, field: str, keys: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _error("invalid-type", field)
    if set(value) != keys:
        _error("invalid-shape", field)
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        _error("invalid-type", field)
    return value


def _string(value: Any, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_BASELINE_STRING_CHARS
        or _has_surrogate(value)
        or (pattern is not None and not pattern.fullmatch(value))
    ):
        _error("invalid-value", field)
    return value


def _has_surrogate(value: str) -> bool:
    return any("\ud800" <= character <= "\udfff" for character in value)


def _nullable_observation(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _string(value, field, _SAFE_OBSERVATION)


def _project_observation(value: Any, field: str) -> str:
    """Validate a project target label before it can enter a fingerprint."""

    return _string(value, field, _PROJECT_OBSERVATION)


def _integer(value: Any, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > MAX_BASELINE_INTEGER
    ):
        _error("invalid-value", field)
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        _error("invalid-type", field)
    return value


def _constant(value: Any, expected: object, field: str) -> None:
    if value != expected or type(value) is not type(expected):
        _error("invalid-value", field)


def _fingerprint(field: str, value: str) -> str:
    """Return a domain-separated opaque comparison value for free-form context."""

    return sha256(f"uv-packsize-baseline-v1\0{field}\0{value}".encode()).hexdigest()


def _nullable_fingerprint(field: str, value: str | None) -> str | None:
    return None if value is None else _fingerprint(field, value)


def _parse_integer(value: str) -> int:
    digits = value[1:] if value.startswith("-") else value
    if len(digits) > 19:
        _error("integer-limit", "document")
    return int(value)


def _validate_nesting(document: object) -> None:
    pending: list[tuple[object, int]] = [(document, 1)]
    items = 0
    while pending:
        value, depth = pending.pop()
        items += 1
        if items > MAX_BASELINE_ITEMS:
            _error("item-limit", "document")
        if depth > MAX_BASELINE_NESTING:
            _error("nesting-limit", "document")
        if isinstance(value, dict):
            for key in value:
                if not isinstance(key, str) or _has_surrogate(key):
                    _error("invalid-value", "document")
                if len(key) > MAX_BASELINE_STRING_CHARS:
                    _error("string-limit", "document")
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            if _has_surrogate(value):
                _error("invalid-value", "document")
            if len(value) > MAX_BASELINE_STRING_CHARS:
                _error("string-limit", "document")


def _validate_measurement(value: Any) -> BaselineMeasurement:
    document = _object(
        value, "measurement", frozenset({"kind", "unit", "ownership", "deduplication"})
    )
    _constant(document["kind"], "installed-logical-size", "measurement.kind")
    _constant(document["unit"], "bytes", "measurement.unit")
    _constant(
        document["ownership"], "distribution-owned-files", "measurement.ownership"
    )
    _constant(
        document["deduplication"], "canonical-identity", "measurement.deduplication"
    )
    return BaselineMeasurement(**document)


def _validate_build_policy(value: Any) -> str:
    policy = _string(value, "context.build_policy")
    if policy not in {"wheel-only", "allow-build"}:
        _error("invalid-value", "context.build_policy")
    return policy


def _validate_warning(value: Any, field: str) -> tuple[str, str, str]:
    document = _object(
        value, field, frozenset({"code", "target_kind", "target_identity"})
    )
    code = _string(document["code"], f"{field}.code")
    if code not in _WARNING_CODES:
        _error("invalid-value", f"{field}.code")
    target_kind = document["target_kind"]
    if target_kind != _WARNING_TARGET_KINDS[code]:
        _error("invalid-value", f"{field}.target_kind")
    target_identity = _string(document["target_identity"], f"{field}.target_identity")
    if target_kind == "file":
        _string(target_identity, f"{field}.target_identity", _PATH)
    else:
        name, separator, version = target_identity.partition("==")
        if (
            separator != "=="
            or not version
            or normalize_distribution_name(
                _string(name, f"{field}.target_identity", _NAME)
            )
            != name
        ):
            _error("invalid-value", f"{field}.target_identity")
    return code, target_kind, target_identity


def _validate_files(value: Any, field: str) -> tuple[tuple[str, int, str, bool], ...]:
    files: list[tuple[str, int, str, bool]] = []
    identities: set[str] = set()
    for item in _array(value, field):
        document = _object(
            item,
            f"{field}[]",
            frozenset(
                {
                    "path",
                    "canonical_identity",
                    "logical_bytes",
                    "category",
                    "origin",
                    "is_symlink",
                }
            ),
        )
        _string(document["path"], f"{field}[].path", _PATH)
        identity = _string(
            document["canonical_identity"], f"{field}[].canonical_identity", _PATH
        )
        if identity in identities:
            _error("duplicate-file", field)
        identities.add(identity)
        logical_bytes = _integer(document["logical_bytes"], f"{field}[].logical_bytes")
        category = document["category"]
        if category not in {
            "python",
            "native",
            "data",
            "metadata",
            "script",
            "other",
        }:
            _error("invalid-value", f"{field}[].category")
        if document["origin"] not in {"record", "generated", "fallback", "discovered"}:
            _error("invalid-value", f"{field}[].origin")
        is_symlink = _boolean(document["is_symlink"], f"{field}[].is_symlink")
        files.append((identity, logical_bytes, category, is_symlink))
    return tuple(files)


def _validate_distributions(
    value: Any,
) -> tuple[
    tuple[BaselineDistribution, ...],
    int,
    dict[str, tuple[str, ...]],
    bool,
    Counter[str],
]:
    distributions: list[BaselineDistribution] = []
    identities: set[str] = set()
    files_by_identity: dict[str, tuple[int, str, bool]] = {}
    owners_by_identity: dict[str, set[str]] = {}
    has_incomplete_warning = False
    warning_counts: Counter[str] = Counter()
    for item in _array(value, "distributions"):
        document = _object(
            item,
            "distributions[]",
            frozenset(
                {"name", "version", "files", "warnings", "completeness", "totals"}
            ),
        )
        name = _string(document["name"], "distributions[].name", _NAME)
        normalized_name = normalize_distribution_name(name)
        if normalized_name in identities:
            _error("duplicate-distribution", "distributions")
        identities.add(normalized_name)
        version = _string(document["version"], "distributions[].version")
        files = _validate_files(document["files"], "distributions[].files")
        warnings = [
            _validate_warning(warning, "distributions[].warnings[]")
            for warning in _array(document["warnings"], "distributions[].warnings")
        ]
        warning_counts.update(code for code, _, _ in warnings)
        if any(code == "duplicate-ownership" for code, _, _ in warnings):
            _error("inconsistent-ownership", "distributions[].warnings")
        distribution_identity = f"{normalized_name}=={version}"
        if any(
            target_kind == "distribution" and target_identity != distribution_identity
            for _, target_kind, target_identity in warnings
        ):
            _error("inconsistent-warning", "distributions[].warnings")
        if document["completeness"] not in {"complete", "incomplete"}:
            _error("invalid-value", "distributions[].completeness")
        distribution_incomplete = any(
            code in _INCOMPLETE_WARNING_CODES for code, _, _ in warnings
        )
        if (document["completeness"] == "incomplete") != distribution_incomplete:
            _error("inconsistent-completeness", "distributions[].completeness")
        has_incomplete_warning = has_incomplete_warning or distribution_incomplete
        totals = _object(
            document["totals"], "distributions[].totals", frozenset({"logical_bytes"})
        )
        logical_bytes = _integer(
            totals["logical_bytes"], "distributions[].totals.logical_bytes"
        )
        if logical_bytes != sum(size for _, size, _, _ in files):
            _error("inconsistent-total", "distributions[].totals.logical_bytes")
        for identity, size, category, is_symlink in files:
            signature = (size, category, is_symlink)
            previous = files_by_identity.setdefault(identity, signature)
            if previous != signature:
                _error("inconsistent-file", "distributions[].files")
            owners_by_identity.setdefault(identity, set()).add(normalized_name)
        distributions.append(
            BaselineDistribution(
                name=normalized_name, version=version, logical_bytes=logical_bytes
            )
        )
    duplicate_owners = {
        identity: tuple(sorted(owners))
        for identity, owners in owners_by_identity.items()
        if len(owners) > 1
    }
    return (
        tuple(sorted(distributions, key=lambda item: (item.name, item.version))),
        sum(signature[0] for signature in files_by_identity.values()),
        duplicate_owners,
        has_incomplete_warning,
        warning_counts,
    )


def _validate_requirement(value: Any) -> BaselineRequirement:
    document = _object(
        value,
        "context.requirements[]",
        frozenset(
            {"input_index", "kind", "name", "extras", "has_specifier", "has_marker"}
        ),
    )
    name = document["name"]
    if name is not None:
        name = _string(name, "context.requirements[].name", _NAME)
        name = normalize_distribution_name(name)
    kind = _string(document["kind"], "context.requirements[].kind")
    if kind not in {"named", "direct-url", "local-path", "opaque"}:
        _error("invalid-value", "context.requirements[].kind")
    extras = tuple(
        sorted(
            normalize_distribution_name(
                _string(item, "context.requirements[].extras[]", _NAME)
            )
            for item in _array(document["extras"], "context.requirements[].extras")
        )
    )
    if len(set(extras)) != len(extras):
        _error("invalid-value", "context.requirements[].extras")
    has_specifier = _boolean(
        document["has_specifier"], "context.requirements[].has_specifier"
    )
    if (
        (kind == "named" and name is None)
        or (kind == "opaque" and (name is not None or extras or has_specifier))
        or (kind in {"direct-url", "local-path"} and has_specifier)
        or (name is None and extras)
    ):
        _error("inconsistent-requirement", "context.requirements")
    return BaselineRequirement(
        input_index=_integer(
            document["input_index"], "context.requirements[].input_index"
        ),
        kind=kind,
        name=name,
        extras=extras,
        has_specifier=has_specifier,
        has_marker=_boolean(
            document["has_marker"], "context.requirements[].has_marker"
        ),
    )


def _validate_context(  # noqa: PLR0912
    schema_version: int, value: Any
) -> tuple[
    str,
    BaselineResolutionContext | None,
    BaselineExistingPrefixContext | None,
    BaselineProjectLockContext | None,
]:
    if schema_version == 3:
        document = _object(
            value,
            "context",
            frozenset(
                {
                    "input_kind",
                    "root_package",
                    "workspace_member",
                    "dependency_group_selection",
                    "dependency_groups",
                    "extras",
                    "python_version",
                    "platform",
                    "architecture",
                    "path_flavor",
                    "case_rule",
                    "uv_version",
                    "build_policy",
                    "compile_bytecode",
                    "resolution_strategy",
                    "lock_identity",
                }
            ),
        )
        _constant(document["input_kind"], "project-lock", "context.input_kind")
        root_package = normalize_distribution_name(
            _string(document["root_package"], "context.root_package", _NAME)
        )
        workspace_member = document["workspace_member"]
        if workspace_member is not None:
            workspace_member = normalize_distribution_name(
                _string(workspace_member, "context.workspace_member", _NAME)
            )
            if workspace_member != root_package:
                _error("inconsistent-context", "context.workspace_member")
        selection = _string(
            document["dependency_group_selection"],
            "context.dependency_group_selection",
        )
        if selection not in {"none", "explicit", "all"}:
            _error("invalid-value", "context.dependency_group_selection")

        def names(field: str) -> tuple[str, ...]:
            result = tuple(
                sorted(
                    normalize_distribution_name(_string(item, field + "[]", _NAME))
                    for item in _array(document[field], field)
                )
            )
            if len(result) != len(set(result)):
                _error("invalid-value", field)
            return result

        groups, extras = names("dependency_groups"), names("extras")
        if (selection == "none" and groups) or (selection == "explicit" and not groups):
            _error("inconsistent-context", "context.dependency_groups")
        if document["path_flavor"] not in {"posix", "windows"} or document[
            "case_rule"
        ] not in {"sensitive", "insensitive"}:
            _error("invalid-value", "context")
        return (
            "project-lock",
            None,
            None,
            BaselineProjectLockContext(
                root_package=root_package,
                workspace_member=workspace_member,
                dependency_group_selection=selection,
                dependency_groups=groups,
                extras=extras,
                python_version_fingerprint=_fingerprint(
                    "python_version",
                    _project_observation(
                        document["python_version"], "context.python_version"
                    ),
                ),
                platform_fingerprint=_fingerprint(
                    "platform",
                    _project_observation(document["platform"], "context.platform"),
                ),
                architecture_fingerprint=_fingerprint(
                    "architecture",
                    _project_observation(
                        document["architecture"], "context.architecture"
                    ),
                ),
                path_flavor=document["path_flavor"],
                case_rule=document["case_rule"],
                uv_version_fingerprint=_fingerprint(
                    "uv_version",
                    _project_observation(document["uv_version"], "context.uv_version"),
                ),
                build_policy=_validate_build_policy(document["build_policy"]),
                compile_bytecode=_boolean(
                    document["compile_bytecode"], "context.compile_bytecode"
                ),
                resolution_strategy_fingerprint=_fingerprint(
                    "resolution_strategy",
                    _project_observation(
                        document["resolution_strategy"], "context.resolution_strategy"
                    ),
                ),
                lock_identity=_string(
                    document["lock_identity"],
                    "context.lock_identity",
                    re.compile(r"^[0-9a-f]{64}$"),
                ),
            ),
        )
    common = {
        "requirements",
        "python_version",
        "platform",
        "architecture",
        "path_flavor",
        "case_rule",
        "uv_version",
        "build_policy",
        "compile_bytecode",
        "extras",
        "index_identifiers",
        "resolution_strategy",
    }
    expected = frozenset(common | ({"input_kind"} if schema_version == 2 else set()))
    document = _object(value, "context", expected)
    if document["path_flavor"] not in {"posix", "windows"} or document[
        "case_rule"
    ] not in {"sensitive", "insensitive"}:
        _error("invalid-value", "context")
    if schema_version == 2:
        _constant(document["input_kind"], "existing-prefix", "context.input_kind")
        for field in ("requirements", "extras", "index_identifiers"):
            if _array(document[field], f"context.{field}"):
                _error("invalid-value", f"context.{field}")
        for field in (
            "uv_version",
            "build_policy",
            "compile_bytecode",
            "resolution_strategy",
        ):
            _constant(document[field], None, f"context.{field}")
        return (
            "existing-prefix",
            None,
            BaselineExistingPrefixContext(
                python_version_fingerprint=_nullable_fingerprint(
                    "existing-prefix.python_version",
                    _nullable_observation(
                        document["python_version"], "context.python_version"
                    ),
                ),
                platform_fingerprint=_nullable_fingerprint(
                    "existing-prefix.platform",
                    _nullable_observation(document["platform"], "context.platform"),
                ),
                architecture_fingerprint=_nullable_fingerprint(
                    "existing-prefix.architecture",
                    _nullable_observation(
                        document["architecture"], "context.architecture"
                    ),
                ),
                path_flavor=document["path_flavor"],
                case_rule=document["case_rule"],
            ),
            None,
        )
    requirements = tuple(
        _validate_requirement(item)
        for item in _array(document["requirements"], "context.requirements")
    )
    if not requirements:
        _error("invalid-value", "context.requirements")
    if tuple(requirement.input_index for requirement in requirements) != tuple(
        range(len(requirements))
    ):
        _error("inconsistent-requirement", "context.requirements")
    extras = tuple(
        sorted(
            normalize_distribution_name(_string(item, "context.extras[]", _NAME))
            for item in _array(document["extras"], "context.extras")
        )
    )
    indices = tuple(
        sorted(
            _string(item, "context.index_identifiers[]", _INDEX_IDENTIFIER)
            for item in _array(
                document["index_identifiers"], "context.index_identifiers"
            )
        )
    )
    if len(set(extras)) != len(extras) or len(set(indices)) != len(indices):
        _error("invalid-value", "context")
    return (
        "fresh-install",
        BaselineResolutionContext(
            requirements=requirements,
            python_version_fingerprint=_fingerprint(
                "python_version",
                _string(document["python_version"], "context.python_version"),
            ),
            platform_fingerprint=_fingerprint(
                "platform", _string(document["platform"], "context.platform")
            ),
            architecture_fingerprint=_fingerprint(
                "architecture",
                _string(document["architecture"], "context.architecture"),
            ),
            path_flavor=document["path_flavor"],
            case_rule=document["case_rule"],
            uv_version_fingerprint=_fingerprint(
                "uv_version", _string(document["uv_version"], "context.uv_version")
            ),
            build_policy=_validate_build_policy(document["build_policy"]),
            compile_bytecode=_boolean(
                document["compile_bytecode"], "context.compile_bytecode"
            ),
            extras=extras,
            index_identifiers=indices,
            resolution_strategy_fingerprint=_fingerprint(
                "resolution_strategy",
                _string(document["resolution_strategy"], "context.resolution_strategy"),
            ),
        ),
        None,
        None,
    )


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            _error("duplicate-key", "document")
        document[key] = value
    return document


def _decode_payload(payload: str | bytes | bytearray) -> str:
    """Accept UTF-8 only and reject a BOM rather than silently changing input."""

    if isinstance(payload, str):
        encoded = payload.encode("utf-8", "surrogatepass")
        text = payload
    else:
        encoded = bytes(payload)
        try:
            text = encoded.decode("utf-8")
        except UnicodeDecodeError:
            _error("unsupported-encoding", "document")
    if len(encoded) > MAX_BASELINE_BYTES:
        _error("size-limit", "document")
    if text.startswith("\ufeff"):
        _error("unsupported-encoding", "document")
    return text


def parse_baseline_json(  # noqa: PLR0912, PLR0915
    payload: str | bytes | bytearray,
) -> Baseline:
    """Decode public v1/v2 JSON without filesystem access or raw diagnostics."""

    if not isinstance(payload, (str, bytes, bytearray)):
        raise TypeError("payload must be str, bytes, or bytearray")
    payload_text = _decode_payload(payload)
    try:
        document = json.loads(
            payload_text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_int=_parse_integer,
        )
    except BaselineError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError, ValueError):
        _error("malformed-json", "document")
    _validate_nesting(document)
    root = _object(
        document,
        "document",
        frozenset(
            {
                "schema_version",
                "measurement",
                "context",
                "distributions",
                "warnings",
                "duplicate_ownerships",
                "completeness",
                "totals",
            }
        ),
    )
    schema_version = _integer(root["schema_version"], "schema_version")
    if schema_version not in {1, 2, 3}:
        _error("unsupported-schema", "schema_version")
    measurement = _validate_measurement(root["measurement"])
    input_kind, resolution_context, existing_prefix_context, project_lock_context = (
        _validate_context(schema_version, root["context"])
    )
    (
        distributions,
        expected_global_bytes,
        expected_duplicate_owners,
        has_distribution_incomplete_warning,
        distribution_warning_counts,
    ) = _validate_distributions(root["distributions"])
    warning_counts = distribution_warning_counts
    duplicate_warning_identities: set[str] = set()
    for warning in _array(root["warnings"], "warnings"):
        code, target_kind, target_identity = _validate_warning(warning, "warnings[]")
        warning_counts[code] += 1
        if code == "duplicate-ownership":
            if target_kind != "file" or target_identity in duplicate_warning_identities:
                _error("inconsistent-ownership", "warnings")
            duplicate_warning_identities.add(target_identity)
    duplicate_ownerships = _array(root["duplicate_ownerships"], "duplicate_ownerships")
    declared_duplicate_owners: dict[str, tuple[str, ...]] = {}
    for duplicate in duplicate_ownerships:
        item = _object(
            duplicate,
            "duplicate_ownerships[]",
            frozenset({"canonical_identity", "owners"}),
        )
        _string(
            item["canonical_identity"],
            "duplicate_ownerships[].canonical_identity",
            _PATH,
        )
        identity = _string(
            item["canonical_identity"],
            "duplicate_ownerships[].canonical_identity",
            _PATH,
        )
        owners = [
            normalize_distribution_name(
                _string(owner, "duplicate_ownerships[].owners[]", _NAME)
            )
            for owner in _array(item["owners"], "duplicate_ownerships[].owners")
        ]
        if (
            len(owners) < 2
            or len(set(owners)) != len(owners)
            or identity in declared_duplicate_owners
        ):
            _error("invalid-value", "duplicate_ownerships[].owners")
        declared_duplicate_owners[identity] = tuple(sorted(owners))
    if declared_duplicate_owners != expected_duplicate_owners:
        _error("inconsistent-ownership", "duplicate_ownerships")
    if duplicate_warning_identities != set(expected_duplicate_owners):
        _error("inconsistent-ownership", "warnings")
    completeness = root["completeness"]
    if completeness not in {"complete", "incomplete"}:
        _error("invalid-value", "completeness")
    has_incomplete_warning = has_distribution_incomplete_warning or any(
        code in _INCOMPLETE_WARNING_CODES for code in warning_counts
    )
    if (completeness == "incomplete") != has_incomplete_warning:
        _error("inconsistent-completeness", "completeness")
    totals = _object(
        root["totals"],
        "totals",
        frozenset({"global_logical_bytes", "distribution_logical_bytes"}),
    )
    global_bytes = _integer(
        totals["global_logical_bytes"], "totals.global_logical_bytes"
    )
    distribution_bytes = _integer(
        totals["distribution_logical_bytes"], "totals.distribution_logical_bytes"
    )
    if global_bytes != expected_global_bytes:
        _error("inconsistent-total", "totals.global_logical_bytes")
    if distribution_bytes != sum(item.logical_bytes for item in distributions):
        _error("inconsistent-total", "totals.distribution_logical_bytes")
    return Baseline(
        schema_version=schema_version,
        input_kind=input_kind,
        measurement=measurement,
        global_logical_bytes=global_bytes,
        distributions=distributions,
        warnings=BaselineWarningSummary(
            completeness=completeness,
            warning_code_counts=tuple(sorted(warning_counts.items())),
        ),
        duplicate_ownership=BaselineDuplicateOwnershipSummary(
            present=bool(duplicate_ownerships), count=len(duplicate_ownerships)
        ),
        resolution_context=resolution_context,
        existing_prefix_context=existing_prefix_context,
        project_lock_context=project_lock_context,
    )


def load_baseline(path: Path) -> Baseline:  # noqa: PLR0912
    """Read one bounded regular file without exposing its path or OS errors."""

    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    try:
        initial = path.lstat()
        if stat.S_ISLNK(initial.st_mode):
            raise BaselineLoadError("symlink")
        if not stat.S_ISREG(initial.st_mode):
            raise BaselineLoadError("not-regular-file")
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
    except BaselineLoadError:
        raise
    except OSError as error:
        raise BaselineLoadError("read-failed") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise BaselineLoadError("not-regular-file")
        if (opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino):
            raise BaselineLoadError("changed-file")
        chunks: list[bytes] = []
        remaining = MAX_BASELINE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > MAX_BASELINE_BYTES:
            raise BaselineLoadError("size-limit")
    except BaselineLoadError:
        raise
    except OSError as error:
        raise BaselineLoadError("read-failed") from error
    finally:
        os.close(descriptor)
    return parse_baseline_json(payload)
