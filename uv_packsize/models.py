"""Immutable result models for installed file-size analysis.

This module deliberately has no filesystem or subprocess dependencies. Inventory
collectors are responsible for producing canonical file identities before they
construct these values.
"""

import re
from dataclasses import dataclass
from enum import Enum

_NORMALIZED_NAME_SEPARATOR = re.compile(r"[-_.]+")
_VALID_DISTRIBUTION_NAME = re.compile(r"^[A-Za-z0-9]+(?:[-_.]+[A-Za-z0-9]+)*$")
_VALID_INDEX_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"{field_name} must not have surrounding whitespace")
    if "\0" in value:
        raise ValueError(f"{field_name} must not contain NUL")


def _non_empty_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{field_name} must be a tuple of strings, not a string")
    result = tuple(values)
    if not result:
        raise ValueError(f"{field_name} must not be empty")
    for value in result:
        _require_non_empty(value, field_name)
    return result


def _string_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{field_name} must be a tuple of strings, not a string")
    result = tuple(values)
    for value in result:
        _require_non_empty(value, field_name)
    return result


def normalize_distribution_name(value: str) -> str:
    """Return the PEP 503 normalized form of a distribution name.

    The value is deliberately validated before normalizing so callers in other
    pure model modules can share the same identifier boundary as the analysis
    inventory.  This function has no packaging-metadata or filesystem
    dependency.
    """

    _require_non_empty(value, "name")
    if not _VALID_DISTRIBUTION_NAME.fullmatch(value):
        raise ValueError("name must be a valid distribution name")
    normalized = _NORMALIZED_NAME_SEPARATOR.sub("-", value).lower()
    return normalized


# Private compatibility alias for the existing model implementation.  New
# modules should use the public name above.
_normalized_name = normalize_distribution_name


