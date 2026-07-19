"""Filesystem inventory collection with target-platform path semantics."""

import csv
import os
import re
import stat
from dataclasses import dataclass
from email.parser import BytesParser
from enum import Enum
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

from uv_packsize.models import (
    AnalysisWarning,
    DistributionResult,
    FileCategory,
    FileEntry,
    FileOrigin,
    WarningCode,
    WarningTargetKind,
)


class PathFlavor(str, Enum):
    POSIX = "posix"
    WINDOWS = "windows"


class CaseRule(str, Enum):
    SENSITIVE = "sensitive"
    INSENSITIVE = "insensitive"


class RecordPathError(ValueError):
    """Base class for a RECORD path that cannot be collected safely."""


class InvalidRecordPathError(RecordPathError):
    """A syntactically invalid path for the selected target flavor."""


class RecordPathOutsidePrefixError(RecordPathError):
    """A valid target path that is not contained by the measurement prefix."""


class InventoryError(ValueError):
    """Installed metadata cannot identify a valid distribution."""


class FilesystemInventoryError(InventoryError):
    """A filesystem entry could not be inspected reliably."""


_RECORD_HASH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*=[A-Za-z0-9_-]+$")
_RECORD_SIZE = re.compile(r"^[0-9]+$")
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def _validate_windows_component(component: str) -> None:
    if (
        component.endswith((".", " "))
        or any(character in '<>:"|?*' or ord(character) < 32 for character in component)
        or component.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_NAMES
    ):
        raise InvalidRecordPathError(
            "RECORD path contains an invalid Windows component"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedRecordPath:
    physical_path: Path
    path: str
    canonical_identity: str


def _pure_path(value: str, flavor: PathFlavor) -> PurePath:
    if not value or "\0" in value:
        raise InvalidRecordPathError("RECORD path must be non-empty and contain no NUL")
    if flavor is PathFlavor.POSIX:
        if "\\" in value:
            raise InvalidRecordPathError(
                "POSIX RECORD paths cannot contain backslashes"
            )
        return PurePosixPath(value)
    return PureWindowsPath(value)


def _key(value: str, case_rule: CaseRule) -> str:
    if case_rule is CaseRule.INSENSITIVE:
        return value.casefold()
    return value


def _parts_without_anchor(path: PurePath) -> tuple[str, ...]:
    if path.anchor:
        return tuple(path.parts[1:])
    return tuple(path.parts)


def _normalize_path(
    value: str,
    *,
    flavor: PathFlavor,
    relative_to: PurePath | None = None,
) -> tuple[str, tuple[str, ...]]:
    path = _pure_path(value, flavor)
    if flavor is PathFlavor.WINDOWS:
        if path.drive and not path.root:
            raise InvalidRecordPathError("drive-relative Windows paths are ambiguous")
        if path.root and not path.drive:
            raise InvalidRecordPathError(
                "rooted Windows paths require an explicit drive"
            )

    if path.is_absolute():
        anchor = path.anchor
        components: list[str] = []
    else:
        if relative_to is None or not relative_to.is_absolute():
            raise InvalidRecordPathError("relative path requires an absolute base")
        anchor = relative_to.anchor
        components = list(_parts_without_anchor(relative_to))

    for component in _parts_without_anchor(path):
        if component in {"", "."}:
            continue
        if component == "..":
            if not components:
                raise InvalidRecordPathError(
                    "RECORD path underflows its filesystem root"
                )
            components.pop()
            continue
        if flavor is PathFlavor.WINDOWS:
            _validate_windows_component(component)
        components.append(component)
    return anchor, tuple(components)


def _is_contained(
    prefix: tuple[str, tuple[str, ...]],
    target: tuple[str, tuple[str, ...]],
    case_rule: CaseRule,
) -> bool:
    prefix_anchor, prefix_parts = prefix
    target_anchor, target_parts = target
    if _key(prefix_anchor, case_rule) != _key(target_anchor, case_rule):
        return False
    if len(target_parts) < len(prefix_parts):
        return False
    return all(
        _key(expected, case_rule) == _key(actual, case_rule)
        for expected, actual in zip(prefix_parts, target_parts, strict=False)
    )


def _physical_path(
    prefix: Path,
    relative_parts: tuple[str, ...],
    case_rule: CaseRule,
) -> Path:
    current = prefix
    try:
        resolved_prefix = prefix.resolve(strict=False)
    except OSError as error:
        raise FilesystemInventoryError(
            "physical prefix could not be inspected"
        ) from error
    for part in relative_parts:
        try:
            current.resolve(strict=False).relative_to(resolved_prefix)
        except ValueError as error:
            raise RecordPathOutsidePrefixError(
                "RECORD path escapes prefix through an intermediate symlink"
            ) from error
        except OSError as error:
            raise FilesystemInventoryError(
                "physical path could not be inspected"
            ) from error
        physical_part = part
        try:
            if case_rule is CaseRule.INSENSITIVE:
                is_directory = current.is_dir()
                matches = (
                    sorted(
                        child.name
                        for child in current.iterdir()
                        if child.name.casefold() == part.casefold()
                    )
                    if is_directory
                    else []
                )
            else:
                is_directory = False
                matches = []
        except OSError as error:
            raise FilesystemInventoryError(
                "physical directory could not be inspected"
            ) from error
        if case_rule is CaseRule.INSENSITIVE and is_directory:
            if len(matches) > 1:
                raise InvalidRecordPathError(
                    "case-insensitive RECORD path is ambiguous on the host filesystem"
                )
            if matches:
                physical_part = matches[0]
        current = current / physical_part
    return current


@dataclass(frozen=True, slots=True, kw_only=True)
class InventoryLayout:
    physical_prefix: Path
    physical_site_packages: Path
    logical_prefix: str
    logical_site_packages: str
    path_flavor: PathFlavor
    case_rule: CaseRule

    def __post_init__(self) -> None:
        if not isinstance(self.path_flavor, PathFlavor):
            raise TypeError("path_flavor must be a PathFlavor")
        if not isinstance(self.case_rule, CaseRule):
            raise TypeError("case_rule must be a CaseRule")
        physical_prefix = Path(os.path.abspath(self.physical_prefix))
        physical_site_packages = Path(os.path.abspath(self.physical_site_packages))
        try:
            physical_relative = physical_site_packages.relative_to(physical_prefix)
        except ValueError as error:
            raise ValueError(
                "physical_site_packages must be inside physical_prefix"
            ) from error
        try:
            physical_site_packages.resolve(strict=False).relative_to(
                physical_prefix.resolve(strict=False)
            )
        except ValueError as error:
            raise ValueError(
                "physical_site_packages must not escape physical_prefix through symlinks"
            ) from error

        logical_prefix = _normalize_path(
            self.logical_prefix,
            flavor=self.path_flavor,
        )
        logical_site = _normalize_path(
            self.logical_site_packages,
            flavor=self.path_flavor,
        )
        if not _is_contained(logical_prefix, logical_site, self.case_rule):
            raise ValueError("logical_site_packages must be inside logical_prefix")
        logical_relative = logical_site[1][len(logical_prefix[1]) :]
        if tuple(
            _key(part, self.case_rule) for part in physical_relative.parts
        ) != tuple(_key(part, self.case_rule) for part in logical_relative):
            raise ValueError("physical and logical site-packages layouts must match")

        object.__setattr__(self, "physical_prefix", physical_prefix)
        object.__setattr__(self, "physical_site_packages", physical_site_packages)

    @property
    def normalized_logical_prefix(self) -> tuple[str, tuple[str, ...]]:
        return _normalize_path(self.logical_prefix, flavor=self.path_flavor)

    @property
    def normalized_logical_site_packages(self) -> tuple[str, tuple[str, ...]]:
        return _normalize_path(self.logical_site_packages, flavor=self.path_flavor)


def resolve_record_path(
    *,
    layout: InventoryLayout,
    dist_info_dir: Path,
    record_path: str,
) -> ResolvedRecordPath:
    """Resolve one RECORD path lexically without following symlinks."""

    dist_info_dir = Path(os.path.abspath(dist_info_dir))
    if dist_info_dir.parent != layout.physical_site_packages:
        raise ValueError("dist_info_dir must be directly inside physical_site_packages")

    target = _normalize_path(
        record_path,
        flavor=layout.path_flavor,
        relative_to=_pure_path(layout.logical_site_packages, layout.path_flavor),
    )
    prefix = layout.normalized_logical_prefix
    if not _is_contained(prefix, target, layout.case_rule):
        raise RecordPathOutsidePrefixError("RECORD path is outside measurement prefix")

    relative_parts = target[1][len(prefix[1]) :]
    if not relative_parts:
        raise InvalidRecordPathError("RECORD path must identify a file below prefix")
    display_path = "/".join(relative_parts)
    canonical_identity = _key(display_path, layout.case_rule)
    return ResolvedRecordPath(
        physical_path=_physical_path(
            layout.physical_prefix,
            relative_parts,
            layout.case_rule,
        ),
        path=display_path,
        canonical_identity=canonical_identity,
    )


def _distribution_metadata(dist_info_dir: Path) -> tuple[str, str]:
    metadata_path = dist_info_dir / "METADATA"
    if not metadata_path.is_symlink() and metadata_path.is_file():
        try:
            metadata = BytesParser().parsebytes(metadata_path.read_bytes())
        except OSError:
            metadata = None
        if metadata is not None:
            name = metadata.get("Name")
            version = metadata.get("Version")
            if name and version:
                return name, version

    stem = dist_info_dir.name.removesuffix(".dist-info")
    name, separator, version = stem.rpartition("-")
    if not separator or not name or not version:
        raise InventoryError("dist-info must provide a distribution name and version")
    return name, version


def _distribution_warning(
    code: WarningCode,
    distribution_identity: str,
) -> AnalysisWarning:
    return AnalysisWarning(
        code=code,
        target_kind=WarningTargetKind.DISTRIBUTION,
        target_identity=distribution_identity,
    )


def _file_warning(code: WarningCode, identity: str) -> AnalysisWarning:
    return AnalysisWarning(
        code=code,
        target_kind=WarningTargetKind.FILE,
        target_identity=identity,
    )


def _category(path: str) -> FileCategory:
    parts = path.split("/")
    lowered_parts = [part.casefold() for part in parts]
    suffix = Path(parts[-1]).suffix.casefold()
    if any(
        part.endswith(".dist-info") or part.endswith(".egg-info")
        for part in lowered_parts
    ):
        return FileCategory.METADATA
    if lowered_parts[0] in {"bin", "scripts"}:
        return FileCategory.SCRIPT
    if suffix in {".so", ".pyd", ".dll", ".dylib"}:
        return FileCategory.NATIVE
    if suffix in {".py", ".pyc", ".pyi"}:
        return FileCategory.PYTHON
    if (
        lowered_parts[0] in {"include", "share"}
        or any(part.endswith(".data") for part in lowered_parts)
        or suffix in {".h", ".json", ".csv"}
    ):
        return FileCategory.DATA
    return FileCategory.OTHER


def _parent_is_safe(layout: InventoryLayout, path: Path) -> bool:
    try:
        path.parent.resolve(strict=False).relative_to(
            layout.physical_prefix.resolve(strict=False)
        )
    except ValueError:
        return False
    return True


def _entry_from_resolved(
    *,
    layout: InventoryLayout,
    resolved: ResolvedRecordPath,
    origin: FileOrigin,
) -> FileEntry | None:
    if not _parent_is_safe(layout, resolved.physical_path):
        raise RecordPathOutsidePrefixError(
            "RECORD path escapes prefix through an intermediate symlink"
        )
    try:
        file_stat = resolved.physical_path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as error:
        raise FilesystemInventoryError("filesystem entry could not be read") from error
    if not (stat.S_ISREG(file_stat.st_mode) or stat.S_ISLNK(file_stat.st_mode)):
        raise InventoryError("unsupported filesystem entry")
    symlink_target = None
    if stat.S_ISLNK(file_stat.st_mode):
        try:
            symlink_target = os.readlink(resolved.physical_path)
        except OSError as error:
            raise FilesystemInventoryError(
                "symlink target could not be read"
            ) from error
    return FileEntry(
        path=resolved.path,
        canonical_identity=resolved.canonical_identity,
        logical_bytes=file_stat.st_size,
        category=_category(resolved.path),
        origin=origin,
        symlink_target=symlink_target,
    )


def _resolved_physical_path(
    layout: InventoryLayout,
    physical_path: Path,
) -> ResolvedRecordPath:
    try:
        relative = physical_path.relative_to(layout.physical_prefix)
    except ValueError as error:
        raise RecordPathOutsidePrefixError(
            "physical path is outside measurement prefix"
        ) from error
    display_path = relative.as_posix()
    return ResolvedRecordPath(
        physical_path=physical_path,
        path=display_path,
        canonical_identity=_key(display_path, layout.case_rule),
    )


def _read_record(record_path: Path) -> list[str]:
    try:
        with record_path.open(
            "r", encoding="utf-8", errors="strict", newline=""
        ) as record_file:
            rows = list(csv.reader(record_file, strict=True))
    except (OSError, UnicodeError, csv.Error) as error:
        raise InventoryError("RECORD is not valid UTF-8 CSV") from error
    if any(
        len(row) != 3
        or not row[0]
        or (row[1] and _RECORD_HASH.fullmatch(row[1]) is None)
        or (row[2] and _RECORD_SIZE.fullmatch(row[2]) is None)
        for row in rows
    ):
        raise InventoryError(
            "RECORD rows must contain exactly three columns and a path"
        )
    return [row[0] for row in rows]


def _fallback_entries(
    layout: InventoryLayout,
    dist_info_dir: Path,
    distribution_identity: str,
) -> tuple[tuple[FileEntry, ...], tuple[AnalysisWarning, ...]]:
    entries: list[FileEntry] = []
    warnings: list[AnalysisWarning] = []
    for path in sorted(dist_info_dir.rglob("*")):
        resolved = _resolved_physical_path(layout, path)
        try:
            if stat.S_ISDIR(path.lstat().st_mode):
                continue
        except OSError:
            warnings.append(
                _file_warning(
                    WarningCode.FILESYSTEM_ERROR,
                    resolved.canonical_identity,
                )
            )
            continue
        try:
            entry = _entry_from_resolved(
                layout=layout,
                resolved=resolved,
                origin=FileOrigin.FALLBACK,
            )
        except RecordPathOutsidePrefixError:
            warnings.append(
                _distribution_warning(
                    WarningCode.RECORD_PATH_OUTSIDE_PREFIX,
                    distribution_identity,
                )
            )
            continue
        except FilesystemInventoryError:
            warnings.append(
                _file_warning(
                    WarningCode.FILESYSTEM_ERROR,
                    resolved.canonical_identity,
                )
            )
            continue
        except InventoryError:
            warnings.append(
                _file_warning(
                    WarningCode.UNSUPPORTED_FILE_TYPE,
                    resolved.canonical_identity,
                )
            )
            continue
        if entry is not None:
            entries.append(entry)
    return tuple(entries), tuple(warnings)


def _bytecode_candidates(
    layout: InventoryLayout,
    source: FileEntry,
) -> tuple[Path, ...]:
    source_parts = tuple(source.path.split("/"))
    source_path = _physical_path(
        layout.physical_prefix,
        source_parts,
        layout.case_rule,
    )
    candidates = [
        _physical_path(
            layout.physical_prefix,
            (*source_parts[:-1], f"{source_path.stem}.pyc"),
            layout.case_rule,
        )
    ]
    cache_dir = _physical_path(
        layout.physical_prefix,
        (*source_parts[:-1], "__pycache__"),
        layout.case_rule,
    )
    try:
        if cache_dir.is_symlink():
            raise RecordPathOutsidePrefixError(
                "generated bytecode cache cannot be a symlink"
            )
        if cache_dir.is_dir():
            expected_prefix = f"{source_path.stem}."
            candidates.extend(
                sorted(
                    child
                    for child in cache_dir.iterdir()
                    if child.name.casefold().startswith(expected_prefix.casefold())
                    and child.suffix.casefold() == ".pyc"
                )
            )
    except OSError as error:
        raise FilesystemInventoryError(
            "bytecode cache could not be inspected"
        ) from error
    return tuple(candidates)


def _generated_bytecode(
    *,
    layout: InventoryLayout,
    record_entries: tuple[FileEntry, ...],
    identities: set[str],
    distribution_identity: str,
) -> tuple[tuple[FileEntry, ...], tuple[AnalysisWarning, ...]]:
    generated: list[FileEntry] = []
    warnings: list[AnalysisWarning] = []
    for source in record_entries:
        if not source.path.casefold().endswith(".py"):
            continue
        try:
            candidates = _bytecode_candidates(layout, source)
        except RecordPathOutsidePrefixError:
            warnings.append(
                _distribution_warning(
                    WarningCode.RECORD_PATH_OUTSIDE_PREFIX,
                    distribution_identity,
                )
            )
            continue
        except FilesystemInventoryError:
            warnings.append(
                _file_warning(
                    WarningCode.FILESYSTEM_ERROR,
                    source.canonical_identity,
                )
            )
            continue
        for candidate in candidates:
            resolved = _resolved_physical_path(layout, candidate)
            if resolved.canonical_identity in identities:
                continue
            try:
                entry = _entry_from_resolved(
                    layout=layout,
                    resolved=resolved,
                    origin=FileOrigin.GENERATED,
                )
            except RecordPathOutsidePrefixError:
                warnings.append(
                    _distribution_warning(
                        WarningCode.RECORD_PATH_OUTSIDE_PREFIX,
                        distribution_identity,
                    )
                )
                continue
            except FilesystemInventoryError:
                warnings.append(
                    _file_warning(
                        WarningCode.FILESYSTEM_ERROR,
                        resolved.canonical_identity,
                    )
                )
                continue
            except InventoryError:
                warnings.append(
                    _file_warning(
                        WarningCode.UNSUPPORTED_FILE_TYPE,
                        resolved.canonical_identity,
                    )
                )
                continue
            if entry is not None:
                identities.add(entry.canonical_identity)
                generated.append(entry)
    return tuple(generated), tuple(warnings)


def _collect_record_entries(
    *,
    layout: InventoryLayout,
    dist_info_dir: Path,
    recorded_paths: list[str],
    distribution_identity: str,
) -> tuple[tuple[FileEntry, ...], tuple[AnalysisWarning, ...]]:
    entries: list[FileEntry] = []
    warnings: list[AnalysisWarning] = []
    identities: set[str] = set()
    for recorded_path in recorded_paths:
        try:
            resolved = resolve_record_path(
                layout=layout,
                dist_info_dir=dist_info_dir,
                record_path=recorded_path,
            )
        except InvalidRecordPathError:
            warnings.append(
                _distribution_warning(
                    WarningCode.INVALID_RECORD_PATH,
                    distribution_identity,
                )
            )
            continue
        except RecordPathOutsidePrefixError:
            warnings.append(
                _distribution_warning(
                    WarningCode.RECORD_PATH_OUTSIDE_PREFIX,
                    distribution_identity,
                )
            )
            continue
        except FilesystemInventoryError:
            warnings.append(
                _distribution_warning(
                    WarningCode.FILESYSTEM_LAYOUT_ERROR,
                    distribution_identity,
                )
            )
            continue

        if resolved.canonical_identity in identities:
            warnings.append(
                _file_warning(
                    WarningCode.DUPLICATE_RECORD_ENTRY,
                    resolved.canonical_identity,
                )
            )
            continue
        identities.add(resolved.canonical_identity)
        try:
            entry = _entry_from_resolved(
                layout=layout,
                resolved=resolved,
                origin=FileOrigin.RECORD,
            )
        except RecordPathOutsidePrefixError:
            warnings.append(
                _distribution_warning(
                    WarningCode.RECORD_PATH_OUTSIDE_PREFIX,
                    distribution_identity,
                )
            )
            continue
        except FilesystemInventoryError:
            warnings.append(
                _file_warning(
                    WarningCode.FILESYSTEM_ERROR,
                    resolved.canonical_identity,
                )
            )
            continue
        except InventoryError:
            warnings.append(
                _file_warning(
                    WarningCode.UNSUPPORTED_FILE_TYPE,
                    resolved.canonical_identity,
                )
            )
            continue
        if entry is None:
            warnings.append(
                _file_warning(
                    WarningCode.MISSING_FILE,
                    resolved.canonical_identity,
                )
            )
        else:
            entries.append(entry)

    generated_entries, generated_warnings = _generated_bytecode(
        layout=layout,
        record_entries=tuple(entries),
        identities=identities,
        distribution_identity=distribution_identity,
    )
    return (
        (*entries, *generated_entries),
        (*warnings, *generated_warnings),
    )


def collect_distribution(
    *,
    layout: InventoryLayout,
    dist_info_dir: Path,
) -> DistributionResult:
    """Collect one distribution without scanning or mutating other environments."""

    dist_info_dir = Path(os.path.abspath(dist_info_dir))
    if dist_info_dir.parent != layout.physical_site_packages:
        raise ValueError("dist_info_dir must be directly inside physical_site_packages")
    if dist_info_dir.is_symlink() or not dist_info_dir.is_dir():
        raise InventoryError("dist_info_dir must be a real directory")
    name, version = _distribution_metadata(dist_info_dir)
    distribution_identity = f"{name}=={version}"
    record_path = dist_info_dir / "RECORD"
    try:
        record_mode = record_path.lstat().st_mode
    except FileNotFoundError:
        fallback_files, fallback_warnings = _fallback_entries(
            layout,
            dist_info_dir,
            distribution_identity,
        )
        return DistributionResult(
            name=name,
            version=version,
            files=fallback_files,
            warnings=(
                _distribution_warning(
                    WarningCode.MISSING_RECORD,
                    distribution_identity,
                ),
                *fallback_warnings,
            ),
        )
    except OSError:
        return DistributionResult(
            name=name,
            version=version,
            files=(),
            warnings=(
                _distribution_warning(
                    WarningCode.FILESYSTEM_LAYOUT_ERROR,
                    distribution_identity,
                ),
            ),
        )
    if not stat.S_ISREG(record_mode):
        return DistributionResult(
            name=name,
            version=version,
            files=(),
            warnings=(
                _distribution_warning(
                    WarningCode.INVALID_RECORD,
                    distribution_identity,
                ),
            ),
        )

    try:
        recorded_paths = _read_record(record_path)
    except InventoryError:
        return DistributionResult(
            name=name,
            version=version,
            files=(),
            warnings=(
                _distribution_warning(
                    WarningCode.INVALID_RECORD,
                    distribution_identity,
                ),
            ),
        )

    entries, warnings = _collect_record_entries(
        layout=layout,
        dist_info_dir=dist_info_dir,
        recorded_paths=recorded_paths,
        distribution_identity=distribution_identity,
    )
    return DistributionResult(
        name=name,
        version=version,
        files=entries,
        warnings=warnings,
    )
