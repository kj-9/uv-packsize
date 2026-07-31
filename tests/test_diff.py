import json
from dataclasses import replace
from pathlib import Path

import pytest

from uv_packsize.baseline import (
    BaselineDistribution,
    BaselineRequirement,
    BaselineWarningSummary,
    parse_baseline_json,
)
from uv_packsize.diff import (
    MAX_BASELINE_INTEGER,
    AnalysisDiff,
    ComparisonIncompatibilityReason,
    DistributionChangeKind,
    DistributionDelta,
    IncompatibleComparisonError,
    compare_baselines,
)
from uv_packsize.models import Completeness

ROOT = Path(__file__).parents[1]


def baseline(version: int = 1):
    name = (
        "analysis-result-v1.json"
        if version == 1
        else "analysis-result-v2-existing-prefix.json"
    )
    return parse_baseline_json((ROOT / "tests" / "golden" / name).read_text())


def changed(**changes: object):
    source = json.loads(
        (ROOT / "tests" / "golden" / "analysis-result-v1.json").read_text()
    )
    source["distributions"] = changes.get("distributions", source["distributions"])
    source["totals"] = changes.get("totals", source["totals"])
    source["context"] = changes.get("context", source["context"])
    source["measurement"] = changes.get("measurement", source["measurement"])
    return parse_baseline_json(json.dumps(source))


def test_compare_baselines_full_outer_join_and_signed_totals():
    before = baseline()
    alpha = before.distributions[0]
    zeta = before.distributions[1]
    current = replace(
        before,
        global_logical_bytes=73,
        distributions=(
            replace(alpha, logical_bytes=30),
            BaselineDistribution(name="new-pkg", version="1", logical_bytes=11),
            replace(zeta, version="3.0", logical_bytes=32),
        ),
    )
    result = compare_baselines(before, current)

    assert [
        (item.name, item.kind, item.logical_bytes_delta)
        for item in result.distributions
    ] == [
        ("alpha-pkg", DistributionChangeKind.UNCHANGED, 5),
        ("new-pkg", DistributionChangeKind.ADDED, 11),
        ("zeta", DistributionChangeKind.VERSION_CHANGED, 9),
    ]
    assert result.global_logical_bytes_delta == 32
    assert result.distribution_logical_bytes_delta == 25
    assert result.global_logical_bytes_delta != result.distribution_logical_bytes_delta


def test_compare_baselines_added_removed_empty_zero_and_bounded_integers():
    before = baseline()
    current = replace(
        before,
        global_logical_bytes=MAX_BASELINE_INTEGER,
        distributions=(
            BaselineDistribution(name="aardvark", version="1", logical_bytes=0),
        ),
    )
    result = compare_baselines(before, current)

    assert [item.kind for item in result.distributions] == [
        DistributionChangeKind.ADDED,
        DistributionChangeKind.REMOVED,
        DistributionChangeKind.REMOVED,
    ]
    assert result.distributions[0].current_logical_bytes == 0
    assert result.global_logical_bytes_delta == (
        MAX_BASELINE_INTEGER - before.global_logical_bytes
    )
    assert result.distributions[1].logical_bytes_delta < 0


@pytest.mark.parametrize("left_version,right_version", [(1, 2), (2, 1), (2, 2)])
def test_existing_prefix_baselines_are_not_comparable(left_version, right_version):
    with pytest.raises(IncompatibleComparisonError) as captured:
        compare_baselines(baseline(left_version), baseline(right_version))
    assert (
        captured.value.reason
        is ComparisonIncompatibilityReason.UNSUPPORTED_EXISTING_PREFIX
    )


def test_comparison_rejects_measurement_and_every_context_field_without_leaking_values():
    source = baseline()
    with pytest.raises(IncompatibleComparisonError) as measurement:
        compare_baselines(
            source,
            replace(source, measurement=replace(source.measurement, unit="private")),
        )
    assert (
        measurement.value.reason is ComparisonIncompatibilityReason.MEASUREMENT_MISMATCH
    )

    secret = "b" * 64
    context = replace(source.resolution_context, platform_fingerprint=secret)
    with pytest.raises(IncompatibleComparisonError) as incompatible:
        compare_baselines(source, replace(source, resolution_context=context))
    assert incompatible.value.reason is ComparisonIncompatibilityReason.CONTEXT_MISMATCH
    assert secret not in str(incompatible.value)


