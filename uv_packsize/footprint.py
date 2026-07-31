"""Pure global size aggregations grouped by category and dependency role.

The inventory remains the source of truth for logical bytes.  This module
derives a second, global-deduplicated view from an
``ExplainedAnalysisResult``; it does not assign bytes to individual root
inputs, read the filesystem, or render a public report.
"""

from dataclasses import dataclass
from enum import Enum

from uv_packsize.dependency_graph import DependencyGraphCompleteness, DependencyKind
from uv_packsize.dependency_paths import ExplainedAnalysisResult
from uv_packsize.models import AnalysisResult, Completeness, FileCategory, FileEntry


class FootprintRole(str, Enum):
    """A global dependency role for a deduplicated installed file."""

    SELF = "self"
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    UNATTRIBUTED = "unattributed"
    MIXED_OWNERSHIP = "mixed-ownership"


_CATEGORY_ORDER = tuple(FileCategory)
_ROLE_ORDER = tuple(FootprintRole)


def _logical_bytes(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class FileCategoryTotal:
    """The global-deduplicated logical bytes for one file category."""

    category: FileCategory
    logical_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.category, FileCategory):
            raise TypeError("category must be a FileCategory")
        _logical_bytes(self.logical_bytes, "logical_bytes")


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyRoleTotal:
    """A role total with a complete, fixed-order category breakdown."""

    role: FootprintRole
    logical_bytes: int
    category_totals: tuple[FileCategoryTotal, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.role, FootprintRole):
            raise TypeError("role must be a FootprintRole")
        _logical_bytes(self.logical_bytes, "logical_bytes")
        category_totals = _category_totals(self.category_totals)
        if sum(total.logical_bytes for total in category_totals) != self.logical_bytes:
            raise ValueError("role logical_bytes must equal its category totals")
        object.__setattr__(self, "category_totals", category_totals)


