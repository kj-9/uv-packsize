"""Budget-policy mapping normalization tests without configuration I/O."""

from __future__ import annotations

from collections import UserDict

import pytest

from uv_packsize import budget_config
from uv_packsize.baseline import MAX_BASELINE_INTEGER
from uv_packsize.budget import BudgetPolicy, IncompleteBudgetPolicy
from uv_packsize.budget_config import (
    BudgetPolicyConfigError,
    BudgetPolicyConfigErrorReason,
    BudgetPolicyConfigField,
    parse_budget_policy,
)


def test_empty_mapping_is_an_explicit_immutable_no_op_policy():
    source: dict[str, object] = {}

    policy = parse_budget_policy(source)

    assert policy == BudgetPolicy()
    source["max_total_logical_bytes"] = 1
    assert policy == BudgetPolicy()


def test_known_fields_normalize_to_budget_policy():
    policy = parse_budget_policy(
        {
            "max_total_logical_bytes": 1,
            "max_increase_logical_bytes": MAX_BASELINE_INTEGER,
            "incomplete_policy": "allow-partial",
        }
    )

    assert policy == BudgetPolicy(
        max_total_logical_bytes=1,
        max_increase_logical_bytes=MAX_BASELINE_INTEGER,
        incomplete_policy=IncompleteBudgetPolicy.ALLOW_PARTIAL,
    )


@pytest.mark.parametrize(
    ("source", "reason", "field"),
    [
        (None, BudgetPolicyConfigErrorReason.INVALID_MAPPING, None),
        (UserDict(), BudgetPolicyConfigErrorReason.INVALID_MAPPING, None),
        ({"unknown": 1}, BudgetPolicyConfigErrorReason.UNKNOWN_FIELD, None),
        ({1: 1}, BudgetPolicyConfigErrorReason.INVALID_MAPPING, None),
        (
            {"max_total_logical_bytes": True},
            BudgetPolicyConfigErrorReason.INVALID_TYPE,
            BudgetPolicyConfigField.MAX_TOTAL_LOGICAL_BYTES,
        ),
        (
            {"max_increase_logical_bytes": "1"},
            BudgetPolicyConfigErrorReason.INVALID_TYPE,
            BudgetPolicyConfigField.MAX_INCREASE_LOGICAL_BYTES,
        ),
        (
            {"max_total_logical_bytes": -1},
            BudgetPolicyConfigErrorReason.OUT_OF_RANGE,
            BudgetPolicyConfigField.MAX_TOTAL_LOGICAL_BYTES,
        ),
        (
            {"max_increase_logical_bytes": MAX_BASELINE_INTEGER + 1},
            BudgetPolicyConfigErrorReason.OUT_OF_RANGE,
            BudgetPolicyConfigField.MAX_INCREASE_LOGICAL_BYTES,
        ),
        (
            {"incomplete_policy": None},
            BudgetPolicyConfigErrorReason.INVALID_TYPE,
            BudgetPolicyConfigField.INCOMPLETE_POLICY,
        ),
        (
            {"incomplete_policy": "partial"},
            BudgetPolicyConfigErrorReason.INVALID_INCOMPLETE_POLICY,
            BudgetPolicyConfigField.INCOMPLETE_POLICY,
        ),
    ],
)
def test_invalid_policy_mapping_is_sanitized(source, reason, field):
    with pytest.raises(BudgetPolicyConfigError) as caught:
        parse_budget_policy(source)

    assert caught.value.reason is reason
    assert caught.value.field is field
    assert caught.value.path == (None if field is None else field.value)


def test_invalid_mapping_does_not_reflect_unknown_keys_or_values():
    secret = "token://private.example/never-reflect"

    with pytest.raises(BudgetPolicyConfigError) as caught:
        parse_budget_policy({secret: secret})

    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
    assert caught.value.field is None
    assert caught.value.path is None


def test_unknown_key_precedes_known_field_validation_without_exposing_the_key():
    secret = "unrecognized-token://private.example/value"

    with pytest.raises(BudgetPolicyConfigError) as caught:
        parse_budget_policy({secret: object(), "max_total_logical_bytes": True})

    assert caught.value.reason is BudgetPolicyConfigErrorReason.UNKNOWN_FIELD
    assert caught.value.field is None
    assert secret not in str(caught.value)


def test_unexpected_domain_constructor_failure_has_a_distinct_sanitized_reason(
    monkeypatch,
):
    secret = "token://private.example/domain-failure"

    def fail_constructor(**_kwargs):
        raise ValueError(secret)

    monkeypatch.setattr(budget_config, "BudgetPolicy", fail_constructor)
    with pytest.raises(BudgetPolicyConfigError) as caught:
        parse_budget_policy({})

    assert caught.value.reason is BudgetPolicyConfigErrorReason.INVALID_INPUT
    assert caught.value.field is None
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


def test_exact_builtin_boundary_rejects_mapping_and_scalar_subclasses():
    class DictSubclass(dict[str, object]):
        pass

    class IntSubclass(int):
        pass

    class StringSubclass(str):
        pass

    with pytest.raises(BudgetPolicyConfigError) as mapping:
        parse_budget_policy(DictSubclass())
    assert mapping.value.reason is BudgetPolicyConfigErrorReason.INVALID_MAPPING

    with pytest.raises(BudgetPolicyConfigError) as limit:
        parse_budget_policy({"max_total_logical_bytes": IntSubclass(1)})
    assert limit.value.reason is BudgetPolicyConfigErrorReason.INVALID_TYPE

    with pytest.raises(BudgetPolicyConfigError) as policy:
        parse_budget_policy({"incomplete_policy": StringSubclass("fail")})
    assert policy.value.reason is BudgetPolicyConfigErrorReason.INVALID_TYPE

    with pytest.raises(BudgetPolicyConfigError) as enum_value:
        parse_budget_policy({"incomplete_policy": IncompleteBudgetPolicy.FAIL})
    assert enum_value.value.reason is BudgetPolicyConfigErrorReason.INVALID_TYPE


def test_outcome_is_deterministic_and_has_no_config_input_reference():
    source = {
        "max_total_logical_bytes": 17,
        "incomplete_policy": "fail",
    }

    first = parse_budget_policy(source)
    second = parse_budget_policy(dict(source))

    assert first == second
    assert first is not second