def test_incomplete_inputs_produce_partial_incomplete_diff():
    source = baseline()
    incomplete = replace(
        source, warnings=replace(source.warnings, completeness="incomplete")
    )
    result = compare_baselines(source, incomplete)
    assert result.baseline_completeness is Completeness.INCOMPLETE
    assert result.current_completeness is Completeness.INCOMPLETE
    assert result.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize(
    "warnings",
    [
        BaselineWarningSummary(
            completeness="complete", warning_code_counts=(("missing-file", 1),)
        ),
        BaselineWarningSummary(completeness="incomplete", warning_code_counts=()),
        BaselineWarningSummary(
            completeness="complete", warning_code_counts=(("unknown", 1),)
        ),
        BaselineWarningSummary(
            completeness="complete", warning_code_counts=(("missing-file", 0),)
        ),
    ],
)
def test_forged_warning_summaries_are_rejected(warnings):
    with pytest.raises(ValueError):
        compare_baselines(replace(baseline(), warnings=warnings), baseline())


def test_forged_context_and_byte_boundaries_are_rejected():
    source = baseline()
    context = source.resolution_context
    assert context is not None
    invalid_requirement = BaselineRequirement(
        input_index=0,
        kind="named",
        name=None,
        extras=(),
        has_specifier=False,
        has_marker=False,
    )
    for forged in (
        replace(source, global_logical_bytes=MAX_BASELINE_INTEGER + 1),
        replace(
            source,
            distributions=(
                replace(
                    source.distributions[0], logical_bytes=MAX_BASELINE_INTEGER + 1
                ),
                source.distributions[1],
            ),
        ),
        replace(
            source,
            resolution_context=replace(
                context,
                platform_fingerprint="private-raw-fingerprint",
            ),
        ),
        replace(
            source,
            resolution_context=replace(context, requirements=(invalid_requirement,)),
        ),
    ):
        with pytest.raises(ValueError):
            compare_baselines(forged, source)


def test_result_repr_does_not_reflect_baseline_values():
    source = baseline()
    context = source.resolution_context
    assert context is not None
    secret_fingerprint = "a" * 64
    forged = replace(
        source,
        distributions=(
            BaselineDistribution(
                name="private-package", version="private-version", logical_bytes=0
            ),
            source.distributions[1],
        ),
        resolution_context=replace(context, platform_fingerprint=secret_fingerprint),
    )
    result = compare_baselines(forged, forged)
    rendered = repr(result)
    assert secret_fingerprint not in rendered
    assert "private-package" not in rendered
    assert "private-version" not in rendered
    assert "Baseline(" not in rendered


def test_model_rejects_forged_delta_and_diff_inputs():
    source = baseline()
    item = source.distributions[0]
    with pytest.raises(ValueError):
        DistributionDelta(
            name=item.name,
            baseline_distribution=item,
            current_distribution=item,
            kind=DistributionChangeKind.VERSION_CHANGED,
        )
    result = compare_baselines(source, source)
    with pytest.raises(ValueError):
        replace(result, distributions=tuple(reversed(result.distributions)))
    with pytest.raises(ValueError):
        compare_baselines(replace(source, schema_version=True), source)


def test_comparison_is_input_permutation_independent():
    source = baseline()
    reverse = replace(source, distributions=tuple(reversed(source.distributions)))
    with pytest.raises(ValueError):
        compare_baselines(reverse, source)
    assert compare_baselines(source, source) == compare_baselines(source, source)


def test_analysis_diff_rejects_wrong_completeness():
    result = compare_baselines(baseline(), baseline())
    with pytest.raises(ValueError):
        AnalysisDiff(
            baseline=result.baseline,
            current=result.current,
            distributions=result.distributions,
            global_logical_bytes_delta=0,
            distribution_logical_bytes_delta=0,
            baseline_completeness=Completeness.COMPLETE,
            current_completeness=Completeness.COMPLETE,
            completeness=Completeness.INCOMPLETE,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("global_logical_bytes_delta", True),
        ("global_logical_bytes_delta", MAX_BASELINE_INTEGER + 1),
        ("distribution_logical_bytes_delta", False),
        ("distribution_logical_bytes_delta", -MAX_BASELINE_INTEGER - 1),
        ("baseline_completeness", "complete"),
        ("current_completeness", "incomplete"),
        ("completeness", "complete"),
    ],
)
def test_analysis_diff_rejects_forged_signed_totals_and_plain_completeness(
    field, value
):
    result = compare_baselines(baseline(), baseline())
    with pytest.raises((TypeError, ValueError)):
        replace(result, **{field: value})
