"""Pure, global-deduplicated size attribution to requested root sets.

This module deliberately assigns a file to the *set* of distinct recognized
root distribution names that reach any of its owning distributions.  It never
splits a shared file's bytes between roots, so the global inventory remains the
only source of truth and every canonical identity is counted once.
"""

from dataclasses import dataclass

from uv_packsize.dependency_graph import (
    DependencyGraphCompleteness,
    RootRequirementStatus,
)
from uv_packsize.dependency_paths import ExplainedAnalysisResult
from uv_packsize.footprint import (
    FileCategoryTotal,
    FootprintResult,
    summarize_footprint,
)
from uv_packsize.models import (
    AnalysisResult,
    Completeness,
    FileCategory,
    FileEntry,
    normalize_distribution_name,
)

_CATEGORY_ORDER = tuple(FileCategory)


def _non_negative_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _category_totals(
    values: tuple[FileCategoryTotal, ...],
) -> tuple[FileCategoryTotal, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("category_totals must be a collection of FileCategoryTotal")
    totals = tuple(values)
    if any(not isinstance(total, FileCategoryTotal) for total in totals):
        raise TypeError("category_totals must contain FileCategoryTotal values")
    by_category = {total.category: total for total in totals}
    if len(by_category) != len(totals):
        raise ValueError("category_totals cannot contain duplicate categories")
    if set(by_category) != set(_CATEGORY_ORDER):
        raise ValueError("category_totals must contain every FileCategory")
    return tuple(by_category[category] for category in _CATEGORY_ORDER)


def _root_names(values: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError("root_names must be a collection of distribution names")
    return tuple(sorted({normalize_distribution_name(value) for value in values}))


@dataclass(frozen=True, slots=True, kw_only=True)
class RootSetTotal:
    """One global-deduplicated bucket for an exact set of root names."""

    root_names: tuple[str, ...]
    logical_bytes: int
    category_totals: tuple[FileCategoryTotal, ...]
    file_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_names", _root_names(self.root_names))
        _non_negative_int(self.logical_bytes, "logical_bytes")
        _non_negative_int(self.file_count, "file_count")
        category_totals = _category_totals(self.category_totals)
        if sum(total.logical_bytes for total in category_totals) != self.logical_bytes:
            raise ValueError("logical_bytes must equal category totals")
        object.__setattr__(self, "category_totals", category_totals)


@dataclass(frozen=True, slots=True, kw_only=True)
class RootScopedTotal:
    """A root-local view composed from one or more exact root-set buckets."""

    logical_bytes: int
    category_totals: tuple[FileCategoryTotal, ...]
    file_count: int

    def __post_init__(self) -> None:
        _non_negative_int(self.logical_bytes, "logical_bytes")
        _non_negative_int(self.file_count, "file_count")
        category_totals = _category_totals(self.category_totals)
        if sum(total.logical_bytes for total in category_totals) != self.logical_bytes:
            raise ValueError("logical_bytes must equal category totals")
        object.__setattr__(self, "category_totals", category_totals)


def _add_scoped_totals(
    first: RootScopedTotal, second: RootScopedTotal
) -> RootScopedTotal:
    by_category = {
        category: first.category_totals[index].logical_bytes
        + second.category_totals[index].logical_bytes
        for index, category in enumerate(_CATEGORY_ORDER)
    }
    return RootScopedTotal(
        logical_bytes=first.logical_bytes + second.logical_bytes,
        category_totals=tuple(
            FileCategoryTotal(category=category, logical_bytes=by_category[category])
            for category in _CATEGORY_ORDER
        ),
        file_count=first.file_count + second.file_count,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class RootContribution:
    """Exclusive and shared, non-split byte views for one root name."""

    root_name: str
    root_input_indexes: tuple[int, ...]
    closure: RootScopedTotal
    exclusive: RootScopedTotal
    shared: RootScopedTotal

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "root_name", normalize_distribution_name(self.root_name)
        )
        if isinstance(self.root_input_indexes, (str, bytes)):
            raise TypeError("root_input_indexes must be a collection of integers")
        indexes = tuple(self.root_input_indexes)
        if any(
            not isinstance(index, int) or isinstance(index, bool) or index < 0
            for index in indexes
        ):
            raise ValueError("root_input_indexes must contain non-negative integers")
        if len(indexes) != len(set(indexes)):
            raise ValueError("root_input_indexes must not contain duplicates")
        object.__setattr__(self, "root_input_indexes", tuple(sorted(indexes)))
        for field_name in ("closure", "exclusive", "shared"):
            if not isinstance(getattr(self, field_name), RootScopedTotal):
                raise TypeError(f"{field_name} must be a RootScopedTotal")
        if self.closure != _add_scoped_totals(self.exclusive, self.shared):
            raise ValueError("closure must equal exclusive plus shared")


def _scoped_total(buckets: tuple[RootSetTotal, ...]) -> RootScopedTotal:
    by_category = {category: 0 for category in _CATEGORY_ORDER}
    for bucket in buckets:
        for total in bucket.category_totals:
            by_category[total.category] += total.logical_bytes
    return RootScopedTotal(
        logical_bytes=sum(bucket.logical_bytes for bucket in buckets),
        category_totals=tuple(
            FileCategoryTotal(category=category, logical_bytes=by_category[category])
            for category in _CATEGORY_ORDER
        ),
        file_count=sum(bucket.file_count for bucket in buckets),
    )


def _root_set_totals(
    result: ExplainedAnalysisResult,
) -> tuple[RootSetTotal, ...]:
    node_roots = {
        attribution.node.name: attribution.node.root_names
        for attribution in result.attributions
    }
    files: dict[str, tuple[FileEntry, set[str]]] = {}
    for distribution in result.analysis.distributions:
        owner_roots = node_roots[distribution.name]
        for file in distribution.files:
            existing = files.get(file.canonical_identity)
            if existing is None:
                files[file.canonical_identity] = (file, set(owner_roots))
            else:
                existing[1].update(owner_roots)

    recognized_names = {
        root.name
        for root in result.graph.roots
        if root.status is RootRequirementStatus.RECOGNIZED and root.name is not None
    }
    files_by_root_set: dict[tuple[str, ...], list[FileEntry]] = {
        (): [],
        **{(name,): [] for name in recognized_names},
    }
    for file, root_names in files.values():
        files_by_root_set.setdefault(tuple(sorted(root_names)), []).append(file)

    totals = []
    for root_names, bucket_files in files_by_root_set.items():
        by_category = {category: 0 for category in _CATEGORY_ORDER}
        for file in bucket_files:
            by_category[file.category] += file.logical_bytes
        totals.append(
            RootSetTotal(
                root_names=root_names,
                logical_bytes=sum(file.logical_bytes for file in bucket_files),
                category_totals=tuple(
                    FileCategoryTotal(
                        category=category, logical_bytes=by_category[category]
                    )
                    for category in _CATEGORY_ORDER
                ),
                file_count=len(bucket_files),
            )
        )
    return tuple(
        sorted(totals, key=lambda total: (len(total.root_names), total.root_names))
    )


def _root_contributions(
    result: ExplainedAnalysisResult,
    totals: tuple[RootSetTotal, ...],
) -> tuple[RootContribution, ...]:
    indexes_by_name: dict[str, list[int]] = {}
    for root in result.graph.roots:
        if root.status is RootRequirementStatus.RECOGNIZED:
            assert root.name is not None
            indexes_by_name.setdefault(root.name, []).append(root.input_index)

    contributions = []
    for root_name, indexes in sorted(indexes_by_name.items()):
        exclusive = _scoped_total(
            tuple(total for total in totals if total.root_names == (root_name,))
        )
        shared = _scoped_total(
            tuple(
                total
                for total in totals
                if len(total.root_names) >= 2 and root_name in total.root_names
            )
        )
        contributions.append(
            RootContribution(
                root_name=root_name,
                root_input_indexes=tuple(indexes),
                closure=_add_scoped_totals(exclusive, shared),
                exclusive=exclusive,
                shared=shared,
            )
        )
    return tuple(contributions)


def _derived_contributions(
    result: ExplainedAnalysisResult,
) -> tuple[
    FootprintResult,
    tuple[RootSetTotal, ...] | None,
    tuple[RootContribution, ...] | None,
]:
    footprint = summarize_footprint(result)
    if result.graph.completeness is DependencyGraphCompleteness.INCOMPLETE:
        return footprint, None, None
    totals = _root_set_totals(result)
    if sum(total.logical_bytes for total in totals) != footprint.logical_bytes:
        raise ValueError("root set totals must equal the global footprint")
    category_bytes = {category: 0 for category in _CATEGORY_ORDER}
    for total in totals:
        for category_total in total.category_totals:
            category_bytes[category_total.category] += category_total.logical_bytes
    if tuple(category_bytes[category] for category in _CATEGORY_ORDER) != tuple(
        total.logical_bytes for total in footprint.category_totals
    ):
        raise ValueError("root set category totals must equal the global footprint")
    if sum(total.file_count for total in totals) != len(
        {
            file.canonical_identity
            for distribution in result.analysis.distributions
            for file in distribution.files
        }
    ):
        raise ValueError("root set file counts must equal the global inventory")
    return footprint, totals, _root_contributions(result, totals)


@dataclass(frozen=True, slots=True, kw_only=True)
class RootContributionResult:
    """Immutable root-set attribution retaining its analyzed source result."""

    explained: ExplainedAnalysisResult
    footprint: FootprintResult
    root_set_totals: tuple[RootSetTotal, ...] | None
    roots: tuple[RootContribution, ...] | None

    def __post_init__(self) -> None:
        if not isinstance(self.explained, ExplainedAnalysisResult):
            raise TypeError("explained must be an ExplainedAnalysisResult")
        if not isinstance(self.footprint, FootprintResult):
            raise TypeError("footprint must be a FootprintResult")
        expected_footprint, expected_sets, expected_roots = _derived_contributions(
            self.explained
        )
        if self.footprint != expected_footprint:
            raise ValueError("footprint is inconsistent with explained analysis")
        if self.root_set_totals is not None:
            if isinstance(self.root_set_totals, (str, bytes)):
                raise TypeError("root_set_totals must be a collection or None")
            if any(
                not isinstance(total, RootSetTotal) for total in self.root_set_totals
            ):
                raise TypeError("root_set_totals must contain RootSetTotal values")
        if self.roots is not None:
            if isinstance(self.roots, (str, bytes)):
                raise TypeError("roots must be a collection or None")
            if any(not isinstance(root, RootContribution) for root in self.roots):
                raise TypeError("roots must contain RootContribution values")
        if self.root_set_totals != expected_sets or self.roots != expected_roots:
            raise ValueError(
                "root contributions are inconsistent with explained analysis"
            )
        object.__setattr__(self, "footprint", expected_footprint)
        object.__setattr__(self, "root_set_totals", expected_sets)
        object.__setattr__(self, "roots", expected_roots)

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
        """Completeness of root attribution metadata."""

        return self.explained.graph_completeness

    @property
    def completeness(self) -> Completeness:
        """Combined completeness, delegated to the explained result."""

        return self.explained.completeness


def summarize_root_contributions(
    result: ExplainedAnalysisResult,
) -> RootContributionResult:
    """Derive non-split, deterministic root-set contribution totals."""

    if not isinstance(result, ExplainedAnalysisResult):
        raise TypeError("result must be an ExplainedAnalysisResult")
    footprint, root_set_totals, roots = _derived_contributions(result)
    return RootContributionResult(
        explained=result,
        footprint=footprint,
        root_set_totals=root_set_totals,
        roots=roots,
    )