def _category_totals(
    values: tuple[FileCategoryTotal, ...],
) -> tuple[FileCategoryTotal, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("category_totals must be a collection of FileCategoryTotal")
    category_totals = tuple(values)
    if any(not isinstance(total, FileCategoryTotal) for total in category_totals):
        raise TypeError("category_totals must contain FileCategoryTotal values")
    by_category = {total.category: total for total in category_totals}
    if len(by_category) != len(category_totals):
        raise ValueError("category_totals cannot contain duplicate categories")
    if set(by_category) != set(_CATEGORY_ORDER):
        raise ValueError("category_totals must contain every FileCategory")
    return tuple(by_category[category] for category in _CATEGORY_ORDER)


def _validated_role_totals(
    values: tuple[DependencyRoleTotal, ...] | None,
    expected: tuple[DependencyRoleTotal, ...] | None,
    logical_bytes: int,
) -> tuple[DependencyRoleTotal, ...] | None:
    if expected is None:
        if values is not None:
            raise ValueError("role totals require a complete dependency graph")
        return None
    if values is None:
        raise ValueError("role totals are required for a complete dependency graph")
    if isinstance(values, (str, bytes)):
        raise TypeError(
            "role_totals must be a collection of DependencyRoleTotal or None"
        )
    role_totals = tuple(values)
    if any(not isinstance(total, DependencyRoleTotal) for total in role_totals):
        raise TypeError("role_totals must contain DependencyRoleTotal values")
    by_role = {total.role: total for total in role_totals}
    if len(by_role) != len(role_totals):
        raise ValueError("role_totals cannot contain duplicate roles")
    if set(by_role) != set(_ROLE_ORDER):
        raise ValueError("role_totals must contain every FootprintRole")
    role_totals = tuple(by_role[role] for role in _ROLE_ORDER)
    if role_totals != expected:
        raise ValueError("role totals are inconsistent with explained analysis")
    if sum(total.logical_bytes for total in role_totals) != logical_bytes:
        raise ValueError("role totals must equal logical_bytes")
    return role_totals


@dataclass(frozen=True, slots=True, kw_only=True)
class FootprintResult:
    """Global category and dependency-role totals for an explained analysis.

    Dependency-role totals are intentionally unavailable when Core Metadata
    graph attribution is incomplete.  Category totals continue to reflect the
    measured file inventory in that case.
    """

    explained: ExplainedAnalysisResult
    logical_bytes: int
    category_totals: tuple[FileCategoryTotal, ...]
    role_totals: tuple[DependencyRoleTotal, ...] | None

    def __post_init__(self) -> None:
        if not isinstance(self.explained, ExplainedAnalysisResult):
            raise TypeError("explained must be an ExplainedAnalysisResult")
        _logical_bytes(self.logical_bytes, "logical_bytes")
        category_totals = _category_totals(self.category_totals)
        if sum(total.logical_bytes for total in category_totals) != self.logical_bytes:
            raise ValueError("logical_bytes must equal category totals")

        expected = _derived_footprint(self.explained)
        if self.logical_bytes != expected[0] or category_totals != expected[1]:
            raise ValueError(
                "footprint totals are inconsistent with explained analysis"
            )

        role_totals = _validated_role_totals(
            self.role_totals,
            expected[2],
            self.logical_bytes,
        )
        object.__setattr__(self, "category_totals", category_totals)
        object.__setattr__(self, "role_totals", role_totals)

    @property
    def analysis(self) -> AnalysisResult:
        """The source size analysis, retained without copying it."""

        return self.explained.analysis

    @property
    def inventory_completeness(self) -> Completeness:
        """Completeness of file inventory, delegated without conflation."""

        return self.explained.inventory_completeness

    @property
    def graph_completeness(self) -> DependencyGraphCompleteness:
        """Completeness of dependency graph attribution."""

        return self.explained.graph_completeness

    @property
    def completeness(self) -> Completeness:
        """Combined completeness, delegated to the explained result."""

        return self.explained.completeness


def _global_files(
    result: ExplainedAnalysisResult,
) -> dict[str, tuple[FileEntry, tuple[DependencyKind, ...]]]:
    kinds_by_name = {
        attribution.node.name: attribution.node.kind
        for attribution in result.attributions
    }
    files: dict[str, tuple[FileEntry, set[DependencyKind]]] = {}
    for distribution in result.analysis.distributions:
        kind = kinds_by_name[distribution.name]
        for file in distribution.files:
            existing = files.get(file.canonical_identity)
            if existing is None:
                files[file.canonical_identity] = (file, {kind})
            else:
                existing[1].add(kind)
    return {
        identity: (file, tuple(sorted(kinds, key=lambda kind: kind.value)))
        for identity, (file, kinds) in files.items()
    }


def _role(kinds: tuple[DependencyKind, ...]) -> FootprintRole:
    if len(kinds) != 1:
        return FootprintRole.MIXED_OWNERSHIP
    return {
        DependencyKind.ROOT: FootprintRole.SELF,
        DependencyKind.DIRECT: FootprintRole.DIRECT,
        DependencyKind.TRANSITIVE: FootprintRole.TRANSITIVE,
        DependencyKind.UNATTRIBUTED: FootprintRole.UNATTRIBUTED,
    }[kinds[0]]


def _totals_by_category(files: tuple[FileEntry, ...]) -> tuple[FileCategoryTotal, ...]:
    bytes_by_category = {category: 0 for category in _CATEGORY_ORDER}
    for file in files:
        bytes_by_category[file.category] += file.logical_bytes
    return tuple(
        FileCategoryTotal(category=category, logical_bytes=bytes_by_category[category])
        for category in _CATEGORY_ORDER
    )


def _derived_footprint(
    result: ExplainedAnalysisResult,
) -> tuple[int, tuple[FileCategoryTotal, ...], tuple[DependencyRoleTotal, ...] | None]:
    global_files = _global_files(result)
    files = tuple(file for file, _kinds in global_files.values())
    categories = _totals_by_category(files)
    logical_bytes = sum(total.logical_bytes for total in categories)
    if logical_bytes != result.analysis.total_logical_bytes:
        raise ValueError("analysis global total is inconsistent with its inventory")
    if result.graph.completeness is DependencyGraphCompleteness.INCOMPLETE:
        return logical_bytes, categories, None

    files_by_role = {role: [] for role in _ROLE_ORDER}
    for file, kinds in global_files.values():
        files_by_role[_role(kinds)].append(file)
    roles = tuple(
        DependencyRoleTotal(
            role=role,
            logical_bytes=sum(file.logical_bytes for file in files_by_role[role]),
            category_totals=_totals_by_category(tuple(files_by_role[role])),
        )
        for role in _ROLE_ORDER
    )
    return logical_bytes, categories, roles


def summarize_footprint(result: ExplainedAnalysisResult) -> FootprintResult:
    """Derive deterministic global category and dependency-role totals."""

    if not isinstance(result, ExplainedAnalysisResult):
        raise TypeError("result must be an ExplainedAnalysisResult")
    logical_bytes, categories, roles = _derived_footprint(result)
    return FootprintResult(
        explained=result,
        logical_bytes=logical_bytes,
        category_totals=categories,
        role_totals=roles,
    )