def _validate_lexical_path(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if "\0" in value:
        raise ValueError(f"{field_name} must not contain NUL")
    if "\\" in value:
        raise ValueError(f"{field_name} must use '/' separators")
    if value.startswith("/") or _WINDOWS_DRIVE_PATH.match(value):
        raise ValueError(f"{field_name} must be relative to the measurement prefix")
    components = value.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise ValueError(f"{field_name} must be a normalized lexical path")


def _validate_canonical_identity(value: str) -> None:
    _validate_lexical_path(value, "canonical_identity")


def _normalized_distribution_identity(value: str) -> str:
    _require_non_empty(value, "target_identity")
    name, separator, version = value.partition("==")
    if separator != "==":
        raise ValueError("distribution target_identity must use name==version")
    _require_non_empty(version, "target_identity version")
    return f"{_normalized_name(name)}=={version}"


class FileCategory(str, Enum):
    """Stable categories used to group installed files."""

    PYTHON = "python"
    NATIVE = "native"
    DATA = "data"
    METADATA = "metadata"
    SCRIPT = "script"
    OTHER = "other"


class FileOrigin(str, Enum):
    """How an inventory collector learned about a file.

    ``RECORD`` is an exact installed-metadata entry, ``GENERATED`` is a file
    derived from one (for example bytecode), ``FALLBACK`` is a conservative
    substitute used because authoritative metadata is unavailable, and
    ``DISCOVERED`` is found by an explicit supplemental scan policy.
    """

    RECORD = "record"
    GENERATED = "generated"
    FALLBACK = "fallback"
    DISCOVERED = "discovered"


class BuildPolicy(str, Enum):
    """Whether resolution may execute an sdist build backend."""

    WHEEL_ONLY = "wheel-only"
    ALLOW_BUILD = "allow-build"


class PathFlavor(str, Enum):
    """Lexical path semantics used by the measured target environment."""

    POSIX = "posix"
    WINDOWS = "windows"


class CaseRule(str, Enum):
    """Case comparison rule used for canonical installed-file identities."""

    SENSITIVE = "sensitive"
    INSENSITIVE = "insensitive"


class WarningCode(str, Enum):
    """Machine-readable conditions that affect an analysis."""

    DUPLICATE_OWNERSHIP = "duplicate-ownership"
    DUPLICATE_RECORD_ENTRY = "duplicate-record-entry"
    FILESYSTEM_ERROR = "filesystem-error"
    FILESYSTEM_LAYOUT_ERROR = "filesystem-layout-error"
    INVALID_RECORD = "invalid-record"
    INVALID_RECORD_PATH = "invalid-record-path"
    INVALID_METADATA = "invalid-metadata"
    MISSING_FILE = "missing-file"
    MISSING_METADATA = "missing-metadata"
    MISSING_RECORD = "missing-record"
    MISSING_RECORD_SELF_ENTRY = "missing-record-self-entry"
    RECORD_PATH_OUTSIDE_PREFIX = "record-path-outside-prefix"
    UNSUPPORTED_FILE_TYPE = "unsupported-file-type"

    @property
    def causes_incomplete_result(self) -> bool:
        return self in {
            self.INVALID_RECORD,
            self.INVALID_RECORD_PATH,
            self.INVALID_METADATA,
            self.FILESYSTEM_ERROR,
            self.FILESYSTEM_LAYOUT_ERROR,
            self.MISSING_FILE,
            self.MISSING_METADATA,
            self.MISSING_RECORD,
            self.MISSING_RECORD_SELF_ENTRY,
            self.RECORD_PATH_OUTSIDE_PREFIX,
            self.UNSUPPORTED_FILE_TYPE,
        }


class WarningTargetKind(str, Enum):
    """Namespace for a warning target identity."""

    DISTRIBUTION = "distribution"
    FILE = "file"


class Completeness(str, Enum):
    """Whether the inventory can be treated as a complete measurement."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalysisWarning:
    """A deterministic warning identified by code and affected target."""

    code: WarningCode
    target_kind: WarningTargetKind
    target_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, WarningCode):
            raise TypeError("code must be a WarningCode")
        if not isinstance(self.target_kind, WarningTargetKind):
            raise TypeError("target_kind must be a WarningTargetKind")
        expected_kind = {
            WarningCode.DUPLICATE_OWNERSHIP: WarningTargetKind.FILE,
            WarningCode.DUPLICATE_RECORD_ENTRY: WarningTargetKind.FILE,
            WarningCode.FILESYSTEM_ERROR: WarningTargetKind.FILE,
            WarningCode.FILESYSTEM_LAYOUT_ERROR: WarningTargetKind.DISTRIBUTION,
            WarningCode.INVALID_RECORD: WarningTargetKind.DISTRIBUTION,
            WarningCode.INVALID_RECORD_PATH: WarningTargetKind.DISTRIBUTION,
            WarningCode.INVALID_METADATA: WarningTargetKind.DISTRIBUTION,
            WarningCode.MISSING_FILE: WarningTargetKind.FILE,
            WarningCode.MISSING_METADATA: WarningTargetKind.DISTRIBUTION,
            WarningCode.MISSING_RECORD: WarningTargetKind.DISTRIBUTION,
            WarningCode.MISSING_RECORD_SELF_ENTRY: WarningTargetKind.DISTRIBUTION,
            WarningCode.RECORD_PATH_OUTSIDE_PREFIX: WarningTargetKind.DISTRIBUTION,
            WarningCode.UNSUPPORTED_FILE_TYPE: WarningTargetKind.FILE,
        }[self.code]
        if self.target_kind is not expected_kind:
            raise ValueError(
                f"{self.code.value} warning requires a {expected_kind.value} target"
            )
        if self.target_kind is WarningTargetKind.FILE:
            _validate_lexical_path(self.target_identity, "target_identity")
        else:
            object.__setattr__(
                self,
                "target_identity",
                _normalized_distribution_identity(self.target_identity),
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DuplicateOwnership:
    """One lexical installed path claimed by multiple distributions."""

    canonical_identity: str
    owners: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_canonical_identity(self.canonical_identity)
        if isinstance(self.owners, str):
            raise TypeError("owners must be a tuple of distribution names")
        owners = tuple(sorted({_normalized_name(owner) for owner in self.owners}))
        if len(owners) < 2:
            raise ValueError("duplicate ownership must have at least two owners")
        object.__setattr__(self, "owners", owners)


def _warnings(
    values: tuple[AnalysisWarning, ...],
) -> tuple[AnalysisWarning, ...]:
    result = tuple(values)
    if any(not isinstance(warning, AnalysisWarning) for warning in result):
        raise TypeError("warnings must contain AnalysisWarning values")
    return tuple(
        sorted(
            set(result),
            key=lambda warning: (
                warning.code.value,
                warning.target_kind.value,
                warning.target_identity,
            ),
        )
    )


def _completeness(warnings: tuple[AnalysisWarning, ...]) -> Completeness:
    if any(warning.code.causes_incomplete_result for warning in warnings):
        return Completeness.INCOMPLETE
    return Completeness.COMPLETE


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolutionContext:
    """Conditions that must match before two analysis results are compared.

    ``index_identifiers`` are ASCII symbolic aliases only, never URLs, paths, or
    credentials. The model stores identities only; it does not contact indexes.
    """

    requirements: tuple[str, ...]
    python_version: str
    platform: str
    architecture: str
    path_flavor: PathFlavor
    case_rule: CaseRule
    uv_version: str
    build_policy: BuildPolicy
    compile_bytecode: bool
    extras: tuple[str, ...] = ()
    index_identifiers: tuple[str, ...] = ()
    resolution_strategy: str = "highest"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requirements",
            _non_empty_tuple(self.requirements, "requirements"),
        )
        for field_name in (
            "python_version",
            "platform",
            "architecture",
            "uv_version",
            "resolution_strategy",
        ):
            _require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.path_flavor, PathFlavor):
            raise TypeError("path_flavor must be a PathFlavor")
        if not isinstance(self.case_rule, CaseRule):
            raise TypeError("case_rule must be a CaseRule")
        object.__setattr__(
            self,
            "extras",
            tuple(
                sorted(
                    {
                        _normalized_name(extra)
                        for extra in _string_tuple(self.extras, "extras")
                    }
                )
            ),
        )
        index_identifiers = _string_tuple(
            self.index_identifiers,
            "index_identifiers",
        )
        if any(
            not _VALID_INDEX_IDENTIFIER.fullmatch(identifier)
            for identifier in index_identifiers
        ):
            raise ValueError(
                "index_identifiers must contain ASCII symbolic aliases only"
            )
        object.__setattr__(
            self,
            "index_identifiers",
            tuple(sorted(set(index_identifiers))),
        )
        if not isinstance(self.build_policy, BuildPolicy):
            raise TypeError("build_policy must be a BuildPolicy")
        if not isinstance(self.compile_bytecode, bool):
            raise TypeError("compile_bytecode must be a bool")


@dataclass(frozen=True, slots=True, kw_only=True)
class FileEntry:
    """One included file, without distribution ownership information.

    ``canonical_identity`` is a lexical installed path supplied by the inventory
    collector after prefix-relative, separator, and platform case normalization.
    A symlink target is recorded separately and never changes file identity.
    """

    path: str
    canonical_identity: str
    logical_bytes: int
    category: FileCategory
    origin: FileOrigin
    symlink_target: str | None = None

    def __post_init__(self) -> None:
        _validate_lexical_path(self.path, "path")
        _validate_canonical_identity(self.canonical_identity)
        if (
            not isinstance(self.logical_bytes, int)
            or isinstance(self.logical_bytes, bool)
            or self.logical_bytes < 0
        ):
            raise ValueError("logical_bytes must be a non-negative integer")
        if not isinstance(self.category, FileCategory):
            raise TypeError("category must be a FileCategory")
        if not isinstance(self.origin, FileOrigin):
            raise TypeError("origin must be a FileOrigin")
        if self.symlink_target is not None:
            if not isinstance(self.symlink_target, str) or not self.symlink_target:
                raise ValueError("symlink_target must be a non-empty string")
            if "\0" in self.symlink_target:
                raise ValueError("symlink_target must not contain NUL")


@dataclass(frozen=True, slots=True, kw_only=True)
class DistributionResult:
    """Resolved distribution and the files it owns."""

    name: str
    version: str
    files: tuple[FileEntry, ...]
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _normalized_name(self.name))
        _require_non_empty(self.version, "version")

        files = tuple(self.files)
        if any(not isinstance(file, FileEntry) for file in files):
            raise TypeError("files must contain FileEntry values")
        identities = [file.canonical_identity for file in files]
        if len(identities) != len(set(identities)):
            raise ValueError(
                "a distribution cannot contain duplicate canonical identities"
            )
        object.__setattr__(
            self,
            "files",
            tuple(sorted(files, key=lambda file: (file.canonical_identity, file.path))),
        )
        object.__setattr__(self, "warnings", _warnings(self.warnings))
        if any(
            warning.code is WarningCode.DUPLICATE_OWNERSHIP for warning in self.warnings
        ):
            raise ValueError(
                "duplicate ownership warnings are derived by AnalysisResult"
            )
        distribution_identity = f"{self.name}=={self.version}"
        if any(
            warning.target_kind is WarningTargetKind.DISTRIBUTION
            and warning.target_identity != distribution_identity
            for warning in self.warnings
        ):
            raise ValueError("distribution warning target must match its distribution")

    @property
    def total_logical_bytes(self) -> int:
        return sum(file.logical_bytes for file in self.files)

    @property
    def completeness(self) -> Completeness:
        return _completeness(self.warnings)


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalysisResult:
    """A complete analysis with totals derived from its file inventory."""

    context: ResolutionContext
    distributions: tuple[DistributionResult, ...]
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.context, ResolutionContext):
            raise TypeError("context must be a ResolutionContext")

        distributions = tuple(self.distributions)
        if any(
            not isinstance(distribution, DistributionResult)
            for distribution in distributions
        ):
            raise TypeError("distributions must contain DistributionResult values")
        names = [distribution.name for distribution in distributions]
        if len(names) != len(set(names)):
            raise ValueError("an analysis cannot contain duplicate distribution names")
        distributions = tuple(
            sorted(
                distributions,
                key=lambda distribution: (distribution.name, distribution.version),
            )
        )
        object.__setattr__(self, "distributions", distributions)

        supplied_warnings = _warnings(self.warnings)
        if any(
            warning.code is WarningCode.DUPLICATE_OWNERSHIP
            for warning in supplied_warnings
        ):
            raise ValueError(
                "duplicate ownership warnings are derived by AnalysisResult"
            )

        signatures_by_identity: dict[str, tuple[int, FileCategory, str | None]] = {}
        for distribution in distributions:
            for file in distribution.files:
                signature = (file.logical_bytes, file.category, file.symlink_target)
                previous_signature = signatures_by_identity.setdefault(
                    file.canonical_identity, signature
                )
                if previous_signature != signature:
                    raise ValueError(
                        "files with the same canonical identity must have the same "
                        "logical size, category, and symlink target"
                    )

        derived_warnings = (
            AnalysisWarning(
                code=WarningCode.DUPLICATE_OWNERSHIP,
                target_kind=WarningTargetKind.FILE,
                target_identity=ownership.canonical_identity,
            )
            for ownership in self.duplicate_ownerships
        )
        object.__setattr__(
            self,
            "warnings",
            _warnings((*supplied_warnings, *derived_warnings)),
        )

    @property
    def duplicate_ownerships(self) -> tuple[DuplicateOwnership, ...]:
        owners_by_identity: dict[str, set[str]] = {}
        for distribution in self.distributions:
            for file in distribution.files:
                owners_by_identity.setdefault(file.canonical_identity, set()).add(
                    distribution.name
                )
        return tuple(
            DuplicateOwnership(
                canonical_identity=identity,
                owners=tuple(owners),
            )
            for identity, owners in sorted(owners_by_identity.items())
            if len(owners) > 1
        )

    @property
    def total_logical_bytes(self) -> int:
        sizes_by_identity = {
            file.canonical_identity: file.logical_bytes
            for distribution in self.distributions
            for file in distribution.files
        }
        return sum(sizes_by_identity.values())

    @property
    def completeness(self) -> Completeness:
        if _completeness(self.warnings) is Completeness.INCOMPLETE:
            return Completeness.INCOMPLETE
        if any(
            distribution.completeness is Completeness.INCOMPLETE
            for distribution in self.distributions
        ):
            return Completeness.INCOMPLETE
        return Completeness.COMPLETE
