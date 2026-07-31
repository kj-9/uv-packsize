"""Orchestration boundary for analyzing an installed environment.

The caller is responsible for supplying an ``AnalysisContext`` that accurately
describes the already-installed environment. Inventory remains authoritative for
which files exist: resolution context fields such as ``compile_bytecode`` are
recorded for comparison and do not filter observed files.
"""

from collections.abc import Iterable
from enum import Enum

from uv_packsize.inventory import (
    InventoryLayout,
    SupplementalOwnership,
    collect_distributions,
)
from uv_packsize.models import AnalysisContext, AnalysisResult


class AnalysisContextErrorCode(str, Enum):
    PATH_FLAVOR_MISMATCH = "path-flavor-mismatch"
    CASE_RULE_MISMATCH = "case-rule-mismatch"


class AnalysisContextError(ValueError):
    def __init__(self, code: AnalysisContextErrorCode, target: str):
        self.code = code
        self.target = target
        super().__init__(f"{code.value}: {target}")


def analyze_installed_environment(
    *,
    context: AnalysisContext,
    layouts: Iterable[InventoryLayout],
    supplemental: Iterable[SupplementalOwnership] = (),
) -> AnalysisResult:
    """Collect installed files and return their immutable analysis result.

    Inventory errors intentionally propagate unchanged so callers can retain
    their typed code and target. This boundary performs no installation,
    subprocess execution, rendering, serialization, or network access.
    """

    if not isinstance(context, AnalysisContext):
        raise TypeError("context must be a ResolutionContext or ExistingPrefixContext")
    if isinstance(layouts, InventoryLayout):
        raise TypeError("layouts must be a collection of InventoryLayout values")
    try:
        layout_values = tuple(layouts)
    except TypeError as error:
        raise TypeError(
            "layouts must be a non-empty collection of InventoryLayout values"
        ) from error
    if not layout_values or any(
        not isinstance(layout, InventoryLayout) for layout in layout_values
    ):
        raise TypeError(
            "layouts must be a non-empty collection of InventoryLayout values"
        )
    if any(layout.path_flavor is not context.path_flavor for layout in layout_values):
        raise AnalysisContextError(
            AnalysisContextErrorCode.PATH_FLAVOR_MISMATCH,
            "inventory-layout",
        )
    if any(layout.case_rule is not context.case_rule for layout in layout_values):
        raise AnalysisContextError(
            AnalysisContextErrorCode.CASE_RULE_MISMATCH,
            "inventory-layout",
        )
    if isinstance(supplemental, SupplementalOwnership):
        raise TypeError(
            "supplemental must be a collection of SupplementalOwnership values"
        )
    try:
        supplemental_values = tuple(supplemental)
    except TypeError as error:
        raise TypeError(
            "supplemental must be a collection of SupplementalOwnership values"
        ) from error
    if any(
        not isinstance(ownership, SupplementalOwnership)
        for ownership in supplemental_values
    ):
        raise TypeError(
            "supplemental must be a collection of SupplementalOwnership values"
        )

    distributions = collect_distributions(
        layouts=layout_values,
        supplemental=supplemental_values,
    )
    return AnalysisResult(context=context, distributions=distributions)
