"""Pure normalization of trusted budget-policy mappings.

This boundary intentionally accepts only a built-in ``dict`` produced by a
future trusted configuration source.  It neither reads configuration files nor
retains the mapping or any of its values.  Keeping that source resolution out
of this module makes the accepted policy shape deterministic and safe to reuse
from a CLI or CI adapter.
"""

from __future__ import annotations

from enum import Enum
from typing import Final, cast

from .baseline import MAX_BASELINE_INTEGER
from .budget import BudgetPolicy, IncompleteBudgetPolicy


class BudgetPolicyConfigErrorReason(str, Enum):
    """Stable, data-free reasons a policy mapping cannot be normalized."""

    INVALID_MAPPING = "invalid-mapping"
    UNKNOWN_FIELD = "unknown-field"
    INVALID_TYPE = "invalid-type"
    OUT_OF_RANGE = "out-of-range"
    INVALID_INCOMPLETE_POLICY = "invalid-incomplete-policy"
    INVALID_INPUT = "invalid-input"


class BudgetPolicyConfigField(str, Enum):
    """Known closed policy fields safe to identify in an error."""

    MAX_TOTAL_LOGICAL_BYTES = "max_total_logical_bytes"
    MAX_INCREASE_LOGICAL_BYTES = "max_increase_logical_bytes"
    INCOMPLETE_POLICY = "incomplete_policy"


class BudgetPolicyConfigError(ValueError):
    """A sanitized policy input error that never reflects configuration data."""

    def __init__(
        self,
        reason: BudgetPolicyConfigErrorReason,
        field: BudgetPolicyConfigField | None = None,
    ) -> None:
        if type(reason) is not BudgetPolicyConfigErrorReason:
            raise TypeError("reason must be a BudgetPolicyConfigErrorReason")
        if field is not None and type(field) is not BudgetPolicyConfigField:
            raise TypeError("field must be a BudgetPolicyConfigField or None")
        self.reason = reason
        self.field = field
        self.path = None if field is None else field.value
        location = "policy" if field is None else self.path
        super().__init__(f"Invalid budget policy ({reason.value} at {location}).")


_MAX_TOTAL_LOGICAL_BYTES: Final = BudgetPolicyConfigField.MAX_TOTAL_LOGICAL_BYTES
_MAX_INCREASE_LOGICAL_BYTES: Final = BudgetPolicyConfigField.MAX_INCREASE_LOGICAL_BYTES
_INCOMPLETE_POLICY: Final = BudgetPolicyConfigField.INCOMPLETE_POLICY
_KNOWN_FIELDS: Final = frozenset(
    {
        _MAX_TOTAL_LOGICAL_BYTES,
        _MAX_INCREASE_LOGICAL_BYTES,
        _INCOMPLETE_POLICY,
    }
)


def parse_budget_policy(value: object) -> BudgetPolicy:
    """Return a fresh immutable policy from one exact trusted mapping.

    Every present limit must be an exact, non-boolean integer in the baseline
    integer range.  The only accepted incomplete-result strings are the stable
    values of :class:`IncompleteBudgetPolicy`.  Missing fields use
    :class:`BudgetPolicy` defaults, so ``{}`` is the explicit no-op policy.
    """

    if type(value) is not dict:
        raise BudgetPolicyConfigError(BudgetPolicyConfigErrorReason.INVALID_MAPPING)
    values = cast(dict[str, object], value)

    for key in values:
        if type(key) is not str:
            raise BudgetPolicyConfigError(BudgetPolicyConfigErrorReason.INVALID_MAPPING)
    if any(key not in _KNOWN_FIELDS for key in values):
        raise BudgetPolicyConfigError(BudgetPolicyConfigErrorReason.UNKNOWN_FIELD)

    max_total = _parse_limit(values, _MAX_TOTAL_LOGICAL_BYTES)
    max_increase = _parse_limit(values, _MAX_INCREASE_LOGICAL_BYTES)
    incomplete_policy = _parse_incomplete_policy(values)
    try:
        return BudgetPolicy(
            max_total_logical_bytes=max_total,
            max_increase_logical_bytes=max_increase,
            incomplete_policy=incomplete_policy,
        )
    except (TypeError, ValueError):
        raise BudgetPolicyConfigError(
            BudgetPolicyConfigErrorReason.INVALID_INPUT
        ) from None


def _parse_limit(
    values: dict[str, object], field: BudgetPolicyConfigField
) -> int | None:
    if field.value not in values:
        return None
    value = values[field.value]
    if type(value) is not int:
        raise BudgetPolicyConfigError(BudgetPolicyConfigErrorReason.INVALID_TYPE, field)
    if not 0 <= value <= MAX_BASELINE_INTEGER:
        raise BudgetPolicyConfigError(BudgetPolicyConfigErrorReason.OUT_OF_RANGE, field)
    return value


def _parse_incomplete_policy(values: dict[str, object]) -> IncompleteBudgetPolicy:
    if _INCOMPLETE_POLICY.value not in values:
        return IncompleteBudgetPolicy.FAIL
    value = values[_INCOMPLETE_POLICY.value]
    if type(value) is not str:
        raise BudgetPolicyConfigError(
            BudgetPolicyConfigErrorReason.INVALID_TYPE, _INCOMPLETE_POLICY
        )
    try:
        return IncompleteBudgetPolicy(value)
    except ValueError:
        raise BudgetPolicyConfigError(
            BudgetPolicyConfigErrorReason.INVALID_INCOMPLETE_POLICY,
            _INCOMPLETE_POLICY,
        ) from None
