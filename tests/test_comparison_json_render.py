import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from uv_packsize.baseline import (
    BaselineDistribution,
    BaselineWarningSummary,
    parse_baseline_json,
)
from uv_packsize.comparison_json_render import (
    _comparison_context_fingerprint,
    comparison_diff_to_json_object,
    render_comparison_json,
)
from uv_packsize.diff import MAX_BASELINE_INTEGER, compare_baselines

ROOT = Path(__file__).parents[1]


def baseline():
    return parse_baseline_json(
        (ROOT / "tests/golden/analysis-result-v1.json").read_text()
    )


def changed_diff():
    before = baseline()
    alpha, zeta = before.distributions
    current = replace(
        before,
        global_logical_bytes=73,
        distributions=(
            replace(alpha, logical_bytes=30),
            BaselineDistribution(name="new-pkg", version="1", logical_bytes=11),
            replace(zeta, version="3.0", logical_bytes=32),
        ),
    )
    return compare_baselines(before, current)


def test_render_matches_committed_golden_and_fixed_order():
    expected = (
        json.dumps(
            json.loads((ROOT / "tests/golden/comparison-result-v1.json").read_text()),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )
    rendered = render_comparison_json(changed_diff())

    assert rendered == expected
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
    document = json.loads(rendered)
    assert list(document) == [
        "schema_version",
        "measurement",
        "context",
        "baseline",
        "current",
        "changes",
        "completeness",
    ]
    assert [item["name"] for item in document["changes"]["distributions"]] == [
        "alpha-pkg",
        "new-pkg",
        "zeta",
    ]


def test_json_is_deterministic_and_context_is_private():
    before = baseline()
    context = before.resolution_context
    assert context is not None
    private = "b" * 64
    before = replace(
        before,
        resolution_context=replace(context, platform_fingerprint=private),
    )
    current = replace(before, distributions=tuple(reversed(before.distributions)))
    # A forged input order is rejected by the model; canonical valid comparisons
    # nevertheless render independently of equivalent current object identity.
    rendered = render_comparison_json(compare_baselines(before, before))

    assert private not in rendered
    assert context.python_version_fingerprint not in rendered
    assert "requirements" not in rendered
    assert render_comparison_json(compare_baselines(before, before)) == rendered
    with pytest.raises(ValueError):
        compare_baselines(before, current)


def test_context_fingerprint_is_domain_separated_deterministic_and_complete():
    context = baseline().resolution_context
    assert context is not None
    assert _comparison_context_fingerprint(context) == _comparison_context_fingerprint(
        context
    )
    requirement = context.requirements[0]
    changed_contexts = (
        replace(context, requirements=tuple(reversed(context.requirements))),
        replace(
            context,
            requirements=(
                replace(requirement, input_index=requirement.input_index + 1),
            )
            + context.requirements[1:],
        ),
        replace(
            context,
            requirements=(replace(requirement, kind="opaque"),)
            + context.requirements[1:],
        ),
        replace(
            context,
            requirements=(replace(requirement, name="changed"),)
            + context.requirements[1:],
        ),
        replace(
            context,
            requirements=(replace(requirement, extras=("changed",)),)
            + context.requirements[1:],
        ),
        replace(
            context,
            requirements=(
                replace(requirement, has_specifier=not requirement.has_specifier),
            )
            + context.requirements[1:],
        ),
        replace(
            context,
            requirements=(replace(requirement, has_marker=not requirement.has_marker),)
            + context.requirements[1:],
        ),
        replace(context, python_version_fingerprint="a" * 64),
        replace(context, platform_fingerprint="a" * 64),
        replace(context, architecture_fingerprint="a" * 64),
        replace(context, path_flavor="windows"),
        replace(context, case_rule="insensitive"),
        replace(context, uv_version_fingerprint="a" * 64),
        replace(context, build_policy="allow-build"),
        replace(context, compile_bytecode=not context.compile_bytecode),
        replace(context, extras=("changed",)),
        replace(context, index_identifiers=("changed",)),
        replace(context, resolution_strategy_fingerprint="a" * 64),
    )
    original = _comparison_context_fingerprint(context)
    assert all(
        _comparison_context_fingerprint(changed) != original
        for changed in changed_contexts
    )


def test_empty_zero_incomplete_and_nonreconciliation_shapes():
    before = baseline()
    empty = replace(before, global_logical_bytes=0, distributions=())
    document = comparison_diff_to_json_object(compare_baselines(empty, empty))
    changes = cast(dict[str, object], document["changes"])
    assert changes["distributions"] == []
    assert changes["nonreconciliation"] == {
        "present": False,
        "distribution_minus_global_logical_bytes_delta": 0,
        "reason": None,
    }

    incomplete = replace(
        before,
        warnings=BaselineWarningSummary(
            completeness="incomplete",
            warning_code_counts=(
                ("duplicate-ownership", 1),
                ("missing-file", 1),
            ),
        ),
        global_logical_bytes=before.global_logical_bytes + 1,
    )
    document = comparison_diff_to_json_object(compare_baselines(before, incomplete))
    assert document["completeness"] == "incomplete"
    changes = cast(dict[str, object], document["changes"])
    assert changes["nonreconciliation"] == {
        "present": True,
        "distribution_minus_global_logical_bytes_delta": -1,
        "reason": "duplicate-owned-files-may-be-counted-per-distribution",
    }


def test_maximum_nonreconciliation_range_is_not_clamped():
    before = baseline()
    before = replace(
        before,
        global_logical_bytes=MAX_BASELINE_INTEGER,
        distributions=(),
    )
    current = replace(
        before,
        global_logical_bytes=0,
        distributions=(
            BaselineDistribution(
                name="max", version="1", logical_bytes=MAX_BASELINE_INTEGER
            ),
        ),
    )
    document = comparison_diff_to_json_object(compare_baselines(before, current))
    changes = cast(dict[str, object], document["changes"])
    nonreconciliation = cast(dict[str, object], changes["nonreconciliation"])
    assert (
        nonreconciliation["distribution_minus_global_logical_bytes_delta"]
        == 2 * MAX_BASELINE_INTEGER
    )


@pytest.mark.parametrize("value", [None, object(), baseline()])
def test_renderer_rejects_wrong_or_forged_diff_type(value: Any):
    with pytest.raises(TypeError, match="exact AnalysisDiff"):
        comparison_diff_to_json_object(value)
    with pytest.raises(TypeError, match="exact AnalysisDiff"):
        render_comparison_json(value)


def test_renderer_rejects_forged_diff_and_lone_surrogate_without_reflection():
    before = baseline()
    current = replace(
        before,
        distributions=(replace(before.distributions[0], version="\ud800"),)
        + before.distributions[1:],
    )
    diff = compare_baselines(before, current)
    with pytest.raises(ValueError, match="invalid string") as error:
        render_comparison_json(diff)
    assert "\\ud800" not in str(error.value)

    forged = object.__new__(type(diff))
    with pytest.raises((AttributeError, TypeError, ValueError)):
        comparison_diff_to_json_object(forged)


def test_schema_is_closed_and_has_correct_large_integer_range():
    schema = json.loads((ROOT / "schemas/comparison-result-v1.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["side"]["additionalProperties"] is False
    assert schema["$defs"]["nonreconciliationInteger"]["maximum"] == (
        2 * MAX_BASELINE_INTEGER
    )
    assert schema["$defs"]["totals"]["properties"]["distribution_logical_bytes"] == {
        "type": "integer",
        "minimum": 0,
    }
    assert all(isinstance(value, dict) for value in schema["$defs"].values())
    assert schema["$defs"]["name"]["pattern"] == "^[a-z0-9]+(?:-[a-z0-9]+)*$"
    warning_constraints = schema["$defs"]["side"]["allOf"]
    assert len(warning_constraints) == 13
    assert all(
        item["minContains"] == 0 and item["maxContains"] == 1
        for item in warning_constraints
    )
    branches = schema["$defs"]["distribution"]["oneOf"]
    assert len(branches) == 3
    nonreconciliation = schema["$defs"]["nonreconciliation"]["allOf"]
    assert len(nonreconciliation) == 2

    def assert_closed_objects(value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False
                required = cast(list[str], value.get("required", ()))
                properties = cast(dict[str, object], value.get("properties", {}))
                assert set(required) == set(properties)
            for child in value.values():
                assert_closed_objects(child)
        elif isinstance(value, list):
            for child in value:
                assert_closed_objects(child)

    assert_closed_objects(schema)
